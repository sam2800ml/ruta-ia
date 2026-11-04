"""Evidencia de las Features 04 y 05."""
import pytest
from sqlalchemy import create_engine, text

from app import diagnosis
from app.config import settings
from app.llm import Candidate, StubLLM
from tests.helpers import generate, seed_evidence


@pytest.fixture
def ready(client, admin, consultant, two_companies):
    (ida, ha), (idb, hb) = two_companies
    seed_evidence(client, ha, admin)
    return ida, ha, idb, hb


def review(client, consultant, rid):
    return client.get(f"/review/{rid}", headers=consultant).json()


# 04-R2, R3 y criterio 1: el puntaje sale de reglas fijas y siempre es el mismo
def test_scores_are_deterministic_and_level_follows_thresholds(client, consultant, ready):
    _, ha, *_ = ready
    r1 = review(client, consultant, generate(client, ha))
    r2 = review(client, consultant, generate(client, ha))
    s1 = {p["pillar"]: p["score"] for p in r1["pillars"]}
    s2 = {p["pillar"]: p["score"] for p in r2["pillars"]}
    assert s1 == s2
    assert s1["governance"] == 1.0 and s1["culture"] == 5.0 and s1["strategy"] == 2.0
    assert r1["average"] == round(sum(s1.values()) / 6, 2)
    assert r1["level"] == diagnosis.level_for(r1["average"], [1.8, 2.6, 3.4, 4.2])
    assert diagnosis.level_for(2.3, [1.8, 2.6, 3.4, 4.2]) == 2   # el ejemplo del diseño: 2,3 → nivel 2


# 04-R4, R5, R8: tipos de hallazgo, pilares bajos destacados, contradicción con ambas posturas
def test_findings_types_and_contradiction(client, consultant, ready):
    _, ha, *_ = ready
    r = review(client, consultant, generate(client, ha))
    kinds = {f["kind"] for f in r["findings"]}
    assert kinds == {"brecha", "fortaleza", "contradiccion"}
    assert any(p["low"] for p in r["pillars"]) and all(p["low"] == (p["score"] < 2) for p in r["pillars"])
    c = next(f for f in r["findings"] if f["kind"] == "contradiccion")
    vals = sorted(e["ref"]["value"] for e in c["evidence"])
    assert vals == [1, 5] and {e["ref"]["role"] for e in c["evidence"]} == {"Tecnología", "Finanzas"}


# 04-R6 y criterio 2: todo hallazgo lleva evidencia y la comprobación automática la confirma en la fuente
def test_every_finding_has_verified_evidence_in_source(client, consultant, ready):
    _, ha, *_ = ready
    rid = generate(client, ha)
    r = review(client, consultant, rid)
    types = {e["source_type"] for f in r["findings"] for e in f["evidence"]}
    assert types == {"survey", "document", "transcript"}
    eng = create_engine(settings.database_url)
    with eng.begin() as s:
        s.execute(text("select set_config('app.is_consultant', 'on', true)"))
        rows = s.execute(text("select source_type, source_id::text as source_id, quote from evidence")).mappings().all()
        assert rows and all(diagnosis.verify_evidence(s, dict(x)) for x in rows)
    assert all(f["evidence"] and f["evidence_status"] == "verificada" for f in r["findings"])
    # y la cita del transcript conserva el minuto exacto
    tr = next(e for f in r["findings"] for e in f["evidence"] if e["source_type"] == "transcript")
    assert tr["ref"]["start_sec"] == 190


# 04-R7 y criterio 3: evidencia inventada → «insuficiente», no se acepta tal cual
class FabricatingLLM(StubLLM):
    def propose_findings(self, fragments, segments):
        return [Candidate("brecha", "data", "Datos sin dueño", "El modelo afirma algo.",
                          [{"source_type": "document", "source_id": fragments[0]["id"], "quote": "Frase que el documento nunca dijo.", "ref": {}}])]


def test_fabricated_evidence_is_flagged_and_blocks_acceptance(client, consultant, ready, monkeypatch):
    _, ha, *_ = ready
    monkeypatch.setattr(diagnosis, "get_llm", lambda: FabricatingLLM())
    rid = generate(client, ha)
    r = review(client, consultant, rid)
    bad = [f for f in r["findings"] if f["evidence_status"] == "insuficiente"]
    assert len(bad) == 1 and r["findings"].count(bad[0]) == 1
    base = f"/review/{rid}/blocks/finding/{bad[0]['id']}"
    assert client.post(base, headers=consultant, json={"action": "accept"}).status_code == 409
    q = client.get("/review/queue", headers=consultant).json()
    assert q[0]["sin_evidencia"] == 1
    # no se publica mientras siga sin resolver, aunque el resto esté decidido
    decide_all(client, consultant, rid, skip=bad[0]["id"])
    assert client.post(f"/review/{rid}/publish", headers=consultant).status_code == 409
    assert client.post(base, headers=consultant, json={"action": "reject", "reason": "No hay respaldo"}).status_code == 200
    assert client.post(f"/review/{rid}/publish", headers=consultant).status_code == 200


