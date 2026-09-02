from decimal import Decimal

from django.db import IntegrityError, models
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from calculations import D, ENGINE, Side, display, solve_breakeven, xirr
from calculations.engine import InsufficientQuantity, InvalidTransaction
from charges.models import BrokerPlan
from portfolio import analytics, services
from portfolio.models import Lot, Position
from stocks.models import CorporateAction, PriceSnapshot, Stock
from transactions.models import Portfolio, Transaction

from .serializers import (
    AllocationSerializer, BrokerPlanSerializer, ChargePreviewSerializer,
    CorporateActionSerializer, LotSerializer, PositionSerializer, PriceSerializer,
    RegisterSerializer, StockSerializer, TransactionSerializer, UserSerializer,
)


def money(v):
    return str(display(v))


# ==========================================================================
# Auth
# ==========================================================================

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        Portfolio.default_for(user)
        user.default_broker_plan = services.resolve_plan(user)
        user.save(update_fields=["default_broker_plan"])
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    def post(self, request):
        token = request.data.get("refresh")
        if token:
            try:
                RefreshToken(token).blacklist()
            except Exception:
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        s = UserSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


# ==========================================================================
# Reference data
# ==========================================================================

class StockViewSet(viewsets.ModelViewSet):
    serializer_class = StockSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Stock.objects.filter(is_active=True)
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(symbol__icontains=q)
        return qs[:50]


class BrokerPlanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BrokerPlanSerializer
    pagination_class = None

    def get_queryset(self):
        qs = BrokerPlan.objects.filter(is_system=True) | BrokerPlan.objects.owned_by(
            self.request.user
        )
        exchange = self.request.query_params.get("exchange", "NSE")
        return qs.filter(exchange=exchange).distinct()


class CorporateActionViewSet(viewsets.ModelViewSet):
    serializer_class = CorporateActionSerializer
    pagination_class = None
    queryset = CorporateAction.objects.all()

    def perform_create(self, serializer):
        ca = serializer.save()
        services.rebuild(self.request.user, ca.stock)


class PriceView(APIView):
    def get(self, request, stock_id):
        snap = PriceSnapshot.objects.owned_by(request.user).filter(stock_id=stock_id).first()
        if not snap:
            return Response({"detail": "No price recorded."}, status=404)
        return Response(PriceSerializer(snap).data)

    def put(self, request, stock_id):
        stock = get_object_or_404(Stock, pk=stock_id)
        price = D(str(request.data.get("price", "0")))
        if price <= 0:
            return Response({"price": ["Price must be greater than zero."]}, status=400)
        snap, _ = PriceSnapshot.objects.update_or_create(
            user=request.user, stock=stock, defaults={"price": price}
        )
        return Response(PriceSerializer(snap).data)


# ==========================================================================
# Ledger
# ==========================================================================

