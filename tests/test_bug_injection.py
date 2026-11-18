"""Bug injection: does the suite notice when one convention is wrong?

Each bug swaps exactly one `Conventions` field. The pricer is then run through
the same checks the real suite makes (QuantLib vs reference, known answers,
golden file). A check "catches" a bug if it fails or raises.

`pricer.Conventions` is monkeypatched, so every pricer function that defaults
to `Conventions()` picks up the broken convention. Run with `-s` to print the
caught/missed table for the README.
"""
import json
from datetime import date
from pathlib import Path

import pytest

ql = pytest.importorskip("QuantLib")

from cdnbond import pricer, reference as ref
from conftest import (BENCHES, DV01_BUMP_TOL, PRICE_TOL, RISK_TOL, SETTLE, TRADE,
                      half_years, next_coupon)

GOLDEN = Path(__file__).parent / "golden" / "bonds.json"
GOLDEN_FIELDS = ("clean", "dirty", "accrued", "mod_duration", "convexity", "dv01")

# name -> {Conventions field: broken value}. One field per bug.
BUGS = {
    "day_count=Actual360": {"day_count": ql.Actual360()},
    "day_count=Actual365Fixed": {"day_count": ql.Actual365Fixed()},
    "settlement_days=2": {"settlement_days": 2},
    "calendar=TARGET": {"calendar": ql.TARGET()},
    "frequency=Annual": {"frequency": ql.Annual},
    "compounding=Simple": {"compounding": ql.Simple},
    "compounding=Continuous": {"compounding": ql.Continuous},
    "payment_convention=Following": {"payment_convention": ql.Following},
}


# ---------------------------------------------------------------- detectors
# Each returns True when it detects a mismatch (i.e. the bug was caught).
def _grid(check):
    """True if `check(bond, ytm, analytics)` is False for any BoC benchmark bond."""
    for bench in BENCHES:
        b, y = bench.bond, bench.ytm
        qb = pricer.make_bond(b.issue, b.maturity, b.coupon)
        a = pricer.analytics_from_yield(qb, y, SETTLE)
        if not check(b, y, a):
            return True
    return False


def _close(x, y, **kw):
    return x == pytest.approx(y, **kw)


# Clean price (QuantLib vs reference) over every bond x yield. Targets anything that changes
# how yield maps to price: day count, frequency, compounding, payment dates. Blind to
# settlement_days and calendar because the grid passes an explicit settle date.
def d_clean(): return _grid(lambda b, y, a: _close(a.clean, ref.clean_price(b, y, SETTLE), abs=PRICE_TOL))
# Dirty price (QuantLib vs reference). Same bugs as clean price: day count, frequency,
# compounding, payment convention. Also blind to settlement_days and calendar.
def d_dirty(): return _grid(lambda b, y, a: _close(a.dirty, ref.dirty_price(b, y, SETTLE), abs=PRICE_TOL))
# Accrued interest (QuantLib vs ISMA reference). Depends only on the schedule and day
# count, not the yield, so it catches day_count and frequency bugs but not compounding
# or payment_convention. Blind to settlement_days and calendar for the same reason as above.
def d_accrued(): return _grid(lambda b, y, a: _close(a.accrued, ref.accrued_isma(b, SETTLE), abs=PRICE_TOL))
# Modified duration (QuantLib vs reference). Sensitive to anything that changes cash-flow
# timing or discounting: day count, frequency, compounding, payment convention.
def d_mod_duration(): return _grid(lambda b, y, a: _close(a.mod_duration, ref.modified_duration(b, y, SETTLE), rel=RISK_TOL))
# Convexity (QuantLib vs reference). Same bugs as modified duration; second-order
# sensitivity, so it also notices small discounting differences.
def d_convexity(): return _grid(lambda b, y, a: _close(a.convexity, ref.convexity(b, y, SETTLE), rel=RISK_TOL))
# Internal consistency: DV01 from modified duration vs a +/-1bp reprice, both from QuantLib
# with no reference. Only catches a bug if it breaks that consistency. In the last run (1e-5
# tolerance) it caught none of the eight bugs, so it is a weak detector of convention errors.
def d_dv01_vs_bump(): return _grid(lambda b, y, a: _close(a.dv01, a.dv01_bump, rel=DV01_BUMP_TOL))


# price -> yield -> price round trip. Price and yield share the same broken convention, so
# the round trip stays self-consistent. Catches none of these bugs; it tests the solver,
# not the conventions. Kept as a control on the yield solver.
def d_yield_round_trip():
    for bench in BENCHES:
        b, y = bench.bond, bench.ytm
        qb = pricer.make_bond(b.issue, b.maturity, b.coupon)
        a = pricer.analytics_from_yield(qb, y, SETTLE)
        if not _close(pricer.yield_from_clean(qb, a.clean, SETTLE), y, abs=1e-8):
            return True
    return False


