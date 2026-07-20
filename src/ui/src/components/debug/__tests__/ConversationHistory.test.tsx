import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ConversationExchange } from "../../../api/conversationTypes";
import { ConversationHistory } from "../ConversationHistory";

const sampleExchange: ConversationExchange = {
  id: "ex-1",
  userMessage: "Plan 2 days in Jaipur",
  requestedAt: "2026-04-01T10:00:00.000Z",
  request: { session_id: null, message: "Plan 2 days in Jaipur" },
  respondedAt: "2026-04-01T10:00:01.000Z",
  response: {
    session_id: "sess-abc",
    correlation_id: "corr-1",
    response: "I understood Jaipur. How many days?",
    conversation_phase: "intake",
    itinerary_approved: false,
    intent: "clarify",
  },
};

describe("ConversationHistory", () => {
  it("shows empty state before any turns", () => {
    render(<ConversationHistory exchanges={[]} />);
    expect(screen.getByTestId("conversation-empty")).toHaveTextContent(/No messages yet/i);
  });

  it("renders user message, API request/response, and supervisor reply", () => {
    render(<ConversationHistory exchanges={[sampleExchange]} />);

    expect(screen.getByTestId("conversation-count")).toHaveTextContent("1 turn");
    expect(screen.getByTestId("conversation-user-message")).toHaveTextContent(
      "Plan 2 days in Jaipur",
    );
    expect(screen.getByTestId("conversation-api-request")).toHaveTextContent(
      "POST /api/session/message (request)",
    );
    expect(screen.getByTestId("conversation-api-request")).toHaveTextContent(
      '"message": "Plan 2 days in Jaipur"',
    );
    expect(screen.getByTestId("conversation-api-response")).toHaveTextContent(
      '"intent": "clarify"',
    );
    expect(screen.getByTestId("conversation-supervisor-message")).toHaveTextContent(
      "I understood Jaipur. How many days?",
    );
  });

  it("accumulates multiple turns without replacing earlier messages", () => {
    const second: ConversationExchange = {
      id: "ex-2",
      userMessage: "yes",
      requestedAt: "2026-04-01T10:01:00.000Z",
      request: { session_id: "sess-abc", message: "yes" },
      respondedAt: "2026-04-01T10:01:01.000Z",
      response: {
        session_id: "sess-abc",
        correlation_id: "corr-2",
        response: "Your itinerary is ready.",
        conversation_phase: "active",
        itinerary_approved: true,
        intent: "plan",
        task_message: { task_type: "plan" },
      },
    };

    render(<ConversationHistory exchanges={[sampleExchange, second]} />);

    expect(screen.getByTestId("conversation-count")).toHaveTextContent("2 turns");
    expect(screen.getAllByTestId("conversation-user-message")).toHaveLength(2);
    expect(screen.getAllByTestId("conversation-supervisor-message")).toHaveLength(2);
    expect(screen.getByText("Plan 2 days in Jaipur")).toBeInTheDocument();
    expect(screen.getByText("yes")).toBeInTheDocument();
    expect(screen.getByText("Your itinerary is ready.")).toBeInTheDocument();
  });

  it("shows API error on failed exchange", () => {
    const failed: ConversationExchange = {
      id: "ex-fail",
      userMessage: "yes",
      requestedAt: "2026-04-01T10:02:00.000Z",
      request: { session_id: "sess-abc", message: "yes" },
      error: "Supervisor unavailable",
    };

    render(<ConversationHistory exchanges={[failed]} />);
    expect(screen.getByTestId("conversation-api-error")).toHaveTextContent(
      "Supervisor unavailable",
    );
  });
});
