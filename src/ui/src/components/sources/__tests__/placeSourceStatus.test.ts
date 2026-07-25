import { describe, expect, it } from "vitest";

import type { Itinerary } from "../../../types/itinerary";
import {
  CURATED_PLACE_SOURCE_TOOLTIP,
  groundingWarningMessage,
  needsGroundingWarning,
  resolvePlaceSourceStatus,
} from "../placeSourceStatus";

const curatedItinerary: Itinerary = {
  city: "Jaipur",
  total_days: 2,
  metadata: {
    live_poi_lookup: false,
    live_poi_count: 0,
    curated_poi_count: 4,
    user_note:
      "Live map verification is temporarily limited. Some suggestions are from the curated fallback catalogue.",
  },
  poi_registry: [
    {
      poi_id: "well_known/jaipur-city-palace",
      name: "City Palace",
      latitude: 26.9,
      longitude: 75.8,
      source: "well_known",
    },
  ],
  days: [
    {
      day_number: 1,
      activities: [{ id: "d1-a1", title: "City Palace", poi_id: "well_known/jaipur-city-palace" }],
      travel_segments: [],
    },
  ],
};

const liveItinerary: Itinerary = {
  city: "Jaipur",
  total_days: 1,
  metadata: { live_poi_lookup: true, live_poi_count: 5, curated_poi_count: 0 },
  days: [
    {
      day_number: 1,
      activities: [{ id: "d1-a1", title: "City Palace", poi_id: "node/1" }],
      travel_segments: [],
    },
  ],
};

const groundingFailureItinerary: Itinerary = {
  city: "Jaipur",
  total_days: 2,
  metadata: {
    live_poi_lookup: false,
    live_poi_count: 0,
    curated_poi_count: 0,
    user_note:
      "Live map verification is temporarily limited. Some suggestions are from the curated fallback catalogue.",
  },
  days: [],
};

describe("placeSourceStatus", () => {
  it("labels live lookups as live map data", () => {
    expect(resolvePlaceSourceStatus(liveItinerary)).toEqual({
      kind: "live",
      label: "Live map data",
    });
  });

  it("labels curated fallback as curated recommendations with tooltip", () => {
    expect(resolvePlaceSourceStatus(curatedItinerary)).toEqual({
      kind: "curated",
      label: "Curated recommendations",
      tooltip: CURATED_PLACE_SOURCE_TOOLTIP,
    });
  });

  it("does not treat curated POIs as live", () => {
    const status = resolvePlaceSourceStatus(curatedItinerary);
    expect(status?.kind).toBe("curated");
    expect(status?.kind).not.toBe("live");
    expect(curatedItinerary.poi_registry?.[0]?.source).toBe("well_known");
  });

  it("flags complete grounding failure for prominent warning", () => {
    expect(needsGroundingWarning(curatedItinerary)).toBe(false);
    expect(needsGroundingWarning(liveItinerary)).toBe(false);
    expect(needsGroundingWarning(groundingFailureItinerary)).toBe(true);
    expect(groundingWarningMessage(groundingFailureItinerary)).toContain(
      "temporarily limited",
    );
  });
});
