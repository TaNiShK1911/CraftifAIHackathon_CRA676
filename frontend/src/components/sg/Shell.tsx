import { Link, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { signOut, useUser } from "@/lib/auth";
import { useQuery } from "@tanstack/react-query";
import { AlertOctagon, Radio, ShieldAlert, Volume2, VolumeX, WifiOff } from "lucide-react";
import type { ReactNode } from "react";
import { healthQuery } from "@/lib/api";
import { useLive } from "@/lib/live";
import { TYPE_LABEL, clock } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useIncidentStatus } from "@/lib/mutations";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/live", label: "Live" },
  { to: "/incidents", label: "Incidents" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/settings", label: "Settings" },
] as const;

function Badge({ tone, children }: { tone: "ok" | "warn" | "bad"; children: ReactNode }) {
  const cls = { ok: "text-ok border-ok/40", warn: "text-warn border-warn/40", bad: "text-sev-critical border-sev-critical/50" }[tone];
  return <span className={cn("inline-flex items-center gap-1.5 rounded-sm border px-2 py-1 font-mono text-xs", cls)}>{children}</span>;
}

export function Shell({ children }: { children: ReactNode }) {
  const { state, criticals, dismissCritical, muted, setMuted } = useLive();
  const health = useQuery(healthQuery());
  const ack = useIncidentStatus();
  const user = useUser();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const logout = async () => {
    await qc.cancelQueries();
    qc.clear();
    signOut();
    navigate({ to: "/login", search: {}, replace: true });
  };
  const offline = health.isError;
  const mqtt = health.data?.mqtt_connected;
  const msgAge = health.data?.last_message_age_s;
  const liveIncidents = health.data?.incidents_by_origin?.live ?? 0;
  const crit = criticals[0];

  return (
    <div className="min-h-screen">
      <div className="hazard-stripe h-1.5" aria-hidden />
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
            <ShieldAlert className="size-6 text-primary" aria-hidden /> SiteGuard
          </Link>
          <span className="font-mono text-sm text-muted-foreground">cam0</span>
          <nav className="flex gap-1">
            {NAV.map((n) => (
              <Link
                key={n.to}
                to={n.to}
                                className="rounded-sm px-3 py-1.5 text-sm font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
                activeProps={{ className: "bg-accent text-foreground" }}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {state === "live" ? (
              <Badge tone="ok"><Radio className="size-3.5" /> LIVE · SSE</Badge>
            ) : (
              <Badge tone="warn"><Radio className="size-3.5" /> {state === "connecting" ? "CONNECTING" : "RECONNECTING"}</Badge>
            )}
            {mqtt === false ? (
              <Badge tone="bad">MQTT DISCONNECTED</Badge>
            ) : mqtt ? (
              <Badge tone="ok">BROKER ✓</Badge>
            ) : null}
            {msgAge != null ? (
              <Badge tone="ok">FEED: {Math.round(msgAge)}s</Badge>
            ) : (
              <Badge tone="warn">FEED: IDLE</Badge>
            )}
            {liveIncidents > 0 ? (
              <Badge tone="ok">LIVE: {liveIncidents}</Badge>
            ) : null}
            <Button variant="ghost" size="icon" onClick={() => setMuted(!muted)} aria-label={muted ? "Unmute alerts" : "Mute alerts"}>
              {muted ? <VolumeX /> : <Volume2 />}
            </Button>
            {user && (
              <span className="hidden text-sm sm:inline">
                {user.name} <span className="font-mono text-xs text-muted-foreground">· {user.role}</span>
              </span>
            )}
            <Button variant="ghost" size="icon" onClick={logout} aria-label="Sign out">
              <LogOut />
            </Button>
          </div>
        </div>
      </header>

      {offline && (
        <div role="status" className="flex items-center justify-center gap-2 bg-warn/15 px-4 py-2 text-sm font-semibold text-warn">
          <WifiOff className="size-4" /> Backend offline, retrying every 3s
        </div>
      )}

      {crit && (
        <div role="alert" className="animate-crit flex flex-wrap items-center gap-4 bg-sev-critical px-4 py-3 text-destructive-foreground">
          <AlertOctagon className="size-7" aria-hidden />
          <div className="text-lg font-bold">
            CRITICAL · {TYPE_LABEL[crit.type]} · zone {crit.zone_id ?? "—"} · track #{crit.track_id ?? "—"}
            <span className="ml-3 font-mono text-sm font-normal">{clock(crit.first_seen)}</span>
          </div>
          {criticals.length > 1 && <span className="font-mono text-sm">+{criticals.length - 1} more</span>}
          <Button
            variant="secondary"
            className="ml-auto font-bold"
            onClick={() => {
              ack.mutate({ id: crit.id, status: "ACKNOWLEDGED" });
              dismissCritical(crit.id);
            }}
          >
            Acknowledge
          </Button>
        </div>
      )}

      <main className="mx-auto max-w-[1600px] px-4 py-5">{children}</main>
    </div>
  );
}
