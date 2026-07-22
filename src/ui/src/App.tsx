/**
 * Consumer travel chat — Aetheric Voyage presentation.
 * Hooks and API wiring unchanged; debug panels behind Developer Mode.
 */

import { useCallback, useEffect, useState } from "react";

import { useSupervisorSession } from "./api";
import {
  activeLoadingMessage,
  isLongRunningHint,
} from "./api/loadingHint";
import { useLoadingProgress } from "./api/useLoadingProgress";
import {
  ChatComposer,
  ChatThread,
  DeveloperPanels,
} from "./components/chat";
import { ItineraryView, TripPanelBusy } from "./components/itinerary";
import { ExportMenu } from "./components/export";
import { collectSourceLinks } from "./components/sources/sourceLinks";

const DEV_MODE_KEY = "vtp.developer_mode";

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
    loadingHint,
    itineraryRevision,
    traceLoading,
    error,
    submitTranscript,
  } = useSupervisorSession();

  const [developerMode, setDeveloperMode] = useState(() => {
    try {
      return sessionStorage.getItem(DEV_MODE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    try {
      sessionStorage.setItem(DEV_MODE_KEY, developerMode ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [developerMode]);

  const toggleDeveloperMode = useCallback(() => {
    setDeveloperMode((prev) => !prev);
  }, []);

  const sourceLinks = itinerary ? collectSourceLinks(itinerary) : [];

  const busy = loading || traceLoading;
  const loadingElapsed = useLoadingProgress(loading);
  const statusMessage = loading
    ? activeLoadingMessage(loadingHint, loadingElapsed)
    : traceLoading
      ? "Refreshing agent trace…"
      : null;
  const showTripSkeleton =
    loading && isLongRunningHint(loadingHint) && !itinerary;
  const showTripOverlay =
    loading && (loadingHint === "plan" || loadingHint === "edit") && Boolean(itinerary);

  return (
    <div
      className="app-shell app-shell--chat"
      aria-busy={busy || undefined}
    >
      <div className="app-atmosphere" aria-hidden="true">
        <div className="app-atmosphere__blob app-atmosphere__blob--primary" />
        <div className="app-atmosphere__blob app-atmosphere__blob--secondary" />
      </div>

      <header className="chat-header">
        <div className="chat-header__brand">
          <span className="chat-header__logo" aria-hidden="true">
            <span className="material-symbols-outlined">flight_takeoff</span>
          </span>
          <div>
            <h1 className="chat-header__title">Aether Travel</h1>
            <p className="chat-header__tagline">Your AI journey companion</p>
          </div>
        </div>

        <div className="chat-header__actions">
          <button
            type="button"
            className={`chat-header__icon-btn${developerMode ? " chat-header__icon-btn--active" : ""}`}
            aria-label={developerMode ? "Developer mode on" : "Developer mode off"}
            title="Developer mode"
            aria-pressed={developerMode}
            onClick={toggleDeveloperMode}
            data-testid="developer-mode-toggle"
          >
            <span className="material-symbols-outlined">code</span>
          </button>
          <button
            type="button"
            className="chat-header__icon-btn"
            aria-label="Settings"
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen((open) => !open)}
            data-testid="settings-toggle"
          >
            <span className="material-symbols-outlined">settings</span>
          </button>
        </div>

        {settingsOpen ? (
          <div className="chat-settings glass-card" role="dialog" aria-label="Settings">
            <h2 className="chat-settings__title">Settings</h2>
            <label className="chat-settings__row">
              <span>Developer mode</span>
              <input
                type="checkbox"
                checked={developerMode}
                onChange={(event) => setDeveloperMode(event.target.checked)}
                data-testid="settings-developer-mode"
              />
            </label>
            <p className="chat-settings__hint">
              Shows sources, quality checks, session details, and legacy voice panel for
              debugging.
            </p>
            <button
              type="button"
              className="chat-settings__close"
              onClick={() => setSettingsOpen(false)}
            >
              Done
            </button>
          </div>
        ) : null}
      </header>

      <main id="main-content" className="chat-layout">
        {!error && statusMessage ? (
          <p className="app-shell__status chat-layout__status" role="status" data-testid="loading-status">
            {statusMessage}
          </p>
        ) : null}

        {!error && !statusMessage && traceLoading ? (
          <p
            className="app-shell__status chat-layout__status"
            role="status"
            data-testid="trace-loading-status"
          >
            Refreshing agent trace…
          </p>
        ) : null}

        {error ? (
          <p className="app-shell__error chat-layout__status" role="alert" data-testid="api-error">
            {error}
          </p>
        ) : null}

        <div
          className={`chat-layout__body${
            itinerary || showTripSkeleton ? " chat-layout__body--split" : ""
          }`}
        >
          <ChatThread
            exchanges={conversationHistory}
            loading={loading}
            loadingHint={loadingHint}
            loadingElapsedSec={loadingElapsed}
            itineraryApproved={itineraryApproved}
            sourceLinks={sourceLinks}
            onSuggestionSelect={(prompt) => {
              void submitTranscript(prompt);
            }}
            suggestionsDisabled={loading}
          />

          {showTripSkeleton ? (
            <TripPanelBusy hint={loadingHint} mode="skeleton" />
          ) : itinerary ? (
            <aside
              key={itineraryRevision}
              className={[
                "trip-panel",
                "glass-card",
                "trip-panel--fresh",
                showTripOverlay ? "trip-panel--busy" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              data-testid="trip-panel"
              aria-label="Trip itinerary"
              aria-busy={showTripOverlay || undefined}
            >
              {showTripOverlay ? (
                <TripPanelBusy hint={loadingHint} mode="overlay" />
              ) : null}
              <div className="trip-panel__header">
                <div className="trip-panel__header-text">
                  <h2 className="trip-panel__title">Your trip</h2>
                  <p className="trip-panel__status">
                    {itineraryApproved ? "Approved" : "Draft"}
                  </p>
                </div>
                <ExportMenu sessionId={sessionId} approved={itineraryApproved} />
              </div>
              <ItineraryView itinerary={itinerary} />
            </aside>
          ) : null}
        </div>

        <DeveloperPanels
          visible={developerMode}
          sessionId={sessionId}
          conversationPhase={conversationPhase}
          intent={intent}
          taskMessage={taskMessage}
          itineraryApproved={itineraryApproved}
          confirmRejectedWarning={confirmRejectedWarning}
          conversationHistory={conversationHistory}
          itinerary={itinerary}
          evalReport={evalReport}
          traceItems={traceItems}
          onSubmitTranscript={submitTranscript}
          submitDisabled={loading}
        />
      </main>

      <ChatComposer
        onSubmitTranscript={submitTranscript}
        submitDisabled={loading}
        busy={loading}
      />
    </div>
  );
}
