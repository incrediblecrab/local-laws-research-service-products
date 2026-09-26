"""verify against a fixture build: clean, it finds nothing; with each defect planted, it names that defect."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from conftest import ORG02, FakeFetcher
from local_laws import census, locus
from local_laws.build import SORT_KEYS, manifest_text, summarize
from local_laws.card import render
from local_laws.census import SourceChanged
from local_laws.schema import TABLES
from local_laws.store import CARD, MANIFEST, sha256_file, write_parquet
from local_laws.verify import verify

GOVERNMENTS, CROSSWALK = TABLES["governments"]["file"], TABLES["locus_crosswalk"]["file"]


def check(store, stated=None, fetcher=True):
    """verify's problems, with LOCUS's card stating the manifest's row count unless told otherwise."""
    def stated_rows():
        return json.loads(store.read_text(MANIFEST))["sources"]["locus"]["rows"] if stated is None else stated

    return verify(store, fetcher=FakeFetcher() if fetcher else None, stated_rows=stated_rows)["problems"]


def edit_table(store, name, edit):
    spec = TABLES[name]
    rows = store.read_table(spec["file"]).to_pylist()
    edit(rows)
    pq.write_table(pa.Table.from_pylist(rows, schema=spec["schema"]), store.root / spec["file"])


def edit_manifest(store, edit):
    manifest = json.loads(store.read_text(MANIFEST))
    edit(manifest)
    (store.root / MANIFEST).write_text(manifest_text(manifest))


def reseal(store):
    """Make the manifest and card agree with the tables as they now are, as a build that was consistently wrong would."""
    tables = {name: store.read_table(spec["file"]).to_pylist() for name, spec in TABLES.items()}

    def edit(manifest):
        for name, spec in TABLES.items():
            manifest["files"][spec["file"]] = write_parquet(tables[name], store.root / spec["file"], spec["schema"], SORT_KEYS[name])
        manifest["sources"]["census_governments"]["rows"] = len(tables["governments"])
        try:
            manifest["stats"] = json.loads(json.dumps(summarize(tables["governments"], tables["locus_crosswalk"])))
        except KeyError:
            pass  # a government_type summarize has no column for; verify names it

    edit_manifest(store, edit)
    (store.root / CARD).write_text(render(json.loads(store.read_text(MANIFEST))))


def row(rows, **match):
    return next(r for r in rows if all(r[key] == value for key, value in match.items()))


def test_a_clean_build_has_no_problems(published):
    store, manifest = published
    report = verify(store, fetcher=FakeFetcher(), stated_rows=lambda: manifest["sources"]["locus"]["rows"])
    assert report == {"rows": {"governments": 50, "locus_crosswalk": 25}, "org02_counts_compared": 312, "locus_stated_rows": manifest["sources"]["locus"]["rows"], "problems": []}


@pytest.mark.parametrize("edit, expected", [
    (lambda rows: rows.append(dict(rows[0])), "governments: duplicate census_id: 1 (100001)"),
    (lambda rows: rows[0].update(census_id="10001"), "governments: census_id null or not 6 digits: 1 ('10001')"),
    (lambda rows: rows[0].update(government_type="tribal"), "governments: government_type values ['tribal'] are not the Census's five types"),
    (lambda rows: rows[0].update(state="AK"), "governments: state does not match state_fips: 1 (100001)"),
    (lambda rows: row(rows, census_id="100117").update(fips_place="62328"), "governments: fips_place set for a district or missing for a general-purpose government: 1 (100117)"),
])
def test_each_planted_governments_defect_is_named_even_in_a_consistent_manifest(published, edit, expected):
    store, _ = published
    edit_table(store, "governments", edit)
    reseal(store)
    assert expected in check(store)


def test_a_government_dropped_consistently_is_caught_only_by_cg2200org02(published):
    store, _ = published
    edit_table(store, "governments", lambda rows: rows.remove(row(rows, census_id="162028")))
    reseal(store)
    assert check(store, fetcher=False) == [], "files, manifest, stats and card all agree with each other"
    assert check(store) == ["CG2200ORG02: US county: 4 rows, CG2200ORG02 says 5", "CG2200ORG02: US total: 49 rows, CG2200ORG02 says 50",
                            "CG2200ORG02: ID county: 0 rows, CG2200ORG02 says 1", "CG2200ORG02: ID total: 0 rows, CG2200ORG02 says 1"]


@pytest.mark.parametrize("edit, expected", [
    (lambda rows: row(rows, locus_name="prattville").update(census_id="999999"), "locus_crosswalk: al/prattville names census_id 999999, which is not in governments"),
    (lambda rows: rows.append(dict(rows[0])), "locus_crosswalk: jurisdictions listed more than once: 1 (ak/cities/anchorage)"),
    (lambda rows: row(rows, locus_name="prattville").update(census_id=None), "locus_crosswalk: al/prattville is name with census_id None"),
    (lambda rows: row(rows, locus_name="howard").update(census_id="127039"), "locus_crosswalk: ks/howard is ambiguous with census_id '127039'"),
    (lambda rows: row(rows, locus_name="prattville").update(candidates=["100019"]), "locus_crosswalk: al/prattville is name with candidates ['100019']"),
    (lambda rows: row(rows, locus_name="barre").update(census_id="114404", candidates=["135964"]), "locus_crosswalk: vt/barre's census_id 114404 is not among its candidates"),
    (lambda rows: row(rows, locus_name="barre").update(match="guess"), "locus_crosswalk: match values ['guess'] are not among"),
    (lambda rows: row(rows, locus_name="barre").update(census_id="100019"), "locus_crosswalk: census_id matched by more than one jurisdiction: 1 (100019)"),
    (lambda rows: row(rows, locus_name="barre").update(locus_rows=0), "locus_crosswalk: vt/barre has locus_rows 0"),
])
def test_each_planted_crosswalk_defect_is_named_even_in_a_consistent_manifest(published, edit, expected):
    store, _ = published
    edit_table(store, "locus_crosswalk", edit)
    reseal(store)
    assert any(problem.startswith(expected) for problem in check(store)), check(store)


