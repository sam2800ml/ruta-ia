import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..deps import NOT_FOUND, Ctx, audit, current_ctx, require_consultant
from .company_profile import own_company_id

router = APIRouter(prefix="/use-cases", tags=["use-cases"])
LOCKED = "Se habilita cuando la estrategia se cierre"
IMPACT_CUTS = [200, 600, 1200, 2400]       # horas al año que separan los puntajes 1 a 5 (decisión 11, supuesto)
LEY = "Trata datos personales: aplica la Ley 1581 de 2012."


def hours_per_year(volume, minutes) -> float | None:
    """Fórmula visible: casos al mes × minutos ahorrados ÷ 60 × 12. Con 400 y 15 → 1.200 h/año."""
    if volume is None or minutes is None:
        return None
    return round(float(volume) * float(minutes) / 60 * 12, 1)


def impact_score(hours: float | None) -> int | None:
    return None if hours is None else 1 + sum(1 for c in IMPACT_CUTS if hours >= c)


def complexity(legal: int, ethic: int, infra: int) -> float:
    return round((legal + ethic + infra) / 3, 1)


def zone(impact: int | None, cx: float) -> str | None:
    if impact is None:
        return None
    if impact >= 3:
        return "estrategico" if cx >= 3 else "quick_win"
    return "reconsiderar" if cx >= 3 else "mejoras_menores"


def _view(r: dict) -> dict:
    h = hours_per_year(r["volume_per_month"], r["minutes_saved"])
    imp = impact_score(h)
    cx = complexity(r["legal"], r["ethic"], r["infra"])
    return {"id": str(r["id"]), "name": r["name"], "area": r["area"], "status": r["status"], "risk": r["risk"],
            "indicator": r["indicator"], "baseline": r["baseline"], "target": r["target"], "tech": r["tech"],
            "personal_data": r["personal_data"], "law_note": LEY if r["personal_data"] else None,
            "ai_proposed": r["ai_proposed"],
            "complexity": cx, "complexity_parts": {"legal": r["legal"], "ethic": r["ethic"], "infra": r["infra"]},
            "complexity_notes": {"legal": r["legal_note"], "ethic": r["ethic_note"], "infra": r["infra_note"]},
            "assumptions": {"volume_per_month": float(r["volume_per_month"]) if r["volume_per_month"] is not None else None,
                            "minutes_saved": float(r["minutes_saved"]) if r["minutes_saved"] is not None else None},
            "formula": "casos al mes × minutos ahorrados ÷ 60 × 12", "hours_per_year": h, "impact": imp, "zone": zone(imp, cx),
            "approved_at": r["approved_at"], "label": "Puntajes y estimaciones propuestos por IA; el consultor puede editarlos" if r["ai_proposed"] else None}


def _enabled(ctx: Ctx, cid: str) -> bool:
    return bool(ctx.session.execute(text("select 1 from strategy where status='closed' and company_id = cast(:c as uuid)"), {"c": cid}).first())


def _uuid(v: str) -> bool:
    try:
        uuid.UUID(v); return True
    except ValueError:
        return False


class Case(BaseModel):
    name: str
    area: str
    risk: str = "limitado"
    indicator: str | None = None
    baseline: str | None = None
    target: str | None = None
    tech: str | None = None
    personal_data: bool = False
    legal: int = Field(ge=1, le=5)
    ethic: int = Field(ge=1, le=5)
    infra: int = Field(ge=1, le=5)
    legal_note: str
    ethic_note: str
    infra_note: str
    volume_per_month: float | None = None
    minutes_saved: float | None = None


def _validate(c: Case) -> None:
    if c.risk not in ("minimo", "limitado", "alto"):
        raise HTTPException(status_code=422, detail="Riesgo no válido")
    if not all(n.strip() for n in (c.legal_note, c.ethic_note, c.infra_note)):
        raise HTTPException(status_code=422, detail="Cada subpuntaje de complejidad lleva su justificación")


