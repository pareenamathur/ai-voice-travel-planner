import { afterEach, describe, expect, it, vi } from "vitest";

import { getSpeechRecognitionConstructor, isSpeechRecognitionSupported } from "../support";
import type { SpeechRecognitionConstructor } from "../types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("isSpeechRecognitionSupported", () => {
  it("returns false when neither constructor is present", () => {
    vi.stubGlobal("window", {});
    expect(isSpeechRecognitionSupported()).toBe(false);
    expect(getSpeechRecognitionConstructor()).toBeNull();
  });

  it("returns true when SpeechRecognition is present", () => {
    const Fake = class {} as unknown as SpeechRecognitionConstructor;
    vi.stubGlobal("window", { SpeechRecognition: Fake });
    expect(isSpeechRecognitionSupported()).toBe(true);
    expect(getSpeechRecognitionConstructor()).toBe(Fake);
  });

  it("falls back to webkitSpeechRecognition", () => {
    const Fake = class {} as unknown as SpeechRecognitionConstructor;
    vi.stubGlobal("window", { webkitSpeechRecognition: Fake });
    expect(isSpeechRecognitionSupported()).toBe(true);
    expect(getSpeechRecognitionConstructor()).toBe(Fake);
  });
});