# Known answer: a bond priced at its own coupon on a coupon date is exactly 100 with zero
# accrued. Catches bugs that distort the discounting of a regular period (day count,
# continuous compounding, payment convention). No reference needed.
def d_par_bond():
    for bench in BENCHES:
        b = bench.bond
        qb = pricer.make_bond(b.issue, b.maturity, b.coupon)
        a = pricer.analytics_from_yield(qb, b.coupon, next_coupon(b, SETTLE))
        if not (_close(a.clean, 100.0, abs=1e-10) and _close(a.accrued, 0.0, abs=1e-12)):
            return True
    return False


# Known answer: a zero-coupon bond with a benchmark's dates and yield, settled on a coupon
# date, is worth 100 / (1 + y/2)**n. Closed form, no reference.
def d_zero_coupon():
    for bench in BENCHES:
        b = bench.bond
        qb = pricer.make_bond(b.issue, b.maturity, 0.0)
        settle = next_coupon(b, SETTLE)
        a = pricer.analytics_from_yield(qb, bench.ytm, settle)
        if not _close(a.dirty, 100 / (1 + bench.ytm / 2) ** half_years(settle, b.maturity), abs=1e-10):
            return True
    return False


# Settlement date for a trade on Tue 2026-11-10 must be Thu 2026-11-12 (Nov 11, Remembrance
# Day, is a Canadian holiday). The only check that sees settlement_days and calendar bugs:
# T+2 lands on Nov 13, and TARGET lands on Nov 11.
def d_t_plus_one():
    return pricer.settlement_date(TRADE) != ql.Date(12, 11, 2026)


# Price from a trade date (trade -> T+1 settle -> price) vs the reference at a hand-checked
# settle date, over the cases in test_settlement.py. Unlike the checks above it goes through
# settlement_date, so it is the one that sees settlement_days and calendar bugs in a price.
def d_trade_date_price():
    from test_settlement import CASES
    for bench in BENCHES:
        b = bench.bond
        for trade, expected, _ in CASES:
            qb = pricer.make_bond(b.issue, b.maturity, b.coupon)
            a = pricer.analytics_from_trade(qb, bench.ytm, trade)
            if not _close(a.clean, ref.clean_price(b, bench.ytm, expected), abs=PRICE_TOL):
                return True
    return False


# Golden file: pricer output for the 6 BoC benchmark bonds must match tests/golden/bonds.json to 1e-10.
# A broad net for any convention change that moves a price, duration, convexity or DV01.
# Blind to settlement bugs because every golden case uses a fixed settle date.
def d_golden():
    for c in json.loads(GOLDEN.read_text())["cases"]:
        qb = pricer.make_bond(date.fromisoformat(c["issue"]),
                              date.fromisoformat(c["maturity"]), c["coupon"])
        a = pricer.analytics_from_yield(qb, c["ytm"], date.fromisoformat(c["settle"]))
        if any(not _close(getattr(a, f), c[f], abs=1e-10) for f in GOLDEN_FIELDS):
            return True
    return False


DETECTORS = {
    "clean_price": d_clean,
    "dirty_price": d_dirty,
    "accrued": d_accrued,
    "modified_duration": d_mod_duration,
    "convexity": d_convexity,
    "dv01_vs_bump": d_dv01_vs_bump,
    "yield_round_trip": d_yield_round_trip,
    "par_bond": d_par_bond,
    "zero_coupon": d_zero_coupon,
    "t_plus_one": d_t_plus_one,
    "trade_date_price": d_trade_date_price,
    "golden_file": d_golden,
}


def _run(detector) -> bool:
    try:
        return bool(detector())
    except Exception:  # a crash also stops the bug going unnoticed
        return True


REAL_CONVENTIONS = pricer.Conventions


def caught_by(bug_name: str, monkeypatch) -> list[str]:
    fields = BUGS[bug_name]
    monkeypatch.setattr(pricer, "Conventions", lambda: REAL_CONVENTIONS(**fields))
    return [name for name, det in DETECTORS.items() if _run(det)]


# --------------------------------------------------------------------- tests
def test_unbroken_conventions_are_caught_by_nothing():
    """Control: with no bug injected, no detector fires (else the table is meaningless)."""
    assert [n for n, d in DETECTORS.items() if _run(d)] == []


@pytest.mark.skipif(not GOLDEN.exists(), reason="run scripts/make_golden.py first")
@pytest.mark.parametrize("bug", BUGS)
def test_bug_is_caught(bug, monkeypatch, capsys):
    hits = caught_by(bug, monkeypatch)
    with capsys.disabled():
        print(f"\n{bug:32s} caught by {len(hits):2d}/{len(DETECTORS)}: {', '.join(hits) or 'NONE'}")
    assert hits, f"suite does not detect {bug}"
