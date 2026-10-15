import { useSyncExternalStore } from "react";

// Demo-only session kept in the browser. Not real security — the backend owns real access control.
export type Role = "Operator" | "Supervisor";
export interface DemoUser {
  name: string;
  email: string;
  role: Role;
}

export const DEMO_USERS: (DemoUser & { password: string; blurb: string })[] = [
  { name: "Site Operator", email: "operator@siteguard.demo", password: "demo1234", role: "Operator", blurb: "Watch the live feed and acknowledge alerts" },
  { name: "Safety Supervisor", email: "supervisor@siteguard.demo", password: "demo1234", role: "Supervisor", blurb: "Review incidents, resolve and export" },
];

const KEY = "siteguard.session";
const listeners = new Set<() => void>();
let cache: { raw: string | null; user: DemoUser | null } = { raw: null, user: null };

export function getUser(): DemoUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(KEY);
  if (raw !== cache.raw) {
    try {
      cache = { raw, user: raw ? (JSON.parse(raw) as DemoUser) : null };
    } catch {
      cache = { raw, user: null };
    }
  }
  return cache.user;
}

export function signIn(email: string, password: string): DemoUser {
  const u = DEMO_USERS.find((d) => d.email === email.trim().toLowerCase() && d.password === password);
  if (!u) throw new Error("Invalid email or password");
  const user: DemoUser = { name: u.name, email: u.email, role: u.role };
  localStorage.setItem(KEY, JSON.stringify(user));
  listeners.forEach((l) => l());
  return user;
}

export function signOut() {
  localStorage.removeItem(KEY);
  listeners.forEach((l) => l());
}

export function useUser() {
  return useSyncExternalStore(
    (cb) => (listeners.add(cb), () => listeners.delete(cb)),
    getUser,
    () => null,
  );
}

export function homeFor(_role: Role) {
  return "/live";
}
