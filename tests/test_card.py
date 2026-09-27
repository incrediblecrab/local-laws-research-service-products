"""The card rendered from a fixture build's manifest: valid front matter, every column documented, no unfilled values, and each branch of the sentences that depend on the data."""

import copy
import json
import re

import yaml

from local_laws import locus, nfip, precision, tribes
from local_laws.build import manifest_text
from local_laws.card import NY_OUTSIDE, render
from local_laws.schema import TABLES
from local_laws.store import CARD

RECORDED = list(precision.RESULTS)


def front_matter(card):
    assert card.startswith("---\n")
    return yaml.safe_load(card.split("---\n")[1])


def test_the_published_card_is_the_render_of_the_published_manifest(published):
    store, manifest = published
    assert store.read_text(CARD) == render(json.loads(store.read_text("manifest.json"))) == render(json.loads(manifest_text(manifest)))


def test_front_matter_declares_each_config_and_the_license(published):
    meta = front_matter(render(published[1]))
    assert meta["license"] == "mit" and meta["size_categories"] == ["n<1K"]
    assert meta["configs"] == [
        {"config_name": "governments", "data_files": [{"split": "train", "path": "data/governments.parquet"}], "default": True},
        {"config_name": "locus_crosswalk", "data_files": [{"split": "train", "path": "data/locus_crosswalk.parquet"}]},
        {"config_name": "ny_local_laws", "data_files": [{"split": "train", "path": "data/ny_local_laws.parquet"}]},
        {"config_name": "ny_local_law_index", "data_files": [{"split": "train", "path": "data/ny_local_law_index.parquet"}]},
        {"config_name": "federally_recognized_tribes", "data_files": [{"split": "train", "path": "data/federally_recognized_tribes.parquet"}]},
        {"config_name": "nfip_communities", "data_files": [{"split": "train", "path": "data/nfip_communities.parquet"}]},
    ]


def test_the_stored_fema_files_are_described_only_when_the_manifest_lists_them(published):
    manifest = published[1]
    card = render(manifest)
    assert f"- `{nfip.SNAPSHOT}`: the two files the build read from FEMA, the report `nation.csv` and OpenFEMA's `NfipCommunityStatusBook.parquet`, stored uncompressed" in card
    assert "and commits the tables, the two FEMA files it read, `manifest.json` and this card in one commit." in card
    assert "and builds `nfip_communities` from them, so New York's filings still update while the FEMA table stays at the report as read on September 26, 2026." in card
    assert f"`{nfip.SNAPSHOT}` holds the report and OpenFEMA's file as the build read them, unchanged." in card
    earlier = copy.deepcopy(manifest)
    del earlier["files"][nfip.SNAPSHOT]
    card = render(earlier)
    assert nfip.SNAPSHOT not in card and "and commits the tables, `manifest.json` and this card in one commit." in card
    assert "a scheduled run that cannot refresh FEMA logs a warning with the HTTP status and headers, writes no commit, and leaves the FEMA table at the last successful report date in this manifest, September 26, 2026." in card


def test_every_column_is_documented_with_its_type(published):
    card = render(published[1])
    for spec in TABLES.values():
        for column in spec["schema"]:
            assert f"| `{column.name}` | {column.type} | {spec['docs'][column.name]} |" in card


def test_no_value_is_left_unfilled(published):
    card = render(published[1])
    assert not re.search(r"\b(None|nan|NaN)\b|\{[a-z_]+\}|\[\]", card)
    assert not re.search(r"\bn/a\b", card), "no share of a zero whole"


def test_the_card_states_the_fixture_s_numbers(published):
    card = render(published[1])
    assert "LOCUS has 25 jurisdictions, and 23 of them match one government here" in card
    assert "The 9 aliases" in card and "The only hand-made input to the rows is 9 name aliases" in card
    assert "It never names 5 of them that way: `ga/unified_government_of_georgetown-quitman_county_commission`, `ky/lexingtonfayetteco`, `ky/middlesboro`, `sd/bison`, `tn/metro_government_of_nashville_and_davidson_county`." in card
    assert "- 1 other LOCUS jurisdiction is `ambiguous` or `unmatched`: `oh/nowhere_village`." in card
    assert "- Dependent public school systems, 1 in the Census file, are left out" in card