def decide_all(client, consultant, rid, skip=None):
    skips = {skip} if isinstance(skip, str) or skip is None else set(skip)
    r = review(client, consultant, rid)
    for kind, key in (("pillar", "pillars"), ("finding", "findings"), ("recommendation", "recommendations")):
        for b in r[key]:
            if b["id"] not in skips:
                resp = client.post(f"/review/{rid}/blocks/{kind}/{b['id']}", headers=consultant, json={"action": "accept"})
                assert resp.status_code == 200, resp.text


# 04-R9, R10 y criterio 4, 5: tres recomendaciones ligadas a hallazgos; «n de m roles» y fuentes
def test_recommendations_and_report_declarations(client, consultant, ready):
    _, ha, *_ = ready
    r = review(client, consultant, generate(client, ha))
    ids = {f["id"] for f in r["findings"]}
    assert 1 <= len(r["recommendations"]) <= 3
    assert all(rec["finding_ids"] and set(rec["finding_ids"]) <= ids for rec in r["recommendations"])
    assert (r["roles_responded"], r["roles_total"]) == (2, 2)
    assert set(r["sources"]) == {"surveys", "documents", "transcripts"} and r["sources"]["documents"] == ["plan.txt"]
    assert "apoyo de IA" in r["declaration"]


def test_partial_surveys_state_how_many_roles(client, admin, consultant, two_companies):
    (_, ha), _ = two_companies
    from tests.helpers import FUTURE, respond, survey_tokens
    for role, mail in (("Tecnología", "ti@example.com"), ("Finanzas", "fin@example.com")):
        client.post("/surveys", headers=ha, json={"role_name": role, "responsible": "R", "email": mail, "deadline": FUTURE})
    respond(client, survey_tokens(admin)["ti@example.com"])
    r = review(client, consultant, generate(client, ha))
    assert (r["roles_responded"], r["roles_total"]) == (1, 2)
    assert client.post("/reports", headers=ha).status_code == 202  # parcial sí se puede
    empty = client.post("/surveys", headers=ha, json={"role_name": "Legal", "responsible": "R", "email": "l@example.com", "deadline": FUTURE})
    assert empty.status_code == 201


def test_cannot_generate_without_any_complete_survey(client, two_companies):
    (_, ha), _ = two_companies
    assert client.post("/reports", headers=ha).status_code == 422


# 04-R13 y criterio 6: regenerar crea versión nueva y conserva las anteriores
def test_regenerate_keeps_previous_versions(client, consultant, ready):
    _, ha, *_ = ready
    r1, r2 = generate(client, ha), generate(client, ha)
    assert review(client, consultant, r1)["version"] == 1 and review(client, consultant, r2)["version"] == 2
    assert len(client.get("/review/queue", headers=consultant).json()) == 2


