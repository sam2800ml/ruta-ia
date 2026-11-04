// Modo demo: cuando no hay backend (GitHub Pages), estas funciones simulan la API
// en memoria con datos de ejemplo, para poder mostrar la aplicación completa.
const iso = (d: number) => new Date(Date.now() + d * 864e5).toISOString();
const today = () => new Date().toISOString().slice(0, 10);

const OPTIONS = {
  sectors: ["Manufactura", "Salud", "Logística", "Comercio", "Educación", "Tecnología", "Servicios financieros"],
  sizes: ["1 a 10 colaboradores", "11 a 50 colaboradores", "51 a 200 colaboradores", "201 a 500 colaboradores", "Más de 500 colaboradores"],
  document_types: {
    plan_estrategico: "Plan estratégico", organigrama: "Organigrama", mapa_procesos: "Mapa de procesos",
    informe_tecnologia: "Informe de tecnología", politica_datos: "Política de datos personales",
    inventario_sistemas: "Inventario de sistemas", otro: "Otro",
  } as Record<string, string>,
};

const PROFILE = {
  id: "demo-company", name: "Empresa Demo S.A.S.", nit: "860035827", sector: "Manufactura",
  size_range: "201 a 500 colaboradores", city: "Cali", website: "", status: "active",
};

let documents = [
  { id: "d1", name: "Plan estratégico 2025-2028.pdf", doc_type: "plan_estrategico", size_bytes: 3_200_000, status: "processed" as const, error: null, created_at: iso(-30) },
  { id: "d2", name: "Organigrama.pdf", doc_type: "organigrama", size_bytes: 800_000, status: "processed" as const, error: null, created_at: iso(-29) },
  { id: "d3", name: "Mapa de procesos.docx", doc_type: "mapa_procesos", size_bytes: 1_400_000, status: "processed" as const, error: null, created_at: iso(-28) },
  { id: "d4", name: "Informe de TI 2026.pdf", doc_type: "informe_tecnologia", size_bytes: 2_100_000, status: "processed" as const, error: null, created_at: iso(-27) },
  { id: "d5", name: "Política de tratamiento de datos.pdf", doc_type: "politica_datos", size_bytes: 600_000, status: "processed" as const, error: null, created_at: iso(-26) },
  { id: "d6", name: "Indicadores de operación.docx", doc_type: "otro", size_bytes: 900_000, status: "processing" as const, error: null, created_at: iso(-1) },
];

let surveys = [
  { id: "s1", role_name: "Dirección", responsible: "Camila Restrepo", email: "gerencia@empresademo.co", status: "complete", deadline: "2026-10-10", total: 8 },
  { id: "s2", role_name: "Tecnología", responsible: "Andrés Gómez", email: "ti@empresademo.co", status: "complete", deadline: "2026-10-10", total: 8 },
  { id: "s3", role_name: "Operaciones", responsible: "Laura Pérez", email: "operaciones@empresademo.co", status: "complete", deadline: "2026-10-10", total: 8 },
  { id: "s4", role_name: "Mercadeo", responsible: "Julián Ortiz", email: "mercadeo@empresademo.co", status: "complete", deadline: "2026-10-10", total: 8 },
  { id: "s5", role_name: "Talento Humano", responsible: "María Fernanda Ríos", email: "talento@empresademo.co", status: "complete", deadline: "2026-10-10", total: 8 },
  { id: "s6", role_name: "Legal", responsible: "Santiago Molina", email: "legal@empresademo.co", status: "pending", deadline: "2026-10-10", total: 8 },
  { id: "s7", role_name: "Finanzas", responsible: "Daniela Castro", email: "finanzas@empresademo.co", status: "pending", deadline: "2026-10-10", total: 8 },
];

let transcripts = [
  { id: "t1", name: "Reunión de dirección", meeting_date: "2026-09-12", duration_min: 48, roles: ["Dirección"], has_timestamps: true, status: "analyzed", usable: true },
  { id: "t2", name: "Mesa de trabajo de operaciones", meeting_date: "2026-09-14", duration_min: 62, roles: ["Operaciones", "Tecnología"], has_timestamps: true, status: "analyzed", usable: true },
  { id: "t3", name: "Entrevista de mercadeo", meeting_date: "2026-09-18", duration_min: 35, roles: ["Mercadeo"], has_timestamps: true, status: "processing", usable: true },
];

let consent = { given: true, text: "Confirmo que los participantes de las reuniones fueron informados y autorizaron el uso de sus transcripciones para el diagnóstico, conforme a la Ley 1581 de 2012." };

