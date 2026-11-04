"""Evidencia de las Features 08 y 09."""
import pytest
from sqlalchemy import text

from tests.helpers import close_strategy, generate, publish_report, seed_evidence
from tests.test_strategy import CASE


@pytest.fixture
def world(client, admin, consultant, two_companies):
    """A: publicado, estrategia cerrada y un caso aprobado. B: informe en revisión."""
    (ida, ha), (idb, hb) = two_companies
    publish_report(client, consultant, ha, admin)
    close_strategy(client, ha)
    cid = client.post("/use-cases", headers=ha, json=CASE).json()["id"]
    client.post(f"/use-cases/{cid}/status", headers=consultant, json={"status": "approved"})
    seed_evidence(client, hb, admin)
    generate(client, hb)
    return ida, ha, idb, hb


# 08-R1 y criterio 1: los cuatro indicadores coinciden con un conteo manual
def test_dashboard_kpis_match_manual_count(client, admin, consultant, world):
    ida, ha, idb, hb = world
    d = client.get("/admin/dashboard", headers=consultant).json()
    with admin.connect() as c:
        manual = {"active": c.execute(text("select count(*) from company where status='active'")).scalar(),
                  "pending": c.execute(text("select count(*) from report where status='in_review'")).scalar(),
                  "avg": float(c.execute(text("select average from report where status='published'")).scalar()),
                  "cases": c.execute(text("select count(*) from use_case where status='approved'")).scalar()}
    assert (d["active_companies"], d["reviews_pending"], d["avg_maturity"], d["approved_use_cases"]) == \
           (manual["active"], manual["pending"], round(manual["avg"], 2), manual["cases"]) == (2, 1, round(manual["avg"], 2), 1)


# 08-R5 y criterio 6: promedio por pilar solo con empresas con diagnóstico, lo declara y destaca los < 2
def test_pillar_average_declares_support_and_flags_low(client, consultant, world):
    d = client.get("/admin/dashboard", headers=consultant).json()
    gov = next(p for p in d["pillar_average"] if p["pillar"] == "governance")
    assert (gov["supported_by"], gov["of"]) == (1, 2) and gov["low"] is True and gov["avg"] == 1.0
    culture = next(p for p in d["pillar_average"] if p["pillar"] == "culture")
    assert culture["low"] is False
    assert d["companies_with_diagnosis"] == 1                       # B no cuenta: su informe no está publicado


# 08-R2 y criterio 2: búsqueda por nombre o NIT, etapa, madurez y avance
def test_company_table_search_and_stage(client, consultant, world):
    ida, *_ = world
    assert [c["id"] for c in client.get("/admin/companies", params={"q": "banco a"}, headers=consultant).json()] == [ida]
    assert [c["id"] for c in client.get("/admin/companies", params={"q": "111"}, headers=consultant).json()] == [ida]
    allc = {c["name"]: c for c in client.get("/admin/companies", headers=consultant).json()}
    a, b = allc["Banco A"], allc["Empresa B"]
    assert a["stage"] == "Casos de uso" and a["progress"] == "4 de 4" and a["maturity"]["level"] in (1, 2, 3, 4, 5)
    assert b["maturity"] is None and b["stage"] == "Diagnóstico"


# 08-R3, R4, R10 y criterio 4: solo el equipo consultor; la empresa no abre ninguna pantalla de administración
def test_admin_is_consultant_only(client, world):
    _, ha, *_ = world
    for path in ("/admin/dashboard", "/admin/companies", "/admin/questions", "/admin/methodology", "/admin/analytics",
                 "/eval/summary", "/eval/baseline", "/eval/runs", "/review/queue"):
        assert client.get(path, headers=ha).status_code == 404, path
    assert client.get("/admin/dashboard").status_code == 401


