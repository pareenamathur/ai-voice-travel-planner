/**
 * UI types for the Evaluation Status Panel.
 * Compatible with future Review Agent ``EvalReport`` / ``ReviewVerdict`` shapes.
 */

/** Canonical display statuses (uppercase). Backend may send lowercase enums. */
export type EvalVerdict = "PASS" | "PASS_WITH_WARNINGS" | "FAIL";

export type EvalVerdictInput =
  | EvalVerdict
  | "pass"
  | "pass_with_warnings"
  | "fail"
  | string;

/** One evaluation result card. */
export interface EvalResult {
  /** Evaluation name (e.g. Feasibility, Grounding, Edit Correctness). */
  name: string;
  status?: EvalVerdictInput | null;
  /** Optional numeric score when provided by future eval modules. */
  score?: number | null;
  /** Human-readable explanation. */
  explanation?: string | null;
  /** Alias for explanation (accepted for flexibility). */
  message?: string | null;
  timestamp?: string | null;
  /**
   * Backend ``EvalReportEntry.passed`` compatibility.
   * Used when ``status`` is omitted: true → PASS, false → FAIL.
   */
  passed?: boolean | null;
  /** Backend ``EvalReportEntry.reasons`` compatibility. */
  reasons?: string[] | null;
  metadata?: Record<string, unknown>;
}

/**
 * Backend-shaped entry from ``EvalReport.entries`` (Phase 7 / current messages).
 */
export interface EvalReportEntryLike {
  name: string;
  passed: boolean;
  reasons?: string[];
}

/**
 * Props-facing evaluation report.
 * Accepts either UI ``evaluations`` or backend ``entries``.
 */
export interface EvalReportData {
  /** Overall Review verdict when known. */
  overall_verdict?: EvalVerdictInput | null;
  /** Alias used by some session payloads. */
  status?: EvalVerdictInput | null;
  evaluations?: EvalResult[];
  /** Backend ``EvalReport.entries`` shape. */
  entries?: EvalReportEntryLike[];
  timestamp?: string | null;
  metadata?: Record<string, unknown>;
}

export interface EvalSummary {
  overallVerdict: EvalVerdict | "UNKNOWN";
  total: number;
  passed: number;
  failed: number;
  warnings: number;
}

export interface EvalStatusPanelProps {
  report?: EvalReportData | null;
  title?: string;
}
