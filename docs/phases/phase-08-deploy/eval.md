# Phase 8 Evaluation — Automation & Deployment

**Phase goal:** Public deployed prototype, n8n PDF/email workflow, submission-ready repository.

---

## Test Plan

### n8n workflow

| ID | Test | Steps | Expected |
|----|------|-------|----------|
| N-01 | Webhook trigger | POST sample itinerary JSON | Workflow starts |
| N-02 | PDF generation | Complete workflow | Valid PDF attachment |
| N-03 | Email delivery | Use test email address | Email received with PDF |
| N-04 | Error handling | Malformed JSON payload | Workflow fails gracefully; agent notified |
| N-05 | Workflow export | Check repo | `workflows/itinerary-email.json` committed |

### Deployment

| ID | Test | Steps | Expected |
|----|------|-------|----------|
| P-01 | Public URL | Open deployed link | UI loads over HTTPS |
| P-02 | Voice planning prod | Full voice flow on deployed app | Plan generated |
| P-03 | Voice edit prod | One edit scenario | Edit applied |
| P-04 | Sources prod | Check sources panel | Live citations |
| P-05 | Eval prod | Run eval from prod or CLI | Completes; results in trace |
| P-06 | Export guard | Export without approved itinerary | Supervisor rejects; Export not invoked |
| P-07 | Export happy path | Export after Review PASS | Email + PDF received |
| P-08 | Env secrets | Review repo | No API keys committed |

### Repository deliverables

| ID | Item | Location | Expected |
|----|------|----------|----------|
| R-01 | README | `/README.md` | Multi-agent architecture, Gateway, Session Manager, Observability, eval commands |
| R-02 | Agent + tool list | README or architecture | 6 agents + Gateway tool registry |
| R-03 | Datasets | README | OSM, Wikivoyage, optional Open-Meteo |
| R-04 | Sample transcripts | `docs/sample-transcripts/` | Planning, edit, explain examples |
| R-05 | n8n workflow | `workflows/` | Importable JSON |

### Demo video checklist (5 min)

- [ ] Architecture overview (Supervisor + 5 specialists)
- [ ] Voice-based planning (show Supervisor → Planning → Review trace)
- [ ] Voice-based edit (show Edit Agent + Review evals)
- [ ] Explanation via Knowledge Agent ("why this place?")
- [ ] Sources view + eval status from Review Agent
- [ ] Export Agent → n8n email (optional if time permits)

---

## Exit Criteria

All must pass:

- [ ] Public HTTPS URL documented in README
- [ ] n8n workflow generates PDF and sends email end-to-end
- [ ] Export blocked when `itinerary_approved` is false
- [ ] Export bypasses Review (precondition enforced by Supervisor + Session Manager)
- [ ] README complete per problem statement deliverables
- [ ] Git repo clean, no secrets, eval command works from README
- [ ] Demo video recorded (link in README or submission doc)
- [ ] All prior phase evals re-run against production — no regressions

---

## Final acceptance rubric (self-assessment)

| Category | Weight | Self-score (1–5) | Notes |
|----------|--------|------------------|-------|
| Voice UX & intent handling | 25% | | |
| MCP usage & system design | 20% | | |
| Grounding & RAG quality | 15% | | |
| AI evals & iteration depth | 20% | | |
| Workflow automation | 10% | | |
| Deployment & code quality | 10% | | |

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 8 complete — project ready for submission:** ☐ Yes ☐ No — blockers: _______________
