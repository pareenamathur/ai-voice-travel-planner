"""POI Search service exposed via MCP Gateway as `search_pois` (Phase 1)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from src.mcp_servers.poi_search.models import POI, osm_element_to_poi
from src.mcp_servers.poi_search.overpass import OverpassClient, OverpassError
from src.mcp_servers.poi_search.queries import INTEREST_MAP, build_overpass_query

DEFAULT_CITY_CACHE_TTL_SECONDS = 24 * 3600


class POISearchService:
    def __init__(
        self,
        *,
        overpass: OverpassClient,
        city_cache_ttl_seconds: int = DEFAULT_CITY_CACHE_TTL_SECONDS,
    ) -> None:
        self._overpass = overpass
        self.city_cache_ttl_seconds = max(0, int(city_cache_ttl_seconds))

    async def search_pois(
        self,
        *,
        city: str,
        interests: list[str] | None = None,
        max_results: int = 50,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Gateway tool handler for `search_pois`.

        Returns a JSON-serializable payload:
        - `pois`: list of POI dicts (normalized)
        - `source`: ``osm`` or ``city_cache``
        - `live_poi_lookup`: True when non-empty live/cached OSM results are returned
        """

        interests = interests or []
        city_key = _city_cache_key(city, interests)

        if use_cache and self.city_cache_ttl_seconds > 0:
            cached = self._read_city_cache(city_key)
            if cached is not None:
                pois = list(cached.get("pois") or [])[: max(1, int(max_results))]
                return {
                    "source": "city_cache",
                    "pois": pois,
                    "live_poi_lookup": True,
                }

        query = build_overpass_query(city=city, interests=interests)
        # Query-hash cache remains useful within a process; city TTL cache reduces
        # repeated Overpass hits across interest variants during development.
        try:
            payload = await self._overpass.run_query(query, use_cache=use_cache)
        except OverpassError:
            # True Overpass failure (timeouts, empty after all mirrors, HTTP errors).
            return {
                "source": "osm",
                "pois": [],
                "live_poi_lookup": False,
            }

        elements = payload.get("elements") or []
        pois: list[POI] = []

        # Best-effort category annotation: first recognized interest wins for Phase 1.
        category: str | None = None
        for interest in interests:
            mapped = INTEREST_MAP.get(interest.strip().lower())
            if mapped:
                category = mapped.category
                break

        for el in elements:
            poi = osm_element_to_poi(el, category=category)
            if poi:
                pois.append(poi)

        # De-dup by osm_id; keep first (Overpass ordering).
        seen: set[str] = set()
        unique: list[POI] = []
        for poi in pois:
            if poi.osm_id in seen:
                continue
            seen.add(poi.osm_id)
            unique.append(poi)

        unique = unique[: max(1, int(max_results))]
        poi_dicts = [p.model_dump() for p in unique]
        live = bool(poi_dicts)
        result = {
            "source": "osm",
            "pois": poi_dicts,
            "live_poi_lookup": live,
        }

        if live and use_cache and self.city_cache_ttl_seconds > 0:
            self._write_city_cache(city_key, poi_dicts)

        return result

    def _city_cache_path(self, city_key: str) -> Path:
        return self._overpass.cache_dir / f"city-{city_key}.json"

    def _read_city_cache(self, city_key: str) -> dict[str, Any] | None:
        path = self._city_cache_path(city_key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        cached_at = payload.get("cached_at")
        pois = payload.get("pois")
        if not isinstance(cached_at, (int, float)) or not isinstance(pois, list) or not pois:
            return None
        age = time.time() - float(cached_at)
        if age > self.city_cache_ttl_seconds:
            return None
        return {"pois": pois}

    def _write_city_cache(self, city_key: str, pois: list[dict[str, Any]]) -> None:
        self._overpass.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._city_cache_path(city_key)
        path.write_text(
            json.dumps({"cached_at": time.time(), "pois": pois}, ensure_ascii=True),
            encoding="utf-8",
        )


def _city_cache_key(city: str, interests: list[str] | None = None) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (city or "").strip().lower()).strip("-")
    city_part = slug or "unknown"
    interests_norm = sorted(
        {i.strip().lower() for i in (interests or []) if i and i.strip()}
    )
    if not interests_norm:
        return f"{city_part}__sightseeing"
    interest_part = "-".join(interests_norm)
    return f"{city_part}__{interest_part}"


def build_default_poi_service(
    *,
    overpass_api_url: str | None = None,
    overpass_urls: list[str] | None = None,
    cache_dir: Path,
    city_cache_ttl_seconds: int = DEFAULT_CITY_CACHE_TTL_SECONDS,
) -> POISearchService:
    urls = [u.strip() for u in (overpass_urls or []) if u and u.strip()]
    if not urls and overpass_api_url:
        urls = [overpass_api_url]
    return POISearchService(
        overpass=OverpassClient(base_urls=urls, cache_dir=cache_dir),
        city_cache_ttl_seconds=city_cache_ttl_seconds,
    )
