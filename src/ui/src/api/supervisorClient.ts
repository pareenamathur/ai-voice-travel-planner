/** Supervisor API client — uses only the existing Phase 5 endpoints. */

import { logApiError, logApiRequest, logApiResponse } from "./apiLogger";

export interface SessionMessageRequest {
  session_id?: string | null;
  message: string;
}

export interface SessionMessageResponse {
  session_id: string;
  correlation_id: string;
  response: string;
  conversation_phase: string;
  itinerary_approved: boolean;
  intent?: string | null;
  itinerary?: Record<string, unknown> | null;
  review_verdict?: Record<string, unknown> | null;
  task_message?: Record<string, unknown> | null;
}

export interface SessionTraceResponse {
  session_id: string;
  spans: Array<Record<string, unknown>>;
}

export class SupervisorApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SupervisorApiError";
    this.status = status;
  }
}

/**
 * Base URL for API calls.
 * Empty string uses the Vite proxy (`/api` → backend) during local `npm run dev`.
 */
export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (typeof configured === "string" && configured.trim()) {
    return configured.replace(/\/$/, "");
  }
  return "";
}

async function parseError(response: Response): Promise<SupervisorApiError> {
  let detail = `Request failed (${response.status})`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (body.detail !== undefined) {
      detail = JSON.stringify(body.detail);
    }
  } catch {
    // keep default message
  }
  return new SupervisorApiError(detail, response.status);
}

/** POST /api/session/message */
export async function postSessionMessage(
  request: SessionMessageRequest,
): Promise<SessionMessageResponse> {
  const url = `${getApiBaseUrl()}/api/session/message`;
  const body = {
    message: request.message,
    session_id: request.session_id ?? null,
  };
  logApiRequest("POST", url, body);

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await parseError(response);
    logApiError("POST", url, { status: response.status, message: error.message });
    throw error;
  }

  const payload = (await response.json()) as SessionMessageResponse;
  logApiResponse("POST", url, payload, response.status);
  return payload;
}

/** GET /api/session/{session_id}/trace — call only after a successful message. */
export async function getSessionTrace(
  sessionId: string,
): Promise<SessionTraceResponse> {
  const url = `${getApiBaseUrl()}/api/session/${encodeURIComponent(sessionId)}/trace`;
  logApiRequest("GET", url, { session_id: sessionId });

  const response = await fetch(url, { method: "GET" });

  if (!response.ok) {
    const error = await parseError(response);
    logApiError("GET", url, { status: response.status, message: error.message });
    throw error;
  }

  const payload = (await response.json()) as SessionTraceResponse;
  logApiResponse("GET", url, payload, response.status);
  return payload;
}
