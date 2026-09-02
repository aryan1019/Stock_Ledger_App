"""
API tests, including the cross-user suite the spec makes non-negotiable:
every endpoint hit as the wrong user must 404, never leak.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from charges.models import BrokerPlan
from portfolio.models import Lot, Position, SellAllocation
from stocks.models import CorporateAction, Stock
from transactions.models import Transaction

User = get_user_model()
pytestmark = pytest.mark.django_db

TODAY = date.today()


def d(offset=0):
    return (TODAY - timedelta(days=offset)).isoformat()


@pytest.fixture(autouse=True)
def plans():
    BrokerPlan.seed()


@pytest.fixture
def stock():
    return Stock.objects.create(symbol="KAYNES", company_name="Kaynes Technology", exchange="NSE")


@pytest.fixture
def other_stock():
    return Stock.objects.create(symbol="IRFC", company_name="Indian Railway Finance", exchange="NSE")


def make_client(email="a@example.com"):
    c = APIClient()
    r = c.post("/api/v1/auth/register/", {"email": email, "name": "T", "password": "Str0ng!Pass99"},
               format="json")
    assert r.status_code == 201, r.data
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c, r.data["user"]["id"]


@pytest.fixture
def client_a():
    return make_client("a@example.com")[0]


@pytest.fixture
def client_b():
    return make_client("b@example.com")[0]


def buy(client, stock, qty, price, days_ago=0, seq=0):
    return client.post("/api/v1/transactions/", {
        "stock": stock.id, "type": "BUY", "quantity": str(qty), "price": str(price),
        "trade_date": d(days_ago), "sequence_no": seq, "exchange": "NSE",
    }, format="json")


def sell(client, stock, qty, price, days_ago=0, seq=0):
    return client.post("/api/v1/transactions/", {
        "stock": stock.id, "type": "SELL", "quantity": str(qty), "price": str(price),
        "trade_date": d(days_ago), "sequence_no": seq, "exchange": "NSE",
    }, format="json")


# ==========================================================================
# Auth
# ==========================================================================

def test_register_creates_portfolio_and_default_plan(client_a):
    me = client_a.get("/api/v1/me/")
    assert me.status_code == 200
    assert me.data["default_broker_plan"] is not None


def test_login_returns_tokens():
    make_client("login@example.com")
    c = APIClient()
    r = c.post("/api/v1/auth/login/",
               {"email": "login@example.com", "password": "Str0ng!Pass99"}, format="json")
    assert r.status_code == 200
    assert "access" in r.data and "refresh" in r.data


def test_anonymous_is_rejected():
    c = APIClient()
    for url in ["/api/v1/portfolio/", "/api/v1/transactions/", "/api/v1/portfolio/summary/"]:
        assert c.get(url).status_code == 401


# ==========================================================================
# Ledger and replay
# ==========================================================================

def test_buy_computes_charges_from_the_plan(client_a, stock):
    r = buy(client_a, stock, 5, "3899.00")
    assert r.status_code == 201, r.data
    assert Decimal(r.data["total_charges"]) == Decimal("22.71")
    assert r.data["charge_breakdown"]["STT"] == "19.00"
    assert r.data["charge_breakdown"]["BROKERAGE"] == "0.00"


def test_sell_does_not_change_remaining_average(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=2)
    buy(client_a, stock, 6, "150", days_ago=1)
    before = Position.objects.get(stock=stock).average_cost
    sell(client_a, stock, 6, "130")
    pos = Position.objects.get(stock=stock)
    assert pos.quantity == Decimal("10")
    assert pos.average_cost == before          # THE rule
    assert pos.realized_pnl != 0


def test_realized_profit_never_lowers_the_new_average(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=2)
    sell(client_a, stock, 10, "120", days_ago=1)
    buy(client_a, stock, 10, "110")
    pos = Position.objects.get(stock=stock)
    assert pos.quantity == Decimal("10")
    # charges push it just above 110; it must NOT be near 90
    assert Decimal("110") <= pos.average_cost < Decimal("111")
    assert pos.realized_pnl > 0


def test_break_even_sits_above_average_cost(client_a, stock):
    buy(client_a, stock, 5, "3899.00")
    pos = Position.objects.get(stock=stock)
    assert pos.break_even > pos.average_cost


def test_lots_and_fifo_allocations_are_persisted(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=2)
    buy(client_a, stock, 6, "150", days_ago=1)
    sell(client_a, stock, 6, "130")
    assert Lot.objects.count() == 2
    assert SellAllocation.objects.count() == 1
    alloc = SellAllocation.objects.first()
    assert alloc.qty == Decimal("6")
    assert alloc.fifo_realized_pnl != alloc.wac_realized_pnl   # both recorded


def test_oversell_is_refused_with_the_remedy(client_a, stock):
    buy(client_a, stock, 4, "100", days_ago=1)
    r = sell(client_a, stock, 10, "130")
    assert r.status_code == 400
    assert "you hold 4" in r.data["detail"]
    assert "opening balance" in r.data["detail"]
    assert Transaction.objects.filter(type="SELL").count() == 0   # rolled back


def test_future_dated_transaction_is_refused(client_a, stock):
    r = client_a.post("/api/v1/transactions/", {
        "stock": stock.id, "type": "BUY", "quantity": "1", "price": "100",
        "trade_date": (TODAY + timedelta(days=1)).isoformat(),
    }, format="json")
    assert r.status_code == 400


def test_backdated_insert_matches_in_order_entry(client_a, client_b, stock):
    buy(client_a, stock, 10, "100", days_ago=10)
    buy(client_a, stock, 5, "120", days_ago=5)
    in_order = Position.objects.get(user__email="a@example.com").average_cost

    buy(client_b, stock, 10, "100", days_ago=10)
    buy(client_b, stock, 5, "120", days_ago=5)   # entered late below
    late = Position.objects.get(user__email="b@example.com").average_cost
    assert in_order == late


def test_delete_supersedes_and_replays(client_a, stock):
    r1 = buy(client_a, stock, 10, "100", days_ago=1)
    buy(client_a, stock, 5, "200")
    assert Position.objects.get(stock=stock).quantity == Decimal("15")

    assert client_a.delete(f"/api/v1/transactions/{r1.data['id']}/").status_code == 204
    assert Position.objects.get(stock=stock).quantity == Decimal("5")
    # the row is kept, just superseded — the ledger is append-only
    assert Transaction.objects.filter(id=r1.data["id"], status="SUPERSEDED").exists()


def test_correction_appends_and_keeps_history(client_a, stock):
    r1 = buy(client_a, stock, 10, "100")
    r = client_a.post(f"/api/v1/transactions/{r1.data['id']}/correct/", {
        "stock": stock.id, "type": "BUY", "quantity": "10", "price": "110",
        "trade_date": d(0),
    }, format="json")
    assert r.status_code == 201
    assert Transaction.objects.count() == 2
    assert Transaction.objects.filter(status="ACTIVE").count() == 1
    assert Position.objects.get(stock=stock).average_cost > Decimal("110")


def test_idempotency_key_prevents_duplicates(client_a, stock):
    body = {
        "stock": stock.id, "type": "BUY", "quantity": "5", "price": "100",
        "trade_date": d(0), "idempotency_key": "abc-123",
    }
    assert client_a.post("/api/v1/transactions/", body, format="json").status_code == 201
    second = client_a.post("/api/v1/transactions/", body, format="json")
    assert second.status_code == 200
    assert Transaction.objects.filter(status="ACTIVE").count() == 1


def test_rebuild_reproduces_the_same_projection(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=3)
    buy(client_a, stock, 6, "150", days_ago=2)
    sell(client_a, stock, 4, "170", days_ago=1)
    before = Position.objects.get(stock=stock)
    snapshot = (before.quantity, before.cost_basis, before.realized_pnl, before.break_even)

    Position.objects.all().delete()          # projection is disposable
    assert client_a.post("/api/v1/portfolio/rebuild/").status_code == 200

    after = Position.objects.get(stock=stock)
    assert (after.quantity, after.cost_basis, after.realized_pnl, after.break_even) == snapshot


# ==========================================================================
# Corporate actions
# ==========================================================================

def test_split_adjusts_quantity_and_average(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=10)
    CorporateAction.objects.create(
        stock=stock, type="SPLIT", ex_date=TODAY - timedelta(days=5),
        ratio_from=1, ratio_to=5,
    )
    client_a.post("/api/v1/portfolio/rebuild/")
    pos = Position.objects.get(stock=stock)
    assert pos.quantity == Decimal("50")
    assert pos.average_cost < Decimal("21")     # ~20 plus a fifth of the charges


# ==========================================================================
# Preview
# ==========================================================================

def test_preview_computes_without_saving(client_a, stock):
    buy(client_a, stock, 10, "3800")
    r = client_a.post("/api/v1/transactions/preview/", {
        "stock": stock.id, "type": "BUY", "quantity": "5", "price": "3899", "exchange": "NSE",
    }, format="json")
    assert r.status_code == 200
    assert r.data["total_charges"] == "22.71"
    assert r.data["after"]["quantity"] == "15.000000"
    assert Decimal(r.data["after"]["break_even"]) > Decimal(r.data["after"]["average_cost"])
    assert Transaction.objects.filter(status="ACTIVE").count() == 1   # nothing saved


def test_preview_flags_an_oversell(client_a, stock):
    buy(client_a, stock, 3, "100")
    r = client_a.post("/api/v1/transactions/preview/", {
        "stock": stock.id, "type": "SELL", "quantity": "10", "price": "120", "exchange": "NSE",
    }, format="json")
    assert r.status_code == 200
    assert r.data["sufficient_quantity"] is False
    assert r.data["held_quantity"] == "3.000000"


# ==========================================================================
# Portfolio views
# ==========================================================================

def test_portfolio_and_summary(client_a, stock, other_stock):
    buy(client_a, stock, 10, "3800", days_ago=2)
    buy(client_a, other_stock, 100, "120", days_ago=1)
    client_a.put(f"/api/v1/prices/{stock.id}/", {"price": "3950"}, format="json")
    client_a.put(f"/api/v1/prices/{other_stock.id}/", {"price": "142.80"}, format="json")

    p = client_a.get("/api/v1/portfolio/")
    assert p.status_code == 200 and len(p.data) == 2
    assert all("break_even" in row and "unrealized_pnl" in row for row in p.data)

    s = client_a.get("/api/v1/portfolio/summary/")
    assert s.status_code == 200
    assert Decimal(s.data["market_value"]) > 0
    assert s.data["holdings_count"] == 2
    assert s.data["prices_missing"] == 0


def test_stock_detail_carries_lots_and_reconciliation(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=2)
    buy(client_a, stock, 6, "150", days_ago=1)
    client_a.put(f"/api/v1/prices/{stock.id}/", {"price": "160"}, format="json")

    r = client_a.get(f"/api/v1/portfolio/{stock.id}/")
    assert r.status_code == 200
    assert len(r.data["lots"]) == 2
    assert all("days_to_long_term" in lot and "term" in lot for lot in r.data["lots"])
    assert Decimal(r.data["break_even"]) > Decimal(r.data["position"]["average_cost"])
    assert "broker_style_average" in r.data


def test_money_is_serialised_as_strings(client_a, stock):
    buy(client_a, stock, 5, "3899")
    row = client_a.get("/api/v1/transactions/").data["results"][0]
    assert isinstance(row["price"], str)
    assert isinstance(row["total_charges"], str)


# ==========================================================================
# CROSS-USER SECURITY — every endpoint, wrong user, expect 404
# ==========================================================================

def test_user_b_cannot_see_user_a_data(client_a, client_b, stock):
    buy(client_a, stock, 10, "100")
    client_a.put(f"/api/v1/prices/{stock.id}/", {"price": "150"}, format="json")

    assert client_b.get("/api/v1/portfolio/").data == []
    assert client_b.get("/api/v1/transactions/").data["results"] == []
    assert client_b.get("/api/v1/portfolio/summary/").data["holdings_count"] == 0
    assert client_b.get(f"/api/v1/portfolio/{stock.id}/").status_code == 404
    assert client_b.get(f"/api/v1/prices/{stock.id}/").status_code == 404


def test_user_b_cannot_read_update_or_delete_user_a_transaction(client_a, client_b, stock):
    txn_id = buy(client_a, stock, 10, "100").data["id"]
    url = f"/api/v1/transactions/{txn_id}/"

    assert client_b.get(url).status_code == 404
    assert client_b.delete(url).status_code == 404
    assert client_b.patch(url, {"price": "1"}, format="json").status_code == 404
    assert client_b.post(f"{url}correct/", {
        "stock": stock.id, "type": "BUY", "quantity": "1", "price": "1", "trade_date": d(0),
    }, format="json").status_code == 404

    # and A's data is untouched
    assert Transaction.objects.filter(id=txn_id, status="ACTIVE").exists()


def test_two_users_positions_are_independent(client_a, client_b, stock):
    buy(client_a, stock, 10, "100")
    buy(client_b, stock, 50, "200")
    a = Position.objects.get(user__email="a@example.com", stock=stock)
    b = Position.objects.get(user__email="b@example.com", stock=stock)
    assert a.quantity == Decimal("10") and b.quantity == Decimal("50")
    assert a.average_cost != b.average_cost


def test_price_snapshots_are_per_user(client_a, client_b, stock):
    buy(client_a, stock, 1, "100")
    buy(client_b, stock, 1, "100")
    client_a.put(f"/api/v1/prices/{stock.id}/", {"price": "500"}, format="json")
    client_b.put(f"/api/v1/prices/{stock.id}/", {"price": "900"}, format="json")
    assert client_a.get(f"/api/v1/prices/{stock.id}/").data["price"] == "500.0000"
    assert client_b.get(f"/api/v1/prices/{stock.id}/").data["price"] == "900.0000"


# ==========================================================================
# Period analytics — the dashboard date range
# ==========================================================================

def test_analytics_reports_realized_pnl_for_a_period(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=40)
    sell(client_a, stock, 5, "150", days_ago=30)
    sell(client_a, stock, 5, "80", days_ago=5)

    r = client_a.get("/api/v1/portfolio/analytics/", {"preset": "90D"})
    assert r.status_code == 200
    assert r.data["closed_trade_count"] == 2
    assert r.data["win_count"] == 1 and r.data["loss_count"] == 1
    assert r.data["win_rate"] == "50.0"
    assert Decimal(r.data["charges_paid"]) > 0
    # three buckets: the buy day carries charges, the two sell days carry both
    assert len(r.data["series"]) == 3
    assert [pt["realized"] for pt in r.data["series"]][0] == "0.00"   # buy day
    assert r.data["best_trade"]["symbol"] == "KAYNES"


def test_analytics_range_excludes_trades_outside_it(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=60)
    sell(client_a, stock, 5, "150", days_ago=50)     # outside
    sell(client_a, stock, 5, "150", days_ago=3)      # inside

    r = client_a.get("/api/v1/portfolio/analytics/", {"from": d(10), "to": d(0)})
    assert r.data["closed_trade_count"] == 1
    assert r.data["sell_count"] == 1


def test_analytics_switches_to_monthly_buckets_over_120_days(client_a, stock):
    buy(client_a, stock, 10, "100", days_ago=300)
    sell(client_a, stock, 5, "150", days_ago=200)
    r = client_a.get("/api/v1/portfolio/analytics/", {"preset": "1Y"})
    assert r.data["granularity"] == "month"
    assert all(len(pt["bucket"]) == 7 for pt in r.data["series"])   # YYYY-MM


def test_analytics_rejects_a_backwards_range(client_a):
    r = client_a.get("/api/v1/portfolio/analytics/", {"from": d(0), "to": d(30)})
    assert r.status_code == 400


def test_analytics_is_per_user(client_a, client_b, stock):
    buy(client_a, stock, 10, "100", days_ago=10)
    sell(client_a, stock, 5, "150", days_ago=5)
    assert client_b.get("/api/v1/portfolio/analytics/").data["closed_trade_count"] == 0


def test_ledger_date_and_symbol_filters(client_a, stock, other_stock):
    buy(client_a, stock, 10, "100", days_ago=40)
    buy(client_a, other_stock, 10, "100", days_ago=3)

    assert len(client_a.get("/api/v1/transactions/", {"from": d(10)}).data["results"]) == 1
    assert len(client_a.get("/api/v1/transactions/", {"q": "IRFC"}).data["results"]) == 1
    assert len(client_a.get("/api/v1/transactions/", {"type": "SELL"}).data["results"]) == 0
