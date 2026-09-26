"""Renders the dataset card (README.md on the Hub) from the manifest alone, so it is committed with every manifest and never disagrees with it."""

from collections import Counter

from . import GITHUB, REPO_ID, census, locus
from .schema import TABLES

TITLE = "US Local Governments and Ordinance Coverage"
LOCUS_URL = f"https://huggingface.co/datasets/{locus.REPO_ID}"
LOCUS_PAPER = "https://arxiv.org/abs/2606.19334"
LOCUS_CITATION = f'Denis Peskoff, Joe Barrow, Christopher Vu and Diag Davenport, "Freeing the Law with LOCUS: A Local Ordinance Corpus for the United States", [arXiv:2606.19334]({LOCUS_PAPER}) (2026)'
TYPE_NAMES = {"county": "County", "municipal": "Municipal", "township": "Township", "special_district": "Special district", "school_district": "Independent school district"}
TECH_DOC = "https://www2.census.gov/programs-surveys/gus/datasets/2022/2022_gov_org_meth_tech_doc.pdf"
HOWARD_ESTIMATES = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/totals/sub-est2024.csv"
ICC_RELEASE = "https://www.iccsafe.org/about/periodicals-and-newsroom/industry-leaders-american-legal-publishing-and-general-code-unite-to-provide-communities-with-best-in-class-codification-services/"


def size_category(rows):
    for limit, label in ((1_000, "n<1K"), (10_000, "1K<n<10K"), (100_000, "10K<n<100K"), (1_000_000, "100K<n<1M")):
        if rows < limit:
            return label
    return "1M<n<10M"


def share(part, whole):
    return f"{part / whole:.1%}" if whole else "n/a"


def front_matter(total):
    lines = ["---", f"pretty_name: {TITLE}", "license: mit", "language:", "- en",
             "tags:", "- legal", "- government", "- local-government", "- ordinances", "- municipal-codes", "- census", "- united-states",
             "size_categories:", f"- {size_category(total)}", "configs:"]
    for index, (name, spec) in enumerate(TABLES.items()):
        lines += [f"- config_name: {name}", "  data_files:", "  - split: train", f"    path: {spec['file']}"]
        if index == 0:
            lines.append("  default: true")
    return lines + ["---", ""]


