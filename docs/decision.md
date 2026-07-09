# Decision Log

Record **important technical and business decisions** here. Each entry should be brief, dated, and include rationale plus alternatives considered.

Use this template for new entries:

```markdown
## ADR-NNN: Title

**Date:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Superseded by ADR-XXX  
**Context:** What problem or choice prompted this?  
**Decision:** What we chose.  
**Alternatives:** What else we considered.  
**Consequences:** Trade-offs, follow-up work.  
```

---

## Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-001 | Target city: Jaipur | Accepted | TBD |
| ADR-002 | MCP as tool boundary | Accepted | TBD |
| ADR-003 | Stack: Python / FastAPI / OpenAI | Accepted | 2026-07-05 |
| ADR-007 | Multi-agent architecture with Supervisor | Accepted | 2026-07-05 |
| ADR-008 | MCP Gateway (Tool Registry) | Accepted | 2026-07-05 |
| ADR-009 | Session Manager for state | Accepted | 2026-07-05 |
| ADR-010 | Shared LLM, model-agnostic adapter | Accepted | 2026-07-05 |

---

## ADR-001: Target city — Jaipur

**Date:** TBD  
**Status:** Accepted  
**Context:** Capstone scopes to one city for depth over coverage.  
**Decision:** Jaipur, India — 2–4 day itineraries; strong Wikivoyage coverage and rich OSM POI density.  
**Alternatives:** Goa (beach-heavy), Delhi (too large), Udaipur (smaller POI set).  
**Consequences:** All ingest scripts, eval fixtures, and demo transcripts reference Jaipur until ADR supersedes.

---

## ADR-002: MCP servers as the tool boundary

**Date:** TBD  
**Status:** Accepted  
**Context:** Capstone requires ≥2 MCP tools with clear orchestration.  
**Decision:** Expose **POI Search** and **Itinerary Builder** as separate MCP servers; optional tools (travel time, weather) follow same pattern.  
**Alternatives:** Single monolithic MCP; direct Python function calls without MCP protocol.  
**Consequences:** Slightly more boilerplate; better demo visibility, independent testing, and alignment with rubric.

---

## ADR-003: Stack — Python, FastAPI, OpenAI-compatible LLM

**Date:** 2026-07-05  
**Status:** Accepted  
**Context:** Phase 0 requires a runnable scaffold with API, typed messages, tests, and room for MCP/RAG/evals.  
**Decision:**

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.11+ | Strong AI/MCP ecosystem |
| API | FastAPI + Uvicorn | Async, OpenAPI, test client |
| Messages | Pydantic v2 | Typed inter-agent contracts |
| LLM | OpenAI API (`gpt-4o-mini` default) | Via model-agnostic `LLMAdapter` |
| UI | Vite + React (Phase 5) | Or Lovable export |
| STT | Browser Web Speech API (Phase 5) | No key required for MVP |
| Vector DB | Chroma (Phase 2) | Local reproducibility |
| Lint / Test | Ruff + Pytest | Phase 0 CI-ready |
| Deploy | Railway / Fly.io (Phase 8) | Public HTTPS |

**Alternatives:** Node/Fastify; Next.js monolith.  
**Consequences:** `pyproject.toml` for deps; `pip install -e ".[dev]"` for setup.

---

## ADR-004: Itinerary as canonical JSON in session

**Date:** TBD  
**Status:** Proposed  
**Context:** Edits must change only affected sections; evals need structured diffs.  
**Decision:** Store one canonical `itinerary` JSON per session; voice edits produce patches scoped by `day` and `block`.  
**Alternatives:** Free-form markdown itinerary regenerated each turn.  
**Consequences:** Requires strict schema validation in Itinerary Builder MCP.

---

## ADR-005: Heuristic travel times (not live routing)

**Date:** TBD  
**Status:** Proposed  
**Context:** Problem statement allows heuristic transit estimates.  
**Decision:** Use haversine distance + speed assumptions; optional OSRM later via Travel Time MCP.  
**Alternatives:** Google Maps API (cost, API keys); fixed 20 min between all stops.  
**Consequences:** Feasibility eval uses configurable thresholds, not ground-truth routing.

---

## ADR-006: n8n for PDF + email

