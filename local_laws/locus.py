"""A crosswalk from LOCUS v1.0, a public dataset of local ordinance text, to the governments in the Census file.
It records which jurisdictions LOCUS covers, how many rows each has, and how its text names each government. It holds none of the text, which LOCUS licenses CC BY-NC 4.0."""

import re
from collections import Counter, defaultdict

import pyarrow.parquet as pq

from .census import SourceChanged

REPO_ID = "LocalLaws/LOCUS-v1"
# The dataset's head commit on September 25, 2026 (last modified June 20, 2026). Reading a pinned commit keeps the crosswalk reproducible.
REVISION = "4cee954ca8ad8e31cb0502dff6682c87b74b4302"
LICENSE = "cc-by-nc-4.0"
COLUMNS = ["state", "source_jurisdiction_type", "city", "county"]

# Census name titles, longest first so that CITY AND COUNTY OF wins over CITY OF.
PREFIXES = ("CITY AND COUNTY OF", "CITY AND BOROUGH OF", "CONSOLIDATED GOVERNMENT OF", "METROPOLITAN GOVERNMENT OF", "METRO GOVERNMENT OF", "UNIFIED GOVERNMENT OF",
            "URBAN COUNTY GOVERNMENT OF", "METRO TOWNSHIP OF", "CHARTER TOWNSHIP OF", "CIVIL TOWNSHIP OF", "CITY-PARISH OF", "CITY OF", "TOWN OF", "VILLAGE OF",
            "BOROUGH OF", "TOWNSHIP OF", "PLANTATION OF", "COUNTY OF", "PARISH OF", "MUNICIPALITY OF", "CORPORATION OF")
# Titles of municipal governments that are also their county: the Census counts these as municipal, with no county government beside them.
CONSOLIDATED = {"CITY AND COUNTY OF", "CITY AND BOROUGH OF", "CONSOLIDATED GOVERNMENT OF", "METROPOLITAN GOVERNMENT OF", "METRO GOVERNMENT OF", "UNIFIED GOVERNMENT OF",
                "URBAN COUNTY GOVERNMENT OF", "CITY-PARISH OF", "COUNTY OF", "MUNICIPALITY OF"}
# The Census titles each type word in a LOCUS name stands for.
KINDS = {
    "city": {"CITY OF", "CITY AND COUNTY OF", "CITY AND BOROUGH OF", "CITY-PARISH OF"},
    "town": {"TOWN OF"},
    "village": {"VILLAGE OF"},
    "borough": {"BOROUGH OF", "CITY AND BOROUGH OF"},
    "township": {"TOWNSHIP OF", "CHARTER TOWNSHIP OF", "CIVIL TOWNSHIP OF", "METRO TOWNSHIP OF"},
    "plantation": {"PLANTATION OF"},
}
MUNICIPAL_KINDS = ("city", "town", "village", "borough")
CITY_SUFFIXES = (("chrtr_township", "township"), ("charter_township", "township"), ("chartertownship", "township"), ("township", "township"), ("twp", "township"),
                 ("town", "town"), ("city", "city"), ("village", "village"), ("borough", "borough"), ("plantation", "plantation"))
# Suffixes LOCUS sometimes writes without an underscore (newyorkcity, conemaughtwp, bedfordbor). "town" is left out: too many names end in it (georgetown).
GLUED_SUFFIXES = (("township", "township"), ("twp", "township"), ("city", "city"), ("borough", "borough"), ("bor", "borough"))
COUNTY_PREFIXES = ("unified_government_of_", "city_and_county_of_", "city_and_borough_of_", "city_borough_of_", "borough_of_", "county_of_", "parish_of_", "municipality_of_")
COUNTY_SUFFIXES = ("_parish_police_jury", "_parish_council", "_parish_government", "_county_commission", "_county_consolidated_government", "_county_-_unified_government",
                   "_county_unified_government", "_consolidated_government", "_county_government", "_county", "_parish", "_borough", "_census_area", "_municipality")
