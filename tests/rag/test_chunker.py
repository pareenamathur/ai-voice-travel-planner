"""Phase 2 Task 3 — section-aware chunking unit tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.rag.chunker import (
    ChunkerConfig,
    SectionAwareChunker,
    chunk_document,
    parse_sections,
    split_section_text,
)
from src.rag.models import Document

SAMPLE_DOCUMENT_TEXT = """Intro paragraph.

## See

See content paragraph one.

See content paragraph two.

### Museums

Museum content paragraph.
""".strip()


def _make_document(text: str = SAMPLE_DOCUMENT_TEXT) -> Document:
    return Document(
        doc_id="jaipur:wikivoyage",
        title="Jaipur",
        source="wikivoyage",
        source_url="https://en.wikivoyage.org/wiki/Jaipur",
        language="en",
        metadata={"city": "jaipur"},
        text=text,
    )


def test_parse_sections_preserves_headings_as_section_names():
    sections = parse_sections(SAMPLE_DOCUMENT_TEXT)
    names = [name for name, _ in sections]
    assert names == ["_intro", "See", "Museums"]
    assert sections[0][1] == "Intro paragraph."
    assert "See content paragraph one." in sections[1][1]
    assert sections[2][1] == "Museum content paragraph."


def test_chunks_never_cross_section_boundaries():
    long_see = "Word " * 400
    long_museums = "Museum " * 400
    text = f"""Intro.

## See

{long_see}

### Museums

{long_museums}
"""
    chunker = SectionAwareChunker(
        ChunkerConfig(max_chunk_characters=200, chunk_overlap_characters=40)
    )
    chunks = list(chunker.chunk(_make_document(text)))

    see_chunks = [c for c in chunks if c.section == "See"]
    museum_chunks = [c for c in chunks if c.section == "Museums"]
    intro_chunks = [c for c in chunks if c.section == "_intro"]

    assert intro_chunks
    assert len(see_chunks) > 1
    assert len(museum_chunks) > 1

    for chunk in chunks:
        assert "Museum " not in chunk.text or chunk.section == "Museums"
        assert "Word " not in chunk.text or chunk.section in {"See", "_intro"}


def test_split_section_text_applies_overlap():
    text = "alpha " * 80
    chunks = split_section_text(text, max_chars=200, overlap_chars=50)
    assert len(chunks) > 1
    # Overlap is preserved at word boundaries (may be slightly less than raw chars).
    assert any(token in chunks[1] for token in chunks[0].split()[-5:])


def test_split_section_text_never_starts_mid_word():
    # Dense text where a naive end-overlap lands inside a token (e.g. "Jaipur" → "ipur").
    text = (
        "Jaipur was founded in 1727 by Sawai Jai Singh II. "
        "It is known as the Pink City of Rajasthan. "
    ) * 40
    chunks = split_section_text(text, max_chars=200, overlap_chars=50)
    assert len(chunks) > 1

    for chunk in chunks:
        assert chunk == chunk.strip()
        # Every chunk must begin at a word/paragraph boundary in the source.
        pos = 0
        found_clean = False
        while True:
            idx = text.find(chunk, pos)
            if idx == -1:
                break
            if idx == 0 or text[idx - 1].isspace():
                found_clean = True
                break
            pos = idx + 1
        assert found_clean, f"chunk starts mid-token: {chunk[:40]!r}"

    # Regression: classic mid-word truncations from the Jaipur corpus must not appear.
    for chunk in chunks[1:]:
        assert not chunk.startswith(("ipur ", "ipur.", "6.[", "tock ", "itage "))


def test_chunking_is_deterministic():
    document = _make_document()
    chunker = SectionAwareChunker()
    first = list(chunker.chunk(document))
    second = list(chunker.chunk(document))

    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.text for c in first] == [c.text for c in second]
    assert [c.citation_id for c in first] == [c.citation_id for c in second]


def test_chunk_metadata_correctness():
    chunker = SectionAwareChunker()
    chunks = list(chunker.chunk(_make_document()))

    for index, chunk in enumerate(chunks):
        assert chunk.chunk_id.startswith("jaipur:wikivoyage::")
        assert chunk.doc_id == "jaipur:wikivoyage"
        assert chunk.metadata["city"] == "jaipur"
        assert chunk.metadata["source"] == "wikivoyage"
        assert chunk.metadata["document_id"] == "jaipur:wikivoyage"
        assert chunk.metadata["chunk_index"] == index
        assert chunk.source_url == "https://en.wikivoyage.org/wiki/Jaipur"
        assert chunk.citation_id
        assert chunk.text
        assert chunk.section in {"_intro", "See", "Museums"}


def test_chunk_document_writes_structured_json(tmp_path: Path):
    chunks_dir = tmp_path / "data" / "chunks"
    chunks = chunk_document(_make_document(), chunks_dir=chunks_dir)

    path = chunks_dir / "jaipur" / "wikivoyage.json"
    assert path.exists()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["document_id"] == "jaipur:wikivoyage"
    assert payload["city"] == "jaipur"
    assert payload["source"] == "wikivoyage"
    assert len(payload["chunks"]) == len(chunks)

    saved = payload["chunks"][0]
    assert set(saved.keys()) == {
        "chunk_id",
        "document_id",
        "city",
        "source",
        "section",
        "citation_id",
        "source_url",
        "chunk_index",
        "text",
    }


def test_chunk_document_is_idempotent_on_disk(tmp_path: Path):
    chunks_dir = tmp_path / "data" / "chunks"
    chunk_document(_make_document(), chunks_dir=chunks_dir)
    path = chunks_dir / "jaipur" / "wikivoyage.json"
    first_mtime = path.stat().st_mtime_ns

    chunk_document(_make_document(), chunks_dir=chunks_dir)
    second_mtime = path.stat().st_mtime_ns

    assert first_mtime == second_mtime
