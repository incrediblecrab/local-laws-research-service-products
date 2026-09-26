# fixtures

**Objective:** real Census rows and real New York filings that reach every normalization and matching rule the tests check, small enough to commit.

**Inputs:** the Census Bureau's `govt_units_2022.ZIP`, at the SHA-256 pinned in `local_laws/census.py`; a New York snapshot `python -m local_laws harvest-ny` wrote.

**Files:**

- `make_census_sample.py`: writes both zips from the real file: `python tests/fixtures/make_census_sample.py path/to/govt_units_2022.ZIP`.
- `govt_units_sample.zip`: 50 governments and 1 dependent school system, copied value for value from the real file, with the columns the dataset leaves out blanked: the contact title and the street, city and ZIP of the mailing address (TITLE, ADDRESS1, ADDRESS2, CITY, ZIP and ZIP4).
- `org02_sample.zip`: a CG2200ORG02 computed from those rows in the real table's layout, so the build's check against it passes; the tests plant a wrong count to see it fail.
- `make_ny_sample.py`: writes the New York sample from a real snapshot: `python tests/fixtures/make_ny_sample.py path/to/ny-local-laws-snapshot.json.gz`. Its `CHOSEN` names each filing and the rule or sentence it is there for.
- `ny_snapshot_sample.json`: those filings, copied as the harvest kept them: public filing records (names, numbers, dates, titles and share links), with the snapshot's counts recomputed for the sample.

Regenerating the zips changes their bytes, because they record when they were written, so the tests hash them as they run instead of pinning them.
