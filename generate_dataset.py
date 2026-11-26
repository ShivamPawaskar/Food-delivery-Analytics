"""Generate deterministic synthetic food delivery data and a quality profile."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import DATA_RAW_DIR, DATA_REPORTS_DIR, RANDOM_SEED

CITIES = ["Pune", "Mumbai", "Bengaluru", "Hyderabad", "Delhi", "Chennai", "Kolkata", "Ahmedabad", "Jaipur", "Nagpur"]
CUISINES = ["North Indian", "South Indian", "Chinese", "Italian", "Fast Food", "Biryani", "Desserts", "Maharashtrian", "Street Food"]
PAYMENTS = ["UPI", "Cash", "Credit Card", "Debit Card", "Wallet"]
STATUSES = ["delivered", "cancelled", "failed"]


def build_master_data(rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    restaurants = pd.DataFrame({
        "restaurant_id": [f"R{i:03d}" for i in range(1, 101)],
        "restaurant_name": [f"{rng.choice(['Spice', 'Urban', 'Royal', 'Fresh', 'Tasty', 'Little'])} {rng.choice(CUISINES)} Kitchen {i:02d}" for i in range(1, 101)],
        "cuisine": rng.choice(CUISINES, 100), "city": rng.choice(CITIES, 100),
        "restaurant_rating": np.round(np.clip(rng.normal(4.0, .45, 100), 2.5, 5), 1),
        "average_prep_minutes": rng.integers(12, 41, 100),
    })
    partners = pd.DataFrame({
        "partner_id": [f"P{i:03d}" for i in range(1, 251)],
        "partner_name": [f"Delivery Partner {i:03d}" for i in range(1, 251)],
        "vehicle_type": rng.choice(["Bike", "Scooter", "Bicycle"], 250, p=[.35, .55, .10]),
        "partner_rating": np.round(np.clip(rng.normal(4.1, .4, 250), 2.5, 5), 1),
        "partner_city": rng.choice(CITIES, 250),
    })
    return restaurants, partners


def generate_orders(rng: np.random.Generator, restaurants: pd.DataFrame, partners: pd.DataFrame) -> pd.DataFrame:
    n = 10_000
    start = pd.Timestamp("2025-01-01")
    offsets = rng.integers(0, 181 * 24 * 60, n)
    # Meal-time weighting: breakfast, lunch, evening snacks and dinner.
    hour_weights = np.array([.01,.01,.01,.005,.005,.01,.03,.06,.07,.05,.04,.05,.09,.08,.04,.035,.04,.075,.095,.095,.08,.06,.03,.015])
    hour_weights /= hour_weights.sum()
    day = (start + pd.to_timedelta(offsets, unit="m")).normalize()
    hours = rng.choice(np.arange(24), n, p=hour_weights)
    minutes = rng.integers(0, 60, n)
    order_ts = day + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m")

    restaurant_idx = rng.integers(0, len(restaurants), n)
    restaurant_rows = restaurants.iloc[restaurant_idx].reset_index(drop=True)
    # Choose partners from the same city when possible.
    partner_ids = []
    partners_by_city = {city: partners.index[partners.partner_city == city].to_numpy() for city in CITIES}
    for city in restaurant_rows.city:
        candidates = partners_by_city[city]
        partner_ids.append(partners.iloc[int(rng.choice(candidates if len(candidates) else partners.index))].partner_id)
    partner_ids = np.array(partner_ids)

    prep = np.maximum(5, rng.normal(restaurant_rows.average_prep_minutes.to_numpy(), 5)).round().astype(int)
    accept_delay = rng.integers(1, 6, n)
    # Pickup cannot precede acceptance. Keeping this invariant leaves the injected
    # timestamp defects as intentional, identifiable source issues only.
    pickup_delay = np.maximum(accept_delay + 1, np.maximum(3, prep + rng.normal(4, 5, n))).round().astype(int)
    distance = np.round(np.clip(rng.gamma(2.1, 2.0, n), .4, 18), 1)
    ride_minutes = np.maximum(5, distance * rng.uniform(3.0, 4.5, n) + rng.normal(5, 4, n)).round().astype(int)
    accepted = order_ts + pd.to_timedelta(accept_delay, unit="m")
    pickup = order_ts + pd.to_timedelta(pickup_delay, unit="m")
    delivered = pickup + pd.to_timedelta(ride_minutes, unit="m")
    amount = np.round(np.clip(rng.lognormal(np.log(420), .55, n), 80, 3500), 2)
    fee = np.round(20 + distance * rng.uniform(4, 7, n), 2)
    status = rng.choice(STATUSES, n, p=[.93, .055, .015])
    promised = np.maximum(20, (prep + ride_minutes + rng.normal(12, 5, n)).round()).astype(int)
    orders = pd.DataFrame({
        "order_id": [f"O{i:05d}" for i in range(1, n + 1)],
        "customer_id": [f"C{x:05d}" for x in rng.integers(1, 3001, n)],
        "restaurant_id": restaurant_rows.restaurant_id.to_numpy(), "partner_id": partner_ids,
        "order_timestamp": order_ts, "accepted_timestamp": accepted, "pickup_timestamp": pickup,
        "delivered_timestamp": delivered, "order_amount": amount, "delivery_fee": fee,
        "payment_method": rng.choice(PAYMENTS, n, p=[.48, .18, .14, .12, .08]),
        "order_status": status, "promised_delivery_minutes": promised,
        "delivery_distance_km": distance, "city": restaurant_rows.city.to_numpy(),
    })
    # Cancelled/failed deliveries need not have completed milestone timestamps.
    not_delivered = orders.order_status.ne("delivered")
    orders.loc[not_delivered, "delivered_timestamp"] = pd.NaT
    return orders


def introduce_quality_issues(orders: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Add small, documented errors (about 2.7% of rows), reproducibly."""
    result = orders.copy()
    # Keep raw timestamp columns capable of preserving malformed source strings.
    result["accepted_timestamp"] = result["accepted_timestamp"].astype(object)
    n = len(result)
    # Disjoint row groups keep issue counts easy to explain and verify.
    groups = np.array_split(rng.permutation(n), 9)
    for i in groups[0][:25]: result.loc[i, "customer_id"] = None
    for i in groups[1][:20]: result.loc[i, "order_amount"] = np.nan
    for i in groups[2][:15]: result.loc[i, "delivery_fee"] = -abs(result.loc[i, "delivery_fee"])
    for i in groups[3][:10]: result.loc[i, "order_amount"] = -abs(result.loc[i, "order_amount"])
    for i in groups[4][:10]: result.loc[i, "restaurant_id"] = "R999"
    for i in groups[5][:10]: result.loc[i, "partner_id"] = "P999"
    for i in groups[6][:10]: result.loc[i, "accepted_timestamp"] = "not-a-timestamp"
    for i in groups[7][:10]: result.loc[i, "pickup_timestamp"] = result.loc[i, "order_timestamp"] - pd.Timedelta(minutes=12)
    for i in groups[8][:10]: result.loc[i, "order_status"] = "in_transit_unknown"
    # Duplicate an existing order ID on a separate row without changing row count.
    result.loc[int(groups[0][25]), "order_id"] = result.loc[int(groups[0][26]), "order_id"]
    return result


