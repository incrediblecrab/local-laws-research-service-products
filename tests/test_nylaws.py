"""New York's local laws: the harvest against a fake of the Department's API, the checks on its rows, and the matching to governments."""

import copy
import datetime
import json
import re

import pytest

from conftest import NY_SAMPLE, FakeFetcher, FakeNYApi, ny_snapshot, units_rows
from local_laws import nylaws
from local_laws.census import SourceChanged


def harvest(**kwargs):
    return nylaws.harvest(FakeFetcher(ny=FakeNYApi(**kwargs)))


def posted(item, uid, filename):
    """A new filing like item, as the Department would post it."""
    new = copy.deepcopy(item)
    new.update(id=uid, filename=filename)
    return new


def test_a_harvest_holds_every_filing_once_with_the_counts_it_was_checked_against():
    snapshot = harvest()
    assert snapshot["items"] == NY_SAMPLE["items"]
    assert (snapshot["total"], snapshot["years"]) == (NY_SAMPLE["total"], NY_SAMPLE["years"])
    assert "Signature" not in json.dumps(snapshot), "the signed download links are left out"


def test_a_year_too_large_for_one_query_is_read_by_month(monkeypatch):
    monkeypatch.setattr(nylaws, "PAGE", 1)
    monkeypatch.setattr(nylaws, "WINDOW", 2)
    fetcher = FakeFetcher()
    snapshot = nylaws.harvest(fetcher)
    assert snapshot["items"] == NY_SAMPLE["items"]
    assert any("dateFiled:[2026-03-01T00:00:00Z TO 2026-03-31T23:59:59Z]" in query["query"] for query in fetcher.ny.queries), "the year with more filings than the window was read by month"


def test_a_month_too_large_for_one_query_stops_the_harvest(monkeypatch):
    monkeypatch.setattr(nylaws, "PAGE", 1)
    monkeypatch.setattr(nylaws, "WINDOW", 1)
    with pytest.raises(SourceChanged, match="the harvest needs a finer split"):
        harvest()


def earliest():
    return min(NY_SAMPLE["items"], key=lambda item: item["fields"]["dateFiled"][0])


def test_a_filing_posted_after_its_year_was_read_is_read_by_reading_that_year_again():
    new = posted(earliest(), "posted-during-the-harvest", "zzzz-new.pdf")
    year = new["fields"]["dateFiled"][0][:4]

    def post_once_the_year_is_read(api, params):
        if f"dateFiled:[{int(year) + 1}-" in params["query"] and all(item["id"] != new["id"] for item in api.items):
            api.items.append(copy.deepcopy(new))

    snapshot = harvest(before_answer=post_once_the_year_is_read)
    assert new in snapshot["items"] and snapshot["total"] == NY_SAMPLE["total"] + 1
    assert snapshot["years"][year] == NY_SAMPLE["years"][year] + 1


def test_a_category_that_does_not_settle_stops_the_harvest():
    count = iter(range(1_000_000))

    def post_before_every_category_count(api, params):
        if params["query"] == "cat:(Local Laws)" and params["sort"] == "filename":
            api.items.append(posted(earliest(), f"posted-{next(count)}", f"zzzz-{len(api.items)}.pdf"))

    with pytest.raises(SourceChanged, match="run again once the Department has finished posting"):
        harvest(before_answer=post_before_every_category_count)


def test_a_count_that_changes_while_a_part_is_paged_stops_the_harvest(monkeypatch):
    monkeypatch.setattr(nylaws, "PAGE", 1)

    def post_on_a_second_page(api, params):
        start, end = FakeNYApi.RANGE.fullmatch(params["query"]).groups()
        if params["offset"] == "1" and all(item["id"] != "posted-mid-part" for item in api.items):
            inside = next(item for item in api.items if start is None or start <= item["fields"]["dateFiled"][0] <= end)
            api.items.append(posted(inside, "posted-mid-part", "zzzz-mid.pdf"))

    with pytest.raises(SourceChanged, match="while it was read"):
        harvest(before_answer=post_on_a_second_page)