def coverage(stats):
    types, lx = stats["types"], stats["locus"]
    municipal, county, township = types["municipal"], types["county"], types["township"]
    years = Counter()
    for kind in locus.GENERAL_PURPOSE:
        years.update(types[kind]["population_years"])
    year, n = max(years.items(), key=lambda item: (item[1], item[0])) if years else ("none", 0)
    general = sum(years.values())
    lines = [
        "## Coverage",
        "",
        f"LOCUS has {lx['jurisdictions']:,} jurisdictions, and {lx['matched']:,} of them match one government here: {municipal['in_locus']:,} of the {municipal['governments']:,} municipal governments ({share(municipal['in_locus'], municipal['governments'])}), which hold {share(municipal['in_locus_population'], municipal['population'])} of the population the Census file gives for municipal governments; {county['in_locus']:,} of the {county['governments']:,} county governments ({share(county['in_locus'], county['governments'])}), holding {share(county['in_locus_population'], county['population'])} of county population; and {township['in_locus']:,} of the {township['governments']:,} township governments ({share(township['in_locus'], township['governments'])}).",
        "",
        "| Type | Governments | Active | Web address reported | In LOCUS | Population | Share of population in LOCUS |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for kind in census.TYPES:
        entry = types[kind]
        population = f"{entry['population']:,}" if "population" in entry else ""
        covered = share(entry["in_locus_population"], entry["population"]) if "population" in entry else ""
        lines.append(f"| {TYPE_NAMES[kind]} | {entry['governments']:,} | {entry['active']:,} | {entry['with_web_address']:,} | {entry['in_locus']:,} | {population} | {covered} |")
    totals = {key: sum(types[kind][key] for kind in census.TYPES) for key in ("governments", "active", "with_web_address", "in_locus")}
    lines += [
        f"| All | {totals['governments']:,} | {totals['active']:,} | {totals['with_web_address']:,} | {totals['in_locus']:,} | | |",
        "",
        f"Population is the Census Bureau's estimate for each county, municipal and township government, for {year} for {n:,} of the {general:,} ({share(n, general)}). Shares compare governments of one type only, and populations are never added across types, because the areas overlap: a municipality usually lies within a county, and in some states within a township too. LOCUS covers counties, municipalities and townships; special districts and independent school districts are here because the Census counts them as local governments. Active counts governments the Census does not mark dormant.",
        "",
    ]
    return lines


def use():
    base = f"hf://datasets/{REPO_ID}/data"
    return [
        "## Use",
        "",
        "```python",
        "from datasets import load_dataset",
        "",
        f'governments = load_dataset("{REPO_ID}", "governments", split="train")',
        f'crosswalk = load_dataset("{REPO_ID}", "locus_crosswalk", split="train")',
        "```",
        "",
        "```sql",
        "-- DuckDB, straight from the Hub: Vermont's cities and towns, largest first, with the rows LOCUS holds for each",
        "SELECT g.name, g.government_type, g.county_name, g.population, c.locus_rows",
        f"FROM '{base}/governments.parquet' AS g",
        f"LEFT JOIN '{base}/locus_crosswalk.parquet' AS c USING (census_id)",
        "WHERE g.state = 'VT' AND g.government_type IN ('municipal', 'township')",
        "ORDER BY g.population DESC NULLS LAST;",
        "```",
        "",
        "```sql",
        "-- The ordinance text is in LOCUS (CC BY-NC 4.0). Find a government's LOCUS name here, then read its sections there, at the revision the crosswalk was built from.",
        f"SELECT locus_state, locus_jurisdiction_type, locus_name FROM '{base}/locus_crosswalk.parquet' WHERE census_id = '135964';",
        f"SELECT header, topic FROM 'hf://datasets/{locus.REPO_ID}@{locus.REVISION}/data/*.parquet' WHERE state = 'vt' AND source_jurisdiction_type = 'cities' AND city = 'barre' LIMIT 20;",
        "```",
        "",
    ]


def files(manifest):
    entries = manifest["files"]
    governments, crosswalk = (entries[TABLES[name]["file"]] for name in ("governments", "locus_crosswalk"))
    return [
        "## Files",
        "",
        f"- `{TABLES['governments']['file']}`: one row per government, {governments['rows']:,} rows, sorted by `census_id`.",
        f"- `{TABLES['locus_crosswalk']['file']}`: one row per LOCUS jurisdiction, {crosswalk['rows']:,} rows, sorted by state, type and name.",
        "- `manifest.json`: each source's URL and SHA-256 or commit, each file's rows and SHA-256, every normalization the build applied with its count, the counts on this card, and the pipeline version and commit that built them.",
        "",
        "## Schema",
        "",
    ] + [line for name, spec in TABLES.items() for line in schema_table(name, spec)]


def schema_table(name, spec):
    lines = [f"### `{name}`", "", "| Column | Type | Description |", "|---|---|---|"]
    lines += [f"| `{column.name}` | {column.type} | {spec['docs'][column.name]} |" for column in spec["schema"]]
    return lines + [""]


def matching(manifest):
    lx = manifest["stats"]["locus"]
    matches = lx["matches"]
    matched = lx["matched"]
    fits = sum(entry["text_fits"] for entry in matches.values())
    differs = lx["text_differs"]
    unchecked = sum(entry["text_unchecked"] for name, entry in matches.items() if name in locus.MATCHED)
    lines = [
        "## Matching",
        "",
        f"LOCUS identifies a jurisdiction by state and a lowercase name, such as `batavia_city` or `saint_tammany_parish`, with no Census or FIPS code. The build matches each name to the Census file's county, municipal and township governments with the rules below, tried in this order. It then reads all {lx['rows']:,} rows of LOCUS's text and counts how the text writes each candidate's name with a type word, such as \"Town of Barre\" or \"Barre City\". Where several governments share a name, that count chooses among them (`text_type`, `text_county`); for every match it is a check (`text_fits`).",
        "",
        "| `match` | Rule | Jurisdictions | LOCUS rows | Text fits | Text differs | Not checked |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for name, doc in locus.MATCH_DOCS.items():
        entry = matches[name]
        lines.append(f"| `{name}` | {doc} | {entry['jurisdictions']:,} | {entry['rows']:,} | {entry['text_fits']:,} | {entry['text_differs']:,} | {entry['text_unchecked']:,} |")
    lines += ["", f"The text fits the matched government's Census title for {fits:,} of the {matched:,} matches ({share(fits, matched)})."]
    reviewed = locus.REVIEWED_DIFFERS if manifest["sources"]["locus"]["revision"] == locus.REVISION else frozenset()
    unread = sorted(set(differs) - reviewed)
    if differs and not unread:
        lines[-1] += f" It differs for {len(differs):,}. Each of those was read by hand against LOCUS's text on September 25, 2026, and each is the government LOCUS means, named with another word" + (f": {locus.REVIEW_FINDING}." if set(differs) == reviewed else ".")
    elif differs:
        lines[-1] += f" It differs for {len(differs):,}, and {len(unread):,} of those {'has' if len(unread) == 1 else 'have'} not been read by hand: {', '.join(f'`{name}`' for name in unread)}."
    silent = lx["matched_without_mentions"]
    few = lx["matched_few_mentions"]
    untitled = unchecked - few
    reasons = f"because it writes the name with a type word fewer than {locus.MIN_MENTIONS} times" if not untitled else f"{few:,} because it writes the name with a type word fewer than {locus.MIN_MENTIONS} times and {untitled:,} because the government's Census title has no type word to check"
    lines += [
        "",
        f"The text does not check {unchecked:,} matches, {reasons}. It never names {len(silent):,} of them that way: {', '.join(f'`{name}`' for name in silent) or 'none'}. That happens when the text does not use the Census name, as with consolidated governments such as METROPOLITAN GOVERNMENT OF NASHVILLE-DAVIDSON COUNTY, or when the text may not be about the place LOCUS files it under.",
        "",
        f"The {len(locus.ALIASES)} aliases, each checked by hand against the Census file and LOCUS's text. The build stops if the Census name at an alias's `census_id` changes or LOCUS drops the jurisdiction.",
        "",
        "| LOCUS jurisdiction | Census government |",
        "|---|---|",
    ]
    lines += [f"| `{state}/{name}` | {census_name} (`{census_id}`) |" for (state, _, name), (census_id, census_name) in locus.ALIASES.items()]
    return lines + [""]


def codifiers(manifest):
    lx = manifest["stats"]["locus"]
    return [
        "## Where local law is published",
        "",
        "The Law Library of Congress's guide to municipal codes says \"there is no one singular clearinghouse for all municipal codes\" ([Municipal Codes: A Beginner's Guide](https://guides.loc.gov/municipal-codes)). A few private codifiers publish many governments' codes online, for the governments that hire them:",
        "",
        "- Municode, owned by CivicPlus. When CivicPlus announced that it had acquired Municode, Municode hosted \"over 3,900 local government codes and 190,000 individual ordinances\" ([CivicPlus](https://www.civicplus.com/news/nn/civicplus-acquires-municode/)).",
        f"- ICC Code Solutions, the International Code Council's union of General Code (eCode360) and American Legal Publishing, which \"now supports more than 7,000 communities across 47 states, Canada and more than a dozen tribal territories\" ([ICC, July 16, 2026]({ICC_RELEASE})).",
        "",
        "This dataset does not collect from them, because their terms forbid automated collection. The [ICC's Terms of Use](https://www.iccsafe.org/about/terms-of-use/) (last revised May 4, 2023) name General Code and American Legal Publishing among the companies they cover and eCode 360 among their E-Content, and say in §4:",
        "",
        "> the licenses ICC grants to use our E-Content, as set forth in these Terms of Use and applicable E-Content Terms, do not include any: ... or use of data mining, robots, or similar data gathering and extraction tools with any Service or E-Content. Please contact us at license@iccsafe.org to discuss additional licenses for further uses.",
        "",
        "The [CivicPlus Terms of Use](https://www.civicplus.help/legal-center/docs/civicplus-terms-of-use) (last revised March 20, 2026) list among prohibited uses, in §7:",
        "",
        "> Use or launch any automated system, including without limitation, \"robots,\" \"spiders,\" or \"offline readers,\" that accesses the Site or any Solution in a manner that sends more request messages to the CivicPlus servers in a given period of time than a human can reasonably produce in the same period by using a conventional on-line web browser, unless specifically permitted by CivicPlus and in accordance with any specific rate or use limitations;",
        "",
        "Their §8(b) forbids anyone to \"engage in Automated Scraping of any CivicPlus Materials or Authority Data for AI Training Purposes\", and §8(a) defines Authority Data as materials provided \"by, for, or on behalf of any government entity\" through CivicPlus's services, \"whether such materials are publicly accessible or non-public\".",
        "",
        "On September 25, 2026, eCode360 and American Legal Publishing's code library also answered plain HTTP requests with a Cloudflare challenge (HTTP 403 with `cf-mitigated: challenge`); the pipeline treats a challenge as a stop, never as something to get past. Which codifier, if any, publishes a government's code is therefore not in this dataset.",
        "",
        f"LOCUS's paper describes a raw corpus of codes from 9,239 cities and counties, \"available for release to researchers\" ([arXiv:2606.19334]({LOCUS_PAPER})); the public LOCUS-v1 has {lx['jurisdictions']:,} jurisdictions.",
        "",
    ]


def gaps(manifest):
    stats = manifest["stats"]
    types, lx = stats["types"], stats["locus"]
    notes = manifest["sources"]["census_governments"]["normalization"]
    dormant = sum(entry["governments"] - entry["active"] for entry in types.values())
    web = sum(entry["with_web_address"] for entry in types.values())
    lines = [
        "## Known gaps",
        "",
        "- Tribal governments are not rows. Besides the federal government and the 50 state governments, the Census Bureau \"recognizes five basic types of local governments\" ([technical documentation](" + TECH_DOC + ")), the five in `government_type`, and tribal governments are not among them. Nor are the territories' governments: the Census file covers the 50 states and the District of Columbia.",
        f"- Dependent public school systems, {notes.get('dependent_school_systems_skipped', 0):,} in the Census file, are left out, as the Census leaves them out of its count: they \"are classified as agencies of other state, county, municipal, or town or township governments and are not counted as separate governments\" ([technical documentation]({TECH_DOC})).",
    ]
    if "ks/howard" in lx["ambiguous"]:
        lines.append(f"- The Census file can omit an active government. Howard, Kansas, in Elk County, is an active incorporated city in the Census's own [Vintage 2024 population estimates]({HOWARD_ESTIMATES}) (561 people in 2024), and LOCUS has its code as `ks/howard`, but it is not in the 2022 file; so `ks/howard` is `ambiguous` between the two townships named Howard, neither of whose titles its text fits.")
    others = [name for name in lx["ambiguous"] if name != "ks/howard"] + lx["unmatched"]
    if others:
        lines.append(f"- {len(others):,} other LOCUS {'jurisdiction is' if len(others) == 1 else 'jurisdictions are'} `ambiguous` or `unmatched`: {', '.join(f'`{name}`' for name in others)}.")
    lines += [
        "- The Census of Governments is for 2022: a government formed, merged or dissolved since then is not reflected.",
        f"- {dormant:,} governments the Census marks dormant are rows, because the Census still counts them.",
        f"- Web addresses are as reported to the Census, which says it did minimal quality control on them; they are not checked here. {web:,} of the {stats['governments']:,} governments reported one. The Census file's mailing addresses and contact titles are left out: the map does not need them, and a few of the addresses name a person.",
        "- LOCUS's text is not here, and LOCUS names are matched to governments by name, with the precision described under Matching. Which governments' codes the codifiers hold is not known here; see Where local law is published.",
        "",
    ]
    return lines


def sources(manifest):
    census_source, org02, locus_source = (manifest["sources"][key] for key in ("census_governments", "census_org02", "locus"))
    return [
        "## Sources",
        "",
        "| Source | Pinned as | Used for |",
        "|---|---|---|",
        f"| [2022 Census of Governments, Government Units List]({census_source['url']}) | SHA-256 `{census_source['sha256']}` | `governments`: {census_source['rows']:,} rows |",
        f"| [CG2200ORG02, Local Governments by Type and State, 2022]({org02['url']}) | SHA-256 `{org02['sha256']}` | Checking `governments`: {org02['counts_compared']:,} counts by state and type compared, {org02['mismatches']:,} differ |",
        f"| [LOCUS-v1]({LOCUS_URL}) | commit `{locus_source['revision']}` | `locus_crosswalk`: {locus_source['rows']:,} rows read |",
        "",
        "`python -m local_laws run` downloads each source at its pinned version, stops if its bytes or its counts are not what the pipeline was checked against, and commits both tables, `manifest.json` and this card in one commit. It runs by hand, not on a schedule: the sources are fixed releases, and a new release needs a person to review it before its pin changes. `python -m local_laws verify` re-reads the published files and checks them against `manifest.json`, the Census's table and LOCUS's card.",
        "",
    ]


def by_state(stats):
    lines = ["## By state", "", "| State | County | Municipal | Township | Special district | Independent school district | All | In LOCUS |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for state, entry in stats["states"].items():
        lines.append(f"| {state} | " + " | ".join(f"{entry[kind]:,}" for kind in census.TYPES) + f" | {sum(entry[kind] for kind in census.TYPES):,} | {entry['in_locus']:,} |")
    return lines + [""]


def license_section():
    return [
        "## License",
        "",
        "MIT, for the compilation and the code that builds it.",
        "",
        "- The Census files are works of the United States Government and are not subject to copyright in the United States ([17 U.S.C. § 105](https://www.copyright.gov/title17/92chap1.html#105)).",
        f"- The crosswalk records facts about LOCUS-v1, namely its jurisdiction names, their row counts and counts of type words in their text, and holds none of its text. LOCUS licenses its text [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), which anyone using that text must follow. Cite LOCUS as {LOCUS_CITATION}.",
        "",
    ]


def render(manifest):
    stats = manifest["stats"]
    lines = front_matter(stats["governments"])
    lines += [
        f"# {TITLE}",
        "",
        f"Every local government the Census Bureau's 2022 Census of Governments counts, {stats['governments']:,} of them in the 50 states and the District of Columbia, and which of them have ordinance text in [LOCUS]({LOCUS_URL}), a public corpus of local ordinances. It maps who makes local law and how much of that law LOCUS holds; the laws themselves are not here.",
        "",
        f"Every row is built by code from sources pinned by SHA-256 or commit, which the build checks against each other. The only hand-made input to the rows is {len(locus.ALIASES)} name aliases, listed under Matching. The pipeline and its tests are in [{GITHUB.removeprefix('https://')}]({GITHUB}), and this card is rendered from `manifest.json` in the same commit.",
        "",
    ]
    lines += coverage(stats) + use() + files(manifest) + matching(manifest) + codifiers(manifest) + gaps(manifest) + sources(manifest) + license_section() + by_state(stats)
    return "\n".join(lines)
