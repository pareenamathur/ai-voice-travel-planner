import { useCallback, useEffect, useRef, useState } from "react";

import { BrowserSpeechRecognitionService } from "./speechRecognition";
import type {
  SpeechRecognitionApi,
  SpeechRecognitionOptions,
  SpeechRecognitionSnapshot,
} from "./types";

const INITIAL_SNAPSHOT: SpeechRecognitionSnapshot = {
  transcript: "",
  interimTranscript: "",
  isListening: false,
  isSupported: false,
  error: null,
};

/**
 * React hook wrapping {@link BrowserSpeechRecognitionService}.
 *
 * Client-side only — does not call the Supervisor API or any cloud STT.
 */
export function useSpeechRecognition(
  options: SpeechRecognitionOptions = {},
): SpeechRecognitionApi {
  const serviceRef = useRef<BrowserSpeechRecognitionService | null>(null);
  const [snapshot, setSnapshot] = useState<SpeechRecognitionSnapshot>(INITIAL_SNAPSHOT);

  // Recreate the service when recognition options change.
  const { lang, continuous, SpeechRecognition } = options;

  useEffect(() => {
    const service = new BrowserSpeechRecognitionService({
      lang,
      continuous,
      SpeechRecognition,
    });
    serviceRef.current = service;
    return service.subscribe(setSnapshot);
  }, [lang, continuous, SpeechRecognition]);

  const startListening = useCallback(() => {
    serviceRef.current?.startListening();
  }, []);

  const stopListening = useCallback(() => {
    serviceRef.current?.stopListening();
  }, []);

  const resetTranscript = useCallback(() => {
    serviceRef.current?.resetTranscript();
  }, []);

  return {
    ...snapshot,
    startListening,
    stopListening,
    resetTranscript,
  };
}
