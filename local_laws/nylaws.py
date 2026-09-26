"""New York's local laws: every filing the Department of State publishes in its local-law search, read from the search's own API, and the government that filed each one.

New York's Municipal Home Rule Law §27 has every county, city, town and village file its local laws with the Secretary of State. The Department publishes the filings since 1998 at https://dos.ny.gov/local-laws, a page whose script asks API (a proxy for the state's Widen digital-asset library) for search results. The API returns at most 100 results a request and none past the 10,000th of a query, so the harvest splits the category by filing year, and by month for any year too large, and pages through each part in filename order.
"""

import datetime
import gzip
import json
import logging
import re
import zoneinfo
from collections import Counter, defaultdict
from urllib.parse import urlencode

from .census import SourceChanged
from .locus import key, split_title

API = "https://locallaws.static-assets.ny.gov/api/search"
APP = "https://dos.ny.gov/local-laws"
CATEGORY = "Local Laws"
PAGE = 100
WINDOW = 10_000
# filename is unique per asset, so pages in filename order do not overlap; dateFiled, the app's own order, has many ties.
ORDER = "filename"
EXPAND = "metadata,embeds,file_properties"
# The metadata fields the API published for every asset on September 25, 2026. Each is a list; a field that is missing, extra or longer than one value stops the build.
FIELDS = ("countyLawType", "countyMuncipalName", "countyMunicipalType", "dateFiled", "enactedThrough", "lawNumber", "municipalityName", "municipalityType", "subject", "subject1", "year")
REPASSES = 1
log = logging.getLogger("local_laws")


def now():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def category(extra=None):
    return f"cat:({CATEGORY})" + (f" AND {extra}" if extra else "")


def filed_between(start, end):
    """The API's range syntax, as the app writes it: both ends inclusive, to the second."""
    return f"dateFiled:[{start:%Y-%m-%dT%H:%M:%SZ} TO {end:%Y-%m-%dT%H:%M:%SZ}]"


def search(fetcher, query, limit=1, offset=0, order=ORDER, expand=EXPAND):
    url = API + "?" + urlencode({"query": query, "sort": order, "limit": limit, "offset": offset, "expand": expand, "search_document_text": "false"})
    data = json.loads(fetcher.get(url))
    if not isinstance(data.get("total_count"), int) or not isinstance(data.get("items"), list):
        raise SourceChanged(f"the NY local-law API answered {query!r} without total_count and items: {sorted(data)[:10]}")
    return data


def total(fetcher, query):
    return search(fetcher, query, expand="metadata")["total_count"]


def first_filed(fetcher, order):
    items = search(fetcher, category(), order=order, expand="metadata")["items"]
    if not items or not items[0]["metadata"]["fields"].get("dateFiled"):
        raise SourceChanged(f"the NY local-law API's first result by {order} has no dateFiled")
    return datetime.datetime.fromisoformat(items[0]["metadata"]["fields"]["dateFiled"][0].replace("Z", "+00:00"))


def year_span(year):
    utc = datetime.UTC
    return datetime.datetime(year, 1, 1, tzinfo=utc), datetime.datetime(year, 12, 31, 23, 59, 59, tzinfo=utc)


def month_spans(year):
    utc = datetime.UTC
    for month in range(1, 13):
        start = datetime.datetime(year, month, 1, tzinfo=utc)
        following = datetime.datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=utc)
        yield start, following - datetime.timedelta(seconds=1)


def keep(item):
    """The parts of an API result the table is built from."""
    fields = (item.get("metadata") or {}).get("fields") or {}
    share = (((item.get("embeds") or {}).get("document_viewer") or {}).get("share"))
    return {
        "id": item.get("id"),
        "external_id": item.get("external_id"),
        "filename": item.get("filename"),
        "created_date": item.get("created_date"),
        "last_update_date": item.get("last_update_date"),
        "size_in_bytes": (item.get("file_properties") or {}).get("size_in_bytes"),
        "current_version": item.get("current_version"),
        "deleted_date": item.get("deleted_date"),
        "released_and_not_expired": item.get("released_and_not_expired"),
        "share": share,
        "fields": fields,
    }


