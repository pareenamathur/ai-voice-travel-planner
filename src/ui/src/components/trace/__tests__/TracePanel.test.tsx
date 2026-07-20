import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TracePanel } from "../TracePanel";
import {
  duplicateCorrelationIds,
  emptyTrace,
  failedWorkflow,
  shuffledTimestamps,
  sparseItems,
  successfulWorkflow,
} from "./fixtures";

describe("TracePanel", () => {
  it("renders empty state when there are no trace items", () => {
    render(<TracePanel items={emptyTrace} />);

    expect(screen.getByTestId("trace-empty")).toHaveTextContent(
      "No trace events yet.",
    );
    expect(screen.getByTestId("trace-count")).toHaveTextContent("0 steps");
    expect(screen.queryByTestId("trace-step")).not.toBeInTheDocument();
  });

  it("renders a successful Supervisor → Planning → Gateway → tools → Review flow", () => {
    render(<TracePanel items={successfulWorkflow} />);

    const steps = screen.getAllByTestId("trace-step");
    expect(steps).toHaveLength(7);
    expect(screen.getByTestId("trace-count")).toHaveTextContent("7 steps");

    const agents = steps.map((step) => within(step).getByTestId("trace-agent").textContent);
    expect(agents).toEqual([
      "Supervisor",
      "Planning",
      "Gateway",
      "search_pois",
      "build_itinerary",
      "Review",
      "Supervisor",
    ]);

    for (const step of steps) {
      expect(within(step).getByTestId("trace-status")).toHaveTextContent("completed");
    }

    expect(within(steps[3]).getByTestId("trace-duration")).toHaveTextContent("820ms");
    expect(within(steps[0]).getByTestId("trace-action")).toHaveTextContent("intent=PLAN");
  });

  it("renders failed steps with a failed status badge", () => {
    render(<TracePanel items={failedWorkflow} />);

    const steps = screen.getAllByTestId("trace-step");
    expect(steps).toHaveLength(3);

    const review = steps.find((step) => step.getAttribute("data-agent") === "Review")!;
    expect(review).toHaveAttribute("data-status", "failed");
    expect(within(review).getByTestId("trace-status")).toHaveTextContent("failed");
    expect(review.className).toContain("trace-step--failed");
  });

  it("omits missing optional fields without inventing placeholders", () => {
    render(<TracePanel items={sparseItems} />);

    const step = screen.getByTestId("trace-step");
    expect(within(step).getByTestId("trace-agent")).toHaveTextContent("Gateway");
    expect(within(step).getByTestId("trace-action")).toHaveTextContent("search_pois");
    expect(within(step).getByTestId("trace-status")).toHaveTextContent("started");
    expect(within(step).queryByTestId("trace-duration")).not.toBeInTheDocument();
    expect(within(step).queryByTestId("trace-timestamp")).not.toBeInTheDocument();
    expect(within(step).queryByTestId("trace-correlation")).not.toBeInTheDocument();
  });

  it("renders steps in chronological order by timestamp", () => {
    render(<TracePanel items={shuffledTimestamps} />);

    const agents = screen
      .getAllByTestId("trace-step")
      .map((step) => within(step).getByTestId("trace-agent").textContent);

    expect(agents).toEqual(["Supervisor", "Planning", "Review"]);
  });

  it("renders all steps even when correlation_id values are duplicated", () => {
    render(<TracePanel items={duplicateCorrelationIds} />);

    const steps = screen.getAllByTestId("trace-step");
    expect(steps).toHaveLength(3);

    const correlations = screen.getAllByTestId("trace-correlation");
    expect(correlations).toHaveLength(3);
    for (const node of correlations) {
      expect(node).toHaveTextContent("same-id");
    }

    const agents = steps.map((step) => within(step).getByTestId("trace-agent").textContent);
    expect(agents).toEqual(["Supervisor", "Planning", "Supervisor"]);
  });
});
