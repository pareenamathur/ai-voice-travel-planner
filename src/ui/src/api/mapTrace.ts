import type { TraceItem, TraceStepStatus } from "../types/trace";

/** Map Observability span dicts from GET /api/session/{id}/trace into TraceItem[]. */
export function spansToTraceItems(
  spans: Array<Record<string, unknown>>,
): TraceItem[] {
  return spans.map((span, index) => {
    const agent =
      (typeof span.tool === "string" && span.tool) ||
      (typeof span.agent === "string" && span.agent) ||
      "unknown";

    const event = typeof span.event === "string" ? span.event : "event";
    const tool = typeof span.tool === "string" ? span.tool : null;
    const action = tool && !String(agent).includes(tool) ? `${event} (${tool})` : event;

    const status = deriveStatus(span, event);
    const timestamp =
      typeof span.timestamp === "string" ? span.timestamp : null;
    const correlationId =
      typeof span.correlation_id === "string" ? span.correlation_id : null;

    let durationMs: number | null = null;
    if (typeof span.duration_ms === "number") {
      durationMs = span.duration_ms;
    }

    return {
      id: typeof span.id === "string" ? span.id : `span-${index}`,
      agent,
      action,
      status,
      timestamp,
      correlation_id: correlationId,
      duration_ms: durationMs,
      metadata: span,
    };
  });
}

function deriveStatus(
  span: Record<string, unknown>,
  event: string,
): TraceStepStatus {
  const explicit = span.status;
  if (explicit === "failed" || explicit === "completed" || explicit === "started") {
    return explicit;
  }
  const lowered = event.toLowerCase();
  if (lowered.includes("fail") || lowered.includes("error") || lowered.includes("denied")) {
    return "failed";
  }
  if (lowered.includes("start")) {
    return "started";
  }
  return "completed";
}
