"""Draws the New York filings local_laws/precision.py records from a build's tables and asks the Department's API about each, one request a second, printing one RESULTS line per filing.

python checks/ny_precision.py --local DIR [--draw-only]

DIR is a directory `python -m local_laws run --local DIR` wrote. With --draw-only, nothing is requested: the draw is compared with the one precision.py records, which it reproduces from the tables published on September 26, 2026. A later build has other pools, so it draws other filings.
"""

import argparse
import json
import random
import sys
from pathlib import Path
from urllib.parse import urlencode

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_laws import nylaws, precision  # noqa: E402
from local_laws.http import Fetcher  # noqa: E402


def stem(name):
    return name.split(" OF ", 1)[-1]


def unnamed(census_name, names):
    """The name after each other Census title with which no government in names is named."""
    title = next(title for title in nylaws.TITLES.values() if census_name.startswith(title + " "))
    stem = census_name[len(title) + 1:]
    return tuple(f"{other} {stem}" for other in nylaws.TITLES.values() if other != title and f"{other} {stem}" not in names)


def draw(ny, governments):
    """[(part, filing, government, decoy, others, unnamed phrases)] in the order precision.py records them."""
    pool = sorted((row for row in ny if row["match"] in nylaws.MATCHED and row["filename"] not in precision.CALIBRATION), key=lambda row: row["filename"])
    main = random.Random(precision.SEEDS["main"]).sample(pool, precision.SIZES["main"])
    chosen = {row["filename"] for row in main}
    rest = [row for row in pool if row["match"] == "name_county" and row["filename"] not in chosen]
    supplement = random.Random(precision.SEEDS["supplement"]).sample(rest, precision.SIZES["supplement"])
    pools = {"main": len(pool), "supplement": len(rest)}
    if pools != precision.POOLS:
        print(f"pools {pools} are not the {precision.POOLS} precision.py records, so this draw is not its draw", file=sys.stderr)
    state = [row for row in governments if row["state_fips"] == "36"]
    by_id = {row["census_id"]: row for row in state}
    names = {row["name"] for row in state}
    by_type = {}
    for row in state:
        by_type.setdefault(row["government_type"], []).append(row)
    decoys = random.Random(precision.SEEDS["decoy"])
    drawn = []
    for part, filings in (("main", main), ("supplement", supplement)):
        for filing in filings:
            government = by_id[filing["census_id"]]
            decoy = decoys.choice([row for row in by_type[government["government_type"]] if row["census_id"] != government["census_id"]])
            others = [row for row in state if stem(row["name"]) == stem(government["name"]) and row["census_id"] != government["census_id"] and row["government_type"] not in (government["government_type"], "county")][:2]
            drawn.append((part, filing, government, decoy, others, unnamed(government["name"], names)))
    return drawn


def ask(fetcher, filename, term, text):
    query = f"cat:({nylaws.CATEGORY}) AND fn:({filename}) AND ({term})"
    url = nylaws.API + "?" + urlencode({"query": query, "sort": "filename", "limit": 1, "offset": 0, "expand": "metadata", "search_document_text": "true" if text else "false"})
    return int(json.loads(fetcher.get(url))["total_count"] > 0)


def both(fetcher, filename, term):
    """(found with text, found in metadata alone), the second asked only when the first found it."""
    found = ask(fetcher, filename, term, True)
    return found, ask(fetcher, filename, term, False) if found else None


def check(fetcher, part, filing, government, decoy, others, phrases):
    """One RESULTS line and the filing's UNNAMED answers. The September 26, 2026 check asked the same questions, but GENERIC without text and the UNNAMED phrases only after every filing's other answers."""
    filename = filing["filename"]
    generic = both(fetcher, filename, precision.GENERIC)
    name = both(fetcher, filename, f'"{government["name"]}"')
    county = None
    if government["government_type"] != "county":
        county = both(fetcher, filename, f'"COUNTY OF {government["county_name"]}" OR "{government["county_name"]} COUNTY"')
    found = ask(fetcher, filename, f'"{decoy["name"]}"', True)
    other = tuple((row["name"], row["county_name"], ask(fetcher, filename, f'"{row["name"]}"', True)) for row in others)
    asked = tuple((phrase, ask(fetcher, filename, f'"{phrase}"', True)) for phrase in phrases)
    return (part, filename, filing["date_filed"].isoformat(), government["census_id"], government["name"], generic, name, county, (decoy["name"], found), other), asked


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--local", required=True, help="a directory `python -m local_laws run --local` wrote")
    parser.add_argument("--draw-only", action="store_true", help="request nothing; compare the draw with precision.py's")
    args = parser.parse_args(argv)
    data = Path(args.local) / "data"
    ny = pq.read_table(data / "ny_local_laws.parquet").to_pylist()
    governments = pq.read_table(data / "governments.parquet").to_pylist()
    drawn = draw(ny, governments)
    if args.draw_only:
        mine = [(part, filing["filename"], filing["date_filed"].isoformat(), government["census_id"], government["name"], decoy["name"], tuple((row["name"], row["county_name"]) for row in others), sorted(phrases)) for part, filing, government, decoy, others, phrases in drawn]
        recorded = [(part, filename, filed, census_id, census_name, decoy[0], tuple((name, county_name) for name, county_name, _ in other), sorted(phrase for phrase, _ in precision.UNNAMED[filename])) for part, filename, filed, census_id, census_name, generic, name, county, decoy, other in precision.RESULTS]
        if mine == recorded:
            print(f"the draw is the one precision.py records: {len(mine)} filings, with the same decoys, same-name governments and UNNAMED phrases")
            return 0
        for left, right in zip(mine, recorded):
            if left != right:
                print(f"drawn {left}, recorded {right}")
        print(f"{len(mine)} drawn, {len(recorded)} recorded", file=sys.stderr)
        return 1
    fetcher = Fetcher()
    unnamed_lines = []
    try:
        for entry in drawn:
            line, asked = check(fetcher, *entry)
            print(f"    {line!r},", flush=True)
            unnamed_lines.append(f"    {line[1]!r}: {asked!r},")
    finally:
        fetcher.close()
    print("UNNAMED = {", *unnamed_lines, "}", sep="\n")
    print(f"{fetcher.requests} requests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
