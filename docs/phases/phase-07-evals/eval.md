# Phase 7 Evaluation — Review Agent + Evaluations + Observability

**Phase goal:** Review Agent is the final quality gate — three evals, one retry from originating agent, structured `ReviewVerdict`, eval results in logs and UI.

---

## Test Plan

### Review Agent orchestration

| ID | Test | Expected |
|----|------|----------|
| RV-01 | Plan workflow evals | Feasibility + Grounding on `PlanArtifact` |
| RV-02 | Edit workflow evals | Feasibility + Grounding + Edit Correctness on `EditArtifact` |
| RV-03 | Regen on plan failure | One `RegenRequest` to **Planning Agent** |
| RV-04 | Regen on edit failure | One `RegenRequest` to **Edit Agent** |
| RV-05 | No second regen | Second failure → PASS_WITH_WARNINGS or FAIL |
| RV-06 | ReviewVerdict to Supervisor only | No Review → User path |
| RV-07 | `itinerary_approved` on PASS | Session Manager flag set |
| RV-08 | `itinerary_approved` on FAIL | Flag remains false |
| RV-09 | Observability eval span | `eval_completed` with per-eval results |

### Eval modules (shared with CLI)

| ID | Test | Expected |
|----|------|----------|
| EV-01 | CLI all suites | Exit 0 on golden fixtures |
| EV-02 | Feasibility fail | `overbudget_day.json` fails |
| EV-03 | Edit fail | `bad_edit_collateral.json` fails |
| EV-04 | Grounding fail | `fake_osm_id.json` fails |
| EV-05 | Fail → regen → pass | One regen logged; then PASS |
| EV-06 | UI eval panel | Per-eval pass/fail visible |

### Golden fixtures (≥5)

| Fixture | Purpose |
|---------|---------|
| `golden_3day_relaxed.json` | Pass all |
| `overbudget_day.json` | Fail Feasibility |
| `bad_edit_collateral.json` | Fail Edit Correctness |
| `fake_osm_id.json` | Fail Grounding |
| `missing_citation.json` | Fail Grounding |

---

## Exit Criteria

- [ ] Review replaces stub with full eval orchestration
- [ ] Plan/edit artifacts never reach Supervisor without ReviewVerdict
- [ ] Three evals implemented; CLI documented
- [ ] One regen from originating agent enforced
- [ ] Eval results in Observability + UI
- [ ] Fail → regen → pass iteration documented

---

## Metrics

| Metric | Target |
|--------|--------|
| Review gate coverage (plan + edit) | 100% |
| Max regens per operation | 1 |
| Eval runtime (full suite) | < 10s |

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 7 complete:** ☐ Yes ☐ No — blockers: _______________
