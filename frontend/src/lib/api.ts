import { queryOptions } from "@tanstack/react-query";

export type Severity = "MEDIUM" | "HIGH" | "CRITICAL";
export type Status = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
export type IncidentType = "ZONE_INTRUSION" | "PPE_VIOLATION" | "LOITERING";
export type DataOrigin = "live" | "replay" | "seed";

export interface Incident {
  id: number;
  type: IncidentType;
  severity: Severity;
  status: Status;
  source_id: string;
  track_id: number | null;
  zone_id: string | null;
  first_seen: string;
  last_seen: string;
  event_count: number;
  max_confidence: number;
  snapshot_path: string | null;
  acknowledged_at?: string | null;
  data_origin: DataOrigin;
}

export interface EventDTO {
  id: number;
  incident_id: number;
  ts: string;
  confidence: number;
}

export interface PipelineRun {
  id: number;
  model_name: string;
  precision: "FP32" | "FP16" | "INT8";
  fps: number;
  latency_ms: number;
  power_w: number | null;
  accuracy_map: number | null;
  data_origin: DataOrigin;
}

export interface Evidence {
  id: number;
  kind: string;
  url: string;
  caption?: string | null;
}

export interface StatsSummary {
  open: number;
  today: number;
  high_critical: number;
  mtta_seconds: number | null;
  by_type?: Partial<Record<IncidentType, number>>;
  fps?: number | null;
}

export interface TimeseriesPoint {
  ts: string;
  count: number;
}

export interface Health {
  status: string;
  mqtt_connected?: boolean;
  last_message_age_s?: number | null;
  last_live_message_age_seconds?: number | null;
  dropped?: number;
  thresholds?: Record<string, unknown>;
  events_by_origin?: Record<string, number>;
  incidents_by_origin?: Record<string, number>;
}

export const API_URL: string = (import.meta.env["VITE_API_URL"] as string | undefined) ?? "";
export const VIDEO_URL: string =
  (import.meta.env["VITE_VIDEO_URL"] as string | undefined) ?? `${API_URL}/media/video`;

export function apiUrl(path: string) {
  return `${API_URL}${path}`;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const ct = res.headers.get("content-type") ?? "";
  if (!res.ok || !ct.includes("json")) throw new Error(`Backend ${res.status} on ${path}`);
  return res.json() as Promise<T>;
}

const live = { retry: false, refetchOnWindowFocus: true } as const;

export const incidentsQuery = (dataOrigin?: DataOrigin) =>
  queryOptions({
    queryKey: ["incidents", dataOrigin ?? "all"],
    queryFn: () => api<Incident[]>(`/api/incidents${dataOrigin ? `?data_origin=${dataOrigin}` : ""}`),
    ...live,
  });
export const summaryQuery = () =>
  queryOptions({ queryKey: ["stats", "summary"], queryFn: () => api<StatsSummary>("/api/stats/summary"), ...live });
export const timeseriesQuery = () =>
  queryOptions({
    queryKey: ["stats", "timeseries"],
    queryFn: () => api<TimeseriesPoint[]>("/api/stats/timeseries?minutes=60"),
    ...live,
  });
export const incidentEventsQuery = (id: number) =>
  queryOptions({ queryKey: ["incidents", id, "events"], queryFn: () => api<EventDTO[]>(`/api/incidents/${id}/events`), ...live });
export const runsQuery = () =>
  queryOptions({ queryKey: ["pipeline", "runs"], queryFn: () => api<PipelineRun[]>("/api/pipeline/runs"), ...live });
export const evidenceQuery = (kind?: string) =>
  queryOptions({
    queryKey: ["evidence", kind ?? "all"],
    queryFn: () => api<Evidence[]>(`/api/evidence${kind ? `?kind=${kind}` : ""}`),
    ...live,
  });
export const healthQuery = () =>
  queryOptions({ queryKey: ["health"], queryFn: () => api<Health>("/api/health"), retry: false, refetchInterval: 3000 });

export function patchIncident(id: number, status: Status) {
  return api<Incident>(`/api/incidents/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
}
