import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..deps import NOT_FOUND, Ctx, audit, require_consultant
from ..indicators import compute

router = APIRouter(prefix="/admin", tags=["admin"])
PILLARS = {"strategy", "infrastructure", "data", "governance", "talent", "culture"}


def _uuid(v: str) -> bool:
    try:
        uuid.UUID(v); return True
    except ValueError:
        return False


@router.get("/dashboard")
def dashboard(ctx: Ctx = Depends(require_consultant)):
    s = ctx.session
    total = s.execute(text("select count(*) from company")).scalar()
    latest = """select distinct on (company_id) company_id, id, average from report where status='published' order by company_id, version desc"""
    avg = s.execute(text(f"select avg(average) from ({latest}) x")).scalar()
    pillars = s.execute(text(f"""select p.pillar, avg(p.score) as avg, count(*) as n from pillar_score p
        join ({latest}) l on l.id = p.report_id where p.review_status in ('accepted','edited') group by p.pillar order by avg(p.score)""")).mappings().all()
    labels = {p["key"]: p["label"] for p in s.execute(text("select pillars from methodology where active")).scalar_one()}
    return {
        "active_companies": s.execute(text("select count(*) from company where status='active'")).scalar(),
        "reviews_pending": s.execute(text("select count(*) from report where status='in_review'")).scalar(),
        "avg_maturity": round(float(avg), 2) if avg is not None else None,
        "approved_use_cases": s.execute(text("select count(*) from use_case where status in ('approved','pilot')")).scalar(),
        "pillar_average": [{"pillar": p["pillar"], "label": labels.get(p["pillar"]), "avg": round(float(p["avg"]), 2),
                            "supported_by": p["n"], "of": total, "low": float(p["avg"]) < 2} for p in pillars],
        "companies_with_diagnosis": s.execute(text(f"select count(*) from ({latest}) x")).scalar(),
    }


@router.get("/companies")
def companies(q: str | None = None, ctx: Ctx = Depends(require_consultant)):
    rows = ctx.session.execute(text("""
      select c.id, c.name, c.nit, c.sector, c.status,
        (select r.level from report r where r.company_id = c.id and r.status='published' order by version desc limit 1) as level,
        (select r.average from report r where r.company_id = c.id and r.status='published' order by version desc limit 1) as average,
        exists (select 1 from document d where d.company_id = c.id and d.status='processed') as has_docs,
        exists (select 1 from survey sv where sv.company_id = c.id and sv.status='complete') as has_surveys,
        exists (select 1 from report r where r.company_id = c.id and r.status='published') as has_report,
        exists (select 1 from strategy st where st.company_id = c.id and st.status='closed') as has_strategy,
        exists (select 1 from use_case u where u.company_id = c.id and u.status <> 'proposed') as has_cases,
        (select max(at) from audit_log a where a.company_id = c.id) as last_activity
      from company c where (cast(:q as text) is null or c.name ilike '%'||cast(:q as text)||'%' or c.nit ilike '%'||cast(:q as text)||'%') order by c.name"""), {"q": q}).mappings().all()
    out = []
    for r in rows:
        stage = ("Casos de uso" if r["has_cases"] else "Estrategia" if r["has_strategy"] else "Informe" if r["has_report"]
                 else "Diagnóstico" if r["has_surveys"] else "Documentos" if r["has_docs"] else "Invitada" if r["status"] == "invited" else "Inicio")
        progress = sum([r["has_docs"], r["has_report"], r["has_strategy"], r["has_cases"]])
        out.append({"id": str(r["id"]), "name": r["name"], "nit": r["nit"], "sector": r["sector"], "stage": stage,
                    "maturity": {"level": r["level"], "average": float(r["average"])} if r["level"] else None,
                    "progress": f"{progress} de 4", "last_activity": r["last_activity"]})
    return out


# ---- Banco de preguntas (08-R6, R7) ----
class Q(BaseModel):
    text: str = Field(min_length=5)
    pillar: str
    roles: list[str] = []
    weight: float = Field(default=1, gt=0)


def _q_view(r) -> dict:
    return {"id": str(r["id"]), "key": str(r["key"]), "version": r["version"], "text": r["text"], "pillar": r["pillar"],
            "roles": r["roles"] or ["Todos"], "answer_type": "Escala de 1 a 5", "active": r["active"],
            "contribution": f"Peso {float(r['weight']):g} en el promedio del pilar", "weight": float(r["weight"])}


