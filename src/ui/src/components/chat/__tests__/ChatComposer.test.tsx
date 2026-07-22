import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatComposer } from "../ChatComposer";

const mockStart = vi.fn();
const mockStop = vi.fn();
const mockReset = vi.fn();

let speechState = {
  transcript: "",
  interimTranscript: "",
  isListening: false,
};

vi.mock("../../../speech", () => ({
  useSpeechRecognition: () => ({
    startListening: mockStart,
    stopListening: mockStop,
    resetTranscript: mockReset,
    transcript: speechState.transcript,
    interimTranscript: speechState.interimTranscript,
    isListening: speechState.isListening,
    isSupported: true,
    error: null,
  }),
}));

describe("ChatComposer", () => {
  beforeEach(() => {
    speechState = { transcript: "", interimTranscript: "", isListening: false };
    mockStart.mockClear();
    mockStop.mockClear();
    mockReset.mockClear();
  });

  it("submits edited draft text without auto-send on mic stop", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(<ChatComposer onSubmitTranscript={onSubmit} />);

    const input = screen.getByTestId("composer-input");
    await user.type(input, "Suggest food in Jaipur");
    await user.click(screen.getByTestId("send-transcript"));

    expect(onSubmit).toHaveBeenCalledWith("Suggest food in Jaipur");
    expect(input).toHaveValue("");
  });

  it("allows clearing the draft before send", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(<ChatComposer onSubmitTranscript={onSubmit} />);

    const input = screen.getByTestId("composer-input");
    await user.type(input, "wrong words");
    await user.clear(input);
    expect(screen.getByTestId("send-transcript")).toBeDisabled();
  });

  it("submits the edited draft instead of the original speech transcript", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    speechState = {
      transcript: "Plan 2 day Jaipur",
      interimTranscript: "",
      isListening: true,
    };
    const { rerender } = render(<ChatComposer onSubmitTranscript={onSubmit} />);

    const input = screen.getByTestId("composer-input");
    await waitFor(() => {
      expect(input).toHaveValue("Plan 2 day Jaipur");
    });

    await user.clear(input);
    await user.type(input, "Plan 3 day Jaipur");

    speechState = {
      transcript: "Plan 2 day Jaipur",
      interimTranscript: "",
      isListening: false,
    };
    rerender(<ChatComposer onSubmitTranscript={onSubmit} />);

    expect(onSubmit).not.toHaveBeenCalled();
    expect(input).toHaveValue("Plan 3 day Jaipur");

    await user.click(screen.getByTestId("send-transcript"));
    expect(onSubmit).toHaveBeenCalledWith("Plan 3 day Jaipur");
  });

  it("does not auto-send when listening stops", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(<ChatComposer onSubmitTranscript={onSubmit} />);

    speechState = {
      transcript: "Plan Jaipur",
      interimTranscript: "",
      isListening: true,
    };
    rerender(<ChatComposer onSubmitTranscript={onSubmit} />);

    speechState = {
      transcript: "Plan Jaipur",
      interimTranscript: "",
      isListening: false,
    };
    rerender(<ChatComposer onSubmitTranscript={onSubmit} />);

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits draft on Enter", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ChatComposer onSubmitTranscript={onSubmit} />);

    const input = screen.getByTestId("composer-input");
    await user.type(input, "Hello Jaipur{Enter}");
    expect(onSubmit).toHaveBeenCalledWith("Hello Jaipur");
  });
});
