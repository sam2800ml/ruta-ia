"""Evidencia de las Features 06 y 07."""
import pytest

from tests.helpers import STAGES, close_strategy, publish_report


@pytest.fixture
def pub(client, admin, consultant, two_companies):
    (ida, ha), (idb, hb) = two_companies
    publish_report(client, consultant, ha, admin)
    return ida, ha, idb, hb


# 06-R1 y criterio 1: con el diagnóstico sin publicar el paso aparece bloqueado
def test_strategy_locked_until_report_published(client, two_companies):
    (_, ha), _ = two_companies
    s = client.get("/strategy", headers=ha).json()
    assert s == {"enabled": False, "locked_message": "Se habilita cuando el diagnóstico se publique"}
    assert client.post("/strategy/start", headers=ha).status_code == 423
    assert client.post("/strategy/messages", headers=ha, json={"text": "hola"}).status_code == 423


# 06-R2, R3, R10: cinco etapas en orden; el asistente se identifica como IA y cita datos del informe publicado
def test_five_stages_ai_disclosure_and_data_from_report(client, pub):
    _, ha, *_ = pub
    assert client.post("/strategy/start", headers=ha).json() == {"started": True}
    assert client.post("/strategy/start", headers=ha).json() == {"started": False}  # idempotente
    s = client.get("/strategy", headers=ha).json()
    assert [x["key"] for x in s["stages"]] == STAGES
    assert [x["status"] for x in s["stages"]] == ["current", "pending", "pending", "pending", "pending"]
    assert s["messages"][0]["author"] == "assistant" and "asistente de IA" in s["messages"][0]["text"]
    report = client.get("/reports/published", headers=ha).json()
    weakest = min(report["pillars"], key=lambda p: p["score"])
    assert s["context"]["weakest"] == {"pillar": weakest["pillar"], "label": weakest["label"], "score": weakest["score"]}
    # no se puede completar una etapa que no es la actual ni vacía
    assert client.post("/strategy/stages/objetivos/complete", headers=ha).status_code == 409
    assert client.post("/strategy/stages/vision/complete", headers=ha).status_code == 409


# 06-R4, R5 y criterio 2: solo se guarda tras «Guardar»; el panel muestra lo guardado
def test_proposal_saved_only_after_decision_and_panel_updates(client, pub):
    _, ha, *_ = pub
    client.post("/strategy/start", headers=ha)
    r = client.post("/strategy/messages", headers=ha, json={"text": "Ser líderes en banca con IA responsable"}).json()
    assert r["proposal"]["kind"] == "vision" and "asistente" not in r["reply"].lower()[:5]
    s = client.get("/strategy", headers=ha).json()
    assert s["items"] == [] and len(s["proposals"]) == 1            # propuesta pendiente, nada guardado
    pid = r["proposal"]["id"]
    assert client.post(f"/strategy/proposals/{pid}/save", headers=ha, json={"text": "Ser líderes en banca digital con IA responsable"}).status_code == 201
    s = client.get("/strategy", headers=ha).json()
    assert [i["text"] for i in s["items"]] == ["Ser líderes en banca digital con IA responsable"] and s["proposals"] == []
    assert client.post(f"/strategy/proposals/{pid}/save", headers=ha, json={}).status_code == 404   # ya decidida
    r2 = client.post("/strategy/messages", headers=ha, json={"text": "otra cosa"}).json()
    assert client.post(f"/strategy/proposals/{r2['proposal']['id']}/discard", headers=ha).status_code == 200
    assert len(client.get("/strategy", headers=ha).json()["items"]) == 1


# 06-R3: en gobernanza el asistente muestra el dato del diagnóstico que lo motiva
def test_governance_proposal_shows_motivating_data(client, pub):
    _, ha, *_ = pub
    client.post("/strategy/start", headers=ha)
    for st in ("vision", "objetivos"):
        pid = client.post("/strategy/messages", headers=ha, json={"text": st}).json()["proposal"]["id"]
        client.post(f"/strategy/proposals/{pid}/save", headers=ha, json={}); client.post(f"/strategy/stages/{st}/complete", headers=ha)
    p = client.post("/strategy/messages", headers=ha, json={"text": "Toda IA se revisa por una persona"}).json()["proposal"]
    assert p["kind"] == "principio" and p["basis"] == "Gobernanza: 1.0 de 5"