const outbox = [
  ...surveys.map((s, i) => ({ id: `o${i}`, to_email: s.email, subject: "Encuesta de adopción de IA", body: `Hola. Responde la encuesta como «${s.role_name}» antes del ${s.deadline}.`, kind: "invitation", created_at: iso(-20 + i), sent_at: iso(-20 + i) })),
  { id: "o10", to_email: "legal@empresademo.co", subject: "Recordatorio: tu encuesta de adopción de IA", body: "Hola. Responde la encuesta como «Legal» antes del 2026-10-10.", kind: "reminder", created_at: iso(-2), sent_at: iso(-2) },
];

const PILLAR_SCORES = [
  { key: "strategy", label: "Estrategia", score: 2.4, low: false },
  { key: "infrastructure", label: "Infraestructura", score: 3.1, low: false },
  { key: "data", label: "Datos", score: 1.8, low: true },
  { key: "governance", label: "Gobernanza", score: 1.5, low: true },
  { key: "talent", label: "Talento", score: 2.2, low: false },
  { key: "culture", label: "Cultura", score: 3.0, low: false },
];

const FINDINGS = [
  { id: "f1", kind: "contradiccion", pillar_label: "Datos", title: "Tecnología reporta datos de clientes centralizados en el CRM, pero operaciones y mercadeo describen bases paralelas en hojas de cálculo.",
    description: "Tecnología reporta datos de clientes centralizados en el CRM, pero operaciones y mercadeo describen bases paralelas en hojas de cálculo.",
    evidence: [{ id: "e1", source_type: "transcript", ref: { transcript: "Mesa de trabajo de operaciones", start_sec: 23 * 60 }, quote: "Cada vendedor lleva su propio Excel con los clientes que atiende." },
      { id: "e2", source_type: "survey", ref: { role: "Tecnología" }, quote: "Encuesta de Tecnología, pregunta 4: calificó la centralización de datos con 4 de 5." }] },
  { id: "f2", kind: "brecha", pillar_label: "Gobernanza", title: "No existe una política de uso de IA ni un responsable de evaluar sus riesgos.",
    description: "No existe una política de uso de IA ni un responsable de evaluar sus riesgos.",
    evidence: [{ id: "e3", source_type: "transcript", ref: { transcript: "Reunión de dirección", start_sec: 31 * 60 }, quote: "Hoy cada área usa las herramientas de IA que quiere, sin ninguna regla." }] },
  { id: "f3", kind: "fortaleza", pillar_label: "Cultura", title: "Los equipos muestran disposición a experimentar: operaciones ya probó un piloto de visión por computador en control de calidad.",
    description: "Los equipos muestran disposición a experimentar: operaciones ya probó un piloto de visión por computador en control de calidad.",
    evidence: [{ id: "e4", source_type: "transcript", ref: { transcript: "Mesa de trabajo de operaciones", start_sec: 47 * 60 }, quote: "El piloto de la cámara en la línea dos nos dejó con ganas de más." }] },
  { id: "f4", kind: "brecha", pillar_label: "Talento", title: "No hay perfiles de analítica o ciencia de datos y la formación en IA ha sido autodidacta.",
    description: "No hay perfiles de analítica o ciencia de datos y la formación en IA ha sido autodidacta.",
    evidence: [{ id: "e5", source_type: "survey", ref: { role: "Talento Humano" }, quote: "Encuesta de Talento humano, preguntas 3 y 7: promedio de 1,8 de 5." }] },
];

const PUBLISHED_REPORT = {
  version: 1, roles_responded: 5, roles_total: 7, methodology_version: 1,
  level: 2, level_name: "Activo", level_description: "Hay experimentos aislados, pero aún ningún caso de IA en producción con valor medible.",
  average: 2.3, pillars: PILLAR_SCORES, findings: FINDINGS,
  recommendations: [
    { id: "r1", text: "Crear un comité de IA con dirección, tecnología y legal, y aprobar una política de uso responsable.", finding_ids: ["f2"] },
    { id: "r2", text: "Unificar los datos de clientes en el CRM antes de cualquier caso de uso comercial.", finding_ids: ["f1"] },
    { id: "r3", text: "Formar a un equipo base de cinco personas en fundamentos de IA y analítica.", finding_ids: ["f4"] },
  ],
  declaration: "Este informe fue generado con apoyo de IA y revisado por un consultor humano antes de publicarse.",
};

