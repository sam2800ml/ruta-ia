import { FormEvent, useState } from "react";
import { api, setSession } from "./api";
import { Spinner } from "./ui";

export default function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const r = await api.login(email, password);
      setSession(r.access_token, r.role);
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="card narrow">
      <h1>Ruta IA</h1>
      <p className="muted">Ingresa con tu cuenta de empresa.</p>
      <form onSubmit={submit}>
        <label>Correo<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required disabled={loading} /></label>
        <label>Contraseña<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required disabled={loading} /></label>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={loading}>{loading && <Spinner />}{loading ? "Ingresando…" : "Ingresar"}</button>
        {loading && <p className="muted" role="status">Si el servidor estaba inactivo puede tardar hasta un minuto en despertar.</p>}
      </form>
    </main>
  );
}
