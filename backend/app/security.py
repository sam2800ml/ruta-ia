import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import settings

_ph = PasswordHasher()


def hash_password(p: str) -> str:
    return _ph.hash(p)


def verify_password(hash_: str, p: str) -> bool:
    try:
        return _ph.verify(hash_, p)
    except VerifyMismatchError:
        return False


def new_token() -> tuple[str, str]:
    """Devuelve (token en claro para el correo, hash para la base)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def make_jwt(user_id: str, role: str, company_id: str | None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "cid": company_id, "exp": exp},
        settings.jwt_secret, algorithm="HS256",
    )


def read_jwt(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
