from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..deps import Ctx, audit, current_ctx, db_anonymous
from ..security import hash_token, new_token

router = APIRouter(tags=["survey-links"])


class NewLink(BaseModel):
    role_name: str


@router.post("/survey-links", status_code=201)
def create_link(body: NewLink, ctx: Ctx = Depends(current_ctx)):
    if ctx.read_only or not ctx.company_id:
        raise HTTPException(status_code=404, detail="No encontrado")
    raw, h = new_token()
    exp = datetime.now(timezone.utc) + timedelta(days=settings.survey_link_days)
    lid = ctx.session.execute(
        text("insert into survey_link(company_id, role_name, token_hash, expires_at) values (:c,:r,:h,:x) returning id"),
        {"c": ctx.company_id, "r": body.role_name, "h": h, "x": exp}).scalar_one()
    audit(ctx, "survey_link.created", "survey_link", str(lid), ctx.company_id, role=body.role_name)
    return {"id": str(lid), "token": raw, "expires_at": exp.isoformat()}


@router.get("/survey/{token}")
def open_link(token: str, s: Session = Depends(db_anonymous)):
    row = s.execute(text("select * from auth_check_survey_link(:h)"), {"h": hash_token(token)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Enlace inválido o vencido")
    return {"company_id": str(row["company_id"]), "role_name": row["role_name"]}


@router.post("/survey/{token}/complete")
def complete(token: str, s: Session = Depends(db_anonymous)):
    # La Feature 03 guardará las respuestas aquí; hoy solo consume el enlace (un solo uso).
    ok = s.execute(text("select auth_consume_survey_link(:h)"), {"h": hash_token(token)}).scalar_one()
    if not ok:
        raise HTTPException(status_code=404, detail="Enlace inválido o vencido")
    return {"ok": True}
