import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { apiUrl, type Incident } from "./api";

export type StreamState = "connecting" | "live" | "reconnecting";

interface LiveCtx {
  state: StreamState;
  lastMessageAt: number | null;
  criticals: Incident[];
  dismissCritical: (id: number) => void;
  freshIds: Set<number>;
  muted: boolean;
  setMuted: (m: boolean) => void;
}

const Ctx = createContext<LiveCtx | null>(null);

function beep() {
  try {
    const ac = new AudioContext();
    const o = ac.createOscillator();
    o.frequency.value = 880;
    o.connect(ac.destination);
    o.start();
    o.stop(ac.currentTime + 0.25);
  } catch {
    /* ignore */
  }
}

export function LiveStreamProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamState>("connecting");
  const [lastMessageAt, setLast] = useState<number | null>(null);
  const [criticals, setCriticals] = useState<Incident[]>([]);
  const [freshIds, setFresh] = useState<Set<number>>(new Set());
  const [muted, setMuted] = useState(true);
  const mutedRef = useRef(muted);
  mutedRef.current = muted;

  useEffect(() => {
    let es: EventSource | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let wasLive = false;
    let closed = false;

    const upsert = (inc: Incident, prepend: boolean) => {
      qc.setQueryData<Incident[]>(["incidents"], (old) => {
        const list = old ?? [];
        const idx = list.findIndex((x) => x.id === inc.id);
        if (idx >= 0) return list.map((x) => (x.id === inc.id ? { ...x, ...inc } : x));
        return prepend ? [inc, ...list] : [...list, inc];
      });
    };

    const connect = () => {
      if (closed) return;
      es = new EventSource(apiUrl("/api/stream"));
      es.onopen = () => {
        setState("live");
        if (poll) clearInterval(poll), (poll = null);
        if (wasLive) qc.invalidateQueries();
        wasLive = true;
      };
      es.onerror = () => {
        setState("reconnecting");
        es?.close();
        if (!poll) poll = setInterval(() => qc.invalidateQueries(), 5000);
        retry = setTimeout(connect, 3000);
      };
      const touch = () => setLast(Date.now());
      es.addEventListener("incident.opened", (e) => {
        touch();
        const inc = JSON.parse((e as MessageEvent).data) as Incident;
        upsert(inc, true);
        qc.invalidateQueries({ queryKey: ["stats"] });
        setFresh((s) => new Set(s).add(inc.id));
        setTimeout(() => setFresh((s) => { const n = new Set(s); n.delete(inc.id); return n; }), 1500);
        if (inc.severity === "CRITICAL") {
          setCriticals((c) => [inc, ...c.filter((x) => x.id !== inc.id)]);
          if (!mutedRef.current) beep();
        }
      });
      es.addEventListener("incident.updated", (e) => {
        touch();
        upsert(JSON.parse((e as MessageEvent).data) as Incident, false);
      });
      es.addEventListener("incident.closed", (e) => {
        touch();
        upsert(JSON.parse((e as MessageEvent).data) as Incident, false);
        qc.invalidateQueries({ queryKey: ["stats"] });
      });
      es.addEventListener("heartbeat", touch);
      es.onmessage = touch;
    };
    connect();
    return () => {
      closed = true;
      es?.close();
      if (poll) clearInterval(poll);
      if (retry) clearTimeout(retry);
    };
  }, [qc]);

  return (
    <Ctx.Provider
      value={{
        state,
        lastMessageAt,
        criticals,
        dismissCritical: (id) => setCriticals((c) => c.filter((x) => x.id !== id)),
        freshIds,
        muted,
        setMuted,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useLive() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useLive outside provider");
  return c;
}
