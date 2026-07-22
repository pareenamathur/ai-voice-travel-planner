# Voice-First AI Travel Planning Assistant

Multi-agent voice travel planner capstone. **Supervisor Agent** is the sole user-facing component; Planning and Edit workflows pass through **Review Agent** before results reach the user.

## Documentation

- [Architecture](docs/architecture.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Deployment](docs/deployment.md)
- [Decision Log](docs/decision.md)
- [Phase 0 Eval](docs/phases/phase-00-foundation/eval.md)

## Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| UI | Vite + React |
| Messages | Pydantic v2 |
| LLM | OpenAI-compatible adapter (`gpt-4o-mini` default) |
| Export | n8n webhook + Gateway `trigger_export` |
| Lint / Test | Ruff, Pytest, Vitest |

## Quick Start (local)

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
# Set CHAT_API_KEY and EMBEDDING_API_KEY in .env

# Run API
python -m src.api.main

# UI (separate terminal)
cd src/ui
npm install
npm run dev
```

- UI: `http://127.0.0.1:5173/` (Vite proxies `/api` and `/health` to port 8000)
- Health: `curl http://localhost:8000/health`

## Deployment

See **[docs/deployment.md](docs/deployment.md)** for:

- Vercel frontend (`VITE_API_BASE_URL`, root directory `src/ui`)
- Render backend (Dockerfile / `render.yaml`, CORS, Chroma startup)
- n8n export workflows (`export_itinerary.json` vs `export_itinerary_http.json`)
- Full environment variable list
- Production verification checklist

## API (Supervisor only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/session/message` | Send user message to Supervisor |
| POST | `/api/session/export` | Download approved itinerary (PDF/Markdown/JSON) |
| GET | `/api/session/{id}/trace` | Observability spans for session |

## Development

```bash
# Backend tests
pytest

# Frontend tests
cd src/ui && npm test

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
├── mcp_servers/      # MCP tools (incl. export → n8n)
├── export/           # PDF/Markdown/JSON renderers
├── rag/              # RAG + Chroma
├── evals/            # Review evals
└── ui/               # Vite companion app
workflows/            # n8n export workflows
data/                 # corpus, embeddings, caches
```

## Phase Status

| Phase | Status |
|-------|--------|
| 0 — Foundation | Complete |
| 1 — MCP & Data | Complete |
| 2 — RAG | Complete |
| 3 — Itinerary Builder | Complete |
| 4 — Supervisor + Planning | Complete |
| 5 — Voice UI | Complete |
| 6 — Edit + Knowledge | Complete |
| 7 — Review + Evals | Complete |
| 8 — Export + Deploy | Export + deployment docs (see deployment.md) |
