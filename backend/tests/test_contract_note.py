"""
GOLDEN TEST — fill this in with a REAL contract note from your broker.

This is the single most valuable test in the suite. Everything else proves
the engine is internally consistent; only this proves it matches reality.

HOW TO USE
----------
1. Open any contract note / trade confirmation PDF from your broker.
2. Pick one trade. Copy its quantity, price, and each charge line.
3. Fill in the dict below and delete the `skip` marker.
4. Run:  python3 -m pytest tests/test_contract_note.py -v

If it fails, the failure message tells you exactly which component is wrong
and by how much. Fix the rate in calculations/plans.py — never in the engine.
"""

import pytest
from conftest import buy

from calculations import D, ENGINE, Exchange, Side, display, get_plan

# ---------------------------------------------------------------------------
# EDIT THIS BLOCK
# ---------------------------------------------------------------------------

CONTRACT_NOTE = {
    "broker":   "ZERODHA",
    "plan":     "STANDARD",
    "exchange": Exchange.NSE,
    "side":     Side.BUY,

    "quantity": "5",
    "price":    "3899.00",

    # Charge lines exactly as printed on the note. Omit any your broker
    # does not itemise; set to "0.00" for those it shows as zero.
    "expected": {
        "BROKERAGE": "0.00",
        "STT":       "19.00",
        "EXCH_TXN":  "0.58",
        "SEBI":      "0.02",
        "STAMP":     "3.00",
        "GST":       "0.11",
        # "DP":      "15.34",     # sell side only
    },
    "expected_total": "22.71",
}

# Delete this line once you have entered your own contract note.
REPLACE_WITH_YOUR_OWN = False

# ---------------------------------------------------------------------------


@pytest.mark.skipif(REPLACE_WITH_YOUR_OWN,
                    reason="Enter a real contract note, then flip the flag.")
def test_engine_matches_a_real_contract_note():
    cn = CONTRACT_NOTE
    plan = get_plan(cn["broker"], cn["plan"], cn["exchange"])
    bd = ENGINE.compute(
        quantity=D(cn["quantity"]), price=D(cn["price"]),
        side=cn["side"], plan=plan, include_day_level=True,
    )

    mismatches = []
    for code, expected in cn["expected"].items():
        actual = display(bd.get(code))
        if actual != D(expected):
            mismatches.append(
                f"    {code:<12} contract note {expected:>10}   "
                f"engine {actual:>10}   diff {display(actual - D(expected)):>10}"
            )

    total_ok = display(bd.total) == D(cn["expected_total"])
    if not total_ok:
        mismatches.append(
            f"    {'TOTAL':<12} contract note {cn['expected_total']:>10}   "
            f"engine {display(bd.total):>10}"
        )

    assert not mismatches, (
        "\nEngine does not match the contract note:\n"
        + "\n".join(mismatches)
        + "\n\n  Fix the rate in calculations/plans.py, not in charges.py.\n"
    )


def test_charge_snapshot_survives_a_rate_change():
    """
    Historical trades must keep their original charges when rates change.
    In production this is guaranteed by snapshotting the breakdown onto the
    transaction; here we prove the engine is a pure function of (txn, plan).
    """
    old = get_plan("ZERODHA")
    new = get_plan("ZERODHA")
    new.component("STT").rate = D("0.002")          # hypothetical rate hike

    a = ENGINE.compute(quantity=D(5), price=D("3899"), side=Side.BUY, plan=old)
    b = ENGINE.compute(quantity=D(5), price=D("3899"), side=Side.BUY, plan=new)

    assert a.get("STT") == D("19")
    assert b.get("STT") == D("39")
    assert a.total != b.total          # same input, different plan, different result
