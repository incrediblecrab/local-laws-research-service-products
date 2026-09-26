"""New York's older index: the release's export read and typed, checked against the State's data file in the same release, and matched to governments."""

import datetime
import io
import re
import struct
import zipfile

import pytest

from conftest import NY_INDEX, ny_snapshot, units_rows
from local_laws import census, nyindex, nylaws
from local_laws.census import SourceChanged
from test_nylaws import GOVERNMENTS

EXPORT = census.zip_member(NY_INDEX, nyindex.EXPORT_MEMBER).decode("utf-8")
STATE = census.zip_member(NY_INDEX, nyindex.STATE_MEMBER)


def rezip(export=EXPORT, state=STATE):
    """The sample release with its export or the State's data file replaced."""
    folder = zipfile.ZipFile(io.BytesIO(NY_INDEX)).namelist()[0].split("/")[0]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(f"{folder}/input/LGSSLAWS", state)
        archive.writestr(f"{folder}/output/LocalLawsIndex.tsv", export.encode("utf-8"))
    return out.getvalue()


def edit_line(number, column, value):
    """The export with one field of one line replaced; line 0 is the header."""
    lines = EXPORT.split("\n")
    values = lines[number].split("\t")
    values[column] = value
    lines[number] = "\t".join(values)
    return "\n".join(lines)


def test_the_sample_reads_as_its_state_records_with_every_field_typed():
    table, records = nyindex.read(NY_INDEX)
    assert (len(table), records) == (14, 14)
    assert [row["index_row"] for row in table] == list(range(1, 15))
    assert table[0] == {"index_row": 1, "municipality_type": None, "municipality_name": None, "law_year": None, "law_number": None, "date_filed": None, "title": None, "subject": None, "pages": 0, "entry_date": datetime.date(2002, 9, 23)}
    assert table[1] == {"index_row": 2, "municipality_type": "City", "municipality_name": "Batavia", "law_year": 1969, "law_number": "1", "date_filed": datetime.date(1969, 3, 13), "title": "Partial tax exemption - real property", "subject": "exemption", "pages": 1, "entry_date": datetime.date(1999, 6, 2)}
    assert "(~Water Rates)" in table[2]["title"], "a title is kept as the export gives it"
    assert (table[6]["law_year"], table[6]["date_filed"]) == (2002, datetime.date(1900, 4, 16)), "a wrong date is kept as recorded"
    assert table[7]["entry_date"] is None and table[11]["municipality_type"] == "TOWN"
    assert (table[13]["municipality_type"], table[13]["municipality_name"]) == ("Lacona", "Village"), "a row whose type and name are swapped is kept as recorded"


def test_the_state_s_text_and_dates_are_read_as_the_export_writes_them():
    assert nyindex.text(b"Port  Washington   Nort ") == "Port Washington Nort"
    assert nyindex.text(b"Ch\xa8teaugay") == "Chateaugay"
    assert (nyindex.day(0), nyindex.day(1), nyindex.day(36525)) == (None, datetime.date(1900, 3, 2), datetime.date(2000, 3, 1))


@pytest.mark.parametrize("export, message", [
    (EXPORT.replace("Entry Date", "Entered", 1), "the export's header is"),
    (edit_line(2, 8, "4\textra"), "line 2 of the export has 10 fields, not 9"),
    (edit_line(2, 2, "969"), "line 2 of the export has year '969' and pages '1'"),
    (edit_line(2, 7, "one"), "line 2 of the export has year '1969' and pages 'one'"),
    (edit_line(2, 4, "1969-03-13"), "line 2 of the export has Filing Date '1969-03-13', not MM/DD/YYYY"),
    (edit_line(2, 8, "06/02/99"), "line 2 of the export has Entry Date '06/02/99', not MM/DD/YYYY"),
])
def test_an_export_the_table_does_not_document_stops_the_read(export, message):
    with pytest.raises(SourceChanged, match=re.escape(message)):
        nyindex.read(rezip(export=export))


def patched(offset, value, fmt="<H"):
    state = bytearray(STATE)
    struct.pack_into(fmt, state, offset, value)
    return bytes(state)


@pytest.mark.parametrize("state, message", [
    (STATE[:31], "the State's LGSSLAWS is 31 bytes, shorter than its header"),
    (STATE[:-1], "the State's LGSSLAWS header gives 14 records of 75 bytes in 1,081 bytes"),
    (patched(26, 76), "the State's LGSSLAWS header gives 14 records of 76 bytes"),
    (patched(28, 13, "<I"), "the export has 14 rows; the State's LGSSLAWS holds 13 records"),
    (patched(32 + nyindex.PAGES_AT, 999), "1 export rows are not records in the State's LGSSLAWS, such as ["),
])
def test_a_state_file_that_is_not_the_export_stops_the_read(state, message):
    with pytest.raises(SourceChanged, match=re.escape(message)):
        nyindex.read(rezip(state=state))