class TooLarge(ValueError):
    """A query matches more filings than the API pages through."""


def harvest_part(fetcher, start, end):
    """(count, {id: kept item}) for every asset filed between start and end. Raises TooLarge if the part holds more than the API pages through, and SourceChanged if its pages disagree with its count."""
    query = category(filed_between(start, end))
    expected = total(fetcher, query)
    if expected > WINDOW:
        raise TooLarge(f"{start:%Y-%m} to {end:%Y-%m} holds {expected:,} filings, more than the {WINDOW:,} the API pages through")
    items = {}
    for offset in range(0, expected, PAGE):
        page = search(fetcher, query, limit=PAGE, offset=offset)
        if page["total_count"] != expected:
            raise SourceChanged(f"{query} counted {expected:,} filings and then {page['total_count']:,} while it was read")
        for item in page["items"]:
            items[item["id"]] = keep(item)
    if len(items) != expected:
        raise SourceChanged(f"{query} counts {expected:,} filings but its pages held {len(items):,} different ones")
    return expected, items


def harvest_year(fetcher, year):
    """(count, items) for one filing year, read by month when the year is more than one query can page through."""
    start, end = year_span(year)
    try:
        return harvest_part(fetcher, start, end)
    except TooLarge:
        count, items = 0, {}
        for start, end in month_spans(year):
            try:
                n, part = harvest_part(fetcher, start, end)
            except TooLarge as error:
                raise SourceChanged(f"{error}: the harvest needs a finer split") from None
            count += n
            items |= part
        return count, items


def harvest(fetcher):
    """A snapshot of the category: every asset, the category's count before and after reading it, and each filing year's count.
    A year whose count changed while the category was read is read again, up to REPASSES times; after that the snapshot is refused."""
    started = now()
    before = total(fetcher, category())
    first, last = first_filed(fetcher, "dateFiled").year, first_filed(fetcher, "-dateFiled").year
    years, items = {}, {}
    for year in range(first, last + 1):
        years[year], part = harvest_year(fetcher, year)
        items |= part
        log.info("NY local laws: %d has %s filings; %s read so far, %s requests", year, f"{years[year]:,}", f"{len(items):,}", f"{fetcher.requests:,}")
    after = total(fetcher, category())
    for _ in range(REPASSES):
        if after == before == sum(years.values()) == len(items):
            break
        changed = [year for year in years if total(fetcher, category(filed_between(*year_span(year)))) != years[year]]
        log.warning("NY local laws: the category counted %s filings before the harvest and %s after; reading %s again", f"{before:,}", f"{after:,}", changed)
        for year in changed:
            items = {uid: item for uid, item in items.items() if filed_year(item) != year}
            years[year], part = harvest_year(fetcher, year)
            items |= part
        before, after = after, total(fetcher, category())
    if not after == before == sum(years.values()) == len(items):
        raise SourceChanged(f"the NY local-law category counted {before:,} and then {after:,} filings; its years add to {sum(years.values()):,} and the harvest holds {len(items):,}: run again once the Department has finished posting")
    return {
        "api": API,
        "category": CATEGORY,
        "started_at": started,
        "finished_at": now(),
        "total": after,
        "years": {str(year): n for year, n in years.items()},
        "items": sorted(items.values(), key=lambda item: item["filename"] or ""),
    }


def filed_year(item):
    filed = item["fields"].get("dateFiled") or []
    return int(filed[0][:4]) if filed else None


def save(snapshot, path):
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, separators=(",", ":"))


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


