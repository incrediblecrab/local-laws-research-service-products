# fixtures

**Objective:** real Census rows, real New York filings and real records of New York's older index that reach every normalization, matching rule and check the tests exercise, small enough to commit.

**Inputs:** the Census Bureau's `govt_units_2022.ZIP`, at the SHA-256 pinned in `local_laws/census.py`; a New York snapshot `python -m local_laws harvest-ny` wrote; the Local Geohistory Project's `law-indexes-new-york-local-laws-v1.0.0.zip`, at the SHA-256 pinned in `local_laws/nyindex.py`.

**Files:**

- `make_census_sample.py`: writes both zips from the real file: `python tests/fixtures/make_census_sample.py path/to/govt_units_2022.ZIP`.
- `govt_units_sample.zip`: 50 governments and 1 dependent school system, copied value for value from the real file, with the columns the dataset leaves out blanked: the contact title and the street, city and ZIP of the mailing address (TITLE, ADDRESS1, ADDRESS2, CITY, ZIP and ZIP4).
- `org02_sample.zip`: a CG2200ORG02 computed from those rows in the real table's layout, so the build's check against it passes; the tests plant a wrong count to see it fail.
- `make_ny_sample.py`: writes the New York sample from a real snapshot: `python tests/fixtures/make_ny_sample.py path/to/ny-local-laws-snapshot.json.gz`. Its `CHOSEN` names each filing and the rule or sentence it is there for.
- `ny_snapshot_sample.json`: those filings, copied as the harvest kept them: public filing records (names, numbers, dates, titles and share links), with the snapshot's counts recomputed for the sample.
- `make_ny_index_sample.py`: writes the index sample from the real release: `python tests/fixtures/make_ny_index_sample.py path/to/law-indexes-new-york-local-laws-v1.0.0.zip`. Its `CHOSEN` names each line of the export and the rule or sentence it is there for.
- `ny_index_sample.zip`: those 14 lines of the export, with its header, and the State's records for them, copied byte for byte into a data file with the real header and the sample's record count, under the release's own folder name. The release is CC0 1.0.

Regenerating the Census zips changes their bytes, because they record when they were written, so the tests hash every zip as they run instead of pinning them. `make_ny_index_sample.py` writes a fixed date, and rewrites `ny_index_sample.zip` byte for byte.
