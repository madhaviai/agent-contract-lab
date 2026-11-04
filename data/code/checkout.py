from datetime import datetime, timedelta

def already_refunded(order):
    return bool(order.get("refunded_at"))

def purchase_date(order):
    return order["purchased_at"]

# TODO: refund_order(order, today) — refund only within 30 days and if not already refunded.
