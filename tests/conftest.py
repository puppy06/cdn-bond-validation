"""Shared fixtures. Every test input comes from the Bank of Canada benchmark fixture
(tests/data/boc_benchmark_<date>.json): the six benchmark bonds, each at its real yield.
Dates a test needs beyond that (coupon dates, settle dates) are derived from those bonds.
"""
from datetime import date
from pathlib import Path

import pytest

from cdnbond import boc, reference as ref

# One fixture drives every test: tests/data/boc_benchmark_<date>.json, with <date> taken from the
# BOC_FIXTURE_DATE environment variable (default boc.DEFAULT_DATE). Make one with
# scripts/fetch_boc_fixture.py <date>, then rerun scripts/make_golden.py with the same variable.
FIXTURE = boc.fixture_path(Path(__file__).parent / "data")
TRADE, BENCHES = boc.load(FIXTURE)
# T+1 from TRADE, stored in the fixture (written from QuantLib's Canada calendar). The hand-checked
# settle dates in test_settlement.py are the independent check on that calendar.
SETTLE = boc.settle_date(FIXTURE)

# Tolerances: tight on purpose. Loosen only with a written reason.
PRICE_TOL = 1e-9
RISK_TOL = 1e-8
# Analytic DV01 vs a +/-1bp reprice. The bump's truncation error is O(bp^2) and scales with
# convexity: measured 1e-8 (2-year) up to 1.2e-6 (31-year LONG), falling 100x per 10x smaller bump.
DV01_BUMP_TOL = 1e-5


def next_coupon(bond: ref.Bond, after: date) -> date:
    return min(d for d in ref.coupon_dates(bond) if d > after)


def half_years(start: date, end: date) -> int:
    """Whole six-month periods between two dates on the same day of month."""
    return ((end.year - start.year) * 12 + end.month - start.month) // 6


@pytest.fixture(params=BENCHES, ids=lambda b: b.tenor)
def bench(request):
    return request.param


@pytest.fixture
def bond(bench):
    return bench.bond


@pytest.fixture
def ytm(bench):
    return bench.ytm
