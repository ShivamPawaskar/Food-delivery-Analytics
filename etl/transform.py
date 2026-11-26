"""Clean, validate, calculate, integrate and aggregate source data."""
from __future__ import annotations

from collections import Counter
import pandas as pd

from etl.validate import validate_order_records, validate_master_data

TIMESTAMP_COLUMNS = ["order_timestamp", "accepted_timestamp", "pickup_timestamp", "delivered_timestamp"]
NUMERIC_COLUMNS = ["order_amount", "delivery_fee", "promised_delivery_minutes", "delivery_distance_km"]
REASON_CATEGORIES = {
    "duplicate_order_id": "uniqueness", "unknown_restaurant_id": "foreign_key", "unknown_partner_id": "foreign_key",
    "invalid_customer_id": "identifier", "nonpositive_order_amount": "business_rule", "invalid_order_amount": "type",
    "negative_delivery_fee": "business_rule", "invalid_delivery_fee": "type", "nonpositive_delivery_distance": "business_rule",
    "invalid_delivery_distance_km": "type", "nonpositive_promised_delivery_time": "business_rule",
    "invalid_promised_delivery_minutes": "type", "invalid_order_status": "domain", "accepted_before_order": "timestamp_sequence",
    "pickup_before_acceptance": "timestamp_sequence", "delivered_before_pickup": "timestamp_sequence",
}


