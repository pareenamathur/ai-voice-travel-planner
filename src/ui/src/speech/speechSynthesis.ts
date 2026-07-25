import { splitSourcesFooter } from "../components/sources/sourceLinks";

export const DEFAULT_SPEECH_RATE = 1;

const SPEECH_MUTED_KEY = "vtp.speech_muted";

/** True when the browser exposes speech synthesis. */
export function isSpeechSynthesisSupported(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return (
    "speechSynthesis" in window &&
    typeof window.speechSynthesis?.speak === "function" &&
    typeof window.SpeechSynthesisUtterance === "function"
  );
}

/** User-facing Supervisor text without the sources footer. */
export function getSpeakableSupervisorText(responseText: string): string {
  const { body } = splitSourcesFooter(responseText ?? "");
  return body.trim();
}

export function readSpeechMutedPreference(): boolean {
  try {
    return sessionStorage.getItem(SPEECH_MUTED_KEY) === "1";
  } catch {
    return false;
  }
}

export function storeSpeechMutedPreference(muted: boolean): void {
  try {
    sessionStorage.setItem(SPEECH_MUTED_KEY, muted ? "1" : "0");
  } catch {
    // ignore quota / private mode
  }
}

/** Stop any in-progress speech. Never throws. */
export function cancelSupervisorSpeech(): void {
  if (!isSpeechSynthesisSupported()) {
    return;
  }
  try {
    window.speechSynthesis.cancel();
  } catch {
    // ignore unsupported / blocked synthesis
  }
}

function applyDefaultVoice(utterance: SpeechSynthesisUtterance): void {
  const pickVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    const voice =
      voices.find((entry) => entry.lang.startsWith("en") && entry.default) ??
      voices.find((entry) => entry.lang.startsWith("en")) ??
      voices[0];
    if (voice) {
      utterance.voice = voice;
    }
  };

  pickVoice();
  if (window.speechSynthesis.getVoices().length === 0) {
    window.speechSynthesis.onvoiceschanged = () => {
      pickVoice();
      window.speechSynthesis.onvoiceschanged = null;
    };
  }
}

/**
 * Speak a completed Supervisor response. Cancels any current utterance first.
 * Returns false when synthesis is unavailable or there is nothing to speak.
 */
export function speakSupervisorResponse(text: string): boolean {
  const speakable = getSpeakableSupervisorText(text);
  if (!speakable || !isSpeechSynthesisSupported()) {
    return false;
  }

  cancelSupervisorSpeech();

  try {
    const utterance = new SpeechSynthesisUtterance(speakable);
    utterance.rate = DEFAULT_SPEECH_RATE;
    applyDefaultVoice(utterance);
    window.speechSynthesis.speak(utterance);
    return true;
  } catch {
    return false;
  }
}
