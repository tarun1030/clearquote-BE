"""
ClearQuote â€“ Health & info routes.
"""

from fastapi import APIRouter
from sqlalchemy import text
from database import get_session_factory
from config import config
from schema_context import SCHEMA_CONTEXT
from schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------
@router.get("/health", response_model=HealthResponse)
async def health():
    """Quick liveness probe â€“ confirms DB connectivity and reports the model."""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"

    return HealthResponse(status="ok", db=db_status, model=config.GEMINI_MODEL)


# ---------------------------------------------------------------------------
# GET /api/schema
# ---------------------------------------------------------------------------
@router.get("/schema")
async def get_schema():
    """Return the full schema context that is fed to Gemini (useful for debugging)."""
    return {"schema": SCHEMA_CONTEXT}