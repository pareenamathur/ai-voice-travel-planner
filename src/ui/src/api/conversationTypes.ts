import type { SessionMessageRequest, SessionMessageResponse } from "./supervisorClient";

/** One user turn and its Supervisor API exchange (debug / chat history). */
export interface ConversationExchange {
  id: string;
  userMessage: string;
  requestedAt: string;
  request: SessionMessageRequest;
  response?: SessionMessageResponse;
  respondedAt?: string;
  error?: string;
}
