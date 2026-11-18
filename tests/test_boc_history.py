"""The benchmark history (from the Bank's PDF) and the lookup that picks the benchmark for a date.

Inputs: tests/data/boc_benchmark_history.json and the BoC fixture, both Bank of Canada data.
"""
import json
from datetime import date, timedelta

import pytest

from cdnbond import boc
from conftest import FIXTURE, TRADE

HISTORY = FIXTURE.parent / "boc_benchmark_history.json"
ROWS = json.loads(HISTORY.read_text())["history"]


@pytest.fixture(params=sorted(ROWS))
def tenor(request):
    return request.param


def test_fixture_issues_match_history_lookup():
    """Catches a fixture that is stale against the history, or a history that changed under it."""
    issues, _ = boc.benchmark_issues(HISTORY, TRADE.isoformat())
    fixture_issues = json.loads(FIXTURE.read_text())["benchmark_issues"]
    assert {t: issues[t] for t in fixture_issues} == fixture_issues


def test_entries_are_strictly_ordered_and_sane(tenor):
    rows = ROWS[tenor]
    effective = [r["effective"] for r in rows]
    assert effective == sorted(set(effective))  # ordered, one issue per effective date
    assert all(r["maturity"] > r["effective"] for r in rows)
    assert all(0 < r["coupon"] < 0.15 for r in rows)


# The lookup returns every tenor at once, so it needs a date on which all six have an entry.
ALL_TENORS_FROM = max(rows[0]["effective"] for rows in ROWS.values())


def test_lookup_on_an_effective_date_returns_that_entry(tenor):
    rows = [r for r in ROWS[tenor] if r["effective"] >= ALL_TENORS_FROM]
    assert rows
    for row in rows:
        assert boc.benchmark_issues(HISTORY, row["effective"])[0][tenor] == row


def test_lookup_the_day_before_a_roll_returns_the_previous_entry(tenor):
    rows = ROWS[tenor]
    checked = 0
    for prev, row in zip(rows, rows[1:]):
        day = (date.fromisoformat(row["effective"]) - timedelta(days=1)).isoformat()
        if day >= ALL_TENORS_FROM:
            assert boc.benchmark_issues(HISTORY, day)[0][tenor] == prev
            checked += 1
    assert checked


def test_lookup_before_the_first_entry_raises():
    with pytest.raises(ValueError):
        boc.benchmark_issues(HISTORY, "1980-01-01")
