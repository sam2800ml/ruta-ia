import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from ..deps import NOT_FOUND, Ctx, audit, current_ctx
from ..llm import STAGE_KIND, STAGE_LABELS, STAGES, get_llm
from .company_profile import own_company_id

router = APIRouter(prefix="/strategy", tags=["strategy"])
DISCLOSURE = "Soy un asistente de IA. Solo hablo de la estrategia de IA de su empresa y no guardo nada sin su decisión."
LOCKED = "Se habilita cuando el diagnóstico se publique"


def _context(ctx: Ctx, cid: str) -> dict | None:
    """Datos del diagnóstico publicado: lo único que el asistente puede citar (06-R8)."""
    row = ctx.session.execute(text(
        "select p.pillar, p.score, (select (x->>'label') from methodology m, jsonb_array_elements(m.pillars) x "
        "  where m.version = r.methodology_version and x->>'key' = p.pillar) as label, r.level, r.average "
        "from report r join pillar_score p on p.report_id = r.id "
        "where r.status='published' and r.company_id = cast(:c as uuid) order by r.version desc, p.score asc limit 1"),
        {"c": cid}).mappings().first()
    if not row:
        return None
    return {"weakest": {"pillar": row["pillar"], "label": row["label"], "score": float(row["score"])},
            "level": row["level"], "average": float(row["average"])}


def _opener(ctx: Ctx, cid: str, stage: str, context: dict) -> None:
    turn = get_llm().strategy_turn(stage, context, [], None)
    msg = (DISCLOSURE + " " if stage == STAGES[0] else "") + turn.reply
    ctx.session.execute(text("insert into strategy_message(company_id, stage, author, text) values (cast(:c as uuid), :s, 'assistant', :t)"),
                        {"c": cid, "s": stage, "t": msg})


def _own_strategy(ctx: Ctx) -> tuple[str, dict]:
    if ctx.read_only or not ctx.company_id:
        raise NOT_FOUND
    context = _context(ctx, ctx.company_id)
    if not context:
        raise HTTPException(status_code=423, detail=LOCKED)
    return ctx.company_id, context


@router.post("/start")
def start(ctx: Ctx = Depends(current_ctx)):
    cid, context = _own_strategy(ctx)
    if ctx.session.execute(text("select 1 from strategy where company_id = cast(:c as uuid)"), {"c": cid}).first():
        return {"started": False}
    ctx.session.execute(text("insert into strategy(company_id, current_stage) values (cast(:c as uuid), :s)"), {"c": cid, "s": STAGES[0]})
    for i, st in enumerate(STAGES):
        ctx.session.execute(text("insert into strategy_stage(company_id, stage, position, status) values (cast(:c as uuid), :s, :p, :st)"),
                            {"c": cid, "s": st, "p": i, "st": "current" if i == 0 else "pending"})
    _opener(ctx, cid, STAGES[0], context)
    audit(ctx, "strategy.started", "strategy", cid, cid)
    return {"started": True}


@router.get("")
def state(company_id: str | None = None, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, company_id)
    context = _context(ctx, cid)
    if not context:
        return {"enabled": False, "locked_message": LOCKED}
    st = ctx.session.execute(text("select status, current_stage from strategy where company_id = cast(:c as uuid)"), {"c": cid}).mappings().first()
    if not st:
        return {"enabled": True, "started": False, "disclosure": DISCLOSURE}
    stages = ctx.session.execute(text("select stage, status from strategy_stage where company_id = cast(:c as uuid) order by position"), {"c": cid}).mappings().all()
    items = ctx.session.execute(text("select key, version, stage, kind, text, basis from strategy_item where status='active' and company_id = cast(:c as uuid) order by created_at"), {"c": cid}).mappings().all()
    msgs = ctx.session.execute(text("select stage, author, text, at from strategy_message where company_id = cast(:c as uuid) order by id"), {"c": cid}).mappings().all()
    props = ctx.session.execute(text("select id, stage, kind, text, basis from strategy_proposal where status='pending' and company_id = cast(:c as uuid) order by created_at"), {"c": cid}).mappings().all()
    return {"enabled": True, "started": True, "status": st["status"], "current_stage": st["current_stage"], "disclosure": DISCLOSURE,
            "stages": [{"key": s["stage"], "label": STAGE_LABELS[s["stage"]], "status": s["status"]} for s in stages],
            "items": [{**i, "key": str(i["key"])} for i in items], "messages": [dict(m) for m in msgs],
            "proposals": [{**p, "id": str(p["id"])} for p in props], "context": context}


class Msg(BaseModel):
    text: str


