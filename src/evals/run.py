"""Offline eval CLI — runs golden fixtures through the same modules Review Agent uses.

Usage:
    python -m src.evals.run --suite all
    python -m src.evals.run --suite feasibility

Exit code 0 when every fixture matches its expected pass/fail outcome.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.evals import (
    EDIT_EVALS,
    PLAN_EVALS,
    evaluate_edit_correctness,
    evaluate_feasibility,
    evaluate_grounding,
)
from src.shared.messages.types import EvalReportEntry

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SUITES = ("feasibility", "grounding", "edit_correctness")


@dataclass(frozen=True, slots=True)
class FixtureResult:
    fixture: str
    eval_name: str
    expected_pass: bool
    actual_pass: bool
    reasons: list[str]

    @property
    def matched(self) -> bool:
        return self.expected_pass == self.actual_pass


def run_eval(eval_name: str, artifact: dict[str, Any]) -> EvalReportEntry:
    """Run one eval module against a plan/edit artifact payload."""
    itinerary = artifact.get("itinerary") or {}
    if eval_name == "feasibility":
        return evaluate_feasibility(itinerary)
    if eval_name == "grounding":
        return evaluate_grounding(
            itinerary,
            poi_registry=artifact.get("poi_registry") or {},
            rag_citations=artifact.get("rag_citations") or [],
        )
    if eval_name == "edit_correctness":
        return evaluate_edit_correctness(
            itinerary,
            artifact.get("before_snapshot") or {},
            artifact.get("edit_scope") or {},
        )
    raise ValueError(f"unknown eval '{eval_name}'")


def applicable_evals(artifact_type: str) -> tuple[str, ...]:
    if artifact_type == "plan":
        return PLAN_EVALS
    if artifact_type == "edit":
        return EDIT_EVALS
    raise ValueError(f"unknown artifact_type '{artifact_type}' (expected 'plan' or 'edit')")


def run_fixture(fixture: dict[str, Any], suites: set[str]) -> list[FixtureResult]:
    name = str(fixture.get("name") or "unnamed")
    artifact_type = str(fixture.get("artifact_type") or "plan")
    artifact = fixture.get("artifact") or {}
    expected: dict[str, str] = fixture.get("expected") or {}

    allowed = applicable_evals(artifact_type)
    results: list[FixtureResult] = []
    for eval_name, verdict in expected.items():
        if eval_name not in allowed:
            raise ValueError(
                f"fixture '{name}': eval '{eval_name}' is not applicable to "
                f"'{artifact_type}' artifacts"
            )
        if eval_name not in suites:
            continue
        entry = run_eval(eval_name, artifact)
        results.append(
            FixtureResult(
                fixture=name,
                eval_name=eval_name,
                expected_pass=str(verdict).lower() == "pass",
                actual_pass=entry.passed,
                reasons=list(entry.reasons),
            )
        )
    return results


def load_fixtures(fixtures_dir: Path = FIXTURES_DIR) -> list[dict[str, Any]]:
    paths = sorted(fixtures_dir.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"no fixtures found in {fixtures_dir}")
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def run_suites(suites: set[str], fixtures_dir: Path = FIXTURES_DIR) -> list[FixtureResult]:
    results: list[FixtureResult] = []
    for fixture in load_fixtures(fixtures_dir):
        results.extend(run_fixture(fixture, suites))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run golden eval fixtures.")
    parser.add_argument(
        "--suite",
        default="all",
        choices=("all", *SUITES),
        help="Which eval suite to run (default: all).",
    )
    args = parser.parse_args(argv)
    suites = set(SUITES) if args.suite == "all" else {args.suite}

    results = run_suites(suites)
    mismatches = [r for r in results if not r.matched]

    for result in results:
        status = "OK  " if result.matched else "DIFF"
        actual = "pass" if result.actual_pass else "fail"
        expected = "pass" if result.expected_pass else "fail"
        print(
            f"[{status}] {result.fixture} :: {result.eval_name} -> {actual} "
            f"(expected {expected})"
        )
        if not result.actual_pass:
            for reason in result.reasons:
                print(f"        - {reason}")

    print(
        f"\n{len(results)} checks across {args.suite} suite(s); "
        f"{len(results) - len(mismatches)} matched, {len(mismatches)} mismatched."
    )
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
