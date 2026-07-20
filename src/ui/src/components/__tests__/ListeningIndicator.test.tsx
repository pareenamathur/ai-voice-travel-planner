import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ListeningIndicator } from "../ListeningIndicator";

describe("ListeningIndicator", () => {
  it("shows idle state when not listening", () => {
    render(<ListeningIndicator isListening={false} />);
    const indicator = screen.getByTestId("listening-indicator");
    expect(indicator).toHaveTextContent("Not listening");
    expect(indicator).toHaveAttribute("data-listening", "false");
  });

  it("shows active state when listening", () => {
    render(<ListeningIndicator isListening={true} />);
    const indicator = screen.getByTestId("listening-indicator");
    expect(indicator).toHaveTextContent("Listening…");
    expect(indicator).toHaveAttribute("data-listening", "true");
  });
});
