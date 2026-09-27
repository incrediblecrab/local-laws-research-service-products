# tests

Offline tests: `PYTHONDONTWRITEBYTECODE=1 ~/.venvs/main/bin/python -m pytest -q`.

**Objective:** pin down the build, CLI, verification, publication fence, probe, OIDC and stale-pin behavior without network access or secrets.

**Inputs:** fixtures in [`fixtures/`](fixtures/README.md): real samples from Census, New York, the Local Geohistory index, Federal Register BIA notices and FEMA/OpenFEMA, plus a synthetic LOCUS written by `conftest.py` because LOCUS text is CC BY-NC.

**Files:** `conftest.py` defines fake HTTP, New York API, LOCUS and local published builds. `test_census.py`, `test_locus.py`, `test_nylaws.py`, `test_nyindex.py`, `test_tribes.py`, `test_nfip.py`, `test_precision.py`, `test_store.py`, `test_card.py`, `test_verify.py`, `test_cli.py` and `test_http.py` cover the package by source and command. `mutate.py` disables one check at a time in a copy and fails unless the suite catches every mutation.
