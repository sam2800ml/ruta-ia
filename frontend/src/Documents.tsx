import { ChangeEvent, DragEvent, useCallback, useEffect, useState } from "react";
import { api, Doc, Options, Profile, Readiness } from "./api";
import { Loading } from "./ui";

const STATUS: Record<Doc["status"], string> = {
  uploaded: "Cargado", processing: "Procesando", processed: "Procesado", error: "Con error",
};
const FIELD_LABELS: Record<string, string> = {
  name: "razón social", nit: "NIT", sector: "sector", size_range: "tamaño", city: "ciudad",
};
const fmtSize = (b: number) => b < 1024 * 1024 ? `${(b / 1024).toFixed(1)} KB` : `${(b / (1024 * 1024)).toFixed(1)} MB`;

export default function Documents({ readOnly = false }: { readOnly?: boolean }) {
  const [opts, setOpts] = useState<Options | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [ready, setReady] = useState<Readiness | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [docType, setDocType] = useState("otro");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const [p, d] = await Promise.all([api.profile(), api.documents()]);
    setProfile(p.profile); setReady(p.readiness); setDocs(d);
  }, []);

  useEffect(() => { api.options().then(setOpts); refresh().catch((e) => setError(e.message)); }, [refresh]);

  // Mientras haya documentos en proceso se consulta su estado: al volver, la pantalla ya está al día.
  const pending = docs.some((d) => d.status === "uploaded" || d.status === "processing");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => refresh().catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [pending, refresh]);

  async function save() {
    if (!profile) return;
    try {
      const { name, nit, sector, size_range, city, website } = profile;
      const r = await api.saveProfile({ name, nit, sector, size_range, city, website });
      setProfile(r.profile); setReady(r.readiness); setMsg("Borrador guardado"); setError("");
    } catch (e) { setError((e as Error).message); }
  }

  async function uploadFiles(files: FileList | File[]) {
    setError("");
    for (const f of Array.from(files)) {
      try { await api.upload(f, docType); } catch (e) { setError(`${f.name}: ${(e as Error).message}`); }
    }
    refresh();
  }

  if (!profile || !ready || !opts) return <main className="card">{error ? <p className="error">{error}</p> : <Loading />}</main>;
  const set = (k: keyof Profile) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setProfile({ ...profile, [k]: e.target.value || null });

  return (
    <main className="card">
      <h1>1 · Documentos</h1>{readOnly && <p className="banner">Vista de solo lectura</p>}<fieldset disabled={readOnly} className="plain">

      <section className="panel">
        <h2>Datos de la empresa</h2>
        <div className="grid">
          <label>Razón social<input value={profile.name ?? ""} onChange={set("name")} /></label>
          <label>NIT<input value={profile.nit ?? ""} onChange={set("nit")} /></label>
          <label>Sector<select value={profile.sector ?? ""} onChange={set("sector")}>
            <option value="">Selecciona</option>{opts.sectors.map((s) => <option key={s}>{s}</option>)}</select></label>
          <label>Tamaño<select value={profile.size_range ?? ""} onChange={set("size_range")}>
            <option value="">Selecciona</option>{opts.sizes.map((s) => <option key={s}>{s}</option>)}</select></label>
          <label>Ciudad<input value={profile.city ?? ""} onChange={set("city")} /></label>
          <label>Sitio web<input value={profile.website ?? ""} onChange={set("website")} /></label>
        </div>
        <button onClick={save}>Guardar borrador</button> <span className="muted" role="status">{msg}</span>
      </section>

      <div className="two">
        <section className="panel">
          <h2>Documentos iniciales</h2>
          <label>Tipo de documento<select value={docType} onChange={(e) => setDocType(e.target.value)}>
            {Object.entries(opts.document_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <div className="drop" onDragOver={(e: DragEvent) => e.preventDefault()}
            onDrop={(e: DragEvent) => { e.preventDefault(); uploadFiles(e.dataTransfer.files); }}>
            Arrastra aquí tus archivos o <label className="pick">selecciónalos
              <input type="file" multiple accept=".pdf,.docx,.txt" hidden onChange={(e) => e.target.files && uploadFiles(e.target.files)} />
            </label>
            <small>PDF, DOCX o TXT · hasta 25 MB</small>
          </div>
          {error && <p role="alert" className="error">{error}</p>}
        </section>

        <section className="panel">
          <h2>Documentos sugeridos</h2>
          <ul className="docs">
            {ready.suggested_documents.map((d) => (
              <li key={d.type}><span>{d.done ? "✓" : "○"} {d.label}</span><small className="muted">{d.required ? "Requerido" : "Opcional"}</small></li>
            ))}
          </ul>
        </section>
      </div>

      {docs.length > 0 && (
        <section className="panel">
          <table>
            <thead><tr><th>Nombre</th><th>Tipo</th><th>Tamaño</th><th>Estado</th></tr></thead>
            <tbody>{docs.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td><td>{opts.document_types[d.doc_type]}</td><td>{fmtSize(d.size_bytes)}</td>
                <td><span className={`pill ${d.status}`} title={d.error ?? ""}>{STATUS[d.status]}</span></td>
              </tr>))}</tbody>
          </table>
        </section>
      )}

      <footer>
        {!ready.can_continue && (
          <p className="muted">
            Falta: {[...ready.missing_fields.map((f) => FIELD_LABELS[f] ?? f),
              ...ready.missing_documents.map((t) => opts.document_types[t])].join(", ")}.
          </p>
        )}
        <button disabled={!ready.can_continue}>Continuar al diagnóstico</button>
      </footer>
    </fieldset></main>
  );
}
