"""
Domain models. Plain dataclasses — no Django, no ORM, no framework.

The ledger (Transaction, CorporateAction) is INPUT.
Everything else (Lot, Allocation, Position) is DERIVED and rebuildable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from .money import D, ZERO, display


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class TxnType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    OPENING_BALANCE = "OPENING_BALANCE"
    DIVIDEND = "DIVIDEND"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    BOTH = "BOTH"


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"


class Segment(str, Enum):
    EQUITY_DELIVERY = "EQUITY_DELIVERY"
    EQUITY_INTRADAY = "EQUITY_INTRADAY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"


class Basis(str, Enum):
    FLAT_PER_ORDER = "FLAT_PER_ORDER"
    PERCENT_TURNOVER = "PERCENT_TURNOVER"
    PER_SHARE = "PER_SHARE"
    PERCENT_OF = "PERCENT_OF"
    FLAT_PER_SCRIP_PER_DAY = "FLAT_PER_SCRIP_PER_DAY"


class Rounding(str, Enum):
    NONE = "NONE"
    TWO_DP = "TWO_DP"
    NEAREST_RUPEE = "NEAREST_RUPEE"


class CAType(str, Enum):
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"


class Term(str, Enum):
    SHORT = "SHORT"
    LONG = "LONG"


LONG_TERM_DAYS = 365   # configurable; equity threshold


def _uid() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------
# Ledger (input)
# --------------------------------------------------------------------------

@dataclass
class Transaction:
    """An immutable ledger row."""
    stock: str
    type: TxnType
    quantity: Decimal
    price: Decimal
    trade_date: date
    exchange: Exchange = Exchange.NSE
    sequence_no: int = 0
    id: str = field(default_factory=_uid)
    plan_id: Optional[str] = None          # None -> use the default plan
    charge_override: Optional[Decimal] = None   # for imports / opening balances
    notes: str = ""

    def __post_init__(self):
        self.quantity = D(self.quantity)
        self.price = D(self.price)
        if self.charge_override is not None:
            self.charge_override = D(self.charge_override)

    @property
    def turnover(self) -> Decimal:
        return self.quantity * self.price

    @property
    def side(self) -> Side:
        return Side.SELL if self.type == TxnType.SELL else Side.BUY

    @property
    def sort_key(self):
        return (self.trade_date, self.sequence_no, self.id)


@dataclass
class CorporateAction:
    """Applied to every lot at ex_date during replay."""
    stock: str
    type: CAType
    ex_date: date
    ratio_from: Decimal = D(1)
    ratio_to: Decimal = D(1)
    sequence_no: int = -1        # sorts before same-day transactions
    id: str = field(default_factory=_uid)
    new_symbol: str = ""

    def __post_init__(self):
        self.ratio_from = D(self.ratio_from)
        self.ratio_to = D(self.ratio_to)

    @property
    def factor(self) -> Decimal:
        """Multiplier applied to quantity. Cost basis is unchanged."""
        if self.type == CAType.SPLIT:
            # 1:5 split -> one share becomes five
            return self.ratio_to / self.ratio_from
        if self.type == CAType.BONUS:
            # 1:2 bonus -> one free share for every two held -> 1.5x
            return (self.ratio_from + self.ratio_to) / self.ratio_from
        return D(1)

    @property
    def trade_date(self) -> date:
        return self.ex_date

    @property
    def sort_key(self):
        return (self.ex_date, self.sequence_no, self.id)


# --------------------------------------------------------------------------
# Charges
# --------------------------------------------------------------------------

@dataclass
class ChargeLine:
    code: str
    label: str
    amount: Decimal


@dataclass
class ChargeBreakdown:
    lines: list[ChargeLine] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((l.amount for l in self.lines), ZERO)

    def get(self, code: str) -> Decimal:
        for l in self.lines:
            if l.code == code:
                return l.amount
        return ZERO

    def as_dict(self) -> dict:
        return {l.code: str(display(l.amount)) for l in self.lines}

    def table(self) -> str:
        rows = [f"  {l.label:<32} {display(l.amount):>10,}" for l in self.lines]
        rows.append(f"  {'TOTAL':<32} {display(self.total):>10,}")
        return "\n".join(rows)


# --------------------------------------------------------------------------
# Projection (derived — never a primary record)
# --------------------------------------------------------------------------

@dataclass
class Lot:
    """One acquisition event. Never merged, never erased."""
    source_txn_id: str
    stock: str
    original_qty: Decimal
    remaining_qty: Decimal
    buy_price: Decimal            # per-share price paid, excluding charges
    buy_charges: Decimal          # charges attributed to the ORIGINAL quantity
    acquisition_date: date
    id: str = field(default_factory=_uid)

    @property
    def original_cost_basis(self) -> Decimal:
        return self.original_qty * self.buy_price + self.buy_charges

    @property
    def cost_per_share(self) -> Decimal:
        if self.original_qty == 0:
            return ZERO
        return self.original_cost_basis / self.original_qty

    @property
    def remaining_cost_basis(self) -> Decimal:
        return self.cost_per_share * self.remaining_qty

    @property
    def is_closed(self) -> bool:
        return self.remaining_qty <= 0

    def holding_days(self, as_of: date) -> int:
        return (as_of - self.acquisition_date).days

    def term(self, as_of: date) -> Term:
        return Term.LONG if self.holding_days(as_of) >= LONG_TERM_DAYS else Term.SHORT

    def days_to_long_term(self, as_of: date) -> int:
        return max(0, LONG_TERM_DAYS - self.holding_days(as_of))


@dataclass
class Allocation:
    """FIFO trail: which lots a SELL consumed. Stored, not displayed in V1."""
    sell_txn_id: str
    lot_id: str
    qty: Decimal
    fifo_cost_basis: Decimal
    fifo_realized_pnl: Decimal
    wac_cost_basis: Decimal
    wac_realized_pnl: Decimal
    holding_days: int
    term: Term


@dataclass
class Position:
    """Derived state for one stock. Discardable and rebuildable from the ledger."""
    stock: str
    quantity: Decimal = ZERO
    cost_basis: Decimal = ZERO
    realized_pnl: Decimal = ZERO            # WAC — the displayed figure
    realized_pnl_fifo: Decimal = ZERO       # FIFO — stored for tax reporting
    total_charges_paid: Decimal = ZERO
    dividends: Decimal = ZERO
    lots: list[Lot] = field(default_factory=list)
    allocations: list[Allocation] = field(default_factory=list)

    @property
    def average_cost(self) -> Decimal:
        if self.quantity == 0:
            return ZERO
        return self.cost_basis / self.quantity

    @property
    def open_lots(self) -> list[Lot]:
        return [l for l in self.lots if not l.is_closed]

    @property
    def broker_style_average(self) -> Decimal:
        """
        What a broker app would show: realized profit netted into remaining cost.
        Displayed ONLY as a reconciliation aid. Never used in any calculation.
        """
        if self.quantity == 0:
            return ZERO
        return (self.cost_basis - self.realized_pnl) / self.quantity
