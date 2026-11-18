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
| `tests/test_pricer_vs_reference.py` | QuantLib vs reference for every bond × yield: price, accrued, duration, convexity, DV01 |
| `tests/test_known_answers.py` | Par bond, zero-coupon closed form, T+1 settlement, Canadian day count |
| `tests/test_curve_and_callable.py` | Curve reprices its inputs; callable ≤ straight; callable value falls as vol rises |
| `tests/test_regression.py` | Golden-file check across 50 seeded bonds |

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
| 2026-11-17 | all QuantLib-vs-reference tests | No numerical disagreement: clean, dirty, accrued, modified duration and convexity match the reference to 1e-9 (1e-8 relative for risk) on 4 bonds x 4 yields. The `bondYield(BondPrice(...))` call also works as written. | n/a | none needed |

## Bug injection

`tests/test_bug_injection.py` swaps one `Conventions` field at a time and reruns checks
equivalent to the suite (a check that raises also counts as a catch). Run
`pytest tests/test_bug_injection.py -s` to print the table. QuantLib 1.44, 2026-11-17.

| Injected bug | Caught by | Count |
| --- | --- | --- |
| `day_count=Actual360` | clean, dirty, accrued, mod duration, convexity, dv01 vs bump, par bond, zero coupon, golden | 9/11 |
| `day_count=Actual365Fixed` | clean, dirty, accrued, mod duration, convexity, par bond, zero coupon, golden | 8/11 |
| `settlement_days=2` | T+1 test only | 1/11 |
| `calendar=TARGET` | T+1 test only | 1/11 |
| `frequency=Annual` | clean, dirty, accrued, mod duration, convexity, dv01 vs bump, zero coupon, golden | 8/11 |
| `compounding=Simple` | clean, dirty, mod duration, convexity, golden | 5/11 |
| `compounding=Continuous` | clean, dirty, mod duration, convexity, par bond, zero coupon, golden | 7/11 |
| `payment_convention=Following` | clean, dirty, mod duration, convexity, par bond, zero coupon, golden | 7/11 |

What the table shows:

* **Settlement is a weak spot.** The analytics tests pass an explicit settle date, so a wrong
  `settlement_days` or calendar is caught only by `test_t_plus_one_skips_remembrance_day`.
  Nothing checks that the settlement date feeds into pricing end to end.
* **`yield_round_trip` caught none of the eight bugs.** Price and yield use the same broken
  convention, so the round trip stays self-consistent. It tests the solver, not the conventions.
* **`compounding=Simple` slips past `par_bond` and `zero_coupon`** while the reference
  comparisons and golden file catch it. Not yet investigated why; worth a look.

## Next steps

1. **Close the settlement gap.** Add a test that prices from a trade date through
   `settlement_date`, so a wrong `settlement_days` or calendar changes a price.
2. **Real data.** Replace the illustrative quotes in `test_curve_and_callable.py`
   with Bank of Canada benchmark bond yields for a fixed date.
3. **Airflow.** A small DAG that pulls daily yields and checks for stale, missing,
   or outlier values.
4. **CORRA floating-rate note.**
