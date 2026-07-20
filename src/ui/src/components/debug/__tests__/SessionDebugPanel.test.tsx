import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SessionDebugPanel } from "../SessionDebugPanel";

describe("SessionDebugPanel", () => {
  it("renders session debug fields", () => {
    render(
      <SessionDebugPanel
        sessionId="sess-123"
        conversationPhase="confirm"
        intent="confirm"
        taskMessage={null}
        itineraryApproved={false}
        confirmRejectedWarning={null}
      />,
    );

    expect(screen.getByTestId("debug-session-id")).toHaveTextContent("sess-123");
    expect(screen.getByTestId("debug-conversation-phase")).toHaveTextContent("confirm");
    expect(screen.getByTestId("debug-intent")).toHaveTextContent("confirm");
    expect(screen.getByTestId("debug-itinerary-approved")).toHaveTextContent("false");
    expect(screen.getByTestId("debug-task-message")).toHaveTextContent("null");
    expect(screen.getByTestId("debug-task-message-null")).toHaveTextContent(
      /task_message is null/i,
    );
  });

  it("shows confirm rejected warning", () => {
    render(
      <SessionDebugPanel
        sessionId="sess-123"
        conversationPhase="confirm"
        intent="confirm"
        taskMessage={null}
        itineraryApproved={false}
        confirmRejectedWarning="Confirmation was not accepted by the backend."
      />,
    );

    expect(screen.getByTestId("confirm-rejected-warning")).toHaveTextContent(
      "Confirmation was not accepted by the backend.",
    );
  });

  it("renders task_message JSON when present", () => {
    render(
      <SessionDebugPanel
        sessionId="sess-123"
        conversationPhase="active"
        intent="plan"
        taskMessage={{ task_type: "plan", session_id: "sess-123" }}
        itineraryApproved={true}
        confirmRejectedWarning={null}
      />,
    );

    expect(screen.getByTestId("debug-task-message")).toHaveTextContent('"task_type": "plan"');
    expect(screen.queryByTestId("debug-task-message-null")).not.toBeInTheDocument();
  });
});