const DISCLOSURE = "Soy un asistente de IA. Solo hablo de la estrategia de IA de su empresa y no guardo nada sin su decisión.";
const STAGE_LABELS: Record<string, string> = { vision: "Visión", objetivos: "Objetivos de negocio", gobernanza: "Principios de gobernanza", oportunidades: "Oportunidades", okrs: "OKRs" };
const STAGES = Object.keys(STAGE_LABELS);

let strategy = {
  status: "in_progress", current_stage: "gobernanza",
  stages: STAGES.map((key, i) => ({ key, label: STAGE_LABELS[key], status: i < 2 ? "complete" : i === 2 ? "current" : "pending" })),
  items: [
    { key: "i1", version: 1, stage: "vision", kind: "vision", text: "Usar la IA para producir con menos desperdicio y responder más rápido a nuestros clientes, con decisiones basadas en datos confiables.", basis: null },
    { key: "i2", version: 1, stage: "objetivos", kind: "objetivo", text: "Reducir el tiempo de respuesta al cliente.", basis: null },
    { key: "i3", version: 1, stage: "objetivos", kind: "objetivo", text: "Disminuir el inventario sin afectar las entregas.", basis: null },
    { key: "i4", version: 1, stage: "objetivos", kind: "objetivo", text: "Liberar tiempo administrativo para tareas de mayor valor.", basis: null },
    { key: "i5", version: 1, stage: "gobernanza", kind: "principio", text: "Todo caso de uso de IA que procese datos personales debe ser aprobado por un comité de IA, conformado por Gerencia General, Tecnología y Legal, antes de iniciar su piloto. El comité revisa esta política cada seis meses.", basis: null },
  ],
  messages: [
    { stage: "gobernanza", author: "assistant", text: DISCLOSURE + " Con la visión y los objetivos definidos, pasemos a la gobernanza. Tu diagnóstico mostró que no existe una política de uso de IA (Gobernanza: 1,5 de 5). ¿Quién debería aprobar los nuevos casos de uso de IA en la empresa?", at: iso(-5) },
    { stage: "gobernanza", author: "user", text: "Creo que un comité con gerencia, tecnología y legal.", at: iso(-5) },
    { stage: "gobernanza", author: "assistant", text: "Buena base. Guardé el principio con revisión semestral. Siguiente tema: ¿cómo deben manejar los equipos las herramientas de IA generativa públicas cuando trabajan con información de la empresa?", at: iso(-5) },
  ],
  proposals: [] as any[],
  context: { weakest: { pillar: "governance", label: "Gobernanza", score: 1.5 }, level: 2, average: 2.3 },
};

const caseFicha = (c: any) => ({
  ...c, label: null, hours_per_year: c.hours_per_year ?? null,
  formula: "Supuesto editable: casos al mes × minutos ahorrados en cada uno",
  assumptions: { volume_per_month: c.volume_per_month, minutes_saved: c.minutes_saved },
  complexity_parts: c.complexity_parts, complexity_notes: c.complexity_notes, law_note: c.law_note ?? null,
});

