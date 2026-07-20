"""Knowledge Agent — grounded explanations; returns AgentResult to Supervisor (Phase 6)."""

from __future__ import annotations

import re
from typing import Any

from src.agents.base import BaseAgent
from src.shared.messages.types import AgentResult, AgentRole, TaskMessage, TaskType

_PLACE_QUERY_RE = re.compile(
    r"\b(?:about|tell me (?:more )?about|what(?:'s| is) special about|why.*?(?:pick|recommend|choose))\b"
    r"[\s:,-]*(?P<name>[A-Za-z][\w\s'-]{2,50})",
    re.IGNORECASE,
)
_BEST_TIME_RE = re.compile(
    r"\b(best time to visit|when should (?:i|we) visit|what time should)\b",
    re.IGNORECASE,
)
_WHY_RECOMMEND_RE = re.compile(
    r"\bwhy\b.*\b(recommend|pick|choose|suggest)\b",
    re.IGNORECASE,
)


class KnowledgeAgent(BaseAgent):
    """RAG + citations via Gateway. Review Agent bypassed for EXPLAIN workflows."""

    role = AgentRole.KNOWLEDGE

    async def run(self, task: TaskMessage) -> AgentResult:
        if task.task_type != TaskType.EXPLAIN:
            raise ValueError(f"Knowledge Agent requires task_type=EXPLAIN, got '{task.task_type}'")

        correlation_id = task.correlation_id
        self._trace("delegation_started", correlation_id, task_type=task.task_type.value)

        question = str(task.payload.get("question") or task.payload.get("message") or "").strip()
        city = str(task.payload.get("city") or _city_from_itinerary(task.payload.get("itinerary")) or "")
        if not question:
            raise ValueError("EXPLAIN payload.question is required")
        if not city:
            raise ValueError("EXPLAIN payload.city is required")

        assert self.gateway is not None
        query = _build_retrieval_query(question, task.payload)
        self._trace("retrieve_guidance", correlation_id, city=city, query_preview=query[:120])
        guidance = await self.gateway.invoke(
            AgentRole.KNOWLEDGE,
            "retrieve_guidance",
            {"query": query, "city": city, "top_k": 5},
            correlation_id=correlation_id,
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


def _city_from_itinerary(itinerary: dict[str, Any] | None) -> str:
    if not itinerary:
        return ""
    return str(itinerary.get("city") or "")


def _build_retrieval_query(question: str, payload: dict[str, Any]) -> str:
    place = _extract_place_name(question)
    city = str(payload.get("city") or _city_from_itinerary(payload.get("itinerary")) or "")
    if place:
        return f"{place} {city}".strip()
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


def _compose_answer(
    *,
    question: str,
    city: str,
    chunks: list[dict[str, Any]],
    itinerary: dict[str, Any] | None,
    poi_registry: dict[str, Any],
) -> str:
    place = _extract_place_name(question)
    if _WHY_RECOMMEND_RE.search(question) and place:
        registry_hit = _find_place_in_registry(place, poi_registry, itinerary)
        if registry_hit:
            name, category = registry_hit
            return (
                f"I recommended {name} because it fits your {city} itinerary and matches your "
                f"interests ({category or 'sightseeing'}). "
            ) + _grounding_suffix(chunks)

    if _BEST_TIME_RE.search(question):
        lead = f"For visiting {place or city}, earlier mornings and late afternoons are usually best"
        return lead + _grounding_suffix(chunks, fallback=" to avoid crowds and heat.")

    if place:
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
