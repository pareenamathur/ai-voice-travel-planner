import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ItineraryView } from "../ItineraryView";
import { sortActivitiesChronologically } from "../ordering";
import {
  emptyItinerary,
  multiDayItinerary,
  oneDayItinerary,
  schemaCompatibleItinerary,
  sparseOptionalFieldsItinerary,
} from "./fixtures";

describe("ItineraryView", () => {
  it("renders empty itinerary state when itinerary prop is null", () => {
    render(<ItineraryView itinerary={null} />);
    expect(screen.getByTestId("itinerary-empty")).toHaveTextContent(
      "No activities scheduled.",
    );
  });

  it("renders empty itinerary state when there are no days", () => {
    render(<ItineraryView itinerary={emptyItinerary} />);

    expect(screen.getByTestId("itinerary-city")).toHaveTextContent("jaipur");
    expect(screen.getByTestId("itinerary-total-days")).toHaveTextContent("2 days");
    expect(screen.getByTestId("itinerary-empty")).toHaveTextContent(
      "No activities scheduled.",
    );
    expect(screen.queryByTestId("day-card")).not.toBeInTheDocument();
  });

  it("renders a one-day itinerary with activities and travel", () => {
    render(<ItineraryView itinerary={oneDayItinerary} />);

    expect(screen.getByTestId("itinerary-city")).toHaveTextContent("jaipur");
    expect(screen.getByTestId("itinerary-total-days")).toHaveTextContent("1 day");

    const day = screen.getByTestId("day-card");
    expect(day).toHaveAttribute("data-day-number", "1");
    expect(within(day).getByTestId("day-date")).toHaveTextContent("2026-04-01");
    expect(within(day).getByTestId("day-notes")).toHaveTextContent("Arrival day");

    const activities = within(day).getAllByTestId("activity-card");
    expect(activities).toHaveLength(2);
    expect(activities[0]).toHaveTextContent("City Palace");
    expect(activities[1]).toHaveTextContent("Lunch near Hawa Mahal");

    expect(within(day).getByTestId("travel-segment")).toBeInTheDocument();
    expect(within(day).getByTestId("travel-minutes")).toHaveTextContent("15 min");
    expect(within(day).getByTestId("transport-mode")).toHaveTextContent("walk");
  });

  it("renders multiple days in day_number order", () => {
    render(<ItineraryView itinerary={multiDayItinerary} />);

    const days = screen.getAllByTestId("day-card");
    expect(days).toHaveLength(3);
    expect(days[0]).toHaveAttribute("data-day-number", "1");
    expect(days[1]).toHaveAttribute("data-day-number", "2");
    expect(days[2]).toHaveAttribute("data-day-number", "3");
    expect(screen.getByTestId("itinerary-total-days")).toHaveTextContent("3 days");
  });

  it("orders activities chronologically by start_time", () => {
    render(<ItineraryView itinerary={multiDayItinerary} />);

    const day2 = screen
      .getAllByTestId("day-card")
      .find((node) => node.getAttribute("data-day-number") === "2")!;

    const activities = within(day2).getAllByTestId("activity-card");
    expect(activities[0]).toHaveAttribute("data-activity-id", "d2-a1");
    expect(activities[0]).toHaveTextContent("Morning market");
    expect(activities[1]).toHaveAttribute("data-activity-id", "d2-a2");
    expect(activities[1]).toHaveTextContent("Amber Fort");

    const sorted = sortActivitiesChronologically(
      multiDayItinerary.days![0].activities!,
    );
    expect(sorted.map((a) => a.id)).toEqual(["d2-a1", "d2-a2"]);
  });

  it("renders travel segments between chronologically adjacent activities", () => {
    render(<ItineraryView itinerary={multiDayItinerary} />);

    const day2 = screen
      .getAllByTestId("day-card")
      .find((node) => node.getAttribute("data-day-number") === "2")!;

    const travel = within(day2).getByTestId("travel-segment");
    expect(travel).toHaveAttribute("data-from", "d2-a1");
    expect(travel).toHaveAttribute("data-to", "d2-a2");
    expect(within(day2).getByTestId("travel-minutes")).toHaveTextContent("40 min");
    expect(within(day2).getByTestId("transport-mode")).toHaveTextContent("drive");
  });

  it("shows empty state for days with no activities", () => {
    render(<ItineraryView itinerary={multiDayItinerary} />);

    const day3 = screen
      .getAllByTestId("day-card")
      .find((node) => node.getAttribute("data-day-number") === "3")!;

    expect(within(day3).getByTestId("day-empty")).toHaveTextContent(
      "No activities scheduled.",
    );
    expect(within(day3).queryByTestId("activity-card")).not.toBeInTheDocument();
  });

  it("omits missing optional fields without inventing placeholders", () => {
    render(<ItineraryView itinerary={sparseOptionalFieldsItinerary} />);

    const card = screen.getByTestId("activity-card");
    expect(card).toHaveTextContent("Open evening stroll");
    expect(within(card).queryByTestId("activity-time")).not.toBeInTheDocument();
    expect(within(card).queryByTestId("activity-duration")).not.toBeInTheDocument();
    expect(within(card).queryByTestId("activity-category")).not.toBeInTheDocument();
    expect(within(card).queryByTestId("activity-notes")).not.toBeInTheDocument();
    expect(screen.queryByTestId("day-date")).not.toBeInTheDocument();
    expect(screen.queryByTestId("day-notes")).not.toBeInTheDocument();
  });

  it("is compatible with the shared Python SAMPLE_ITINERARY shape", () => {
    render(<ItineraryView itinerary={schemaCompatibleItinerary} />);

    expect(screen.getByTestId("itinerary-city")).toHaveTextContent("jaipur");
    expect(screen.getByTestId("itinerary-total-days")).toHaveTextContent("2 days");

    const days = screen.getAllByTestId("day-card");
    expect(days).toHaveLength(2);

    const day1 = days[0];
    const firstActivity = within(day1).getAllByTestId("activity-card")[0];
    expect(within(day1).getByText("City Palace")).toBeInTheDocument();
    expect(within(firstActivity).getByTestId("activity-duration")).toHaveTextContent(
      "2h",
    );
    expect(within(firstActivity).getByTestId("activity-category")).toHaveTextContent(
      "culture",
    );
    expect(within(firstActivity).getByTestId("activity-notes")).toHaveTextContent(
      "Buy combo ticket",
    );
    expect(within(day1).getByTestId("travel-notes")).toHaveTextContent(
      "Short walk through old city",
    );

    const day2 = days[1];
    expect(within(day2).getByTestId("day-empty")).toHaveTextContent(
      "No activities scheduled.",
    );

    // Schema extras exist on the object but are not required UI fields for Task 3.
    expect(schemaCompatibleItinerary.poi_registry?.[0]?.poi_id).toBe("node/123");
    expect(schemaCompatibleItinerary.citations?.[0]?.citation_id).toContain(
      "wikivoyage",
    );
    expect(schemaCompatibleItinerary.traveler_constraints?.pace).toBe("relaxed");
    expect(schemaCompatibleItinerary.metadata?.schema_version).toBe("1.0");
  });
});
