"""Write tests/golden/bonds.json: pricer output for 50 seeded random bonds."""
import json
import random
import sys
from datetime import date
from pathlib import Path

import QuantLib as ql

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cdnbond import pricer  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "tests" / "golden" / "bonds.json"
SETTLE = date(2026, 11, 12)


def main(n: int = 50, seed: int = 20261110) -> None:
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        month = rng.choice([3, 6, 9, 12])
        issue = date(rng.randint(2015, 2025), month, 1)  # always before SETTLE
        maturity = date(rng.randint(2027, 2056), month, 1)
        coupon = round(rng.uniform(0.0, 0.06) * 400) / 400  # nearest 0.25%
        ytm = round(rng.uniform(0.005, 0.06), 6)
        a = pricer.analytics_from_yield(pricer.make_bond(issue, maturity, coupon), ytm, SETTLE)
        cases.append({
            "id": f"b{i:02d}", "issue": issue.isoformat(), "maturity": maturity.isoformat(),
            "coupon": coupon, "ytm": ytm, "settle": SETTLE.isoformat(),
            "clean": a.clean, "dirty": a.dirty, "accrued": a.accrued,
            "mod_duration": a.mod_duration, "convexity": a.convexity, "dv01": a.dv01,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"quantlib": ql.__version__, "cases": cases}, indent=1))
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