class StuckApi(FakeNYApi):
    """An API that answers every page as if it were the first."""

    def answer(self, url):
        return super().answer(re.sub(r"offset=\d+", "offset=0", url))


def test_pages_that_repeat_filings_stop_the_harvest(monkeypatch):
    monkeypatch.setattr(nylaws, "PAGE", 1)
    with pytest.raises(SourceChanged, match="different ones"):
        nylaws.harvest(FakeFetcher(ny=StuckApi()))


def test_a_saved_snapshot_loads_as_it_was(tmp_path):
    path = tmp_path / "snapshot.json.gz"
    nylaws.save(NY_SAMPLE, path)
    assert nylaws.load(path) == NY_SAMPLE


def test_rows_keep_every_field_typed():
    rows = nylaws.rows(ny_snapshot())
    assert len(rows) == NY_SAMPLE["total"]
    assert all(isinstance(row["date_filed"], datetime.date) and row["posted_at"].tzinfo is not None and nylaws.SHARE.fullmatch(row["share_url"]) for row in rows)
    item, first = NY_SAMPLE["items"][0], rows[0]
    fields = {field: (values[0] if values else None) for field, values in item["fields"].items()}
    assert (first["asset_id"], first["municipality_type"], first["municipality_name"], first["law_number"], first["subject"], first["title"]) == (
        item["id"], fields["municipalityType"], fields["municipalityName"], fields["lawNumber"], fields["subject"], fields["subject1"])
    assert first["date_filed"].isoformat() == fields["dateFiled"][:10] and first["filename"] == item["filename"] and first["file_bytes"] == item["size_in_bytes"]


@pytest.mark.parametrize("edit, message", [
    (lambda item: item["fields"].update(extra=["x"]), "metadata fields ['extra']"),
    (lambda item: item["fields"].pop("subject1"), "metadata fields ['subject1']"),
    (lambda item: item["fields"].update(lawNumber=["1", "2"]), "2 values for lawNumber"),
    (lambda item: item["fields"].update(dateFiled=["2020-03-05T12:00:00Z"]), "not midnight Central time"),
    (lambda item: item["fields"].update(dateFiled=[]), "has no dateFiled"),
    (lambda item: item["fields"].update(enactedThrough=["2020-03-05T00:00:00Z"]), "not midnight Central time"),
    (lambda item: item.update(share=item["share"] + "&Signature=x"), "not the public link"),
    (lambda item: item.update(share=None), "not the public link"),
    (lambda item: item.update(deleted_date="2026-01-01T00:00:00Z"), "not a current, released asset"),
    (lambda item: item.update(current_version=False), "not a current, released asset"),
    (lambda item: item.update(released_and_not_expired=False), "not a current, released asset"),
    (lambda item: item["fields"].update(year=["20x6"]), "has year '20x6'"),
])
def test_rows_stop_at_anything_the_table_does_not_document(edit, message):
    snapshot = ny_snapshot()
    edit(snapshot["items"][0])
    with pytest.raises(SourceChanged, match=re.escape(message)):
        nylaws.rows(snapshot)


def government(census_id, name, county, kind):
    return {"census_id": census_id, "state": "NY", "name": name, "county_name": county, "government_type": kind}


