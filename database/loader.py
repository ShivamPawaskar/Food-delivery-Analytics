"""Transactional, bulk PostgreSQL loader for Set 2 outputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from uuid import UUID
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import MetaData, Table, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from config.settings import DATA_PROCESSED_DIR, DATA_RAW_DIR, DATA_REPORTS_DIR
from database.connection import get_engine
from database.setup import initialize_schema

AGGREGATE_TABLES = ("daily_performance", "restaurant_performance", "city_performance", "cuisine_performance", "delivery_partner_performance")
KEY_COLUMNS = {
    "restaurants": "restaurant_id", "delivery_partners": "partner_id", "processed_orders": "order_id",
    "daily_performance": "order_date", "restaurant_performance": "restaurant_id", "city_performance": "city",
    "cuisine_performance": "cuisine", "delivery_partner_performance": "partner_id",
}


def _value(value: Any):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (float, np.floating)) and np.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _records(frame: pd.DataFrame) -> list[dict]:
    return [{key: _value(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def _upsert(conn, table: Table, rows: list[dict], key: str, chunk_size: int = 1000) -> int:
    if not rows:
        return 0
    statement = pg_insert(table)
    update_columns = [column.name for column in table.columns if column.name != key and not column.primary_key]
    statement = statement.on_conflict_do_update(
        index_elements=[table.c[key]],
        set_={name: getattr(statement.excluded, name) for name in update_columns},
    )
    for start in range(0, len(rows), chunk_size):
        conn.execute(statement, rows[start:start + chunk_size])
    return len(rows)


def _sync_snapshot(conn, table: Table, key: str, rows: list[dict]) -> None:
    """Remove stale keys after the idempotent upsert, keeping table counts aligned with this snapshot."""
    keys = [row[key] for row in rows]
    statement = delete(table)
    if keys:
        statement = statement.where(table.c[key].not_in(keys))
    conn.execute(statement)


def _audit_row(audit: dict) -> dict:
    return {"execution_id": UUID(str(audit["execution_id"])),
            "execution_timestamp": pd.to_datetime(audit["execution_timestamp"], utc=True).to_pydatetime(),
            "execution_status": audit.get("execution_status", "success"),
            "execution_duration_seconds": audit.get("execution_duration_seconds"),
            "source_row_counts": audit.get("source_row_counts", {}),
            "valid_row_count": audit.get("valid_row_count", 0), "rejected_row_count": audit.get("rejected_row_count", 0),
            "transformation_counts": audit.get("transformation_counts", {}),
            "rejection_reason_counts": audit.get("rejection_reason_counts", {}),
            "raw_sources_unchanged": audit.get("raw_sources_unchanged"),
            "database_load_status": audit.get("database_load_status", "success"),
            "database_loaded_row_counts": audit.get("database_loaded_row_counts", {}),
            "error": audit.get("error")}


def _rejected_rows(frame: pd.DataFrame, execution_id: str) -> list[dict]:
    result = []
    for row in frame.to_dict(orient="records"):
        original = {key.removeprefix("original_"): _value(value)
                    for key, value in row.items() if key.startswith("original_")}
        canonical = json.dumps(original, sort_keys=True, default=str, ensure_ascii=False)
        source_row_number = int(row["source_row_number"])
        result.append({"execution_id": UUID(str(execution_id)), "source_row_number": source_row_number,
                       "source_record_hash": hashlib.sha256(f"{source_row_number}:{canonical}".encode("utf-8")).hexdigest(),
                       "original_record": json.loads(canonical),
                       "rejection_reason": str(row["rejection_reason"]),
                       "validation_category": str(row["validation_category"]),
                       "processing_timestamp": _value(pd.to_datetime(row["processing_timestamp"], utc=True))})
    return result


def load_frames(frames: dict[str, pd.DataFrame], *, rejected: pd.DataFrame | None = None,
                aggregations: dict[str, pd.DataFrame] | None = None, audit: dict | None = None,
                engine: Engine | None = None, create_schema: bool = False) -> dict:
    """Bulk upsert a validated pipeline run in one transaction.

    Rejected rows go only to rejected_records. `processed_orders` receives only validated rows.
    """
    required = ("restaurants", "delivery_partners", "orders")
    missing = [name for name in required if name not in frames]
    if missing:
        raise ValueError(f"Missing frames required for database loading: {missing}")
    if audit is None:
        raise ValueError("An ETL audit object is required for traceable database loading")
    if rejected is None:
        rejected = pd.DataFrame()
    if aggregations is None:
        raise ValueError("All five aggregate datasets are required for database loading")
    source_orders = int(audit.get("source_row_counts", {}).get("orders", len(frames["orders"]) + len(rejected)))
    if len(frames["orders"]) + len(rejected) != source_orders:
        raise ValueError("Unique processed plus rejected records do not match the raw source order count")
    audit["database_load_status"] = "success"
    audit["database_loaded_row_counts"] = {
        "restaurants": len(frames["restaurants"]), "delivery_partners": len(frames["delivery_partners"]),
        "processed_orders": len(frames["orders"]), "rejected_records": len(rejected),
        **{name: len(aggregations[name]) for name in AGGREGATE_TABLES},
    }
    owned = engine is None
    engine = engine or get_engine()
    loaded: dict[str, int] = {}
    pipeline_started = audit.get("_started_perf_counter")
    try:
        if create_schema:
            initialize_schema(engine)
        metadata = MetaData()
        table_names = ["restaurants", "delivery_partners", "processed_orders", *AGGREGATE_TABLES, "etl_audit", "rejected_records"]
        tables = {name: Table(name, metadata, autoload_with=engine) for name in table_names}
        with engine.begin() as conn:
            # Parent dimensions must exist before their fact rows (foreign keys are enforced).
            loaded["restaurants"] = _upsert(conn, tables["restaurants"], _records(frames["restaurants"]), "restaurant_id")
            loaded["delivery_partners"] = _upsert(conn, tables["delivery_partners"], _records(frames["delivery_partners"]), "partner_id")
            loaded["etl_audit"] = _upsert(conn, tables["etl_audit"], [_audit_row(audit)], "execution_id")
            loaded["processed_orders"] = _upsert(conn, tables["processed_orders"], _records(frames["orders"]), "order_id")
            for name in AGGREGATE_TABLES:
                frame = (aggregations or {}).get(name)
                if frame is None:
                    raise ValueError(f"Missing required aggregate frame: {name}")
                loaded[name] = _upsert(conn, tables[name], _records(frame), KEY_COLUMNS[name])
            rejected_rows = _rejected_rows(rejected if rejected is not None else pd.DataFrame(), audit["execution_id"])
            if rejected_rows:
                statement = pg_insert(tables["rejected_records"]).on_conflict_do_nothing(
                    index_elements=[tables["rejected_records"].c.execution_id, tables["rejected_records"].c.source_record_hash])
                for start in range(0, len(rejected_rows), 1000):
                    conn.execute(statement, rejected_rows[start:start + 1000])
            loaded["rejected_records"] = len(rejected_rows)
            # The facts and aggregates are snapshots of the current ETL run. Upsert
            # first (so repeated runs update in place), then remove no-longer-present keys.
            for name in AGGREGATE_TABLES:
                _sync_snapshot(conn, tables[name], KEY_COLUMNS[name], _records((aggregations or {})[name]))
            _sync_snapshot(conn, tables["processed_orders"], "order_id", _records(frames["orders"]))
            _sync_snapshot(conn, tables["restaurants"], "restaurant_id", _records(frames["restaurants"]))
            _sync_snapshot(conn, tables["delivery_partners"], "partner_id", _records(frames["delivery_partners"]))
            if pipeline_started is not None:
                duration = round(time.perf_counter() - pipeline_started, 4)
                audit["execution_duration_seconds"] = duration
                conn.execute(update(tables["etl_audit"]).where(
                    tables["etl_audit"].c.execution_id == audit["execution_id"]).values(execution_duration_seconds=duration))
        return {"loaded_rows": loaded, "execution_id": audit["execution_id"]}
    except Exception as exc:
        # engine.begin() rolls back all inserts/upserts on any failure.
        audit["database_load_status"] = "failed"
        audit["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if owned:
            engine.dispose()


def load_processed_outputs(engine: Engine | None = None, *, create_schema: bool = False) -> dict:
    """Load the CSVs and latest ETL audit produced by `python -m etl.pipeline`."""
    processed_path = DATA_PROCESSED_DIR / "processed_orders.csv"
    rejected_path = DATA_PROCESSED_DIR / "rejected_records.csv"
    quality_path = DATA_REPORTS_DIR / "data_quality_report.json"
    history_path = DATA_REPORTS_DIR / "etl_audit.json"
    for path in (processed_path, rejected_path, quality_path, history_path):
        if not path.is_file():
            raise FileNotFoundError(f"Run the ETL pipeline before loading PostgreSQL: missing {path}")
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    history = json.loads(history_path.read_text(encoding="utf-8"))
    audit = next((item for item in reversed(history if isinstance(history, list) else [history])
                 if item.get("execution_id") == quality["execution_id"]), None)
    if audit is None:
        raise ValueError("The latest ETL audit does not match the data quality report")
    orders = pd.read_csv(processed_path, parse_dates=["order_timestamp", "accepted_timestamp", "pickup_timestamp", "delivered_timestamp"])
    orders["order_date"] = pd.to_datetime(orders.order_date, errors="raise").dt.date
    rejected = pd.read_csv(rejected_path, keep_default_na=False)
    restaurants = pd.read_csv(DATA_PROCESSED_DIR / "restaurants.csv")
    partners = pd.read_csv(DATA_PROCESSED_DIR / "delivery_partners.csv")
    aggregations = {name: pd.read_csv(DATA_PROCESSED_DIR / f"{name}.csv") for name in AGGREGATE_TABLES}
    if not (len(orders) + len(rejected) == quality["source_rows"]):
        raise ValueError("Processed plus rejected rows do not equal the ETL source order count")
    return load_frames({"orders": orders, "restaurants": restaurants, "delivery_partners": partners},
                       rejected=rejected, aggregations=aggregations, audit=audit,
                       engine=engine, create_schema=create_schema)


def check_data_consistency(engine: Engine | None = None) -> dict:
    """Compare raw/processed/rejected CSV counts to current PostgreSQL table counts."""
    owned = engine is None
    engine = engine or get_engine()
    try:
        raw_count = len(pd.read_csv(DATA_RAW_DIR / "orders.csv", usecols=["order_id"]))
        processed_count = len(pd.read_csv(DATA_PROCESSED_DIR / "processed_orders.csv", usecols=["order_id"]))
        rejected_count = len(pd.read_csv(DATA_PROCESSED_DIR / "rejected_records.csv", usecols=["rejection_reason"]))
        counts = {}
        with engine.connect() as conn:
            for table in ("restaurants", "delivery_partners", "processed_orders", *AGGREGATE_TABLES):
                reflected = Table(table, MetaData(), autoload_with=conn)
                counts[table] = int(conn.execute(select(func.count()).select_from(reflected)).scalar_one())
            report = json.loads((DATA_REPORTS_DIR / "data_quality_report.json").read_text(encoding="utf-8"))
            execution_id = UUID(str(report["execution_id"]))
            audit_table = Table("etl_audit", MetaData(), autoload_with=conn)
            counts["etl_audit"] = int(conn.execute(select(func.count()).select_from(audit_table).where(
                audit_table.c.execution_id == execution_id)).scalar_one())
            rejected_table = Table("rejected_records", MetaData(), autoload_with=conn)
            counts["rejected_records"] = int(conn.execute(select(func.count()).select_from(rejected_table).where(
                rejected_table.c.execution_id == execution_id)).scalar_one())
        expected_counts = {"restaurants": len(pd.read_csv(DATA_PROCESSED_DIR / "restaurants.csv")),
            "delivery_partners": len(pd.read_csv(DATA_PROCESSED_DIR / "delivery_partners.csv")),
            "processed_orders": processed_count, "rejected_records": rejected_count,
            **{name: len(pd.read_csv(DATA_PROCESSED_DIR / f"{name}.csv")) for name in AGGREGATE_TABLES},
            "etl_audit": 1}
        comparisons = {name: counts.get(name) == expected for name, expected in expected_counts.items()}
        comparisons["rejected_records"] = counts["rejected_records"] == expected_counts["rejected_records"]
        return {"source_csv_orders": raw_count, "processed_csv_orders": processed_count,
                "rejected_csv_records": rejected_count, "reconciled": raw_count == processed_count + rejected_count,
                "expected_postgres_table_counts": expected_counts, "postgres_table_counts": counts,
                "table_count_comparison": comparisons,
                "postgres_counts_match_current_csv": all(comparisons.values())}
    finally:
        if owned:
            engine.dispose()
