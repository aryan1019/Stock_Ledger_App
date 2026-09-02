"""
Reporting layer: turns a replayed Position + a current price into every
number the UI shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .breakeven import net_proceeds_at, sell_charges_at, solve_breakeven
from .charges import ChargePlan
from .models import Lot, Position, Term
from .money import D, ZERO, display


@dataclass
class LotReport:
    lot_id: str
    acquisition_date: date
    original_qty: Decimal
    remaining_qty: Decimal
    buy_price: Decimal
    cost_per_share: Decimal
    cost_basis: Decimal
    break_even: Decimal
    holding_days: int
    term: Term
    days_to_long_term: int
    unrealized_pnl: Decimal


@dataclass
class PositionReport:
    stock: str
    as_of: date
    quantity: Decimal
    cost_basis: Decimal
    average_cost: Decimal
    current_price: Decimal

    break_even: Decimal
    recovery_break_even: Decimal
    exit_charges: Decimal

    realized_pnl: Decimal
    realized_pnl_fifo: Decimal
    unrealized_pnl_gross: Decimal
    unrealized_pnl_net: Decimal
    total_pnl: Decimal
    dividends: Decimal

    total_charges_paid: Decimal
    market_value: Decimal
    return_pct: Decimal
    broker_style_average: Decimal

    lots: list[LotReport] = field(default_factory=list)

    def summary(self) -> str:
        w = 26
        rows = [
            ("Stock", self.stock),
            ("Quantity", f"{display(self.quantity)}"),
            ("Average cost", f"{display(self.average_cost):,}"),
            ("Cost basis (invested)", f"{display(self.cost_basis):,}"),
            ("Current price", f"{display(self.current_price):,}"),
            ("Market value", f"{display(self.market_value):,}"),
            ("", ""),
            ("Break-even", f"{display(self.break_even):,}"),
            ("Recovery break-even", f"{display(self.recovery_break_even):,}"),
            ("Exit charges if sold now", f"{display(self.exit_charges):,}"),
            ("", ""),
            ("Realized P&L", f"{display(self.realized_pnl):,}"),
            ("Unrealized P&L (gross)", f"{display(self.unrealized_pnl_gross):,}"),
            ("Unrealized P&L (net)", f"{display(self.unrealized_pnl_net):,}"),
            ("TOTAL P&L", f"{display(self.total_pnl):,}"),
            ("Return %", f"{display(self.return_pct)}%"),
            ("", ""),
            ("Total charges paid", f"{display(self.total_charges_paid):,}"),
            ("Broker-style avg (recon.)", f"{display(self.broker_style_average):,}"),
        ]
        out = []
        for k, v in rows:
            out.append("" if not k else f"  {k:<{w}} {v:>14}")
        return "\n".join(out)

    def breakeven_bar(self, width: int = 58) -> str:
        """The break-even visualisation, as a console approximation."""
        lo = min(self.average_cost, self.current_price) * D("0.97")
        hi = max(self.break_even, self.current_price) * D("1.03")
        span = hi - lo
        if span <= 0:
            return ""

        def pos(p):
            return int((D(p) - lo) / span * width)

        line = [" "] * (width + 1)
        for p, ch in ((self.average_cost, "A"), (self.break_even, "B"),
                      (self.current_price, "^")):
            i = max(0, min(width, pos(p)))
            line[i] = ch
        bar = "".join(line)
        legend = (f"  A = avg cost {display(self.average_cost):,}   "
                  f"B = break-even {display(self.break_even):,}   "
                  f"^ = current {display(self.current_price):,}")
        return f"  LOSS |{bar}| PROFIT\n{legend}"


def build_report(position: Position, current_price, plan: ChargePlan,
                 as_of: date) -> PositionReport:
    price = D(current_price)
    qty = position.quantity

    if qty > 0:
        exit_charges = sell_charges_at(qty, price, plan)
        net_now = net_proceeds_at(qty, price, plan)
        break_even = solve_breakeven(qty, position.cost_basis, plan)
        booked_loss = max(ZERO, -position.realized_pnl)
        recovery = solve_breakeven(qty, position.cost_basis, plan,
                                   extra_to_recover=booked_loss)
        unreal_gross = (price - position.average_cost) * qty
        unreal_net = net_now - position.cost_basis
    else:
        exit_charges = net_now = break_even = recovery = ZERO
        unreal_gross = unreal_net = ZERO

    invested = position.cost_basis if position.cost_basis > 0 else ZERO
    total_pnl = position.realized_pnl + unreal_gross
    ret = (total_pnl / invested * 100) if invested > 0 else ZERO

    lots = []
    for lot in position.open_lots:
        lot_be = solve_breakeven(lot.remaining_qty, lot.remaining_cost_basis, plan)
        lots.append(LotReport(
            lot_id=lot.id,
            acquisition_date=lot.acquisition_date,
            original_qty=lot.original_qty,
            remaining_qty=lot.remaining_qty,
            buy_price=lot.buy_price,
            cost_per_share=lot.cost_per_share,
            cost_basis=lot.remaining_cost_basis,
            break_even=lot_be,
            holding_days=lot.holding_days(as_of),
            term=lot.term(as_of),
            days_to_long_term=lot.days_to_long_term(as_of),
            unrealized_pnl=(price - lot.cost_per_share) * lot.remaining_qty,
        ))

    return PositionReport(
        stock=position.stock,
        as_of=as_of,
        quantity=qty,
        cost_basis=position.cost_basis,
        average_cost=position.average_cost,
        current_price=price,
        break_even=break_even,
        recovery_break_even=recovery,
        exit_charges=exit_charges,
        realized_pnl=position.realized_pnl,
        realized_pnl_fifo=position.realized_pnl_fifo,
        unrealized_pnl_gross=unreal_gross,
        unrealized_pnl_net=unreal_net,
        total_pnl=total_pnl,
        dividends=position.dividends,
        total_charges_paid=position.total_charges_paid,
        market_value=qty * price,
        return_pct=ret,
        broker_style_average=position.broker_style_average,
        lots=lots,
    )
