"""Writes the New York fixture from a real harvest: python tests/fixtures/make_ny_sample.py path/to/ny-local-laws-snapshot.json.gz

ny_snapshot_sample.json holds the chosen filings of a snapshot `python -m local_laws harvest-ny` wrote, copied as the harvest kept them, with the snapshot's reading times and counts made the sample's own: total is the number of filings chosen, and years counts them by filing year from the first to the last, as a harvest does.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from local_laws import nylaws  # noqa: E402

HERE = Path(__file__).resolve().parent
# Each is here for a rule or a sentence the tests check. No month holds more than two, so a test can make a year too large for one query and still read it by month.
CHOSEN = {
    "090213438003dcc1.pdf": "the earliest filing, from 1995, before the database's stated start",
    "090213438003dcca.pdf": "a 1997 filing, and a year of two",
    "090213438003dccb.pdf": "the other 1997 filing",
    "0902134380069747.pdf": "TOWN OF HEMPSTEAD in 1999, in the Census sample",
    "09021343800682ff.pdf": "CITY OF BATAVIA in 1999, in the Census sample, which also has TOWN OF BATAVIA",
    "0902134380038669.pdf": "BRIGHTON, a name two towns have",
    "090213438001c3dd.pdf": "LEWIS (LEWIS CO), a county written short",
    "090213438000f96e.pdf": "SOUTH NYACK, a village dissolved before 2022",
    "090213438000d774.pdf": "TOWN OF BATAVIA in 2008",
    "{D057F6FC-1C21-46BC-9209-82F8DD971993}.pdf": "the Saratoga County Code, one of the two codifications, with enactedThrough",
    "0902134380009926.pdf": "AMHERST  (CORRECTED COPY), a remark after the name",
    "09021343800cf44e.pdf": "TOWN OF HEMPSTEAD in 2015, with a title",
    "09021343800dcab1.pdf": "CITY OF BATAVIA in 2015",
    "090213438010451e.pdf": "East Hampton, one of the three filings without a law number",
    "0902134380110542.pdf": "VILLAGE OF THE BRANCH, a name that repeats its title",
    "090213438026addd.pdf": "CHESTER (WARREN COUNTY), with a law year",
    "09021343802b170b.pdf": "TOWN OF BATAVIA in 2020",
    "09021343802f7ae6.pdf": "New York City in 2021",
    "0902134380343917.pdf": "CITY OF BATAVIA in 2024",
    "090213438036563e.pdf": "TOWN OF BATAVIA in 2025",
    "0902134380363de8.pdf": "TOWN OF HEMPSTEAD in 2025, the second filing that January",
    "09021343803b7aa9.pdf": "Buffalo in January 2026, standard time",
    "09021343803c5ac8.pdf": "TOWN OF HEMPSTEAD in March 2026",
    "09021343803c6660.pdf": "New York City in March 2026, the second filing that month",
    "09021343803e6ba8.pdf": "New York City in July 2026, daylight time",
}


def sample(snapshot):
    items = {item["filename"]: item for item in snapshot["items"]}
    missing = sorted(set(CHOSEN) - set(items))
    if missing:
        raise SystemExit(f"not in the snapshot: {missing}")
    chosen = sorted((items[name] for name in CHOSEN), key=lambda item: item["filename"] or "")
    years = Counter(nylaws.filed_year(item) for item in chosen)
    months = Counter(item["fields"]["dateFiled"][0][:7] for item in chosen)
    if max(months.values()) > 2:
        raise SystemExit(f"a month holds more than two filings: {months.most_common(1)}")
    return {
        "api": snapshot["api"],
        "category": snapshot["category"],
        "started_at": snapshot["started_at"],
        "finished_at": snapshot["finished_at"],
        "total": len(chosen),
        "years": {str(year): years[year] for year in range(min(years), max(years) + 1)},
        "items": chosen,
    }


def main(path):
    out = HERE / "ny_snapshot_sample.json"
    out.write_text(json.dumps(sample(nylaws.load(path)), indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1])
