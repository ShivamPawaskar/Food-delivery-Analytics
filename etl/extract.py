"""Robust CSV extraction with schema, encoding and source-count checks."""
from __future__ import annotations

import pandas as pd

from config.settings import DATA_RAW_DIR

EXPECTED_COLUMNS = {
    "orders": {"order_id", "customer_id", "restaurant_id", "partner_id", "order_timestamp",
                "accepted_timestamp", "pickup_timestamp", "delivered_timestamp", "order_amount",
                "delivery_fee", "payment_method", "order_status", "promised_delivery_minutes",
                "delivery_distance_km", "city"},
    "restaurants": {"restaurant_id", "restaurant_name", "cuisine", "city", "restaurant_rating", "average_prep_minutes"},
    "delivery_partners": {"partner_id", "partner_name", "vehicle_type", "partner_rating", "partner_city"},
}
FILES = {"orders": "orders.csv", "restaurants": "restaurants.csv", "delivery_partners": "delivery_partners.csv"}


def extract(raw_dir=DATA_RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read all required sources as strings so original values remain auditable."""
    frames: dict[str, pd.DataFrame] = {}
    for name, filename in FILES.items():
        path = raw_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required ETL source is missing: {path}")
        if path.stat().st_size == 0:
            raise ValueError(f"Required ETL source is empty: {path}")
        last_error = None
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=encoding, on_bad_lines="error")
                break
            except UnicodeDecodeError as exc:
                last_error = exc
        else:
            raise ValueError(f"Could not decode {path} as UTF-8 or Windows-1252") from last_error
        if frame.empty:
            raise ValueError(f"Required ETL source has headers but no records: {path}")
        frame.columns = [str(col).strip().lower() for col in frame.columns]
        missing = EXPECTED_COLUMNS[name] - set(frame.columns)
        if missing:
            raise ValueError(f"{filename} is missing expected columns: {sorted(missing)}")
        frame.attrs["source_row_count"] = int(len(frame))
        frame.attrs["source_file"] = str(path)
        frames[name] = frame
    return frames