# The Census mostly writes ST, MOUNT and FORT; LOCUS mostly writes saint and mount, sometimes glued to the next word (mountpulaski). Both sides are reduced to st, mt and ft.
SHORT = (("saint", "st"), ("mount", "mt"), ("fort", "ft"))
TRAILING_TYPES = ("CITY", "TOWN", "VILLAGE", "BOROUGH", "TOWNSHIP")
# LOCUS writes a county after some names: thornapple_township,_(barry_co.), porter_township,_(van_buren_county), harrison,_calumet_co.
COUNTY_HINT = re.compile(r",_?\(?([a-z_.' -]+?)_(?:co\.?|county)\)?$")
GENERAL_PURPOSE = ("county", "municipal", "township")
# LOCUS jurisdictions whose names no rule below reads, each checked by hand against the Census file and LOCUS's text on September 25, 2026: (state, LOCUS type, LOCUS name) -> (census_id, Census name).
# aurel and aust are cut-off names: their text calls itself the City of Aurelia and the City of Austin (Scott County).
# The build stops if the Census name at that census_id changes or LOCUS no longer has the jurisdiction.
ALIASES = {
    ("in", "counties", "indianapolis_marion_county"): ("207957", "CITY OF INDIANAPOLIS"),
    ("ga", "counties", "unified_government_of_georgetown-quitman_county_commission"): ("161958", "UNIFIED GOVERNMENT OF GEORGETOWN AND QUITMAN COUNTY"),
    ("ky", "cities", "lexingtonfayetteco"): ("165831", "URBAN COUNTY GOVERNMENT OF LEXINGTON-FAYETTE"),
    ("la", "counties", "lafayette_city-parish_consolidated_government"): ("166076", "CITY-PARISH OF LAFAYETTE"),
    ("tn", "counties", "metro_government_of_nashville_and_davidson_county"): ("175728", "METROPOLITAN GOVERNMENT OF NASHVILLE-DAVIDSON COUNTY"),
    ("ky", "cities", "middlesboro"): ("127573", "CITY OF MIDDLESBOROUGH"),
    ("ny", "cities", "hempstead_bzo_town"): ("170895", "TOWN OF HEMPSTEAD"),
    ("ia", "cities", "aurel"): ("164335", "CITY OF AURELIA"),
    ("in", "cities", "aust"): ("126082", "CITY OF AUSTIN"),
}

