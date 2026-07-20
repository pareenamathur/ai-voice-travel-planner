"""Eval CLI runner tests over the golden fixtures (Phase 7 Task 1)."""

from __future__ import annotations

from src.evals.run import SUITES, load_fixtures, main, run_suites


def test_five_golden_fixtures_present() -> None:
    fixtures = load_fixtures()
    names = {fixture["name"] for fixture in fixtures}
    assert names == {
        "golden_3day_relaxed",
        "overbudget_day",
        "bad_edit_collateral",
        "fake_osm_id",
        "missing_citation",
    }


def test_all_fixture_expectations_match() -> None:
    results = run_suites(set(SUITES))
    mismatched = [r for r in results if not r.matched]
    assert mismatched == [], [
        (r.fixture, r.eval_name, r.reasons) for r in mismatched
    ]


def test_golden_fixture_passes_all_evals() -> None:
    results = [r for r in run_suites(set(SUITES)) if r.fixture == "golden_3day_relaxed"]
    assert results
    assert all(r.actual_pass for r in results)


def test_failure_fixtures_fail_expected_eval() -> None:
    results = run_suites(set(SUITES))
    by_key = {(r.fixture, r.eval_name): r.actual_pass for r in results}
    assert by_key[("overbudget_day", "feasibility")] is False
    assert by_key[("fake_osm_id", "grounding")] is False
    assert by_key[("missing_citation", "grounding")] is False
    assert by_key[("bad_edit_collateral", "edit_correctness")] is False


def test_cli_exit_zero_on_all_suites(capsys) -> None:
    assert main(["--suite", "all"]) == 0
    output = capsys.readouterr().out
    assert "mismatched" in output


def test_cli_single_suite(capsys) -> None:
    assert main(["--suite", "feasibility"]) == 0
    output = capsys.readouterr().out
    assert "edit_correctness" not in output
