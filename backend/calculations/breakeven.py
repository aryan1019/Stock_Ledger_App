"""
Break-even solver.

Break-even is a FIXED POINT, not a formula: percentage sell charges depend on
the sell price, which is the thing being solved for. With caps, floors and
nearest-rupee rounding in the charge plan, the closed form is only an
approximation — so we bisect, then correct upward for the step discontinuity
introduced by STT's rupee rounding.

Break-even is ALWAYS rounded UP. Rounding it down yields a losing price.
"""

from __future__ import annotations

from decimal import Decimal

from .charges import ChargePlan, ENGINE
from .models import Side
from .money import D, ZERO, round_up_price

PENNY = Decimal("0.01")
_TOLERANCE = Decimal("0.00001")
_MAX_ITER = 300


def sell_charges_at(quantity: Decimal, price: Decimal, plan: ChargePlan) -> Decimal:
    """All-in exit charges for selling `quantity` at `price`, including DP charge."""
    return ENGINE.total(
        quantity=D(quantity), price=D(price),
        side=Side.SELL, plan=plan, include_day_level=True,
    )


def net_proceeds_at(quantity: Decimal, price: Decimal, plan: ChargePlan) -> Decimal:
    quantity, price = D(quantity), D(price)
    return quantity * price - sell_charges_at(quantity, price, plan)


def closed_form_seed(quantity: Decimal, target: Decimal, plan: ChargePlan) -> Decimal:
    """
    P = (C + F) / (Q * (1 - r))

    Used only to seed the bisection bracket. Ignores caps, floors and rounding,
    so it is not accurate enough to return directly.
    """
    quantity, target = D(quantity), D(target)
    if quantity == 0:
        return ZERO

    r = ZERO
    flat = ZERO
    gst = plan.component("GST")
    gst_rate = gst.rate if gst else ZERO
    gst_base = set(gst.of) if gst else set()

    for c in plan.components:
        if c.code == "GST" or not c.applies_to(Side.SELL):
            continue
        multiplier = (1 + gst_rate) if c.code in gst_base else D(1)
        if c.rate is not None:
            r += c.rate * multiplier
        elif c.amount is not None:
            flat += c.amount * multiplier

    denom = quantity * (D(1) - r)
    if denom <= 0:
        raise ValueError("Sell-side charge rates sum to >= 100% of turnover.")
    return (target + flat) / denom


def solve_breakeven(quantity: Decimal, cost_basis: Decimal, plan: ChargePlan,
                    extra_to_recover: Decimal = ZERO) -> Decimal:
    """
    Lowest 2dp price at which net proceeds >= cost_basis + extra_to_recover.

    extra_to_recover carries accumulated realized LOSSES, producing the
    "recovery break-even" — the price that also claws back booked losses.
    """
    quantity = D(quantity)
    if quantity <= 0:
        return ZERO
    target = D(cost_basis) + D(extra_to_recover)

    lo = target / quantity                      # cannot break even below this
    hi = max(closed_form_seed(quantity, target, plan) * D("1.05"), lo + D(10))

    guard = 0
    while net_proceeds_at(quantity, hi, plan) < target and guard < 60:
        hi *= 2
        guard += 1

    for _ in range(_MAX_ITER):
        if hi - lo <= _TOLERANCE:
            break
        mid = (lo + hi) / 2
        if net_proceeds_at(quantity, mid, plan) < target:
            lo = mid
        else:
            hi = mid

    price = round_up_price(hi)

    # Net proceeds is a STEP function, not a smooth curve: STT rounds to the
    # nearest rupee and brokerage may be capped. So bisection alone is not
    # enough — correct in both directions against the real charge engine.

    # 1. Walk UP until the price genuinely clears the target.
    steps = 0
    while net_proceeds_at(quantity, price, plan) < target and steps < 500:
        price += PENNY
        steps += 1

    # 2. Walk DOWN to undo the ROUND_CEILING overshoot (at most a few paisa),
    #    so the result is the lowest price that actually breaks even.
    steps = 0
    while steps < 5 and price > PENNY and \
            net_proceeds_at(quantity, price - PENNY, plan) >= target:
        price -= PENNY
        steps += 1

    return price
