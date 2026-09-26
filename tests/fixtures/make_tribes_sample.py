"""Writes the Tribes fixtures from the two real notices: python tests/fixtures/make_tribes_sample.py path/to/2026-01899.xml path/to/2024-29005.xml

tribes_notice_sample.xml and tribes_previous_sample.xml are each notice's XML with only the chosen entries left in its lists and the count its summary states made the sample's: the entries kept less 2, the gap the real notices have, so the samples reconcile as the real ones do. Everything else, the preamble, the headings and the page breaks inside entries, is the notice's own. Both notices are works of the United States Government.
"""

import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from local_laws import census, tribes  # noqa: E402

HERE = Path(__file__).resolve().parent
# The entries kept, by name, each here for a rule or a sentence the tests check.
SHARED = {
    "Absentee-Shawnee Tribe of Indians of Oklahoma": "the first entry",
    "Capitan Grande Band of Diegueno Mission Indians of California": "a parenthetical that is no former name",
    "Hoopa Valley Tribe, California": "a page break inside the entry in the 2026 notice",
    "Zuni Tribe of the Zuni Reservation, New Mexico": "the last entry of the contiguous 48 states",
    "Agdaagux Tribe of King Cove": "the first entry for Alaska",
    "Pribilof Islands Aleut Communities of St. Paul & St. George Islands": "an entry two others send the reader to",
    "St. George Island": "one of them; the 2024 notice spaces its parenthesis, ( See",
    "Arctic Village": "sends the reader to the Native Village of Venetie Tribal Government",
    "Native Village of Venetie Tribal Government": "an entry two others send the reader to",
    "Village of Venetie": "sends the reader to the Native Village of Venetie Tribal Government",
    "Native Village of Atqasuk": "a page break inside the entry in the 2026 notice",
    "Yupiit of Andreafski": "the last entry",
}
NOTICE_CHOSEN = SHARED | {
    "Cabazon Band of Cahuilla Indians": "the same entry, but for the space the 2024 notice puts in its parenthesis",
    "Kiowa Tribe": "a new name, continued by its previously listed as",
    "Match-E-Be-Nash-She-Wish Band of Pottawatomi": "a new name, and capitals the 2024 notice wrote otherwise",
    "Lumbee Tribe of North Carolina": "the one entry added, with a See that names no entry",
    "Aleut Community of St. Paul Island": "a new name whose previously listed as holds a spaced ( See",
    "Native Village of Chenega": "an aka dropped",
    "Wrangell Cooperative Association": "one word the 2024 notice breaks in two",
}
PREVIOUS_CHOSEN = SHARED | {
    "Cabazon Band of Cahuilla Indians": "continued by the same entry",
    "Kiowa Indian Tribe of Oklahoma": "continued by the Kiowa Tribe",
    "Match-e-be-nash-she-wish Band of Pottawatomi Indians of Michigan": "continued by the Match-E-Be-Nash-She-Wish Band of Pottawatomi",
    "Saint Paul Island": "continued by the Aleut Community of St. Paul Island",
    "Native Village of Chenega": "continued by the entry without its aka",
    "Wrangell Coopera tive Association": "continued by the Wrangell Cooperative Association",
}
GAP = 2


def sample(data, chosen):
    root = ElementTree.fromstring(data)
    kept = []
    for parent in root.iter():
        for child in list(parent):
            if child.tag == "FP":
                if tribes.name(tribes.text(child)) in chosen:
                    kept.append(tribes.name(tribes.text(child)))
                else:
                    parent.remove(child)
    if sorted(kept) != sorted(chosen):
        raise SystemExit(f"kept {sorted(kept)}, chose {sorted(chosen)}")
    summary = next(element for element in root.find(".//SUM").iter("P") if tribes.STATED.search(element.text or ""))
    summary.text = tribes.STATED.sub(f"the current list of {len(kept) - GAP} Tribal entities", summary.text, count=1)
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    for path, notice, chosen, out in ((sys.argv[1], tribes.NOTICE, NOTICE_CHOSEN, "tribes_notice_sample.xml"), (sys.argv[2], tribes.PREVIOUS, PREVIOUS_CHOSEN, "tribes_previous_sample.xml")):
        data = Path(path).read_bytes()
        census.check_sha256(data, notice["sha256"], path)
        (HERE / out).write_bytes(sample(data, chosen))
        print(f"wrote {len(chosen)} entries to {HERE / out}")