GOVERNMENTS = [
    government("1", "TOWN OF CHESTER", "ORANGE", "township"),
    government("2", "TOWN OF CHESTER", "WARREN", "township"),
    government("3", "VILLAGE OF CHESTER", "ORANGE", "municipal"),
    government("4", "TOWN OF AMHERST", "ERIE", "township"),
    government("5", "COUNTY OF ST LAWRENCE", "ST LAWRENCE", "county"),
    government("6", "CITY OF NEW YORK", "NEW YORK CITY", "municipal"),
    government("7", "TOWN OF SENECA FALLS", "SENECA", "township"),
    government("8", "TOWN OF SHELTER ISLAND", "SUFFOLK", "township"),
    government("9", "TOWN OF ELIZABETHTOWN", "ESSEX", "township"),
    government("10", "CHESTER FIRE DISTRICT", "ORANGE", "special_district"),
    {"census_id": "11", "state": "NJ", "name": "TOWN OF AMHERST", "county_name": "SUSSEX", "government_type": "township"},
    government("12", "VILLAGE OF BRANCH", "SUFFOLK", "municipal"),
    government("13", "VILLAGE OF CUBA", "ALLEGANY", "municipal"),
    government("14", "TOWN OF CUBA", "ALLEGANY", "township"),
    government("15", "TOWN OF THERESA", "JEFFERSON", "township"),
    government("16", "TOWN OF LEWIS", "LEWIS", "township"),
    government("17", "TOWN OF LEWIS", "ESSEX", "township"),
    government("18", "COUNTY OF LEWIS", "LEWIS", "county"),
    government("19", "COUNTY OF ESSEX", "ESSEX", "county"),
]


@pytest.mark.parametrize("kind, name, expected", [
    ("Town", "CHESTER", (None, "ambiguous", ["1", "2"])),
    ("Town", "Chester (Warren County)", ("2", "name_county", [])),
    ("Town", "Chester (Warren)", ("2", "name_county", [])),
    ("Town", "Chester (Essex County)", (None, "unmatched", [])),
    ("Village", "CHESTER", ("3", "name", [])),
    ("Town", "Amherst  (Corrected Copy)", ("4", "name", [])),
    ("Town", "Shelter Island  (Corrected Copy", ("8", "name", [])),
    ("County", "ST. LAWRENCE", ("5", "name", [])),
    ("County", "SAINT LAWRENCE", ("5", "name", [])),
    ("City", "NEW YORK", ("6", "name", [])),
    ("Village", "SENECA FALLS", (None, "unmatched", [])),
    ("Town", "ORANGE", (None, "unmatched", [])),
    ("Borough", "CHESTER", (None, "unmatched", [])),
    (None, None, (None, "unmatched", [])),
    ("Village", "VILLAGE OF THE BRANCH", ("12", "name", [])),
    ("Village", "CUBA VILLAGE", ("13", "name", [])),
    ("Town", "CUBA VILLAGE", (None, "unmatched", [])),
    ("Town", "TOWN OF CUBA", ("14", "name", [])),
    ("Town", "THERESA", ("15", "name", [])),
    ("Town", "TOWN OF THERESA", ("15", "name", [])),
    ("Village", "VILLAGE", (None, "unmatched", [])),
    ("Town", "LEWIS", (None, "ambiguous", ["16", "17"])),
    ("Town", "LEWIS (LEWIS CO)", ("16", "name_county", [])),
    ("Town", "LEWIS (LEWISCOUNTY)", ("16", "name_county", [])),
    ("Town", "LEWIS (ESSEX CO.)", ("17", "name_county", [])),
    ("Town", "LEWIS(LEWS)", (None, "ambiguous", ["16", "17"])),
    ("County", "LEWIS (ESSEX COUNTY)", (None, "unmatched", [])),
])
def test_a_filing_is_matched_only_within_its_type_and_county(kind, name, expected):
    table = nylaws.match([{"municipality_type": kind, "municipality_name": name}], GOVERNMENTS)
    assert (table[0]["census_id"], table[0]["match"], table[0]["candidates"]) == expected


def test_a_census_title_that_does_not_fit_its_type_stops_the_match():
    with pytest.raises(SourceChanged, match="which its title does not say"):
        nylaws.match([], GOVERNMENTS + [government("99", "TOWN OF BARRE", "ORLEANS", "municipal")])


def test_the_sample_matches_the_census_sample_s_new_york_governments():
    governments, _ = units_rows()
    table = nylaws.match(nylaws.rows(ny_snapshot()), governments)
    ids = {row["census_id"] for row in table if row["census_id"]}
    assert ids == {"109507", "170831", "170895"}, "CITY OF BATAVIA, TOWN OF BATAVIA and TOWN OF HEMPSTEAD"
    assert all(row["match"] == "unmatched" for row in table if row["census_id"] is None)


