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


def generate_query_plan(prompt):
    """
    Primary interface expected by the app.

    Tries to parse a JSON plan from the LLM output.
    Falls back to raw SQL if needed.
    Always returns a dict.
    """
    logger.info("generate_query_plan: sending prompt to LLM")
    try:
        response = _GROQ_CLIENT.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content
        
        # Check if content is None or empty
        if not content:
            logger.error("LLM returned empty response")
            raise ValueError("LLM returned an empty response")
        
        content = content.strip()
        
        # Remove markdown code block formatting if present
        if content.startswith("```"):
            # Extract content between triple backticks
            lines = content.split('\n')
            # Skip the opening ``` line (and language identifier if present)
            start_idx = 1
            # Find the closing ```
            end_idx = len(lines)
            for i in range(1, len(lines)):
                if lines[i].strip().startswith("```"):
                    end_idx = i
                    break
            content = '\n'.join(lines[start_idx:end_idx]).strip()
        
        logger.debug(
            "LLM response (truncated): %s",
            (content[:300] + "...") if len(content) > 300 else content,
        )

        # Try to parse as JSON first
        try:
            plan = json.loads(content)
            
            # Validate it's a dict
            if not isinstance(plan, dict):
                logger.warning("LLM returned JSON but not a dict, treating as raw SQL")
                return {"sql": content.strip()}
            
            # Clean up SQL if present
            if "sql" in plan and isinstance(plan["sql"], str):
                plan["sql"] = plan["sql"].strip()
                
            return plan
            
        except json.JSONDecodeError:
            # Not JSON, check if it's raw SQL
            if content.lower().strip().startswith("select"):
                logger.info("LLM returned raw SQL (no JSON wrapper)")
                return {"sql": content.strip()}
            else:
                logger.warning(f"LLM did not return valid JSON or SQL. Response: {content[:200]}")
                raise ValueError(f"LLM response is neither valid JSON nor SQL. Got: {content[:200]}")

    except Exception:
        logger.exception("generate_query_plan: LLM call failed")
        raise
