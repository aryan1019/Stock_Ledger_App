"""
Seeded broker charge plans — Indian equity delivery.

RATES ARE DATA, NOT CONSTANTS. In the real application these live in the
database with effective_from / effective_to dates and are editable by the
user. This module is the seed fixture.

Kotak Neo Trade Free YOUTH is VERIFIED against two real broker bills:

    BUY  turnover 47,250          SELL turnover 50,000
      Brokerage        0.00         Brokerage        0.00
      Transaction chg  1.40         Transaction chg  1.49
      STT/CTT         47.25         STT/CTT         50.00
      SEBI             0.05         SEBI             0.05
      Stamp duty       7.00         Stamp duty       0.00
      GST              0.26         GST              0.28
      TOTAL           55.96         TOTAL           51.82   <- no DP charge

Those bills settled four things that were previously guessed:

1. Exchange transaction charge is 0.00297% on NSE, not 0.00307%. The higher
   published figure bundles IPFT, so charging both double-counted it.
2. There is therefore NO separate IPFT component. It is inside the exchange
   charge.
3. Stamp duty rounds to the NEAREST RUPEE (7.0875 was billed as 7.00).
4. Kotak's YOUTH plan levies NO DP charge on a sell.

STT rounding differs by broker presentation — Kotak bills it unrounded to
2dp (47.25), Zerodha publishes it rounded to the nearest rupee — so it is a
per-plan setting rather than a constant.

Sources:
  Kotak Neo  in-app charge breakdown, supplied by the account holder (2026)
             https://www.kotakneo.com/pricing/trade-free-youth/
  Zerodha    https://zerodha.com/charges/
  Angel One  https://www.angelone.in/exchange-transaction-charges
  Upstox     https://upstox.com/brokerage-charges/
  Groww      https://www.chittorgarh.com/brokerage_charges/groww/173/
"""

from __future__ import annotations

from datetime import date

from .charges import ChargePlan, Component
from .models import Basis, Exchange, Rounding, Segment, Side

RATES_VERIFIED_ON = date(2026, 9, 2)
EFFECTIVE_FROM = date(2026, 4, 1)

# --------------------------------------------------------------------------
# Statutory / exchange components
# --------------------------------------------------------------------------

STT_RATE = "0.001"            # 0.1% both sides, delivery
STAMP_RATE = "0.00015"        # 0.015% BUY side only
SEBI_RATE = "0.000001"        # Rs 10 per crore
GST_RATE = "0.18"             # 18%

# Verified against a real NSE bill. IPFT is included in this figure — do not
# add a separate IPFT component on top, that is a double count.
EXCH_TXN_RATE = {
    Exchange.NSE: "0.0000297",   # 0.00297%  (verified)
    Exchange.BSE: "0.0000375",   # 0.00375%  (group A; verify against a BSE bill)
}

GST_BASE = ("BROKERAGE", "EXCH_TXN", "SEBI")
GST_BASE_WITH_DP = GST_BASE + ("DP",)


def _statutory(exchange: Exchange, stt_rounding: Rounding) -> list[Component]:
    return [
        Component("STT", "Securities Transaction Tax", Basis.PERCENT_TURNOVER,
                  side=Side.BOTH, rate=STT_RATE, rounding=stt_rounding),
        Component("EXCH_TXN", f"Exchange txn charge ({exchange.value})", Basis.PERCENT_TURNOVER,
                  side=Side.BOTH, rate=EXCH_TXN_RATE[exchange]),
        Component("SEBI", "SEBI turnover fee", Basis.PERCENT_TURNOVER,
                  side=Side.BOTH, rate=SEBI_RATE),
        Component("STAMP", "Stamp duty", Basis.PERCENT_TURNOVER,
                  side=Side.BUY, rate=STAMP_RATE, rounding=Rounding.NEAREST_RUPEE),
    ]


def _plan(broker, plan_name, exchange, brokerage: Component, dp: Component | None,
          gst_of: tuple[str, ...], display_name: str = "", notes: str = "",
          stt_rounding: Rounding = Rounding.NEAREST_RUPEE,
          verified: bool = False) -> ChargePlan:
    components = [brokerage, *_statutory(exchange, stt_rounding)]
    if dp is not None:
        components.append(dp)
    components.append(
        Component("GST", "GST @ 18%", Basis.PERCENT_OF, side=Side.BOTH, rate=GST_RATE, of=gst_of)
    )
    return ChargePlan(
        broker=broker,
        plan=plan_name,
        segment=Segment.EQUITY_DELIVERY.value,
        exchange=exchange.value,
        effective_from=EFFECTIVE_FROM,
        display_name=display_name,
        notes=notes,
        verified=verified,
        components=components,
    )


# --------------------------------------------------------------------------
# Broker plans
# --------------------------------------------------------------------------

def _kotak_neo_youth(exchange: Exchange) -> ChargePlan:
    """
    VERIFIED against two real bills. Zero delivery brokerage AND no DP charge.
    Eligibility: enrolled under 30.
    """
    return _plan(
        "KOTAK_NEO", "TRADE_FREE_YOUTH", exchange,
        brokerage=Component("BROKERAGE", "Brokerage", Basis.FLAT_PER_ORDER,
                            side=Side.BOTH, amount="0.00"),
        dp=None,                       # no DP charge on this plan
        gst_of=GST_BASE,
        display_name="Kotak Neo - Trade Free YOUTH (zero brokerage, no DP)",
        notes="Rs 0 delivery brokerage and no DP charge on sells. "
              "Rs 10 per F&O order. Enrol under 30.",
        stt_rounding=Rounding.TWO_DP,  # billed as 47.25, not 47
        verified=True,
    )


