import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MicrophoneButton } from "../MicrophoneButton";

describe("MicrophoneButton", () => {
  it("calls onToggle when clicked and reflects listening state", () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <MicrophoneButton isListening={false} onToggle={onToggle} />,
    );

    const button = screen.getByTestId("microphone-button");
    expect(button).toHaveAttribute("data-listening", "false");
    expect(button).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);

    rerender(<MicrophoneButton isListening={true} onToggle={onToggle} />);
    expect(screen.getByTestId("microphone-button")).toHaveAttribute(
      "data-listening",
      "true",
    );
    expect(screen.getByTestId("microphone-button")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("does not call onToggle when disabled", () => {
    const onToggle = vi.fn();
    render(<MicrophoneButton isListening={false} disabled onToggle={onToggle} />);
    fireEvent.click(screen.getByTestId("microphone-button"));
    expect(onToggle).not.toHaveBeenCalled();
  });
});
