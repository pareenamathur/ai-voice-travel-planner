"""AI evaluation suites — Phase 7. Invoked at runtime by Review Agent only."""

from src.evals.edit_correctness import evaluate_edit_correctness
from src.evals.feasibility import evaluate_feasibility
from src.evals.grounding import evaluate_grounding
from src.evals.interest_coverage import evaluate_interest_coverage

PLAN_EVALS = ("feasibility", "grounding", "interest_coverage")
EDIT_EVALS = ("feasibility", "grounding", "edit_correctness")

__all__ = [
    "EDIT_EVALS",
    "PLAN_EVALS",
    "evaluate_edit_correctness",
    "evaluate_feasibility",
    "evaluate_grounding",
    "evaluate_interest_coverage",
]