# 06-R6, R7 y criterios 3, 5: se retoma donde se quedó y editar conserva la versión anterior
def test_conversation_persists_and_edits_keep_versions(client, pub):
    _, ha, *_ = pub
    client.post("/strategy/start", headers=ha)
    pid = client.post("/strategy/messages", headers=ha, json={"text": "Visión inicial"}).json()["proposal"]["id"]
    key = client.post(f"/strategy/proposals/{pid}/save", headers=ha, json={}).json()["key"]
    before = client.get("/strategy", headers=ha).json()           # "cerrar la ventana y volver"
    again = client.get("/strategy", headers=ha).json()
    assert before["current_stage"] == again["current_stage"] == "vision" and before["messages"] == again["messages"]
    assert client.put(f"/strategy/items/{key}", headers=ha, json={"text": "Visión editada"}).json()["version"] == 2
    versions = client.get(f"/strategy/items/{key}/versions", headers=ha).json()
    assert [(v["version"], v["text"], v["status"]) for v in versions] == [(1, "Visión inicial", "superseded"), (2, "Visión editada", "active")]
    assert [i["text"] for i in client.get("/strategy", headers=ha).json()["items"]] == ["Visión editada"]


# 06-R9 y criterio 6: con las cinco etapas completas se cierra y se habilitan los casos de uso
def test_closing_strategy_unlocks_use_cases(client, pub):
    _, ha, *_ = pub
    assert client.get("/use-cases", headers=ha).json()["enabled"] is False
    close_strategy(client, ha)
    s = client.get("/strategy", headers=ha).json()
    assert s["status"] == "closed" and {x["status"] for x in s["stages"]} == {"complete"}
    assert client.post("/strategy/messages", headers=ha, json={"text": "más"}).status_code == 409
    assert client.get("/use-cases", headers=ha).json()["enabled"] is True


def test_strategy_is_isolated_and_read_only_for_consultant(client, consultant, pub):
    ida, ha, idb, hb = pub
    client.post("/strategy/start", headers=ha)
    assert client.get("/strategy", headers=hb).json()["enabled"] is False
    seen = client.get("/strategy", params={"company_id": ida}, headers=consultant).json()
    assert seen["started"] is True
    assert client.post("/strategy/messages", headers={**consultant, "X-View-As-Company": ida}, json={"text": "x"}).status_code == 404


# ---------- Feature 07 ----------
CASE = dict(name="Clasificación automática de PQRS", area="Servicio al cliente", risk="limitado", indicator="Tiempo de respuesta",
            baseline="48 h", target="24 h", tech="Clasificador de texto", personal_data=True, legal=3, ethic=2, infra=2,
            legal_note="Maneja datos personales", ethic_note="Sin decisiones automáticas", infra_note="Integra con el CRM",
            volume_per_month=400, minutes_saved=15)


@pytest.fixture
def uc(client, pub):
    _, ha, idb, hb = pub
    close_strategy(client, ha)
    return ha, hb


# 07-R1 y criterio 1: bloqueado con la estrategia sin cerrar
def test_use_cases_locked_until_strategy_closed(client, pub):
    _, ha, *_ = pub
    r = client.get("/use-cases", headers=ha).json()
    assert r["enabled"] is False and r["locked_message"] == "Se habilita cuando la estrategia se cierre"
    assert client.post("/use-cases", headers=ha, json=CASE).status_code == 423


# 07-R4, R5, R6 y criterios 2, 3: complejidad = promedio de tres subpuntajes; impacto con fórmula visible y recalculable
def test_complexity_average_and_impact_formula(client, uc):
    ha, _ = uc
    cid = client.post("/use-cases", headers=ha, json=CASE).json()["id"]
    c = client.get(f"/use-cases/{cid}", headers=ha).json()
    assert c["complexity"] == 2.3                                    # 3, 2 y 2, como en el diseño
    assert c["hours_per_year"] == 1200.0 and c["formula"] == "casos al mes × minutos ahorrados ÷ 60 × 12"
    assert c["law_note"] and "1581" in c["law_note"]                 # 07-R7
    r = client.put(f"/use-cases/{cid}", headers=ha, json={**CASE, "volume_per_month": 500}).json()
    assert r["hours_per_year"] == 1500.0                             # con 500 casos, 1.500
    assert {"legal", "ethic", "infra"} == set(r["complexity_notes"])


