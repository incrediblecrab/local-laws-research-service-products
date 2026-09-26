"""The Tribal entities the Bureau of Indian Affairs recognizes, from the list it publishes in the Federal Register.

The Census of Governments does not count tribal governments. Under the Federally Recognized Indian Tribe List Act of 1994, the Bureau of Indian Affairs publishes the list of Tribal entities it recognizes in the Federal Register. The build reads the latest notice and the one it says it updates, each at a pinned SHA-256, from the Federal Register's XML, and takes one row per entry of the latest notice's two lists. It then checks the list against the earlier one: every earlier entry must be continued by exactly one row, and the rows no earlier entry continues must be as many as the stated count grew by, which also makes the lists hold as many entries more than their stated count as the earlier lists did.
"""

import re
from collections import Counter
from xml.etree import ElementTree

from .census import SourceChanged, check_sha256

# Each notice as the Federal Register publishes it: XML from the full-text address its API gives as the document's full_text_xml_url, which its robots.txt allows. The site limits programmatic access to its API, so the page and the official PDF are only links for readers.
NOTICE = {
    "document_number": "2026-01899",
    "citation": "91 FR 4102",
    "published": "2026-01-30",
    "url": "https://www.federalregister.gov/documents/full_text/xml/2026/01/30/2026-01899.xml",
    "page": "https://www.federalregister.gov/documents/2026/01/30/2026-01899/indian-entities-recognized-by-and-eligible-to-receive-services-from-the-united-states-bureau-of",
    "pdf": "https://www.govinfo.gov/content/pkg/FR-2026-01-30/pdf/2026-01899.pdf",
    # SHA-256 of the XML as downloaded on September 26, 2026.
    "sha256": "616e96f6288cc0bbcdfb947042b1402de8f8bc5e5e90bf49d6c84acdc9458dfa",
}
PREVIOUS = {
    "document_number": "2024-29005",
    "citation": "89 FR 99899",
    "published": "2024-12-11",
    "url": "https://www.federalregister.gov/documents/full_text/xml/2024/12/11/2024-29005.xml",
    "page": "https://www.federalregister.gov/documents/2024/12/11/2024-29005/indian-entities-recognized-by-and-eligible-to-receive-services-from-the-united-states-bureau-of",
    "pdf": "https://www.govinfo.gov/content/pkg/FR-2024-12-11/pdf/2024-29005.pdf",
    "sha256": "31f306394463efde155a04c8d7307a9be6a4b35b0d8c0973ab066b72cff950fe",
}
TITLE = "Indian Entities Recognized by and Eligible To Receive Services From the United States Bureau of Indian Affairs"
# The `list` value for each of the notice's two lists, and how its heading begins.
LISTS = {
    "contiguous_48": "Indian Tribal Entities Within the Contiguous 48 States",
    "alaska": "Native Entities Within the State of Alaska",
}
STATED = re.compile(r"the current list of (\d+) Tribal entities")
# The notice's DATES paragraph names the notice it updates, as "The list is updated from the notice published on December 11, 2024 (89 FR 99899)."
UPDATES = re.compile(r"updated from the notice published on [^()]*\((\d+ FR \d+)\)")
# The day the Federal Register's API was last searched for a later notice of the list, finding none.
LATEST_CHECKED = "2026-09-26"
# What the pinned notice says of its changes, for the card, quoted from its Supplementary Information.
NOTICE_SAYS = 'The notice says the list "includes the addition of the Lumbee Tribe of North Carolina following the enactment of the National Defense Authorization Act for Fiscal Year 2026 on December 18, 2025", which set conditions on the Tribe\'s eligibility for federal services, and that "Other amendments to the list include formatting edits and name changes." It keeps former names in parentheses and says it will do so "for several years".'
PREVIOUSLY = "(previously listed as "
SEE = re.compile(r"\(\s*See ([^()]*)\)")
FIELDS = ("list_row", "list", "entry", "name", "previous_entry")


def download(fetcher, notice):
    data = fetcher.get(notice["url"])
    check_sha256(data, notice["sha256"], notice["url"])
    return data


def load(fetcher):
    """(the notice as read(), the earlier notice as read(), the rows) from both notices, each downloaded at its pinned SHA-256. Stops if the notice does not say it updates the earlier one, or the two do not reconcile."""
    notice, previous = read(download(fetcher, NOTICE)), read(download(fetcher, PREVIOUS))
    if notice["updates"] != PREVIOUS["citation"]:
        raise SourceChanged(f"the notice says it updates the notice at {notice['updates']}, not {PREVIOUS['citation']}")
    return notice, previous, rows(notice, previous)


def text(element):
    """An element's text with its children's, each run of spaces and line breaks read as one space."""
    return " ".join("".join(element.itertext()).split())


def read(data):
    """From a notice's XML: the number of Tribal entities its summary states, the citation of the notice it says it updates (None if it names none), and its entries as [(list, entry), ...] in its order."""
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise SourceChanged(f"the notice is not XML: {error}") from None
    summary, dates = root.find(".//SUM"), root.find(".//DATES")
    found = STATED.search(text(summary)) if summary is not None else None
    if not found:
        raise SourceChanged("the notice's summary does not say how many Tribal entities it lists")
    updates = UPDATES.search(text(dates)) if dates is not None else None
    entries, headings, current = [], [], None
    for element in root.iter():
        if element.tag == "HD":
            current = next((name for name, start in LISTS.items() if text(element).startswith(start)), None)
            if current:
                headings.append(current)
        elif element.tag == "FP" and current:
            entries.append((current, text(element)))
    if headings != list(LISTS):
        raise SourceChanged(f"the notice's lists are {headings}, not {list(LISTS)} in that order")
    blank = sum(1 for _, entry in entries if not entry)
    if blank:
        raise SourceChanged(f"the notice's lists have {blank} blank entries")
    return {"stated": int(found.group(1)), "updates": updates.group(1) if updates else None, "entries": entries}