def profile_data(frames: dict[str, pd.DataFrame]) -> dict:
    report = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(), "datasets": {}}
    for name, df in frames.items():
        numeric = df.select_dtypes(include=[np.number])
        report["datasets"][name] = {
            "row_count": int(len(df)), "column_names": list(df.columns),
            "data_types": {c: str(t) for c, t in df.dtypes.items()},
            "missing_values": {c: int(v) for c, v in df.isna().sum().items()},
            "duplicate_rows": int(df.duplicated().sum()),
            "duplicate_key_count": int(df["order_id"].duplicated().sum()) if "order_id" in df else 0,
            "unique_values": {c: int(df[c].nunique(dropna=True)) for c in df.columns},
            "numeric_summary": json.loads(numeric.describe().to_json()) if len(numeric.columns) else {},
        }
    orders = frames["orders"]
    report["foreign_key_integrity"] = {
        "orders.restaurant_id": {"invalid_count": int((~orders.restaurant_id.isin(frames["restaurants"].restaurant_id)).sum()), "master_count": int(frames["restaurants"].restaurant_id.nunique())},
        "orders.partner_id": {"invalid_count": int((~orders.partner_id.isin(frames["delivery_partners"].partner_id)).sum()), "master_count": int(frames["delivery_partners"].partner_id.nunique())},
    }
    return report


def main() -> None:
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)
    restaurants, partners = build_master_data(rng)
    orders = introduce_quality_issues(generate_orders(rng, restaurants, partners), rng)
    # Use ISO timestamps and empty fields for readable interoperable CSVs.
    orders.to_csv(DATA_RAW_DIR / "orders.csv", index=False, date_format="%Y-%m-%dT%H:%M:%S")
    restaurants.to_csv(DATA_RAW_DIR / "restaurants.csv", index=False)
    partners.to_csv(DATA_RAW_DIR / "delivery_partners.csv", index=False)
    report = profile_data({"orders": orders, "restaurants": restaurants, "delivery_partners": partners})
    (DATA_REPORTS_DIR / "dataset_profile.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"counts": {k: v["row_count"] for k, v in report["datasets"].items()}, "foreign_key_integrity": report["foreign_key_integrity"], "output": str(DATA_RAW_DIR)}, indent=2))


if __name__ == "__main__":
    main()
