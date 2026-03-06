import streamlit as st
import requests
import pandas as pd
from datetime import datetime

API_URL = "http://127.0.0.1:8000/query"

st.set_page_config(
    page_title="RampAI SQL Intelligence",
    layout="wide"
)

st.title("🏢 RampAI Enterprise SQL Dashboard")

# -------------------------------
# Session State for History
# -------------------------------

if "history" not in st.session_state:
    st.session_state.history = []

# -------------------------------
# Query Section
# -------------------------------

st.subheader("🔎 Query Console")

query = st.text_input("Enter your query:")

col1, col2 = st.columns([1, 6])

with col1:
    run_button = st.button("Run Query")

# -------------------------------
# Run Query
# -------------------------------

if run_button and query.strip():

    with st.spinner("Processing..."):

        payload = {
            "query": query,
            "role": "admin"
        }

        response = requests.post(API_URL, json=payload)
        data = response.json()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        st.session_state.history.insert(0, {
            "timestamp": timestamp,
            "query": query,
            "response": data
        })

# -------------------------------
# Display Latest Result
# -------------------------------

if st.session_state.history:

    latest = st.session_state.history[0]
    data = latest["response"]

    st.divider()
    st.subheader("📊 Execution Summary")

    if not data.get("success"):
        st.error(f"❌ {data.get('error')}")
    else:

        similarity = data.get("similarity_score")
        timing = data.get("timing", {})

        # -----------------------
        # Metrics Panel
        # -----------------------

        col1, col2, col3, col4 = st.columns(4)

        if similarity is not None:
            col1.metric("Similarity Score", round(similarity, 4))
        else:
            col1.metric("Similarity Score", "N/A")

        col2.metric("Retrieval (s)", timing.get("retrieval_sec", "N/A"))
        col3.metric("Generation (s)", timing.get("generation_sec", "N/A"))
        col4.metric("Total Time (s)", timing.get("total_sec", "N/A"))

        st.caption(f"Request ID: {data.get('request_id')}")

        # -----------------------
        # SQL Transparency
        # -----------------------

        if data.get("sql"):
            with st.expander("📝 Generated SQL"):
                st.code(data["sql"], language="sql")

        if data.get("retrieved_tables"):
            with st.expander("📚 Retrieved Tables"):
                st.write(data["retrieved_tables"])

        # -----------------------
        # Results Display
        # -----------------------

        st.subheader("📈 Query Results")

        results = data.get("results", {})
        columns = results.get("columns", [])
        rows = results.get("rows", [])

        df = pd.DataFrame(rows, columns=columns)

        st.dataframe(df, use_container_width=True)

        # -----------------------
        # Automatic Visualization
        # -----------------------

        if len(df.columns) == 2:

            col_x = df.columns[0]
            col_y = df.columns[1]

            if pd.api.types.is_numeric_dtype(df[col_y]):

                st.subheader("📊 Visualization")

                # Detect date/time column
                try:
                    df[col_x] = pd.to_datetime(df[col_x])
                    st.line_chart(df.set_index(col_x)[col_y])
                except:
                    st.bar_chart(df.set_index(col_x)[col_y])

        # -----------------------
        # Download Button
        # -----------------------

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="⬇ Download CSV",
            data=csv,
            file_name="query_results.csv",
            mime="text/csv"
        )

# -------------------------------
# History Section
# -------------------------------

st.divider()
st.subheader("🕘 Query History")

for item in st.session_state.history[:5]:

    with st.expander(f"{item['timestamp']} | {item['query']}"):

        response = item["response"]

        if response.get("success"):
            if response.get("sql"):
                st.code(response["sql"], language="sql")
        else:
            st.error(response.get("error"))