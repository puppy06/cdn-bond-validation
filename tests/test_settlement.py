"""Trade date -> settlement date -> price, end to end. Bonds: BoC benchmark bonds.

The other price tests pass an explicit settle date, so a wrong `settlement_days`
or calendar could not change a price there. Here the expected settlement date is
hard-coded by hand and the price is compared with the reference at that date.
The trade dates are calendar facts, not market data, so they are written out here.
"""
from datetime import date

import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer, reference as ref
from conftest import PRICE_TOL, SETTLE, TRADE

# (trade date, expected T+1 settlement, why it is interesting)
CASES = [
    (TRADE, SETTLE, "Tue: Nov 11 Remembrance Day is skipped"),
    (date(2026, 11, 12), date(2026, 11, 13), "Thu -> Fri, plain T+1"),
    (date(2026, 11, 13), date(2026, 11, 16), "Fri -> Mon, weekend skipped"),
    (date(2026, 6, 30), date(2026, 7, 2), "Tue: Jul 1 Canada Day is skipped"),
]


@pytest.fixture(params=CASES, ids=lambda c: c[2])
def case(request):
    return request.param


def test_settlement_date_is_hand_checked(case):
    trade, expected, _ = case
    s = pricer.settlement_date(trade)
    assert date(s.year(), s.month(), s.dayOfMonth()) == expected


def test_price_from_trade_date_uses_t_plus_one_settle(bench, case):
    trade, expected, _ = case
    b = bench.bond
    qb = pricer.make_bond(b.issue, b.maturity, b.coupon)
    a = pricer.analytics_from_trade(qb, bench.ytm, trade)
    assert a.clean == pytest.approx(ref.clean_price(b, bench.ytm, expected), abs=PRICE_TOL)
    assert a.accrued == pytest.approx(ref.accrued_isma(b, expected), abs=PRICE_TOL)


def test_settle_date_moves_the_price(bond):
    """Guard: if two settle dates gave the same price, the tests above could not see a bug."""
    d1 = ref.accrued_isma(bond, date(2026, 11, 12))
    d2 = ref.accrued_isma(bond, date(2026, 11, 13))
    assert abs(d1 - d2) > 1e-3
