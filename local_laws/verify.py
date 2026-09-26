"""Checks a published build: its files against manifest.json, its tables against their schemas and each other, its counts against the Census's own table and LOCUS's card, and its card against a fresh render."""

import json
import re
from collections import Counter

import pyarrow as pa

from . import census, locus
from .build import summarize
from .card import render
from .schema import TABLES
from .store import CARD, HUB_FILES, MANIFEST

SAMPLE = 10
CENSUS_ID = re.compile(r"\d{6}")


def sample(values):
    values = sorted(values)
    return f"{len(values):,} ({', '.join(map(str, values[:SAMPLE]))}{', ...' if len(values) > SAMPLE else ''})"


def check_governments(rows, problems):
    ids = [row["census_id"] for row in rows]
    malformed = [uid for uid in ids if uid is None or not CENSUS_ID.fullmatch(uid)]
    if malformed:
        problems.append(f"governments: census_id null or not 6 digits: {sample(map(repr, malformed))}")
    duplicates = [uid for uid, n in Counter(ids).items() if uid is not None and n > 1]
    if duplicates:
        problems.append(f"governments: duplicate census_id: {sample(duplicates)}")
    kinds = Counter(row["government_type"] for row in rows)
    if set(kinds) - set(census.TYPES):
        problems.append(f"governments: government_type values {sorted(set(kinds) - set(census.TYPES))} are not the Census's five types")
    misplaced = [row["census_id"] for row in rows if census.STATES.get(row["state_fips"]) != row["state"]]
    if misplaced:
        problems.append(f"governments: state does not match state_fips: {sample(misplaced)}")
    general = set(locus.GENERAL_PURPOSE)
    stray = [row["census_id"] for row in rows if (row["government_type"] in general) != (row["fips_place"] is not None)]
    if stray:
        problems.append(f"governments: fips_place set for a district or missing for a general-purpose government: {sample(stray)}")


def check_crosswalk(rows, government_ids, problems):
    """government_ids is None when the governments table was not read, so no census_id is judged against it."""
    keys = Counter((row["locus_state"], row["locus_jurisdiction_type"], row["locus_name"]) for row in rows)
    repeated = [f"{state}/{kind}/{name}" for (state, kind, name), n in keys.items() if n > 1]
    if repeated:
        problems.append(f"locus_crosswalk: jurisdictions listed more than once: {sample(repeated)}")
    unknown = sorted({row["match"] for row in rows} - set(locus.MATCHES))
    if unknown:
        problems.append(f"locus_crosswalk: match values {unknown} are not among {list(locus.MATCHES)}")
    unmatched = set(locus.MATCHES) - set(locus.MATCHED)
    for row in rows:
        name = f"{row['locus_state']}/{row['locus_name']}"
        if (row["census_id"] is None) != (row["match"] in unmatched):
            problems.append(f"locus_crosswalk: {name} is {row['match']} with census_id {row['census_id']!r}")
        if government_ids is not None and row["census_id"] is not None and row["census_id"] not in government_ids:
            problems.append(f"locus_crosswalk: {name} names census_id {row['census_id']}, which is not in governments")
        if bool(row["candidates"]) != (row["match"] in locus.POOLED):
            problems.append(f"locus_crosswalk: {name} is {row['match']} with candidates {row['candidates']}")
        if row["census_id"] is not None and row["candidates"] and row["census_id"] not in row["candidates"]:
            problems.append(f"locus_crosswalk: {name}'s census_id {row['census_id']} is not among its candidates")
        if row["locus_rows"] is None or row["locus_rows"] < 1:
            problems.append(f"locus_crosswalk: {name} has locus_rows {row['locus_rows']!r}")
    duplicates = [uid for uid, n in Counter(row["census_id"] for row in rows if row["census_id"]).items() if n > 1]
    if duplicates:
        problems.append(f"locus_crosswalk: census_id matched by more than one jurisdiction: {sample(duplicates)}")


