"""python -m local_laws end to end on the fixtures: exit codes, what is written, and what is refused."""

import copy
import itertools
import json
import os

import pytest

from conftest import CODE, NY_SAMPLE, FakeFetcher, FakeNYApi, fake_locus_download, nfip_snapshot
from local_laws import census, cli, locus, nfip, nyindex, nylaws, tribes
from local_laws.http import Blocked, Unavailable
from local_laws.store import CARD, MANIFEST, LocalStore, Superseded

FILES = [CARD, "data/federally_recognized_tribes.parquet", "data/governments.parquet", "data/locus_crosswalk.parquet", "data/nfip_communities.parquet", "data/ny_local_law_index.parquet", "data/ny_local_laws.parquet", MANIFEST]


@pytest.fixture
def offline(monkeypatch, pins):
    """The CLI with the Census, New York index and notice fixtures for downloads, the synthetic LOCUS, and a clean committed tree."""
    monkeypatch.setattr(cli, "Fetcher", FakeFetcher)
    monkeypatch.setattr(locus, "download", fake_locus_download)
    monkeypatch.setattr(locus, "stated_rows", lambda: 71)
    monkeypatch.setattr(cli, "code_version", lambda: dict(CODE))


def run(*argv):
    return cli.main(list(argv))


@pytest.fixture
def snapshot(tmp_path):
    """The New York sample saved as harvest-ny saves a snapshot."""
    path = tmp_path / "ny.json.gz"
    nylaws.save(NY_SAMPLE, path)
    return str(path)


@pytest.fixture
def flood(tmp_path):
    """The NFIP samples saved as harvest-nfip saves a snapshot."""
    path = tmp_path / "nfip.zip"
    nfip.save(nfip_snapshot(), path)
    return str(path)


class DownNYApi(FakeNYApi):
    def answer(self, url):
        raise Unavailable("HTTP 503 from locallaws.static-assets.ny.gov")


def test_run_writes_a_build_that_verifies_and_an_unchanged_rerun_writes_nothing(tmp_path, offline, capsys, snapshot, flood):
    out, work = tmp_path / "out", tmp_path / "work"
    assert run("run", "--local", str(out), "--workdir", str(work), "--ny-snapshot", snapshot, "--nfip-snapshot", flood) == 0
    assert json.loads(capsys.readouterr().out) == {"governments": 50, "locus_jurisdictions": 25, "matched": 23, "ny_filings": 25, "ny_matched": 10, "ny_index_rows": 14, "ny_index_matched": 7, "tribes": 19, "nfip_communities": 25, "requests": 5, "commit": "1", "unchanged": False}
    assert LocalStore(out).list_files() == FILES
    assert not any(path.name.startswith("locus-") for path in work.iterdir()), "LOCUS's download is deleted after the build"
    manifest = (out / MANIFEST).read_text()
    assert run("run", "--local", str(out), "--ny-snapshot", snapshot, "--nfip-snapshot", flood) == 0
    assert json.loads(capsys.readouterr().out)["unchanged"] is True
    assert (out / MANIFEST).read_text() == manifest, "an unchanged rebuild is not committed, so even built_at stays"
    assert run("verify", "--local", str(out)) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["problems"], report["org02_counts_compared"], report["locus_stated_rows"], report["nfip_report"]) == ([], 312, 71, {"same_file": True, "rows": 25})


def test_a_run_without_a_snapshot_reads_the_api_and_harvest_ny_saves_the_same_reading(tmp_path, offline, monkeypatch, capsys):
    clock = (f"2026-09-26T04:{minute:02d}:00Z" for minute in itertools.count())
    monkeypatch.setattr(nylaws, "now", lambda: next(clock))
    monkeypatch.setattr(nfip, "now", lambda: next(clock))
    live, saved, path = tmp_path / "live", tmp_path / "saved", tmp_path / "ny.json.gz"
    assert run("run", "--local", str(live)) == 0
    summary = json.loads(capsys.readouterr().out)
    assert (summary["ny_filings"], summary["ny_matched"], summary["requests"] > 5, summary["unchanged"]) == (25, 10, True, False)
    assert run("run", "--local", str(live)) == 0
    assert json.loads(capsys.readouterr().out)["unchanged"] is False, "a new reading of the API is a new build: the manifest says when it was read"
    assert run("harvest-ny", "--out", str(path)) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["total"], report["years"], report["requests"]) == (25, NY_SAMPLE["years"], summary["requests"] - 7), "the run also made the two Census requests, the index's, the two notices' and FEMA's two"
    assert nylaws.load(path)["items"] == NY_SAMPLE["items"]
    assert run("run", "--local", str(saved), "--ny-snapshot", str(path)) == 0
    capsys.readouterr()
    assert (saved / "data/ny_local_laws.parquet").read_bytes() == (live / "data/ny_local_laws.parquet").read_bytes()


