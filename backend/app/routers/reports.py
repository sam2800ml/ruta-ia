import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text

from ..deps import NOT_FOUND, Ctx, audit, current_ctx
from ..diagnosis import generate, load_report
from ..pdf import report_pdf
from .company_profile import own_company_id

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=202)
def request_report(ctx: Ctx = Depends(current_ctx)):
    """«Generar diagnóstico». Con encuestas parciales se puede generar; el informe declara cuántos roles lo respaldan (03-R9)."""
    if ctx.read_only or not ctx.company_id:
        raise NOT_FOUND
    cid = ctx.company_id
    done = ctx.session.execute(text("select count(*) from survey where status='complete' and company_id = cast(:c as uuid)"), {"c": cid}).scalar()
    if not done:
        raise HTTPException(status_code=422, detail="Se necesita al menos una encuesta completa")
    state = ctx.session.execute(text("select * from company_report_state(cast(:c as uuid))"), {"c": cid}).mappings().first()
    if state and state["status"] == "generating":
        raise HTTPException(status_code=409, detail="Ya hay un diagnóstico en proceso")
    version = (state["version"] if state else 0) + 1
    rid = uuid.uuid4()  # sin RETURNING: la empresa no puede leer informes que aún no están publicados
    ctx.session.execute(
        text("insert into report(id, company_id, version, status, requested_by) values (:i, cast(:c as uuid), :v, 'generating', cast(:u as uuid))"),
        {"i": rid, "c": cid, "v": version, "u": ctx.user_id})
    audit(ctx, "report.requested", "report", str(rid), cid, version=version)
    ctx.after_commit.append(lambda: generate(cid, str(rid)))
    return {"id": str(rid), "version": version, "status": "generating"}


@router.get("/state")
def state(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    row = ctx.session.execute(text("select * from company_report_state(cast(:c as uuid))"), {"c": cid}).mappings().first()
    pub = ctx.session.execute(text("select version, published_at from report where status='published' and company_id = cast(:c as uuid) "
                                   "order by version desc limit 1"), {"c": cid}).mappings().first()
    return {"latest": dict(row) | {"id": str(row["id"])} if row else None, "published": dict(pub) if pub else None}


def _published_id(ctx: Ctx, company_id: str | None) -> str:
    cid = own_company_id(ctx, company_id)
    rid = ctx.session.execute(text("select id from report where status='published' and company_id = cast(:c as uuid) order by version desc limit 1"),
                              {"c": cid}).scalar()
    if not rid:
        raise NOT_FOUND
    return str(rid)


@router.get("/published")
def published(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    return load_report(ctx.session, _published_id(ctx, company_id))


@router.get("/published/pdf")
def published_pdf(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    r = load_report(ctx.session, _published_id(ctx, company_id))
    audit_ok = ctx.company_id is not None and not ctx.read_only
    if audit_ok:
        audit(ctx, "report.exported", "report", r["id"], ctx.company_id)
    return Response(report_pdf(r), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="diagnostico-v{r["version"]}.pdf"'})
