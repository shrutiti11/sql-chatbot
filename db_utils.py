import sqlite3
import pandas as pd
from logger_config import get_logger

logger = get_logger(__name__)


def csv_to_sqlite(df, db_name="data.db", table_name="data"):
    logger.info("ENTER csv_to_sqlite")

    if df is None or df.empty:
        logger.warning("csv_to_sqlite: received empty DataFrame")
        return

    logger.debug("Original columns: %s", list(df.columns))

    # Clean column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    logger.debug("Cleaned columns: %s", list(df.columns))
    logger.info(
        "Writing DataFrame to SQLite | db=%s table=%s rows=%d cols=%d",
        db_name, table_name, df.shape[0], df.shape[1]
    )

    logger.debug("Opening SQLite connection")
    conn = sqlite3.connect(db_name)

    try:
        logger.debug("Calling DataFrame.to_sql(if_exists='replace')")
        df.to_sql(
            table_name,
            conn,
            if_exists="replace",
            index=False
        )
        logger.info("SUCCESS csv_to_sqlite: table '%s' written", table_name)

    except Exception as e:
        logger.exception(
            "FAILED csv_to_sqlite | db=%s table=%s error=%s",
            db_name, table_name, e
        )
        raise

    finally:
        logger.debug("Closing SQLite connection")
        conn.close()
        logger.info("EXIT csv_to_sqlite")


def get_db_schema(db_name="data.db", table_name="data"):
    logger.info("ENTER get_db_schema | db=%s table=%s", db_name, table_name)

    conn = sqlite3.connect(db_name)
    logger.debug("SQLite connection opened")

    try:
        cursor = conn.cursor()
        sql = f"PRAGMA table_info({table_name});"

        logger.debug("Executing SQL: %s", sql)
        cursor.execute(sql)

        columns = cursor.fetchall()
        logger.debug("Raw schema rows: %s", columns)

    except Exception as e:
        logger.exception(
            "FAILED get_db_schema | db=%s table=%s error=%s",
            db_name, table_name, e
        )
        raise

    finally:
        logger.debug("Closing SQLite connection")
        conn.close()

    schema = [f"- {col[1]} ({col[2]})" for col in columns]
    result = "\n".join(schema)

    logger.info("EXIT get_db_schema | columns=%d", len(schema))
    return result


def run_sql(sql, db_name="data.db"):
    logger.info("ENTER run_sql | db=%s", db_name)

    sql_clean = sql.strip()
    logger.debug("Received SQL: %s", sql_clean)

    # Check if it's a SELECT query (handle comments and whitespace)
    sql_lower = sql_clean.lower()
    # Remove leading SQL comments (-- or /* */)
    while sql_lower.startswith("--"):
        sql_lower = "\n".join(sql_lower.split("\n")[1:]).lstrip()
    if sql_lower.startswith("/*"):
        sql_lower = sql_lower.split("*/", 1)[1].lstrip().lower()
    
    if not sql_lower.startswith("select"):
        logger.warning("Rejected non-SELECT SQL: %s", sql_clean[:100])
        raise ValueError("Only SELECT queries are allowed")

    conn = sqlite3.connect(db_name)
    logger.debug("SQLite connection opened")

    try:
        cursor = conn.cursor()

        logger.debug("EXPLAIN QUERY PLAN for SQL")
        cursor.execute(f"EXPLAIN QUERY PLAN {sql_clean}")
        plan = cursor.fetchall()
        logger.debug("Query plan: %s", plan)

        logger.debug("Executing SQL query")
        cursor.execute(sql_clean)

        logger.debug("Fetching all rows")
        rows = cursor.fetchall()

        col_names = [desc[0] for desc in cursor.description]

        logger.info(
            "Query SUCCESS | rows=%d cols=%d",
            len(rows), len(col_names)
        )

        logger.debug("Column names: %s", col_names)
        logger.debug("First 5 rows: %s", rows[:5])

        return col_names, rows

    except Exception as e:
        logger.exception(
            "Query FAILED | db=%s sql=%s error=%s",
            db_name, sql_clean, e
        )
        raise

    finally:
        logger.debug("Closing SQLite connection")
        conn.close()
        logger.info("EXIT run_sql")


def debug_table(table_name="data", db_name="data.db", sample_limit: int = 5):
    """Return diagnostics for a table: row count, columns, distinct counts, and sample values.

    Useful for understanding why a WHERE clause may match nothing.
    """
    logger.info("ENTER debug_table | db=%s table=%s", db_name, table_name)
    conn = sqlite3.connect(db_name)
    try:
        cur = conn.cursor()

        # total rows
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        total = cur.fetchone()[0]
        logger.info("debug_table: total rows=%d", total)

        # columns
        cur.execute(f"PRAGMA table_info({table_name});")
        cols = cur.fetchall()
        col_names = [c[1] for c in cols]
        logger.info("debug_table: columns=%s", col_names)

        diagnostics = {"total_rows": total, "columns": {}}

        for col in col_names:
            try:
                # distinct count
                cur.execute(f"SELECT COUNT(DISTINCT {col}) FROM {table_name}")
                distinct = cur.fetchone()[0]

                # sample non-null values
                cur.execute(f"SELECT {col} FROM {table_name} WHERE {col} IS NOT NULL LIMIT {sample_limit}")
                samples = [r[0] for r in cur.fetchall()]

                diagnostics["columns"][col] = {
                    "distinct_count": distinct,
                    "sample_values": samples
                }
                logger.debug("debug_table col=%s distinct=%s samples=%s", col, distinct, samples)
            except Exception as e:
                logger.exception("debug_table: failed to inspect column %s: %s", col, e)
                diagnostics["columns"][col] = {"error": str(e)}

        logger.info("EXIT debug_table")
        return diagnostics

    finally:
        conn.close()
