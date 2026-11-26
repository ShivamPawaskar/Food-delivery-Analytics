"""Small read-only API that serves parameterized PostgreSQL analytics to React."""
from __future__ import annotations

import math
from io import BytesIO
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
import numpy as np
from sqlalchemy import text

from database.connection import get_engine, test_connection
from database.queries import ANALYTICS_QUERIES, load_filter_options, run_analytics
from analytics.forecast import forecast_series

app = FastAPI(title="Food Delivery Analytics API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])
_engine = None
MAX_ANALYSIS_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ANALYSIS_ROWS = 100_000
MAX_ANALYSIS_COLUMNS = 100


def engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def json_value(value: Any):
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item"):
        value = value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


@app.get("/api/health")
def health():
    try:
        status = test_connection(engine())
        return {"status": "ok", "database": status["database"]}
    except Exception as exc:
        raise HTTPException(503, "PostgreSQL is unavailable. Check DATABASE_URL and database setup.") from exc


@app.post("/api/upload-analysis")
async def upload_analysis(file: UploadFile = File(...)):
    """Profile a temporary CSV upload; never retain it or load it into PostgreSQL."""
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(415, "Upload a CSV file to analyze.")
    raw = await file.read(MAX_ANALYSIS_UPLOAD_BYTES + 1)
    await file.close()
    if len(raw) > MAX_ANALYSIS_UPLOAD_BYTES:
        raise HTTPException(413, "CSV files must be 10 MB or smaller.")
    try:
        frame = pd.read_csv(BytesIO(raw), low_memory=False)
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
        raise HTTPException(422, "We could not read this CSV. Check its encoding and column formatting.") from exc
    if frame.empty or len(frame.columns) == 0:
        raise HTTPException(422, "The CSV has no analyzable rows or columns.")
    if len(frame) > MAX_ANALYSIS_ROWS:
        raise HTTPException(413, "CSV files are limited to 100,000 rows per analysis.")
    if len(frame.columns) > MAX_ANALYSIS_COLUMNS:
        raise HTTPException(413, "CSV files are limited to 100 columns per analysis.")

    profiles, chart_data = [], {}
    for col in frame.columns:
        name = str(col)
        series = frame[col]
        profile = {"column": name, "data_type": str(series.dtype), "missing": int(series.isna().sum()),
                   "missing_pct": round(float(series.isna().mean() * 100), 1),
                   "unique_values": int(series.nunique(dropna=True))}
        if pd.api.types.is_numeric_dtype(series):
            values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            profile["data_type"] = "numeric"
            if not values.empty:
                profile.update({"mean": round(float(values.mean()), 2), "median": round(float(values.median()), 2),
                                "min": round(float(values.min()), 2), "max": round(float(values.max()), 2)})
                bins = min(12, max(1, int(math.sqrt(len(values)))))
                counts, edges = np.histogram(values.to_numpy(), bins=bins)
                chart_data[name] = [{"label": f"{edges[i]:.2f} – {edges[i+1]:.2f}", "count": int(counts[i])}
                                    for i in range(len(counts))]
            else:
                chart_data[name] = []
        else:
            labels = series.dropna().astype(str).value_counts().head(12)
            chart_data[name] = [{"label": str(label), "count": int(count)} for label, count in labels.items()]
            profile["data_type"] = "text/category"
        profiles.append(profile)

    preview = json_value(frame.head(100).to_dict(orient="records"))
    return {"filename": Path(file.filename).name, "row_count": int(len(frame)), "column_count": int(len(frame.columns)),
            "duplicate_rows": int(frame.duplicated().sum()), "missing_cells": int(frame.isna().sum().sum()),
            "profile": profiles, "charts": chart_data, "preview": preview}


@app.get("/api/filters")
def filters():
    try:
        options = load_filter_options(engine())
        return {key: [v.isoformat() if hasattr(v, "isoformat") else v for v in value]
                if isinstance(value, list) else value.isoformat() if hasattr(value, "isoformat") else value
                for key, value in options.items()}
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Could not load filter options from PostgreSQL.") from exc


@app.get("/api/query/{query_name}")
def query(query_name: str, start_date: date | None = None, end_date: date | None = None,
          city: str | None = None, restaurant_id: str | None = None, cuisine: str | None = None,
          payment_method: str | None = None, order_status: str | None = None,
          search_term: str | None = None, execution_id: UUID | None = None, reason: str | None = None,
          limit: int = Query(default=500, ge=1, le=50_000)):
    if query_name not in ANALYTICS_QUERIES:
        raise HTTPException(404, "Unknown analytics query.")
    try:
        frame = run_analytics(engine(), query_name, start_date=start_date,
            end_date=end_date + timedelta(days=1) if end_date else None,
            city=city, restaurant_id=restaurant_id, cuisine=cuisine, payment_method=payment_method,
            order_status=order_status, search_term=search_term, execution_id=execution_id,
            reason=reason, limit=limit)
        return {"data": [{key: json_value(value) for key, value in row.items()}
                          for row in frame.to_dict(orient="records")], "count": len(frame)}
    except (SQLAlchemyError, ValueError) as exc:
        raise HTTPException(503, f"Analytics query failed ({type(exc).__name__}).") from exc


@app.get("/api/export/{query_name}")
def export(query_name: str, start_date: date | None = None, end_date: date | None = None,
           city: str | None = None, restaurant_id: str | None = None, cuisine: str | None = None,
           payment_method: str | None = None, order_status: str | None = None,
           execution_id: UUID | None = None, reason: str | None = None,
           limit: int = Query(default=50_000, ge=1, le=50_000)):
    if query_name not in ANALYTICS_QUERIES:
        raise HTTPException(404, "Unknown analytics query.")
    try:
        frame = run_analytics(engine(), query_name, start_date=start_date,
            end_date=end_date + timedelta(days=1) if end_date else None,
            city=city, restaurant_id=restaurant_id, cuisine=cuisine, payment_method=payment_method,
            order_status=order_status, execution_id=execution_id, reason=reason, limit=limit)
        return {"filename": f"{query_name}.csv", "csv": frame.to_csv(index=False)}
    except (SQLAlchemyError, ValueError) as exc:
        raise HTTPException(503, f"Report query failed ({type(exc).__name__}).") from exc


@app.get("/api/forecast")
def demand_forecast(horizon: int = Query(default=7), anchor_date: date | None = None,
                    city: str | None = None, restaurant_id: str | None = None,
                    cuisine: str | None = None, payment_method: str | None = None,
                    order_status: str | None = None):
    """Forecast daily filtered order demand from aggregated PostgreSQL history."""
    if horizon not in (7, 14):
        raise HTTPException(422, "Forecast horizon must be 7 or 14 days.")
    try:
        end = anchor_date or load_filter_options(engine()).get("max_date")
        if end is None:
            raise HTTPException(422, "There are no order dates available for forecasting.")
        first = end - timedelta(days=179)
        sql = text("""SELECT calendar.day::date AS order_date,
            COUNT(o.order_id) AS total_orders,COALESCE(SUM(o.revenue),0) AS revenue
            FROM generate_series(CAST(:first_day AS DATE),CAST(:last_day AS DATE),INTERVAL '1 day') AS calendar(day)
            LEFT JOIN processed_orders o ON o.order_date=calendar.day::date
                AND (:city IS NULL OR o.city=:city)
                AND (:restaurant_id IS NULL OR o.restaurant_id=:restaurant_id)
                AND (:cuisine IS NULL OR o.cuisine=:cuisine)
                AND (:payment_method IS NULL OR o.payment_method=:payment_method)
                AND (:order_status IS NULL OR o.order_status=:order_status)
            GROUP BY calendar.day ORDER BY calendar.day""")
        with engine().connect() as conn:
            frame = pd.read_sql_query(sql, conn, params={"first_day": first, "last_day": end,
                "city": city, "restaurant_id": restaurant_id, "cuisine": cuisine,
                "payment_method": payment_method, "order_status": order_status})
        result = forecast_series(frame.to_dict(orient="records"), horizon=horizon)
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, f"Forecast query failed ({type(exc).__name__}).") from exc


dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str):
        path = (dist / full_path).resolve()
        if path.is_relative_to(dist.resolve()) and path.is_file():
            return FileResponse(path)
        return FileResponse(dist / "index.html")
