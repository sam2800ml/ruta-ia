"""Motor del diagnóstico (Feature 04).

1) Puntaje por reglas fijas (sin modelo).  2) Hallazgos con evidencia: reglas sobre encuestas + candidatos del modelo
sobre documentos y transcripciones.  3) Cada evidencia se verifica contra su fuente; sin verificación, el hallazgo
queda «insuficiente» y no se puede publicar sin que el consultor lo edite.  4) Recomendaciones ligadas a hallazgos.
"""
import json
import time
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import engine
from .deps import _apply
from .llm import LLM, get_llm

BRECHA_MAX = 2.5
FORTALEZA_MIN = 3.5
CONTRADICTION_GAP = 3
RECS = {
    "strategy": "Formalizar una estrategia de IA con objetivos, responsables y presupuesto.",
    "infrastructure": "Definir un entorno seguro de pruebas y una arquitectura de integración para cargas de IA.",
    "data": "Establecer dueños y estándares de calidad para los datos prioritarios.",
    "governance": "Aprobar una política de uso responsable de la IA y un comité que autorice los casos.",
    "talent": "Diseñar un plan de formación y definir los perfiles necesarios para IA.",
    "culture": "Promover la experimentación guiada y comunicar el propósito de la IA a los equipos.",
}


def level_for(avg: float, thresholds: list[float]) -> int:
    return 1 + sum(1 for t in thresholds if avg >= t)


def pillar_scores(answers: list[dict]) -> dict[str, tuple[float, int]]:
    acc: dict[str, list] = defaultdict(lambda: [0.0, 0.0, 0])
    for a in answers:
        w = float(a["weight"])
        acc[a["pillar"]][0] += a["value"] * w
        acc[a["pillar"]][1] += w
        acc[a["pillar"]][2] += 1
    return {p: (round(s / w, 2), n) for p, (s, w, n) in acc.items()}


def verify_evidence(s: Session, ev: dict) -> bool:
    """La evidencia existe en su fuente original y dice lo que se cita."""
    sid = ev["source_id"]
    if ev["source_type"] == "survey":
        row = s.execute(text("select question_text, value from survey_answer where id = cast(:i as uuid)"), {"i": sid}).first()
        return bool(row) and ev["quote"] == f"{row.question_text} → {row.value}"
    table, col = {"document": ("fragment", "text"), "transcript": ("transcript_segment", "text")}[ev["source_type"]]
    row = s.execute(text(f"select {col} from {table} where id = cast(:i as uuid)"), {"i": sid}).first()
    return bool(row) and bool(ev["quote"].strip()) and ev["quote"].strip() in row[0]


def _add_finding(s: Session, cid: str, rid: str, pos: int, kind, pillar, title, description, evidence: list[dict]) -> str:
    verified = bool(evidence) and all(verify_evidence(s, e) for e in evidence)
    fid = s.execute(
        text("insert into finding(company_id, report_id, position, kind, pillar, title, description, evidence_status) "
             "values (cast(:c as uuid), cast(:r as uuid), :p, :k, :pl, :t, :d, :e) returning id"),
        {"c": cid, "r": rid, "p": pos, "k": kind, "pl": pillar, "t": title, "d": description,
         "e": "verificada" if verified else "insuficiente"}).scalar_one()
    for e in evidence:
        s.execute(text("insert into evidence(company_id, finding_id, source_type, source_id, ref, quote) "
                       "values (cast(:c as uuid), :f, :st, cast(:si as uuid), cast(:ref as jsonb), :q)"),
                  {"c": cid, "f": fid, "st": e["source_type"], "si": e["source_id"], "ref": json.dumps(e.get("ref", {})), "q": e["quote"]})
    return str(fid)


def generate(company_id: str, report_id: str, llm: LLM | None = None) -> None:
    """Trabajo en segundo plano. Corre con el contexto del sistema (equipo consultor) para escribir el informe."""
    llm = llm or get_llm()
    t0 = time.time()
    with Session(engine) as s, s.begin():
        _apply(s, company_id=company_id, consultant=True, read_only=False)
        try:
            with s.begin_nested():       # si algo falla se deshace todo lo del informe, sin contenido a medias
                _generate(s, company_id, report_id, llm)
            status, err = "in_review", None
        except Exception as e:
            status, err = "error", str(e)[:300]
        secs = round(time.time() - t0, 3)
        s.execute(text("update report set status=:st, error=:e, seconds=:sec where id = cast(:r as uuid)"),
                  {"st": status, "e": err, "sec": secs, "r": report_id})
        s.execute(text("insert into llm_usage(company_id, report_id, kind, provider, seconds) values (cast(:c as uuid), cast(:r as uuid), 'diagnosis', :p, :s)"),
                  {"c": company_id, "r": report_id, "p": llm.name, "s": secs})


