"""
Plan identity tests.

Added after a real misreading: the two Kotak Neo plans have very different
delivery brokerage, and a table that collapses them looks like a bug. These
tests pin the distinction so it can never drift silently.
"""

import pytest

from calculations import D, ENGINE, Side, display, get_plan, list_plans

QTY, PRICE = D(5), D("3899")     # turnover 19,495


def brokerage(broker, plan):
    p = get_plan(broker, plan)
    return ENGINE.compute(quantity=QTY, price=PRICE, side=Side.BUY, plan=p).get("BROKERAGE")


def test_kotak_youth_has_zero_delivery_brokerage():
    """The under-30 plan: Rs 0 delivery brokerage."""
    assert brokerage("KOTAK_NEO", "TRADE_FREE_YOUTH") == D("0.00")


def test_kotak_trade_free_charges_point_two_percent():
    """The GENERAL plan: 0.20% per order. 0.002 * 19,495 = 38.99."""
    assert brokerage("KOTAK_NEO", "TRADE_FREE") == D("38.99")


def test_the_two_kotak_plans_are_genuinely_different():
    youth = brokerage("KOTAK_NEO", "TRADE_FREE_YOUTH")
    general = brokerage("KOTAK_NEO", "TRADE_FREE")
    assert youth == D("0.00")
    assert general > youth
    # and the difference is exactly the 0.20% brokerage plus its GST
    p_y = get_plan("KOTAK_NEO", "TRADE_FREE_YOUTH")
    p_g = get_plan("KOTAK_NEO", "TRADE_FREE")
    ty = ENGINE.compute(quantity=QTY, price=PRICE, side=Side.BUY, plan=p_y).total
    tg = ENGINE.compute(quantity=QTY, price=PRICE, side=Side.BUY, plan=p_g).total
    # 38.99 brokerage + 7.02 extra GST (the GST base rises by the brokerage)
    assert tg - ty == D("46.01")


def test_zero_brokerage_plans_agree_with_each_other():
    """Zerodha and Kotak Youth both charge no delivery brokerage."""
    assert brokerage("ZERODHA", "STANDARD") == brokerage("KOTAK_NEO", "TRADE_FREE_YOUTH")


def test_kotak_youth_costs_less_than_zerodha_on_a_sell():
    """
    Zerodha's Rs 15.34 DP charge is the whole difference — the youth plan
    has none. This is what was over-charging before the real bills arrived.
    """
    from calculations import Side as S
    args = dict(quantity=QTY, price=PRICE, side=S.SELL)
    youth = ENGINE.compute(**args, plan=get_plan("KOTAK_NEO", "TRADE_FREE_YOUTH")).total
    zerodha = ENGINE.compute(**args, plan=get_plan("ZERODHA")).total
    assert zerodha - youth == D("15.34") - D("0.50")   # DP, less the STT rounding


def test_every_plan_has_a_distinct_human_label():
    labels = [get_plan(*k.split(":")).label for k in list_plans()]
    assert len(labels) == len(set(labels)), "two plans share a display label"
    assert all(labels), "a plan is missing a display label"


def test_kotak_labels_state_the_difference_explicitly():
    youth = get_plan("KOTAK_NEO", "TRADE_FREE_YOUTH")
    general = get_plan("KOTAK_NEO", "TRADE_FREE")
    assert "YOUTH" in youth.label
    assert "0.20%" in general.label
    assert "NOT the zero-brokerage youth plan" in general.notes


def test_every_plan_carries_eligibility_notes():
    for key in list_plans():
        p = get_plan(*key.split(":"))
        assert p.notes, f"{key} has no notes — the user cannot tell plans apart"