# The type words looked for in the text, and the ones each Census title accepts.
TEXT_TYPES = ("city", "town", "village", "borough", "township", "plantation", "county", "parish", "municipality")
TITLE_WORDS = {title: {kind for kind, titles in KINDS.items() if title in titles} for title in PREFIXES}
TITLE_WORDS.update({"COUNTY OF": {"county"}, "PARISH OF": {"parish"}, "MUNICIPALITY OF": {"municipality", "borough"}, "CORPORATION OF": {"city", "town"}})
CONSOLIDATED_WORDS = {"city", "county", "parish", "borough", "municipality", "town"}
# Text evidence picks one of several same-name governments only when it is lopsided: at least MIN_MENTIONS mentions, and at least MIN_SHARE of those that fit a candidate.
MIN_MENTIONS = 3
MIN_SHARE = 2 / 3
# What each match value means, in the order the card lists them.
MATCH_DOCS = {
    "alias": "Listed by hand in `ALIASES` in `local_laws/locus.py`, after reading the Census file and the jurisdiction's text: names no rule reads, such as `indianapolis_marion_county` for CITY OF INDIANAPOLIS, or the cut-off `aurel` for CITY OF AURELIA",
    "name": "The name alone fits one government in the state: a municipality or township for LOCUS's `cities`, a county for its `counties`",
    "name_county": "The name and the county LOCUS writes after it fit one government (`harrison,_calumet_co`: VILLAGE OF HARRISON, in Calumet County)",
    "name_type": "The name without its type word fits one government with that title (`batavia_city`: CITY OF BATAVIA, not TOWN OF BATAVIA)",
    "name_type_county": "The name, its type word and the county after it fit one government (`bedford_township,_(monroe_co.)`: TOWNSHIP OF BEDFORD, in Monroe County)",
    "name_type_differs": "No government of the name has the title LOCUS's type word gives, and exactly one municipality has the name under another title (`barnstable_town`: CITY OF BARNSTABLE)",
    "name_variant": "Fits one government only once a second title or a trailing type word is dropped from the Census name (`creede`: TOWN OF CITY OF CREEDE)",
    "consolidated": "A `counties` name fits one consolidated city-county, which the Census counts as a municipal government (`macon-bibb_county`: COUNTY OF MACON-BIBB)",
    "text_type": "Several governments share the name, and the type word the text writes with it fits exactly one of them (`vt/barre`: the text says Town of Barre, so TOWN OF BARRE rather than CITY OF BARRE). The word needs at least 3 mentions and two-thirds of the mentions that fit any candidate",
    "text_county": "Several same-name governments in different counties, and the text names one of those counties in at least 3 mentions and two-thirds of all mentions of them (`nj/franklin_township`: Gloucester County)",
    "municipal_preferred": "The name fits one municipality and one or more townships, the text does not settle which, and the municipality is taken: the least certain match",
    "ambiguous": "Several governments fit and neither the name nor the text settles which, so `census_id` is null and `candidates` lists them",
    "unmatched": "No government in the Census file fits",
}
MATCHES = tuple(MATCH_DOCS)
MATCHED = MATCHES[:-2]
# The matches that choose among several same-name governments, whose candidates are kept.
POOLED = ("text_type", "text_county", "municipal_preferred", "ambiguous")
# The matches at REVISION whose text most often writes another type word than the Census title's, each read by hand against LOCUS's text on September 25, 2026, with what the reading found.
# The card repeats REVIEW_FINDING only while the published matches that differ are exactly these.
REVIEWED_DIFFERS = frozenset({
    "ak/skagway_borough", "al/moundville", "co/creede", "co/lake_city", "co/orchard_city", "fl/cross_city", "ia/corydon", "la/winnsboro", "ma/barnstable_town",
    "ma/greenfield_town", "md/ocean_city", "ne/bennet", "ne/franklin", "nm/silver_city", "oh/newlexington", "ok/lexington", "ok/seiling", "or/monmouth",
    "sc/lexington", "sc/manning", "tx/bandera", "tx/bigsandy", "tx/canadian", "tx/clarksville_city", "tx/clyde", "tx/henrietta", "tx/livingston",
    "tx/mount_vernon", "tx/panhandle", "tx/spearman", "tx/woodsboro", "tx/woodville", "va/gate_city", "wa/republic", "wv/ceredo", "wy/newcastle",
})
REVIEW_FINDING = ("25 towns and villages whose code says City of (11 of them in Texas), 8 cities whose code says Town of (Barnstable and Greenfield, Massachusetts, among them), "
                  "Skagway, whose code says Municipality, and 2 codes that name their county more often than themselves (Lexington, South Carolina, and Franklin, Nebraska)")


def latest():
    """The Hub's current HEAD for LOCUS-v1, for the scheduled stale-pin check. The build still reads REVISION until a person reviews a newer release."""
    from huggingface_hub import HfApi

    info = HfApi(token=False).dataset_info(REPO_ID)
    modified = getattr(info, "last_modified", None)
    return {"repo_id": REPO_ID, "sha": info.sha, "last_modified": modified.isoformat() if modified else None, "pinned": REVISION}


def stated_rows(api=None):
    """The row count LOCUS's card states at REVISION. Raises SourceChanged if the card's license is not the one the dataset card was written for."""
    from huggingface_hub import HfApi

    api = api or HfApi(token=False)
    card = api.dataset_info(REPO_ID, revision=REVISION).card_data.to_dict()
    if card.get("license") != LICENSE:
        raise SourceChanged(f"LOCUS's license is {card.get('license')!r}, not {LICENSE}: the card's License section needs review")
    return sum(split["num_examples"] for split in card["dataset_info"]["splits"])


