"""Deterministic intent classification for the Supervisor (Phase 4 Task 2)."""

from __future__ import annotations

import re

from src.shared.messages.types import ConversationPhase, TaskType, TripConstraints

GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|greetings)\b[\s!.?]*$",
    re.IGNORECASE,
)

CONFIRM_RE = re.compile(
    r"^\s*("
    r"yes|yeah|yep|yup|sure|ok|okay|confirm|confirmed|go\s*ahead|"
    r"please\s+(do|proceed|generate)|generate(\s+it)?"
    r"|looks?\s+good|that\s+works|proceed|do\s+it|sounds?\s+good"
    r")[\s!.]*$",
    re.IGNORECASE,
)

NEGATE_RE = re.compile(
    r"\b(no|nope|not\s+yet|change|wait|hold\s+on|don'?t)\b",
    re.IGNORECASE,
)


def is_greeting(message: str) -> bool:
    return bool(GREETING_RE.match(message.strip()))


def is_explicit_confirmation(message: str) -> bool:
    text = message.strip()
    if not text or NEGATE_RE.search(text):
        return False
    return bool(CONFIRM_RE.match(text))


def classify_intent(
    *,
    message: str,
    constraints: TripConstraints,
    phase: ConversationPhase,
    has_sufficient: bool,
) -> TaskType:
    """Classify user intent into CLARIFY, CONFIRM, or PLAN (rule-based)."""
    if is_explicit_confirmation(message) and phase == ConversationPhase.CONFIRM and has_sufficient:
        return TaskType.PLAN

    if has_sufficient:
        # User may still be refining slots while in CONFIRM; stay on CONFIRM
        # unless they explicitly confirmed (handled above).
        return TaskType.CONFIRM

    if is_greeting(message) and not constraints.city and constraints.days is None:
        return TaskType.CLARIFY

    return TaskType.CLARIFY
