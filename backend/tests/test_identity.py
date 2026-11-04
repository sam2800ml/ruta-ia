"""Evidencia de la Feature 01. Cada prueba cita la tarea (01-Rn) que verifica."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

from app.config import settings
from app.security import hash_token
from tests.conftest import PASSWORD, login, make_company


# 01-R1 perfiles diferenciados
def test_login_profiles_and_bad_credentials(client, consultant, two_companies):
    (_, ha), _ = two_companies
    assert client.get("/auth/me", headers=consultant).json()["role"] == "consultant"
    assert client.get("/auth/me", headers=ha).json()["role"] == "company_user"
    r = client.post("/auth/login", json={"email": "a@a.example.com", "password": "incorrecta-123"})
    assert r.status_code == 401
    assert client.get("/auth/me").status_code == 401


# 01-R2 aislamiento (aplicación)
def test_company_user_gets_not_found_for_other_company(client, two_companies):
    (ida, ha), (idb, hb) = two_companies
    assert client.get(f"/companies/{ida}", headers=ha).status_code == 200
    r = client.get(f"/companies/{idb}", headers=ha)
    assert r.status_code == 404
    missing = client.get("/companies/00000000-0000-0000-0000-000000000000", headers=ha)
    assert r.json() == missing.json()  # no revela si el dato existe en otra empresa
    assert [c["id"] for c in client.get("/companies", headers=ha).json()] == [ida]


# 01-R2 aislamiento (base de datos): aunque la aplicación falle
def test_rls_blocks_cross_company_even_with_raw_sql(two_companies):
    (ida, _), (idb, _) = two_companies
    eng = create_engine(settings.database_url)
    with eng.begin() as c:
        owner, bypass = c.execute(text(
            "select pg_get_userbyid(c.relowner) = current_user, (select rolbypassrls from pg_roles where rolname = current_user) "
            "from pg_class c where relname = 'company'")).one()
        assert not owner and not bypass  # el rol de la app no es dueño ni se salta las políticas
        c.execute(text("select set_config('app.company_id', :c, true)"), {"c": ida})
        assert c.execute(text("select count(*) from company where id = :b"), {"b": idb}).scalar() == 0
        assert c.execute(text("select count(*) from company")).scalar() == 1
    # escritura cruzada rechazada por WITH CHECK
    with eng.connect() as c:
        try:
            with c.begin():
                c.execute(text("select set_config('app.company_id', :c, true)"), {"c": ida})
                c.execute(text("insert into survey_link(company_id, role_name, token_hash, expires_at) "
                               "values (:b, 'x', 'h', now() + interval '1 day')"), {"b": idb})
            raise AssertionError("debió fallar")
        except Exception as e:
            assert "row-level security" in str(e)


# 01-R3 invitar empresa
def test_invite_company_flow(client, consultant):
    r = client.post("/companies", json={"name": "X", "admin_email": "x@x.example.com"}, headers=consultant)
    assert r.status_code == 201 and r.json()["status"] == "invited"
    cid = r.json()["id"]
    assert client.get(f"/companies/{cid}", headers=consultant).json()["status"] == "invited"
    token = r.json()["invitation_token"]
    assert client.post("/auth/accept-invitation", json={"token": token, "password": PASSWORD}).status_code == 200
    assert client.get(f"/companies/{cid}", headers=consultant).json()["status"] == "active"
    # un solo uso, y una empresa no puede invitar
    assert client.post("/auth/accept-invitation", json={"token": token, "password": PASSWORD}).status_code == 400
    ha = login(client, "x@x.example.com")
    assert client.post("/companies", json={"name": "Y", "admin_email": "y@y.example.com"}, headers=ha).status_code == 404


# 01-R4 «Ver como empresa» es de solo lectura
def test_view_as_company_is_read_only(client, consultant, two_companies):
    (ida, _), (idb, _) = two_companies
    view = {**consultant, "X-View-As-Company": ida}
    assert [c["id"] for c in client.get("/companies", headers=view).json()] == [ida]
    assert client.get(f"/companies/{idb}", headers=view).status_code == 404
    assert client.post("/survey-links", json={"role_name": "TI"}, headers=view).status_code == 404
    assert client.post("/companies", json={"name": "Z", "admin_email": "z@z.example.com"}, headers=view).status_code == 404


def test_company_user_cannot_use_view_as(client, two_companies):
    (_, ha), (idb, _) = two_companies
    assert client.get("/companies", headers={**ha, "X-View-As-Company": idb}).status_code == 404


# 01-R5 enlaces de encuesta: un solo uso, ligados a empresa y rol, vencen
def test_survey_link_single_use_and_expiry(client, two_companies, admin):
    (ida, ha), _ = two_companies
    link = client.post("/survey-links", json={"role_name": "Tecnología"}, headers=ha).json()
    opened = client.get(f"/survey/{link['token']}").json()
    assert opened == {"company_id": ida, "role_name": "Tecnología"}
    assert client.post(f"/survey/{link['token']}/complete").status_code == 200
    assert client.get(f"/survey/{link['token']}").status_code == 404
    assert client.post(f"/survey/{link['token']}/complete").status_code == 404
    old = client.post("/survey-links", json={"role_name": "Finanzas"}, headers=ha).json()
    with admin.connect() as c:
        c.execute(text("update survey_link set expires_at = :x where token_hash = :h"),
                  {"x": datetime.now(timezone.utc) - timedelta(minutes=1), "h": hash_token(old["token"])})
    assert client.get(f"/survey/{old['token']}").status_code == 404
    assert client.get("/survey/token-inventado").status_code == 404


# 01-R6 auditoría con usuario y hora, y solo de adición
def test_audit_log_records_and_is_append_only(client, consultant, two_companies):
    (ida, ha), (idb, hb) = two_companies
    client.post("/survey-links", json={"role_name": "TI"}, headers=ha)
    eng = create_engine(settings.database_url)
    with eng.begin() as c:
        c.execute(text("select set_config('app.company_id', :c, true)"), {"c": ida})
        rows = c.execute(text("select action, actor_id, at from audit_log order by id")).all()
        assert [r.action for r in rows] == ["company.invited", "invitation.accepted", "survey_link.created"]
        assert all(r.at is not None for r in rows)
        assert rows[-1].actor_id is not None
    for stmt in ("update audit_log set action = 'x'", "delete from audit_log"):
        with eng.connect() as c:
            try:
                with c.begin():
                    c.execute(text("select set_config('app.is_consultant', 'on', true)"))
                    c.execute(text(stmt))
                raise AssertionError("debió fallar")
            except Exception as e:
                assert "permission denied" in str(e)