def download(directory, api=None):
    """Download LOCUS's parquet files at REVISION into directory. Returns their paths and the row count LOCUS's card states."""
    from huggingface_hub import HfApi

    api = api or HfApi(token=False)
    stated = stated_rows(api)
    files = sorted(path for path in api.list_repo_files(REPO_ID, repo_type="dataset", revision=REVISION) if path.startswith("data/") and path.endswith(".parquet"))
    if not files:
        raise SourceChanged(f"no parquet files in {REPO_ID} at {REVISION}")
    paths = [api.hf_hub_download(REPO_ID, path, repo_type="dataset", revision=REVISION, local_dir=directory) for path in files]
    return paths, stated


def jurisdiction_key(state, kind, city, county):
    name = city if kind == "cities" else county if kind == "counties" else None
    if not name or not state:
        raise SourceChanged(f"LOCUS row without a jurisdiction: {state!r} {kind!r} {city!r} {county!r}")
    return state, kind, name


def jurisdictions(paths):
    """[{locus_state, locus_jurisdiction_type, locus_name, locus_rows}] for every jurisdiction in the files, reading only the identifying columns."""
    counts = Counter()
    for path in paths:
        table = pq.read_table(path, columns=COLUMNS)
        for row in table.group_by(COLUMNS).aggregate([([], "count_all")]).to_pylist():
            counts[jurisdiction_key(row["state"], row["source_jurisdiction_type"], row["city"], row["county"])] += row["count_all"]
    return [{"locus_state": state, "locus_jurisdiction_type": kind, "locus_name": name, "locus_rows": rows} for (state, kind, name), rows in sorted(counts.items())]


def key(text):
    words = re.findall(r"[a-z0-9]+", text.lower().replace("&", " and ").replace("'", "").replace("\u2019", ""))
    joined = "".join(words)
    for long, short in SHORT:
        joined = joined.replace(long, short)
    return joined


def split_title(name):
    """COUNTY OF ST TAMMANY -> ("COUNTY OF", "ST TAMMANY"); parenthetical notes such as (BRISCOE) are dropped."""
    upper = re.sub(r"\s*\([^)]*\)", "", " ".join(name.upper().split()))
    for prefix in PREFIXES:
        if upper.startswith(prefix + " "):
            return prefix, upper[len(prefix) + 1:]
    return "", upper


def bare_words(rest):
    """The name without a second title or a trailing type word, for irregular Census names: CITY OF CREEDE -> [CREEDE], MT JULIET CITY -> [MT, JULIET]."""
    for prefix in PREFIXES:
        if rest.startswith(prefix + " "):
            rest = rest[len(prefix) + 1:]
            break
    words = rest.split()
    if len(words) > 1 and words[-1] in TRAILING_TYPES:
        words = words[:-1]
    return words


def title_and_core(name):
    """COUNTY OF ST TAMMANY -> ("COUNTY OF", "sttammany", []). The list holds variant readings of irregular names, used only when nothing else fits:
    TOWN OF CITY OF CREEDE -> creede, CITY OF MT JULIET CITY -> mtjuliet."""
    title, rest = split_title(name)
    core = key(rest)
    bare = key(" ".join(bare_words(rest)))
    return title, core, [bare] if bare != core else []


def title_words(entry):
    """The type words that fit a government's Census title, such as {"town"} for TOWN OF BARRE."""
    if entry["type"] == "municipal" and entry["title"] in CONSOLIDATED:
        return CONSOLIDATED_WORDS
    return TITLE_WORDS.get(entry["title"], set())


class Index:
    """General-purpose governments by (state, core name); counties and consolidated governments also by their county area name."""

    def __init__(self, governments):
        self.by_core = defaultdict(list)
        self.by_variant = defaultdict(list)
        self.by_county_name = defaultdict(list)
        self.entries = {}
        self.names = {}
        for row in governments:
            self.names[row["census_id"]] = row["name"]
            if row["government_type"] not in GENERAL_PURPOSE:
                continue
            title, core, variants = title_and_core(row["name"])
            entry = {"census_id": row["census_id"], "type": row["government_type"], "title": title, "county": key(row["county_name"] or ""),
                     "name": row["name"], "county_name": row["county_name"]}
            self.entries[row["census_id"]] = entry
            state = row["state"].lower()
            self.by_core[(state, core)].append(entry)
            for variant in variants:
                self.by_variant[(state, variant)].append(entry)
            if row["government_type"] == "county" or title in CONSOLIDATED:
                self.by_county_name[(state, entry["county"])].append(entry)


