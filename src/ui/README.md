# Companion UI — Phase 5

Vite/React companion UI. Speech recognition is client-side only (browser
Web Speech API). Transcripts are sent to the **Supervisor API only**.

## Design

Presentation follows the **Aetheric Voyage** Stitch system under
`designs/stitch/` (dark glassmorphism, Geist, purple→cyan accents).
Home emphasizes the voice card; an approved itinerary switches the shell
into the itinerary layout. `useSupervisorSession` and API contracts are
unchanged.

## Phase status

| Task | Status |
|------|--------|
| 1 — STT hook/service | Done |
| 2 — Microphone + live transcript UI | Done |
| 3 — Itinerary view | Done |
| 4 — Sources panel | Done |
| 5 — Agent trace panel | Done |
| 6 — Eval status panel | Done |
| 7 — UI → Supervisor API | Done |

## How to run

**Backend (required for live chat):**

```bash
# repo root, venv active
python -m src.api.main
# listens on http://127.0.0.1:8000
```

**Frontend:**

```bash
cd src/ui
npm install
npm run dev
# http://127.0.0.1:5173 — Vite proxies /api → :8000
```

Optional: set `VITE_API_BASE_URL=http://127.0.0.1:8000` to call the API
without the proxy (browser CORS would then need to be enabled separately).

## API endpoints used

| Method | Path | When |
|--------|------|------|
| `POST` | `/api/session/message` | After speech stop / Send — body `{ session_id?, message }` |
| `GET` | `/api/session/{session_id}/trace` | Once after each successful message (no polling) |

No other backend routes are called from the UI.

## Data flow

SpeechPanel → Supervisor `POST /api/session/message` → Supervisor reply →
ItineraryView / SourcesPanel / EvalStatusPanel (when fields present) →
TracePanel (`GET .../trace`).

Missing fields keep each panel’s empty state; nothing is invented.

## Debug UI (testing)

- **Conversation** — chat-style history with every `POST /api/session/message` request/response JSON.
- **Session Debug** — latest `session_id`, `conversation_phase`, `intent`, `task_message`, `itinerary_approved`.
- **Confirm warning** — if you send an affirmative (e.g. “yes”) and the backend returns `intent: confirm` again.
- **Console logs** — timestamped `Supervisor API →` / `←` lines for message and trace calls.
- Transcript clears only after a **successful** Supervisor response (failed requests keep the text).

## Tests

```bash
cd src/ui
npm test
```
