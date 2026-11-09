import { useCallback, useEffect, useRef, useState } from "react";
import { http } from "./api";
import { Banner, Loading, Spinner } from "./ui";

export default function Estrategia({ readOnly = false }: { readOnly?: boolean }) {
  const [s, setS] = useState<any>(null);
  const [text, setText] = useState("");
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const load = useCallback(async () => { try { setS(await http("GET", "/strategy")); } catch (e) { setErr((e as Error).message); } }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [s?.messages?.length, pending, sending]);

  const act = (key: string, fn: () => Promise<any>) => async () => {
    setBusy(key);
    try { setErr(""); await fn(); await load(); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };
  if (!s) return <main className="card">{err ? <p className="error">{err}</p> : <Loading />}</main>;
  if (!s.enabled) return <main className="card"><h1>3 · Estrategia</h1><div className="locked">🔒 {s.locked_message}</div></main>;
  if (!s.started) return <main className="card"><h1>3 · Estrategia</h1><p>{s.disclosure}</p>
    {!readOnly && <button disabled={busy === "start"} onClick={act("start", () => http("POST", "/strategy/start"))}>{busy === "start" && <Spinner />}Empezar</button>}</main>;

  const cur = s.current_stage as string;
  const msgs = s.messages.filter((m: any) => m.stage === cur);
  const props = s.proposals.filter((p: any) => p.stage === cur);
  const done = s.status === "closed";

  async function send() {
    if (!text.trim() || sending) return;
    const t = text;
    setText(""); setErr(""); setPending(t); setSending(true);
    try {
      await http("POST", "/strategy/messages", { text: t });
      await load();
    } catch (e) {
      setErr((e as Error).message);
      setText(t);
    } finally {
      setSending(false); setPending(null);
    }
  }

  return (
    <main className="card wide">
      <h1>3 · Estrategia</h1>
      {readOnly && <Banner>Vista de solo lectura</Banner>}
      <ol className="stepper">{s.stages.map((st: any) => <li key={st.key} className={st.status}>{st.label}</li>)}</ol>
      <div className="chatgrid">
        <section>
          <div className="chat" aria-live="polite">
            {msgs.map((m: any, i: number) => <div key={i} className={`bubble ${m.author}`}>{m.text}</div>)}
            {pending && <div className="bubble user">{pending}</div>}
            {sending && <div className="bubble assistant"><Spinner /> Pensando…</div>}
            {props.map((p: any) => (
              <div key={p.id} className="proposal">
                <small className="muted">Propuesta · {p.kind}{p.basis ? ` · ${p.basis}` : ""}</small>
                <textarea value={edit[p.id] ?? p.text} onChange={(e) => setEdit({ ...edit, [p.id]: e.target.value })} disabled={readOnly} />
                {!readOnly && <div>
                  <button disabled={busy === `save-${p.id}`} onClick={act(`save-${p.id}`, () => http("POST", `/strategy/proposals/${p.id}/save`, { text: edit[p.id] ?? p.text }))}>{busy === `save-${p.id}` && <Spinner />}Guardar</button>{" "}
                  <button className="secondary" disabled={busy === `discard-${p.id}`} onClick={act(`discard-${p.id}`, () => http("POST", `/strategy/proposals/${p.id}/discard`))}>{busy === `discard-${p.id}` && <Spinner />}Descartar</button>
                </div>}
              </div>))}
            <div ref={end} />
          </div>
          {err && <p role="alert" className="error">{err}</p>}
          {!done && !readOnly && <div className="compose">
            <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Escribe tu respuesta…" disabled={sending} />
            <button onClick={send} disabled={sending || !text.trim()}>{sending && <Spinner />}Enviar</button>
            <button className="secondary" disabled={busy === "complete"} onClick={act("complete", () => http("POST", `/strategy/stages/${cur}/complete`))}>{busy === "complete" && <Spinner />}Completar etapa</button>
          </div>}
          {done && <p className="banner">Estrategia cerrada. Ya puedes trabajar los casos de uso.</p>}
        </section>
        <aside className="panel"><h3>Lo que hemos definido</h3>
          {s.stages.map((st: any) => { const items = s.items.filter((i: any) => i.stage === st.key); return (
            <div key={st.key}><strong>{st.label}</strong>
              {items.length === 0 ? <p className="muted">Pendiente</p> : items.map((i: any) => (
                <p key={i.key}>{i.text} <small className="muted">v{i.version}</small>
                  {!readOnly && <button className="link" onClick={() => { const t = window.prompt("Editar", i.text); if (t) act(`item-${i.key}`, () => http("PUT", `/strategy/items/${i.key}`, { text: t }))(); }}> editar</button>}</p>))}
            </div>); })}
        </aside>
      </div>
    </main>
  );
}
