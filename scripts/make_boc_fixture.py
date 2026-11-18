"""Extract one day of Bank of Canada benchmark yields into a small test fixture.

Usage: python scripts/make_boc_fixture.py [path/to/bond_yields_benchmark.json] [YYYY-MM-DD]

Source file: https://www.bankofcanada.ca/valet/observations/group/bond_yields_benchmark/json
(scripts/fetch_boc_fixture.py does the same straight from the API, without the big download).
Output:      tests/data/boc_benchmark_<date>.json
  yields           percent, as published
  benchmark_issues the benchmark bond (coupon, maturity) per tenor on that date, looked up in
                   tests/data/boc_benchmark_history.json (run scripts/make_benchmark_history.py)
  settle           T+1 settle date from QuantLib's Canada calendar, with the default conventions
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cdnbond import boc, pricer  # noqa: E402

SERIES = ["2YR", "3YR", "5YR", "7YR", "10YR", "LONG"]  # RRB (real return bond) is not nominal
HISTORY = ROOT / "tests" / "data" / "boc_benchmark_history.json"


def write_fixture(obs: dict, day: str) -> Path:
    """Write the fixture for one Valet observation (a dict with 'BD.CDN.<tenor>.DQ.YLD' keys)."""
    issues, history_modified = boc.benchmark_issues(HISTORY, day)
    if day > history_modified:
        print(f"WARNING: the Bank last updated its benchmark history on {history_modified}; a "
              f"benchmark that rolled between then and {day} would not appear. Refresh it with "
              "scripts/make_benchmark_history.py and check the Bank's benchmark page.")
    s = pricer.settlement_date(pricer.date.fromisoformat(day))
    out = {
        "source": "https://www.bankofcanada.ca/valet/observations/group/bond_yields_benchmark/json",
        "date": day,
        "settle": f"{s.year():04d}-{s.month():02d}-{s.dayOfMonth():02d}",
        "unit": "percent",
        "benchmark_history_as_of": history_modified,
        "benchmark_issues": {t: issues[t] for t in SERIES},
        "yields": {t: float(obs[f"BD.CDN.{t}.DQ.YLD"]["v"]) for t in SERIES},
    }
    dest = ROOT / "tests" / "data" / f"boc_benchmark_{day}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {dest}")
    return dest


def main(src: Path, day: str) -> None:
    data = json.loads(src.read_text(encoding="utf-8"))
    write_fixture(next(o for o in data["observations"] if o["d"] == day), day)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "bond_yields_benchmark.json"),
         sys.argv[2] if len(sys.argv) > 2 else "2026-11-10")