def differs(manifest, names, revision=None):
    manifest = copy.deepcopy(manifest)
    manifest["stats"]["locus"]["text_differs"] = sorted(names)
    if revision:
        manifest["sources"]["locus"]["revision"] = revision
    return render(manifest)


def test_differing_matches_are_called_read_by_hand_only_when_they_were(published):
    manifest = published[1]
    assert manifest["stats"]["locus"]["text_differs"] == ["co/creede", "ma/barnstable_town"]
    card = render(manifest)
    assert "It differs for 2. Each of those was read by hand against LOCUS's text on September 25, 2026, and each is the government LOCUS means, named with another word." in card
    assert locus.REVIEW_FINDING not in card, "the finding describes the full reviewed set only"
    assert f"named with another word: {locus.REVIEW_FINDING}." in differs(manifest, locus.REVIEWED_DIFFERS)
    assert "It differs for 3, and 1 of those has not been read by hand: `xx/unread`." in differs(manifest, ["co/creede", "ma/barnstable_town", "xx/unread"])
    assert "and 2 of those have not been read by hand: `co/creede`, `ma/barnstable_town`." in differs(manifest, ["co/creede", "ma/barnstable_town"], revision="0" * 40), "a review at one LOCUS revision says nothing about another"
    assert "It differs for" not in differs(manifest, [])


def test_the_howard_gap_is_stated_only_while_ks_howard_is_ambiguous(published):
    manifest = copy.deepcopy(published[1])
    assert "Howard, Kansas" in render(manifest)
    manifest["stats"]["locus"]["ambiguous"] = []
    assert "Howard, Kansas" not in render(manifest)


def test_the_population_year_is_the_commonest_and_ties_go_to_the_later_year(published):
    manifest = copy.deepcopy(published[1])
    for kind in locus.GENERAL_PURPOSE:
        manifest["stats"]["types"][kind]["population_years"] = {}
    manifest["stats"]["types"]["county"]["population_years"] = {"2020": 2, "2021": 2}
    assert "for 2021 for 2 of the 4 (50.0%)" in render(manifest)


def new_york(manifest, posting=None, **stats):
    manifest = copy.deepcopy(manifest)
    manifest["stats"]["ny"]["posting"].update(posting or {})
    manifest["stats"]["ny"].update(stats)
    return render(manifest)


def test_the_new_york_section_states_the_fixture_s_numbers(published):
    manifest = published[1]
    assert manifest["stats"]["ny"]["posting"] == {"moved": 19, "moved_from": "2024-10-15", "moved_to": "2024-10-22", "moved_filed_before": 19, "latest": "2026-07-13", "recent": 4, "within_two_weekdays": 0, "median_weekdays": 3, "p90_days": 8}
    card = render(manifest)
    assert "1 of the filings is a county codification rather than a local law, and 3 carry a filing date before 1998." in card
    assert "2 of the filings are county codifications rather than local laws, and 1 carries a filing date before 1998." in new_york(manifest, codifications=2, years={"1997": manifest["stats"]["ny"]["years"]["1997"] | {"filings": 1}} | {year: entry for year, entry in manifest["stats"]["ny"]["years"].items() if int(year) >= 1998})
    assert "`posted_at` is when a filing was added to the Department's document library, which the search reads. 19 filings were added from October 15, 2024 to October 22, 2024, 19 of them filed before then; for those, `posted_at` is the day they came into the library and says nothing of when they were first published." in card
    assert "Of the 4 filings added in the 365 days to July 13, 2026, 0 (0.0%) were added within two weekdays after the day they were filed; at least half were added within 3 weekdays, and at least nine in ten within 8 days." in card
    assert f"- {NY_OUTSIDE}" in card
    assert "the API's host had no robots.txt (it answered HTTP 404)" in card
    assert "| Town | 12 | 7 | 58.3% |" in card and "| Village | 3 | 0 | 0.0% |" in card
    assert "Unmatched, with the number of filings: City NEW YORK (3), City POUGHKEEPSIE (2), City BUFFALO (1), County Saratoga (1), Town AMHERST  (CORRECTED COPY) (1), Town BRIGHTON (1), Town CHESTER (WARREN COUNTY) (1), Town East Hampton (1), Town LEWIS (LEWIS CO) (1), Village PAWLING (1), Village SOUTH NYACK (1), Village VILLAGE OF THE BRANCH (1)." in card
    assert "Ambiguous, with the number of filings: none." in card
    assert "Ambiguous, with the number of filings: Town BRIGHTON (135), Town DICKINSON (107)." in new_york(manifest, ambiguous=[["Town", "BRIGHTON", 135], ["Town", "DICKINSON", 107]])


