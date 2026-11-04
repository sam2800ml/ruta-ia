import { FormEvent, useCallback, useEffect, useState } from "react";
import { download, http } from "./api";
import { Banner } from "./ui";

const ZONES: Record<string, string> = { quick_win: "Victorias rápidas", estrategico: "Estratégicos", mejoras_menores: "Mejoras menores", reconsiderar: "Reconsiderar" };
const empty = { name: "", area: "", risk: "limitado", indicator: "", baseline: "", target: "", tech: "", personal_data: false,
  legal: 3, ethic: 3, infra: 3, legal_note: "", ethic_note: "", infra_note: "", volume_per_month: "", minutes_saved: "" };

function Matrix({ cases, onPick }: { cases: any[]; onPick: (id: string) => void }) {
  const W = 420, H = 320, m = 40;
  const x = (c: number) => m + ((c - 1) / 4) * (W - 2 * m);
  const y = (i: number) => H - m - ((i - 1) / 3) * (H - 2 * m);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="matrix" role="img" aria-label="Matriz impacto contra complejidad">
      <rect x={m} y={m} width={(W - 2 * m) / 2} height={(H - 2 * m) / 2} className="z-win" />
      <rect x={W / 2} y={m} width={(W - 2 * m) / 2} height={(H - 2 * m) / 2} className="z-str" />
      <text x={m + 4} y={m + 14} className="zl">Victorias rápidas</text><text x={W / 2 + 4} y={m + 14} className="zl">Estratégicos</text>
      <text x={m + 4} y={H - m - 4} className="zl">Mejoras menores</text><text x={W / 2 + 4} y={H - m - 4} className="zl">Reconsiderar</text>
      <text x={W / 2} y={H - 6} textAnchor="middle" className="zl">Complejidad →</text>
      <text x={10} y={H / 2} className="zl" transform={`rotate(-90 10 ${H / 2})`} textAnchor="middle">Impacto →</text>
      {cases.filter((c) => c.impact).map((c) => (
        <g key={c.id} onClick={() => onPick(c.id)} style={{ cursor: "pointer" }}>
          <circle cx={x(c.complexity)} cy={y(c.impact)} r={11} className="dot" /><text x={x(c.complexity)} y={y(c.impact) + 4} textAnchor="middle" className="dn">{c.n}</text>
        </g>))}
    </svg>
  );
}