def city_readings(name):
    """The ways to read a LOCUS city name, most literal first, as (core, type word or None), and the county it names, if any."""
    name = name.strip("_")
    hint = None
    found = COUNTY_HINT.search(name)
    if found:
        hint, name = key(found.group(1)), name[:found.start()]
    readings = [(key(name), None)]
    for suffix, kind in CITY_SUFFIXES:
        if name.endswith("_" + suffix) and len(name) > len(suffix) + 1:
            readings.append((key(name[:-len(suffix) - 1]), kind))
            break
    whole = key(name)
    for suffix, kind in GLUED_SUFFIXES:
        if whole.endswith(suffix) and len(whole) > len(suffix):
            readings.append((whole[:-len(suffix)], kind))
            break
    return readings, hint


def match_city(index, state, name):
    """(census_id or None, match, candidates). Candidates are the same-name governments a choice was made among, or that remain ambiguous."""
    readings, hint = city_readings(name)
    ambiguous = []
    for table, variant in ((index.by_core, False), (index.by_variant, True)):
        for core, kind in readings:
            found = [entry for entry in table.get((state, core), []) if entry["type"] in ("municipal", "township")]
            if hint:
                found = [entry for entry in found if entry["county"] == hint]
            pool = [entry for entry in found if entry["title"] in KINDS[kind]] if kind else found
            if len(pool) == 1:
                method = "name_variant" if variant else "name" + ("_type" if kind else "") + ("_county" if hint else "")
                return pool[0]["census_id"], method, []
            municipal = [entry for entry in pool if entry["type"] == "municipal"]
            if len(pool) > 1 and kind is None and len(municipal) == 1:
                return municipal[0]["census_id"], "municipal_preferred", sorted(entry["census_id"] for entry in pool)
            if not pool and kind in MUNICIPAL_KINDS:
                municipal = [entry for entry in found if entry["type"] == "municipal"]
                if len(municipal) == 1:
                    return municipal[0]["census_id"], "name_variant" if variant else "name_type_differs", []
            if len(pool) > 1 and not ambiguous:
                ambiguous = sorted(entry["census_id"] for entry in pool)
    return (None, "ambiguous", ambiguous) if ambiguous else (None, "unmatched", [])


def county_readings(name):
    stripped = name.strip("_")
    readings = [key(stripped)]
    for prefix in COUNTY_PREFIXES:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):]
            break
    for suffix in COUNTY_SUFFIXES:
        if stripped.endswith(suffix):
            stripped = stripped[:-len(suffix)]
            break
    for reading in (key(stripped), key(stripped).removesuffix("county")):
        if reading and reading not in readings:
            readings.append(reading)
    return readings


def match_county(index, state, name):
    ambiguous = []
    for core in county_readings(name):
        pool = {}
        for entry in index.by_core.get((state, core), []) + index.by_county_name.get((state, core), []):
            if entry["type"] == "county" or (entry["type"] == "municipal" and entry["title"] in CONSOLIDATED):
                pool[entry["census_id"]] = entry
        if len(pool) == 1:
            entry = next(iter(pool.values()))
            return entry["census_id"], "name" if entry["type"] == "county" else "consolidated", []
        if len(pool) > 1 and not ambiguous:
            ambiguous = sorted(pool)
    return (None, "ambiguous", ambiguous) if ambiguous else (None, "unmatched", [])


