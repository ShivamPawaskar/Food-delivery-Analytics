import streamlit as st

from dashboard.components.charts import bar_chart
from dashboard.data import fetch
from dashboard.shared import download_csv


def render(filters):
    st.title("City & Geographic Analytics")
    st.caption("Compare city-level volume, revenue, delivery time and cancellations.")
    with st.spinner("Loading city analytics…"):
        cities = fetch("city_analytics", filters)
    if cities.empty:
        st.info("No city-level records match the selected filters.")
        return
    left, right = st.columns(2)
    left.plotly_chart(bar_chart(cities, "city", "total_orders", "Orders by city"), width="stretch")
    right.plotly_chart(bar_chart(cities, "city", "revenue", "Revenue by city", y_title="Revenue (₹)"), width="stretch")
    left, right = st.columns(2)
    left.plotly_chart(bar_chart(cities, "city", "average_delivery_time", "Average delivery time by city", y_title="Minutes"), width="stretch")
    right.plotly_chart(bar_chart(cities, "city", "cancellation_rate", "City-wise cancellation rate", y_title="Cancelled orders (%)"), width="stretch")
    st.info("The source data contains city names but no verified latitude/longitude. This page uses city-level comparisons instead of inventing map coordinates.")
    st.dataframe(cities, width="stretch", hide_index=True)
    download_csv(cities, "Download city performance", "city_performance_report.csv", key="city_export")
