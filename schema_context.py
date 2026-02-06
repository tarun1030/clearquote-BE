"""
ClearQuote – Static schema context fed to Gemini on every prompt.
Keep this in sync with database.py whenever columns change.
"""

SCHEMA_CONTEXT = """
You are working with a PostgreSQL database called 'clearquote'.
The database contains exactly the following 4 tables.  You must ONLY query these tables.

─────────────────────────────────────────────
TABLE 1 – vehicle_cards
─────────────────────────────────────────────
  card_id          INTEGER   PRIMARY KEY (auto-increment)
  vehicle_type     VARCHAR   e.g. 'car', 'truck', 'van', 'suv'
  manufacturer     VARCHAR   e.g. 'Toyota', 'BMW', 'Ford'
  model            VARCHAR   e.g. 'Camry', '3 Series'
  manufacture_year INTEGER   4-digit year
  created_at       TIMESTAMP when the card was created

─────────────────────────────────────────────
TABLE 2 – damage_detections
─────────────────────────────────────────────
  damage_id   INTEGER   PRIMARY KEY (auto-increment)
  card_id     INTEGER   FK → vehicle_cards.card_id
  panel_name  VARCHAR   physical panel: 'front bumper', 'rear bumper',
                        'left door', 'right door', 'hood', 'trunk',
                        'front panel', 'rear panel', 'left fender',
                        'right fender', 'roof', 'windshield', etc.
  damage_type VARCHAR   e.g. 'scratch', 'dent', 'crack', 'rust',
                        'paint damage', 'impact'
  severity    VARCHAR   'low', 'medium', 'high', 'severe'
  confidence  FLOAT     AI confidence score 0.0 – 1.0
  detected_at TIMESTAMP when the damage was detected

─────────────────────────────────────────────
TABLE 3 – repairs
─────────────────────────────────────────────
  repair_id     INTEGER   PRIMARY KEY (auto-increment)
  card_id       INTEGER   FK → vehicle_cards.card_id
  panel_name    VARCHAR   same values as damage_detections.panel_name
  repair_action VARCHAR   e.g. 'repaint', 'replace panel', 'polish',
                          'buff and polish', 'weld repair'
  repair_cost   NUMERIC(12,2)   cost in the local currency
  approved      BOOLEAN   true / false
  created_at    TIMESTAMP when the repair record was created

─────────────────────────────────────────────
TABLE 4 – quotes
─────────────────────────────────────────────
  quote_id            INTEGER        PRIMARY KEY (auto-increment)
  card_id             INTEGER        FK → vehicle_cards.card_id
  total_estimated_cost NUMERIC(12,2) total cost estimate for the vehicle
  currency            VARCHAR        e.g. 'USD', 'EUR', 'INR'
  generated_at        TIMESTAMP      when the quote was generated

─────────────────────────────────────────────
IMPORTANT NOTES FOR SQL GENERATION
─────────────────────────────────────────────
• panel_name values may differ in casing in the DB; always use ILIKE or
  LOWER() when filtering on panel_name, severity, damage_type, etc.
• Informal user phrases must be mapped to actual panel_name values:
      "front side"   → 'front panel' or 'front bumper'
      "back bumper"  → 'rear bumper'
      "back side"    → 'rear panel' or 'rear bumper'
      "left side"    → 'left door' or 'left fender'
      "right side"   → 'right door' or 'right fender'
• severity levels are: low, medium, high, severe
• confidence is a float between 0 and 1.
• TODAY in PostgreSQL is: CURRENT_DATE
• Use CURRENT_TIMESTAMP for "now".
• "This month"  → WHERE date_column >= DATE_TRUNC('month', CURRENT_DATE)
• "Last 30 days" → WHERE date_column >= CURRENT_DATE - INTERVAL '30 days'
• Never invent tables or columns that don't exist above.

─────────────────────────────────────────────
JOIN RULES  (critical – read carefully)
─────────────────────────────────────────────
• repairs and damage_detections share the same card_id FK but are
  independent tables.  A repair row existing does NOT guarantee a matching
  damage_detection row, and vice-versa.

• WHEN THE USER MENTIONS "damages" AND "repair cost" (or any repair
  column) IN THE SAME QUESTION you MUST join the two tables:
      JOIN damage_detections dd
        ON dd.card_id    = r.card_id
       AND LOWER(dd.panel_name) = LOWER(r.panel_name)
  This ensures only repairs that correspond to an actual detected damage
  are included.  Filtering on repairs.panel_name alone is NOT sufficient
  when the user asks about "damages".

• Example – "average repair cost for rear bumper DAMAGES in the last 30
  days" must produce:
      SELECT AVG(r.repair_cost) AS average_repair_cost,
             COUNT(r.repair_id) AS matching_repairs
        FROM repairs r
        JOIN damage_detections dd
          ON dd.card_id = r.card_id
         AND LOWER(dd.panel_name) = LOWER(r.panel_name)
       WHERE LOWER(r.panel_name) = 'rear bumper'
         AND r.created_at >= CURRENT_DATE - INTERVAL '30 days'

• If the user asks ONLY about repairs (no mention of damages) you may
  query the repairs table alone.  If the user asks ONLY about damages
  (no mention of repairs) you may query damage_detections alone.

─────────────────────────────────────────────
NULL vs EMPTY-SET RULES  (critical)
─────────────────────────────────────────────
• AVG(), SUM(), MAX(), MIN() return NULL when there are zero input rows.
  A single-row result like {"average_repair_cost": null} does NOT mean
  "the value is zero" – it means NO rows matched the filter at all.

• Whenever you use an aggregate function, ALWAYS also select a COUNT so
  the downstream answer layer can tell NULL-because-empty apart from
  NULL-because-of-bad-data:
      SELECT AVG(r.repair_cost) AS average_repair_cost,
             COUNT(r.repair_id) AS matching_repairs   -- ← always include
        FROM …

• This COUNT must be included even when the user did not ask for it –
  it is a diagnostic column that the answer formatter needs.
"""