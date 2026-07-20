import type { ConversationExchange } from "../../api/conversationTypes";
import "./debug.css";

export interface ConversationHistoryProps {
  exchanges: ConversationExchange[];
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

/**
 * Chat-style log of every user message and Supervisor API exchange.
 */
export function ConversationHistory({ exchanges }: ConversationHistoryProps) {
  if (exchanges.length === 0) {
    return (
      <section
        className="conversation-history"
        data-testid="conversation-history"
        aria-label="Conversation history"
      >
        <header className="conversation-history__header">
          <h2 className="conversation-history__title">Conversation</h2>
        </header>
        <p className="conversation-history__empty" data-testid="conversation-empty">
          No messages yet. Speak or send a transcript to start.
        </p>
      </section>
    );
  }

  return (
    <section
      className="conversation-history"
      data-testid="conversation-history"
      aria-label="Conversation history"
    >
      <header className="conversation-history__header">
        <h2 className="conversation-history__title">Conversation</h2>
        <span className="conversation-history__count" data-testid="conversation-count">
          {exchanges.length} turn{exchanges.length === 1 ? "" : "s"}
        </span>
      </header>

      <ol className="conversation-history__list">
        {exchanges.map((exchange) => (
          <li
            key={exchange.id}
            className="conversation-history__turn"
            data-testid={`conversation-turn-${exchange.id}`}
          >
            <article
              className="conversation-history__bubble conversation-history__bubble--user"
              data-testid="conversation-user-message"
            >
              <span className="conversation-history__role">You</span>
              <p className="conversation-history__text">{exchange.userMessage}</p>
              <time
                className="conversation-history__time"
                dateTime={exchange.requestedAt}
              >
                {exchange.requestedAt}
              </time>
            </article>

            <details
              className="conversation-history__api"
              open
              data-testid="conversation-api-request"
            >
              <summary>POST /api/session/message (request)</summary>
              <pre>{formatJson(exchange.request)}</pre>
            </details>

            {exchange.response ? (
              <>
                <details
                  className="conversation-history__api"
                  open
                  data-testid="conversation-api-response"
                >
                  <summary>POST /api/session/message (response)</summary>
                  <pre>{formatJson(exchange.response)}</pre>
                </details>

                <article
                  className="conversation-history__bubble conversation-history__bubble--supervisor"
                  data-testid="conversation-supervisor-message"
                >
                  <span className="conversation-history__role">Supervisor</span>
                  <p className="conversation-history__text">
                    {exchange.response.response}
                  </p>
                  {exchange.respondedAt ? (
                    <time
                      className="conversation-history__time"
                      dateTime={exchange.respondedAt}
                    >
                      {exchange.respondedAt}
                    </time>
                  ) : null}
                </article>
              </>
            ) : exchange.error ? (
              <p
                className="conversation-history__error"
                role="alert"
                data-testid="conversation-api-error"
              >
                API error: {exchange.error}
              </p>
            ) : (
              <p
                className="conversation-history__pending"
                data-testid="conversation-pending"
              >
                Waiting for Supervisor…
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
