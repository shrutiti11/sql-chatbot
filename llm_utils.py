import json
import os
from dotenv import load_dotenv

from groq import Groq
from logger_config import get_logger

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)
_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
_GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))


def build_prompt(schema, user_question):
    logger.debug("build_prompt called with user_question=%s", user_question)

    return f"""
You are an expert SQL and data visualization code generator.

Database: SQLite
Table: data
Columns:
{schema}

Output MUST be valid JSON.

The JSON must contain:
- "sql": the SQL query

The JSON MAY contain:
- "viz_code": Python code using plotly to create a visualization

If you include anything other than valid JSON, your response will be programmatically rejected.


--------------------------------
CHART SELECTION RULES (MANDATORY)
--------------------------------
If the user explicitly asks for a specific chart type, you MUST generate
that exact chart in "viz_code".

Use the following mapping:

- Bar chart:
  Use plotly.express.bar
  Trigger words: "bar", "bar chart", "compare", "distribution by category"

- Pie chart:
  Use plotly.express.pie
  Trigger words: "pie", "pie chart", "percentage", "proportion", "share"

- Line graph:
  Use plotly.express.line
  Trigger words: "line", "line chart", "trend", "over time", "time series"

- Scatter plot:
  Use plotly.express.scatter
  Trigger words: "scatter", "relationship", "correlation"

- Histogram:
  Use plotly.express.histogram
  Trigger words: "histogram", "frequency", "distribution of values"

If the user does NOT ask for a chart or visualization, OMIT the "viz_code"
field entirely.

--------------------------------
VISUALIZATION RULES
--------------------------------
If "viz_code" is included, it must:
- Import plotly.express as px (or plotly.graph_objects as go)
- Use the DataFrame variable named 'df'
- Create a figure and assign it to variable 'fig'
- Be executable Python code (no markdown, no backticks)
- Include appropriate title and axis labels

--------------------------------
STRICT SQL RULES
--------------------------------
- Query MUST start with SELECT
- Use only the table named "data"
- Use at least ONE nested subquery (IN, EXISTS, or scalar subquery)
- Subqueries must be logically necessary
- Avoid scalar subqueries returning multiple rows
- Use table aliases where required
- End the query with a semicolon
- Limit results to 100

--------------------------------
PERCENTAGE RULES (SQLite)
--------------------------------
- Do NOT return raw COUNT
- Percentages must be computed as:
  COUNT(*) * 100.0 / (SELECT COUNT(*) FROM data)
- Multiply by 100.0 BEFORE division
- Always force floating-point division

--------------------------------
OUTPUT RULES (CRITICAL)
--------------------------------
- DO NOT include explanations or comments
- DO NOT include markdown, backticks, or code fences
- DO NOT include the word "Here"
- Output ONLY a valid JSON object

User question:
{user_question}

Example JSON output when a visualization is required:
{{
    "sql": "SELECT category AS cat, COUNT(*) * 100.0 / (SELECT COUNT(*) FROM data) AS pct FROM data GROUP BY category;",
    "viz_code": "import plotly.express as px\\nfig = px.bar(df, x='cat', y='pct', title='Distribution by Category', labels={{'pct': 'Percentage'}})"
}}

If no visualization is appropriate, omit "viz_code" entirely.
"""



def generate_sql(prompt):
    logger.info("generate_sql: sending prompt to LLM (truncated)")
    try:
        response = _GROQ_CLIENT.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        sql = response.choices[0].message.content.strip()
        logger.debug(
            "generate_sql: llm response (truncated): %s",
            (sql[:300] + "...") if len(sql) > 300 else sql,
        )
        return sql
    except Exception:
        logger.exception("generate_sql: LLM call failed")
        raise


import re
import json

def generate_query_plan(prompt, retry=False):
    logger.info("generate_query_plan: sending prompt to LLM | retry=%s", retry)

    system_msg = (
        "You are a backend service. "
        "Return ONLY valid JSON. "
        "Never explain. Never use markdown."
    )

    user_prompt = prompt
    if retry:
        user_prompt = (
            "Return ONLY a valid JSON object with a single key 'sql'. "
            "The SQL must be a complete SELECT query on table 'data'. "
            "End the query with a semicolon.\n\n"
            + prompt
        )

    response = _GROQ_CLIENT.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )

    content = (response.choices[0].message.content or "").strip()
    logger.debug("Raw LLM response:\n%s", content)

    # -------- Parse attempt --------
    try:
        plan = json.loads(content)
        if isinstance(plan, dict) and "sql" in plan:
            return plan
    except json.JSONDecodeError:
        pass

    # Strip markdown
    code_block = re.search(r"```(?:sql)?([\s\S]*?)```", content, re.IGNORECASE)
    if code_block:
        content = code_block.group(1).strip()

    # Extract SELECT
    select_match = re.search(r"(select[\s\S]*)", content, re.IGNORECASE)
    if select_match:
        sql = select_match.group(1).strip()

        # Reject truncated SQL
        if " from " not in sql.lower():
            logger.warning("Detected truncated SQL, retrying...")
        else:
            if not sql.endswith(";"):
                sql += ";"
            return {"sql": sql}

    # -------- Retry once --------
    if not retry:
        return generate_query_plan(prompt, retry=True)

    # -------- Hard fail --------
    raise ValueError(
        "LLM returned incomplete or invalid SQL after retry.\n"
        f"Response:\n{content[:300]}"
    )
