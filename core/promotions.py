"""Shared checkout promotions. Discounts apply to dishes, one code per order."""
from decimal import Decimal, ROUND_HALF_UP

PROMOTIONS = {"BITE5": 5, "BITE10": 10, "LUNCH15": 15, "TASTY20": 20, "BITE25": 25}


def calculate_discount(subtotal, code):
    if not isinstance(code, str) or len(code) > 32:
        raise ValueError("Invalid promo code.")
    code = code.strip().upper()
    if not code:
        return "", Decimal("0.00")
    if code not in PROMOTIONS:
        raise ValueError("Invalid promo code.")
    discount = (subtotal * Decimal(PROMOTIONS[code]) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return code, min(subtotal, discount)
