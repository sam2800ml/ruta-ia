import { FormEvent, useCallback, useEffect, useState } from "react";
import { fmtDate, http, setViewAs } from "./api";
import { Evidence, kindLabel, Loading, PillarBars } from "./ui";

export function Empresas({ onView }: { onView: (id: string, name: string) => void }) {
  const [dash, setDash] = useState<any>(null);
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [f, setF] = useState({ name: "", nit: "", admin_email: "" });
  const [tok, setTok] = useState("");
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    setDash(await http("GET", "/admin/dashboard")); setRows(await http("GET", `/admin/companies?q=${encodeURIComponent(q)}`));
  }, [q]);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);
  async function invite(e: FormEvent) {
    e.preventDefault();
    try { setErr(""); const r = await http("POST", "/companies", { ...f, nit: f.nit || null }); setTok(r.invitation_token); setF({ name: "", nit: "", admin_email: "" }); load(); } catch (x) { setErr((x as Error).message); }
  }
  if (!dash) return <main className="card wide">{err ? <p className="error">{err}</p> : <Loading />}</main>;
  return (
    <main className="card wide">
      <h1>Empresas en la plataforma</h1>
      {dash && <div className="kpis">
        <div><b>{dash.active_companies}</b>Empresas activas</div><div><b>{dash.reviews_pending}</b>Diagnósticos por revisar</div>
        <div><b>{dash.avg_maturity ?? "—"}</b>Madurez promedio (de 5)</div><div><b>{dash.approved_use_cases}</b>Casos de uso aprobados</div></div>}
      <form onSubmit={invite} className="grid">
        <label>Razón social<input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
        <label>NIT<input value={f.nit} onChange={(e) => setF({ ...f, nit: e.target.value })} /></label>
        <label>Correo del administrador<input required type="email" value={f.admin_email} onChange={(e) => setF({ ...f, admin_email: e.target.value })} /></label>
        <div><button type="submit">Invitar empresa</button></div></form>
      {tok && <p className="banner" role="status">Enlace de invitación (aún no se envía por correo): <code id="invite-token">{tok}</code></p>}
      {err && <p role="alert" className="error">{err}</p>}

      <div className="two">
        <section className="panel">
          <h2>Todas las empresas</h2>
          <label>Buscar<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nombre o NIT" /></label>
          <table><thead><tr><th>Empresa</th><th>Sector</th><th>Etapa</th><th>Madurez</th><th>Avance</th><th>Última actividad</th><th></th></tr></thead>
            <tbody>{rows.map((r) => <tr key={r.id}><td>{r.name}</td><td>{r.sector ?? "—"}</td><td>{r.stage}</td><td>{r.maturity ? `${r.maturity.level} (${r.maturity.average})` : "—"}</td><td>{r.progress}</td><td>{r.last_activity ? fmtDate(r.last_activity) : "—"}</td>
              <td><button className="link" onClick={() => { setViewAs(r.id); onView(r.id, r.name); }}>Ver como empresa</button></td></tr>)}</tbody></table>
        </section>
        {dash?.pillar_average?.length > 0 && <section className="panel">
          <h2>Promedio por pilar</h2>
          <PillarBars scores={dash.pillar_average.map((p: any) => ({ label: p.label, score: p.avg, low: p.low }))} />
          <small className="muted">Empresas con diagnóstico generado ({dash.companies_with_diagnosis} de {dash.pillar_average[0]?.of ?? 0}).</small>
        </section>}
      </div>
    </main>
  );
}

