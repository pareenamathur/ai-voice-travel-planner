# Sample Test Transcripts

> **Note:** These are illustrative walkthroughs based on flows the current application supports. They are **not** automatically captured production logs. Tool names, eval outcomes, and response wording may vary slightly by session, Overpass availability, and review results.

---

## Transcript 1 — Initial voice trip request

**Input modality:** Voice (browser Web Speech API) or text chat

### Turn 1 — User

```text
Plan a 3-day Jaipur trip with food, culture and adventure at a relaxed pace.
```

### Turn 1 — Assistant (summary)

Asks for one remaining optional slot (budget) or presents a confirmation summary, depending on session state:

```text
What is your budget level — low, medium, or high?
```

*(If budget is already known, the assistant shows a confirmation summary instead.)*

**Extracted constraints (session):**

| Slot | Value |
|------|-------|
| `city` | Jaipur |
| `days` | 3 |
| `interests` | food, culture, adventure |
| `pace` | relaxed |

### Turn 2 — User

```text
Medium budget. Yes, please go ahead.
```

### Turn 2 — Assistant (summary)

```text
Your 3-day itinerary for Jaipur is ready. Open the trip panel for the full day-by-day timeline
with travel times and visit durations.
```

### Agent / tool trace (representative)

| Step | Component | Event |
|------|-----------|-------|
| 1 | Supervisor | `intent_classified` → `PLAN` |
| 2 | Planning Agent | `search_pois` via MCP Gateway |
| 3 | MCP Gateway | `tool_call_complete` — `search_pois` |
| 4 | Planning Agent | `build_itinerary` via MCP Gateway |
| 5 | MCP Gateway | `tool_call_complete` — `build_itinerary` |
| 6 | Review Agent | `eval_completed` — plan artifact |
| 7 | Supervisor | `user_response_sent` |

### Source status (trip panel)

- **Live map data** when Overpass returns OSM POIs (`metadata.live_poi_lookup: true`, `live_poi_count > 0`)
- **Curated recommendations** when only fallback catalogue POIs are used (`source: well_known`, synthetic `well_known/jaipur-*` ids)

### Review outcome (eval panel)

| Eval | Typical result |
|------|----------------|
| Feasibility | pass |
| Grounding | pass |
| Interest coverage | pass *(plan workflows only)* |

**Session flags:** `itinerary_approved: true` after `PASS` or `PASS_WITH_WARNINGS`

---

## Transcript 2 — Clarification flow

### Turn 1 — User

```text
I'd like to visit Jaipur for food and culture.
```

### Turn 1 — Assistant

```text
How many days will you be traveling?
```

**Extracted constraints:**

| Slot | Value |
|------|-------|
| `city` | Jaipur |
| `days` | *(missing — required)* |
| `interests` | food, culture |

**Intent:** `CLARIFY`  
**Agent calls:** Supervisor ↔ Session Manager only (no Planning delegation yet)

### Turn 2 — User

```text
3 days.
```

### Turn 2 — Assistant (summary)

Presents confirmation summary (city, days, interests) and waits for explicit confirmation before planning.

**Intent:** `CONFIRM` → user must confirm (e.g. “yes”, “go ahead”) to trigger `PLAN`.

---

## Transcript 3 — Itinerary edit

**Precondition:** Approved 3-day Jaipur itinerary in session.

### Turn 1 — User

```text
Make Day 2 more relaxed.
```

### Turn 1 — Assistant (summary)

```text
Your itinerary has been updated.
Day 2 is refreshed in the trip panel — check the timeline on the right for stops, travel times, and durations.
```

### Agent / tool trace (representative)

| Step | Component | Event |
|------|-----------|-------|
| 1 | Supervisor | `intent_classified` → `EDIT` |
| 2 | Edit Agent | resolves scope → Day 2 |
| 3 | Edit Agent | `rebuild_day` via MCP Gateway |
| 4 | Review Agent | Feasibility + Grounding + **Edit Correctness** |
| 5 | Supervisor | updates session itinerary |

### Edit Correctness evaluation

| Check | Expected |
|-------|----------|
| Scoped day | Day 2 rescheduled with fewer / shorter activities |
| Collateral days | Day 1 and Day 3 unchanged (byte-identical day payloads) |
| Trip-level fields | `city`, `total_days` preserved |

**Review outcome:**

| Eval | Typical result |
|------|----------------|
| Feasibility | pass |
| Grounding | pass |
| Edit correctness | pass |

---

## Transcript 4 — Missing live map data

Simulates Overpass outage, rate limiting, or empty live results (curated fallback path).

### Turn 1 — User

```text
Plan a 2-day Jaipur trip focused on culture. Go ahead.
```

### Planning pipeline (degraded)

| Step | Result |
|------|--------|
| `search_pois` | Overpass mirrors exhausted or empty → `live_poi_lookup: false` |
| Fallback | Curated catalogue POIs (`source: well_known`, ids like `well_known/jaipur-city-palace`) |
| `build_itinerary` | Schedule built from merged / fallback POIs |
| Metadata | `user_note` includes live-data limitation message |

### Assistant / UI communication

- Trip panel label: **Curated recommendations** (not “Live map data”)
- Tooltip: *“Live map verification was not available for this request.”*
- Itinerary metadata may include:  
  `Live map verification is temporarily limited. Some suggestions are from the curated fallback catalogue.`

### Review — Grounding eval

| Check | Result |
|-------|--------|
| POI id format | pass (`well_known/*` is an accepted prefix) |
| Registry traceability | pass when activities reference curated ids |
| Disclaimer | pass when `metadata.user_note` is present for degraded lookup |

**Important:** Curated fallback entries use **synthetic** ids (`well_known/jaipur-*`). They are **not** individual public OSM node URLs unless a live OSM POI was also returned.

---

## Transcript 5 (optional) — PDF download and email export

**Precondition:** `itinerary_approved: true`

### PDF download

1. User opens **Export** menu in the trip panel.
2. UI calls `POST /api/session/export` with `{ "session_id": "...", "format": "pdf" }`.
3. Supervisor → Export Agent → MCP Gateway `trigger_export` → n8n webhook → rendered PDF bytes returned.
4. Browser downloads the file.

**Requires:** `N8N_EXPORT_WEBHOOK_URL` configured on the API (see [Deployment](../docs/deployment.md)).

### Email export

1. User enters email in export UI.
2. UI calls `POST /api/session/export/email` with `{ "session_id": "...", "email": "traveler@example.com" }`.
3. Supervisor invokes n8n email workflow (`invoke_n8n_export_email`).
4. Assistant confirms delivery (when n8n + Gmail credentials are configured).

**Blocked when:** itinerary is not approved — API returns HTTP 400 with an error message.

---

## Explain flow (bonus reference)

Not one of the four required transcripts, but supported:

```text
User: Is Day 1 feasible for seniors?
```

| Step | Component |
|------|-----------|
| Intent | `EXPLAIN` |
| Knowledge Agent | `retrieve_guidance` + optional `search_pois` |
| RAG citations | Wikivoyage / Wikipedia chunks surfaced in Sources panel |
| Review | **not** invoked for explain flows |
