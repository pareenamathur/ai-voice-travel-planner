import type { Itinerary } from "../../types/itinerary";

/** Minimal empty itinerary (schema-valid shape, no invented activities). */
export const emptyItinerary: Itinerary = {
  city: "jaipur",
  total_days: 2,
  days: [],
};

/** Single day with two activities and one travel segment. */
export const oneDayItinerary: Itinerary = {
  city: "jaipur",
  total_days: 1,
  start_date: "2026-04-01",
  metadata: { live_poi_lookup: true },
  citations: [
    {
      citation_id: "map:openstreetmap",
      source_url: "https://www.openstreetmap.org/",
      section: "Live map places",
      document_id: "openstreetmap",
      metadata: { source: "OpenStreetMap", label: "OpenStreetMap" },
    },
  ],
  days: [
    {
      day_number: 1,
      date: "2026-04-01",
      notes: "Arrival day",
      activities: [
        {
          id: "d1-a1",
          title: "City Palace",
          category: "culture",
          start_time: "10:00",
          end_time: "12:00",
          duration_minutes: 120,
          notes: "Buy combo ticket",
        },
        {
          id: "d1-a2",
          title: "Lunch near Hawa Mahal",
          category: "food",
          start_time: "12:30",
          end_time: "13:30",
          duration_minutes: 60,
        },
      ],
      travel_segments: [
        {
          from_activity_id: "d1-a1",
          to_activity_id: "d1-a2",
          travel_minutes: 15,
          transport_mode: "walk",
          notes: "Short walk through old city",
        },
      ],
    },
  ],
};

/** Multi-day fixture with intentionally out-of-order activity times for sort tests. */
export const multiDayItinerary: Itinerary = {
  city: "jaipur",
  total_days: 3,
  start_date: "2026-04-01",
  days: [
    {
      day_number: 2,
      date: "2026-04-02",
      activities: [
        {
          id: "d2-a2",
          title: "Amber Fort",
          category: "sightseeing",
          start_time: "14:00",
          end_time: "17:00",
          duration_minutes: 180,
        },
        {
          id: "d2-a1",
          title: "Morning market",
          category: "shopping",
          start_time: "09:00",
          end_time: "10:30",
          duration_minutes: 90,
        },
      ],
      travel_segments: [
        {
          from_activity_id: "d2-a1",
          to_activity_id: "d2-a2",
          travel_minutes: 40,
          transport_mode: "drive",
        },
      ],
    },
    {
      day_number: 1,
      date: "2026-04-01",
      notes: "Light day",
      activities: [
        {
          id: "d1-only",
          title: "Jantar Mantar",
          start_time: "11:00",
          end_time: "12:00",
          duration_minutes: 60,
          category: "culture",
        },
      ],
      travel_segments: [],
    },
    {
      day_number: 3,
      activities: [],
      travel_segments: [],
    },
  ],
};

/** Activities with many optional fields omitted. */
export const sparseOptionalFieldsItinerary: Itinerary = {
  city: "Jaipur",
  total_days: 1,
  days: [
    {
      day_number: 1,
      activities: [
        {
          id: "sparse-1",
          title: "Open evening stroll",
        },
      ],
      travel_segments: [],
    },
  ],
};

/**
 * Fixture aligned with ``tests/shared/test_itinerary_schema.py`` SAMPLE_ITINERARY
 * for schema-compatibility checks in the UI layer.
 */
export const schemaCompatibleItinerary: Itinerary = {
  city: "jaipur",
  total_days: 2,
  start_date: "2026-04-01",
  traveler_constraints: {
    interests: ["culture", "food"],
    pace: "relaxed",
    party_size: 2,
    daily_window_start: "09:00",
    daily_window_end: "21:00",
  },
  poi_registry: [
    {
      poi_id: "node/123",
      name: "City Palace",
      latitude: 26.9855,
      longitude: 75.8513,
      category: "culture",
      source: "osm",
    },
  ],
  citations: [
    {
      citation_id: "jaipur:wikivoyage#see#0001",
      source_url: "https://en.wikivoyage.org/wiki/Jaipur",
      section: "See",
    },
  ],
  days: [
    {
      day_number: 1,
      date: "2026-04-01",
      notes: "Arrival day",
      activities: [
        {
          id: "d1-a1",
          title: "City Palace",
          poi_id: "node/123",
          category: "culture",
          latitude: 26.9855,
          longitude: 75.8513,
          start_time: "10:00",
          end_time: "12:00",
          duration_minutes: 120,
          notes: "Buy combo ticket",
          citations: [
            {
              citation_id: "jaipur:wikivoyage#see#0001",
              source_url: "https://en.wikivoyage.org/wiki/Jaipur",
              section: "See",
            },
          ],
        },
        {
          id: "d1-a2",
          title: "Lunch near Hawa Mahal",
          category: "food",
          start_time: "12:30",
          end_time: "13:30",
          duration_minutes: 60,
        },
      ],
      travel_segments: [
        {
          from_activity_id: "d1-a1",
          to_activity_id: "d1-a2",
          travel_minutes: 15,
          transport_mode: "walk",
          notes: "Short walk through old city",
        },
      ],
    },
    {
      day_number: 2,
      date: "2026-04-02",
      activities: [],
      travel_segments: [],
    },
  ],
  metadata: { schema_version: "1.0" },
};
