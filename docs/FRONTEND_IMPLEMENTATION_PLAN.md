# SiteGuard — Frontend Implementation Plan

**Purpose:** a live safety-operations dashboard that makes the PipeGen pipeline's output *actionable for a person*, which is the Track A mandatory "Actionable Output" requirement. It also doubles as the judge-facing **evidence page** (Pipeline IR, TensorRT speed report, FP16 vs INT8 trade-off).

The frontend shows nothing the PipeGen pipeline did not produce. No mock data in the demo.

---

## 1. Tech stack

- **React 18 + TypeScript + Vite**
- **Tailwind CSS** (utility styling, dark mode via `prefers-color-scheme` + manual toggle)
- **TanStack Query** (REST caching/refetch)
- **Native `EventSource`** wrapped in a `useLiveStream` hook (SSE)
- **Recharts** (time series, bar charts)
- **React Router** (4 routes)
- **lucide-react** icons
- **Vitest + React Testing Library** (a few smoke tests only)

## 2. Information architecture

```
/                  Live Monitor  (default, the demo screen)
/incidents         Incident log + detail drawer
/pipeline          Pipeline & Evidence (judges' page)
/settings          Connection status, thresholds (read-only), about
```

## 3. Screens

### 3.1 Live Monitor (`/`)
Single-screen layout designed to be readable on a projector.

```
┌──────────────────────────────────────────────────────────────┐
│ Header: SiteGuard · cam0 · ● Live (SSE) · Broker ✓ · FPS 78  │
├──────────────────────────────┬───────────────────────────────┤
│                              │ KPI row: Open | Today | High  │
│  Video panel                 │ Incidents by type (bar)       │
│  (annotated PipeGen output)  ├───────────────────────────────┤
│  + zone legend               │ Live incident feed            │
│                              │ (newest first, animated)      │
├──────────────────────────────┴───────────────────────────────┤
│ Timeline chart: violations per minute (last 60 min)          │
└──────────────────────────────────────────────────────────────┘
```

- **Video panel:** plays the PipeGen annotated output. Priority order:
  1. HLS/WebRTC URL if the RTSP output is bridged (see `INTEGRATION.md`, MediaMTX).
  2. Otherwise `<video src="/media/video" loop muted autoplay>`.
  3. Otherwise a clear empty state: "Open the PipeGen live window on the demo machine."
- **Live feed:** each row shows severity chip, type, zone, track ID, time-ago, confidence. New items slide in and flash briefly. Rows are clickable (opens the detail drawer).
- **Critical banner:** a full-width red banner appears on any `CRITICAL` incident until acknowledged. Optional audio beep with a mute toggle.
- **KPI cards:** Open incidents, Total today, High/Critical count, Mean time to acknowledge.

### 3.2 Incidents (`/incidents`)
- Table: ID, type, severity, zone, track, first seen, duration, status, actions.
- Filters: status, type, severity, time window. Sort by last seen.
- **Detail drawer:** snapshot or video timestamp link, event count, max confidence, mini timeline of its events, buttons **Acknowledge** and **Resolve** (`PATCH /api/incidents/{id}`).
- Export **CSV** of the filtered list (client-side).

### 3.3 Pipeline & Evidence (`/pipeline`)
This page maps directly onto the judging rubric.

| Section | Content | Source |
|---|---|---|
| Pipeline summary | Inputs, tasks, models, precision, outputs (the exact text for the submission form) | static markdown + `/api/pipeline/runs` |
| **Pipeline IR graph** | Screenshot of PipeGen's node graph | `/api/evidence?kind=ir_graph` |
| **TensorRT speed report** | Screenshot + table: FPS, latency, power, accuracy per precision | `/api/pipeline/runs` |
| **Edge Optimization** (bonus) | Bar chart FP32 vs FP16 vs INT8 (FPS) with accuracy delta annotation | `/api/pipeline/runs` |
| Run it yourself | The `run.sh` command and MQTT topic | static |

### 3.4 Settings (`/settings`)
Read-only: backend URL, MQTT status, last message age, dropped count, active thresholds. A "Copy diagnostics" button helps debugging during the demo.

## 4. Component inventory

```
src/
├── main.tsx / App.tsx / routes.tsx
├── api/
│   ├── client.ts            # fetch wrapper, base URL from VITE_API_URL
│   ├── types.ts             # Incident, EventDTO, PipelineRun, Evidence, Stats
│   └── hooks.ts             # useIncidents, useStats, useTimeseries, usePipelineRuns...
├── hooks/
│   └── useLiveStream.ts     # EventSource, reconnect, dispatches to query cache
├── components/
│   ├── layout/ Header.tsx, ConnectionBadge.tsx, Shell.tsx
│   ├── live/ VideoPanel.tsx, LiveFeed.tsx, KpiCards.tsx, TypeBar.tsx,
│   │         TimelineChart.tsx, CriticalBanner.tsx
│   ├── incidents/ IncidentTable.tsx, IncidentDrawer.tsx, Filters.tsx
│   ├── pipeline/ PrecisionTable.tsx, PrecisionChart.tsx, EvidenceGallery.tsx
│   └── ui/ SeverityChip.tsx, StatusChip.tsx, EmptyState.tsx, Skeleton.tsx
├── lib/ format.ts (time-ago, durations), severity.ts, csv.ts
└── styles/ index.css (Tailwind layers + CSS variables)
```

