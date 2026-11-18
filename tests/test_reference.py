"""Sanity tests on the pure-Python reference itself. No QuantLib needed.

If the reference is wrong, every comparison against it is meaningless,
so it gets its own known-answer tests first. Inputs: the BoC benchmark bonds.
"""
from datetime import timedelta

import pytest

from cdnbond import reference as ref
from conftest import DV01_BUMP_TOL, SETTLE, half_years, next_coupon


def test_schedule_is_semiannual_and_backward(bond):
    d = ref.coupon_dates(bond)
    assert d[0] == bond.issue and d[-1] == bond.maturity
    assert len(d) == half_years(bond.issue, bond.maturity) + 1
    assert all(half_years(a, b) == 1 for a, b in zip(d, d[1:]))


def test_irregular_issue_is_rejected(bond):
    with pytest.raises(ValueError):
        ref.coupon_dates(ref.Bond(bond.issue.replace(day=15), bond.maturity, bond.coupon))


def test_par_bond_on_coupon_date(bond):
    on_coupon = next_coupon(bond, SETTLE)
    assert ref.clean_price(bond, bond.coupon, on_coupon) == pytest.approx(100.0, abs=1e-10)
    assert ref.accrued_isma(bond, on_coupon) == 0.0


def test_zero_coupon_matches_closed_form(bond, ytm):
    z = ref.Bond(bond.issue, bond.maturity, 0.0)  # same dates and yield, coupon set to zero
    settle = next_coupon(bond, SETTLE)  # on a coupon date, so t is a whole number of periods
    n = half_years(settle, bond.maturity)
    assert ref.dirty_price(z, ytm, settle) == pytest.approx(100 / (1 + ytm / 2) ** n, abs=1e-12)


def test_price_yield_round_trip(bond, ytm):
    p = ref.clean_price(bond, ytm, SETTLE)
    assert ref.yield_from_clean(bond, p, SETTLE) == pytest.approx(ytm, abs=1e-10)


def test_dv01_matches_bump_and_reprice(bond, ytm):
    bp = 1e-4
    bump = (ref.dirty_price(bond, ytm - bp, SETTLE) - ref.dirty_price(bond, ytm + bp, SETTLE)) / 2
    assert ref.dv01(bond, ytm, SETTLE) == pytest.approx(bump, rel=DV01_BUMP_TOL)


def test_convexity_matches_second_difference(bond, ytm):
    h = 1e-4
    p = lambda yy: ref.dirty_price(bond, yy, SETTLE)
    numeric = (p(ytm + h) - 2 * p(ytm) + p(ytm - h)) / h**2 / p(ytm)
    assert ref.convexity(bond, ytm, SETTLE) == pytest.approx(numeric, rel=1e-5)


def test_price_falls_as_yield_rises(bond, ytm):
    prices = [ref.clean_price(bond, ytm + d, SETTLE) for d in (-0.01, 0.0, 0.01, 0.02)]
    assert prices == sorted(prices, reverse=True)


def test_canadian_accrued_hand_example(bond):
    # 30 days into the period: coupon * 30 / 365
    prev, _, _ = ref._period(bond, SETTLE)
    assert ref.accrued_canadian(bond, prev + timedelta(days=30)) == pytest.approx(
        100 * bond.coupon * 30 / 365)


def test_canadian_accrued_one_day_before_next_coupon(bond):
    prev, nxt, _ = ref._period(bond, SETTLE)
    settle = nxt - timedelta(days=1)
    days, c = (settle - prev).days, 100 * bond.coupon
    # 182+ days in: half coupon less one day's accrual; shorter periods stay on the days/365 rule
    expected = c / 2 - c / 365 if days >= 182 else c * days / 365
    assert ref.accrued_canadian(bond, settle) == pytest.approx(expected)
