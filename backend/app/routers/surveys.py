import json
import pathlib
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..deps import NOT_FOUND, Ctx, audit, current_ctx, db_anonymous, run_job
from ..security import hash_token, new_token
from ..transcripts import parse
from .company_profile import own_company_id

router = APIRouter(tags=["surveys"])
CONSENT_TEXT = ("Confirmo que los participantes de las reuniones fueron informados y autorizaron el uso de "
                "sus transcripciones para el diagnóstico, conforme a la Ley 1581 de 2012.")


def _need_company(ctx: Ctx) -> str:
    if ctx.read_only or not ctx.company_id:
        raise NOT_FOUND
    return ctx.company_id


class NewSurvey(BaseModel):
    role_name: str
    responsible: str
    email: EmailStr
    deadline: date


def _issue_link_and_email(ctx: Ctx, survey_id: str, role: str, email: str, deadline: date, kind: str) -> None:
    raw, h = new_token()
    exp = datetime.combine(deadline, datetime.max.time(), tzinfo=timezone.utc)
    ctx.session.execute(
        text("insert into survey_link(company_id, role_name, token_hash, expires_at, survey_id) "
             "values (cast(:c as uuid), :r, :h, :x, cast(:s as uuid))"),
        {"c": ctx.company_id, "r": role, "h": h, "x": exp, "s": survey_id})
    link = f"{settings.public_url}/?encuesta={raw}"
    subject = "Recordatorio: tu encuesta de adopción de IA" if kind == "reminder" else "Encuesta de adopción de IA"
    ctx.session.execute(
        text("insert into outbox_email(company_id, to_email, subject, body, kind) values (cast(:c as uuid), :t, :s, :b, :k)"),
        {"c": ctx.company_id, "t": email, "s": subject,
         "b": f"Hola. Responde la encuesta como «{role}» antes del {deadline.isoformat()}: {link}", "k": kind})
    audit(ctx, f"survey.email_{kind}", "survey", survey_id, ctx.company_id, to=email)  # 01-R6: cada correo queda registrado


@router.post("/surveys", status_code=201)
def create_survey(body: NewSurvey, ctx: Ctx = Depends(current_ctx)):
    cid = _need_company(ctx)
    if body.deadline < date.today():
        raise HTTPException(status_code=422, detail="La fecha límite ya pasó")
    qs = ctx.session.execute(text("select survey_questions_for_role(:r)"), {"r": body.role_name}).scalar_one()
    if not qs:
        raise HTTPException(status_code=422, detail="No hay preguntas para ese rol")
    try:
        sid = ctx.session.execute(
            text("insert into survey(company_id, role_name, responsible, email, deadline, questions) "
                 "values (cast(:c as uuid), :r, :p, :e, :d, cast(:q as jsonb)) returning id"),
            {"c": cid, "r": body.role_name, "p": body.responsible, "e": body.email, "d": body.deadline,
             "q": json.dumps(qs)}).scalar_one()
    except Exception:
        raise HTTPException(status_code=409, detail="Ese rol ya tiene una encuesta")
    _issue_link_and_email(ctx, str(sid), body.role_name, body.email, body.deadline, "invitation")
    return {"id": str(sid), "role_name": body.role_name, "status": "pending", "questions": len(qs)}


def _surveys(ctx: Ctx, cid: str) -> list[dict]:
    rows = ctx.session.execute(
        text("select id, role_name, responsible, email, status, deadline, jsonb_array_length(questions) as total "
             "from survey where company_id = cast(:c as uuid) order by created_at"), {"c": cid}).mappings().all()
    return [{**r, "id": str(r["id"]), "deadline": r["deadline"].isoformat()} for r in rows]


