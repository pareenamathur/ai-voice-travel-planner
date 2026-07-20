import "./debug.css";

export interface SessionDebugPanelProps {
  sessionId: string | null;
  conversationPhase: string | null;
  intent: string | null;
  taskMessage: Record<string, unknown> | null;
  itineraryApproved: boolean;
  confirmRejectedWarning: string | null;
}

function formatTaskMessage(taskMessage: Record<string, unknown> | null): string {
  if (taskMessage === null) {
    return "null";
  }
  return JSON.stringify(taskMessage, null, 2);
}

/**
 * Visible snapshot of the latest Supervisor session fields for debugging.
 */
export function SessionDebugPanel({
  sessionId,
  conversationPhase,
  intent,
  taskMessage,
  itineraryApproved,
  confirmRejectedWarning,
}: SessionDebugPanelProps) {
  const showNullTaskMessageNote =
    intent === "confirm" && taskMessage === null;

  return (
    <section
      className="session-debug"
      data-testid="session-debug"
      aria-label="Session debug"
    >
      <header className="session-debug__header">
        <h2 className="session-debug__title">Session Debug</h2>
      </header>

      {confirmRejectedWarning ? (
        <p
          className="session-debug__warning"
          role="alert"
          data-testid="confirm-rejected-warning"
        >
          {confirmRejectedWarning}
        </p>
      ) : null}

      <dl className="session-debug__grid">
        <div className="session-debug__row">
          <dt>session_id</dt>
          <dd data-testid="debug-session-id">{sessionId ?? "—"}</dd>
        </div>
        <div className="session-debug__row">
          <dt>conversation_phase</dt>
          <dd data-testid="debug-conversation-phase">{conversationPhase ?? "—"}</dd>
        </div>
        <div className="session-debug__row">
          <dt>intent</dt>
          <dd data-testid="debug-intent">{intent ?? "—"}</dd>
        </div>
        <div className="session-debug__row">
          <dt>itinerary_approved</dt>
          <dd data-testid="debug-itinerary-approved">
            {String(itineraryApproved)}
          </dd>
        </div>
        <div className="session-debug__row session-debug__row--full">
          <dt>task_message</dt>
          <dd data-testid="debug-task-message">
            <pre className="session-debug__pre">{formatTaskMessage(taskMessage)}</pre>
            {showNullTaskMessageNote ? (
              <p
                className="session-debug__note"
                data-testid="debug-task-message-null"
              >
                task_message is null (no TaskMessage was created for this turn).
              </p>
            ) : null}
          </dd>
        </div>
      </dl>
    </section>
  );
}
