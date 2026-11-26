import pandas as pd

from analytics.insights import build_insights
from dashboard.export_utils import csv_bytes, csv_zip_bytes
from dashboard.filtering import normalize_filters
from database.queries import ANALYTICS_QUERIES
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


def test_insights_only_report_rows_meeting_rules():
    kpis = {"late_delivery_percentage": 5.0, "cancellation_percentage": 10.0}
    restaurants = pd.DataFrame([
        {"restaurant_id": "R1", "restaurant_name": "Revenue Leader", "restaurant_rating": 4.5, "total_orders": 30,
         "completed_orders": 28, "revenue": 12000.0, "late_delivery_percentage": 22.0},
        {"restaurant_id": "R2", "restaurant_name": "Low Rated", "restaurant_rating": 3.2, "total_orders": 12,
         "completed_orders": 10, "revenue": 3000.0, "late_delivery_percentage": 0.0},
    ])
    cities = pd.DataFrame([
        {"city": "Pune", "total_orders": 100, "revenue": 50000, "average_delivery_time": 35, "cancellation_rate": 10.0},
        {"city": "Mumbai", "total_orders": 20, "revenue": 12000, "average_delivery_time": 40, "cancellation_rate": 18.0},
    ])
    cuisines = pd.DataFrame([{"cuisine": "Biryani", "total_orders": 50, "revenue": 30000},
                             {"cuisine": "Desserts", "total_orders": 15, "revenue": 9000}])
    partners = pd.DataFrame([{"partner_id": "P1", "partner_name": "Reliable", "total_deliveries": 12,
        "partner_rating": 4.8, "late_delivery_percentage": 2.0, "average_delivery_time": 24.0}])
    peak = pd.DataFrame([{"order_hour": 20, "total_orders": 33, "revenue": 17000}])
    results = build_insights(kpis, restaurants, cities, cuisines, partners, peak)
    assert any("highest order volume" in x["insight"] and "Pune" in x["insight"] for x in results)
    assert any(x["category"] == "Late delivery risk" and "Revenue Leader" in x["insight"] for x in results)
    assert any(x["category"] == "Cancellation risk" and "Mumbai" in x["insight"] for x in results)
    assert any(x["category"] == "Cuisine revenue" and "Biryani" in x["insight"] for x in results)
    assert any(x["category"] == "Restaurant rating" and "Low Rated" in x["insight"] for x in results)
    assert any(x["category"] == "Delivery performance" and "Reliable" in x["insight"] for x in results)
    assert any(x["category"] == "Peak ordering" and "20:00" in x["evidence"] for x in results)
    assert all(x["evidence"] and x["rule"] for x in results)


def test_dashboard_filter_normalization_and_validation():
    filters = normalize_filters(pd.Timestamp("2025-01-02").date(), pd.Timestamp("2025-01-04").date(),
        city="Pune", restaurant_label="R023 | Cafe", cuisine="Biryani", payment_method="UPI", order_status="delivered")
    assert filters["end_date"].isoformat() == "2025-01-05"
    assert filters["restaurant_id"] == "R023"
    assert filters["city"] == "Pune" and filters["order_status"] == "delivered"
    assert normalize_filters(None, None)["end_date"] is None
    try:
        normalize_filters(pd.Timestamp("2025-01-05").date(), pd.Timestamp("2025-01-04").date())
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid date range must be rejected")


def test_csv_and_bundle_exports_are_valid():
    frame = pd.DataFrame([{"city": "Pune", "orders": 4}])
    raw = csv_bytes(frame)
    assert raw.startswith(b"\xef\xbb\xbf") and b"Pune" in raw
    import io, zipfile
    with zipfile.ZipFile(io.BytesIO(csv_zip_bytes({"city_report": frame}))) as archive:
        assert archive.namelist() == ["city_report.csv"]
        assert b"orders" in archive.read("city_report.csv")


def test_plotly_components_render_real_query_frames():
    import pytest
    pytest.importorskip("plotly")
    from dashboard.components.charts import bar_chart, line_chart, donut_chart
    frame = pd.DataFrame([{"day": "2025-01-01", "orders": 4, "city": "Pune"}, {"day": "2025-01-02", "orders": 7, "city": "Mumbai"}])
    assert len(line_chart(frame, "day", "orders", "Orders").data) == 1
    assert len(bar_chart(frame, "city", "orders", "Orders").data) == 1
    assert len(donut_chart(frame, "city", "orders", "Orders").data) == 1


def test_pdf_export_returns_pdf_when_optional_dependency_is_installed():
    import pytest
    pytest.importorskip("reportlab")
    from analytics.reports import build_pdf_report
    pdf = build_pdf_report({"overall_business_performance": pd.DataFrame([{"orders": 3, "revenue": 125.0}])})
    assert pdf.startswith(b"%PDF-")


def test_analytics_sql_compiles_for_postgresql():
    assert "daily_advanced_trends" in ANALYTICS_QUERIES
    assert "monthly_advanced_trends" in ANALYTICS_QUERIES
    for sql in ANALYTICS_QUERIES.values():
        text(sql).compile(dialect=postgresql.dialect())
