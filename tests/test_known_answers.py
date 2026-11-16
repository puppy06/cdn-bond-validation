"""Known answers and conventions checked directly against QuantLib."""
from datetime import date

import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer, reference as ref


def test_par_bond_prices_at_par_on_coupon_date():
    qb = pricer.make_bond(date(2022, 12, 1), date(2032, 12, 1), 0.0325)
    a = pricer.analytics_from_yield(qb, 0.0325, date(2026, 12, 1))
    assert a.clean == pytest.approx(100.0, abs=1e-10)
    assert a.accrued == pytest.approx(0.0, abs=1e-12)


def test_zero_coupon_closed_form():
    qb = pricer.make_bond(date(2025, 6, 1), date(2030, 6, 1), 0.0)
    a = pricer.analytics_from_yield(qb, 0.04, date(2026, 6, 1))
    assert a.dirty == pytest.approx(100 / 1.02 ** 8, abs=1e-10)


def test_t_plus_one_skips_remembrance_day():
    # Trade Tue 2026-11-10; Nov 11 is a holiday on QuantLib's Canada settlement calendar.
    assert pricer.settlement_date(date(2026, 11, 10)) == ql.Date(12, 11, 2026)


@pytest.mark.parametrize("settle", [date(2026, 7, 1), date(2026, 9, 15), date(2026, 11, 30)])
def test_quantlib_canadian_daycount_matches_hand_formula(settle):
    """QuantLib's Actual365Fixed(Canadian) vs the hand-written Canadian accrual.

    If this fails, decide which side is wrong and write it up in the README.
    """
    b = ref.Bond(date(2025, 6, 1), date(2030, 6, 1), 0.05)
    prev, nxt, _ = ref._period(b, settle)
    dc = ql.Actual365Fixed(ql.Actual365Fixed.Canadian)
    p, s, n = pricer.to_ql(prev), pricer.to_ql(settle), pricer.to_ql(nxt)
    ql_accrued = 100 * b.coupon * dc.yearFraction(p, s, p, n)
    assert ql_accrued == pytest.approx(ref.accrued_canadian(b, settle), abs=1e-10)


def test_canadian_and_isma_accrued_differ_mid_period():
    """Documents that the convention matters: same bond, same day, different accrued."""
    b = ref.Bond(date(2025, 6, 1), date(2030, 6, 1), 0.05)
    d = date(2026, 9, 15)
    assert abs(ref.accrued_canadian(b, d) - ref.accrued_isma(b, d)) > 1e-4
