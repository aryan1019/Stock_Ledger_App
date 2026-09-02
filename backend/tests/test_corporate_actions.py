"""
Corporate actions. Without these, one stock split silently makes every
number in that position wrong and nothing warns the user.
"""

from datetime import date

import pytest
from conftest import buy, sell, DAY

from calculations import CAType, CorporateAction, D, LONG_TERM_DAYS, replay


def ca(type_, day, ratio_from=1, ratio_to=1, stock="KAYNES"):
    return CorporateAction(
        stock=stock, type=type_,
        ex_date=date.fromordinal(DAY.toordinal() + day),
        ratio_from=D(ratio_from), ratio_to=D(ratio_to),
    )


def test_split_multiplies_quantity_and_divides_average(nocharge):
    """1:5 split — 10 shares @ 100 becomes 50 shares @ 20. Cost basis unchanged."""
    pos = replay(
        [buy(10, "100")], [ca(CAType.SPLIT, day=1, ratio_from=1, ratio_to=5)],
        plan=nocharge,
    ).position
    assert pos.quantity == D(50)
    assert pos.average_cost == D("20")
    assert pos.cost_basis == D("1000")


def test_bonus_one_for_one_halves_the_average(nocharge):
    pos = replay(
        [buy(10, "100")], [ca(CAType.BONUS, day=1, ratio_from=1, ratio_to=1)],
        plan=nocharge,
    ).position
    assert pos.quantity == D(20)
    assert pos.average_cost == D("50")
    assert pos.cost_basis == D("1000")


def test_bonus_one_for_two_scales_by_one_and_a_half(nocharge):
    pos = replay(
        [buy(10, "100")], [ca(CAType.BONUS, day=1, ratio_from=2, ratio_to=1)],
        plan=nocharge,
    ).position
    assert pos.quantity == D(15)
    assert pos.cost_basis == D("1000")
    assert pos.average_cost == D("1000") / D(15)


def test_split_applies_to_every_lot_proportionally(nocharge):
    pos = replay(
        [buy(10, "100"), buy(6, "150", day=1)],
        [ca(CAType.SPLIT, day=2, ratio_from=1, ratio_to=2)],
        plan=nocharge,
    ).position
    assert [l.remaining_qty for l in pos.lots] == [D(20), D(12)]
    assert [l.buy_price for l in pos.lots] == [D(50), D(75)]
    assert pos.quantity == D(32)
    assert pos.cost_basis == D("1900")


def test_split_does_not_reset_holding_period(nocharge):
    """A split must not turn a long-term holding back into a short-term one."""
    pos = replay(
        [buy(10, "100", day=0)],
        [ca(CAType.SPLIT, day=400, ratio_from=1, ratio_to=5)],
        plan=nocharge,
    ).position
    as_of = date.fromordinal(DAY.toordinal() + 400)
    lot = pos.lots[0]
    assert lot.acquisition_date == DAY
    assert lot.holding_days(as_of) == 400
    assert lot.term(as_of).value == "LONG"


def test_selling_after_a_split_uses_the_adjusted_average(nocharge):
    pos = replay(
        [buy(10, "100"), sell(25, "30", day=2)],
        [ca(CAType.SPLIT, day=1, ratio_from=1, ratio_to=5)],
        plan=nocharge,
    ).position
    assert pos.quantity == D(25)
    assert pos.average_cost == D("20")               # still 20 after the sell
    assert pos.realized_pnl == D("250")              # (30 - 20) * 25


def test_corporate_action_ordering_is_by_ex_date(nocharge):
    """A buy after the ex-date must NOT be scaled by the split."""
    pos = replay(
        [buy(10, "100", day=0), buy(10, "20", day=5)],
        [ca(CAType.SPLIT, day=2, ratio_from=1, ratio_to=5)],
        plan=nocharge,
    ).position
    assert pos.quantity == D(60)                     # 50 split-adjusted + 10 new
    assert pos.cost_basis == D("1200")               # 1000 + 200
    assert pos.average_cost == D("20")


def test_symbol_change_is_a_no_op_on_the_numbers(nocharge):
    pos = replay(
        [buy(10, "100")], [ca(CAType.SYMBOL_CHANGE, day=1)], plan=nocharge,
    ).position
    assert pos.quantity == D(10)
    assert pos.average_cost == D("100")


def test_replay_after_a_split_is_still_deterministic(zerodha):
    txns = [buy(10, "100"), buy(6, "150", day=1), sell(4, "130", day=3)]
    cas = [ca(CAType.SPLIT, day=2, ratio_from=1, ratio_to=2)]
    a = replay(txns, cas, plan=zerodha).position
    b = replay(list(reversed(txns)), cas, plan=zerodha).position
    assert a.quantity == b.quantity
    assert a.cost_basis == b.cost_basis
    assert a.realized_pnl == b.realized_pnl
