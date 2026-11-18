"""Extract one day of Bank of Canada benchmark yields into a small test fixture.

Usage: python scripts/make_boc_fixture.py [path/to/bond_yields_benchmark.json] [YYYY-MM-DD]

Source file: https://www.bankofcanada.ca/valet/observations/group/bond_yields_benchmark/json
Output:      tests/data/boc_benchmark_<date>.json (yields in percent, as published)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES = ["2YR", "3YR", "5YR", "7YR", "10YR", "LONG"]  # RRB (real return bond) is not nominal

# Benchmark issue behind each tenor, copied by hand from "Current benchmark bond yields" at
# https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/ (fetched 2026-11-18).
# `effective` is when the issue became the benchmark, not its issue date. The page gives no issue
# date or ISIN. Re-check this table against the page for any other trade date: benchmarks roll.
BENCHMARKS = {
    "2YR": {"maturity": "2028-11-01", "coupon": 0.0300, "effective": "2026-10-23"},
    "3YR": {"maturity": "2029-09-01", "coupon": 0.0350, "effective": "2026-10-23"},
    "5YR": {"maturity": "2031-09-01", "coupon": 0.0300, "effective": "2026-09-10"},
    "7YR": {"maturity": "2033-06-01", "coupon": 0.0275, "effective": "2026-09-10"},
    "10YR": {"maturity": "2036-06-01", "coupon": 0.0325, "effective": "2026-06-23"},
    "LONG": {"maturity": "2057-12-01", "coupon": 0.0350, "effective": "2026-03-06"},
}


def main(src: Path, day: str) -> None:
    data = json.loads(src.read_text(encoding="utf-8"))
    obs = next(o for o in data["observations"] if o["d"] == day)
    out = {
        "source": "https://www.bankofcanada.ca/valet/observations/group/bond_yields_benchmark/json",
        "date": day,
        "unit": "percent",
        "benchmark_issues": BENCHMARKS,
        "yields": {s: float(obs[f"BD.CDN.{s}.DQ.YLD"]["v"]) for s in SERIES},
    }
    dest = ROOT / "tests" / "data" / f"boc_benchmark_{day}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "bond_yields_benchmark.json"),
         sys.argv[2] if len(sys.argv) > 2 else "2026-11-10")
