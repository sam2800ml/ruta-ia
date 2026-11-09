export type Readiness = {
  profile_complete: boolean; missing_fields: string[]; missing_documents: string[]; can_continue: boolean;
  suggested_documents: { type: string; label: string; required: boolean; done: boolean }[];
};
export type Profile = { id: string; name: string; nit: string | null; sector: string | null; size_range: string | null;
  city: string | null; website: string | null; status: string };
export type Doc = { id: string; name: string; doc_type: string; size_bytes: number;
  status: "uploaded" | "processing" | "processed" | "error"; error: string | null };
export type Options = { sectors: string[]; sizes: string[]; document_types: Record<string, string> };

import { demoBlob, demoRequest } from "./demo";

const API_BASE = import.meta.env.VITE_API_URL || "/api";
export const DEMO = import.meta.env.VITE_DEMO === "true";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

let token: string | null = sessionStorage.getItem("token");
let role: string | null = sessionStorage.getItem("role");
let viewAs: string | null = null;

export const setSession = (t: string | null, r: string | null = null) => {
  token = t; role = r; viewAs = null;
  for (const [k, v] of [["token", t], ["role", r]] as const) v ? sessionStorage.setItem(k, v) : sessionStorage.removeItem(k);
};
export const hasToken = () => !!token;
export const getRole = () => role;
export const setViewAs = (id: string | null) => { viewAs = id; };
export const getViewAs = () => viewAs;

export async function http<T = any>(method: string, path: string, body?: unknown): Promise<T> {
  if (DEMO) {
    await sleep(200 + Math.random() * 200);
    return structuredClone(demoRequest(method, path, body));
  }
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (viewAs) headers.set("X-View-As-Company", viewAs);
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) { headers.set("Content-Type", "application/json"); payload = JSON.stringify(body); }
  const r = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(typeof d.detail === "string" ? d.detail : "Algo salió mal.,");
  }
  return r.json();
}

export async function download(path: string, filename: string) {
  if (DEMO) {
    await sleep(200);
    const url = URL.createObjectURL(demoBlob(path));
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
    return;
  }
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (viewAs) headers.set("X-View-As-Company", viewAs);
  const r = await fetch(`${API_BASE}${path}`, { headers });
  if (!r.ok) throw new Error("No se pudo descargar");
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}

export const api = {
  login: (email: string, password: string) => http<{ access_token: string; role: string }>("POST", "/auth/login", { email, password }),
  options: () => http<Options>("GET", "/company/options"),
  profile: () => http<{ profile: Profile; readiness: Readiness }>("GET", "/company/profile"),
  saveProfile: (p: Partial<Profile>) => http<{ profile: Profile; readiness: Readiness }>("PUT", "/company/profile", p),
  documents: () => http<Doc[]>("GET", "/documents"),
  upload: (file: File, docType: string) => {
    const f = new FormData(); f.append("file", file); f.append("doc_type", docType);
    return http<Doc>("POST", "/documents", f);
  },
};

export const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleDateString("es-CO") : "—");
