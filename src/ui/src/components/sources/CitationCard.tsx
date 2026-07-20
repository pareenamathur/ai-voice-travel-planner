import type { Citation } from "../../types/itinerary";
import { deriveCitationLabel, deriveCitationSource } from "./collectCitations";

export interface CitationCardProps {
  citation: Citation;
  index: number;
}

export function CitationCard({ citation, index }: CitationCardProps) {
  const source = deriveCitationSource(citation);
  const label = deriveCitationLabel(citation);
  const section = citation.section?.trim() || null;
  const url = citation.source_url?.trim() || null;

  return (
    <article
      className="citation-card"
      data-testid="citation-card"
      data-citation-id={citation.citation_id}
    >
      <header className="citation-card__header">
        <span className="citation-card__index" data-testid="citation-index">
          [{index}]
        </span>
        {label ? (
          <span className="citation-card__label" data-testid="citation-label">
            {label}
          </span>
        ) : null}
      </header>

      <p className="citation-card__id" data-testid="citation-id">
        {citation.citation_id}
      </p>

      {source ? (
        <p className="citation-card__source" data-testid="citation-source">
          Source: {source}
        </p>
      ) : null}

      {section ? (
        <p className="citation-card__section" data-testid="citation-section">
          Section: {section}
        </p>
      ) : null}

      {url ? (
        <a
          className="citation-card__url"
          data-testid="citation-url"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {url}
        </a>
      ) : null}
    </article>
  );
}
