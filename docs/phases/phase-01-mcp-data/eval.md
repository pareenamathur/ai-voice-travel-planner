# Phase 1 Evaluation — MCP & Data Layer + Gateway

**Phase goal:** POI Search MCP registered in Gateway; `search_pois` invocable only through Gateway with role permissions.

---

## Test Plan

### Automated

| ID | Test | Expected |
|----|------|----------|
| D-01 | Overpass client unit tests | All pass |
| D-02 | POI schema validation | Valid `osm_id`, `name`, `lat`, `lon`, `source` |
| D-03 | Gateway routes `search_pois` | Returns POIs |
| D-04 | Permission: Planning role | `search_pois` allowed |
| D-05 | Permission: Supervisor role | `search_pois` **denied** |
| D-06 | Observability tool log | Gateway emits tool_call span |
| D-07 | Direct MCP bypass blocked | Agent code has no direct Overpass import in agent layer |

### Manual

| ID | Test | Expected |
|----|------|----------|
| D-M1 | Jaipur food search via Gateway | ≥5 food POIs with OSM IDs |
| D-M2 | Jaipur culture search | ≥5 culture POIs |
| D-M3 | Tool trace | Observability log shows `search_pois` with latency |

---

## Exit Criteria

- [ ] POI Search MCP server runs independently
- [ ] `search_pois` registered in MCP Gateway
- [ ] Planning + Knowledge roles permitted; others denied
- [ ] ≥20 Jaipur POIs retrievable via Gateway
- [ ] Tool calls logged to Observability
- [ ] OSM cache under `data/`

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 1 complete:** ☐ Yes ☐ No — blockers: _______________
