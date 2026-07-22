import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatThread } from "../ChatThread";

describe("ChatThread", () => {
  it("shows Jaipur-only starter prompts (no unsupported cities)", () => {
    render(
      <ChatThread
        exchanges={[]}
        loading={false}
        itineraryApproved={false}
        onSuggestionSelect={() => undefined}
      />,
    );

    const suggestions = screen.getByTestId("chat-suggestions");
    const text = suggestions.textContent || "";
    expect(text.toLowerCase()).toContain("jaipur");
    expect(text.toLowerCase()).not.toContain("barcelona");
    expect(text.toLowerCase()).not.toContain("singapore");
    expect(text.toLowerCase()).not.toContain("tokyo");
  });
});
