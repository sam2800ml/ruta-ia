from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from ..deps import NOT_FOUND, Ctx, audit, require_consultant
from ..diagnosis import load_report, verify_evidence

router = APIRouter(prefix="/review", tags=["review"])
TABLES = {"pillar": "pillar_score", "finding": "finding", "recommendation": "recommendation"}


@router.get("/queue")
def queue(ctx: Ctx = Depends(require_consultant)):
    rows = ctx.session.execute(text(
        "select r.id, r.version, r.created_at, c.id as company_id, c.name, c.sector, "
        " (select count(*) from finding f where f.report_id = r.id) as findings, "
        " (select count(*) from finding f where f.report_id = r.id and f.evidence_status = 'insuficiente') as sin_evidencia, "
        " (select count(*) from finding f where f.report_id = r.id and f.kind = 'contradiccion') as contradicciones "
        "from report r join company c on c.id = r.company_id where r.status = 'in_review' order by r.created_at")).mappings().all()
    return [{**r, "id": str(r["id"]), "company_id": str(r["company_id"])} for r in rows]


def _progress(ctx: Ctx, rid: str) -> dict:
    total = done = 0
    for t in TABLES.values():
        a, b = ctx.session.execute(text(f"select count(*), count(*) filter (where review_status <> 'pending') from {t} where report_id = cast(:r as uuid)"),
                                   {"r": rid}).one()
        total += a; done += b
    return {"reviewed": done, "total": total}


@router.get("/{report_id}")
def detail(report_id: str, ctx: Ctx = Depends(require_consultant)):
    try:
        r = load_report(ctx.session, report_id)
    except Exception:
        raise NOT_FOUND
    if not r:
        raise NOT_FOUND
    return {**r, "progress": _progress(ctx, report_id)}


class Decision(BaseModel):
    action: str                      # accept | edit | reject
    reason: str | None = None
    new_text: str | None = None


@router.post("/{report_id}/blocks/{block_type}/{block_id}")
def decide(report_id: str, block_type: str, block_id: str, body: Decision, ctx: Ctx = Depends(require_consultant)):
    if block_type not in TABLES or body.action not in ("accept", "edit", "reject"):
        raise HTTPException(status_code=422, detail="Acción o bloque no válido")
    rep = ctx.session.execute(text("select status, company_id from report where id = cast(:r as uuid)"), {"r": report_id}).mappings().first()
    if not rep:
        raise NOT_FOUND
    if rep["status"] != "in_review":
        raise HTTPException(status_code=409, detail="El informe no está en revisión")
    tbl = TABLES[block_type]
    row = ctx.session.execute(text(f"select * from {tbl} where id = cast(:b as uuid) and report_id = cast(:r as uuid)"),
                              {"b": block_id, "r": report_id}).mappings().first()
    if not row:
        raise NOT_FOUND
    old = {"pillar": lambda r: f"{r['pillar']}: {r['score']}", "finding": lambda r: r["description"], "recommendation": lambda r: r["text"]}[block_type](row)
    new_text = None
    if body.action == "reject":
        if not (body.reason or "").strip():
            raise HTTPException(status_code=422, detail="Rechazar exige un motivo")
        ctx.session.execute(text(f"update {tbl} set review_status='rejected' where id = cast(:b as uuid)"), {"b": block_id})
    elif body.action == "edit":
        new_text = (body.new_text or "").strip()
        if block_type == "pillar":
            raise HTTPException(status_code=422, detail="El puntaje sale de reglas fijas: no se edita. Rechaza el bloque si no aplica.")
        if not new_text:
            raise HTTPException(status_code=422, detail="Editar exige el texto nuevo")
        col = "text" if block_type == "recommendation" else "description"
        extra = ", evidence_status = 'revisada'" if block_type == "finding" and row["evidence_status"] == "insuficiente" else ""
        ctx.session.execute(text(f"update {tbl} set {col} = :t, review_status='edited'{extra} where id = cast(:b as uuid)"), {"t": new_text, "b": block_id})
    else:
        if block_type == "finding" and row["evidence_status"] == "insuficiente":
            raise HTTPException(status_code=409, detail="Un hallazgo sin evidencia suficiente no se acepta tal cual: edítalo o recházalo")
        ctx.session.execute(text(f"update {tbl} set review_status='accepted' where id = cast(:b as uuid)"), {"b": block_id})
    ctx.session.execute(
        text("insert into review_decision(company_id, report_id, block_type, block_id, action, reason, old_text, new_text, actor_id) "
             "values (cast(:c as uuid), cast(:r as uuid), :bt, cast(:b as uuid), :a, :re, :o, :n, cast(:u as uuid))"),
        {"c": rep["company_id"], "r": report_id, "bt": block_type, "b": block_id, "a": body.action, "re": body.reason,
         "o": old, "n": new_text, "u": ctx.user_id})
    return {"ok": True, "progress": _progress(ctx, report_id)}


