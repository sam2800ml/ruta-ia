import { FormEvent, useState } from "react";
import { api, setSession } from "./api";

export default function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const r = await api.login(email, password);
      setSession(r.access_token, r.role);
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <main className="card narrow">
      <h1>Ruta IA</h1>
      <p className="muted">Ingresa con tu cuenta de empresa.</p>
      <form onSubmit={submit}>
        <label>Correo<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>Contraseña<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit">Ingresar</button>
      </form>
    </main>
  );
}
