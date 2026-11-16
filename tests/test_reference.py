"""Sanity tests on the pure-Python reference itself. No QuantLib needed.

If the reference is wrong, every comparison against it is meaningless,
so it gets its own known-answer tests first.
"""
from datetime import date

import pytest

from cdnbond import reference as ref
from conftest import SETTLE

B = ref.Bond(date(2022, 12, 1), date(2032, 12, 1), 0.0325)


def test_schedule_is_semiannual_and_backward():
    d = ref.coupon_dates(B)
    assert d[0] == B.issue and d[-1] == B.maturity
    assert len(d) == 21


def test_irregular_issue_is_rejected():
    with pytest.raises(ValueError):
        ref.coupon_dates(ref.Bond(date(2022, 11, 15), date(2032, 12, 1), 0.03))


def test_par_bond_on_coupon_date():
    on_coupon = date(2026, 12, 1)
    assert ref.clean_price(B, B.coupon, on_coupon) == pytest.approx(100.0, abs=1e-10)
    assert ref.accrued_isma(B, on_coupon) == 0.0


def test_zero_coupon_matches_closed_form():
    z = ref.Bond(date(2025, 6, 1), date(2030, 6, 1), 0.0)
    settle = date(2026, 6, 1)  # exactly 4 years, 8 periods
    assert ref.dirty_price(z, 0.04, settle) == pytest.approx(100 / 1.02 ** 8, abs=1e-12)


def test_price_yield_round_trip():
    p = ref.clean_price(B, 0.0287, SETTLE)
    assert ref.yield_from_clean(B, p, SETTLE) == pytest.approx(0.0287, abs=1e-10)


def test_dv01_matches_bump_and_reprice():
    y, bp = 0.03, 1e-4
    bump = (ref.dirty_price(B, y - bp, SETTLE) - ref.dirty_price(B, y + bp, SETTLE)) / 2
    assert ref.dv01(B, y, SETTLE) == pytest.approx(bump, rel=1e-6)


def test_convexity_matches_second_difference():
    y, h = 0.03, 1e-4
    p = lambda yy: ref.dirty_price(B, yy, SETTLE)
    numeric = (p(y + h) - 2 * p(y) + p(y - h)) / h**2 / p(y)
    assert ref.convexity(B, y, SETTLE) == pytest.approx(numeric, rel=1e-5)


def test_price_falls_as_yield_rises():
    prices = [ref.clean_price(B, y, SETTLE) for y in (0.01, 0.02, 0.03, 0.04)]
    assert prices == sorted(prices, reverse=True)


def test_canadian_accrued_hand_example():
    # 5% bond, 30 days into the period: 5 * 30 / 365
    b = ref.Bond(date(2025, 6, 1), date(2030, 6, 1), 0.05)
    assert ref.accrued_canadian(b, date(2026, 7, 1)) == pytest.approx(5 * 30 / 365)


def test_canadian_accrued_reaches_half_coupon_at_period_end():
    b = ref.Bond(date(2025, 6, 1), date(2030, 6, 1), 0.05)
    # one day before the Dec 1 coupon: 2.5 - 5 * 1/365
    assert ref.accrued_canadian(b, date(2026, 11, 30)) == pytest.approx(2.5 - 5 / 365)