def _clean_source(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    for column in df.select_dtypes(include=["object", "string"]).columns:
        df[column] = df[column].map(lambda v: v.strip() if isinstance(v, str) else v)
        df[column] = df[column].replace(r"^\s*$", pd.NA, regex=True)
    return df


def transform_orders(raw_orders: pd.DataFrame, restaurants: pd.DataFrame, partners: pd.DataFrame,
                     processing_timestamp: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return enriched valid orders, traceable rejected records, and transformation counts."""
    raw = _clean_source(raw_orders).reset_index(drop=True)
    df = raw.copy()
    restaurants = _clean_source(restaurants).reset_index(drop=True)
    partners = _clean_source(partners).reset_index(drop=True)
    validate_master_data(restaurants, partners)

    for column in TIMESTAMP_COLUMNS:
        df[column] = pd.to_datetime(df[column], errors="coerce")
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["order_status"] = df.order_status.astype("string").str.lower()

    reason_lists = validate_order_records(df, restaurants, partners, tuple(TIMESTAMP_COLUMNS))
    # Include parse failures distinctly from genuinely absent optional milestones.
    for col in TIMESTAMP_COLUMNS:
        malformed = raw[col].notna() & raw[col].astype("string").str.strip().ne("") & df[col].isna()
        for idx in df.index[malformed]:
            reason_lists.at[idx].append(f"invalid_{col}")
    rejected_mask = reason_lists.map(bool)
    process_time = processing_timestamp or pd.Timestamp.now(tz="UTC").isoformat()
    rejected = raw.loc[rejected_mask].copy()
    rejected = rejected.rename(columns={c: f"original_{c}" for c in rejected.columns})
    rejected["source_row_number"] = rejected.index + 2  # one-based CSV line number, including header
    rejected["rejection_reason"] = reason_lists[rejected_mask].map(lambda rs: "|".join(dict.fromkeys(rs)))
    rejected["validation_category"] = reason_lists[rejected_mask].map(lambda rs: "|".join(dict.fromkeys(
        REASON_CATEGORIES.get(r, "timestamp" if "timestamp" in r else "required_field") for r in rs)))
    rejected["processing_timestamp"] = process_time

    valid = df.loc[~rejected_mask].copy().reset_index(drop=True)
    valid["prep_time_minutes"] = (valid.pickup_timestamp - valid.accepted_timestamp).dt.total_seconds() / 60
    valid["delivery_time_minutes"] = (valid.delivered_timestamp - valid.pickup_timestamp).dt.total_seconds() / 60
    valid["total_fulfilment_minutes"] = (valid.delivered_timestamp - valid.order_timestamp).dt.total_seconds() / 60
    delivered = valid.order_status.eq("delivered")
    # Delivery performance is undefined for cancelled/failed orders.
    valid.loc[~delivered, ["delivery_time_minutes", "total_fulfilment_minutes"]] = pd.NA
    valid["order_date"] = valid.order_timestamp.dt.date.astype(str)
    valid["order_month"] = valid.order_timestamp.dt.to_period("M").astype(str)
    valid["order_hour"] = valid.order_timestamp.dt.hour
    valid["is_late"] = False
    valid.loc[delivered, "is_late"] = valid.loc[delivered, "total_fulfilment_minutes"].gt(valid.loc[delivered, "promised_delivery_minutes"])

    restaurant_columns = restaurants[["restaurant_id", "restaurant_name", "cuisine", "restaurant_rating", "city"]].rename(columns={"city": "restaurant_city"})
    partner_columns = partners[["partner_id", "partner_name", "vehicle_type", "partner_rating", "partner_city"]]
    valid = valid.merge(restaurant_columns, on="restaurant_id", how="left", validate="many_to_one")
    valid = valid.merge(partner_columns, on="partner_id", how="left", validate="many_to_one")
    # Revenue and average order value count completed orders only; all other total order counts include valid statuses.
    valid["revenue"] = valid.order_amount.where(delivered, 0)
    reason_counts = Counter(reason for row in reason_lists for reason in row)
    stats = {"source_rows": int(len(raw)), "valid_rows": int(len(valid)), "rejected_rows": int(len(rejected)),
             "transformation_counts": {"column_names_standardized": int(len(raw.columns)),
                 "timestamps_parsed": int(len(TIMESTAMP_COLUMNS) * len(raw)),
                 "numeric_fields_converted": int(len(NUMERIC_COLUMNS) * len(raw)),
                 "records_enriched": int(len(valid)), "calculated_columns_added": 7},
             "rejection_reason_counts": dict(sorted(reason_counts.items()))}
    return valid, rejected.reset_index(drop=True), stats


def build_aggregations(orders: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Create required analytic tables from the validated, enriched order frame."""
    d = orders.copy()
    delivered = d[d.order_status.eq("delivered")]
    daily_rows = []
    for date, group in d.groupby("order_date", dropna=False):
        done = group[group.order_status.eq("delivered")]
        daily_rows.append({"order_date": date, "total_orders": len(group), "completed_orders": len(done),
            "cancelled_orders": int(group.order_status.eq("cancelled").sum()), "revenue": done.order_amount.sum(),
            "average_order_value": done.order_amount.mean(), "average_delivery_time": done.delivery_time_minutes.mean(),
            "late_deliveries": int(done.is_late.sum())})
    daily = pd.DataFrame(daily_rows)

    restaurant_rows = []
    for rid, group in d.groupby("restaurant_id"):
        done = group[group.order_status.eq("delivered")]
        restaurant_rows.append({"restaurant_id": rid, "restaurant_name": group.restaurant_name.iloc[0], "total_orders": len(group),
            "revenue": done.order_amount.sum(), "average_order_value": done.order_amount.mean(),
            "average_preparation_time": group.prep_time_minutes.mean(), "average_delivery_time": done.delivery_time_minutes.mean(),
            "late_delivery_percentage": 100 * done.is_late.mean() if len(done) else 0.0})
    restaurant = pd.DataFrame(restaurant_rows)

    city_rows = []
    for city, group in d.groupby("city"):
        done = group[group.order_status.eq("delivered")]
        city_rows.append({"city": city, "total_orders": len(group), "revenue": done.order_amount.sum(),
            "average_delivery_time": done.delivery_time_minutes.mean(),
            "cancellation_rate": 100 * group.order_status.eq("cancelled").mean()})
    city = pd.DataFrame(city_rows)

    cuisine_rows = []
    for cuisine, group in d.groupby("cuisine"):
        done = group[group.order_status.eq("delivered")]
        cuisine_rows.append({"cuisine": cuisine, "total_orders": len(group), "revenue": done.order_amount.sum(),
            "average_order_value": done.order_amount.mean()})
    cuisine = pd.DataFrame(cuisine_rows)

    partner_rows = []
    for pid, group in delivered.groupby("partner_id"):
        partner_rows.append({"partner_id": pid, "partner_name": group.partner_name.iloc[0], "total_deliveries": len(group),
            "average_delivery_time": group.delivery_time_minutes.mean(), "partner_rating": group.partner_rating.iloc[0],
            "late_delivery_percentage": 100 * group.is_late.mean()})
    partner = pd.DataFrame(partner_rows, columns=["partner_id", "partner_name", "total_deliveries", "average_delivery_time", "partner_rating", "late_delivery_percentage"])
    return {"daily_performance": daily, "restaurant_performance": restaurant, "city_performance": city,
            "cuisine_performance": cuisine, "delivery_partner_performance": partner}


def transform(frames: dict[str, pd.DataFrame]):
    """Compatibility entry point; use pipeline.run for complete output and audit."""
    return transform_orders(frames["orders"], frames["restaurants"], frames["delivery_partners"])
