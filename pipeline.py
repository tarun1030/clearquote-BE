"""
ClearQuote – Core NL → SQL → Execute → Answer pipeline.

This module is the single place that orchestrates the full flow.
Every public endpoint calls one of the functions here.
"""

from sqlalchemy import text
from database import get_session_factory
from gemini_client import nl_to_sql, format_answer
from sql_validator import validate_sql


# ---------------------------------------------------------------------------
# Pipeline result dataclass (plain dict-compatible)
# ---------------------------------------------------------------------------
class PipelineResult:
    """Holds every piece of information the API response needs."""

    def __init__(self):
        self.question: str        = ""
        self.generated_sql: str   = ""          # raw output from Gemini
        self.validated_sql: str   = ""          # after safety checks
        self.rows: list[dict]     = []          # DB result rows
        self.answer: str          = ""          # Gemini-formatted answer
        self.error: str | None    = None        # first error if any
        self.stage: str           = "init"      # last completed stage

    def to_dict(self) -> dict:
        return {
            "question":      self.question,
            "generated_sql": self.generated_sql,
            "validated_sql": self.validated_sql,
            "row_count":     len(self.rows),
            "answer":        self.answer,
            "error":         self.error,
            "stage":         self.stage,
        }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
async def run_pipeline(question: str) -> PipelineResult:
    """
    Full pipeline:
        1. NL → SQL   (Gemini)
        2. Validate   (sql_validator)
        3. Execute    (asyncpg via SQLAlchemy)
        4. Format     (Gemini)

    Errors are caught per-stage so the caller always gets a result object,
    never an uncaught exception.
    """
    result = PipelineResult()
    result.question = question

    # ------------------------------------------------------------------
    # Stage 1 – NL → SQL
    # ------------------------------------------------------------------
    try:
        raw_sql = await nl_to_sql(question)
        result.generated_sql = raw_sql
        result.stage = "nl_to_sql"
    except RuntimeError as exc:
        result.error = str(exc)
        result.stage = "nl_to_sql_failed"
        return result

    # ------------------------------------------------------------------
    # Guard – Gemini said "not answerable"
    # ------------------------------------------------------------------
    if raw_sql.strip().upper() == "NOT_ANSWERABLE":
        result.answer = (
            "Sorry, I can only answer questions related to vehicle cards, "
            "detected damages, repairs, and quotes in the ClearQuote database. "
            "Your question doesn't seem to fall into any of those categories. "
            "Could you rephrase or ask something else?"
        )
        result.stage = "not_answerable"
        return result

    # ------------------------------------------------------------------
    # Stage 2 – SQL validation / sanitisation
    # ------------------------------------------------------------------
    try:
        validated = validate_sql(raw_sql)
        result.validated_sql = validated
        result.stage = "validated"
    except ValueError as exc:
        result.error = f"SQL validation failed: {exc}"
        result.stage = "validation_failed"
        return result

    # ------------------------------------------------------------------
    # Stage 3 – Execute against PostgreSQL
    # ------------------------------------------------------------------
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            db_result = await session.execute(text(validated))
            columns   = list(db_result.keys())
            rows      = [dict(zip(columns, row)) for row in db_result.fetchall()]
        result.rows  = rows
        result.stage = "executed"
    except Exception as exc:
        result.error = f"Database execution failed: {exc}"
        result.stage = "execution_failed"
        return result

    # ------------------------------------------------------------------
    # Stage 4 – Format answer with Gemini
    # ------------------------------------------------------------------
    try:
        answer       = await format_answer(question, validated, rows)
        result.answer = answer
        result.stage  = "completed"
    except RuntimeError as exc:
        # We still have raw rows – return them with an error note
        result.error  = f"Answer formatting failed: {exc}"
        result.answer = (
            "I was able to retrieve data but couldn't format a nice answer. "
            "Raw results are available in the 'rows' field."
        )
        result.stage  = "format_failed"

    return result