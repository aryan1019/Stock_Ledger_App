import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations import (  # noqa: E402
    D, Exchange, Transaction, TxnType, ZERO_CHARGE_PLAN, get_plan,
)

DAY = date(2026, 8, 21)


def txn(type_, qty, price, day=0, stock="KAYNES", seq=0, **kw):
    """Terse transaction builder. `day` is an offset in days from DAY."""
    return Transaction(
        stock=stock,
        type=type_,
        quantity=D(qty),
        price=D(price),
        trade_date=date.fromordinal(DAY.toordinal() + day),
        sequence_no=seq,
        **kw,
    )


def buy(qty, price, day=0, **kw):
    return txn(TxnType.BUY, qty, price, day, **kw)


def sell(qty, price, day=0, **kw):
    return txn(TxnType.SELL, qty, price, day, **kw)


def opening(qty, price, day=0, **kw):
    return txn(TxnType.OPENING_BALANCE, qty, price, day, **kw)


@pytest.fixture
def nocharge():
    """Zero-charge plan — isolates the accounting model from the charge model."""
    return ZERO_CHARGE_PLAN


@pytest.fixture
def zerodha():
    return get_plan("ZERODHA", "STANDARD", Exchange.NSE)


@pytest.fixture
def angel():
    return get_plan("ANGEL_ONE", "STANDARD", Exchange.NSE)
