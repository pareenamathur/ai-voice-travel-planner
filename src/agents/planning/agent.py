"""Planning Agent — itinerary creation via MCP Gateway only (Phase 4 Task 3)."""

from __future__ import annotations

import time
from typing import Any

from src.agents.base import BaseAgent
from src.mcp_servers.poi_search.fallback import parse_llm_pois_payload, well_known_pois_for_city
from src.mcp_servers.poi_search.overpass import OverpassError
from src.shared.messages.types import (
    AgentRole,
    PlanArtifact,
    TaskMessage,
    TaskType,
    TripConstraints,
)

LIVE_POI_UNAVAILABLE_NOTE = (
    "Live place lookup was temporarily unavailable. This itinerary uses general "
    "destination knowledge instead of live map data."
)

# Food / dining must not enter sightseeing schedules unless the traveler asked for food.
_FOOD_POI_CATEGORIES = frozenset({"food"})


class PlanningAgent(BaseAgent):
    """Invokes ``search_pois`` + ``build_itinerary`` via MCP Gateway. Never user-facing."""

    role = AgentRole.PLANNING

    async def run(self, task: TaskMessage) -> PlanArtifact:
        """Accept a PLAN TaskMessage and return a PlanArtifact for Review."""
        constraints = self._validate_task(task)
        correlation_id = task.correlation_id

        if self.gateway is None:
            raise ValueError("Planning Agent requires an MCP Gateway")

        self._trace(
            "planning_started",
            correlation_id,
            session_id=task.session_id,
            city=constraints.city,
            days=constraints.days,
        )

        run_started = time.perf_counter()
        pois, live_poi_lookup, search_source = await self._resolve_pois(
            constraints,
            correlation_id,
            task.session_id,
        )
        unfiltered = list(pois)
        pois = _filter_pois_for_planning(pois, list(constraints.interests or []))
        if not pois and unfiltered:
            pois = unfiltered
        self._trace(
            "planning_pois_selected",
            correlation_id,
            poi_count=len(pois),
            interests=list(constraints.interests or []),
        )
        itinerary_payload = await self._build_itinerary(constraints, pois, correlation_id)

        itinerary = dict(itinerary_payload.get("itinerary") or {})
        itinerary_meta = dict(itinerary.get("metadata") or {})
        itinerary_meta["live_poi_lookup"] = live_poi_lookup
        itinerary_meta["search_source"] = search_source
        if not live_poi_lookup:
            itinerary_meta["user_note"] = LIVE_POI_UNAVAILABLE_NOTE
        itinerary["metadata"] = itinerary_meta

        citations = _build_plan_citations(
            city=constraints.city,
            live_poi_lookup=live_poi_lookup,
            search_source=search_source,
            pois=pois,
        )
        itinerary["citations"] = citations

        poi_registry = self._build_poi_registry(pois, itinerary)
        artifact = PlanArtifact(
            itinerary=itinerary,
            poi_registry=poi_registry,
            rag_citations=list(citations),
            correlation_id=correlation_id,
            constraints=constraints.model_dump(mode="json"),
            metadata={
                "session_id": task.session_id,
                "source": "planning_agent",
                "tools_used": ["search_pois", "build_itinerary"],
                "poi_count": len(pois),
                "search_source": search_source,
                "live_poi_lookup": live_poi_lookup,
                "itinerary_source": itinerary_payload.get("source", "itinerary_builder"),
            },
        )

        self._trace(
            "plan_artifact_created",
            correlation_id,
            session_id=task.session_id,
            day_count=itinerary.get("total_days"),
            poi_registry_size=len(poi_registry),
            live_poi_lookup=live_poi_lookup,
            duration_ms=round((time.perf_counter() - run_started) * 1000, 2),
        )
        return artifact

    async def handle_regen(self, hints: dict[str, Any], correlation_id: str) -> PlanArtifact:
        """Stub for future Review regen — not implemented in Task 3."""
        self._trace("regen_requested", correlation_id, hints=hints)
        return PlanArtifact(itinerary={}, correlation_id=correlation_id)

    def _validate_task(self, task: TaskMessage) -> TripConstraints:
        if not isinstance(task, TaskMessage):
            raise ValueError("task must be a TaskMessage")
        if task.task_type != TaskType.PLAN:
            raise ValueError(f"Planning Agent requires task_type=PLAN, got '{task.task_type}'")
        if not task.session_id or not str(task.session_id).strip():
            raise ValueError("session_id is required")
        if not task.correlation_id or not str(task.correlation_id).strip():
            raise ValueError("correlation_id is required")

        raw = task.payload.get("constraints")
        if raw is None:
            raise ValueError("PLAN payload.constraints is required")
        if not isinstance(raw, dict):
            raise ValueError("PLAN payload.constraints must be a dict")

        try:
            constraints = TripConstraints.model_validate(raw)
        except Exception as exc:
            raise ValueError(f"invalid PLAN constraints: {exc}") from exc

        city = (constraints.city or "").strip()
        if not city:
            raise ValueError("PLAN constraints.city is required")
        if constraints.days is None or constraints.days < 1:
            raise ValueError("PLAN constraints.days must be at least 1")

        # Normalize city whitespace for downstream tools.
        return constraints.model_copy(update={"city": city})

    async def _resolve_pois(
        self,
        constraints: TripConstraints,
        correlation_id: str,
        session_id: str | None,
    ) -> tuple[list[dict[str, Any]], bool, str]:
        """Return (pois, live_poi_lookup, search_source). Never abort on Overpass failure."""
        try:
            result = await self._search_pois(constraints, correlation_id, session_id)
        except OverpassError as exc:
            self._trace(
                "poi_lookup_degraded",
                correlation_id,
                reason="overpass_error",
                detail=str(exc)[:200],
                city=constraints.city,
            )
            pois = await self._fallback_pois(constraints, correlation_id)
            source = pois[0].get("source", "well_known") if pois else "well_known"
            return pois, False, str(source)

        pois = result.get("pois") or []
        if not isinstance(pois, list):
            raise ValueError("search_pois.pois must be a list")

        source = str(result.get("source") or "osm")
        live = bool(result.get("live_poi_lookup", bool(pois)))
        if pois and source in ("osm", "city_cache"):
            live = True
        if live and pois:
            self._trace(
                "poi_search_complete",
                correlation_id,
                poi_count=len(pois),
                source=source,
                live_poi_lookup=True,
                duration_ms=result.get("duration_ms"),
            )
            return pois, True, source

        self._trace(
            "poi_lookup_degraded",
            correlation_id,
            reason="empty_or_failed_live_search",
            city=constraints.city,
            duration_ms=result.get("duration_ms"),
            error=result.get("error"),
        )
        fallback = await self._fallback_pois(constraints, correlation_id)
        fallback_source = fallback[0].get("source", "well_known") if fallback else "well_known"
        return fallback, False, str(fallback_source)

    async def _search_pois(
        self,
        constraints: TripConstraints,
        correlation_id: str,
        session_id: str | None,
    ) -> dict[str, Any]:
        assert self.gateway is not None
        self._trace("search_pois", correlation_id, city=constraints.city)
        poi_started = time.perf_counter()
        result = await self.gateway.invoke(
            AgentRole.PLANNING,
            "search_pois",
            {
                "city": constraints.city,
                "interests": list(constraints.interests or []),
                "session_id": session_id,
            },
            correlation_id=correlation_id,
        )
        self._trace(
            "poi_search_stage",
            correlation_id,
            duration_ms=round((time.perf_counter() - poi_started) * 1000, 2),
        )
        if not isinstance(result, dict):
            raise ValueError("search_pois must return a dict payload")
        return result

    async def _fallback_pois(
        self,
        constraints: TripConstraints,
        correlation_id: str,
    ) -> list[dict[str, Any]]:
        """Use LLM (best-effort) plus well-known attractions when live map data is unavailable."""
        interests = list(constraints.interests or [])
        well_known = well_known_pois_for_city(constraints.city, interests=interests)
        if len(well_known) >= 4:
            self._trace(
                "fallback_pois_ready",
                correlation_id,
                source="well_known",
                poi_count=len(well_known),
            )
            return well_known

        llm_pois: list[dict[str, Any]] = []
        if self.llm is not None:
            try:
                completion = await self.llm.complete(
                    AgentRole.PLANNING,
                    [
                        {
                            "role": "user",
                            "content": (
                                f"List well-known attractions for {constraints.city} as JSON array "
                                'of objects with keys name, lat, lon, category. Interests: '
                                f"{', '.join(interests) or 'general sightseeing'}."
                            ),
                        }
                    ],
                )
                content = str(completion.get("content") or "")
                llm_pois = parse_llm_pois_payload(content, city=constraints.city)
            except Exception as exc:  # noqa: BLE001 — fallback must never abort planning
                self._trace(
                    "fallback_llm_pois_failed",
                    correlation_id,
                    detail=str(exc)[:200],
                )

        well_known = well_known_pois_for_city(constraints.city, interests=interests)
        if llm_pois:
            # Prefer LLM names when present; fill gaps from curated catalog.
            merged = list(llm_pois)
            seen = {p.get("osm_id") for p in merged}
            seen_names = {str(p.get("name") or "").lower() for p in merged}
            for poi in well_known:
                name = str(poi.get("name") or "").lower()
                if poi.get("osm_id") in seen or name in seen_names:
                    continue
                merged.append(poi)
            self._trace(
                "fallback_pois_ready",
                correlation_id,
                source="llm",
                poi_count=len(merged),
            )
            return merged

        self._trace(
            "fallback_pois_ready",
            correlation_id,
            source="well_known",
            poi_count=len(well_known),
        )
        return well_known

    async def _build_itinerary(
        self,
        constraints: TripConstraints,
        pois: list[dict[str, Any]],
        correlation_id: str,
    ) -> dict[str, Any]:
        assert self.gateway is not None
        traveler_constraints = {
            "interests": list(constraints.interests or []),
            "pace": constraints.pace,
            "party_size": constraints.party_size,
            "mobility_notes": constraints.mobility_notes,
            "metadata": {
                "budget": constraints.budget,
                "travel_dates": constraints.travel_dates,
                "food_preferences": list(constraints.food_preferences or []),
                "transport_preferences": list(constraints.transport_preferences or []),
            },
        }
        # Drop None values for cleaner tool input.
        traveler_constraints = {
            key: value for key, value in traveler_constraints.items() if value is not None
        }

        params: dict[str, Any] = {
            "city": constraints.city,
            "pois": pois,
            "total_days": constraints.days,
            "traveler_constraints": traveler_constraints,
        }
        if constraints.travel_dates and _looks_like_iso_date(constraints.travel_dates):
            params["start_date"] = constraints.travel_dates[:10]

        self._trace(
            "build_itinerary",
            correlation_id,
            city=constraints.city,
            total_days=constraints.days,
            poi_count=len(pois),
        )
        build_started = time.perf_counter()
        result = await self.gateway.invoke(
            AgentRole.PLANNING,
            "build_itinerary",
            params,
            correlation_id=correlation_id,
        )
        self._trace(
            "itinerary_builder_stage",
            correlation_id,
            duration_ms=round((time.perf_counter() - build_started) * 1000, 2),
        )
        if not isinstance(result, dict):
            raise ValueError("build_itinerary must return a dict payload")
        return result

    def _build_poi_registry(
        self,
        pois: list[dict[str, Any]],
        itinerary: dict[str, Any],
    ) -> dict[str, Any]:
        registry: dict[str, Any] = {}
        for poi in pois:
            poi_id = poi.get("osm_id") or poi.get("poi_id")
            if poi_id:
                registry[str(poi_id)] = dict(poi)

        for ref in itinerary.get("poi_registry") or []:
            if not isinstance(ref, dict):
                continue
            poi_id = ref.get("poi_id")
            if poi_id and str(poi_id) not in registry:
                registry[str(poi_id)] = dict(ref)
        return registry