export function Revision() {
  const [queue, setQueue] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [r, setR] = useState<any>(null);
  const [err, setErr] = useState("");
  const [edit, setEdit] = useState<Record<string, string>>({});
  const loadQ = useCallback(async () => { setQueue(await http("GET", "/review/queue")); setLoaded(true); }, []);
  useEffect(() => { loadQ().catch((e) => setErr(e.message)); }, [loadQ]);
  const open = async (id: string) => setR(await http("GET", `/review/${id}`));
  async function decide(type: string, id: string, action: string, extra: any = {}) {
    try { setErr(""); await http("POST", `/review/${r.id}/blocks/${type}/${id}`, { action, ...extra }); await open(r.id); } catch (e) { setErr((e as Error).message); }
  }
  async function publish() { try { setErr(""); await http("POST", `/review/${r.id}/publish`); setR(null); loadQ(); } catch (e) { setErr((e as Error).message); } }
  const Btns = ({ type, b, field }: { type: string; b: any; field: string }) => (
    <div className="actions">
      <span className={`pill ${b.review_status === "accepted" || b.review_status === "edited" ? "processed" : b.review_status === "rejected" ? "error" : ""}`}>{b.review_status}</span>
      <button disabled={b.evidence_status === "insuficiente" && type === "finding"} title={b.evidence_status === "insuficiente" ? "Evidencia insuficiente: edita o rechaza" : ""} onClick={() => decide(type, b.id, "accept")}>Aceptar</button>
      <button className="secondary" onClick={() => { const t = window.prompt("Texto editado", edit[b.id] ?? b[field]); if (t) decide(type, b.id, "edit", { new_text: t }); }}>Editar</button>
      <button className="secondary" onClick={() => { const why = window.prompt("Motivo del rechazo"); if (why) decide(type, b.id, "reject", { reason: why }); }}>Rechazar</button>
    </div>);
  if (!r) return (
    <main className="card wide"><h1>Cola de revisión</h1>{err && <p className="error">{err}</p>}
      {!loaded ? <Loading /> : (
      <table><thead><tr><th>Empresa</th><th>Versión</th><th>Hallazgos</th><th>Sin evidencia</th><th>Contradicciones</th><th></th></tr></thead>
        <tbody>{queue.map((q) => <tr key={q.id}><td>{q.name}</td><td>{q.version}</td><td>{q.findings}</td><td>{q.sin_evidencia}</td><td>{q.contradicciones}</td><td><button onClick={() => open(q.id)}>Revisar</button></td></tr>)}
          {queue.length === 0 && <tr><td colSpan={6} className="muted">No hay informes pendientes.</td></tr>}</tbody></table>)}</main>);
  const p = r.progress;
  return (
    <main className="card wide">
      <button className="link" onClick={() => { setR(null); loadQ(); }}>← Cola</button>
      <h1>{r.company_name} · versión {r.version}</h1>
      <p>Nivel {r.level} {r.level_name} · promedio {r.average} · {r.roles_responded} de {r.roles_total} roles. <strong>Revisados {p.reviewed} de {p.total}</strong></p>
      {err && <p role="alert" className="error">{err}</p>}
      <h3>Puntajes por pilar</h3>
      {r.pillars.map((x: any) => <div key={x.id} className="row2"><span>{x.label}: <strong>{x.score}</strong> (determinista, no editable)</span><Btns type="pillar" b={x} field="label" /></div>)}
      <h3>Hallazgos</h3>
      {r.findings.map((x: any) => <article key={x.id} className={`finding ${x.kind}`}>
        <header><span className="tag">{kindLabel[x.kind]}</span> <small className="muted">{x.pillar_label}</small> {x.evidence_status === "insuficiente" && <span className="pill error">Evidencia insuficiente</span>}</header>
        <strong>{x.title}</strong><p>{x.description}</p>{x.evidence.map((e: any) => <Evidence key={e.id} e={e} />)}<Btns type="finding" b={x} field="description" /></article>)}
      <h3>Recomendaciones</h3>
      {r.recommendations.map((x: any) => <div key={x.id} className="row2"><span>{x.text}</span><Btns type="recommendation" b={x} field="text" /></div>)}
      <p><button disabled={p.reviewed < p.total} onClick={publish}>Publicar informe</button> {p.reviewed < p.total && <small className="muted">Revisa todos los bloques para publicar.</small>}</p>
    </main>);
}

