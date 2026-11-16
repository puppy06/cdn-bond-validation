"""Golden-file regression: flags any change in pricer output.

Generate the golden file once with `python scripts/make_golden.py`, commit it,
and regenerate only when a change is intended and reviewed.
"""
import json
from datetime import date
from pathlib import Path

import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer

GOLDEN = Path(__file__).parent / "golden" / "bonds.json"
TOL = 1e-10
FIELDS = ("clean", "dirty", "accrued", "mod_duration", "convexity", "dv01")


def _cases():
    if not GOLDEN.exists():
        return []
    return json.loads(GOLDEN.read_text())["cases"]


@pytest.mark.skipif(not GOLDEN.exists(), reason="run scripts/make_golden.py first")
@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_matches_golden(case):
    qb = pricer.make_bond(date.fromisoformat(case["issue"]),
                          date.fromisoformat(case["maturity"]), case["coupon"])
    a = pricer.analytics_from_yield(qb, case["ytm"], date.fromisoformat(case["settle"]))
    for f in FIELDS:
        assert getattr(a, f) == pytest.approx(case[f], abs=TOL), f
