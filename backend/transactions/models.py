import uuid

from django.db import models

from accounts.ownership import OwnedManager
from calculations import Exchange, TxnType


class Portfolio(models.Model):
    """
    Present from day one even though V1 exposes only the default portfolio.
    Adding the FK now costs nothing; retrofitting it means migrating every row.
    """

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="portfolios")
    name = models.CharField(max_length=80, default="Default")
    is_default = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OwnedManager()

    def __str__(self):
        return f"{self.name} ({self.user.email})"

    @classmethod
    def default_for(cls, user):
        obj, _ = cls.objects.get_or_create(user=user, is_default=True, defaults={"name": "Default"})
        return obj


class Transaction(models.Model):
    """
    THE LEDGER. Append-only: rows are never updated in place.

    A correction appends a new row pointing at the one it supersedes, and the
    original is marked SUPERSEDED. Everything downstream is rebuilt by replay.
    """

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    STATUS = [(ACTIVE, ACTIVE), (SUPERSEDED, SUPERSEDED)]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="transactions")
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="transactions")
    stock = models.ForeignKey("stocks.Stock", on_delete=models.PROTECT, related_name="transactions")

    type = models.CharField(max_length=20, choices=[(t.value, t.value) for t in TxnType])
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    price = models.DecimalField(max_digits=18, decimal_places=4)
    trade_date = models.DateField()
    sequence_no = models.IntegerField(default=0)
    exchange = models.CharField(
        max_length=4, choices=[(e.value, e.value) for e in Exchange], default=Exchange.NSE.value
    )

    broker_plan = models.ForeignKey(
        "charges.BrokerPlan", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    charge_breakdown = models.JSONField(default=dict, blank=True)
    total_charges = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    charge_override = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )

    status = models.CharField(max_length=12, choices=STATUS, default=ACTIVE)
    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="superseded_by"
    )
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OwnedManager()

    class Meta:
        ordering = ["-trade_date", "-sequence_no", "-created_at"]
        indexes = [
            models.Index(fields=["user", "stock", "trade_date", "sequence_no"]),
            models.Index(fields=["user", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="uniq_user_idempotency_key",
            )
        ]

    def __str__(self):
        return f"{self.type} {self.quantity} {self.stock.symbol} @ {self.price}"

    @property
    def turnover(self):
        return self.quantity * self.price
