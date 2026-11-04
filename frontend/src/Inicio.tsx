import { useCallback, useEffect, useState } from "react";
import { api, http } from "./api";

type StepStatus = "done" | "progress" | "pending";
const STATUS_LABEL: Record<StepStatus, string> = { done: "Completo", progress: "En curso", pending: "Pendiente" };

function relDate(iso: string): string {
  const d = new Date(iso), now = new Date();
  const days = Math.floor((new Date(now.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 864e5);
  if (days === 0) return "Hoy";
  if (days === 1) return "Ayer";
  return d.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function activityText(action: string, detail: any): string {
  const d = typeof detail === "string" ? JSON.parse(detail || "{}") : detail || {};
  switch (action) {
    case "document.uploaded": return `Se subió el documento «${d.name ?? ""}»`;
    case "transcript.uploaded": return `Se cargó la transcripción «${d.name ?? ""}»`;
    case "survey.email_invitation": return `Se invitó a ${d.to ?? "un rol"} a responder la encuesta`;
    case "survey.email_reminder": return `Se envió un recordatorio a ${d.to ?? ""}`;
    case "company.profile_saved": return "Se actualizaron los datos de la empresa";
    case "consent.given": return "Se registró el consentimiento para usar las transcripciones";
    case "report.requested": return "Se solicitó el diagnóstico";
    case "report.published": return "Se publicó el diagnóstico";
    case "report.returned_to_draft": return "El diagnóstico volvió a borrador";
    case "report.exported": return "Se exportó el diagnóstico en PDF";
    case "strategy.started": return "Se inició la estrategia de IA";
    case "strategy.closed": return "Se cerró la estrategia de IA";
    case "use_case.created": return "Se registró un nuevo caso de uso";
    default:
      if (action.startsWith("use_case.")) return `Caso de uso marcado como «${action.split(".")[1]}»`;
      return action.replace(/[._]/g, " ");
  }
}

export default function Inicio({ onGo }: { onGo: (tab: string) => void }) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    const [{ profile, readiness }, documents, surveys, reportState, strategy, useCases, activity] = await Promise.all([
      api.profile(), api.documents(), http<any>("GET", "/surveys"), http<any>("GET", "/reports/state"),
      http<any>("GET", "/strategy"), http<any>("GET", "/use-cases"), http<any[]>("GET", "/activity"),
    ]);
    setData({ profile, readiness, documents, surveys, reportState, strategy, useCases, activity });
  }, []);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);

  if (err) return <main className="card"><p className="error">{err}</p></main>;
  if (!data) return <main className="card">Cargando…</main>;
  const { profile, readiness, documents, surveys, reportState, strategy, useCases, activity } = data;

  const processed = documents.filter((d: any) => d.status === "processed").length;
  const step1: StepStatus = readiness.can_continue ? "done" : documents.length > 0 ? "progress" : "pending";
  const step2: StepStatus = reportState.published ? "done" : reportState.latest || surveys.complete > 0 ? "progress" : "pending";
  const step3: StepStatus = !strategy.enabled ? "pending" : strategy.status === "closed" ? "done" : strategy.started ? "progress" : "pending";
  const step4: StepStatus = !useCases.enabled ? "pending" : useCases.cases.length > 0 ? "progress" : "pending";

  const curStageLabel = strategy.started && strategy.stages ? strategy.stages.find((s: any) => s.key === strategy.current_stage)?.label : null;

  const steps = [
    { n: "01", title: "Documentos", status: step1, desc: `${processed} documento${processed === 1 ? "" : "s"} procesado${processed === 1 ? "" : "s"}`
        + (readiness.can_continue ? " y datos de la empresa registrados." : " · faltan datos o documentos obligatorios."),
      cta: "Ver documentos", tab: "Documentos" },
    { n: "02", title: "Diagnóstico", status: step2,
      desc: surveys.total > 0 ? `${surveys.complete} de ${surveys.total} roles respondieron la encuesta.` : "Aún no se han invitado roles a la encuesta.",
      cta: "Continuar diagnóstico", tab: "Diagnóstico" },
    { n: "03", title: "Estrategia", status: step3,
      desc: !strategy.enabled ? strategy.locked_message : strategy.started ? `Etapa actual: ${curStageLabel ?? "—"}.` : "Lista para iniciar.",
      cta: strategy.enabled ? "Ir a estrategia" : null, tab: "Estrategia" },
    { n: "04", title: "Casos de uso", status: step4,
      desc: !useCases.enabled ? useCases.locked_message : `${useCases.cases.length} caso${useCases.cases.length === 1 ? "" : "s"} de uso registrados.`,
      cta: useCases.enabled ? "Ver casos de uso" : null, tab: "Casos de uso" },
  ];

  const pendingSurveys = surveys.surveys.filter((s: any) => s.status === "pending");
  let next: { title: string; desc: string; cta: string; tab: string; extra?: { label: string; fn: () => Promise<any> } } | null = null;
  if (!readiness.can_continue) {
    next = { title: "Completa documentos y datos de la empresa", desc: "Se necesitan para iniciar el diagnóstico.", cta: "Ir a documentos", tab: "Documentos" };
  } else if (surveys.total === 0) {
    next = { title: "Invita a los roles a responder la encuesta", desc: "Cada rol recibe preguntas específicas de su área.", cta: "Ir al diagnóstico", tab: "Diagnóstico" };
  } else if (pendingSurveys.length > 0) {
    const names = pendingSurveys.map((s: any) => s.role_name).join(" y ");
    const deadline = pendingSurveys[0].deadline;
    next = { title: `Falta${pendingSurveys.length === 1 ? "" : "n"} ${pendingSurveys.length} rol${pendingSurveys.length === 1 ? "" : "es"} por responder la encuesta`,
      desc: `${names} aún no responde${pendingSurveys.length === 1 ? "" : "n"}. La fecha límite es el ${deadline}.`,
      cta: "Ir al diagnóstico", tab: "Diagnóstico",
      extra: { label: "Enviar recordatorio", fn: () => http("POST", "/surveys/remind-pending") } };
  } else if (!reportState.latest) {
    next = { title: "Genera el diagnóstico", desc: "Ya tienes respuestas suficientes para generarlo.", cta: "Ir al diagnóstico", tab: "Diagnóstico" };
  } else if (reportState.latest.status === "generating") {
    next = { title: "El diagnóstico se está generando", desc: "Puede tardar unos minutos.", cta: "Ver diagnóstico", tab: "Diagnóstico" };
  } else if (reportState.latest.status === "in_review") {
    next = { title: "Tu diagnóstico está en revisión", desc: "Un consultor revisa cada hallazgo antes de publicarlo.", cta: "Ver estado", tab: "Diagnóstico" };
  } else if (strategy.enabled && !strategy.started) {
    next = { title: "Construye tu estrategia de IA", desc: "Un asistente te guía con base en tu diagnóstico.", cta: "Ir a estrategia", tab: "Estrategia" };
  } else if (strategy.status === "in_progress") {
    next = { title: "Continúa tu estrategia de IA", desc: curStageLabel ? `Etapa actual: ${curStageLabel}.` : "", cta: "Continuar estrategia", tab: "Estrategia" };
  } else if (useCases.enabled && useCases.cases.length === 0) {
    next = { title: "Registra tus primeros casos de uso", desc: "Prioriza oportunidades de IA según impacto y complejidad.", cta: "Ir a casos de uso", tab: "Casos de uso" };
  }

  const runExtra = async (fn: () => Promise<any>) => { try { await fn(); setMsg("Recordatorio enviado"); await load(); } catch (e) { setErr((e as Error).message); } };

  return (
    <main className="home">
      <p className="eyebrow">Ruta de adopción</p>
      <h1>Hola, bienvenido</h1>
      <p className="sub">este es el avance de tu empresa</p>
      <p className="muted">{profile.name}{profile.sector ? ` · ${profile.sector}` : ""}{profile.size_range ? ` · ${profile.size_range}` : ""}</p>

      <div className="steps">
        {steps.map((s) => (
          <div key={s.n} className="step-card">
            <span className="step-n">{s.n}</span>
            <h3>{s.title}</h3>
            <span className={`badge ${s.status}`}>{STATUS_LABEL[s.status]}</span>
            <p className="muted">{s.desc}</p>
            {s.cta && <button className="link" onClick={() => onGo(s.tab)}>{s.cta}</button>}
          </div>
        ))}
      </div>

      {next && (
        <div className="nextstep">
          <p className="eyebrow">Próximo paso</p>
          <h2>{next.title}</h2>
          {next.desc && <p>{next.desc}</p>}
          {msg && <p role="status">{msg}</p>}
          <div className="actions">
            <button onClick={() => onGo(next!.tab)}>{next.cta}</button>
            {next.extra && <button className="secondary" onClick={() => runExtra(next!.extra!.fn)}>{next.extra.label}</button>}
          </div>
        </div>
      )}

      <section className="activity">
        <h2>Actividad reciente</h2>
        <ul className="docs">
          {activity.slice(0, 6).map((a: any, i: number) => (
            <li key={i}><span>{activityText(a.action, a.detail)}</span><small className="muted">{relDate(a.at)}</small></li>
          ))}
          {activity.length === 0 && <li className="muted">Sin actividad todavía.</li>}
        </ul>
      </section>
    </main>
  );
}
