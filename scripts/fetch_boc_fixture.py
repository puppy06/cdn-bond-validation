"""Fetch one day of Bank of Canada benchmark yields from the Valet API and write the test fixture.

Usage: python scripts/fetch_boc_fixture.py YYYY-MM-DD

Same output as make_boc_fixture.py (tests/data/boc_benchmark_<date>.json), but it requests only
that day, so the 3.9 MB bond_yields_benchmark.json download is not needed. Needs network access.
The benchmark issues (coupon, maturity) still come from BENCHMARKS in make_boc_fixture.py.
"""
import json
import sys
import urllib.error
import urllib.request

from make_boc_fixture import SERIES, write_fixture

VALET = "https://www.bankofcanada.ca/valet/observations/{series}/json?start_date={d}&end_date={d}"


def fetch(day: str) -> dict:
    series = ",".join(f"BD.CDN.{s}.DQ.YLD" for s in SERIES)
    with urllib.request.urlopen(VALET.format(series=series, d=day), timeout=30) as resp:
        observations = json.load(resp)["observations"]
    if not observations:
        sys.exit(f"No Valet observation for {day} (weekend or market holiday?).")
    obs = observations[0]
    missing = [s for s in SERIES if "v" not in obs.get(f"BD.CDN.{s}.DQ.YLD", {})]
    if missing:
        sys.exit(f"{day}: no yield published for {', '.join(missing)}.")
    return obs


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        write_fixture(fetch(sys.argv[1]), sys.argv[1])
    except urllib.error.URLError as e:
        sys.exit(f"Valet request failed: {e}")
