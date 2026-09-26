"""Writes the New York index fixture from the real release: python tests/fixtures/make_ny_index_sample.py path/to/law-indexes-new-york-local-laws-v1.0.0.zip

ny_index_sample.zip holds, under the release's own folder name, the chosen lines of the export (output/LocalLawsIndex.tsv, with its header) and the State's records for them (input/LGSSLAWS: the real header with the record count made the sample's, then each chosen line's record, copied byte for byte, in the State file's order). Both are CC0, like the release.
"""

import io
import struct
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from local_laws import census, nyindex  # noqa: E402

HERE = Path(__file__).resolve().parent
# Line numbers in the real export, each here for a rule or a sentence the tests check.
CHOSEN = {
    1: "a blank record: no type, name, number or filing date, and year 0000",
    5442: "City Batavia, 1969: CITY OF BATAVIA is in the Census sample",
    5559: "City Batavia, 1998: a title with ~, and a filing from 1998 on that the search sample lacks",
    5562: "City Batavia, 1999: also in the search sample (09021343800682ff.pdf)",
    5576: "Town Batavia, 1975: TOWN OF BATAVIA, the other Batavia",
    7868: "Village Black River: year 0000 and no filing date",
    15934: "Town Charleston: a law of 2002 dated 1900",
    22201: "Village Cornwall: no entry date",
    27400: "East Greenbush with no type",
    44721: "Town Hempstead, 1969: TOWN OF HEMPSTEAD",
    47542: "Town Hempstead, 1999: also in the search sample (0902134380069747.pdf)",
    47728: "TOWN HEMPSTEAD: a type in capitals",
    107759: "Village South Nyack: dissolved before 2022",
    119822: "Lacona: a type that is a village's name",
}
MODIFIED = (2023, 12, 31, 0, 0, 0)


def sample(data):
    members = zipfile.ZipFile(io.BytesIO(data)).namelist()
    folder = members[0].split("/")[0]
    export = census.zip_member(data, nyindex.EXPORT_MEMBER).decode("utf-8").split("\n")
    state = census.zip_member(data, nyindex.STATE_MEMBER)
    table = {row["index_row"]: row for row in nyindex.rows(census.zip_member(data, nyindex.EXPORT_MEMBER))}
    wanted = defaultdict(list)
    for line in CHOSEN:
        wanted[nyindex.record(table[line])].append(line)
    length, count = struct.unpack_from("<HI", state, 26)
    records = []
    for number, parsed in enumerate(nyindex.state_records(state)):
        if wanted.get(parsed):
            wanted[parsed].pop()
            records.append(state[32 + number * length:32 + (number + 1) * length])
    if len(records) != len(CHOSEN):
        raise SystemExit(f"found {len(records)} State records for {len(CHOSEN)} lines")
    header = state[:28] + struct.pack("<I", len(records))
    tsv = "\n".join([export[0]] + [export[line] for line in sorted(CHOSEN)]) + "\n"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo(f"{folder}/input/LGSSLAWS", MODIFIED), header + b"".join(records))
        archive.writestr(zipfile.ZipInfo(f"{folder}/output/LocalLawsIndex.tsv", MODIFIED), tsv.encode("utf-8"))
    return out.getvalue()


if __name__ == "__main__":
    data = Path(sys.argv[1]).read_bytes()
    census.check_sha256(data, nyindex.SHA256, sys.argv[1])
    (HERE / "ny_index_sample.zip").write_bytes(sample(data))
    print(f"wrote {len(CHOSEN)} lines to {HERE / 'ny_index_sample.zip'}")
