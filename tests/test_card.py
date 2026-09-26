"""The card rendered from a fixture build's manifest: valid front matter, every column documented, no unfilled values, and each branch of the sentences that depend on the data."""

import copy
import json
import re

import yaml

from local_laws import locus, precision
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
    ]


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
