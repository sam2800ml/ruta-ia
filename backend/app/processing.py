"""Procesamiento de documentos. El estado vive en la base: sobrevive a cerrar la ventana (02-R4)."""
import pathlib

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import engine
from .deps import _apply
from .extract import ExtractError, detect_kind, extract


def process_document(company_id: str, document_id: str) -> None:
    with Session(engine) as s, s.begin():
        _apply(s, company_id=company_id, consultant=False, read_only=False)
        row = s.execute(text("select name, storage_path, status from document where id = cast(:i as uuid)"),
                        {"i": document_id}).mappings().first()
        if not row or row["status"] not in ("uploaded", "processing"):
            return  # idempotente: ya procesado o inexistente
        s.execute(text("update document set status='processing' where id = cast(:i as uuid)"), {"i": document_id})
        s.execute(text("delete from fragment where document_id = cast(:i as uuid)"), {"i": document_id})
        try:
            data = pathlib.Path(row["storage_path"]).read_bytes()
            frags = extract(data, detect_kind(row["name"], data[:8]))
        except ExtractError as e:
            s.execute(text("update document set status='error', error=:e where id = cast(:i as uuid)"),
                      {"e": str(e), "i": document_id})
            return
        for pos, (page, body) in enumerate(frags):
            s.execute(text("insert into fragment(company_id, document_id, page, position, text) "
                           "values (cast(:c as uuid), cast(:d as uuid), :p, :pos, :t)"),
                      {"c": company_id, "d": document_id, "p": page, "pos": pos, "t": body})
        s.execute(text("update document set status='processed', processed_at=now(), error=null "
                       "where id = cast(:i as uuid)"), {"i": document_id})