def test_the_posting_measure_reads_for_one_day_no_recent_filings_and_no_move(published):
    manifest = published[1]
    assert "at least half were added within 1 weekday, and at least nine in ten within 1 day." in new_york(manifest, {"median_weekdays": 1, "p90_days": 1})
    quiet = new_york(manifest, {"recent": 0, "within_two_weekdays": 0, "median_weekdays": None, "p90_days": None})
    assert "No filing was added in the 365 days to July 13, 2026 with a filing date before it was added, so the table has no recent measure of how long that takes." in quiet and "Of the 0" not in quiet
    unmoved = new_york(manifest, {"moved": 0, "moved_from": None, "moved_to": None, "moved_filed_before": 0})
    assert "`posted_at` is when a filing was added to the Department's document library, which the search reads.\n" in unmoved and "filed before then" not in unmoved
    for card in (quiet, unmoved):
        assert not re.search(r"\b(None|nan|NaN)\b", card)


def test_filings_dated_after_they_were_added_are_named(published):
    manifest = published[1]
    assert manifest["stats"]["ny"]["filed_after_posted"] == [] and "dated after the day" not in render(manifest)
    late = ["090213438010d564.pdf", "Village", "Montgomery", "2", "2025-05-02", "2024-10-17"]
    assert "One filing is dated after the day it was added, so one of those dates is wrong; the table keeps both as the Department recorded them: Village Montgomery, local law 2, filed May 2, 2025 by its record and added October 17, 2024 (`090213438010d564.pdf`)." in new_york(manifest, filed_after_posted=[late])
    assert "2 filings are dated after the day they were added, so one date of each is wrong; the table keeps the dates as the Department recorded them: Village Montgomery, local law 2, filed May 2, 2025 by its record and added October 17, 2024 (`090213438010d564.pdf`); Town FLORENCE, local law (none), filed January 2, 2026 by its record and added January 1, 2026 (`x.pdf`)." in new_york(manifest, filed_after_posted=[late, ["x.pdf", "Town", "FLORENCE", "", "2026-01-02", "2026-01-01"]])


def test_governments_without_a_matched_filing_are_named(published):
    manifest = published[1]
    assert manifest["stats"]["ny"]["without_filings"] == [] and "Every government in the table has at least one matched filing." in render(manifest)
    red_house = ["208871", "TOWN OF RED HOUSE", "CATTARAUGUS", 30]
    assert "The one government in the table without a matched filing is TOWN OF RED HOUSE, in Cattaraugus County (`208871`, population 30)." in new_york(manifest, without_filings=[red_house])
    assert "The 2 governments in the table without a matched filing are TOWN OF RED HOUSE, in Cattaraugus County (`208871`, population 30); CITY OF NOWHERE, in no county (`1`)." in new_york(manifest, without_filings=[red_house, ["1", "CITY OF NOWHERE", None, None]])


