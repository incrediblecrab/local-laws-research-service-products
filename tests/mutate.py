"""Disables one check at a time in a copy of the package and runs the tests against it: python tests/mutate.py

Each mutation below breaks a check the build, the card or verify relies on. The suite must fail (pytest exit 1) for every one; a test run that errors instead does not count as caught. Exits 0 when all are caught, 1 otherwise. The real source is never edited.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns("__pycache__")
# (module, what the mutation breaks, code to replace, replacement). Each code string must occur exactly once in its module.
MUTATIONS = [
    ("census.py", "compare: never reports", "if counts.get((state, kind), 0) != expected]", "if False]"),
    ("census.py", "parse_units: duplicates allowed", "    if duplicates:\n        raise SourceChanged(f\"duplicate census ids", "    if False:\n        raise SourceChanged(f\"duplicate census ids"),
    ("census.py", "check_sha256: no pin", "    if actual != expected:\n", "    if False:\n"),
    ("locus.py", "lopsided: any share", "n >= MIN_SHARE * total", "n >= 0"),
    ("locus.py", "alias guard off", "    if unused:\n", "    if False:\n"),
    ("locus.py", "duplicate-match guard off", "    if duplicates:\n        raise SourceChanged(f\"LOCUS jurisdictions matched", "    if False:\n        raise SourceChanged(f\"LOCUS jurisdictions matched"),
    ("locus.py", "choose: text never settles", "        if len(pool) == 1:\n            return pool[0], \"text_type\"", "        if False:\n            return pool[0], \"text_type\""),
    ("store.py", "412 not treated as conflict", "if status == CONFLICT:", "if False:"),
    ("store.py", "landed commit never adopted", "                return head\n", "                return None\n"),
    ("store.py", "superseded store keeps calling", "        if self.superseded:\n            raise self.superseded\n", ""),
    ("verify.py", "crosswalk id not checked against governments", "row[\"census_id\"] not in government_ids", "False"),
    ("verify.py", "crosswalk judged against a rejected table", "check_crosswalk(crosswalk, None if governments is None else {", "check_crosswalk(crosswalk, set() if governments is None else {"),
    ("verify.py", "card not compared", "if store.read_text(CARD) != card:", "if False:"),
    ("verify.py", "ORG02 mismatches dropped", "problems += [f\"CG2200ORG02: {mismatch}\" for mismatch in mismatches]", "pass"),
    ("verify.py", "pins not compared", "!= pin:", "!= pin and False:"),
    ("verify.py", "stats not compared", "            if stats != manifest.get(\"stats\"):", "            if False:"),
    ("verify.py", "sha not compared", "sha256s.get(path) != entry.get(\"sha256\")", "False"),
    ("http.py", "challenge retried as a 403", "response.status_code == 403 and (", "False and ("),
    ("http.py", "no pacing", "        if at > now:\n", "        if False:\n"),
    ("cli.py", "dirty tree may publish", "code[\"dirty\"] is not False", "False"),
    ("build.py", "unchanged ignores the card", " and store.read_text(CARD) == render(manifest)", ""),
    ("build.py", "LOCUS row count not compared", "    if read != stated:\n", "    if False:\n"),
    ("card.py", "review claimed for unread names", "    if differs and not unread:", "    if differs:"),
    ("nylaws.py", "NY part: count change while paging ignored", "if page[\"total_count\"] != expected:", "if False:"),
    ("nylaws.py", "NY part: repeated pages accepted", "    if len(items) != expected:\n", "    if False:\n"),
    ("nylaws.py", "NY part: no window limit", "    if expected > WINDOW:\n", "    if False:\n"),
    ("nylaws.py", "NY: month too large read anyway", "raise SourceChanged(f\"{error}: the harvest needs a finer split\") from None", "continue"),
    ("nylaws.py", "NY: category that moved accepted", "    if not after == before == sum(years.values()) == len(items):\n", "    if False:\n"),
    ("nylaws.py", "NY: changed year not read again", "REPASSES = 1", "REPASSES = 0"),
    ("nylaws.py", "NY rows: undocumented fields accepted", "        if set(fields) != set(FIELDS):\n", "        if False:\n"),
    ("nylaws.py", "NY rows: deleted or unreleased accepted", "if item[\"current_version\"] is not True or item[\"deleted_date\"] is not None or item[\"released_and_not_expired\"] is not True:", "if False:"),
    ("nylaws.py", "NY rows: signed link accepted", "if not item[\"share\"] or not SHARE.fullmatch(item[\"share\"]):", "if False:"),
    ("nylaws.py", "NY rows: several values accepted", "    if len(values) > 1:\n", "    if False:\n"),
    ("nylaws.py", "NY rows: undated accepted", "        if value[\"dateFiled\"] is None:\n", "        if False:\n"),
    ("nylaws.py", "NY rows: odd year accepted", "if year is not None and not (year.isdigit() and len(year) == 4):", "if False:"),
    ("nylaws.py", "NY rows: any time of day accepted", "    if not value.endswith(MIDNIGHTS):\n", "    if False:\n"),
    ("nylaws.py", "NY reading: X CO not a county", "r\"\\s*county$|\\s+co\\.?$\"", "r\"\\s*county$\""),
    ("nylaws.py", "NY reading: repeated title kept", "    if title and words[:len(title)] == title and len(words) > len(title):\n", "    if False:\n"),
    ("nylaws.py", "NY reading: THE kept after the title", "        if words[0] == \"THE\" and len(words) > 1:\n", "        if False:\n"),
    ("nylaws.py", "NY reading: trailing type word kept", "    if municipality_type and len(words) > 1 and words[-1] == municipality_type.upper():\n", "    if False:\n"),
    ("nylaws.py", "NY match: county ignored", "    if county:\n        pool = [entry for entry in pool if entry[\"county\"] == county]\n", ""),
    ("nylaws.py", "NY match: Village read as Town", "\"Village\": \"VILLAGE OF\"", "\"Village\": \"TOWN OF\""),
    ("nylaws.py", "NY index: title and type may disagree", "        if GOVERNMENT_TYPES.get(title) != row[\"government_type\"]:\n", "        if False:\n"),
    ("nylaws.py", "NY posting: UTC days", "    return row[\"posted_at\"].astimezone(NEW_YORK).date()", "    return row[\"posted_at\"].date()"),
    ("nylaws.py", "NY posting: window edge included", "row[\"posted_at\"] > latest - datetime.timedelta(days=RECENT_DAYS)", "row[\"posted_at\"] >= latest - datetime.timedelta(days=RECENT_DAYS)"),
    ("nylaws.py", "NY posting: p90 below nine in ten", "days[-(-9 * len(days) // 10) - 1]", "days[int(0.9 * (len(days) - 1))]"),
    ("nylaws.py", "NY posting: upper median", "waits[(len(waits) - 1) // 2]", "waits[len(waits) // 2]"),
    ("nylaws.py", "NY: misdated filings not listed", "for row in table if row[\"date_filed\"] > posted_on(row)),", "for row in table if False),"),
    ("nylaws.py", "NY: governments without filings not listed", "if census_id not in filed),", "if False),"),
    ("build.py", "NY snapshot not checked against its counts", "    if len(ny) != snapshot[\"total\"] or Counter(str(row[\"date_filed\"].year) for row in ny) != Counter(snapshot[\"years\"]):\n", "    if False:\n"),
    ("verify.py", "NY rows without asset_id pass", "    if None in ids or \"\" in ids:\n", "    if False:\n"),
    ("verify.py", "NY duplicate asset_id pass", "duplicates = [uid for uid, n in ids.items() if uid and n > 1]", "duplicates = []"),
    ("verify.py", "NY manifest year sum not checked", "    if sum(counted.values()) != source.get(\"total\"):\n", "    if False:\n"),
    ("verify.py", "NY row count not checked", "    if len(rows) != source.get(\"total\"):\n", "    if False:\n"),
    ("verify.py", "NY filings by year not checked", "    if differing:\n        problems.append(f\"ny_local_laws: filings by year", "    if False:\n        problems.append(f\"ny_local_laws: filings by year"),
    ("verify.py", "NY signed links pass", "if not row[\"share_url\"] or not nylaws.SHARE.fullmatch(row[\"share_url\"])]", "if False]"),
    ("verify.py", "NY unknown match values pass", "unknown = sorted({row[\"match\"] for row in rows} - set(nylaws.MATCHES))", "unknown = []"),
    ("verify.py", "NY census_id, match, candidates may disagree", "        if (row[\"census_id\"] is None) != unmatched or bool(row[\"candidates\"]) != (row[\"match\"] == \"ambiguous\"):\n", "        if False:\n"),
    ("verify.py", "NY stray census_id passes", "                stray.append(row[\"asset_id\"])", "                pass"),
    ("verify.py", "NY mistitled census_id passes", "                mistitled.append(row[\"asset_id\"])", "                pass"),
    ("verify.py", "NY judged against a rejected table", "titles = None if governments is None else {", "titles = {} if governments is None else {"),
    ("card.py", "NY unmatched not listed", "        f\"Unmatched, with the number of filings: {listed(ny['unmatched'])}.\",", "        \"Unmatched, with the number of filings: none.\","),
    ("card.py", "NY ambiguous not listed", "        f\"Ambiguous, with the number of filings: {listed(ny['ambiguous'])}.\",", "        \"Ambiguous, with the number of filings: none.\","),
    ("card.py", "NY per-type rates dropped", "    for kind, entry in kinds.items():\n", "    for kind, entry in []:\n"),
    ("card.py", "NY misdated filings not stated", "{misdated(ny['filed_after_posted'])}", ""),
    ("card.py", "NY governments without filings not stated", "    lines += [\"\", without_filings(ny[\"without_filings\"])]\n", ""),
    ("card.py", "NY outside-category gap dropped", "        f\"- {NY_OUTSIDE}\",\n", ""),
    ("cli.py", "run ignores --ny-snapshot", "snapshot = nylaws.load(args.ny_snapshot) if args.ny_snapshot else None", "snapshot = None"),
    ("cli.py", "harvest-ny does not stop cleanly", "        snapshot = nylaws.harvest(fetcher)\n    except (SourceChanged, Blocked, Unavailable) as error:", "        snapshot = nylaws.harvest(fetcher)\n    except () as error:"),
    ("precision.py", "NY check: name in metadata taken as confirmed", "    if in_text(name):\n        return \"confirmed\"", "    if name[0]:\n        return \"confirmed\""),
    ("precision.py", "NY check: other-type names ignored", "    if any(found for _, _, found in other):\n        return \"contradicted\"", "    if False:\n        return \"contradicted\""),
    ("precision.py", "NY check: GENERIC's metadata control ignored", "return \"not_named\" if in_text(generic) else \"no_text\"", "return \"not_named\" if generic[0] else \"no_text\""),
    ("precision.py", "NY check: text counted from metadata hits", "entry[\"with_text\"] += in_text(generic) or in_text(name) or (county is not None and in_text(county))", "entry[\"with_text\"] += bool(generic[0] or name[0])"),
    ("card.py", "NY check paragraph dropped", "        checked(),\n        \"\",\n", ""),
    ("card.py", "NY check: confirmed count typed in", "f\"{found['confirmed']:,} of the {n} were confirmed", "f\"35 of the {n} were confirmed"),
    ("card.py", "NY check: contradictions not stated", "verdict = \"No filing was\" if not contradicted else", "verdict = \"No filing was\" if True else"),
    ("card.py", "NY check: second draw's other names not stated", "    if second[\"other_found\"]:\n", "    if False:\n"),
    ("card.py", "NY check: every filing said to have text", "    if with_text == filings:\n        lines.append(f\"Every filing checked", "    if True:\n        lines.append(f\"Every filing checked"),
    ("card.py", "NY text gap: every filing said to have text", "{'every one' if with_text == filings else f'{with_text:,}'}", "every one"),
    ("precision.py", "NY check: a real county counted as unnamed", " if phrase not in REAL)", ")"),
    ("card.py", "NY check: form titles sentence dropped", "    lines.append(form_titles(parts))\n", ""),
    ("card.py", "NY check: unnamed count typed in", "was found in {found:,} of the {asked:,} filings checked, likely", "was found in 7 of the {asked:,} filings checked, likely"),
    ("card.py", "NY check: no-hit form titles branch never taken", "    if not found:\n        return f\"The matched name", "    if False:\n        return f\"The matched name"),
]


def main():
    missed = []
    with tempfile.TemporaryDirectory(prefix="local-laws-mutate-") as scratch:
        copy = Path(scratch).resolve()
        shutil.copytree(REPO / "tests", copy / "tests", ignore=IGNORE)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(copy))
        for module, label, old, new in MUTATIONS:
            shutil.rmtree(copy / "local_laws", ignore_errors=True)
            shutil.copytree(REPO / "local_laws", copy / "local_laws", ignore=IGNORE)
            path = copy / "local_laws" / module
            code = path.read_text()
            if code.count(old) != 1:
                raise SystemExit(f"{module}: the code behind '{label}' has changed; update its mutation")
            path.write_text(code.replace(old, new))
            result = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-x", "--rootdir", str(copy), str(copy / "tests")], capture_output=True, text=True, env=env, cwd=copy)
            failed = next((line for line in result.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))), "")
            print(f"exit {result.returncode}  {module:10} {label:46} {failed[:100]}", flush=True)
            if result.returncode != 1:
                missed.append(label)
    print(f"not caught: {missed}" if missed else f"all {len(MUTATIONS)} mutations were caught")
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
