import streamlit as st

from dashboard.components.charts import bar_chart, histogram
from dashboard.components.kpi import kpi_card
from dashboard.data import fetch
from dashboard.shared import download_csv


def render(filters):
    st.title("Customer Analytics")
    st.caption("Customer activity counts include all validated order statuses; spending counts delivered orders only.")
    with st.spinner("Calculating customer metrics…"):
        kpis = fetch("customer_kpis", filters).iloc[0]
        frequency = fetch("customer_frequency", filters)
        spending = fetch("customer_spending", filters, limit=10_000)
        top = fetch("top_customers_by_spend", filters, limit=10)
    cols = st.columns(3)
    with cols[0]: kpi_card("Unique customers", f"{int(kpis.unique_customers or 0):,}", "Distinct customers with at least one validated order.")
    with cols[1]: kpi_card("Repeat customers", f"{int(kpis.repeat_customers or 0):,}", "Customers with two or more validated orders.")
    with cols[2]: kpi_card("Orders per customer", f"{float(kpis.average_orders_per_customer or 0):.2f}", "Mean validated orders per distinct customer.")
    if spending.empty:
        st.info("No customers match the selected filters.")
        return
    left, right = st.columns(2)
    left.plotly_chart(histogram(spending, "spending", "Customer completed-order spending distribution", nbins=24), width="stretch")
    right.plotly_chart(bar_chart(frequency, "total_orders", "customers", "Customer ordering frequency", y_title="Customers"), width="stretch")
    st.subheader("Highest spending customers")
    st.dataframe(top, width="stretch", hide_index=True)
    download_csv(spending, "Download customer report", "customer_spending_report.csv", key="customer_export")
