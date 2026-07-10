"""RAG source configuration (Phase 2 Task 2).

Ingestion reads *exclusively* from this file. To add another city, update this
configuration only—no ingestion code changes required.
"""

from __future__ import annotations

from dataclasses import dataclass

# Phase 2 Task 3: section-aware chunking limits.
MAX_CHUNK_CHARACTERS: int = 1200
CHUNK_OVERLAP_CHARACTERS: int = 120


@dataclass(frozen=True, slots=True)
class CitySources:
    enabled: bool
    wikivoyage: str
    wikipedia: str


SOURCE_PAGES: dict[str, CitySources] = {
    "jaipur": CitySources(
        enabled=True,
        wikivoyage="https://en.wikivoyage.org/wiki/Jaipur",
        wikipedia="https://en.wikipedia.org/wiki/Jaipur",
    )
}

