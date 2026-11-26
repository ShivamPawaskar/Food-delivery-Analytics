"""Rule-based observations derived only from named PostgreSQL analytics queries."""
from __future__ import annotations

from database.queries import run_analytics


def _number(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def build_insights(kpis, restaurants, cities, cuisines, partners, peak_hours) -> list[dict[str, str]]:
    """Turn actual database query rows into transparent, thresholded observations."""
    insights: list[dict[str, str]] = []
    overall_late = _number(kpis.get("late_delivery_percentage"))
    overall_cancel = _number(kpis.get("cancellation_percentage"))
    if not cities.empty:
        city = cities.sort_values(["total_orders", "city"], ascending=[False, True]).iloc[0]
        insights.append({"category": "City volume", "insight": f"{city.city} has the highest order volume.",
            "evidence": f"{int(city.total_orders):,} orders in the selected period.", "rule": "Maximum city total_orders."})
        high_cancel = cities[(cities.total_orders >= 10) & (cities.cancellation_rate > overall_cancel + 5)]
        for row in high_cancel.sort_values("cancellation_rate", ascending=False).head(3).itertuples():
            insights.append({"category": "Cancellation risk", "insight": f"{row.city} has an elevated cancellation rate.",
                "evidence": f"{row.cancellation_rate:.1f}% versus {overall_cancel:.1f}% overall, across {int(row.total_orders)} orders.",
                "rule": "At least 10 orders and more than 5 percentage points above the filtered overall rate."})
    if not cuisines.empty:
        cuisine = cuisines.sort_values(["revenue", "cuisine"], ascending=[False, True]).iloc[0]
        insights.append({"category": "Cuisine revenue", "insight": f"{cuisine.cuisine} generates the most revenue.",
            "evidence": f"₹{_number(cuisine.revenue):,.0f} from {int(cuisine.total_orders):,} orders.", "rule": "Maximum cuisine revenue."})
    active_restaurants = restaurants[restaurants.total_orders > 0] if not restaurants.empty else restaurants
    if not active_restaurants.empty:
        revenue_leader = active_restaurants.sort_values("revenue", ascending=False).iloc[0]
        order_leader = active_restaurants.sort_values("total_orders", ascending=False).iloc[0]
        insights.append({"category": "Restaurant comparison", "insight": f"{revenue_leader.restaurant_name} leads revenue; {order_leader.restaurant_name} leads order volume.",
            "evidence": f"Revenue leader: ₹{_number(revenue_leader.revenue):,.0f}; order leader: {int(order_leader.total_orders):,} orders.",
            "rule": "Rank restaurants by filtered revenue and order count."})
        high_late = active_restaurants[(active_restaurants.completed_orders >= 5) & (active_restaurants.late_delivery_percentage > max(10.0, overall_late + 5.0))]
        for row in high_late.sort_values("late_delivery_percentage", ascending=False).head(3).itertuples():
            insights.append({"category": "Late delivery risk", "insight": f"{row.restaurant_name} has an unusually high late delivery rate.",
                "evidence": f"{row.late_delivery_percentage:.1f}% across {int(row.completed_orders)} completed orders; filtered overall rate is {overall_late:.1f}%.",
                "rule": "At least 5 completed orders and late rate above both 10% and the overall rate by 5 percentage points."})
        low_rated = active_restaurants[active_restaurants.restaurant_rating < 3.5]
        for row in low_rated.sort_values("restaurant_rating").head(3).itertuples():
            insights.append({"category": "Restaurant rating", "insight": f"{row.restaurant_name} has a low restaurant rating.",
                "evidence": f"Rating {row.restaurant_rating:.1f}/5 with {int(row.total_orders)} filtered orders.",
                "rule": "Restaurant rating below 3.5/5."})
    if not partners.empty:
        strong = partners[(partners.total_deliveries >= 5) & (partners.partner_rating >= 4.5)
                          & (partners.late_delivery_percentage <= overall_late)]
        for row in strong.sort_values(["average_delivery_time", "partner_rating"], ascending=[True, False]).head(3).itertuples():
            insights.append({"category": "Delivery performance", "insight": f"{row.partner_name} is a strong delivery performer.",
                "evidence": f"{int(row.total_deliveries)} deliveries, {row.average_delivery_time:.1f} minute average, {row.late_delivery_percentage:.1f}% late, {row.partner_rating:.1f}/5 rating.",
                "rule": "At least 5 deliveries, rating at least 4.5/5, and late rate no higher than the filtered overall rate."})
    if not peak_hours.empty:
        row = peak_hours.sort_values(["total_orders", "order_hour"], ascending=[False, True]).iloc[0]
        hour = int(row.order_hour)
        period = "breakfast" if 6 <= hour <= 10 else "lunch" if 11 <= hour <= 14 else "evening snacks" if 15 <= hour <= 17 else "dinner" if 18 <= hour <= 22 else "overnight"
        insights.append({"category": "Peak ordering", "insight": f"{period.title()} is the busiest ordering period, peaking at {hour:02d}:00.",
            "evidence": f"{int(row.total_orders):,} orders at {hour:02d}:00 in the selected filters.", "rule": "The hour with the highest filtered order count; period label follows fixed hour bands."})
    return insights


def generate_insights(engine, filters=None) -> list[dict[str, str]]:
    """Query PostgreSQL and generate auditable observations for the current filters."""
    filters = filters or {}
    kpis = run_analytics(engine, "overall_kpis", **filters).iloc[0].to_dict()
    restaurants = run_analytics(engine, "restaurant_ratings", **filters)
    cities = run_analytics(engine, "city_analytics", **filters)
    cuisines = run_analytics(engine, "cuisine_analytics", **filters)
    partners = run_analytics(engine, "delivery_partner_analytics", **filters, limit=500)
    peak_hours = run_analytics(engine, "peak_ordering_hours", **filters)
    return build_insights(kpis, restaurants, cities, cuisines, partners, peak_hours)
