"""XIRR — annualised return from a dated cash-flow series."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .money import D, ZERO


def xirr(cashflows: list[tuple[date, Decimal]],
         tolerance: Decimal = Decimal("0.0000001")) -> Decimal:
    """
    cashflows: [(date, amount)] — negative for money out (buys),
    positive for money in (sells, dividends, current market value).

    Solved by bisection on the discount rate. Returns a decimal fraction
    (0.184 == 18.4% p.a.), or ZERO when undefined.
    """
    if len(cashflows) < 2:
        return ZERO
    flows = sorted(cashflows, key=lambda x: x[0])
    t0 = flows[0][0]

    if not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        return ZERO

    def npv(rate: Decimal) -> Decimal:
        total = ZERO
        for d, amount in flows:
            years = (d - t0).days / 365.0
            discount = D(str((1.0 + float(rate)) ** years))
            total += D(amount) / discount
        return total

    lo, hi = D("-0.9999"), D("100")
    if npv(lo) * npv(hi) > 0:
        return ZERO

    for _ in range(300):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < tolerance:
            return mid
        if npv(lo) * v < 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2
