"""Evidencia de la Feature 03."""
import re
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from tests.conftest import login, make_company

FUTURE = (date.today() + timedelta(days=10)).isoformat()


def tokens(admin, company_id=None):
    with admin.connect() as c:
        rows = c.execute(text("select to_email, body, kind from outbox_email order by id")).all()
    return [(r.to_email, re.search(r"encuesta=([\w-]+)", r.body).group(1), r.kind) for r in rows]


def new_survey(client, h, role="Tecnología", email="ti@example.com"):
    r = client.post("/surveys", headers=h, json={"role_name": role, "responsible": "Ana", "email": email, "deadline": FUTURE})
    assert r.status_code == 201, r.text
    return r.json()


def answer_all(client, token, value=4):
    qs = client.get(f"/survey/{token}/questions").json()["questions"]
    return client.post(f"/survey/{token}/answers", json={"answers": [{"question_id": q["id"], "value": value} for q in qs]})


# 03-R1, R2: rol con correo y encuesta con preguntas de su área (del banco)
def test_survey_created_with_role_questions_and_email(client, admin, two_companies):
    (_, ha), _ = two_companies
    ti = new_survey(client, ha, "Tecnología")
    fin = new_survey(client, ha, "Finanzas", "fin@example.com")
    assert ti["questions"] == fin["questions"] + 2  # Tecnología recibe sus 2 preguntas propias
    assert [t[0] for t in tokens(admin)] == ["ti@example.com", "fin@example.com"]
    assert client.post("/surveys", headers=ha, json={"role_name": "Tecnología", "responsible": "B", "email": "x@example.com", "deadline": FUTURE}).status_code == 409


# 03-R3 y criterio 2 / 01-R5: el enlace abre solo la encuesta de su rol; avance «n de m»
def test_link_opens_only_its_role_and_progress_shows(client, admin, two_companies):
    (_, ha), _ = two_companies
    new_survey(client, ha, "Tecnología"); new_survey(client, ha, "Finanzas", "fin@example.com")
    (_, t_ti, _), (_, t_fin, _) = tokens(admin)
    assert client.get(f"/survey/{t_ti}/questions").json()["role_name"] == "Tecnología"
    assert client.get(f"/survey/{t_fin}/questions").json()["role_name"] == "Finanzas"
    assert answer_all(client, t_ti).status_code == 200
    s = client.get("/surveys", headers=ha).json()
    assert (s["complete"], s["total"]) == (1, 2)
    assert client.get(f"/survey/{t_ti}/questions").status_code == 404   # usado
    assert client.post(f"/survey/{t_ti}/answers", json={"answers": []}).status_code == 404  # no se responde dos veces


def test_incomplete_or_invalid_answers_are_rejected(client, admin, two_companies):
    (_, ha), _ = two_companies
    new_survey(client, ha)
    (_, tok, _), = tokens(admin)
    qs = client.get(f"/survey/{tok}/questions").json()["questions"]
    assert client.post(f"/survey/{tok}/answers", json={"answers": [{"question_id": qs[0]["id"], "value": 3}]}).status_code == 404
    bad = [{"question_id": q["id"], "value": 9} for q in qs]
    assert client.post(f"/survey/{tok}/answers", json={"answers": bad}).status_code == 404
    assert client.get("/surveys", headers=ha).json()["complete"] == 0  # nada quedó a medias


# 03-R4 y criterio 5: el recordatorio no duplica ni borra respuestas completas
def test_reminders_only_to_pending_and_keep_answers(client, admin, two_companies):
    (_, ha), _ = two_companies
    a = new_survey(client, ha, "Tecnología"); b = new_survey(client, ha, "Finanzas", "fin@example.com")
    (_, t_ti, _), _ = tokens(admin)
    answer_all(client, t_ti)
    assert client.post("/surveys/remind-pending", headers=ha).json() == {"sent": 1}
    assert client.post(f"/surveys/{a['id']}/reminder", headers=ha).json() == {"sent": 0}
    assert tokens(admin)[-1][0] == "fin@example.com" and tokens(admin)[-1][2] == "reminder"
    with admin.connect() as c:
        assert c.execute(text("select count(*) from survey_answer")).scalar() > 0
        assert c.execute(text("select count(distinct survey_id) from survey_answer")).scalar() == 1


