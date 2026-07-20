import type { Citation, Itinerary } from "../../types/itinerary";

/**
 * Collect citations from itinerary-level and activity-level lists,
 * deduplicating by ``citation_id`` (first occurrence wins).
 */
export function collectCitations(itinerary: Itinerary): Citation[] {
  const seen = new Set<string>();
  const unique: Citation[] = [];

  const push = (citation: Citation | undefined | null) => {
    if (!citation?.citation_id) {
      return;
    }
    if (seen.has(citation.citation_id)) {
      return;
    }
    seen.add(citation.citation_id);
    unique.push(citation);
  };

  for (const citation of itinerary.citations ?? []) {
    push(citation);
  }

  for (const day of itinerary.days ?? []) {
    for (const activity of day.activities ?? []) {
      for (const citation of activity.citations ?? []) {
        push(citation);
      }
    }
  }

  return unique;
}

/** Derive a human-readable source name from citation fields. */
export function deriveCitationSource(citation: Citation): string | null {
  const meta = citation.metadata ?? {};
  if (typeof meta.source === "string" && meta.source.trim()) {
    return meta.source.trim();
  }

  if (citation.document_id?.trim()) {
    const parts = citation.document_id.split(":");
    return parts.length > 1 ? parts[parts.length - 1]! : citation.document_id;
  }

  const match = citation.citation_id.match(/^[^:]+:([^#]+)/);
  return match?.[1] ?? null;
}

/** Optional short label from metadata (``label`` or ``short_label``). */
export function deriveCitationLabel(citation: Citation): string | null {
  const meta = citation.metadata ?? {};
  if (typeof meta.label === "string" && meta.label.trim()) {
    return meta.label.trim();
  }
  if (typeof meta.short_label === "string" && meta.short_label.trim()) {
    return meta.short_label.trim();
  }
  return null;
}
