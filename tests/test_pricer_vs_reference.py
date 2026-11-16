"""QuantLib vs the independent reference: every analytic, every bond, every yield."""
import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer, reference as ref
from conftest import PRICE_TOL, RISK_TOL, SETTLE


@pytest.fixture
def analytics(bond, ytm):
    qb = pricer.make_bond(bond.issue, bond.maturity, bond.coupon)
    return pricer.analytics_from_yield(qb, ytm, SETTLE)


def test_clean_price(bond, ytm, analytics):
    assert analytics.clean == pytest.approx(ref.clean_price(bond, ytm, SETTLE), abs=PRICE_TOL)


def test_dirty_price(bond, ytm, analytics):
    assert analytics.dirty == pytest.approx(ref.dirty_price(bond, ytm, SETTLE), abs=PRICE_TOL)


def test_accrued(bond, analytics):
    assert analytics.accrued == pytest.approx(ref.accrued_isma(bond, SETTLE), abs=PRICE_TOL)


def test_modified_duration(bond, ytm, analytics):
    assert analytics.mod_duration == pytest.approx(
        ref.modified_duration(bond, ytm, SETTLE), rel=RISK_TOL)


def test_convexity(bond, ytm, analytics):
    assert analytics.convexity == pytest.approx(ref.convexity(bond, ytm, SETTLE), rel=RISK_TOL)


def test_analytic_dv01_matches_bump(analytics):
    # The gap is convexity error, O(bp^2): small but not zero.
    assert analytics.dv01 == pytest.approx(analytics.dv01_bump, rel=1e-6)


def test_yield_round_trip(bond, ytm, analytics):
    qb = pricer.make_bond(bond.issue, bond.maturity, bond.coupon)
    assert pricer.yield_from_clean(qb, analytics.clean, SETTLE) == pytest.approx(ytm, abs=1e-8)