def _generate(s: Session, cid: str, rid: str, llm: LLM) -> None:
    meth = s.execute(text("select version, pillars, thresholds from methodology where active order by version desc limit 1")).mappings().one()
    labels = {p["key"]: p["label"] for p in meth["pillars"]}
    answers = [dict(r) for r in s.execute(text(
        "select id, question_key, question_text, pillar, weight, role_name, value from survey_answer where company_id = cast(:c as uuid)"),
        {"c": cid}).mappings()]
    if not answers:
        raise ValueError("No hay respuestas de encuesta")
    scores = pillar_scores(answers)
    avg = round(sum(v[0] for v in scores.values()) / len(scores), 2)
    surveys = s.execute(text("select role_name, status from survey where company_id = cast(:c as uuid)"), {"c": cid}).all()
    docs = s.execute(text("select distinct d.name from document d where d.status='processed' and d.company_id = cast(:c as uuid)"), {"c": cid}).scalars().all()
    trs = s.execute(text("select name from transcript where consent_id is not null and company_id = cast(:c as uuid)"), {"c": cid}).scalars().all()
    s.execute(text("update report set methodology_version=:m, level=:l, average=:a, roles_responded=:rr, roles_total=:rt, sources=cast(:src as jsonb) "
                   "where id = cast(:r as uuid)"),
              {"m": meth["version"], "l": level_for(avg, [float(x) for x in meth["thresholds"]]), "a": avg,
               "rr": sum(1 for x in surveys if x.status == "complete"), "rt": len(surveys), "r": rid,
               "src": json.dumps({"surveys": [x.role_name for x in surveys if x.status == "complete"], "documents": docs, "transcripts": trs})})
    for p, (sc, n) in scores.items():
        s.execute(text("insert into pillar_score(company_id, report_id, pillar, score, answers) values (cast(:c as uuid), cast(:r as uuid), :p, :s, :n)"),
                  {"c": cid, "r": rid, "p": p, "s": sc, "n": n})

    pos = 0
    by_pillar: dict[str, list[str]] = defaultdict(list)

    def ev_answer(a) -> dict:
        return {"source_type": "survey", "source_id": str(a["id"]), "quote": f"{a['question_text']} → {a['value']}",
                "ref": {"role": a["role_name"], "question": a["question_text"], "value": a["value"]}}

    for p, (sc, n) in sorted(scores.items(), key=lambda kv: kv[1][0]):
        mine = [a for a in answers if a["pillar"] == p]
        if sc < BRECHA_MAX:
            low = sorted(mine, key=lambda a: a["value"])[:3]
            by_pillar[p].append(_add_finding(s, cid, rid, pos, "brecha", p, f"{labels[p]}: brecha ({sc:.1f} de 5)",
                                             f"Las respuestas en {labels[p]} promedian {sc:.1f} de 5, por debajo del nivel esperado.",
                                             [ev_answer(a) for a in low])); pos += 1
        elif sc >= FORTALEZA_MIN:
            high = sorted(mine, key=lambda a: -a["value"])[:3]
            by_pillar[p].append(_add_finding(s, cid, rid, pos, "fortaleza", p, f"{labels[p]}: fortaleza ({sc:.1f} de 5)",
                                             f"Las respuestas en {labels[p]} promedian {sc:.1f} de 5.", [ev_answer(a) for a in high])); pos += 1
    by_q: dict[str, list[dict]] = defaultdict(list)
    for a in answers:
        by_q[str(a["question_key"])].append(a)
    for qa in by_q.values():
        lo, hi = min(qa, key=lambda a: a["value"]), max(qa, key=lambda a: a["value"])
        if len({a["role_name"] for a in qa}) > 1 and hi["value"] - lo["value"] >= CONTRADICTION_GAP:
            p = lo["pillar"]
            by_pillar[p].append(_add_finding(
                s, cid, rid, pos, "contradiccion", p, f"Contradicción entre {hi['role_name']} y {lo['role_name']}",
                f"Sobre «{lo['question_text']}», {hi['role_name']} responde {hi['value']} y {lo['role_name']} responde {lo['value']}.",
                [ev_answer(hi), ev_answer(lo)])); pos += 1

    frags = [dict(r) for r in s.execute(text(
        "select f.id::text as id, d.name as document, f.page, f.text from fragment f join document d on d.id = f.document_id "
        "where f.company_id = cast(:c as uuid) order by f.document_id, f.position limit 200"), {"c": cid}).mappings()]
    segs = [dict(r) for r in s.execute(text(
        "select sg.id::text as id, t.name as transcript, sg.start_sec, sg.text from transcript_segment sg join transcript t on t.id = sg.transcript_id "
        "where t.consent_id is not null and sg.company_id = cast(:c as uuid) order by sg.transcript_id, sg.position limit 400"), {"c": cid}).mappings()]
    for cand in llm.propose_findings(frags, segs):
        by_pillar[cand.pillar].append(_add_finding(s, cid, rid, pos, cand.kind, cand.pillar, cand.title, cand.description, cand.evidence)); pos += 1

    rank = 0
    for p, (sc, n) in sorted(scores.items(), key=lambda kv: kv[1][0]):
        if rank == 3:
            break
        ids = by_pillar.get(p)
        if ids:
            s.execute(text("insert into recommendation(company_id, report_id, position, text, finding_ids) values (cast(:c as uuid), cast(:r as uuid), :p, :t, cast(:f as uuid[]))"),
                      {"c": cid, "r": rid, "p": rank + 1, "t": f"{labels[p]}: {RECS[p]}", "f": "{" + ",".join(ids) + "}"})
            rank += 1