# criterio 6 / 01-R6: cada correo enviado queda en el registro
def test_every_email_is_audited(client, admin, two_companies):
    (_, ha), _ = two_companies
    new_survey(client, ha); client.post("/surveys/remind-pending", headers=ha)
    acts = [a["action"] for a in client.get("/activity", headers=ha).json()]
    assert "survey.email_invitation" in acts and "survey.email_reminder" in acts


# Editar el banco no cambia las encuestas ya enviadas (08-R6)
def test_bank_edits_do_not_change_sent_surveys(client, admin, two_companies):
    (_, ha), _ = two_companies
    new_survey(client, ha)
    (_, tok, _), = tokens(admin)
    before = client.get(f"/survey/{tok}/questions").json()["questions"]
    with admin.connect() as c:
        original = c.execute(text("select id, text from question")).all()
        c.execute(text("update question set text = 'CAMBIADO'"))
    try:
        assert client.get(f"/survey/{tok}/questions").json()["questions"] == before
    finally:
        with admin.connect() as c:
            for r in original:
                c.execute(text("update question set text = :t where id = :i"), {"t": r.text, "i": r.id})


# 03-R5, R6, R7 y criterio 3: formatos, minuto exacto y aviso sin marcas de tiempo
VTT = "WEBVTT\n\n00:01:05.000 --> 00:01:09.500\nNo tenemos política de IA.\n\n00:02:10.000 --> 00:02:12.000\nCada área prueba por su cuenta.\n"
SRT = "1\n00:00:03,000 --> 00:00:06,000\nHola a todos.\n"


def upload_t(client, h, name, data, roles="Tecnología,Finanzas"):
    return client.post("/transcripts", headers=h, data={"roles": roles, "duration_min": "45", "meeting_date": "2026-10-01"},
                       files={"file": (name, data, "text/plain")})


def test_transcripts_formats_and_timestamps(client, admin, two_companies):
    (_, ha), _ = two_companies
    v = upload_t(client, ha, "reunion.vtt", VTT).json()
    assert v["has_timestamps"] and v["warning"] is None and v["segments"] == 2
    assert upload_t(client, ha, "reunion.srt", SRT).json()["has_timestamps"]
    t = upload_t(client, ha, "notas.txt", "Linea uno\nLinea dos").json()
    assert not t["has_timestamps"] and "minuto" in t["warning"]
    from tests.samples import make_docx
    assert upload_t(client, ha, "acta.docx", make_docx(["Acta de la reunión"])).status_code == 201
    assert upload_t(client, ha, "x.mp3", b"ID3").status_code == 422
    with admin.connect() as c:
        row = c.execute(text("select start_sec, end_sec, text from transcript_segment s join transcript t on t.id = s.transcript_id "
                             "where t.name = 'reunion.vtt' order by position limit 1")).one()
    assert (row.start_sec, row.end_sec) == (65, 69)   # minuto 1:05 exacto
    listed = client.get("/transcripts", headers=ha).json()
    assert {x["status"] for x in listed} == {"analyzed"} and listed[0]["roles"] == ["Tecnología", "Finanzas"]


# 03-R8 y criterio 4: sin consentimiento la transcripción no es utilizable; el registro guarda quién y cuándo
def test_consent_required_to_use_transcripts(client, admin, two_companies):
    (_, ha), _ = two_companies
    assert upload_t(client, ha, "a.vtt", VTT).json()["usable"] is False
    assert client.get("/consent", headers=ha).json()["given"] is False
    assert client.post("/consent", headers=ha).status_code == 201
    assert upload_t(client, ha, "b.vtt", VTT).json()["usable"] is True
    with admin.connect() as c:
        row = c.execute(text("select user_id, at, text from consent")).one()
    assert row.user_id and row.at and "1581" in row.text


# 01-R2 también en encuestas y transcripciones
def test_survey_data_is_isolated(client, consultant, two_companies):
    (ida, ha), (idb, hb) = two_companies
    new_survey(client, ha); upload_t(client, ha, "a.vtt", VTT)
    assert client.get("/surveys", headers=hb).json()["total"] == 0
    assert client.get("/transcripts", headers=hb).json() == []
    assert client.get("/surveys", params={"company_id": ida}, headers=consultant).json()["total"] == 1
    assert client.post("/surveys", headers=consultant, json={"role_name": "TI", "responsible": "x", "email": "x@example.com", "deadline": FUTURE}).status_code == 404
