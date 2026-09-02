"""
Replay orchestration — the only place that writes projection tables.

Nothing in here calculates anything. It loads the ledger, hands it to the
pure-Python engine, and persists what comes back. That separation is what
lets the engine stay framework-free and testable in milliseconds.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction as db_transaction

from calculations import (
    CAType, CorporateAction as EngineCA, D, Exchange, Transaction as EngineTxn,
    TxnType, build_report, replay, solve_breakeven,
)
from charges.models import BrokerPlan
from stocks.models import CorporateAction, PriceSnapshot, Stock
from transactions.models import Portfolio, Transaction

from .models import Lot, Position, SellAllocation


# --------------------------------------------------------------------------
# Plan resolution
# --------------------------------------------------------------------------

def resolve_plan(user, exchange: str = Exchange.NSE.value) -> BrokerPlan:
    """The user's chosen plan for an exchange, falling back to Zerodha."""
    chosen = user.default_broker_plan
    if chosen is not None:
        if chosen.exchange == exchange:
            return chosen
        sibling = BrokerPlan.objects.filter(
            broker=chosen.broker, plan=chosen.plan, exchange=exchange
        ).first()
        if sibling:
            return sibling
    return (
        BrokerPlan.objects.filter(broker="ZERODHA", plan="STANDARD", exchange=exchange).first()
        or BrokerPlan.objects.filter(exchange=exchange).first()
    )


def _plan_cache(user):
    cache: dict[str, BrokerPlan] = {}

    def get(exchange: str) -> BrokerPlan:
        if exchange not in cache:
            cache[exchange] = resolve_plan(user, exchange)
        return cache[exchange]

    return get


# --------------------------------------------------------------------------
# Ledger -> engine
# --------------------------------------------------------------------------

def _to_engine(row: Transaction) -> EngineTxn:
    return EngineTxn(
        stock=row.stock.symbol,
        type=TxnType(row.type),
        quantity=D(row.quantity),
        price=D(row.price),
        trade_date=row.trade_date,
        exchange=Exchange(row.exchange),
        sequence_no=row.sequence_no,
        id=str(row.id),
        charge_override=D(row.charge_override) if row.charge_override is not None else None,
    )


def _ca_to_engine(ca: CorporateAction) -> EngineCA:
    return EngineCA(
        stock=ca.stock.symbol,
        type=CAType(ca.type),
        ex_date=ca.ex_date,
        ratio_from=D(ca.ratio_from),
        ratio_to=D(ca.ratio_to),
        id=str(ca.id),
    )


# --------------------------------------------------------------------------
# Rebuild
# --------------------------------------------------------------------------

