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
    ("verify.py", "crosswalk judged against a rejected table", "None if governments is None else {", "set() if governments is None else {"),
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
