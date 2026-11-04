import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..config import settings
from ..deps import NOT_FOUND, Ctx, audit, require_consultant
from ..indicators import compute

router = APIRouter(prefix="/eval", tags=["evaluation"])
SYSTEM_VERSION = "0.1.0"
# Supuesto (decisión 12): criterios de la rúbrica hasta que el consultor líder los fije.
RUBRIC = ["precision", "evidencia", "accionabilidad", "claridad", "completitud"]
GOALS = {"human_control": 1.0, "evidence": 1.0, "time_saving": 0.60, "quality": 4.2, "sus": 75.0, "top3": 0.80}


def sus_score(a: list[int]) -> float:
    """Escala de usabilidad SUS: impares (a-1), pares (5-a), suma × 2,5."""
    return round(sum((v - 1) if i % 2 == 0 else (5 - v) for i, v in enumerate(a)) * 2.5, 1)


class Baseline(BaseModel):
    task: str
    hours: float = Field(ge=0)
    with_system: bool
    case_ref: str | None = None
    notes: str | None = None


@router.post("/baseline", status_code=201)
def add_baseline(b: Baseline, ctx: Ctx = Depends(require_consultant)):
    ctx.session.execute(text("insert into baseline_measure(task, hours, with_system, case_ref, notes, measured_by) values (:t, :h, :w, :c, :n, cast(:u as uuid))"),
                        {"t": b.task, "h": b.hours, "w": b.with_system, "c": b.case_ref, "n": b.notes, "u": ctx.user_id})
    return {"ok": True}


@router.get("/baseline")
def baseline(ctx: Ctx = Depends(require_consultant)):
    return [dict(r) | {"id": str(r["id"])} for r in ctx.session.execute(text("select * from baseline_measure order by at")).mappings()]


class RefCase(BaseModel):
    name: str
    system_company_id: str | None = None
    inputs: dict = {}
    reference: dict          # {pillar_scores: {clave: puntaje}, top3: [claves]}


@router.post("/reference-cases", status_code=201)
def add_case(b: RefCase, ctx: Ctx = Depends(require_consultant)):
    if not isinstance(b.reference.get("pillar_scores"), dict) or not isinstance(b.reference.get("top3"), list):
        raise HTTPException(status_code=422, detail="El informe de referencia lleva pillar_scores y top3")
    cid = uuid.uuid4()
    ctx.session.execute(text("insert into reference_case(id, name, system_company_id, inputs, reference) values (:i, :n, cast(:s as uuid), cast(:in as jsonb), cast(:r as jsonb))"),
                        {"i": cid, "n": b.name, "s": b.system_company_id, "in": json.dumps(b.inputs), "r": json.dumps(b.reference)})
    return {"id": str(cid)}


class Rubric(BaseModel):
    case_id: str
    criterion: str
    value: int = Field(ge=1, le=5)


@router.post("/rubric", status_code=201)
def add_rubric(b: Rubric, ctx: Ctx = Depends(require_consultant)):
    if b.criterion not in RUBRIC:
        raise HTTPException(status_code=422, detail=f"Criterio no válido. Usa: {', '.join(RUBRIC)}")
    try:
        ctx.session.execute(text("insert into rubric_score(case_id, criterion, value, evaluator) values (cast(:c as uuid), :k, :v, cast(:u as uuid))"),
                            {"c": b.case_id, "k": b.criterion, "v": b.value, "u": ctx.user_id})
    except Exception:
        raise NOT_FOUND
    return {"ok": True}


class Sus(BaseModel):
    answers: list[int] = Field(min_length=10, max_length=10)


@router.post("/sus", status_code=201)
def add_sus(b: Sus, ctx: Ctx = Depends(require_consultant)):
    if not all(1 <= a <= 5 for a in b.answers):
        raise HTTPException(status_code=422, detail="Cada respuesta va de 1 a 5")
    score = sus_score(b.answers)
    ctx.session.execute(text("insert into sus_response(user_id, answers, score) values (cast(:u as uuid), :a, :s)"), {"u": ctx.user_id, "a": b.answers, "s": score})
    return {"score": score}


