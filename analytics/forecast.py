"""Small, transparent weekday demand forecast and rolling-origin backtest."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _weekday_average(values: list[float], weekdays: list[int], target_index: int, weekday: int) -> float:
    prior = [values[i] for i in range(min(target_index, len(values)) - 1, -1, -1)
             if weekdays[i] == weekday][:4]
    return float(np.mean(prior)) if prior else 0.0


def _score(actual: list[float], predicted: list[float]) -> dict:
    errors = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    return {
        "mae": float(np.mean(np.abs(errors))) if len(errors) else None,
        "rmse": float(np.sqrt(np.mean(errors ** 2))) if len(errors) else None,
        "p90_absolute_error": float(np.quantile(np.abs(errors), .90)) if len(errors) else 0.0,
    }


def forecast_series(rows: list[dict], *, horizon: int) -> dict:
    """Forecast orders/revenue by weekday; score against last-week seasonal naive.

    The last 28 observations are held out chronologically. Backtesting rolls forward
    one day at a time; the final forecast uses the same weekday's latest four values.
    Error bands are empirical 90th-percentile absolute backtest errors, not guarantees.
    """
    if horizon not in (7, 14):
        raise ValueError("Forecast horizon must be 7 or 14 days.")
    frame = pd.DataFrame(rows)
    if frame.empty or len(frame) < 56:
        raise ValueError("At least 56 days of filtered order history are required for this forecast.")
    frame["order_date"] = pd.to_datetime(frame["order_date"])
    frame = frame.sort_values("order_date").reset_index(drop=True)
    frame["total_orders"] = pd.to_numeric(frame["total_orders"], errors="coerce").fillna(0)
    frame["revenue"] = pd.to_numeric(frame["revenue"], errors="coerce").fillna(0)
    actual_orders = frame["total_orders"].astype(float).tolist()
    actual_revenue = frame["revenue"].astype(float).tolist()
    weekdays = frame["order_date"].dt.dayofweek.tolist()

    holdout_start = len(frame) - 28
    test_orders, model_orders, naive_orders = [], [], []
    test_revenue, model_revenue, naive_revenue = [], [], []
    for index in range(holdout_start, len(frame)):
        weekday = weekdays[index]
        model_orders.append(_weekday_average(actual_orders[:index], weekdays[:index], index, weekday))
        model_revenue.append(_weekday_average(actual_revenue[:index], weekdays[:index], index, weekday))
        naive_orders.append(actual_orders[index - 7])
        naive_revenue.append(actual_revenue[index - 7])
        test_orders.append(actual_orders[index])
        test_revenue.append(actual_revenue[index])

    orders_score = _score(test_orders, model_orders)
    orders_baseline = _score(test_orders, naive_orders)
    revenue_score = _score(test_revenue, model_revenue)
    revenue_baseline = _score(test_revenue, naive_revenue)
    order_band = orders_score["p90_absolute_error"] or 0.0
    revenue_band = revenue_score["p90_absolute_error"] or 0.0

    last_date = frame["order_date"].iloc[-1]
    forecast_rows = []
    for step in range(1, horizon + 1):
        target_date = last_date + pd.Timedelta(days=step)
        # Train on observed rows only. Use weekday identity rather than recursively
        # feeding predictions back into the model.
        weekday = target_date.dayofweek
        count = _weekday_average(actual_orders, weekdays, len(actual_orders), weekday)
        revenue = _weekday_average(actual_revenue, weekdays, len(actual_revenue), weekday)
        forecast_rows.append({
            "date": target_date.date().isoformat(),
            "predicted_orders": round(max(0.0, count), 1),
            "orders_lower": round(max(0.0, count - order_band), 1),
            "orders_upper": round(max(0.0, count + order_band), 1),
            "predicted_revenue": round(max(0.0, revenue), 2),
            "revenue_lower": round(max(0.0, revenue - revenue_band), 2),
            "revenue_upper": round(max(0.0, revenue + revenue_band), 2),
        })

    history = [{
        "date": row.order_date.date().isoformat(),
        "actual_orders": int(row.total_orders),
        "actual_revenue": round(float(row.revenue), 2),
    } for row in frame.tail(84).itertuples(index=False)]
    forecast_total = sum(x["predicted_orders"] for x in forecast_rows)
    revenue_total = sum(x["predicted_revenue"] for x in forecast_rows)
    improvement = None
    if orders_baseline["mae"] and orders_baseline["mae"] > 0:
        improvement = 100.0 * (orders_baseline["mae"] - orders_score["mae"]) / orders_baseline["mae"]
    return {
        "history": history,
        "forecast": forecast_rows,
        "metrics": {
            "forecast_orders": round(forecast_total, 1),
            "forecast_revenue": round(revenue_total, 2),
            "backtest_days": len(test_orders),
            "orders_mae": round(orders_score["mae"], 2),
            "orders_rmse": round(orders_score["rmse"], 2),
            "baseline_mae": round(orders_baseline["mae"], 2),
            "mae_improvement_pct": round(improvement, 1) if improvement is not None else None,
            "revenue_mae": round(revenue_score["mae"], 2),
            "revenue_baseline_mae": round(revenue_baseline["mae"], 2),
            "orders_error_band_p90": round(order_band, 2),
            "revenue_error_band_p90": round(revenue_band, 2),
            "history_days": len(frame),
            "anchor_date": last_date.date().isoformat(),
            "method": "Four-week weekday mean",
        },
    }
