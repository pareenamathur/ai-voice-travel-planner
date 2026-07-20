# Architecture Decision Records (ADR)

This file is the project’s **ADR log**. Update it whenever a significant architectural decision is made.

Each ADR uses this structure:

- **ADR Number**
- **Title**
- **Status** (Accepted)
- **Context**
- **Decision**
- **Consequences**

---

## ADR-001

### Title
Multi-Agent Architecture

### Status
Accepted

### Context
The system needs clear separation of responsibilities, production-oriented modularity, and a demoable delegation chain. A single orchestrator mixed user conversation, tool calls, and quality checks.

### Decision
- The **Supervisor Agent** is the **only user-facing agent**.
- Specialist agents:
  - **Planning Agent**
  - **Edit Agent**
  - **Knowledge Agent**
  - **Export Agent**
  - **Review Agent**
- The **Review Agent** is the **final quality gate** for itinerary generation and itinerary edits.

### Consequences
- Specialist agents never communicate with the user.
- Planning/Edit results must be represented as typed artifacts (`PlanArtifact`, `EditArtifact`) and gated by Review before reaching the user.

---

## ADR-002

### Title
Platform Services

### Status
Accepted

### Context
We need consistent state management, tool permission enforcement, and system observability without coupling those concerns to the agent logic.

### Decision
Introduce three platform services:
- **Session Manager**: owns all conversation/session state.
- **MCP Gateway (Tool Registry)**: single indirection point for tool calls with permission checks.
- **Observability**: captures traces for agent runs, tool calls, decisions, and evaluation results.

### Consequences
- Supervisor reads/writes state through Session Manager APIs only.
- Tools are centrally registered and audited.
- Debugging and demo UI can show end-to-end trace chains.

---

## ADR-003

### Title
Technology Stack

### Status
Accepted

### Context
Phase 0/1 require a runnable, testable backend scaffold that supports async tool calls, typed message contracts, and incremental evolution into a multi-agent system.

### Decision
- **Python 3.11+**
- **FastAPI**
- **Pydantic v2**
- **OpenAI-compatible LLM Adapter** (model-agnostic interface)
- **Ruff**
- **Pytest**

### Consequences
- Async-first code style.
- Typed contracts for inter-agent messages and platform interfaces.
- Local dev/test ergonomics via Ruff + Pytest.

---

## ADR-004

### Title
Shared LLM Strategy

### Status
Accepted

### Context
Multiple agents need reasoning, but using different models per agent increases complexity and cost for the capstone. We still want to remain provider/model-agnostic.

### Decision
- All agents use the **same underlying LLM**.
- Agents differ only by:
  - system prompt
  - MCP Gateway permissions
  - responsibility boundaries
- The LLM is accessed via a **model-agnostic adapter**.

### Consequences
- One configuration surface for model/provider.
- Easier to swap providers later without rewriting agent logic.

---

## ADR-005

### Title
MCP Design

### Status
Accepted

### Context
Directly wiring agents to MCP servers couples business logic to tool implementations and makes permission enforcement inconsistent.

### Decision
- Agents never communicate with MCP servers directly.
- All tool access flows through the **MCP Gateway**.
- The Gateway enforces per-agent-role permissions.

### Consequences
- Uniform tool telemetry and auditability.
- Clear control point to block/allow tools per role.

---

## ADR-006

### Title
State Management

### Status
Accepted

### Context
The system needs a single source of truth for constraints, itinerary state, approvals, and eval reports. The Supervisor must not “own” state directly.

### Decision
- **Session Manager** owns all conversation state (constraints, itinerary, approvals, eval status, etc.).
- The **Supervisor** reads and writes **only** through Session Manager.

### Consequences
- Review/Export preconditions become explicit (e.g., `itinerary_approved`).
- More testable, less coupled orchestration.

---

## ADR-007

### Title
Review Gate

### Status
Accepted

### Context
Itineraries must be checked for feasibility and grounding before being shown to the user. Edits must also be scope-correct. The system must support a single retry on failure.

### Decision
- Planning/Edit outputs always flow through Review:
  - Planning/Edit → Review → Supervisor → User
- Review allows **at most one regeneration** from the originating agent if an evaluation fails.
- Only Review-approved itineraries reach the Supervisor for user display.

### Consequences
- Specialist artifacts must include enough metadata for evaluation.
- Supervisor must not present raw specialist artifacts.

---

## ADR-008

### Title
Initial RAG Design

### Status
Accepted

### Context
Explanation workflows must be grounded and cite sources. We start with a single-city corpus (Jaipur) with strong public coverage.

### Decision
- Initial corpus: **Wikivoyage + Wikipedia**
- **Section-aware chunking** (preserve headings / citation boundaries)
- **Citation-first retrieval** (return passages with `citation_id`, `source_url`, `section`)
- Local vector store: **to be confirmed later** (initial direction: Chroma or equivalent)
- Embedding model: **to be selected later**

### Consequences
- Ingestion must preserve section headings exactly.
- Retrieval responses must be citation-forward and support grounding evaluation later.

