import type { Incident, IncidentType, Severity } from "./api";

export function timeAgo(iso: string, now = Date.now()) {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function duration(seconds: number) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export function incidentDuration(i: Incident) {
  return duration((new Date(i.last_seen).getTime() - new Date(i.first_seen).getTime()) / 1000);
}

export function clock(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour12: false });
}

export const TYPE_LABEL: Record<IncidentType, string> = {
  ZONE_INTRUSION: "Zone intrusion",
  PPE_VIOLATION: "PPE violation",
  LOITERING: "Loitering",
};

export const SEVERITY_RANK: Record<Severity, number> = { MEDIUM: 1, HIGH: 2, CRITICAL: 3 };

export function toCsv(rows: Incident[]) {
  const cols: (keyof Incident)[] = [
    "id", "type", "severity", "status", "source_id", "track_id", "zone_id",
    "first_seen", "last_seen", "event_count", "max_confidence",
  ];
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}

export function downloadText(name: string, text: string, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