## 5. State and data flow

1. On load: TanStack Query fetches `/api/incidents`, `/api/stats/summary`, `/api/stats/timeseries`.
2. `useLiveStream` opens `EventSource('/api/stream')`.
3. SSE handlers **update the query cache directly**:
   - `incident.opened` → prepend to the incidents list, increment KPIs, trigger the banner if `CRITICAL`
   - `incident.updated` → patch the row in place
   - `incident.closed` → update status
4. On SSE reconnect: invalidate all queries (the backend is the source of truth).
5. Acknowledge/Resolve use optimistic updates with rollback on error.

No global state library is needed.

## 6. Types (mirror the backend)

```ts
type Severity = 'MEDIUM' | 'HIGH' | 'CRITICAL';
type Status = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
type IncidentType = 'ZONE_INTRUSION' | 'PPE_VIOLATION' | 'LOITERING';

interface Incident {
  id: number; type: IncidentType; severity: Severity; status: Status;
  source_id: string; track_id: number | null; zone_id: string | null;
  first_seen: string; last_seen: string; event_count: number;
  max_confidence: number; snapshot_path: string | null;
}
interface PipelineRun {
  id: number; model_name: string; precision: 'FP32' | 'FP16' | 'INT8';
  fps: number; latency_ms: number; power_w: number | null; accuracy_map: number | null;
}
```

## 7. Design direction

- **Tone:** industrial control-room. Dark default, high contrast, restrained palette.
- **Severity colours:** Medium = amber, High = orange-red, Critical = red (always paired with text and icon, never colour alone).
- **Typography:** a clean sans for UI, a monospace for IDs, timestamps and numbers.
- **Motion:** only meaningful motion (new incident slide-in, critical banner pulse); respect `prefers-reduced-motion`.
- **Large type for the projector:** KPI numbers 40px+, feed rows 16px+.
- **Responsive:** desktop first, but the layout stacks cleanly to one column at <1024px (phones are used by some judges).
- **Accessibility:** keyboard-focusable rows, `aria-live="polite"` on the feed, contrast ≥ 4.5:1.

## 8. Error and empty states (these matter in a live demo)

| State | UI |
|---|---|
| Backend unreachable | Top banner "Backend offline, retrying", retries every 3s |
| SSE disconnected | Badge turns amber "Reconnecting", falls back to 5s polling |
| Broker down | Badge red "MQTT disconnected" with hint |
| No incidents yet | "Watching… no violations detected" with live FPS/last message age |
| No video available | Instruction card pointing to PipeGen live window |

## 9. Build order

| # | Task | Est. |
|---|---|---|
| F1 | Vite + Tailwind scaffold, router, shell, API client and types | 25 min |
| F2 | Incidents list + SeverityChip + table | 30 min |
| F3 | `useLiveStream` + live feed + KPI cards (needs backend B5–B6) | 40 min |
| F4 | Video panel + timeline chart + type bar | 35 min |
| F5 | Incident drawer + acknowledge/resolve | 30 min |
| F6 | Pipeline & Evidence page (static first, then wire to real runs) | 35 min |
| F7 | Critical banner, empty/error states, dark/light polish | 25 min |
| F8 | README screenshots + smoke tests | 15 min |

**Parallelisation:** F1–F2 can start against the backend skeleton immediately, using the dev-only replay script. F3 onward needs real PipeGen output.

**Cut order:** drop audio beep, CSV export, light theme, then the type bar chart.

## 10. Environment

```
VITE_API_URL=http://localhost:8000
VITE_VIDEO_URL=/media/video          # or an HLS URL from MediaMTX
```

Dev: `npm run dev` (port 5173). Production demo: `npm run build`, then serve `dist/` from FastAPI (`StaticFiles`) so the demo needs only one process.

## 13. Definition of done

- [ ] Open the page and a real violation from the PipeGen pipeline appears in the feed within ~1 s with no refresh
- [ ] Critical banner fires and acknowledging it works
- [ ] `/pipeline` shows the real IR screenshot and real FP16/INT8 numbers
- [ ] Readable from 3 m on a projector
- [ ] Recovers cleanly after backend restart

---

## 14. Local run notes (single CUDA machine)

- The browser, Vite dev server and PipeGen's DeepStream display window share the same GPU/desktop. Close heavy tabs and disable video-heavy extensions during the final run so GPU memory is left to PipeGen.
- If you also want the optional GPU card on the Live Monitor, add a small `GpuCard` component polling `GET /api/system/gpu` every 2 s (utilisation, memory, power). It is a nice proof of "running on CUDA locally" for judges.
- For the demo, prefer `npm run build` and serve `dist/` from FastAPI. It uses less CPU than the Vite dev server and means one fewer process to start.
- Vite's dev server proxies to the backend: set `server.proxy['/api'] = 'http://localhost:8000'` and the same for `/media` to avoid CORS problems.
