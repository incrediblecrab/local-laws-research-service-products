"""The Bureau of Indian Affairs' notices: each read into its stated count and its two lists, the latest checked against the one it says it updates, and the counts the card shows."""

import re
from xml.etree import ElementTree

import pytest

from conftest import TRIBES_NOTICE, TRIBES_PREVIOUS, FakeFetcher, sha256
from local_laws import tribes
from local_laws.census import SourceChanged

NOTICE, PREVIOUS = tribes.read(TRIBES_NOTICE), tribes.read(TRIBES_PREVIOUS)


def edited(data, old, new):
    text = data.decode("utf-8")
    assert text.count(old) == 1, old
    return text.replace(old, new).encode("utf-8")


def entry(rows, name):
    return next(row for row in rows if row["name"] == name)


def test_the_samples_read_as_their_counts_and_lists_in_order():
    assert (NOTICE["stated"], NOTICE["updates"], len(NOTICE["entries"])) == (17, "89 FR 99899", 19)
    assert (PREVIOUS["stated"], PREVIOUS["updates"], len(PREVIOUS["entries"])) == (16, "88 FR 944", 18)
    assert [listed for listed, _ in NOTICE["entries"]] == ["contiguous_48"] * 8 + ["alaska"] * 11
    assert NOTICE["entries"][0] == ("contiguous_48", "Absentee-Shawnee Tribe of Indians of Oklahoma")
    assert NOTICE["entries"][-1] == ("alaska", "Yupiit of Andreafski")


def test_an_entry_s_text_is_read_whole_across_page_breaks_emphasis_and_line_breaks():
    assert b"<PRTPAGE" in TRIBES_NOTICE and b"<E " in TRIBES_NOTICE
    entries = dict((name, text) for name, text in ((tribes.name(value), value) for _, value in NOTICE["entries"]))
    assert entries["Hoopa Valley Tribe, California"] == "Hoopa Valley Tribe, California"
    assert entries["Native Village of Atqasuk"] == "Native Village of Atqasuk"
    assert entries["Lumbee Tribe of North Carolina"] == "Lumbee Tribe of North Carolina (See Supplementary Information supra, noting conditions on the Tribe's eligibility for Federal services)"
    assert not any("  " in value or "\n" in value for _, value in NOTICE["entries"])


def test_each_row_continues_the_earlier_entry_the_rules_give():
    rows = tribes.rows(NOTICE, PREVIOUS)
    assert [row["list_row"] for row in rows] == list(range(1, 20))
    assert entry(rows, "Cabazon Band of Cahuilla Indians")["previous_entry"] == "Cabazon Band of Cahuilla Indians ( previously listed as Cabazon Band of Mission Indians, California)"
    assert entry(rows, "Wrangell Cooperative Association")["previous_entry"] == "Wrangell Coopera tive Association"
    assert entry(rows, "Kiowa Tribe")["previous_entry"] == "Kiowa Indian Tribe of Oklahoma"
    assert entry(rows, "Match-E-Be-Nash-She-Wish Band of Pottawatomi")["previous_entry"] == "Match-e-be-nash-she-wish Band of Pottawatomi Indians of Michigan"
    assert entry(rows, "Aleut Community of St. Paul Island")["previous_entry"] == "Saint Paul Island ( See Pribilof Islands Aleut Communities of St. Paul & St. George Islands)"
    assert entry(rows, "Native Village of Chenega")["previous_entry"] == "Native Village of Chenega (aka Chanega)"
    assert entry(rows, "Lumbee Tribe of North Carolina")["previous_entry"] is None
    assert entry(rows, "Kiowa Tribe")["entry"] == "Kiowa Tribe (previously listed as Kiowa Indian Tribe of Oklahoma)"


