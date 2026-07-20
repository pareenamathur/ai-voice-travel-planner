import type { EvalResult } from "./types";
import {
  formatVerdictLabel,
  resolveEvalStatus,
  resolveExplanation,
  statusCssClass,
} from "./normalize";

export interface EvalCardProps {
  evaluation: EvalResult;
}

export function EvalCard({ evaluation }: EvalCardProps) {
  const status = resolveEvalStatus(evaluation);
  const css = statusCssClass(status);
  const explanation = resolveExplanation(evaluation);
  const timestamp = evaluation.timestamp?.trim() || null;
  const hasScore = evaluation.score !== null && evaluation.score !== undefined;
  const name = evaluation.name?.trim() || "Unknown evaluation";

  return (
    <article
      className={`eval-card eval-card--${css}`}
      data-testid="eval-card"
      data-eval-name={name}
      data-eval-status={status}
    >
      <header className="eval-card__header">
        <h3 className="eval-card__name" data-testid="eval-name">
          {name}
        </h3>
        <span
          className={`eval-card__badge eval-card__badge--${css}`}
          data-testid="eval-status"
        >
          {formatVerdictLabel(status)}
        </span>
      </header>

      {hasScore ? (
        <p className="eval-card__score" data-testid="eval-score">
          Score: {evaluation.score}
        </p>
      ) : null}

      {explanation ? (
        <p className="eval-card__message" data-testid="eval-message">
          {explanation}
        </p>
      ) : null}

      {timestamp ? (
        <time
          className="eval-card__timestamp"
          data-testid="eval-timestamp"
          dateTime={timestamp}
        >
          {timestamp}
        </time>
      ) : null}
    </article>
  );
}
