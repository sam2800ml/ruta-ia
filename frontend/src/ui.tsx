import { ReactNode } from "react";

export const PILLARS = ["strategy", "infrastructure", "data", "governance", "talent", "culture"];

export function Radar({ scores }: { scores: { label: string; score: number }[] }) {
  const n = scores.length, R = 90, cx = 130, cy = 120;
  const pt = (i: number, v: number) => { const a = (Math.PI * 2 * i) / n - Math.PI / 2; return [cx + Math.cos(a) * R * (v / 5), cy + Math.sin(a) * R * (v / 5)]; };
  const poly = (v: number) => scores.map((_, i) => pt(i, v).join(",")).join(" ");
  return (
    <svg viewBox="0 0 260 250" role="img" aria-label="Puntaje por pilar" className="radar">
      {[1, 2, 3, 4, 5].map((v) => <polygon key={v} points={poly(v)} fill="none" stroke="var(--line)" />)}
      <polygon points={scores.map((s, i) => pt(i, s.score).join(",")).join(" ")} fill="var(--accent)" fillOpacity=".25" stroke="var(--accent)" strokeWidth="2" />
      {scores.map((s, i) => { const [x, y] = pt(i, 5.9); return <text key={i} x={x} y={y} textAnchor="middle" fontSize="10" fill="var(--ink)">{s.label}</text>; })}
    </svg>
  );
}

export const PILLAR_LABELS: Record<string, string> = {
  strategy: "Estrategia", infrastructure: "Infraestructura", data: "Datos",
  governance: "Gobernanza", talent: "Talento", culture: "Cultura",
};

export function PillarChips() {
  return <div className="chips">{PILLARS.map((p) => <span key={p} className="chip">{PILLAR_LABELS[p]}</span>)}</div>;
}

export function PillarBars({ scores }: { scores: { label: string; score: number; low?: boolean }[] }) {
  const sorted = [...scores].sort((a, b) => b.score - a.score);
  return (
    <div className="pbars">
      {sorted.map((p) => (
        <div key={p.label} className="pbar">
          <span className="pbar-label">{p.label}</span>
          <div className="pbar-track"><div className={`pbar-fill${p.low ? " low" : ""}`} style={{ width: `${(p.score / 5) * 100}%` }} /></div>
          <strong className="pbar-val">{p.score.toFixed(1)}</strong>
        </div>
      ))}
    </div>
  );
}

export function Banner({ children }: { children: ReactNode }) { return <p className="banner">{children}</p>; }
export function Section({ title, children }: { title: string; children: ReactNode }) { return <section><h2>{title}</h2>{children}</section>; }
export const kindLabel: Record<string, string> = { contradiccion: "Contradicción", brecha: "Brecha", fortaleza: "Fortaleza" };

export function Evidence({ e }: { e: { source_type: string; ref: any; quote: string } }) {
  const where = e.source_type === "survey" ? `Encuesta · ${e.ref.role}`
    : e.source_type === "document" ? `${e.ref.document}${e.ref.page ? ` · p. ${e.ref.page}` : ""}`
    : `${e.ref.transcript}${e.ref.start_sec != null ? ` · ${Math.floor(e.ref.start_sec / 60)}:${String(e.ref.start_sec % 60).padStart(2, "0")}` : ""}`;
  return <blockquote className="ev"><small className="muted">{where}</small><br />{e.quote}</blockquote>;
}
