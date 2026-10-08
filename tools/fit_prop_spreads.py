"""Fit how far each stat strays from the model's projection: the fitting run of
M4 v1 (GRIDIRON_ENTRY_CHECK step 2; ruling D of 2026-10-05; built 2026-10-07).

    # what it would write; reads only, through the read-only door
    python tools/fit_prop_spreads.py --database PATH

    # a test world or a scratch copy: write the fits
    python tools/fit_prop_spreads.py --database PATH --write

    # the live record, AFTER the release that carries the table, dry first
    python tools/fit_prop_spreads.py --database var/gridiron.db --live
    python tools/fit_prop_spreads.py --database var/gridiron.db --write --live

RULING D, in the operator's words: "Step 2 needs the model's chance at any
line: a first version of M4, P(stat over x) from the model's projection and a
per-stat spread fitted on settled history. Written inactive; shown as 'not yet
proven' until its record clears 100 graded legs."

WHAT IT DOES (`m4.refit`): for each NFL prop stat whose forecasts store a
projection -- receptions and passing touchdowns; never a yardage stat, which
stores none (reading (a)) -- the spread of the declared form (`m4.FORM`,
declared `m4.FORM_DECLARED`), by the arithmetic declared (`m4.spread_of`):
the mean, over the stat's settled standing forecasts carrying a projection,
one per player and game, of the stat he recorded less the projection,
squared, over the projection. With `--write`, one dated, append-only row of
`prop_spread_fits` per stat whose fit differs from its latest, in one
transaction. WRITTEN INACTIVE: nothing activates a fit (no activation row is
written; none exists), and every chance M4 states from one is drawn "not yet
proven", 0 of 100 graded legs, until step 3 grades legs (reading (c)).

HOW THE OPERATOR'S RECORD GETS ITS FIRST FIT (recorded in docs/REPAIR_STATE.md,
2026-10-07): by this tool, after the release that carries the table, dry
first -- the void tools' precedent. No ruling lets the weekly recalibration
task fit M4, so it does not; whether it should refit each week is operator
question 44 (default: this tool by hand only).

REFUSED ON THE LIVE RECORD without `--live`, and `--live` refused on anything
else; the record is known by the file's identity (`db.is_the_live_record_file`).
It applies no schema: a database not yet opened under the schema that
carries `prop_spread_fits` is refused by name with `--write` (any scheduled
pass or the server's start after the release opens it so, through
`db.init`). Dry, it reads through the read-only door, which SQLite itself
will not write through.

IDEMPOTENT: a stat whose latest fit was worked from the same forecasts with
the same spread gets no second row.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import db, m4  # noqa: E402


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED, NOTHING WRITTEN: " + why)
        super().__init__(2)


def _line(got: dict) -> str:
    if got.get("why_not"):
        return f"  {got['stat']}: no fit -- {got['why_not']}"
    said = (f"  {got['stat']}: spread {got['spread']:.6f} on {got['n']} settled "
            f"player-games (forecasts {', '.join(str(i) for i in got['forecasts'])})")
    if "written" in got:
        said += (f"  [written as fit {got['written']}]" if got["written"]
                 else "  [the same as its latest fit: not written again]")
    return said


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ruling D: fit how far each NFL prop stat strays from the model's "
                    "projections on settled history, written inactive")
    parser.add_argument("--database", required=True,
                        help="the database whose stats are fitted")
    parser.add_argument("--write", action="store_true",
                        help="write the fits; without it, only say what they would be")
    parser.add_argument("--live", action="store_true",
                        help="the database is the operator's record, and this is the "
                             "run that reads or writes it")
    args = parser.parse_args(argv)
    path = Path(args.database)
    if not path.exists():
        raise Refused(f"there is no database at {path}")
    live = db.is_the_live_record_file(path)
    if args.live and not live:
        raise Refused(f"--live names the operator's record, and {path} is not the "
                      f"same file as it")
    if live and not args.live:
        raise Refused(
            f"{path} is the operator's record (the same file as the live record, found "
            f"by its identity). It is read or written only with --live, after the "
            f"release that carries the table")
    why = ("ruling D: fitting how far each NFL prop stat strays from the model's "
           "projections on settled history (M4 v1), read-only")
    # DRY MEANS READ-ONLY, whatever the file: the read-only door. The write
    # goes through `db.connect`, which refuses the record under any
    # verification, and applies no schema.
    conn = db.connect(path) if args.write else db.read_only(path, why)
    try:
        if args.write and not m4.has_the_table(conn):
            raise Refused(f"{path} holds no {m4.TABLE} table: it has not been opened "
                          f"under the schema that carries it (db.init brings it)")
        report = m4.refit(conn, write=args.write)
    finally:
        conn.close()
    print(f"M4 v1, the declared form {m4.FORM!r} (declared {m4.FORM_DECLARED}); "
          f"{'written' if args.write else 'dry, nothing written'}:")
    for got in report:
        print(_line(got))
    print("Written inactive: nothing activates a fit, and every chance read from one is "
          f"drawn not yet proven, {m4.graded_legs()} of {m4.PROVEN_AT} graded legs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
