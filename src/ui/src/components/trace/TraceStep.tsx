import type { TraceItem, TraceStepStatus } from "../../types/trace";

export interface TraceStepProps {
  item: TraceItem;
  index: number;
  isLast: boolean;
}

const STATUS_LABEL: Record<TraceStepStatus, string> = {
  started: "started",
  completed: "completed",
  failed: "failed",
};

function formatDuration(ms: number | null | undefined): string | null {
  if (ms === null || ms === undefined) {
    return null;
  }
  if (ms < 1000) {
    return `${ms}ms`;
  }
  const seconds = ms / 1000;
  return Number.isInteger(seconds) ? `${seconds}s` : `${seconds.toFixed(1)}s`;
}

export function TraceStep({ item, index, isLast }: TraceStepProps) {
  const duration = formatDuration(item.duration_ms ?? null);
  const status = item.status;
  const timestamp = item.timestamp?.trim() || null;
  const correlationId = item.correlation_id?.trim() || null;

  return (
    <li
      className={[
        "trace-step",
        `trace-step--${status}`,
        isLast ? "trace-step--last" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      data-testid="trace-step"
      data-agent={item.agent}
      data-status={status}
      data-index={index}
    >
      <div className="trace-step__rail" aria-hidden="true">
        <span className="trace-step__dot" />
        {!isLast ? <span className="trace-step__connector" /> : null}
      </div>

      <div className="trace-step__body">
        <div className="trace-step__header">
          <h3 className="trace-step__agent" data-testid="trace-agent">
            {item.agent}
          </h3>
          <span
            className={`trace-step__badge trace-step__badge--${status}`}
            data-testid="trace-status"
          >
            {STATUS_LABEL[status]}
          </span>
        </div>

        <p className="trace-step__action" data-testid="trace-action">
          {item.action}
        </p>

        <div className="trace-step__meta">
          {duration ? (
            <span className="trace-step__duration" data-testid="trace-duration">
              {duration}
            </span>
          ) : null}
          {timestamp ? (
            <time
              className="trace-step__timestamp"
              data-testid="trace-timestamp"
              dateTime={timestamp}
            >
              {timestamp}
            </time>
          ) : null}
          {correlationId ? (
            <span
              className="trace-step__correlation"
              data-testid="trace-correlation"
            >
              {correlationId}
            </span>
          ) : null}
        </div>
      </div>
    </li>
  );
}