def test_an_export_row_the_state_does_not_hold_stops_the_read_but_a_title_is_not_checked():
    with pytest.raises(SourceChanged, match=re.escape("1 export rows are not records in the State's LGSSLAWS")):
        nyindex.read(rezip(export=edit_line(2, 6, "exemptions")))
    table, _ = nyindex.read(rezip(export=edit_line(2, 5, "another title")))
    assert table[1]["title"] == "another title", "the State keeps the titles in a file the build does not read"


def test_the_type_is_read_with_only_its_first_letter_capitalized():
    assert [nyindex.read_type(kind) for kind in ("TOWN", "TOwn", "town", "Village", "", None)] == ["Town", "Town", "Town", "Village", "", None]
    table = nyindex.match([{"municipality_type": kind, "municipality_name": name} for kind, name in (
        ("TOWN", "CHESTER"), ("VIllage", "Chester"), ("town", "Chester (Warren County)"), ("Lacona", "Village"), (None, "Chester"))], GOVERNMENTS)
    assert [(row["census_id"], row["match"], row["candidates"]) for row in table] == [
        (None, "ambiguous", ["1", "2"]), ("3", "name", []), ("2", "name_county", []), (None, "unmatched", []), (None, "unmatched", [])]
    assert table[0]["municipality_type"] == "TOWN", "the row keeps the type as the index writes it"


def sample_tables():
    governments, _ = units_rows()
    table, _ = nyindex.read(NY_INDEX)
    return nyindex.match(table, governments), governments, nylaws.match(nylaws.rows(ny_snapshot()), governments)


def test_the_sample_matches_the_census_sample_s_new_york_governments():
    table, _, _ = sample_tables()
    assert {row["index_row"]: row["census_id"] for row in table if row["census_id"]} == {2: "109507", 3: "109507", 4: "109507", 5: "170831", 10: "170895", 11: "170895", 12: "170895"}
    assert all(row["match"] == "unmatched" for row in table if row["census_id"] is None)


def test_stats_count_the_sample():
    table, governments, ny = sample_tables()
    assert nyindex.stats(table, governments, ny) == {
        "rows": 14,
        "with_title": 11,
        "law_years": {"1960s": {"rows": 2, "matched": 2}, "1970s": {"rows": 3, "matched": 1}, "1990s": {"rows": 3, "matched": 3}, "2000s": {"rows": 3, "matched": 1}, "none": {"rows": 3, "matched": 0}},
        "first_law_year": 1969,
        "last_law_year": 2002,
        "municipality_types": {"Town": {"rows": 4, "matched": 3}, "City": {"rows": 3, "matched": 3}, "Village": {"rows": 3, "matched": 0}, "": {"rows": 2, "matched": 0}, "Lacona": {"rows": 1, "matched": 0}, "TOWN": {"rows": 1, "matched": 1}},
        "matches": {"name": {"rows": 7, "names": 4}, "name_county": {"rows": 0, "names": 0}, "ambiguous": {"rows": 0, "names": 0}, "unmatched": {"rows": 7, "names": 7}},
        "governments": {"CITY OF": {"governments": 1, "with_rows": 1}, "TOWN OF": {"governments": 2, "with_rows": 2}},
        "first_filed": "1900-04-16",
        "last_filed": "2002-04-15",
        "undated": 3,
        "filed_before_search": 6,
        "filed_from_search": 5,
        "in_search": 2,
        "filed_before_law_year": 1,
        "filed_after_entry": 0,
        "first_entered": "1997-06-11",
        "last_entered": "2018-12-05",
        "ambiguous": [],
        "unmatched": [["", "", 1], ["", "East Greenbush", 1], ["Lacona", "Village", 1], ["Town", "Charleston", 1], ["Village", "Black River", 1], ["Village", "Cornwall", 1], ["Village", "South Nyack", 1]],
    }


def test_a_row_is_in_the_search_when_a_filing_has_its_type_name_number_and_date():
    table, governments, ny = sample_tables()
    later = [row for row in table if row["date_filed"] and row["date_filed"] >= nyindex.SEARCH_BEGINS]
    searched = {nylaws.filing(row["municipality_type"], row["municipality_name"], row["law_number"], row["date_filed"]) for row in ny}
    assert [row["index_row"] for row in later if nylaws.filing(nyindex.read_type(row["municipality_type"]), row["municipality_name"], row["law_number"], row["date_filed"]) in searched] == [4, 11]
    capitals = [dict(row, municipality_type=row["municipality_type"].upper()) if row["index_row"] == 4 else row for row in table]
    assert nyindex.stats(capitals, governments, ny)["in_search"] == 2, "CITY is read as City here too"
    moved = [dict(row, date_filed=row["date_filed"] + datetime.timedelta(days=1)) if row["index_row"] == 4 else row for row in table]
    assert nyindex.stats(moved, governments, ny)["in_search"] == 1
