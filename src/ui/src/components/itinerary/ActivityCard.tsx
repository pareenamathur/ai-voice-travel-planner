import type { Activity } from "../../types/itinerary";
import { formatDurationMinutes } from "./ordering";

export interface ActivityCardProps {
  activity: Activity;
}

function periodLabel(activity: Activity): string | null {
  const notes = (activity.notes || "").toLowerCase();
  if (notes.includes("lunch")) return "Lunch";
  if (notes.includes("dinner")) return "Dinner";
  if (notes.includes("tea")) return "Tea / Break";
  if (notes.includes("night") || notes.includes("return") || notes.includes("hotel")) {
    return "Night";
  }
  if (notes.includes("morning") && !notes.includes("late")) return "Morning";
  if (notes.includes("afternoon")) return "Afternoon";
  if (notes.includes("evening")) return "Evening";

  if (!activity.start_time) return null;
  const hour = Number.parseInt(activity.start_time.slice(0, 2), 10);
  if (Number.isNaN(hour)) return null;
  if (hour < 12) return "Morning";
  if (hour < 14) return "Late Morning";
  if (hour < 17) return "Afternoon";
  if (hour < 19) return "Evening";
  return "Night";
}

export function ActivityCard({ activity }: ActivityCardProps) {
  const duration = formatDurationMinutes(activity.duration_minutes ?? null);
  const hasTime = Boolean(activity.start_time || activity.end_time);
  const period = periodLabel(activity);

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

      {activity.notes && !_isPeriodOnlyNote(activity.notes) ? (
        <p className="activity-card__notes" data-testid="activity-notes">
          {activity.notes}
        </p>
      ) : null}
    </article>
  );
}

function _isPeriodOnlyNote(notes: string): boolean {
  const normalized = notes.trim().toLowerCase();
  return [
    "morning",
    "late morning",
    "late morning / midday",
    "afternoon",
    "early evening",
    "evening",
    "lunch",
    "dinner",
    "tea break",
    "night — return / hotel",
  ].includes(normalized);
}
