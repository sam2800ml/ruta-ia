import { FormEvent, useState } from "react";
import { http, setSession } from "./api";

export default function Invitation({ token, onDone }: { token: string; onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    try { const r = await http("POST", "/auth/accept-invitation", { token, password: pw }); setSession(r.access_token, r.role); history.replaceState(null, "", "/"); onDone(); }
    catch (x) { setErr((x as Error).message); }
  }
  return (
    <main className="card narrow"><h1>Bienvenido a Ruta IA</h1><p className="muted">Crea tu contraseña (mínimo 10 caracteres).</p>
      <form onSubmit={submit}><label>Contraseña<input type="password" minLength={10} required value={pw} onChange={(e) => setPw(e.target.value)} /></label>
        {err && <p role="alert" className="error">{err}</p>}<button type="submit">Crear cuenta</button></form></main>);
}
