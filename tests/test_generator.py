import numpy as np
from generate_dataset import build_master_data, generate_orders, introduce_quality_issues


def test_generation_counts_and_controlled_issues():
    rng = np.random.default_rng(42)
    restaurants, partners = build_master_data(rng)
    raw = introduce_quality_issues(generate_orders(rng, restaurants, partners), rng)
    assert (len(raw), len(restaurants), len(partners)) == (10_000, 100, 250)
    assert raw.order_id.duplicated().any()
    assert raw.customer_id.isna().any()
    assert raw.order_amount.lt(0).any()
    assert (~raw.restaurant_id.isin(restaurants.restaurant_id)).any()
    assert (~raw.partner_id.isin(partners.partner_id)).any()


def test_master_data_is_clean():
    restaurants, partners = build_master_data(np.random.default_rng(42))
    assert not restaurants.isna().any().any()
    assert not partners.isna().any().any()
    assert restaurants.restaurant_id.is_unique
    assert partners.partner_id.is_unique
