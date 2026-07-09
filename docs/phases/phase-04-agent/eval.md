# Phase 4 Evaluation — Supervisor + Planning Agent + Review Stub

**Phase goal:** Review-gated plan workflow: **Planning → Review → Supervisor → User**. Session Manager wired. Planning never returns to Supervisor directly.

---

## Test Plan

### Automated

| ID | Test | Expected |
|----|------|----------|
| A-01 | Supervisor slot extraction | city, days, interests, pace parsed |
| A-02 | Clarifying cap via Session Manager | Stops at 6 |
| A-03 | Confirm gate | Planning not invoked without confirm |
| A-04 | Planning → Review routing | `PlanArtifact` sent to Review, not Supervisor |
| A-05 | Review → Supervisor routing | `ReviewVerdict` only path for itinerary to Supervisor |
| A-06 | No Planning → Supervisor shortcut | Integration test fails if wired incorrectly |
| A-07 | Session Manager persistence | constraints + itinerary after PASS |
| A-08 | `itinerary_approved` on PASS | Flag set true after ReviewVerdict |
| A-09 | Gateway-only tools in Planning | `search_pois`, `build_itinerary` via Gateway |
| A-10 | Observability trace | Spans for supervisor, planning, review, gateway |

### Manual (text E2E)

| ID | Test | Expected |
|----|------|----------|
| A-M1 | Happy path | confirm → plan via **Planning → Review → Supervisor** |
| A-M2 | Clarification flow | ≤6 questions, then confirm |
| A-M3 | Trace inspection | Log shows no Planning → User or Planning → Supervisor artifact skip |
| A-M4 | Session readback | `itinerary_approved=true` after plan |

### Sample transcript

```
User: Plan a 3-day trip to Jaipur. Food and culture, relaxed pace.
Supervisor: Confirm 3 days, food & culture, relaxed?
User: Yes.
[Planning → Review → Supervisor]
Supervisor: Here's your 3-day plan…
```

---

## Exit Criteria

- [ ] Supervisor reads/writes state via Session Manager only
- [ ] Planning Agent submits `PlanArtifact` to Review Agent
- [ ] Review stub returns `ReviewVerdict` to Supervisor
- [ ] Supervisor never presents itinerary without ReviewVerdict
- [ ] Text E2E happy path passes
- [ ] Observability trace shows full chain
- [ ] Sample transcript in `docs/sample-transcripts/`

---

## Metrics

| Metric | Target |
|--------|--------|
| Happy-path E2E (5 runs) | 5/5 |
| Planning → Supervisor direct calls | 0 |

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 4 complete:** ☐ Yes ☐ No — blockers: _______________
