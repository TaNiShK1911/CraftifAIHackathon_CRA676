import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { toast } from "sonner";
import { API_URL, VIDEO_URL, healthQuery } from "@/lib/api";
import { useLive } from "@/lib/live";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_authenticated/settings")({
  head: () => ({
    meta: [
      { title: "Settings & Diagnostics — SiteGuard" },
      { name: "description", content: "Connection status, MQTT health and active detection thresholds for SiteGuard." },
      { property: "og:title", content: "Settings & Diagnostics — SiteGuard" },
      { property: "og:description", content: "Connection status, MQTT health and active thresholds." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const health = useQuery(healthQuery());
  const { state, lastMessageAt } = useLive();
  const h = health.data;
  const rows: [string, string][] = [
    ["Backend URL", API_URL || "(same origin)"],
    ["Video URL", VIDEO_URL],
    ["Backend", health.isError ? "offline" : h?.status ?? "…"],
    ["SSE stream", state],
    ["MQTT", h?.mqtt_connected == null ? "unknown" : h.mqtt_connected ? "connected" : "disconnected"],
    ["Last message age", h?.last_message_age_s != null ? `${h.last_message_age_s.toFixed(1)}s` : lastMessageAt ? `${((Date.now() - lastMessageAt) / 1000).toFixed(1)}s` : "—"],
    ["Dropped messages", h?.dropped != null ? String(h.dropped) : "—"],
  ];
  const diag = JSON.stringify({ at: new Date().toISOString(), apiUrl: API_URL, videoUrl: VIDEO_URL, sse: state, health: h ?? null, healthError: health.isError }, null, 2);

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Settings</h1>
        <Button variant="outline" onClick={() => navigator.clipboard.writeText(diag).then(() => toast.success("Diagnostics copied"))}>
          <Copy /> Copy diagnostics
        </Button>
      </div>
      <section className="panel divide-y">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 px-4 py-3">
            <span className="label-caps">{k}</span>
            <span className="font-mono text-sm">{v}</span>
          </div>
        ))}
      </section>
      <section className="panel p-4">
        <h2 className="label-caps mb-3">Active thresholds (read-only)</h2>
        {h?.thresholds && Object.keys(h.thresholds).length ? (
          <dl className="grid grid-cols-2 gap-2 font-mono text-sm">
            {Object.entries(h.thresholds).map(([k, v]) => (
              <div key={k} className="flex justify-between border-b py-1"><dt className="text-muted-foreground">{k}</dt><dd>{String(v)}</dd></div>
            ))}
          </dl>
        ) : (
          <p className="text-sm text-muted-foreground">Thresholds are reported by the backend health endpoint.</p>
        )}
      </section>
      <section className="panel p-4 text-sm text-muted-foreground">
        <h2 className="label-caps mb-2">About</h2>
        SiteGuard turns PipeGen edge-vision output into actionable safety incidents. All data shown comes from the live pipeline.
      </section>
    </div>
  );
}