def _looks_like_iso_date(value: str) -> bool:
    return len(value) >= 10 and value[4] == "-" and value[7] == "-"


def _build_plan_citations(
    *,
    city: str,
    live_poi_lookup: bool,
    search_source: str,
    pois: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """User-facing grounding references — no internal tool IDs in labels."""
    city_title = city.strip().title() or "Destination"
    citations: list[dict[str, Any]] = []

    if live_poi_lookup:
        citations.append(
            {
                "citation_id": "map:openstreetmap",
                "source_url": "https://www.openstreetmap.org/",
                "section": "Live map places",
                "document_id": "openstreetmap",
                "metadata": {
                    "source": "OpenStreetMap",
                    "label": "OpenStreetMap",
                    "search_source": search_source,
                    "poi_count": len(pois),
                },
            }
        )
    else:
        citations.append(
            {
                "citation_id": "fallback:destination-knowledge",
                "source_url": None,
                "section": "Offline destination knowledge",
                "document_id": "well_known",
                "metadata": {
                    "source": "Trusted travel guidance",
                    "label": "Trusted travel guidance (offline map fallback)",
                    "search_source": search_source,
                },
            }
        )

    citations.append(
        {
            "citation_id": f"tourism:{city_title.lower().replace(' ', '-')}",
            "source_url": _city_tourism_url(city_title),
            "section": f"{city_title} visitor guidance",
            "document_id": f"tourism:{city_title.lower()}",
            "metadata": {
                "source": f"{city_title} Tourism",
                "label": f"{city_title} Tourism",
            },
        }
    )

    slug = city_title.replace(" ", "_")
    citations.append(
        {
            "citation_id": f"guide:wikivoyage-{city_title.lower()}",
            "source_url": f"https://en.wikivoyage.org/wiki/{slug}",
            "section": "Travel guide",
            "document_id": f"wikivoyage:{city_title.lower()}",
            "metadata": {"source": "Wikivoyage", "label": "Wikivoyage"},
        }
    )

    return citations


def _city_tourism_url(city: str) -> str | None:
    normalized = city.strip().lower()
    if normalized == "jaipur":
        return "https://www.tourism.rajasthan.gov.in/jaipur"
    if normalized:
        return f"https://en.wikivoyage.org/wiki/{city.strip().replace(' ', '_')}"
    return None


def _filter_pois_for_planning(
    pois: list[dict[str, Any]],
    interests: list[str],
) -> list[dict[str, Any]]:
    """Drop dining POIs from the schedule unless the trip explicitly asks for food."""
    interests_norm = {i.strip().lower() for i in interests if i and i.strip()}
    if "food" in interests_norm:
        return list(pois)

    filtered: list[dict[str, Any]] = []
    for poi in pois:
        category = str(poi.get("category") or "").strip().lower()
        if category in _FOOD_POI_CATEGORIES:
            continue
        name = str(poi.get("name") or "").lower()
        # Guard OSM/cache rows tagged without category but clearly dining.
        if not category and any(
            token in name
            for token in ("restaurant", "cafe", "café", "coffee", "rooftop", "bakery")
        ):
            continue
        filtered.append(poi)
    return filtered