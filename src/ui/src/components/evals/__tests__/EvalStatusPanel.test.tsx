import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvalStatusPanel } from "../EvalStatusPanel";
import {
  allPassReport,
  backendEntriesReport,
  emptyReport,
  failAfterRegenReport,
  mixedPassFailReport,
  sparseReport,
  unknownNamesReport,
  warningsReport,
} from "./fixtures";

describe("EvalStatusPanel", () => {
  it("renders empty state when there are no evaluations", () => {
    render(<EvalStatusPanel report={emptyReport} />);

    expect(screen.getByTestId("eval-empty")).toHaveTextContent("No evaluations yet.");
    expect(screen.queryByTestId("eval-summary")).not.toBeInTheDocument();
    expect(screen.queryByTestId("eval-card")).not.toBeInTheDocument();
    expect(screen.queryByTestId("eval-regen-indicator")).not.toBeInTheDocument();
    expect(screen.queryByTestId("eval-approval-warning")).not.toBeInTheDocument();
  });

  it("renders all PASS evaluations and summary counts", () => {
    render(<EvalStatusPanel report={allPassReport} itineraryApproved />);

    expect(screen.getByTestId("eval-overall-verdict")).toHaveTextContent("Overall: PASS");
    expect(screen.getByTestId("eval-count-total")).toHaveTextContent("Total: 2");
    expect(screen.getByTestId("eval-count-passed")).toHaveTextContent("Passed: 2");
    expect(screen.getByTestId("eval-count-failed")).toHaveTextContent("Failed: 0");
    expect(screen.getByTestId("eval-count-warnings")).toHaveTextContent("Warnings: 0");
    expect(screen.queryByTestId("eval-approval-warning")).not.toBeInTheDocument();

    const cards = screen.getAllByTestId("eval-card");
    expect(cards).toHaveLength(2);
    for (const card of cards) {
      expect(card).toHaveAttribute("data-eval-status", "PASS");
      expect(within(card).getByTestId("eval-status")).toHaveTextContent("PASS");
    }

    expect(within(cards[0]).getByTestId("eval-score")).toHaveTextContent("Score: 1");
    expect(within(cards[0]).getByTestId("eval-message")).toHaveTextContent(
      "Daily windows respected",
    );
    expect(screen.getByTestId("eval-report-timestamp")).toHaveTextContent(
      "2026-04-01T10:00:00.000Z",
    );
  });

  it("renders mixed PASS / FAIL results", () => {
    render(<EvalStatusPanel report={mixedPassFailReport} itineraryApproved={false} />);

    expect(screen.getByTestId("eval-overall-verdict")).toHaveTextContent("Overall: FAIL");
    expect(screen.getByTestId("eval-count-passed")).toHaveTextContent("Passed: 1");
    expect(screen.getByTestId("eval-count-failed")).toHaveTextContent("Failed: 1");
    expect(screen.getByTestId("eval-approval-warning")).toHaveTextContent(
      /did not pass all quality checks/i,
    );

    const failCard = screen
      .getAllByTestId("eval-card")
      .find((card) => card.getAttribute("data-eval-name") === "Grounding")!;
    expect(failCard).toHaveAttribute("data-eval-status", "FAIL");
    expect(failCard.className).toContain("eval-card--fail");
    expect(within(failCard).getByTestId("eval-message")).toHaveTextContent(
      "Missing osm_id on Day 2 lunch",
    );
  });

  it("renders PASS_WITH_WARNINGS", () => {
    render(<EvalStatusPanel report={warningsReport} itineraryApproved />);

    expect(screen.getByTestId("eval-overall-verdict")).toHaveTextContent(
      "Overall: PASS WITH WARNINGS",
    );
    expect(screen.getByTestId("eval-count-warnings")).toHaveTextContent("Warnings: 1");
    expect(screen.getByTestId("eval-count-passed")).toHaveTextContent("Passed: 1");
    expect(screen.getByTestId("eval-count-failed")).toHaveTextContent("Failed: 0");
    expect(screen.queryByTestId("eval-approval-warning")).not.toBeInTheDocument();

    const warningCard = screen
      .getAllByTestId("eval-card")
      .find((card) => card.getAttribute("data-eval-name") === "Grounding")!;
    expect(warningCard).toHaveAttribute("data-eval-status", "PASS_WITH_WARNINGS");
    expect(warningCard.className).toContain("eval-card--warning");
  });

  it("shows regeneration indicator and final FAIL outcome", () => {
    render(
      <EvalStatusPanel report={failAfterRegenReport} itineraryApproved={false} />,
    );

    expect(screen.getByTestId("eval-regen-indicator")).toHaveTextContent(
      /regenerated once/i,
    );
    expect(screen.getByTestId("eval-regen-indicator")).toHaveTextContent(
      /final review outcome/i,
    );
    expect(screen.getByTestId("eval-overall-verdict")).toHaveTextContent("Overall: FAIL");
    expect(screen.getByTestId("eval-approval-warning")).toBeInTheDocument();

    const feasibility = screen
      .getAllByTestId("eval-card")
      .find((card) => card.getAttribute("data-eval-name") === "feasibility")!;
    expect(within(feasibility).getByTestId("eval-message")).toHaveTextContent(
      /840 min exceeds/i,
    );
  });

  it("omits approval warning when itineraryApproved is omitted", () => {
    render(<EvalStatusPanel report={mixedPassFailReport} />);
    expect(screen.queryByTestId("eval-approval-warning")).not.toBeInTheDocument();
  });

  it("omits missing optional fields without inventing placeholders", () => {
    render(<EvalStatusPanel report={sparseReport} />);

    const card = screen.getByTestId("eval-card");
    expect(within(card).getByTestId("eval-name")).toHaveTextContent("Feasibility");
    expect(within(card).queryByTestId("eval-score")).not.toBeInTheDocument();
    expect(within(card).queryByTestId("eval-message")).not.toBeInTheDocument();
    expect(within(card).queryByTestId("eval-timestamp")).not.toBeInTheDocument();
    expect(screen.queryByTestId("eval-report-timestamp")).not.toBeInTheDocument();
  });

  it("supports unknown evaluation names", () => {
    render(<EvalStatusPanel report={unknownNamesReport} />);

    const cards = screen.getAllByTestId("eval-card");
    expect(cards[0]).toHaveAttribute("data-eval-name", "CustomFutureEval");
    expect(within(cards[0]).getByTestId("eval-name")).toHaveTextContent(
      "CustomFutureEval",
    );
    expect(within(cards[1]).getByTestId("eval-name")).toHaveTextContent(
      "Unknown evaluation",
    );
    expect(screen.getByTestId("eval-count-total")).toHaveTextContent("Total: 2");
  });

  it("accepts backend EvalReport.entries shape", () => {
    render(<EvalStatusPanel report={backendEntriesReport} />);

    expect(screen.getByTestId("eval-overall-verdict")).toHaveTextContent("Overall: FAIL");
    expect(screen.getByTestId("eval-count-total")).toHaveTextContent("Total: 2");
    expect(screen.getByTestId("eval-count-passed")).toHaveTextContent("Passed: 1");
    expect(screen.getByTestId("eval-count-failed")).toHaveTextContent("Failed: 1");

    const grounding = screen
      .getAllByTestId("eval-card")
      .find((card) => card.getAttribute("data-eval-name") === "grounding")!;
    expect(within(grounding).getByTestId("eval-message")).toHaveTextContent(
      "missing citation; invalid osm id",
    );
  });
});
