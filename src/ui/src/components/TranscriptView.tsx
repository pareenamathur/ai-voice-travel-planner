export interface TranscriptViewProps {
  transcript: string;
  interimTranscript: string;
}

/**
 * Live transcript display. Finalized text and interim hypotheses are shown
 * separately so interim speech is visually distinct.
 */
export function TranscriptView({ transcript, interimTranscript }: TranscriptViewProps) {
  const hasFinal = transcript.trim().length > 0;
  const hasInterim = interimTranscript.trim().length > 0;

  return (
    <div className="transcript-view" data-testid="transcript-view">
      <div className="transcript-view__section">
        <h3 className="transcript-view__heading">Transcript</h3>
        <p
          className="transcript-view__final"
          data-testid="final-transcript"
          aria-live="polite"
        >
          {hasFinal ? transcript : "Speak to see your transcript here."}
        </p>
      </div>

      <div className="transcript-view__section">
        <h3 className="transcript-view__heading">Interim</h3>
        <p
          className={[
            "transcript-view__interim",
            hasInterim ? "transcript-view__interim--active" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          data-testid="interim-transcript"
          aria-live="polite"
        >
          {hasInterim ? interimTranscript : "—"}
        </p>
      </div>
    </div>
  );
}