def test_the_counts_the_card_shows():
    assert tribes.stats(tribes.rows(NOTICE, PREVIOUS)) == {
        "rows": 19,
        "lists": {"contiguous_48": 8, "alaska": 11},
        "unchanged": 14,
        "respaced": 4,
        "respaced_names": [["Wrangell Cooperative Association", "Wrangell Coopera tive Association"]],
        "changed": ["Aleut Community of St. Paul Island", "Kiowa Tribe", "Match-E-Be-Nash-She-Wish Band of Pottawatomi", "Native Village of Chenega"],
        "renamed": 3,
        "added": ["Lumbee Tribe of North Carolina"],
        "referred": {
            "Native Village of Venetie Tribal Government": ["Arctic Village", "Village of Venetie"],
            "Pribilof Islands Aleut Communities of St. Paul & St. George Islands": ["Aleut Community of St. Paul Island", "St. George Island"],
        },
    }


def test_names_and_former_names_are_read_to_their_own_parenthesis():
    assert tribes.name("Kiowa Tribe (previously listed as Kiowa Indian Tribe of Oklahoma)") == "Kiowa Tribe"
    assert tribes.name("Hoopa Valley Tribe, California") == "Hoopa Valley Tribe, California"
    assert tribes.previously_listed("X ( previously listed as Y (Z)) (previously listed as W)") == ["Y (Z)", "W"]
    assert tribes.previously_listed("Native Village of Chenega (aka Chanega)") == []


@pytest.mark.parametrize("data, stop", [
    (b"<html>unblock</html", "the notice is not XML"),
    (edited(TRIBES_NOTICE, "the current list of 17 Tribal entities", "the current list of Tribal entities"), "the notice's summary does not say how many Tribal entities it lists"),
    (edited(TRIBES_NOTICE, ">Native Entities Within the State of Alaska", ">Entities Within the State of Alaska"), "the notice's lists are ['contiguous_48'], not ['contiguous_48', 'alaska'] in that order"),
    (edited(TRIBES_NOTICE, "<FP SOURCE=\"FP-1\">Absentee-Shawnee Tribe of Indians of Oklahoma</FP>", "<FP SOURCE=\"FP-1\"> </FP>"), "the notice's lists have 1 blank entries"),
])
def test_a_notice_that_does_not_read_as_one_stops_the_build(data, stop):
    with pytest.raises(SourceChanged, match=re.escape(stop)):
        tribes.read(data)


def test_a_notice_whose_lists_are_out_of_order_stops_the_build():
    root = ElementTree.fromstring(TRIBES_NOTICE)
    headings = [element for element in root.iter("HD") if any(tribes.text(element).startswith(start) for start in tribes.LISTS.values())]
    first, second = (tribes.text(element) for element in headings)
    headings[0].text, headings[1].text = second, first
    with pytest.raises(SourceChanged, match=re.escape("the notice's lists are ['alaska', 'contiguous_48'], not ['contiguous_48', 'alaska'] in that order")):
        tribes.read(ElementTree.tostring(root))


def with_entries(notice, entries, stated=None):
    return {**notice, "entries": entries, "stated": notice["stated"] if stated is None else stated}


@pytest.mark.parametrize("notice, previous, stop", [
    (NOTICE, with_entries(PREVIOUS, PREVIOUS["entries"] + [("alaska", "Native Village of Nowhere")], 17), "the earlier notice's entries ['Native Village of Nowhere'] are continued by no row"),
    (NOTICE, with_entries(PREVIOUS, PREVIOUS["entries"] + [("alaska", "Agdaagux Tribe of King Cove")], 17), "could continue any of ['Agdaagux Tribe of King Cove', 'Agdaagux Tribe of King Cove']"),
    (with_entries(NOTICE, NOTICE["entries"] + [("alaska", "Saint Paul Island ( See Pribilof Islands Aleut Communities of St. Paul & St. George Islands)")], 18), PREVIOUS, "and ['Saint Paul Island ( See Pribilof Islands Aleut Communities of St. Paul & St. George Islands)'] by more than one"),
    (with_entries(NOTICE, NOTICE["entries"], 18), PREVIOUS, '1 rows continue no earlier entry (["Lumbee Tribe of North Carolina (See Supplementary Information supra, noting conditions on the Tribe\'s eligibility for Federal services)"]), but the stated count went from 16 to 18'),
    (NOTICE, with_entries(PREVIOUS, [value for value in PREVIOUS["entries"] if value[1] != "Kiowa Indian Tribe of Oklahoma"]), "2 rows continue no earlier entry"),
])
def test_lists_that_do_not_reconcile_stop_the_build(notice, previous, stop):
    with pytest.raises(SourceChanged, match=re.escape(stop)):
        tribes.rows(notice, previous)


