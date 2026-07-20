import { useCallback, useEffect, useState } from "react";



import type { EvalReportData } from "../components/evals/types";

import type { Itinerary } from "../types/itinerary";

import type { TraceItem } from "../types/trace";

import type { ConversationExchange } from "./conversationTypes";

import { shouldShowConfirmRejectedWarning } from "./debugHelpers";

import {

  getSessionTrace,

  postSessionMessage,

  SupervisorApiError,

} from "./supervisorClient";

import type { SessionMessageResponse } from "./supervisorClient";

import { asItinerary, evalReportFromVerdict } from "./mapSession";

import { spansToTraceItems } from "./mapTrace";



const SESSION_STORAGE_KEY = "vtp.session_id";



export interface SupervisorSessionState {

  sessionId: string | null;

  supervisorReply: string;

  itinerary: Itinerary | null;

  evalReport: EvalReportData | null;

  traceItems: TraceItem[];

  conversationPhase: string | null;

  itineraryApproved: boolean;

  intent: string | null;

  taskMessage: Record<string, unknown> | null;

  conversationHistory: ConversationExchange[];

  confirmRejectedWarning: string | null;

  loading: boolean;

  traceLoading: boolean;

  error: string | null;

  submitTranscript: (message: string) => Promise<void>;

  clearError: () => void;

}



function readStoredSessionId(): string | null {

  try {

    const value = sessionStorage.getItem(SESSION_STORAGE_KEY);

    return value && value.trim() ? value.trim() : null;

  } catch {

    return null;

  }

}



function storeSessionId(sessionId: string): void {

  try {

    sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);

  } catch {

    // ignore quota / private mode

  }

}



function createExchangeId(): string {

  return `exchange-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

}



function applySessionResponse(

  result: SessionMessageResponse,

  setters: {

    setSessionId: (id: string) => void;

    setSupervisorReply: (text: string) => void;

    setConversationPhase: (phase: string | null) => void;

    setItineraryApproved: (approved: boolean) => void;

    setIntent: (intent: string | null) => void;

    setTaskMessage: (task: Record<string, unknown> | null) => void;

    setItinerary: (updater: (prev: Itinerary | null) => Itinerary | null) => void;

    setEvalReport: (updater: (prev: EvalReportData | null) => EvalReportData | null) => void;

  },

): void {

  setters.setSessionId(result.session_id);

  storeSessionId(result.session_id);

  setters.setSupervisorReply(result.response ?? "");

  setters.setConversationPhase(result.conversation_phase ?? null);

  setters.setItineraryApproved(Boolean(result.itinerary_approved));

  setters.setIntent(result.intent ?? null);

  setters.setTaskMessage(result.task_message ?? null);



  const nextItinerary = asItinerary(result.itinerary ?? null);

  if (nextItinerary) {

    setters.setItinerary(() => nextItinerary);

  }



  const nextEval = evalReportFromVerdict(result.review_verdict ?? null);

  if (nextEval) {

    setters.setEvalReport(() => nextEval);

  }

}



/**

 * Holds Companion UI session state and talks to the Supervisor API only.

 */

export function useSupervisorSession(): SupervisorSessionState {

  const [sessionId, setSessionId] = useState<string | null>(() => readStoredSessionId());

  const [supervisorReply, setSupervisorReply] = useState("");

  const [itinerary, setItinerary] = useState<Itinerary | null>(null);

  const [evalReport, setEvalReport] = useState<EvalReportData | null>(null);

  const [traceItems, setTraceItems] = useState<TraceItem[]>([]);

  const [conversationPhase, setConversationPhase] = useState<string | null>(null);

  const [itineraryApproved, setItineraryApproved] = useState(false);

  const [intent, setIntent] = useState<string | null>(null);

  const [taskMessage, setTaskMessage] = useState<Record<string, unknown> | null>(null);

  const [conversationHistory, setConversationHistory] = useState<ConversationExchange[]>([]);

  const [confirmRejectedWarning, setConfirmRejectedWarning] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);

  const [traceLoading, setTraceLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);



  useEffect(() => {

    if (sessionId) {

      storeSessionId(sessionId);

    }

  }, [sessionId]);



  const clearError = useCallback(() => setError(null), []);



  const submitTranscript = useCallback(

    async (message: string) => {

      const trimmed = message.trim();

      if (!trimmed) {

        setError("Nothing to send — speak or type a message first.");

        throw new Error("empty-transcript");

      }



      const exchangeId = createExchangeId();

      const requestedAt = new Date().toISOString();

      const request = { session_id: sessionId, message: trimmed };



      setLoading(true);

      setError(null);

      setConfirmRejectedWarning(null);



      setConversationHistory((prev) => [

        ...prev,

        {

          id: exchangeId,

          userMessage: trimmed,

          requestedAt,

          request,

        },

      ]);



      try {

        const result = await postSessionMessage(request);



        const respondedAt = new Date().toISOString();

        setConversationHistory((prev) =>

          prev.map((entry) =>

            entry.id === exchangeId

              ? { ...entry, response: result, respondedAt }

              : entry,

          ),

        );



        applySessionResponse(result, {

          setSessionId,

          setSupervisorReply,

          setConversationPhase,

          setItineraryApproved,

          setIntent,

          setTaskMessage,

          setItinerary,

          setEvalReport,

        });



        if (shouldShowConfirmRejectedWarning(trimmed, result.intent)) {

          setConfirmRejectedWarning(

            "Confirmation was not accepted by the backend.",

          );

        }



        setTraceLoading(true);

        try {

          const trace = await getSessionTrace(result.session_id);

          setTraceItems(spansToTraceItems(trace.spans ?? []));

        } catch (traceErr) {

          const messageText =

            traceErr instanceof SupervisorApiError

              ? traceErr.message

              : "Could not load agent trace.";

          setError(`Supervisor replied, but trace failed: ${messageText}`);

        } finally {

          setTraceLoading(false);

        }

      } catch (err) {

        const messageText =

          err instanceof SupervisorApiError

            ? err.message

            : err instanceof Error

              ? err.message

              : "Could not reach the Supervisor API.";



        if (messageText !== "empty-transcript") {

          setError(messageText);

        }



        setConversationHistory((prev) =>

          prev.map((entry) =>

            entry.id === exchangeId ? { ...entry, error: messageText } : entry,

          ),

        );

        throw err;

      } finally {

        setLoading(false);

      }

    },

    [sessionId],

  );



  return {

    sessionId,

    supervisorReply,

    itinerary,

    evalReport,

    traceItems,

    conversationPhase,

    itineraryApproved,

    intent,

    taskMessage,

    conversationHistory,

    confirmRejectedWarning,

    loading,

    traceLoading,

    error,

    submitTranscript,

    clearError,

  };

}