def _case_comparison(s, case) -> dict:
    ref = case["reference"]
    out = {"case": case["name"], "case_id": str(case["id"]), "compared": False}
    rubric = s.execute(text("select avg(value) from rubric_score where case_id = :c"), {"c": case["id"]}).scalar()
    out["rubric_avg"] = round(float(rubric), 2) if rubric is not None else None
    if not case["system_company_id"]:
        return out
    rep = s.execute(text("select id from report where company_id = :c and status='published' order by version desc limit 1"), {"c": case["system_company_id"]}).scalar()
    if not rep:
        return out
    sys_scores = {r.pillar: float(r.score) for r in s.execute(text("select pillar, score from pillar_score where report_id = :r"), {"r": rep})}
    diffs = {p: round(abs(sys_scores[p] - float(v)), 2) for p, v in ref["pillar_scores"].items() if p in sys_scores}
    sys_top3 = [p for p, _ in sorted(sys_scores.items(), key=lambda kv: kv[1])[:3]]
    overlap = len(set(sys_top3) & set(ref["top3"])) / max(len(ref["top3"]), 1)
    out.update(compared=True, pillar_score_diff=diffs, avg_pillar_diff=round(sum(diffs.values()) / len(diffs), 2) if diffs else None,
               system_top3=sys_top3, reference_top3=ref["top3"], top3_overlap=round(overlap, 3))
    return out


def _results(s) -> dict:
    ind = compute(s)
    base = {w: s.execute(text("select avg(hours) from baseline_measure where with_system = :w"), {"w": w}).scalar() for w in (False, True)}
    saving = round(1 - float(base[True]) / float(base[False]), 3) if base[False] and base[True] is not None and float(base[False]) > 0 else None
    quality = s.execute(text("select avg(value) from rubric_score")).scalar()
    sus = s.execute(text("select avg(score) from sus_response")).scalar()
    cases = [_case_comparison(s, c) for c in s.execute(text("select * from reference_case order by created_at, id")).mappings()]
    top3 = [c["top3_overlap"] for c in cases if c["compared"]]
    metrics = {
        "human_control": ind["human_control"]["share"], "evidence": ind["evidence"]["share"], "time_saving": saving,
        "quality": round(float(quality), 2) if quality is not None else None, "sus": round(float(sus), 1) if sus is not None else None,
        "top3": round(sum(top3) / len(top3), 3) if top3 else None,
    }
    return {"metrics": metrics, "goals": GOALS,
            "met": {k: (None if metrics[k] is None else metrics[k] >= GOALS[k]) for k in GOALS},
            "indicators": ind, "cases": cases, "baseline_hours": {"without_system": float(base[False]) if base[False] is not None else None,
                                                                 "with_system": float(base[True]) if base[True] is not None else None}}


@router.get("/summary")
def summary(ctx: Ctx = Depends(require_consultant)):
    return _results(ctx.session)


@router.post("/runs", status_code=201)
def run(ctx: Ctx = Depends(require_consultant)):
    """Congela los indicadores con la versión del sistema y de la configuración que los produjo (09-R8)."""
    results = json.loads(json.dumps(_results(ctx.session), default=str))
    meth = ctx.session.execute(text("select version from methodology where active")).scalar()
    config = {"llm_provider": settings.llm_provider, "model": settings.anthropic_model if settings.llm_provider == "anthropic" else None,
              "methodology_version": meth}
    rid = uuid.uuid4()
    ctx.session.execute(text("insert into eval_run(id, system_version, config, results, created_by) values (:i, :v, cast(:c as jsonb), cast(:r as jsonb), cast(:u as uuid))"),
                        {"i": rid, "v": SYSTEM_VERSION, "c": json.dumps(config), "r": json.dumps(results), "u": ctx.user_id})
    audit(ctx, "eval.run", "eval_run", str(rid), None)
    return {"id": str(rid), "system_version": SYSTEM_VERSION, "config": config, "results": results}


@router.get("/runs")
def runs(ctx: Ctx = Depends(require_consultant)):
    rows = ctx.session.execute(text("select id, system_version, config, results->'metrics' as metrics, at from eval_run order by at desc")).mappings().all()
    return [dict(r) | {"id": str(r["id"])} for r in rows]


@router.get("/runs/{run_id}/report")
def run_report(run_id: str, ctx: Ctx = Depends(require_consultant)):
    """Informe de resultados: caso por caso, la salida del sistema frente al entregable humano."""
    row = ctx.session.execute(text("select * from eval_run where id = cast(:i as uuid)"), {"i": run_id}).mappings().first()
    if not row:
        raise NOT_FOUND
    return {"system_version": row["system_version"], "config": row["config"], "at": row["at"], **row["results"]}
