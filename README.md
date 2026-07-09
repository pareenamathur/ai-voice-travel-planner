# Voice-First AI Travel Planning Assistant

Multi-agent voice travel planner capstone. **Supervisor Agent** is the sole user-facing component; Planning and Edit workflows pass through **Review Agent** before results reach the user.

## Documentation

- [Architecture](docs/architecture.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Decision Log](docs/decision.md)
- [Phase 0 Eval](docs/phases/phase-00-foundation/eval.md)

## Stack (Phase 0)

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| Messages | Pydantic v2 |
| LLM | OpenAI-compatible adapter (`gpt-4o-mini` default) |
| Lint / Test | Ruff, Pytest |

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install with dev dependencies
pip install -e ".[dev]"

# Copy environment template
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux

# Run API
python -m src.api.main
# or: travel-planner

# Health check
curl http://localhost:8000/health
```

## API (Supervisor only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/session/message` | Send user message to Supervisor |
| GET | `/api/session/{id}/trace` | Observability spans for session |

## Development

```bash
# Tests
pytest

# Lint
ruff check src tests
```

## Project Structure

```
src/
├── agents/           # supervisor, planning, knowledge, edit, export, review
├── platform/         # session, mcp_gateway, llm, observability
├── shared/messages/  # typed inter-agent contracts
├── api/              # HTTP entry → Supervisor only
├── mcp_servers/      # Phase 1+
├── rag/              # Phase 2
├── evals/            # Phase 7
└── ui/               # Phase 5
data/phases/          # per-phase artifact folders
```

## Phase Status

| Phase | Status |
|-------|--------|
| 0 — Foundation | ✅ Complete |
| 1 — MCP & Data | Pending |
| 2 — RAG | Pending |
| 3 — Itinerary Builder | Pending |
| 4 — Supervisor + Planning | Pending |
| 5 — Voice UI | Pending |
| 6 — Edit + Knowledge | Pending |
| 7 — Review + Evals | Pending |
| 8 — Export + Deploy | Pending |