def test_each_complexity_part_needs_justification(client, uc):
    ha, _ = uc
    assert client.post("/use-cases", headers=ha, json={**CASE, "ethic_note": "  "}).status_code == 422
    assert client.post("/use-cases", headers=ha, json={**CASE, "legal": 6}).status_code == 422


# 07-R2, R3 y criterio 5: cada caso cae en la zona que le corresponde
def test_matrix_zones(client, uc):
    ha, _ = uc
    mk = lambda n, imp_v, cx: client.post("/use-cases", headers=ha, json={**CASE, "name": n, "volume_per_month": imp_v, "legal": cx, "ethic": cx, "infra": cx})
    mk("quick", 400, 2); mk("estrategico", 400, 4); mk("menor", 50, 2); mk("reconsiderar", 50, 4)
    z = client.get("/use-cases", headers=ha).json()
    names = {c["n"]: c["name"] for c in z["cases"]}
    assert {k: sorted(names[n] for n in v) for k, v in z["zones"].items()} == \
           {"quick_win": ["quick"], "estrategico": ["estrategico"], "mejoras_menores": ["menor"], "reconsiderar": ["reconsiderar"]}


# 07-R8 y criterio 4: aprobar exige consultor y queda registrado
def test_approval_needs_consultant_and_is_audited(client, consultant, uc):
    ha, _ = uc
    cid = client.post("/use-cases", headers=ha, json=CASE).json()["id"]
    assert client.post(f"/use-cases/{cid}/status", headers=ha, json={"status": "approved"}).status_code == 404
    assert client.post(f"/use-cases/{cid}/status", headers=consultant, json={"status": "pilot"}).status_code == 409
    assert client.post(f"/use-cases/{cid}/status", headers=consultant, json={"status": "approved"}).status_code == 200
    c = client.get(f"/use-cases/{cid}", headers=ha).json()
    assert c["status"] == "approved" and c["approved_at"]
    assert "use_case.approved" in [a["action"] for a in client.get("/activity", headers=ha).json()]
    assert client.put(f"/use-cases/{cid}", headers=ha, json=CASE).status_code == 404       # la empresa ya no edita un caso aprobado
    assert client.post(f"/use-cases/{cid}/status", headers=consultant, json={"status": "pilot"}).status_code == 200


# 07-R9 revisión de sesgos, 07-R11 exportación con todos los casos y su estado
def test_bias_report_and_export(client, consultant, uc):
    ha, _ = uc
    a = client.post("/use-cases", headers=ha, json=CASE).json()["id"]
    client.post("/use-cases", headers=ha, json={**CASE, "name": "Otro", "area": "Riesgos"})
    client.post(f"/use-cases/{a}/status", headers=consultant, json={"status": "approved"})
    b = client.get("/use-cases/bias", headers=ha).json()
    assert {x["area"]: x["cases"] for x in b["areas"]} == {"Servicio al cliente": 1, "Riesgos": 1} and b["total"] == 2
    csv_text = client.get("/use-cases/export.csv", headers=ha).text
    assert csv_text.count("\n") == 3 and "approved" in csv_text and "proposed" in csv_text


# Las oportunidades de la estrategia se vuelven casos propuestos con etiqueta de IA (decisión 10)
def test_opportunities_become_proposed_cases(client, uc):
    ha, _ = uc
    assert client.post("/use-cases/from-opportunities", headers=ha).json() == {"created": 1}
    assert client.post("/use-cases/from-opportunities", headers=ha).json() == {"created": 0}   # no duplica
    c = client.get("/use-cases", headers=ha).json()["cases"][0]
    assert c["status"] == "proposed" and c["ai_proposed"] and "IA" in c["label"]


def test_use_cases_isolated(client, consultant, uc):
    ha, hb = uc
    cid = client.post("/use-cases", headers=ha, json=CASE).json()["id"]
    assert client.get(f"/use-cases/{cid}", headers=hb).status_code == 404
    assert client.get("/use-cases", headers=hb).json()["enabled"] is False
    assert client.put(f"/use-cases/{cid}", headers=hb, json=CASE).status_code == 404
