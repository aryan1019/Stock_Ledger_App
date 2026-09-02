"""
Money and quantity precision policy.

Rule: Decimal everywhere. Never float. Never round intermediates.
Round only at component boundaries (charges) and at display.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING, ROUND_DOWN, getcontext

# Wide enough that no intermediate calculation loses precision.
getcontext().prec = 28

ZERO = Decimal("0")
ONE = Decimal("1")

MONEY_DP = Decimal("0.0001")   # storage precision  NUMERIC(18,4)
QTY_DP = Decimal("0.000001")   # storage precision  NUMERIC(18,6)
DISPLAY_DP = Decimal("0.01")   # 2dp, display only
RUPEE = Decimal("1")


def D(value) -> Decimal:
    """Coerce to Decimal safely. Floats are rejected: they are how money bugs start."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError(
            f"float {value!r} in a money path. Pass a str or Decimal, e.g. D('3899.00')."
        )
    return Decimal(str(value))


def money(value) -> Decimal:
    """Quantize to storage precision (4dp)."""
    return D(value).quantize(MONEY_DP, rounding=ROUND_HALF_UP)


def qty(value) -> Decimal:
    """Quantize to quantity precision (6dp)."""
    return D(value).quantize(QTY_DP, rounding=ROUND_HALF_UP)


def display(value) -> Decimal:
    """Quantize to 2dp for display / serialisation."""
    return D(value).quantize(DISPLAY_DP, rounding=ROUND_HALF_UP)


def round_nearest_rupee(value) -> Decimal:
    """STT is levied rounded to the nearest rupee."""
    return D(value).quantize(RUPEE, rounding=ROUND_HALF_UP)


def round_two_dp(value) -> Decimal:
    return D(value).quantize(DISPLAY_DP, rounding=ROUND_HALF_UP)


def round_up_price(value) -> Decimal:
    """Break-even is always rounded UP. Rounding it down yields a losing price."""
    return D(value).quantize(DISPLAY_DP, rounding=ROUND_CEILING)


def floor_qty(value) -> Decimal:
    """Whole shares, rounding down (fractional entitlement policy)."""
    return D(value).quantize(RUPEE, rounding=ROUND_DOWN)


def fmt(value, width: int = 12) -> str:
    """Right-aligned 2dp string for console output."""
    return f"{display(value):>{width},}"
