import { useCallback, useEffect, useRef, useState } from "react";

import type { ConversationExchange } from "../api/conversationTypes";

import {
  cancelSupervisorSpeech,
  readSpeechMutedPreference,
  speakSupervisorResponse,
  storeSpeechMutedPreference,
} from "./speechSynthesis";

export interface SupervisorSpeechControls {
  muted: boolean;
  toggleMuted: () => void;
  replay: (responseText: string) => void;
}

/**
 * Auto-speak completed Supervisor responses once per exchange.
 * Manual replay always works (even when muted).
 */
export function useSupervisorSpeech(
  conversationHistory: ConversationExchange[],
): SupervisorSpeechControls {
  const [muted, setMuted] = useState(() => readSpeechMutedPreference());
  const lastAutoSpokenExchangeId = useRef<string | null>(null);

  const toggleMuted = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      storeSpeechMutedPreference(next);
      if (next) {
        cancelSupervisorSpeech();
      }
      return next;
    });
  }, []);

  const replay = useCallback((responseText: string) => {
    speakSupervisorResponse(responseText);
  }, []);

  useEffect(() => {
    if (conversationHistory.length === 0) {
      lastAutoSpokenExchangeId.current = null;
      cancelSupervisorSpeech();
      return;
    }

    const latestCompleted = [...conversationHistory]
      .reverse()
      .find((exchange) => exchange.response?.response?.trim());

    if (!latestCompleted?.response?.response) {
      return;
    }

    if (lastAutoSpokenExchangeId.current === latestCompleted.id) {
      return;
    }

    lastAutoSpokenExchangeId.current = latestCompleted.id;

    if (!muted) {
      speakSupervisorResponse(latestCompleted.response.response);
    }
  }, [conversationHistory, muted]);

  useEffect(() => () => cancelSupervisorSpeech(), []);

  return { muted, toggleMuted, replay };
}
