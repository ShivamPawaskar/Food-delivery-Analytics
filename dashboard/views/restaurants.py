import streamlit as st

from dashboard.components.charts import bar_chart
from dashboard.data import fetch, filter_options_cached
from dashboard.shared import download_csv


def render(filters):
    st.title("Restaurant Analytics")
    st.caption("Compare restaurant revenue, order volume, cuisine and service performance.")
    options = filter_options_cached()
    c1, c2 = st.columns(2)
    all_restaurants = options.get("restaurants") or []
    if filters.get("restaurant_id"):
        all_restaurants = [r for r in all_restaurants if r.split(" | ", 1)[0] == filters["restaurant_id"]]
    restaurant_options = ["Use global selection", "All visible restaurants", *all_restaurants]
    local_restaurant = c1.selectbox("Restaurant filter", restaurant_options, key="restaurant_page_filter")
    all_cuisines = options.get("cuisines") or []
    if filters.get("cuisine"):
        all_cuisines = [c for c in all_cuisines if c == filters["cuisine"]]
    cuisine_options = ["Use global selection", "All visible cuisines", *all_cuisines]
    local_cuisine = c2.selectbox("Cuisine filter", cuisine_options, key="restaurant_cuisine_filter")
    page_filters = dict(filters)
    if local_restaurant == "All visible restaurants":
        page_filters["restaurant_id"] = filters.get("restaurant_id")
    elif local_restaurant != "Use global selection":
        page_filters["restaurant_id"] = local_restaurant.split(" | ", 1)[0]
    if local_cuisine == "All visible cuisines":
        page_filters["cuisine"] = filters.get("cuisine")
    elif local_cuisine != "Use global selection":
        page_filters["cuisine"] = local_cuisine
    with st.spinner("Loading restaurant performance…"):
        revenue = fetch("top_restaurants_by_revenue", page_filters, limit=10)
        orders = fetch("top_restaurants_by_orders", page_filters, limit=10)
        ratings = fetch("restaurant_ratings", page_filters, limit=500)
        cuisine = fetch("cuisine_analytics", page_filters)
    if revenue.empty and cuisine.empty:
        st.info("No restaurant orders match the selected filters.")
        return
    st.markdown("## Revenue & order leaders")
    left, right = st.columns(2)
    if not revenue.empty:
        left.plotly_chart(bar_chart(revenue, "restaurant_name", "revenue", "Top 10 by revenue", horizontal=True, y_title="Revenue (₹)"), width="stretch")
    if not orders.empty:
        right.plotly_chart(bar_chart(orders, "restaurant_name", "total_orders", "Top 10 by order volume", horizontal=True), width="stretch")
    left, right = st.columns(2)
    if not cuisine.empty:
        st.markdown("## Cuisine performance")
        left.plotly_chart(bar_chart(cuisine, "cuisine", "revenue", "Revenue by cuisine", y_title="Revenue (₹)"), width="stretch")
        right.plotly_chart(bar_chart(cuisine, "cuisine", "total_orders", "Orders by cuisine"), width="stretch")
    if not ratings.empty:
        st.markdown("## Service quality & preparation")
        left, right = st.columns(2)
        left.plotly_chart(bar_chart(ratings, "restaurant_name", "restaurant_rating", "Restaurant ratings", horizontal=True, y_title="Rating / 5"), width="stretch")
        right.plotly_chart(bar_chart(ratings, "restaurant_name", "average_preparation_time", "Average preparation time", horizontal=True, y_title="Minutes"), width="stretch")
        st.subheader("Restaurant performance ranking")
        st.dataframe(ratings.sort_values(["total_orders", "restaurant_rating"], ascending=False), width="stretch", hide_index=True)
    export = fetch("top_restaurants_by_revenue", page_filters, limit=500)
    download_csv(export, "Download restaurant performance", "restaurant_performance.csv", key="restaurant_export")
