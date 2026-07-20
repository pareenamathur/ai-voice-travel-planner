/**
 * Companion UI shell — Aetheric Voyage presentation (Stitch source of truth).
 * Speech → POST /api/session/message → panels; trace via GET after success.
 * Backend contracts and useSupervisorSession wiring are unchanged.
 */

import { useState } from "react";

import {
  ConversationHistory,
  EvalStatusPanel,
  ItineraryView,
  SessionDebugPanel,
  SourcesPanel,
  SpeechPanel,
  TracePanel,
} from "./components";
import { SideNav, TopBar, type AppNavId } from "./components/layout";
import { useSupervisorSession } from "./api";

export function App() {
  const {
    sessionId,
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
    supervisorReply,
  } = useSupervisorSession();

  const [nav, setNav] = useState<AppNavId>("new-trip");
  const showItineraryScreen = Boolean(itineraryApproved && itinerary);

  const handleNavigate = (id: AppNavId) => {
    setNav(id);
  };

  // When an itinerary is approved, highlight Recent Trips in the shell.
  const activeNav = showItineraryScreen && nav === "new-trip" ? "recent" : nav;

  return (
    <div className="app-shell" data-screen={showItineraryScreen ? "itinerary" : "home"}>
      <div className="app-atmosphere" aria-hidden="true">
        <div className="app-atmosphere__blob app-atmosphere__blob--primary" />
        <div className="app-atmosphere__blob app-atmosphere__blob--secondary" />
      </div>

      <SideNav active={activeNav} onNavigate={handleNavigate} />

      <div className="app-shell__workspace">
        <TopBar
          placeholder={
            showItineraryScreen ? "Search itineraries..." : "Search destinations..."
          }
        />

        <main className="app-shell__main">
          {loading ? (
            <p className="app-shell__status" role="status" data-testid="loading-status">
              Talking to Supervisor…
            </p>
          ) : null}

          {traceLoading ? (
            <p
              className="app-shell__status"
              role="status"
              data-testid="trace-loading-status"
            >
              Loading agent trace…
            </p>
          ) : null}

          {error ? (
            <p className="app-shell__error" role="alert" data-testid="api-error">
              {error}
            </p>
          ) : null}

          {!showItineraryScreen ? (
            <section className="home-hero" aria-label="Plan with voice">
              <h2 className="home-hero__title">Plan your perfect trip with AI</h2>
              <p className="home-hero__subtitle">
                Speak your desires into existence. Our neural engine crafts bespoke
                journeys across the globe, tailored to your exact rhythm.
              </p>
            </section>
          ) : null}

          {showItineraryScreen && itinerary ? (
            <section className="itinerary-hero" aria-label="Trip summary">
              <nav className="itinerary-hero__crumbs" aria-label="Breadcrumb">
                <span>Recent Trips</span>
                <span className="material-symbols-outlined" aria-hidden="true">
                  chevron_right
                </span>
                <span className="itinerary-hero__crumb-current">
                  {itinerary.city} Expedition
                </span>
              </nav>
              <div className="itinerary-hero__row">
                <div>
                  <h2 className="itinerary-hero__title">
                    The {titleCase(itinerary.city)} Experience
                  </h2>
                  <div className="itinerary-hero__chips">
                    <span className="chip">
                      <span className="material-symbols-outlined" aria-hidden="true">
                        location_on
                      </span>
                      {titleCase(itinerary.city)}
                    </span>
                    <span className="chip">
                      <span className="material-symbols-outlined" aria-hidden="true">
                        calendar_today
                      </span>
                      {itinerary.total_days}{" "}
                      {itinerary.total_days === 1 ? "Day" : "Days"}
                    </span>
                    {itinerary.traveler_constraints?.pace ? (
                      <span className="chip">
                        <span className="material-symbols-outlined" aria-hidden="true">
                          spa
                        </span>
                        {titleCase(String(itinerary.traveler_constraints.pace))}
                      </span>
                    ) : null}
                    {(itinerary.traveler_constraints?.interests ?? [])
                      .slice(0, 2)
                      .map((interest) => (
                        <span className="chip" key={interest}>
                          <span className="material-symbols-outlined" aria-hidden="true">
                            restaurant
                          </span>
                          {titleCase(interest)}
                        </span>
                      ))}
                  </div>
                </div>
                <div className="itinerary-hero__actions">
                  <button type="button" className="btn-ghost">
                    <span className="material-symbols-outlined" aria-hidden="true">
                      share
                    </span>
                    Share Trip
                  </button>
                  <button type="button" className="btn-primary">
                    <span className="material-symbols-outlined" aria-hidden="true">
                      picture_as_pdf
                    </span>
                    Export PDF
                  </button>
                </div>
              </div>

              {supervisorReply ? (
                <div className="ai-greeting glass-card">
                  <div className="ai-greeting__icon" aria-hidden="true">
                    <span className="material-symbols-outlined">auto_awesome</span>
                  </div>
                  <div>
                    <h3 className="ai-greeting__title">
                      Your {titleCase(itinerary.city)} journey is ready.
                    </h3>
                    <p className="ai-greeting__body">{supervisorReply}</p>
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}

          <div
            className={
              showItineraryScreen
                ? "app-shell__voice app-shell__voice--compact"
                : "app-shell__voice"
            }
          >
            <SpeechPanel
              onSubmitTranscript={submitTranscript}
              submitDisabled={loading}
            />
          </div>

          <div
            className={
              showItineraryScreen
                ? "app-shell__itinerary"
                : "app-shell__itinerary app-shell__itinerary--muted"
            }
          >
            <ItineraryView itinerary={itinerary} />
          </div>

          <details className="meta-drawer glass-card" open>
            <summary className="meta-drawer__summary">
              <span className="meta-drawer__summary-left">
                <span className="material-symbols-outlined" aria-hidden="true">
                  analytics
                </span>
                <span className="meta-drawer__label">Sources &amp; Metadata</span>
              </span>
              <span className="material-symbols-outlined" aria-hidden="true">
                expand_more
              </span>
            </summary>
            <div className="meta-drawer__body">
              <SourcesPanel itinerary={itinerary ?? undefined} />
              <TracePanel items={traceItems} />
              <EvalStatusPanel report={evalReport} />
            </div>
          </details>

          <details className="meta-drawer glass-card meta-drawer--debug" open>
            <summary className="meta-drawer__summary">
              <span className="meta-drawer__summary-left">
                <span className="material-symbols-outlined" aria-hidden="true">
                  bug_report
                </span>
                <span className="meta-drawer__label">Session Debug</span>
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
        </main>
      </div>
    </div>
  );
}

function titleCase(value: string): string {
  if (!value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}
