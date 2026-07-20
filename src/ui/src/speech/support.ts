import type { SpeechRecognitionConstructor } from "./types";

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

/** Return the browser SpeechRecognition constructor, if available. */
export function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/** True when the browser exposes the Web Speech API recognition interface. */
export function isSpeechRecognitionSupported(): boolean {
  return getSpeechRecognitionConstructor() !== null;
}
