from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from ..config import settings
from ..deps import NOT_FOUND, Ctx, audit, current_ctx, require_consultant
from ..security import new_token

router = APIRouter(prefix="/companies", tags=["companies"])


class NewCompany(BaseModel):
    name: str
    nit: str | None = None
    admin_email: EmailStr


@router.post("", status_code=201)
def invite_company(body: NewCompany, ctx: Ctx = Depends(require_consultant)):
    s = ctx.session
    cid = s.execute(text("insert into company(name, nit) values (:n, :nit) returning id"),
                    {"n": body.name, "nit": body.nit}).scalar_one()
    raw, h = new_token()
    exp = datetime.now(timezone.utc) + timedelta(days=settings.invitation_days)
    s.execute(text("insert into invitation(company_id, email, token_hash, expires_at) values (:c,:e,:h,:x)"),
              {"c": cid, "e": body.admin_email, "h": h, "x": exp})
    audit(ctx, "company.invited", "company", str(cid), str(cid), email=body.admin_email)
    # El envío real del correo llega con la Feature 03; mientras tanto el token se devuelve al consultor.
    return {"id": str(cid), "status": "invited", "invitation_token": raw}


@router.get("")
def list_companies(ctx: Ctx = Depends(current_ctx)):
    rows = ctx.session.execute(text("select id, name, nit, status from company order by name")).mappings().all()
    return [{**r, "id": str(r["id"])} for r in rows]


@router.get("/{company_id}")
def get_company(company_id: str, ctx: Ctx = Depends(current_ctx)):
    try:
        row = ctx.session.execute(text("select id, name, nit, status from company where id = cast(:i as uuid)"),
                                  {"i": company_id}).mappings().first()
    except Exception:
        raise NOT_FOUND
    if not row:
        raise NOT_FOUND  # misma respuesta exista o no en otra empresa
    return {**row, "id": str(row["id"])}
