"""Deterministic intent classification for the Supervisor (Phase 4 Task 2)."""

from __future__ import annotations

import re

from src.agents.edit.intent import is_edit_message
from src.agents.supervisor.recommend import is_recommend_message
from src.shared.messages.types import ConversationPhase, TaskType, TripConstraints

GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|greetings)\b[\s!.?]*$",
    re.IGNORECASE,
)

# Trailing punctuation and politeness suffixes common in speech / Web Speech API output.
_CONFIRM_TAIL = r"[\s!.,?]*(?:\s+(?:please|thanks|thank\s+you))?[\s!.,?]*$"

CONFIRM_RE = re.compile(
    r"^\s*("
    r"yes|yeah|yep|yup|sure|ok|okay|confirm|confirmed|go\s*ahead|"
    r"please\s+(do|proceed|generate)|generate(\s+it)?"
    r"|looks?\s+good|that\s+works|proceed|do\s+it|sounds?\s+good"
    f"){_CONFIRM_TAIL}",
    re.IGNORECASE,
)

INVISIBLE_CHARS_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")

NEGATE_RE = re.compile(
    r"\b(no|nope|not\s+yet|change|wait|hold\s+on|don'?t)\b",
    re.IGNORECASE,
)

_EXPLAIN_RE = re.compile(
    r"\b("
    r"why|what|how|when|tell me|explain|describe|more about|special about|best time|"
    r"why (?:this|that|did you)|what is special|why was this included"
    r")\b",
    re.IGNORECASE,
)

# Trip-fit / logistics questions (require an existing itinerary in classify_intent).
_ITINERARY_ADVISORY_RE = re.compile(
    r"\b("
    r"doable|feasible|realistic|too\s+hectic|too\s+busy|too\s+much\s+walking|"
    r"comfortably|overwhelming|overpacked|rushed|rushing|"
    r"kid[- ]?friendly|child(?:ren)?|toddler|family[- ]?friendly|"
    r"senior\s+citizen|elderly|older\s+parents?|wheelchair|accessible|accessibility|"
    r"\bsafe(?:ty)?\b|solo\s+travell?er|scam|"
    r"monsoon|during\s+summer|in\s+summer|summer\s+heat|"
    r"pack(?:ing)?|what\s+should\s+i\s+(?:carry|bring|wear)|"
    r"expensive|budget[- ]?friendly|cost(?:ly)?|"
    r"public\s+transport|need\s+a\s+taxi|"
    r"suitable\s+for|suitable\s+during|"
    r"parents|"
    r"can\s+i\s+do\s+this"
    r")\b",
    re.IGNORECASE,
)

_TRIP_CONTEXT_RE = re.compile(
    r"\b(this|it|the\s+plan|the\s+itinerary|my\s+trip|this\s+plan|this\s+itinerary)\b",
    re.IGNORECASE,
)

# Single-token affirmatives that speech engines often stutter/repeat.
_AFFIRMATIVE_TOKENS = frozenset(
    {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed"}
)
_TRAILING_PUNCT = "!.,?"


def is_greeting(message: str) -> bool:
    return bool(GREETING_RE.match(message.strip()))


def _token_core(token: str) -> str:
    return token.rstrip(_TRAILING_PUNCT)


def _trailing_punct(token: str) -> str:
    core = _token_core(token)
    return token[len(core) :]


def _collapse_repeated_affirmatives(text: str) -> str:
    """Collapse consecutive repeated affirmatives: 'yes yes' → 'yes'."""
    parts = text.split(" ")
    if len(parts) < 2:
        return text

    result: list[str] = []
    prev_affirmative: str | None = None

    for part in parts:
        if not part:
            continue
        core = _token_core(part)
        if core in _AFFIRMATIVE_TOKENS and core == prev_affirmative:
            # Keep the latest trailing punctuation on the retained token.
            if result:
                result[-1] = _token_core(result[-1]) + _trailing_punct(part)
            continue

        result.append(part)
        prev_affirmative = core if core in _AFFIRMATIVE_TOKENS else None

    return " ".join(result)


def normalize_confirmation_text(message: str) -> str:
    """Normalize spoken confirmations before ``CONFIRM_RE`` matching.

    - Strip invisible Unicode
    - Lowercase
    - Collapse whitespace
    - Collapse consecutive repeated affirmative tokens (e.g. ``yes yes`` → ``yes``)
      while preserving trailing politeness (please / thanks / thank you) and punctuation
    """
    text = INVISIBLE_CHARS_RE.sub("", message)
    text = text.lower()
    text = WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return text
    return _collapse_repeated_affirmatives(text)


def is_explicit_confirmation(message: str) -> bool:
    text = normalize_confirmation_text(message)
    if not text or NEGATE_RE.search(text):
        return False
    return bool(CONFIRM_RE.match(text))


def is_itinerary_advisory_message(message: str) -> bool:
    """Feasibility, suitability, safety, weather, logistics — not slot confirmation."""
    text = (message or "").strip()
    if not text:
        return False
    if is_edit_message(text) or is_recommend_message(text):
        return False
    if is_explicit_confirmation(text):
        return False
    if _ITINERARY_ADVISORY_RE.search(text):
        return True
    if text.endswith("?") and _TRIP_CONTEXT_RE.search(text):
        return True
    return False


def is_explain_message(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if is_edit_message(text):
        return False
    if is_recommend_message(text):
        return False
    if is_itinerary_advisory_message(text):
        return True
    return bool(_EXPLAIN_RE.search(text))


def _has_destination_context(*, constraints: TripConstraints, has_itinerary: bool) -> bool:
    return has_itinerary or bool(constraints.city)


def classify_intent(
    *,
    message: str,
    constraints: TripConstraints,
    phase: ConversationPhase,
    has_sufficient: bool,
    has_itinerary: bool = False,
    itinerary_approved: bool = False,
) -> TaskType:
    """Classify user intent: EDIT → RECOMMEND → EXPLAIN → PLAN → CONFIRM → CLARIFY."""
    if itinerary_approved and is_edit_message(message):
        return TaskType.EDIT

    if _has_destination_context(constraints=constraints, has_itinerary=has_itinerary):
        if is_recommend_message(message):
            return TaskType.RECOMMEND

    if has_itinerary and is_explain_message(message):
        return TaskType.EXPLAIN

    if is_explicit_confirmation(message) and phase == ConversationPhase.CONFIRM and has_sufficient:
        return TaskType.PLAN

    if has_sufficient:
        if has_itinerary and not is_explicit_confirmation(message):
            stripped = (message or "").strip()
            if stripped.endswith("?") or is_itinerary_advisory_message(message):
                return TaskType.EXPLAIN
        return TaskType.CONFIRM

    if is_greeting(message) and not constraints.city and constraints.days is None:
        return TaskType.CLARIFY

    return TaskType.CLARIFY