# 08-R6, R7: versiones del banco y metadatos por pregunta
def test_question_bank_versions_and_metadata(client, consultant):
    qs = client.get("/admin/questions", params={"pillar": "data"}, headers=consultant).json()
    assert qs and all({"pillar", "roles", "answer_type", "contribution"} <= set(q) for q in qs)
    assert all(q["answer_type"] == "Escala de 1 a 5" and q["contribution"].startswith("Peso") for q in qs)
    new = client.post("/admin/questions", headers=consultant, json={"text": "¿Hay un catálogo de datos vigente?", "pillar": "data", "roles": ["Tecnología"], "weight": 2}).json()
    edited = client.put(f"/admin/questions/{new['key']}", headers=consultant, json={"text": "¿Hay un catálogo de datos actualizado?", "pillar": "data", "roles": ["Tecnología"], "weight": 2}).json()
    assert edited["version"] == 2 and edited["key"] == new["key"]
    actives = [q for q in client.get("/admin/questions", headers=consultant).json() if q["key"] == new["key"]]
    assert [q["version"] for q in actives] == [2]
    assert client.post("/admin/questions", headers=consultant, json={"text": "Pregunta rara", "pillar": "magia"}).status_code == 422
    assert client.delete(f"/admin/questions/{new['key']}", headers=consultant).status_code == 200
    assert not [q for q in client.get("/admin/questions", headers=consultant).json() if q["key"] == new["key"]]
    only_ti = client.get("/admin/questions", params={"role": "Finanzas"}, headers=consultant).json()
    assert all(q["roles"] == ["Todos"] for q in only_ti)


# 08-R8 y criterio 5: cada informe indica con qué versión de metodología se calculó
def test_reports_keep_methodology_version(client, admin, consultant, two_companies):
    (_, ha), _ = two_companies
    seed_evidence(client, ha, admin)
    r1 = client.get(f"/review/{generate(client, ha)}", headers=consultant).json()
    assert r1["methodology_version"] == 1
    levels = [{"level": i, "name": f"N{i}", "description": "x"} for i in range(1, 6)]
    assert client.post("/admin/methodology", headers=consultant, json={"levels": levels, "thresholds": [1, 2, 3, 4], "formula": "v2"}).json() == {"version": 2}
    assert client.post("/admin/methodology", headers=consultant, json={"levels": levels, "thresholds": [4, 3, 2, 1], "formula": "mal"}).status_code == 422
    r2 = client.get(f"/review/{generate(client, ha)}", headers=consultant).json()
    assert r2["methodology_version"] == 2 and r2["level_name"].startswith("N")
    assert client.get(f"/review/{r1['id']}", headers=consultant).json()["methodology_version"] == 1
    m = client.get("/admin/methodology", headers=consultant).json()
    assert [(x["version"], x["reports"], x["active"]) for x in m] == [(2, 1, True), (1, 1, False)]


# 08-R9 y 05-R10: analítica desde los registros
def test_analytics_computed_from_records(client, admin, consultant, world):
    a = client.get("/admin/analytics", headers=consultant).json()
    rp = a["review_proportions"]
    assert rp["finding"]["share"]["accept"] == 1.0 and rp["pillar"]["total"] == 6
    assert a["human_control"]["share"] == 1.0 and a["evidence"]["share"] == 1.0
    assert a["avg_generation_seconds"] is not None and a["reports"] == 2 and a["avg_hours_to_publish"] is not None
    with admin.connect() as c:
        n = c.execute(text("select count(*) from (select distinct on (block_type, block_id) 1 from review_decision order by block_type, block_id, id desc) x")).scalar()
    assert sum(v["total"] for v in rp.values()) == n


# ---------- Feature 09 ----------
def test_sus_formula(client, consultant):
    assert client.post("/eval/sus", headers=consultant, json={"answers": [5, 1] * 5}).json()["score"] == 100.0
    assert client.post("/eval/sus", headers=consultant, json={"answers": [3] * 10}).json()["score"] == 50.0
    assert client.post("/eval/sus", headers=consultant, json={"answers": [5, 1, 5]}).status_code == 422
    assert client.post("/eval/sus", headers=consultant, json={"answers": [9] + [1] * 9}).status_code == 422


