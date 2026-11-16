"""Independent, pure-Python bond math.

This module deliberately does NOT import QuantLib. It is the "second opinion"
the test suite compares QuantLib against, so it must be written from the
formulas, not from QuantLib's code.

Conventions implemented (match the QuantLib wrapper in pricer.py):
  * Semi-annual coupons, schedule generated backward from maturity, dates unadjusted.
  * Regular schedules only: the issue date must fall on the coupon cycle.
  * Price/yield uses street convention: the first (partial) period is discounted
    as a fraction of a semi-annual period, days / days-in-period (ActualActual ISMA).
  * Accrued interest is ISMA (coupon/2 * days/days-in-period) by default.
    accrued_canadian() implements the Canadian Actual/365 bond convention separately.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

FREQ = 2  # semi-annual


@dataclass(frozen=True)
class Bond:
    issue: date
    maturity: date
    coupon: float  # annual rate as a decimal, e.g. 0.0325
    face: float = 100.0


def add_months(d: date, n: int) -> date:
    """Shift by n months, clamping the day to month end (same as QuantLib)."""
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def coupon_dates(bond: Bond) -> list[date]:
    """Schedule dates including issue date, generated backward from maturity."""
    dates = [bond.maturity]
    k = 1
    while True:
        d = add_months(bond.maturity, -6 * k)
        if d <= bond.issue:
            break
        dates.append(d)
        k += 1
    if add_months(bond.maturity, -6 * k) != bond.issue:
        raise ValueError("irregular first period: issue date not on the coupon cycle")
    dates.append(bond.issue)
    return sorted(dates)


def _period(bond: Bond, settle: date) -> tuple[date, date, list[date]]:
    """(previous coupon date, next coupon date, remaining payment dates > settle)."""
    dates = coupon_dates(bond)
    if not (bond.issue <= settle < bond.maturity):
        raise ValueError("settlement must be in [issue, maturity)")
    remaining = [d for d in dates if d > settle]
    prev = max(d for d in dates if d <= settle)
    return prev, remaining[0], remaining


def _cashflows(bond: Bond, settle: date) -> list[tuple[float, float]]:
    """List of (time in years from settlement, amount)."""
    prev, nxt, remaining = _period(bond, settle)
    t1 = 0.5 * (nxt - settle).days / (nxt - prev).days
    cpn = bond.face * bond.coupon / FREQ
    flows = []
    for i, d in enumerate(remaining):
        amt = cpn + (bond.face if d == bond.maturity else 0.0)
        flows.append((t1 + 0.5 * i, amt))
    return flows


# ---------------------------------------------------------------- accrued
def accrued_isma(bond: Bond, settle: date) -> float:
    prev, nxt, _ = _period(bond, settle)
    return bond.face * bond.coupon / FREQ * (settle - prev).days / (nxt - prev).days


def accrued_canadian(bond: Bond, settle: date) -> float:
    """Canadian Actual/365 bond accrual.

    days < 182: coupon * days / 365
    otherwise:  coupon/2 - coupon * (days left in period) / 365
    TODO: confirm the 182-day threshold against an official market-convention source.
    """
    prev, nxt, _ = _period(bond, settle)
    c = bond.face * bond.coupon
    days = (settle - prev).days
    if days < 182:
        return c * days / 365
    return c / 2 - c * ((nxt - prev).days - days) / 365


# ---------------------------------------------------------- price / yield
def dirty_price(bond: Bond, y: float, settle: date) -> float:
    return sum(a / (1 + y / FREQ) ** (FREQ * t) for t, a in _cashflows(bond, settle))


def clean_price(bond: Bond, y: float, settle: date) -> float:
    return dirty_price(bond, y, settle) - accrued_isma(bond, settle)


def yield_from_clean(bond: Bond, clean: float, settle: date, tol: float = 1e-12) -> float:
    """Bisection: slow but impossible to get subtly wrong."""
    lo, hi = -0.05, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if clean_price(bond, mid, settle) > clean:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2


# -------------------------------------------------------------- risk
def modified_duration(bond: Bond, y: float, settle: date) -> float:
    flows = _cashflows(bond, settle)
    df = lambda t: (1 + y / FREQ) ** (-FREQ * t)
    p = sum(a * df(t) for t, a in flows)
    macaulay = sum(t * a * df(t) for t, a in flows) / p
    return macaulay / (1 + y / FREQ)


def convexity(bond: Bond, y: float, settle: date) -> float:
    """(1/P) d2P/dy2 with semi-annual compounding."""
    flows = _cashflows(bond, settle)
    p = sum(a * (1 + y / FREQ) ** (-FREQ * t) for t, a in flows)
    d2 = sum(a * t * (t + 1 / FREQ) * (1 + y / FREQ) ** (-FREQ * t - 2) for t, a in flows)
    return d2 / p


def dv01(bond: Bond, y: float, settle: date) -> float:
    """Price change (per face) for a 1bp fall in yield, from modified duration."""
    return modified_duration(bond, y, settle) * dirty_price(bond, y, settle) * 1e-4
