"""Parse the Bank of Canada's "Benchmark Canada Bonds" PDF into tests/data/boc_benchmark_history.json.

Usage: python scripts/make_benchmark_history.py [path/to/bench_CDN.pdf]

Without an argument the PDF is downloaded from
https://www.bankofcanada.ca/stats/assets/pdf/bench_CDN.pdf. Needs pypdf (pip install ".[data]").
The PDF lists, per tenor, each benchmark issue (coupon, maturity month and year) with the date it
became the benchmark. The output is one entry per (tenor, issue, effective date). The PDF gives no
maturity day for most rows, so it is taken as the 1st, which holds for the six 2026 benchmarks (checked against
the Bank's benchmark page). The real-return bond (RRB) is skipped.
"""
import json
import re
import sys
import tempfile
import urllib.request
from datetime import date, datetime
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit('pypdf is required: pip install ".[data]"')

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.bankofcanada.ca/stats/assets/pdf/bench_CDN.pdf"
OUT = ROOT / "tests" / "data" / "boc_benchmark_history.json"

MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
ABBR = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
# "7 1/2% / March 1994", "2.25 % February 2028", "4% / 15 March 1999", "2 % Sept 2012",
# "1.25 %February2018" (the PDF is inconsistent about spaces)
ISSUE = re.compile(rf"(\d+\.\d+|\d+(?:\s+\d/\d)?)\s*%\s*/?\s*(?:(\d{{1,2}})\s+)?({MON})\s*(\d{{4}})")
# "(23 October 2026)", "(21 Aug 2008)", "(11 September1997)", "(April 30th 2010)"
EFFECTIVE = re.compile(
    rf"\(\s*(?:(?P<d1>\d{{1,2}})\s+(?P<m1>{MON})\s*(?P<y1>\d{{4}})"
    rf"|(?P<m2>{MON})\s+(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<y2>\d{{4}}))\s*\)")


def month(abbr: str) -> int:
    return ABBR.index(abbr[:3].lower()) + 1


TENOR = re.compile(r"^\s*(?:(\d+)\s*-\s*YEAR|(LONG)|(RRB))\b")


def coupon(text: str) -> float:
    parts = text.split()
    if len(parts) == 2:  # "7 1/2"
        num, den = parts[1].split("/")
        return int(parts[0]) + int(num) / int(den)
    return float(parts[0])


def parse(pdf: Path) -> tuple[dict, str]:
    reader = PdfReader(str(pdf))
    modified = reader.metadata.modification_date or reader.metadata.creation_date
    history: dict[str, set] = {}
    problems = []
    for pno, page in enumerate(reader.pages, 1):
        lines = [ln for ln in page.extract_text(extraction_mode="layout").splitlines() if ln.strip()]
        for i, ln in enumerate(lines):
            m = TENOR.match(ln)
            if not m or m.group(3):  # not a tenor row, or RRB
                continue
            tenor = f"{m.group(1)}YR" if m.group(1) else "LONG"
            issues = ISSUE.findall(ln)
            dates = []
            for em in (EFFECTIVE.finditer(lines[i + 1]) if i + 1 < len(lines) else []):
                g = em.groupdict()
                dates.append((g["d1"] or g["d2"], g["m1"] or g["m2"], g["y1"] or g["y2"]))
            if len(issues) != len(dates):
                problems.append(f"page {pno} {tenor}: {len(issues)} issues vs {len(dates)} dates")
                continue
            for (c, mday, mon, yr), (d, dmon, dyr) in zip(issues, dates):
                eff = date(int(dyr), month(dmon), int(d))
                mat = date(int(yr), month(mon), int(mday) if mday else 1)
                history.setdefault(tenor, set()).add((eff, mat, round(coupon(c) / 100, 6)))
    if problems:
        sys.exit("Could not align issues with dates:\n  " + "\n  ".join(problems))
    out = {t: [{"effective": e.isoformat(), "maturity": mt.isoformat(), "coupon": c}
               for e, mt, c in sorted(rows)] for t, rows in sorted(history.items())}
    return out, modified.date().isoformat()


def main(pdf: Path) -> None:
    history, modified = parse(pdf)
    out = {
        "source": URL,
        "source_modified": modified,
        "note": "Maturity day is taken as the 1st when the PDF gives only month and year. An entry holds from its "
                "effective date until the next entry for the same tenor. Rolls after "
                "source_modified are not captured.",
        "history": history,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {OUT}: " + ", ".join(f"{t} {len(r)}" for t, r in history.items())
          + f"; PDF modified {modified}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(Path(sys.argv[1]))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "bench_CDN.pdf"
            urllib.request.urlretrieve(URL, dest)
            main(dest)