@router.get("/questions")
def questions(pillar: str | None = None, role: str | None = None, ctx: Ctx = Depends(require_consultant)):
    rows = ctx.session.execute(text(
        "select * from question where active and (cast(:p as text) is null or pillar = cast(:p as text)) and (cast(:r as text) is null or roles = '{}' or cast(:r as text) = any(roles)) order by pillar, created_at"),
        {"p": pillar, "r": role}).mappings().all()
    return [_q_view(r) for r in rows]


@router.post("/questions", status_code=201)
def add_question(body: Q, ctx: Ctx = Depends(require_consultant)):
    if body.pillar not in PILLARS:
        raise HTTPException(status_code=422, detail="Pilar desconocido")
    r = ctx.session.execute(text("insert into question(text, pillar, roles, weight) values (:t, :p, :r, :w) returning *"),
                            {"t": body.text, "p": body.pillar, "r": body.roles, "w": body.weight}).mappings().one()
    return _q_view(r)


@router.put("/questions/{key}")
def edit_question(key: str, body: Q, ctx: Ctx = Depends(require_consultant)):
    """Editar crea una versión nueva; las encuestas ya enviadas conservan la suya."""
    if body.pillar not in PILLARS:
        raise HTTPException(status_code=422, detail="Pilar desconocido")
    cur = ctx.session.execute(text("select * from question where key = cast(:k as uuid) and active"), {"k": key}).mappings().first() if _uuid(key) else None
    if not cur:
        raise NOT_FOUND
    ctx.session.execute(text("update question set active=false where id = :i"), {"i": cur["id"]})
    r = ctx.session.execute(text("insert into question(key, version, text, pillar, roles, weight) values (cast(:k as uuid), :v, :t, :p, :r, :w) returning *"),
                            {"k": key, "v": cur["version"] + 1, "t": body.text, "p": body.pillar, "r": body.roles, "w": body.weight}).mappings().one()
    audit(ctx, "question.edited", "question", key, None, version=cur["version"] + 1)
    return _q_view(r)


@router.delete("/questions/{key}")
def retire_question(key: str, ctx: Ctx = Depends(require_consultant)):
    n = ctx.session.execute(text("update question set active=false where key = cast(:k as uuid) and active"), {"k": key}).rowcount if _uuid(key) else 0
    if not n:
        raise NOT_FOUND
    return {"ok": True}


# ---- Metodología (08-R8). Supuesto: el equipo la edita desde la plataforma, con versiones. ----
class Method(BaseModel):
    levels: list[dict]
    thresholds: list[float]
    formula: str


@router.get("/methodology")
def methodology(ctx: Ctx = Depends(require_consultant)):
    rows = ctx.session.execute(text(
        "select m.*, (select count(*) from report r where r.methodology_version = m.version) as reports from methodology m order by version desc")).mappings().all()
    return [{**r, "created_at": r["created_at"]} for r in rows]


@router.post("/methodology", status_code=201)
def new_methodology(body: Method, ctx: Ctx = Depends(require_consultant)):
    if len(body.levels) != 5 or len(body.thresholds) != 4 or body.thresholds != sorted(body.thresholds):
        raise HTTPException(status_code=422, detail="Se requieren 5 niveles y 4 cortes ascendentes")
    cur = ctx.session.execute(text("select version, pillars from methodology where active")).mappings().one()
    ctx.session.execute(text("update methodology set active=false where active"))
    ctx.session.execute(text("insert into methodology(version, pillars, levels, thresholds, formula, active) values (:v, cast(:p as jsonb), cast(:l as jsonb), cast(:t as jsonb), :f, true)"),
                        {"v": cur["version"] + 1, "p": json.dumps(cur["pillars"]), "l": json.dumps(body.levels), "t": json.dumps(body.thresholds), "f": body.formula})
    audit(ctx, "methodology.published", "methodology", str(cur["version"] + 1), None)
    return {"version": cur["version"] + 1}


@router.get("/analytics")
def analytics(ctx: Ctx = Depends(require_consultant)):
    return compute(ctx.session)
