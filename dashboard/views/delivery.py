import streamlit as st

from dashboard.components.charts import bar_chart, scatter_chart
from dashboard.components.kpi import kpi_card
from dashboard.data import fetch
from dashboard.shared import download_csv


def render(filters):
    st.title("Delivery Analytics")
    st.caption("Delivery timing, partner rankings, vehicle comparison and distance performance.")
    kpi = fetch("overall_kpis", filters).iloc[0]
    cols = st.columns(3)
    with cols[0]: kpi_card("Average delivery time", f"{float(kpi.average_delivery_time or 0):.1f} min", "Pickup to delivery; completed orders only.")
    with cols[1]: kpi_card("Late deliveries", f"{int(kpi.late_deliveries or 0):,}", "Completed orders later than the promised fulfilment time.")
    with cols[2]: kpi_card("Late delivery rate", f"{float(kpi.late_delivery_percentage or 0):.1f}%", "Late completed orders divided by completed orders.")
    with st.spinner("Loading delivery performance…"):
        distribution = fetch("delivery_time_distribution", filters)
        partners = fetch("delivery_partner_analytics", filters, limit=500)
        vehicles = fetch("vehicle_type_comparison", filters)
        scatter = fetch("delivery_distance_scatter", filters, limit=10_000)
        cities = fetch("city_analytics", filters)
    if partners.empty:
        st.info("No completed deliveries match the selected filters.")
        return
    st.markdown("## Delivery time & vehicle mix")
    left, right = st.columns(2)
    if not distribution.empty:
        left.plotly_chart(bar_chart(distribution, "bucket", "deliveries", "Delivery time distribution (10 minute buckets)"), width="stretch")
    if not vehicles.empty:
        right.plotly_chart(bar_chart(vehicles, "vehicle_type", "average_delivery_time", "Average delivery time by vehicle", y_title="Minutes"), width="stretch")
    left, right = st.columns(2)
    right.plotly_chart(bar_chart(partners.head(10), "partner_name", "total_deliveries", "Top delivery partners", horizontal=True), width="stretch")
    if not cities.empty:
        st.markdown("## City & distance performance")
        left.plotly_chart(bar_chart(cities, "city", "average_delivery_time", "Delivery performance by city", y_title="Minutes"), width="stretch")
    if not scatter.empty:
        st.plotly_chart(scatter_chart(scatter, "delivery_distance_km", "delivery_time_minutes", "Delivery distance versus delivery time", color="city", hover_data=["order_id", "is_late"]), width="stretch")
    st.subheader("Delivery partner ranking")
    st.dataframe(partners, width="stretch", hide_index=True)
    download_csv(partners, "Download delivery report", "delivery_partner_report.csv", key="delivery_export")
    download_csv(cities, "Download city delivery report", "city_delivery_report.csv", key="delivery_city_export")