# The share link the Department's app gives for each filing: a public page, stable as long as the asset is, unlike the signed download links the API also returns.
SHARE = re.compile(r"https://itswebny\.widen\.net/content/[a-z0-9]+/pdf/[^?#\s]+\?u=[a-z0-9]+&x\.share=t")
# Every dateFiled read on September 25, 2026 is midnight in Central time (Widen is in Madison, Wisconsin): 05:00 or 06:00 UTC, so its UTC date is the filing date.
MIDNIGHTS = ("T05:00:00Z", "T06:00:00Z")
TITLES = {"Town": "TOWN OF", "Village": "VILLAGE OF", "City": "CITY OF", "County": "COUNTY OF"}
GOVERNMENT_TYPES = {"TOWN OF": "township", "VILLAGE OF": "municipal", "CITY OF": "municipal", "COUNTY OF": "county"}
# A note the Department writes after some names: a county, as in Chester (Warren County), or a remark, as in Amherst (Corrected Copy). Some are not closed.
NOTE = re.compile(r"\s*\(([^()]*)\)?\s*$")
MATCH_DOCS = {
    "name": "The name fits exactly one New York government with the title `municipality_type` gives: TOWN OF FLORENCE for Town and FLORENCE. A remark after the name, such as (Corrected Copy), is set aside, and so is the title when the name repeats it: VILLAGE OF THE BRANCH and CUBA VILLAGE, for Village, read as BRANCH (the Census's name for the Village of The Branch) and CUBA",
    "name_county": "The name has a county after it, and the name and county fit exactly one government with that title: TOWN OF CHESTER, in Warren County, for Town and Chester (Warren County), Chester (Warren) or Chester (Warren Co)",
    "ambiguous": "Several governments with that title have the name, and nothing in the filing's metadata says which, so `census_id` is null and `candidates` lists them",
    "unmatched": "No government with that title in the 2022 Census of Governments has the name (and county, if one is given): a village dissolved before 2022, a misspelling, or a filing under another title than the government's",
}
MATCHES = tuple(MATCH_DOCS)
MATCHED = ("name", "name_county")
# The library received nearly every filing from before September 26, 2024 in bulk, from then to October 24, 2024, so created_date says when a filing was posted only for filings added after that.
MOVED_BY = datetime.datetime(2024, 11, 1, tzinfo=datetime.UTC)
# The card's measure of how long the Department takes to post a filing covers the filings added in this many days before the latest one.
RECENT_DAYS = 365
# The Department's day: a filing added at 22:30 in Albany is added on that day, although its UTC date is the next.
NEW_YORK = zoneinfo.ZoneInfo("America/New_York")


def one(values, field, uid):
    if len(values) > 1:
        raise SourceChanged(f"NY filing {uid} has {len(values)} values for {field}: {values[:3]}")
    return values[0] if values else None


def filed_date(value, field, uid):
    if value is None:
        return None
    if not value.endswith(MIDNIGHTS):
        raise SourceChanged(f"NY filing {uid} has {field} {value}, not midnight Central time: check what date it means before publishing")
    return datetime.date.fromisoformat(value[:10])


def rows(snapshot):
    """One row per asset in the snapshot, without the match to governments. Stops at anything the table's documentation does not cover."""
    out = []
    for item in snapshot["items"]:
        uid = item["id"]
        fields = item["fields"]
        if set(fields) != set(FIELDS):
            raise SourceChanged(f"NY filing {uid} has metadata fields {sorted(set(fields) ^ set(FIELDS))} that the table does not document")
        if item["current_version"] is not True or item["deleted_date"] is not None or item["released_and_not_expired"] is not True:
            raise SourceChanged(f"NY filing {uid} is not a current, released asset: {item['current_version']!r} {item['deleted_date']!r} {item['released_and_not_expired']!r}")
        if not item["share"] or not SHARE.fullmatch(item["share"]):
            raise SourceChanged(f"NY filing {uid} has share link {item['share']!r}, not the public link the app uses")
        value = {field: one(fields[field], field, uid) for field in FIELDS}
        if value["dateFiled"] is None:
            raise SourceChanged(f"NY filing {uid} has no dateFiled")
        year = value["year"]
        if year is not None and not (year.isdigit() and len(year) == 4):
            raise SourceChanged(f"NY filing {uid} has year {year!r}")
        out.append({
            "asset_id": uid,
            "municipality_type": value["municipalityType"],
            "municipality_name": value["municipalityName"],
            "law_number": value["lawNumber"],
            "law_year": int(year) if year else None,
            "date_filed": filed_date(value["dateFiled"], "dateFiled", uid),
            "title": value["subject1"],
            "subject": value["subject"],
            "county_law_type": value["countyLawType"],
            "county_municipal_type": value["countyMunicipalType"],
            "county_municipal_name": value["countyMuncipalName"],
            "enacted_through": filed_date(value["enactedThrough"], "enactedThrough", uid),
            "filename": item["filename"],
            "file_bytes": item["size_in_bytes"],
            "posted_at": datetime.datetime.fromisoformat(item["created_date"].replace("Z", "+00:00")),
            "share_url": item["share"],
        })
    return out


