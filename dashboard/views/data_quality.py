import pandas as pd
import streamlit as st

from dashboard.components.charts import bar_chart
from dashboard.components.kpi import kpi_card
from dashboard.data import fetch
from dashboard.shared import download_csv


def _count(reasons, predicate):
    return sum(int(value) for name, value in reasons.items() if predicate(name))


def render(_filters):
    st.title("Data Quality Dashboard")
    st.caption("Quality figures describe the latest recorded ETL input. Rejection reason totals count issues, so one order may have multiple reasons.")
    with st.spinner("Loading ETL quality report…"):
        quality_rows = fetch("latest_quality_run")
    if quality_rows.empty:
        st.info("No ETL quality reports have been loaded into PostgreSQL yet.")
        return
    latest = quality_rows.iloc[0]
    reasons = latest.rejection_reason_counts or {}
    source = int(latest.source_orders or 0)
    accepted = int(latest.valid_row_count or 0)
    rejected = int(latest.rejected_row_count or 0)
    missing = _count(reasons, lambda n: n.startswith("missing_"))
    duplicates = _count(reasons, lambda n: n == "duplicate_order_id")
    timestamps = _count(reasons, lambda n: "timestamp" in n)
    foreign_keys = _count(reasons, lambda n: n.startswith("unknown_"))
    numerical = _count(reasons, lambda n: any(term in n for term in ("amount", "delivery_fee", "distance", "promised_delivery")))
    quality_pct = 100 * accepted / source if source else 0
    cards = [("Raw records", f"{source:,}"), ("Accepted records", f"{accepted:,}"), ("Rejected records", f"{rejected:,}"),
        ("Data quality", f"{quality_pct:.1f}%"), ("Duplicate rows", f"{duplicates:,}"), ("Missing value issues", f"{missing:,}"),
        ("Timestamp issues", f"{timestamps:,}"), ("Foreign key issues", f"{foreign_keys:,}"), ("Numeric issues", f"{numerical:,}")]
    for i in range(0, len(cards), 3):
        cols = st.columns(3)
        for col, (label, value) in zip(cols, cards[i:i+3]):
            with col:
                kpi_card(label, value)
    reason_frame = pd.DataFrame([{"rejection_reason": name, "issue_count": int(value)} for name, value in reasons.items()])
    if not reason_frame.empty:
        reason_frame = reason_frame.sort_values("issue_count", ascending=False)
        st.plotly_chart(bar_chart(reason_frame.head(15), "rejection_reason", "issue_count", "Most common rejection reasons", horizontal=True), width="stretch")
    reason_choices = ["All reasons", *(reason_frame.rejection_reason.tolist() if not reason_frame.empty else [])]
    selected = st.selectbox("Inspect rejected records", reason_choices, key="quality_reason_filter")
    records = fetch("rejected_records", limit=50_000, execution_id=str(latest.execution_id),
        reason=None if selected == "All reasons" else selected)
    st.dataframe(records.head(250), width="stretch", hide_index=True)
    if len(records) > 250:
        st.caption(f"Showing 250 of {len(records):,} matching rejected records; the download contains all matching rows.")
    download_csv(records, "Download rejection report", "rejected_records.csv", key="rejected_report_download")
    quality = pd.DataFrame([{"metric": label, "value": value} for label, value in cards])
    download_csv(quality, "Download data quality summary", "data_quality_report.csv", key="quality_summary_download")
