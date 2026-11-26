import streamlit as st

from dashboard.components.charts import bar_chart, donut_chart, line_chart, multi_line_chart, weekday_heatmap
from dashboard.data import fetch
from dashboard.shared import download_csv


def render(filters):
    st.title("Order Analytics")
    st.caption("Volume, payment mix, ordering patterns and revenue trends.")
    with st.spinner("Querying order analytics…"):
        daily = fetch("daily_advanced_trends", filters)
        monthly = fetch("monthly_advanced_trends", filters)
        payments = fetch("orders_by_payment_method", filters)
        status = fetch("order_status_distribution", filters)
        hours = fetch("peak_ordering_hours", filters)
        periods = fetch("weekday_weekend_performance", filters)
        aov = fetch("average_order_value_trends", filters)
        heat = fetch("orders_by_weekday_hour", filters)
    if daily.empty:
        st.info("No orders match the selected filters.")
        return
    st.markdown("## Order volume & revenue")
    left, right = st.columns(2)
    left.plotly_chart(multi_line_chart(daily, "order_date", ["total_orders", "orders_7_day_avg"], "Daily orders with 7-day moving average", y_title="Orders"), width="stretch")
    right.plotly_chart(multi_line_chart(daily, "order_date", ["revenue", "revenue_7_day_avg"], "Revenue with 7-day moving average", y_title="Revenue (₹)"), width="stretch")
    left, right = st.columns(2)
    left.plotly_chart(multi_line_chart(monthly, "order_month", ["total_orders", "orders_3_month_avg"], "Monthly orders with 3-month moving average", y_title="Orders"), width="stretch")
    right.plotly_chart(line_chart(aov, "order_date", "average_order_value", "Average order value trend", y_title="AOV (₹)"), width="stretch")
    st.markdown("## Ordering patterns")
    left, right = st.columns(2)
    left.plotly_chart(bar_chart(payments, "payment_method", "total_orders", "Orders by payment method"), width="stretch")
    right.plotly_chart(donut_chart(status, "order_status", "total_orders", "Orders by status"), width="stretch")
    st.markdown("## Growth & weekly rhythm")
    left, right = st.columns(2)
    left.plotly_chart(bar_chart(hours, "order_hour", "total_orders", "Peak ordering hours"), width="stretch")
    right.plotly_chart(bar_chart(periods, "period", "total_orders", "Weekday versus weekend"), width="stretch")
    st.plotly_chart(bar_chart(periods, "period", "revenue", "Weekday versus weekend revenue", y_title="Revenue (₹)"), width="stretch")
    growth = daily[daily.revenue_growth_pct.notna()]
    if not growth.empty:
        st.plotly_chart(line_chart(growth, "order_date", "revenue_growth_pct", "Daily revenue growth", y_title="Change versus previous day (%)"), width="stretch")
    monthly_growth = monthly[monthly.revenue_growth_pct.notna()]
    if not monthly_growth.empty:
        st.plotly_chart(line_chart(monthly_growth, "order_month", "revenue_growth_pct", "Monthly revenue growth", y_title="Change versus previous month (%)"), width="stretch")
    st.plotly_chart(weekday_heatmap(heat), width="stretch")
    download_csv(fetch("filtered_orders", filters, limit=50_000), "Download filtered order report", "order_analytics.csv", key="order_analytics_download")
