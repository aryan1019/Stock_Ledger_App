"""
Charge engine.

A ChargePlan is a versioned list of Components. A Component is evaluated
against a transaction and yields one ChargeLine. Rates are DATA, never
constants — see plans.py for the seeded broker plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from .models import Basis, ChargeBreakdown, ChargeLine, Rounding, Side
from .money import D, ZERO, round_nearest_rupee, round_two_dp


@dataclass
class Component:
    code: str
    label: str
    basis: Basis
    side: Side = Side.BOTH
    rate: Optional[Decimal] = None        # PERCENT_TURNOVER / PERCENT_OF
    amount: Optional[Decimal] = None      # FLAT_* / PER_SHARE
    cap: Optional[Decimal] = None         # "lower of X or Y%"
    floor: Optional[Decimal] = None       # "...minimum Z"
    of: tuple[str, ...] = ()              # PERCENT_OF base component codes
    rounding: Rounding = Rounding.TWO_DP
    gst_inclusive: bool = False           # amount already contains GST

    def __post_init__(self):
        for f in ("rate", "amount", "cap", "floor"):
            v = getattr(self, f)
            if v is not None:
                setattr(self, f, D(v))

    def applies_to(self, side: Side) -> bool:
        return self.side == Side.BOTH or self.side == side


@dataclass
class ChargePlan:
    broker: str
    plan: str
    segment: str
    exchange: str
    effective_from: date
    components: list[Component] = field(default_factory=list)
    currency: str = "INR"
    display_name: str = ""      # human label shown in the UI plan picker
    notes: str = ""             # eligibility / promo caveats the user must see
    verified: bool = False      # True once checked against a real broker bill

    @property
    def id(self) -> str:
        return f"{self.broker}:{self.plan}:{self.segment}:{self.exchange}"

    @property
    def label(self) -> str:
        return self.display_name or f"{self.broker} {self.plan}"

    def component(self, code: str) -> Optional[Component]:
        return next((c for c in self.components if c.code == code), None)


def _apply_rounding(value: Decimal, mode: Rounding) -> Decimal:
    if mode == Rounding.NEAREST_RUPEE:
        return round_nearest_rupee(value)
    if mode == Rounding.TWO_DP:
        return round_two_dp(value)
    return value


class ChargeEngine:
    """
    Stateless. compute() returns an itemised breakdown which the caller
    snapshots onto the transaction so later rate changes never rewrite history.
    """

    def compute(
        self,
        *,
        quantity: Decimal,
        price: Decimal,
        side: Side,
        plan: ChargePlan,
        include_day_level: bool = True,
    ) -> ChargeBreakdown:
        """
        include_day_level=False suppresses FLAT_PER_SCRIP_PER_DAY components
        (DP charges), which are levied once per stock per day regardless of
        how many orders were placed. The replay engine decides.
        """
        quantity = D(quantity)
        price = D(price)
        turnover = quantity * price

        breakdown = ChargeBreakdown()
        computed: dict[str, Decimal] = {}

        # Pass 1 — everything except PERCENT_OF (GST needs the others first).
        for c in plan.components:
            if c.basis == Basis.PERCENT_OF:
                continue
            if not c.applies_to(side):
                continue
            if c.basis == Basis.FLAT_PER_SCRIP_PER_DAY and not include_day_level:
                continue

            if c.basis == Basis.FLAT_PER_ORDER:
                raw = c.amount or ZERO
            elif c.basis == Basis.FLAT_PER_SCRIP_PER_DAY:
                raw = c.amount or ZERO
            elif c.basis == Basis.PER_SHARE:
                raw = (c.amount or ZERO) * quantity
            elif c.basis == Basis.PERCENT_TURNOVER:
                raw = (c.rate or ZERO) * turnover
            else:
                raise ValueError(f"Unsupported basis {c.basis}")

            # "lower of Rs 20 or 0.1%"  ->  cap;  "...minimum Rs 5"  ->  floor
            if c.cap is not None:
                raw = min(raw, c.cap)
            if c.floor is not None:
                raw = max(raw, c.floor)

            amount = _apply_rounding(raw, c.rounding)
            computed[c.code] = amount
            breakdown.lines.append(ChargeLine(c.code, c.label, amount))

        # Pass 2 — PERCENT_OF (GST), evaluated on the ROUNDED pass-1 results.
        for c in plan.components:
            if c.basis != Basis.PERCENT_OF or not c.applies_to(side):
                continue
            base = sum((computed.get(code, ZERO) for code in c.of), ZERO)
            amount = _apply_rounding((c.rate or ZERO) * base, c.rounding)
            computed[c.code] = amount
            breakdown.lines.append(ChargeLine(c.code, c.label, amount))

        return breakdown

    def total(self, **kwargs) -> Decimal:
        return self.compute(**kwargs).total


ENGINE = ChargeEngine()
