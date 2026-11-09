import { useEffect, useState } from "react";
import { http } from "./api";
import { Loading } from "./ui";

type Q = { id: string; text: string; pillar: string };
const SCALE = ["Muy en desacuerdo", "En desacuerdo", "Neutral", "De acuerdo", "Muy de acuerdo"];

/** Persona que responde: entra por enlace, sin cuenta. */
export default function Survey({ token }: { token: string }) {
  const [role, setRole] = useState("");
  const [qs, setQs] = useState<Q[]>([]);
  const [vals, setVals] = useState<Record<string, number>>({});
  const [state, setState] = useState<"loading" | "form" | "done" | "invalid">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    http("GET", `/survey/${token}/questions`).then((d) => { setRole(d.role_name); setQs(d.questions); setState("form"); }).catch(() => setState("invalid"));
  }, [token]);

  async function send() {
    try {
      await http("POST", `/survey/${token}/answers`, { answers: qs.map((q) => ({ question_id: q.id, value: vals[q.id] })) });
      setState("done");
    } catch (e) { setError((e as Error).message); }
  }

  if (state === "loading") return <main className="card narrow"><Loading /></main>;
  if (state === "invalid") return <main className="card narrow"><h1>Enlace no disponible</h1><p className="muted">Este enlace ya se usó o venció. Pide un recordatorio a quien te invitó.</p></main>;
  if (state === "done") return <main className="card narrow"><h1>¡Gracias!</h1><p>Tus respuestas quedaron registradas.</p></main>;
  const complete = qs.every((q) => vals[q.id]);
  return (
    <main className="card">
      <h1>Encuesta de adopción de IA</h1>
      <p className="muted">Respondes como <strong>{role}</strong>. Tus respuestas se asocian a tu rol. 1 = muy en desacuerdo · 5 = muy de acuerdo.</p>
      {qs.map((q, i) => (
        <fieldset key={q.id} className="q"><legend>{i + 1}. {q.text}</legend>
          <div className="scale">{[1, 2, 3, 4, 5].map((v) => (
            <label key={v} title={SCALE[v - 1]}><input type="radio" name={q.id} checked={vals[q.id] === v} onChange={() => setVals({ ...vals, [q.id]: v })} />{v}</label>))}</div>
        </fieldset>))}
      {error && <p role="alert" className="error">{error}</p>}
      <button disabled={!complete} onClick={send}>Enviar respuestas</button>
    </main>
  );
}