def test_the_check_of_the_matches_states_its_recorded_answers(published):
    card = render(published[1])
    assert "To check the matches, 40 matched filings were drawn at random, leaving out five used first to try the queries, and looked up on September 26, 2026 in the search API's full-text index of the filed PDFs" in card
    assert "35 of the 40 were confirmed: their text has the matched government's Census name, such as VILLAGE OF AMITYVILLE, and their metadata does not. No filing was contradicted, that is, found to name a same-name government of another type and not the matched one." in card
    assert "Of the rest, for 3, the metadata has the name too, so the search cannot tell whether the text does; for 2, the text has neither the name nor that of a same-name government of another type." in card
    assert "was found in 0 of the 40 filings, and that of a same-name government of another type in 0 of the 16 filings that have one." in card
    assert "Of a second draw of 10 filings matched by name and county, all 10 were confirmed, and 3 of the 4 with a same-name government of another type have its Census name as well, as the County of Cortland's filing has CITY OF CORTLAND. Yet the matched name after a title that no government of that name has, such as COUNTY OF SCHAGHTICOKE for the Town of Schaghticoke, was found in 7 of the 50 filings checked, likely because the Department's [filing form](https://dos.ny.gov/system/files/documents/2025/04/0239-f_0.pdf) prints the four titles before \"of\" and the government's name. So a phrase naming a same-name government of another type does not by itself make a match wrong, and a confirmation shows that the text has the name more surely than that it has the title." in card
    assert "Every filing checked, the oldest filed May 7, 1998, has text the search reads: a term the check asked, such as \"hereby\" or \"enacted\", is in its text and not its metadata. A sample of 40 cannot rule out wrong matches among several percent of filings." in card
    assert "- The laws' text is not here, only a link to each filed PDF, which this pipeline does not open. The search reads text for every one of the 50 filings the check of the matches looked up, filed from May 7, 1998 to August 17, 2026, but that is a sample" in card


def answered(monkeypatch, manifest, outcome, change):
    """The card with the first recorded filing of that outcome given other answers."""
    results = [list(row) for row in RECORDED]
    row = next(row for row in results if row[0] == "main" and precision.outcome(row[5], row[6], row[9]) == outcome)
    change(row)
    monkeypatch.setattr(precision, "RESULTS", [tuple(row) for row in results])
    return render(manifest)


def test_the_check_s_sentences_follow_its_answers(monkeypatch, published):
    manifest = published[1]
    card = answered(monkeypatch, manifest, "confirmed", lambda row: row.__setitem__(6, (1, 1)))
    assert "34 of the 40 were confirmed" in card and "for 4, the metadata has the name too" in card
    card = answered(monkeypatch, manifest, "not_named", lambda row: row.__setitem__(9, tuple((name, county, 1) for name, county, _ in row[9])))
    assert "1 was contradicted, that is" in card and "for 1, the text has neither" in card
    for generic in ((0, None), (1, 1)):
        card = answered(monkeypatch, manifest, "not_named", lambda row: row.__setitem__(5, generic))
        assert "for 1, the search finds no text." in card and "49 of the 50 filings checked have text the search reads: a term the check asked" in card and "The search reads text for 49 of the 50 filings" in card
        assert "the oldest filed" not in card


def test_the_form_titles_sentence_follows_the_unnamed_answers(monkeypatch, published):
    manifest = published[1]
    unnamed = dict(precision.UNNAMED)
    schaghticoke = next(row[1] for row in RECORDED if row[4] == "TOWN OF SCHAGHTICOKE")
    monkeypatch.setattr(precision, "UNNAMED", dict(unnamed, **{schaghticoke: tuple((phrase, 0) for phrase, _ in unnamed[schaghticoke])}))
    assert "such as CITY OF BELLPORT for the Village of Bellport, was found in 6 of the 50 filings checked" in render(manifest)
    monkeypatch.setattr(precision, "UNNAMED", {filename: tuple((phrase, 0) for phrase, _ in asked) for filename, asked in unnamed.items()})
    card = render(manifest)
    assert "The matched name after a title that no government of that name has, such as COUNTY OF AMITYVILLE for the Village of Amityville, was found in none of the 50 filings checked." in card
    assert "more surely than" not in card


