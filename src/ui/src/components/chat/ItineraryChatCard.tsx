import type { Itinerary } from "../../types/itinerary";
import { DayCard } from "../itinerary/DayCard";
import "./chat.css";

export interface ItineraryChatCardProps {
  itinerary: Itinerary;
  approved: boolean;
}

function titleCase(value: string): string {
  if (!value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/**
 * Itinerary embedded in the chat thread — timeline cards with glass styling.
 */
export function ItineraryChatCard({ itinerary, approved }: ItineraryChatCardProps) {
  const days = [...(itinerary.days ?? [])].sort((a, b) => a.day_number - b.day_number);

  return (
    <article
      className="itinerary-chat-card glass-card"
      data-testid="itinerary-chat-card"
      aria-label={`Trip plan for ${itinerary.city}`}
    >
      <header className="itinerary-chat-card__header">
        <div className="itinerary-chat-card__badge" aria-hidden="true">
          <span className="material-symbols-outlined">map</span>
        </div>
        <div>
          <h3 className="itinerary-chat-card__title">
            {approved
              ? `${titleCase(itinerary.city)} · ${itinerary.total_days}-day journey`
              : `Draft · ${titleCase(itinerary.city)}`}
          </h3>
          <p className="itinerary-chat-card__meta">
            {itinerary.total_days} {itinerary.total_days === 1 ? "day" : "days"}
            {itinerary.traveler_constraints?.pace
              ? ` · ${titleCase(String(itinerary.traveler_constraints.pace))} pace`
              : null}
          </p>
        </div>
      </header>

      {!approved ? (
        <p
          className="itinerary-approval-banner itinerary-chat-card__banner"
          data-testid="itinerary-approval-banner"
          role="status"
        >
          This plan needs a quick quality review before export or edits. You can still
          explore the draft below.
        </p>
      ) : null}

      {days.length === 0 ? (
        <p className="itinerary-chat-card__empty">No activities scheduled yet.</p>
      ) : (
        <div className="itinerary-chat-card__timeline">
          {days.map((day) => (
            <DayCard key={day.day_number} day={day} />
          ))}
        </div>
      )}
    </article>
  );
}
