# local-laws-research-service-products

Builds [incrediblecrab/local-laws-research-service-products](https://huggingface.co/datasets/incrediblecrab/local-laws-research-service-products), a public Hugging Face dataset of every local government in the Census Bureau's 2022 Census of Governments, with a crosswalk to the ordinance text in [LOCUS-v1](https://huggingface.co/datasets/LocalLaws/LOCUS-v1). The dataset card gives the counts, the matching rules and the known gaps.

**Objective:** map who makes local law in the United States and how much of that law is openly published, using only sources whose terms allow automated use.

**Inputs:** the Census's 2022 Government Units List and table CG2200ORG02 (public domain) and LOCUS-v1 (CC BY-NC 4.0), of which only facts are published: jurisdiction names, row counts and type-word counts. Each source is pinned by SHA-256 or commit.

**Files:**

- [`local_laws/`](local_laws/README.md): the pipeline package
- [`tests/`](tests/README.md): offline tests
- `pyproject.toml`: pinned dependencies
- `LICENSE`: MIT

**Try it:** `pip install .`, then `python -m local_laws run --local /tmp/out` and `python -m local_laws verify --local /tmp/out`. A run downloads 1.77 GB of LOCUS parquet to a temporary directory it then deletes. Without `--local`, `run` publishes, from a clean commit, with a write token in `HF_TOKEN`. It runs by hand, never on a schedule: the sources are fixed releases, and a person reviews a new release before its pin changes.
