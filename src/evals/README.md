# Phase 7 — Evaluation Modules

Deterministic eval suites used by the **Review Agent** at runtime and by the offline CLI.
No LLM calls; every check is reproducible.

| Eval | Applies to | Checks |
|------|------------|--------|
| `feasibility` | Plan + Edit | Daily duration ≤ window (default 600 min), per-leg travel ≤ 90 min, daily travel ≤ 240 min, activity count consistent with pace |
| `grounding` | Plan + Edit | POI ids match known source formats (`node/`, `way/`, `relation/`, `well_known/`, `llm/`), activities trace to the POI registry, grounding sources present, disclaimer required when `live_poi_lookup` is false |
| `edit_correctness` | Edit only | Scoped day exists, no collateral changes to other days, no days added/removed, `city`/`total_days` preserved |

## CLI

Runs the golden fixtures in `fixtures/` through the same modules and compares
against each fixture's expected outcome:

```bash
python -m src.evals.run --suite all
python -m src.evals.run --suite feasibility   # or grounding | edit_correctness
```

Exit code `0` means every fixture matched its expected pass/fail result.

## Golden fixtures

| Fixture | Purpose |
|---------|---------|
| `golden_3day_relaxed.json` | Passes all evals |
| `overbudget_day.json` | Fails feasibility (840 min scheduled vs 600 min budget) |
| `fake_osm_id.json` | Fails grounding (fabricated POI id + unknown reference) |
| `missing_citation.json` | Fails grounding (no sources, missing degraded-lookup disclaimer) |
| `bad_edit_collateral.json` | Fails edit correctness (day 1 mutated when scope was day 2) |