# 05-R1..R10 y criterios: control humano de punta a punta
def test_human_review_workflow_and_company_visibility(client, consultant, ready):
    ida, ha, idb, hb = ready
    rid = generate(client, ha)
    # la empresa no ve nada mientras no esté publicado
    assert client.get("/reports/published", headers=ha).status_code == 404
    assert client.get("/reports/state", headers=ha).json()["latest"]["status"] == "in_review"
    r = review(client, consultant, rid)
    assert r["progress"]["reviewed"] == 0 and r["progress"]["total"] == len(r["pillars"]) + len(r["findings"]) + len(r["recommendations"])
    # no se publica con bloques sin decidir
    assert client.post(f"/review/{rid}/publish", headers=consultant).status_code == 409
    # una empresa no puede revisar ni publicar
    assert client.post(f"/review/{rid}/publish", headers=ha).status_code == 404
    # reglas por acción
    f0, f1 = r["findings"][0], r["findings"][1]
    assert client.post(f"/review/{rid}/blocks/finding/{f0['id']}", headers=consultant, json={"action": "reject"}).status_code == 422
    assert client.post(f"/review/{rid}/blocks/pillar/{r['pillars'][0]['id']}", headers=consultant, json={"action": "edit", "new_text": "x"}).status_code == 422
    assert client.post(f"/review/{rid}/blocks/finding/{f1['id']}", headers=consultant, json={"action": "edit"}).status_code == 422
    # editar guarda texto anterior y nuevo, autor y hora
    assert client.post(f"/review/{rid}/blocks/finding/{f1['id']}", headers=consultant, json={"action": "edit", "new_text": "Texto del consultor."}).status_code == 200
    assert client.post(f"/review/{rid}/blocks/finding/{f0['id']}", headers=consultant, json={"action": "reject", "reason": "No aplica a esta empresa"}).status_code == 200
    h = client.get(f"/review/{rid}/blocks/finding/{f1['id']}/history", headers=consultant).json()
    assert h[0]["old_text"] == f1["description"] and h[0]["new_text"] == "Texto del consultor." and h[0]["actor"] and h[0]["at"]
    decide_all(client, consultant, rid, skip=f0["id"])   # acepta el resto (re-decide f1: queda historial de ambas)
    assert len(client.get(f"/review/{rid}/blocks/finding/{f1['id']}/history", headers=consultant).json()) == 2
    p = review(client, consultant, rid)["progress"]
    assert p["reviewed"] == p["total"]
    assert client.post(f"/review/{rid}/publish", headers=consultant).status_code == 200
    # la empresa ve lo publicado y aceptado/editado; lo rechazado no aparece
    pub = client.get("/reports/published", headers=ha).json()
    assert pub["status"] == "published" and f0["id"] not in {f["id"] for f in pub["findings"]}
    assert all(f["review_status"] in ("accepted", "edited") for f in pub["findings"])
    assert "revisado por un consultor" in pub["declaration"]
    # aislamiento
    assert client.get("/reports/published", headers=hb).status_code == 404
    assert client.get(f"/review/{rid}", headers=hb).status_code == 404
    # ya publicado no admite más decisiones
    assert client.post(f"/review/{rid}/blocks/finding/{f1['id']}", headers=consultant, json={"action": "accept"}).status_code == 409


# 05, criterio 1: ninguna ruta ni la propia base permite publicar sin aprobación registrada
def test_company_cannot_publish_even_with_sql(client, consultant, ready):
    ida, ha, *_ = ready
    rid = generate(client, ha)
    eng = create_engine(settings.database_url)
    with eng.begin() as c:
        c.execute(text("select set_config('app.company_id', :c, true)"), {"c": ida})
        assert c.execute(text("update report set status='published' where id = cast(:r as uuid)"), {"r": rid}).rowcount == 0
        assert c.execute(text("select count(*) from finding")).scalar() == 0        # ni ve los borradores
    with eng.begin() as c:
        c.execute(text("select set_config('app.company_id', :c, true)"), {"c": ida})
        try:
            c.execute(text("insert into report(company_id, version, status) values (cast(:c as uuid), 99, 'published')"), {"c": ida})
            raise AssertionError("debió fallar")
        except Exception as e:
            assert "row-level security" in str(e)
    with eng.begin() as c:
        c.execute(text("select set_config('app.is_consultant', 'on', true)"))
        assert c.execute(text("select count(*) from report where status='published'")).scalar() == 0
        for stmt in ("update review_decision set action='accept'", "delete from review_decision"):
            try:
                with c.begin_nested():
                    c.execute(text(stmt))
                raise AssertionError("debió fallar")
            except Exception as e:
                assert "permission denied" in str(e)


# 04-R12 y criterio 7: el PDF sale del informe publicado y lleva la declaración de IA
def test_pdf_export_of_published_report(client, consultant, ready):
    _, ha, *_ = ready
    rid = generate(client, ha)
    assert client.get("/reports/published/pdf", headers=ha).status_code == 404
    decide_all(client, consultant, rid)
    assert client.post(f"/review/{rid}/publish", headers=consultant).status_code == 200
    r = client.get("/reports/published/pdf", headers=ha)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    import io
    from pypdf import PdfReader
    txt = "".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
    pub = client.get("/reports/published", headers=ha).json()
    assert f"Versión {pub['version']}" in txt and "revisado por un consultor" in txt and pub["findings"][0]["title"][:20] in txt


def test_return_to_draft_hides_from_queue(client, consultant, ready):
    _, ha, *_ = ready
    rid = generate(client, ha)
    assert client.post(f"/review/{rid}/return-to-draft", headers=consultant).status_code == 200
    assert client.get("/review/queue", headers=consultant).json() == []
    assert client.get("/reports/state", headers=ha).json()["latest"]["status"] == "in_review"
