"""Data-backed CSV bundle and compact PDF report generation."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json

import pandas as pd

from analytics.insights import build_insights
from database.queries import run_analytics


def build_report_data(engine, filters=None) -> dict[str, pd.DataFrame]:
    filters = filters or {}
    queries = {
        "overall_business_performance": ("overall_kpis", {}),
        "daily_order_analytics": ("daily_advanced_trends", {}),
        "monthly_order_analytics": ("monthly_advanced_trends", {}),
        "restaurant_analytics": ("restaurant_ratings", {"limit": 500}),
        "restaurant_revenue_ranking": ("top_restaurants_by_revenue", {"limit": 500}),
        "delivery_analytics": ("delivery_partner_analytics", {"limit": 500}),
        "vehicle_analytics": ("vehicle_type_comparison", {}),
        "city_analytics": ("city_analytics", {}),
        "cuisine_analytics": ("cuisine_analytics", {}),
        "payment_analytics": ("orders_by_payment_method", {}),
        "order_status_analytics": ("order_status_distribution", {}),
        "average_order_value_trends": ("average_order_value_trends", {}),
        "peak_order_times": ("peak_ordering_hours", {}),
        "customer_analytics": ("customer_kpis", {}),
        "data_quality": ("latest_quality_run", {}),
        "etl_execution_history": ("latest_etl_runs", {"limit": 100}),
    }
    reports = {name: run_analytics(engine, query, **filters, **options) for name, (query, options) in queries.items()}
    reports["business_insights"] = pd.DataFrame(build_insights(
        reports["overall_business_performance"].iloc[0].to_dict(), reports["restaurant_analytics"],
        reports["city_analytics"], reports["cuisine_analytics"], reports["delivery_analytics"],
        reports["peak_order_times"]), columns=["category", "insight", "evidence", "rule"])
    return reports


def build_csv_bundle(reports: dict[str, pd.DataFrame]) -> bytes:
    """Create a zip of complete CSV reports (all source rows returned by SQL)."""
    from dashboard.export_utils import csv_zip_bytes
    return csv_zip_bytes(reports)


def build_pdf_report(reports: dict[str, pd.DataFrame], filters=None) -> bytes:
    """Build a jury-friendly PDF summary; complete tables remain available in CSVs."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    def pdf_text(value):
        return str(value).replace("₹", "INR ").replace("—", "-").replace("·", "-").encode("ascii", "replace").decode("ascii")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=14*mm, leftMargin=14*mm,
        topMargin=13*mm, bottomMargin=13*mm, title="Food Delivery Analytics Report", author="Food Delivery Analytics")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], textColor=colors.HexColor("#0F766E"), spaceBefore=8))
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=7, leading=8, alignment=TA_LEFT))
    story = [Paragraph("Food Delivery Analytics - Business Report", styles["Title"]),
        Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]),
        Paragraph("All figures below are queried from the configured PostgreSQL database. Full result sets are included in the CSV bundle.", styles["Normal"]), Spacer(1, 5*mm)]
    if filters:
        safe_filters = {key: str(value) for key, value in filters.items() if value is not None}
        story.append(Paragraph("Filters: " + escape(pdf_text(json.dumps(safe_filters, default=str))), styles["Normal"]))
    for index, (name, frame) in enumerate(reports.items()):
        story.append(Paragraph(escape(pdf_text(name.replace("_", " ").title())), styles["SectionHeading"]))
        if frame.empty:
            story.append(Paragraph("No matching database rows.", styles["Normal"]))
            continue
        view = frame.head(12).copy()
        headers = [Paragraph(escape(pdf_text(col)), styles["SmallCell"]) for col in view.columns]
        rows = [headers]
        for values in view.itertuples(index=False, name=None):
            rows.append([Paragraph(escape(pdf_text(value)[:110]), styles["SmallCell"]) for value in values])
        widths = [doc.width / max(1, len(headers))] * len(headers)
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#15334A")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#CFD8DE")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F3F7F8")]),
            ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
        story.append(table)
        if index < len(reports) - 1:
            story.append(Spacer(1, 3*mm))
    doc.build(story)
    return buffer.getvalue()
