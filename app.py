import streamlit as st
import pandas as pd

from db_utils import csv_to_sqlite, get_db_schema, run_sql
from llm_utils import build_prompt, generate_query_plan
from viz_utils import execute_visualization
from logger_config import get_logger

logger = get_logger(__name__)

st.title("Chat with your CSV")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        logger.info("File uploaded: shape=%s", df.shape)
    except UnicodeDecodeError:
        df = pd.read_csv(uploaded_file, encoding="latin1")
        logger.info("File uploaded with latin1 encoding: shape=%s", df.shape)

    st.subheader("Preview of CSV")
    st.dataframe(df.head())

    csv_to_sqlite(df)
    st.success("CSV saved to database")

    st.subheader("Detected SQL Schema")
    schema = get_db_schema()
    st.text(schema)

    user_question = st.text_input("Ask a question about your data")

    if user_question:
        # 1️⃣ Build prompt
        prompt = build_prompt(schema, user_question)

        # 2️⃣ Ask LLM (SQL + optional chart metadata)
        plan = generate_query_plan(prompt)

        #DEBUG: Inspect what the LLM actually returned
        st.subheader("LLM Raw Plan")
        st.json(plan)

        # Extract SQL with validation
        if isinstance(plan, str):
            # If plan is still a string, try to parse it
            import json
            try:
                plan = json.loads(plan)
            except:
                # Fall back to treating it as raw SQL
                plan = {"sql": plan}
        
        sql = plan.get("sql", "")
        if not sql:
            st.error("No SQL query generated")
            st.stop()
            
        # Clean the SQL (remove any JSON artifacts)
        sql = sql.strip()
        
        logger.info("Generated SQL: %s", sql[:200])

        st.subheader("Generated SQL")
        st.code(sql)

        # 3️⃣ Execute SQL (UNCHANGED logic)
        cols, rows = run_sql(sql)
        df_result = pd.DataFrame(rows, columns=cols)

        logger.info("Query returned %d rows", len(df_result))

        st.subheader("Results")

        # 4️⃣ Execute visualization OR show table
        if "viz_code" in plan:
            st.write("Result DataFrame:")
            st.dataframe(df_result)
            
            st.subheader("Visualization")
            execute_visualization(df_result, plan["viz_code"])
        else:
            st.dataframe(df_result)
