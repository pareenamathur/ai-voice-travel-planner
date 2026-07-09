# Phase 0 Evaluation — Foundation

**Phase goal:** Multi-agent + platform scaffold — Session Manager, MCP Gateway, Observability, shared LLM adapter, Supervisor as sole API entry.

---

## Test Plan

### Automated

| ID | Test | Command / method | Expected |
|----|------|------------------|----------|
| F-01 | Repo initializes | `git status` | Clean tracked structure |
| F-02 | Dependencies install | `npm install` or `pip install -r requirements.txt` | No errors |
| F-03 | Health check | `curl /health` | `200 OK` |
| F-04 | Env template | `.env.example` exists | LLM API key, STT, n8n placeholders |
| F-05 | Lint passes | `npm run lint` or `ruff check` | Zero errors |
| F-06 | Message types | Unit test | `PlanArtifact`, `EditArtifact`, `ReviewVerdict` defined |
| F-07 | API → Supervisor only | Integration test | No specialist HTTP endpoints |
| F-08 | LLM adapter stub | Unit test | `complete(agent_role, ...)` callable |
| F-09 | Gateway permission stub | Unit test | Unauthorized role rejected |
| F-10 | Session Manager stub | Unit test | read/write/get by `session_id` |

### Manual

| ID | Test | Steps | Expected |
|----|------|-------|----------|
| F-M1 | Fresh clone setup | Follow README | Running in < 15 min |
| F-M2 | Folder layout | Inspect `src/` | `agents/*`, `platform/session`, `platform/mcp-gateway`, `platform/llm`, `platform/observability` |
| F-M3 | Decision log | Open `decision.md` | ADR-007, ADR-008, ADR-009, ADR-010 Accepted |

---

## Exit Criteria

All must pass:

- [ ] Git repo + `.gitignore`; no secrets committed
- [ ] Stack + LLM model recorded in `decision.md`
- [ ] Six agent module stubs with single-responsibility docs
- [ ] Platform stubs: Session Manager, MCP Gateway, Observability, LLM adapter
- [ ] Message contracts include Review-gated artifact types
- [ ] API routes only to Supervisor
- [ ] README points to architecture + implementation plan

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 0 complete:** ☐ Yes ☐ No — blockers: _______________
