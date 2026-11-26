import hashlib
import pytest

from config.settings import DATA_RAW_DIR
from etl.extract import extract
from etl.pipeline import run
from etl.transform import build_aggregations


def _source_hashes():
    return {name: hashlib.sha256((DATA_RAW_DIR / name).read_bytes()).hexdigest()
            for name in ("orders.csv", "restaurants.csv", "delivery_partners.csv")}


def test_end_to_end_reconciles_and_preserves_raw_files():
    before = _source_hashes()
    result = run()
    assert _source_hashes() == before
    assert len(result["processed"]) + len(result["rejected"]) == 10_000
    assert result["processed"].order_id.is_unique
    assert result["rejected"].rejection_reason.notna().all()
    assert result["rejected"].rejection_reason.str.len().gt(0).all()
    assert result["audit"]["raw_sources_unchanged"] is True
    assert result["audit"]["execution_status"] == "success"


def test_processed_formulas_and_integrity():
    result = run()
    orders = result["processed"]
    delivered = orders[orders.order_status.eq("delivered")]
    assert orders.restaurant_name.notna().all() and orders.partner_name.notna().all()
    assert (orders.prep_time_minutes >= 0).all()
    assert (delivered.delivery_time_minutes ==
            (delivered.delivered_timestamp - delivered.pickup_timestamp).dt.total_seconds() / 60).all()
    assert (delivered.total_fulfilment_minutes ==
            (delivered.delivered_timestamp - delivered.order_timestamp).dt.total_seconds() / 60).all()
    assert orders.loc[~orders.order_status.eq("delivered"), "delivery_time_minutes"].isna().all()
    assert (delivered.is_late == delivered.total_fulfilment_minutes.gt(delivered.promised_delivery_minutes)).all()
    assert orders.revenue.sum() == delivered.order_amount.sum()


def test_aggregates_match_processed_orders():
    result = run()
    orders = result["processed"]
    aggregates = build_aggregations(orders)
    assert aggregates["daily_performance"].total_orders.sum() == len(orders)
    assert aggregates["daily_performance"].completed_orders.sum() == int(orders.order_status.eq("delivered").sum())
    assert aggregates["restaurant_performance"].total_orders.sum() == len(orders)
    assert aggregates["city_performance"].total_orders.sum() == len(orders)
    assert abs(aggregates["cuisine_performance"].revenue.sum() - orders.revenue.sum()) < 0.01
    assert aggregates["delivery_partner_performance"].total_deliveries.sum() == int(orders.order_status.eq("delivered").sum())


def test_extractor_checks_required_sources(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract(tmp_path)
    (tmp_path / "orders.csv").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        extract(tmp_path)