def load_report(s: Session, report_id: str) -> dict | None:
    """Informe con sus bloques. Lo que se ve lo decide la base: la empresa solo recibe lo publicado y aceptado."""
    r = s.execute(text("select r.*, c.name as company_name from report r join company c on c.id = r.company_id where r.id = cast(:i as uuid)"),
                  {"i": report_id}).mappings().first()
    if not r:
        return None
    meth = s.execute(text("select pillars, levels from methodology where version = :v"), {"v": r["methodology_version"]}).mappings().first()
    labels = {p["key"]: p["label"] for p in meth["pillars"]} if meth else {}
    level = next((l for l in meth["levels"] if l["level"] == r["level"]), None) if meth else None
    rid = {"i": report_id}
    pillars = [{"id": str(x["id"]), "pillar": x["pillar"], "label": labels.get(x["pillar"], x["pillar"]), "score": float(x["score"]),
                "answers": x["answers"], "review_status": x["review_status"], "low": float(x["score"]) < 2}
               for x in s.execute(text("select * from pillar_score where report_id = cast(:i as uuid) order by score"), rid).mappings()]
    findings = []
    for f in s.execute(text("select * from finding where report_id = cast(:i as uuid) order by position"), rid).mappings():
        evs = [{"id": str(e["id"]), "source_type": e["source_type"], "ref": e["ref"], "quote": e["quote"]}
               for e in s.execute(text("select * from evidence where finding_id = :f"), {"f": f["id"]}).mappings()]
        findings.append({"id": str(f["id"]), "kind": f["kind"], "pillar": f["pillar"], "pillar_label": labels.get(f["pillar"]),
                         "title": f["title"], "description": f["description"], "evidence_status": f["evidence_status"],
                         "review_status": f["review_status"], "evidence": evs})
    recs = [{"id": str(x["id"]), "position": x["position"], "text": x["text"], "finding_ids": [str(i) for i in x["finding_ids"]],
             "review_status": x["review_status"]}
            for x in s.execute(text("select * from recommendation where report_id = cast(:i as uuid) order by position"), rid).mappings()]
    return {"id": str(r["id"]), "company_id": str(r["company_id"]), "company_name": r["company_name"], "version": r["version"],
            "status": r["status"], "level": r["level"], "level_name": level["name"] if level else None,
            "level_description": level["description"] if level else None, "average": float(r["average"]) if r["average"] is not None else None,
            "roles_responded": r["roles_responded"], "roles_total": r["roles_total"], "sources": r["sources"],
            "methodology_version": r["methodology_version"], "created_at": r["created_at"], "published_at": r["published_at"],
            "pillars": pillars, "findings": findings, "recommendations": recs,
            "declaration": "Informe generado con apoyo de IA y revisado por un consultor." if r["status"] == "published"
                           else "Borrador generado con apoyo de IA, pendiente de revisión por un consultor."}
