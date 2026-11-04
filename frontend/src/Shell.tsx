import { ReactNode } from "react";

export type NavItem = { key: string; label: string };

export default function Shell({
  brandSub, nav, active, onSelect, onLogout, children,
}: {
  brandSub: string;
  nav: NavItem[];
  active: string;
  onSelect: (key: string) => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>Ruta IA</strong>
          <small>{brandSub}</small>
        </div>
        <nav className="sidenav">
          {nav.map((n) => (
            <button key={n.key} className={n.key === active ? "on" : ""} onClick={() => onSelect(n.key)}>{n.label}</button>
          ))}
        </nav>
        <button className="link logout" onClick={onLogout}>Salir</button>
      </aside>
      <main className="shell-main">{children}</main>
    </div>
  );
}
