import re
from datetime import date, timedelta

from sqlalchemy import text

FUTURE = (date.today() + timedelta(days=10)).isoformat()
VALUES = {"governance": 1, "strategy": 2, "data": 4, "culture": 5}    # el resto: 3
CONTRA_Q = "Hay responsables claros de la calidad de los datos."


def survey_tokens(admin):
    with admin.connect() as c:
        rows = c.execute(text("select to_email, body from outbox_email where kind='invitation' order by id")).all()
    return {r.to_email: re.search(r"encuesta=([\w-]+)", r.body).group(1) for r in rows}


def respond(client, token, role_bias=None):
    qs = client.get(f"/survey/{token}/questions").json()["questions"]
    answers = []
    for q in qs:
        v = VALUES.get(q["pillar"], 3)
        if q["text"] == CONTRA_Q and role_bias:
            v = role_bias
        answers.append({"question_id": q["id"], "value": v})
    r = client.post(f"/survey/{token}/answers", json={"answers": answers})
    assert r.status_code == 200, r.text


def seed_evidence(client, h, admin):
    """Encuestas de dos roles con una contradicción, un documento y una transcripción con consentimiento."""
    for role, mail in (("Tecnología", "ti@example.com"), ("Finanzas", "fin@example.com")):
        r = client.post("/surveys", headers=h, json={"role_name": role, "responsible": "R", "email": mail, "deadline": FUTURE})
        assert r.status_code == 201, r.text
    t = survey_tokens(admin)
    respond(client, t["ti@example.com"], role_bias=5)
    respond(client, t["fin@example.com"], role_bias=1)
    client.post("/documents", headers=h, data={"doc_type": "plan_estrategico"},
                files={"file": ("plan.txt", "No tenemos política de IA aprobada. Contamos con infraestructura en la nube.".encode(), "text/plain")})
    client.post("/consent", headers=h)
    vtt = "WEBVTT\n\n00:03:10.000 --> 00:03:14.000\nCada área prueba herramientas de IA por su cuenta, sin coordinación ni política.\n"
    client.post("/transcripts", headers=h, data={"roles": "Tecnología"}, files={"file": ("reunion.vtt", vtt, "text/plain")})


def generate(client, h):
    r = client.post("/reports", headers=h)
    assert r.status_code == 202, r.text
    return r.json()["id"]


def publish_report(client, consultant, ha, admin):
    seed_evidence(client, ha, admin)
    rid = generate(client, ha)
    r = client.get(f"/review/{rid}", headers=consultant).json()
    for kind, key in (("pillar", "pillars"), ("finding", "findings"), ("recommendation", "recommendations")):
        for b in r[key]:
            resp = client.post(f"/review/{rid}/blocks/{kind}/{b['id']}", headers=consultant, json={"action": "accept"})
            assert resp.status_code == 200, resp.text
    assert client.post(f"/review/{rid}/publish", headers=consultant).status_code == 200
    return rid


STAGES = ["vision", "objetivos", "gobernanza", "oportunidades", "okrs"]


def close_strategy(client, ha):
    client.post("/strategy/start", headers=ha)
    for st in STAGES:
        r = client.post("/strategy/messages", headers=ha, json={"text": f"Contenido de {st}"})
        pid = r.json()["proposal"]["id"]
        assert client.post(f"/strategy/proposals/{pid}/save", headers=ha, json={}).status_code == 201
        assert client.post(f"/strategy/stages/{st}/complete", headers=ha).status_code == 200
