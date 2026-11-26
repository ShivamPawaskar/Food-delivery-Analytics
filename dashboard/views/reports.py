import streamlit as st

from analytics.reports import build_csv_bundle, build_pdf_report
from dashboard.data import reports
from dashboard.shared import download_csv


def render(filters):
    st.title("Automated Reports")
    st.caption("Generate filter-aware reports directly from the PostgreSQL analytics tables.")
    with st.spinner("Collecting current database reports…"):
        report_data = reports(filters)
    st.info("The PDF summarizes up to 12 rows per section for readability. The ZIP includes complete query results as individual CSV files.")
    left, right = st.columns(2)
    with left:
        st.download_button("Download all reports (ZIP)", build_csv_bundle(report_data),
            file_name="food_delivery_analytics_reports.zip", mime="application/zip", key="all_reports_zip")
    with right:
        pdf_data = build_pdf_report(report_data, filters)
        st.download_button("Download business report (PDF)", pdf_data,
            file_name="food_delivery_analytics_report.pdf", mime="application/pdf", key="business_report_pdf")
    st.subheader("Report sections")
    for name, frame in report_data.items():
        with st.expander(name.replace("_", " ").title(), expanded=False):
            st.dataframe(frame.head(100), width="stretch", hide_index=True)
            st.caption(f"{len(frame):,} rows queried from PostgreSQL.")
            download_csv(frame, f"Download {name.replace('_', ' ')} CSV", f"{name}.csv", key=f"report_{name}")
