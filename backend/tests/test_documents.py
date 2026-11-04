"""Evidencia de la Feature 02."""
from sqlalchemy import create_engine, text

from app.config import settings
from app.processing import process_document
from tests.conftest import login, make_company
from tests.samples import make_pdf, six_samples


def upload(client, headers, doc_type, name, mime, data):
    return client.post("/documents", headers=headers, data={"doc_type": doc_type},
                       files={"file": (name, data, mime)})


import pytest


@pytest.fixture(autouse=True)
def tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))


# 02-R1 formulario con borrador y listas cerradas
def test_profile_draft_and_closed_lists(client, two_companies):
    (ida, ha), _ = two_companies
    r = client.put("/company/profile", headers=ha, json={"city": "Cali", "sector": "Financiero"})
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["city"] == "Cali" and not body["readiness"]["profile_complete"]
    assert set(body["readiness"]["missing_fields"]) == {"size_range"}  # nit y nombre ya existen
    assert client.put("/company/profile", headers=ha, json={"sector": "Inventado"}).status_code == 422
    assert client.put("/company/profile", headers=ha, json={"size_range": "7"}).status_code == 422
    # persiste: otra petición ve el borrador
    assert client.get("/company/profile", headers=ha).json()["profile"]["city"] == "Cali"


# Criterio 1: los seis documentos llegan a «processed» sin intervención manual (02-R2, R3, R4, R7)
def test_six_sample_documents_reach_processed(client, two_companies):
    (_, ha), _ = two_companies
    for doc_type, name, mime, data, _kind in six_samples():
        r = upload(client, ha, doc_type, name, mime, data)
        assert r.status_code == 201, r.text
    docs = client.get("/documents", headers=ha).json()
    assert len(docs) == 6
    assert {d["status"] for d in docs} == {"processed"}, docs


# Criterio 3 / 02-R7: cada fragmento conserva documento y página
def test_fragments_keep_document_and_page(client, two_companies):
    (_, ha), _ = two_companies
    pdf = make_pdf(["Primera página\nGobernanza de datos", "Segunda página\nInfraestructura en la nube"])
    doc_id = upload(client, ha, "plan_estrategico", "plan.pdf", "application/pdf", pdf).json()["id"]
    frags = client.get(f"/documents/{doc_id}/fragments", headers=ha).json()
    by_page = {f["page"]: f for f in frags}
    assert set(by_page) == {1, 2}
    assert "Gobernanza" in by_page[1]["text"] and "nube" in by_page[2]["text"]
    assert all(f["document"] == "plan.pdf" for f in frags)


# Criterio 2 / 02-R2, R8: límites y formatos
def test_rejects_big_empty_and_wrong_formats(client, two_companies):
    (_, ha), _ = two_companies
    big = b"%PDF-" + b"0" * (26 * 1024 * 1024)
    r = upload(client, ha, "otro", "grande.pdf", "application/pdf", big)
    assert r.status_code == 413 and "25 MB" in r.json()["detail"]
    assert upload(client, ha, "otro", "vacio.txt", "text/plain", b"").status_code == 422
    assert upload(client, ha, "otro", "virus.exe", "application/octet-stream", b"MZ....").status_code == 422
    assert upload(client, ha, "otro", "falso.pdf", "application/pdf", b"esto no es un pdf").status_code == 422
    assert upload(client, ha, "tipo_raro", "a.txt", "text/plain", b"hola").status_code == 422
    assert client.get("/documents", headers=ha).json() == []


# Decisión 8 (supuesto): un PDF sin texto se marca con error y motivo, no se queda procesando
def test_scanned_pdf_ends_in_error_with_reason(client, two_companies):
    (_, ha), _ = two_companies
    blank = make_pdf([""])
    doc = upload(client, ha, "otro", "escaneo.pdf", "application/pdf", blank).json()
    got = [d for d in client.get("/documents", headers=ha).json() if d["id"] == doc["id"]][0]
    assert got["status"] == "error" and "texto" in got["error"]


# Criterio 4: el estado vive en la base y el procesamiento es idempotente
def test_processing_state_survives_and_is_idempotent(client, two_companies):
    (ida, ha), _ = two_companies
    eng = create_engine(settings.database_url)
    doc_id = upload(client, ha, "otro", "n.txt", "text/plain", b"Notas de la empresa").json()["id"]
    with eng.begin() as c:  # simula que el trabajo nunca corrió: vuelve a «uploaded» y sin fragmentos
        c.execute(text("select set_config('app.company_id', :c, true)"), {"c": ida})
        c.execute(text("delete from fragment where document_id = cast(:d as uuid)"), {"d": doc_id})
        c.execute(text("update document set status='uploaded' where id = cast(:d as uuid)"), {"d": doc_id})
    assert client.get("/documents", headers=ha).json()[0]["status"] == "uploaded"
    process_document(ida, doc_id)
    process_document(ida, doc_id)  # segunda vez: no duplica fragmentos
    assert client.get("/documents", headers=ha).json()[0]["status"] == "processed"
    assert len(client.get(f"/documents/{doc_id}/fragments", headers=ha).json()) == 1


# Criterio 5 / 01-R2: solo la empresa y el equipo consultor ven los documentos
def test_documents_are_isolated_per_company(client, consultant, two_companies):
    (ida, ha), (idb, hb) = two_companies
    doc_id = upload(client, ha, "otro", "n.txt", "text/plain", b"Confidencial de A").json()["id"]
    assert client.get("/documents", headers=hb).json() == []
    assert client.get(f"/documents/{doc_id}/fragments", headers=hb).status_code == 404
    seen = client.get("/documents", params={"company_id": ida}, headers=consultant).json()
    assert [d["id"] for d in seen] == [doc_id]  # el consultor valida el contexto (historia 4)
    assert upload(client, consultant, "otro", "x.txt", "text/plain", b"hola").status_code == 404
    eng = create_engine(settings.database_url)
    with eng.begin() as c:
        c.execute(text("select set_config('app.company_id', :c, true)"), {"c": idb})
        assert c.execute(text("select count(*) from document")).scalar() == 0
        assert c.execute(text("select count(*) from fragment")).scalar() == 0


# 02-R5, R6: sugeridos, inventario opcional y «Continuar» solo con lo mínimo
def test_readiness_gates_continue(client, two_companies):
    (_, ha), _ = two_companies
    r = client.get("/company/readiness", headers=ha).json()
    assert not r["can_continue"] and len(r["missing_documents"]) == 5
    assert [d["required"] for d in r["suggested_documents"]].count(False) == 1  # inventario opcional
    client.put("/company/profile", headers=ha, json={"sector": "Financiero", "size_range": "201-1000", "city": "Cali"})
    for doc_type, name, mime, data, _k in six_samples():
        if doc_type != "operaciones":
            upload(client, ha, doc_type, name, mime, data)
    r = client.get("/company/readiness", headers=ha).json()
    assert r["can_continue"] and r["missing_documents"] == [] and r["profile_complete"]


def test_view_as_cannot_write_profile(client, consultant, two_companies):
    (ida, _), _ = two_companies
    view = {**consultant, "X-View-As-Company": ida}
    assert client.put("/company/profile", headers=view, json={"city": "X"}).status_code == 404
    assert client.get("/company/profile", headers=view).status_code == 200
