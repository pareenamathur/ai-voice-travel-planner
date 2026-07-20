import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TranscriptView } from "../TranscriptView";

describe("TranscriptView", () => {
  it("renders finalized transcript text", () => {
    render(
      <TranscriptView transcript="Plan a 3-day trip to Jaipur" interimTranscript="" />,
    );
    expect(screen.getByTestId("final-transcript")).toHaveTextContent(
      "Plan a 3-day trip to Jaipur",
    );
  });

  it("renders interim transcript distinctly from final", () => {
    render(
      <TranscriptView
        transcript="Plan a trip"
        interimTranscript="to the Pink City"
      />,
    );

    const finalNode = screen.getByTestId("final-transcript");
    const interimNode = screen.getByTestId("interim-transcript");

    expect(finalNode).toHaveTextContent("Plan a trip");
    expect(interimNode).toHaveTextContent("to the Pink City");
    expect(interimNode.className).toContain("transcript-view__interim");
    expect(finalNode.className).toContain("transcript-view__final");
    expect(interimNode.className).not.toEqual(finalNode.className);
  });

  it("shows placeholders when empty", () => {
    render(<TranscriptView transcript="" interimTranscript="" />);
    expect(screen.getByTestId("final-transcript")).toHaveTextContent(
      "Speak to see your transcript here.",
    );
    expect(screen.getByTestId("interim-transcript")).toHaveTextContent("—");
  });
});
