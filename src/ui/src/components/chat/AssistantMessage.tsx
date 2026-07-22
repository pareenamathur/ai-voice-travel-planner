import type { SourceLink } from "../sources/sourceLinks";
import { splitSourcesFooter } from "../sources/sourceLinks";
import { SourceLinksList } from "../sources/SourceLinksList";

export interface AssistantMessageProps {
  text: string;
  sourceLinks?: SourceLink[];
}

export function AssistantMessage({ text, sourceLinks = [] }: AssistantMessageProps) {
  const { body, hasSourcesFooter } = splitSourcesFooter(text);

  return (
    <div className="chat-bubble__content">
      {body ? (
        <p className="chat-bubble__text chat-bubble__text--pre">{body}</p>
      ) : null}
      {hasSourcesFooter && sourceLinks.length > 0 ? (
        <SourceLinksList links={sourceLinks} className="chat-bubble__sources" />
      ) : hasSourcesFooter ? (
        <p className="chat-bubble__text chat-bubble__text--sources-muted">
          Sources: trusted travel guidance and map data.
        </p>
      ) : null}
    </div>
  );
}
