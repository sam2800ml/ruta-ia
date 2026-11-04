import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, DEMO, getRole, hasToken, setSession, setViewAs } from "./api";
import Shell, { NavItem } from "./Shell";
import Inicio from "./Inicio";
import Login from "./Login";
import Documents from "./Documents";
import Diagnostico from "./Diagnostico";
import Estrategia from "./Estrategia";
import Casos from "./Casos";
import Survey from "./Survey";
import Invitation from "./Invitation";
import { Analitica, Banco, Empresas, Metodologia, Revision } from "./Consultor";
import "./styles.css";

const COMPANY_NAV: NavItem[] = [
  { key: "Inicio", label: "Inicio" },
  { key: "Documentos", label: "1 · Documentos" },
  { key: "Diagnóstico", label: "2 · Diagnóstico" },
  { key: "Estrategia", label: "3 · Estrategia" },
  { key: "Casos de uso", label: "4 · Casos de uso" },
];

const CONSULTANT_NAV: NavItem[] = [
  { key: "Empresas", label: "Empresas" },
  { key: "Revisión", label: "Revisión" },
  { key: "Banco de preguntas", label: "Banco de preguntas" },
  { key: "Metodología", label: "Metodología" },
  { key: "Analítica", label: "Analítica" },
];

function CompanyContent({ tab, readOnly, companyId, onGo }: { tab: string; readOnly: boolean; companyId?: string; onGo: (t: string) => void }) {
  if (tab === "Documentos") return <Documents readOnly={readOnly} />;
  if (tab === "Diagnóstico") return <Diagnostico readOnly={readOnly} onGo={onGo} />;
  if (tab === "Estrategia") return <Estrategia readOnly={readOnly} />;
  if (tab === "Casos de uso") return <Casos readOnly={readOnly} companyId={companyId} />;
  return <Inicio onGo={onGo} />;
}

const DemoBadge = () => DEMO ? <p className="demo-badge">Modo demostración · datos de ejemplo, sin conexión a un backend real</p> : null;

function App() {
  const [auth, setAuth] = useState(DEMO || hasToken());
  const [companyTab, setCompanyTab] = useState("Inicio");
  const [companyName, setCompanyName] = useState("");
  const [consultantTab, setConsultantTab] = useState("Empresas");
  const [view, setView] = useState<{ id: string; name: string } | null>(null);
  const [viewTab, setViewTab] = useState("Inicio");
  const [demoRole, setDemoRole] = useState<"company_user" | "consultant">("company_user");

  const role = DEMO ? demoRole : getRole();
  const isConsultant = role === "consultant";

  useEffect(() => {
    if (auth && !isConsultant) api.profile().then(({ profile }) => setCompanyName(profile.name)).catch(() => {});
  }, [auth, isConsultant]);

  if (!DEMO) {
    const survey = new URLSearchParams(location.search).get("encuesta");
    const inv = new URLSearchParams(location.search).get("invitacion");
    if (survey) return <Survey token={survey} />;
    if (inv && !auth) return <Invitation token={inv} onDone={() => setAuth(true)} />;
  }
  if (!auth) return <Login onDone={() => setAuth(true)} />;

  const logout = () => { setSession(null); setAuth(false); };

  if (!isConsultant) {
    const extra = DEMO ? <button className="link demo-switch" onClick={() => setDemoRole("consultant")}>Vista superadministrador</button> : undefined;
    return (
      <Shell brandSub={companyName} nav={COMPANY_NAV} active={companyTab} onSelect={setCompanyTab} onLogout={logout} extra={extra}>
        <DemoBadge /><CompanyContent tab={companyTab} readOnly={false} onGo={setCompanyTab} />
      </Shell>
    );
  }

  if (view) {
    const exitNav: NavItem[] = [{ key: "__exit", label: "← Salir de esta vista" }, ...COMPANY_NAV];
    return (
      <Shell brandSub={`${view.name} · solo lectura`} nav={exitNav} active={viewTab} onLogout={logout}
        onSelect={(k) => (k === "__exit" ? (setViewAs(null), setView(null)) : setViewTab(k))}>
        <DemoBadge /><CompanyContent tab={viewTab} readOnly companyId={view.id} onGo={setViewTab} />
      </Shell>
    );
  }

  const extra = DEMO ? <button className="link demo-switch" onClick={() => setDemoRole("company_user")}>Ver como empresa</button> : undefined;
  return (
    <Shell brandSub="Superadministrador" nav={CONSULTANT_NAV} active={consultantTab} onSelect={setConsultantTab} onLogout={logout} extra={extra}>
      <DemoBadge />
      {consultantTab === "Empresas" && <Empresas onView={(id, name) => { setView({ id, name }); setViewTab("Inicio"); }} />}
      {consultantTab === "Revisión" && <Revision />}
      {consultantTab === "Banco de preguntas" && <Banco />}
      {consultantTab === "Metodología" && <Metodologia />}
      {consultantTab === "Analítica" && <Analitica />}
    </Shell>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
