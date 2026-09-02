"""
Charge engine tests. These are what let the user stop entering charges by hand.
"""

import pytest
from conftest import buy, sell

from calculations import (
    D, ENGINE, Exchange, Side, display, get_plan, replay,
)


def charges(plan, qty, price, side, day_level=True):
    return ENGINE.compute(quantity=D(qty), price=D(price), side=side,
                          plan=plan, include_day_level=day_level)


# --------------------------------------------------------------------------
# Statutory components
# --------------------------------------------------------------------------

def test_stt_is_point_one_percent_rounded_to_nearest_rupee(zerodha):
    # 0.1% of 19,490 = 19.49 -> 19
    assert charges(zerodha, 1, "19490", Side.BUY).get("STT") == D("19")
    # 0.1% of 19,500 = 19.50 -> 20  (half up)
    assert charges(zerodha, 1, "19500", Side.BUY).get("STT") == D("20")
    # 0.1% of 19,510 = 19.51 -> 20
    assert charges(zerodha, 1, "19510", Side.BUY).get("STT") == D("20")


def test_stamp_duty_applies_to_buy_only(zerodha):
    # 0.015% of 19,495 = 2.92425, levied rounded to the nearest rupee
    assert charges(zerodha, 5, "3899", Side.BUY).get("STAMP") == D("3")
    assert charges(zerodha, 5, "3899", Side.SELL).get("STAMP") == D("0")


def test_dp_charge_applies_to_sell_only(zerodha):
    assert charges(zerodha, 5, "3899", Side.BUY).get("DP") == D("0")
    assert charges(zerodha, 5, "3899", Side.SELL).get("DP") == D("15.34")


def test_gst_base_excludes_stt_and_stamp_duty(zerodha):
    b = charges(zerodha, 5, "3899", Side.BUY)
    base = b.get("BROKERAGE") + b.get("EXCH_TXN") + b.get("SEBI")
    assert b.get("GST") == (D("0.18") * base).quantize(D("0.01"))
    # sanity: STT dwarfs the GST base, so if STT leaked in this would blow up
    assert b.get("STT") > base * 10


def test_nse_and_bse_transaction_charges_differ():
    nse = get_plan("ZERODHA", "STANDARD", Exchange.NSE)
    bse = get_plan("ZERODHA", "STANDARD", Exchange.BSE)
    t = D("1000000")
    assert (charges(bse, 1, t, Side.BUY).get("EXCH_TXN")
            > charges(nse, 1, t, Side.BUY).get("EXCH_TXN"))


# --------------------------------------------------------------------------
# Broker-specific brokerage shapes
# --------------------------------------------------------------------------

def test_zerodha_delivery_brokerage_is_zero(zerodha):
    assert charges(zerodha, 5, "3899", Side.BUY).get("BROKERAGE") == D("0")


def test_upstox_brokerage_is_flat_twenty():
    plan = get_plan("UPSTOX")
    assert charges(plan, 1, "500", Side.BUY).get("BROKERAGE") == D("20")
    assert charges(plan, 100, "5000", Side.BUY).get("BROKERAGE") == D("20")


def test_angel_one_brokerage_cap_and_floor(angel):
    # 0.1% of 15,000 = 15  -> under the Rs 20 cap, over the Rs 5 floor
    assert charges(angel, 1, "15000", Side.BUY).get("BROKERAGE") == D("15")
    # 0.1% of 25,000 = 25  -> capped at Rs 20
    assert charges(angel, 1, "25000", Side.BUY).get("BROKERAGE") == D("20")
    # 0.1% of 2,000 = 2    -> floored at Rs 5
    assert charges(angel, 1, "2000", Side.BUY).get("BROKERAGE") == D("5")
    # exactly at the cap boundary
    assert charges(angel, 1, "20000", Side.BUY).get("BROKERAGE") == D("20")


