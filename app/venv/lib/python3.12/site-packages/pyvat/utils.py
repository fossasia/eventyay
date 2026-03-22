from decimal import Decimal


def ensure_decimal(value):
    return value if isinstance(value, Decimal) else Decimal(value)