def test_a_file_that_is_not_the_manifest_s_is_named(published):
    store, manifest = published
    rows = manifest["sources"]["locus"]["rows"]
    edit_table(store, "locus_crosswalk", lambda crosswalk: row(crosswalk, locus_name="barre").update(locus_rows=4))
    problems = check(store, stated=rows)
    assert problems[0].startswith(f"{CROSSWALK} has SHA-256 ")
    assert f"locus_crosswalk: {rows + 1} LOCUS rows, the manifest says {rows}" in problems and f"locus_crosswalk: {rows + 1} LOCUS rows, LOCUS's card states {rows}" in problems
    assert "the manifest's stats differ from the tables' in ['locus']" in problems


def test_the_live_locus_row_count_is_compared(published):
    store, manifest = published
    rows = manifest["sources"]["locus"]["rows"]
    assert check(store, stated=rows + 1) == [f"locus_crosswalk: {rows:,} LOCUS rows, LOCUS's card states {rows + 1:,}"]


@pytest.mark.parametrize("plant, expected", [
    (lambda store: (store.root / "data/extra.parquet").write_bytes(b"x"), ["data/extra.parquet is in the repo but not in the manifest"]),
    (lambda store: (store.root / CARD).write_text(store.read_text(CARD) + "\nedited by hand\n"), [f"{CARD} is not the card this code renders from the manifest; run `python -m local_laws card`"]),
    (lambda store: (store.root / MANIFEST).unlink(), ["no manifest.json"]),
    (lambda store: (store.root / MANIFEST).write_text("{"), ["manifest.json is not JSON: "]),
])
def test_each_planted_repo_defect_is_the_only_problem(published, plant, expected):
    store, _ = published
    plant(store)
    problems = check(store)
    assert len(problems) == len(expected) and all(problem.startswith(start) for problem, start in zip(problems, expected)), problems


def test_a_missing_or_unreadable_table_is_named(published):
    store, _ = published
    (store.root / CROSSWALK).unlink()
    (store.root / GOVERNMENTS).write_bytes(b"PAR1 truncated")
    problems = check(store)
    assert f"{CROSSWALK} is in the manifest but not in the repo" in problems
    assert any(problem.startswith(f"governments: {GOVERNMENTS} cannot be read as parquet") for problem in problems), problems


def test_a_manifest_that_disagrees_with_its_files_is_named(published):
    store, _ = published
    edit_manifest(store, lambda manifest: manifest["files"][GOVERNMENTS].update(rows=51))
    assert "governments: 50 rows, the manifest says 51" in check(store)
    edit_manifest(store, lambda manifest: manifest["stats"].update(governments=51))
    assert "the manifest's stats differ from the tables' in ['governments']" in check(store)


def test_a_table_whose_schema_drifted_is_named(published):
    store, _ = published
    rows = store.read_table(GOVERNMENTS).to_pylist()
    schema = pa.schema([field.with_type(pa.string()) if field.name == "population" else field for field in TABLES["governments"]["schema"]])
    pq.write_table(pa.Table.from_pylist([dict(r, population=str(r["population"])) for r in rows], schema=schema), store.root / GOVERNMENTS)
    assert any(problem.startswith("governments: schema ") and problem.endswith("is not the documented one") for problem in check(store))


def test_an_extra_column_in_a_consistent_build_is_one_problem_not_one_per_crosswalk_row(published):
    store, _ = published
    table = store.read_table(GOVERNMENTS)
    pq.write_table(table.append_column("mailing_city", pa.array(["X"] * table.num_rows, pa.string())), store.root / GOVERNMENTS)
    edit_manifest(store, lambda manifest: manifest["files"][GOVERNMENTS].update(sha256=sha256_file(store.root / GOVERNMENTS), bytes=(store.root / GOVERNMENTS).stat().st_size))
    (store.root / CARD).write_text(render(json.loads(store.read_text(MANIFEST))))
    problems = check(store)
    assert len(problems) == 1 and problems[0].startswith("governments: schema ") and "mailing_city" in problems[0], problems


def test_an_undocumented_column_is_named(published, monkeypatch):
    store, _ = published
    docs = dict(TABLES["governments"]["docs"])
    del docs["is_active"]
    monkeypatch.setitem(TABLES["governments"], "docs", docs)
    problems = check(store)
    assert "governments: documented columns differ from the schema's: ['is_active']" in problems
    assert "the card cannot be rendered from the manifest: KeyError: 'is_active'" in problems


def test_a_manifest_built_from_other_pins_is_named(published, monkeypatch):
    store, _ = published
    monkeypatch.setattr(locus, "REVISION", "f" * 40)
    monkeypatch.setattr(census, "GOVT_UNITS_SHA256", "e" * 64)
    problems = check(store)
    assert f"the manifest's locus revision is '4cee954ca8ad8e31cb0502dff6682c87b74b4302'; this code pins {'f' * 40}" in problems
    assert any(problem.startswith("the manifest's census_governments sha256 is ") and problem.endswith("e" * 64) for problem in problems)


def test_a_changed_cg2200org02_stops_verify(published):
    store, _ = published
    with pytest.raises(SourceChanged, match="not the pinned"):
        verify(store, fetcher=FakeFetcher({census.ORG02_URL: ORG02 + b"x"}))
