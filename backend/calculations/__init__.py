"""
Stock P&L calculation engine — pure Python, zero framework dependencies.

Ledger in, numbers out. Import nothing from Django here, ever.

    from calculations import replay, get_plan, build_report, Transaction, TxnType

Design rules enforced throughout:
  * Decimal everywhere; floats raise TypeError in money paths.
  * Weighted Average Cost drives every displayed figure.
  * FIFO allocations are recorded alongside, for tax reporting.
  * Position/lots are a projection, always rebuildable from the ledger.
  * Charge rates are data, never constants.
"""

from .breakeven import net_proceeds_at, sell_charges_at, solve_breakeven
from .charges import ChargeEngine, ChargePlan, Component, ENGINE
from .engine import (
    InsufficientQuantity, InvalidTransaction, LedgerError, ReplayResult,
    ledger_hash, replay, replay_portfolio,
)
from .models import (
    Allocation, Basis, CAType, ChargeBreakdown, ChargeLine, CorporateAction,
    Exchange, LONG_TERM_DAYS, Lot, Position, Rounding, Segment, Side, Term,
    Transaction, TxnType,
)
from .money import D, display, money, qty
from .plans import RATES_VERIFIED_ON, ZERO_CHARGE_PLAN, get_plan, list_plans
from .reporting import LotReport, PositionReport, build_report
from .returns import xirr

__all__ = [
    "D", "display", "money", "qty",
    "Transaction", "TxnType", "CorporateAction", "CAType", "Exchange",
    "Side", "Segment", "Basis", "Rounding", "Term", "LONG_TERM_DAYS",
    "Lot", "Position", "Allocation", "ChargeLine", "ChargeBreakdown",
    "Component", "ChargePlan", "ChargeEngine", "ENGINE",
    "get_plan", "list_plans", "ZERO_CHARGE_PLAN", "RATES_VERIFIED_ON",
    "replay", "replay_portfolio", "ReplayResult", "ledger_hash",
    "LedgerError", "InvalidTransaction", "InsufficientQuantity",
    "solve_breakeven", "sell_charges_at", "net_proceeds_at",
    "build_report", "PositionReport", "LotReport", "xirr",
]

__version__ = "1.0.0"
