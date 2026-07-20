import type { DayPlan } from "../../types/itinerary";
import { ActivityCard } from "./ActivityCard";
import { TravelSegmentView } from "./TravelSegmentView";
import {
  findTravelSegment,
  getDayActivities,
  getDayTravelSegments,
  sortActivitiesChronologically,
} from "./ordering";

export interface DayCardProps {
  day: DayPlan;
}

export function DayCard({ day }: DayCardProps) {
  const activities = sortActivitiesChronologically(getDayActivities(day));
  const segments = getDayTravelSegments(day);

  return (
    <section
      className="day-card"
      data-testid="day-card"
      data-day-number={day.day_number}
      aria-label={`Day ${day.day_number}`}
    >
      <header className="day-card__header">
        <h3 className="day-card__title">Day {day.day_number}</h3>
        {day.date ? (
          <p className="day-card__date" data-testid="day-date">
            {day.date}
          </p>
        ) : null}
        {day.notes ? (
          <p className="day-card__notes" data-testid="day-notes">
            {day.notes}
          </p>
        ) : null}
      </header>

      {activities.length === 0 ? (
        <p className="day-card__empty" data-testid="day-empty">
          No activities scheduled.
        </p>
      ) : (
        <ol className="day-card__timeline" data-testid="day-timeline">
          {activities.map((activity, index) => {
            const next = activities[index + 1];
            const travel =
              next !== undefined
                ? findTravelSegment(segments, activity.id, next.id)
                : undefined;

            return (
              <li key={activity.id} className="day-card__item">
                <ActivityCard activity={activity} />
                {travel ? <TravelSegmentView segment={travel} /> : null}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
