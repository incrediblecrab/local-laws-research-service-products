# workflows

**Objective:** keep the Hugging Face dataset current with no personal device and no stored Hugging Face token. The workflow runs at 00:00 and 12:00 UTC.

**Inputs:** GitHub's OIDC token, which Hugging Face exchanges for a one-hour dataset-scoped write token when the Hub dataset has this repository, branch and `pipeline.yml` registered as a Trusted Publisher. No `HF_TOKEN` secret is used.

**Files:**

- [`pipeline.yml`](pipeline.yml): `probe` compares New York filing-year counts, FEMA file hashes and the published card with cheap reads. When only the card render changed, `card` updates it without a full build; otherwise `run` harvests New York and FEMA, builds from pinned sources, writes only if changed, verifies the published commit, then checks pinned sources for newer releases a person must review. `inactivity` fails after 50 days without a commit; it makes no keepalive commit because GitHub treats that as circumventing the 60-day schedule disablement policy.
