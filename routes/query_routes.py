"""
ClearQuote – Query endpoints.

POST /api/query   – runs the full NL→SQL→Answer pipeline, returns a polished answer.
POST /api/debug   – same pipeline but also exposes raw DB rows and both SQL variants.
GET  /api/examples – returns a list of example questions the user can try.
"""

from fastapi import APIRouter, HTTPException
from pipeline import run_pipeline
from schemas import QueryRequest, QueryResponse, DebugResponse
from config import config

router = APIRouter(prefix="/api", tags=["query"])


# ---------------------------------------------------------------------------
# POST /api/query   – production endpoint
# ---------------------------------------------------------------------------
@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    Takes a natural-language question, runs the full pipeline, and returns
    a human-readable answer.
    """
    # Validate configuration before attempting to run pipeline
    if not config.DB_URL:
        raise HTTPException(
            status_code=422,
            detail="Database execution failed: DB_URL is not configured. Please set it via POST /api/config/db-url endpoint."
        )
    
    result = await run_pipeline(req.question)

    # If the pipeline hit a hard error before producing any answer, return 422
    if result.error and not result.answer:
        raise HTTPException(status_code=422, detail=result.error)

    return QueryResponse(
        question=result.question,
        generated_sql=result.generated_sql,
        validated_sql=result.validated_sql,
        row_count=len(result.rows),
        answer=result.answer,
        error=result.error,
        stage=result.stage,
    )


# ---------------------------------------------------------------------------
# POST /api/debug   – developer endpoint (includes raw rows)
# ---------------------------------------------------------------------------
@router.post("/debug", response_model=DebugResponse)
async def debug(req: QueryRequest):
    """
    Same as /query but also returns the raw database rows in the response.
    Handy for development and evaluation.
    """
    # Validate configuration before attempting to run pipeline
    if not config.DB_URL:
        raise HTTPException(
            status_code=422,
            detail="Database execution failed: DB_URL is not configured. Please set it via POST /api/config/db-url endpoint."
        )
    
    result = await run_pipeline(req.question)

    if result.error and not result.answer:
        raise HTTPException(status_code=422, detail=result.error)

    # Serialise any non-JSON-native types (dates, Decimals) to strings
    safe_rows = []
    for row in result.rows:
        safe_rows.append({k: str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
                          for k, v in row.items()})

    return DebugResponse(
        question=result.question,
        generated_sql=result.generated_sql,
        validated_sql=result.validated_sql,
        row_count=len(result.rows),
        answer=result.answer,
        error=result.error,
        stage=result.stage,
        rows=safe_rows,
    )


# ---------------------------------------------------------------------------
# GET /api/examples  – seed questions for the UI
# ---------------------------------------------------------------------------
_EXAMPLE_QUESTIONS = [
    "What is the average repair cost for rear bumper damages in the last 30 days?",
    "How many vehicles had severe damages on the front panel this month?",
    "Which car models have the highest repair cost variance?",
    "Show me all unapproved repairs with a cost greater than 500.",
    "What is the total estimated cost of all quotes generated this week?",
    "List all damages detected on Toyota vehicles in the last 60 days.",
    "What is the most common damage type across all vehicles?",
    "How many quotes have been generated per manufacturer this month?",
    "Which vehicles have both a damage detection and an approved repair?",
    "What is the average confidence score for high-severity damages?",
]


@router.get("/examples")
async def examples():
    """Return a curated list of example questions the user can try."""
    return {"examples": _EXAMPLE_QUESTIONS}
