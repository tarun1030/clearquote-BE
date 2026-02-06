"""
ClearQuote – SQL safety / validation layer.

Responsibilities:
  1. Block any non-SELECT statement (DDL / DML).
  2. Reject known dangerous keywords / functions.
  3. Strip trailing semicolons (PostgreSQL quirk with asyncpg).
  4. Return a clean, validated query string or raise ValueError.
"""

import re

# ---------------------------------------------------------------------------
# Blocked top-level statements  (case-insensitive)
# ---------------------------------------------------------------------------
_BLOCKED_STATEMENTS = re.compile(
    r"^\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|CALL)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Blocked keywords / functions anywhere in the query
# ---------------------------------------------------------------------------
_BLOCKED_TOKENS = re.compile(
    r"\b(pg_sleep|COPY|EXPLAIN\s+ANALYZE|SET\s+ROLE|"
    r"pg_read_file|pg_write|pg_dump|system|RAISE|"
    r"dblink|EXECUTE|FORMAT\s*\(\s*'.*DROP|"
    r"information_schema|pg_catalog)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Must start with SELECT (after optional WITH for CTEs)
# ---------------------------------------------------------------------------
_ALLOWED_START = re.compile(r"^\s*(WITH\s+.*)?SELECT\b", re.IGNORECASE | re.DOTALL)


def validate_sql(raw_sql: str) -> str:
    """
    Validate and sanitise *raw_sql*.

    Returns
    -------
    str – the cleaned query ready for execution.

    Raises
    ------
    ValueError – if the query fails any safety check.
    """
    if not raw_sql or not raw_sql.strip():
        raise ValueError("Empty SQL query received.")

    sql = raw_sql.strip()

    # ---- strip wrapping markdown code-fences the LLM sometimes adds ----
    # e.g.  ```sql\nSELECT …\n```
    sql = re.sub(r"^```(?:sql)?\s*\n?", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\n?```\s*$", "", sql)
    sql = sql.strip()

    # ---- strip trailing semicolons (asyncpg does not like them) ----
    sql = sql.rstrip(";").strip()

    # ---- blocked top-level command? ----
    if _BLOCKED_STATEMENTS.match(sql):
        raise ValueError(
            "Only SELECT queries are allowed. "
            "Destructive statements (DROP, INSERT, UPDATE, DELETE, …) are blocked."
        )

    # ---- must start with SELECT or WITH … SELECT ----
    if not _ALLOWED_START.match(sql):
        raise ValueError(
            "Query must be a SELECT statement (or a CTE starting with WITH … SELECT)."
        )

    # ---- blocked tokens / functions anywhere? ----
    if _BLOCKED_TOKENS.search(sql):
        raise ValueError(
            "Query contains a blocked keyword or function. "
            "Only standard SELECT queries against ClearQuote tables are permitted."
        )

    # ---- only allow known table names ----
    _ALLOWED_TABLES = {"vehicle_cards", "damage_detections", "repairs", "quotes"}
    # quick heuristic: FROM / JOIN clauses
    tables_in_query = set(
        t.lower().strip()
        for t in re.findall(
            r"(?:FROM|JOIN)\s+(\w+)", sql, re.IGNORECASE
        )
    )
    unknown = tables_in_query - _ALLOWED_TABLES
    if unknown:
        raise ValueError(
            f"Query references unknown table(s): {unknown}. "
            f"Allowed tables: {_ALLOWED_TABLES}"
        )

    return sql