let useCases = [
  { id: "u1", n: 1, name: "Clasificación automática de PQRS", area: "Servicio al cliente", impact: 4.0, complexity: 2.3, risk: "limitado", status: "approved", zone: "quick_win",
    indicator: "Tiempo promedio de respuesta a PQRS", baseline: "5 días", target: "2 días en 6 meses",
    tech: "LLM con clasificación y recuperación aumentada (RAG) sobre el histórico de respuestas",
    hours_per_year: 1200, volume_per_month: 400, minutes_saved: 15,
    complexity_parts: { legal: 3, ethic: 2, infra: 2 },
    complexity_notes: { legal: "Procesa datos personales de clientes: requiere autorización y aviso según la Ley 1581 de 2012.", ethic: "Riesgo moderado de priorizar mal casos sensibles; una persona revisa cada respuesta antes de enviarla.", infra: "Requiere integración con el CRM y acceso al histórico de PQRS, que ya está digitalizado." } },
  { id: "u2", n: 2, name: "Asistente de revisión de contratos", area: "Legal", impact: 3.5, complexity: 2.7, risk: "limitado", status: "proposed", zone: "quick_win",
    indicator: "Horas de revisión por contrato", baseline: "3 horas", target: "1 hora",
    tech: "LLM con extracción de cláusulas sobre plantillas estándar",
    hours_per_year: 400, volume_per_month: 30, minutes_saved: 90,
    complexity_parts: { legal: 4, ethic: 2, infra: 2 },
    complexity_notes: { legal: "Revisa obligaciones contractuales: requiere validación de un abogado antes de enviar.", ethic: "Riesgo bajo: no toma decisiones, solo resalta cláusulas.", infra: "Requiere acceso al repositorio de contratos." } },
  { id: "u3", n: 3, name: "Pronóstico de demanda", area: "Operaciones", impact: 4.5, complexity: 2.0, risk: "mínimo", status: "pilot", zone: "quick_win",
    indicator: "Error de pronóstico (MAPE)", baseline: "22%", target: "12%",
    tech: "Modelo de series de tiempo sobre histórico de ventas e inventario",
    hours_per_year: 600, volume_per_month: null, minutes_saved: null,
    complexity_parts: { legal: 1, ethic: 1, infra: 3 },
    complexity_notes: { legal: "No usa datos personales.", ethic: "Riesgo mínimo: decisión de inventario, no afecta personas directamente.", infra: "Requiere integrar el histórico de ventas con el sistema de inventario." } },
  { id: "u4", n: 4, name: "Contenido para campañas", area: "Mercadeo", impact: 2.5, complexity: 2.3, risk: "limitado", status: "proposed", zone: "mejoras_menores",
    indicator: "Piezas de contenido por mes", baseline: "10", target: "25",
    tech: "LLM generativo con guía de marca",
    hours_per_year: 200, volume_per_month: 15, minutes_saved: 45,
    complexity_parts: { legal: 2, ethic: 3, infra: 1 },
    complexity_notes: { legal: "Debe revisarse el uso de marcas y derechos de imagen.", ethic: "Riesgo de mensajes fuera de tono: requiere revisión editorial.", infra: "No requiere integraciones adicionales." } },
  { id: "u5", n: 5, name: "Preselección de hojas de vida", area: "Talento humano", impact: 3.5, complexity: 3.7, risk: "alto", status: "proposed", zone: "estrategico",
    indicator: "Tiempo de preselección por vacante", baseline: "5 días", target: "1 día",
    tech: "LLM con evaluación de criterios contra el perfil del cargo",
    hours_per_year: 300, volume_per_month: 40, minutes_saved: 20,
    complexity_parts: { legal: 4, ethic: 5, infra: 2 },
    complexity_notes: { legal: "Alto riesgo de discriminación indirecta: requiere evaluación de impacto antes de operar.", ethic: "Decide sobre oportunidades laborales: requiere supervisión humana en toda decisión.", infra: "Requiere integración con el sistema de reclutamiento." },
    law_note: "Riesgo alto: requiere evaluación de impacto y supervisión humana en cada decisión, conforme a la guía de IA responsable." },
  { id: "u6", n: 6, name: "Conciliación contable automática", area: "Finanzas", impact: 3.5, complexity: 2.0, risk: "mínimo", status: "approved", zone: "quick_win",
    indicator: "Horas de conciliación por cierre", baseline: "40 horas", target: "10 horas",
    tech: "Modelo de emparejamiento de transacciones con reglas y aprendizaje supervisado",
    hours_per_year: 360, volume_per_month: null, minutes_saved: null,
    complexity_parts: { legal: 1, ethic: 1, infra: 3 },
    complexity_notes: { legal: "No usa datos personales.", ethic: "Riesgo mínimo: proceso interno, auditado por contabilidad.", infra: "Requiere acceso al ERP contable." } },
].map(caseFicha);

const activity = [
  { action: "report.published", entity: "report", detail: {}, at: iso(-11) },
  { action: "report.requested", entity: "report", detail: {}, at: iso(-12) },
  { action: "survey.email_reminder", entity: "survey", detail: { to: "legal@empresademo.co" }, at: iso(-2) },
  { action: "transcript.uploaded", entity: "transcript", detail: { name: "Entrevista de mercadeo" }, at: iso(-1) },
  { action: "transcript.uploaded", entity: "transcript", detail: { name: "Mesa de trabajo de operaciones" }, at: iso(-15) },
  { action: "document.uploaded", entity: "document", detail: { name: "Indicadores de operación.docx" }, at: iso(-1) },
  { action: "document.uploaded", entity: "document", detail: { name: "Política de tratamiento de datos.pdf" }, at: iso(-26) },
  { action: "strategy.started", entity: "strategy", detail: {}, at: iso(-5) },
  { action: "company.profile_saved", entity: "company", detail: {}, at: iso(-31) },
  { action: "survey.email_invitation", entity: "survey", detail: { to: "finanzas@empresademo.co" }, at: iso(-20) },
];

