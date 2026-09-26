# fixtures

**Objective:** real Census rows that reach every normalization and matching rule the tests check, small enough to commit.

**Inputs:** the Census Bureau's `govt_units_2022.ZIP`, at the SHA-256 pinned in `local_laws/census.py`.

**Files:**

- `make_census_sample.py`: writes both zips from the real file: `python tests/fixtures/make_census_sample.py path/to/govt_units_2022.ZIP`.
- `govt_units_sample.zip`: 50 governments and 1 dependent school system, copied value for value from the real file, with the columns the dataset leaves out blanked: the contact title and the street, city and ZIP of the mailing address (TITLE, ADDRESS1, ADDRESS2, CITY, ZIP and ZIP4).
- `org02_sample.zip`: a CG2200ORG02 computed from those rows in the real table's layout, so the build's check against it passes; the tests plant a wrong count to see it fail.

Regenerating the zips changes their bytes, because they record when they were written, so the tests hash them as they run instead of pinning them.