export default function Casos({ readOnly = false, consultant = false, companyId }: { readOnly?: boolean; consultant?: boolean; companyId?: string }) {
  const [d, setD] = useState<any>(null);
  const [bias, setBias] = useState<any>(null);
  const [sel, setSel] = useState<any>(null);
  const [form, setForm] = useState<any>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const q = companyId ? `?company_id=${companyId}` : "";
  const load = useCallback(async () => {
    try { setD(await http("GET", `/use-cases${q}`)); setBias(await http("GET", `/use-cases/bias${q}`).catch(() => null)); } catch (e) { setErr((e as Error).message); }
  }, [q]);
  useEffect(() => { load(); }, [load]);
  const pick = async (id: string) => setSel(await http("GET", `/use-cases/${id}${q}`));
  const act = (fn: () => Promise<any>) => async () => { try { setErr(""); await fn(); await load(); if (sel) setSel(await http("GET", `/use-cases/${sel.id}${q}`)); } catch (e) { setErr((e as Error).message); } };

  async function save(e: FormEvent) {
    e.preventDefault();
    const b = { ...form, volume_per_month: form.volume_per_month === "" ? null : Number(form.volume_per_month), minutes_saved: form.minutes_saved === "" ? null : Number(form.minutes_saved),
      legal: Number(form.legal), ethic: Number(form.ethic), infra: Number(form.infra) };
    try { setErr(""); if (editId) await http("PUT", `/use-cases/${editId}`, b); else await http("POST", "/use-cases", b); setForm(null); setEditId(null); await load(); } catch (x) { setErr((x as Error).message); }
  }
  if (!d) return <main className="card">{err || "Cargando…"}</main>;
  if (!d.enabled) return <main className="card"><h1>4 · Casos de uso</h1><div className="locked">🔒 {d.locked_message}</div></main>;
  const f = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <main className="card wide">
      <h1>4 · Casos de uso</h1>
      {readOnly && <Banner>Vista de solo lectura</Banner>}
      {err && <p role="alert" className="error">{err}</p>}
      {!readOnly && !consultant && <p>
        <button onClick={() => { setForm({ ...empty }); setEditId(null); }}>Nuevo caso</button>{" "}
        <button className="secondary" onClick={act(() => http("POST", "/use-cases/from-opportunities"))}>Crear desde las oportunidades de la estrategia</button>{" "}
        <button className="secondary" onClick={() => download("/use-cases/export.csv", "casos-de-uso.csv")}>Exportar CSV</button></p>}
      <div className="two">
        <section className="panel">
          <h2>Matriz de priorización</h2>
          <Matrix cases={d.cases} onPick={pick} />
        </section>

        {sel ? (
          <section className="panel"><h2>{sel.n}. {sel.name}<small className="muted"> · {sel.area}</small></h2>
            <p>{sel.zone && <span className="pill">{ZONES[sel.zone]}</span>} <span className="pill">{sel.status === "proposed" ? "Propuesto" : sel.status === "approved" ? "Aprobado" : "Piloto"}</span></p>
            {sel.label && <p className="banner">{sel.label}</p>}
            <p><strong>Impacto:</strong> {sel.impact ?? "—"} ({sel.hours_per_year ?? "—"} h/año) · <strong>Complejidad:</strong> {sel.complexity}<br />
              <small className="muted">{sel.formula} · {sel.assumptions.volume_per_month ?? "?"} casos/mes × {sel.assumptions.minutes_saved ?? "?"} min</small></p>
            <p>Riesgo: {sel.risk}. {sel.law_note && <span className="error">{sel.law_note}</span>}</p>
            <div className="pbars">
              {(["legal", "ethic", "infra"] as const).map((k) => (
                <div key={k} className="pbar">
                  <span className="pbar-label">{{ legal: "Legal", ethic: "Ético", infra: "Infraestructura" }[k]}</span>
                  <div className="pbar-track"><div className="pbar-fill" style={{ width: `${(sel.complexity_parts[k] / 5) * 100}%` }} /></div>
                  <strong className="pbar-val">{sel.complexity_parts[k]}/5</strong>
                </div>))}
            </div>
            <ul className="docs">
              <li><small className="muted">Legal</small><span>{sel.complexity_notes.legal}</span></li>
              <li><small className="muted">Ético</small><span>{sel.complexity_notes.ethic}</span></li>
              <li><small className="muted">Infraestructura</small><span>{sel.complexity_notes.infra}</span></li>
            </ul>
            <p>Indicador: {sel.indicator ?? "—"} · línea base {sel.baseline ?? "—"} · meta {sel.target ?? "—"}</p>
            {!readOnly && sel.status === "proposed" && !consultant && <button className="secondary" onClick={() => { setEditId(sel.id); setForm({ ...empty, ...Object.fromEntries(Object.entries({ ...sel, ...sel.complexity_parts, legal_note: sel.complexity_notes.legal, ethic_note: sel.complexity_notes.ethic, infra_note: sel.complexity_notes.infra, volume_per_month: sel.assumptions.volume_per_month ?? "", minutes_saved: sel.assumptions.minutes_saved ?? "" }).map(([k, v]) => [k, v ?? ""])) }); }}>Editar</button>}
            {sel.status === "proposed" && !consultant && <p className="muted">Pendiente de aprobación del consultor.</p>}
            {consultant && !readOnly && <>{sel.status === "proposed" && <button onClick={act(() => http("POST", `/use-cases/${sel.id}/status`, { status: "approved" }))}>Aprobar</button>}
              {sel.status === "approved" && <button onClick={act(() => http("POST", `/use-cases/${sel.id}/status`, { status: "pilot" }))}>Pasar a piloto</button>}</>}
          </section>
        ) : <section className="panel"><p className="muted">Selecciona un caso en la matriz o en la tabla para ver su ficha.</p></section>}
      </div>
      {bias && bias.areas?.length > 0 && <details><summary className="muted">Revisión de sesgo por área</summary>
        <ul>{bias.areas.map((a: any) => <li key={a.area}>{a.area}: {a.count} {a.note ? `· ${a.note}` : ""}</li>)}</ul></details>}

      <section className="panel">
        <h2>Todos los casos</h2>
        <table>
          <thead><tr><th>Caso</th><th>Área</th><th>Impacto</th><th>Complejidad</th><th>Riesgo</th><th>Estado</th></tr></thead>
          <tbody>{d.cases.map((c: any) => (
            <tr key={c.id} onClick={() => pick(c.id)} style={{ cursor: "pointer" }}>
              <td>{c.n}. {c.name}</td><td>{c.area}</td><td>{c.impact ? `${c.impact} de 5` : "—"}</td><td>{c.complexity ? `${c.complexity} de 5` : "—"}</td>
              <td>{c.risk}</td><td><span className="pill">{c.status === "proposed" ? "Propuesto" : c.status === "approved" ? "Aprobado" : "Piloto"}</span></td>
            </tr>))}
            {d.cases.length === 0 && <tr><td colSpan={6} className="muted">Aún no hay casos.</td></tr>}</tbody>
        </table>
      </section>

      {form && <form onSubmit={save} className="panel grid">
        <label>Nombre<input required value={form.name} onChange={f("name")} /></label>
        <label>Área<input required value={form.area} onChange={f("area")} /></label>
        <label>Riesgo<select value={form.risk} onChange={f("risk")}><option value="minimo">Mínimo</option><option value="limitado">Limitado</option><option value="alto">Alto</option></select></label>
        <label>Casos al mes<input type="number" value={form.volume_per_month} onChange={f("volume_per_month")} /></label>
        <label>Minutos ahorrados por caso<input type="number" value={form.minutes_saved} onChange={f("minutes_saved")} /></label>
        <label>Indicador<input value={form.indicator} onChange={f("indicator")} /></label>
        <label>Línea base<input value={form.baseline} onChange={f("baseline")} /></label>
        <label>Meta<input value={form.target} onChange={f("target")} /></label>
        <label className="check"><input type="checkbox" checked={form.personal_data} onChange={f("personal_data")} /> Usa datos personales</label>
        {(["legal", "ethic", "infra"] as const).map((k) => <div key={k}><label>{{ legal: "Legal", ethic: "Ético", infra: "Infraestructura" }[k]} (1–5)<input type="number" min={1} max={5} value={form[k]} onChange={f(k)} /></label>
          <label>Justificación<input required value={form[`${k}_note`]} onChange={f(`${k}_note`)} /></label></div>)}
        <div><button type="submit">Guardar</button> <button type="button" className="secondary" onClick={() => setForm(null)}>Cancelar</button></div>
      </form>}
    </main>
  );
}