const dashboard = {
  active_companies: 5, reviews_pending: 2, avg_maturity: 2.5, approved_use_cases: 18,
  pillar_average: [
    { label: "Cultura", avg: 3.0, supported_by: 4, of: 5, low: false },
    { label: "Infraestructura", avg: 2.9, supported_by: 4, of: 5, low: false },
    { label: "Estrategia", avg: 2.6, supported_by: 4, of: 5, low: false },
    { label: "Talento", avg: 2.1, supported_by: 4, of: 5, low: false },
    { label: "Datos", avg: 2.0, supported_by: 4, of: 5, low: false },
    { label: "Gobernanza", avg: 1.7, supported_by: 4, of: 5, low: true },
  ],
  companies_with_diagnosis: 4,
};

const companies = [
  { id: "demo-company", name: "Empresa Demo S.A.S.", nit: "860035827", sector: "Manufactura", stage: "Diagnóstico · encuestas 5/7", maturity: null as any, progress: "1 de 4", last_activity: iso(0) },
  { id: "c2", name: "Empresa Demo 02", nit: "900111222", sector: "Salud", stage: "Estrategia", maturity: { level: 3, average: 2.8 }, progress: "2 de 4", last_activity: iso(-1) },
  { id: "c3", name: "Empresa Demo 03", nit: "900333444", sector: "Logística", stage: "Diagnóstico en revisión", maturity: { level: 2, average: 1.9 }, progress: "1 de 4", last_activity: "2026-09-30" },
  { id: "c4", name: "Empresa Demo 04", nit: "900555666", sector: "Comercio", stage: "Casos de uso", maturity: { level: 3, average: 3.1 }, progress: "4 de 4", last_activity: "2026-09-28" },
  { id: "c5", name: "Empresa Demo 05", nit: "900777888", sector: "Educación", stage: "Diagnóstico en revisión", maturity: { level: 2, average: 2.2 }, progress: "1 de 4", last_activity: "2026-09-27" },
];

const reviewQueue = [
  { id: "c3", name: "Empresa Demo 03", version: 1, findings: 14, sin_evidencia: 1, contradicciones: 0 },
  { id: "c5", name: "Empresa Demo 05", version: 1, findings: 11, sin_evidencia: 0, contradicciones: 2 },
];
const reviewDetail: Record<string, any> = {
  c3: { id: "c3", company_name: "Empresa Demo 03 · Logística", version: 1, level: 1, level_name: "Inicial", average: 1.9, roles_responded: 4, roles_total: 6,
    pillars: PILLAR_SCORES.map((p) => ({ id: p.key, label: p.label, score: p.score, review_status: "pending" })),
    findings: FINDINGS.map((f) => ({ ...f, review_status: "pending", evidence_status: f.id === "f4" ? "insuficiente" : "suficiente" })),
    recommendations: PUBLISHED_REPORT.recommendations.map((r) => ({ ...r, review_status: "pending" })) },
  c5: { id: "c5", company_name: "Empresa Demo 05 · Educación", version: 1, level: 2, level_name: "Activo", average: 2.2, roles_responded: 5, roles_total: 6,
    pillars: PILLAR_SCORES.map((p) => ({ id: p.key, label: p.label, score: p.score, review_status: "pending" })),
    findings: FINDINGS.map((f) => ({ ...f, review_status: "pending", evidence_status: "suficiente" })),
    recommendations: PUBLISHED_REPORT.recommendations.map((r) => ({ ...r, review_status: "pending" })) },
};

let methodology = [{
  version: 1, active: true, reports: 23,
  formula: "Promedio ponderado de las respuestas por pilar, ajustado por evidencia de transcripciones.",
  thresholds: [1.5, 2.5, 3.5, 4.5],
  levels: [
    { level: 1, name: "Inicial", description: "Sin experimentación formal con IA." },
    { level: 2, name: "Activo", description: "Hay experimentos aislados, pero aún ningún caso de IA en producción con valor medible." },
    { level: 3, name: "Definido", description: "Hay casos de IA en producción en al menos un área, con gobernanza básica." },
    { level: 4, name: "Gestionado", description: "La IA se gestiona con métricas e indicadores en varias áreas." },
    { level: 5, name: "Optimizado", description: "La IA es parte central de la estrategia y se mejora continuamente." },
  ],
  pillars: [{ key: "strategy", label: "Estrategia" }, { key: "infrastructure", label: "Infraestructura" }, { key: "data", label: "Datos" },
    { key: "governance", label: "Gobernanza" }, { key: "talent", label: "Talento" }, { key: "culture", label: "Cultura" }],
}];