def test_the_index_section_states_the_fixture_s_numbers(published):
    manifest = published[1]
    assert manifest["sources"]["ny_local_law_index"]["state_records"] == 14
    card = render(manifest)
    assert "`ny_local_law_index` is that export, 14 rows, read from the release at the SHA-256 the build pins." in card and "whose header counts 14 records:" in card
    assert "Law years run from 1969 to 2002. 6 rows were filed before 1998, when the search begins; of the 5 filed from 1998 on, 2 (40.0%) have a row in `ny_local_laws` with the same type, name, law number and filing date. The index gives filing dates from April 16, 1900 to April 15, 2002, and 3 rows have none. 1 row has a filing date before the law's own year, so one of the two is wrong, and 0 a filing date after the day the record was entered; the table keeps the dates as recorded. Entry dates run from June 11, 1997 to December 5, 2018, and 3 rows have no title." in card
    assert "| 1960s | 2 | 2 |\n| 1970s | 3 | 1 |\n| 1990s | 3 | 3 |\n| 2000s | 3 | 1 |\n| (none) | 3 | 0 |\n" in card
    assert "7 of the 14 rows (50.0%) are matched." in card
    assert "| Town | 4 | 3 |\n| City | 3 | 3 |\n| Village | 3 | 0 |\n| (none) | 2 | 0 |\n| Lacona | 1 | 0 |\n| TOWN | 1 | 1 |\n" in card
    assert "| CITY OF | 1 | 1 | 100.0% |\n| TOWN OF | 2 | 2 | 100.0% |\n" in card
    assert "Ambiguous, with the number of rows: none." in card
    assert "Unmatched, with the number of rows: (none) (none) (1), (none) East Greenbush (1), Lacona Village (1), Town Charleston (1), Village Black River (1), Village Cornwall (1), Village South Nyack (1)." in card
    assert "For those, `ny_local_law_index` has the State's older index, 6 rows filed before 1998, without the laws' text." in card
    assert "with the State's older index of local laws, 14 rows, each matched where it can be" in card and "in the older index, with law years back to 1969;" in card
    assert "`ny_local_law_index`: 14 rows, checked against the 14 records of the State's data file in the release |" in card


def index_card(manifest, **stats):
    manifest = copy.deepcopy(manifest)
    manifest["stats"]["ny_index"].update(stats)
    return render(manifest)


def test_the_index_s_date_and_count_sentences_follow_its_counts(published):
    manifest = published[1]
    assert "a filing date before the law's own year" not in index_card(manifest, filed_before_law_year=0, filed_after_entry=0)
    assert "15 rows have a filing date before the law's own year, so one of the two is wrong, and 9 a filing date after the day the record was entered;" in index_card(manifest, filed_before_law_year=15, filed_after_entry=9)
    card = index_card(manifest, filed_before_search=1, in_search=1, undated=1, with_title=13)
    assert "1 row was filed before 1998, when the search begins; of the 5 filed from 1998 on, 1 (20.0%) has a row" in card and "and 1 row has none." in card and "and 1 row has no title." in card
    assert "Ambiguous, with the number of rows: Town Greenville (Orange C (64)." in index_card(manifest, ambiguous=[["Town", "Greenville (Orange C", 64]])


def repeats(manifest, counts):
    manifest = copy.deepcopy(manifest)
    for year, n in counts.items():
        manifest["stats"]["ny"]["years"][year]["repeats"] = n
    return render(manifest)


def test_repeated_filings_are_counted_with_the_years_that_hold_most_of_them(published):
    manifest = published[1]
    years = manifest["stats"]["ny"]["years"]
    card = render(manifest)
    assert "No two rows have the same type, name, law number and filing date." in card and "as another row" not in card
    filings = {year: years[year]["filings"] for year in ("2003", "2024", "2025", "2026")}
    card = repeats(manifest, {"2003": 1, "2025": 1, "2026": 1})
    assert f"the rows after the first: 3 in all, most in 2003 (1 of its {filings['2003']} rows) and 2025 (1 of its {filings['2025']} rows)." in card
    assert "- 3 rows of `ny_local_laws` have the same type, name, law number and filing date as another row, most of them filed in 2003 and 2025;" in card
    assert re.search(r"\n\| 2026 \| [\d,]+ \| [\d,]+ \| [\d,]+ \| [\d,]+ \| 1 \|\n", card), "the table's column"
    card = repeats(manifest, {"2003": 1, "2024": 1, "2025": 1, "2026": 1})
    assert f"4 in all, the largest shares in 2003 (1 of its {filings['2003']} rows) and 2024 (1 of its {filings['2024']} rows)." in card and "as another row, the largest shares of them filed in 2003 and 2024;" in card
    card = repeats(manifest, {"2003": 1, "2025": 2})
    assert "3 in all, all in 2025 (2 of its" in card and "as another row, all of them filed in 2025 and 2003;" in card
    card = repeats(manifest, {"2026": 1})
    assert "1 in all, all in 2026 (1 of its" in card and "- 1 row of `ny_local_laws` has the same type, name, law number and filing date as another row, filed in 2026;" in card


