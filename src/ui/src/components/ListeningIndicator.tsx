export interface ListeningIndicatorProps {
  isListening: boolean;
}

/** Visual status for whether the microphone is actively capturing speech. */
export function ListeningIndicator({ isListening }: ListeningIndicatorProps) {
  return (
    <div
      className={[
        "listening-indicator",
        isListening ? "listening-indicator--active" : "listening-indicator--idle",
      ].join(" ")}
      role="status"
      aria-live="polite"
      data-testid="listening-indicator"
      data-listening={isListening ? "true" : "false"}
    >
      {isListening ? "Listening…" : "Not listening"}
    </div>
  );
}
