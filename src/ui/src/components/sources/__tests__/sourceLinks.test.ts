import { describe, expect, it } from "vitest";

import type { Itinerary } from "../../../types/itinerary";
import {
  collectSourceLinks,
  resolveWellKnownSourceUrl,
  splitSourcesFooter,
} from "../sourceLinks";

describe("sourceLinks", () => {
  it("maps friendly labels to public URLs", () => {
    expect(resolveWellKnownSourceUrl("Wikivoyage", "Jaipur")).toBe(
      "https://en.wikivoyage.org/wiki/Jaipur",
    );
    expect(resolveWellKnownSourceUrl("Rajasthan Tourism", "Jaipur")).toContain(
      "tourism.rajasthan.gov.in",
    );
    expect(resolveWellKnownSourceUrl("OpenStreetMap", "Jaipur")).toBe(
      "https://www.openstreetmap.org/",
    );
  });

  it("collects clickable links from itinerary citations", () => {
    const itinerary: Itinerary = {
      city: "Jaipur",
      total_days: 1,
      metadata: { live_poi_lookup: true },
      citations: [
        {
          citation_id: "guide:wikivoyage-jaipur",
          source_url: "https://en.wikivoyage.org/wiki/Jaipur",
          metadata: { label: "Wikivoyage" },
        },
      ],
      days: [],
    };
    const links = collectSourceLinks(itinerary);
    expect(links.some((l) => l.label === "Wikivoyage" && l.href?.includes("wikivoyage"))).toBe(
      true,
    );
    expect(links.some((l) => l.label === "OpenStreetMap")).toBe(true);
  });

  it("splits assistant Sources footer from body text", () => {
    const { body, hasSourcesFooter } = splitSourcesFooter(
      "Your plan is ready.\n\nSources: OpenStreetMap; Wikivoyage.",
    );
    expect(body).toBe("Your plan is ready.");
    expect(hasSourcesFooter).toBe(true);
  });
});
