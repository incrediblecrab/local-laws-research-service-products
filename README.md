# us-local-laws

Builds [incrediblecrab/us-local-laws](https://huggingface.co/datasets/incrediblecrab/us-local-laws), a public Hugging Face dataset of the local governments of the United States, with a crosswalk to their ordinance text and, for New York, every local law filed with the State. [What it contains](#what-it-contains) describes the sources, and the dataset card gives the counts, the matching rules and the known gaps.

**Objective:** map who makes local law in the United States and how much of that law is openly published, using only sources whose terms allow automated use.

**Inputs:** the Census's 2022 Government Units List and table CG2200ORG02; LOCUS-v1; the New York Department of State's filing records and the State's older index of local laws; the Bureau of Indian Affairs' two latest Federal Register notices of federally recognized Tribes; and FEMA's Community Status Book report. [Sources and terms](#sources-and-terms) gives the terms each is used under and how the build reads it.

**Files:**

- [`local_laws/`](local_laws/README.md): the pipeline package
- [`tests/`](tests/README.md): offline tests
- [`checks/`](checks/README.md): one-off checks run by hand against a build, whose results the card states
- [`pyproject.toml`](pyproject.toml): pinned dependencies

**Try it:** `pip install .`, then `python -m local_laws harvest-ny --out /tmp/ny.json.gz`, `python -m local_laws harvest-nfip --out /tmp/nfip.zip`, `python -m local_laws run --local /tmp/out --ny-snapshot /tmp/ny.json.gz --nfip-snapshot /tmp/nfip.zip` and `python -m local_laws verify --local /tmp/out`. Without `--local`, `run` publishes, from a clean commit, with a write token in `HF_TOKEN`. [Running a build](#running-a-build) gives what each step downloads.

## What it contains

The dataset covers every local government in the Census Bureau's 2022 Census of Governments, with a crosswalk to the ordinance text in [LOCUS-v1](https://huggingface.co/datasets/LocalLaws/LOCUS-v1) and, for New York, every local law in the Department of State's [Local Laws search](https://dos.ny.gov/local-laws) and the State's older index of local laws, released under FOIL and [published by the Local Geohistory Project](https://doi.org/10.5281/zenodo.10446245), each matched where it can be to the government that filed it. Beside them it lists the Tribes the United States recognizes, from the Bureau of Indian Affairs' latest notice in the Federal Register, since the Census does not count tribal governments, and the communities in FEMA's [Community Status Book](https://www.fema.gov/flood-insurance/work-with-nfip/community-status-book), which records which communities participate in the National Flood Insurance Program, whose communities agree to adopt floodplain management regulations. The dataset card gives the counts, the matching rules and the known gaps.

## Sources and terms

- The Census's 2022 Government Units List and table CG2200ORG02 (public domain).
- LOCUS-v1 (CC BY-NC 4.0), of which only facts are published: jurisdiction names, row counts and type-word counts.
- The filing records the New York Department of State's search reads from its API, whose robots.txt is absent: names, numbers, dates, titles and share links, not the filed PDFs, whose host's robots.txt disallows all robots.
- The Local Geohistory Project's release of New York's older index (CC0 1.0).
- The XML of the Bureau of Indian Affairs' two latest notices of its list of federally recognized Tribes, works of the United States Government and not subject to copyright, read at the full-text address the Federal Register's API gives for each, since the site limits programmatic access to its API; its robots.txt allows that path.
- FEMA's Community Status Book report, `nation.csv`, a work of the United States Government, checked against OpenFEMA's copy of the book, whose terms the card quotes; fema.gov's robots.txt allows both paths and asks for 15 seconds between requests, which the build keeps.

The Census files, LOCUS, the index release and the two notices are pinned by SHA-256 or commit; New York's records and FEMA's report are each read once into a snapshot, checked, New York's against the API's own counts and FEMA's against OpenFEMA's copy, and built from.

## Running a build

The New York harvest makes about 1,500 requests to New York's API, one a second; the FEMA harvest makes 2 to fema.gov, 15 seconds apart, for 3.1 MB of report and 0.96 MB of OpenFEMA parquet; `run` without `--ny-snapshot` or `--nfip-snapshot` makes them itself. A run downloads 1.77 GB of LOCUS parquet to a temporary directory it then deletes, the 10 MB index release from Zenodo and the Bureau's two notices, about 100 KB, from the Federal Register; `verify` downloads the index release, the notices, CG2200ORG02 and FEMA's report again, to compare; it compares the report row for row only while fema.gov still serves the file the build read, since FEMA regenerates it. It runs by hand, never on a schedule: the Census files, LOCUS, the index and the notices are fixed releases, a person reviews a new release before its pin changes, and a new New York or FEMA reading is a new snapshot a person builds from.

## License

MIT. See [`LICENSE`](LICENSE).