def reading(name, counties, municipality_type=None):
    """(core, county, note) for a Department name: Chester (Warren County) -> ("chester", "warren", None); Amherst  (Corrected Copy) -> ("amherst", None, "Corrected Copy").
    counties maps key(county name) for New York's counties; a note that is not one of them is a remark. A name that repeats its own title is read without it:
    VILLAGE OF THE BRANCH and CUBA VILLAGE, for a Village, read as BRANCH (the Census's name for the Village of The Branch) and CUBA."""
    text = " ".join((name or "").split())
    county = note = None
    found = NOTE.search(text)
    if found:
        inner = found.group(1).strip()
        text = text[:found.start()]
        named = key(re.sub(r"\s*county$|\s+co\.?$", "", inner, flags=re.IGNORECASE))
        if named in counties:
            county = named
        else:
            note = inner
    words = text.upper().split()
    title = TITLES.get(municipality_type, "").split()
    if title and words[:len(title)] == title and len(words) > len(title):
        words = words[len(title):]
        if words[0] == "THE" and len(words) > 1:
            words = words[1:]
    if municipality_type and len(words) > 1 and words[-1] == municipality_type.upper():
        words = words[:-1]
    return key(" ".join(words)), county, note


def index(governments):
    """New York's county, municipal and township governments by (title, core name)."""
    by_name = defaultdict(list)
    for row in governments:
        if row["state"] != "NY" or row["government_type"] not in GOVERNMENT_TYPES.values():
            continue
        title, rest = split_title(row["name"])
        if GOVERNMENT_TYPES.get(title) != row["government_type"]:
            raise SourceChanged(f"New York government {row['census_id']} {row['name']!r} is {row['government_type']}, which its title does not say")
        by_name[(title, key(rest))].append({"census_id": row["census_id"], "county": key(row["county_name"] or "")})
    return by_name


def match_one(by_name, counties, municipality_type, municipality_name):
    """(census_id, match, candidates) for one Department type and name."""
    title = TITLES.get(municipality_type)
    core, county, _ = reading(municipality_name, counties, municipality_type)
    pool = by_name.get((title, core), []) if title else []
    if county:
        pool = [entry for entry in pool if entry["county"] == county]
    if len(pool) == 1:
        return pool[0]["census_id"], "name_county" if county else "name", []
    if pool:
        return None, "ambiguous", sorted(entry["census_id"] for entry in pool)
    return None, "unmatched", []


def match(table, governments):
    """Adds census_id, match and candidates to each row, matching each distinct (municipality_type, municipality_name) once."""
    by_name = index(governments)
    counties = {entry["county"] for entries in by_name.values() for entry in entries}
    cache = {}
    for row in table:
        pair = (row["municipality_type"], row["municipality_name"])
        if pair not in cache:
            cache[pair] = match_one(by_name, counties, *pair)
        row["census_id"], row["match"], row["candidates"] = cache[pair]
    return table


def weekdays_after(start, end):
    """The weekdays from the day after start through end: 1 from a Friday to the next Monday. Holidays count as weekdays."""
    weeks, extra = divmod(max((end - start).days, 0), 7)
    return weeks * 5 + sum(1 for step in range(1, extra + 1) if (start.weekday() + step) % 7 < 5)


def posted_on(row):
    return row["posted_at"].astimezone(NEW_YORK).date()