let questions = [
  { id: "q1", key: "q1", version: 1, text: "¿Qué tan centralizados están los datos de clientes?", pillar: "data", roles: ["Tecnología"], answer_type: "Escala de 1 a 5", contribution: "Peso 1 en el promedio del pilar", weight: 1 },
  { id: "q2", key: "q2", version: 1, text: "¿Existe una política de uso de IA generativa?", pillar: "governance", roles: ["Todos"], answer_type: "Escala de 1 a 5", contribution: "Peso 1 en el promedio del pilar", weight: 1 },
  { id: "q3", key: "q3", version: 1, text: "¿Qué tan dispuesto está su equipo a experimentar con IA?", pillar: "culture", roles: ["Todos"], answer_type: "Escala de 1 a 5", contribution: "Peso 1 en el promedio del pilar", weight: 1 },
];

const analytics = {
  human_control: { share: 0.92 }, evidence: { share: 0.88 }, avg_generation_seconds: 14, compute_cost_per_cycle_usd: 0.42,
  review_proportions: { finding: { accept: 40, edit: 8, reject: 2, total: 50 }, recommendation: { accept: 18, edit: 3, reject: 1, total: 22 }, pillar: { accept: 24, edit: 0, reject: 0, total: 24 } },
};
let evalRuns = [{ id: "run1", at: "2026-09-20T10:00:00Z", system_version: "1.0.0" }];

let nextId = 100;
const uid = () => `demo-${nextId++}`;

type Handler = (p: Record<string, string>, q: URLSearchParams, body: any) => any;
const routes: { method: string; re: RegExp; keys: string[]; fn: Handler }[] = [];
function on(method: string, path: string, fn: Handler) {
  const keys: string[] = [];
  const re = new RegExp("^" + path.replace(/:[a-zA-Z]+/g, (m) => { keys.push(m.slice(1)); return "([^/]+)"; }) + "$");
  routes.push({ method, re, keys, fn });
}

on("GET", "/company/options", () => OPTIONS);
on("GET", "/company/profile", () => ({ profile: PROFILE, readiness: readiness() }));
on("PUT", "/company/profile", (_p, _q, body) => { Object.assign(PROFILE, body); return { profile: PROFILE, readiness: readiness() }; });
function readiness() {
  const done = new Set(documents.filter((d) => d.status === "processed").map((d) => d.doc_type));
  const req = ["plan_estrategico", "organigrama", "mapa_procesos", "informe_tecnologia", "politica_datos"];
  const opt = ["inventario_sistemas"];
  const docs = [...req, ...opt].map((t) => ({ type: t, label: OPTIONS.document_types[t], required: req.includes(t), done: done.has(t) }));
  return { profile_complete: true, missing_fields: [], suggested_documents: docs, missing_documents: docs.filter((d) => d.required && !d.done).map((d) => d.type), can_continue: true };
}

on("GET", "/documents", () => documents);
on("POST", "/documents", (_p, _q, body: FormData) => {
  const file = body.get("file") as File; const doc_type = String(body.get("doc_type"));
  const doc = { id: uid(), name: file?.name ?? "documento.pdf", doc_type, size_bytes: file?.size ?? 100000, status: "processed" as const, error: null, created_at: new Date().toISOString() };
  documents = [...documents, doc];
  return { id: doc.id, name: doc.name, doc_type, status: "uploaded" };
});

on("GET", "/surveys", () => ({ surveys, complete: surveys.filter((s) => s.status === "complete").length, total: surveys.length }));
on("POST", "/surveys", (_p, _q, body) => {
  const s = { id: uid(), role_name: body.role_name, responsible: body.responsible, email: body.email, status: "pending", deadline: body.deadline, total: 8 };
  surveys = [...surveys, s]; return { id: s.id, role_name: s.role_name, status: "pending", questions: 8 };
});
on("POST", "/surveys/:id/reminder", (p) => { return { ok: true, id: p.id }; });
on("POST", "/surveys/remind-pending", () => ({ ok: true }));

on("GET", "/transcripts", () => transcripts);
on("POST", "/transcripts", (_p, _q, body: FormData) => {
  const file = body.get("file") as File; const roles = String(body.get("roles") || "").split(",").map((s) => s.trim()).filter(Boolean);
  const t = { id: uid(), name: (file?.name ?? "transcripcion.txt").replace(/\.[^.]+$/, ""), meeting_date: today(), duration_min: 30, roles, has_timestamps: true, status: "analyzed", usable: true };
  transcripts = [...transcripts, t];
  return { id: t.id, name: t.name, has_timestamps: true, usable: true, warning: null, segments: 12 };
});

