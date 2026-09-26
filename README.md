# local-laws-research-service-products

Builds [incrediblecrab/local-laws-research-service-products](https://huggingface.co/datasets/incrediblecrab/local-laws-research-service-products), a public Hugging Face dataset of every local government in the Census Bureau's 2022 Census of Governments, with a crosswalk to the ordinance text in [LOCUS-v1](https://huggingface.co/datasets/LocalLaws/LOCUS-v1) and, for New York, every local law in the Department of State's [Local Laws search](https://dos.ny.gov/local-laws) and the State's older index of local laws, released under FOIL and [published by the Local Geohistory Project](https://doi.org/10.5281/zenodo.10446245), each matched where it can be to the government that filed it. The dataset card gives the counts, the matching rules and the known gaps.

**Objective:** map who makes local law in the United States and how much of that law is openly published, using only sources whose terms allow automated use.

**Inputs:** the Census's 2022 Government Units List and table CG2200ORG02 (public domain); LOCUS-v1 (CC BY-NC 4.0), of which only facts are published: jurisdiction names, row counts and type-word counts; and the filing records the New York Department of State's search reads from its API, whose robots.txt is absent: names, numbers, dates, titles and share links, not the filed PDFs, whose host's robots.txt disallows all robots; and the Local Geohistory Project's release of New York's older index (CC0 1.0). The Census files, LOCUS and the index release are pinned by SHA-256 or commit; New York's records are read once into a snapshot, checked against the API's own counts, and built from.

**Files:**

- [`local_laws/`](local_laws/README.md): the pipeline package
- [`tests/`](tests/README.md): offline tests
- [`checks/`](checks/README.md): one-off checks run by hand against a build, whose results the card states
- `pyproject.toml`: pinned dependencies
- `LICENSE`: MIT

**Try it:** `pip install .`, then `python -m local_laws harvest-ny --out /tmp/ny.json.gz`, `python -m local_laws run --local /tmp/out --ny-snapshot /tmp/ny.json.gz` and `python -m local_laws verify --local /tmp/out`. The harvest makes about 1,500 requests to New York's API, one a second; `run` without `--ny-snapshot` makes them itself. A run downloads 1.77 GB of LOCUS parquet to a temporary directory it then deletes, and the 10 MB index release from Zenodo; `verify` downloads the index release and CG2200ORG02 again, to compare. Without `--local`, `run` publishes, from a clean commit, with a write token in `HF_TOKEN`. It runs by hand, never on a schedule: the Census files, LOCUS and the index are fixed releases, a person reviews a new release before its pin changes, and a new New York reading is a new snapshot a person builds from.
