# fixtures

**Objective:** small real-source samples that reach every normalization, matching rule and source-change check the offline tests exercise.

**Inputs:** the Census 2022 Government Units file; a New York local-laws snapshot; the Local Geohistory Project's New York index release; Federal Register XML for BIA notices 2026-01899 and 2024-29005; FEMA `nation.csv`; and OpenFEMA `NfipCommunityStatusBook.parquet`.

**Files:** generator scripts `make_census_sample.py`, `make_ny_sample.py`, `make_ny_index_sample.py`, `make_tribes_sample.py` and `make_nfip_sample.py` rebuild the samples from full source files. `govt_units_sample.zip` and `org02_sample.zip` hold 50 governments and matching counts. `ny_snapshot_sample.json` holds selected public filing metadata. `ny_index_sample.zip` holds 14 index lines and matching State records. `tribes_notice_sample.xml` and `tribes_previous_sample.xml` preserve the notices' structure with selected entries. `nfip_nation_sample.csv` and `nfip_api_sample.parquet` hold 25 report communities plus three OpenFEMA-only records.

Regenerated Census zips have changing timestamps, so tests pin their hashes at runtime; the other generators write stable bytes.
