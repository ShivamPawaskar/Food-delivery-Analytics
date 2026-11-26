"""Cached PostgreSQL access for Streamlit pages."""
import streamlit as st

from database.connection import get_engine
from database.queries import load_filter_options, run_analytics
from analytics.insights import build_insights
from analytics.reports import build_report_data


@st.cache_resource
def engine():
    return get_engine()


@st.cache_data(ttl=60, show_spinner=False)
def query_cached(query_name, start_date, end_date, city, restaurant_id, cuisine, payment_method,
                 order_status, limit=10, execution_id=None, reason=None):
    return run_analytics(engine(), query_name, start_date=start_date, end_date=end_date, city=city,
        restaurant_id=restaurant_id, cuisine=cuisine, payment_method=payment_method,
        order_status=order_status, limit=limit, execution_id=execution_id, reason=reason)


@st.cache_data(ttl=300, show_spinner=False)
def filter_options_cached():
    return load_filter_options(engine())


@st.cache_data(ttl=60, show_spinner=False)
def report_data_cached(start_date, end_date, city, restaurant_id, cuisine, payment_method, order_status):
    filters = {"start_date": start_date, "end_date": end_date, "city": city,
        "restaurant_id": restaurant_id, "cuisine": cuisine, "payment_method": payment_method, "order_status": order_status}
    return build_report_data(engine(), filters)


@st.cache_data(ttl=60, show_spinner=False)
def insights_cached(start_date, end_date, city, restaurant_id, cuisine, payment_method, order_status):
    kpis = query_cached("overall_kpis", start_date, end_date, city, restaurant_id, cuisine, payment_method, order_status).iloc[0].to_dict()
    restaurants = query_cached("restaurant_ratings", start_date, end_date, city, restaurant_id, cuisine, payment_method, order_status)
    cities = query_cached("city_analytics", start_date, end_date, city, restaurant_id, cuisine, payment_method, order_status)
    cuisines = query_cached("cuisine_analytics", start_date, end_date, city, restaurant_id, cuisine, payment_method, order_status)
    partners = query_cached("delivery_partner_analytics", start_date, end_date, city, restaurant_id, cuisine, payment_method, order_status, 500)
    peak = query_cached("peak_ordering_hours", start_date, end_date, city, restaurant_id, cuisine, payment_method, order_status)
    return build_insights(kpis, restaurants, cities, cuisines, partners, peak)


def fetch(query_name, filters=None, *, limit=10, execution_id=None, reason=None):
    filters = filters or {}
    return query_cached(query_name, filters.get("start_date"), filters.get("end_date"),
        filters.get("city"), filters.get("restaurant_id"), filters.get("cuisine"),
        filters.get("payment_method"), filters.get("order_status"), limit, execution_id, reason)


@st.cache_data(ttl=60, show_spinner=False)
def search_orders(term, filters=None):
    """Search matching orders in PostgreSQL under the currently selected filters."""
    filters = filters or {}
    return run_analytics(engine(), "quick_order_search", start_date=filters.get("start_date"),
        end_date=filters.get("end_date"), city=filters.get("city"),
        restaurant_id=filters.get("restaurant_id"), cuisine=filters.get("cuisine"),
        payment_method=filters.get("payment_method"), order_status=filters.get("order_status"),
        search_term=term.strip() or None, limit=100)


def insights(filters=None):
    filters = filters or {}
    return insights_cached(filters.get("start_date"), filters.get("end_date"), filters.get("city"),
        filters.get("restaurant_id"), filters.get("cuisine"), filters.get("payment_method"), filters.get("order_status"))


def reports(filters=None):
    filters = filters or {}
    return report_data_cached(filters.get("start_date"), filters.get("end_date"), filters.get("city"),
        filters.get("restaurant_id"), filters.get("cuisine"), filters.get("payment_method"), filters.get("order_status"))
