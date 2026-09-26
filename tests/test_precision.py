"""The check of New York's matches against the filings' text: the outcome each set of answers gives, and answers recorded as the draws the module describes."""

from collections import Counter

import pytest

from local_laws import nylaws, precision


def title(census_name):
    return next(title for title in nylaws.GOVERNMENT_TYPES if census_name.startswith(title + " "))


def census_type(census_name):
    return nylaws.GOVERNMENT_TYPES[title(census_name)]


@pytest.mark.parametrize("generic, name, other, expected", [
    ((1, 0), (1, 0), (), "confirmed"),
    ((0, None), (1, 0), (), "confirmed"),
    ((1, 0), (1, 1), (("TOWN OF X", "Y", 1),), "in_metadata"),
    ((1, 0), (0, None), (("TOWN OF X", "Y", 0), ("TOWN OF X", "Z", 1)), "contradicted"),
    ((1, 0), (0, None), (("TOWN OF X", "Y", 0),), "not_named"),
    ((1, 0), (0, None), (), "not_named"),
    ((1, 1), (0, None), (), "no_text"),
    ((0, None), (0, None), (), "no_text"),
])
def test_each_set_of_answers_gives_its_outcome(generic, name, other, expected):
    assert precision.outcome(generic, name, other) == expected
    assert expected in precision.OUTCOMES


def test_the_answers_are_the_draws_the_module_describes():
    assert Counter(row[0] for row in precision.RESULTS) == precision.SIZES
    filenames = [row[1] for row in precision.RESULTS]
    assert len(set(filenames)) == len(filenames) and not set(filenames) & set(precision.CALIBRATION)
    for part, filename, filed, census_id, census_name, generic, name, county, decoy, other in precision.RESULTS:
        kind = census_type(census_name)
        assert (county is None) == (kind == "county")
        for text, metadata in (generic, name) + ((county,) if county else ()):
            assert text in (0, 1) and (metadata is None) == (text == 0) and metadata in (None, 0, 1)
        assert census_type(decoy[0]) == kind and decoy[0] != census_name and decoy[1] in (0, 1)
        for other_name, _, found in other:
            assert census_type(other_name) not in (kind, "county") and other_name.split(" OF ", 1)[1] == census_name.split(" OF ", 1)[1] and found in (0, 1)


def test_the_summary_counts_each_part():
    parts = precision.summary()
    for part, entry in parts.items():
        rows = [row for row in precision.RESULTS if row[0] == part]
        assert entry["filings"] == len(rows) == sum(entry["outcomes"].values())
        assert entry["decoys_found"] == sum(row[8][1] for row in rows)
        assert entry["first_filed"] == min(row[2] for row in rows) and entry["last_filed"] == max(row[2] for row in rows)


@pytest.mark.parametrize("generic, name, county, expected", [
    ((1, 1), (0, None), (0, None), 0),
    ((1, 1), (1, 1), (1, 1), 0),
    ((1, 1), (1, 1), (1, 0), 1),
    ((0, None), (1, 0), None, 1),
    ((1, 0), (0, None), None, 1),
])
def test_text_is_counted_only_for_a_term_found_in_it_and_not_the_metadata(monkeypatch, generic, name, county, expected):
    monkeypatch.setattr(precision, "RESULTS", [("main", "a.pdf", "2020-01-01", "1", "TOWN OF X", generic, name, county, ("TOWN OF Z", 0), ())])
    assert precision.summary()["main"]["with_text"] == expected


def test_the_unnamed_phrases_are_the_matched_name_after_the_other_titles():
    assert list(precision.UNNAMED) == [row[1] for row in precision.RESULTS]
    asked = set()
    for part, filename, filed, census_id, census_name, *_ in precision.RESULTS:
        stem = census_name[len(title(census_name)) + 1:]
        for phrase, found in precision.UNNAMED[filename]:
            assert title(phrase) != title(census_name) and phrase == f"{title(phrase)} {stem}" and found in (0, 1)
            asked.add(phrase)
    assert set(precision.REAL) <= asked


def test_a_phrase_naming_a_real_government_is_not_counted(monkeypatch):
    monkeypatch.setattr(precision, "RESULTS", [("main", "a.pdf", "2020-01-01", "1", "CITY OF NEW YORK", (1, 0), (1, 0), None, ("CITY OF ROME", 0), ())])
    monkeypatch.setattr(precision, "UNNAMED", {"a.pdf": (("COUNTY OF NEW YORK", 1), ("TOWN OF NEW YORK", 0))})
    entry = precision.summary()["main"]
    assert (entry["unnamed_asked"], entry["unnamed_found"]) == (1, 0)
    monkeypatch.setattr(precision, "UNNAMED", {"a.pdf": (("COUNTY OF NEW YORK", 1),)})
    entry = precision.summary()["main"]
    assert (entry["unnamed_asked"], entry["unnamed_found"]) == (0, 0)
