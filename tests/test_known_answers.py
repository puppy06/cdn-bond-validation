"""Known answers and conventions checked directly against QuantLib. Inputs: BoC benchmark bonds."""
from datetime import date, timedelta

import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer, reference as ref
from conftest import SETTLE, TRADE, half_years, next_coupon


def test_par_bond_prices_at_par_on_coupon_date(bond):
    qb = pricer.make_bond(bond.issue, bond.maturity, bond.coupon)
    a = pricer.analytics_from_yield(qb, bond.coupon, next_coupon(bond, SETTLE))
    assert a.clean == pytest.approx(100.0, abs=1e-10)
    assert a.accrued == pytest.approx(0.0, abs=1e-12)


def test_zero_coupon_closed_form(bond, ytm):
    qb = pricer.make_bond(bond.issue, bond.maturity, 0.0)  # same dates and yield, coupon zero
    settle = next_coupon(bond, SETTLE)
    a = pricer.analytics_from_yield(qb, ytm, settle)
    assert a.dirty == pytest.approx(100 / (1 + ytm / 2) ** half_years(settle, bond.maturity),
                                    abs=1e-10)


def test_t_plus_one_matches_fixture_settle():
    assert pricer.settlement_date(TRADE) == pricer.to_ql(SETTLE)


def test_t_plus_one_skips_remembrance_day():
    # A calendar fact, independent of the fixture date: Tue 2026-11-10 trades settle Thu Nov 12
    # because Nov 11 is a holiday on QuantLib's Canada settlement calendar.
    assert pricer.settlement_date(date(2026, 11, 10)) == ql.Date(12, 11, 2026)


def _settle(bond, which):
    prev, nxt, _ = ref._period(bond, SETTLE)
    return {"early": prev + timedelta(days=30),
            "mid": prev + (nxt - prev) // 2,
            "late": nxt - timedelta(days=1)}[which]


@pytest.mark.parametrize("which", ["early", "mid", "late"])
def test_quantlib_canadian_daycount_matches_hand_formula(bond, which):
    """QuantLib's Actual365Fixed(Canadian) vs the hand-written Canadian accrual.

    'late' is one day before the next coupon, which reaches the 182-day branch on 6-month
    periods of 183/184 days. If this fails, decide which side is wrong and write it up in the README.
    """
    settle = _settle(bond, which)
    prev, nxt, _ = ref._period(bond, settle)
    dc = ql.Actual365Fixed(ql.Actual365Fixed.Canadian)
    p, s, n = pricer.to_ql(prev), pricer.to_ql(settle), pricer.to_ql(nxt)
    ql_accrued = 100 * bond.coupon * dc.yearFraction(p, s, p, n)
    assert ql_accrued == pytest.approx(ref.accrued_canadian(bond, settle), abs=1e-10)


def test_canadian_and_isma_accrued_differ_mid_period(bond):
    """Documents that the convention matters: same bond, same day, different accrued."""
    d = _settle(bond, "mid")
    assert abs(ref.accrued_canadian(bond, d) - ref.accrued_isma(bond, d)) > 1e-4
