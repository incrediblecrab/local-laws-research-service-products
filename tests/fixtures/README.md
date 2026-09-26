# fixtures

**Objective:** real Census rows, real New York filings, real records of New York's older index, real entries of the list of federally recognized Tribes and real communities of FEMA's Community Status Book that reach every normalization, matching rule and check the tests exercise, small enough to commit.

**Inputs:** the Census Bureau's `govt_units_2022.ZIP`, at the SHA-256 pinned in `local_laws/census.py`; a New York snapshot `python -m local_laws harvest-ny` wrote; the Local Geohistory Project's `law-indexes-new-york-local-laws-v1.0.0.zip`, at the SHA-256 pinned in `local_laws/nyindex.py`; the XML of the Bureau of Indian Affairs' notices 2026-01899 and 2024-29005 from the Federal Register, at the SHA-256s pinned in `local_laws/tribes.py`; FEMA's `nation.csv` and OpenFEMA's `NfipCommunityStatusBook.parquet`, as `python -m local_laws harvest-nfip` read them.

**Files:**

- `make_census_sample.py`: writes both zips from the real file: `python tests/fixtures/make_census_sample.py path/to/govt_units_2022.ZIP`.
- `govt_units_sample.zip`: 50 governments and 1 dependent school system, copied value for value from the real file, with the columns the dataset leaves out blanked: the contact title and the street, city and ZIP of the mailing address (TITLE, ADDRESS1, ADDRESS2, CITY, ZIP and ZIP4).
- `org02_sample.zip`: a CG2200ORG02 computed from those rows in the real table's layout, so the build's check against it passes; the tests plant a wrong count to see it fail.
- `make_ny_sample.py`: writes the New York sample from a real snapshot: `python tests/fixtures/make_ny_sample.py path/to/ny-local-laws-snapshot.json.gz`. Its `CHOSEN` names each filing and the rule or sentence it is there for.
- `ny_snapshot_sample.json`: those filings, copied as the harvest kept them: public filing records (names, numbers, dates, titles and share links), with the snapshot's counts recomputed for the sample.
- `make_ny_index_sample.py`: writes the index sample from the real release: `python tests/fixtures/make_ny_index_sample.py path/to/law-indexes-new-york-local-laws-v1.0.0.zip`. Its `CHOSEN` names each line of the export and the rule or sentence it is there for.
- `ny_index_sample.zip`: those 14 lines of the export, with its header, and the State's records for them, copied byte for byte into a data file with the real header and the sample's record count, under the release's own folder name. The release is CC0 1.0.
- `make_tribes_sample.py`: writes both notice samples from the real XML: `python tests/fixtures/make_tribes_sample.py path/to/2026-01899.xml path/to/2024-29005.xml`. Its `SHARED`, `NOTICE_CHOSEN` and `PREVIOUS_CHOSEN` name each entry and the rule or sentence it is there for.
- `tribes_notice_sample.xml`, `tribes_previous_sample.xml`: each notice's XML with only those entries left in its lists, 19 and 18, and the count its summary states set to the entries kept less 2, 17 and 16, the gap the real notices have, so the samples reconcile as the real ones do. Everything else, the preamble, the headings and the page breaks inside entries, is the notice's own. The notices are works of the United States Government.
- `make_nfip_sample.py`: writes both NFIP samples from the real files: `python tests/fixtures/make_nfip_sample.py path/to/nation.csv path/to/NfipCommunityStatusBook.parquet`. Its `CHOSEN` names each community and the rule or sentence it is there for, and `API_ONLY` the three OpenFEMA records kept that the report does not list.
- `nfip_nation_sample.csv`: the report with only those 25 communities left, each with the lines the report prints beneath it, and the report's three headers, the one it repeats and the one that begins its part for communities not participating: 40 records, each copied byte for byte.
- `nfip_api_sample.parquet`: OpenFEMA's records for the same 25 communities and the three it holds that the report does not list, 28 records, in the file's order and schema. Both NFIP files are works of the United States Government.

Regenerating the Census zips changes their bytes, because they record when they were written, so the tests hash every zip as they run instead of pinning them. `make_ny_index_sample.py` writes a fixed date, and rewrites `ny_index_sample.zip` byte for byte; `make_tribes_sample.py` rewrites both notice samples byte for byte, and `make_nfip_sample.py` both NFIP samples.
