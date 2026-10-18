import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { apiUrl, incidentEventsQuery, incidentsQuery } from "@/lib/api";
import { TYPE_LABEL, clock, incidentDuration } from "@/lib/format";
import { useIncidentStatus } from "@/lib/mutations";
import { DataOriginChip, SeverityChip, StatusChip } from "./chips";

export function IncidentDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { data: list } = useQuery(incidentsQuery());
  const inc = list?.find((i) => i.id === id) ?? null;
  const events = useQuery({ ...incidentEventsQuery(id ?? 0), enabled: id != null });
  const m = useIncidentStatus();

  return (
    <Sheet open={id != null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {inc ? (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-3 text-2xl">
                <span className="font-mono text-muted-foreground">#{inc.id}</span> {TYPE_LABEL[inc.type]}
              </SheetTitle>
              <SheetDescription className="flex items-center gap-2">
                <SeverityChip severity={inc.severity} />
                <StatusChip status={inc.status} />
                <DataOriginChip origin={inc.data_origin} />
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-5 px-4 pb-6">
              {inc.snapshot_path ? (
                <img src={apiUrl(inc.snapshot_path)} alt={`Snapshot for incident ${inc.id}`} className="w-full rounded-sm border" />
              ) : (
                <div className="panel p-6 text-center text-sm text-muted-foreground">No snapshot recorded</div>
              )}
              <dl className="grid grid-cols-2 gap-3 font-mono text-sm">
                {[
                  ["Origin", inc.data_origin?.toUpperCase() ?? "UNKNOWN"],
                  ["Zone", inc.zone_id ?? "—"],
                  ["Track", inc.track_id != null ? `#${inc.track_id}` : "—"],
                  ["Source", inc.source_id],
                  ["Events", inc.event_count],
                  ["Max conf.", `${(inc.max_confidence * 100).toFixed(1)}%`],
                  ["Duration", incidentDuration(inc)],
                  ["First seen", clock(inc.first_seen)],
                  ["Last seen", clock(inc.last_seen)],
                ].map(([k, v]) => (
                  <div key={k as string} className="panel p-2">
                    <dt className="label-caps">{k}</dt>
                    <dd className="text-base">{v}</dd>
                  </div>
                ))}
              </dl>
              <div>
                <p className="label-caps mb-2">Event confidence timeline</p>
                <div className="panel h-36 p-2">
                  {events.data?.length ? (
                    <ResponsiveContainer>
                      <BarChart data={events.data.map((e) => ({ t: clock(e.ts), c: +(e.confidence * 100).toFixed(1) }))}>
                        <XAxis dataKey="t" hide />
                        <YAxis domain={[0, 100]} width={30} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
                        <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)" }} />
                        <Bar dataKey="c" fill="var(--primary)" />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="p-4 text-center text-sm text-muted-foreground">{events.isError ? "Events unavailable" : "No events"}</p>
                  )}
                </div>
              </div>
              <div className="flex gap-3">
                <Button
                  className="flex-1"
                  variant="secondary"
                  disabled={inc.status !== "OPEN"}
                  onClick={() => m.mutate({ id: inc.id, status: "ACKNOWLEDGED" })}
                >
                  Acknowledge
                </Button>
                <Button
                  className="flex-1"
                  disabled={inc.status === "RESOLVED"}
                  onClick={() => m.mutate({ id: inc.id, status: "RESOLVED" })}
                >
                  Resolve
                </Button>
              </div>
            </div>
          </>
        ) : (
          <SheetHeader>
            <SheetTitle>Incident not found</SheetTitle>
          </SheetHeader>
        )}
      </SheetContent>
    </Sheet>
  );
}
