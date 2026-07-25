import type { Itinerary } from "../../types/itinerary";

export type PlaceSourceKind = "live" | "curated";

export interface PlaceSourceStatusInfo {
  kind: PlaceSourceKind;
  label: string;
  tooltip?: string;
}

export const CURATED_PLACE_SOURCE_TOOLTIP =
  "Live map verification was not available for this request.";

export function hasScheduledActivities(itinerary: Itinerary): boolean {
  return (itinerary.days ?? []).some((day) => (day.activities?.length ?? 0) > 0);
}

/** Small trip-panel label for how scheduled places were sourced. */
export function resolvePlaceSourceStatus(
  itinerary: Itinerary,
): PlaceSourceStatusInfo | null {
  const metadata = itinerary.metadata ?? {};
  const liveCount = Number(metadata.live_poi_count ?? 0);
  const curatedCount = Number(metadata.curated_poi_count ?? 0);
  const liveLookup = metadata.live_poi_lookup;

  if (liveLookup === true || liveCount > 0) {
    return { kind: "live", label: "Live map data" };
  }

  if (curatedCount > 0 || (liveLookup === false && hasScheduledActivities(itinerary))) {
    return {
      kind: "curated",
      label: "Curated recommendations",
      tooltip: CURATED_PLACE_SOURCE_TOOLTIP,
    };
  }

  return null;
}

/** Prominent warning only when neither live nor curated grounding is available. */
export function needsGroundingWarning(itinerary: Itinerary): boolean {
  if (resolvePlaceSourceStatus(itinerary)) {
    return false;
  }
  const metadata = itinerary.metadata ?? {};
  const userNote = String(metadata.user_note ?? "").trim();
  return Boolean(userNote) || !hasScheduledActivities(itinerary);
}

export function groundingWarningMessage(itinerary: Itinerary): string {
  const metadata = itinerary.metadata ?? {};
  const userNote = String(metadata.user_note ?? "").trim();
  if (userNote) {
    return userNote;
  }
  return "This itinerary could not be verified with live map data or curated recommendations.";
}

export interface PlaceSourceStatusProps {
  status: PlaceSourceStatusInfo;
  testId?: string;
}

export function PlaceSourceStatus({
  status,
  testId = "place-source-status",
}: PlaceSourceStatusProps) {
  const hintId = `${testId}-hint`;

  return (
    <p
      className="place-source-status"
      data-testid={testId}
      data-kind={status.kind}
      role="note"
      aria-describedby={status.tooltip ? hintId : undefined}
    >
      <span className="place-source-status__label">Place source:</span>{" "}
      <span className="place-source-status__value">{status.label}</span>
      {status.tooltip ? (
        <span className="place-source-status__hint" id={hintId}>
          {status.tooltip}
        </span>
      ) : null}
    </p>
  );
}
