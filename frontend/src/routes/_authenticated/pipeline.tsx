import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiUrl, evidenceQuery, runsQuery, type Evidence } from "@/lib/api";
import { DataOriginChip, EmptyState } from "@/components/sg/chips";

export const Route = createFileRoute("/_authenticated/pipeline")({
  head: () => ({
    meta: [
      { title: "Pipeline & Evidence — SiteGuard" },
      { name: "description", content: "PipeGen pipeline IR, TensorRT speed report and FP32/FP16/INT8 edge optimization results." },
      { property: "og:title", content: "Pipeline & Evidence — SiteGuard" },
      { property: "og:description", content: "Pipeline IR, TensorRT speed report and precision trade-offs." },
    ],
  }),
  component: PipelinePage,
});

const ORDER = { FP32: 0, FP16: 1, INT8: 2 } as const;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel p-4">
      <h2 className="label-caps mb-3">{title}</h2>
      {children}
    </section>
  );
}

function Shot({ items, label }: { items: Evidence[] | undefined; label: string }) {
  if (!items?.length) return <EmptyState title={`No ${label} uploaded yet`}>Awaiting real capture from PipeGen. See docs/evidence/README.md.</EmptyState>;
  return (
    <div className="grid gap-3">
      {items.map((e) => (
        <figure key={e.id}>
          <img src={e.url.startsWith("http") ? e.url : apiUrl(e.url)} alt={e.caption ?? label} className="w-full rounded-sm border" />
          {e.caption && <figcaption className="mt-1 text-sm text-muted-foreground">{e.caption}</figcaption>}
        </figure>
      ))}
    </div>
  );
}

function PipelinePage() {
  const runs = useQuery(runsQuery());
  const ir = useQuery(evidenceQuery("ir_graph"));
  const trt = useQuery(evidenceQuery("trt_report"));
  const data = [...(runs.data ?? [])].sort((a, b) => ORDER[a.precision] - ORDER[b.precision]);
  const base = data.find((r) => r.precision === "FP32") ?? data[0];
  const chart = data.map((r) => ({
    name: `${r.precision}`,
    fps: +r.fps.toFixed(1),
    delta: base?.accuracy_map != null && r.accuracy_map != null ? `${((r.accuracy_map - base.accuracy_map) * 100).toFixed(1)} mAP` : "",
  }));

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">Pipeline & Evidence</h1>

      <Section title="Pipeline summary">
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["Inputs", "cam0 · RTSP / file source"],
            ["Tasks", "Detection · tracking · zone & PPE rules"],
            ["Models", data.length ? [...new Set(data.map((r) => r.model_name))].join(", ") : "—"],
            ["Precision", data.length ? data.map((r) => r.precision).join(" / ") : "—"],
            ["Outputs", "Annotated RTSP · MQTT events · incidents API"],
          ].map(([k, v]) => (
            <div key={k} className="border-l-2 border-primary pl-3">
              <dt className="label-caps">{k}</dt>
              <dd className="mt-1 font-mono text-sm">{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Pipeline IR graph"><Shot items={ir.data} label="IR graph screenshot" /></Section>
        <Section title="TensorRT speed report"><Shot items={trt.data} label="TensorRT report screenshot" /></Section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Speed report by precision">
          {data.length ? (
            <table className="w-full font-mono text-base">
              <thead>
                <tr className="border-b text-left">
                  {["Model", "Prec.", "Origin", "FPS", "Latency", "Power", "mAP"].map((h) => <th key={h} className="label-caps py-2">{h}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.map((r) => (
                  <tr key={r.id}>
                    <td className="py-2">{r.model_name}</td>
                    <td className="py-2 font-bold text-primary">{r.precision}</td>
                    <td className="py-2"><DataOriginChip origin={r.data_origin} /></td>
                    <td className="py-2">{r.fps.toFixed(1)}</td>
                    <td className="py-2">{r.latency_ms.toFixed(1)} ms</td>
                    <td className="py-2">{r.power_w != null ? `${r.power_w.toFixed(1)} W` : "—"}</td>
                    <td className="py-2">{r.accuracy_map != null ? r.accuracy_map.toFixed(3) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title={runs.isError ? "Backend unreachable" : "No PipeGen speed report imported yet"}>
              <p>To display verified benchmarks, export PipeGen's speed report into <code className="font-mono text-foreground">captured/</code> and run:</p>
              <code className="mt-2 block rounded bg-background p-2 font-mono text-xs">
                python scripts/import_speed_report.py captured/speed_report.csv
              </code>
            </EmptyState>
          )}
        </Section>
        <Section title="Edge optimization · FPS by precision">
          <div className="h-64">
            {chart.length ? (
              <ResponsiveContainer>
                <BarChart data={chart} margin={{ top: 24 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fill: "var(--muted-foreground)" }} />
                  <YAxis tick={{ fill: "var(--muted-foreground)" }} width={40} />
                  <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)" }} cursor={{ fill: "var(--accent)" }} />
                  <Bar dataKey="fps" fill="var(--primary)">
                    <LabelList dataKey="delta" position="top" fill="var(--muted-foreground)" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="Awaiting real benchmark import" />
            )}
          </div>
        </Section>
      </div>

      <Section title="Run it yourself">
        <pre className="overflow-x-auto rounded-sm bg-background p-4 font-mono text-sm">{`# Run the PipeGen-generated pipeline
cd captured/export && ./run.sh --source cam0 --precision INT8

# Subscribe to real-time events
mosquitto_sub -t '#' -v`}</pre>
      </Section>
    </div>
  );
}

