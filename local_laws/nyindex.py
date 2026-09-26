"""New York's index of local laws from before its online search: an index database of local laws filed with the Secretary of State, released by the State under the Freedom of Information Law and published under CC0 by the Local Geohistory Project.

The Department of State's search (nylaws.py) holds filings from 1998 on. For older laws, the State released a copy of its DataPerfect index database on March 17, 2022 under FOIL Request No. DOS-22-02-052. The Local Geohistory Project published the release's data files with a tab-separated export of them, made by running DataPerfect over the files and tidying its output, as a GitHub repository archived on Zenodo under CC0 1.0. The build reads the export at the pinned Zenodo version, checks it field by field against the State's own data file in the same release, and matches each row to a government by nylaws's rules.
"""

import datetime
import struct
from collections import Counter, defaultdict

from . import nylaws
from .census import SourceChanged, check_sha256, zip_member

TITLE = "Law Indexes: New York (Local Laws)"
CREATOR = "Mark A. Connelly"
DOI = "10.5281/zenodo.10446245"
RECORD = "https://zenodo.org/records/10446245"
URL = RECORD + "/files/localgeohistoryproject/law-indexes-new-york-local-laws-v1.0.0.zip?download=1"
# SHA-256 of the zip as downloaded on September 26, 2026: the v1.0.0 release, published December 31, 2023, of the GitHub repository at COMMIT.
SHA256 = "d37330d611971bdfec864f93e7d8e101db5a8c3cef7ff33e5b94f07f3f02822d"
REPOSITORY = "https://github.com/localgeohistoryproject/law-indexes-new-york-local-laws"
COMMIT = "b6c3127e3b6afd2eb810f7e79c7baa9398733f2f"
LICENSE = "CC0-1.0"
EXPORT_MEMBER = r"LocalLawsIndex\.tsv"
STATE_MEMBER = r"LGSSLAWS"
HEADER = ("Municipality Type", "Municipality Name", "Year", "Number of Law", "Filing Date", "Title", "Subject", "Pages", "Entry Date")
NO_DATE = "\\N"
# The State's data file: a 32-byte header whose bytes 26-27 give the record length and 28-31 the number of records, then the records.
# Where each field sits in a record was found by comparing the file with the export; the build checks that every record reads as one of the export's rows.
RECORD_BYTES = 75
TEXTS = {"municipality_type": slice(0, 8), "municipality_name": slice(8, 33), "law_number": slice(37, 40), "subject": slice(45, 65)}
YEAR_AT, FILED_AT, PAGES_AT, ENTERED_AT = 33, 40, 65, 69
# DataPerfect keeps a date as the number of days since this day, and no date as 0.
EPOCH = datetime.date(1900, 3, 1)
# The day the Department's search begins; the card counts the index's rows before it and compares the rest with ny_local_laws.
SEARCH_BEGINS = datetime.date(1998, 1, 1)
# The columns the table takes from the export, before the match.
FIELDS = ("index_row", "municipality_type", "municipality_name", "law_year", "law_number", "date_filed", "title", "subject", "pages", "entry_date")


def download(fetcher):
    data = fetcher.get(URL)
    check_sha256(data, SHA256, URL)
    return data


def text(raw):
    """A State text field as the export writes it: Windows-1252, runs of spaces as one, and ¨ as a, as the export's tidying does."""
    return " ".join(raw.decode("cp1252").replace("¨", "a").split())


def day(number):
    return EPOCH + datetime.timedelta(days=number) if number else None


def state_records(data):
    """The records in the State's data file, each as record() gives a row: (type, name, law year, law number, filing date, subject, pages, entry date)."""
    if len(data) < 32:
        raise SourceChanged(f"the State's {STATE_MEMBER} is {len(data)} bytes, shorter than its header")
    length, count = struct.unpack_from("<HI", data, 26)
    if length != RECORD_BYTES or len(data) < 32 + count * length:
        raise SourceChanged(f"the State's {STATE_MEMBER} header gives {count:,} records of {length} bytes in {len(data):,} bytes; the build reads {RECORD_BYTES}-byte records")
    out = []
    for start in range(32, 32 + count * length, length):
        raw = data[start:start + length]
        values = {field: text(raw[place]) for field, place in TEXTS.items()}
        out.append((values["municipality_type"], values["municipality_name"], struct.unpack_from("<i", raw, YEAR_AT)[0], values["law_number"],
                    day(struct.unpack_from("<H", raw, FILED_AT)[0]), values["subject"], struct.unpack_from("<H", raw, PAGES_AT)[0], day(struct.unpack_from("<H", raw, ENTERED_AT)[0])))
    return out


def record(row):
    """A row's fields as the State's data file holds them: blank text as empty, no law year as 0."""
    return (row["municipality_type"] or "", row["municipality_name"] or "", row["law_year"] or 0, row["law_number"] or "", row["date_filed"], row["subject"] or "", row["pages"], row["entry_date"])


def export_date(value, column, line):
    if value == NO_DATE:
        return None
    try:
        return datetime.datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        raise SourceChanged(f"line {line} of the export has {column} {value!r}, not MM/DD/YYYY or {NO_DATE}") from None


