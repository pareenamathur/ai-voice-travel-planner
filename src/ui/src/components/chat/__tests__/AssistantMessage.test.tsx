import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AssistantMessage } from "../AssistantMessage";

describe("AssistantMessage", () => {
  it("renders clickable source links instead of plain Sources text", () => {
    render(
      <AssistantMessage
        text={"Done.\n\nSources: OpenStreetMap; Wikivoyage."}
        sourceLinks={[
          { label: "OpenStreetMap", href: "https://www.openstreetmap.org/" },
          { label: "Wikivoyage", href: "https://en.wikivoyage.org/wiki/Jaipur" },
        ]}
      />,
    );

    expect(screen.getByText("Done.")).toBeInTheDocument();
    const links = screen.getAllByTestId("source-link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "https://www.openstreetmap.org/");
    expect(links[0]).toHaveAttribute("target", "_blank");
    expect(screen.queryByText(/Sources: OpenStreetMap/)).not.toBeInTheDocument();
  });

  it("renders a replay control that invokes onReplay with the full response text", async () => {
    const user = userEvent.setup();
    const onReplay = vi.fn();

    render(
      <AssistantMessage
        text="Your itinerary is ready."
        onReplay={onReplay}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Listen to response" }));

    expect(onReplay).toHaveBeenCalledWith("Your itinerary is ready.");
  });
});
