"""
GOLDEN TEST — two real Kotak Neo Trade Free YOUTH bills.

These are actual charge breakdowns from the account holder's broker app, not
figures from a published rate card. They are the only evidence in the suite
that the engine matches reality rather than matching itself, so they are
asserted line by line.

Between them they pinned down four things that were previously guessed:

  * exchange transaction charge is 0.00297% on NSE, not 0.00307%
  * there is no separate IPFT component — it sits inside the exchange charge
  * stamp duty rounds to the nearest rupee (7.0875 was billed as 7.00)
  * the YOUTH plan levies no DP charge at all on a sell
"""

from decimal import Decimal

import pytest

from calculations import D, ENGINE, Exchange, Side, display, get_plan

PLAN = get_plan("KOTAK_NEO", "TRADE_FREE_YOUTH", Exchange.NSE)


def charges(qty, price, side):
    return ENGINE.compute(quantity=D(qty), price=D(price), side=side,
                          plan=PLAN, include_day_level=True)


# --------------------------------------------------------------------------
# Bill 1 — BUY, turnover 47,250
# --------------------------------------------------------------------------

BUY_BILL = {
    "BROKERAGE": "0.00",
    "EXCH_TXN": "1.40",
    "STT": "47.25",
    "SEBI": "0.05",
    "STAMP": "7.00",
    "GST": "0.26",
}
BUY_TOTAL = Decimal("55.96")


@pytest.mark.parametrize("code,expected", BUY_BILL.items())
def test_buy_bill_line_by_line(code, expected):
    bd = charges(1, "47250", Side.BUY)
    assert display(bd.get(code)) == Decimal(expected), (
        f"{code}: engine {display(bd.get(code))}, bill {expected}"
    )


def test_buy_bill_total():
    assert display(charges(1, "47250", Side.BUY).total) == BUY_TOTAL


def test_buy_bill_has_no_dp_charge():
    assert charges(1, "47250", Side.BUY).get("DP") == Decimal("0")


# --------------------------------------------------------------------------
# Bill 2 — SELL, turnover 50,000
# --------------------------------------------------------------------------

SELL_BILL = {
    "BROKERAGE": "0.00",
    "EXCH_TXN": "1.49",
    "STT": "50.00",
    "SEBI": "0.05",
    "STAMP": "0.00",
    "GST": "0.28",
}
SELL_TOTAL = Decimal("51.82")


@pytest.mark.parametrize("code,expected", SELL_BILL.items())
def test_sell_bill_line_by_line(code, expected):
    bd = charges(1, "50000", Side.SELL)
    assert display(bd.get(code)) == Decimal(expected), (
        f"{code}: engine {display(bd.get(code))}, bill {expected}"
    )


def test_sell_bill_total():
    assert display(charges(1, "50000", Side.SELL).total) == SELL_TOTAL


def test_youth_plan_charges_no_dp_on_sell():
    """The whole reason the engine was over-charging: DP does not apply here."""
    assert charges(1, "50000", Side.SELL).get("DP") == Decimal("0")
    assert not any(line.code == "DP" for line in charges(1, "50000", Side.SELL).lines)


# --------------------------------------------------------------------------
# The four corrections, asserted directly so they cannot regress
# --------------------------------------------------------------------------

def test_exchange_rate_is_the_verified_one():
    """0.00297%, not the 0.00307% figure that bundles IPFT."""
    assert PLAN.component("EXCH_TXN").rate == D("0.0000297")


def test_there_is_no_separate_ipft_component():
    """IPFT sits inside the exchange charge. Charging both double-counts it."""
    assert PLAN.component("IPFT") is None
    for key in ["ZERODHA:STANDARD", "GROWW:STANDARD", "UPSTOX:STANDARD", "ANGEL_ONE:STANDARD"]:
        broker, plan = key.split(":")
        assert get_plan(broker, plan).component("IPFT") is None, f"{key} still has IPFT"


def test_stamp_duty_rounds_to_the_nearest_rupee():
    # 0.015% of 47,250 = 7.0875 -> billed as 7.00
    assert charges(1, "47250", Side.BUY).get("STAMP") == Decimal("7")
    # and it is buy-side only
    assert charges(1, "47250", Side.SELL).get("STAMP") == Decimal("0")


def test_stt_rounding_is_per_plan_not_a_constant():
    """Kotak bills STT unrounded; Zerodha publishes it rounded to the rupee."""
    kotak = charges(1, "47250", Side.BUY).get("STT")
    zerodha = ENGINE.compute(
        quantity=D(1), price=D("47250"), side=Side.BUY, plan=get_plan("ZERODHA"),
    ).get("STT")
    assert kotak == Decimal("47.25")
    assert zerodha == Decimal("47")


def test_gst_base_excludes_stt_and_stamp_duty():
    bd = charges(1, "47250", Side.BUY)
    base = bd.get("BROKERAGE") + bd.get("EXCH_TXN") + bd.get("SEBI")
    assert bd.get("GST") == (Decimal("0.18") * base).quantize(Decimal("0.01"))


def test_only_the_youth_plan_is_marked_verified():
    assert get_plan("KOTAK_NEO", "TRADE_FREE_YOUTH").verified is True
    assert get_plan("ZERODHA").verified is False   # needs a contract note
