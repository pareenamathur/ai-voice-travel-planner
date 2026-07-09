"""POI Search service exposed via MCP Gateway as `search_pois` (Phase 1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.mcp_servers.poi_search.models import POI, osm_element_to_poi
from src.mcp_servers.poi_search.overpass import OverpassClient
from src.mcp_servers.poi_search.queries import INTEREST_MAP, build_overpass_query


class POISearchService:
    def __init__(self, *, overpass: OverpassClient) -> None:
        self._overpass = overpass

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
        - `source`: 'osm'
        """

        interests = interests or []
        query = build_overpass_query(city=city, interests=interests)
        payload = await self._overpass.run_query(query, use_cache=use_cache)

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
        return {"source": "osm", "pois": [p.model_dump() for p in unique]}


def build_default_poi_service(*, overpass_api_url: str, cache_dir: Path) -> POISearchService:
    return POISearchService(overpass=OverpassClient(base_url=overpass_api_url, cache_dir=cache_dir))

