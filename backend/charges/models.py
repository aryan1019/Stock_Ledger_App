from django.db import models

from accounts.ownership import OwnedManager
from calculations import ChargePlan, Component, Exchange, Segment
from calculations.plans import get_plan, list_plans


class BrokerPlan(models.Model):
    """
    A charge plan stored as DATA — components as JSON, with effective dates.

    Seeded from calculations.plans, so the six broker plans the engine ships
    with are exactly the rows in this table. Users can add custom plans.
    """

    broker = models.CharField(max_length=40)
    plan = models.CharField(max_length=40)
    display_name = models.CharField(max_length=120)
    notes = models.CharField(max_length=300, blank=True)
    segment = models.CharField(
        max_length=24, choices=[(s.value, s.value) for s in Segment],
        default=Segment.EQUITY_DELIVERY.value,
    )
    exchange = models.CharField(
        max_length=4, choices=[(e.value, e.value) for e in Exchange], default=Exchange.NSE.value
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    components = models.JSONField(default=list)
    is_system = models.BooleanField(default=True)
    verified = models.BooleanField(
        default=False, help_text="Checked against a real broker bill."
    )
    user = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.CASCADE, related_name="broker_plans"
    )

    objects = OwnedManager()

    class Meta:
        ordering = ["broker", "plan", "exchange"]
        constraints = [
            models.UniqueConstraint(
                fields=["broker", "plan", "segment", "exchange", "effective_from"],
                name="uniq_plan_version",
            )
        ]

    def __str__(self):
        return f"{self.display_name} [{self.exchange}]"

    # -- bridge back into the pure engine ---------------------------------

    def to_engine_plan(self) -> ChargePlan:
        """Rebuild the framework-free ChargePlan the calculation engine wants."""
        return ChargePlan(
            broker=self.broker,
            plan=self.plan,
            segment=self.segment,
            exchange=self.exchange,
            effective_from=self.effective_from,
            display_name=self.display_name,
            notes=self.notes,
            verified=self.verified,
            components=[Component(**c) for c in self.components],
        )

    @staticmethod
    def _component_to_json(c: Component) -> dict:
        out = {
            "code": c.code,
            "label": c.label,
            "basis": c.basis.value if hasattr(c.basis, "value") else c.basis,
            "side": c.side.value if hasattr(c.side, "value") else c.side,
            "rounding": c.rounding.value if hasattr(c.rounding, "value") else c.rounding,
            "gst_inclusive": c.gst_inclusive,
        }
        for f in ("rate", "amount", "cap", "floor"):
            v = getattr(c, f)
            if v is not None:
                out[f] = str(v)
        if c.of:
            out["of"] = list(c.of)
        return out

    @classmethod
    def seed(cls):
        """Idempotent: load every seeded engine plan for both exchanges."""
        created = 0
        for key in list_plans():
            broker, plan = key.split(":")
            for exchange in Exchange:
                p = get_plan(broker, plan, exchange)
                _, made = cls.objects.update_or_create(
                    broker=p.broker, plan=p.plan, segment=p.segment,
                    exchange=p.exchange, effective_from=p.effective_from,
                    defaults={
                        "display_name": p.label,
                        "notes": p.notes,
                        "verified": p.verified,
                        "components": [cls._component_to_json(c) for c in p.components],
                        "is_system": True,
                        "user": None,
                    },
                )
                created += int(made)
        return created
