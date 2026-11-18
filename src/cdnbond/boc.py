"""Load the Bank of Canada benchmark fixture as bonds the reference and pricer can use.

The fixture (tests/data/boc_benchmark_<date>.json, made by scripts/fetch_boc_fixture.py) holds
real benchmark yields, the benchmark issues' coupon and maturity, and the T+1 settle date. The Bank
publishes no issue date, so each is set to the latest coupon date at least a year before the trade
date: a regular, seasoned schedule. Price from yield does not depend on it.

The benchmark issues come from tests/data/boc_benchmark_history.json (made by
scripts/make_benchmark_history.py from the Bank's "Benchmark Canada Bonds" PDF).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .reference import Bond, add_months

DEFAULT_DATE = "2026-11-10"  # fixture used unless BOC_FIXTURE_DATE is set


@dataclass(frozen=True)
class Benchmark:
    tenor: str
    bond: Bond
    ytm: float  # decimal, e.g. 0.0325


def fixture_path(data_dir: str | Path, day: str | None = None) -> Path:
    """tests/data/boc_benchmark_<day>.json; day defaults to $BOC_FIXTURE_DATE, then DEFAULT_DATE."""
    day = day or os.environ.get("BOC_FIXTURE_DATE") or DEFAULT_DATE
    return Path(data_dir) / f"boc_benchmark_{day}.json"


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


def settle_date(path: str | Path) -> date:
    """The T+1 settle date stored in a fixture."""
    return date.fromisoformat(json.loads(Path(path).read_text())["settle"])


def benchmark_issues(history_path: str | Path, day: str) -> tuple[dict, str]:
    """Benchmark issue per tenor on `day`: the latest history entry effective on or before it.

    Returns ({tenor: {"maturity", "coupon", "effective"}}, date the Bank last updated the history).
    Raises ValueError if a tenor has no entry yet on `day`.
    """
    h = json.loads(Path(history_path).read_text())
    out = {}
    for tenor, rows in h["history"].items():
        current = [r for r in rows if r["effective"] <= day]
        if not current:
            raise ValueError(f"no {tenor} benchmark in the history on or before {day}")
        out[tenor] = max(current, key=lambda r: r["effective"])
    return out, h["source_modified"]
