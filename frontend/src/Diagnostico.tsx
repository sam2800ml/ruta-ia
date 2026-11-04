import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";
import { http } from "./api";
import Informe from "./Informe";
import { Banner, PillarChips, Section } from "./ui";

const ROLES = ["Tecnología", "Finanzas", "Operaciones", "Riesgos", "Talento Humano", "Comercial"];
const today = () => new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10);

export default function Diagnostico({ readOnly = false, onGo }: { readOnly?: boolean; onGo?: (t: string) => void }) {
  const [sv, setSv] = useState<any>({ surveys: [], complete: 0, total: 0 });
  const [tr, setTr] = useState<any[]>([]);
  const [consent, setConsent] = useState<any>(null);
  const [state, setState] = useState<any>(null);
  const [mails, setMails] = useState<any[]>([]);
  const [form, setForm] = useState({ role_name: ROLES[0], responsible: "", email: "", deadline: today() });
  const [trRoles, setTrRoles] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    const [a, b, c, d, e] = await Promise.all([http("GET", "/surveys"), http("GET", "/transcripts"), http("GET", "/consent"), http("GET", "/reports/state"), http("GET", "/outbox")]);
    setSv(a); setTr(b); setConsent(c); setState(d); setMails(e);
  }, []);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);
  const generating = state?.latest?.status === "generating";
  useEffect(() => { if (!generating) return; const t = setInterval(() => load().catch(() => {}), 2000); return () => clearInterval(t); }, [generating, load]);

  const run = (fn: () => Promise<any>, ok = "") => async () => { try { setErr(""); await fn(); setMsg(ok); await load(); } catch (e) { setErr((e as Error).message); } };

  async function addSurvey(e: FormEvent) { e.preventDefault(); await run(() => http("POST", "/surveys", form), "Encuesta enviada")(); }
  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f); fd.append("roles", trRoles);
    await run(async () => { const r = await http("POST", "/transcripts", fd); setMsg(r.warning ?? "Transcripción cargada"); })();
    e.target.value = "";
  }

  const latest = state?.latest?.status as string | undefined;
  return (
    <main className="card wide">
      <h1>2 · Diagnóstico</h1>
      <PillarChips />
      {readOnly && <Banner>Vista de solo lectura</Banner>}
      <fieldset disabled={readOnly} className="plain">
        <Section title="Encuestas por rol">
          <form onSubmit={addSurvey} className="grid">
            <label>Rol<select value={form.role_name} onChange={(e) => setForm({ ...form, role_name: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></label>
            <label>Responsable<input required value={form.responsible} onChange={(e) => setForm({ ...form, responsible: e.target.value })} /></label>
            <label>Correo<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
            <label>Fecha límite<input required type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} /></label>
            <div><button type="submit">Enviar encuesta</button></div>
          </form>
          <p><strong>{sv.complete} de {sv.total}</strong> encuestas completas</p>
          {sv.total > 0 && <div className="progressbar"><div style={{ width: `${(sv.complete / sv.total) * 100}%` }} /></div>}
          <table>
            <thead><tr><th>Rol</th><th>Responsable</th><th>Correo</th><th>Estado</th><th>Acción</th></tr></thead>
            <tbody>{sv.surveys.map((s: any) => (
              <tr key={s.id}>
                <td>{s.role_name}</td><td>{s.responsible}</td><td>{s.email}</td>
                <td><span className={`pill ${s.status === "complete" ? "processed" : ""}`}>{s.status === "complete" ? "Completa" : "Pendiente"}</span></td>
                <td>{s.status === "pending" && <button className="link" onClick={run(() => http("POST", `/surveys/${s.id}/reminder`), "Recordatorio enviado")}>Reenviar</button>}</td>
              </tr>))}
              {sv.surveys.length === 0 && <tr><td colSpan={5} className="muted">Aún no hay encuestas.</td></tr>}</tbody>
          </table>
          {sv.surveys.some((s: any) => s.status === "pending") && <button className="secondary" onClick={run(() => http("POST", "/surveys/remind-pending"), "Recordatorios enviados")}>Reenviar a todos los pendientes</button>}
        </Section>

        <Section title="Transcripciones de reuniones">
          <label className="check"><input type="checkbox" checked={!!consent?.given} disabled={!!consent?.given} onChange={run(() => http("POST", "/consent"), "Consentimiento registrado")} /> {consent?.text}</label>
          <label>Roles que participaron (separados por coma)<input value={trRoles} onChange={(e) => setTrRoles(e.target.value)} placeholder="Tecnología, Finanzas" /></label>
          <input type="file" accept=".txt,.vtt,.srt,.docx" onChange={upload} />
          <small className="muted"> TXT, VTT, SRT o DOCX. Con VTT o SRT se cita el minuto exacto.</small>
          <ul className="docs">{tr.map((t) => (
            <li key={t.id}>
              <span>{t.name}{!t.has_timestamps && <small className="muted"> · sin marcas de tiempo</small>}<br />
                {t.roles.map((r: string) => <span key={r} className="tagchip">{r}</span>)}{t.roles.length === 0 && <small className="muted">sin roles</small>}</span>
              <span><span className={`pill ${t.status === "analyzed" ? "processed" : ""}`}>{t.status === "analyzed" ? "Analizada" : "En análisis"}</span>{!t.usable && <span className="pill error" title="Sin consentimiento no se usa">No se usará</span>}</span></li>))}
            {tr.length === 0 && <li className="muted">Sin transcripciones.</li>}</ul>
        </Section>

        <Section title="Generar diagnóstico">
          {msg && <p role="status" className="muted">{msg}</p>}
          {err && <p role="alert" className="error">{err}</p>}
          {sv.complete < sv.total && sv.complete > 0 && <p className="muted">Puedes generarlo con respuestas parciales: el informe dirá que lo respaldan {sv.complete} de {sv.total} roles.</p>}
          <button disabled={sv.complete === 0 || generating || latest === "in_review"} onClick={run(() => http("POST", "/reports"), "Diagnóstico en proceso")}>
            {generating ? "Generando…" : latest === "in_review" ? "En revisión por un consultor" : "Generar diagnóstico"}</button>
          {latest === "in_review" && <p className="muted">Un consultor revisa tu informe antes de publicarlo. Recibirás el resultado en esta pantalla.</p>}
          {latest === "error" && <p className="error">No se pudo generar el diagnóstico. Inténtalo de nuevo.</p>}
        </Section>
      </fieldset>

      <details><summary className="muted">Bandeja de salida (modo prueba: los correos quedan en cola)</summary>
        <ul className="docs">{mails.map((m) => <li key={m.id}><span><small className="muted">{m.to_email}</small><br />{m.body}</span></li>)}</ul></details>

      {state?.published && <Informe readOnly={readOnly} onGo={onGo} />}
    </main>
  );
}
