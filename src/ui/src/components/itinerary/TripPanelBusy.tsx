import type { LoadingHint } from "../../api/loadingHint";
import { loadingHintMessage } from "../../api/loadingHint";
import "./itinerary.css";

export interface TripPanelBusyProps {
  hint: LoadingHint;
  mode: "skeleton" | "overlay";
}

export function TripPanelBusy({ hint, mode }: TripPanelBusyProps) {
  const label = loadingHintMessage(hint);

  if (mode === "overlay") {
    return (
      <div
        className="trip-panel__busy-overlay"
        role="status"
        aria-live="polite"
        data-testid="trip-panel-busy"
      >
        <span className="trip-panel__busy-spinner" aria-hidden="true" />
        <span>{label}</span>
      </div>
    );
  }

  return (
    <aside
      className="trip-panel glass-card trip-panel--loading"
      data-testid="trip-panel-loading"
      aria-busy="true"
      aria-label="Trip itinerary loading"
    >
      <div className="trip-panel__header">
        <h2 className="trip-panel__title">Your trip</h2>
        <p className="trip-panel__status trip-panel__status--loading">{label}</p>
      </div>
      <div className="trip-panel__skeleton" aria-hidden="true">
        <div className="trip-panel__skeleton-bar trip-panel__skeleton-bar--wide" />
        <div className="trip-panel__skeleton-bar" />
        <div className="trip-panel__skeleton-bar" />
        <div className="trip-panel__skeleton-bar trip-panel__skeleton-bar--short" />
      </div>
    </aside>
  );
}
