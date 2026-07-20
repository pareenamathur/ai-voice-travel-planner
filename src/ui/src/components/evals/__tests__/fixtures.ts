import type { EvalReportData } from "../types";

export const emptyReport: EvalReportData = {
  evaluations: [],
};

export const allPassReport: EvalReportData = {
  overall_verdict: "PASS",
  timestamp: "2026-04-01T10:00:00.000Z",
  evaluations: [
    {
      name: "Feasibility",
      status: "PASS",
      score: 1,
      explanation: "Daily windows respected",
      timestamp: "2026-04-01T10:00:00.000Z",
    },
    {
      name: "Grounding",
      status: "pass",
      message: "Citations present for all stops",
    },
  ],
};

export const mixedPassFailReport: EvalReportData = {
  overall_verdict: "FAIL",
  evaluations: [
    {
      name: "Feasibility",
      status: "PASS",
      explanation: "OK",
    },
    {
      name: "Grounding",
      status: "FAIL",
      explanation: "Missing osm_id on Day 2 lunch",
    },
  ],
};

export const warningsReport: EvalReportData = {
  overall_verdict: "PASS_WITH_WARNINGS",
  evaluations: [
    {
      name: "Feasibility",
      status: "PASS",
    },
    {
      name: "Grounding",
      status: "PASS_WITH_WARNINGS",
      explanation: "One citation is approximate",
      score: 0.8,
    },
  ],
};

export const sparseReport: EvalReportData = {
  evaluations: [
    {
      name: "Feasibility",
      status: "PASS",
    },
  ],
};

export const unknownNamesReport: EvalReportData = {
  status: "pass",
  evaluations: [
    {
      name: "CustomFutureEval",
      status: "PASS",
      explanation: "Unknown-but-valid eval module",
    },
    {
      name: "",
      status: "FAIL",
      message: "Nameless entry still renders",
    },
  ],
};

/** Backend ``EvalReport.entries`` shape for Phase 7 compatibility. */
export const backendEntriesReport: EvalReportData = {
  overall_verdict: "fail",
  entries: [
    { name: "feasibility", passed: true, reasons: [] },
    {
      name: "grounding",
      passed: false,
      reasons: ["missing citation", "invalid osm id"],
    },
  ],
};
