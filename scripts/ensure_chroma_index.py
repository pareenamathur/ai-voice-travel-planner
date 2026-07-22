#!/usr/bin/env python3
"""Build Chroma from bundled embeddings (no API key). Used at container startup."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.vector_store import index_city  # noqa: E402


async def main() -> None:
    city = (sys.argv[1] if len(sys.argv) > 1 else "jaipur").strip().lower()
    paths = await index_city(city)
    print(f"Chroma index ready for {city!r} ({len(paths)} embedding file(s)).")


if __name__ == "__main__":
    asyncio.run(main())
