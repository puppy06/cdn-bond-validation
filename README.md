# cdn-bond-validation

A QuantLib pricer for Canadian fixed-rate government bonds, and a pytest suite that
proves its numbers are right. The pricer is small on purpose: **the tests are the project.**

## Setup

### macOS / Linux (bash or zsh)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
python scripts/make_golden.py   # once, then commit tests/golden/bonds.json
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -v
python scripts/make_golden.py   # once, then commit tests/golden/bonds.json
```

If PowerShell blocks activation, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use
`.venv\Scripts\activate.bat` from cmd. PowerShell 5.1 has no `&&`, so run the
commands on separate lines.

## Layout

| Path | What it is |
| --- | --- |
| `src/cdnbond/pricer.py` | QuantLib wrapper: bond construction, price/yield, duration, convexity, DV01, curve bootstrap, callable bond |
| `src/cdnbond/reference.py` | Independent pure-Python bond math with no QuantLib import, used as the second opinion |
| `tests/test_reference.py` | Known-answer tests on the reference itself (runs without QuantLib) |
| `tests/test_pricer_vs_reference.py` | QuantLib vs reference for every BoC benchmark bond at its real yield: price, accrued, duration, convexity, DV01 |
| `tests/test_settlement.py` | Trade date to T+1 settle to price, with hand-checked settle dates around weekends and holidays |
| `tests/test_known_answers.py` | Par bond, zero-coupon closed form, T+1 settlement, Canadian day count |
| `tests/test_curve_and_callable.py` | Curve (bootstrapped from the real Bank of Canada benchmark bonds and yields for 2026-11-10) reprices its inputs; callable ≤ straight; callable value falls as vol rises |
| `tests/data/boc_benchmark_2026-11-10.json` | One day of Bank of Canada benchmark yields (from the Valet `bond_yields_benchmark` group) plus the benchmark issues' coupon and maturity (copied from the Bank's "Current benchmark bond yields" page), written by `scripts/make_boc_fixture.py` |
| `tests/test_regression.py` | Golden-file check on the 6 BoC benchmark bonds (`scripts/make_golden.py`) |
| `src/cdnbond/boc.py` | Loads the BoC fixture as bonds and yields for the tests and the golden-file script |

**Test inputs.** Every test file takes its bonds and yields from the BoC fixture
(`tests/conftest.py` loads it). Coupon dates and settle dates a test needs are derived from those
bonds. The only values written into tests are calendar facts: the trade dates and expected T+1
settle dates in `test_settlement.py`. Zero-coupon tests reuse a benchmark's dates and yield with
the coupon set to zero.

## Conventions (and why they matter)

* Semi-annual coupons, unadjusted dates, schedule generated backward from maturity.
* Price/yield uses ActualActual (ISMA): a partial first period is discounted as
  days / days-in-period of a half-year.
* Accrued interest is ISMA in the pricer. The Canadian Actual/365 convention is
  implemented separately (`reference.accrued_canadian`) and checked against
  `ql.Actual365Fixed(ql.Actual365Fixed.Canadian)`. The two give different accrued
  amounts mid-period; see `test_canadian_and_isma_accrued_differ_mid_period`.
* Payments are unadjusted to keep cash-flow times identical to the reference.
  Real payments roll to the next business day. That is a good next convention to test.

Verify settlement cycle, accrual rule and holiday calendar against a current
market-convention source before quoting any of them in an interview.

## Findings

_Record every place QuantLib, the reference, and the market convention disagree._

| Date found | Test | What differed | Which side was right | Fix |
| --- | --- | --- | --- | --- |
| 2026-11-17 | every pricer test (first hit: `test_par_bond_prices_at_par_on_coupon_date`) | `BondFunctions.dirtyPrice(bond, yield, dc, comp, freq, settle)` raises `TypeError` in QuantLib 1.44: its overloads take a discount curve or z-spread, not a yield | QuantLib API (the reference was unaffected) | `pricer._dirty` now returns `cleanPrice(yield) + accruedAmount` |
| 2026-11-17 | all QuantLib-vs-reference tests | No numerical disagreement: clean, dirty, accrued, modified duration and convexity match the reference to 1e-9 (1e-8 relative for risk) on 4 bonds x 4 yields (the original synthetic test bonds). The `bondYield(BondPrice(...))` call also works as written. | n/a | none needed |
| 2026-11-18 | `test_dv01_matches_bump_and_reprice[LONG]`, `test_analytic_dv01_matches_bump[LONG]` | Analytic DV01 vs a +/-1bp reprice differ by 1.2e-6 relative on the 31-year LONG benchmark, over the 1e-6 tolerance. The gap is 1e-8 for the 2-year and falls 100x for every 10x smaller bump (checked on the reference at 1bp, 0.1bp, 0.01bp). | Neither: truncation error of the central difference, which grows with convexity. Analytic DV01 is correct. | `DV01_BUMP_TOL` loosened to 1e-5 in `conftest.py`, with the reason written next to it |

## Bug injection

`tests/test_bug_injection.py` swaps one `Conventions` field at a time and reruns checks
equivalent to the suite (a check that raises also counts as a catch). Run
`pytest tests/test_bug_injection.py -s` to print the table. QuantLib 1.44, 2026-11-18, on the
BoC benchmark bonds.

| Injected bug | Caught by | Count |
| --- | --- | --- |
| `day_count=Actual360` | clean, dirty, accrued, mod duration, convexity, par bond, zero coupon, trade-date price, golden | 9/12 |
| `day_count=Actual365Fixed` | clean, dirty, accrued, mod duration, convexity, par bond, zero coupon, trade-date price, golden | 9/12 |
| `settlement_days=2` | T+1 test, trade-date price | 2/12 |
| `calendar=TARGET` | T+1 test, trade-date price | 2/12 |
| `frequency=Annual` | clean, dirty, accrued, mod duration, convexity, par bond, zero coupon, trade-date price, golden | 9/12 |
| `compounding=Simple` | clean, dirty, mod duration, convexity, trade-date price, golden | 6/12 |
| `compounding=Continuous` | clean, dirty, mod duration, convexity, par bond, zero coupon, trade-date price, golden | 8/12 |
| `payment_convention=Following` | clean, dirty, mod duration, convexity, par bond, zero coupon, trade-date price, golden | 8/12 |

What the table shows:

* **Settlement was a weak spot, now closed.** The analytics tests pass an explicit settle date,
  so originally only `test_t_plus_one_skips_remembrance_day` saw a wrong `settlement_days` or
  calendar (1/11). `tests/test_settlement.py` now prices from a trade date through
  `settlement_date` against hand-checked settle dates, and a wrong `settlement_days` or
  calendar changes a price (2/12).
* **`yield_round_trip` caught none of the eight bugs.** Price and yield use the same broken
  convention, so the round trip stays self-consistent. It tests the solver, not the conventions.
* **`dv01_vs_bump` caught none of the eight bugs** once its tolerance was set to 1e-5 (it caught
  `Actual360` and `Annual` at 1e-6). Both DV01 figures come from the same broken pricer, so it
  checks internal consistency only.
* **Moving to the BoC bonds changed the table slightly:** `par_bond` now also catches
  `frequency=Annual`; nothing else changed.
* **`compounding=Simple` slips past `par_bond` and `zero_coupon`** while the reference
  comparisons and golden file catch it. Not yet investigated why; worth a look.

## Next steps

1. **Tighten the benchmark data.** The curve now uses the actual benchmark issues (coupon,
   maturity) with their real yields. Remaining gaps: the Bank publishes no issue date or ISIN, so
   issue dates are set to a regular seasoned schedule (price from yield does not depend on it);
   the coupon/maturity table is copied by hand, not fetched; and benchmarks roll, so re-check it
   for any other date. Yields for non-benchmark bonds are not available from the Bank (only
   bucket averages), so a larger curve needs a market data vendor.
2. **Airflow.** A small DAG that pulls daily yields and checks for stale, missing,
   or outlier values.
3. **CORRA floating-rate note.**
