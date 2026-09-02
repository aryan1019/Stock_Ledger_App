from django.db import models

from accounts.ownership import OwnedManager
from calculations import CAType, Exchange


class Stock(models.Model):
    """ISIN is the stable identity — symbols get renamed, ISINs do not."""

    symbol = models.CharField(max_length=32, db_index=True)
    isin = models.CharField(max_length=12, unique=True, null=True, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    exchange = models.CharField(
        max_length=4, choices=[(e.value, e.value) for e in Exchange], default=Exchange.NSE.value
    )
    currency = models.CharField(max_length=3, default="INR")
    lot_size = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["symbol"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "exchange"], name="uniq_symbol_exchange")
        ]

    def __str__(self):
        return f"{self.symbol} ({self.exchange})"


class CorporateAction(models.Model):
    """Splits and bonuses. Replayed in ex-date order alongside transactions."""

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="corporate_actions")
    type = models.CharField(max_length=20, choices=[(t.value, t.value) for t in CAType])
    ex_date = models.DateField()
    ratio_from = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    ratio_to = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ex_date"]

    def __str__(self):
        return f"{self.stock.symbol} {self.type} {self.ratio_from}:{self.ratio_to} @ {self.ex_date}"


class PriceSnapshot(models.Model):
    """
    V1 has no market feed, so prices are entered by hand and stamped with a
    time. The `source` column is the seam a real feed drops into later.
    """

    MANUAL = "MANUAL"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="prices")
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="prices")
    price = models.DecimalField(max_digits=18, decimal_places=4)
    as_of = models.DateTimeField(auto_now=True)
    source = models.CharField(max_length=20, default=MANUAL)

    objects = OwnedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "stock"], name="uniq_user_stock_price")
        ]

    def __str__(self):
        return f"{self.stock.symbol} @ {self.price}"
