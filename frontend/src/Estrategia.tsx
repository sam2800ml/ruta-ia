import { useCallback, useEffect, useRef, useState } from "react";
import { http } from "./api";
import { Banner, Loading } from "./ui";

export default function Estrategia({ readOnly = false }: { readOnly?: boolean }) {
  const [s, setS] = useState<any>(null);
  const [text, setText] = useState("");
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const load = useCallback(async () => { try { setS(await http("GET", "/strategy")); } catch (e) { setErr((e as Error).message); } }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [s?.messages?.length]);

  const act = (fn: () => Promise<any>) => async () => { try { setErr(""); await fn(); await load(); } catch (e) { setErr((e as Error).message); } };
  if (!s) return <main className="card">{err ? <p className="error">{err}</p> : <Loading />}</main>;
  if (!s.enabled) return <main className="card"><h1>3 · Estrategia</h1><div className="locked">🔒 {s.locked_message}</div></main>;
  if (!s.started) return <main className="card"><h1>3 · Estrategia</h1><p>{s.disclosure}</p>{!readOnly && <button onClick={act(() => http("POST", "/strategy/start"))}>Empezar</button>}</main>;

  const cur = s.current_stage as string;
  const msgs = s.messages.filter((m: any) => m.stage === cur);
  const props = s.proposals.filter((p: any) => p.stage === cur);
  const done = s.status === "closed";
  async function send() { if (!text.trim()) return; const t = text; setText(""); await act(() => http("POST", "/strategy/messages", { text: t }))(); }
  return (
    <main className="card wide">
      <h1>3 · Estrategia</h1>
      {readOnly && <Banner>Vista de solo lectura</Banner>}
      <ol className="stepper">{s.stages.map((st: any) => <li key={st.key} className={st.status}>{st.label}</li>)}</ol>
      <div className="chatgrid">
        <section>
          <div className="chat" aria-live="polite">
            {msgs.map((m: any, i: number) => <div key={i} className={`bubble ${m.author}`}>{m.text}</div>)}
            {props.map((p: any) => (
              <div key={p.id} className="proposal">
                <small className="muted">Propuesta · {p.kind}{p.basis ? ` · ${p.basis}` : ""}</small>
                <textarea value={edit[p.id] ?? p.text} onChange={(e) => setEdit({ ...edit, [p.id]: e.target.value })} disabled={readOnly} />
                {!readOnly && <div><button onClick={act(() => http("POST", `/strategy/proposals/${p.id}/save`, { text: edit[p.id] ?? p.text }))}>Guardar</button>{" "}
                  <button className="secondary" onClick={act(() => http("POST", `/strategy/proposals/${p.id}/discard`))}>Descartar</button></div>}
              </div>))}
            <div ref={end} />
          </div>
          {err && <p role="alert" className="error">{err}</p>}
          {!done && !readOnly && <div className="compose"><input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Escribe tu respuesta…" />
            <button onClick={send}>Enviar</button>
            <button className="secondary" onClick={act(() => http("POST", `/strategy/stages/${cur}/complete`))}>Completar etapa</button></div>}
          {done && <p className="banner">Estrategia cerrada. Ya puedes trabajar los casos de uso.</p>}
        </section>
        <aside className="panel"><h3>Lo que hemos definido</h3>
          {s.stages.map((st: any) => { const items = s.items.filter((i: any) => i.stage === st.key); return (
            <div key={st.key}><strong>{st.label}</strong>
              {items.length === 0 ? <p className="muted">Pendiente</p> : items.map((i: any) => (
                <p key={i.key}>{i.text} <small className="muted">v{i.version}</small>
                  {!readOnly && <button className="link" onClick={() => { const t = window.prompt("Editar", i.text); if (t) act(() => http("PUT", `/strategy/items/${i.key}`, { text: t }))(); }}> editar</button>}</p>))}
            </div>); })}
        </aside>
      </div>
    </main>
  );
}
