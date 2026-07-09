# Phase 6 Evaluation — Edit Agent + Knowledge Agent

**Phase goal:** Review-gated edits (**Edit → Review → Supervisor**). Explanations bypass Review (**Knowledge → Supervisor**).

---

## Test Plan

### Automated

#### Edit Agent

| ID | Test | Expected |
|----|------|----------|
| E-01 | Edit scope parser | Correct day/block |
| E-02 | Edit → Review routing | `EditArtifact` to Review, not Supervisor |
| E-03 | No Edit → Supervisor shortcut | Integration test enforced |
| E-04 | Gateway `rebuild_day` | Edit uses Gateway only |
| E-05 | Byte-identical unchanged days | Diff test passes |

#### Knowledge Agent

| ID | Test | Expected |
|----|------|----------|
| K-01 | Knowledge → Supervisor | `AgentResult` direct; Review not invoked |
| K-02 | Citation payload | `citation_ids` present |
| K-03 | Review bypass | No Review span in explain workflow trace |
| K-04 | Gateway `retrieve_guidance` | Knowledge uses Gateway only |

#### Supervisor

| ID | Test | Expected |
|----|------|----------|
| S-01 | EDIT workflow | Edit → Review stub → Supervisor → user |
| S-02 | EXPLAIN workflow | Knowledge → Supervisor → user |

### Manual — Edits (Review-gated)

| ID | Utterance | Expected |
|----|-----------|----------|
| ED-M1 | "Make Day 2 more relaxed." | Day 2 only changes; trace shows Edit → Review → Supervisor |
| ED-M2 | "Swap Day 1 evening indoors." | Day 1 evening only |
| ED-M3 | "Reduce travel time." | Travel decreases or regrouped |
| ED-M4 | "Add one famous local food place." | One food stop added |

### Manual — Explanations (Review bypassed)

| ID | Question | Expected |
|----|----------|----------|
| EX-M1 | "Why this place?" | Citations in UI; no Review in trace |
| EX-M2 | "Is this doable?" | Feasibility reasoning + citations |
| EX-M3 | "What if it rains?" | Indoor alt or disclaimer |

---

## Exit Criteria

- [ ] Edit Agent returns artifacts to Review only
- [ ] Knowledge Agent returns to Supervisor only (Review bypassed)
- [ ] All 4 edit + 3 explain scenarios pass
- [ ] Trace confirms no Edit → User path
- [ ] Transcripts in `docs/sample-transcripts/`

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 6 complete:** ☐ Yes ☐ No — blockers: _______________
