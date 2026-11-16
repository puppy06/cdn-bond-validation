"""Thin QuantLib wrapper for Canadian fixed-rate bonds.

Every convention lives in `Conventions`, so a test (or a deliberately injected
bug) can change one thing at a time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import QuantLib as ql


@dataclass
class Conventions:
    calendar: ql.Calendar = field(default_factory=ql.Canada)
    day_count: ql.DayCounter = field(
        default_factory=lambda: ql.ActualActual(ql.ActualActual.ISMA)
    )
    settlement_days: int = 1  # verify current GoC settlement cycle
    frequency: int = ql.Semiannual
    compounding: int = ql.Compounded
    # Unadjusted so cash-flow times match the reference implementation.
    # Real payments roll to the next business day: a good convention to test later.
    payment_convention: int = ql.Unadjusted


@dataclass
class Analytics:
    clean: float
    dirty: float
    accrued: float
    ytm: float
    mod_duration: float
    convexity: float
    dv01: float  # from modified duration
    dv01_bump: float  # from a +/- 1bp reprice


def to_ql(d: date) -> ql.Date:
    return ql.Date(d.day, d.month, d.year)


def make_schedule(issue: date, maturity: date, conv: Conventions) -> ql.Schedule:
    return ql.Schedule(
        to_ql(issue), to_ql(maturity), ql.Period(conv.frequency), conv.calendar,
        ql.Unadjusted, ql.Unadjusted, ql.DateGeneration.Backward, False,
    )


def make_bond(issue: date, maturity: date, coupon: float, face: float = 100.0,
              conv: Conventions | None = None) -> ql.FixedRateBond:
    conv = conv or Conventions()
    return ql.FixedRateBond(
        conv.settlement_days, face, make_schedule(issue, maturity, conv),
        [coupon], conv.day_count, conv.payment_convention,
    )


def settlement_date(trade: date, conv: Conventions | None = None) -> ql.Date:
    conv = conv or Conventions()
    return conv.calendar.advance(to_ql(trade), conv.settlement_days, ql.Days)


def _dirty(bond, y, s, conv):
    return ql.BondFunctions.dirtyPrice(bond, y, conv.day_count, conv.compounding, conv.frequency, s)


def analytics_from_yield(bond: ql.Bond, ytm: float, settle: date,
                         conv: Conventions | None = None) -> Analytics:
    conv = conv or Conventions()
    s = to_ql(settle)
    args = (conv.day_count, conv.compounding, conv.frequency)
    clean = ql.BondFunctions.cleanPrice(bond, ytm, *args, s)
    dirty = _dirty(bond, ytm, s, conv)
    md = ql.BondFunctions.duration(bond, ytm, *args, ql.Duration.Modified, s)
    bp = 1e-4
    return Analytics(
        clean=clean,
        dirty=dirty,
        accrued=ql.BondFunctions.accruedAmount(bond, s),
        ytm=ytm,
        mod_duration=md,
        convexity=ql.BondFunctions.convexity(bond, ytm, *args, s),
        dv01=md * dirty * bp,
        dv01_bump=(_dirty(bond, ytm - bp, s, conv) - _dirty(bond, ytm + bp, s, conv)) / 2,
    )


def yield_from_clean(bond: ql.Bond, clean: float, settle: date,
                     conv: Conventions | None = None) -> float:
    conv = conv or Conventions()
    args = (conv.day_count, conv.compounding, conv.frequency, to_ql(settle))
    try:  # QuantLib >= 1.34
        return ql.BondFunctions.bondYield(bond, ql.BondPrice(clean, ql.BondPrice.Clean), *args)
    except (AttributeError, TypeError, NotImplementedError):  # older releases
        return ql.BondFunctions.bondYield(bond, clean, *args)


# ------------------------------------------------------------------ curve
def build_curve(trade: date, quotes: list[tuple[date, date, float, float]],
                conv: Conventions | None = None) -> ql.YieldTermStructureHandle:
    """Bootstrap a discount curve from bonds quoted by yield.

    quotes: (issue, maturity, coupon, yield). Sets the global evaluation date.
    """
    conv = conv or Conventions()
    ql.Settings.instance().evaluationDate = to_ql(trade)
    s = settlement_date(trade, conv)
    helpers = []
    for issue, maturity, cpn, y in quotes:
        bond = make_bond(issue, maturity, cpn, conv=conv)
        clean = ql.BondFunctions.cleanPrice(
            bond, y, conv.day_count, conv.compounding, conv.frequency, s)
        helpers.append(ql.FixedRateBondHelper(
            ql.QuoteHandle(ql.SimpleQuote(clean)), conv.settlement_days, 100.0,
            make_schedule(issue, maturity, conv), [cpn], conv.day_count,
            conv.payment_convention,
        ))
    curve = ql.PiecewiseLogCubicDiscount(to_ql(trade), helpers, ql.Actual365Fixed())
    curve.enableExtrapolation()
    return ql.YieldTermStructureHandle(curve)


# --------------------------------------------------------------- callable
def _call_price(p: float):
    try:
        return ql.BondPrice(p, ql.BondPrice.Clean)
    except AttributeError:  # older releases
        return ql.CallabilityPrice(p, ql.CallabilityPrice.Clean)


def price_callable(issue: date, maturity: date, coupon: float, call_dates: list[date],
                   curve: ql.YieldTermStructureHandle, a: float = 0.03,
                   sigma: float = 0.01, grid: int = 200,
                   conv: Conventions | None = None) -> tuple[float, float]:
    """Return (callable clean price, equivalent straight bond clean price)."""
    conv = conv or Conventions()
    schedule = make_schedule(issue, maturity, conv)
    calls = ql.CallabilitySchedule()
    for d in call_dates:
        calls.append(ql.Callability(_call_price(100.0), ql.Callability.Call, to_ql(d)))
    cb = ql.CallableFixedRateBond(
        conv.settlement_days, 100.0, schedule, [coupon], conv.day_count,
        conv.payment_convention, 100.0, to_ql(issue), calls,
    )
    cb.setPricingEngine(ql.TreeCallableFixedRateBondEngine(ql.HullWhite(curve, a, sigma), grid))
    straight = make_bond(issue, maturity, coupon, conv=conv)
    straight.setPricingEngine(ql.DiscountingBondEngine(curve))
    return cb.cleanPrice(), straight.cleanPrice()