@router.get("")
def portfolio(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    if not _enabled(ctx, cid):
        return {"enabled": False, "locked_message": LOCKED, "cases": []}
    rows = ctx.session.execute(text("select * from use_case where company_id = cast(:c as uuid) order by created_at"), {"c": cid}).mappings().all()
    cases = [_view(dict(r)) for r in rows]
    for i, c in enumerate(cases, start=1):
        c["n"] = i
    return {"enabled": True, "cases": cases,
            "zones": {z: [c["n"] for c in cases if c["zone"] == z] for z in ("quick_win", "estrategico", "mejoras_menores", "reconsiderar")}}


@router.post("", status_code=201)
def create(body: Case, ctx: Ctx = Depends(current_ctx)):
    if ctx.read_only or not ctx.company_id:
        raise NOT_FOUND
    if not _enabled(ctx, ctx.company_id):
        raise HTTPException(status_code=423, detail=LOCKED)
    _validate(body)
    cid = uuid.uuid4()
    ctx.session.execute(text(
        "insert into use_case(id, company_id, name, area, risk, indicator, baseline, target, tech, personal_data, legal, ethic, infra, "
        "legal_note, ethic_note, infra_note, volume_per_month, minutes_saved, ai_proposed, created_by, source) "
        "values (:i, cast(:c as uuid), :name, :area, :risk, :indicator, :baseline, :target, :tech, :personal_data, :legal, :ethic, :infra, "
        ":legal_note, :ethic_note, :infra_note, :volume_per_month, :minutes_saved, false, cast(:u as uuid), 'manual')"),
        {**body.model_dump(), "i": cid, "c": ctx.company_id, "u": ctx.user_id})
    audit(ctx, "use_case.created", "use_case", str(cid), ctx.company_id)
    return {"id": str(cid)}


@router.post("/from-opportunities", status_code=201)
def from_opportunities(ctx: Ctx = Depends(current_ctx)):
    """Las oportunidades guardadas en la estrategia se vuelven casos «propuestos» (decisión 10, supuesto: la fuente es la conversación)."""
    if ctx.read_only or not ctx.company_id:
        raise NOT_FOUND
    cid = ctx.company_id
    if not _enabled(ctx, cid):
        raise HTTPException(status_code=423, detail=LOCKED)
    items = ctx.session.execute(text(
        "select key, text from strategy_item where status='active' and stage='oportunidades' and company_id = cast(:c as uuid) "
        "and key not in (select source_item_key from use_case where source_item_key is not null)"), {"c": cid}).mappings().all()
    note = "Estimación inicial propuesta por IA: pendiente de revisión por el consultor."
    for it in items:
        ctx.session.execute(text(
            "insert into use_case(company_id, name, area, legal, ethic, infra, legal_note, ethic_note, infra_note, source, source_item_key, created_by) "
            "values (cast(:c as uuid), :n, 'Por definir', 3, 3, 3, :note, :note, :note, 'opportunity', :k, cast(:u as uuid))"),
            {"c": cid, "n": it["text"][:120], "note": note, "k": it["key"], "u": ctx.user_id})
    return {"created": len(items)}


@router.get("/bias")
def bias_report(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    """Distribución de casos y puntajes por área, para detectar si el criterio favorece a alguna (constitución, 10)."""
    cid = own_company_id(ctx, company_id)
    rows = [_view(dict(r)) for r in ctx.session.execute(text("select * from use_case where company_id = cast(:c as uuid)"), {"c": cid}).mappings()]
    areas: dict[str, list[dict]] = {}
    for r in rows:
        areas.setdefault(r["area"], []).append(r)
    out = []
    for area, cs in sorted(areas.items()):
        imps = [c["impact"] for c in cs if c["impact"] is not None]
        out.append({"area": area, "cases": len(cs), "avg_impact": round(sum(imps) / len(imps), 2) if imps else None,
                    "avg_complexity": round(sum(c["complexity"] for c in cs) / len(cs), 2),
                    "approved": sum(1 for c in cs if c["status"] != "proposed")})
    return {"areas": out, "total": len(rows)}


@router.get("/export.csv")
def export_csv(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    """Hoja de ruta: todos los casos con su estado."""
    cid = own_company_id(ctx, company_id)
    rows = [_view(dict(r)) for r in ctx.session.execute(text("select * from use_case where company_id = cast(:c as uuid) order by created_at"), {"c": cid}).mappings()]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Caso", "Área", "Estado", "Riesgo", "Impacto (1-5)", "Complejidad", "Horas al año", "Indicador", "Línea base", "Meta"])
    for r in rows:
        w.writerow([r["name"], r["area"], r["status"], r["risk"], r["impact"], r["complexity"], r["hours_per_year"], r["indicator"], r["baseline"], r["target"]])
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="hoja-de-ruta.csv"'})


@router.get("/{case_id}")
def detail(case_id: str, company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    row = ctx.session.execute(text("select * from use_case where id = cast(:i as uuid)"), {"i": case_id}).mappings().first() if _uuid(case_id) else None
    if not row:
        raise NOT_FOUND
    return _view(dict(row))


@router.put("/{case_id}")
def update(case_id: str, body: Case, ctx: Ctx = Depends(current_ctx)):
    """La empresa edita casos «propuestos» (y recalcula el impacto cambiando supuestos); el consultor edita cualquiera."""
    if ctx.read_only:
        raise NOT_FOUND
    _validate(body)
    data = body.model_dump()
    sets = ", ".join(f"{k} = :{k}" for k in data)
    n = ctx.session.execute(text(f"update use_case set {sets}, ai_proposed = false where id = cast(:i as uuid)"), {**data, "i": case_id}).rowcount if _uuid(case_id) else 0
    if not n:
        raise NOT_FOUND   # no existe, es de otra empresa o ya no es editable por la empresa
    audit(ctx, "use_case.updated", "use_case", case_id, ctx.company_id)
    return detail(case_id, None, ctx)


class Status(BaseModel):
    status: str


@router.post("/{case_id}/status")
def set_status(case_id: str, body: Status, ctx: Ctx = Depends(require_consultant)):
    """Aprobar o pasar a piloto exige aprobación registrada del consultor (07-R8)."""
    if body.status not in ("proposed", "approved", "pilot"):
        raise HTTPException(status_code=422, detail="Estado no válido")
    row = ctx.session.execute(text("select company_id, status from use_case where id = cast(:i as uuid)"), {"i": case_id}).mappings().first() if _uuid(case_id) else None
    if not row:
        raise NOT_FOUND
    if body.status == "pilot" and row["status"] != "approved":
        raise HTTPException(status_code=409, detail="Solo un caso aprobado pasa a piloto")
    ctx.session.execute(text("update use_case set status = :s, approved_by = case when :s = 'proposed' then null else coalesce(approved_by, cast(:u as uuid)) end, "
                             "approved_at = case when :s = 'proposed' then null else coalesce(approved_at, now()) end where id = cast(:i as uuid)"),
                        {"s": body.status, "u": ctx.user_id, "i": case_id})
    audit(ctx, f"use_case.{body.status}", "use_case", case_id, str(row["company_id"]), previous=row["status"])
    return {"status": body.status}
