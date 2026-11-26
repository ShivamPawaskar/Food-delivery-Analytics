"""Optional PostgreSQL integration tests; TEST_DATABASE_URL must be a dedicated *_test DB."""
import os
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from database.connection import test_connection
from database.loader import check_data_consistency, load_frames, load_processed_outputs
from database.queries import explain_analyze, run_analytics
from database.setup import create_database, initialize_schema
from config.settings import DATA_PROCESSED_DIR
from analytics.insights import generate_insights
from analytics.reports import build_csv_bundle, build_pdf_report, build_report_data

TEST_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Set TEST_DATABASE_URL to a dedicated PostgreSQL *_test database")


@pytest.fixture
def pg_engine():
    test_database_name = make_url(TEST_URL).database
    if not test_database_name.endswith("_test"):
        pytest.fail("Refusing PostgreSQL integration tests unless TEST_DATABASE_URL database name ends in _test")
    create_database(TEST_URL, database_name=test_database_name)
    engine = create_engine(TEST_URL, pool_pre_ping=True)
    initialize_schema(engine)
    yield engine
    engine.dispose()


def _payload(suffix):
    restaurant_id, partner_id, order_id = f"T_R_{suffix}", f"T_P_{suffix}", f"T_O_{suffix}"
    timestamp = pd.Timestamp("2026-01-03 12:00:00")
    restaurants = pd.DataFrame([{"restaurant_id": restaurant_id, "restaurant_name": "Integration Kitchen",
        "cuisine": "Test Cuisine", "city": "Pune", "restaurant_rating": 4.5, "average_prep_minutes": 20}])
    partners = pd.DataFrame([{"partner_id": partner_id, "partner_name": "Integration Partner",
        "vehicle_type": "Bike", "partner_rating": 4.6, "partner_city": "Pune"}])
    orders = pd.DataFrame([{"order_id": order_id, "customer_id": "C999999", "restaurant_id": restaurant_id,
        "partner_id": partner_id, "order_timestamp": timestamp, "accepted_timestamp": timestamp + pd.Timedelta(minutes=2),
        "pickup_timestamp": timestamp + pd.Timedelta(minutes=12), "delivered_timestamp": timestamp + pd.Timedelta(minutes=32),
        "order_amount": 500.0, "delivery_fee": 25.0, "payment_method": "UPI", "order_status": "delivered",
        "promised_delivery_minutes": 40, "delivery_distance_km": 4.0, "city": "Pune", "prep_time_minutes": 10.0,
        "delivery_time_minutes": 20.0, "total_fulfilment_minutes": 32.0, "order_date": timestamp.date(),
        "order_month": "2026-01", "order_hour": 12, "is_late": False, "restaurant_name": "Integration Kitchen",
        "cuisine": "Test Cuisine", "restaurant_rating": 4.5, "restaurant_city": "Pune",
        "partner_name": "Integration Partner", "vehicle_type": "Bike", "partner_rating": 4.6,
        "partner_city": "Pune", "revenue": 500.0}])
    aggregates = {
        "daily_performance": pd.DataFrame([{"order_date": timestamp.date(), "total_orders": 1, "completed_orders": 1,
            "cancelled_orders": 0, "revenue": 500.0, "average_order_value": 500.0, "average_delivery_time": 20.0, "late_deliveries": 0}]),
        "restaurant_performance": pd.DataFrame([{"restaurant_id": restaurant_id, "restaurant_name": "Integration Kitchen",
            "total_orders": 1, "revenue": 500.0, "average_order_value": 500.0, "average_preparation_time": 10.0,
            "average_delivery_time": 20.0, "late_delivery_percentage": 0.0}]),
        "city_performance": pd.DataFrame([{"city": "Pune", "total_orders": 1, "revenue": 500.0,
            "average_delivery_time": 20.0, "cancellation_rate": 0.0}]),
        "cuisine_performance": pd.DataFrame([{"cuisine": "Test Cuisine", "total_orders": 1,
            "revenue": 500.0, "average_order_value": 500.0}]),
        "delivery_partner_performance": pd.DataFrame([{"partner_id": partner_id, "partner_name": "Integration Partner",
            "total_deliveries": 1, "average_delivery_time": 20.0, "partner_rating": 4.6,
            "late_delivery_percentage": 0.0}]),
    }
    rejected = pd.DataFrame([{"source_row_number": 3, "original_order_id": f"BAD_{suffix}",
        "original_customer_id": "", "rejection_reason": "missing_customer_id|invalid_customer_id",
        "validation_category": "required_field|identifier", "processing_timestamp": pd.Timestamp.now(tz="UTC").isoformat()}])
    audit = {"execution_id": str(uuid4()), "execution_timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
        "execution_status": "success", "execution_duration_seconds": .1,
        "source_row_counts": {"orders": 2}, "valid_row_count": 1, "rejected_row_count": 1,
        "transformation_counts": {}, "rejection_reason_counts": {}, "raw_sources_unchanged": True}
    return {"restaurants": restaurants, "delivery_partners": partners, "orders": orders}, aggregates, audit, order_id, rejected