def match_names(index, jurisdictions):
    """The crosswalk rows from names alone, before any text is read."""
    for (state, kind, name), (census_id, expected) in ALIASES.items():
        if index.names.get(census_id) != expected or census_id not in index.entries:
            raise SourceChanged(f"alias {state}/{kind}/{name} expects general-purpose government {census_id} to be {expected!r}, the Census file has {index.names.get(census_id)!r}")
    unused = set(ALIASES) - {(j["locus_state"], j["locus_jurisdiction_type"], j["locus_name"]) for j in jurisdictions}
    if unused:
        raise SourceChanged(f"aliases for jurisdictions LOCUS no longer has: {sorted(unused)}")
    rows = []
    for jurisdiction in jurisdictions:
        kind, state, name = jurisdiction["locus_jurisdiction_type"], jurisdiction["locus_state"], jurisdiction["locus_name"]
        if (state, kind, name) in ALIASES:
            census_id, match, candidates = ALIASES[(state, kind, name)][0], "alias", []
        elif kind == "cities":
            census_id, match, candidates = match_city(index, state, name)
        elif kind == "counties":
            census_id, match, candidates = match_county(index, state, name)
            if match == "unmatched":
                # LOCUS files a few townships under counties, such as porter_township,_(van_buren_county). Only a name that carries its type word is read this way.
                fallback = match_city(index, state, name)
                if fallback[1] in ("name_type", "name_type_county"):
                    census_id, match, candidates = fallback
        else:
            raise SourceChanged(f"unknown LOCUS jurisdiction type {kind!r}")
        rows.append(dict(jurisdiction, census_id=census_id, match=match, candidates=candidates))
    return rows


SAINT, SAINTE, MOUNT, FORT = r"(?:st\.?|saint)", r"(?:ste\.?|sainte)", r"(?:mt\.?|mount)", r"(?:ft\.?|fort)"
WORD_FORMS = {"ST": SAINT, "SAINT": SAINT, "STE": SAINTE, "SAINTE": SAINTE, "MT": MOUNT, "MOUNT": MOUNT, "FT": FORT, "FORT": FORT}
TYPES_PATTERN = "(" + "|".join(TEXT_TYPES) + ")"


# The Census writes names in plain capitals; prose adds accents, sometimes as combining marks, and possessive apostrophes.
ACCENTS = {"A": "aáàâäã", "C": "cç", "E": "eéèêë", "I": "iíìîï", "N": "nñ", "O": "oóòôöõ", "U": "uúùûü"}
COMBINING = "[\u0300-\u036f]*"


def piece_pattern(piece):
    if piece in WORD_FORMS:
        return WORD_FORMS[piece]
    pattern = "".join(f"[{ACCENTS[char]}]{COMBINING}" if char in ACCENTS else re.escape(char) for char in piece)
    if len(piece) > 2 and piece.endswith("S"):
        pattern = pattern[:-1] + "['\u2019]?S"
    return pattern


def words_pattern(words):
    """A case-insensitive pattern for a Census name as prose writes it: ST CHARLES matches St. Charles and Saint Charles, COEUR D ALENE matches Coeur d'Alene,
    EL DORADO matches ElDorado, SAN JOSE matches San José and ST MARYS matches St. Mary's."""
    return r"[\s\-'\u2019.]*".join(r"[\s\-]*".join(piece_pattern(piece) for piece in word.split("-")) for word in words)


class Target:
    """What to look for in one jurisdiction's text: its governments' shared name with a type word before or after it, and, when they sit in different counties, those counties' names."""

    def __init__(self, entries):
        # Same-name governments can spell the name differently (TOWNSHIP OF ELDORADO, CITY OF EL DORADO), so every spelling is looked for.
        spellings = sorted({words_pattern(bare_words(split_title(entry["name"])[1])) for entry in entries}, key=lambda pattern: (-len(pattern), pattern))
        name = "(?:" + "|".join(spellings) + ")"
        self.names = re.compile(rf"\b(?:{TYPES_PATTERN}\s+of\s+(?:the\s+)?{name}\b|{name}\s+{TYPES_PATTERN}\b)", re.I)
        counties = sorted({entry["county_name"] for entry in entries if entry["county_name"]})
        self.counties = None
        if len(counties) > 1:
            either = "(" + "|".join(words_pattern(county.split()) for county in counties) + ")"
            self.counties = re.compile(rf"\b(?:(?:county|parish)\s+of\s+{either}|{either}\s+(?:county|parish))\b", re.I)
        self.words = Counter()
        self.county_mentions = Counter()

    def read(self, content):
        for found in self.names.finditer(content):
            self.words[(found.group(1) or found.group(2)).lower()] += 1
        if self.counties is not None:
            for found in self.counties.finditer(content):
                self.county_mentions[key(found.group(1) or found.group(2))] += 1