def filing(filed, posted, kind="Town", name="CHESTER (WARREN COUNTY)", number="1", filename=None):
    """A row as stats reads it, filed on a date and added at a UTC moment."""
    return {"asset_id": filename or f"{filed} {posted}", "municipality_type": kind, "municipality_name": name, "law_number": number, "law_year": None, "title": None, "county_law_type": None,
            "date_filed": datetime.date.fromisoformat(filed), "posted_at": datetime.datetime.fromisoformat(posted), "filename": filename or f"{filed}.pdf"}


def test_posting_counts_new_york_days_and_names_what_does_not_fit():
    governments = [dict(row, population=100) for row in GOVERNMENTS]
    table = nylaws.match([
        filing("2024-09-20", "2024-10-01T15:00:00+00:00"),
        filing("2025-05-02", "2024-10-17T15:00:00+00:00", kind="Village", name="CHESTER", number="2", filename="late.pdf"),
        filing("2026-09-04", "2026-09-09T02:30:00+00:00"),
        filing("2026-09-04", "2026-09-10T02:30:00+00:00"),
        filing("2026-08-01", "2026-09-14T02:30:00+00:00"),
        filing("2025-09-01", "2025-09-14T02:30:00+00:00"),
    ], governments)
    stats = nylaws.stats(table, governments)
    # Friday September 4 to 22:30 on Tuesday September 8 in New York is 2 weekdays, Labor Day among them, although the UTC date is the Wednesday; the 2025 filing was added exactly 365 days before the latest, so it is not in the window.
    assert stats["posting"] == {"moved": 2, "moved_from": "2024-10-01", "moved_to": "2024-10-17", "moved_filed_before": 1, "latest": "2026-09-13", "recent": 3, "within_two_weekdays": 1, "median_weekdays": 3, "p90_days": 43}
    assert stats["filed_after_posted"] == [["late.pdf", "Village", "CHESTER", "2", "2025-05-02", "2024-10-17"]]
    assert [place[0] for place in stats["without_filings"]] == sorted({row["census_id"] for row in governments if row["state"] == "NY" and row["government_type"] != "special_district"} - {"2", "3"})
    assert stats["without_filings"][0] == ["1", "TOWN OF CHESTER", "ORANGE", 100]


def test_weekdays_after_counts_the_days_after_the_first_through_the_last():
    friday = datetime.date(2026, 9, 25)
    assert [nylaws.weekdays_after(friday, friday + datetime.timedelta(days=n)) for n in range(-1, 11)] == [0, 0, 0, 0, 1, 2, 3, 4, 5, 5, 5, 6]


def test_rows_that_are_the_same_filing_as_another_are_counted_as_repeats_by_filing_year():
    governments = [dict(row, population=100) for row in GOVERNMENTS]
    table = nylaws.match([
        filing("2002-05-01", "2024-10-01T15:00:00+00:00", filename="a.pdf"),
        filing("2002-05-01", "2024-10-01T15:00:00+00:00", filename="b.pdf"),
        filing("2002-05-01", "2024-10-01T15:00:00+00:00", name="Chester  (Warren County)", filename="c.pdf"),
        filing("2002-05-01", "2024-10-01T15:00:00+00:00", number="2", filename="d.pdf"),
        filing("2002-05-01", "2024-10-01T15:00:00+00:00", kind="Village", filename="e.pdf"),
        filing("2002-05-02", "2024-10-01T15:00:00+00:00", filename="f.pdf"),
        filing("2003-05-01", "2024-10-01T15:00:00+00:00", number=None, filename="g.pdf"),
        filing("2003-05-01", "2024-10-01T15:00:00+00:00", number=None, filename="h.pdf"),
    ], governments)
    years = nylaws.stats(table, governments)["years"]
    assert {year: entry["repeats"] for year, entry in years.items()} == {"2002": 2, "2003": 0}, "the name is compared in capitals with its spaces collapsed, and a row without a law number repeats nothing"
    assert years["2002"] == {"filings": 6, "with_title": 0, "with_law_year": 0, "matched": 5, "repeats": 2}
