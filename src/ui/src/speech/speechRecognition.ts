import { getSpeechRecognitionConstructor } from "./support";
import type {
  SpeechRecognitionConstructor,
  SpeechRecognitionEventLike,
  SpeechRecognitionErrorEventLike,
  SpeechRecognitionLike,
  SpeechRecognitionOptions,
  SpeechRecognitionSnapshot,
} from "./types";

type Listener = (snapshot: SpeechRecognitionSnapshot) => void;

function appendTranscript(existing: string, addition: string): string {
  const next = addition.trim();
  if (!next) {
    return existing;
  }
  if (!existing) {
    return next;
  }
  // Avoid double spaces when the engine already includes leading whitespace.
  if (addition.startsWith(" ") || existing.endsWith(" ")) {
    return `${existing}${addition}`.replace(/\s+/g, " ").trim();
  }
  return `${existing} ${next}`;
}

/**
 * Client-side speech recognition service backed only by the browser
 * Web Speech API. No audio or transcripts are sent to any backend.
 */
export class BrowserSpeechRecognitionService {
  private readonly lang: string;
  private readonly continuous: boolean;
  private readonly Recognition: SpeechRecognitionConstructor | null;

  private recognition: SpeechRecognitionLike | null = null;
  private transcript = "";
  private interimTranscript = "";
  private isListening = false;
  private error: string | null = null;
  private readonly listeners = new Set<Listener>();
  private intentionallyStopped = false;

  constructor(options: SpeechRecognitionOptions = {}) {
    this.lang = options.lang ?? "en-IN";
    this.continuous = options.continuous ?? true;
    this.Recognition =
      options.SpeechRecognition === undefined
        ? getSpeechRecognitionConstructor()
        : options.SpeechRecognition;
  }

  get isSupported(): boolean {
    return this.Recognition !== null;
  }

  getSnapshot(): SpeechRecognitionSnapshot {
    return {
      transcript: this.transcript,
      interimTranscript: this.interimTranscript,
      isListening: this.isListening,
      isSupported: this.isSupported,
      error: this.error,
    };
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.getSnapshot());
    return () => {
      this.listeners.delete(listener);
    };
  }

  startListening(): void {
    if (!this.Recognition) {
      this.error = "not-supported";
      this.emit();
      return;
    }

    if (this.isListening) {
      return;
    }

    this.error = null;
    this.intentionallyStopped = false;
    this.interimTranscript = "";

    const recognition = new this.Recognition();
    recognition.continuous = this.continuous;
    recognition.interimResults = true;
    recognition.lang = this.lang;
    recognition.onresult = (event) => this.handleResult(event);
    recognition.onerror = (event) => this.handleError(event);
    recognition.onend = () => this.handleEnd();

    this.recognition = recognition;
    this.isListening = true;
    this.emit();

    try {
      recognition.start();
    } catch (err) {
      this.isListening = false;
      this.recognition = null;
      this.error = err instanceof Error ? err.message : "start-failed";
      this.emit();
    }
  }

  stopListening(): void {
    if (!this.recognition) {
      this.isListening = false;
      this.emit();
      return;
    }

    this.intentionallyStopped = true;
    try {
      this.recognition.stop();
    } catch {
      // Some browsers throw if recognition is already stopping.
    }
  }

  /** Clear accumulated transcript state (does not change listening). */
  resetTranscript(): void {
    this.transcript = "";
    this.interimTranscript = "";
    this.error = null;
    this.emit();
  }

  private handleResult(event: SpeechRecognitionEventLike): void {
    let interim = "";
    let finals = "";

    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      const piece = result[0]?.transcript ?? "";
      if (result.isFinal) {
        finals += piece;
      } else {
        interim += piece;
      }
    }

    if (finals) {
      this.transcript = appendTranscript(this.transcript, finals);
    }
    this.interimTranscript = interim;
    this.emit();
  }

  private handleError(event: SpeechRecognitionErrorEventLike): void {
    // "aborted" is expected when the caller stops listening.
    if (event.error === "aborted" && this.intentionallyStopped) {
      this.error = null;
    } else {
      this.error = event.error || "recognition-error";
    }
    this.isListening = false;
    this.emit();
  }

  private handleEnd(): void {
    this.isListening = false;
    this.recognition = null;
    // Promote any leftover interim text into the final transcript on stop.
    if (this.interimTranscript.trim()) {
      this.transcript = appendTranscript(this.transcript, this.interimTranscript);
      this.interimTranscript = "";
    }
    this.emit();
  }

  private emit(): void {
    const snapshot = this.getSnapshot();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}
