"""
Invariant and property tests — these catch the bugs enumerated cases miss.
"""

import random
from datetime import date

import pytest
from conftest import buy, sell, DAY

from calculations import (
    D, ZERO_CHARGE_PLAN, build_report, get_plan, ledger_hash, replay,
    solve_breakeven, net_proceeds_at,
)


def test_lot_remaining_quantities_sum_to_position_quantity(zerodha):
    txns = [buy(10, "100"), buy(6, "150", day=1), sell(7, "130", day=2),
            buy(4, "180", day=3), sell(3, "200", day=4)]
    pos = replay(txns, plan=zerodha).position
    assert sum(l.remaining_qty for l in pos.lots) == pos.quantity


def test_allocation_quantities_sum_to_sell_quantity(zerodha):
    txns = [buy(10, "100"), buy(6, "150", day=1), sell(12, "130", day=2)]
    pos = replay(txns, plan=zerodha).position
    total = sum(a.qty for a in pos.allocations)
    assert total == D(12)


def test_total_pnl_is_identical_under_wac_and_fifo(nocharge):
    """
    D11: the method changes the realized/unrealized SPLIT, never the total.
    Proven by closing the position entirely, at which point both totals must
    equal the same cash-in-minus-cash-out figure.
    """
    txns = [buy(10, "100"), buy(6, "150", day=1),
            sell(6, "130", day=2), sell(10, "170", day=3)]
    pos = replay(txns, plan=nocharge).position
    cash_out = D(10) * D(100) + D(6) * D(150)
    cash_in = D(6) * D(130) + D(10) * D(170)
    expected = cash_in - cash_out
    assert pos.realized_pnl == expected
    assert pos.realized_pnl_fifo == expected


def test_replay_is_deterministic_regardless_of_insertion_order(zerodha):
    txns = [buy(10, "100"), buy(6, "150", day=1), sell(7, "130", day=2),
            buy(4, "180", day=3)]
    forward = replay(txns, plan=zerodha).position
    shuffled = list(txns)
    random.Random(42).shuffle(shuffled)
    backward = replay(shuffled, plan=zerodha).position

    assert forward.quantity == backward.quantity
    assert forward.cost_basis == backward.cost_basis
    assert forward.realized_pnl == backward.realized_pnl
    assert forward.total_charges_paid == backward.total_charges_paid


def test_backdated_insert_matches_in_order_entry(zerodha):
    """Enter a trade late; the result must equal having entered it on time."""
    in_order = [buy(10, "100", day=0), buy(5, "120", day=1), sell(6, "150", day=2)]
    late = [buy(10, "100", day=0), sell(6, "150", day=2), buy(5, "120", day=1)]

    a = replay(in_order, plan=zerodha).position
    b = replay(late, plan=zerodha).position
    assert a.average_cost == b.average_cost
    assert a.realized_pnl == b.realized_pnl
    assert a.quantity == b.quantity


def test_ledger_hash_changes_when_ledger_changes(zerodha):
    base = [buy(10, "100"), buy(6, "150", day=1)]
    h1 = replay(base, plan=zerodha).ledger_hash
    h2 = replay(base + [sell(3, "160", day=2)], plan=zerodha).ledger_hash
    assert h1 != h2
    assert replay(list(reversed(base)), plan=zerodha).ledger_hash == h1


def test_break_even_is_never_below_average_cost(zerodha):
    for price in ("50", "500", "3899", "25000"):
        pos = replay([buy(7, price)], plan=zerodha).position
        be = solve_breakeven(pos.quantity, pos.cost_basis, zerodha)
        assert be >= pos.average_cost, f"break-even below average at {price}"


def test_selling_at_break_even_recovers_cost_basis(zerodha, angel):
    """Feed break-even back through the charge engine: proceeds must clear cost."""
    for plan in (zerodha, angel):
        for q, p in ((5, "3899"), (100, "250"), (1, "18000"), (37, "612.45")):
            pos = replay([buy(q, p)], plan=plan).position
            be = solve_breakeven(pos.quantity, pos.cost_basis, plan)
            net = net_proceeds_at(pos.quantity, be, plan)
            assert net >= pos.cost_basis
            # and it is the LOWEST such price to the paisa
            below = net_proceeds_at(pos.quantity, be - D("0.01"), plan)
            assert below < pos.cost_basis


def test_recovery_break_even_exceeds_position_break_even_after_a_loss(zerodha):
    txns = [buy(20, "100"), sell(10, "80", day=1)]     # book a loss
    pos = replay(txns, plan=zerodha).position
    assert pos.realized_pnl < 0
    rpt = build_report(pos, "95", zerodha, as_of=date(2026, 9, 1))
    assert rpt.recovery_break_even > rpt.break_even


def test_no_monetary_drift_over_random_sequences(zerodha):
    """
    Over many random trades: realized + unrealized must equal
    (cash in - cash out - charges + market value of what remains).
    """
    rng = random.Random(7)
    for trial in range(30):
        txns = [buy(rng.randint(5, 50), str(rng.randint(50, 500)))]
        held = txns[0].quantity
        day = 1
        for _ in range(rng.randint(1, 8)):
            if held > 1 and rng.random() < 0.45:
                q = D(rng.randint(1, int(held)))
                txns.append(sell(q, str(rng.randint(50, 600)), day=day))
                held -= q
            else:
                q = D(rng.randint(1, 30))
                txns.append(buy(q, str(rng.randint(50, 600)), day=day))
                held += q
            day += 1

        pos = replay(txns, plan=zerodha).position
        cash = D(0)
        for t in txns:
            cash += (t.quantity * t.price) * (D(1) if t.type.value == "SELL" else D(-1))
        price = D("300")
        expected_total = cash - pos.total_charges_paid + pos.quantity * price

        rpt = build_report(pos, price, zerodha, as_of=date(2026, 12, 31))
        # unrealized_net already carries exit charges, so compare gross totals
        actual = pos.realized_pnl + (price - pos.average_cost) * pos.quantity
        assert abs(actual - expected_total) < D("0.0001"), f"drift in trial {trial}"


def test_average_cost_never_moves_on_a_sell_over_random_sequences(zerodha):
    rng = random.Random(99)
    for _ in range(50):
        q1, p1 = rng.randint(5, 40), str(rng.randint(50, 900))
        q2, p2 = rng.randint(5, 40), str(rng.randint(50, 900))
        txns = [buy(q1, p1), buy(q2, p2, day=1)]
        before = replay(txns, plan=zerodha).position.average_cost
        sell_qty = rng.randint(1, q1 + q2 - 1)
        txns.append(sell(sell_qty, str(rng.randint(50, 900)), day=2))
        after = replay(txns, plan=zerodha).position.average_cost
        assert abs(after - before) < D("0.00000001")
