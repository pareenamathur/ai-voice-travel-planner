/** UI types for the Companion Agent Trace Panel (props-only). */

export type TraceStepStatus = "started" | "completed" | "failed";

/**
 * One ordered event in an agent/tool trace, similar to Observability spans.
 * Field names are UI-facing; callers map backend spans into this shape.
 */
export interface TraceItem {
  /** Agent or tool name (e.g. Supervisor, Planning, search_pois). */
  agent: string;
  /** What the step did (e.g. delegate, tool_call, review). */
  action: string;
  status: TraceStepStatus;
  /** ISO-8601 or display timestamp. */
  timestamp?: string | null;
  correlation_id?: string | null;
  duration_ms?: number | null;
  /** Optional stable key when the same agent appears multiple times. */
  id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface TracePanelProps {
  /** Ordered trace events (chronological). */
  items?: TraceItem[];
  /** Optional panel title override. */
  title?: string;
}