def test_groww_brokerage_is_lower_of_twenty_or_point_one_percent():
    plan = get_plan("GROWW")
    assert charges(plan, 1, "10000", Side.BUY).get("BROKERAGE") == D("10")
    assert charges(plan, 1, "50000", Side.BUY).get("BROKERAGE") == D("20")


def test_kotak_neo_youth_is_zero_delivery_brokerage():
    plan = get_plan("KOTAK_NEO", "TRADE_FREE_YOUTH")
    assert charges(plan, 5, "3899", Side.BUY).get("BROKERAGE") == D("0")


def test_kotak_neo_trade_free_is_point_two_percent():
    plan = get_plan("KOTAK_NEO", "TRADE_FREE")
    assert charges(plan, 1, "10000", Side.BUY).get("BROKERAGE") == D("20")


def test_every_seeded_plan_loads():
    from calculations import list_plans
    for key in list_plans():
        broker, plan = key.split(":")
        p = get_plan(broker, plan)
        assert charges(p, 10, "1000", Side.BUY).total > 0


# --------------------------------------------------------------------------
# The reference trade from the specification
# --------------------------------------------------------------------------

def test_reference_buy_matches_spec_worked_example(zerodha):
    b = charges(zerodha, 5, "3899", Side.BUY)
    assert b.get("BROKERAGE") == D("0.00")
    assert b.get("STT") == D("19")            # nearest rupee on this plan
    assert b.get("EXCH_TXN") == D("0.58")     # 0.00297%, verified against a real bill
    assert b.get("SEBI") == D("0.02")
    assert b.get("GST") == D("0.11")          # 18% of 0.60
    assert b.get("STAMP") == D("3")           # 2.92425 -> nearest rupee
    assert b.total == D("22.71")


def test_reference_sell_matches_spec_worked_example(zerodha):
    s = charges(zerodha, 5, "4000", Side.SELL)
    assert s.get("STT") == D("20")
    assert s.get("DP") == D("15.34")
    assert s.get("STAMP") == D("0")
    assert s.total == D("36.06")


def test_reference_round_trip_realized_pnl(zerodha):
    pos = replay([buy(5, "3899"), sell(5, "4000", day=1)], plan=zerodha).position
    assert display(pos.realized_pnl) == D("446.23")
    assert display(pos.total_charges_paid) == D("58.77")   # 22.71 + 36.06


# --------------------------------------------------------------------------
# Day-level DP charge
# --------------------------------------------------------------------------

def test_dp_charge_levied_once_per_scrip_per_day(zerodha):
    """Two SELLs of the same stock on one day incur ONE DP charge."""
    res = replay(
        [buy(20, "100"), sell(5, "120", day=1, seq=0), sell(5, "120", day=1, seq=1)],
        plan=zerodha,
    )
    sells = [t for t in res.charges if True]
    dp_total = sum(bd.get("DP") for bd in res.charges.values())
    assert dp_total == D("15.34")


def test_dp_charge_levied_again_on_a_different_day(zerodha):
    res = replay(
        [buy(20, "100"), sell(5, "120", day=1), sell(5, "120", day=2)],
        plan=zerodha,
    )
    dp_total = sum(bd.get("DP") for bd in res.charges.values())
    assert dp_total == D("30.68")


# --------------------------------------------------------------------------
# Historical stability
# --------------------------------------------------------------------------

def test_components_sum_exactly_to_total(zerodha, angel):
    for plan in (zerodha, angel):
        for side in (Side.BUY, Side.SELL):
            bd = charges(plan, 7, "1234.56", side)
            assert sum(l.amount for l in bd.lines) == bd.total


def test_charge_override_bypasses_the_engine(zerodha):
    t = buy(5, "3899", charge_override=D("99.99"))
    res = replay([t], plan=zerodha)
    assert res.position.total_charges_paid == D("99.99")


def test_opening_balance_carries_no_charges(zerodha):
    from conftest import opening
    res = replay([opening(10, "100")], plan=zerodha)
    assert res.position.total_charges_paid == D("0")
    assert res.position.average_cost == D("100")
