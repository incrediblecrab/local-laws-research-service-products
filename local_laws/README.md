# local_laws

The pipeline: `python -m local_laws {run,verify,card}`, against the Hub (`--repo`, default `incrediblecrab/local-laws-research-service-products`) or a directory (`--local DIR`).

**Objective:** build both tables from pinned sources, stop rather than publish when a source has changed, commit the tables, manifest and card together, and check what is published.

**Inputs:** the Census files and LOCUS-v1 at their pins; for a Hub write, a token in `HF_TOKEN`.

**Files:**

- `cli.py`, `__main__.py`: the commands. Exit 0 when done; 1 when verify finds a problem or another writer committed first; 2 when a command stops, for example on a changed source, a bot challenge or uncommitted code.
- `build.py`: downloads, checks, both tables and the manifest.
- `census.py`: Census rows, normalized and checked against CG2200ORG02.
- `locus.py`: the crosswalk: name rules, text check, hand-checked aliases.
- `schema.py`: both tables' columns and what each means.
- `card.py`: the dataset card, rendered from the manifest.
- `store.py`: a local directory or the Hub, with a parent-commit fence.
- `verify.py`: the publication check.
- `http.py`: per-host pacing and bounded retries; a bot challenge stops the run.
- `__init__.py`: version and repository names.
