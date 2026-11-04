"""Contexto de cada petición: quién es y qué empresa ve, fijado dentro de la transacción."""
from dataclasses import dataclass, field
from typing import Iterator

import threading

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .db import engine
from .security import read_jwt

def run_job(job) -> None:
    """Trabajos largos fuera de la petición. En pruebas corren en línea para ser deterministas."""
    if settings.inline_jobs:
        job()
    else:
        threading.Thread(target=job, daemon=True).start()


NOT_FOUND = HTTPException(status_code=404, detail="No encontrado")


@dataclass
class Ctx:
    session: Session
    user_id: str | None
    role: str | None
    company_id: str | None
    read_only: bool = False
    after_commit: list = field(default_factory=list)


def _apply(session: Session, *, company_id: str | None, consultant: bool, read_only: bool) -> None:
    # set_config(..., true) vale solo dentro de esta transacción (equivale a SET LOCAL).
    session.execute(text("select set_config('app.company_id', :c, true)"), {"c": company_id or ""})
    session.execute(text("select set_config('app.is_consultant', :v, true)"),
                    {"v": "on" if consultant else "off"})
    if read_only:
        session.execute(text("set transaction read only"))


def db_anonymous() -> Iterator[Session]:
    """Sin identidad: solo puede llamar las funciones de autenticación."""
    with Session(engine) as s, s.begin():
        _apply(s, company_id=None, consultant=False, read_only=False)
        yield s


def current_ctx(
    authorization: str | None = Header(default=None),
    x_view_as_company: str | None = Header(default=None),
) -> Iterator[Ctx]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        claims = read_jwt(authorization.split(" ", 1)[1])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    role, cid = claims["role"], claims.get("cid")
    view_as = None
    if x_view_as_company:
        if role != "consultant":
            raise NOT_FOUND
        view_as = x_view_as_company
    with Session(engine) as s, s.begin():
        if view_as:  # «Ver como empresa»: se ve lo que ve la empresa y la base impide escribir.
            _apply(s, company_id=view_as, consultant=False, read_only=True)
            ctx = Ctx(s, claims["sub"], role, view_as, read_only=True)
        else:
            _apply(s, company_id=cid, consultant=role == "consultant", read_only=False)
            ctx = Ctx(s, claims["sub"], role, cid)
        yield ctx
    # La transacción ya se confirmó: ahora sí pueden correr los trabajos que dependen de ella.
    for job in ctx.after_commit:
        run_job(job)


def require_consultant(ctx: Ctx = Depends(current_ctx)) -> Ctx:
    if ctx.role != "consultant" or ctx.read_only:
        raise NOT_FOUND
    return ctx


def audit(ctx: Ctx, action: str, entity: str, entity_id: str, company_id: str | None, **detail) -> None:
    import json
    ctx.session.execute(
        text("insert into audit_log(company_id, actor_id, action, entity, entity_id, detail) "
             "values (:c, :a, :act, :e, :eid, cast(:d as jsonb))"),
        {"c": company_id, "a": ctx.user_id, "act": action, "e": entity, "eid": entity_id,
         "d": json.dumps(detail)},
    )
