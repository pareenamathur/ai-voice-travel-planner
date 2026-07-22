"""Phase 1 tests — Overpass client + POI search service."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from src.api.config import DEFAULT_OVERPASS_URL, Settings
from src.mcp_servers.poi_search.models import POI, osm_element_to_poi
from src.mcp_servers.poi_search.overpass import (
    DEFAULT_REFERER,
    DEFAULT_USER_AGENT,
    OverpassClient,
    OverpassError,
)
from src.mcp_servers.poi_search.service import POISearchService


def test_poi_schema_normalization_node():
    poi = osm_element_to_poi(
        {
            "type": "node",
            "id": 123,
            "lat": 26.9124,
            "lon": 75.7873,
            "tags": {"name": "Test Place"},
        },
        category="food",
    )
    assert poi is not None
    assert isinstance(poi, POI)
    assert poi.osm_id == "node/123"
    assert poi.name == "Test Place"
    assert poi.source == "osm"
    assert poi.category == "food"


def test_poi_schema_normalization_way_center():
    poi = osm_element_to_poi(
        {
            "type": "way",
            "id": 456,
            "center": {"lat": 26.9, "lon": 75.8},
            "tags": {"name": "Way Place"},
        }
    )
    assert poi is not None
    assert poi.osm_id == "way/456"
    assert poi.lat == 26.9
    assert poi.lon == 75.8


@pytest.mark.asyncio
async def test_overpass_client_caches(tmp_path: Path):
    query = "[out:json];node(0,0,1,1);out;"
    payload = {"elements": [{"type": "node", "id": 1, "lat": 26.9, "lon": 75.8}]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(base_url="https://overpass.test/api", cache_dir=tmp_path, client=client)
        first = await oc.run_query(query, use_cache=True)
        assert first == payload

        # Second call should hit cache; change transport payload to prove it isn't used.
        payload2 = {"elements": [{"type": "node", "id": 99}]}
        transport2 = httpx.MockTransport(lambda req: httpx.Response(200, json=payload2))
        async with httpx.AsyncClient(transport=transport2) as client2:
            oc2 = OverpassClient(
                base_url="https://overpass.test/api",
                cache_dir=tmp_path,
                client=client2,
            )
            second = await oc2.run_query(query, use_cache=True)
            assert second == payload

    # Ensure cache file exists and is valid JSON.
    cached_files = list(tmp_path.glob("overpass-*.json"))
    assert cached_files
    json.loads(cached_files[0].read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_overpass_does_not_cache_empty_elements(tmp_path: Path):
    query = "[out:json];node(0,0,1,1);out;"
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"elements": []})
        return httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 7,
                        "lat": 26.9,
                        "lon": 75.8,
                        "tags": {"name": "Live POI"},
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(
            base_urls=[
                "https://overpass-a.test/api",
                "https://overpass-b.test/api",
            ],
            cache_dir=tmp_path,
            client=client,
            max_attempts_per_mirror=1,
        )
        payload = await oc.run_query(query, use_cache=True)

    assert calls["n"] == 2
    assert payload["elements"]
    # Empty response must never poison the on-disk cache.
    for path in tmp_path.glob("overpass-*.json"):
        cached = json.loads(path.read_text(encoding="utf-8"))
        assert cached.get("elements")


@pytest.mark.asyncio
async def test_overpass_ignores_poisoned_empty_cache(tmp_path: Path):
    query = "[out:json];node(0,0,1,1);out;"
    oc = OverpassClient(base_url="https://overpass.test/api", cache_dir=tmp_path)
    cache_path = oc._cache_path(query)
    cache_path.write_text(json.dumps({"elements": []}), encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "elements": [
                    {"type": "node", "id": 3, "lat": 26.9, "lon": 75.8, "tags": {"name": "A"}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        oc2 = OverpassClient(
            base_url="https://overpass.test/api",
            cache_dir=tmp_path,
            client=client,
        )
        payload = await oc2.run_query(query, use_cache=True)

    assert len(payload["elements"]) == 1
    assert json.loads(cache_path.read_text(encoding="utf-8"))["elements"]


@pytest.mark.asyncio
async def test_overpass_sends_descriptive_user_agent_and_referer(tmp_path: Path):
    query = "[out:json];node(0,0,1,1);out;"
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers.get("user-agent") == DEFAULT_USER_AGENT
        assert request.headers.get("referer") == DEFAULT_REFERER
        assert request.headers.get("content-type", "").startswith(
            "application/x-www-form-urlencoded"
        )
        assert b"data=" in request.content
        return httpx.Response(
            200,
            json={
                "elements": [
                    {"type": "node", "id": 1, "lat": 26.9, "lon": 75.8, "tags": {"name": "A"}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(
            base_url="https://overpass.test/api/interpreter",
            cache_dir=tmp_path,
            client=client,
        )
        await oc.run_query(query, use_cache=False)

    assert len(seen) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_overpass_retries_retryable_statuses_with_backoff(tmp_path: Path, status: int):
    query = "[out:json];node(0,0,1,1);out;"
    statuses: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if len(statuses) == 0:
            statuses.append(status)
            return httpx.Response(status, text="retryable")
        statuses.append(200)
        return httpx.Response(200, json={"elements": [{"type": "node", "id": 1}]})

    transport = httpx.MockTransport(handler)
    sleep = AsyncMock()
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(
            base_url="https://overpass.test/api/interpreter",
            cache_dir=tmp_path,
            client=client,
            backoff_base_seconds=0.25,
            max_attempts_per_mirror=3,
        )
        with patch("src.mcp_servers.poi_search.overpass.asyncio.sleep", sleep):
            payload = await oc.run_query(query, use_cache=False)

    assert statuses == [status, 200]
    assert payload["elements"][0]["id"] == 1
    sleep.assert_awaited_once_with(0.25)


@pytest.mark.asyncio
async def test_overpass_raises_after_retryable_exhausted(tmp_path: Path):
    query = "[out:json];node(0,0,1,1);out;"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, text="Gateway Timeout")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(
            base_url="https://overpass.test/api/interpreter",
            cache_dir=tmp_path,
            client=client,
            backoff_base_seconds=0.01,
            max_attempts_per_mirror=2,
        )
        with patch("src.mcp_servers.poi_search.overpass.asyncio.sleep", AsyncMock()):
            with pytest.raises(OverpassError, match="Overpass HTTP 504"):
                await oc.run_query(query, use_cache=False)


@pytest.mark.asyncio
async def test_overpass_fails_over_to_next_mirror(tmp_path: Path):
    query = "[out:json];node(0,0,1,1);out;"
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(str(request.url.host))
        if request.url.host == "primary.test":
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json={"elements": [{"type": "node", "id": 99}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(
            base_urls=[
                "https://primary.test/api/interpreter",
                "https://mirror.test/api/interpreter",
            ],
            cache_dir=tmp_path,
            client=client,
            backoff_base_seconds=0.01,
            max_attempts_per_mirror=1,
        )
        with patch("src.mcp_servers.poi_search.overpass.asyncio.sleep", AsyncMock()):
            payload = await oc.run_query(query, use_cache=False)

    assert hosts == ["primary.test", "mirror.test"]
    assert payload["elements"][0]["id"] == 99


def test_overpass_url_configurable_via_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OVERPASS_URL", "https://mirror.example/api/interpreter")
    cfg = Settings(_env_file=None)
    assert cfg.overpass_api_url == "https://mirror.example/api/interpreter"


def test_overpass_url_default_preserved(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OVERPASS_URL", raising=False)
    monkeypatch.delenv("OVERPASS_API_URL", raising=False)
    cfg = Settings(_env_file=None)
    assert cfg.overpass_api_url == DEFAULT_OVERPASS_URL


def test_overpass_api_url_env_still_accepted(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OVERPASS_URL", raising=False)
    monkeypatch.setenv("OVERPASS_API_URL", "https://legacy.example/api/interpreter")
    cfg = Settings(_env_file=None)
    assert cfg.overpass_api_url == "https://legacy.example/api/interpreter"


def test_overpass_mirrors_env_parsed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OVERPASS_URL", "https://primary.example/api/interpreter")
    monkeypatch.setenv(
        "OVERPASS_MIRRORS",
        "https://mirror-a.example/api/interpreter, https://mirror-b.example/api/interpreter",
    )
    cfg = Settings(_env_file=None)
    assert cfg.overpass_urls() == [
        "https://primary.example/api/interpreter",
        "https://mirror-a.example/api/interpreter",
        "https://mirror-b.example/api/interpreter",
    ]


@pytest.mark.asyncio
async def test_poi_search_caches_successful_city_lookup_for_24h(tmp_path: Path):
    overpass_payload = {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 26.91,
                "lon": 75.79,
                "tags": {"name": "Alpha Cafe", "amenity": "cafe"},
            }
        ]
    }
    hits = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        return httpx.Response(200, json=overpass_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(base_url="https://overpass.test/api", cache_dir=tmp_path, client=client)
        service = POISearchService(overpass=oc, city_cache_ttl_seconds=24 * 3600)
        first = await service.search_pois(city="Jaipur", interests=["food"], use_cache=True)
        # Same interests → city+interest cache hit (no second Overpass call).
        cached_same = await service.search_pois(city="Jaipur", interests=["food"], use_cache=True)
        # Different interests must not reuse the food cache.
        culture = await service.search_pois(city="Jaipur", interests=["culture"], use_cache=True)

    assert hits["n"] == 2
    assert first["live_poi_lookup"] is True
    assert cached_same["pois"] == first["pois"]
    assert cached_same["source"] == "city_cache"
    assert culture["source"] == "osm"


@pytest.mark.asyncio
async def test_poi_search_empty_elements_marks_not_live(tmp_path: Path):
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"elements": []}))
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(base_url="https://overpass.test/api", cache_dir=tmp_path, client=client)
        service = POISearchService(overpass=oc)
        result = await service.search_pois(city="Jaipur", interests=["landmark"], use_cache=False)

    assert result["pois"] == []
    assert result["live_poi_lookup"] is False
    assert result["source"] == "osm"


@pytest.mark.asyncio
async def test_poi_search_service_returns_pois(tmp_path: Path):
    overpass_payload = {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 26.91,
                "lon": 75.79,
                "tags": {"name": "Alpha Cafe", "amenity": "cafe"},
            },
            {
                "type": "way",
                "id": 2,
                "center": {"lat": 26.92, "lon": 75.78},
                "tags": {"name": "Beta Museum", "tourism": "museum"},
            },
        ]
    }

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=overpass_payload))
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(base_url="https://overpass.test/api", cache_dir=tmp_path, client=client)
        service = POISearchService(overpass=oc)
        result = await service.search_pois(city="Jaipur", interests=["food"], max_results=10)

    assert result["source"] == "osm"
    assert result["live_poi_lookup"] is True
    assert len(result["pois"]) == 2
    assert result["pois"][0]["osm_id"].startswith(("node/", "way/", "relation/"))
    assert result["pois"][0]["category"] == "food"
