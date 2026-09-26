"""Writes the NFIP fixtures from FEMA's files: python tests/fixtures/make_nfip_sample.py path/to/nation.csv path/to/NfipCommunityStatusBook.parquet

nfip_nation_sample.csv is the Community Status Book's national report with only the chosen communities left, each with the lines the report prints beneath it, and the report's three headers; every record kept is copied byte for byte. nfip_api_sample.parquet is the OpenFEMA file's records for the same communities and for three that the report does not list, in the file's order and schema. Both are works of the United States Government.
"""

import csv
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from local_laws import nfip  # noqa: E402

HERE = Path(__file__).resolve().parent
# The communities kept, by number, each here for a rule or a sentence the tests check.
CHOSEN = {
    "010116": "a note beneath a community",
    "010371": "the last community before the report repeats its header",
    "010224": "the first after the repeated header",
    "010153": "a county list the report carries on to a line of its own",
    "010465": "a name the API ends with a space, and NSFHA in place of a map date",
    "010350": "L beside the current map's date",
    "010504": "M beside the current map's date",
    "020013": "no program, no map date, no character after its number and two spaces in its name",
    "020127": "E beside its date of entry",
    "025009": "a first FIRM of 1969 that the API gives as 2069",
    "040133": "a tribal community that participates",
    "060243": "class 1 in the Community Rating System",
    "080037": "All Zone D in place of a map date",
    "080296": "> beside a current map date after the report",
    "120425": "a note with line breaks and an HTML entity",
    "120665": "a note the report breaks over two lines",
    "350045": "class 10, with a discount only the API gives",
    "380146": "a current map date of 01/02/50, read as 2050",
    "600001": "a territory, American Samoa",
    "720100": "a territory, Puerto Rico",
    "010214": "S beside its sanction's date, in the Regular Program",
    "020040": "W beside its sanction's date",
    "010095": "the sample's first community not participating, with no program or code",
    "040123": "a tribal community not participating, with a note",
    "160056": "a sanction dated after the report",
}
# Communities the OpenFEMA file holds and the report does not list.
API_ONLY = {
    "080268": "participating",
    "010469": "not participating",
    "530335": "tribal, not participating",
}


def records(text):
    """(values, raw text) for each CSV record, the raw text being the lines the record spans."""
    lines = text.splitlines(keepends=True)
    taken = []

    def feed():
        for line in lines:
            taken.append(line)
            yield line

    for values in csv.reader(feed()):
        yield [nfip.cell(value) for value in values], "".join(taken)
        taken.clear()


def main(report_path, api_path):
    text = Path(report_path).read_bytes().decode("utf-8")
    kept, keeping, found = [], False, set()
    for values, raw in records(text):
        if values in (nfip.COLUMNS, nfip.SANCTIONED):
            kept.append(raw)
            keeping = False
            continue
        if values[0]:
            cid = nfip.CID.fullmatch(values[0]).group(1)
            keeping = cid in CHOSEN
            if keeping:
                found.add(cid)
        if keeping:
            kept.append(raw)
    missing = sorted(set(CHOSEN) - found)
    if missing:
        raise SystemExit(f"not in the report: {missing}")
    (HERE / "nfip_nation_sample.csv").write_bytes("".join(kept).encode("utf-8"))
    table = pq.read_table(api_path)
    wanted = sorted(set(CHOSEN) | set(API_ONLY))
    sample = table.filter(pc.is_in(table["communityIdNumber"], value_set=pa.array(wanted)))
    if sample.num_rows != len(wanted):
        raise SystemExit(f"the OpenFEMA file has {sample.num_rows} of the {len(wanted)} communities")
    pq.write_table(sample, HERE / "nfip_api_sample.parquet")
    print(f"{len(CHOSEN)} communities in {len(kept)} records; {sample.num_rows} OpenFEMA records")


if __name__ == "__main__":
    main(*sys.argv[1:])
