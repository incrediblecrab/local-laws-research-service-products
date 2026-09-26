"""python -m local_laws end to end on the fixtures: exit codes, what is written, and what is refused."""

import json

import pytest

from conftest import CODE, FakeFetcher, fake_locus_download
from local_laws import census, cli, locus
from local_laws.http import Blocked, Unavailable
from local_laws.store import CARD, MANIFEST, LocalStore, Superseded


@pytest.fixture
def offline(monkeypatch, pins):
    """The CLI with the Census fixtures for downloads, the synthetic LOCUS, and a clean committed tree."""
    monkeypatch.setattr(cli, "Fetcher", FakeFetcher)
    monkeypatch.setattr(locus, "download", fake_locus_download)
    monkeypatch.setattr(locus, "stated_rows", lambda: 71)
    monkeypatch.setattr(cli, "code_version", lambda: dict(CODE))


def run(*argv):
    return cli.main(list(argv))


def test_run_writes_a_build_that_verifies_and_an_unchanged_rerun_writes_nothing(tmp_path, offline, capsys):
    out, work = tmp_path / "out", tmp_path / "work"
    assert run("run", "--local", str(out), "--workdir", str(work)) == 0
    assert json.loads(capsys.readouterr().out) == {"governments": 50, "locus_jurisdictions": 25, "matched": 23, "requests": 2, "commit": "1", "unchanged": False}
    assert LocalStore(out).list_files() == [CARD, "data/governments.parquet", "data/locus_crosswalk.parquet", MANIFEST]
    assert not any(path.name.startswith("locus-") for path in work.iterdir()), "LOCUS's download is deleted after the build"
    manifest = (out / MANIFEST).read_text()
    assert run("run", "--local", str(out)) == 0
    assert json.loads(capsys.readouterr().out)["unchanged"] is True
    assert (out / MANIFEST).read_text() == manifest, "an unchanged rebuild is not committed, so even built_at stays"
    assert run("verify", "--local", str(out)) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["problems"], report["org02_counts_compared"], report["locus_stated_rows"]) == ([], 312, 71)


def test_verify_exits_1_on_a_problem_and_card_repairs_the_card(tmp_path, offline, capsys):
    out = tmp_path / "out"
    assert run("run", "--local", str(out)) == 0
    (out / CARD).write_text((out / CARD).read_text().replace("Coverage", "Coverage (edited)"))
    capsys.readouterr()
    assert run("verify", "--local", str(out), "--offline") == 1
    assert json.loads(capsys.readouterr().out)["problems"] == [f"{CARD} is not the card this code renders from the manifest; run `python -m local_laws card`"]
    assert run("card", "--local", str(out)) == 0 and capsys.readouterr().out == "card updated\n"
    assert run("card", "--local", str(out)) == 0 and capsys.readouterr().out == "card unchanged\n"
    assert run("verify", "--local", str(out), "--offline") == 0


@pytest.mark.parametrize("plant, stop", [
    (lambda monkeypatch: monkeypatch.setattr(census, "GOVT_UNITS_SHA256", "0" * 64), "SourceChanged: https://www2.census.gov/programs-surveys/gus/datasets/2022/govt_units_2022.ZIP has SHA-256"),
    (lambda monkeypatch: monkeypatch.setattr(locus, "stated_rows", lambda: 72) or monkeypatch.setattr(locus, "download", lambda directory: (fake_locus_download(directory)[0], 72)), "SourceChanged: read 71 LOCUS rows; its card states 72"),
    (lambda monkeypatch: monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher({census.GOVT_UNITS_URL: Blocked("bot challenge at www2.census.gov/")})), "Blocked: bot challenge"),
    (lambda monkeypatch: monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher({census.ORG02_URL: Unavailable("HTTP 503 from www2.census.gov")})), "Unavailable: HTTP 503"),
])
def test_a_source_that_is_not_what_was_checked_stops_the_run_with_nothing_written(tmp_path, offline, monkeypatch, capsys, plant, stop):
    plant(monkeypatch)
    out = tmp_path / "out"
    assert run("run", "--local", str(out)) == cli.STOPPED
    assert f"stopped, nothing written: {stop}" in capsys.readouterr().err
    assert not out.exists()


def test_a_superseded_commit_exits_1(tmp_path, offline, monkeypatch, capsys):
    def commit(self, files, message):
        raise Superseded("x/y has a commit this run did not write")

    monkeypatch.setattr(LocalStore, "commit", commit)
    assert run("run", "--local", str(tmp_path / "out")) == 1
    assert "not written: x/y has a commit this run did not write" in capsys.readouterr().err


@pytest.mark.parametrize("code", [{"version": "0.1.0", "commit": "a" * 40, "dirty": True}, {"version": "0.1.0", "commit": None, "dirty": None}])
@pytest.mark.parametrize("command", ["run", "card"])
def test_the_hub_is_not_written_from_code_that_is_not_committed(offline, monkeypatch, capsys, code, command):
    monkeypatch.setattr(cli, "code_version", lambda: code)

    def hub(*args, **kwargs):
        raise AssertionError("the Hub was contacted")

    monkeypatch.setattr(cli, "HubStore", hub)
    assert run(command) == cli.STOPPED
    assert "refusing to write to the Hub" in capsys.readouterr().err


def test_a_rerun_commits_a_card_that_is_not_the_current_render(tmp_path, offline, capsys):
    out = tmp_path / "out"
    assert run("run", "--local", str(out)) == 0
    card = (out / CARD).read_text()
    (out / CARD).write_text("an older card\n")
    capsys.readouterr()
    assert run("run", "--local", str(out)) == 0
    assert json.loads(capsys.readouterr().out)["unchanged"] is False and (out / CARD).read_text() == card


def test_card_needs_a_manifest(tmp_path, offline, capsys):
    assert run("card", "--local", str(tmp_path / "empty")) == cli.STOPPED
    assert "no manifest.json" in capsys.readouterr().err
