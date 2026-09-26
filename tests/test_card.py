"""The card rendered from a fixture build's manifest: valid front matter, every column documented, no unfilled values, and each branch of the sentences that depend on the data."""

import copy
import json
import re

import yaml

from local_laws import locus
from local_laws.build import manifest_text
from local_laws.card import render
from local_laws.schema import TABLES
from local_laws.store import CARD


def front_matter(card):
    assert card.startswith("---\n")
    return yaml.safe_load(card.split("---\n")[1])


def test_the_published_card_is_the_render_of_the_published_manifest(published):
    store, manifest = published
    assert store.read_text(CARD) == render(json.loads(store.read_text("manifest.json"))) == render(json.loads(manifest_text(manifest)))


def test_front_matter_declares_both_configs_and_the_license(published):
    meta = front_matter(render(published[1]))
    assert meta["license"] == "mit" and meta["size_categories"] == ["n<1K"]
    assert meta["configs"] == [
        {"config_name": "governments", "data_files": [{"split": "train", "path": "data/governments.parquet"}], "default": True},
        {"config_name": "locus_crosswalk", "data_files": [{"split": "train", "path": "data/locus_crosswalk.parquet"}]},
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
