import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourcesPanel } from "../SourcesPanel";
import { collectCitations } from "../collectCitations";
import {
  duplicateCitationsItinerary,
  emptyCitationsItinerary,
  multipleCitationsItinerary,
  sparseCitationsItinerary,
} from "./fixtures";

describe("SourcesPanel", () => {
  it("renders empty state when there are no citations", () => {
    render(<SourcesPanel itinerary={emptyCitationsItinerary} />);

    expect(screen.getByTestId("sources-empty")).toHaveTextContent("No sources yet.");
    expect(screen.getByTestId("sources-count")).toHaveTextContent("0 sources");
    expect(screen.queryByTestId("citation-card")).not.toBeInTheDocument();
  });

  it("renders multiple citations from itinerary and activities", () => {
    render(<SourcesPanel itinerary={multipleCitationsItinerary} />);

    const cards = screen.getAllByTestId("citation-card");
    expect(cards).toHaveLength(3);
    expect(screen.getByTestId("sources-count")).toHaveTextContent("3 sources");

    expect(cards[0]).toHaveAttribute(
      "data-citation-id",
      "jaipur:wikivoyage#see#0001",
    );
    expect(within(cards[0]).getByTestId("citation-label")).toHaveTextContent(
      "Wikivoyage — Jaipur",
    );
    expect(within(cards[0]).queryByTestId("citation-id")).not.toBeInTheDocument();
    expect(within(cards[0]).getByTestId("citation-section")).toHaveTextContent(
      "See",
    );

    expect(cards[1]).toHaveAttribute(
      "data-citation-id",
      "jaipur:wikipedia#tourism#0016",
    );
    expect(within(cards[1]).getByTestId("citation-label")).toHaveTextContent(
      "Wikipedia tourism",
    );

    expect(cards[2]).toHaveAttribute("data-citation-id", "osm:node/123");
    expect(within(cards[2]).getByTestId("citation-label")).toHaveTextContent(
      "OSM node/123",
    );
  });

  it("deduplicates citations that share the same citation_id", () => {
    render(<SourcesPanel itinerary={duplicateCitationsItinerary} />);

    const cards = screen.getAllByTestId("citation-card");
    expect(cards).toHaveLength(2);
    expect(collectCitations(duplicateCitationsItinerary)).toHaveLength(2);

    expect(cards[0]).toHaveAttribute(
      "data-citation-id",
      "jaipur:wikivoyage#see#0001",
    );
    expect(within(cards[0]).getByTestId("citation-label")).toHaveTextContent(
      "Top-level copy",
    );
    expect(screen.queryByText("Activity copy — should be dropped")).not.toBeInTheDocument();

    expect(cards[1]).toHaveAttribute(
      "data-citation-id",
      "jaipur:wikipedia#history#0003",
    );
  });

  it("handles missing optional metadata without inventing values", () => {
    render(<SourcesPanel itinerary={sparseCitationsItinerary} />);

    const card = screen.getByTestId("citation-card");
    // Friendly label is derived; raw citation_id is not shown to users.
    expect(within(card).getByTestId("citation-label")).toHaveTextContent(
      "wikivoyage",
    );
    expect(within(card).queryByTestId("citation-id")).not.toBeInTheDocument();
    expect(within(card).queryByTestId("citation-section")).not.toBeInTheDocument();
    expect(within(card).queryByTestId("citation-url")).not.toBeInTheDocument();
  });

  it("renders clickable source URLs that open in a new tab", () => {
    render(<SourcesPanel itinerary={multipleCitationsItinerary} />);

    const urls = screen.getAllByTestId("citation-url");
    expect(urls.length).toBeGreaterThanOrEqual(2);

    const first = urls[0];
    expect(first).toHaveAttribute("href", "https://en.wikivoyage.org/wiki/Jaipur");
    expect(first).toHaveAttribute("target", "_blank");
    expect(first).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(first.tagName).toBe("A");
  });

  it("accepts an explicit citations prop without an itinerary", () => {
    render(
      <SourcesPanel
        citations={[
          {
            citation_id: "only-prop",
            source_url: "https://example.com/ref",
            section: "Intro",
          },
          {
            citation_id: "only-prop",
            source_url: "https://example.com/dup",
          },
        ]}
      />,
    );

    expect(screen.getAllByTestId("citation-card")).toHaveLength(1);
    expect(screen.getByTestId("citation-url")).toHaveAttribute(
      "href",
      "https://example.com/ref",
    );
  });
});