def verify(store, fetcher=None, stated_rows=None):
    """A report whose "problems" is empty when every check passed. With a fetcher, CG2200ORG02 is downloaded again and compared; with stated_rows (a callable), LOCUS's card is read again."""
    text = store.read_text(MANIFEST)
    if text is None:
        return {"problems": [f"no {MANIFEST}"]}
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as error:
        return {"problems": [f"{MANIFEST} is not JSON: {error}"]}
    problems = []
    entries = manifest.get("files") or {}
    expected = set(entries) | {MANIFEST, CARD}
    listed = set(store.list_files())
    for path in sorted(expected - listed):
        problems.append(f"{path} is in the manifest but not in the repo")
    for path in sorted(listed - expected - set(HUB_FILES)):
        problems.append(f"{path} is in the repo but not in the manifest")
    sha256s = store.file_sha256s(sorted(set(entries) & listed))
    for path, entry in sorted(entries.items()):
        if path in listed and sha256s.get(path) != entry.get("sha256"):
            problems.append(f"{path} has SHA-256 {str(sha256s.get(path))[:12]}, the manifest says {str(entry.get('sha256'))[:12]}")
    tables = {}
    for name, spec in TABLES.items():
        if set(spec["docs"]) != set(spec["schema"].names):
            problems.append(f"{name}: documented columns differ from the schema's: {sorted(set(spec['docs']) ^ set(spec['schema'].names))}")
        if spec["file"] not in entries:
            problems.append(f"{name}: {spec['file']} is not in the manifest")
            continue
        try:
            table = store.read_table(spec["file"]) if spec["file"] in listed else None
        except (pa.ArrowException, OSError) as error:
            problems.append(f"{name}: {spec['file']} cannot be read as parquet: {type(error).__name__}: {error}")
            continue
        if table is None:
            continue
        if not table.schema.equals(spec["schema"], check_metadata=False):
            problems.append(f"{name}: schema {table.schema.to_string(show_schema_metadata=False)!r} is not the documented one")
            continue
        if table.num_rows != entries[spec["file"]].get("rows"):
            problems.append(f"{name}: {table.num_rows:,} rows, the manifest says {entries[spec['file']].get('rows')}")
        tables[name] = table.to_pylist()
    report = {"rows": {name: len(rows) for name, rows in tables.items()}}
    sources = manifest.get("sources") or {}
    pins = {("census_governments", "sha256"): census.GOVT_UNITS_SHA256, ("census_org02", "sha256"): census.ORG02_SHA256, ("locus", "revision"): locus.REVISION}
    for (source, field), pin in pins.items():
        if (sources.get(source) or {}).get(field) != pin:
            problems.append(f"the manifest's {source} {field} is {(sources.get(source) or {}).get(field)!r}; this code pins {pin}")
    governments, crosswalk = tables.get("governments"), tables.get("locus_crosswalk")
    if governments is not None:
        check_governments(governments, problems)
        if len(governments) != (sources.get("census_governments") or {}).get("rows"):
            problems.append(f"governments: {len(governments):,} rows, the manifest's source says {(sources.get('census_governments') or {}).get('rows')}")
        if fetcher is not None:
            data = fetcher.get(census.ORG02_URL)
            census.check_sha256(data, census.ORG02_SHA256, census.ORG02_URL)
            org02 = census.parse_org02(census.zip_member(data, census.ORG02_MEMBER))
            mismatches = census.compare(governments, org02)
            problems += [f"CG2200ORG02: {mismatch}" for mismatch in mismatches]
            report["org02_counts_compared"] = len(org02)
    if crosswalk is not None:
        check_crosswalk(crosswalk, None if governments is None else {row["census_id"] for row in governments}, problems)
        read = sum(row["locus_rows"] or 0 for row in crosswalk)
        if read != (sources.get("locus") or {}).get("rows"):
            problems.append(f"locus_crosswalk: {read:,} LOCUS rows, the manifest says {(sources.get('locus') or {}).get('rows')}")
        if stated_rows is not None:
            stated = stated_rows()
            report["locus_stated_rows"] = stated
            if read != stated:
                problems.append(f"locus_crosswalk: {read:,} LOCUS rows, LOCUS's card states {stated:,}")
    if governments is not None and crosswalk is not None:
        try:
            stats = json.loads(json.dumps(summarize(governments, crosswalk)))
        except (KeyError, TypeError) as error:
            problems.append(f"the manifest's stats cannot be recomputed from the tables: {type(error).__name__}: {error}")
        else:
            if stats != manifest.get("stats"):
                differing = sorted(key for key in set(stats) | set(manifest.get("stats") or {}) if stats.get(key) != (manifest.get("stats") or {}).get(key))
                problems.append(f"the manifest's stats differ from the tables' in {differing}")
    try:
        card = render(manifest)
    except (KeyError, TypeError, ValueError) as error:
        problems.append(f"the card cannot be rendered from the manifest: {type(error).__name__}: {error}")
    else:
        if store.read_text(CARD) != card:
            problems.append(f"{CARD} is not the card this code renders from the manifest; run `python -m local_laws card`")
    report["problems"] = problems
    return report
