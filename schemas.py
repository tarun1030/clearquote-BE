"""
ClearQuote – Pydantic schemas for all API request / response bodies.
"""

from pydantic import BaseModel, Field
from typing import Any


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    """Body sent by the frontend / client."""
    question: str = Field(..., min_length=3, description="Natural-language question about vehicles / damages / repairs / quotes.")


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class QueryResponse(BaseModel):
    """Full pipeline response returned to the caller."""
    question:      str          = ""
    generated_sql: str          = ""
    validated_sql: str          = ""
    row_count:     int          = 0
    answer:        str          = ""
    error:         str | None   = None
    stage:         str          = ""   # last completed stage for debugging


class DebugResponse(QueryResponse):
    """Extended response that also includes raw DB rows (for /debug endpoint)."""
    rows: list[dict[str, Any]]  = []


class HealthResponse(BaseModel):
    status: str
    db:     str
    model:  str
