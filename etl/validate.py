"""Reusable record-level and master-data quality validation."""
from __future__ import annotations

import pandas as pd


def validate_master_data(restaurants: pd.DataFrame, partners: pd.DataFrame) -> None:
    for label, frame, key in (("restaurants", restaurants, "restaurant_id"), ("delivery partners", partners, "partner_id")):
        if frame[key].isna().any() or frame[key].duplicated().any():
            raise ValueError(f"{label} must have nonmissing, unique {key} values")
        if frame.empty:
            raise ValueError(f"{label} master data is empty")


def validate_order_records(orders: pd.DataFrame, restaurants: pd.DataFrame, partners: pd.DataFrame,
                          timestamp_columns: tuple[str, ...]) -> pd.DataFrame:
    """Return a reason list per row; no bad row is silently thrown away."""
    reasons: list[list[str]] = [[] for _ in range(len(orders))]
    def add(mask, code):
        for position in orders.index[mask.fillna(True)].tolist():
            reasons[orders.index.get_loc(position)].append(code)

    required = ["order_id", "customer_id", "restaurant_id", "partner_id",
                "order_amount", "delivery_fee",
                "payment_method", "order_status", "promised_delivery_minutes", "delivery_distance_km", "city"]
    for column in required:
        add(orders[column].isna() | orders[column].astype("string").str.strip().eq(""), f"missing_{column}")
    add(orders.order_id.duplicated(keep=False), "duplicate_order_id")
    add(~orders.restaurant_id.isin(restaurants.restaurant_id), "unknown_restaurant_id")
    add(~orders.partner_id.isin(partners.partner_id), "unknown_partner_id")
    add(orders.customer_id.notna() & ~orders.customer_id.astype("string").str.fullmatch(r"C\d+", na=False), "invalid_customer_id")

    amount = pd.to_numeric(orders.order_amount, errors="coerce")
    fee = pd.to_numeric(orders.delivery_fee, errors="coerce")
    distance = pd.to_numeric(orders.delivery_distance_km, errors="coerce")
    promised = pd.to_numeric(orders.promised_delivery_minutes, errors="coerce")
    for column, parsed in (("order_amount", amount), ("delivery_fee", fee), ("delivery_distance_km", distance), ("promised_delivery_minutes", promised)):
        add(parsed.isna(), f"invalid_{column}")
    add(amount.notna() & amount.le(0), "nonpositive_order_amount")
    add(fee.notna() & fee.lt(0), "negative_delivery_fee")
    add(distance.notna() & distance.le(0), "nonpositive_delivery_distance")
    add(promised.notna() & promised.le(0), "nonpositive_promised_delivery_time")
    statuses = {"delivered", "cancelled", "failed"}
    add(~orders.order_status.astype("string").str.lower().isin(statuses), "invalid_order_status")

    status = orders.order_status.astype("string").str.lower()
    delivered = status.eq("delivered")
    add(orders.order_timestamp.isna(), "missing_or_invalid_order_timestamp")
    for column in ("accepted_timestamp", "pickup_timestamp"):
        required_at_stage = delivered
        add(required_at_stage & orders[column].isna(), f"missing_or_invalid_{column}")
    add(delivered & orders.delivered_timestamp.isna(), "missing_delivered_timestamp")
    add(orders.accepted_timestamp.notna() & orders.order_timestamp.notna() & orders.accepted_timestamp.lt(orders.order_timestamp), "accepted_before_order")
    add(orders.pickup_timestamp.notna() & orders.accepted_timestamp.notna() & orders.pickup_timestamp.lt(orders.accepted_timestamp), "pickup_before_acceptance")
    add(delivered & orders.delivered_timestamp.lt(orders.pickup_timestamp), "delivered_before_pickup")
    return pd.Series(reasons, index=orders.index, name="rejection_reasons", dtype=object)


def quality_summary(orders: pd.DataFrame, restaurants: pd.DataFrame, partners: pd.DataFrame) -> dict:
    return {"row_count": len(orders), "duplicate_order_ids": int(orders.order_id.duplicated().sum()),
            "invalid_restaurant_ids": int((~orders.restaurant_id.isin(restaurants.restaurant_id)).sum()),
            "invalid_partner_ids": int((~orders.partner_id.isin(partners.partner_id)).sum())}
