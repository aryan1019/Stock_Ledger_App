from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from charges.models import BrokerPlan
from portfolio.models import Lot, Position, SellAllocation
from stocks.models import CorporateAction, PriceSnapshot, Stock
from transactions.models import Transaction

User = get_user_model()


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "email", "name", "password"]

    def create(self, data):
        return User.objects.create_user(**data)


class UserSerializer(serializers.ModelSerializer):
    default_broker_plan_label = serializers.CharField(
        source="default_broker_plan.display_name", read_only=True, default=""
    )

    class Meta:
        model = User
        fields = ["id", "email", "name", "default_broker_plan", "default_broker_plan_label"]
        read_only_fields = ["id", "email"]


# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------

class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ["id", "symbol", "isin", "company_name", "exchange", "currency", "lot_size"]


class BrokerPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrokerPlan
        fields = [
            "id", "broker", "plan", "display_name", "notes", "segment",
            "exchange", "effective_from", "components", "is_system", "verified",
        ]


class PriceSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="stock.symbol", read_only=True)

    class Meta:
        model = PriceSnapshot
        fields = ["stock", "symbol", "price", "as_of", "source"]
        read_only_fields = ["as_of", "source"]


class CorporateActionSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="stock.symbol", read_only=True)

    class Meta:
        model = CorporateAction
        fields = ["id", "stock", "symbol", "type", "ex_date", "ratio_from", "ratio_to", "notes"]


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------

class TransactionSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="stock.symbol", read_only=True)
    company_name = serializers.CharField(source="stock.company_name", read_only=True)
    turnover = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "stock", "symbol", "company_name", "type", "quantity", "price",
            "trade_date", "sequence_no", "exchange", "turnover", "broker_plan",
            "charge_breakdown", "total_charges", "charge_override", "status",
            "supersedes", "idempotency_key", "notes", "created_at",
        ]
        read_only_fields = [
            "id", "charge_breakdown", "total_charges", "status", "supersedes", "created_at",
        ]

    def validate_quantity(self, v):
        if v <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return v

    def validate_price(self, v):
        if v <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return v

    def validate_trade_date(self, v):
        from datetime import date
        if v > date.today():
            raise serializers.ValidationError("Trade date cannot be in the future.")
        return v


class ChargePreviewSerializer(serializers.Serializer):
    """Input for POST /transactions/preview/ — computes without saving."""

    stock = serializers.PrimaryKeyRelatedField(queryset=Stock.objects.all())
    type = serializers.ChoiceField(choices=["BUY", "SELL", "OPENING_BALANCE"])
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6, min_value=Decimal("0.000001"))
    price = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    exchange = serializers.ChoiceField(choices=["NSE", "BSE"], default="NSE")
    broker_plan = serializers.PrimaryKeyRelatedField(
        queryset=BrokerPlan.objects.all(), required=False, allow_null=True
    )


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------

class LotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lot
        fields = [
            "id", "original_qty", "remaining_qty", "buy_price", "buy_charges",
            "cost_per_share", "break_even", "acquisition_date",
        ]


class AllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellAllocation
        fields = [
            "id", "sell_transaction", "lot", "qty", "fifo_cost_basis",
            "fifo_realized_pnl", "wac_cost_basis", "wac_realized_pnl",
            "holding_days", "term",
        ]


class PositionSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="stock.symbol", read_only=True)
    company_name = serializers.CharField(source="stock.company_name", read_only=True)
    exchange = serializers.CharField(source="stock.exchange", read_only=True)

    class Meta:
        model = Position
        fields = [
            "id", "stock", "symbol", "company_name", "exchange", "quantity",
            "cost_basis", "average_cost", "realized_pnl", "realized_pnl_fifo",
            "total_charges_paid", "break_even", "recovery_break_even",
            "ledger_hash", "last_rebuilt_at",
        ]
