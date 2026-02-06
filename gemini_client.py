"""
ClearQuote – Gemini API client.

Two responsibilities:
  1. nl_to_sql(question)  → raw SQL string
  2. format_answer(question, sql, rows) → human-readable answer string

Both use gemini-2.5-flash via the official google-genai SDK.
"""

import json
import google.generativeai as genai
from config import config
from schema_context import SCHEMA_CONTEXT

# ---------------------------------------------------------------------------
# Model will be configured dynamically when needed
# ---------------------------------------------------------------------------
def _get_model():
    """
    Get a Gemini model instance with current configuration.
    This ensures we always use the latest API key and model settings.
    """
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "Gemini API key is not configured. "
            "Please set it via POST /api/config/api-key endpoint."
        )
    
    genai.configure(api_key=config.GEMINI_API_KEY)
    return genai.GenerativeModel(config.GEMINI_MODEL)

# ---------------------------------------------------------------------------
# Prompt templates (kept as module-level constants for easy tweaking)
# ---------------------------------------------------------------------------

_NL_TO_SQL_PROMPT = """
{schema}

─────────────────────────────────────────────
RULES FOR SQL GENERATION
─────────────────────────────────────────────
1. Output ONLY the raw SQL query.  No explanation, no markdown fences, no
   trailing semicolon.
2. The query MUST be a SELECT statement.  Never produce INSERT / UPDATE /
   DELETE / DROP / ALTER.
3. Use ILIKE or LOWER() for all string comparisons (panel_name, severity,
   damage_type, manufacturer, model).
4. Map informal user phrases to real column values as documented above.
5. If the user does NOT specify a time range, default to the last 30 days
   for any date-filtered query.
6. If the query is completely unrelated to vehicles / damages / repairs /
   quotes, return exactly:  NOT_ANSWERABLE
7. If the query is ambiguous (e.g. "front side" could be front panel OR
   front bumper), write the SQL so it matches BOTH options using OR / IN.
8. Alias numeric results with readable names  (e.g. AS avg_repair_cost).
9. Limit result sets to 100 rows unless the user explicitly asks for more.
10. Always prefer explicit column lists over SELECT *.
11. If the user's question mentions BOTH "damages" (or any damage-related
    word) AND any repair column (cost, action, approved …), you MUST join
    damage_detections to repairs on card_id AND panel_name.  Querying
    repairs alone when the user said "damages" is WRONG.
12. Whenever you use an aggregate function (AVG, SUM, MIN, MAX), you MUST
    also SELECT a COUNT of the rows being aggregated.  Name it clearly
    (e.g. matching_repairs, total_vehicles).  This lets the answer layer
    distinguish "NULL because zero rows matched" from "NULL because of
    bad data".  Include it even if the user did not ask for a count.
13. Never produce an aggregate-only SELECT without the companion COUNT
    described in rule 12.
14. Follow the JOIN RULES and NULL vs EMPTY-SET RULES in the schema
    context above exactly.

─────────────────────────────────────────────
USER QUESTION
─────────────────────────────────────────────
{question}
"""

_FORMAT_ANSWER_PROMPT = """
The user asked the following question about vehicle data:

"{question}"

A SQL query was run and returned the following results (as JSON):

{results_json}

The SQL that was executed:
{sql}

─────────────────────────────────────────────
RULES FOR FORMATTING THE ANSWER
─────────────────────────────────────────────
1. Convert the raw data into a clear, concise, human-readable answer.
2. If the result is a single number, state it directly with context.
3. If there are multiple rows, present them as a neat summary or short
   table (plain-text markdown is fine).
4. Include units where relevant (currency symbols(always 'INR/₹'), percentages, counts).
5. Do NOT invent information that is not in the result set.
6. Keep the tone professional but friendly.
7. If numeric values are monetary, format with 2 decimal places.

8. NULL vs EMPTY-SET – this is critical, do NOT confuse them:
   a) If the result contains a COUNT column (e.g. matching_repairs,
      total_vehicles) and that count is 0, the correct answer is:
      "No matching records were found for [what the user asked].
       There are no [X] in the database that match the given criteria."
   b) If the COUNT is > 0 but an aggregate (AVG / SUM / etc.) is NULL,
      something unexpected happened with the data – say:
      "Records were found but the [value] could not be calculated
       (the relevant field may be empty or null in the database)."
   c) If the COUNT is > 0 and the aggregate has a real value, give the
      value normally and mention how many records contributed to it:
      "The average repair cost … is ₹ XXX.XX (based on N repairs)."
   d) If no COUNT column is present and the result set is an empty list
      ([]), say: "No matching records were found."
9. Never say "no data available" without explaining WHY – use the
   distinctions in rule 8 above.
"""


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

async def nl_to_sql(question: str) -> str:
    """
    Send *question* to Gemini and get back a raw SQL string.

    Returns
    -------
    str – either a SQL query or the literal string "NOT_ANSWERABLE".

    Raises
    ------
    RuntimeError – if the API call fails.
    """
    prompt = _NL_TO_SQL_PROMPT.format(schema=SCHEMA_CONTEXT, question=question)

    try:
        model = _get_model()  # Get model with current config
        response = await model.generate_content_async(prompt)
        sql_raw = response.text.strip()
    except Exception as exc:
        raise RuntimeError(f"Gemini nl_to_sql call failed: {exc}") from exc

    return sql_raw


async def format_answer(question: str, sql: str, rows: list[dict]) -> str:
    """
    Send the user question + executed SQL + raw rows to Gemini and get back
    a polished, human-readable answer.

    Parameters
    ----------
    question : str   – original natural-language question
    sql      : str   – the SQL that was actually executed
    rows     : list  – list of dicts returned by the DB

    Returns
    -------
    str – formatted answer.
    """
    results_json = json.dumps(rows, indent=2, default=str)

    prompt = _FORMAT_ANSWER_PROMPT.format(
        question=question,
        sql=sql,
        results_json=results_json,
    )

    try:
        model = _get_model()  # Get model with current config
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as exc:
        raise RuntimeError(f"Gemini format_answer call failed: {exc}") from exc