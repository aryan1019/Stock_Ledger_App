"""
Period analytics — "how much did I actually make between these two dates?"

Realized P&L is read from SellAllocation rows, which carry the WAC figure per
lot consumed and are linked to the SELL that created them. Summing those by
the sell's trade_date gives an honest per-day realized series; nothing here
re-derives P&L, it only groups what replay already computed.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from stocks.models import PriceSnapshot
from transactions.models import Transaction

from .models import Position, SellAllocation

ZERO = Decimal("0")

PRESETS = {
    "7D": 7, "30D": 30, "90D": 90, "180D": 180, "1Y": 365, "ALL": None,
}


def resolve_range(preset: str | None, start: str | None, end: str | None):
    """A named preset, or an explicit from/to pair. Presets lose to explicit dates."""
    today = date.today()
    if start or end:
        return (
            date.fromisoformat(start) if start else date(2000, 1, 1),
            date.fromisoformat(end) if end else today,
        )
    days = PRESETS.get((preset or "90D").upper(), 90)
    return (date(2000, 1, 1) if days is None else today - timedelta(days=days)), today


def _bucket(d: date, granularity: str) -> str:
    if granularity == "month":
        return d.strftime("%Y-%m")
    return d.isoformat()


def period_report(user, start: date, end: date) -> dict:
    """Everything the dashboard needs for one date range, in a single query pass."""
    txns = list(
        Transaction.objects.owned_by(user)
        .filter(status=Transaction.ACTIVE, trade_date__gte=start, trade_date__lte=end)
        .select_related("stock")
        .order_by("trade_date", "sequence_no")
    )
    allocs = list(
        SellAllocation.objects.owned_by(user)
        .filter(
            sell_transaction__status=Transaction.ACTIVE,
            sell_transaction__trade_date__gte=start,
            sell_transaction__trade_date__lte=end,
        )
        .select_related("sell_transaction", "sell_transaction__stock")
    )

    span_days = (end - start).days
    granularity = "month" if span_days > 120 else "day"

    # ---- realized P&L, grouped by the sell that produced it ----------------
    per_sell: dict[str, dict] = {}
    for a in allocs:
        t = a.sell_transaction
        row = per_sell.setdefault(str(t.id), {
            "id": str(t.id), "symbol": t.stock.symbol, "stock": t.stock_id,
            "trade_date": t.trade_date, "quantity": ZERO, "price": t.price,
            "realized": ZERO, "charges": t.total_charges,
            "holding_days": a.holding_days, "term": a.term,
        })
        row["quantity"] += a.qty
        row["realized"] += a.wac_realized_pnl

    realized_total = sum((r["realized"] for r in per_sell.values()), ZERO)

    # ---- charges and turnover across every trade in the window -------------
    charges_total = sum((t.total_charges for t in txns), ZERO)
    buy_turnover = sum((t.quantity * t.price for t in txns if t.type == "BUY"), ZERO)
    sell_turnover = sum((t.quantity * t.price for t in txns if t.type == "SELL"), ZERO)

    charge_components: dict[str, Decimal] = defaultdict(Decimal)
    for t in txns:
        for code, amount in (t.charge_breakdown or {}).items():
            charge_components[code] += Decimal(str(amount))

    # ---- time series -------------------------------------------------------
    realized_by_bucket: dict[str, Decimal] = OrderedDict()
    charges_by_bucket: dict[str, Decimal] = defaultdict(Decimal)

    for r in sorted(per_sell.values(), key=lambda x: x["trade_date"]):
        key = _bucket(r["trade_date"], granularity)
        realized_by_bucket[key] = realized_by_bucket.get(key, ZERO) + r["realized"]
    for t in txns:
        charges_by_bucket[_bucket(t.trade_date, granularity)] += t.total_charges

    keys = sorted(set(realized_by_bucket) | set(charges_by_bucket))
    running = ZERO
    series = []
    for k in keys:
        realized = realized_by_bucket.get(k, ZERO)
        running += realized
        series.append({
            "bucket": k,
            "realized": str(realized.quantize(Decimal("0.01"))),
            "cumulative": str(running.quantize(Decimal("0.01"))),
            "charges": str(charges_by_bucket.get(k, ZERO).quantize(Decimal("0.01"))),
        })

    # ---- per-stock breakdown ----------------------------------------------
    by_stock: dict[int, dict] = {}
    for r in per_sell.values():
        s = by_stock.setdefault(r["stock"], {
            "stock": r["stock"], "symbol": r["symbol"],
            "realized": ZERO, "trades": 0, "quantity": ZERO,
        })
        s["realized"] += r["realized"]
        s["trades"] += 1
        s["quantity"] += r["quantity"]

    stock_rows = sorted(by_stock.values(), key=lambda s: s["realized"], reverse=True)

    wins = [r for r in per_sell.values() if r["realized"] > 0]
    losses = [r for r in per_sell.values() if r["realized"] < 0]

    def trade_json(r):
        return {
            "id": r["id"], "stock": r["stock"], "symbol": r["symbol"],
            "trade_date": r["trade_date"].isoformat(),
            "quantity": str(r["quantity"]),
            "price": str(r["price"].quantize(Decimal("0.01"))),
            "realized": str(r["realized"].quantize(Decimal("0.01"))),
            "charges": str(r["charges"].quantize(Decimal("0.01"))),
            "holding_days": r["holding_days"], "term": r["term"],
        }

    closed = sorted(per_sell.values(), key=lambda r: r["trade_date"], reverse=True)

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "granularity": granularity,
        "realized_pnl": str(realized_total.quantize(Decimal("0.01"))),
        "net_of_charges": str((realized_total - ZERO).quantize(Decimal("0.01"))),
        "charges_paid": str(charges_total.quantize(Decimal("0.01"))),
        "buy_turnover": str(buy_turnover.quantize(Decimal("0.01"))),
        "sell_turnover": str(sell_turnover.quantize(Decimal("0.01"))),
        "trade_count": len(txns),
        "buy_count": sum(1 for t in txns if t.type == "BUY"),
        "sell_count": sum(1 for t in txns if t.type == "SELL"),
        "closed_trade_count": len(per_sell),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": str(
            (Decimal(len(wins)) / Decimal(len(per_sell)) * 100).quantize(Decimal("0.1"))
        ) if per_sell else "0.0",
        "best_trade": trade_json(max(wins, key=lambda r: r["realized"])) if wins else None,
        "worst_trade": trade_json(min(losses, key=lambda r: r["realized"])) if losses else None,
        "series": series,
        "by_stock": [
            {
                "stock": s["stock"], "symbol": s["symbol"],
                "realized": str(s["realized"].quantize(Decimal("0.01"))),
                "trades": s["trades"], "quantity": str(s["quantity"]),
            }
            for s in stock_rows
        ],
        "charge_components": [
            {"code": code, "amount": str(amount.quantize(Decimal("0.01")))}
            for code, amount in sorted(
                charge_components.items(), key=lambda kv: kv[1], reverse=True
            )
            if amount > 0
        ],
        "closed_trades": [trade_json(r) for r in closed],
    }
