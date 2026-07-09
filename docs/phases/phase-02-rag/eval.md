# Phase 2 Evaluation — RAG & Grounding

**Phase goal:** City guidance retrievable via Gateway tool `retrieve_guidance` with citations (Knowledge Agent only).

---

## Test Plan

### Automated

| ID | Test | Command / method | Expected |
|----|------|------------------|----------|
| R-01 | Ingest completes | `python scripts/ingest_rag.py` | Exit 0; corpus in `data/rag/` |
| R-02 | Chunk metadata | Unit test on chunks | Each has `source_url`, `section`, `city` |
| R-03 | Retrieval returns citations | `retrieve("Jaipur safety tips", k=3)` | Every chunk has `citation_id` + URL |
| R-04 | Gateway retrieval | `retrieve_guidance` via Gateway as Knowledge role | Cited chunks returned |
| R-05 | Permission denied | `retrieve_guidance` as Planning role | Rejected |
| R-06 | Empty retrieval | Obscure query | Empty list, not fabricated text |

### Manual

| ID | Test | Steps | Expected |
|----|------|-------|----------|
| R-M1 | Etiquette query | "What should I wear at temples in Jaipur?" | Relevant Wikivoyage/Wikipedia excerpt + link |
| R-M2 | Area guidance | "Best areas to stay in Jaipur" | Cited sections only |
| R-M3 | Citation click-through | Open source URLs in UI stub | Links resolve (HTTP 200) |
| R-M4 | Re-ingest idempotency | Run ingest twice | Same chunk count (±0) |

### Sample retrieval checks

| Query | Must include citation from |
|-------|---------------------------|
| Jaipur safety | Wikivoyage Jaipur |
| Local food etiquette | Wikivoyage or Wikipedia |
| City Palace background | Wikipedia City Palace Jaipur |

---

## Exit Criteria

All must pass:

- [ ] Wikivoyage Jaipur + linked Wikipedia articles ingested
- [ ] `retrieve_guidance` registered in MCP Gateway (Knowledge Agent only)
- [ ] 5/5 sample queries return ≥1 relevant cited chunk
- [ ] Zero retrieval results contain invented URLs
- [ ] Frozen corpus snapshot committed or reproducible via script
- [ ] Embedding model name recorded in `decision.md`

---

## Metrics

| Metric | Target |
|--------|--------|
| Retrieval precision (manual 10-query eval) | ≥7/10 relevant top-1 |
| Ingest time | < 5 min on dev machine |
| Chunk count (Jaipur) | ≥30 |

---

## Sign-off

| Role | Name | Date | Pass/Fail |
|------|------|------|-----------|
| Builder | | | |
| Reviewer | | | |

**Phase 2 complete:** ☐ Yes ☐ No — blockers: _______________
