# Phase 3 Evaluation — Itinerary Builder MCP

**Phase goal:** Itinerary Builder MCP tools `build_itinerary` and `rebuild_day` registered in Gateway with role permissions.

---

## Test Plan

### Automated

| ID | Test | Command / method | Expected |
|----|------|------------------|----------|
| I-01 | Schema validation | Validate output against JSON Schema | Pass |
| I-02 | Block structure | Unit test | Each day has morning/afternoon/evening |
| I-03 | Duration fields | Unit test | Every stop has `duration_min`, `travel_min` |
| I-04 | Pace: relaxed vs packed | Same POIs, different pace | Relaxed has fewer stops per day |
| I-05 | `rebuild_day` isolation | Rebuild Day 2 only | Day 1 and Day 3 byte-identical |
| I-06 | Gateway permissions | `build_itinerary` as Planning | Allowed |
| I-07 | Gateway permissions | `rebuild_day` as Edit | Allowed |
| I-08 | Gateway permissions | `build_itinerary` as Edit | Denied |

### Manual

| ID | Test | Steps | Expected |
|----|------|-------|----------|
| I-M1 | 3-day Jaipur plan | 25 POIs, relaxed pace, 09:00–21:00 | 3 days, no empty blocks unless intentional |
| I-M2 | Geographic sanity | Inspect map or lat/lon | Same-day stops not wildly scattered |
| I-M3 | Category mix | interests=[food, culture] | Each day includes both categories |
| I-M4 | Invalid input | 0 POIs | Structured error, no partial itinerary |

### Fixture scenarios

| Scenario | Input | Expected |
|----------|-------|----------|
| 2-day packed | 15 POIs, pace=packed | 2 days, high stop count |
| 4-day relaxed | 20 POIs, pace=relaxed | 4 days, ≤3 major stops/day |
| Rebuild evening | `rebuild_day(day=1, block=evening, indoor=true)` | Only Day 1 evening changes |

---

## Exit Criteria

All must pass:

- [ ] `build_itinerary` and `rebuild_day` registered in MCP Gateway with correct role permissions
- [ ] Canonical itinerary JSON schema committed to repo
- [ ] 3-day sample itinerary generated from Phase 1 POIs
- [ ] `rebuild_day` preserves unchanged days exactly
- [ ] All stops reference POIs from input list (no invented stops)
- [ ] Unit tests green for scheduling and travel heuristics

---

## Metrics

| Metric | Target |
|--------|--------|
| Daily activity time (relaxed) | ≤ 12 hours |
| Travel time per leg (heuristic) | ≤ 45 min default max |
| Schema validation | 100% on fixtures |

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 3 complete:** ☐ Yes ☐ No — blockers: _______________
