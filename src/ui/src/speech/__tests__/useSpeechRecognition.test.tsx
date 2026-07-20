import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSpeechRecognition } from "../useSpeechRecognition";
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

  emitFinal(text: string): void {
    const alternative = { transcript: text, confidence: 1 };
    const result = {
      isFinal: true,
      length: 1,
      0: alternative,
      item: () => alternative,
    } as SpeechRecognitionResultLike;
    const results = [result] as unknown as SpeechRecognitionResultListLike;
    Object.defineProperty(results, "length", { value: 1 });
    (results as unknown as Record<number, SpeechRecognitionResultLike>)[0] = result;
    this.onresult?.({ resultIndex: 0, results } as SpeechRecognitionEventLike);
  }
}

describe("useSpeechRecognition", () => {
  it("exposes the required STT API surface", () => {
    const { result } = renderHook(() =>
      useSpeechRecognition({ SpeechRecognition: MockSpeechRecognition }),
    );

    expect(result.current).toEqual(
      expect.objectContaining({
        transcript: "",
        interimTranscript: "",
        isListening: false,
        isSupported: true,
        error: null,
      }),
    );
    expect(typeof result.current.startListening).toBe("function");
    expect(typeof result.current.stopListening).toBe("function");
  });

  it("updates transcript through startListening", () => {
    const { result } = renderHook(() =>
      useSpeechRecognition({ SpeechRecognition: MockSpeechRecognition }),
    );

    act(() => {
      result.current.startListening();
    });
    expect(result.current.isListening).toBe(true);

    act(() => {
      MockSpeechRecognition.last!.emitFinal("visit Amer Fort");
    });
    expect(result.current.transcript).toBe("visit Amer Fort");

    act(() => {
      result.current.stopListening();
    });
    expect(result.current.isListening).toBe(false);
  });

  it("reports unsupported browsers", () => {
    const { result } = renderHook(() =>
      useSpeechRecognition({ SpeechRecognition: null }),
    );

    expect(result.current.isSupported).toBe(false);
    act(() => {
      result.current.startListening();
    });
    expect(result.current.error).toBe("not-supported");
  });
});
