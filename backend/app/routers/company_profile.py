from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from .. import company_rules as rules
from ..deps import Ctx, audit, current_ctx

router = APIRouter(prefix="/company", tags=["company"])

FIELDS = ["name", "nit", "sector", "size_range", "city", "website"]


class Profile(BaseModel):
    name: str | None = None
    nit: str | None = None
    sector: str | None = None
    size_range: str | None = None
    city: str | None = None
    website: str | None = None


def own_company_id(ctx: Ctx, company_id: str | None = None) -> str:
    """Empresa de la petición. El consultor debe indicar cuál mira (solo lectura)."""
    cid = ctx.company_id or company_id
    if not cid:
        raise HTTPException(status_code=422, detail="Indica la empresa")
    return cid


def load_profile(ctx: Ctx, cid: str) -> dict:
    row = ctx.session.execute(
        text("select id, name, nit, sector, size_range, city, website, status from company where id = cast(:i as uuid)"),
        {"i": cid}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No encontrado")
    return dict(row) | {"id": str(row["id"])}


def readiness(ctx: Ctx, cid: str) -> dict:
    p = load_profile(ctx, cid)
    missing = [f for f in rules.REQUIRED_FIELDS if not p.get(f)]
    done = {r[0] for r in ctx.session.execute(
        text("select distinct doc_type from document where status='processed' and company_id = cast(:c as uuid)"),
        {"c": cid})}
    docs = [{"type": t, "label": rules.DOC_TYPES[t], "required": t in rules.REQUIRED_DOC_TYPES, "done": t in done}
            for t in rules.REQUIRED_DOC_TYPES + rules.OPTIONAL_DOC_TYPES]
    missing_docs = [d["type"] for d in docs if d["required"] and not d["done"]]
    return {"profile_complete": not missing, "missing_fields": missing, "suggested_documents": docs,
            "missing_documents": missing_docs, "can_continue": not missing and not missing_docs}


@router.get("/options")
def options():
    return {"sectors": rules.SECTORS, "sizes": rules.SIZES, "document_types": rules.DOC_TYPES}


@router.get("/profile")
def get_profile(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    return {"profile": load_profile(ctx, cid), "readiness": readiness(ctx, cid)}


@router.put("/profile")
def save_profile(body: Profile, ctx: Ctx = Depends(current_ctx)):
    """Guarda como borrador: acepta datos incompletos (02-R1)."""
    if ctx.read_only or not ctx.company_id:
        raise HTTPException(status_code=404, detail="No encontrado")
    data = body.model_dump(exclude_unset=True)
    if data.get("sector") and data["sector"] not in rules.SECTORS:
        raise HTTPException(status_code=422, detail="Sector fuera de la lista")
    if data.get("size_range") and data["size_range"] not in rules.SIZES:
        raise HTTPException(status_code=422, detail="Tamaño fuera de la lista")
    data = {k: v for k, v in data.items() if k in FIELDS}
    if data:
        sets = ", ".join(f"{k} = :{k}" for k in data)
        ctx.session.execute(text(f"update company set {sets} where id = cast(:cid as uuid)"),
                            {**data, "cid": ctx.company_id})
        audit(ctx, "company.profile_saved", "company", ctx.company_id, ctx.company_id, fields=sorted(data))
    return {"profile": load_profile(ctx, ctx.company_id), "readiness": readiness(ctx, ctx.company_id)}


@router.get("/readiness")
def get_readiness(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    return readiness(ctx, own_company_id(ctx, company_id))
