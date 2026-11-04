"""Indicadores del programa, siempre calculados desde los registros (nunca escritos a mano)."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def _f(v, nd=2):
    return None if v is None else round(float(v), nd)


def compute(s: Session) -> dict:
    # Proporción de bloques aceptados, editados y rechazados: última decisión de cada bloque (05-R10).
    rows = s.execute(text(
        "select block_type, action, count(*) n from (select distinct on (block_type, block_id) block_type, action "
        "from review_decision order by block_type, block_id, id desc) d group by 1, 2")).all()
    props: dict[str, dict] = {}
    for bt, act, n in rows:
        props.setdefault(bt, {"accept": 0, "edit": 0, "reject": 0})[act] = n
    for bt, d in props.items():
        total = sum(d.values())
        d["total"] = total
        d["share"] = {k: round(d[k] / total, 3) for k in ("accept", "edit", "reject")}
    published = s.execute(text("select count(*) from report where status='published'")).scalar()
    with_approval = s.execute(text("""select count(*) from report r where r.status='published' and r.published_by is not null
        and exists (select 1 from audit_log a where a.entity='report' and a.entity_id = r.id::text and a.action='report.published')""")).scalar()
    f_total, f_ok = s.execute(text("""select count(*), count(*) filter (where exists (select 1 from evidence e where e.finding_id = f.id))
        from finding f join report r on r.id = f.report_id where r.status='published' and f.review_status in ('accepted','edited')""")).one()
    reports = s.execute(text("select count(*) from report where status in ('in_review','published','draft')")).scalar()
    return {
        "review_proportions": props,
        "human_control": {"published": published, "with_recorded_approval": with_approval,
                          "share": _f(with_approval / published, 3) if published else None},
        "evidence": {"published_findings": f_total, "with_evidence": f_ok, "share": _f(f_ok / f_total, 3) if f_total else None},
        "findings_without_sufficient_evidence_per_report": _f(s.execute(text(
            "select avg(n) from (select count(*) filter (where evidence_status in ('insuficiente','revisada')) n from finding group by report_id) x")).scalar()),
        "avg_generation_seconds": _f(s.execute(text("select avg(seconds) from report where seconds is not null")).scalar(), 3),
        "avg_hours_to_publish": _f(s.execute(text("select avg(extract(epoch from (published_at - created_at))/3600) from report where status='published'")).scalar(), 3),
        "compute_cost_per_cycle_usd": _f(s.execute(text("select coalesce(sum(cost_usd),0) / nullif(%s, 0) from llm_usage" % int(reports))).scalar(), 4),
        "reports": reports,
    }
