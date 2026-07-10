"""Ingestion pipeline for RAG corpus building (Phase 2 Task 2).

Implements **only** ingestion:
- Read enabled sources from `src.rag.config.SOURCE_PAGES`
- Download raw HTML (idempotent; cached on disk unless `force_refresh=True`)
- Extract readable MediaWiki article text (ignoring nav/sidebars/menus)
- Preserve section headings exactly as they appear
- Convert to `Document` objects
- Save raw HTML to `data/raw/` and clean text to `data/corpus/`

Does NOT implement chunking/embeddings/vector store/retrieval.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from src.rag.config import SOURCE_PAGES
from src.rag.models import CorpusSource, Document

MEDIAWIKI_USER_AGENT = "VoiceTravelPlanner/0.1 (RAG ingestion; +https://github.com/pareenamathur/ai-voice-travel-planner)"


class Ingestor(ABC):
    """Produces raw `Document` objects from a corpus source."""

    source: CorpusSource

    @abstractmethod
    async def ingest(self) -> AsyncIterator[Document]:
        """Yield documents from the configured corpus source."""


class IngestConfig:
    """Configuration for ingest (kept minimal in Phase 2 Task 1)."""

    def __init__(self, city: str, language: str = "en") -> None:
        self.city = city
        self.language = language


class MediaWikiIngestor(Ingestor):
    """Ingest Wikivoyage + Wikipedia for a single city (MediaWiki HTML)."""

    source: CorpusSource = "custom"

    def __init__(
        self,
        *,
        city: str,
        raw_dir: Path = Path("data/raw"),
        corpus_dir: Path = Path("data/corpus"),
        http_client: httpx.AsyncClient | None = None,
        force_refresh: bool = False,
    ) -> None:
        self.city = city.strip().lower()
        self.raw_dir = raw_dir
        self.corpus_dir = corpus_dir
        self.http_client = http_client
        self.force_refresh = force_refresh

    async def ingest(self) -> AsyncIterator[Document]:
        city_sources = SOURCE_PAGES.get(self.city)
        if not city_sources or not city_sources.enabled:
            return

        sources: list[tuple[CorpusSource, str]] = [
            ("wikivoyage", city_sources.wikivoyage),
            ("wikipedia", city_sources.wikipedia),
        ]

        for source, url in sources:
            html_path = self._raw_path(source)
            text_path = self._corpus_path(source)

            html = await _get_or_fetch(
                url=url,
                dest_path=html_path,
                http_client=self.http_client,
                force_refresh=self.force_refresh,
            )

            clean_text = extract_mediawiki_article_text(html)
            _write_if_missing(text_path, clean_text, force_refresh=self.force_refresh)

            doc = Document(
                doc_id=f"{self.city}:{source}",
                title=self.city.title(),
                source=source,
                source_url=url,
                language="en",
                metadata={"city": self.city},
                text=clean_text,
            )
            yield doc

    def _raw_path(self, source: CorpusSource) -> Path:
        return self.raw_dir / self.city / f"{source}.html"

    def _corpus_path(self, source: CorpusSource) -> Path:
        return self.corpus_dir / self.city / f"{source}.txt"


async def ingest_city(
    *,
    city: str,
    force_refresh: bool = False,
    http_client: httpx.AsyncClient | None = None,
    raw_dir: Path = Path("data/raw"),
    corpus_dir: Path = Path("data/corpus"),
) -> list[Document]:
    """Convenience entry point for ingestion of a city corpus (Phase 2 Task 2)."""

    ingestor = MediaWikiIngestor(
        city=city,
        raw_dir=raw_dir,
        corpus_dir=corpus_dir,
        http_client=http_client,
        force_refresh=force_refresh,
    )
    docs: list[Document] = []
    async for doc in ingestor.ingest():
        docs.append(doc)
    return docs


def extract_mediawiki_article_text(html: str) -> str:
    """Extract readable article text from MediaWiki HTML.

    Implementation intentionally targets MediaWiki pages (Wikipedia/Wikivoyage):
    we take only the content under the `mw-content-text` container, which avoids
    navigation menus/sidebars/headers/footers.

    Headings are preserved in-order and emitted as plain text lines:
    - `## Heading` for h2
    - `### Heading` for h3
    """

    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self._in_content = False
            self._content_depth = 0
            self._capture_text = False
            self._buf: list[str] = []
            self._current_line: list[str] = []
            self._heading_level: int | None = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attr_map = {k: (v or "") for k, v in attrs}
            if tag == "div" and attr_map.get("id") == "mw-content-text":
                self._in_content = True

            if self._in_content and tag == "div":
                self._content_depth += 1

            if not self._in_content:
                return

            if tag in {"h2", "h3"}:
                self._heading_level = 2 if tag == "h2" else 3
                self._capture_text = True
                self._current_line = []
                return

            if tag in {"p", "li"}:
                self._capture_text = True
                self._current_line = []
                return

        def handle_endtag(self, tag: str) -> None:
            if self._in_content and tag == "div":
                self._content_depth -= 1
                if self._content_depth <= 0:
                    self._in_content = False
                    self._content_depth = 0

            if not self._in_content and tag != "div":
                return

            if tag in {"h2", "h3"} and self._heading_level is not None:
                heading = " ".join("".join(self._current_line).split()).strip()
                if heading:
                    prefix = "##" if self._heading_level == 2 else "###"
                    self._buf.append(f"{prefix} {heading}")
                    self._buf.append("")
                self._heading_level = None
                self._capture_text = False
                self._current_line = []
                return

            if tag in {"p", "li"}:
                line = " ".join("".join(self._current_line).split()).strip()
                if line:
                    self._buf.append(line)
                    self._buf.append("")
                self._capture_text = False
                self._current_line = []

        def handle_data(self, data: str) -> None:
            if self._in_content and self._capture_text:
                self._current_line.append(data)

    parser = _Extractor()
    parser.feed(html)
    text = "\n".join(parser._buf).strip()
    return text


async def _get_or_fetch(
    *,
    url: str,
    dest_path: Path,
    http_client: httpx.AsyncClient | None,
    force_refresh: bool,
) -> str:
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists() and not force_refresh:
        return dest_path.read_text(encoding="utf-8")

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": MEDIAWIKI_USER_AGENT},
    ) if http_client is None else _null_async_cm(http_client) as client:
        c = client if http_client is None else http_client
        resp = await c.get(url)

    resp.raise_for_status()
    html = resp.text
    dest_path.write_text(html, encoding="utf-8")
    return html


def _write_if_missing(path: Path, content: str, *, force_refresh: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force_refresh:
        return
    path.write_text(content, encoding="utf-8")


class _null_async_cm:
    def __init__(self, obj: Any) -> None:
        self._obj = obj

    async def __aenter__(self) -> Any:
        return self._obj

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