**Date:** TBD  
**Status:** Proposed  
**Context:** Deliverable requires workflow automation outside core agent.  
**Decision:** n8n workflow triggered by webhook; **Export Agent** is the sole component that calls n8n. Supervisor delegates export; Export Agent handles templating handoff.  
**Alternatives:** Backend-only PDF (Puppeteer) + SendGrid; Zapier.  
**Consequences:** Export workflow versioned as n8n JSON in repo; need n8n cloud or self-hosted instance.

---

## ADR-007: Multi-agent architecture with Supervisor coordination

**Date:** 2026-07-05  
**Status:** Accepted (updated 2026-07-05)  
**Context:** Single orchestrator mixed concerns; capstone requires clear system design, evals, and MCP usage.  
**Decision:** Six agents with strict routing:

| Agent | Responsibility | Returns to |
|-------|----------------|------------|
| **Supervisor** | User conversation, routing, synthesis | User (only) |
| **Planning** | Itinerary creation | **Review Agent** |
| **Edit** | Scoped patches | **Review Agent** |
| **Knowledge** | RAG explanations | Supervisor (Review bypassed) |
| **Export** | n8n PDF/email | Supervisor (Review bypassed; approved itinerary only) |
| **Review** | Feasibility, Grounding, Edit Correctness + one retry | Supervisor |

**Plan/edit chain:** Planning/Edit → Review → Supervisor → User. Specialists never return itinerary results directly to the user or to Supervisor without Review.  
**Alternatives:** Planning → Supervisor → Review; evals as middleware; single LLM orchestrator.  
**Consequences:** Extra message types (`PlanArtifact`, `EditArtifact`); clearer quality gate and demo narrative.

---

## ADR-008: MCP Gateway (Tool Registry)

**Date:** 2026-07-05  
**Status:** Accepted  
**Context:** Direct MCP imports in agents couple specialists to tool implementations and complicate permission enforcement.  
**Decision:** Introduce **MCP Gateway** between specialist agents and MCP servers. Agents invoke logical tool names; Gateway routes, enforces per-role permissions, and logs calls to Observability.  
**Alternatives:** Direct MCP clients per agent; shared tool helper library without registry.  
**Consequences:** One extra platform module; uniform tool telemetry; easier demo of MCP calls.

---

## ADR-009: Session Manager for conversation state

**Date:** 2026-07-05  
**Status:** Accepted  
**Context:** Supervisor owning state directly mixes orchestration with persistence and complicates Review/Export preconditions.  
**Decision:** **Session Manager** owns all session fields including `itinerary_approved`. Supervisor reads/writes through Session Manager API. Review reads for context; Export precondition checked via `itinerary_approved`.  
**Alternatives:** Supervisor in-memory dict; Redis accessed by all agents.  
**Consequences:** Explicit approval flag for export; cleaner testability.

---

## ADR-010: Shared LLM with model-agnostic adapter

**Date:** 2026-07-05  
**Status:** Accepted  
**Context:** Multiple agents need LLM reasoning; separate models per agent add cost and complexity for a capstone.  
**Decision:** All agents use the **same underlying LLM** via a **model-agnostic adapter**. Agents differ by system prompt and Gateway tool permissions only. Swap providers by changing adapter config.  
**Alternatives:** Per-agent models; single monolithic prompt without agent split.  
**Consequences:** Record model ID in ADR-003; adapter interface required in Phase 0.

---

## Business / Product Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| TBD | Max 6 clarifying questions | Per capstone spec; enforced in code |
| TBD | Voice-first, UI second | UI displays state; planning optimized for speech |
| TBD | No booking / payments | Out of scope for capstone |
| TBD | Cite or disclaim | Never hallucinate tips; missing data must be explicit |
| 2026-07-05 | One retry on eval failure | Review Agent may request one regen from originating agent per plan/edit |
| 2026-07-05 | Review-gated itineraries | Planning/Edit → Review → Supervisor → User; no shortcut paths |
| 2026-07-05 | Export requires approval | `itinerary_approved` set only after Review PASS; Export bypasses Review |
| 2026-07-05 | Explain bypasses Review | Knowledge Agent → Supervisor directly |
| 2026-07-05 | Gateway-only tool access | Agents never call MCP servers directly |

---

## Superseded Decisions

*(Move entries here when replaced, with link to new ADR.)*