def test_the_rules_are_tried_in_order_so_the_same_entry_wins_over_a_looser_match():
    entries = [("alaska", "Native Village of Chenega"), ("alaska", "Native Village of Chenega (aka Chanega)")]
    notice = {"stated": 2, "updates": None, "entries": entries}
    assert [row["previous_entry"] for row in tribes.rows(notice, notice)] == [entry for _, entry in entries]


def test_the_same_entry_in_both_lists_continues_the_one_in_its_own_list():
    entries = [("contiguous_48", "Village X"), ("alaska", "Village X")]
    notice = {"stated": 2, "updates": None, "entries": entries}
    assert [row["previous_entry"] for row in tribes.rows(notice, notice)] == ["Village X", "Village X"]


def test_an_earlier_entry_is_continued_only_within_its_own_list():
    moved = [("contiguous_48" if value == "Native Village of Atqasuk" else listed, value) for listed, value in PREVIOUS["entries"]]
    with pytest.raises(SourceChanged, match=re.escape("the earlier notice's entries ['Native Village of Atqasuk'] are continued by no row")):
        tribes.rows(NOTICE, with_entries(PREVIOUS, moved))


def test_the_build_reads_both_pinned_notices_and_stops_unless_the_notice_updates_the_earlier_one(pins, monkeypatch):
    notice, previous, rows = tribes.load(FakeFetcher())
    assert (notice, previous, rows) == (NOTICE, PREVIOUS, tribes.rows(NOTICE, PREVIOUS))
    other = edited(TRIBES_NOTICE, "(89 FR 99899)", "(88 FR 944)")
    monkeypatch.setitem(tribes.NOTICE, "sha256", sha256(other))
    with pytest.raises(SourceChanged, match=re.escape("the notice says it updates the notice at 88 FR 944, not 89 FR 99899")):
        tribes.load(FakeFetcher({tribes.NOTICE["url"]: other}))
    with pytest.raises(SourceChanged, match="not the pinned"):
        tribes.load(FakeFetcher({tribes.NOTICE["url"]: TRIBES_NOTICE + b" "}))


def test_what_the_card_quotes_from_the_notice_is_in_the_notice():
    text = tribes.text(ElementTree.fromstring(TRIBES_NOTICE))
    quotes = re.findall(r'"([^"]+)"', tribes.NOTICE_SAYS)
    assert len(quotes) == 3 and all(quote in text for quote in quotes), [quote for quote in quotes if quote not in text]
    assert "The list is updated from the notice published on December 11, 2024 (89 FR 99899)." in text


def test_latest_reads_the_two_latest_matching_federal_register_notices():
    class Fetcher:
        def get(self, url):
            assert tribes.LATEST_API in url
            return b'{"results":[{"document_number":"2026-17057","publication_date":"2026-08-21","title":"Caddo Nation Liquor Control Code","html_url":"x"},{"document_number":"2026-01899","publication_date":"2026-01-30","title":"Indian Entities Recognized by and Eligible To Receive Services From the United States Bureau of Indian Affairs","html_url":"a"},{"document_number":"2024-29005","publication_date":"2024-12-11","title":"Indian Entities Recognized by and Eligible To Receive Services From the United States Bureau of Indian Affairs","html_url":"b"}]} '

    assert tribes.latest(Fetcher()) == [
        {"document_number": "2026-01899", "published": "2026-01-30", "title": tribes.TITLE, "html_url": "a"},
        {"document_number": "2024-29005", "published": "2024-12-11", "title": tribes.TITLE, "html_url": "b"},
    ]


def test_latest_stops_when_the_api_does_not_return_two_matching_notices():
    class Fetcher:
        def get(self, url):
            return b'{"results":[{"document_number":"2026-01899","publication_date":"2026-01-30","title":"Indian Entities Recognized by and Eligible To Receive Services From the United States Bureau of Indian Affairs"}]}'

    with pytest.raises(SourceChanged, match="returned 1 matching recognized-Tribes notices"):
        tribes.latest(Fetcher())
