import type { TravelSegment } from "../../types/itinerary";
import { formatDurationMinutes, formatTransportMode } from "./ordering";

export interface TravelSegmentViewProps {
  segment: TravelSegment;
}

export function TravelSegmentView({ segment }: TravelSegmentViewProps) {
  const travelTime = formatDurationMinutes(segment.travel_minutes) ?? "0 min";
  const mode = formatTransportMode(segment.transport_mode);

  return (
    <div
      className="travel-segment"
      data-testid="travel-segment"
      data-from={segment.from_activity_id}
      data-to={segment.to_activity_id}
      aria-label={`${travelTime} ${mode}`}
    >
      <span className="travel-segment__arrow" aria-hidden="true">
        ↓
      </span>
      <span className="travel-segment__time" data-testid="travel-minutes">
        {travelTime}
      </span>
      <span className="travel-segment__mode" data-testid="transport-mode">
        {mode}
      </span>
      {segment.notes ? (
        <span className="travel-segment__notes" data-testid="travel-notes">
          {segment.notes}
        </span>
      ) : null}
    </div>
  );
}
