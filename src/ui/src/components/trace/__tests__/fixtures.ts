import type { TraceItem } from "../../../types/trace";

export const emptyTrace: TraceItem[] = [];

/** Happy-path Planning flow in chronological order. */
export const successfulWorkflow: TraceItem[] = [
  {
    id: "1",
    agent: "Supervisor",
    action: "intent=PLAN",
    status: "completed",
    timestamp: "2026-04-01T10:00:00.000Z",
    correlation_id: "turn-abc123",
    duration_ms: 12,
  },
  {
    id: "2",
    agent: "Planning",
    action: "build draft itinerary",
    status: "completed",
    timestamp: "2026-04-01T10:00:01.000Z",
    correlation_id: "turn-abc123",
    duration_ms: 820,
  },
  {
    id: "3",
    agent: "Gateway",
    action: "route tools",
    status: "completed",
    timestamp: "2026-04-01T10:00:02.000Z",
    correlation_id: "turn-abc123",
    duration_ms: 5,
  },
  {
    id: "4",
    agent: "search_pois",
    action: "tool_call",
    status: "completed",
    timestamp: "2026-04-01T10:00:03.000Z",
    correlation_id: "turn-abc123",
    duration_ms: 820,
  },
  {
    id: "5",
    agent: "build_itinerary",
    action: "tool_call",
    status: "completed",
    timestamp: "2026-04-01T10:00:04.000Z",
    correlation_id: "turn-abc123",
    duration_ms: 340,
  },
  {
    id: "6",
    agent: "Review",
    action: "feasibility + grounding",
    status: "completed",
    timestamp: "2026-04-01T10:00:05.000Z",
    correlation_id: "turn-abc123",
    duration_ms: 110,
  },
  {
    id: "7",
    agent: "Supervisor",
    action: "present plan to user",
    status: "completed",
    timestamp: "2026-04-01T10:00:06.000Z",
    correlation_id: "turn-abc123",
    duration_ms: 8,
  },
];

/** Same flow with a failed Review step. */
export const failedWorkflow: TraceItem[] = [
  {
    agent: "Supervisor",
    action: "intent=PLAN",
    status: "completed",
    timestamp: "2026-04-01T11:00:00.000Z",
    correlation_id: "turn-fail1",
  },
  {
    agent: "Planning",
    action: "build draft itinerary",
    status: "completed",
    timestamp: "2026-04-01T11:00:01.000Z",
    correlation_id: "turn-fail1",
  },
  {
    agent: "Review",
    action: "feasibility check",
    status: "failed",
    timestamp: "2026-04-01T11:00:02.000Z",
    correlation_id: "turn-fail1",
    duration_ms: 90,
  },
];

/** Out-of-order timestamps — panel should render chronologically. */
export const shuffledTimestamps: TraceItem[] = [
  {
    agent: "Review",
    action: "evaluate",
    status: "completed",
    timestamp: "2026-04-01T12:00:02.000Z",
    correlation_id: "turn-sort",
  },
  {
    agent: "Supervisor",
    action: "start",
    status: "completed",
    timestamp: "2026-04-01T12:00:00.000Z",
    correlation_id: "turn-sort",
  },
  {
    agent: "Planning",
    action: "draft",
    status: "completed",
    timestamp: "2026-04-01T12:00:01.000Z",
    correlation_id: "turn-sort",
  },
];

export const sparseItems: TraceItem[] = [
  {
    agent: "Gateway",
    action: "search_pois",
    status: "started",
  },
];

/** Duplicate correlation IDs across steps — all should still render. */
export const duplicateCorrelationIds: TraceItem[] = [
  {
    id: "a",
    agent: "Supervisor",
    action: "first",
    status: "completed",
    correlation_id: "same-id",
    timestamp: "2026-04-01T13:00:00.000Z",
  },
  {
    id: "b",
    agent: "Planning",
    action: "second",
    status: "completed",
    correlation_id: "same-id",
    timestamp: "2026-04-01T13:00:01.000Z",
  },
  {
    id: "c",
    agent: "Supervisor",
    action: "third",
    status: "completed",
    correlation_id: "same-id",
    timestamp: "2026-04-01T13:00:02.000Z",
  },
];
