"""Trade date -> settlement date -> price, end to end. Bonds: BoC benchmark bonds.

The other price tests pass an explicit settle date, so a wrong `settlement_days`
or calendar could not change a price there. Here the expected settlement date is
hard-coded by hand and the price is compared with the reference at that date.
The trade dates are calendar facts, not market data, so they are written out here.

A bond is priced only on settle dates when it exists and has not matured, so a fixture
from an earlier date (whose short bonds mature before the 2026 cases) still works.
`test_every_case_prices_at_least_one_bond` fails if a case would be left with no bond.
"""
from datetime import date, timedelta

import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer, reference as ref
from conftest import BENCHES, PRICE_TOL, SETTLE, TRADE

# (trade date, expected T+1 settlement, why it is interesting)
CASES = [
    (TRADE, SETTLE, "fixture trade date (settle stored in the fixture)"),
    (date(2026, 11, 10), date(2026, 11, 12), "Tue: Nov 11 Remembrance Day is skipped"),
    (date(2026, 11, 12), date(2026, 11, 13), "Thu -> Fri, plain T+1"),
    (date(2026, 11, 13), date(2026, 11, 16), "Fri -> Mon, weekend skipped"),
    (date(2026, 6, 30), date(2026, 7, 2), "Tue: Jul 1 Canada Day is skipped"),
]

# (benchmark, case) pairs where the bond is tradable on the settle date.
PAIRS = [(b, c) for b in BENCHES for c in CASES if b.bond.issue <= c[1] < b.bond.maturity]


@pytest.fixture(params=CASES, ids=lambda c: c[2])
def case(request):
    return request.param


def test_settlement_date_is_hand_checked(case):
    trade, expected, _ = case
    s = pricer.settlement_date(trade)
    assert date(s.year(), s.month(), s.dayOfMonth()) == expected


def test_every_case_prices_at_least_one_bond(case):
    assert any(c == case for _, c in PAIRS), "no benchmark bond is tradable on this settle date"


@pytest.mark.parametrize("pair", PAIRS, ids=lambda p: f"{p[0].tenor}-{p[1][2]}")
def test_price_from_trade_date_uses_t_plus_one_settle(pair):
    bench, (trade, expected, _) = pair
    b = bench.bond
    qb = pricer.make_bond(b.issue, b.maturity, b.coupon)
    a = pricer.analytics_from_trade(qb, bench.ytm, trade)
    assert a.clean == pytest.approx(ref.clean_price(b, bench.ytm, expected), abs=PRICE_TOL)
    assert a.accrued == pytest.approx(ref.accrued_isma(b, expected), abs=PRICE_TOL)


def test_settle_date_moves_the_price(bond):
    """Guard: if two settle dates gave the same price, the tests above could not see a bug."""
    d1 = ref.accrued_isma(bond, SETTLE)
    d2 = ref.accrued_isma(bond, SETTLE + timedelta(days=1))
    assert abs(d1 - d2) > 1e-3
