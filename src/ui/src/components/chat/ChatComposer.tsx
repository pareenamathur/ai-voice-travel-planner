import { useCallback, useEffect, useRef, useState } from "react";

import { useSpeechRecognition } from "../../speech";
import { MicrophoneButton } from "../MicrophoneButton";
import "../speech-panel.css";
import "./chat.css";

export interface ChatComposerProps {
  onSubmitTranscript: (message: string) => Promise<void>;
  submitDisabled?: boolean;
  busy?: boolean;
}

/**
 * ChatGPT-style composer: the textarea draft is the single source of truth.
 * Mic only fills/appends into the draft; Send/Enter submit the edited draft.
 * Mic stop never auto-sends and never overwrites manual edits.
 */
export function ChatComposer({
  onSubmitTranscript,
  submitDisabled = false,
}: ChatComposerProps) {
  const [draft, setDraft] = useState("");
  const speechBaseRef = useRef("");
  const manualEditDuringListenRef = useRef(false);
  const wasListeningRef = useRef(false);

  const {
    startListening,
    stopListening,
    resetTranscript,
    transcript,
    interimTranscript,
    isListening,
    isSupported,
    error: speechError,
  } = useSpeechRecognition();

  const liveSpeech = `${transcript} ${interimTranscript}`.trim();

  // While listening, mirror speech into draft — unless the user has typed over it.
  useEffect(() => {
    if (!isListening || manualEditDuringListenRef.current) {
      return;
    }
    if (!liveSpeech) {
      return;
    }
    const prefix = speechBaseRef.current.trim();
    setDraft(prefix ? `${prefix} ${liveSpeech}` : liveSpeech);
  }, [isListening, liveSpeech]);

  // Mic stop: keep the current draft (possibly user-edited). Never auto-send.
  useEffect(() => {
    if (wasListeningRef.current && !isListening) {
      resetTranscript();
      manualEditDuringListenRef.current = false;
    }
    wasListeningRef.current = isListening;
  }, [isListening, resetTranscript]);

  const submitAndClear = useCallback(
    (raw: string) => {
      const trimmed = raw.trim();
      if (!trimmed) {
        return;
      }
      void onSubmitTranscript(trimmed)
        .then(() => {
          setDraft("");
          speechBaseRef.current = "";
          manualEditDuringListenRef.current = false;
          resetTranscript();
        })
        .catch(() => {
          /* keep draft visible until a successful response */
        });
    },
    [onSubmitTranscript, resetTranscript],
  );

  const handleMicToggle = () => {
    if (isListening) {
      stopListening();
      return;
    }
    speechBaseRef.current = draft;
    manualEditDuringListenRef.current = false;
    resetTranscript();
    startListening();
  };

  const handleSend = () => {
    if (isListening) {
      // Stop listening first; draft already holds speech or user edits — do not auto-send.
      stopListening();
      return;
    }
    if (!draft.trim() || submitDisabled) {
      return;
    }
    submitAndClear(draft);
  };

  const handleDraftChange = (value: string) => {
    if (isListening) {
      manualEditDuringListenRef.current = true;
    }
    setDraft(value);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }
    event.preventDefault();
    if (isListening || submitDisabled || !draft.trim()) {
      return;
    }
    submitAndClear(draft);
  };

  const canSend = Boolean(draft.trim()) && !submitDisabled && !isListening;

  return (
    <footer className="chat-composer-wrap" data-testid="chat-composer-wrap">
      <div
        className={[
          "chat-composer",
          "glass-card",
          isListening ? "chat-composer--listening" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        data-testid="chat-composer"
      >
        {!isSupported ? (
          <p className="chat-composer__unsupported" role="alert" data-testid="unsupported-message">
            Voice works best in Chrome or Edge.
          </p>
        ) : null}

        {speechError ? (
          <p className="chat-composer__speech-error" role="alert" data-testid="error-message">
            {speechError}
          </p>
        ) : null}

        <div className="chat-composer__row">
          <button
            type="button"
            className="chat-composer__icon-btn"
            aria-label="Add attachment (coming soon)"
            title="Attachments coming soon"
            disabled
            data-testid="composer-attachment"
          >
            <span className="material-symbols-outlined">attach_file</span>
          </button>

          <textarea
            className="chat-composer__input"
            value={draft}
            onChange={(event) => handleDraftChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isListening
                ? "Listening… edit text before you send"
                : submitDisabled
                  ? "Working on your last message…"
                  : "Type a message or tap the mic"
            }
            rows={1}
            aria-label="Message"
            data-testid="composer-input"
            disabled={submitDisabled}
          />

          {draft.trim() ? (
            <span className="visually-hidden" data-testid="final-transcript">
              {draft.trim()}
            </span>
          ) : null}

          <button
            type="button"
            className="chat-composer__icon-btn"
            aria-label="Insert emoji (coming soon)"
            title="Emoji picker coming soon"
            disabled
            data-testid="composer-emoji"
          >
            <span className="material-symbols-outlined">sentiment_satisfied</span>
          </button>

          <MicrophoneButton
            className="chat-composer__mic chat-composer__mic--compact"
            isListening={isListening}
            disabled={!isSupported}
            onToggle={handleMicToggle}
          />

          <button
            type="button"
            className="chat-composer__send"
            disabled={!canSend}
            aria-label="Send message"
            data-testid="send-transcript"
            onClick={handleSend}
          >
            <span className="material-symbols-outlined" aria-hidden="true">
              arrow_upward
            </span>
          </button>
        </div>
      </div>
    </footer>
  );
}
