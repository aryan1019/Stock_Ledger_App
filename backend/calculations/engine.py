"""
The replay engine.

THE core architectural rule: the ledger is the only truth. Position, lots and
allocations are a PROJECTION — derived, disposable, and rebuilt from scratch
whenever anything changes. That is what makes backdating, corrections and
corporate actions safe.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable, Iterable, Optional, Sequence, Union

from .charges import ChargePlan, ENGINE
from .models import (
    Allocation, CAType, ChargeBreakdown, CorporateAction, Exchange, Lot,
    Position, Side, Transaction, TxnType,
)
from .money import D, ZERO

Event = Union[Transaction, CorporateAction]
PlanResolver = Callable[[Transaction], ChargePlan]


# --------------------------------------------------------------------------
# Errors — every one carries the remedy, never a bare failure
# --------------------------------------------------------------------------

class LedgerError(ValueError):
    pass


def _q(value) -> str:
    """Quantity for humans: 10 rather than 10.000000."""
    text = format(D(value).normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class InsufficientQuantity(LedgerError):
    def __init__(self, stock, held, requested, on):
        self.held, self.requested = held, requested
        super().__init__(
            f"Cannot sell {_q(requested)} {stock} on {on}: you hold {_q(held)} on that date. "
            f"Add the missing BUY, or record an opening balance first."
        )


class InvalidTransaction(LedgerError):
    pass


# --------------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------------

@dataclass
class ReplayResult:
    position: Position
    charges: dict           # txn_id -> ChargeBreakdown
    ledger_hash: str

    def breakdown(self, txn: Transaction) -> ChargeBreakdown:
        return self.charges[txn.id]


def ledger_hash(events: Sequence[Event]) -> str:
    """Cheap staleness check: if this changes, the projection must be rebuilt."""
    h = hashlib.sha256()
    for e in sorted(events, key=lambda x: x.sort_key):
        h.update(f"{e.id}|{e.sort_key}".encode())
    return h.hexdigest()[:16]


def replay(
    transactions: Iterable[Transaction],
    corporate_actions: Iterable[CorporateAction] = (),
    *,
    plan: Optional[ChargePlan] = None,
    plan_resolver: Optional[PlanResolver] = None,
    as_of: Optional[date] = None,
) -> ReplayResult:
    """
    Rebuild a stock's entire position from its ledger.

    Deterministic: the same ledger always produces byte-identical output,
    regardless of the order rows were inserted.
    """
    txns = list(transactions)
    cas = list(corporate_actions)
    if not txns and not cas:
        raise InvalidTransaction("Nothing to replay.")

    stocks = {t.stock for t in txns} | {c.stock for c in cas}
    if len(stocks) > 1:
        raise InvalidTransaction(
            f"replay() handles one stock at a time; got {sorted(stocks)}. "
            f"Use replay_portfolio()."
        )
    stock = stocks.pop()

    if plan_resolver is None:
        if plan is None:
            raise InvalidTransaction("Provide either plan= or plan_resolver=.")
        plan_resolver = lambda _t: plan  # noqa: E731

    events: list[Event] = sorted([*txns, *cas], key=lambda e: e.sort_key)

    position = Position(stock=stock)
    charges: dict[str, ChargeBreakdown] = {}
    day_level_seen: set[tuple[str, date, Side]] = set()
    seen_first_txn = False

    for event in events:
        if isinstance(event, CorporateAction):
            _apply_corporate_action(position, event)
            continue

        txn = event
        _validate(txn, position, seen_first_txn)
        seen_first_txn = True

        if txn.type == TxnType.DIVIDEND:
            position.dividends += txn.quantity * txn.price
            charges[txn.id] = ChargeBreakdown()
            continue

        key = (txn.stock, txn.trade_date, txn.side)
        include_day_level = key not in day_level_seen
        breakdown = _charges_for(txn, plan_resolver(txn), include_day_level)
        if include_day_level and breakdown.get("DP") > 0:
            day_level_seen.add(key)

        charges[txn.id] = breakdown
        position.total_charges_paid += breakdown.total

        if txn.type in (TxnType.BUY, TxnType.OPENING_BALANCE):
            _apply_buy(position, txn, breakdown.total)
        elif txn.type == TxnType.SELL:
            _apply_sell(position, txn, breakdown.total)

    return ReplayResult(position=position, charges=charges,
                        ledger_hash=ledger_hash(events))


def replay_portfolio(
    transactions: Iterable[Transaction],
    corporate_actions: Iterable[CorporateAction] = (),
    **kwargs,
) -> dict[str, ReplayResult]:
    """Replay every stock independently. Positions never interact."""
    txns = list(transactions)
    cas = list(corporate_actions)
    out = {}
    for stock in sorted({t.stock for t in txns}):
        out[stock] = replay(
            [t for t in txns if t.stock == stock],
            [c for c in cas if c.stock == stock],
            **kwargs,
        )
    return out


# --------------------------------------------------------------------------
# Event handlers
# --------------------------------------------------------------------------

def _validate(txn: Transaction, position: Position, seen_first_txn: bool) -> None:
    if txn.quantity <= 0:
        raise InvalidTransaction(f"Quantity must be > 0, got {txn.quantity}.")
    if txn.price <= 0:
        raise InvalidTransaction(f"Price must be > 0, got {txn.price}.")
    if txn.type == TxnType.OPENING_BALANCE and seen_first_txn:
        raise InvalidTransaction(
            "OPENING_BALANCE must be the earliest transaction for a stock."
        )
    if txn.type == TxnType.SELL and txn.quantity > position.quantity:
        raise InsufficientQuantity(
            txn.stock, position.quantity, txn.quantity, txn.trade_date
        )


def _charges_for(txn: Transaction, plan: ChargePlan,
                 include_day_level: bool) -> ChargeBreakdown:
    if txn.charge_override is not None:
        from .models import ChargeLine
        return ChargeBreakdown([ChargeLine("MANUAL", "Charges (manual)",
                                           txn.charge_override)])
    if txn.type == TxnType.OPENING_BALANCE:
        return ChargeBreakdown()          # historical holding, charges unknown
    return ENGINE.compute(
        quantity=txn.quantity, price=txn.price, side=txn.side,
        plan=plan, include_day_level=include_day_level,
    )


def _apply_buy(position: Position, txn: Transaction, charges: Decimal) -> None:
    """Buy-side charges are CAPITALISED into cost basis."""
    position.lots.append(Lot(
        source_txn_id=txn.id,
        stock=txn.stock,
        original_qty=txn.quantity,
        remaining_qty=txn.quantity,
        buy_price=txn.price,
        buy_charges=charges,
        acquisition_date=txn.trade_date,
    ))
    position.quantity += txn.quantity
    position.cost_basis += txn.quantity * txn.price + charges


def _apply_sell(position: Position, txn: Transaction, charges: Decimal) -> None:
    """
    WAC drives the displayed numbers; FIFO allocation is recorded alongside.

    The remaining average is UNCHANGED by construction: we remove
    average_cost * sold_qty from the basis and sold_qty from the quantity,
    so the ratio is preserved exactly.
    """
    avg = position.average_cost
    gross = txn.quantity * txn.price
    cost_of_sold = avg * txn.quantity

    realized = gross - charges - cost_of_sold
    position.realized_pnl += realized

    # FIFO allocation trail — stored for tax reporting, not displayed in V1.
    remaining = txn.quantity
    for lot in position.lots:
        if remaining <= 0:
            break
        if lot.remaining_qty <= 0:
            continue
        take = min(lot.remaining_qty, remaining)
        share = take / txn.quantity

        slice_gross = txn.price * take
        slice_charges = charges * share
        fifo_cost = lot.cost_per_share * take
        wac_cost = avg * take

        position.allocations.append(Allocation(
            sell_txn_id=txn.id,
            lot_id=lot.id,
            qty=take,
            fifo_cost_basis=fifo_cost,
            fifo_realized_pnl=slice_gross - slice_charges - fifo_cost,
            wac_cost_basis=wac_cost,
            wac_realized_pnl=slice_gross - slice_charges - wac_cost,
            holding_days=lot.holding_days(txn.trade_date),
            term=lot.term(txn.trade_date),
        ))
        position.realized_pnl_fifo += slice_gross - slice_charges - fifo_cost

        lot.remaining_qty -= take
        remaining -= take

    position.quantity -= txn.quantity
    position.cost_basis -= cost_of_sold

    # Guard against Decimal dust on a full exit.
    if position.quantity == 0:
        position.cost_basis = ZERO


def _apply_corporate_action(position: Position, ca: CorporateAction) -> None:
    """
    Quantity scales, per-share cost scales inversely, COST BASIS IS UNCHANGED.
    Acquisition dates are preserved — a split does not reset holding period.
    """
    if ca.type == CAType.SYMBOL_CHANGE:
        return
    factor = ca.factor
    if factor <= 0:
        raise InvalidTransaction(f"Corporate action factor must be > 0, got {factor}.")

    for lot in position.lots:
        lot.original_qty *= factor
        lot.remaining_qty *= factor
        lot.buy_price /= factor

    position.quantity *= factor
    # position.cost_basis intentionally unchanged
