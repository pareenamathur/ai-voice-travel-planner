"""Section-aware chunking for ingested travel documents."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.rag.config import CHUNK_OVERLAP_CHARACTERS, MAX_CHUNK_CHARACTERS
from src.rag.models import Chunk, Document

_SECTION_HEADING_RE = re.compile(r"^(##|###) (.+)$")


@dataclass(frozen=True)
class ChunkerConfig:
    """Configuration for section-aware chunking."""

    max_chunk_characters: int = MAX_CHUNK_CHARACTERS
    chunk_overlap_characters: int = CHUNK_OVERLAP_CHARACTERS


class Chunker(ABC):
    """Splits documents into section-aware chunks."""

    @abstractmethod
    def chunk(self, document: Document) -> Iterable[Chunk]:
        """Yield chunks for a single document."""


def parse_sections(text: str) -> list[tuple[str, str]]:
    """Split document text into (section_name, section_body) pairs.

    Headings ``##`` and ``###`` start new sections. Content before the first
    heading is assigned to section ``_intro``.
    """
    sections: list[tuple[str, str]] = []
    current_section = "_intro"
    body_lines: list[str] = []

    for line in text.splitlines():
        match = _SECTION_HEADING_RE.match(line.strip())
        if match:
            body = "\n".join(body_lines).strip()
            if body or current_section == "_intro":
                sections.append((current_section, body))
            current_section = match.group(2).strip()
            body_lines = []
            continue
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if body or not sections:
        sections.append((current_section, body))

    return sections


def split_section_text(
    text: str,
    *,
    max_chars: int,
    overlap_chars: int,
) -> list[str]:
    """Split long section text into overlapping chunks without crossing sections."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_chars, text_len)
        if end < text_len:
            window = text[start:end]
            para_break = window.rfind("\n\n")
            if para_break > max_chars // 2:
                end = start + para_break
            else:
                space_break = window.rfind(" ")
                if space_break > max_chars // 2:
                    end = start + space_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        next_start = end - overlap_chars if overlap_chars > 0 else end
        start = max(start + 1, next_start)

    return chunks


def _parse_doc_id(doc_id: str) -> tuple[str, str]:
    city, source = doc_id.split(":", 1)
    return city, source


def _section_slug(section: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-")
    return slug or "section"


def chunk_to_dict(chunk: Chunk) -> dict[str, object]:
    """Serialize a chunk to the structured JSON format."""
    city = chunk.metadata.get("city", "")
    source = chunk.metadata.get("source", "")
    chunk_index = chunk.metadata.get("chunk_index", 0)
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.doc_id,
        "city": city,
        "source": source,
        "section": chunk.section,
        "citation_id": chunk.citation_id,
        "source_url": chunk.source_url,
        "chunk_index": chunk_index,
        "text": chunk.text,
    }


def chunks_file_path(chunks_dir: Path, doc_id: str) -> Path:
    """Return the JSON path for a document's chunks."""
    city, source = _parse_doc_id(doc_id)
    return chunks_dir / city / f"{source}.json"


def save_document_chunks(
    chunks: list[Chunk],
    *,
    chunks_dir: Path,
    force_refresh: bool = False,
) -> Path:
    """Persist chunks for one document under ``data/chunks/<city>/<source>.json``."""
    if not chunks:
        raise ValueError("Cannot save empty chunk list")

    doc_id = chunks[0].doc_id
    city, source = _parse_doc_id(doc_id)
    path = chunks_dir / city / f"{source}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "document_id": doc_id,
        "city": city,
        "source": source,
        "chunks": [chunk_to_dict(chunk) for chunk in chunks],
    }
    content = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if path.exists() and not force_refresh and path.read_text(encoding="utf-8") == content:
        return path

    path.write_text(content, encoding="utf-8")
    return path


class SectionAwareChunker(Chunker):
    """Chunk documents while preserving section boundaries."""

    def __init__(self, config: ChunkerConfig | None = None) -> None:
        self._config = config or ChunkerConfig()

    def chunk(self, document: Document) -> Iterable[Chunk]:
        """Split a document into section-bounded chunks with metadata."""
        city = (document.metadata or {}).get("city")
        if not city:
            city, _ = _parse_doc_id(document.doc_id)
        source = document.source
        chunk_index = 0
        produced: list[Chunk] = []

        for section_name, section_body in parse_sections(document.text):
            section_chunks = split_section_text(
                section_body,
                max_chars=self._config.max_chunk_characters,
                overlap_chars=self._config.chunk_overlap_characters,
            )
            for section_text in section_chunks:
                section_slug = _section_slug(section_name)
                chunk_id = f"{document.doc_id}::{section_slug}::{chunk_index:04d}"
                citation_id = f"{document.doc_id}#{section_slug}#{chunk_index:04d}"
                chunk = Chunk(
                    chunk_id=chunk_id,
                    doc_id=document.doc_id,
                    text=section_text,
                    section=section_name,
                    citation_id=citation_id,
                    source_url=document.source_url,
                    metadata={
                        "city": city,
                        "source": source,
                        "chunk_index": chunk_index,
                        "document_id": document.doc_id,
                    },
                )
                produced.append(chunk)
                chunk_index += 1

        return produced


def chunk_document(
    document: Document,
    *,
    config: ChunkerConfig | None = None,
    chunks_dir: Path | None = None,
    force_refresh: bool = False,
) -> list[Chunk]:
    """Chunk one document and optionally persist chunks to disk."""
    chunker = SectionAwareChunker(config=config)
    chunks = list(chunker.chunk(document))
    if chunks_dir is not None:
        save_document_chunks(chunks, chunks_dir=chunks_dir, force_refresh=force_refresh)
    return chunks


def chunk_documents(
    documents: Iterable[Document],
    *,
    config: ChunkerConfig | None = None,
    chunks_dir: Path | None = None,
    force_refresh: bool = False,
) -> list[Chunk]:
    """Chunk multiple documents and optionally persist each to disk."""
    all_chunks: list[Chunk] = []
    for document in documents:
        all_chunks.extend(
            chunk_document(
                document,
                config=config,
                chunks_dir=chunks_dir,
                force_refresh=force_refresh,
            )
        )
    return all_chunks
