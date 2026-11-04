import { useEffect, useState } from "react";
import { download, http } from "./api";
import { Evidence, kindLabel, PillarBars, Radar } from "./ui";

export default function Informe({ readOnly = false, onGo }: { readOnly?: boolean; onGo?: (t: string) => void }) {
  const [r, setR] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { http("GET", "/reports/published").then(setR).catch((e) => setErr(e.message)); }, []);
  if (err) return null;
  if (!r) return <p className="muted">Cargando informe…</p>;
  const scores = r.pillars as { label: string; score: number; low: boolean }[];
  const byId = Object.fromEntries(r.findings.map((f: any) => [f.id, f]));
  return (
    <div>
      <div className="head2">
        <div><h2>Informe de diagnóstico · versión {r.version}</h2>
          <p className="muted">Respaldado por {r.roles_responded} de {r.roles_total} roles · metodología v{r.methodology_version}</p></div>
        <span className="pill processed">Revisado por consultor · publicado</span>
      </div>
      <div className="level-card">
        <div className="level"><div className="big">{r.level} <small>de 5</small></div><div><strong>{r.level_name}</strong><br /><span className="muted">{r.level_description} Promedio {r.average?.toFixed(1)}</span></div></div>
      </div>
      <div className="two">
        <Radar scores={scores} />
        <div>
          <h3>Puntaje por pilar</h3>
          <PillarBars scores={scores} />
          <small className="muted">En naranja, los pilares por debajo de 2.</small>
        </div>
      </div>
      <h3>Hallazgos</h3>
      {r.findings.map((f: any) => (
        <article key={f.id} className={`finding ${f.kind}`}>
          <header><span className="tag">{kindLabel[f.kind]}</span> <small className="muted">{f.pillar_label}</small></header>
          <strong>{f.title}</strong><p>{f.description}</p>
          {f.evidence.map((e: any) => <Evidence key={e.id} e={e} />)}
        </article>))}
      <h3>Recomendaciones prioritarias</h3>
      <ol>{r.recommendations.map((x: any) => <li key={x.id}>{x.text}<br /><small className="muted">Apoyada en: {x.finding_ids.map((i: string) => byId[i]?.title).filter(Boolean).join("; ") || "—"}</small></li>)}</ol>
      <p className="muted">{r.declaration}</p>
      <div className="actions">
        {!readOnly && <button className="secondary" onClick={() => download("/reports/published/pdf", `diagnostico-v${r.version}.pdf`)}>Exportar PDF</button>}
        {onGo && <button onClick={() => onGo("Estrategia")}>Construir la estrategia</button>}
      </div>
    </div>
  );
}
