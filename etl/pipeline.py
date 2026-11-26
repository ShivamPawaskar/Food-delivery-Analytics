"""End-to-end, auditable CSV ETL pipeline. Raw source files are read-only."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import time
import uuid

import pandas as pd

from config.settings import DATA_RAW_DIR, DATA_REPORTS_DIR
from etl.extract import extract
from etl.load import write_outputs
from etl.transform import build_aggregations, transform_orders
from utils.logging_config import configure_logging


def _sha256_sources() -> dict[str, str]:
    hashes = {}
    for filename in ("orders.csv", "restaurants.csv", "delivery_partners.csv"):
        path = DATA_RAW_DIR / filename
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _quality_report(run_id: str, processed: pd.DataFrame, rejected: pd.DataFrame,
                    source_count: int, transformation_counts: dict, reason_counts: dict) -> dict:
    reasons_by_record = rejected.rejection_reason.fillna("").map(lambda x: [r for r in x.split("|") if r])
    delivered = processed[processed.order_status.eq("delivered")]
    prep_expected = (processed.pickup_timestamp - processed.accepted_timestamp).dt.total_seconds() / 60
    delivery_expected = (delivered.delivered_timestamp - delivered.pickup_timestamp).dt.total_seconds() / 60
    calculated_fulfilment = (delivered.delivered_timestamp - delivered.order_timestamp).dt.total_seconds() / 60
    foreign_keys_valid = bool(processed.restaurant_name.notna().all() and processed.partner_name.notna().all())
    return {
        "execution_id": run_id, "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_rows": source_count, "valid_rows": int(len(processed)), "rejected_rows": int(len(rejected)),
        "row_reconciliation_passed": source_count == len(processed) + len(rejected),
        "processed_order_ids_unique": bool(processed.order_id.is_unique), "foreign_keys_valid": foreign_keys_valid,
        "calculated_columns_correct": {
            "prep_time_minutes": bool(processed.prep_time_minutes.reset_index(drop=True).equals(prep_expected.reset_index(drop=True))),
            "delivery_time_minutes": bool(delivered.delivery_time_minutes.reset_index(drop=True).equals(delivery_expected.reset_index(drop=True))),
            "total_fulfilment_minutes": bool(calculated_fulfilment.reset_index(drop=True).round(8).equals(
                delivered.total_fulfilment_minutes.reset_index(drop=True).round(8))),
            "order_date": bool(processed.order_date.reset_index(drop=True).equals(processed.order_timestamp.dt.date.astype(str).reset_index(drop=True))),
            "order_month": bool(processed.order_month.reset_index(drop=True).equals(processed.order_timestamp.dt.to_period("M").astype(str).reset_index(drop=True))),
            "order_hour": bool(processed.order_hour.reset_index(drop=True).equals(processed.order_timestamp.dt.hour.reset_index(drop=True))),
            "is_late": bool((delivered.is_late.reset_index(drop=True) == delivered.total_fulfilment_minutes.gt(delivered.promised_delivery_minutes).reset_index(drop=True)).all()),
        },
        "calculated_fulfilment_minutes_correct": bool((calculated_fulfilment.reset_index(drop=True).round(8).equals(
            delivered.total_fulfilment_minutes.reset_index(drop=True).round(8)))),
        "rejected_records_with_reason": int(sum(bool(rs) for rs in reasons_by_record)),
        "rejection_reason_counts": reason_counts,
        "transformation_counts": transformation_counts,
        "business_formulas": {
            "prep_time_minutes": "pickup_timestamp - accepted_timestamp, in minutes",
            "delivery_time_minutes": "delivered_timestamp - pickup_timestamp, in minutes; null when not delivered",
            "total_fulfilment_minutes": "delivered_timestamp - order_timestamp, in minutes; null when not delivered",
            "is_late": "delivered order and total_fulfilment_minutes > promised_delivery_minutes",
            "revenue": "order_amount for delivered orders; zero otherwise",
            "average_order_value": "mean order_amount among delivered orders",
            "cancellation_rate_and_late_delivery_percentage": "percentage of group orders cancelled / delivered orders late",
        },
    }


def run(load_to_database: bool = False, engine=None) -> dict:
    """Extract -> validate/transform -> aggregate -> write CSVs/reports; DB load optional."""
    logger = configure_logging()
    started = time.perf_counter()
    run_id = str(uuid.uuid4())
    execution_timestamp = datetime.now(timezone.utc).isoformat()
    raw_hashes_before = _sha256_sources()
    logger.info("ETL %s started", run_id)
    status = "failed"
    audit = {"execution_id": run_id, "execution_timestamp": execution_timestamp}
    try:
        frames = extract()
        source_counts = {name: int(len(frame)) for name, frame in frames.items()}
        processed, rejected, stats = transform_orders(frames["orders"], frames["restaurants"], frames["delivery_partners"], execution_timestamp)
        if stats["source_rows"] != stats["valid_rows"] + stats["rejected_rows"]:
            raise AssertionError("Accepted and rejected order counts do not reconcile")
        aggregations = build_aggregations(processed)
        quality = _quality_report(run_id, processed, rejected, stats["source_rows"], stats["transformation_counts"], stats["rejection_reason_counts"])
        status = "success"
        audit.update({"source_row_counts": source_counts, "valid_row_count": stats["valid_rows"],
                      "rejected_row_count": stats["rejected_rows"], "transformation_counts": stats["transformation_counts"],
                      "rejection_reason_counts": stats["rejection_reason_counts"], "execution_status": status})
        quality["execution_duration_seconds"] = round(time.perf_counter() - started, 4)
        if not all(quality["calculated_columns_correct"].values()):
            raise AssertionError("One or more calculated columns did not match their business formula")
        audit["execution_duration_seconds"] = quality["execution_duration_seconds"]
        audit["raw_source_sha256_before"] = raw_hashes_before
        audit["raw_sources_unchanged"] = raw_hashes_before == _sha256_sources()
        if not audit["raw_sources_unchanged"]:
            raise AssertionError("Raw source data changed during the ETL run")
        if load_to_database:
            from etl.load import load_to_postgres
            audit["_started_perf_counter"] = started
            load_result = load_to_postgres(processed, rejected, aggregations, frames["restaurants"],
                                           frames["delivery_partners"], audit, engine=engine)
            audit.pop("_started_perf_counter", None)
            quality["database_load_status"] = "success"
            quality["database_loaded_row_counts"] = load_result["loaded_rows"]
        else:
            audit["database_load_status"] = "not_requested"
            audit["database_loaded_row_counts"] = {}
            quality["database_load_status"] = "not_requested"
        audit["execution_duration_seconds"] = round(time.perf_counter() - started, 4)
        quality["execution_duration_seconds"] = audit["execution_duration_seconds"]
        write_outputs(processed, rejected, aggregations, quality, audit)
        logger.info("ETL %s succeeded: %s valid, %s rejected", run_id, len(processed), len(rejected))
        return {"processed": processed, "rejected": rejected, "aggregations": aggregations, "quality_report": quality, "audit": audit}
    except Exception as exc:
        audit.pop("_started_perf_counter", None)
        audit.update({"execution_status": "failed", "database_load_status": "failed" if load_to_database else "not_requested",
                      "error": f"{type(exc).__name__}: {exc}",
                      "execution_duration_seconds": round(time.perf_counter() - started, 4),
                      "source_row_counts": locals().get("source_counts", {})})
        DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        audit_path = DATA_REPORTS_DIR / "etl_audit.json"
        try:
            existing = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else []
            if isinstance(existing, dict): existing = [existing]
        except (OSError, json.JSONDecodeError):
            existing = []
        existing.append(audit)
        audit_path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")
        (DATA_REPORTS_DIR / f"etl_audit_{run_id}.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
        logger.exception("ETL %s failed", run_id)
        raise


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the Food Delivery Analytics ETL pipeline")
    parser.add_argument("--load-to-database", action="store_true", help="Also load this run to PostgreSQL")
    args = parser.parse_args()
    result = run(load_to_database=args.load_to_database)
    print(json.dumps({"execution_id": result["audit"]["execution_id"],
                      "valid_orders": len(result["processed"]), "rejected_orders": len(result["rejected"]),
                      "status": result["audit"]["execution_status"],
                      "database_load_status": result["audit"].get("database_load_status")}, indent=2))
