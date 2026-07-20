import type { Citation, Itinerary } from "../../../types/itinerary";

export const emptyCitationsItinerary: Itinerary = {
  city: "jaipur",
  total_days: 1,
  days: [{ day_number: 1, activities: [], travel_segments: [] }],
  citations: [],
};

export const multipleCitationsItinerary: Itinerary = {
  city: "jaipur",
  total_days: 1,
  citations: [
    {
      citation_id: "jaipur:wikivoyage#see#0001",
      source_url: "https://en.wikivoyage.org/wiki/Jaipur",
      section: "See",
      document_id: "jaipur:wikivoyage",
      metadata: { label: "Wikivoyage — Jaipur" },
    },
    {
      citation_id: "jaipur:wikipedia#tourism#0016",
      source_url: "https://en.wikipedia.org/wiki/Jaipur",
      section: "Tourism",
      document_id: "jaipur:wikipedia",
      metadata: { source: "wikipedia", short_label: "Wikipedia tourism" },
    },
  ],
  days: [
    {
      day_number: 1,
      activities: [
        {
          id: "a1",
          title: "City Palace",
          citations: [
            {
              citation_id: "osm:node/123",
              source_url: "https://www.openstreetmap.org/node/123",
              metadata: { source: "osm", label: "OSM node/123" },
            },
          ],
        },
      ],
      travel_segments: [],
    },
  ],
};

/** Same citation_id appears at itinerary and activity level — should render once. */
export const duplicateCitationsItinerary: Itinerary = {
  city: "jaipur",
  total_days: 1,
  citations: [
    {
      citation_id: "jaipur:wikivoyage#see#0001",
      source_url: "https://en.wikivoyage.org/wiki/Jaipur",
      section: "See",
      metadata: { label: "Top-level copy" },
    },
  ],
  days: [
    {
      day_number: 1,
      activities: [
        {
          id: "a1",
          title: "City Palace",
          citations: [
            {
              citation_id: "jaipur:wikivoyage#see#0001",
              source_url: "https://en.wikivoyage.org/wiki/Jaipur",
              section: "See (activity)",
              metadata: { label: "Activity copy — should be dropped" },
            },
            {
              citation_id: "jaipur:wikipedia#history#0003",
              section: "History",
            },
          ],
        },
      ],
      travel_segments: [],
    },
  ],
};

export const sparseCitation: Citation = {
  citation_id: "jaipur:wikivoyage#eat#0009",
};

export const sparseCitationsItinerary: Itinerary = {
  city: "jaipur",
  total_days: 1,
  citations: [sparseCitation],
};