def read_text(paths, targets):
    """One pass over LOCUS's text, feeding each row to its jurisdiction's Target."""
    for path in paths:
        for batch in pq.ParquetFile(path).iter_batches(batch_size=20_000, columns=COLUMNS + ["content"]):
            data = batch.to_pydict()
            for state, kind, city, county, content in zip(data["state"], data["source_jurisdiction_type"], data["city"], data["county"], data["content"]):
                target = targets.get(jurisdiction_key(state, kind, city, county))
                if target is not None and content:
                    target.read(content)


def lopsided(counts):
    """The key holding at least MIN_MENTIONS and at least MIN_SHARE of all counts, if one does."""
    total = sum(counts.values())
    if not total:
        return None
    top, n = counts.most_common(1)[0]
    return top if n >= MIN_MENTIONS and n >= MIN_SHARE * total else None


def choose(pool, target):
    """One government from several same-name ones, by the type word the text uses for the name and then by the county it names; (None, None) when the text does not settle it.
    A text that names the government only with words no candidate's title fits (a city where the Census lists only townships) settles nothing."""
    fitting = Counter({word: n for word, n in target.words.items() if any(word in title_words(entry) for entry in pool)})
    if target.words and not fitting:
        return None, None
    word = lopsided(fitting)
    if word:
        pool = [entry for entry in pool if word in title_words(entry)]
        if len(pool) == 1:
            return pool[0], "text_type"
    counties = {entry["county"] for entry in pool}
    if len(counties) > 1:
        county = lopsided(Counter({name: n for name, n in target.county_mentions.items() if name in counties}))
        chosen = [entry for entry in pool if entry["county"] == county]
        if len(chosen) == 1:
            return chosen[0], "text_county"
    return None, None


def crosswalk(paths, governments):
    """One row per LOCUS jurisdiction: the government it names when exactly one fits, and how its text names that government."""
    index = Index(governments)
    rows = match_names(index, jurisdictions(paths))
    targets = {}
    for row in rows:
        ids = [row["census_id"]] if row["candidates"] == [] and row["census_id"] else row["candidates"]
        if ids:
            targets[(row["locus_state"], row["locus_jurisdiction_type"], row["locus_name"])] = Target([index.entries[census_id] for census_id in ids])
    read_text(paths, targets)
    for row in rows:
        target = targets.get((row["locus_state"], row["locus_jurisdiction_type"], row["locus_name"]))
        if target is None:
            row.update(text_type=None, text_type_mentions=None, text_mentions=None, text_fits=None)
            continue
        if row["match"] in ("municipal_preferred", "ambiguous"):
            chosen, how = choose([index.entries[census_id] for census_id in row["candidates"]], target)
            if chosen is not None:
                row.update(census_id=chosen["census_id"], match=how)
        top = target.words.most_common(1)
        text_type, text_type_mentions = top[0] if top else (None, 0)
        mentions = sum(target.words.values())
        fits = None
        if row["census_id"] and mentions >= MIN_MENTIONS and title_words(index.entries[row["census_id"]]):
            fits = text_type in title_words(index.entries[row["census_id"]])
        row.update(text_type=text_type, text_type_mentions=text_type_mentions, text_mentions=mentions, text_fits=fits)
    duplicates = sorted(census_id for census_id, n in Counter(row["census_id"] for row in rows if row["census_id"]).items() if n > 1)
    if duplicates:
        raise SourceChanged(f"LOCUS jurisdictions matched to the same government, which the rules were never checked against: {duplicates[:10]}")
    return rows
