"""python -m local_laws {run,verify,card,harvest-ny}: build the dataset and publish it, check what is published, re-render its card, or read New York's local-law filings into a snapshot to build from."""

import argparse
import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from . import REPO_ID, locus, nylaws
from .build import build, code_version, unchanged
from .card import render
from .census import SourceChanged
from .http import Blocked, Fetcher, Unavailable
from .store import CARD, MANIFEST, HubStore, LocalStore, Superseded

# Exit codes besides 0 (done) and 1 (verify found problems, or a commit was superseded).
STOPPED = 2


def open_store(args, write=False):
    """Reads are anonymous (token=False): the dataset is public. A write uses the token huggingface_hub finds, such as HF_TOKEN, and creates the repo if it does not exist."""
    if args.local:
        return LocalStore(args.local)
    return HubStore(args.repo, token=None if write else False, create=write)


def publishable(args):
    """The code version to record, or None when writing to the Hub from code that is not committed: a published build names the commit that made it."""
    code = code_version()
    if not args.local and (code["commit"] is None or code["dirty"] is not False):
        print("refusing to write to the Hub from a working tree with uncommitted changes (or outside git): commit first, so the manifest names the code that built it", file=sys.stderr)
        return None
    return code


def cmd_run(args):
    code = publishable(args)
    if code is None:
        return STOPPED
    store = open_store(args, write=True)
    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="local-laws-"))
    workdir.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher()
    try:
        snapshot = nylaws.load(args.ny_snapshot) if args.ny_snapshot else None
        manifest, files = build(fetcher, workdir, ny_snapshot=snapshot, code=code)
        stats = manifest["stats"]
        summary = {"governments": stats["governments"], "locus_jurisdictions": stats["locus"]["jurisdictions"], "matched": stats["locus"]["matched"],
                   "ny_filings": stats["ny"]["filings"], "ny_matched": sum(stats["ny"]["matches"][name]["filings"] for name in nylaws.MATCHED),
                   "ny_index_rows": stats["ny_index"]["rows"], "ny_index_matched": sum(stats["ny_index"]["matches"][name]["rows"] for name in nylaws.MATCHED), "requests": fetcher.requests}
        if unchanged(store, manifest):
            print(json.dumps(dict(summary, commit=None, unchanged=True), indent=1))
            return 0
        read = manifest["sources"]["ny_local_laws"]["finished_at"][:10]
        message = f"Build from the 2022 Census of Governments, LOCUS-v1 {locus.REVISION[:12]} and New York's local laws as of {read}" + (f" (pipeline {code['commit'][:12]})" if code["commit"] else "")
        oid = store.commit({repo_path: str(local) for repo_path, local in files.items()}, message)
        print(json.dumps(dict(summary, commit=oid, unchanged=False), indent=1))
        return 0
    except (SourceChanged, Blocked, Unavailable) as error:
        print(f"stopped, nothing written: {type(error).__name__}: {error}", file=sys.stderr)
        return STOPPED
    except Superseded as error:
        print(f"not written: {error}", file=sys.stderr)
        return 1
    finally:
        fetcher.close()
        if not args.workdir:
            shutil.rmtree(workdir, ignore_errors=True)


def cmd_verify(args):
    from .verify import verify

    store = open_store(args)
    fetcher = None if args.offline else Fetcher()
    try:
        report = verify(store, fetcher=fetcher, stated_rows=None if args.offline else locus.stated_rows)
    except (SourceChanged, Blocked, Unavailable) as error:
        print(f"stopped: {type(error).__name__}: {error}", file=sys.stderr)
        return STOPPED
    finally:
        if fetcher:
            fetcher.close()
    print(json.dumps(report, indent=1))
    return 1 if report["problems"] else 0


def cmd_card(args):
    """Re-renders the card from the published manifest, for a card change that needs no rebuild."""
    if publishable(args) is None:
        return STOPPED
    store = open_store(args, write=True)
    text = store.read_text(MANIFEST)
    if text is None:
        print(f"no {MANIFEST}: run `python -m local_laws run` first", file=sys.stderr)
        return STOPPED
    card = render(json.loads(text))
    if store.read_text(CARD) == card:
        print("card unchanged")
        return 0
    with tempfile.TemporaryDirectory(prefix="local-laws-card-") as directory:
        path = Path(directory) / CARD
        path.write_text(card)
        try:
            store.commit({CARD: str(path)}, "Update dataset card")
        except Superseded as error:
            print(f"not written: {error}", file=sys.stderr)
            return 1
    print("card updated")
    return 0


def cmd_harvest_ny(args):
    """Reads New York's local-law category into a snapshot file that `run --ny-snapshot` builds from, so a build can be repeated without reading the API again."""
    fetcher = Fetcher()
    try:
        snapshot = nylaws.harvest(fetcher)
    except (SourceChanged, Blocked, Unavailable) as error:
        print(f"stopped, nothing written: {type(error).__name__}: {error}", file=sys.stderr)
        return STOPPED
    finally:
        fetcher.close()
    nylaws.save(snapshot, args.out)
    print(json.dumps({"out": args.out, "total": snapshot["total"], "years": snapshot["years"], "started_at": snapshot["started_at"], "finished_at": snapshot["finished_at"], "requests": fetcher.requests}, indent=1))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="local_laws", description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name, handler, help_text):
        sub = commands.add_parser(name, help=help_text, allow_abbrev=False)
        target = sub.add_mutually_exclusive_group()
        target.add_argument("--repo", default=REPO_ID, help=f"Hugging Face dataset repo (default {REPO_ID})")
        target.add_argument("--local", help="a local directory instead of the Hub, for tests and dry runs")
        sub.set_defaults(handler=handler)
        return sub

    run = add("run", cmd_run, "download the sources, check them, build the tables and commit them with the manifest and card")
    run.add_argument("--workdir", help="keep scratch files here (default: a temporary directory, deleted afterwards); LOCUS's download needs about 2 GB")
    run.add_argument("--ny-snapshot", help="build New York's table from a snapshot harvest-ny wrote, instead of reading the API again (about 1,500 requests)")
    add("verify", cmd_verify, "check the published files against the manifest, each other, CG2200ORG02, LOCUS's card, the NY API's counts at the reading and the NY index's release").add_argument(
        "--offline", action="store_true", help="skip the checks that download: CG2200ORG02, LOCUS's card and the NY index's release")
    add("card", cmd_card, "re-render README.md from the published manifest")
    harvest = commands.add_parser("harvest-ny", help="read New York's local-law filings from the Department of State's API into a snapshot file", allow_abbrev=False)
    harvest.add_argument("--out", required=True, help="where to write the snapshot (gzipped JSON)")
    harvest.set_defaults(handler=cmd_harvest_ny)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "httpcore", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    from huggingface_hub.utils import disable_progress_bars

    disable_progress_bars()
    return args.handler(args)
