"""HTTP API — routes exclusively to Supervisor Agent."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.agents.planning.errors import PlanningFailedError
from src.agents.registry import AgentRegistry
from src.api.config import settings
from src.api.deps import get_registry
from src.api.internal_export import router as internal_export_router
from src.shared.messages.types import ConversationPhase, TaskType

app = FastAPI(
    title="Voice Travel Planner",
    description="Multi-agent voice-first travel planning API. All user traffic goes to Supervisor.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api")


class SessionMessageRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1)


class SessionExportRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    format: Literal["pdf", "markdown", "json"] = "pdf"


class SessionMessageResponse(BaseModel):
    """Supervisor response for the Companion UI (Phase 5 Task 7).

    Extra fields mirror what ``SupervisorAgent.handle_message`` already returns;
    agent logic is unchanged — this only stops FastAPI from stripping them.
    """

    session_id: str
    correlation_id: str
    response: str
    conversation_phase: str
    itinerary_approved: bool
    intent: str | None = None
    itinerary: dict[str, Any] | None = None
    review_verdict: dict[str, Any] | None = None
    task_message: dict[str, Any] | None = None


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "voice-travel-planner"}


@router.post("/session/message", response_model=SessionMessageResponse)
async def session_message(
    body: SessionMessageRequest,
    registry: AgentRegistry = Depends(get_registry),
) -> SessionMessageResponse:
    """Sole user entry point — delegates to Supervisor Agent only."""
    try:
        result = await registry.supervisor.handle_message(body.session_id, body.message)
        return SessionMessageResponse(**result)
    except PlanningFailedError as exc:
        # Planning converted Overpass/external failures into a friendly error.
        # Return HTTP 200 so the companion UI can show the message (not a raw 500).
        session_id = exc.session_id or body.session_id or ""
        return SessionMessageResponse(
            session_id=session_id,
            correlation_id=exc.correlation_id or "",
            response=exc.user_message,
            conversation_phase=ConversationPhase.ACTIVE.value,
            itinerary_approved=False,
            intent=TaskType.PLAN.value,
            itinerary=None,
            review_verdict=None,
            task_message=None,
        )


@router.post("/session/export")
async def session_export(
    body: SessionExportRequest,
    registry: AgentRegistry = Depends(get_registry),
) -> Response:
    """Download an approved itinerary (Supervisor → Export Agent)."""
    outcome = await registry.supervisor.handle_export(body.session_id, body.format)
    if outcome.get("error"):
        raise HTTPException(status_code=400, detail=str(outcome["error"]))
    filename = str(outcome.get("filename") or "itinerary-export")
    return Response(
        content=outcome["content"],
        media_type=str(outcome.get("media_type") or "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/session/{session_id}/trace")
async def session_trace(
    session_id: str,
    registry: AgentRegistry = Depends(get_registry),
) -> dict:
    """Observability trace for demo UI (Phase 5+)."""
    spans = registry.observability.get_spans()
    session_spans = [s for s in spans if s.get("session_id") == session_id]
    return {"session_id": session_id, "spans": session_spans}


app.include_router(router)
app.include_router(internal_export_router, prefix="/api")


@app.get("/health")
async def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "voice-travel-planner"}


def run() -> None:
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