export function Banco() {
  const [qs, setQs] = useState<any[]>([]);
  const [f, setF] = useState({ text: "", pillar: "", roles: "" });
  const [pillars, setPillars] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const load = useCallback(async () => { setQs(await http("GET", "/admin/questions")); const m = await http("GET", "/admin/methodology"); setPillars(m[0].pillars); }, []);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);
  async function add(e: FormEvent) {
    e.preventDefault();
    try { setErr(""); await http("POST", "/admin/questions", { text: f.text, pillar: f.pillar || pillars[0].key, roles: f.roles.split(",").map((s) => s.trim()).filter(Boolean), weight: 1 }); setF({ text: "", pillar: "", roles: "" }); load(); } catch (x) { setErr((x as Error).message); }
  }
  if (!pillars.length) return <main className="card wide">{err ? <p className="error">{err}</p> : <Loading />}</main>;
  return (
    <main className="card wide"><h1>Banco de preguntas</h1>
      <form onSubmit={add} className="grid"><label>Pregunta<input required minLength={5} value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} /></label>
        <label>Pilar<select value={f.pillar} onChange={(e) => setF({ ...f, pillar: e.target.value })}>{pillars.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}</select></label>
        <label>Roles (vacío = todos)<input value={f.roles} onChange={(e) => setF({ ...f, roles: e.target.value })} /></label><div><button type="submit">Agregar</button></div></form>
      {err && <p role="alert" className="error">{err}</p>}
      <table><thead><tr><th>Pregunta</th><th>Pilar</th><th>Roles</th><th>v</th><th>Aporte</th><th></th></tr></thead>
        <tbody>{qs.map((q) => <tr key={q.id}><td>{q.text}</td><td>{q.pillar}</td><td>{q.roles.join(", ")}</td><td>{q.version}</td><td>{q.contribution}</td>
          <td><button className="link" onClick={async () => { const t = window.prompt("Editar pregunta", q.text); if (t) { await http("PUT", `/admin/questions/${q.key}`, { text: t, pillar: q.pillar, roles: q.roles[0] === "Todos" ? [] : q.roles, weight: q.weight }); load(); } }}>Editar</button>{" "}
            <button className="link" onClick={async () => { await http("DELETE", `/admin/questions/${q.key}`); load(); }}>Retirar</button></td></tr>)}</tbody></table></main>);
}

export function Metodologia() {
  const [ms, setMs] = useState<any[]>([]);
  const [cuts, setCuts] = useState("");
  const [err, setErr] = useState("");
  const load = useCallback(async () => { const m = await http("GET", "/admin/methodology"); setMs(m); setCuts(m[0].thresholds.join(", ")); }, []);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);
  async function publish() {
    try { setErr(""); await http("POST", "/admin/methodology", { levels: ms[0].levels, thresholds: cuts.split(",").map(Number), formula: ms[0].formula }); load(); } catch (x) { setErr((x as Error).message); }
  }
  if (!ms.length) return <main className="card">{err ? <p className="error">{err}</p> : <Loading />}</main>;
  const m = ms[0];
  return (
    <main className="card wide"><h1>Metodología · versión {m.version}</h1>
      <p className="muted">{m.formula}</p>
      <ol>{m.levels.map((l: any) => <li key={l.level}><strong>{l.name}</strong>: {l.description}</li>)}</ol>
      <label>Cortes entre niveles (4, ascendentes)<input value={cuts} onChange={(e) => setCuts(e.target.value)} /></label>
      <button onClick={publish}>Publicar nueva versión</button>
      {err && <p role="alert" className="error">{err}</p>}
      <h3>Historial</h3><ul>{ms.map((x) => <li key={x.version}>v{x.version}{x.active ? " (vigente)" : ""} · cortes {x.thresholds.join(", ")} · {x.reports} informes</li>)}</ul></main>);
}

export function Analitica() {
  const [a, setA] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const load = useCallback(async () => { setA(await http("GET", "/admin/analytics")); setRuns(await http("GET", "/eval/runs")); }, []);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);
  if (!a) return <main className="card">{err ? <p className="error">{err}</p> : <Loading />}</main>;
  const pct = (v: number | null) => (v == null ? "—" : `${Math.round(v * 100)} %`);
  return (
    <main className="card wide"><h1>Analítica y evaluación</h1>
      <div className="kpis"><div><b>{pct(a.human_control.share)}</b>Informes con aprobación humana</div><div><b>{pct(a.evidence.share)}</b>Hallazgos con evidencia</div>
        <div><b>{a.avg_generation_seconds ?? "—"}</b>Segundos de generación</div><div><b>{a.compute_cost_per_cycle_usd ?? "—"}</b>USD por ciclo</div></div>
      <h3>Propuestas de la IA: aceptadas / editadas / rechazadas</h3>
      <ul>{Object.entries(a.review_proportions).map(([k, v]: any) => <li key={k}>{k}: {v.accept} / {v.edit} / {v.reject} (de {v.total})</li>)}</ul>
      <button onClick={async () => { await http("POST", "/eval/runs"); load(); }}>Congelar corrida de evaluación</button>
      <ul>{runs.map((r) => <li key={r.id}>{String(r.at).slice(0, 16)} · sistema {r.system_version}</li>)}</ul></main>);
}

export { setViewAs };