---

## ADR-009

### Title
Separate chat model provider from embedding model provider

### Status
Accepted

### Context
Chat generation and embedding generation have different operational requirements (model choice, API keys, base URLs, and potentially different vendors). A single shared LLM configuration couples retrieval to generation and makes provider swaps harder.

### Decision
- Chat model and embedding model are configured **independently**.
- Chat uses `CHAT_PROVIDER`, `CHAT_MODEL`, `CHAT_API_KEY`, `CHAT_BASE_URL`.
- Embeddings use `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`.
- This allows different providers to be used for generation and retrieval.
- Improves modularity and keeps the architecture provider-agnostic.

### Consequences
- `LLMAdapter` reads only chat configuration.
- RAG embeddings read only embedding configuration.
- Environment files must define both sets of variables when both features are used.

---

## ADR-010

### Title
Embeddings provider factory

### Status
Accepted

### Context
RAG indexing and retrieval depend on embedding generation, but different vendors (OpenAI, Google, future Grok) expose different HTTP APIs and configuration. Hard-coding a single OpenAI-compatible client in pipeline functions couples business logic to one vendor and complicates swapping providers.

This builds on ADR-009, which separated chat and embedding configuration so generation and retrieval can use different models and credentials.

### Decision
- Introduce an **EmbeddingsProviderFactory** that selects the implementation from `EMBEDDING_PROVIDER`.
- Implement dedicated provider classes (`OpenAIEmbeddingsProvider`, `GoogleEmbeddingsProvider`) behind the shared `EmbeddingsProvider` interface.
- Pipeline functions (`generate_embeddings_for_city`, `generate_embeddings_for_chunks_file`) obtain a provider from the factory and remain provider-agnostic.
- Reserve factory registration for **Grok** without implementing it yet.

### Consequences
- Adding a new embeddings vendor requires a provider class and a factory branch only.
- Chat configuration remains independent of embeddings configuration.
- Tests can mock provider selection without changing pipeline signatures.

---

## ADR-011

### Title
Chroma as the local RAG vector store

### Status
Accepted

### Context
ADR-008 left the vector database choice open. Phase 2 required a reproducible local index for Jaipur corpus retrieval with city metadata filters.

### Decision
- Use **Chroma** (`PersistentClient`) as the local vector store.
- Persist under `data/rag/index/chroma` (configurable via `CHROMA_PERSIST_DIR`).
- Collection name defaults to `travel_guidance` (`CHROMA_COLLECTION_NAME`).
- Similarity search uses cosine space; city scoping is applied via metadata filters.

### Consequences
- RAG retrieval depends on a populated Chroma index for the target city.
- Index artifacts under `data/rag/index/` remain local/generated (not required in source control).

---

## ADR-012

### Title
Canonical itinerary schema and heuristic scheduling

### Status
Accepted

### Context
Planning and Edit workflows need a shared itinerary document shape, plus deterministic day scheduling and travel-time estimates without external routing APIs in early phases.

### Decision
- Define a canonical **Pydantic itinerary schema** in `src/shared/itinerary/` (`Itinerary`, `DayPlan`, `Activity`, `TravelSegment`, `TravelerConstraints`, etc.).
- Implement a **deterministic heuristic scheduler** in the Itinerary Builder MCP (`schedule_itinerary` / `schedule_day`).
- Estimate travel time with **Haversine distance** and capped mode inference (walk/drive), not live maps APIs.

### Consequences
- All itinerary producers/consumers share one schema.
- Schedules are reproducible for tests and demos.
- Travel times are approximate and may be replaced later (see future travel-time ADR).

---

## ADR-013

### Title
Itinerary Builder MCP tools registered in the Gateway

### Status
Accepted

### Context
Agents must not call itinerary construction services directly. Phase 3 required `build_itinerary` and `rebuild_day` behind the MCP Gateway with role permissions.

### Decision
- Expose **`build_itinerary`** (Planning only) and **`rebuild_day`** (Edit only) via the Itinerary Builder MCP service.
- Register both tools in the MCP Gateway using the same pattern as `search_pois`.
- Gateway permission denials and observability spans apply uniformly.

### Consequences
- Planning builds itineraries only through the Gateway.
- Edit-day rebuilds are isolated to the Edit role.
- Unauthorized roles (e.g. Supervisor, Knowledge) cannot invoke these tools.

---

## ADR-014

### Title
Session Manager full session schema (Phase 4)

### Status
Accepted

### Context
Phase 0 provided a Session Manager stub. Phase 4 requires a complete in-memory session document for constraints, clarification caps, itinerary approval, eval reports, and conversation history.

### Decision
- Session documents include: `session_id`, trip/user constraints, clarification count, `itinerary`, `itinerary_approved`, `last_eval_report`, conversation history, metadata, plus architecture fields (`poi_registry`, `rag_citations`, `conversation_phase`, `last_review_verdict`, timestamps).
- Supervisor-oriented APIs (`update_constraints`, `append_conversation_turn`, `increment_clarification_count`, `set_itinerary`, `record_eval_report`, etc.) own all mutations.
- Storage remains **in-memory** (no database) for Phases 0–4.

