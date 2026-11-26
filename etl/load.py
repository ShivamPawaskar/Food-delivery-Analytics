"""Write pipeline outputs atomically enough for local analytics use."""
import json
from pathlib import Path
import pandas as pd

from config.settings import DATA_PROCESSED_DIR, DATA_REPORTS_DIR


def load_to_postgres(processed, rejected, aggregations, restaurant_master, partner_master, audit, engine=None):
    """Persist one fully transformed ETL run in PostgreSQL transactionally."""
    from database.loader import load_frames
    return load_frames({"orders": processed, "restaurants": restaurant_master,
                        "delivery_partners": partner_master}, rejected=rejected,
                       aggregations=aggregations, audit=audit, engine=engine)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str, allow_nan=False), encoding="utf-8")


def write_outputs(processed: pd.DataFrame, rejected: pd.DataFrame, aggregations: dict[str, pd.DataFrame],
                  quality_report: dict, audit: dict) -> None:
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    processed.to_csv(DATA_PROCESSED_DIR / "processed_orders.csv", index=False)
    # Backward-compatible dashboard input name.
    processed.to_csv(DATA_PROCESSED_DIR / "orders.csv", index=False)
    rejected.to_csv(DATA_PROCESSED_DIR / "rejected_records.csv", index=False)
    for name, frame in aggregations.items():
        frame.to_csv(DATA_PROCESSED_DIR / f"{name}.csv", index=False)
    _write_json(DATA_REPORTS_DIR / "data_quality_report.json", quality_report)
    _write_json(DATA_REPORTS_DIR / f"etl_audit_{audit['execution_id']}.json", audit)
    audit_path = DATA_REPORTS_DIR / "etl_audit.json"
    if audit_path.exists():
        try:
            history = json.loads(audit_path.read_text(encoding="utf-8"))
            if isinstance(history, dict):
                history = [history]
        except (json.JSONDecodeError, OSError):
            history = []
    else:
        history = []
    history.append(audit)
    _write_json(audit_path, history)
