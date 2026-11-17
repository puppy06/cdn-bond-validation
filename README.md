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
| | | | | |

## Next steps

1. **Bug injection.** Add `tests/test_bug_injection.py`: build `Conventions` with one
   thing broken (`ql.Actual360()`, `settlement_days=2`, `ql.TARGET()` calendar,
   `ql.Annual` frequency) and record which tests catch each bug. Put the
   caught/missed table in this README.
2. **Real data.** Replace the illustrative quotes in `test_curve_and_callable.py`
   with Bank of Canada benchmark bond yields for a fixed date.
3. **Airflow.** A small DAG that pulls daily yields and checks for stale, missing,
   or outlier values.
4. **CORRA floating-rate note.**
