import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Eye, MonitorPlay } from "lucide-react";
import { VIDEO_URL, healthQuery, incidentsQuery, summaryQuery, timeseriesQuery, type IncidentType } from "@/lib/api";
import { TYPE_LABEL, clock, duration, timeAgo } from "@/lib/format";
import { useLive } from "@/lib/live";
import { cn } from "@/lib/utils";
import { DataOriginChip, EmptyState, SeverityChip } from "@/components/sg/chips";
import { IncidentDrawer } from "@/components/sg/IncidentDrawer";

export const Route = createFileRoute("/_authenticated/live")({
  head: () => ({
    meta: [
      { title: "Live Monitor — SiteGuard" },
      { name: "description", content: "Real-time safety violations from the PipeGen pipeline: video, incident feed and KPIs." },
      { property: "og:title", content: "Live Monitor — SiteGuard" },
      { property: "og:description", content: "Real-time safety violations from the PipeGen pipeline." },
    ],
  }),
  component: LiveMonitor,
});

const tip = { contentStyle: { background: "var(--popover)", border: "1px solid var(--border)", fontFamily: "var(--font-mono)" } };
const axis = { fill: "var(--muted-foreground)", fontSize: 12 };

function useNow(ms = 1000) {
  const [n, setN] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setN(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return n;
}

function VideoPanel() {
  const [failed, setFailed] = useState(false);
  return (
    <section className="panel flex flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="label-caps">Annotated output · cam0</span>
        <span className="flex gap-3 font-mono text-xs">
          <span className="text-sev-critical">■ restricted</span>
          <span className="text-sev-medium">■ PPE required</span>
          <span className="text-chart-4">■ walkway</span>
        </span>
      </div>
      <div className="relative aspect-video bg-background">
        {failed ? (
          <EmptyState icon={<MonitorPlay className="size-10" />} title="No video stream available">
            Open the PipeGen live window on the demo machine, or bridge RTSP via MediaMTX and set VITE_VIDEO_URL.
          </EmptyState>
        ) : (
          <video className="size-full object-contain" src={VIDEO_URL} autoPlay muted loop playsInline onError={() => setFailed(true)} />
        )}
      </div>
    </section>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="panel p-4">
      <p className="label-caps">{label}</p>
      <p className={cn("mt-1 font-mono text-5xl font-bold tabular-nums", tone)}>{value}</p>
    </div>
  );
}

function LiveMonitor() {
  const now = useNow();
  const [sel, setSel] = useState<number | null>(null);
  const [liveOnly, setLiveOnly] = useState(false);
  const { freshIds, lastMessageAt } = useLive();
  const incidents = useQuery(incidentsQuery(liveOnly ? "live" : undefined));
  const summary = useQuery(summaryQuery());
  const ts = useQuery(timeseriesQuery());
  const health = useQuery(healthQuery());
  const s = summary.data;
  const dash = "—";

  const byType = (Object.keys(TYPE_LABEL) as IncidentType[]).map((t) => ({
    type: TYPE_LABEL[t],
    count: s?.by_type?.[t] ?? incidents.data?.filter((i) => i.type === t).length ?? 0,
  }));
  const feed = [...(incidents.data ?? [])].sort((a, b) => +new Date(b.first_seen) - +new Date(a.first_seen)).slice(0, 30);
  const lastAge = lastMessageAt ? `${Math.round((now - lastMessageAt) / 1000)}s` : health.data?.last_message_age_s != null ? `${Math.round(health.data.last_message_age_s)}s` : dash;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      <VideoPanel />

      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <Kpi label="Open" value={s?.open ?? dash} tone="text-sev-high" />
          <Kpi label="Today" value={s?.today ?? dash} />
          <Kpi label="High/Crit" value={s?.high_critical ?? dash} tone="text-sev-critical" />
          <Kpi label="MTTA" value={s?.mtta_seconds != null ? duration(s.mtta_seconds) : dash} />
        </div>
        <section className="panel p-3">
          <p className="label-caps mb-2">Incidents by type</p>
          <div className="h-32">
            <ResponsiveContainer>
              <BarChart data={byType} layout="vertical" margin={{ left: 10 }}>
                <XAxis type="number" allowDecimals={false} tick={axis} />
                <YAxis type="category" dataKey="type" width={110} tick={axis} />
                <Tooltip {...tip} cursor={{ fill: "var(--accent)" }} />
                <Bar dataKey="count" fill="var(--primary)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <section className="panel flex min-h-80 flex-col lg:col-start-2 lg:row-start-2">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="label-caps">Live incident feed</span>
            <button
              type="button"
              onClick={() => setLiveOnly(!liveOnly)}
              className={cn(
                "rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase transition-colors",
                liveOnly ? "border-ok bg-ok/10 text-ok" : "border-border text-muted-foreground hover:bg-accent",
              )}
            >
              {liveOnly ? "✓ Live Only" : "All Origins"}
            </button>
          </div>
          <span className="font-mono text-xs text-muted-foreground">last msg {lastAge}</span>
        </div>
        <ul aria-live="polite" className="max-h-[420px] flex-1 divide-y overflow-y-auto">
          {feed.length === 0 ? (
            <EmptyState icon={<Eye className="size-8" />} title={incidents.isError ? "Waiting for backend…" : liveOnly ? "No live violations (watching…)" : "Watching… no violations detected"}>
              MQTT {health.data?.mqtt_connected ? "connected" : "disconnected"} · last message {lastAge}
            </EmptyState>
          ) : (
            feed.map((i) => (
              <li key={i.id}>
                <button
                  onClick={() => setSel(i.id)}
                  className={cn(
                    "grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 px-3 py-3 text-left text-base hover:bg-accent focus-visible:bg-accent focus-visible:outline-none",
                    freshIds.has(i.id) && "animate-flash-in",
                  )}
                >
                  <div className="flex items-center gap-1.5">
                    <SeverityChip severity={i.severity} />
                    <DataOriginChip origin={i.data_origin} />
                  </div>
                  <span>
                    <span className="font-semibold">{TYPE_LABEL[i.type]}</span>
                    <span className="ml-2 font-mono text-sm text-muted-foreground">
                      {i.zone_id ?? "—"} · #{i.track_id ?? "—"} · {(i.max_confidence * 100).toFixed(0)}%
                    </span>
                  </span>
                  <span className="font-mono text-sm text-muted-foreground" title={clock(i.first_seen)}>
                    {timeAgo(i.first_seen, now)}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      </section>

      <section className="panel p-3 lg:col-start-1 lg:row-start-2">
        <p className="label-caps mb-2">Violations per minute · last 60 min</p>
        <div className="h-64">
          {ts.data?.length ? (
            <ResponsiveContainer>
              <AreaChart data={ts.data.map((p) => ({ t: clock(p.ts).slice(0, 5), count: p.count }))}>
                <defs>
                  <linearGradient id="vpm" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                <XAxis dataKey="t" tick={axis} minTickGap={30} />
                <YAxis allowDecimals={false} tick={axis} width={30} />
                <Tooltip {...tip} />
                <Area type="stepAfter" dataKey="count" stroke="var(--primary)" fill="url(#vpm)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title={ts.isError ? "Timeline unavailable" : "No violations in the last hour"} />
          )}
        </div>
      </section>

      <IncidentDrawer id={sel} onClose={() => setSel(null)} />
    </div>
  );
}