@router.get("/surveys")
def list_surveys(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    items = _surveys(ctx, cid)
    done = sum(1 for s in items if s["status"] == "complete")
    return {"surveys": items, "complete": done, "total": len(items)}


@router.post("/surveys/{survey_id}/reminder")
def remind_one(survey_id: str, ctx: Ctx = Depends(current_ctx)):
    cid = _need_company(ctx)
    s = ctx.session.execute(
        text("select id, role_name, email, deadline, status from survey where id = cast(:i as uuid)"), {"i": survey_id}
    ).mappings().first() if _is_uuid(survey_id) else None
    if not s:
        raise NOT_FOUND
    if s["status"] == "complete":
        return {"sent": 0}  # no duplica ni toca respuestas ya completas
    _issue_link_and_email(ctx, str(s["id"]), s["role_name"], s["email"], max(s["deadline"], date.today()), "reminder")
    return {"sent": 1}


@router.post("/surveys/remind-pending")
def remind_all(ctx: Ctx = Depends(current_ctx)):
    cid = _need_company(ctx)
    rows = ctx.session.execute(
        text("select id, role_name, email, deadline from survey where status='pending' and company_id = cast(:c as uuid)"),
        {"c": cid}).mappings().all()
    for s in rows:
        _issue_link_and_email(ctx, str(s["id"]), s["role_name"], s["email"], max(s["deadline"], date.today()), "reminder")
    return {"sent": len(rows)}


def _is_uuid(v: str) -> bool:
    import uuid
    try:
        uuid.UUID(v); return True
    except ValueError:
        return False


@router.get("/outbox")
def outbox(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    """Bandeja de salida. El envío por proveedor de correo se conecta aquí (hoy los correos quedan en cola)."""
    cid = own_company_id(ctx, company_id)
    rows = ctx.session.execute(
        text("select id, to_email, subject, body, kind, created_at, sent_at from outbox_email "
             "where company_id = cast(:c as uuid) order by id desc limit 100"), {"c": cid}).mappings().all()
    return [dict(r) for r in rows]


# ---- Persona que responde (sin cuenta) ----
class Answers(BaseModel):
    answers: list[dict]


@router.get("/survey/{token}/questions")
def survey_questions(token: str, s: Session = Depends(db_anonymous)):
    row = s.execute(text("select * from auth_survey_open(:h)"), {"h": hash_token(token)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Enlace inválido o vencido")
    qs = [{"id": q["id"], "text": q["text"], "pillar": q["pillar"]} for q in row["questions"]]
    return {"role_name": row["role_name"], "questions": qs}


@router.post("/survey/{token}/answers")
def submit_answers(token: str, body: Answers, s: Session = Depends(db_anonymous)):
    ok = s.execute(text("select auth_survey_submit(:h, cast(:a as jsonb))"),
                   {"h": hash_token(token), "a": json.dumps(body.answers)}).scalar_one()
    if not ok:
        raise HTTPException(status_code=404, detail="Enlace inválido, vencido o respuestas incompletas")
    return {"ok": True}


# ---- Consentimiento y transcripciones ----
@router.get("/consent")
def get_consent(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    row = ctx.session.execute(
        text("select user_id, at from consent where company_id = cast(:c as uuid) order by at desc limit 1"),
        {"c": cid}).mappings().first()
    return {"text": CONSENT_TEXT, "given": bool(row), "at": row["at"] if row else None}


@router.post("/consent", status_code=201)
def give_consent(ctx: Ctx = Depends(current_ctx)):
    cid = _need_company(ctx)
    ctx.session.execute(
        text("insert into consent(company_id, user_id, text) values (cast(:c as uuid), cast(:u as uuid), :t)"),
        {"c": cid, "u": ctx.user_id, "t": CONSENT_TEXT})
    audit(ctx, "consent.given", "consent", cid, cid)
    return {"given": True}


def _mark_analyzed(company_id: str, transcript_id: str) -> None:
    from ..deps import _apply
    from ..db import engine
    with Session(engine) as s, s.begin():
        _apply(s, company_id=company_id, consultant=False, read_only=False)
        s.execute(text("update transcript set status='analyzed' where id = cast(:i as uuid) and status='analyzing'"),
                  {"i": transcript_id})


@router.post("/transcripts", status_code=201)
async def upload_transcript(file: UploadFile = File(...), meeting_date: date | None = Form(None),
                            duration_min: int | None = Form(None), roles: str = Form(""),
                            ctx: Ctx = Depends(current_ctx)):
    cid = _need_company(ctx)
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if not data or len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Archivo vacío o de más de 25 MB")
    name = pathlib.Path(file.filename or "transcripcion").name
    try:
        segs, has_ts = parse(name, data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e) if isinstance(e, ValueError) else "No se pudo leer el archivo")
    if not segs:
        raise HTTPException(status_code=422, detail="La transcripción no tiene texto")
    role_list = [r.strip() for r in roles.split(",") if r.strip()]
    consent_id = ctx.session.execute(
        text("select id from consent where company_id = cast(:c as uuid) order by at desc limit 1"), {"c": cid}).scalar()
    tid = ctx.session.execute(
        text("insert into transcript(company_id, name, meeting_date, duration_min, roles, has_timestamps, consent_id) "
             "values (cast(:c as uuid), :n, :d, :m, :r, :h, :k) returning id"),
        {"c": cid, "n": name, "d": meeting_date, "m": duration_min, "r": role_list, "h": has_ts, "k": consent_id}).scalar_one()
    for i, (a, b, body) in enumerate(segs):
        ctx.session.execute(
            text("insert into transcript_segment(company_id, transcript_id, position, start_sec, end_sec, text) "
                 "values (cast(:c as uuid), :t, :p, :a, :b, :x)"), {"c": cid, "t": tid, "p": i, "a": a, "b": b, "x": body})
    audit(ctx, "transcript.uploaded", "transcript", str(tid), cid, name=name, usable=bool(consent_id))
    ctx.after_commit.append(lambda: _mark_analyzed(cid, str(tid)))
    return {"id": str(tid), "name": name, "has_timestamps": has_ts, "usable": bool(consent_id),
            "warning": None if has_ts else "Sin marcas de tiempo: no se podrá citar el minuto exacto",
            "segments": len(segs)}


@router.get("/transcripts")
def list_transcripts(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    rows = ctx.session.execute(
        text("select id, name, meeting_date, duration_min, roles, has_timestamps, status, (consent_id is not null) as usable "
             "from transcript where company_id = cast(:c as uuid) order by created_at"), {"c": cid}).mappings().all()
    return [{**r, "id": str(r["id"])} for r in rows]


@router.get("/activity")
def activity(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    rows = ctx.session.execute(
        text("select action, entity, detail, at from audit_log where company_id = cast(:c as uuid) "
             "order by id desc limit 20"), {"c": cid}).mappings().all()
    return [dict(r) for r in rows]
