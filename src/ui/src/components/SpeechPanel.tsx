import { useCallback, useEffect, useRef } from "react";

import { MicrophoneButton } from "./MicrophoneButton";
import { ListeningIndicator } from "./ListeningIndicator";
import { TranscriptView } from "./TranscriptView";
import { useSpeechRecognition } from "../speech";
import type { SpeechRecognitionOptions } from "../speech";
import "./speech-panel.css";

export interface SpeechPanelProps {
  /** Forwarded to {@link useSpeechRecognition}; public hook API unchanged. */
  speechOptions?: SpeechRecognitionOptions;
  /**
   * Called when listening stops with a non-empty final transcript,
   * or when the user clicks Send. Resolves after the backend succeeds.
   */
  onSubmitTranscript?: (transcript: string) => Promise<void>;
  /** Disable send while Supervisor request is in flight. */
  submitDisabled?: boolean;
}

/**
 * Microphone controls + live transcript.
 * Optionally notifies the parent when a transcript is ready to send.
 */
export function SpeechPanel({
  speechOptions,
  onSubmitTranscript,
  submitDisabled = false,
}: SpeechPanelProps) {
  const {
    startListening,
    stopListening,
    resetTranscript,
    transcript,
    interimTranscript,
    isListening,
    isSupported,
    error,
  } = useSpeechRecognition(speechOptions);

  const wasListeningRef = useRef(false);

  const submitAndMaybeClear = useCallback(
    (text: string) => {
      if (!text || !onSubmitTranscript) {
        return;
      }
      void onSubmitTranscript(text)
        .then(() => {
          resetTranscript();
        })
        .catch(() => {
          // Keep transcript visible until a successful Supervisor response.
        });
    },
    [onSubmitTranscript, resetTranscript],
  );

  useEffect(() => {
    if (wasListeningRef.current && !isListening) {
      const text = transcript.trim();
      if (text && onSubmitTranscript && !submitDisabled) {
        submitAndMaybeClear(text);
      }
    }
    wasListeningRef.current = isListening;
  }, [isListening, transcript, onSubmitTranscript, submitDisabled, submitAndMaybeClear]);

  const controlsDisabled = !isSupported;

  const handleMicToggle = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const handleSend = () => {
    const text = `${transcript} ${interimTranscript}`.trim();
    submitAndMaybeClear(text);
  };

  return (
    <section
      className="speech-panel"
      data-testid="speech-panel"
      data-listening={isListening ? "true" : "false"}
      aria-label="Voice input"
    >
      <div className="speech-panel__controls">
        <MicrophoneButton
          isListening={isListening}
          disabled={controlsDisabled}
          onToggle={handleMicToggle}
        />
      </div>

      <header className="speech-panel__header">
        <h2 className="speech-panel__title">Voice input</h2>
        <ListeningIndicator isListening={isListening} />
      </header>

      {!isSupported ? (
        <p
          className="speech-panel__unsupported"
          role="alert"
          data-testid="unsupported-message"
        >
          Speech recognition is not supported in this browser. Try Chrome or Edge.
        </p>
      ) : null}

      {error ? (
        <p className="speech-panel__error" role="alert" data-testid="error-message">
          {error}
        </p>
      ) : null}

      <div className="speech-visualizer" aria-hidden="true">
        {Array.from({ length: 7 }, (_, index) => (
          <span key={index} className="speech-visualizer__bar" />
        ))}
      </div>

      <TranscriptView transcript={transcript} interimTranscript={interimTranscript} />

      <div className="speech-panel__controls">
        <button
          type="button"
          className="speech-panel__start"
          data-testid="start-listening"
          disabled={controlsDisabled || isListening}
          onClick={startListening}
        >
          Start Listening
        </button>
        <button
          type="button"
          className="speech-panel__stop"
          data-testid="stop-listening"
          disabled={controlsDisabled || !isListening}
          onClick={stopListening}
        >
          Stop Listening
        </button>
        {onSubmitTranscript ? (
          <button
            type="button"
            className="speech-panel__send"
            data-testid="send-transcript"
            disabled={
              submitDisabled || (!transcript.trim() && !interimTranscript.trim())
            }
            onClick={handleSend}
          >
            Send to Supervisor
          </button>
        ) : null}
      </div>
    </section>
  );
}
