"""One build: every source downloaded at its pinned version and checked against the others, then the two tables, the manifest that describes them and the card."""

import datetime
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from . import __version__, census, locus, schema
from .card import render
from .census import SourceChanged
from .store import CARD, MANIFEST, write_parquet

SORT_KEYS = {
    "governments": lambda row: row["census_id"],
    "locus_crosswalk": lambda row: (row["locus_state"], row["locus_jurisdiction_type"], row["locus_name"]),
}
# Manifest keys that change with every build even when nothing they describe does; a build that differs from the published one only in these is not committed.
VOLATILE = ("built_at", "code")


def code_version():
    """The pipeline's version, its git commit and whether the working tree had changes not yet committed."""
    root = Path(__file__).resolve().parent.parent

    def git(*args):
        try:
            return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain")
    return {"version": __version__, "commit": commit, "dirty": None if status is None else bool(status)}


def summarize(governments, crosswalk):
    """The counts the card shows. verify recomputes them from the published tables, so they are only ever what the data holds."""
    matched = {row["census_id"] for row in crosswalk if row["census_id"]}
    types = {}
    for kind in census.TYPES:
        rows = [row for row in governments if row["government_type"] == kind]
        entry = {
            "governments": len(rows),
            "active": sum(1 for row in rows if row["is_active"]),
            "with_web_address": sum(1 for row in rows if row["web_address"]),
            "in_locus": sum(1 for row in rows if row["census_id"] in matched),
        }
        if kind in locus.GENERAL_PURPOSE:
            entry["population"] = sum(row["population"] or 0 for row in rows)
            entry["in_locus_population"] = sum(row["population"] or 0 for row in rows if row["census_id"] in matched)
            entry["population_years"] = {"none" if year is None else str(year): n for year, n in sorted(Counter(row["population_year"] for row in rows).items(), key=lambda item: -1 if item[0] is None else item[0])}
        types[kind] = entry
    states = {}
    for row in governments:
        entry = states.setdefault(row["state"], dict.fromkeys(census.TYPES, 0) | {"in_locus": 0})
        entry[row["government_type"]] += 1
        entry["in_locus"] += int(row["census_id"] in matched)
    matches = {}
    for match in locus.MATCHES:
        rows = [row for row in crosswalk if row["match"] == match]
        matches[match] = {
            "jurisdictions": len(rows),
            "rows": sum(row["locus_rows"] for row in rows),
            "text_fits": sum(1 for row in rows if row["text_fits"] is True),
            "text_differs": sum(1 for row in rows if row["text_fits"] is False),
            "text_unchecked": sum(1 for row in rows if row["text_fits"] is None),
        }
    def names(rows):
        return sorted(f"{row['locus_state']}/{row['locus_name']}" for row in rows)

    located = [row for row in crosswalk if row["census_id"]]
    return {
        "governments": len(governments),
        "types": types,
        "states": dict(sorted(states.items())),
        "locus": {
            "jurisdictions": len(crosswalk),
            "rows": sum(row["locus_rows"] for row in crosswalk),
            "matched": len(located),
            "matches": matches,
            "matched_few_mentions": sum(1 for row in located if row["text_fits"] is None and row["text_mentions"] < locus.MIN_MENTIONS),
            "matched_without_mentions": names(row for row in located if row["text_mentions"] == 0),
            "text_differs": names(row for row in crosswalk if row["text_fits"] is False),
            "ambiguous": names(row for row in crosswalk if row["match"] == "ambiguous"),
            "unmatched": names(row for row in crosswalk if row["match"] == "unmatched"),
        },
    }


def fetch_census(fetcher):
    """The two Census downloads, each checked against its pinned SHA-256."""
    units = fetcher.get(census.GOVT_UNITS_URL)
    census.check_sha256(units, census.GOVT_UNITS_SHA256, census.GOVT_UNITS_URL)
    org02 = fetcher.get(census.ORG02_URL)
    census.check_sha256(org02, census.ORG02_SHA256, census.ORG02_URL)
    return units, org02


def build(fetcher, workdir, locus_download=None, built_at=None, code=None):
    """Downloads and checks every source and writes the files for one commit into workdir/stage. Returns (manifest, files), files mapping repo paths to local files.
    Raises SourceChanged, and writes nothing, if a source is not the one pinned or the sources disagree. locus_download defaults to locus.download."""
    units_zip, org02_zip = fetch_census(fetcher)
    governments, notes = census.parse_units(census.zip_member(units_zip, census.GOVT_UNITS_MEMBER))
    org02 = census.parse_org02(census.zip_member(org02_zip, census.ORG02_MEMBER))
    mismatches = census.compare(governments, org02)
    if mismatches:
        raise SourceChanged(f"{len(mismatches)} counts in CG2200ORG02 disagree with the Census file: {mismatches[:5]}")
    Path(workdir).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="locus-", dir=workdir) as directory:
        paths, stated = (locus_download or locus.download)(directory)
        crosswalk = locus.crosswalk(paths, governments)
    read = sum(row["locus_rows"] for row in crosswalk)
    if read != stated:
        raise SourceChanged(f"read {read:,} LOCUS rows; its card states {stated:,}")
    stage = Path(workdir) / "stage"
    files, entries = {}, {}
    for name, rows in (("governments", governments), ("locus_crosswalk", crosswalk)):
        spec = schema.TABLES[name]
        local = stage / spec["file"]
        entries[spec["file"]] = write_parquet(rows, local, spec["schema"], SORT_KEYS[name])
        files[spec["file"]] = local
    manifest = {
        "built_at": built_at or datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code": code or code_version(),
        "sources": {
            "census_governments": {"url": census.GOVT_UNITS_URL, "sha256": census.GOVT_UNITS_SHA256, "rows": len(governments), "normalization": notes},
            "census_org02": {"url": census.ORG02_URL, "sha256": census.ORG02_SHA256, "counts_compared": len(org02), "mismatches": 0},
            "locus": {"repo_id": locus.REPO_ID, "revision": locus.REVISION, "license": locus.LICENSE, "rows": stated, "jurisdictions": len(crosswalk)},
        },
        "files": entries,
        "stats": summarize(governments, crosswalk),
    }
    files[MANIFEST] = stage / MANIFEST
    files[MANIFEST].write_text(manifest_text(manifest))
    # The card is rendered from the manifest as written, which is what verify reads back.
    manifest = json.loads(files[MANIFEST].read_text())
    files[CARD] = stage / CARD
    files[CARD].write_text(render(manifest))
    return manifest, files


def manifest_text(manifest):
    return json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def unchanged(store, manifest):
    """True when the store already holds this build: the same manifest apart from VOLATILE keys, and the same card."""
    old = store.read_text(MANIFEST)
    if old is None:
        return False

    def stable(value):
        return {key: item for key, item in value.items() if key not in VOLATILE}

    return stable(json.loads(old)) == stable(json.loads(manifest_text(manifest))) and store.read_text(CARD) == render(manifest)