on("GET", "/consent", () => consent);
on("POST", "/consent", () => { consent = { ...consent, given: true }; return consent; });

on("GET", "/outbox", () => outbox);

on("GET", "/reports/state", () => ({ latest: { id: "report-1", version: 1, status: "published" }, published: { version: 1, published_at: iso(-11) } }));
on("POST", "/reports", () => ({ id: "report-1", version: 1, status: "generating" }));
on("GET", "/reports/published", () => PUBLISHED_REPORT);

on("GET", "/strategy", () => ({ enabled: true, started: true, status: strategy.status, current_stage: strategy.current_stage, disclosure: DISCLOSURE,
  stages: strategy.stages, items: strategy.items, messages: strategy.messages, proposals: strategy.proposals, context: strategy.context }));
on("POST", "/strategy/start", () => ({ started: true }));
on("POST", "/strategy/messages", (_p, _q, body) => {
  strategy.messages = [...strategy.messages, { stage: strategy.current_stage, author: "user", text: body.text, at: new Date().toISOString() }];
  const reply = "Gracias, lo tendré en cuenta para la estrategia. (Este es un asistente de demostración: en la versión real, el modelo de lenguaje continúa la conversación con base en tu diagnóstico.)";
  strategy.messages = [...strategy.messages, { stage: strategy.current_stage, author: "assistant", text: reply, at: new Date().toISOString() }];
  return { ok: true };
});
on("POST", "/strategy/proposals/:id/save", (_p, _q, body) => { return { ok: true, text: body.text }; });
on("POST", "/strategy/proposals/:id/discard", () => ({ ok: true }));
on("PUT", "/strategy/items/:key", (p, _q, body) => {
  strategy.items = strategy.items.map((i) => i.key === p.key ? { ...i, text: body.text, version: i.version + 1 } : i);
  return { ok: true };
});
on("POST", "/strategy/stages/:stage/complete", (p) => {
  const i = strategy.stages.findIndex((s) => s.key === p.stage);
  strategy.stages = strategy.stages.map((s, idx) => idx === i ? { ...s, status: "complete" } : idx === i + 1 ? { ...s, status: "current" } : s);
  if (i + 1 < STAGES.length) { strategy.current_stage = STAGES[i + 1]; return { closed: false, current_stage: strategy.current_stage }; }
  strategy.status = "closed"; return { closed: true };
});

on("GET", "/use-cases", () => ({ enabled: true, cases: useCases, zones: {
  quick_win: useCases.filter((c) => c.zone === "quick_win").map((c) => c.n),
  estrategico: useCases.filter((c) => c.zone === "estrategico").map((c) => c.n),
  mejoras_menores: useCases.filter((c) => c.zone === "mejoras_menores").map((c) => c.n),
  reconsiderar: useCases.filter((c) => c.zone === "reconsiderar").map((c) => c.n),
} }));
on("GET", "/use-cases/bias", () => ({ areas: Object.values(useCases.reduce((acc: any, c) => {
  acc[c.area] = acc[c.area] || { area: c.area, count: 0 }; acc[c.area].count++; return acc; }, {})) }));
on("GET", "/use-cases/:id", (p) => useCases.find((c) => c.id === p.id) ?? {});
on("POST", "/use-cases", (_p, _q, body) => {
  const n = useCases.length + 1;
  const c = caseFicha({ id: uid(), n, name: body.name, area: body.area, risk: body.risk, status: "proposed", zone: null,
    indicator: body.indicator, baseline: body.baseline, target: body.target, tech: body.tech,
    impact: null, complexity: Number(((body.legal + body.ethic + body.infra) / 3).toFixed(1)),
    volume_per_month: body.volume_per_month, minutes_saved: body.minutes_saved,
    complexity_parts: { legal: Number(body.legal), ethic: Number(body.ethic), infra: Number(body.infra) },
    complexity_notes: { legal: body.legal_note, ethic: body.ethic_note, infra: body.infra_note } });
  useCases = [...useCases, c]; return { id: c.id };
});
on("PUT", "/use-cases/:id", (p, _q, body) => {
  useCases = useCases.map((c) => c.id === p.id ? caseFicha({ ...c, ...body,
    complexity_parts: { legal: Number(body.legal), ethic: Number(body.ethic), infra: Number(body.infra) },
    complexity_notes: { legal: body.legal_note, ethic: body.ethic_note, infra: body.infra_note } }) : c);
  return { ok: true };
});
on("POST", "/use-cases/:id/status", (p, _q, body) => { useCases = useCases.map((c) => c.id === p.id ? { ...c, status: body.status } : c); return { ok: true }; });
on("POST", "/use-cases/from-opportunities", () => ({ created: 0 }));