def test_harvest_ny_stops_with_nothing_written_when_the_api_does_not_answer(tmp_path, offline, monkeypatch, capsys):
    monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher(ny=DownNYApi()))
    path = tmp_path / "ny.json.gz"
    assert run("harvest-ny", "--out", str(path)) == cli.STOPPED
    assert "stopped, nothing written: Unavailable: HTTP 503 from locallaws.static-assets.ny.gov" in capsys.readouterr().err
    assert not path.exists()


def test_harvest_nfip_saves_what_run_builds_from_and_writes_nothing_it_could_not_reconcile(tmp_path, offline, monkeypatch, capsys):
    clock = iter(["2026-09-26T08:18:00Z", "2026-09-26T08:23:00Z"])
    monkeypatch.setattr(nfip, "now", lambda: next(clock))
    path = tmp_path / "nfip.zip"
    assert run("harvest-nfip", "--out", str(path)) == 0
    assert json.loads(capsys.readouterr().out) == {"out": str(path), "rows": 25, "api_rows": 28, "only_in_api": {"participating": 1, "not_participating": 2}, "retrieved_at": "2026-09-26T08:18:00Z", "api_retrieved_at": "2026-09-26T08:23:00Z", "requests": 2}
    assert nfip.load(path) == nfip_snapshot()
    for response, stop in (({nfip.CSV_URL: b"<html>"}, "SourceChanged: the report's header is ['<html>']"), ({nfip.API_URL: b"<html>"}, "SourceChanged: the OpenFEMA file cannot be read as parquet"), ({nfip.API_URL: Unavailable("HTTP 503 from www.fema.gov")}, "Unavailable: HTTP 503 from www.fema.gov")):
        monkeypatch.setattr(nfip, "now", lambda: "2026-09-26T09:00:00Z")
        monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher(response))
        other = tmp_path / "other.zip"
        assert run("harvest-nfip", "--out", str(other)) == cli.STOPPED
        assert f"stopped, nothing written: {stop}" in capsys.readouterr().err
        assert not other.exists()


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
    (lambda monkeypatch: monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher(ny=DownNYApi())), "Unavailable: HTTP 503 from locallaws.static-assets.ny.gov"),
    (lambda monkeypatch: monkeypatch.setattr(nyindex, "SHA256", "0" * 64), f"SourceChanged: {nyindex.URL} has SHA-256"),
    (lambda monkeypatch: monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher({nyindex.URL: Blocked("HTTP 403 from zenodo.org")})), "Blocked: HTTP 403 from zenodo.org"),
    (lambda monkeypatch: monkeypatch.setitem(tribes.PREVIOUS, "sha256", "0" * 64), f"SourceChanged: {tribes.PREVIOUS['url']} has SHA-256"),
    (lambda monkeypatch: monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher({tribes.NOTICE["url"]: Blocked("bot challenge at www.federalregister.gov/")})), "Blocked: bot challenge at www.federalregister.gov/"),
    (lambda monkeypatch: monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher({nfip.CSV_URL: Blocked("HTTP 403 from www.fema.gov")})), "Blocked: HTTP 403 from www.fema.gov"),
    (lambda monkeypatch: monkeypatch.setattr(cli, "Fetcher", lambda: FakeFetcher({nfip.API_URL: b"<html>"})), "SourceChanged: the OpenFEMA file cannot be read as parquet"),
])
def test_a_source_that_is_not_what_was_checked_stops_the_run_with_nothing_written(tmp_path, offline, monkeypatch, capsys, plant, stop):
    plant(monkeypatch)
    out = tmp_path / "out"
    assert run("run", "--local", str(out)) == cli.STOPPED
    assert f"stopped, nothing written: {stop}" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("edit, stop", [
    (lambda sample: sample["items"].pop(), "the NY snapshot holds 24 filings; its API counts say 25"),
    (lambda sample: sample["items"][0]["fields"].update(dateFiled=["2002-05-05T05:00:00Z"]), "the NY snapshot holds 25 filings; its API counts say 25, by year"),
])
def test_a_snapshot_whose_filings_are_not_its_counts_stops_the_run_with_nothing_written(tmp_path, offline, capsys, edit, stop):
    sample = copy.deepcopy(NY_SAMPLE)
    assert sample["years"].get("2002") == 0
    edit(sample)
    path, out = tmp_path / "ny.json.gz", tmp_path / "out"
    nylaws.save(sample, path)
    assert run("run", "--local", str(out), "--ny-snapshot", str(path)) == cli.STOPPED
    assert f"stopped, nothing written: SourceChanged: {stop}" in capsys.readouterr().err
    assert not out.exists()


def test_a_superseded_commit_exits_1(tmp_path, offline, monkeypatch, capsys):
    def commit(self, files, message):
        raise Superseded("x/y has a commit this run did not write")

    monkeypatch.setattr(LocalStore, "commit", commit)
    assert run("run", "--local", str(tmp_path / "out")) == 1
    assert "not written: x/y has a commit this run did not write" in capsys.readouterr().err


