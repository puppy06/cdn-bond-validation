"""Write tests/golden/bonds.json: pricer output for the BoC benchmark bonds at their real yields.

Inputs come from tests/data/boc_benchmark_<date>.json (see scripts/make_boc_fixture.py).
Regenerate only when a change is intended and reviewed.
"""
import json
import sys
from datetime import date
from pathlib import Path

import QuantLib as ql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cdnbond import boc, pricer  # noqa: E402

FIXTURE = ROOT / "tests" / "data" / "boc_benchmark_2026-11-10.json"
OUT = ROOT / "tests" / "golden" / "bonds.json"
SETTLE = date(2026, 11, 12)  # T+1 from the fixture's trade date (2026-11-10)


def main() -> None:
    _, benches = boc.load(FIXTURE)
    cases = []
    for b in benches:
        bd = b.bond
        a = pricer.analytics_from_yield(pricer.make_bond(bd.issue, bd.maturity, bd.coupon),
                                        b.ytm, SETTLE)
        cases.append({
            "id": b.tenor, "issue": bd.issue.isoformat(), "maturity": bd.maturity.isoformat(),
            "coupon": bd.coupon, "ytm": b.ytm, "settle": SETTLE.isoformat(),
            "clean": a.clean, "dirty": a.dirty, "accrued": a.accrued,
            "mod_duration": a.mod_duration, "convexity": a.convexity, "dv01": a.dv01,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"quantlib": ql.__version__, "cases": cases}, indent=1))
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
