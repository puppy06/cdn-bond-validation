"""Curve bootstrap and callable-bond no-arbitrage checks. Inputs: the BoC benchmark bonds."""
from datetime import date

import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer, reference as ref
from conftest import BENCHES, TRADE

# (issue, maturity, coupon, yield) for the curve bootstrap
QUOTES = [(b.bond.issue, b.bond.maturity, b.bond.coupon, b.ytm) for b in BENCHES]

# The callable bond is the 10-year benchmark, callable at par on dates counted back from maturity.
TEN_YEAR = next(b.bond for b in BENCHES if b.tenor == "10YR")


def _call_dates(years_before_maturity):
    return [ref.add_months(TEN_YEAR.maturity, -12 * k) for k in years_before_maturity]


@pytest.fixture(scope="module")
def curve():
    return pricer.build_curve(TRADE, QUOTES)


@pytest.mark.parametrize("q", QUOTES, ids=lambda q: str(q[1]))
def test_curve_reprices_its_inputs(curve, q):
    issue, maturity, cpn, y = q
    bond = pricer.make_bond(issue, maturity, cpn)
    bond.setPricingEngine(ql.DiscountingBondEngine(curve))
    s = pricer.settlement_date(TRADE)
    c = pricer.Conventions()
    expected = ql.BondFunctions.cleanPrice(bond, y, c.day_count, c.compounding, c.frequency, s)
    assert bond.cleanPrice() == pytest.approx(expected, abs=1e-6)


def test_discount_factors_are_positive_and_decreasing(curve):
    dfs = [curve.discount(t) for t in (0.5, 1, 2, 5, 10, 20, 29)]
    assert all(d > 0 for d in dfs)
    assert dfs == sorted(dfs, reverse=True)


def test_callable_not_worth_more_than_straight(curve):
    cb, straight = pricer.price_callable(
        TEN_YEAR.issue, TEN_YEAR.maturity, TEN_YEAR.coupon, _call_dates((5, 4, 3)), curve)
    # The holder is short the call, so callable <= straight (allow tree error).
    assert cb <= straight + 0.05


def test_callable_value_falls_as_volatility_rises(curve):
    args = (TEN_YEAR.issue, TEN_YEAR.maturity, TEN_YEAR.coupon, _call_dates((5,)), curve)
    low, _ = pricer.price_callable(*args, sigma=0.005)
    high, _ = pricer.price_callable(*args, sigma=0.02)
    assert high < low