### Consequences
- Supervisor never stores conversation state in agent instance variables.
- Clarifying-question cap (max 6) is enforced by the Session Manager.
- Later persistence backends can implement the same API surface.

---

## ADR-015

### Title
Supervisor deterministic intent and slot extraction (no LLM in Phase 4)

### Status
Accepted

### Context
Phase 4 needs a working confirm-gated plan flow. LLM-based intent classification can wait; the Supervisor must still extract constraints and route CLARIFY / CONFIRM / PLAN reliably.

### Decision
- Implement **rule-based** intent classification and slot extraction in the Supervisor.
- Do **not** call the LLM for Supervisor turns in Phase 4 Task 2+.
- Required slots for confirmation are **city** and **days**; explicit user confirmation is required before PLAN.
- On PLAN, create a `TaskMessage` for delegation (orchestration completed in ADR-018).

### Consequences
- Deterministic, testable Supervisor behavior for demos and CI.
- Slot coverage is keyword/heuristic-based and may miss synonyms (e.g. “historical” vs “history”).
- LLM-backed Supervisor reasoning remains a future enhancement.

---

## ADR-016

### Title
Planning Agent uses Gateway tools only

### Status
Accepted

### Context
Planning must construct itineraries from confirmed constraints without talking to the user or bypassing tool permissions.

### Decision
- Planning accepts `TaskMessage(PLAN)`, validates required constraints (city, days ≥ 1).
- Planning invokes **only** `search_pois` then `build_itinerary` through `MCPGateway.invoke`.
- Planning returns a **`PlanArtifact`** (for Review), never a user-facing response.
- No LLM calls in the Planning path for Phase 4.

### Consequences
- Tool order and permissions are enforceable and observable.
- Plan quality depends on POI Search + heuristic scheduler outputs.
- Review remains the only path for approved itineraries to reach the Supervisor.

---

## ADR-017

### Title
Review Agent stub always returns PASS (Phase 4)

### Status
Accepted

### Context
Phase 4 must enforce the Planning → Review → Supervisor chain before full evaluation modules exist (Phase 7).

### Decision
- Review accepts a **`PlanArtifact`**, validates the schema, and **always** returns `ReviewVerdict(status=PASS)`.
- No evaluation modules, no LLM, no Gateway calls, no regeneration in the stub.
- Emit observability spans: `review_started`, `artifact_validated`, `review_completed`.

### Consequences
- Architecture wiring is testable end-to-end without eval flakiness.
- Real feasibility/grounding gates replace the stub in Phase 7.
- FAIL/regen paths remain placeholders until then.

---

## ADR-018

### Title
Supervisor orchestrates Planning → Review → Session persistence

### Status
Accepted

### Context
After confirm, the Supervisor must not invent itineraries or call MCP tools. It must wait for a Review verdict before updating session state or responding to the user.

### Decision
- On PLAN: Supervisor creates `TaskMessage` → invokes Planning → sends `PlanArtifact` to Review → receives `ReviewVerdict`.
- On `PASS` / `PASS_WITH_WARNINGS`: persist itinerary via Session Manager, set `itinerary_approved=true`, store `last_review_verdict` and `last_eval_report`, then respond to the user.
- On non-PASS: do not regenerate in Phase 4; return a structured placeholder for future regeneration.
- Supervisor remains the only user-facing agent; Planning/Review never speak to the user.

### Consequences
- End-to-end Phase 4 demos follow the architecture sequence diagram.
- Session approval flags are trustworthy preconditions for later Export.
- Regeneration and real evals are deferred to Phase 7.

---

## ADR-019

### Title
Browser Web Speech API for Phase 5 STT

### Status
Accepted

### Context
Phase 5 Task 1 needs speech-to-text for the companion UI. Cloud STT (Deepgram, Whisper, Google, Azure) adds cost, keys, and server-side audio handling before any microphone UI exists.

### Decision
- Use the **browser Web Speech API** only (`SpeechRecognition` / `webkitSpeechRecognition`).
- Keep recognition **fully client-side**; do not send audio or transcripts to the backend in Task 1.
- Expose a reusable service + React hook (`startListening`, `stopListening`, `transcript`, `interimTranscript`, `isListening`, support detection, `error`).
- Defer microphone UI and Supervisor API wiring to later Phase 5 tasks.

### Consequences
- Chrome/Edge (and Safari with webkit prefix) are the primary demo browsers; unsupported browsers surface `isSupported=false` / `error=not-supported`.
- No STT API keys are required for Task 1 beyond the existing `STT_PROVIDER=browser` placeholder.
- Cloud STT remains out of scope unless a future ADR revisits providers.

---

## Future ADRs (placeholders)

These will be decided in later phases and recorded here:

- **ADR-020** — Weather provider (TBD)
- **ADR-021** — Travel time provider (TBD)
- **ADR-022** — Deployment architecture (TBD)
