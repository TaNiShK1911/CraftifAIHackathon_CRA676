import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { apiUrl, evidenceQuery, runsQuery, type Evidence } from "@/lib/api";
import { DataOriginChip, EmptyState } from "@/components/sg/chips";

export const Route = createFileRoute("/_authenticated/pipeline")({
  head: () => ({
    meta: [
      { title: "Pipeline & Evidence — SiteGuard" },
      { name: "description", content: "PipeGen pipeline IR, TensorRT speed report and FP32 edge execution results (INT8 not run)." },
      { property: "og:title", content: "Pipeline & Evidence — SiteGuard" },
      { property: "og:description", content: "Pipeline IR, TensorRT speed report and precision details." },
    ],
  }),
  component: PipelinePage,
});

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
  // Only display real imported benchmark runs, never synthetic seed runs
  const data = [...(runs.data ?? [])].filter((r) => r.data_origin !== "seed");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Pipeline & Evidence</h1>
        <DataOriginChip origin="live" />
      </div>

      <Section title="Pipeline summary">
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["Inputs", "demo.mp4 · 2560x1440 · 395 frames"],
            ["Tasks", "Person detection · Hungarian tracking · hazard zone & PPE alerts"],
            ["Models", data.length ? [...new Set(data.map((r) => r.model_name))].join(", ") : "yolo11s, best (PPE)"],
            ["Precision", "FP32 (both models) · INT8 not run"],
            ["Outputs", "MQTT pipegen/detection/demo (395 msgs) · metadata.json"],
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
        <Section title="Speed report by model (FP32 TensorRT)">
          {data.length ? (
            <div className="space-y-2">
              <div className="flex justify-end">
                <DataOriginChip origin="live" />
              </div>
              <table className="w-full font-mono text-base">
                <thead>
                  <tr className="border-b text-left">
                    {["Model", "Prec.", "Origin", "FPS", "Latency", "Power", "Accuracy"].map((h) => <th key={h} className="label-caps py-2">{h}</th>)}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.map((r) => (
                    <tr key={r.id}>
                      <td className="py-2 font-semibold">{r.model_name}</td>
                      <td className="py-2 font-bold text-primary">{r.precision}</td>
                      <td className="py-2"><DataOriginChip origin={r.data_origin} /></td>
                      <td className="py-2">{r.fps.toFixed(1)}</td>
                      <td className="py-2">{r.latency_ms.toFixed(1)} ms</td>
                      <td className="py-2">{r.power_w != null ? `${r.power_w.toFixed(1)} W` : "—"}</td>
                      <td className="py-2 text-muted-foreground">{r.accuracy_map != null ? r.accuracy_map.toFixed(3) : "Not reported"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title={runs.isError ? "Backend unreachable" : "No PipeGen speed report imported yet"}>
              <p>To display verified benchmarks, export PipeGen's speed report into <code className="font-mono text-foreground">captured/</code> and run:</p>
              <code className="mt-2 block rounded bg-background p-2 font-mono text-xs">
                python scripts/import_speed_report.py captured/speed_report.csv
              </code>
            </EmptyState>
          )}
        </Section>
        <Section title="Edge optimization (INT8)">
          <div className="flex h-64 flex-col items-center justify-center rounded-sm border border-dashed border-border p-6 text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-sev-medium/40 bg-sev-medium/10 px-3 py-1 font-mono text-xs font-semibold text-sev-medium">
              <span className="size-2 rounded-full bg-sev-medium" />
              INT8 not run
            </div>
            <h3 className="mt-3 font-semibold">No INT8 Engine Compiled</h3>
            <p className="mt-2 max-w-md font-mono text-xs text-muted-foreground">
              Both models were compiled and profiled on-device using FP32 precision (<code className="text-foreground">yolo11s</code> @ 30.75 FPS, <code className="text-foreground">best</code> PPE @ 66.2 FPS).
              INT8 calibration was not executed in this PipeGen session, and FP16 was not run.
              Edge Optimization bonus is not claimed.
            </p>
          </div>
        </Section>
      </div>

      <Section title="Run it yourself">
        <pre className="overflow-x-auto rounded-sm bg-background p-4 font-mono text-sm">{`# Run the PipeGen-generated pipeline on target device
cd captured/export && ./run.sh --input demo.mp4

# Subscribe to real-time events published by DeepStream
mosquitto_sub -t 'pipegen/detection/demo' -v`}</pre>
      </Section>
    </div>
  );
}