def test_the_tribes_section_states_the_fixture_s_numbers(published):
    card = render(published[1])
    assert "`federally_recognized_tribes` is the list in its notice of January 30, 2026, [91 FR 4102](https://www.federalregister.gov/documents/2026/01/30/2026-01899/" in card
    assert "one row per entry, 19 in all, 8 in its list for the contiguous 48 states and 11 in its list for Alaska, in the notice's order." in card
    assert "The notice's summary says it publishes \"the current list of 17 Tribal entities\", 2 fewer than the 19 entries its lists hold, and the notice it updates stated 16 for 18 entries. Neither says why. Some entries send the reader to another with \"See\": Arctic Village and Village of Venetie to Native Village of Venetie Tribal Government; Aleut Community of St. Paul Island and St. George Island to Pribilof Islands Aleut Communities of St. Paul & St. George Islands. The stated count is the entries less the 2 that others send the reader to, but the notice does not say that is how the Bureau counts, so every entry is a row." in card
    assert "of December 11, 2024 ([89 FR 99899](https://www.federalregister.gov/documents/2024/12/11/2024-29005/" in card and "which had 18 entries: each of them must be continued by exactly one row," in card
    assert "14 entries are the same, 4 of them only when spaces and capitals are ignored, 1 of those in the name before any parenthesis; 4 changed, 3 of them in the name before any parenthesis; and 1 is new: Lumbee Tribe of North Carolina. `previous_entry` holds each row's earlier entry. " + tribes.NOTICE_SAYS in card
    assert "\n\nNames that differ from the earlier notice's only in spaces or capitals, kept as each notice types them: Wrangell Cooperative Association, which the earlier notice typed Wrangell Coopera tive Association.\n\n" in card
    assert "Changed since the earlier notice: Aleut Community of St. Paul Island, Kiowa Tribe, Match-E-Be-Nash-She-Wish Band of Pottawatomi, Native Village of Chenega." in card
    assert "Beside them, `federally_recognized_tribes` lists the 19 entries of the Bureau of Indian Affairs' list of federally recognized Tribes," in card
    assert "- `data/federally_recognized_tribes.parquet`: one row per entry of the Bureau of Indian Affairs' list of federally recognized Tribes, 19 rows, sorted by `list_row`." in card
    assert "- `federally_recognized_tribes` is the Bureau's list as its notice of January 30, 2026 gives it, the latest the Federal Register's API found on September 26, 2026: a Tribe recognized, or an entry corrected, since then is not reflected." in card
    assert "| SHA-256 `7299b636401302136bc58d8e5fb3f2c494ca1aa702fa1e16240271f94d96ea19` of its XML | `federally_recognized_tribes`: 19 rows |" in card
    assert "| SHA-256 `fc9ee378384cc4834bbba42c0a888839e47ca127e9855616fca5fb4b40c82da2` of its XML | Checking `federally_recognized_tribes`: its 18 entries, each continued by one row |" in card
    assert "each signed by its Assistant Secretary—Indian Affairs. They are works of the United States Government, and \"Copyright protection under this title is not available for any work of the United States Government\" ([17 U.S.C. § 105](https://www.copyright.gov/title17/92chap1.html#105)). Cite the list as Bureau of Indian Affairs, \"Indian Entities Recognized by and Eligible To Receive Services From the United States Bureau of Indian Affairs\", 91 FR 4102 (January 30, 2026)." in card


