# Phase 5 Evaluation — Voice & Companion UI

**Phase goal:** Speech-to-text input and minimal UI connected to the Supervisor Agent only — showing itinerary, transcript, sources, and agent delegation trace.

---

## Test Plan

### Automated

| ID | Test | Command / method | Expected |
|----|------|------------------|----------|
| V-01 | UI component tests | `npm test` | Itinerary blocks render |
| V-02 | API integration | Mock agent response → UI | 3 days displayed |
| V-03 | Sources binding | Fixture with citations | All citation IDs render |
| V-04 | Empty state | No itinerary yet | Sensible placeholder |

### Manual

| ID | Test | Steps | Expected |
|----|------|-------|----------|
| V-M1 | Microphone capture | Click mic, speak planning request | Transcript appears live |
| V-M2 | Voice → plan | Full voice happy path (Phase 4 flow) | Itinerary populates after confirm |
| V-M3 | Day/block layout | Inspect UI | Day 1/2/3 with morning/afternoon/evening |
| V-M4 | Duration & travel | Check each leg | `duration_min` and `travel_min` visible |
| V-M5 | Sources panel | After plan | OSM IDs + Wikivoyage/Wikipedia links |
| V-M6 | Browser compatibility | Chrome + one other browser | Mic + UI functional |
| V-M7 | Agent trace | Complete voice plan | Delegation chain visible (Supervisor → Planning → Review) |

### UI checklist (per problem statement)

- [ ] Day-wise itinerary
- [ ] Morning / afternoon / evening blocks
- [ ] Duration and travel time between stops
- [ ] Microphone button
- [ ] Live transcript
- [ ] Sources / References section
- [ ] Agent trace / eval status (recommended for demo)

---

## Exit Criteria

All must pass:

- [ ] STT integrated (browser or cloud)
- [ ] User can complete voice-only planning flow end-to-end
- [ ] UI displays full itinerary structure from agent session
- [ ] Sources panel shows RAG citations and POI source IDs
- [ ] UI connected to Supervisor backend (not hardcoded mock data in production path)
- [ ] No direct UI calls to specialist agents
- [ ] Agent trace panel shows Planning → Review → Supervisor chain
- [ ] Tool call line shows Gateway spans (e.g. `search_pois`, `build_itinerary`)
- [ ] Eval status from Session Manager `last_eval_report`
- [ ] Responsive enough for demo recording (desktop minimum)

---

## Metrics

| Metric | Target |
|--------|--------|
| Transcript latency (first partial) | < 2s |
| UI update after plan ready | < 1s |
| Voice planning E2E (3 attempts) | 3/3 success |

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 5 complete:** ☐ Yes ☐ No — blockers: _______________
