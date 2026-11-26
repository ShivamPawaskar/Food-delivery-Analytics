"""Parameterized SQL analytics executed by PostgreSQL, not Python-side CSV scans."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

DATE_FILTER = "(:start_date IS NULL OR order_date >= CAST(:start_date AS DATE)) AND (:end_date IS NULL OR order_date < CAST(:end_date AS DATE))"
TS_FILTER = "(:start_date IS NULL OR order_timestamp >= CAST(:start_date AS TIMESTAMP)) AND (:end_date IS NULL OR order_timestamp < CAST(:end_date AS TIMESTAMP))"


def order_filters(alias: str = "") -> str:
    """Predicates are fixed here; values are always passed as bound parameters."""
    prefix = f"{alias}." if alias else ""
    return " AND ".join((f"(:city IS NULL OR {prefix}city=:city)", f"(:restaurant_id IS NULL OR {prefix}restaurant_id=:restaurant_id)",
        f"(:cuisine IS NULL OR {prefix}cuisine=:cuisine)", f"(:payment_method IS NULL OR {prefix}payment_method=:payment_method)",
        f"(:order_status IS NULL OR {prefix}order_status=:order_status)"))

ANALYTICS_QUERIES = {
    "overall_kpis": f"""SELECT COUNT(*) AS total_orders,
        COUNT(*) FILTER (WHERE order_status='delivered') AS completed_orders,
        COUNT(*) FILTER (WHERE order_status='cancelled') AS cancelled_orders,
        COALESCE(SUM(revenue),0) AS total_revenue,
        AVG(order_amount) FILTER (WHERE order_status='delivered') AS average_order_value,
        AVG(delivery_time_minutes) FILTER (WHERE order_status='delivered') AS average_delivery_time,
        COUNT(*) FILTER (WHERE is_late AND order_status='delivered') AS late_deliveries,
        100.0 * COUNT(*) FILTER (WHERE is_late AND order_status='delivered') / NULLIF(COUNT(*) FILTER (WHERE order_status='delivered'),0) AS late_delivery_percentage,
        100.0 * COUNT(*) FILTER (WHERE order_status='cancelled') / NULLIF(COUNT(*),0) AS cancellation_percentage
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()}""",
    "top_restaurants_by_revenue": f"""SELECT r.restaurant_id, r.restaurant_name, r.restaurant_rating,
        COUNT(o.order_id) AS total_orders, COALESCE(SUM(o.revenue),0) AS revenue,
        AVG(o.prep_time_minutes) AS average_preparation_time,
        AVG(o.delivery_time_minutes) FILTER (WHERE o.order_status='delivered') AS average_delivery_time,
        100.0 * COUNT(*) FILTER (WHERE o.is_late AND o.order_status='delivered') / NULLIF(COUNT(*) FILTER (WHERE o.order_status='delivered'),0) AS late_delivery_percentage
        FROM restaurants r JOIN processed_orders o ON o.restaurant_id=r.restaurant_id
        WHERE {DATE_FILTER} AND {order_filters('o')}
        GROUP BY r.restaurant_id, r.restaurant_name, r.restaurant_rating ORDER BY revenue DESC LIMIT :limit""",
    "top_restaurants_by_orders": f"""SELECT r.restaurant_id, r.restaurant_name, r.restaurant_rating,
        COUNT(o.order_id) AS total_orders, COALESCE(SUM(o.revenue),0) AS revenue,
        AVG(o.prep_time_minutes) AS average_preparation_time,
        AVG(o.delivery_time_minutes) FILTER (WHERE o.order_status='delivered') AS average_delivery_time,
        100.0 * COUNT(*) FILTER (WHERE o.is_late AND o.order_status='delivered') / NULLIF(COUNT(*) FILTER (WHERE o.order_status='delivered'),0) AS late_delivery_percentage
        FROM restaurants r JOIN processed_orders o ON o.restaurant_id=r.restaurant_id
        WHERE {DATE_FILTER} AND {order_filters('o')}
        GROUP BY r.restaurant_id, r.restaurant_name, r.restaurant_rating ORDER BY total_orders DESC LIMIT :limit""",
    "restaurant_ratings": f"""SELECT r.restaurant_id, r.restaurant_name, r.restaurant_rating,
        COUNT(o.order_id) AS total_orders,COUNT(o.order_id) FILTER (WHERE o.order_status='delivered') AS completed_orders,
        COALESCE(SUM(o.revenue),0) AS revenue,
        AVG(o.prep_time_minutes) AS average_preparation_time,
        AVG(o.delivery_time_minutes) FILTER (WHERE o.order_status='delivered') AS average_delivery_time,
        100.0 * COUNT(*) FILTER (WHERE o.is_late AND o.order_status='delivered') / NULLIF(COUNT(*) FILTER (WHERE o.order_status='delivered'),0) AS late_delivery_percentage
        FROM restaurants r LEFT JOIN processed_orders o ON o.restaurant_id=r.restaurant_id AND {DATE_FILTER} AND {order_filters('o')}
        WHERE (:restaurant_id IS NULL OR r.restaurant_id=:restaurant_id)
          AND (:cuisine IS NULL OR r.cuisine=:cuisine) AND (:city IS NULL OR r.city=:city)
        GROUP BY r.restaurant_id,r.restaurant_name,r.restaurant_rating ORDER BY r.restaurant_rating DESC""",
    "city_analytics": f"""SELECT city, COUNT(*) AS total_orders, SUM(revenue) AS revenue,
        AVG(delivery_time_minutes) FILTER (WHERE order_status='delivered') AS average_delivery_time,
        100.0 * COUNT(*) FILTER (WHERE order_status='cancelled') / NULLIF(COUNT(*),0) AS cancellation_rate
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY city ORDER BY total_orders DESC""",
    "cuisine_analytics": f"""SELECT cuisine, COUNT(*) AS total_orders, SUM(revenue) AS revenue,
        AVG(order_amount) FILTER (WHERE order_status='delivered') AS average_order_value
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY cuisine ORDER BY revenue DESC""",
    "delivery_partner_analytics": f"""SELECT partner_id, partner_name, vehicle_type, partner_rating,
        COUNT(*) FILTER (WHERE order_status='delivered') AS total_deliveries,
        AVG(delivery_time_minutes) FILTER (WHERE order_status='delivered') AS average_delivery_time,
        AVG(delivery_distance_km) FILTER (WHERE order_status='delivered') AS average_delivery_distance,
        100.0 * COUNT(*) FILTER (WHERE is_late AND order_status='delivered') / NULLIF(COUNT(*) FILTER (WHERE order_status='delivered'),0) AS late_delivery_percentage
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()}
        GROUP BY partner_id, partner_name, vehicle_type, partner_rating ORDER BY total_deliveries DESC""",
    "vehicle_type_comparison": f"""SELECT vehicle_type,
        COUNT(*) FILTER (WHERE order_status='delivered') AS total_deliveries,
        AVG(delivery_time_minutes) FILTER (WHERE order_status='delivered') AS average_delivery_time,
        AVG(delivery_distance_km) FILTER (WHERE order_status='delivered') AS average_delivery_distance,
        100.0 * COUNT(*) FILTER (WHERE is_late AND order_status='delivered') / NULLIF(COUNT(*) FILTER (WHERE order_status='delivered'),0) AS late_delivery_percentage
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY vehicle_type ORDER BY total_deliveries DESC""",
    "city_vehicle_delivery": f"""SELECT city,vehicle_type,COUNT(*) AS delivered_orders,
        AVG(delivery_time_minutes) AS average_delivery_time,
        100.0*COUNT(*) FILTER (WHERE is_late)/NULLIF(COUNT(*),0) AS late_delivery_percentage
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} AND order_status='delivered'
        GROUP BY city,vehicle_type ORDER BY city,vehicle_type""",
    "daily_order_trends": f"""SELECT order_date, COUNT(*) AS total_orders,
        COUNT(*) FILTER (WHERE order_status='delivered') AS completed_orders, SUM(revenue) AS revenue
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY order_date ORDER BY order_date""",
    "daily_advanced_trends": f"""WITH daily AS (
        SELECT order_date,COUNT(*) AS total_orders,SUM(revenue) AS revenue
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY order_date),
        compared AS (SELECT *,LAG(revenue) OVER (ORDER BY order_date) AS previous_revenue FROM daily)
        SELECT order_date,total_orders,revenue,
        AVG(total_orders::numeric) OVER (ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS orders_7_day_avg,
        AVG(revenue) OVER (ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS revenue_7_day_avg,
        CASE WHEN previous_revenue>0 THEN 100.0*(revenue-previous_revenue)/previous_revenue END AS revenue_growth_pct
        FROM compared ORDER BY order_date""",
    "monthly_order_trends": f"""SELECT order_month, COUNT(*) AS total_orders, SUM(revenue) AS revenue
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY order_month ORDER BY order_month""",
    "monthly_advanced_trends": f"""WITH monthly AS (
        SELECT order_month,COUNT(*) AS total_orders,SUM(revenue) AS revenue
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY order_month),
        compared AS (SELECT *,LAG(revenue) OVER (ORDER BY order_month) AS previous_revenue FROM monthly)
        SELECT order_month,total_orders,revenue,
        AVG(total_orders::numeric) OVER (ORDER BY order_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS orders_3_month_avg,
        AVG(revenue) OVER (ORDER BY order_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS revenue_3_month_avg,
        CASE WHEN previous_revenue>0 THEN 100.0*(revenue-previous_revenue)/previous_revenue END AS revenue_growth_pct
        FROM compared ORDER BY order_month""",
    "peak_ordering_hours": f"""SELECT order_hour, COUNT(*) AS total_orders, SUM(revenue) AS revenue
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY order_hour ORDER BY total_orders DESC""",
    "weekday_weekend_performance": f"""SELECT CASE WHEN EXTRACT(ISODOW FROM order_timestamp) IN (6,7) THEN 'weekend' ELSE 'weekday' END AS period,
        COUNT(*) AS total_orders, SUM(revenue) AS revenue,
        COUNT(*) FILTER (WHERE order_status='delivered') AS completed_orders,
        AVG(delivery_time_minutes) FILTER (WHERE order_status='delivered') AS average_delivery_time
        FROM processed_orders WHERE {TS_FILTER} AND {order_filters()} GROUP BY period ORDER BY period""",
    "orders_by_payment_method": f"""SELECT payment_method, COUNT(*) AS total_orders, SUM(revenue) AS revenue,
        AVG(order_amount) FILTER (WHERE order_status='delivered') AS average_order_value
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY payment_method ORDER BY total_orders DESC""",
    "order_status_distribution": f"""SELECT order_status, COUNT(*) AS total_orders
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY order_status ORDER BY total_orders DESC""",
    "average_order_value_trends": f"""SELECT order_date,
        AVG(order_amount) FILTER (WHERE order_status='delivered') AS average_order_value
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY order_date ORDER BY order_date""",
    "orders_by_weekday_hour": f"""SELECT EXTRACT(ISODOW FROM order_timestamp)::INTEGER AS weekday,
        order_hour,COUNT(*) AS total_orders FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()}
        GROUP BY weekday,order_hour ORDER BY weekday,order_hour""",
    "delivery_time_distribution": f"""SELECT width_bucket(delivery_time_minutes,0,120,12) AS bucket,
        COUNT(*) AS deliveries, MIN(delivery_time_minutes) AS min_minutes, MAX(delivery_time_minutes) AS max_minutes
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} AND order_status='delivered'
        GROUP BY bucket ORDER BY bucket""",
    "delivery_distance_scatter": f"""SELECT order_id,city,delivery_distance_km,delivery_time_minutes,is_late
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} AND order_status='delivered'
        ORDER BY order_timestamp DESC LIMIT :limit""",
    "customer_kpis": f"""WITH customer_orders AS (
        SELECT customer_id,COUNT(*) AS orders,COUNT(*) FILTER (WHERE order_status='delivered') AS completed_orders,
        SUM(revenue) AS spending FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY customer_id)
        SELECT COUNT(*) AS unique_customers,COUNT(*) FILTER (WHERE orders>1) AS repeat_customers,
        AVG(orders) AS average_orders_per_customer FROM customer_orders""",
    "customer_spending": f"""SELECT customer_id,COUNT(*) AS total_orders,
        COUNT(*) FILTER (WHERE order_status='delivered') AS completed_orders,SUM(revenue) AS spending
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY customer_id ORDER BY spending DESC""",
    "customer_spending_distribution": f"""WITH spend AS (
        SELECT customer_id,SUM(revenue) AS spending FROM processed_orders
        WHERE {DATE_FILTER} AND {order_filters()} GROUP BY customer_id)
        SELECT width_bucket(spending,0,5000,20) AS spending_bucket,COUNT(*) AS customers
        FROM spend GROUP BY spending_bucket ORDER BY spending_bucket""",
    "customer_frequency": f"""WITH per_customer AS (SELECT customer_id,COUNT(*) AS total_orders
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()} GROUP BY customer_id)
        SELECT total_orders,COUNT(*) AS customers FROM per_customer GROUP BY total_orders ORDER BY total_orders""",
    "top_customers_by_spend": f"""SELECT customer_id,COUNT(*) AS total_orders,
        COUNT(*) FILTER (WHERE order_status='delivered') AS completed_orders,SUM(revenue) AS spending
        FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()}
        GROUP BY customer_id ORDER BY spending DESC LIMIT :limit""",
    "filtered_orders": f"""SELECT * FROM processed_orders WHERE {DATE_FILTER} AND {order_filters()}
        ORDER BY order_timestamp DESC LIMIT :limit""",
    "quick_order_search": f"""SELECT order_id, order_timestamp, customer_id, restaurant_name, city,
        order_status, payment_method, order_amount, delivery_time_minutes
        FROM processed_orders
        WHERE {DATE_FILTER} AND {order_filters()}
          AND (:search_term IS NULL OR order_id ILIKE ('%' || :search_term || '%')
            OR customer_id ILIKE ('%' || :search_term || '%')
            OR restaurant_name ILIKE ('%' || :search_term || '%')
            OR partner_name ILIKE ('%' || :search_term || '%')
            OR city ILIKE ('%' || :search_term || '%'))
        ORDER BY order_timestamp DESC LIMIT :limit""",
    "latest_etl_runs": """SELECT execution_id::text AS execution_id,execution_timestamp,execution_status,
        execution_duration_seconds,source_row_counts,valid_row_count,rejected_row_count,
        transformation_counts,rejection_reason_counts,database_load_status
        FROM etl_audit ORDER BY execution_timestamp DESC LIMIT :limit""",
    "latest_quality_run": """SELECT execution_id::text AS execution_id,execution_timestamp,execution_status,
        source_row_counts->>'orders' AS source_orders,valid_row_count,rejected_row_count,
        rejection_reason_counts,raw_sources_unchanged FROM etl_audit
        ORDER BY execution_timestamp DESC LIMIT 1""",
    "rejected_records": """SELECT source_row_number,original_record->>'order_id' AS order_id,
        original_record->>'customer_id' AS customer_id,original_record,rejection_reason,validation_category,processing_timestamp
        FROM rejected_records WHERE execution_id=CAST(:execution_id AS UUID)
        AND (:reason IS NULL OR rejection_reason ILIKE ('%' || :reason || '%'))
        ORDER BY source_row_number LIMIT :limit""",
}


def run_analytics(engine: Engine, query_name: str, *, start_date=None, end_date=None, limit: int = 10,
                  city=None, restaurant_id=None, cuisine=None, payment_method=None, order_status=None, search_term=None,
                  execution_id=None, reason=None) -> pd.DataFrame:
    """Run a named, parameterized analytics query and return only its result rows."""
    try:
        sql = ANALYTICS_QUERIES[query_name]
    except KeyError as exc:
        raise ValueError(f"Unknown analytics query: {query_name}") from exc
    params = {"start_date": start_date, "end_date": end_date, "limit": limit,
              "city": city, "restaurant_id": restaurant_id, "cuisine": cuisine,
              "payment_method": payment_method, "order_status": order_status, "search_term": search_term,
              "execution_id": execution_id, "reason": reason}
    with engine.connect() as conn:
        result = pd.read_sql_query(text(sql), conn, params=params)
    # PostgreSQL NUMERIC values can arrive as Decimal objects; convert numeric
    # result columns to native Pandas numbers so Plotly and CSV exports serialize cleanly.
    for column in result.select_dtypes(include="object").columns:
        converted = pd.to_numeric(result[column], errors="coerce")
        if result[column].notna().sum() == converted.notna().sum() and result[column].notna().any():
            result[column] = converted
    return result


def explain_analyze(engine: Engine, query_name: str, *, start_date=None, end_date=None, limit: int = 10,
                    city=None, restaurant_id=None, cuisine=None, payment_method=None, order_status=None):
    """Inspect execution plan for a predefined SELECT query using EXPLAIN ANALYZE."""
    if query_name not in ANALYTICS_QUERIES:
        raise ValueError(f"Unknown analytics query: {query_name}")
    sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + ANALYTICS_QUERIES[query_name]
    params = {"start_date": start_date, "end_date": end_date, "limit": limit,
              "city": city, "restaurant_id": restaurant_id, "cuisine": cuisine,
              "payment_method": payment_method, "order_status": order_status,
              "execution_id": None, "reason": None, "search_term": None}
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def load_filter_options(engine: Engine) -> dict:
    """Return real date bounds and selectable values from the fact and dimension tables."""
    sql = text("""SELECT MIN(order_date) AS min_date,MAX(order_date) AS max_date,
        (SELECT array_agg(city ORDER BY city) FROM (SELECT DISTINCT city FROM processed_orders) c) AS cities,
        (SELECT array_agg(restaurant_id || ' | ' || restaurant_name ORDER BY restaurant_name)
            FROM (SELECT DISTINCT restaurant_id,restaurant_name FROM restaurants) r) AS restaurants,
        (SELECT array_agg(cuisine ORDER BY cuisine) FROM (SELECT DISTINCT cuisine FROM restaurants) q) AS cuisines,
        (SELECT array_agg(payment_method ORDER BY payment_method) FROM (SELECT DISTINCT payment_method FROM processed_orders) p) AS payment_methods,
        (SELECT array_agg(order_status ORDER BY order_status) FROM (SELECT DISTINCT order_status FROM processed_orders) s) AS statuses
        FROM processed_orders""")
    with engine.connect() as conn:
        row = conn.execute(sql).mappings().one()
    return {key: (list(row[key]) if row[key] is not None and key not in ("min_date", "max_date") else row[key])
            for key in row.keys()}
