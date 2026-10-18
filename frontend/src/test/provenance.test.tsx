import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataOriginChip } from "@/components/sg/chips";
import { incidentsQuery } from "@/lib/api";

describe("DataOrigin provenance UI", () => {
  it("renders LIVE badge for live data origin", () => {
    render(<DataOriginChip origin="live" />);
    const badge = screen.getByText("LIVE");
    expect(badge).toBeDefined();
    expect(badge.className).toContain("text-ok");
  });

  it("renders REPLAY badge for replayed telemetry", () => {
    render(<DataOriginChip origin="replay" />);
    const badge = screen.getByText("REPLAY");
    expect(badge).toBeDefined();
    expect(badge.className).toContain("text-sev-medium");
  });

  it("renders SYNTHETIC badge for seeded demo data", () => {
    render(<DataOriginChip origin="seed" />);
    const badge = screen.getByText("SYNTHETIC");
    expect(badge).toBeDefined();
    expect(badge.className).toContain("text-muted-foreground");
  });

  it("defaults to SYNTHETIC badge if origin is missing", () => {
    render(<DataOriginChip origin={undefined} />);
    const badge = screen.getByText("SYNTHETIC");
    expect(badge).toBeDefined();
  });

  it("configures incidentsQuery with optional data_origin filter", () => {
    const allQuery = incidentsQuery();
    expect(allQuery.queryKey).toEqual(["incidents", "all"]);

    const liveQuery = incidentsQuery("live");
    expect(liveQuery.queryKey).toEqual(["incidents", "live"]);

    const seedQuery = incidentsQuery("seed");
    expect(seedQuery.queryKey).toEqual(["incidents", "seed"]);
  });
});
