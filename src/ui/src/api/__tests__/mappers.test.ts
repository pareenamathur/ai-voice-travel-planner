import { describe, expect, it } from "vitest";

import { asItinerary, evalReportFromVerdict } from "../mapSession";
import { spansToTraceItems } from "../mapTrace";

describe("asItinerary", () => {
  it("returns null for missing or invalid payloads", () => {
    expect(asItinerary(null)).toBeNull();
    expect(asItinerary({})).toBeNull();
    expect(asItinerary({ city: "Jaipur" })).toBeNull();
  });

  it("accepts a minimal valid itinerary", () => {
    const itinerary = asItinerary({ city: "Jaipur", total_days: 2, days: [] });
    expect(itinerary?.city).toBe("Jaipur");
    expect(itinerary?.total_days).toBe(2);
  });
});

describe("evalReportFromVerdict", () => {
  it("returns null when verdict is absent", () => {
    expect(evalReportFromVerdict(null)).toBeNull();
  });

  it("maps review_verdict.eval_report entries", () => {
    const report = evalReportFromVerdict({
      status: "pass",
      eval_report: {
        entries: [{ name: "Feasibility", passed: true, reasons: [] }],
      },
    });
    expect(report?.overall_verdict).toBe("pass");
    expect(report?.entries).toHaveLength(1);
  });
});

describe("spansToTraceItems", () => {
  it("maps observability spans into TraceItem fields", () => {
    const items = spansToTraceItems([
      {
        agent: "supervisor",
        event: "receive_message",
        correlation_id: "c1",
        timestamp: "2026-04-01T10:00:00Z",
      },
      {
        agent: "mcp_gateway",
        event: "tool_call_start",
        tool: "search_pois",
        correlation_id: "c1",
      },
    ]);
    expect(items).toHaveLength(2);
    expect(items[0].agent).toBe("supervisor");
    expect(items[0].action).toBe("receive_message");
    expect(items[1].agent).toBe("search_pois");
    expect(items[1].action).toContain("tool_call_start");
  });
});