@pytest.mark.parametrize("code", [{"version": "0.2.0", "commit": "a" * 40, "dirty": True}, {"version": "0.2.0", "commit": None, "dirty": None}])
@pytest.mark.parametrize("command", ["run", "card"])
def test_the_hub_is_not_written_from_code_that_is_not_committed(offline, monkeypatch, capsys, code, command):
    monkeypatch.setattr(cli, "code_version", lambda: code)

    def hub(*args, **kwargs):
        raise AssertionError("the Hub was contacted")

    monkeypatch.setattr(cli, "HubStore", hub)
    assert run(command) == cli.STOPPED
    assert "refusing to write to the Hub" in capsys.readouterr().err


def test_a_rerun_commits_a_card_that_is_not_the_current_render(tmp_path, offline, capsys, snapshot):
    out = tmp_path / "out"
    assert run("run", "--local", str(out), "--ny-snapshot", snapshot) == 0
    card = (out / CARD).read_text()
    (out / CARD).write_text("an older card\n")
    capsys.readouterr()
    assert run("run", "--local", str(out), "--ny-snapshot", snapshot) == 0
    assert json.loads(capsys.readouterr().out)["unchanged"] is False and (out / CARD).read_text() == card


def test_card_needs_a_manifest(tmp_path, offline, capsys):
    assert run("card", "--local", str(tmp_path / "empty")) == cli.STOPPED
    assert "no manifest.json" in capsys.readouterr().err


def test_probe_skips_a_build_when_new_york_fema_and_the_card_match(published, offline, monkeypatch, capsys):
    store, _ = published
    assert run("probe", "--local", str(store.root)) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["needed"] is False
    assert report["reasons"] == ["published sources match"]
    assert report["requests"] == 38


def test_probe_requests_a_build_when_a_cheap_head_changes(published, offline, monkeypatch, capsys):
    store, _ = published

    original = cli.ny_head

    def changed(fetcher):
        head = original(fetcher)
        head["total"] += 1
        return head

    monkeypatch.setattr(cli, "ny_head", changed)
    assert run("probe", "--local", str(store.root)) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["needed"] is True
    assert "New York local-law counts changed" in report["reasons"]


def test_github_actions_writes_set_the_hugging_face_oidc_resource(monkeypatch):
    seen = {}

    class Args:
        local = None
        repo = "owner/data"

    def hub(repo, token=None, create=False):
        seen.update(repo=repo, token=token, create=create, oidc=os.environ.get("HF_OIDC_RESOURCE"))
        raise RuntimeError("stop before network")

    monkeypatch.setattr(cli, "HubStore", hub)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("HF_OIDC_RESOURCE", raising=False)
    with pytest.raises(RuntimeError):
        cli.open_store(Args, write=True)
    assert seen == {"repo": "owner/data", "token": None, "create": True, "oidc": "datasets/owner/data"}


def test_reads_do_not_request_an_oidc_token_in_github_actions(monkeypatch):
    seen = {}

    class Args:
        local = None
        repo = "owner/data"

    def hub(repo, token=None, create=False):
        seen.update(token=token, create=create, oidc=os.environ.get("HF_OIDC_RESOURCE"))
        raise RuntimeError("stop before network")

    monkeypatch.setattr(cli, "HubStore", hub)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("HF_OIDC_RESOURCE", raising=False)
    with pytest.raises(RuntimeError):
        cli.open_store(Args, write=False)
    assert seen == {"token": False, "create": False, "oidc": None}


def test_check_pins_fails_loudly_when_a_person_must_review_a_new_notice(offline, monkeypatch, capsys):
    monkeypatch.setattr(tribes, "latest", lambda fetcher: [{"document_number": "2027-00001", "published": "2027-01-30"}, {"document_number": tribes.NOTICE["document_number"], "published": tribes.NOTICE["published"]}])
    monkeypatch.setattr(locus, "latest", lambda: {"repo_id": locus.REPO_ID, "sha": locus.REVISION, "pinned": locus.REVISION})
    assert run("check-pins", "--local", "unused") == 1
    output = capsys.readouterr().out
    assert "Federal Register has newer BIA recognized-Tribes notices" in output
    assert "review the new notice" in output


def test_check_pins_accepts_the_current_pins(offline, monkeypatch, capsys):
    monkeypatch.setattr(tribes, "latest", lambda fetcher: [{"document_number": tribes.NOTICE["document_number"], "published": tribes.NOTICE["published"]}, {"document_number": tribes.PREVIOUS["document_number"], "published": tribes.PREVIOUS["published"]}])
    monkeypatch.setattr(locus, "latest", lambda: {"repo_id": locus.REPO_ID, "sha": locus.REVISION, "pinned": locus.REVISION})
    assert run("check-pins", "--local", "unused") == 0
    assert "bia_notices" in capsys.readouterr().out


def test_no_trusted_publisher_message_is_a_github_actions_error(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert cli.trusted_publisher_error(RuntimeError("invalid_grant: No trusted publisher configured"), "owner/data") is True
    assert "::error::No trusted publisher configured for owner/data" in capsys.readouterr().out
