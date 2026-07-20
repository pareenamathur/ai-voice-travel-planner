import type { EvalReportData } from "../components/evals/types";
import type { Itinerary } from "../types/itinerary";
import type { SessionMessageResponse } from "./supervisorClient";

/** Safely coerce Supervisor itinerary payload into the UI Itinerary type. */
export function asItinerary(
  value: Record<string, unknown> | null | undefined,
): Itinerary | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  if (typeof value.city !== "string" || !value.city.trim()) {
    return null;
  }
  if (typeof value.total_days !== "number" || value.total_days < 1) {
    return null;
  }
  return value as unknown as Itinerary;
}

/** Build EvalStatusPanel report from review_verdict (when present). */
export function evalReportFromVerdict(
  reviewVerdict: Record<string, unknown> | null | undefined,
): EvalReportData | null {
  if (!reviewVerdict || typeof reviewVerdict !== "object") {
    return null;
  }

  const status =
    typeof reviewVerdict.status === "string" ? reviewVerdict.status : null;
  const rawReport = reviewVerdict.eval_report;
  const entries =
    rawReport &&
    typeof rawReport === "object" &&
    Array.isArray((rawReport as { entries?: unknown }).entries)
      ? ((rawReport as { entries: EvalReportData["entries"] }).entries ?? [])
      : [];

  if (!status && entries.length === 0) {
    return null;
  }

  return {
    overall_verdict: status,
    entries,
  };
}

export function supervisorReplyLabel(response: SessionMessageResponse): string {
  return response.response?.trim() || "";
}
