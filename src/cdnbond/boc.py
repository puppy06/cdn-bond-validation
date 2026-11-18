"""Load the Bank of Canada benchmark fixture as bonds the reference and pricer can use.

The fixture (tests/data/boc_benchmark_<date>.json, made by scripts/make_boc_fixture.py) holds
real benchmark yields and the benchmark issues' coupon and maturity. The Bank publishes no issue
date, so each is set to the latest coupon date at least a year before the trade date: a regular,
seasoned schedule. Price from yield does not depend on it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .reference import Bond, add_months


@dataclass(frozen=True)
class Benchmark:
    tenor: str
    bond: Bond
    ytm: float  # decimal, e.g. 0.0325


def load(path: str | Path) -> tuple[date, list[Benchmark]]:
    """Return (trade date, benchmarks) from a fixture file."""
    fx = json.loads(Path(path).read_text())
    trade = date.fromisoformat(fx["date"])
    cutoff = date(trade.year - 1, trade.month, trade.day)
    out = []
    for tenor, bm in fx["benchmark_issues"].items():
        maturity = date.fromisoformat(bm["maturity"])
        issue = maturity
        while issue > cutoff:
            issue = add_months(issue, -6)
        out.append(Benchmark(tenor, Bond(issue, maturity, bm["coupon"]), fx["yields"][tenor] / 100))
    return trade, out
