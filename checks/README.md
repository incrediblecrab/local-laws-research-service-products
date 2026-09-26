# checks

One-off checks run by hand against a build, whose results the dataset card states. They are not part of the build or the offline tests, and they make requests.

**Objective:** measure what the build cannot check by itself, and keep the draw and every answer so the result can be re-derived.

**Inputs:** a directory `python -m local_laws run --local DIR` wrote; for a check that asks New York's API, network access, at one request a second.

**Files:**

- `ny_precision.py`: the check of New York's matches against the filings' text. `python checks/ny_precision.py --local DIR --draw-only` redraws the sample from the tables and compares it with the one [`local_laws/precision.py`](../local_laws/precision.py) records, requesting nothing; without `--draw-only` it asks the API about each filing (about 480 requests) and prints the lines `precision.py` keeps. The September 26, 2026 check made 471 requests for the draws: 295; then 50 asking each filing for `precision.GENERIC` without text, a control for the metadata added after the other answers; then 126 for the `UNNAMED` phrases, the matched name after each other title with which no government in `governments` is named. One of those, COUNTY OF NEW YORK, names a real county the Census does not count as a government, so `precision.REAL` leaves its answers out of the counts. Before them it made 40: 2 to find the restriction to one filing and 38 for the five calibration filings.
