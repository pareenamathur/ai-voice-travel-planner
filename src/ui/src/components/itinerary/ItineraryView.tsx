import type { Itinerary } from "../../types/itinerary";
import { DayCard } from "./DayCard";
import "./itinerary.css";

export interface ItineraryViewProps {
  /** Canonical itinerary from Supervisor, or null/undefined before one exists. */
  itinerary?: Itinerary | null;
}

/**
 * Renders the canonical Itinerary schema as day/activity cards.
 * Props-only — no API, Supervisor, or Session Manager calls.
 */
export function ItineraryView({ itinerary }: ItineraryViewProps) {
  if (!itinerary) {
    return (
      <section
        className="itinerary-view"
        data-testid="itinerary-view"
        aria-label="Itinerary"
      >
        <header className="itinerary-view__header">
          <h2 className="itinerary-view__city" data-testid="itinerary-city">
            Itinerary
          </h2>
        </header>
        <p className="itinerary-view__empty" data-testid="itinerary-empty">
          No activities scheduled.
        </p>
      </section>
    );
  }

  const days = [...(itinerary.days ?? [])].sort(
    (a, b) => a.day_number - b.day_number,
  );

  return (
    <section
      className="itinerary-view"
      data-testid="itinerary-view"
      aria-label={`Itinerary for ${itinerary.city}`}
    >
      <header className="itinerary-view__header">
        <div className="itinerary-view__header-main">
          <h2 className="itinerary-view__city" data-testid="itinerary-city">
            {itinerary.city}
          </h2>
          <p className="itinerary-view__days" data-testid="itinerary-total-days">
            {itinerary.total_days} {itinerary.total_days === 1 ? "day" : "days"}
          </p>
        </div>
      </header>

      {days.length === 0 ? (
        <p className="itinerary-view__empty" data-testid="itinerary-empty">
          No activities scheduled.
        </p>
      ) : (
        <div className="itinerary-view__days-list" data-testid="itinerary-days">
          {days.map((day) => (
            <DayCard key={day.day_number} day={day} />
          ))}
        </div>
      )}
    </section>
  );
}
