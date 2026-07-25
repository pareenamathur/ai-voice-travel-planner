import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ConversationExchange } from "../../api/conversationTypes";
import {
  installMockSpeechSynthesis,
  removeMockSpeechSynthesis,
} from "../../components/__tests__/mockSpeechSynthesis";
import {
  cancelSupervisorSpeech,
  getSpeakableSupervisorText,
  speakSupervisorResponse,
} from "../speechSynthesis";
import { useSupervisorSpeech } from "../useSupervisorSpeech";

function exchange(
  id: string,
  responseText: string,
  overrides: Partial<ConversationExchange> = {},
): ConversationExchange {
  return {
    id,
    userMessage: "Plan Jaipur",
    requestedAt: "2026-01-01T00:00:00.000Z",
    request: { message: "Plan Jaipur", session_id: null },
    respondedAt: "2026-01-01T00:00:01.000Z",
    response: {
      session_id: "sess-1",
      correlation_id: `corr-${id}`,
      response: responseText,
      conversation_phase: "active",
      itinerary_approved: false,
      intent: "clarify",
    },
    ...overrides,
  };
}

describe("speechSynthesis", () => {
  let mock: ReturnType<typeof installMockSpeechSynthesis>;

  beforeEach(() => {
    mock = installMockSpeechSynthesis();
    sessionStorage.clear();
  });

  afterEach(() => {
    removeMockSpeechSynthesis();
    sessionStorage.clear();
  });

  it("strips the sources footer from speakable text", () => {
    expect(
      getSpeakableSupervisorText("Your trip is ready.\n\nSources: OpenStreetMap."),
    ).toBe("Your trip is ready.");
  });

  it("cancels before speaking a new response", () => {
    speakSupervisorResponse("First reply.");
    speakSupervisorResponse("Second reply.");

    expect(mock.cancel).toHaveBeenCalled();
    expect(mock.speak).toHaveBeenCalledTimes(2);
    const utterance = mock.speak.mock.calls[1][0] as SpeechSynthesisUtterance;
    expect(utterance.text).toBe("Second reply.");
  });

  it("does not throw when speech synthesis is unavailable", () => {
    removeMockSpeechSynthesis();
    expect(speakSupervisorResponse("Hello")).toBe(false);
    expect(() => cancelSupervisorSpeech()).not.toThrow();
  });
});

describe("useSupervisorSpeech", () => {
  let mock: ReturnType<typeof installMockSpeechSynthesis>;

  beforeEach(() => {
    mock = installMockSpeechSynthesis();
    sessionStorage.clear();
  });

  afterEach(() => {
    removeMockSpeechSynthesis();
    sessionStorage.clear();
  });

  it("speaks a completed Supervisor response once", () => {
    const history = [exchange("turn-1", "Your Jaipur itinerary is ready.")];

    renderHook(() => useSupervisorSpeech(history));

    expect(mock.speak).toHaveBeenCalledTimes(1);
    const utterance = mock.speak.mock.calls[0][0] as SpeechSynthesisUtterance;
    expect(utterance.text).toBe("Your Jaipur itinerary is ready.");
  });

  it("does not speak again on rerender with the same exchange", () => {
    const history = [exchange("turn-1", "Your Jaipur itinerary is ready.")];
    const { rerender } = renderHook(
      ({ exchanges }) => useSupervisorSpeech(exchanges),
      { initialProps: { exchanges: history } },
    );

    expect(mock.speak).toHaveBeenCalledTimes(1);

    rerender({ exchanges: [...history] });
    rerender({ exchanges: [...history] });

    expect(mock.speak).toHaveBeenCalledTimes(1);
  });

  it("does not auto-speak when muted", () => {
    sessionStorage.setItem("vtp.speech_muted", "1");
    const history = [exchange("turn-1", "Muted reply should stay silent.")];

    renderHook(() => useSupervisorSpeech(history));

    expect(mock.speak).not.toHaveBeenCalled();
  });

  it("replay manually invokes speech even when muted", () => {
    sessionStorage.setItem("vtp.speech_muted", "1");
    const history = [exchange("turn-1", "Replay me later.")];
    const { result } = renderHook(() => useSupervisorSpeech(history));

    expect(mock.speak).not.toHaveBeenCalled();

    act(() => {
      result.current.replay("Replay me later.");
    });

    expect(mock.speak).toHaveBeenCalledTimes(1);
  });

  it("cancels previous speech when a new response arrives", () => {
    const first = exchange("turn-1", "First reply.");
    const { rerender } = renderHook(
      ({ exchanges }) => useSupervisorSpeech(exchanges),
      { initialProps: { exchanges: [first] } },
    );

    expect(mock.speak).toHaveBeenCalledTimes(1);

    const second = exchange("turn-2", "Second reply.");
    rerender({ exchanges: [first, second] });

    expect(mock.cancel).toHaveBeenCalled();
    expect(mock.speak).toHaveBeenCalledTimes(2);
  });

  it("keeps the app usable when speech synthesis is unsupported", () => {
    removeMockSpeechSynthesis();
    const history = [exchange("turn-1", "Silent mode only.")];

    expect(() => renderHook(() => useSupervisorSpeech(history))).not.toThrow();
  });
});
