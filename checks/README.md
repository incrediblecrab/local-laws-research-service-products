# checks

One-off network checks run by hand against a completed local build; the dataset card states their results. They are not part of the build or offline tests.

**Objective:** measure evidence the build cannot check by itself, while keeping the draw and answers reproducible.

**Inputs:** a directory from `python -m local_laws run --local DIR`, and network access for checks that query New York's API at one request per second.

**Files:**

- `ny_precision.py`: checks New York matches against filing text. `python checks/ny_precision.py --local DIR --draw-only` redraws the sample and compares it with `local_laws/precision.py` without network access; without `--draw-only`, it asks the API about each filing and prints the lines recorded in `precision.py`.
