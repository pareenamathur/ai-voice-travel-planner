import type { EvalStatusPanelProps } from "./types";
import { EvalCard } from "./EvalCard";
import {
  buildSummary,
  collectEvaluations,
  formatVerdictLabel,
  statusCssClass,
} from "./normalize";
import "./evals.css";

/**
 * Evaluation Status Panel — displays Review ``EvalReport`` / ``ReviewVerdict`` data.
 */
export function EvalStatusPanel({
  report = null,
  title = "Evaluation status",
  itineraryApproved = null,
}: EvalStatusPanelProps) {
  const evaluations = collectEvaluations(report);
  const summary = buildSummary(evaluations, report);
  const overallClass =
    summary.overallVerdict === "UNKNOWN"
      ? "unknown"
      : statusCssClass(summary.overallVerdict);
  const regenAttempted = Boolean(report?.regen_attempted);
  const showApprovalWarning =
    evaluations.length > 0 && itineraryApproved === false;

  return (
    <section
      className="eval-status-panel"
      data-testid="eval-status-panel"
      aria-label={title}
    >
      <header className="eval-status-panel__header">
        <h2 className="eval-status-panel__title">{title}</h2>
      </header>

      {evaluations.length === 0 ? (
        <p className="eval-status-panel__empty" data-testid="eval-empty">
          No evaluations yet.
        </p>
      ) : (
        <>
          {regenAttempted ? (
            <p
              className="eval-status-panel__regen"
              data-testid="eval-regen-indicator"
              role="status"
            >
              This itinerary was regenerated once by Review. The results below
              are the final review outcome.
            </p>
          ) : null}

          {showApprovalWarning ? (
            <p
              className="eval-status-panel__approval-warning"
              data-testid="eval-approval-warning"
              role="alert"
            >
              This itinerary did not pass all quality checks and is not approved.
              You can still inspect the draft below; export and further edits stay
              blocked until a passing review.
            </p>
          ) : null}

          <div
            className={`eval-summary eval-summary--${overallClass}`}
            data-testid="eval-summary"
          >
            <p className="eval-summary__verdict" data-testid="eval-overall-verdict">
              Overall: {formatVerdictLabel(summary.overallVerdict)}
            </p>
            <ul className="eval-summary__counts" data-testid="eval-summary-counts">
              <li data-testid="eval-count-total">Total: {summary.total}</li>
              <li data-testid="eval-count-passed">Passed: {summary.passed}</li>
              <li data-testid="eval-count-failed">Failed: {summary.failed}</li>
              <li data-testid="eval-count-warnings">Warnings: {summary.warnings}</li>
            </ul>
            {report?.timestamp ? (
              <time
                className="eval-summary__timestamp"
                data-testid="eval-report-timestamp"
                dateTime={report.timestamp}
              >
                {report.timestamp}
              </time>
            ) : null}
          </div>

          <ul className="eval-status-panel__list" data-testid="eval-list">
            {evaluations.map((evaluation, index) => (
              <li
                key={`${evaluation.name}-${index}`}
                className="eval-status-panel__item"
              >
                <EvalCard evaluation={evaluation} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
