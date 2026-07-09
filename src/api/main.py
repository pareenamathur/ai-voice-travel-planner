"""HTTP API — routes exclusively to Supervisor Agent."""

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, Field

from src.agents.registry import AgentRegistry
from src.api.config import settings
from src.api.deps import get_registry

app = FastAPI(
    title="Voice Travel Planner",
    description="Multi-agent voice-first travel planning API. All user traffic goes to Supervisor.",
    version="0.1.0",
)

router = APIRouter(prefix="/api")


class SessionMessageRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1)


class SessionMessageResponse(BaseModel):
    session_id: str
    correlation_id: str
    response: str
    conversation_phase: str
    itinerary_approved: bool


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "phase": "0-foundation"}


@router.post("/session/message", response_model=SessionMessageResponse)
async def session_message(
    body: SessionMessageRequest,
    registry: AgentRegistry = Depends(get_registry),
) -> SessionMessageResponse:
    """Sole user entry point — delegates to Supervisor Agent only."""
    result = await registry.supervisor.handle_message(body.session_id, body.message)
    return SessionMessageResponse(**result)


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


@app.get("/health")
async def root_health() -> dict[str, str]:
    return {"status": "ok", "phase": "0-foundation"}


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
