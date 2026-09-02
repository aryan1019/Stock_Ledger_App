"""
The core accounting rules. If any of these fail, the app is lying to the user.
"""

from datetime import date

import pytest
from conftest import buy, sell, opening, DAY

from calculations import (
    D, InsufficientQuantity, InvalidTransaction, TxnType, replay,
)


def test_single_buy_average_equals_price(nocharge):
    pos = replay([buy(10, "100")], plan=nocharge).position
    assert pos.quantity == D(10)
    assert pos.average_cost == D("100")


def test_two_buys_produce_weighted_average(nocharge):
    pos = replay([buy(10, "100"), buy(6, "150", day=1)], plan=nocharge).position
    assert pos.quantity == D(16)
    assert pos.average_cost == D("118.75")
    assert pos.cost_basis == D("1900")


def test_sell_does_not_change_remaining_average(nocharge):
    """THE central rule. A SELL reduces quantity; it never moves the average."""
    pos = replay(
        [buy(10, "100"), buy(6, "150", day=1), sell(6, "130", day=2)],
        plan=nocharge,
    ).position
    assert pos.quantity == D(10)
    assert pos.average_cost == D("118.75")          # unchanged
    assert pos.realized_pnl == D("67.50")           # (130 - 118.75) * 6
    assert pos.cost_basis == D("1187.50")


def test_buy_after_sell_uses_true_remaining_cost(nocharge):
    """Realized profit must NOT lower the new average."""
    pos = replay(
        [buy(10, "100"), buy(6, "150", day=1),
         sell(6, "130", day=2), buy(10, "150", day=3)],
        plan=nocharge,
    ).position
    assert pos.quantity == D(20)
    assert pos.average_cost == D("134.375")
    assert pos.realized_pnl == D("67.50")           # still separate


def test_same_day_sell_then_buy_does_not_net_profit_into_cost(nocharge):
    """The exact broker behaviour this application exists to avoid."""
    pos = replay(
        [buy(10, "100"), sell(10, "120", seq=1), buy(10, "110", seq=2)],
        plan=nocharge,
    ).position
    assert pos.realized_pnl == D("200")
    assert pos.average_cost == D("110")             # NOT 110 - 20 = 90
    assert pos.cost_basis == D("1100")
    # The broker-style number is available, but only for reconciliation.
    assert pos.broker_style_average == D("90")


def test_full_exit_then_rebuy_starts_fresh(nocharge):
    pos = replay(
        [buy(10, "100"), sell(10, "130", day=1), buy(5, "200", day=2)],
        plan=nocharge,
    ).position
    assert pos.quantity == D(5)
    assert pos.average_cost == D("200")
    assert pos.realized_pnl == D("300")


def test_sell_everything_zeroes_position_but_keeps_realized(nocharge):
    pos = replay([buy(10, "100"), sell(10, "130", day=1)], plan=nocharge).position
    assert pos.quantity == D(0)
    assert pos.cost_basis == D(0)
    assert pos.realized_pnl == D("300")
    assert len(pos.lots) == 1                       # history preserved


def test_buy_charges_are_capitalised_into_cost(zerodha):
    pos = replay([buy(5, "3899")], plan=zerodha).position
    assert pos.average_cost > D("3899")             # charges raise true cost
    assert pos.cost_basis == D(5) * D("3899") + pos.total_charges_paid


def test_fifo_allocation_is_recorded_alongside_wac(nocharge):
    """WAC drives display; FIFO is stored for tax. Both are correct."""
    res = replay(
        [buy(10, "100"), buy(6, "150", day=1), sell(6, "130", day=2)],
        plan=nocharge,
    )
    pos = res.position
    assert pos.realized_pnl == D("67.50")           # WAC, displayed
    assert pos.realized_pnl_fifo == D("180")        # FIFO, stored
    assert len(pos.allocations) == 1
    alloc = pos.allocations[0]
    assert alloc.qty == D(6)
    assert alloc.fifo_cost_basis == D("600")        # all from the @100 lot
    assert pos.lots[0].remaining_qty == D(4)
    assert pos.lots[1].remaining_qty == D(6)


def test_partial_sell_spans_multiple_lots_in_fifo_order(nocharge):
    res = replay(
        [buy(10, "100"), buy(6, "150", day=1), sell(12, "200", day=2)],
        plan=nocharge,
    )
    allocs = res.position.allocations
    assert [a.qty for a in allocs] == [D(10), D(2)]
    assert res.position.lots[0].remaining_qty == D(0)
    assert res.position.lots[1].remaining_qty == D(4)
    assert sum(a.qty for a in allocs) == D(12)


def test_opening_balance_enables_immediate_sell(nocharge):
    pos = replay(
        [opening(50, "80"), sell(20, "100", day=1)], plan=nocharge
    ).position
    assert pos.quantity == D(30)
    assert pos.average_cost == D("80")
    assert pos.realized_pnl == D("400")


def test_opening_balance_must_come_first(nocharge):
    with pytest.raises(InvalidTransaction, match="earliest"):
        replay([buy(10, "100"), opening(5, "90", day=1)], plan=nocharge)


def test_oversell_is_rejected_with_a_helpful_message(nocharge):
    with pytest.raises(InsufficientQuantity) as e:
        replay([buy(4, "100"), sell(10, "130", day=1)], plan=nocharge)
    assert "you hold 4" in str(e.value)
    assert "opening balance" in str(e.value)        # offers the remedy


def test_negative_and_zero_inputs_rejected(nocharge):
    with pytest.raises(InvalidTransaction):
        replay([buy(0, "100")], plan=nocharge)
    with pytest.raises(InvalidTransaction):
        replay([buy(10, "0")], plan=nocharge)


def test_float_in_money_path_is_rejected():
    from calculations import D
    with pytest.raises(TypeError, match="float"):
        D(3899.00)


def test_multiple_stocks_are_independent(nocharge):
    from calculations import replay_portfolio
    txns = [
        buy(10, "100", stock="KAYNES"),
        buy(20, "50", stock="TATAMOTORS", day=1),
        sell(5, "120", stock="KAYNES", day=2),
    ]
    res = replay_portfolio(txns, plan=nocharge)
    assert res["KAYNES"].position.quantity == D(5)
    assert res["TATAMOTORS"].position.quantity == D(20)
    assert res["TATAMOTORS"].position.realized_pnl == D(0)
