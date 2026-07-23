"""POI search session cache."""

from unittest.mock import AsyncMock

import pytest

from src.mcp_servers.poi_search.overpass import OverpassClient
from src.mcp_servers.poi_search.service import POISearchService


@pytest.mark.asyncio
async def test_search_pois_reuses_session_city_cache(tmp_path) -> None:
    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(
        return_value={
            "elements": [
                {
                    "type": "node",
                    "id": 1,
                    "lat": 26.9,
                    "lon": 75.8,
                    "tags": {"name": "Test Palace", "tourism": "attraction"},
                }
            ]
        }
    )
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    first = await service.search_pois(
        city="Jaipur",
        interests=["culture"],
        session_id="session-abc",
        use_cache=False,
    )
    second = await service.search_pois(
        city="Jaipur",
        interests=["landmark"],
        session_id="session-abc",
        use_cache=False,
    )

    assert first["live_poi_lookup"] is True
    assert second["live_poi_lookup"] is True
    assert overpass.run_query.await_count == 1
