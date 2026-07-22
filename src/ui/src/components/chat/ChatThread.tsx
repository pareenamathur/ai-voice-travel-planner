import { useEffect, useRef } from "react";

import type { LoadingHint } from "../../api/loadingHint";
import { activePendingBubbleMessage } from "../../api/loadingHint";
import type { ConversationExchange } from "../../api/conversationTypes";
import type { SourceLink } from "../sources/sourceLinks";
import { AssistantMessage } from "./AssistantMessage";
import "./chat.css";

export interface ChatThreadProps {
  exchanges: ConversationExchange[];
  loading: boolean;
  loadingHint?: LoadingHint;
  loadingElapsedSec?: number;
  itineraryApproved: boolean;
  sourceLinks?: SourceLink[];
  /** Optional: send a suggestion as a full user message. */
  onSuggestionSelect?: (prompt: string) => void;
  suggestionsDisabled?: boolean;
}

const SUGGESTIONS = [
  {
    icon: "landscape",
    label: "3-day Jaipur",
    prompt: "Plan a 3-day Jaipur trip with culture, landmarks, and a relaxed pace.",
  },
  {
    icon: "family_restroom",
    label: "Family itinerary",
    prompt: "Create a family itinerary for Jaipur with kids — not too rushed.",
  },
  {
    icon: "museum",
    label: "Cultural weekend",
    prompt: "Plan a relaxing Jaipur weekend focused on culture and heritage.",
  },
] as const;

export function ChatThread({
  exchanges,
  loading,
  loadingHint = "default",
  loadingElapsedSec = 0,
  itineraryApproved: _itineraryApproved,
  sourceLinks = [],
  onSuggestionSelect,
  suggestionsDisabled = false,
}: ChatThreadProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = endRef.current;
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [exchanges.length, loading]);

  const hasMessages = exchanges.length > 0;

  return (
    <div className="chat-thread" data-testid="chat-thread" role="log" aria-live="polite">
      {!hasMessages ? (
        <div className="chat-thread__welcome">
          <p className="chat-thread__eyebrow">Aether Travel</p>
          <h2 className="chat-thread__welcome-title">
            Plan your next trip
            <span className="chat-thread__welcome-title-accent"> by voice</span>
          </h2>
          <p className="chat-thread__welcome-body">
            Tell me the destination, how many days, and the vibe you want. I&apos;ll shape a
            day-by-day itinerary you can refine in conversation.
          </p>

          <div className="chat-thread__cta-hint" aria-hidden="true">
            <span className="material-symbols-outlined">mic</span>
            <span>Tap the microphone below to start</span>
          </div>

          <ul
            className="chat-thread__suggestions"
            aria-label="Try an example"
            data-testid="chat-suggestions"
          >
            {SUGGESTIONS.map((item) => (
              <li key={item.label}>
                <button
                  type="button"
                  className="chat-thread__suggestion"
                  disabled={suggestionsDisabled || !onSuggestionSelect}
                  onClick={() => onSuggestionSelect?.(item.prompt)}
                >
                  <span className="material-symbols-outlined" aria-hidden="true">
                    {item.icon}
                  </span>
                  <span className="chat-thread__suggestion-copy">
                    <span className="chat-thread__suggestion-label">{item.label}</span>
                    <span className="chat-thread__suggestion-prompt">{item.prompt}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <ol className="chat-thread__messages">
        {exchanges.map((exchange) => {
          return (
            <li
              key={exchange.id}
              className="chat-thread__turn"
              data-testid={`chat-turn-${exchange.id}`}
            >
              <div className="chat-bubble chat-bubble--user">
                <span className="chat-bubble__avatar chat-bubble__avatar--user" aria-hidden="true">
                  You
                </span>
                <p className="chat-bubble__text">{exchange.userMessage}</p>
              </div>

              {exchange.error ? (
                <div className="chat-bubble chat-bubble--assistant chat-bubble--error">
                  <span
                    className="chat-bubble__avatar chat-bubble__avatar--assistant"
                    aria-hidden="true"
                  >
                    <span className="material-symbols-outlined">auto_awesome</span>
                  </span>
                  <p className="chat-bubble__text">
                    {exchange.error &&
                    exchange.error !== "empty-transcript" &&
                    !exchange.error.startsWith("Supervisor replied")
                      ? exchange.error
                      : "Something went wrong. Please try again in a moment."}
                  </p>
                </div>
              ) : exchange.response ? (
                <div className="chat-bubble chat-bubble--assistant">
                  <span
                    className="chat-bubble__avatar chat-bubble__avatar--assistant"
                    aria-hidden="true"
                  >
                    <span className="material-symbols-outlined">auto_awesome</span>
                  </span>
                  <AssistantMessage
                    text={exchange.response.response}
                    sourceLinks={sourceLinks}
                  />
                </div>
              ) : (
                <div className="chat-bubble chat-bubble--assistant chat-bubble--pending">
                  <span className="chat-typing" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  <span className="chat-bubble__pending-label">
                    {activePendingBubbleMessage(loadingHint, loadingElapsedSec)}
                  </span>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <div ref={endRef} className="chat-thread__anchor" />
    </div>
  );
}
