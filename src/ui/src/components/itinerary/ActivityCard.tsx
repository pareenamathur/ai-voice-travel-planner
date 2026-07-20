import type { Activity } from "../../types/itinerary";
import { formatDurationMinutes } from "./ordering";

export interface ActivityCardProps {
  activity: Activity;
}

function periodLabel(startTime?: string | null): string | null {
  if (!startTime) return null;
  const hour = Number.parseInt(startTime.slice(0, 2), 10);
  if (Number.isNaN(hour)) return null;
  if (hour < 12) return "Morning Activity";
  if (hour < 17) return "Afternoon Activity";
  return "Evening Experience";
}

export function ActivityCard({ activity }: ActivityCardProps) {
  const duration = formatDurationMinutes(activity.duration_minutes ?? null);
  const hasTime = Boolean(activity.start_time || activity.end_time);
  const period = periodLabel(activity.start_time);

  return (
    <article
      className="activity-card"
      data-testid="activity-card"
      data-activity-id={activity.id}
    >
      {period ? <p className="activity-card__period">{period}</p> : null}

      <h4 className="activity-card__title">{activity.title}</h4>

      {hasTime ? (
        <p className="activity-card__time" data-testid="activity-time">
          <span className="material-symbols-outlined" aria-hidden="true">
            schedule
          </span>
          {activity.start_time ?? "—"}
          {" – "}
          {activity.end_time ?? "—"}
        </p>
      ) : null}

      {duration ? (
        <p className="activity-card__duration" data-testid="activity-duration">
          Duration: {duration}
        </p>
      ) : null}

      {activity.category ? (
        <p className="activity-card__category" data-testid="activity-category">
          {String(activity.category)}
        </p>
      ) : null}

      {activity.notes ? (
        <p className="activity-card__notes" data-testid="activity-notes">
          {activity.notes}
        </p>
      ) : null}
    </article>
  );
}