def tribes_card(manifest, source=None, **stats):
    manifest = copy.deepcopy(manifest)
    manifest["stats"]["tribes"].update(stats)
    manifest["sources"]["federally_recognized_tribes"].update(source or {})
    return render(manifest)


def test_the_stated_count_sentences_follow_the_counts(published):
    manifest = published[1]
    card = tribes_card(manifest, {"stated": 19})
    assert "\"the current list of 19 Tribal entities\", as many as its lists hold." in card and "Neither says why" not in card and "send the reader" not in card
    card = tribes_card(manifest, {"stated": 20})
    assert "\"the current list of 20 Tribal entities\", 1 more than the 19 entries its lists hold," in card and "Some entries send the reader to another" in card and "The stated count is the entries less" not in card
    card = tribes_card(manifest, referred={})
    assert "2 fewer than the 19 entries its lists hold, and the notice it updates stated 16 for 18 entries. Neither says why.\n" in card
    card = tribes_card(manifest, referred={"Native Village of Venetie Tribal Government": ["Arctic Village", "Village of Venetie"]})
    assert "Some entries send the reader to another with \"See\": Arctic Village and Village of Venetie to Native Village of Venetie Tribal Government.\n" in card


def test_the_comparison_sentence_reads_for_no_new_entry_and_no_new_name(published):
    card = tribes_card(published[1], added=[], renamed=0, respaced=0, respaced_names=[])
    assert "14 entries are the same; 4 changed, none of them in the name before any parenthesis; and none is new. `previous_entry`" in card and "only in spaces or capitals" not in card
    card = tribes_card(published[1], added=["Lumbee Tribe of North Carolina", "Tribe X"])
    assert "; and 2 are new: Lumbee Tribe of North Carolina, Tribe X." in card
    card = tribes_card(published[1], respaced_names=[["A B", "AB"], ["C", "c"]])
    assert "4 of them only when spaces and capitals are ignored, 2 of those in the name before any parenthesis; 4 changed" in card
    assert "kept as each notice types them: A B, which the earlier notice typed AB; C, which the earlier notice typed c.\n" in card
    card = tribes_card(published[1], respaced=2, respaced_names=[])
    assert "14 entries are the same, 2 of them only when spaces and capitals are ignored, none of those in the name before any parenthesis; 4 changed" in card and "only in spaces or capitals, kept" not in card


def test_what_the_notice_says_is_quoted_only_for_the_notice_it_was_read_from(published):
    card = tribes_card(published[1], {"document_number": "2027-00001"})
    assert tribes.NOTICE_SAYS not in card and "Lumbee Tribe of North Carolina. `previous_entry` holds each row's earlier entry.\n" in card
    assert "- `federally_recognized_tribes` is the Bureau's list as its notice of January 30, 2026 gives it: a Tribe recognized" in card and "the latest the Federal Register's API found" not in card


