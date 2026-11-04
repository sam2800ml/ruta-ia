import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import settings
from app.main import app
from app.security import hash_password

PASSWORD = "contraseña-larga-1"


@pytest.fixture(scope="session")
def admin():
    eng = create_engine(settings.admin_database_url, isolation_level="AUTOCOMMIT")
    yield eng


@pytest.fixture(scope="session")
def bank(admin):
    with admin.connect() as c:
        yield [r.id for r in c.execute(text("select id from question"))]


@pytest.fixture(autouse=True)
def clean(admin, bank, monkeypatch):
    monkeypatch.setattr(settings, "inline_jobs", True)
    with admin.connect() as c:
        c.execute(text("truncate audit_log, survey_link, invitation, app_user, company, baseline_measure, eval_run, sus_response restart identity cascade"))
        c.execute(text("delete from question where id <> all(:ids)"), {"ids": bank})
        c.execute(text("update question set active = true"))
        c.execute(text("delete from methodology where version > 1"))
        c.execute(text("update methodology set active = (version = 1)"))
        c.execute(text("insert into app_user(email, password_hash, role) values ('consultor@icesi.example.com', :p, 'consultant')"),
                  {"p": hash_password(PASSWORD)})


@pytest.fixture
def client():
    return TestClient(app)


def login(client, email, password=PASSWORD):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def consultant(client):
    return login(client, "consultor@icesi.example.com")


def make_company(client, consultant, name, email, nit=None):
    r = client.post("/companies", json={"name": name, "nit": nit, "admin_email": email}, headers=consultant)
    assert r.status_code == 201, r.text
    body = r.json()
    r2 = client.post("/auth/accept-invitation", json={"token": body["invitation_token"], "password": PASSWORD})
    assert r2.status_code == 200, r2.text
    return body["id"], {"Authorization": f"Bearer {r2.json()['access_token']}"}


@pytest.fixture
def two_companies(client, consultant):
    a = make_company(client, consultant, "Banco A", "a@a.example.com", "111")
    b = make_company(client, consultant, "Empresa B", "b@b.example.com", "222")
    return a, b
