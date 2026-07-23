"""Knowledge Agent — grounded explanations; returns AgentResult to Supervisor (Phase 6)."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from src.agents.base import BaseAgent
from src.agents.supervisor.recommend import recommend_category_label, recommend_search_interests
from src.mcp_servers.poi_search.fallback import well_known_pois_for_city
from src.shared.messages.types import AgentResult, AgentRole, TaskMessage, TaskType

_PLACE_QUERY_RE = re.compile(
    r"\b(?:about|tell me (?:more )?about|what(?:'s| is) special about|"
    r"why.*?(?:pick|recommend|choose|chose|include|included|select))\b"
    r"[\s:,-]*(?P<name>[A-Za-z][\w\s'-]{2,50})",
    re.IGNORECASE,
)
_BEST_TIME_RE = re.compile(
    r"\b(best time to visit|when should (?:i|we) visit|what time should)\b",
    re.IGNORECASE,
)
_WHY_PLANNING_RE = re.compile(
    r"\bwhy\b.*\b(recommend|pick|choose|chose|include|included|select|plan)\b",
    re.IGNORECASE,
)
_WHY_CHOOSE_RE = re.compile(
    r"\bwhy\b.*\b(did you|you)\b.*\b(choose|pick|include|add|plan)\b",
    re.IGNORECASE,
)
_FEASIBILITY_RE = re.compile(
    r"\b("
    r"doable|feasible|too packed|too busy|too hectic|too much walking|"
    r"rushing|rushed|tight schedule|"
    r"enough time|overpacked|overwhelming|pace (?:ok|okay|fine)|"
    r"will i (?:be )?(?:rush|rushed)|cover (?:this|it) comfortably|"
    r"is (?:this|the|it) (?:itinerary|day|plan) "
    r"(?:doable|realistic|ok|okay|feasible)"
    r")\b",
    re.IGNORECASE,
)
_RAIN_RE = re.compile(
    r"\b("
    r"rain|rains|raining|weather|monsoon|wet day|if it rains|what if it rains"
    r")\b",
    re.IGNORECASE,
)
_KID_FRIENDLY_RE = re.compile(
    r"\b(kid|kids|child|children|toddler|family[- ]friendly|kid[- ]friendly)\b",
    re.IGNORECASE,
)
_PACKING_RE = re.compile(
    r"\b(pack(?:ing)?|what should i (?:bring|wear|carry)|luggage|carry[- ]on|essentials)\b",
    re.IGNORECASE,
)
_SENIOR_RE = re.compile(
    r"\b(senior\s+citizen|elderly|older\s+parents?|elder\s+parents?)\b",
    re.IGNORECASE,
)
_WHEELCHAIR_RE = re.compile(
    r"\b(wheelchair|accessible|accessibility|mobility)\b",
    re.IGNORECASE,
)
_SAFETY_RE = re.compile(
    r"\b(safe(?:ty)?|solo\s+travell?er|scam)\b",
    re.IGNORECASE,
)
_BUDGET_RE = re.compile(
    r"\b(expensive|budget[- ]?friendly|cost(?:ly)?|how much)\b",
    re.IGNORECASE,
)
_TRANSPORT_RE = re.compile(
    r"\b(public\s+transport|need\s+a\s+taxi|taxi|uber|auto[- ]?rickshaw)\b",
    re.IGNORECASE,
)
_SEASON_RE = re.compile(
    r"\b(summer|monsoon|during\s+monsoon|in\s+summer|hot\s+season)\b",
    re.IGNORECASE,
)

_OUTDOORISH = frozenset({"landmark", "sightseeing", "nature", "park", "adventure"})
_INDOORISH = frozenset({"culture", "museum", "shopping", "food"})

_KNOWLEDGE_TASKS = frozenset({TaskType.EXPLAIN, TaskType.RECOMMEND})


class KnowledgeAgent(BaseAgent):
    """RAG + citations via Gateway. Review Agent bypassed for EXPLAIN / RECOMMEND."""

    role = AgentRole.KNOWLEDGE

    async def run(self, task: TaskMessage) -> AgentResult:
        if task.task_type not in _KNOWLEDGE_TASKS:
            raise ValueError(
                f"Knowledge Agent requires task_type EXPLAIN or RECOMMEND, got '{task.task_type}'"
            )

        correlation_id = task.correlation_id
        self._trace("delegation_started", correlation_id, task_type=task.task_type.value)

        if task.task_type == TaskType.RECOMMEND:
            return await self._run_recommend(task)

        question = str(task.payload.get("question") or task.payload.get("message") or "").strip()
        city = str(task.payload.get("city") or _city_from_itinerary(task.payload.get("itinerary")) or "")
        if not question:
            raise ValueError("EXPLAIN payload.question is required")
        if not city:
            raise ValueError("EXPLAIN payload.city is required")

        assert self.gateway is not None
        query = _build_retrieval_query(question, task.payload)
        self._trace("retrieve_guidance", correlation_id, city=city, query_preview=query[:120])
        rag_started = time.perf_counter()
        guidance = await self.gateway.invoke(
            AgentRole.KNOWLEDGE,
            "retrieve_guidance",
            {
                "query": query,
                "city": city,
                "top_k": 5,
                "session_id": task.session_id,
            },
            correlation_id=correlation_id,
        )
        self._trace(
            "rag_retrieval_stage",
            correlation_id,
            duration_ms=round((time.perf_counter() - rag_started) * 1000, 2),
        )
        if not isinstance(guidance, dict):
            raise ValueError("retrieve_guidance must return a dict payload")

        chunks = list(guidance.get("chunks") or [])
        citations = list(guidance.get("citations") or [])
        answer = _compose_answer(
            question=question,
            city=city,
            chunks=chunks,
            itinerary=task.payload.get("itinerary"),
            poi_registry=task.payload.get("poi_registry") or {},
            trip_constraints=task.payload.get("trip_constraints") or {},
            eval_report=task.payload.get("eval_report"),
        )

        self._trace(
            "knowledge_answer_ready",
            correlation_id,
            citation_count=len(citations),
            chunk_count=len(chunks),
        )
        return AgentResult(
            status="ok",
            payload={"answer": answer, "query": query, "chunk_count": len(chunks)},
            citations=citations,
            correlation_id=correlation_id,
        )

    async def _run_recommend(self, task: TaskMessage) -> AgentResult:
        question = str(task.payload.get("question") or task.payload.get("message") or "").strip()
        city = str(task.payload.get("city") or "").strip()
        if not question or not city:
            raise ValueError("RECOMMEND requires question and city")

        interests = list(task.payload.get("interests") or recommend_search_interests(question))
        assert self.gateway is not None

        category_label = recommend_category_label(question, interests)
        guidance_query = f"best {category_label} in {city}"
        self._trace(
            "search_pois",
            task.correlation_id,
            city=city,
            interests=interests,
        )
        poi_result, guidance = await asyncio.gather(
            self.gateway.invoke(
                AgentRole.KNOWLEDGE,
                "search_pois",
                {
                    "city": city,
                    "interests": interests,
                    "max_results": 12,
                    "session_id": task.session_id,
                },
                correlation_id=task.correlation_id,
            ),
            self.gateway.invoke(
                AgentRole.KNOWLEDGE,
                "retrieve_guidance",
                {
                    "query": guidance_query,
                    "city": city,
                    "top_k": 3,
                    "session_id": task.session_id,
                },
                correlation_id=task.correlation_id,
            ),
        )
        if not isinstance(poi_result, dict):
            raise ValueError("search_pois must return a dict payload")

        pois = list(poi_result.get("pois") or [])
        if not pois:
            # Overpass/city-cache can be empty offline; still recommend curated places.
            fallback = well_known_pois_for_city(city, interests=interests)
            interest_set = {i.lower() for i in interests}
            matched = [
                p for p in fallback if (p.get("category") or "").lower() in interest_set
            ]
            pois = matched or fallback
            self._trace(
                "recommend_fallback_pois",
                task.correlation_id,
                city=city,
                poi_count=len(pois),
            )
        else:
            # Prefer POIs matching the requested interest when live results are mixed.
            interest_set = {i.lower() for i in interests}
            matched = [
                p for p in pois if (p.get("category") or "").lower() in interest_set
            ]
            if matched:
                pois = matched
        guidance_chunks: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        if isinstance(guidance, dict):
            guidance_chunks = list(guidance.get("chunks") or [])
            citations = list(guidance.get("citations") or [])

        answer = _compose_recommendations(
            city=city,
            category_label=category_label,
            pois=pois,
            chunks=guidance_chunks,
            trip_constraints=task.payload.get("trip_constraints") or {},
        )
        self._trace(
            "knowledge_answer_ready",
            task.correlation_id,
            citation_count=len(citations),
            poi_count=len(pois),
        )
        return AgentResult(
            status="ok",
            payload={
                "answer": answer,
                "query": guidance_query,
                "poi_count": len(pois),
            },
            citations=citations,
            correlation_id=task.correlation_id,
        )


def _city_from_itinerary(itinerary: dict[str, Any] | None) -> str:
    if not itinerary:
        return ""
    return str(itinerary.get("city") or "")


def _build_retrieval_query(question: str, payload: dict[str, Any]) -> str:
    place = _extract_place_name(question)
    city = str(payload.get("city") or _city_from_itinerary(payload.get("itinerary")) or "")
    if place:
        return f"{place} {city} itinerary planning".strip()
    if _BEST_TIME_RE.search(question):
        target = place or city
        return f"best time to visit {target}".strip()
    return question


def _extract_place_name(question: str) -> str | None:
    match = _PLACE_QUERY_RE.search(question)
    if match:
        return match.group("name").strip(" ?.,!")
    for known in ("Amber Fort", "Hawa Mahal", "City Palace", "Jantar Mantar", "Jal Mahal"):
        if known.lower() in question.lower():
            return known
    return None


def _compose_recommendations(
    *,
    city: str,
    category_label: str,
    pois: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    trip_constraints: dict[str, Any],
) -> str:
    lines = [f"Here are {category_label} recommendations in {_title(city)}:"]
    interests = trip_constraints.get("interests") or []
    if interests:
        lines.append(
            f"(Matched to your interests: {', '.join(str(i) for i in interests[:4])}.)"
        )
    lines.append("")

    if pois:
        for poi in pois[:8]:
            name = str(poi.get("name") or "Unnamed place")
            cat = poi.get("category")
            suffix = f" ({cat})" if cat else ""
            lines.append(f"- {name}{suffix}")
    else:
        lines.append(
            "- I couldn't load live POI results right now; try asking again in a moment."
        )

    excerpt = _format_chunk_excerpt(chunks, max_chunks=1)
    if excerpt:
        lines.append("")
        lines.append("Travel guide note:")
        lines.append(excerpt)

    return "\n".join(lines)


def _compose_answer(
    *,
    question: str,
    city: str,
    chunks: list[dict[str, Any]],
    itinerary: dict[str, Any] | None,
    poi_registry: dict[str, Any],
    trip_constraints: dict[str, Any],
    eval_report: dict[str, Any] | None = None,
) -> str:
    place = _extract_place_name(question)
    planning_why = _WHY_PLANNING_RE.search(question) or _WHY_CHOOSE_RE.search(question)

    if _FEASIBILITY_RE.search(question):
        return _compose_feasibility_answer(
            question=question,
            city=city,
            itinerary=itinerary,
            trip_constraints=trip_constraints,
            eval_report=eval_report,
        )

    if _RAIN_RE.search(question):
        return _compose_rain_answer(
            city=city,
            itinerary=itinerary,
            chunks=chunks,
            trip_constraints=trip_constraints,
        )

    if _SEASON_RE.search(question) and itinerary:
        return _compose_season_answer(
            question=question,
            city=city,
            itinerary=itinerary,
            chunks=chunks,
            trip_constraints=trip_constraints,
        )

    focused = _compose_focused_travel_answer(
        question=question,
        city=city,
        chunks=chunks,
        trip_constraints=trip_constraints,
        itinerary=itinerary,
    )
    if focused:
        return focused

    if place and planning_why:
        ctx = _itinerary_context_for_place(place, itinerary, poi_registry)
        if ctx:
            return _format_planning_rationale(place, city, ctx, chunks, trip_constraints)

    if _WHY_PLANNING_RE.search(question) and place:
        registry_hit = _find_place_in_registry(place, poi_registry, itinerary)
        if registry_hit:
            ctx = _itinerary_context_for_place(place, itinerary, poi_registry)
            if ctx:
                return _format_planning_rationale(place, city, ctx, chunks, trip_constraints)
            name, category = registry_hit
            return (
                f"I included {name} because it fits your {city} itinerary and matches your "
                f"focus on {category or 'sightseeing'}. "
            ) + _grounding_suffix(chunks)

    if _BEST_TIME_RE.search(question):
        lead = f"For visiting {place or city}, earlier mornings and late afternoons are usually best"
        return lead + _grounding_suffix(chunks, fallback=" to avoid crowds and heat.")

    if place:
        ctx = _itinerary_context_for_place(place, itinerary, poi_registry)
        if ctx and (_asks_about_itinerary(question) or planning_why):
            lines = [
                f"About {ctx['title']} on your Day {ctx['day_number']} itinerary:",
                f"- It is grouped with: {ctx['same_day_summary']}.",
            ]
            pace = trip_constraints.get("pace") or (itinerary or {}).get(
                "traveler_constraints", {}
            ).get("pace")
            if pace:
                lines.append(f"- Your pace is {pace}, which fits how this stop is scheduled.")
            body = _format_chunk_excerpt(chunks)
            if body:
                lines.append("")
                lines.append("What to know about the place:")
                lines.append(body)
            return "\n".join(lines)

        lead = f"Here is what stands out about {place} in {city}:"
        body = _format_chunk_excerpt(chunks)
        if body:
            return f"{lead}\n{body}"
        return f"{lead} it is one of the city's well-known attractions."

    body = _format_chunk_excerpt(chunks)
    if body:
        return body
    return (
        f"I don't have live guidance loaded for that question about {city} right now. "
        "Try asking about a specific place in your itinerary."
    )


def _compose_focused_travel_answer(
    *,
    question: str,
    city: str,
    chunks: list[dict[str, Any]],
    trip_constraints: dict[str, Any],
    itinerary: dict[str, Any] | None = None,
) -> str | None:
    """Answer a single travel question without dumping the full itinerary."""
    pace = trip_constraints.get("pace") or "moderate"
    excerpt = _format_chunk_excerpt(chunks, max_chunks=2)
    day_summaries = _day_load_summaries(itinerary)
    stop_titles = _itinerary_stop_titles(itinerary, limit=6)

    if _KID_FRIENDLY_RE.search(question):
        lines = [_kid_friendly_lead(city, day_summaries, pace, stop_titles)]
        if excerpt:
            lines.append("")
            lines.append(excerpt)
        else:
            lines.append(
                "For young children, build in a longer afternoon break and use jeep or "
                "elephant rides at forts where walking is steep."
            )
        return "\n".join(lines)

    if _SENIOR_RE.search(question):
        lines = [
            f"For {_title(city)} with senior travellers, shorter walking segments and "
            "midday rest usually matter more than packing in sights.",
        ]
        if day_summaries:
            busiest = max(day_summaries, key=lambda d: d["total"])
            lines.append(
                f"Your heaviest day is Day {busiest['day_number']} "
                f"({busiest['activity_count']} stops); consider asking to relax that day if needed."
            )
        if pace == "relaxed":
            lines.append("Your relaxed pace already helps.")
        if excerpt:
            lines.append("")
            lines.append(excerpt)
        return "\n".join(lines)

    if _WHEELCHAIR_RE.search(question):
        lines = [
            f"Wheelchair access in {_title(city)} varies by site — palaces and museums "
            "are often easier than hill forts and old bazaars on uneven stone.",
        ]
        if stop_titles:
            lines.append(f"On your plan, key stops include: {', '.join(stop_titles[:4])}.")
        lines.append(
            "Ask venues ahead about ramps and lifts; at Amber Fort, plan drop-off near the entrance."
        )
        if excerpt:
            lines.append("")
            lines.append(excerpt)
        return "\n".join(lines)

    if _SAFETY_RE.search(question):
        lines = [
            f"{_title(city)} is a common tourist city; stick to licensed guides and prepaid taxis, "
            "agree auto fares before rides, and keep valuables in inner pockets in busy markets.",
        ]
        if "solo" in question.lower():
            lines.append(
                "Solo travellers usually do fine on this style of itinerary if you use daytime "
                "sightseeing and trusted transport at night."
            )
        if excerpt:
            lines.append("")
            lines.append(excerpt)
        return "\n".join(lines)

    if _BUDGET_RE.search(question):
        budget = trip_constraints.get("budget") or (itinerary or {}).get(
            "traveler_constraints", {}
        ).get("budget")
        lines = [
            f"Cost depends on hotels and dining, but a {pace} {_title(city)} plan with "
            f"{len(day_summaries) or 'several'} days is usually mid-range if you mix street food with one nicer meal a day.",
        ]
        if budget:
            lines.append(f"You listed budget preference: {budget}.")
        if excerpt:
            lines.append("")
            lines.append(excerpt)
        return "\n".join(lines)

    if _TRANSPORT_RE.search(question):
        lines = [
            f"For this {_title(city)} itinerary, autos and app taxis work well between clusters; "
            "there is no single metro line covering every stop.",
        ]
        if day_summaries:
            travel_total = sum(d["travel_minutes"] for d in day_summaries)
            lines.append(
                f"Planned driving/transit between stops is about {travel_total} minutes total across the trip."
            )
        lines.append(
            "Public buses are possible but slower; many travellers use a taxi for early-morning fort visits."
        )
        if excerpt:
            lines.append("")
            lines.append(excerpt)
        return "\n".join(lines)

    if _PACKING_RE.search(question):
        lines = [
            f"For {_title(city)}, pack light breathable clothing, comfortable walking shoes, sun protection, "
            "and a refillable water bottle.",
        ]
        if excerpt:
            lines.append("")
            lines.append(excerpt)
        else:
            lines.append(
                "A light layer for evening and modest clothing for temples or heritage sites is helpful year-round."
            )
        return "\n".join(lines)

    return None


def _kid_friendly_lead(
    city: str,
    day_summaries: list[dict[str, Any]],
    pace: str,
    stop_titles: list[str],
) -> str:
    if day_summaries:
        avg_stops = round(
            sum(d["activity_count"] for d in day_summaries) / len(day_summaries), 1
        )
        lead = (
            f"Yes — overall this {_title(city)} plan is fairly kid-friendly: about "
            f"{avg_stops} stops per day at a {pace} pace."
        )
    else:
        lead = f"For {_title(city)} with kids, shorter days and indoor backups usually work best."
    if stop_titles:
        names = ", ".join(stop_titles[:3])
        lead += f" Highlights like {names} are popular with families."
    if pace in {"fast", "packed"}:
        lead += " The schedule is on the fuller side — consider a relaxed edit if little legs tire easily."
    elif pace == "relaxed":
        lead += " Your relaxed pace is a good fit for family travel."
    return lead


def _itinerary_stop_titles(itinerary: dict[str, Any] | None, *, limit: int = 8) -> list[str]:
    titles: list[str] = []
    for day in (itinerary or {}).get("days") or []:
        for activity in day.get("activities") or []:
            title = str(activity.get("title") or "").strip()
            if title and title not in titles:
                titles.append(title)
            if len(titles) >= limit:
                return titles
    return titles


def _compose_season_answer(
    *,
    question: str,
    city: str,
    itinerary: dict[str, Any] | None,
    chunks: list[dict[str, Any]],
    trip_constraints: dict[str, Any],
) -> str:
    outdoor = [
        t
        for t in _itinerary_stop_titles(itinerary, limit=10)
        if any(k in t.lower() for k in ("fort", "garden", "mahal", "lake"))
    ]
    lines = [f"Season matters for {_title(city)}:"]
    if _SEASON_RE.search(question) and "monsoon" in question.lower():
        lines.append(
            "- Monsoon brings humidity and showers; outdoor forts are slippery — keep indoor museums as backups."
        )
    else:
        lines.append(
            "- Summer heat is intense midday; do forts and outdoor sights early, then rest or shop indoors."
        )
    if outdoor:
        lines.append("Outdoor-heavy stops on your plan:")
        for name in outdoor[:4]:
            lines.append(f"- {name}")
    pace = trip_constraints.get("pace")
    if pace:
        lines.append(f"Your {pace} pace helps you avoid the hottest hours if you start mornings early.")
    excerpt = _format_chunk_excerpt(chunks, max_chunks=1)
    if excerpt:
        lines.append("")
        lines.append(excerpt)
    return "\n".join(lines)


def _asks_about_itinerary(question: str) -> bool:
    return bool(
        re.search(
            r"\b(itinerary|schedule|day\s*\d+|stops?|planned|included|why did you)\b",
            question,
            re.IGNORECASE,
        )
    )


def _compose_feasibility_answer(
    *,
    question: str,
    city: str,
    itinerary: dict[str, Any] | None,
    trip_constraints: dict[str, Any],
    eval_report: dict[str, Any] | None,
) -> str:
    day_focus = _extract_day_number_from_question(question)
    pace = (
        trip_constraints.get("pace")
        or (itinerary or {}).get("traveler_constraints", {}).get("pace")
        or "moderate"
    )
    lines: list[str] = []
    day_summaries = _day_load_summaries(itinerary)
    feasibility = _feasibility_entry(eval_report)

    if feasibility is not None and feasibility.get("passed"):
        lines.append(
            f"Yes. According to the itinerary evaluation, this {city} plan is feasible."
        )
        lines.append("")
        if day_focus is not None:
            match = next((d for d in day_summaries if d["day_number"] == day_focus), None)
            if match:
                hours = round(match["total"] / 60, 1)
                lines.append(
                    f"• Day {day_focus} uses around {hours} hours "
                    f"({match['activity_count']} stops, {match['travel_minutes']} min travel)."
                )
        else:
            for summary in day_summaries:
                hours = round(summary["total"] / 60, 1)
                lines.append(
                    f"• Day {summary['day_number']} uses around {hours} hours "
                    f"({summary['activity_count']} stops)."
                )
        lines.append("• Travel time is within the planner's limits.")
        lines.append("• No day exceeds the planner's daily limit.")
        lines.append(f"• The pace matches your requested {pace} itinerary.")
        warnings = list(feasibility.get("reasons") or [])
        if warnings:
            lines.append("")
            lines.append("Notes from Review:")
            for reason in warnings[:4]:
                lines.append(f"• {reason}")
        return "\n".join(lines)

    if feasibility is not None and not feasibility.get("passed"):
        lines.append(
            "The itinerary evaluation found packing or travel issues to watch:"
        )
        reasons = list(feasibility.get("reasons") or [])
        focused = [
            r
            for r in reasons
            if day_focus is None or f"day {day_focus}" in str(r).lower()
        ] or reasons
        for reason in focused[:5]:
            lines.append(f"• {reason}")
        if day_focus is not None:
            match = next((d for d in day_summaries if d["day_number"] == day_focus), None)
            if match:
                lines.append(
                    f"• Day {day_focus} currently has {match['activity_count']} stops "
                    f"({match['activity_minutes']} min sightseeing + {match['travel_minutes']} min travel)."
                )
        lines.append("")
        lines.append("Ask me to make a day more relaxed if you want a lighter schedule.")
        return "\n".join(lines)

    # No Review report yet — still answer from the live itinerary shape.
    if day_summaries:
        lines.append(
            f"I don't have a saved Review feasibility report yet, but based on the current "
            f"{city} schedule:"
        )
        if day_focus is not None:
            match = next((d for d in day_summaries if d["day_number"] == day_focus), None)
            if match:
                hours = round(match["total"] / 60, 1)
                lines.append(
                    f"• Day {day_focus} has {match['activity_count']} stops (~{hours} hours including travel)."
                )
                if match["activity_count"] >= 5 or match["total"] >= 480:
                    lines.append("• That day is on the fuller side for a relaxed pace.")
                else:
                    lines.append("• That load looks manageable for most travelers.")
        else:
            busiest = max(day_summaries, key=lambda d: d["total"])
            lines.append(
                f"• Day {busiest['day_number']} is the heaviest "
                f"({busiest['activity_count']} stops, ~{round(busiest['total'] / 60, 1)} hours)."
            )
            lines.append(f"• Planned pace: {pace}.")
        return "\n".join(lines)

    return (
        f"I don't have a Review feasibility report yet for this {city} plan. "
        "Generate or confirm an itinerary first, then ask again."
    )


def _compose_rain_answer(
    *,
    city: str,
    itinerary: dict[str, Any] | None,
    chunks: list[dict[str, Any]],
    trip_constraints: dict[str, Any],
) -> str:
    outdoor: list[str] = []
    indoor: list[str] = []
    for day in (itinerary or {}).get("days") or []:
        day_n = day.get("day_number")
        for activity in day.get("activities") or []:
            title = str(activity.get("title") or "").strip()
            if not title:
                continue
            category = str(activity.get("category") or "").lower()
            label = f"{title} (Day {day_n})"
            if category in _INDOORISH or "museum" in title.lower() or "palace" in title.lower():
                indoor.append(label)
            elif category in _OUTDOORISH or "fort" in title.lower() or "garden" in title.lower():
                outdoor.append(label)
            else:
                indoor.append(label)

    lines = [f"If it rains in {city}, here is how I'd adapt your current plan:"]
    if outdoor:
        lines.append("Outdoor stops that are more weather-sensitive:")
        for item in outdoor[:5]:
            lines.append(f"- {item}")
    if indoor:
        lines.append("Indoor (or covered) options already on your itinerary — swap toward these:")
        for item in indoor[:5]:
            lines.append(f"- {item}")
    else:
        lines.append(
            "- I don't see strong indoor stops on the current plan; ask me to swap an evening "
            "for something indoors (for example a museum)."
        )

    pace = trip_constraints.get("pace")
    if pace:
        lines.append(f"Your {pace} pace leaves room to reshuffle without rebuilding every day.")

    excerpt = _format_chunk_excerpt(chunks, max_chunks=1)
    if excerpt:
        lines.append("")
        lines.append("Guide note:")
        lines.append(excerpt)
    return "\n".join(lines)


def _feasibility_entry(eval_report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not eval_report:
        return None
    for entry in eval_report.get("entries") or []:
        if str(entry.get("name") or "").lower() == "feasibility":
            return entry
    return None


def _day_load_summaries(itinerary: dict[str, Any] | None) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for day in (itinerary or {}).get("days") or []:
        activities = day.get("activities") or []
        activity_minutes = sum(int(a.get("duration_minutes") or 0) for a in activities)
        travel_minutes = sum(
            int(seg.get("travel_minutes") or 0) for seg in (day.get("travel_segments") or [])
        )
        summaries.append(
            {
                "day_number": day.get("day_number"),
                "activity_count": len(activities),
                "activity_minutes": activity_minutes,
                "travel_minutes": travel_minutes,
                "total": activity_minutes + travel_minutes,
            }
        )
    return summaries


def _extract_day_number_from_question(question: str) -> int | None:
    match = re.search(r"\bday\s*(\d+)\b", question, re.I)
    if match:
        return int(match.group(1))
    return None


def _format_planning_rationale(
    place: str,
    city: str,
    ctx: dict[str, Any],
    chunks: list[dict[str, Any]],
    trip_constraints: dict[str, Any],
) -> str:
    title = ctx["title"]
    lines = [
        f"I selected {title} on Day {ctx['day_number']} because:",
        f"- It sits near {ctx['same_day_summary']}, which keeps travel time down for that day.",
        f"- It fits the day's theme ({ctx.get('day_theme') or 'sightseeing'}) in {city}.",
    ]
    interests = trip_constraints.get("interests") or []
    if interests:
        lines.append(
            f"- It matches your interests ({', '.join(str(i) for i in interests[:4])})."
        )
    pace = trip_constraints.get("pace")
    if pace:
        lines.append(f"- Your {pace} pace works with the surrounding stops that day.")
    duration = ctx.get("duration_minutes")
    if duration:
        lines.append(f"- I budgeted about {duration} minutes here.")

    body = _format_chunk_excerpt(chunks, max_chunks=1)
    if body:
        lines.append("")
        lines.append("What to know about the place:")
        lines.append(body)
    return "\n".join(line for line in lines if line)


def _itinerary_context_for_place(
    place: str,
    itinerary: dict[str, Any] | None,
    poi_registry: dict[str, Any],
) -> dict[str, Any] | None:
    needle = place.lower()

    for day in (itinerary or {}).get("days") or []:
        activities = day.get("activities") or []
        titles = [str(a.get("title") or "") for a in activities]
        for activity in activities:
            title = str(activity.get("title") or "")
            poi_id = activity.get("poi_id")
            registry_name = ""
            if poi_id and poi_id in poi_registry:
                registry_name = str(poi_registry[poi_id].get("name") or "")
            matched = needle in title.lower() or (
                registry_name and needle in registry_name.lower()
            )
            if not matched:
                continue
            display = registry_name or title or place
            others = [
                t
                for t in titles
                if t and needle not in t.lower() and display.lower() not in t.lower()
            ]
            return {
                "title": display,
                "day_number": day.get("day_number", "?"),
                "day_theme": day.get("theme"),
                "same_day_summary": ", ".join(others[:3]) if others else "other stops that day",
                "duration_minutes": activity.get("duration_minutes"),
            }

    hit = _find_place_in_registry(place, poi_registry, itinerary)
    if hit:
        name, _ = hit
        return {
            "title": name,
            "day_number": "?",
            "day_theme": None,
            "same_day_summary": "other planned stops",
            "duration_minutes": None,
        }
    return None


def _find_place_in_registry(
    place: str,
    poi_registry: dict[str, Any],
    itinerary: dict[str, Any] | None,
) -> tuple[str, str | None] | None:
    needle = place.lower()
    for ref in poi_registry.values():
        name = str(ref.get("name") or "")
        if needle in name.lower():
            return name, ref.get("category")

    for day in (itinerary or {}).get("days") or []:
        for activity in day.get("activities") or []:
            title = str(activity.get("title") or "")
            if needle in title.lower():
                return title, activity.get("category")
    return None


def _format_chunk_excerpt(chunks: list[dict[str, Any]], *, max_chunks: int = 2) -> str:
    if not chunks:
        return ""
    lines: list[str] = []
    for chunk in chunks[:max_chunks]:
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        section = chunk.get("section")
        prefix = f"{section}: " if section else ""
        lines.append(f"- {prefix}{text}")
    return "\n".join(lines)


def _grounding_suffix(chunks: list[dict[str, Any]], *, fallback: str = ".") -> str:
    excerpt = _format_chunk_excerpt(chunks, max_chunks=1)
    if excerpt:
        return f" According to the travel guides: {excerpt.lstrip('- ')}"
    return fallback


def _title(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:]
