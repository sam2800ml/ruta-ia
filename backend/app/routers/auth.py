from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import Ctx, current_ctx, db_anonymous
from ..security import hash_password, hash_token, make_jwt, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash válido para igualar el tiempo de respuesta cuando el correo no existe.
_DUMMY = hash_password("no-existe")


class Login(BaseModel):
    email: EmailStr
    password: str


class Accept(BaseModel):
    token: str
    password: str = Field(min_length=10)


@router.post("/login")
def login(body: Login, s: Session = Depends(db_anonymous)):
    row = s.execute(text("select * from auth_get_user(:e)"), {"e": body.email}).mappings().first()
    ok = verify_password(row["password_hash"] if row else _DUMMY, body.password)
    if not row or not ok:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    cid = str(row["company_id"]) if row["company_id"] else None
    return {"access_token": make_jwt(str(row["id"]), row["role"], cid), "role": row["role"], "company_id": cid}


@router.post("/accept-invitation")
def accept(body: Accept, s: Session = Depends(db_anonymous)):
    row = s.execute(
        text("select * from auth_accept_invitation(:t, :p)"),
        {"t": hash_token(body.token), "p": hash_password(body.password)},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=400, detail="Invitación inválida o vencida")
    cid = str(row["company_id"])
    return {"access_token": make_jwt(str(row["user_id"]), "company_user", cid), "role": "company_user", "company_id": cid}


@router.get("/me")
def me(ctx: Ctx = Depends(current_ctx)):
    return {"user_id": ctx.user_id, "role": ctx.role, "company_id": ctx.company_id, "read_only": ctx.read_only}
