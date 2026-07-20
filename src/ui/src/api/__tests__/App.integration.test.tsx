import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { useSupervisorSession } from "../useSupervisorSession";
import type { SessionMessageResponse } from "../supervisorClient";

function jsonResponse(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const clarifyResponse: SessionMessageResponse = {
  session_id: "sess-abc",
  correlation_id: "corr-1",
  response: "I understood Jaipur. How many days?",
  conversation_phase: "intake",
  itinerary_approved: false,
  intent: "clarify",
  itinerary: null,
  review_verdict: null,
};

const confirmResponse: SessionMessageResponse = {
  session_id: "sess-abc",
  correlation_id: "corr-confirm",
  response: "I understood the following. Would you like me to generate your itinerary?",
  conversation_phase: "confirm",
  itinerary_approved: false,
  intent: "confirm",
  task_message: null,
};

const confirmRejectedResponse: SessionMessageResponse = {
  ...confirmResponse,
  correlation_id: "corr-yes-fail",
  response: "I understood the following. Would you like me to generate your itinerary?",
  intent: "confirm",
  task_message: null,
};

const approvedResponse: SessionMessageResponse = {
  session_id: "sess-abc",
  correlation_id: "corr-2",
  response: "Your 2-day itinerary for Jaipur is ready.",
  conversation_phase: "active",
  itinerary_approved: true,
  intent: "plan",
  itinerary: {
    city: "Jaipur",
    total_days: 2,
    days: [
      {
        day_number: 1,
        activities: [
          {
            id: "a1",
            title: "City Palace",
            start_time: "10:00",
            end_time: "12:00",
            duration_minutes: 120,
            category: "culture",
            citations: [
              {
                citation_id: "jaipur:wikivoyage#see#0001",
                source_url: "https://en.wikivoyage.org/wiki/Jaipur",
                section: "See",
              },
            ],
          },
        ],
        travel_segments: [],
      },
      { day_number: 2, activities: [], travel_segments: [] },
    ],
    citations: [
      {
        citation_id: "jaipur:wikivoyage#see#0001",
        source_url: "https://en.wikivoyage.org/wiki/Jaipur",
        section: "See",
      },
    ],
  },
  review_verdict: {
    status: "pass",
    eval_report: {
      entries: [
        { name: "Feasibility", passed: true, reasons: [] },
        { name: "Grounding", passed: true, reasons: [] },
      ],
    },
  },
};

function SessionHarness() {
  const session = useSupervisorSession();
  return (
    <div>
      <button
        type="button"
        data-testid="harness-submit"
        onClick={() =>
          session.submitTranscript("Plan 2 days in Jaipur").catch(() => {})
        }
      >
        Submit
      </button>
      <button
        type="button"
        data-testid="harness-submit-yes"
        onClick={() => session.submitTranscript("yes").catch(() => {})}
      >
        Submit yes
      </button>
      {session.loading ? <p data-testid="loading-status">Talking to Supervisor…</p> : null}
      {session.traceLoading ? (
        <p data-testid="trace-loading-status">Loading agent trace…</p>
      ) : null}
      {session.error ? <p data-testid="api-error">{session.error}</p> : null}
      {session.confirmRejectedWarning ? (
        <p data-testid="confirm-rejected-warning">{session.confirmRejectedWarning}</p>
      ) : null}
      <p data-testid="session-id">{session.sessionId ?? ""}</p>
      <p data-testid="supervisor-reply">{session.supervisorReply}</p>
      <p data-testid="conversation-count">{session.conversationHistory.length}</p>
      <p data-testid="debug-intent">{session.intent ?? ""}</p>
      <p data-testid="debug-task-message">
        {session.taskMessage === null ? "null" : JSON.stringify(session.taskMessage)}
      </p>
      <p data-testid="has-itinerary">{session.itinerary ? "yes" : "no"}</p>
      <p data-testid="has-eval">{session.evalReport ? "yes" : "no"}</p>
      <p data-testid="trace-count">{session.traceItems.length}</p>
    </div>
  );
}

describe("App empty states", () => {
  it("shows empty itinerary, sources, eval, trace, and conversation before any request", () => {
    render(<App />);

    expect(screen.getByTestId("itinerary-empty")).toHaveTextContent(
      "No activities scheduled.",
    );
    expect(screen.getByTestId("sources-empty")).toHaveTextContent("No sources yet.");
    expect(screen.getByTestId("eval-empty")).toHaveTextContent("No evaluations yet.");
    expect(screen.getByTestId("trace-empty")).toHaveTextContent("No trace events yet.");
    expect(screen.getByTestId("conversation-empty")).toHaveTextContent(/No messages yet/i);
    expect(screen.getByTestId("debug-session-id")).toHaveTextContent("—");
  });
});

describe("useSupervisorSession integration", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("handles a successful Supervisor request and persists session_id", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        return jsonResponse(clarifyResponse);
      }
      if (url.includes("/trace")) {
        return jsonResponse({
          session_id: "sess-abc",
          spans: [
            {
              agent: "supervisor",
              event: "receive_message",
              correlation_id: "corr-1",
              timestamp: "2026-04-01T10:00:00.000Z",
              session_id: "sess-abc",
            },
          ],
        });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("supervisor-reply")).toHaveTextContent("Jaipur");
    });
    expect(screen.getByTestId("session-id")).toHaveTextContent("sess-abc");
    expect(sessionStorage.getItem("vtp.session_id")).toBe("sess-abc");
    expect(screen.getByTestId("has-itinerary")).toHaveTextContent("no");
    expect(screen.getByTestId("has-eval")).toHaveTextContent("no");
    expect(screen.getByTestId("trace-count")).toHaveTextContent("1");

    const messageCall = vi.mocked(fetch).mock.calls.find((call) =>
      String(call[0]).includes("/api/session/message"),
    );
    expect(messageCall).toBeTruthy();
    const init = messageCall![1] as RequestInit;
    expect(JSON.parse(String(init.body))).toMatchObject({
      message: "Plan 2 days in Jaipur",
      session_id: null,
    });
  });

  it("shows loading state while waiting for the Supervisor", async () => {
    const user = userEvent.setup();
    let resolveMessage!: (value: Response) => void;
    const messagePromise = new Promise<Response>((resolve) => {
      resolveMessage = resolve;
    });

    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        return messagePromise;
      }
      if (url.includes("/trace")) {
        return jsonResponse({ session_id: "sess-abc", spans: [] });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit"));

    expect(await screen.findByTestId("loading-status")).toHaveTextContent(
      "Talking to Supervisor…",
    );

    await act(async () => {
      resolveMessage(
        new Response(JSON.stringify(clarifyResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    await waitFor(() => {
      expect(screen.queryByTestId("loading-status")).not.toBeInTheDocument();
    });
  });

  it("displays a friendly error when the backend fails", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Supervisor unavailable" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit"));

    expect(await screen.findByTestId("api-error")).toHaveTextContent(
      "Supervisor unavailable",
    );
    expect(screen.getByTestId("has-itinerary")).toHaveTextContent("no");
  });

  it("loads trace after a successful Supervisor response", async () => {
    const user = userEvent.setup();
    const order: string[] = [];

    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        order.push("message");
        return jsonResponse(clarifyResponse);
      }
      if (url.includes("/trace")) {
        order.push("trace");
        return jsonResponse({
          session_id: "sess-abc",
          spans: [
            { agent: "supervisor", event: "intent_classification", correlation_id: "c" },
            { agent: "mcp_gateway", event: "tool_call_start", tool: "search_pois" },
          ],
        });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("trace-count")).toHaveTextContent("2");
    });
    expect(order).toEqual(["message", "trace"]);
  });

  it("hydrates itinerary, sources-compatible itinerary, and eval from approval response", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        return jsonResponse(approvedResponse);
      }
      if (url.includes("/trace")) {
        return jsonResponse({ session_id: "sess-abc", spans: [] });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("has-itinerary")).toHaveTextContent("yes");
      expect(screen.getByTestId("has-eval")).toHaveTextContent("yes");
    });
  });

  it("keeps empty itinerary/sources/eval when Supervisor returns null fields", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        return jsonResponse(clarifyResponse);
      }
      if (url.includes("/trace")) {
        return jsonResponse({ session_id: "sess-abc", spans: [] });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("supervisor-reply")).not.toHaveTextContent("");
    });
    expect(screen.getByTestId("has-itinerary")).toHaveTextContent("no");
    expect(screen.getByTestId("has-eval")).toHaveTextContent("no");
  });

  it("reuses persisted session_id on the next request", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("vtp.session_id", "sess-persisted");

    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        return jsonResponse({ ...clarifyResponse, session_id: "sess-persisted" });
      }
      if (url.includes("/trace")) {
        return jsonResponse({ session_id: "sess-persisted", spans: [] });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    expect(screen.getByTestId("session-id")).toHaveTextContent("sess-persisted");

    await user.click(screen.getByTestId("harness-submit"));
    await waitFor(() => {
      expect(screen.getByTestId("supervisor-reply")).toHaveTextContent("Jaipur");
    });

    const messageCall = vi.mocked(fetch).mock.calls.find((call) =>
      String(call[0]).includes("/api/session/message"),
    );
    const body = JSON.parse(String((messageCall![1] as RequestInit).body));
    expect(body.session_id).toBe("sess-persisted");
  });

  it("accumulates conversation history across turns", async () => {
    const user = userEvent.setup();
    let call = 0;
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        call += 1;
        return jsonResponse(call === 1 ? clarifyResponse : confirmResponse);
      }
      if (url.includes("/trace")) {
        return jsonResponse({ session_id: "sess-abc", spans: [] });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit"));
    await waitFor(() => {
      expect(screen.getByTestId("conversation-count")).toHaveTextContent("1");
    });

    await user.click(screen.getByTestId("harness-submit"));
    await waitFor(() => {
      expect(screen.getByTestId("conversation-count")).toHaveTextContent("2");
    });
  });

  it("shows confirm rejected warning when yes gets confirm intent again", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        return jsonResponse(confirmRejectedResponse);
      }
      if (url.includes("/trace")) {
        return jsonResponse({ session_id: "sess-abc", spans: [] });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit-yes"));

    await waitFor(() => {
      expect(screen.getByTestId("confirm-rejected-warning")).toHaveTextContent(
        "Confirmation was not accepted by the backend.",
      );
    });
    expect(screen.getByTestId("debug-intent")).toHaveTextContent("confirm");
    expect(screen.getByTestId("debug-task-message")).toHaveTextContent("null");
  });

  it("logs API request and response to the console", async () => {
    const user = userEvent.setup();
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});

    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/session/message")) {
        return jsonResponse(clarifyResponse);
      }
      if (url.includes("/trace")) {
        return jsonResponse({ session_id: "sess-abc", spans: [] });
      }
      return jsonResponse({}, 404);
    });

    render(<SessionHarness />);
    await user.click(screen.getByTestId("harness-submit"));

    await waitFor(() => {
      expect(infoSpy).toHaveBeenCalled();
    });

    const messages = infoSpy.mock.calls.map((call) => String(call[0]));
    expect(messages.some((line) => line.includes("Supervisor API → POST"))).toBe(true);
    expect(messages.some((line) => line.includes("Supervisor API ←"))).toBe(true);
    infoSpy.mockRestore();
  });
});
