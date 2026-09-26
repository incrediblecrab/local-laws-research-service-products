# local_laws

The pipeline: `python -m local_laws {run,verify,card,harvest-ny}`, against the Hub (`--repo`, default `incrediblecrab/local-laws-research-service-products`) or a directory (`--local DIR`).

**Objective:** build the five tables from pinned sources and a checked New York snapshot, stop rather than publish when a source has changed, commit the tables, manifest and card together, and check what is published.

**Inputs:** the Census files, LOCUS-v1, the Local Geohistory Project's release of New York's older index and the Bureau of Indian Affairs' two latest notices of its list of federally recognized Tribes, from the Federal Register, at their pins; New York's local-law filings, from a snapshot `harvest-ny` wrote (`run --ny-snapshot`) or from the API; for a Hub write, a token in `HF_TOKEN`.

**Files:**

- `cli.py`, `__main__.py`: the commands. Exit 0 when done; 1 when verify finds a problem or another writer committed first; 2 when a command stops, for example on a changed source, a bot challenge or uncommitted code.
- `build.py`: downloads, checks, the tables and the manifest.
- `census.py`: Census rows, normalized and checked against CG2200ORG02.
- `locus.py`: the crosswalk: name rules, text check, hand-checked aliases.
- `nylaws.py`: New York's filings: the harvest, reconciled with the API's counts by filing year; the table's rows; the match to Census governments by type, name and county; and the statistics the card states.
- `nyindex.py`: New York's older index: the release's export, checked against the State's data file in the same release, typed, matched by `nylaws.py`'s rules, and its statistics.
- `tribes.py`: the list of federally recognized Tribes: each notice's XML read into its stated count and its two lists, each entry matched to the one it continues in the notice it updates, the two reconciled, and the statistics the card states.
- `precision.py`: the check of New York's matches against the filings' text, run once by hand, and every answer it got.
- `schema.py`: the tables' columns and what each means.
- `card.py`: the dataset card, rendered from the manifest.
- `store.py`: a local directory or the Hub, with a parent-commit fence.
- `verify.py`: the publication check, which downloads CG2200ORG02, the index's release and the Bureau's two notices again to compare.
- `http.py`: per-host pacing and bounded retries; a bot challenge stops the run.
- `__init__.py`: version and repository names.
