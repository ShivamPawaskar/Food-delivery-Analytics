import streamlit as st

from dashboard.components.charts import bar_chart, donut_chart, line_chart
from dashboard.components.kpi import kpi_card
from dashboard.data import fetch, insights
from dashboard.shared import download_csv


def render(filters):
    st.title("Overview Dashboard")
    st.caption("A filtered view of orders and delivery performance stored in PostgreSQL.")
    with st.spinner("Loading overview metrics…"):
        kpis = fetch("overall_kpis", filters).iloc[0]
        daily = fetch("daily_order_trends", filters)
        status = fetch("order_status_distribution", filters)
        restaurants = fetch("top_restaurants_by_revenue", filters, limit=10)
        cuisines = fetch("cuisine_analytics", filters)
        delivery = fetch("vehicle_type_comparison", filters)
        business_insights = insights(filters)
    cards = [
        ("Total orders", f"{int(kpis.total_orders):,}", "Validated orders in the selected filters."),
        ("Completed orders", f"{int(kpis.completed_orders):,}", "Orders with delivered status."),
        ("Cancelled orders", f"{int(kpis.cancelled_orders):,}", "Orders with cancelled status."),
        ("Total revenue", f"₹{float(kpis.total_revenue or 0):,.0f}", "Order amount from completed deliveries."),
        ("Average order value", f"₹{float(kpis.average_order_value or 0):,.0f}", "Mean order amount for completed deliveries."),
        ("Average delivery time", f"{float(kpis.average_delivery_time or 0):.1f} min", "Pickup to delivery, completed orders only."),
        ("Late deliveries", f"{int(kpis.late_deliveries or 0):,}", "Completed orders exceeding promised fulfilment time."),
        ("Cancellation rate", f"{float(kpis.cancellation_percentage or 0):.1f}%", "Cancelled orders divided by filtered orders."),
    ]
    for row in (cards[:4], cards[4:]):
        cols = st.columns(4)
        for col, (label, value, help_text) in zip(cols, row):
            with col:
                kpi_card(label, value, help_text)
    if not len(daily):
        st.info("No orders match the selected filters.")
        return
    left, right = st.columns(2)
    with left:
        st.plotly_chart(line_chart(daily, "order_date", "total_orders", "Daily order volume"), width="stretch")
    with right:
        st.plotly_chart(line_chart(daily, "order_date", "revenue", "Daily revenue", y_title="Revenue (₹)"), width="stretch")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(donut_chart(status, "order_status", "total_orders", "Order status distribution"), width="stretch")
    with right:
        if not restaurants.empty:
            st.plotly_chart(bar_chart(restaurants, "restaurant_name", "revenue", "Top restaurants by revenue", horizontal=True, y_title="Revenue (₹)"), width="stretch")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(bar_chart(cuisines, "cuisine", "total_orders", "Orders by cuisine"), width="stretch")
    with right:
        if not delivery.empty:
            st.plotly_chart(bar_chart(delivery, "vehicle_type", "average_delivery_time", "Delivery time by vehicle", y_title="Minutes"), width="stretch")
    st.subheader("Database-backed business insights")
    if business_insights:
        for item in business_insights:
            with st.container(border=True):
                st.markdown(f"**{item['category']} · {item['insight']}**")
                st.caption(f"{item['evidence']} Rule: {item['rule']}")
    else:
        st.info("No insight rules were triggered for the selected filters.")
    orders = fetch("filtered_orders", filters, limit=50_000)
    download_csv(orders, "Download filtered orders", "filtered_orders.csv", key="overview_orders_download")
