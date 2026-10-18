import { AlertOctagon, AlertTriangle, CheckCircle2, CircleDot, Eye, Info } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Severity, Status } from "@/lib/api";

const SEV: Record<Severity, { cls: string; Icon: typeof Info }> = {
  MEDIUM: { cls: "text-sev-medium border-sev-medium/50 bg-sev-medium/10", Icon: Info },
  HIGH: { cls: "text-sev-high border-sev-high/50 bg-sev-high/10", Icon: AlertTriangle },
  CRITICAL: { cls: "text-sev-critical border-sev-critical/60 bg-sev-critical/15", Icon: AlertOctagon },
};

export function SeverityChip({ severity }: { severity: Severity }) {
  const { cls, Icon } = SEV[severity];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 font-mono text-xs font-bold", cls)}>
      <Icon className="size-3.5" aria-hidden /> {severity}
    </span>
  );
}

const ST: Record<Status, { cls: string; Icon: typeof Info }> = {
  OPEN: { cls: "text-sev-high", Icon: CircleDot },
  ACKNOWLEDGED: { cls: "text-chart-4", Icon: Eye },
  RESOLVED: { cls: "text-ok", Icon: CheckCircle2 },
};

export function StatusChip({ status }: { status: Status }) {
  const { cls, Icon } = ST[status];
  return (
    <span className={cn("inline-flex items-center gap-1 font-mono text-xs font-semibold", cls)}>
      <Icon className="size-3.5" aria-hidden /> {status}
    </span>
  );
}

const ORIGIN_CONFIG: Record<string, { label: string; cls: string; title: string }> = {
  live: {
    label: "LIVE",
    cls: "text-ok border-ok/50 bg-ok/10",
    title: "Real-time edge perception stream",
  },
  replay: {
    label: "REPLAY",
    cls: "text-sev-medium border-sev-medium/50 bg-sev-medium/10",
    title: "Replayed telemetry capture (development)",
  },
  seed: {
    label: "SYNTHETIC",
    cls: "text-muted-foreground border-border bg-accent/40",
    title: "Synthetic seed demo data",
  },
};

export function DataOriginChip({ origin }: { origin?: string }) {
  const cfg = (origin && ORIGIN_CONFIG[origin]) || ORIGIN_CONFIG.seed;
  return (
    <span
      title={cfg.title}
      className={cn(
        "inline-flex items-center rounded-sm border px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-wider uppercase",
        cfg.cls,
      )}
    >
      {cfg.label}
    </span>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 p-8 text-center">
      {icon && <div className="text-muted-foreground">{icon}</div>}
      <p className="text-lg font-semibold">{title}</p>
      {children && <div className="max-w-sm text-sm text-muted-foreground">{children}</div>}
    </div>
  );
}