def _kotak_neo_trade_free(exchange: Exchange) -> ChargePlan:
    """
    NOT the youth plan. Delivery brokerage is 0.20% per executed order after
    the first 30 days. DP charge unverified — check a contract note.
    """
    return _plan(
        "KOTAK_NEO", "TRADE_FREE", exchange,
        brokerage=Component("BROKERAGE", "Brokerage", Basis.PERCENT_TURNOVER,
                            side=Side.BOTH, rate="0.002"),
        dp=Component("DP", "DP charge (per scrip/day)", Basis.FLAT_PER_SCRIP_PER_DAY,
                     side=Side.SELL, amount="20.00"),
        gst_of=GST_BASE_WITH_DP,
        display_name="Kotak Neo - Trade Free (0.20% delivery)",
        notes="General plan. Delivery 0.20% per order after the first 30 days; "
              "Rs 10 per F&O order. NOT the zero-brokerage youth plan.",
        stt_rounding=Rounding.TWO_DP,
    )


def _zerodha(exchange: Exchange) -> ChargePlan:
    return _plan(
        "ZERODHA", "STANDARD", exchange,
        brokerage=Component("BROKERAGE", "Brokerage", Basis.FLAT_PER_ORDER,
                            side=Side.BOTH, amount="0.00"),
        # Rs 3.5 CDSL + Rs 9.5 Zerodha + Rs 2.34 GST = Rs 15.34, GST already inside
        dp=Component("DP", "DP charge (per scrip/day)", Basis.FLAT_PER_SCRIP_PER_DAY,
                     side=Side.SELL, amount="15.34", gst_inclusive=True),
        gst_of=GST_BASE,               # DP excluded: already GST-inclusive
        display_name="Zerodha - Standard",
        notes="Zero delivery brokerage. DP Rs 15.34 per scrip on any day you sell.",
    )


def _groww(exchange: Exchange) -> ChargePlan:
    return _plan(
        "GROWW", "STANDARD", exchange,
        brokerage=Component("BROKERAGE", "Brokerage", Basis.PERCENT_TURNOVER,
                            side=Side.BOTH, rate="0.001", cap="20.00"),
        dp=Component("DP", "DP charge (per scrip/day)", Basis.FLAT_PER_SCRIP_PER_DAY,
                     side=Side.SELL, amount="20.00"),
        gst_of=GST_BASE_WITH_DP,
        display_name="Groww - Standard",
        notes="Delivery brokerage: lower of Rs 20 or 0.1% per order.",
    )


def _upstox(exchange: Exchange) -> ChargePlan:
    return _plan(
        "UPSTOX", "STANDARD", exchange,
        brokerage=Component("BROKERAGE", "Brokerage", Basis.FLAT_PER_ORDER,
                            side=Side.BOTH, amount="20.00"),
        dp=Component("DP", "DP charge (per scrip/day)", Basis.FLAT_PER_SCRIP_PER_DAY,
                     side=Side.SELL, amount="20.00", gst_inclusive=True),
        gst_of=GST_BASE,
        display_name="Upstox - Standard",
        notes="Flat Rs 20 per executed order on delivery.",
    )


def _angel_one(exchange: Exchange) -> ChargePlan:
    return _plan(
        "ANGEL_ONE", "STANDARD", exchange,
        # lower of Rs 20 or 0.1% per executed order, minimum Rs 5
        brokerage=Component("BROKERAGE", "Brokerage", Basis.PERCENT_TURNOVER,
                            side=Side.BOTH, rate="0.001", cap="20.00", floor="5.00"),
        dp=Component("DP", "DP charge (per ISIN debit)", Basis.FLAT_PER_SCRIP_PER_DAY,
                     side=Side.SELL, amount="20.00"),
        gst_of=GST_BASE_WITH_DP,
        display_name="Angel One - Standard",
        notes="Delivery brokerage: lower of Rs 20 or 0.1%, minimum Rs 5.",
    )


_BUILDERS = {
    "KOTAK_NEO:TRADE_FREE_YOUTH": _kotak_neo_youth,
    "KOTAK_NEO:TRADE_FREE": _kotak_neo_trade_free,
    "ZERODHA:STANDARD": _zerodha,
    "GROWW:STANDARD": _groww,
    "UPSTOX:STANDARD": _upstox,
    "ANGEL_ONE:STANDARD": _angel_one,
}


def get_plan(broker: str, plan: str = "STANDARD",
             exchange: Exchange = Exchange.NSE) -> ChargePlan:
    """Fetch a seeded plan. In production this reads from the database."""
    key = f"{broker.upper()}:{plan.upper()}"
    if key not in _BUILDERS:
        raise KeyError(f"Unknown plan {key}. Available: {sorted(_BUILDERS)}")
    return _BUILDERS[key](exchange)


def list_plans() -> list[str]:
    return sorted(_BUILDERS)


ZERO_CHARGE_PLAN = ChargePlan(
    broker="NONE", plan="ZERO", segment=Segment.EQUITY_DELIVERY.value,
    exchange=Exchange.NSE.value, effective_from=EFFECTIVE_FROM, components=[],
    display_name="No charges", notes="Used to demonstrate the pure accounting model.",
)
"""A plan with no charges at all."""
