"""Restate every close the old closer made, by the one rule.

    python tools/restate_closes.py            # what it would write
    python tools/restate_closes.py --write    # write it

WHY (GRIDIRON_REPAIR item 1, 2026-09-23). Until that date the close was "the
last claim written before kickoff", and for a recommended prediction that was
the claim it had been priced from: every close equalled the price paid and
every closing-line value read 0.00c. Those closes stand as recorded -- a
recommendation's close is written once, and LAW 3 does not bend for a defect.

This writes the account BESIDE each one, in `recommendation_closes`: the true
close where the record holds a later near-start read of the same contract from
before the start, UNMEASURED where it does not. Every row it writes is marked
`restated`, and nothing counts a restated close inside the closing line: it
was computed by somebody who already knew how the games went.

Idempotent. A recommendation that already has its account is never touched,
and the table refuses a second one.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import db  # noqa: E402
from gridiron.market import recommend  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="write the restated closes; without it, only count")
    parser.add_argument("--database", default=None)
    args = parser.parse_args(argv)

    # DRY MEANS READ-ONLY. `open_db` applies the schema, which is a write; the
    # dry run opens a query-only handle instead and so cannot change the file
    # it is describing.
    if args.write:
        conn = db.open_db(args.database)
    elif args.database is None:
        conn = db.read_the_live_record(
            "counting the closes the old closer made, before restating them")
    else:
        # THROUGH THE DOOR, NOT ROUND IT (schema ruling 6, 2026-09-24;
        # 2026-09-25). This was a raw `sqlite3.connect` of whatever path was
        # named, and the path could be the operator's record.
        conn = db.read_only(
            args.database,
            "counting the closes the old closer made, before restating them")
    report = recommend.restate_old_closes(conn, write=args.write)
    print(f"{report['rows']} closes made by the old closer carry no account")
    for (sport, market), got in sorted(report["by"].items()):
        clv = got["clv"]
        mean = f"{sum(clv) / len(clv):+.2f}c" if clv else "none"
        print(f"  {sport} {market}: {got['measured']} with a later read of "
              f"their own contract (mean {mean}), {got['unmeasured']} unmeasured")
    if not args.write:
        print("nothing written. Pass --write to record them, marked restated.")
        return 0
    print(f"wrote {report['written']} restated rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
