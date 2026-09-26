# tests

Offline tests (no network or token): `pip install '.[test]'`, then `python -m pytest -q`.

**Objective:** pin down the behavior the build and verify depend on, and show that they catch a broken check.

**Inputs:** real Census rows in [`fixtures/`](fixtures/README.md); a synthetic LOCUS written by `conftest.py`, with invented text, since LOCUS's own text is CC BY-NC; fakes for the Hub and HTTP.

**Files:**

- `conftest.py`: the synthetic LOCUS with each jurisdiction's expected match, a fetcher serving the fixtures, and a build published to a local store.
- `test_census.py`: normalization, the CG2200ORG02 check, and source changes that stop a parse.
- `test_locus.py`: each match rule, the text thresholds, the alias and duplicate guards, and names in prose.
- `test_store.py`: the commit fence against a fake Hub: conflicts, lost responses and bounded retries.
- `test_card.py`: front matter, schema tables and each sentence that depends on the data.
- `test_verify.py`: each planted data defect is named.
- `test_cli.py`: exit codes, unchanged reruns and refusals.
- `test_http.py`: challenges, retries and pacing.
- `mutate.py`: `python tests/mutate.py` disables one check at a time in a copy of the package and exits 1 unless the suite fails for every one.
