"""Exact decimal money handling and the output formats the samples use."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENTS = Decimal("0.01")
ZERO = Decimal("0")


class MoneyError(ValueError):
    """A dataset amount could not be parsed as a finite decimal."""


def parse(value, *, default=None):
    """Parse a CSV money field. Blank means unknown, never zero."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, Decimal):
        return value
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise MoneyError(f"Invalid monetary value: {value!r}") from None
    if not result.is_finite():
        raise MoneyError("Monetary values must be finite.")
    return result


def quantize(value):
    """Round to cents once, at the point a figure becomes a reported amount."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def normalized(value):
    """Cent-rounded with trailing zeros removed: the amount_safe_to_pay style."""
    text = format(quantize(value), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def plan_amount(value):
    """Two decimals when fractional, plain integer otherwise: the payment_plan style."""
    value = quantize(value)
    return format(value, "f") if value % 1 else str(int(value))


def clamp(value, low, high):
    return max(low, min(value, high))