def test_connection_schema_bulk_upsert_and_analytics(pg_engine):
    assert test_connection(pg_engine)["database"].endswith("_test")
    frames, aggregates, audit, order_id, rejected = _payload(uuid4().hex[:10])
    first = load_frames(frames, rejected=rejected, aggregations=aggregates, audit=audit, engine=pg_engine)
    second = load_frames(frames, rejected=rejected, aggregations=aggregates, audit=audit, engine=pg_engine)
    assert first["loaded_rows"]["processed_orders"] == second["loaded_rows"]["processed_orders"] == 1
    with pg_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM processed_orders WHERE order_id=:id"), {"id": order_id}).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM rejected_records WHERE execution_id=:id"), {"id": audit["execution_id"]}).scalar_one() == 1
    rejected_query = run_analytics(pg_engine, "rejected_records", execution_id=audit["execution_id"], reason="missing_customer_id")
    assert len(rejected_query) == 1
    assert not run_analytics(pg_engine, "latest_etl_runs", limit=5).empty
    kpis = run_analytics(pg_engine, "overall_kpis", start_date="2026-01-01", end_date="2026-02-01")
    assert int(kpis.iloc[0].completed_orders) >= 1
    for query_name in ("top_restaurants_by_revenue", "top_restaurants_by_orders", "restaurant_ratings",
        "city_analytics", "cuisine_analytics", "delivery_partner_analytics", "vehicle_type_comparison",
        "daily_order_trends", "daily_advanced_trends", "monthly_order_trends", "monthly_advanced_trends", "peak_ordering_hours", "weekday_weekend_performance",
        "orders_by_payment_method", "order_status_distribution", "average_order_value_trends",
        "orders_by_weekday_hour", "delivery_time_distribution", "delivery_distance_scatter",
        "customer_kpis", "customer_spending", "customer_frequency", "top_customers_by_spend", "filtered_orders"):
        assert isinstance(run_analytics(pg_engine, query_name, start_date="2026-01-01", end_date="2026-02-01"), pd.DataFrame)
    filtered = run_analytics(pg_engine, "overall_kpis", start_date="2026-01-01", end_date="2026-02-01",
        city="Pune", restaurant_id=frames["orders"].iloc[0].restaurant_id, cuisine="Test Cuisine",
        payment_method="UPI", order_status="delivered")
    assert int(filtered.iloc[0].total_orders) == 1
    assert run_analytics(pg_engine, "overall_kpis").iloc[0].total_orders >= 1
    assert explain_analyze(pg_engine, "city_analytics", start_date="2026-01-01", end_date="2026-02-01")


def test_foreign_key_failure_rolls_back_transaction(pg_engine):
    frames, aggregates, audit, _, rejected = _payload(uuid4().hex[:10])
    frames["orders"].loc[0, "restaurant_id"] = "MISSING_RESTAURANT"
    with pytest.raises(IntegrityError):
        load_frames(frames, rejected=rejected, aggregations=aggregates, audit=audit, engine=pg_engine)
    with pg_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM restaurants WHERE restaurant_id=:id"),
                            {"id": frames["restaurants"].iloc[0].restaurant_id}).scalar_one() == 0


def test_load_set2_outputs_and_reconcile_table_counts(pg_engine):
    load = load_processed_outputs(pg_engine)
    assert load["loaded_rows"]["processed_orders"] == len(pd.read_csv(DATA_PROCESSED_DIR / "processed_orders.csv"))
    assert load["loaded_rows"]["rejected_records"] == len(pd.read_csv(DATA_PROCESSED_DIR / "rejected_records.csv"))
    check = check_data_consistency(pg_engine)
    assert check["reconciled"]
    assert check["postgres_counts_match_current_csv"]
    reports = build_report_data(pg_engine)
    assert "business_insights" in reports and "daily_order_analytics" in reports
    assert build_csv_bundle(reports).startswith(b"PK")
    assert build_pdf_report(reports).startswith(b"%PDF-")
    assert all("evidence" in insight and "rule" in insight for insight in generate_insights(pg_engine))