@pytest.fixture
def evaluated(client, consultant, world):
    ida, *_ = world
    for hours, with_sys in ((10, False), (8, False), (3, True)):
        assert client.post("/eval/baseline", headers=consultant, json={"task": "Diagnóstico", "hours": hours, "with_system": with_sys}).status_code == 201
    client.post("/eval/sus", headers=consultant, json={"answers": [5, 1] * 5})
    pub = client.get("/reports/published", headers=world[1]).json()
    ref = {"pillar_scores": {p["pillar"]: p["score"] + 0.5 for p in pub["pillars"]},
           "top3": [p["pillar"] for p in sorted(pub["pillars"], key=lambda p: p["score"])[:3]]}
    case = client.post("/eval/reference-cases", headers=consultant, json={"name": "Caso 1", "system_company_id": ida, "inputs": {"nota": "anonimizado"}, "reference": ref}).json()["id"]
    for crit in ("precision", "evidencia", "accionabilidad", "claridad", "completitud"):
        assert client.post("/eval/rubric", headers=consultant, json={"case_id": case, "criterion": crit, "value": 5}).status_code == 201
    return case


# 09-R1, R4: línea base y ahorro de tiempo; 09-R3, R7: rúbrica y SUS; metas y cumplimiento
def test_metrics_vs_goals(client, consultant, evaluated):
    s = client.get("/eval/summary", headers=consultant).json()
    m = s["metrics"]
    assert m["time_saving"] == round(1 - 3 / 9, 3) and s["met"]["time_saving"] is True
    assert m["sus"] == 100.0 and m["quality"] == 5.0 and m["human_control"] == 1.0 and m["evidence"] == 1.0
    assert m["top3"] == 1.0 and all(v is True for v in s["met"].values())
    assert s["goals"]["quality"] == 4.2 and s["goals"]["sus"] == 75.0
    assert client.post("/eval/rubric", headers=consultant, json={"case_id": evaluated, "criterion": "belleza", "value": 5}).status_code == 422


# 09-R9 y criterio 5: informe caso por caso frente al entregable humano
def test_case_by_case_comparison(client, consultant, evaluated):
    run = client.post("/eval/runs", headers=consultant).json()
    rep = client.get(f"/eval/runs/{run['id']}/report", headers=consultant).json()
    c = rep["cases"][0]
    assert c["compared"] and c["avg_pillar_diff"] == 0.5 and set(c["system_top3"]) == set(c["reference_top3"]) and c["rubric_avg"] == 5.0


# 09-R8 y criterios 2, 3: la evaluación se repite igual y cada resultado queda ligado a una versión
def test_runs_are_reproducible_and_versioned(client, consultant, evaluated):
    r1 = client.post("/eval/runs", headers=consultant).json()
    r2 = client.post("/eval/runs", headers=consultant).json()
    assert r1["results"]["metrics"] == r2["results"]["metrics"] and r1["results"]["cases"] == r2["results"]["cases"]
    assert r1["system_version"] == "0.1.0" and r1["config"]["methodology_version"] == 1 and r1["config"]["llm_provider"] == "stub"
    runs = client.get("/eval/runs", headers=consultant).json()
    assert len(runs) == 2 and all(r["system_version"] and r["config"] for r in runs)


def test_eval_results_cannot_be_rewritten(client, admin, consultant, evaluated):
    from sqlalchemy import create_engine
    from app.config import settings
    client.post("/eval/runs", headers=consultant)
    eng = create_engine(settings.database_url)
    for stmt in ("update eval_run set results = '{}'", "delete from eval_run", "update baseline_measure set hours = 0"):
        with eng.connect() as c:
            try:
                with c.begin():
                    c.execute(text("select set_config('app.is_consultant', 'on', true)"))
                    c.execute(text(stmt))
                raise AssertionError("debió fallar")
            except Exception as e:
                assert "permission denied" in str(e), stmt
