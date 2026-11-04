import pathlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text

from .. import company_rules as rules
from ..config import settings
from ..deps import NOT_FOUND, Ctx, audit, current_ctx
from ..extract import ExtractError, detect_kind
from ..processing import process_document
from .company_profile import own_company_id

router = APIRouter(prefix="/documents", tags=["documents"])
COLS = "id, name, doc_type, size_bytes, status, error, created_at, processed_at"


@router.post("", status_code=201)
async def upload(file: UploadFile = File(...), doc_type: str = Form(...),
                 ctx: Ctx = Depends(current_ctx)):
    if ctx.read_only or not ctx.company_id:
        raise NOT_FOUND
    if doc_type not in rules.DOC_TYPES:
        raise HTTPException(status_code=422, detail="Tipo de documento desconocido")
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"El archivo supera {settings.max_upload_mb} MB")
    if not data:
        raise HTTPException(status_code=422, detail="El archivo está vacío")
    name = pathlib.Path(file.filename or "documento").name
    try:
        detect_kind(name, data[:8])
    except ExtractError as e:
        raise HTTPException(status_code=422, detail=str(e))
    doc_id = uuid.uuid4()
    folder = pathlib.Path(settings.storage_dir) / ctx.company_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{doc_id}{pathlib.Path(name).suffix.lower()}"
    path.write_bytes(data)
    ctx.session.execute(
        text("insert into document(id, company_id, name, doc_type, size_bytes, storage_path) "
             "values (:i, cast(:c as uuid), :n, :t, :s, :p)"),
        {"i": doc_id, "c": ctx.company_id, "n": name, "t": doc_type, "s": len(data), "p": str(path)})
    audit(ctx, "document.uploaded", "document", str(doc_id), ctx.company_id, name=name, type=doc_type)
    # El procesamiento no bloquea la pantalla (02-R4). Corre tras confirmar la transacción.
    cid, did = ctx.company_id, str(doc_id)
    ctx.after_commit.append(lambda: process_document(cid, did))
    return {"id": str(doc_id), "name": name, "doc_type": doc_type, "status": "uploaded"}


@router.get("")
def list_documents(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    rows = ctx.session.execute(
        text(f"select {COLS} from document where company_id = cast(:c as uuid) order by created_at"),
        {"c": cid}).mappings().all()
    return [{**r, "id": str(r["id"])} for r in rows]


@router.get("/{document_id}/fragments")
def fragments(document_id: str, ctx: Ctx = Depends(current_ctx)):
    try:
        rows = ctx.session.execute(
            text("select f.id, f.page, f.position, f.text, d.name as document from fragment f "
                 "join document d on d.id = f.document_id where f.document_id = cast(:d as uuid) order by f.position"),
            {"d": document_id}).mappings().all()
    except Exception:
        raise NOT_FOUND
    if not rows:
        raise NOT_FOUND
    return [{**r, "id": str(r["id"])} for r in rows]