def rows(data):
    """One row per line of the export, typed, without the match to governments. Stops at a line the table's documentation does not cover."""
    lines = data.decode("utf-8").split("\n")
    if lines[-1] == "":
        lines.pop()
    if tuple(lines[0].split("\t")) != HEADER:
        raise SourceChanged(f"the export's header is {lines[0]!r}, not the columns the table documents")
    out = []
    for line, content in enumerate(lines[1:], start=1):
        values = content.split("\t")
        if len(values) != len(HEADER):
            raise SourceChanged(f"line {line} of the export has {len(values)} fields, not {len(HEADER)}")
        kind, name, year, number, filed, title, subject, pages, entered = values
        if not (year.isdigit() and len(year) == 4) or not pages.isdigit():
            raise SourceChanged(f"line {line} of the export has year {year!r} and pages {pages!r}")
        out.append({
            "index_row": line,
            "municipality_type": kind or None,
            "municipality_name": name or None,
            "law_year": int(year) or None,
            "law_number": number or None,
            "date_filed": export_date(filed, "Filing Date", line),
            "title": title or None,
            "subject": subject or None,
            "pages": int(pages),
            "entry_date": export_date(entered, "Entry Date", line),
        })
    return out


def check(table, state):
    """Stops unless the State's data file holds one record for each row of the export, equal to it in every field but the title, which the State keeps in another file."""
    if len(state) != len(table):
        raise SourceChanged(f"the export has {len(table):,} rows; the State's {STATE_MEMBER} holds {len(state):,} records")
    exported, held = Counter(map(record, table)), Counter(state)
    if exported != held:
        missing, extra = exported - held, held - exported
        raise SourceChanged(f"{sum(missing.values()):,} export rows are not records in the State's {STATE_MEMBER}, such as {list(missing)[:2]}, and {sum(extra.values()):,} records are not export rows, such as {list(extra)[:2]}")


def read(data):
    """(rows, the number of State records) from the release's zip, after checking the export against the State's data file."""
    table = rows(zip_member(data, EXPORT_MEMBER))
    state = state_records(zip_member(data, STATE_MEMBER))
    check(table, state)
    return table, len(state)


def read_type(value):
    """The index's type as the search writes it: TOWN, town and TOwn as Town."""
    return value.capitalize() if value else value


def match(table, governments):
    return nylaws.match(table, governments, read_type)


def first(values):
    return min(values).isoformat() if values else None


def last(values):
    return max(values).isoformat() if values else None


def stats(table, governments, ny):
    """The counts the card shows for the index; ny is ny_local_laws. verify recomputes them from the published tables."""
    titles = {row["census_id"]: nylaws.split_title(row["name"])[0] for row in governments if row["state"] == "NY" and row["government_type"] in nylaws.GOVERNMENT_TYPES.values()}
    names = defaultdict(Counter)
    decades, kinds = defaultdict(Counter), defaultdict(Counter)
    for row in table:
        names[row["match"]][(row["municipality_type"] or "", row["municipality_name"] or "")] += 1
        decade = "none" if row["law_year"] is None else f"{row['law_year'] // 10 * 10}s"
        for tally, key in ((decades, decade), (kinds, row["municipality_type"] or "")):
            tally[key]["rows"] += 1
            tally[key]["matched"] += row["census_id"] is not None

    def listed(match):
        return [[kind, name, n] for (kind, name), n in sorted(names[match].items(), key=lambda item: (-item[1], item[0]))]

    searched = {nylaws.filing(row["municipality_type"], row["municipality_name"], row["law_number"], row["date_filed"]) for row in ny}
    later = [row for row in table if row["date_filed"] is not None and row["date_filed"] >= SEARCH_BEGINS]
    filed = [row["date_filed"] for row in table if row["date_filed"] is not None]
    # A census_id that is not a New York government is left out here; verify names it.
    filers = Counter(titles[census_id] for census_id in {row["census_id"] for row in table if row["census_id"] in titles})
    return {
        "rows": len(table),
        "with_title": sum(1 for row in table if row["title"]),
        "law_years": {decade: {"rows": entry["rows"], "matched": entry["matched"]} for decade, entry in sorted(decades.items(), key=lambda item: (item[0] == "none", item[0]))},
        "first_law_year": min((row["law_year"] for row in table if row["law_year"] is not None), default=None),
        "last_law_year": max((row["law_year"] for row in table if row["law_year"] is not None), default=None),
        "municipality_types": {kind: {"rows": entry["rows"], "matched": entry["matched"]} for kind, entry in sorted(kinds.items(), key=lambda item: (-item[1]["rows"], item[0]))},
        "matches": {match: {"rows": sum(names[match].values()), "names": len(names[match])} for match in nylaws.MATCHES},
        "governments": {title: {"governments": n, "with_rows": filers[title]} for title, n in sorted(Counter(titles.values()).items())},
        "first_filed": first(filed),
        "last_filed": last(filed),
        "undated": len(table) - len(filed),
        "filed_before_search": sum(1 for date in filed if date < SEARCH_BEGINS),
        "filed_from_search": len(later),
        "in_search": sum(1 for row in later if nylaws.filing(read_type(row["municipality_type"]), row["municipality_name"], row["law_number"], row["date_filed"]) in searched),
        "filed_before_law_year": sum(1 for row in table if row["date_filed"] and row["law_year"] and row["date_filed"].year < row["law_year"]),
        "filed_after_entry": sum(1 for row in table if row["date_filed"] and row["entry_date"] and row["date_filed"] > row["entry_date"]),
        "first_entered": first([row["entry_date"] for row in table if row["entry_date"] is not None]),
        "last_entered": last([row["entry_date"] for row in table if row["entry_date"] is not None]),
        "ambiguous": listed("ambiguous"),
        "unmatched": listed("unmatched"),
    }
