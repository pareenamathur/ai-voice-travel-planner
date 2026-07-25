"""POI Search service exposed via MCP Gateway as `search_pois` (Phase 1)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from src.mcp_servers.poi_search.fallback import ensure_poi_source_labels
from src.mcp_servers.poi_search.models import POI, osm_element_to_poi
from src.mcp_servers.poi_search.overpass import OverpassClient, OverpassError
from src.mcp_servers.poi_search.queries import INTEREST_MAP, build_overpass_query
from src.shared.interests import missing_interests, normalize_interests, search_keys_for_interests

logger = logging.getLogger(__name__)

DEFAULT_CITY_CACHE_TTL_SECONDS = 24 * 3600
DEFAULT_POI_SEARCH_BUDGET_SECONDS = 45.0
_MIN_POIS_TO_SKIP_BROADER_SEARCH = 6


class _SearchBudget:
    """Monotonic deadline for bounded live POI lookup within one search_pois call."""

    def __init__(self, budget_seconds: float) -> None:
        self._deadline = time.perf_counter() + max(0.0, budget_seconds)

    def remaining(self) -> float:
        return max(0.0, self._deadline - time.perf_counter())

    def expired(self) -> bool:
        return self.remaining() <= 0.0


class POISearchService:
    def __init__(
        self,
        *,
        overpass: OverpassClient,
        city_cache_ttl_seconds: int = DEFAULT_CITY_CACHE_TTL_SECONDS,
        search_budget_seconds: float = DEFAULT_POI_SEARCH_BUDGET_SECONDS,
    ) -> None:
        self._overpass = overpass
        self.city_cache_ttl_seconds = max(0, int(city_cache_ttl_seconds))
        self.search_budget_seconds = max(1.0, float(search_budget_seconds))
        # In-process session cache: one successful live lookup per (session, city, interests).
        self._session_city_cache: dict[str, dict[str, Any]] = {}
        # When every mirror fails for a specific query, skip duplicate Overpass calls.
        self._session_overpass_exhausted: set[str] = set()

    async def search_pois(
        self,
        *,
        city: str,
        interests: list[str] | None = None,
        max_results: int = 50,
        use_cache: bool = True,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Gateway tool handler for `search_pois`.

        Returns a JSON-serializable payload:
        - `pois`: list of POI dicts (normalized)
        - `source`: ``osm`` or ``city_cache``
        - `live_poi_lookup`: True when non-empty live/cached OSM results are returned
        """

        interests_norm = normalize_interests(interests)
        search_keys = search_keys_for_interests(interests_norm)
        city_key = _city_cache_key(city, interests_norm)
        session_key = _session_cache_key(session_id, city, interests_norm)

        if session_key and session_key in self._session_city_cache:
            cached = self._session_city_cache[session_key]
            pois = ensure_poi_source_labels(list(cached.get("pois") or []))[
                : max(1, int(max_results))
            ]
            if pois:
                logger.info(
                    "poi_search_session_cache_hit city=%s interests=%s poi_count=%s",
                    city,
                    interests_norm,
                    len(pois),
                )
                return {
                    "source": cached.get("source", "osm"),
                    "pois": pois,
                    "live_poi_lookup": True,
                }

        if use_cache and self.city_cache_ttl_seconds > 0:
            cached = self._read_city_cache(city_key)
            if cached is not None:
                pois = ensure_poi_source_labels(list(cached.get("pois") or []))[
                    : max(1, int(max_results))
                ]
                result = {
                    "source": "city_cache",
                    "pois": pois,
                    "live_poi_lookup": True,
                }
                self._remember_session(session_key, result)
                logger.info(
                    "poi_search_city_cache_hit city=%s interests=%s poi_count=%s",
                    city,
                    interests_norm,
                    len(pois),
                )
                return result

        budget = _SearchBudget(self.search_budget_seconds)
        result = await self._live_search(
            city=city,
            interests=search_keys,
            max_results=max_results,
            use_cache=use_cache,
            session_key=session_key,
            query_label=",".join(search_keys) or "sightseeing",
            budget=budget,
            stage="combined",
        )
        pois = _dedupe_poi_dicts(list(result.get("pois") or []))

        # Supplemental lookups only when the combined Overpass call failed. A successful
        # combined query already searched every interest key; re-querying wastes latency.
        combined_failed = bool(result.get("error"))
        if interests_norm and combined_failed and not budget.expired():
            supplemental_specs = _supplemental_search_specs(
                interests_norm,
                pois,
                session_id=session_id,
                city=city,
            )
            if supplemental_specs:
                extras = await asyncio.gather(
                    *[
                        self._live_search(
                            city=city,
                            interests=spec["search_keys"],
                            max_results=max(12, max_results // 2),
                            use_cache=use_cache,
                            session_key=spec["session_key"],
                            query_label=spec["query_label"],
                            budget=budget,
                            stage="supplemental",
                        )
                        for spec in supplemental_specs
                    ]
                )
                for extra in extras:
                    pois = _merge_poi_dicts(pois, list(extra.get("pois") or []))
                    if extra.get("live_poi_lookup"):
                        result["live_poi_lookup"] = True
                    if not result.get("error") and extra.get("error"):
                        result["error"] = extra.get("error")

        result["pois"] = pois[: max(1, int(max_results))]

        if result.get("live_poi_lookup") and result.get("pois"):
            self._remember_session(session_key, result)
            return result

        exhausted_key = _exhaustion_key(session_key, "sightseeing")
        needs_broader = (
            interests_norm
            and len(pois) < _MIN_POIS_TO_SKIP_BROADER_SEARCH
            and exhausted_key not in self._session_overpass_exhausted
        )
        if needs_broader and not budget.expired():
            broader_key = _session_cache_key(session_id, city, ["sightseeing"])
            broader = await self._live_search(
                city=city,
                interests=["sightseeing"],
                max_results=max_results,
                use_cache=use_cache,
                session_key=broader_key,
                query_label="sightseeing_fallback",
                budget=budget,
                stage="broader_fallback",
            )
            merged = _merge_poi_dicts(pois, list(broader.get("pois") or []))
            if merged:
                result = {
                    **result,
                    "pois": merged[: max(1, int(max_results))],
                    "live_poi_lookup": bool(broader.get("live_poi_lookup") or result.get("live_poi_lookup")),
                    "source": broader.get("source") or result.get("source") or "osm",
                }
                if result.get("live_poi_lookup"):
                    self._remember_session(session_key, result)
                    return result

        return result

    async def _live_search(
        self,
        *,
        city: str,
        interests: list[str],
        max_results: int,
        use_cache: bool,
        session_key: str | None = None,
        query_label: str = "",
        budget: _SearchBudget | None = None,
        stage: str = "live",
    ) -> dict[str, Any]:
        query = build_overpass_query(city=city, interests=interests)
        started = time.perf_counter()
        label = query_label or ",".join(interests)
        exhaustion_key = _exhaustion_key(session_key, label)
        if exhaustion_key in self._session_overpass_exhausted:
            logger.info(
                "poi_search_skipped_exhausted city=%s stage=%s query=%s",
                city,
                stage,
                label,
            )
            return {
                "source": "osm",
                "pois": [],
                "live_poi_lookup": False,
                "error": "overpass_exhausted_for_query",
                "duration_ms": 0.0,
            }

        remaining = budget.remaining() if budget is not None else None
        if remaining is not None and remaining <= 0.0:
            logger.warning(
                "poi_search_budget_exceeded city=%s stage=%s query=%s reason=deadline_before_start",
                city,
                stage,
                label,
            )
            return {
                "source": "osm",
                "pois": [],
                "live_poi_lookup": False,
                "error": "poi_search_budget_exceeded",
                "duration_ms": 0.0,
            }

        try:
            overpass_task = self._overpass.run_query(query, use_cache=use_cache)
            if remaining is not None:
                payload = await asyncio.wait_for(overpass_task, timeout=remaining)
            else:
                payload = await overpass_task
        except asyncio.TimeoutError:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.warning(
                "poi_search_budget_exceeded city=%s stage=%s query=%s duration_ms=%s",
                city,
                stage,
                label,
                duration_ms,
            )
            return {
                "source": "osm",
                "pois": [],
                "live_poi_lookup": False,
                "error": "poi_search_budget_exceeded",
                "duration_ms": duration_ms,
            }
        except OverpassError as exc:
            self._session_overpass_exhausted.add(exhaustion_key)
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.warning(
                "poi_search_overpass_failed city=%s stage=%s query=%s duration_ms=%s error=%s",
                city,
                stage,
                label,
                duration_ms,
                str(exc)[:200],
            )
            return {
                "source": "osm",
                "pois": [],
                "live_poi_lookup": False,
                "error": str(exc)[:300],
                "duration_ms": duration_ms,
            }

        elements = payload.get("elements") or []
        pois: list[POI] = []

        for el in elements:
            poi = osm_element_to_poi(el)
            if poi:
                pois.append(poi)

        unique = _dedupe_pois(pois)
        unique = unique[: max(1, int(max_results))]
        poi_dicts = [p.model_dump() for p in unique]
        live = bool(poi_dicts)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        result = {
            "source": "osm",
            "pois": poi_dicts,
            "live_poi_lookup": live,
            "duration_ms": duration_ms,
            "element_count": len(elements),
        }

        logger.info(
            "poi_search_complete city=%s stage=%s query=%s elements=%s poi_count=%s live=%s duration_ms=%s budget_remaining_ms=%s",
            city,
            stage,
            label,
            len(elements),
            len(poi_dicts),
            live,
            duration_ms,
            round((budget.remaining() * 1000), 2) if budget is not None else None,
        )

        if live and use_cache and self.city_cache_ttl_seconds > 0:
            city_key = _city_cache_key(city, interests)
            self._write_city_cache(city_key, poi_dicts)

        return result

    def _remember_session(self, session_key: str | None, result: dict[str, Any]) -> None:
        if not session_key or not result.get("pois"):
            return
        self._session_city_cache[session_key] = {
            "source": result.get("source"),
            "pois": list(result.get("pois") or []),
            "live_poi_lookup": True,
        }

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


def _dedupe_pois(pois: list[POI]) -> list[POI]:
    seen: set[str] = set()
    unique: list[POI] = []
    for poi in pois:
        if poi.osm_id in seen:
            continue
        seen.add(poi.osm_id)
        unique.append(poi)
    return unique


def _dedupe_poi_dicts(pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for poi in pois:
        poi_id = str(poi.get("osm_id") or poi.get("poi_id") or "")
        if not poi_id or poi_id in seen:
            continue
        seen.add(poi_id)
        unique.append(poi)
    return unique


def _merge_poi_dicts(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_poi_dicts([*primary, *secondary])


def _city_cache_key(city: str, interests: list[str] | None = None) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (city or "").strip().lower()).strip("-")
    city_part = slug or "unknown"
    interests_norm = sorted(normalize_interests(interests))
    if not interests_norm:
        return f"{city_part}__sightseeing"
    interest_part = "-".join(interests_norm)
    return f"{city_part}__{interest_part}"


def _session_cache_key(
    session_id: str | None,
    city: str,
    interests: list[str] | None = None,
) -> str | None:
    if not session_id or not str(session_id).strip():
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", (city or "").strip().lower()).strip("-")
    interests_norm = "-".join(sorted(normalize_interests(interests))) or "sightseeing"
    return f"{session_id.strip()}::{slug or 'unknown'}::{interests_norm}"


def _exhaustion_key(session_key: str | None, query_label: str) -> str:
    base = session_key or "global"
    return f"{base}::{query_label}"


def _supplemental_search_specs(
    interests_norm: list[str],
    pois: list[dict[str, Any]],
    *,
    session_id: str | None,
    city: str,
) -> list[dict[str, Any]]:
    """Deduplicated supplemental lookups for interests missing after a failed combined search."""
    specs: list[dict[str, Any]] = []
    seen_key_sets: set[tuple[str, ...]] = set()
    for interest in missing_interests(interests_norm, pois):
        search_keys = tuple(search_keys_for_interests([interest]))
        if not search_keys or search_keys in seen_key_sets:
            continue
        seen_key_sets.add(search_keys)
        specs.append(
            {
                "search_keys": list(search_keys),
                "query_label": interest,
                "session_key": _session_cache_key(session_id, city, [interest]),
            }
        )
    return specs


def build_default_poi_service(
    *,
    overpass_api_url: str | None = None,
    overpass_urls: list[str] | None = None,
    cache_dir: Path,
    city_cache_ttl_seconds: int = DEFAULT_CITY_CACHE_TTL_SECONDS,
    search_budget_seconds: float = DEFAULT_POI_SEARCH_BUDGET_SECONDS,
) -> POISearchService:
    urls = [u.strip() for u in (overpass_urls or []) if u and u.strip()]
    if not urls and overpass_api_url:
        urls = [overpass_api_url]
    return POISearchService(
        overpass=OverpassClient(base_urls=urls, cache_dir=cache_dir),
        city_cache_ttl_seconds=city_cache_ttl_seconds,
        search_budget_seconds=search_budget_seconds,
    )