@db_transaction.atomic
def rebuild(user, stock: Stock, portfolio: Portfolio | None = None) -> Position | None:
    """
    Discard and rebuild this stock's projection from the ledger.

    Called after every write. On a personal portfolio this is a few hundred
    rows and sub-millisecond, which is what makes backdating and corrections
    safe: order of entry cannot matter.
    """
    portfolio = portfolio or Portfolio.default_for(user)

    rows = list(
        Transaction.objects.owned_by(user)
        .filter(stock=stock, portfolio=portfolio, status=Transaction.ACTIVE)
        .select_related("stock", "broker_plan")
    )
    if not rows:
        Position.objects.filter(user=user, portfolio=portfolio, stock=stock).delete()
        return None

    cas = list(CorporateAction.objects.filter(stock=stock))
    plans = _plan_cache(user)
    by_id = {str(r.id): r for r in rows}

    def plan_resolver(engine_txn: EngineTxn):
        row = by_id[engine_txn.id]
        chosen = row.broker_plan or plans(row.exchange)
        return chosen.to_engine_plan()

    result = replay(
        [_to_engine(r) for r in rows],
        [_ca_to_engine(c) for c in cas],
        plan_resolver=plan_resolver,
    )
    pos = result.position

    # snapshot the itemised charges back onto each ledger row
    for txn_id, breakdown in result.charges.items():
        row = by_id[txn_id]
        row.charge_breakdown = breakdown.as_dict()
        row.total_charges = breakdown.total
        Transaction.objects.filter(pk=row.pk).update(
            charge_breakdown=row.charge_breakdown, total_charges=row.total_charges
        )

    exit_plan = plans(rows[-1].exchange).to_engine_plan()
    booked_loss = max(Decimal("0"), -pos.realized_pnl)

    db_pos, _ = Position.objects.update_or_create(
        user=user, portfolio=portfolio, stock=stock,
        defaults={
            "quantity": pos.quantity,
            "cost_basis": pos.cost_basis,
            "average_cost": pos.average_cost,
            "realized_pnl": pos.realized_pnl,
            "realized_pnl_fifo": pos.realized_pnl_fifo,
            "total_charges_paid": pos.total_charges_paid,
            "dividends": pos.dividends,
            "break_even": (
                solve_breakeven(pos.quantity, pos.cost_basis, exit_plan)
                if pos.quantity > 0 else Decimal("0")
            ),
            "recovery_break_even": (
                solve_breakeven(pos.quantity, pos.cost_basis, exit_plan,
                                extra_to_recover=booked_loss)
                if pos.quantity > 0 else Decimal("0")
            ),
            "ledger_hash": result.ledger_hash,
        },
    )

    # projections are disposable: wipe and rewrite
    Lot.objects.filter(position=db_pos).delete()
    lot_pk = {}
    for lot in pos.lots:
        obj = Lot.objects.create(
            user=user, position=db_pos, source_transaction_id=lot.source_txn_id,
            original_qty=lot.original_qty, remaining_qty=lot.remaining_qty,
            buy_price=lot.buy_price, buy_charges=lot.buy_charges,
            cost_per_share=lot.cost_per_share,
            break_even=(
                solve_breakeven(lot.remaining_qty, lot.remaining_cost_basis, exit_plan)
                if lot.remaining_qty > 0 else Decimal("0")
            ),
            acquisition_date=lot.acquisition_date,
        )
        lot_pk[lot.id] = obj.pk

    SellAllocation.objects.filter(lot__position=db_pos).delete()
    for a in pos.allocations:
        if a.lot_id not in lot_pk:
            continue
        SellAllocation.objects.create(
            user=user, sell_transaction_id=a.sell_txn_id, lot_id=lot_pk[a.lot_id],
            qty=a.qty, fifo_cost_basis=a.fifo_cost_basis, fifo_realized_pnl=a.fifo_realized_pnl,
            wac_cost_basis=a.wac_cost_basis, wac_realized_pnl=a.wac_realized_pnl,
            holding_days=a.holding_days, term=a.term.value,
        )

    return db_pos


def rebuild_all(user, portfolio: Portfolio | None = None):
    portfolio = portfolio or Portfolio.default_for(user)
    stock_ids = (
        Transaction.objects.owned_by(user)
        .filter(portfolio=portfolio, status=Transaction.ACTIVE)
        .values_list("stock_id", flat=True).distinct()
    )
    return [rebuild(user, Stock.objects.get(pk=sid), portfolio) for sid in stock_ids]


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def current_price(user, stock: Stock) -> Decimal | None:
    snap = PriceSnapshot.objects.owned_by(user).filter(stock=stock).first()
    return snap.price if snap else None


def position_report(user, stock: Stock, portfolio: Portfolio | None = None):
    """
    Full report for the Stock Detail screen. Re-runs replay in memory so the
    numbers are always derived, never read from a possibly stale projection.
    """
    portfolio = portfolio or Portfolio.default_for(user)
    rows = list(
        Transaction.objects.owned_by(user)
        .filter(stock=stock, portfolio=portfolio, status=Transaction.ACTIVE)
    )
    if not rows:
        return None

    cas = list(CorporateAction.objects.filter(stock=stock))
    plans = _plan_cache(user)
    by_id = {str(r.id): r for r in rows}

    def plan_resolver(engine_txn: EngineTxn):
        row = by_id[engine_txn.id]
        return (row.broker_plan or plans(row.exchange)).to_engine_plan()

    result = replay(
        [_to_engine(r) for r in rows],
        [_ca_to_engine(c) for c in cas],
        plan_resolver=plan_resolver,
    )
    price = current_price(user, stock) or result.position.average_cost
    exit_plan = plans(rows[-1].exchange).to_engine_plan()
    return build_report(result.position, price, exit_plan, as_of=date.today())
