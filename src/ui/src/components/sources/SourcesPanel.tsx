import type { Citation, Itinerary } from "../../types/itinerary";
import { CitationCard } from "./CitationCard";
import { collectCitations } from "./collectCitations";
import "./sources.css";

export interface SourcesPanelProps {
  /** Canonical itinerary — citations are collected from top-level and activities. */
  itinerary?: Itinerary;
  /**
   * Optional explicit citation list. When provided without ``itinerary``,
   * these are rendered (still deduplicated by ``citation_id``).
   */
  citations?: Citation[];
}

function dedupeCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>();
  const unique: Citation[] = [];
  for (const citation of citations) {
    if (!citation.citation_id || seen.has(citation.citation_id)) {
      continue;
    }
    seen.add(citation.citation_id);
    unique.push(citation);
  }
  return unique;
}

/**
 * Sources / References panel. Props-only — no API or Supervisor calls.
 */
export function SourcesPanel({ itinerary, citations }: SourcesPanelProps) {
  const items = itinerary
    ? collectCitations(itinerary)
    : dedupeCitations(citations ?? []);

  return (
    <section
      className="sources-panel"
      data-testid="sources-panel"
      aria-label="Sources and references"
    >
      <header className="sources-panel__header">
        <h2 className="sources-panel__title">Sources / References</h2>
        <p className="sources-panel__count" data-testid="sources-count">
          {items.length} {items.length === 1 ? "source" : "sources"}
        </p>
      </header>

      {items.length === 0 ? (
        <p className="sources-panel__empty" data-testid="sources-empty">
          No sources yet.
        </p>
      ) : (
        <ul className="sources-panel__list" data-testid="sources-list">
          {items.map((citation, index) => (
            <li key={citation.citation_id} className="sources-panel__item">
              <CitationCard citation={citation} index={index + 1} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
