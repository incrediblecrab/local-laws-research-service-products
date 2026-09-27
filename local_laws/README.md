# local_laws

The package behind `python -m local_laws {probe,run,verify,card,check-pins,harvest-ny,harvest-nfip}`, against the Hub (`--repo`, default `incrediblecrab/us-local-laws`) or a directory (`--local DIR`).

**Objective:** build the six tables from reviewed source pins plus live New York and FEMA snapshots, commit the tables, the FEMA files read, manifest and card together, and verify what is published.

**Inputs:** pinned Census files, LOCUS-v1, New York's older index and the Bureau of Indian Affairs' two latest Federal Register notices; New York filings from the API or a `harvest-ny` snapshot; FEMA's Community Status Book and OpenFEMA copy from fema.gov or a `harvest-nfip` snapshot, or, when fema.gov refuses a run, the copy the last build stored in the dataset; for Hub writes, either local `HF_TOKEN` or GitHub Actions Trusted Publishing.

**Files:** `cli.py` and `__main__.py` define the commands; `build.py` coordinates downloads, checks, tables and manifest; source modules (`census.py`, `locus.py`, `nylaws.py`, `nyindex.py`, `tribes.py`, `nfip.py`) parse and check each source; `schema.py` documents columns; `card.py` renders the dataset card; `store.py` writes local or Hub commits with a parent fence; `verify.py` checks publication; `http.py` handles pacing, retries and bot-challenge stops; `precision.py` records the hand-run New York precision check.