class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = (
            Transaction.objects.owned_by(self.request.user)
            .filter(status=Transaction.ACTIVE)
            .select_related("stock")
        )
        stock = self.request.query_params.get("stock")
        if stock:
            qs = qs.filter(stock_id=stock)
        kind = self.request.query_params.get("type")
        if kind:
            qs = qs.filter(type=kind)
        date_from = self.request.query_params.get("from")
        if date_from:
            qs = qs.filter(trade_date__gte=date_from)
        date_to = self.request.query_params.get("to")
        if date_to:
            qs = qs.filter(trade_date__lte=date_to)
        search = self.request.query_params.get("q")
        if search:
            qs = qs.filter(stock__symbol__icontains=search)
        return qs

    def _next_sequence_no(self, user, stock, trade_date):
        """
        Same-day trades must replay in the order they were entered. Ties broken
        by a random UUID are not stable, so the sequence number is assigned
        server-side whenever the client does not supply one.
        """
        last = (
            Transaction.objects.owned_by(user)
            .filter(stock=stock, trade_date=trade_date)
            .aggregate(models.Max("sequence_no"))["sequence_no__max"]
        )
        return 0 if last is None else last + 1

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)

        portfolio = Portfolio.default_for(request.user)
        plan = s.validated_data.get("broker_plan") or services.resolve_plan(
            request.user, s.validated_data.get("exchange", "NSE")
        )
        extra = {"user": request.user, "portfolio": portfolio, "broker_plan": plan}
        if "sequence_no" not in request.data:
            extra["sequence_no"] = self._next_sequence_no(
                request.user, s.validated_data["stock"], s.validated_data["trade_date"]
            )

        try:
            with db_transaction.atomic():
                row = s.save(**extra)
        except IntegrityError:
            existing = Transaction.objects.owned_by(request.user).filter(
                idempotency_key=request.data.get("idempotency_key")
            ).first()
            if existing:
                return Response(self.get_serializer(existing).data, status=200)
            raise

        try:
            services.rebuild(request.user, row.stock, portfolio)
        except (InsufficientQuantity, InvalidTransaction) as exc:
            row.delete()
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        row.refresh_from_db()
        return Response(self.get_serializer(row).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Soft delete — the ledger is append-only, so we supersede and replay."""
        row = self.get_object()
        row.status = Transaction.SUPERSEDED
        row.save(update_fields=["status"])
        try:
            services.rebuild(request.user, row.stock, row.portfolio)
        except (InsufficientQuantity, InvalidTransaction) as exc:
            row.status = Transaction.ACTIVE
            row.save(update_fields=["status"])
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def correct(self, request, pk=None):
        """Append a corrected row and supersede the original. History is kept."""
        original = self.get_object()
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)

        plan = s.validated_data.get("broker_plan") or original.broker_plan
        new_row = s.save(
            user=request.user, portfolio=original.portfolio,
            broker_plan=plan, supersedes=original,
        )
        original.status = Transaction.SUPERSEDED
        original.save(update_fields=["status"])
        try:
            services.rebuild(request.user, new_row.stock, original.portfolio)
        except (InsufficientQuantity, InvalidTransaction) as exc:
            new_row.delete()
            original.status = Transaction.ACTIVE
            original.save(update_fields=["status"])
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        new_row.refresh_from_db()
        return Response(self.get_serializer(new_row).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def preview(self, request):
        """
        Charges and resulting position WITHOUT saving. This powers the live
        preview on the Add Transaction screen.
        """
        s = ChargePreviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data

        plan_row = v.get("broker_plan") or services.resolve_plan(request.user, v["exchange"])
        plan = plan_row.to_engine_plan()
        side = Side.SELL if v["type"] == "SELL" else Side.BUY
        qty, price = D(v["quantity"]), D(v["price"])

        breakdown = ENGINE.compute(quantity=qty, price=price, side=side, plan=plan)

        pos = Position.objects.owned_by(request.user).filter(stock=v["stock"]).first()
        cur_qty = pos.quantity if pos else Decimal("0")
        cur_basis = pos.cost_basis if pos else Decimal("0")
        cur_avg = pos.average_cost if pos else Decimal("0")

        if side == Side.BUY:
            new_qty = cur_qty + qty
            new_basis = cur_basis + qty * price + breakdown.total
        else:
            new_qty = cur_qty - qty
            new_basis = cur_basis - (cur_avg * qty)

        new_avg = (new_basis / new_qty) if new_qty > 0 else Decimal("0")
        new_be = solve_breakeven(new_qty, new_basis, plan) if new_qty > 0 else Decimal("0")

        realized = None
        if side == Side.SELL and cur_qty > 0:
            realized = qty * price - breakdown.total - cur_avg * qty

        return Response({
            "plan": plan_row.display_name,
            "turnover": money(qty * price),
            "charges": [
                {"code": line.code, "label": line.label, "amount": money(line.amount)}
                for line in breakdown.lines
            ],
            "total_charges": money(breakdown.total),
            "net_amount": money(
                qty * price + breakdown.total if side == Side.BUY
                else qty * price - breakdown.total
            ),
            "before": {
                "quantity": str(cur_qty), "average_cost": money(cur_avg),
                "cost_basis": money(cur_basis),
                "break_even": money(pos.break_even) if pos else "0.00",
            },
            "after": {
                "quantity": str(new_qty), "average_cost": money(new_avg),
                "cost_basis": money(new_basis), "break_even": money(new_be),
            },
            "average_cost_delta": money(new_avg - cur_avg) if cur_qty > 0 and new_qty > 0 else None,
            "realized_pnl": money(realized) if realized is not None else None,
            "sufficient_quantity": (side == Side.BUY) or (qty <= cur_qty),
            "held_quantity": str(cur_qty),
        })


# ==========================================================================
# Portfolio
# ==========================================================================

class PortfolioListView(APIView):
    def get(self, request):
        positions = (
            Position.objects.owned_by(request.user)
            .filter(quantity__gt=0).select_related("stock")
        )
        prices = {
            p.stock_id: p.price
            for p in PriceSnapshot.objects.owned_by(request.user)
        }
        out = []
        for pos in positions:
            price = prices.get(pos.stock_id, pos.average_cost)
            mv = pos.quantity * price
            unrealized = mv - pos.cost_basis
            out.append({
                **PositionSerializer(pos).data,
                "current_price": money(price),
                "has_price": pos.stock_id in prices,
                "market_value": money(mv),
                "unrealized_pnl": money(unrealized),
                "total_pnl": money(unrealized + pos.realized_pnl),
                "vs_break_even_pct": money(
                    (price - pos.break_even) / pos.break_even * 100
                ) if pos.break_even > 0 else "0.00",
            })
        return Response(out)


class PortfolioSummaryView(APIView):
    def get(self, request):
        positions = list(
            Position.objects.owned_by(request.user).select_related("stock")
        )
        prices = {p.stock_id: p.price for p in PriceSnapshot.objects.owned_by(request.user)}

        invested = market_value = realized = charges = Decimal("0")
        for pos in positions:
            realized += pos.realized_pnl
            charges += pos.total_charges_paid
            if pos.quantity > 0:
                invested += pos.cost_basis
                market_value += pos.quantity * prices.get(pos.stock_id, pos.average_cost)

        unrealized = market_value - invested
        total = unrealized + realized

        flows = []
        for row in Transaction.objects.owned_by(request.user).filter(status=Transaction.ACTIVE):
            amount = row.quantity * row.price
            flows.append((row.trade_date, amount if row.type == "SELL" else -amount))
        if market_value > 0:
            from datetime import date
            flows.append((date.today(), market_value))

        return Response({
            "invested": money(invested),
            "market_value": money(market_value),
            "unrealized_pnl": money(unrealized),
            "realized_pnl": money(realized),
            "total_pnl": money(total),
            "total_charges_paid": money(charges),
            "return_pct": money(total / invested * 100) if invested > 0 else "0.00",
            "xirr_pct": money(xirr(flows) * 100) if len(flows) > 1 else "0.00",
            "holdings_count": sum(1 for p in positions if p.quantity > 0),
            "prices_missing": sum(
                1 for p in positions if p.quantity > 0 and p.stock_id not in prices
            ),
        })


class StockDetailView(APIView):
    def get(self, request, stock_id):
        stock = get_object_or_404(Stock, pk=stock_id)
        report = services.position_report(request.user, stock)
        if report is None:
            return Response({"detail": "No transactions for this stock."}, status=404)

        pos = Position.objects.owned_by(request.user).filter(stock=stock).first()
        rows = (
            Transaction.objects.owned_by(request.user)
            .filter(stock=stock, status=Transaction.ACTIVE).select_related("stock")
        )
        lots = Lot.objects.owned_by(request.user).filter(
            position=pos, remaining_qty__gt=0
        ) if pos else Lot.objects.none()

        return Response({
            "stock": StockSerializer(stock).data,
            "position": PositionSerializer(pos).data if pos else None,
            "current_price": money(report.current_price),
            "has_price": services.current_price(request.user, stock) is not None,
            "market_value": money(report.market_value),
            "break_even": money(report.break_even),
            "recovery_break_even": money(report.recovery_break_even),
            "exit_charges": money(report.exit_charges),
            "realized_pnl": money(report.realized_pnl),
            "realized_pnl_fifo": money(report.realized_pnl_fifo),
            "unrealized_pnl_gross": money(report.unrealized_pnl_gross),
            "unrealized_pnl_net": money(report.unrealized_pnl_net),
            "total_pnl": money(report.total_pnl),
            "total_charges_paid": money(report.total_charges_paid),
            "return_pct": money(report.return_pct),
            "broker_style_average": money(report.broker_style_average),
            "lots": [
                {
                    **LotSerializer(db_lot).data,
                    "holding_days": r.holding_days,
                    "term": r.term.value,
                    "days_to_long_term": r.days_to_long_term,
                    "unrealized_pnl": money(r.unrealized_pnl),
                }
                for db_lot, r in zip(lots, report.lots)
            ],
            "transactions": TransactionSerializer(rows, many=True).data,
            "allocations": AllocationSerializer(
                pos.lots.first().allocations.all() if pos and pos.lots.exists() else [],
                many=True,
            ).data,
        })


class AnalyticsView(APIView):
    """
    Period P&L for the dashboard date range.

    ?preset=7D|30D|90D|180D|1Y|ALL  or  ?from=YYYY-MM-DD&to=YYYY-MM-DD
    Explicit dates win over a preset.
    """

    def get(self, request):
        try:
            start, end = analytics.resolve_range(
                request.query_params.get("preset"),
                request.query_params.get("from"),
                request.query_params.get("to"),
            )
        except ValueError:
            return Response(
                {"detail": "Dates must be YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST
            )
        if start > end:
            return Response(
                {"detail": "The start date is after the end date."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(analytics.period_report(request.user, start, end))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rebuild_view(request):
    """Force a full rebuild — proves the projection is derived, not primary."""
    rebuilt = services.rebuild_all(request.user)
    return Response({"rebuilt": len([r for r in rebuilt if r])})
