import { describe, expect, it, vi } from "vitest";

import { BrowserSpeechRecognitionService } from "../speechRecognition";
import type {
  SpeechRecognitionErrorEventLike,
  SpeechRecognitionEventLike,
  SpeechRecognitionLike,
  SpeechRecognitionResultLike,
  SpeechRecognitionResultListLike,
} from "../types";

class MockSpeechRecognition extends EventTarget implements SpeechRecognitionLike {
  static last: MockSpeechRecognition | null = null;

  continuous = false;
  interimResults = false;
  lang = "";
  onresult: ((event: SpeechRecognitionEventLike) => void) | null = null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null = null;
  onend: ((event: Event) => void) | null = null;
  started = false;

  constructor() {
    super();
    MockSpeechRecognition.last = this;
  }

  start(): void {
    this.started = true;
  }

  stop(): void {
    this.started = false;
    this.onend?.(new Event("end"));
  }

  abort(): void {
    this.started = false;
    this.onerror?.({
      error: "aborted",
      message: "aborted",
    } as SpeechRecognitionErrorEventLike);
    this.onend?.(new Event("end"));
  }

  emitResult(parts: Array<{ transcript: string; isFinal: boolean }>, resultIndex = 0): void {
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
      resultIndex,
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

describe("BrowserSpeechRecognitionService", () => {
  it("reports not-supported when constructor is null", () => {
    const service = new BrowserSpeechRecognitionService({
      SpeechRecognition: null,
    });
    expect(service.isSupported).toBe(false);
    service.startListening();
    expect(service.getSnapshot()).toMatchObject({
      error: "not-supported",
      isListening: false,
    });
  });

  it("starts and stops listening", () => {
    const service = new BrowserSpeechRecognitionService({
      SpeechRecognition: MockSpeechRecognition,
    });

    service.startListening();
    expect(service.getSnapshot().isListening).toBe(true);
    expect(service.getSnapshot().error).toBeNull();
    expect(MockSpeechRecognition.last?.started).toBe(true);
    expect(MockSpeechRecognition.last?.continuous).toBe(true);
    expect(MockSpeechRecognition.last?.interimResults).toBe(true);
    expect(MockSpeechRecognition.last?.lang).toBe("en-IN");

    service.stopListening();
    expect(service.getSnapshot().isListening).toBe(false);
  });

  it("merges interim then final transcripts", () => {
    const service = new BrowserSpeechRecognitionService({
      SpeechRecognition: MockSpeechRecognition,
    });
    service.startListening();
    const recognition = MockSpeechRecognition.last!;

    recognition.emitResult([{ transcript: "plan a trip", isFinal: false }]);
    expect(service.getSnapshot().interimTranscript).toBe("plan a trip");
    expect(service.getSnapshot().transcript).toBe("");

    recognition.emitResult([{ transcript: "plan a trip to Jaipur", isFinal: true }]);
    expect(service.getSnapshot().transcript).toBe("plan a trip to Jaipur");
    expect(service.getSnapshot().interimTranscript).toBe("");

    recognition.emitResult([{ transcript: "for three days", isFinal: true }]);
    expect(service.getSnapshot().transcript).toBe("plan a trip to Jaipur for three days");
  });

  it("records recognition errors", () => {
    const service = new BrowserSpeechRecognitionService({
      SpeechRecognition: MockSpeechRecognition,
    });
    service.startListening();
    MockSpeechRecognition.last!.emitError("not-allowed");
    expect(service.getSnapshot().error).toBe("not-allowed");
    expect(service.getSnapshot().isListening).toBe(false);
  });

  it("notifies subscribers on state changes", () => {
    const service = new BrowserSpeechRecognitionService({
      SpeechRecognition: MockSpeechRecognition,
    });
    const listener = vi.fn();
    service.subscribe(listener);
    expect(listener).toHaveBeenCalledTimes(1);

    service.startListening();
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("promotes leftover interim text into transcript on stop", () => {
    const service = new BrowserSpeechRecognitionService({
      SpeechRecognition: MockSpeechRecognition,
    });
    service.startListening();
    MockSpeechRecognition.last!.emitResult([
      { transcript: "hello pink city", isFinal: false },
    ]);
    service.stopListening();
    expect(service.getSnapshot().transcript).toBe("hello pink city");
    expect(service.getSnapshot().interimTranscript).toBe("");
  });
});
