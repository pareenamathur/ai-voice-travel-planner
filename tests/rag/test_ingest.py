"""Phase 2 Task 2 — ingestion pipeline unit tests."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from src.rag.ingest import extract_mediawiki_article_text, ingest_city

SAMPLE_MEDIAWIKI_HTML = """
<html>
  <body>
    <div id="mw-navigation">NAV</div>
    <div id="content">
      <div id="mw-content-text">
        <p>Intro paragraph.</p>
        <h2><span class="mw-headline">See</span></h2>
        <p>See content.</p>
        <h3><span class="mw-headline">Museums</span></h3>
        <p>Museum content.</p>
      </div>
    </div>
    <div id="footer">FOOTER</div>
  </body>
</html>
""".strip()


def test_extract_mediawiki_article_text_preserves_headings():
    text = extract_mediawiki_article_text(SAMPLE_MEDIAWIKI_HTML)
    assert "Intro paragraph." in text
    assert "## See" in text
    assert "### Museums" in text
    assert "NAV" not in text
    assert "FOOTER" not in text


@pytest.mark.asyncio
async def test_ingest_city_writes_raw_and_corpus_and_is_idempotent(tmp_path: Path, monkeypatch):
    # Redirect data dirs to temp.
    raw_dir = tmp_path / "data" / "raw"
    corpus_dir = tmp_path / "data" / "corpus"

    calls: dict[str, int] = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, text=SAMPLE_MEDIAWIKI_HTML)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        docs1 = await ingest_city(
            city="jaipur",
            force_refresh=False,
            http_client=client,
            raw_dir=raw_dir,
            corpus_dir=corpus_dir,
        )

        # Second run should not refetch.
        docs2 = await ingest_city(
            city="jaipur",
            force_refresh=False,
            http_client=client,
            raw_dir=raw_dir,
            corpus_dir=corpus_dir,
        )

    assert calls["count"] == 2  # wikivoyage + wikipedia fetched once each
    assert len(docs1) == 2
    assert len(docs2) == 2

    # Files exist for both sources.
    assert (raw_dir / "jaipur" / "wikivoyage.html").exists()
    assert (raw_dir / "jaipur" / "wikipedia.html").exists()
    assert (corpus_dir / "jaipur" / "wikivoyage.txt").exists()
    assert (corpus_dir / "jaipur" / "wikipedia.txt").exists()


@pytest.mark.asyncio
async def test_ingest_city_force_refresh_refetches(tmp_path: Path):
    raw_dir = tmp_path / "data" / "raw"
    corpus_dir = tmp_path / "data" / "corpus"

    calls: dict[str, int] = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, text=SAMPLE_MEDIAWIKI_HTML)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await ingest_city(
            city="jaipur",
            force_refresh=False,
            http_client=client,
            raw_dir=raw_dir,
            corpus_dir=corpus_dir,
        )
        await ingest_city(
            city="jaipur",
            force_refresh=True,
            http_client=client,
            raw_dir=raw_dir,
            corpus_dir=corpus_dir,
        )

    assert calls["count"] == 4  # 2 sources x 2 runs (second forced)

