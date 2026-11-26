"""Metrics derived from cleaned order data."""
import pandas as pd


def summarize(orders: pd.DataFrame) -> dict:
    delivered = orders[orders.order_status.eq("delivered")].copy()
    duration = (pd.to_datetime(delivered.delivered_timestamp) - pd.to_datetime(delivered.order_timestamp)).dt.total_seconds() / 60
    return {"orders": int(len(orders)), "delivered": int(len(delivered)),
            "gross_order_value": float(delivered.order_amount.sum()),
            "average_order_value": float(delivered.order_amount.mean()) if len(delivered) else 0.0,
            "average_delivery_minutes": float(duration.mean()) if len(duration) else 0.0}
