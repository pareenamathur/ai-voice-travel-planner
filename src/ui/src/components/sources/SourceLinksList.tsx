import type { SourceLink } from "./sourceLinks";
import "./sources.css";

export interface SourceLinksListProps {
  links: SourceLink[];
  className?: string;
  title?: string;
  testId?: string;
}

export function SourceLinksList({
  links,
  className = "",
  title = "Sources",
  testId = "source-links",
}: SourceLinksListProps) {
  if (links.length === 0) {
    return null;
  }

  return (
    <footer
      className={`source-links ${className}`.trim()}
      data-testid={testId}
      aria-label={title}
    >
      <h4 className="source-links__title">{title}</h4>
      <ul className="source-links__list">
        {links.map((link) => (
          <li key={link.label}>
            {link.href ? (
              <a
                className="source-links__anchor"
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                data-testid="source-link"
              >
                {link.label}
              </a>
            ) : (
              <span className="source-links__plain">{link.label}</span>
            )}
          </li>
        ))}
      </ul>
    </footer>
  );
}