@router.post("/messages")
def message(body: Msg, ctx: Ctx = Depends(current_ctx)):
    cid, context = _own_strategy(ctx)
    st = ctx.session.execute(text("select status, current_stage from strategy where company_id = cast(:c as uuid)"), {"c": cid}).mappings().first()
    if not st or st["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="La conversación no está activa")
    stage = st["current_stage"]
    ctx.session.execute(text("insert into strategy_message(company_id, stage, author, text) values (cast(:c as uuid), :s, 'user', :t)"),
                        {"c": cid, "s": stage, "t": body.text})
    history = [dict(m) for m in ctx.session.execute(text("select author, text from strategy_message where company_id = cast(:c as uuid) and stage = :s order by id"), {"c": cid, "s": stage}).mappings()]
    turn = get_llm().strategy_turn(stage, context, history[:-1], body.text)
    ctx.session.execute(text("insert into strategy_message(company_id, stage, author, text) values (cast(:c as uuid), :s, 'assistant', :t)"),
                        {"c": cid, "s": stage, "t": turn.reply})
    proposal = None
    if turn.proposal:
        pid = uuid.uuid4()
        ctx.session.execute(text("insert into strategy_proposal(id, company_id, stage, kind, text, basis) values (:i, cast(:c as uuid), :s, :k, :t, :b)"),
                            {"i": pid, "c": cid, "s": stage, "k": turn.proposal["kind"], "t": turn.proposal["text"], "b": turn.proposal.get("basis")})
        proposal = {"id": str(pid), **turn.proposal}
    return {"reply": turn.reply, "proposal": proposal}


class Save(BaseModel):
    text: str | None = None


@router.post("/proposals/{proposal_id}/save", status_code=201)
def save_proposal(proposal_id: str, body: Save, ctx: Ctx = Depends(current_ctx)):
    """«Guardar» (o «Editar» y guardar). Nada se guarda sin esta decisión (06-R4)."""
    cid, _ = _own_strategy(ctx)
    p = ctx.session.execute(text("select * from strategy_proposal where id = cast(:i as uuid) and status='pending'"), {"i": proposal_id}).mappings().first() if _uuid(proposal_id) else None
    if not p:
        raise NOT_FOUND
    final = (body.text or p["text"]).strip()
    if not final:
        raise HTTPException(status_code=422, detail="El texto no puede quedar vacío")
    key = uuid.uuid4()
    ctx.session.execute(text("insert into strategy_item(company_id, key, stage, kind, text, basis) values (cast(:c as uuid), :k, :s, :kd, :t, :b)"),
                        {"c": cid, "k": key, "s": p["stage"], "kd": p["kind"], "t": final, "b": p["basis"]})
    ctx.session.execute(text("update strategy_proposal set status='saved' where id = cast(:i as uuid)"), {"i": proposal_id})
    return {"key": str(key), "version": 1}


@router.post("/proposals/{proposal_id}/discard")
def discard(proposal_id: str, ctx: Ctx = Depends(current_ctx)):
    _own_strategy(ctx)
    n = ctx.session.execute(text("update strategy_proposal set status='discarded' where id = cast(:i as uuid) and status='pending'"), {"i": proposal_id}).rowcount if _uuid(proposal_id) else 0
    if not n:
        raise NOT_FOUND
    return {"ok": True}


def _uuid(v: str) -> bool:
    try:
        uuid.UUID(v); return True
    except ValueError:
        return False


@router.put("/items/{key}")
def edit_item(key: str, body: Msg, ctx: Ctx = Depends(current_ctx)):
    """Editar un elemento guardado crea una versión nueva y conserva la anterior (06-R7)."""
    cid, _ = _own_strategy(ctx)
    cur = ctx.session.execute(text("select * from strategy_item where key = cast(:k as uuid) and status='active'"), {"k": key}).mappings().first() if _uuid(key) else None
    if not cur or not body.text.strip():
        raise NOT_FOUND if not cur else HTTPException(status_code=422, detail="El texto no puede quedar vacío")
    ctx.session.execute(text("update strategy_item set status='superseded' where id = :i"), {"i": cur["id"]})
    ctx.session.execute(text("insert into strategy_item(company_id, key, version, stage, kind, text, basis) values (cast(:c as uuid), :k, :v, :s, :kd, :t, :b)"),
                        {"c": cid, "k": cur["key"], "v": cur["version"] + 1, "s": cur["stage"], "kd": cur["kind"], "t": body.text.strip(), "b": cur["basis"]})
    return {"key": key, "version": cur["version"] + 1}


@router.get("/items/{key}/versions")
def versions(key: str, ctx: Ctx = Depends(current_ctx)):
    cid = own_company_id(ctx, None)
    rows = ctx.session.execute(text("select version, text, status, created_at from strategy_item where key = cast(:k as uuid) order by version"), {"k": key}).mappings().all() if _uuid(key) else []
    if not rows:
        raise NOT_FOUND
    return [dict(r) for r in rows]


@router.post("/stages/{stage}/complete")
def complete_stage(stage: str, ctx: Ctx = Depends(current_ctx)):
    """Una etapa está completa cuando tiene al menos un elemento guardado y la persona la da por cerrada (decisión 10, supuesto)."""
    cid, context = _own_strategy(ctx)
    if stage not in STAGES:
        raise NOT_FOUND
    cur = ctx.session.execute(text("select current_stage, status from strategy where company_id = cast(:c as uuid)"), {"c": cid}).mappings().first()
    if not cur or cur["current_stage"] != stage or cur["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="Esa no es la etapa actual")
    if not ctx.session.execute(text("select 1 from strategy_item where status='active' and stage = :s and company_id = cast(:c as uuid)"), {"s": stage, "c": cid}).first():
        raise HTTPException(status_code=409, detail="Guarda al menos un elemento antes de completar la etapa")
    ctx.session.execute(text("update strategy_stage set status='complete' where stage = :s and company_id = cast(:c as uuid)"), {"s": stage, "c": cid})
    i = STAGES.index(stage)
    if i + 1 < len(STAGES):
        nxt = STAGES[i + 1]
        ctx.session.execute(text("update strategy_stage set status='current' where stage = :s and company_id = cast(:c as uuid)"), {"s": nxt, "c": cid})
        ctx.session.execute(text("update strategy set current_stage = :s where company_id = cast(:c as uuid)"), {"s": nxt, "c": cid})
        _opener(ctx, cid, nxt, context)
        return {"closed": False, "current_stage": nxt}
    ctx.session.execute(text("update strategy set status='closed', closed_at=now() where company_id = cast(:c as uuid)"), {"c": cid})
    audit(ctx, "strategy.closed", "strategy", cid, cid)
    return {"closed": True}