@router.get("/{report_id}/blocks/{block_type}/{block_id}/history")
def history(report_id: str, block_type: str, block_id: str, ctx: Ctx = Depends(require_consultant)):
    rows = ctx.session.execute(
        text("select d.action, d.reason, d.old_text, d.new_text, d.at, u.email as actor from review_decision d "
             "join app_user u on u.id = d.actor_id where d.report_id = cast(:r as uuid) and d.block_type = :t and d.block_id = cast(:b as uuid) order by d.id"),
        {"r": report_id, "t": block_type, "b": block_id}).mappings().all()
    return [dict(r) for r in rows]


@router.post("/{report_id}/publish")
def publish(report_id: str, ctx: Ctx = Depends(require_consultant)):
    rep = ctx.session.execute(text("select status, company_id from report where id = cast(:r as uuid)"), {"r": report_id}).mappings().first()
    if not rep:
        raise NOT_FOUND
    if rep["status"] != "in_review":
        raise HTTPException(status_code=409, detail="El informe no está en revisión")
    prog = _progress(ctx, report_id)
    if prog["reviewed"] < prog["total"]:
        raise HTTPException(status_code=409, detail=f"Faltan bloques por decidir ({prog['reviewed']} de {prog['total']} revisados)")
    # Volver a comprobar la evidencia contra su fuente antes de publicar.
    for f in ctx.session.execute(text("select id, evidence_status from finding where report_id = cast(:r as uuid) and review_status in ('accepted','edited')"),
                                 {"r": report_id}).mappings():
        evs = ctx.session.execute(text("select source_type, source_id::text as source_id, quote from evidence where finding_id = :f"), {"f": f["id"]}).mappings().all()
        if f["evidence_status"] == "verificada" and not (evs and all(verify_evidence(ctx.session, dict(e)) for e in evs)):
            raise HTTPException(status_code=409, detail="Un hallazgo aceptado ya no tiene su evidencia en la fuente")
        if f["evidence_status"] == "insuficiente":
            raise HTTPException(status_code=409, detail="Hay hallazgos sin evidencia suficiente sin resolver")
    ctx.session.execute(text("update report set status='published', published_at=now(), published_by=cast(:u as uuid) where id = cast(:r as uuid)"),
                        {"u": ctx.user_id, "r": report_id})
    audit(ctx, "report.published", "report", report_id, str(rep["company_id"]))
    return {"status": "published"}


@router.post("/{report_id}/return-to-draft")
def return_to_draft(report_id: str, ctx: Ctx = Depends(require_consultant)):
    r = ctx.session.execute(text("update report set status='draft' where id = cast(:r as uuid) and status='in_review' returning company_id"),
                            {"r": report_id}).first()
    if not r:
        raise HTTPException(status_code=409, detail="El informe no está en revisión")
    audit(ctx, "report.returned_to_draft", "report", report_id, str(r[0]))
    return {"status": "draft"}
