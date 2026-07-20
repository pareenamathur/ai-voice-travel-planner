import type {
  EvalReportData,
  EvalResult,
  EvalSummary,
  EvalVerdict,
  EvalVerdictInput,
} from "./types";

export function normalizeVerdict(input: EvalVerdictInput | null | undefined): EvalVerdict | null {
  if (input === null || input === undefined) {
    return null;
  }
  const raw = String(input).trim().toLowerCase().replace(/-/g, "_");
  if (raw === "pass") {
    return "PASS";
  }
  if (raw === "pass_with_warnings" || raw === "pass with warnings" || raw === "warning") {
    return "PASS_WITH_WARNINGS";
  }
  if (raw === "fail" || raw === "failed") {
    return "FAIL";
  }
  return null;
}

export function resolveEvalStatus(item: EvalResult): EvalVerdict {
  const fromStatus = normalizeVerdict(item.status ?? null);
  if (fromStatus) {
    return fromStatus;
  }
  if (item.passed === true) {
    return "PASS";
  }
  if (item.passed === false) {
    return "FAIL";
  }
  return "FAIL";
}

export function resolveExplanation(item: EvalResult): string | null {
  const direct = item.explanation?.trim() || item.message?.trim() || null;
  if (direct) {
    return direct;
  }
  if (item.reasons && item.reasons.length > 0) {
    return item.reasons.join("; ");
  }
  return null;
}

/** Flatten UI evaluations + backend entries into a single list. */
export function collectEvaluations(report: EvalReportData | null | undefined): EvalResult[] {
  if (!report) {
    return [];
  }

  const fromUi = report.evaluations ?? [];
  const fromEntries: EvalResult[] = (report.entries ?? []).map((entry) => ({
    name: entry.name,
    passed: entry.passed,
    reasons: entry.reasons ?? [],
    status: entry.passed ? "PASS" : "FAIL",
  }));

  return [...fromUi, ...fromEntries];
}

export function buildSummary(
  evaluations: EvalResult[],
  report: EvalReportData | null | undefined,
): EvalSummary {
  let passed = 0;
  let failed = 0;
  let warnings = 0;

  for (const item of evaluations) {
    const status = resolveEvalStatus(item);
    if (status === "PASS") {
      passed += 1;
    } else if (status === "PASS_WITH_WARNINGS") {
      warnings += 1;
    } else {
      failed += 1;
    }
  }

  const explicit =
    normalizeVerdict(report?.overall_verdict ?? null) ??
    normalizeVerdict(report?.status ?? null);

  let overallVerdict: EvalVerdict | "UNKNOWN" = explicit ?? "UNKNOWN";
  if (!explicit && evaluations.length > 0) {
    if (failed > 0) {
      overallVerdict = "FAIL";
    } else if (warnings > 0) {
      overallVerdict = "PASS_WITH_WARNINGS";
    } else {
      overallVerdict = "PASS";
    }
  }

  return {
    overallVerdict,
    total: evaluations.length,
    passed,
    failed,
    warnings,
  };
}

export function statusCssClass(status: EvalVerdict): string {
  if (status === "PASS") {
    return "pass";
  }
  if (status === "PASS_WITH_WARNINGS") {
    return "warning";
  }
  return "fail";
}

export function formatVerdictLabel(status: EvalVerdict | "UNKNOWN"): string {
  if (status === "PASS_WITH_WARNINGS") {
    return "PASS WITH WARNINGS";
  }
  return status;
}