def key(value):
    """What two entries are compared by: their text without spaces and in one case, since the notices' XML sometimes breaks a word (Coopera tive) or spaces a parenthesis, and a notice may change only a name's capitals."""
    return "".join(value.split()).casefold()


def name(entry):
    """The entry's name: its text before the first parenthesis, where the notice puts former names, other names and notes."""
    return entry.split(" (")[0]


def previously_listed(entry):
    """The names in each "(previously listed as ...)" of the entry, each read to the parenthesis that closes it."""
    entry = re.sub(r"\(\s+", "(", entry)
    out, start = [], entry.find(PREVIOUSLY)
    while start != -1:
        depth, end = 0, len(entry)
        for position in range(start, len(entry)):
            depth += {"(": 1, ")": -1}.get(entry[position], 0)
            if depth == 0:
                end = position
                break
        out.append(entry[start + len(PREVIOUSLY):end].strip())
        start = entry.find(PREVIOUSLY, end)
    return out


# How a row continues an earlier entry, tried in this order: the same entry; the entry its "previously listed as" gives; the earlier entry with its parentheticals dropped, as Native Village of Chenega (aka Chanega) became Native Village of Chenega.
RULES = (
    lambda entry, earlier: key(earlier) == key(entry),
    lambda entry, earlier: key(earlier) in {key(value) for value in previously_listed(entry)},
    lambda entry, earlier: key(name(earlier)) == key(entry),
)


def rows(notice, previous):
    """One row per entry of the current notice, each with the earlier notice's entry it continues. notice and previous are what read() gives for each.
    Stops unless the lists reconcile: every earlier entry continued by exactly one row, no row continuing two, and as many rows continuing none as the stated count grew by."""
    stated, entries = notice["stated"], notice["entries"]
    earlier_stated, earlier = previous["stated"], previous["entries"]
    out, used = [], Counter()
    for number, (listed, entry) in enumerate(entries, start=1):
        pool = [value for kind, value in earlier if kind == listed]
        continued = None
        for rule in RULES:
            found = [value for value in pool if rule(entry, value)]
            if len(found) > 1:
                raise SourceChanged(f"entry {number}, {entry!r}, could continue any of {found}")
            if found:
                continued = found[0]
                break
        if continued is not None:
            used[(listed, continued)] += 1
        out.append({"list_row": number, "list": listed, "entry": entry, "name": name(entry), "previous_entry": continued})
    dropped = [value for kind, value in earlier if used[(kind, value)] == 0]
    doubled = [value for (_, value), n in used.items() if n > 1]
    if dropped or doubled:
        raise SourceChanged(f"the earlier notice's entries {dropped} are continued by no row and {doubled} by more than one")
    added = [row["entry"] for row in out if row["previous_entry"] is None]
    if len(added) != stated - earlier_stated:
        raise SourceChanged(f"{len(added)} rows continue no earlier entry ({added[:5]}), but the stated count went from {earlier_stated:,} to {stated:,}")
    return out


def source(notice, previous, table):
    """The manifest's record of the two notices: each as pinned, with the count its summary states and the entries its lists hold. notice and previous are what read() gives for each."""
    fields = ("document_number", "citation", "published", "url", "page", "sha256")
    return ({field: NOTICE[field] for field in fields} | {"stated": notice["stated"], "entries": len(notice["entries"])}
            | {f"previous_{field}": PREVIOUS[field] for field in fields} | {"previous_stated": previous["stated"], "previous_entries": len(previous["entries"])}
            | {"rows": len(table)})


def stats(table):
    """The counts the card shows for the table; verify recomputes them from the published rows."""
    lists = Counter(row["list"] for row in table)
    added = sorted(row["name"] for row in table if row["previous_entry"] is None)
    changed = [row for row in table if row["previous_entry"] is not None and key(row["previous_entry"]) != key(row["entry"])]
    same = [row for row in table if row["previous_entry"] is not None and key(row["previous_entry"]) == key(row["entry"])]
    names = {key(row["name"]): row["name"] for row in table}
    referred = {}
    for row in table:
        for target in SEE.findall(row["entry"]):
            if key(target) in names:
                referred.setdefault(names[key(target)], set()).add(row["name"])
    return {
        "rows": len(table),
        "lists": {kind: lists[kind] for kind in LISTS},
        "unchanged": len(same),
        # Of those, the entries that are the earlier notice's only once spaces and capitals are ignored, and the names among them, with the earlier notice's name.
        "respaced": sum(1 for row in same if row["entry"] != row["previous_entry"]),
        "respaced_names": sorted([row["name"], name(row["previous_entry"])] for row in same if row["name"] != name(row["previous_entry"])),
        "changed": sorted(row["name"] for row in changed),
        "renamed": sum(1 for row in changed if key(name(row["previous_entry"])) != key(row["name"])),
        "added": added,
        # Each listed entry that others send the reader to ("See ..."), with the names of those others.
        "referred": {target: sorted(others) for target, others in sorted(referred.items())},
    }