def test_the_flood_section_states_the_fixture_s_numbers(published):
    card = render(published[1])
    assert f"FEMA's page for its [Community Status Book](https://www.fema.gov/flood-insurance/work-with-nfip/community-status-book) says: \"{nfip.PROGRAM_SAYS}\" `nfip_communities` is the book's national report, [nation.csv](https://www.fema.gov/cis/nation.csv), as fema.gov served it on September 26, 2026, 08:18 UTC: one row per community, 25 in all, 20 participating in the program and 5 not, in the report's order. Of those participating, 18 are in its Regular Program and 1 in its Emergency Program; the report gives no program for 1. The report marks 3 communities as tribal, 1 of them participating." in card
    assert "with the notes the report prints beneath 10 communities. The table records which communities have joined and when, not the regulations they adopted" in card
    assert "read from `https://www.fema.gov/api/open/v1/NfipCommunityStatusBook.parquet` on September 26, 2026, 08:23 UTC: every community in the report must be in it once, under the same name and state and with the same participation, or the build stops. The API holds 28 communities, 3 more than the report lists, 1 of them participating and 2 not; they are not rows. The report's other values, its counties, tribal marks, dates, codes and classes, agree with the API's for every community except `crs_discount` for 1 community (350045, null here and 5 in the API) and `initial_firm_date` for 1 community (025009, 1969-06-25 here and 2069-06-25 in the API)." in card
    assert f"The Community Rating System, the page says, is \"{nfip.CRS_SAYS}\". 5 communities have a class in it" in card
    assert "| Class | Communities | Discount |\n|---:|---:|---:|\n| 1 | 1 | 45% |\n| 5 | 1 | 25% |\n| 7 | 2 | 15% |\n| 10 | 1 | none |\n" in card, "classes in number order, 10 last"
    assert "6 dates are later than the day the report was read: 3 in `current_map_date`, 1 in `crs_effective_date`, 1 in `initial_firm_date`, 1 in `sanction_date`. The report marks 1 of the current map dates as after the date of the report (`>`); the rest it gives without comment. 1 is more than five years ahead: WILLIAMS COUNTY* (380146), whose `current_map_date` reads as January 2, 2050. The report writes years with two digits, which the table reads as 1968 to 2067." in card
    assert "and `nfip_communities` the 25 communities in FEMA's Community Status Book, 20 of which participate in the National Flood Insurance Program" in card
    assert "- `data/nfip_communities.parquet`: one row per community in FEMA's Community Status Book, 25 rows, sorted by `report_row`." in card
    assert "- `nfip_communities` is FEMA's report as fema.gov served it on September 26, 2026; FEMA regenerates it, so a community's standing may have changed since." in card and "The 3 communities that OpenFEMA's copy holds and the report does not list are not rows." in card
    assert "| read on September 26, 2026, 08:18 UTC; SHA-256 `eccd1a8778d861e28b2d80b4e984c99ab8bfb1d12cd0609e8d57427b2bd37029` | `nfip_communities`: 25 rows |" in card
    assert "| read on September 26, 2026, 08:23 UTC; SHA-256 `e09b393fe7fdf364294b9305b2c5e95974188a649cd123f59f3c28579fde9dbc` | Checking `nfip_communities`: its 28 records, every community in the report among them |" in card
    assert f"FEMA's [website information](https://www.fema.gov/about/website-information) says: \"{nfip.REUSE_SAYS}\"" in card and f"OpenFEMA's [terms](https://www.fema.gov/about/openfema/terms-conditions) ask its users to state: \"{nfip.OPENFEMA_STATEMENT}\"" in card


def nfip_card(manifest, source=None, api=None, **stats):
    manifest = copy.deepcopy(manifest)
    manifest["stats"]["nfip"].update(stats)
    manifest["sources"]["nfip_communities"].update(source or {})
    manifest["sources"]["nfip_communities"]["api"].update(api or {})
    return render(manifest)


def test_the_openfema_sentence_follows_what_differed(published):
    card = nfip_card(published[1], api={"differ": {}})
    assert "they are not rows. The report's other values, its counties, tribal marks, dates, codes and classes, agree with the API's for every community.\n" in card
    cases = [[f"0100{n:02}", n, None] for n in range(7)]
    card = nfip_card(published[1], api={"differ": {"crs_class": cases}})
    assert "agree with the API's for every community except `crs_class` for 7 communities (010000, 0 here and null in the API; 010001, 1 here and null in the API; 010002, 2 here and null in the API; 010003, 3 here and null in the API; 010004, 4 here and null in the API; ...)." in card


def test_the_later_dates_paragraph_follows_the_dates(published):
    manifest = published[1]
    card = nfip_card(manifest, {"after_retrieval": []})
    assert "later than the day the report was read" not in card and "| 10 | 1 | none |\n\n## " in card
    near = [each for each in manifest["sources"]["nfip_communities"]["after_retrieval"] if each[0] != "380146"]
    card = nfip_card(manifest, {"after_retrieval": near})
    assert "5 dates are later than the day the report was read: 2 in `current_map_date`" in card and "the rest it gives without comment.\n" in card and "five years ahead" not in card


def test_communities_without_a_program_are_mentioned_only_when_there_are_some(published):
    manifest = published[1]
    card = nfip_card(manifest, programs={"Regular": 19, "Emergency": 1, "none": 0})
    assert "Of those participating, 19 are in its Regular Program and 1 in its Emergency Program. The report marks" in card
