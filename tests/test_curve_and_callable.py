"""Curve bootstrap and callable-bond no-arbitrage checks."""
from datetime import date

import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer

TRADE = date(2026, 11, 10)

# Illustrative benchmark quotes: (issue, maturity, coupon, yield).
# Replace with Bank of Canada benchmark yields for a real date.
QUOTES = [
    (date(2025, 9, 1), date(2027, 9, 1), 0.0250, 0.0245),
    (date(2025, 6, 1), date(2028, 6, 1), 0.0275, 0.0260),
    (date(2024, 9, 1), date(2029, 9, 1), 0.0300, 0.0275),
    (date(2024, 6, 1), date(2031, 6, 1), 0.0300, 0.0295),
    (date(2025, 6, 1), date(2035, 6, 1), 0.0325, 0.0315),
    (date(2023, 12, 1), date(2055, 12, 1), 0.0275, 0.0350),
]


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
    calls = [date(2030, 6, 1), date(2031, 6, 1), date(2032, 6, 1)]
    cb, straight = pricer.price_callable(
        date(2025, 6, 1), date(2035, 6, 1), 0.04, calls, curve)
    # The holder is short the call, so callable <= straight (allow tree error).
    assert cb <= straight + 0.05


def test_callable_value_falls_as_volatility_rises(curve):
    calls = [date(2030, 6, 1)]
    args = (date(2025, 6, 1), date(2035, 6, 1), 0.04, calls, curve)
    low, _ = pricer.price_callable(*args, sigma=0.005)
    high, _ = pricer.price_callable(*args, sigma=0.02)
    assert high < low
