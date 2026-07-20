/** Browser Web Speech API types used by the STT layer (client-side only). */

export interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  item(index: number): SpeechRecognitionAlternativeLike;
  [index: number]: SpeechRecognitionAlternativeLike;
}

export interface SpeechRecognitionAlternativeLike {
  readonly transcript: string;
  readonly confidence: number;
}

export interface SpeechRecognitionResultListLike {
  readonly length: number;
  item(index: number): SpeechRecognitionResultLike;
  [index: number]: SpeechRecognitionResultLike;
}

export interface SpeechRecognitionEventLike extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultListLike;
}

export interface SpeechRecognitionErrorEventLike extends Event {
  readonly error: string;
  readonly message: string;
}

export interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: ((event: Event) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

export interface SpeechRecognitionOptions {
  /** BCP-47 language tag. Defaults to ``en-IN`` for the Jaipur MVP. */
  lang?: string;
  /** Keep listening until ``stopListening`` is called. Defaults to ``true``. */
  continuous?: boolean;
  /**
   * Optional constructor injection for tests. Defaults to the browser
   * ``SpeechRecognition`` / ``webkitSpeechRecognition`` global.
   * Pass ``null`` to simulate an unsupported browser.
   */
  SpeechRecognition?: SpeechRecognitionConstructor | null;
}

export interface SpeechRecognitionSnapshot {
  /** Accumulated final transcript text (finals merged as they arrive). */
  transcript: string;
  /** Current interim (non-final) hypothesis. */
  interimTranscript: string;
  isListening: boolean;
  isSupported: boolean;
  error: string | null;
}

export interface SpeechRecognitionControls {
  startListening: () => void;
  stopListening: () => void;
  /** Clear accumulated transcript after a successful Supervisor submit. */
  resetTranscript: () => void;
}

export type SpeechRecognitionApi = SpeechRecognitionSnapshot & SpeechRecognitionControls;
