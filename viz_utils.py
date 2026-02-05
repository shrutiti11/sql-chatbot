import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from logger_config import get_logger

logger = get_logger(__name__)


def execute_visualization(df, viz_code):
    logger.info("Executing visualization code")
    logger.debug("Viz code: %s", viz_code)

    try:
        # Remove import statements for safety (already provided in globals)
        viz_code = "\n".join(
            line for line in viz_code.splitlines()
            if not line.strip().startswith(("import ", "from "))
        )

        # Create execution environment with required modules and data
        exec_globals = {
            'df': df,
            'px': px,
            'go': go,
            'fig': None,
            '__builtins__': __builtins__
        }

        exec(viz_code, exec_globals)

        fig = exec_globals.get('fig')

        if fig is None:
            st.error("Error: Generated code did not create a figure")
            st.code(viz_code, language='python')
            return

        st.plotly_chart(fig, use_container_width=True)
        logger.info("Visualization rendered successfully")

    except Exception as e:
        logger.exception("Failed to execute visualization code")
        st.error(f"Error executing visualization: {str(e)}")
        st.subheader("Generated Code:")
        st.code(viz_code, language='python')
        st.subheader("DataFrame Preview:")
        st.dataframe(df)
