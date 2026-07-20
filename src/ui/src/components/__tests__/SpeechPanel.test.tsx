import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SpeechPanel } from "../SpeechPanel";
import { MockSpeechRecognition } from "./mockSpeechRecognition";

describe("SpeechPanel", () => {
  it("starts and stops listening via microphone and explicit buttons", () => {
    render(<SpeechPanel speechOptions={{ SpeechRecognition: MockSpeechRecognition }} />);

    expect(screen.getByTestId("listening-indicator")).toHaveAttribute(
      "data-listening",
      "false",
    );

    fireEvent.click(screen.getByTestId("start-listening"));
    expect(screen.getByTestId("listening-indicator")).toHaveAttribute(
      "data-listening",
      "true",
    );
    expect(screen.getByTestId("microphone-button")).toHaveAttribute(
      "data-listening",
      "true",
    );

    fireEvent.click(screen.getByTestId("stop-listening"));
    expect(screen.getByTestId("listening-indicator")).toHaveAttribute(
      "data-listening",
      "false",
    );
  });

  it("toggles listening with the microphone button", () => {
    render(<SpeechPanel speechOptions={{ SpeechRecognition: MockSpeechRecognition }} />);

    fireEvent.click(screen.getByTestId("microphone-button"));
    expect(screen.getByTestId("microphone-button")).toHaveAttribute(
      "data-listening",
      "true",
    );

    fireEvent.click(screen.getByTestId("microphone-button"));
    expect(screen.getByTestId("microphone-button")).toHaveAttribute(
      "data-listening",
      "false",
    );
  });

  it("renders live final and interim transcripts", () => {
    render(<SpeechPanel speechOptions={{ SpeechRecognition: MockSpeechRecognition }} />);

    fireEvent.click(screen.getByTestId("start-listening"));

    act(() => {
      MockSpeechRecognition.last!.emitParts([
        { transcript: "Plan a trip", isFinal: false },
      ]);
    });
    expect(screen.getByTestId("interim-transcript")).toHaveTextContent("Plan a trip");
    expect(screen.getByTestId("final-transcript")).toHaveTextContent(
      "Speak to see your transcript here.",
    );

    act(() => {
      MockSpeechRecognition.last!.emitParts([
        { transcript: "Plan a trip to Jaipur", isFinal: true },
      ]);
    });
    expect(screen.getByTestId("final-transcript")).toHaveTextContent(
      "Plan a trip to Jaipur",
    );
    expect(screen.getByTestId("interim-transcript")).toHaveTextContent("—");
  });

  it("shows unsupported browser message and disables controls", () => {
    render(<SpeechPanel speechOptions={{ SpeechRecognition: null }} />);

    expect(screen.getByTestId("unsupported-message")).toHaveTextContent(
      /not supported/i,
    );
    expect(screen.getByTestId("microphone-button")).toBeDisabled();
    expect(screen.getByTestId("start-listening")).toBeDisabled();
    expect(screen.getByTestId("stop-listening")).toBeDisabled();
  });

  it("renders recognition errors", () => {
    render(<SpeechPanel speechOptions={{ SpeechRecognition: MockSpeechRecognition }} />);

    fireEvent.click(screen.getByTestId("start-listening"));
    act(() => {
      MockSpeechRecognition.last!.emitError("not-allowed");
    });

    expect(screen.getByTestId("error-message")).toHaveTextContent("not-allowed");
  });

  it("keeps transcript after a failed Supervisor submit", async () => {
    const onSubmitTranscript = vi
      .fn()
      .mockRejectedValue(new Error("Supervisor unavailable"));

    render(
      <SpeechPanel
        speechOptions={{ SpeechRecognition: MockSpeechRecognition }}
        onSubmitTranscript={onSubmitTranscript}
      />,
    );

    fireEvent.click(screen.getByTestId("start-listening"));
    act(() => {
      MockSpeechRecognition.last!.emitParts([
        { transcript: "Plan a trip to Jaipur", isFinal: true },
      ]);
    });

    fireEvent.click(screen.getByTestId("send-transcript"));

    await waitFor(() => {
      expect(onSubmitTranscript).toHaveBeenCalledWith("Plan a trip to Jaipur");
    });
    expect(screen.getByTestId("final-transcript")).toHaveTextContent(
      "Plan a trip to Jaipur",
    );
  });

  it("clears transcript after a successful Supervisor submit", async () => {
    const onSubmitTranscript = vi.fn().mockResolvedValue(undefined);

    render(
      <SpeechPanel
        speechOptions={{ SpeechRecognition: MockSpeechRecognition }}
        onSubmitTranscript={onSubmitTranscript}
      />,
    );

    fireEvent.click(screen.getByTestId("start-listening"));
    act(() => {
      MockSpeechRecognition.last!.emitParts([
        { transcript: "Plan a trip to Jaipur", isFinal: true },
      ]);
    });

    fireEvent.click(screen.getByTestId("send-transcript"));

    await waitFor(() => {
      expect(screen.getByTestId("final-transcript")).toHaveTextContent(
        "Speak to see your transcript here.",
      );
    });
  });
});