on("GET", "/activity", () => activity);

on("GET", "/admin/dashboard", () => dashboard);
on("GET", "/admin/companies", (_p, q) => { const term = (q.get("q") || "").toLowerCase();
  return companies.filter((c) => !term || c.name.toLowerCase().includes(term) || c.nit.includes(term)); });
on("POST", "/companies", (_p, _q, body) => ({ id: uid(), invitation_token: "demo-token-" + Math.random().toString(36).slice(2, 10), name: body.name }));

on("GET", "/review/queue", () => reviewQueue);
on("GET", "/review/:id", (p) => {
  const d = reviewDetail[p.id]; if (!d) return {};
  const blocks = [...d.pillars, ...d.findings, ...d.recommendations];
  const reviewed = blocks.filter((b: any) => b.review_status !== "pending").length;
  return { ...d, progress: { reviewed, total: blocks.length } };
});
on("POST", "/review/:id/blocks/:type/:bid", (p, _q, body) => {
  const d = reviewDetail[p.id]; if (!d) return {};
  const coll = p.type === "pillar" ? d.pillars : p.type === "finding" ? d.findings : d.recommendations;
  const row = coll.find((x: any) => x.id === p.bid); if (row) row.review_status = body.action === "accept" ? "accepted" : body.action === "edit" ? "edited" : "rejected";
  return { ok: true };
});
on("POST", "/review/:id/publish", (p) => { reviewQueue.splice(reviewQueue.findIndex((q) => q.id === p.id), 1); return { ok: true }; });

on("GET", "/admin/questions", () => questions);
on("POST", "/admin/questions", (_p, _q, body) => { const q = { id: uid(), key: uid(), version: 1, text: body.text, pillar: body.pillar, roles: body.roles.length ? body.roles : ["Todos"], answer_type: "Escala de 1 a 5", contribution: `Peso ${body.weight} en el promedio del pilar`, weight: body.weight }; questions = [...questions, q]; return { id: q.id }; });
on("PUT", "/admin/questions/:key", (p, _q, body) => { questions = questions.map((q) => q.key === p.key ? { ...q, text: body.text, pillar: body.pillar, roles: body.roles.length ? body.roles : ["Todos"], version: q.version + 1 } : q); return { ok: true }; });
on("DELETE", "/admin/questions/:key", (p) => { questions = questions.filter((q) => q.key !== p.key); return { ok: true }; });

on("GET", "/admin/methodology", () => methodology);
on("POST", "/admin/methodology", (_p, _q, body) => { methodology = [{ ...methodology[0], version: methodology[0].version + 1, levels: body.levels, thresholds: body.thresholds, formula: body.formula }, ...methodology]; return { ok: true }; });

on("GET", "/admin/analytics", () => analytics);
on("GET", "/eval/runs", () => evalRuns);
on("POST", "/eval/runs", () => { const r = { id: uid(), at: new Date().toISOString(), system_version: "1.0.0" }; evalRuns = [r, ...evalRuns]; return r; });

on("POST", "/auth/login", () => ({ access_token: "demo-token", role: "company_user" }));

export function isDemoRoute(method: string, path: string): boolean {
  const clean = path.split("?")[0];
  return routes.some((r) => r.method === method && r.re.test(clean));
}

export function demoRequest(method: string, fullPath: string, body?: any): any {
  const [path, qs] = fullPath.split("?");
  const query = new URLSearchParams(qs ?? "");
  for (const r of routes) {
    if (r.method !== method) continue;
    const m = r.re.exec(path);
    if (!m) continue;
    const params: Record<string, string> = {};
    r.keys.forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1])));
    return r.fn(params, query, body);
  }
  return {};
}

const MIN_PDF = "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
  + "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
  + "4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
  + "5 0 obj<</Length 73>>stream\nBT /F1 14 Tf 20 100 Td (Ruta IA - documento de demostracion) Tj ET\nendstream endobj\n"
  + "trailer<</Root 1 0 R>>";

export function demoBlob(path: string): Blob {
  if (path.endsWith(".csv")) {
    const rows = ["Caso,Área,Impacto,Complejidad,Riesgo,Estado", ...useCases.map((c) => `${c.name},${c.area},${c.impact ?? ""},${c.complexity ?? ""},${c.risk},${c.status}`)];
    return new Blob([rows.join("\n")], { type: "text/csv" });
  }
  return new Blob([MIN_PDF], { type: "application/pdf" });
}
