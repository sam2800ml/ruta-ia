import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, getRole, hasToken, setSession, setViewAs } from "./api";
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

function App() {
  const [auth, setAuth] = useState(hasToken());
  const [companyTab, setCompanyTab] = useState("Inicio");
  const [companyName, setCompanyName] = useState("");
  const [consultantTab, setConsultantTab] = useState("Empresas");
  const [view, setView] = useState<{ id: string; name: string } | null>(null);
  const [viewTab, setViewTab] = useState("Inicio");

  const role = getRole();
  const isConsultant = role === "consultant";

  useEffect(() => {
    if (auth && !isConsultant) api.profile().then(({ profile }) => setCompanyName(profile.name)).catch(() => {});
  }, [auth, isConsultant]);

  const survey = new URLSearchParams(location.search).get("encuesta");
  const inv = new URLSearchParams(location.search).get("invitacion");
  if (survey) return <Survey token={survey} />;
  if (inv && !auth) return <Invitation token={inv} onDone={() => setAuth(true)} />;
  if (!auth) return <Login onDone={() => setAuth(true)} />;

  const logout = () => { setSession(null); setAuth(false); };

  if (!isConsultant) {
    return (
      <Shell brandSub={companyName} nav={COMPANY_NAV} active={companyTab} onSelect={setCompanyTab} onLogout={logout}>
        <CompanyContent tab={companyTab} readOnly={false} onGo={setCompanyTab} />
      </Shell>
    );
  }

  if (view) {
    const exitNav: NavItem[] = [{ key: "__exit", label: "← Salir de esta vista" }, ...COMPANY_NAV];
    return (
      <Shell brandSub={`${view.name} · solo lectura`} nav={exitNav} active={viewTab} onLogout={logout}
        onSelect={(k) => (k === "__exit" ? (setViewAs(null), setView(null)) : setViewTab(k))}>
        <CompanyContent tab={viewTab} readOnly companyId={view.id} onGo={setViewTab} />
      </Shell>
    );
  }

  return (
    <Shell brandSub="Superadministrador" nav={CONSULTANT_NAV} active={consultantTab} onSelect={setConsultantTab} onLogout={logout}>
      {consultantTab === "Empresas" && <Empresas onView={(id, name) => { setView({ id, name }); setViewTab("Inicio"); }} />}
      {consultantTab === "Revisión" && <Revision />}
      {consultantTab === "Banco de preguntas" && <Banco />}
      {consultantTab === "Metodología" && <Metodologia />}
      {consultantTab === "Analítica" && <Analitica />}
    </Shell>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