def posting(table):
    """How many filings the 2024 move added, and how long the filings added in the RECENT_DAYS before the latest took to be added after they were filed, in New York days.
    A filing dated after the day it was added has no wait, and is left out here and listed in filed_after_posted."""
    latest = max(row["posted_at"] for row in table)
    moved = sorted((posted_on(row), row["date_filed"]) for row in table if row["posted_at"] < MOVED_BY)
    recent = [row for row in table if row["posted_at"] > latest - datetime.timedelta(days=RECENT_DAYS) and row["date_filed"] <= posted_on(row)]
    waits = sorted(weekdays_after(row["date_filed"], posted_on(row)) for row in recent)
    days = sorted((posted_on(row) - row["date_filed"]).days for row in recent)
    return {
        "moved": len(moved),
        "moved_from": moved[0][0].isoformat() if moved else None,
        "moved_to": moved[-1][0].isoformat() if moved else None,
        "moved_filed_before": sum(1 for _, filed in moved if filed < moved[0][0]),
        "latest": posted_on({"posted_at": latest}).isoformat(),
        "recent": len(recent),
        "within_two_weekdays": sum(1 for wait in waits if wait <= 2),
        # At least half of the filings waited this many weekdays or fewer, and at least nine in ten this many days or fewer.
        "median_weekdays": waits[(len(waits) - 1) // 2] if waits else None,
        "p90_days": days[-(-9 * len(days) // 10) - 1] if days else None,
    }


def stats(table, governments):
    """The counts the card shows for the table. verify recomputes them from the published tables."""
    titles, places = {}, {}
    for row in governments:
        if row["state"] == "NY" and row["government_type"] in GOVERNMENT_TYPES.values():
            titles[row["census_id"]] = split_title(row["name"])[0]
            places[row["census_id"]] = [row["census_id"], row["name"], row["county_name"], row["population"]]
    filers = Counter(titles[row["census_id"]] for row in {row["census_id"]: row for row in table if row["census_id"]}.values())
    filed = {row["census_id"] for row in table if row["census_id"]}
    names = defaultdict(Counter)
    for row in table:
        names[row["match"]][(row["municipality_type"] or "", row["municipality_name"] or "")] += 1

    def listed(match):
        return [[kind, name, n] for (kind, name), n in sorted(names[match].items(), key=lambda item: (-item[1], item[0]))]

    def tally(rows):
        return {"filings": len(rows), "with_title": sum(1 for row in rows if row["title"]), "with_law_year": sum(1 for row in rows if row["law_year"] is not None), "matched": sum(1 for row in rows if row["census_id"])}

    by_year, by_kind = defaultdict(list), defaultdict(list)
    for row in table:
        by_year[row["date_filed"].year].append(row)
        by_kind[row["municipality_type"] or ""].append(row)
    return {
        "filings": len(table),
        "first_filed": min(row["date_filed"] for row in table).isoformat(),
        "last_filed": max(row["date_filed"] for row in table).isoformat(),
        "years": {str(year): tally(rows) for year, rows in sorted(by_year.items())},
        "municipality_types": {kind: tally(rows) for kind, rows in sorted(by_kind.items(), key=lambda item: (-len(item[1]), item[0]))},
        "matches": {match: {"filings": sum(names[match].values()), "names": len(names[match])} for match in MATCHES},
        "governments": {title: {"governments": n, "with_filings": filers[title]} for title, n in sorted(Counter(titles.values()).items())},
        "codifications": sum(1 for row in table if row["county_law_type"] == "Codification"),
        "posting": posting(table),
        "filed_after_posted": sorted([row["filename"], row["municipality_type"] or "", row["municipality_name"] or "", row["law_number"] or "", row["date_filed"].isoformat(), posted_on(row).isoformat()] for row in table if row["date_filed"] > posted_on(row)),
        "without_filings": sorted(place for census_id, place in places.items() if census_id not in filed),
        "ambiguous": listed("ambiguous"),
        "unmatched": listed("unmatched"),
    }
