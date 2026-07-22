import type { ReactNode } from "react";

import { ConversationHistory } from "../debug/ConversationHistory";
import { SessionDebugPanel } from "../debug/SessionDebugPanel";
import { EvalStatusPanel } from "../evals/EvalStatusPanel";
import { ItineraryView } from "../itinerary/ItineraryView";
import { SourcesPanel } from "../sources/SourcesPanel";
import { TracePanel } from "../trace/TracePanel";
import { SpeechPanel } from "../SpeechPanel";
import type { TraceItem } from "../trace";
import type { ConversationExchange } from "../../api/conversationTypes";
import type { EvalReportData } from "../evals/types";
import type { Itinerary } from "../../types/itinerary";
import "./chat.css";

export interface DeveloperPanelsProps {
  sessionId: string | null;
  conversationPhase: string | null;
  intent: string | null;
  taskMessage: Record<string, unknown> | null;
  itineraryApproved: boolean;
  confirmRejectedWarning: string | null;
  conversationHistory: ConversationExchange[];
  itinerary: Itinerary | null | undefined;
  evalReport: EvalReportData | null;
  traceItems: TraceItem[];
  onSubmitTranscript?: (message: string) => Promise<void>;
  submitDisabled?: boolean;
  visible: boolean;
}

/**
 * Legacy debugging panels — unchanged behavior, hidden unless developer mode is on.
 */
export function DeveloperPanels({
  sessionId,
  conversationPhase,
  intent,
  taskMessage,
  itineraryApproved,
  confirmRejectedWarning,
  conversationHistory,
  itinerary,
  evalReport,
  traceItems,
  onSubmitTranscript,
  submitDisabled,
  visible,
}: DeveloperPanelsProps) {
  const wrap = (children: ReactNode) => (
    <div className={visible ? "developer-panels" : "developer-panels developer-panels--sr"}>
      {children}
    </div>
  );

  return wrap(
    <>
      <details className="meta-drawer glass-card" open={visible}>
        <summary className="meta-drawer__summary">
          <span className="meta-drawer__summary-left">
            <span className="material-symbols-outlined" aria-hidden="true">
              analytics
            </span>
            <span className="meta-drawer__label">Sources &amp; diagnostics</span>
          </span>
          <span className="material-symbols-outlined" aria-hidden="true">
            expand_more
          </span>
        </summary>
        <div className="meta-drawer__body">
          <SourcesPanel itinerary={itinerary ?? undefined} />
          <TracePanel items={traceItems} />
          <EvalStatusPanel report={evalReport} itineraryApproved={itineraryApproved} />
        </div>
      </details>

      <details className="meta-drawer glass-card meta-drawer--debug" open={visible}>
        <summary className="meta-drawer__summary">
          <span className="meta-drawer__summary-left">
            <span className="material-symbols-outlined" aria-hidden="true">
              bug_report
            </span>
            <span className="meta-drawer__label">Session debug</span>
          </span>
          <span className="material-symbols-outlined" aria-hidden="true">
            expand_more
          </span>
        </summary>
        <div className="meta-drawer__body">
          <SessionDebugPanel
            sessionId={sessionId}
            conversationPhase={conversationPhase}
            intent={intent}
            taskMessage={taskMessage}
            itineraryApproved={itineraryApproved}
            confirmRejectedWarning={confirmRejectedWarning}
          />
          <ConversationHistory exchanges={conversationHistory} />
        </div>
      </details>

      <div className="developer-panels__legacy">
        <ItineraryView itinerary={itinerary} />
        <SpeechPanel onSubmitTranscript={onSubmitTranscript} submitDisabled={submitDisabled} />
      </div>
    </>,
  );
}
