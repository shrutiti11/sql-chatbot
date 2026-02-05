# 📊 Chat with Your CSV – Natural Language to SQL & Visualization

An interactive Streamlit application that allows users to **upload a CSV file, ask questions in natural language**, and instantly get **SQL-powered answers and visualizations** using an LLM.

This project bridges **data analysis, databases, and generative AI**, making structured data querying accessible to non-technical users.

---

## 🚀 Features

- 📁 Upload any CSV file
- 🗄️ Automatically converts CSV to SQLite database
- 🧠 Uses an LLM to convert **natural language → SQL**
- 🔒 Enforces **safe, read-only (SELECT-only)** SQL execution
- 📊 Generates **interactive Plotly visualizations** when relevant
- 🧩 Displays generated SQL queries transparently
- 📈 Supports bar, pie, line, scatter, and histogram charts
- 📝 Clean logging for debugging and traceability

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit  
- **Data Handling:** Pandas  
- **Database:** SQLite  
- **LLM:** Groq (LLaMA 3.1)  
- **Visualization:** Plotly  
- **Environment Management:** python-dotenv  

---

## 📂 Project Structure

```text
.
├── app.py               # Streamlit application entry point
├── db_utils.py          # CSV → SQLite, schema extraction, SQL execution
├── llm_utils.py         # Prompt building & LLM interaction
├── viz_utils.py         # Secure execution of LLM-generated visualizations
├── logger_config.py     # Centralized logging configuration
├── data.db              # SQLite database (auto-generated)
├── requirements.txt     # Project dependencies
└── .env                 # Environment variables (not committed)
