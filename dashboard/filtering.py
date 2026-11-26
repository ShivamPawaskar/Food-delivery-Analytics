"""Pure validation/normalization for user-selected dashboard filters."""
from datetime import timedelta


def normalize_filters(start_date, end_date, *, city=None, restaurant_label=None,
                      cuisine=None, payment_method=None, order_status=None):
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("Start date must not be later than end date")
    restaurant_id = None
    if restaurant_label and restaurant_label != "All":
        restaurant_id = restaurant_label.split(" | ", 1)[0].strip()
        if not restaurant_id:
            raise ValueError("Invalid restaurant selection")
    return {"start_date": start_date,
        "end_date": end_date + timedelta(days=1) if end_date is not None else None,
        "city": city if city and city != "All" else None,
        "restaurant_id": restaurant_id,
        "cuisine": cuisine if cuisine and cuisine != "All" else None,
        "payment_method": payment_method if payment_method and payment_method != "All" else None,
        "order_status": order_status if order_status and order_status != "All" else None}
