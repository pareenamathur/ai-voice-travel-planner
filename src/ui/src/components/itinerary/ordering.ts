import type { Activity, DayPlan, TravelSegment } from "../../types/itinerary";

/** Sort activities chronologically by ``start_time`` (HH:MM); missing times last. */
export function sortActivitiesChronologically(activities: Activity[]): Activity[] {
  return [...activities].sort((a, b) => {
    const aTime = a.start_time ?? null;
    const bTime = b.start_time ?? null;
    if (aTime === null && bTime === null) {
      return 0;
    }
    if (aTime === null) {
      return 1;
    }
    if (bTime === null) {
      return -1;
    }
    return aTime.localeCompare(bTime);
  });
}

export function findTravelSegment(
  segments: TravelSegment[],
  fromActivityId: string,
  toActivityId: string,
): TravelSegment | undefined {
  return segments.find(
    (segment) =>
      segment.from_activity_id === fromActivityId &&
      segment.to_activity_id === toActivityId,
  );
}

export function formatDurationMinutes(minutes: number | null | undefined): string | null {
  if (minutes === null || minutes === undefined) {
    return null;
  }
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (remainder === 0) {
    return `${hours}h`;
  }
  return `${hours}h ${remainder} min`;
}

export function formatTransportMode(mode: string | null | undefined): string {
  if (!mode) {
    return "walk";
  }
  return mode.replaceAll("_", " ");
}

export function getDayActivities(day: DayPlan): Activity[] {
  return day.activities ?? [];
}

export function getDayTravelSegments(day: DayPlan): TravelSegment[] {
  return day.travel_segments ?? [];
}
