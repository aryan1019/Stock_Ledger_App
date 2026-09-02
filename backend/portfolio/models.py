"""
PROJECTION TABLES.

Nothing here is a primary record. Every row can be deleted and rebuilt from
the ledger by portfolio.services.rebuild(). `ledger_hash` on Position says
whether the projection is current.
"""

import uuid

from django.db import models

from accounts.ownership import OwnedManager
from calculations import Term


class Position(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="positions")
    portfolio = models.ForeignKey(
        "transactions.Portfolio", on_delete=models.CASCADE, related_name="positions"
    )
    stock = models.ForeignKey("stocks.Stock", on_delete=models.CASCADE, related_name="positions")

    quantity = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    cost_basis = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    average_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    realized_pnl = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    realized_pnl_fifo = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_charges_paid = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    dividends = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    break_even = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    recovery_break_even = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    ledger_hash = models.CharField(max_length=32, blank=True)
    last_rebuilt_at = models.DateTimeField(auto_now=True)

    objects = OwnedManager()

    class Meta:
        ordering = ["stock__symbol"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "stock"], name="uniq_portfolio_stock_position"
            )
        ]

    def __str__(self):
        return f"{self.stock.symbol}: {self.quantity} @ {self.average_cost}"


class Lot(models.Model):
    """One acquisition event. Never merged, never erased."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="lots")
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="lots")
    source_transaction = models.ForeignKey(
        "transactions.Transaction", on_delete=models.CASCADE, related_name="lots"
    )

    original_qty = models.DecimalField(max_digits=18, decimal_places=6)
    remaining_qty = models.DecimalField(max_digits=18, decimal_places=6)
    buy_price = models.DecimalField(max_digits=18, decimal_places=4)
    buy_charges = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    cost_per_share = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    break_even = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    acquisition_date = models.DateField()

    objects = OwnedManager()

    class Meta:
        ordering = ["acquisition_date", "id"]

    @property
    def is_closed(self):
        return self.remaining_qty <= 0


class SellAllocation(models.Model):
    """
    The FIFO trail. Not displayed in V1 — it exists because Indian capital
    gains are computed FIFO and the allocation cannot be reconstructed later.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="allocations")
    sell_transaction = models.ForeignKey(
        "transactions.Transaction", on_delete=models.CASCADE, related_name="allocations"
    )
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="allocations")

    qty = models.DecimalField(max_digits=18, decimal_places=6)
    fifo_cost_basis = models.DecimalField(max_digits=18, decimal_places=4)
    fifo_realized_pnl = models.DecimalField(max_digits=18, decimal_places=4)
    wac_cost_basis = models.DecimalField(max_digits=18, decimal_places=4)
    wac_realized_pnl = models.DecimalField(max_digits=18, decimal_places=4)
    holding_days = models.IntegerField(default=0)
    term = models.CharField(max_length=8, choices=[(t.value, t.value) for t in Term])

    objects = OwnedManager()

    class Meta:
        ordering = ["id"]
