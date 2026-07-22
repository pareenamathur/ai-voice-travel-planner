import type { Citation, Itinerary } from "../../types/itinerary";

import { collectCitations, deriveCitationLabel, deriveCitationSource } from "./collectCitations";

export interface SourceLink {
  label: string;
  href?: string;
}

function wikiSlug(city: string): string {
  return city.trim().replace(/\s+/g, "_");
}

/** Known public URLs when citations omit ``source_url``. */
export function resolveWellKnownSourceUrl(label: string, city: string): string | undefined {
  const key = label.toLowerCase();
  const cityTitle = city.trim() || "Jaipur";
  const slug = wikiSlug(cityTitle);

  if (key.includes("wikivoyage")) {
    return `https://en.wikivoyage.org/wiki/${slug}`;
  }
  if (key.includes("wikipedia")) {
    return `https://en.wikipedia.org/wiki/${slug}`;
  }
  if (key.includes("rajasthan tourism")) {
    return "https://www.tourism.rajasthan.gov.in/";
  }
  if (key.includes("openstreetmap")) {
    return "https://www.openstreetmap.org/";
  }
  if (key.endsWith(" tourism") || key.includes(" tourism")) {
    if (cityTitle.toLowerCase() === "jaipur") {
      return "https://www.tourism.rajasthan.gov.in/jaipur";
    }
    return `https://en.wikivoyage.org/wiki/${slug}`;
  }
  return undefined;
}

function citationUrl(citation: Citation, city: string): string | undefined {
  const direct = citation.source_url?.trim();
  if (direct) {
    return direct;
  }
  const label =
    deriveCitationLabel(citation) ||
    deriveCitationSource(citation) ||
    citation.section?.trim() ||
    "";
  if (!label) {
    return undefined;
  }
  return resolveWellKnownSourceUrl(label, city);
}

function citationLabel(citation: Citation): string {
  return (
    deriveCitationLabel(citation) ||
    deriveCitationSource(citation) ||
    citation.section?.trim() ||
    "Travel guidance"
  );
}

/** User-facing source list with optional hrefs — never exposes internal IDs. */
export function collectSourceLinks(itinerary: Itinerary): SourceLink[] {
  const city = itinerary.city ?? "";
  const seen = new Set<string>();
  const links: SourceLink[] = [];

  const push = (label: string, href?: string) => {
    const key = label.toLowerCase();
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    links.push({ label, href: href || resolveWellKnownSourceUrl(label, city) });
  };

  const metadata = itinerary.metadata ?? {};
  if (metadata.live_poi_lookup === true) {
    push("OpenStreetMap", "https://www.openstreetmap.org/");
  } else if (metadata.live_poi_lookup === false) {
    push("Trusted travel guidance");
  }

  for (const citation of collectCitations(itinerary)) {
    const label = citationLabel(citation);
    push(label, citationUrl(citation, city));
  }

  if (links.length === 0 && city) {
    push(`${city} Tourism`, resolveWellKnownSourceUrl(`${city} Tourism`, city));
  }

  return links;
}

/** Split assistant prose from a trailing "Sources:" footer. */
export function splitSourcesFooter(text: string): {
  body: string;
  hasSourcesFooter: boolean;
} {
  const marker = /\n\s*Sources:\s*/i;
  const match = marker.exec(text);
  if (!match || match.index === undefined) {
    return { body: text, hasSourcesFooter: false };
  }
  return {
    body: text.slice(0, match.index).trimEnd(),
    hasSourcesFooter: true,
  };
}
