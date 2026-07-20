import type {
  SpeechRecognitionErrorEventLike,
  SpeechRecognitionEventLike,
  SpeechRecognitionLike,
  SpeechRecognitionResultLike,
  SpeechRecognitionResultListLike,
} from "../../speech";

/** Test double for the browser Web Speech API. */
export class MockSpeechRecognition extends EventTarget implements SpeechRecognitionLike {
  static last: MockSpeechRecognition | null = null;

  continuous = false;
  interimResults = false;
  lang = "";
  onresult: ((event: SpeechRecognitionEventLike) => void) | null = null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null = null;
  onend: ((event: Event) => void) | null = null;

  constructor() {
    super();
    MockSpeechRecognition.last = this;
  }

  start(): void {}

  stop(): void {
    this.onend?.(new Event("end"));
  }

  abort(): void {
    this.onend?.(new Event("end"));
  }

  emitParts(parts: Array<{ transcript: string; isFinal: boolean }>): void {
    const resultsArray = parts.map((part) => {
      const alternative = { transcript: part.transcript, confidence: 1 };
      return {
        isFinal: part.isFinal,
        length: 1,
        0: alternative,
        item: () => alternative,
      } as SpeechRecognitionResultLike;
    });

    const results = resultsArray as unknown as SpeechRecognitionResultListLike;
    Object.defineProperty(results, "length", { value: parts.length });
    for (let i = 0; i < resultsArray.length; i += 1) {
      (results as unknown as Record<number, SpeechRecognitionResultLike>)[i] = resultsArray[i];
    }

    this.onresult?.({
      resultIndex: 0,
      results,
    } as SpeechRecognitionEventLike);
  }

  emitError(code: string): void {
    this.onerror?.({
      error: code,
      message: code,
    } as SpeechRecognitionErrorEventLike);
  }
}
