"""Shared fixtures. Bonds are illustrative GoC-style issues, not real CUSIPs."""
from datetime import date

import pytest

from cdnbond.reference import Bond

SETTLE = date(2026, 11, 12)

BONDS = [
    Bond(date(2024, 9, 1), date(2027, 9, 1), 0.0275),
    Bond(date(2023, 6, 1), date(2029, 6, 1), 0.0300),
    Bond(date(2022, 12, 1), date(2032, 12, 1), 0.0325),
    Bond(date(2016, 12, 1), date(2051, 12, 1), 0.0200),
]
YIELDS = [0.005, 0.025, 0.0325, 0.06]

# Tolerances: tight on purpose. Loosen only with a written reason.
PRICE_TOL = 1e-9
RISK_TOL = 1e-8


@pytest.fixture(params=BONDS, ids=lambda b: f"{b.coupon:.2%}-{b.maturity}")
def bond(request):
    return request.param


@pytest.fixture(params=YIELDS, ids=lambda y: f"y={y:.2%}")
def ytm(request):
    return request.param
