import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { incidentsQuery, type DataOrigin, type IncidentType, type Severity, type Status } from "@/lib/api";
import { TYPE_LABEL, clock, downloadText, incidentDuration, toCsv } from "@/lib/format";
import { useIncidentStatus } from "@/lib/mutations";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DataOriginChip, EmptyState, SeverityChip, StatusChip } from "@/components/sg/chips";
import { IncidentDrawer } from "@/components/sg/IncidentDrawer";

export const Route = createFileRoute("/_authenticated/incidents")({
  head: () => ({
    meta: [
      { title: "Incident Log — SiteGuard" },
      { name: "description", content: "Filter, review, acknowledge and resolve safety incidents detected by PipeGen." },
      { property: "og:title", content: "Incident Log — SiteGuard" },
      { property: "og:description", content: "Filter, review, acknowledge and resolve safety incidents." },
    ],
  }),
  component: IncidentsPage,
});

const WINDOWS = { "15m": 15, "1h": 60, "24h": 1440, all: Infinity } as const;

function Filter<T extends string>({ label, value, onChange, options }: { label: string; value: T; onChange: (v: T) => void; options: [T, string][] }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="label-caps">{label}</span>
      <Select value={value} onValueChange={(v) => onChange(v as T)}>
        <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
        <SelectContent>
          {options.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
        </SelectContent>
      </Select>
    </label>
  );
}

function IncidentsPage() {
  const [origin, setOrigin] = useState<DataOrigin | "all">("live");
  const { data, isError, isLoading } = useQuery(incidentsQuery(origin === "all" ? undefined : origin));
  const m = useIncidentStatus();
  const [sel, setSel] = useState<number | null>(null);
  const [status, setStatus] = useState<Status | "all">("all");
  const [type, setType] = useState<IncidentType | "all">("all");
  const [sev, setSev] = useState<Severity | "all">("all");
  const [win, setWin] = useState<keyof typeof WINDOWS>("all");

  const rows = useMemo(() => {
    const cutoff = Date.now() - WINDOWS[win] * 60000;
    return (data ?? [])
      .filter((i) => (status === "all" || i.status === status) && (type === "all" || i.type === type) && (sev === "all" || i.severity === sev))
      .filter((i) => new Date(i.last_seen).getTime() >= cutoff)
      .sort((a, b) => +new Date(b.last_seen) - +new Date(a.last_seen));
  }, [data, status, type, sev, win]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <h1 className="mr-auto text-3xl font-bold">Incidents</h1>
        <Filter label="Origin" value={origin} onChange={setOrigin} options={[["all", "All Origins"], ["live", "Live Only"], ["replay", "Replay Only"], ["seed", "Synthetic/Seed"]]} />
        <Filter label="Status" value={status} onChange={setStatus} options={[["all", "All"], ["OPEN", "Open"], ["ACKNOWLEDGED", "Acknowledged"], ["RESOLVED", "Resolved"]]} />
        <Filter label="Type" value={type} onChange={setType} options={[["all", "All"], ...(Object.entries(TYPE_LABEL) as [IncidentType, string][])]} />
        <Filter label="Severity" value={sev} onChange={setSev} options={[["all", "All"], ["MEDIUM", "Medium"], ["HIGH", "High"], ["CRITICAL", "Critical"]]} />
        <Filter label="Window" value={win} onChange={setWin} options={[["15m", "Last 15 min"], ["1h", "Last hour"], ["24h", "Last 24h"], ["all", "All time"]]} />
        <Button variant="outline" disabled={!rows.length} onClick={() => downloadText(`siteguard-incidents-${Date.now()}.csv`, toCsv(rows))}>
          <Download /> CSV
        </Button>
      </div>

      <div className="panel overflow-x-auto">
        <table className="w-full text-left text-base">
          <thead className="border-b">
            <tr>
              {["ID", "Origin", "Type", "Severity", "Zone", "Track", "First seen", "Duration", "Status", "Actions"].map((h) => (
                <th key={h} className="label-caps px-3 py-2">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((i) => (
              <tr key={i.id} tabIndex={0} onClick={() => setSel(i.id)} onKeyDown={(e) => e.key === "Enter" && setSel(i.id)} className="cursor-pointer hover:bg-accent focus-visible:bg-accent focus-visible:outline-none">
                <td className="px-3 py-2 font-mono text-muted-foreground">#{i.id}</td>
                <td className="px-3 py-2"><DataOriginChip origin={i.data_origin} /></td>
                <td className="px-3 py-2 font-semibold">{TYPE_LABEL[i.type]}</td>
                <td className="px-3 py-2"><SeverityChip severity={i.severity} /></td>
                <td className="px-3 py-2 font-mono">{i.zone_id ?? "—"}</td>
                <td className="px-3 py-2 font-mono">{i.track_id != null ? `#${i.track_id}` : "—"}</td>
                <td className="px-3 py-2 font-mono">{clock(i.first_seen)}</td>
                <td className="px-3 py-2 font-mono">{incidentDuration(i)}</td>
                <td className="px-3 py-2"><StatusChip status={i.status} /></td>
                <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" disabled={i.status !== "OPEN"} onClick={() => m.mutate({ id: i.id, status: "ACKNOWLEDGED" })}>Ack</Button>
                    <Button size="sm" disabled={i.status === "RESOLVED"} onClick={() => m.mutate({ id: i.id, status: "RESOLVED" })}>Resolve</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <EmptyState title={isLoading ? "Loading…" : isError ? "Backend unreachable" : "No incidents match these filters"} />
        )}
      </div>
      <IncidentDrawer id={sel} onClose={() => setSel(null)} />
    </div>
  );
}
