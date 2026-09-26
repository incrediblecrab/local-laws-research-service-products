# tests

Offline tests (no network or token): `pip install '.[test]'`, then `python -m pytest -q`.

**Objective:** pin down the behavior the build and verify depend on, and show that they catch a broken check.

**Inputs:** real Census rows, real New York filings and real records of New York's older index in [`fixtures/`](fixtures/README.md); a synthetic LOCUS written by `conftest.py`, with invented text, since LOCUS's own text is CC BY-NC; fakes for the Hub, HTTP and New York's API.

**Files:**

- `conftest.py`: the synthetic LOCUS with each jurisdiction's expected match, a fake of New York's API over the fixture filings with its range syntax, sorts and paging limits, a fetcher serving the fixtures, the index sample among them, and a build published to a local store.
- `test_census.py`: normalization, the CG2200ORG02 check, and source changes that stop a parse.
- `test_locus.py`: each match rule, the text thresholds, the alias and duplicate guards, and names in prose.
- `test_nylaws.py`: the harvest's reconciliation with the API's counts, the rows' checks, the match to Census governments, and the posting and repeat statistics.
- `test_nyindex.py`: New York's older index: the export read and typed, the check against the State's data file, types in any case read as the search writes them, the match and the statistics.
- `test_precision.py`: the outcome each set of the API's answers gives in the check of New York's matches, and that the recorded answers are the draws `local_laws/precision.py` describes.
- `test_store.py`: the commit fence against a fake Hub: conflicts, lost responses and bounded retries.
- `test_card.py`: front matter, schema tables and each sentence that depends on the data.
- `test_verify.py`: each planted data defect is named, among them index rows that are not the release's.
- `test_cli.py`: exit codes, unchanged reruns and refusals.
- `test_http.py`: challenges, retries and pacing.
- `mutate.py`: `python tests/mutate.py` disables one check at a time in a copy of the package and exits 1 unless the suite fails for every one. Run it with `PYTHONDONTWRITEBYTECODE=1`: a same-size edit within the same second can otherwise reuse a stale `.pyc`.
