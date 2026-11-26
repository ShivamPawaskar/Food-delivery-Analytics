import pandas as pd
import streamlit as st

from dashboard.components.charts import bar_chart
from dashboard.components.kpi import kpi_card
from dashboard.data import fetch
from dashboard.shared import download_csv


def render(_filters):
    st.title("ETL Monitoring")
    st.caption("Execution history and row-level processing outcomes stored in PostgreSQL.")
    with st.spinner("Loading ETL history…"):
        history = fetch("latest_etl_runs", limit=100)
    if history.empty:
        st.info("No ETL runs have been loaded into PostgreSQL yet.")
        return
    latest = history.iloc[0]
    source_orders = (latest.source_row_counts or {}).get("orders", 0)
    cards = [("Latest execution", str(latest.execution_id)[:12] + "…"), ("Status", latest.execution_status),
        ("Duration", f"{float(latest.execution_duration_seconds or 0):.2f} sec"),
        ("Input orders", f"{int(source_orders):,}"), ("Processed orders", f"{int(latest.valid_row_count):,}"),
        ("Rejected orders", f"{int(latest.rejected_row_count):,}")]
    for i in (0, 3):
        cols = st.columns(3)
        for col, (label, value) in zip(cols, cards[i:i+3]):
            with col:
                kpi_card(label, value)
    st.caption(f"Database load status: {latest.database_load_status}")
    reasons = latest.rejection_reason_counts or {}
    if reasons:
        reasons_frame = pd.DataFrame([{"reason": name, "count": int(value)} for name, value in reasons.items()]).sort_values("count", ascending=False)
        st.plotly_chart(bar_chart(reasons_frame.head(15), "reason", "count", "Latest run rejection statistics", horizontal=True), width="stretch")
    st.subheader("ETL execution history")
    display = history.drop(columns=["source_row_counts", "transformation_counts", "rejection_reason_counts"], errors="ignore")
    st.dataframe(display, width="stretch", hide_index=True)
    download_csv(history, "Download ETL history", "etl_execution_history.csv", key="etl_history_download")
