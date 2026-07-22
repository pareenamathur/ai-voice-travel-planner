# Deployment

Public prototype: **Vite/React** on Vercel, **FastAPI** on Render (Docker), **n8n** for export (Cloud or self-hosted).

## Architecture (unchanged)

```
Browser → Vercel (UI) → Render (API) → MCP Gateway → Agents
                                              ↓
                                    n8n webhook → PDF / Markdown / JSON
```

Supervisor remains the only user-facing agent. Export bypasses Review. Session Manager is the source of truth.

## Environment variables

Copy `.env.example` to `.env` for local API development. Production values:

| Variable | Where | Required | Description |
|----------|--------|----------|-------------|
| `CHAT_API_KEY` | Backend | Yes | OpenAI-compatible chat API key |
| `CHAT_MODEL` | Backend | No | Default `gpt-4o-mini` |
| `CHAT_BASE_URL` | Backend | No | Custom OpenAI-compatible base URL |
| `EMBEDDING_API_KEY` | Backend | Yes* | Embeddings for RAG (*bundled Jaipur embeddings work without re-embed at runtime) |
| `EMBEDDING_MODEL` | Backend | No | Default `text-embedding-3-small` |
| `EMBEDDING_BASE_URL` | Backend | No | Custom embeddings base URL |
| `HOST` | Backend | No | Default `0.0.0.0` |
| `PORT` | Backend | No | Default `8000` (Render sets `PORT` automatically) |
| `LOG_LEVEL` | Backend | No | Default `INFO` |
| `SESSION_TTL_SECONDS` | Backend | No | Default `3600` |
| `OVERPASS_URL` | Backend | No | Overpass interpreter URL |
| `OVERPASS_MIRRORS` | Backend | No | Comma-separated fallback mirrors |
| `OSM_CACHE_DIR` | Backend | No | OSM cache path |
| `POI_CITY_CACHE_TTL_SECONDS` | Backend | No | POI city cache TTL |
| `CHROMA_PERSIST_DIR` | Backend | No | Chroma persistence (Docker: `/app/data/rag/index/chroma`) |
| `CHROMA_COLLECTION_NAME` | Backend | No | Default `travel_guidance` |
| `N8N_EXPORT_WEBHOOK_URL` | Backend | Yes (export) | Full n8n production webhook URL |
| `CORS_ORIGINS` | Backend | Yes (prod) | Comma-separated UI origins, e.g. `https://your-app.vercel.app` |
| `EXPORT_RENDER_SECRET` | Backend + n8n | Yes (HTTP workflow) | Protects `/api/internal/export/render` |
| `VITE_API_BASE_URL` | Frontend (Vercel) | Yes (prod) | Backend base URL, no trailing slash |

Optional / local: `STT_PROVIDER`, `DEEPGRAM_API_KEY`.

## Backend (Render)

1. Push this repository to GitHub.
2. In [Render](https://render.com): **New → Blueprint** and connect the repo (uses `render.yaml`), or **New → Web Service → Docker** with `Dockerfile` at repo root.
3. Set secret environment variables in the Render dashboard (`CHAT_API_KEY`, `EMBEDDING_API_KEY`, `N8N_EXPORT_WEBHOOK_URL`, `CORS_ORIGINS`, `EXPORT_RENDER_SECRET`).
4. Deploy. Note the service URL, e.g. `https://voice-travel-planner-api.onrender.com`.
5. Verify: `GET https://<api-host>/health` → `{"status":"ok",...}`.

The container runs `scripts/ensure_chroma_index.py` on startup to build Chroma from bundled Jaipur embeddings.

Local Docker:

```bash
docker compose up --build api
```

## Frontend (Vercel)

1. Import the GitHub repo in [Vercel](https://vercel.com).
2. Set **Root Directory** to `src/ui`.
3. Framework preset: **Vite** (`vercel.json` is included).
4. Environment variable (Production + Preview):  
   `VITE_API_BASE_URL=https://<your-render-api-host>` (no trailing slash).
5. Deploy. SPA routing is handled via `rewrites` in `src/ui/vercel.json`.

Local production build against a remote API:

```bash
cd src/ui
set VITE_API_BASE_URL=https://your-api.onrender.com   # Windows
npm run build && npm run preview
```

## n8n export

Choose one workflow:

| Workflow | Use when |
|----------|----------|
| `workflows/export_itinerary.json` | Self-hosted n8n on a machine with this repo and Python (`Execute Command` runs `python -m src.mcp_servers.export.runner`) |
| `workflows/export_itinerary_http.json` | **n8n Cloud** or any host without shell access |

### HTTP workflow (recommended for Cloud)

1. Import `workflows/export_itinerary_http.json`.
2. In n8n, set environment variables:
   - `API_EXPORT_RENDER_URL` = `https://<api-host>/api/internal/export/render`
   - `EXPORT_RENDER_SECRET` = same value as on the API
3. Activate the workflow.
4. Copy the **Production** webhook URL → set backend `N8N_EXPORT_WEBHOOK_URL`.

**Webhook URL format:** `https://<n8n-host>/webhook/export-itinerary`  
(Test URL uses `/webhook-test/export-itinerary` until activated.)

5. Restart the API after setting `N8N_EXPORT_WEBHOOK_URL`.

## Local development

```bash
# API
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env   # add CHAT_API_KEY, EMBEDDING_API_KEY
python -m src.api.main

# UI (proxy to localhost:8000 — no VITE_API_BASE_URL needed)
cd src/ui && npm install && npm run dev
```

Open `http://127.0.0.1:5173/`. API health: `http://127.0.0.1:8000/health`.

For export locally without n8n, point `N8N_EXPORT_WEBHOOK_URL` at a running n8n instance or use API tests that mock the webhook.

## Production verification checklist

Against the deployed UI and API:

- [ ] **Planning** — create a Jaipur trip from chat
- [ ] **Confirmation** — confirm when prompted
- [ ] **Review** — eval panel shows pass/fail after plan/edit
- [ ] **Edit** — change a day after approval flow as designed
- [ ] **Recommend** — ask for food/market suggestions
- [ ] **Explain** — ask about a POI or feasibility
- [ ] **Export** — download PDF/Markdown/JSON only when itinerary is approved

## Public URLs (fill after deploy)

| Service | URL |
|---------|-----|
| Frontend | `https://<your-project>.vercel.app` |
| Backend | `https://<your-service>.onrender.com` |
| n8n webhook | `https://<your-n8n>/webhook/export-itinerary` |

Replace placeholders in this table after your first successful deploy.
