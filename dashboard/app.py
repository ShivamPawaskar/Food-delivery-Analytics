"""Multipage PostgreSQL-backed Food Delivery Analytics dashboard."""
import streamlit as st

from dashboard.data import filter_options_cached, search_orders
from dashboard.views import about, cities, customers, data_quality, delivery, etl_monitoring, orders, overview, reports, restaurants
from dashboard.shared import apply_style, render_global_filters

st.set_page_config(page_title="Food Delivery Analytics", page_icon="🍽️", layout="wide", initial_sidebar_state="expanded")
apply_style()

PAGES = {
    "Overview Dashboard": overview.render,
    "Order Analytics": orders.render,
    "Restaurant Analytics": restaurants.render,
    "Delivery Analytics": delivery.render,
    "Customer Analytics": customers.render,
    "City & Geographic Analytics": cities.render,
    "Data Quality Dashboard": data_quality.render,
    "ETL Monitoring": etl_monitoring.render,
    "Automated Reports": reports.render,
    "About Project": about.render,
}

st.sidebar.title("Food Delivery Insights")
st.sidebar.caption("PostgreSQL analytics workspace")
page_name = st.sidebar.radio("Navigate", list(PAGES), label_visibility="collapsed", key="dashboard_page")
if page_name == "About Project":
    about.render()
    st.stop()

try:
    with st.spinner("Connecting to PostgreSQL and loading filter options…"):
        options = filter_options_cached()
    filters = render_global_filters(options)
    with st.sidebar.form("quick_order_search", clear_on_submit=False):
        st.subheader("Quick search")
        search_text = st.text_input("Order, customer, restaurant, partner or city", placeholder="e.g. O00123")
        search_submitted = st.form_submit_button("Search orders", width="stretch")
    if search_submitted:
        st.session_state["order_search_term"] = search_text.strip()
    if st.session_state.get("order_search_term"):
        term = st.session_state["order_search_term"]
        with st.spinner("Searching matching PostgreSQL orders…"):
            matches = search_orders(term, filters)
        with st.expander(f"Search results for ‘{term}’ · {len(matches)} shown", expanded=True):
            if matches.empty:
                st.info("No orders matched that search under the current filters.")
            else:
                st.dataframe(matches, width="stretch", hide_index=True)
                st.download_button("Download search results", matches.to_csv(index=False).encode("utf-8"),
                    file_name="order_search.csv", mime="text/csv", key="order_search_download")
            if st.button("Clear search", key="clear_order_search"):
                st.session_state.pop("order_search_term", None)
                st.rerun()
    PAGES[page_name](filters)
except Exception as exc:
    st.error("Dashboard data is unavailable from PostgreSQL.")
    st.info("Set DATABASE_URL in .env, initialize food_delivery_analytics, and load the ETL outputs. See README.md for setup commands.")
    st.caption(f"Error type: {type(exc).__name__}. Check the server logs for connection details.")
