import type { TraceItem, TracePanelProps } from "../../types/trace";
import { TraceStep } from "./TraceStep";
import "./trace.css";

function sortChronologically(items: TraceItem[]): TraceItem[] {
  return [...items].sort((a, b) => {
    const aTs = a.timestamp?.trim() || "";
    const bTs = b.timestamp?.trim() || "";
    if (aTs && bTs) {
      const cmp = aTs.localeCompare(bTs);
      if (cmp !== 0) {
        return cmp;
      }
    } else if (aTs && !bTs) {
      return -1;
    } else if (!aTs && bTs) {
      return 1;
    }
    // Stable fallback: preserve relative order via original index in metadata if set.
    const aIdx = typeof a.metadata?.order === "number" ? a.metadata.order : 0;
    const bIdx = typeof b.metadata?.order === "number" ? b.metadata.order : 0;
    return aIdx - bIdx;
  });
}

/**
 * Agent Trace Panel — vertical timeline of Observability-like spans.
 * Props-only; does not call Supervisor or Observability APIs.
 */
export function TracePanel({
  items = [],
  title = "Agent trace",
}: TracePanelProps) {
  // Preserve caller order when timestamps are absent; otherwise sort by timestamp.
  const hasAnyTimestamp = items.some((item) => Boolean(item.timestamp?.trim()));
  const ordered = hasAnyTimestamp
    ? sortChronologically(
        items.map((item, index) => ({
          ...item,
          metadata: { ...item.metadata, order: index },
        })),
      )
    : items;

  return (
    <section
      className="trace-panel"
      data-testid="trace-panel"
      aria-label={title}
    >
      <header className="trace-panel__header">
        <h2 className="trace-panel__title">{title}</h2>
        <p className="trace-panel__count" data-testid="trace-count">
          {ordered.length} {ordered.length === 1 ? "step" : "steps"}
        </p>
      </header>

      {ordered.length === 0 ? (
        <p className="trace-panel__empty" data-testid="trace-empty">
          No trace events yet.
        </p>
      ) : (
        <ol className="trace-panel__timeline" data-testid="trace-timeline">
          {ordered.map((item, index) => (
            <TraceStep
              key={item.id ?? `${item.agent}-${item.action}-${index}-${item.correlation_id ?? ""}`}
              item={item}
              index={index}
              isLast={index === ordered.length - 1}
            />
          ))}
        </ol>
      )}
    </section>
  );
}
