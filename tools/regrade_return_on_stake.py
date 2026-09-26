"""Re-grade the recommendations the yes-price divisor let through
(GRIDIRON_REPAIR item 4, the operator's ruling of 2026-09-23).

    # what it would write; reads only, through the read-only door
    python tools/regrade_return_on_stake.py --database PATH

    # a scratch copy: write the labels
    python tools/regrade_return_on_stake.py --database PATH --write

    # the live record, AFTER the release that carries the table
    python tools/regrade_return_on_stake.py --database var/gridiron.db --write --live

THE RULING, in the operator's words: "Return-on-stake denominator: a no-side
edge divides by the no-side cost. Re-grade the three recommendations it let
through as 'would not have cleared'."

WHAT IT SELECTS, by rule and nothing else (`recommend.let_through_by_the_yes_price`):
every standing recommendation written once the bar was declared whose edge
cleared 5% of the yes price -- the divisor the bar used until 2026-09-26 --
and does not clear 5% of what its own side cost, recomputed from the row's
frozen side, price and edge through the bar itself. Never by outcome.

THEN IT CHECKS the selection against the set the ruling names, and refuses,
loudly and writing nothing, if they differ by one row. A re-grade is
permanent; a selection that has drifted from the ruling is a question for the
operator, not for this script -- the precedent of `tools/void_fs5.py`.

MEASURED 2026-09-26, read-only on the live record: the rule selects FOUR --
recs 3, 10 and 26, the three THE READ of 2026-09-23 counted, and rec 56,
written at 05:21:25Z on 24 September by the logon catch-up, after the ruling
and before the fix. The ruling says "the three". So until the operator rules
(docs/REPAIR_STATE.md, "Questions for the operator") this tool REFUSES on the
live record and names rec 56 and its arithmetic. His answer is one line
below: rec 56 joins `RULED`, or it goes in `LEFT_BY_RULING` -- selected by
the rule and left unlabelled by his words.

REFUSED ON THE LIVE RECORD without `--live`, and `--live` refused on anything
else; the record is known by the file's identity (`db.is_the_live_record_file`),
the door the dated migration and the prompt reconstruction ask. It applies no
schema: a record not yet opened under the schema that carries
`recommendation_regrades` is refused by name (any scheduled pass or the
server's start after the release opens it so, through `db.init`).

IDEMPOTENT. A recommendation already re-graded is counted and skipped; the
table refuses a second row anyway, and the first stands. All the labels are
written in one transaction, so the record never holds half of them.
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

from gridiron import db  # noqa: E402
from gridiron.market import recommend  # noqa: E402

#: THE THREE THE RULING NAMES -- "the three recommendations it let through",
#: as THE READ of 2026-09-23 counted them.
RULED = (3, 10, 26)

#: SELECTED BY THE RULE AND LEFT UNLABELLED BY THE OPERATOR'S WORDS. Empty
#: until he rules on rec 56 (docs/REPAIR_STATE.md): nothing is left out on
#: the session's own reading.
LEFT_BY_RULING: tuple[int, ...] = ()


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED, NOTHING WRITTEN: " + why)
        super().__init__(2)


def _line(got: dict) -> str:
    return (f"  rec {got['id']} ({got['sport']} {got['market']}, {got['side']} "
            f"side, written {got['created_utc']}): {got['edge_cents']:+.2f}c at "
            f"a {got['price'] * 100:.1f}c yes price -- "
            f"{got['return_on_yes_price']:.2%} of the yes price, "
            f"{got['return_on_cost']:.2%} of the {got['side_cost'] * 100:.1f}c "
            f"it cost" + ("  [already re-graded]" if got["already"] else ""))


def check(selected: list[dict]) -> list[int]:
    """The ids to write, or `Refused` naming how the rule's selection differs
    from the ruling's set. Every ruled id must be selected by the rule -- its
    arithmetic verified -- and every selected id must be ruled on."""
    ids = {g["id"] for g in selected}
    ruled, left = set(RULED), set(LEFT_BY_RULING)
    unsupported = sorted((ruled | left) - ids)
    if unsupported:
        raise Refused(
            f"recommendation(s) {unsupported} are named by the ruling, and the "
            f"rule does not select them: on the record as it stands they "
            f"clear on the cost of their own side, were never let through by "
            f"the yes price, or are withdrawn. A re-grade is permanent; this "
            f"goes back to the operator.")
    unruled = sorted(ids - ruled - left)
    if unruled:
        by_id = {g["id"]: g for g in selected}
        raise Refused(
            f"the rule selects {len(ids)} recommendations and the ruling names "
            f"{len(ruled)} ({', '.join(str(i) for i in sorted(ruled))}). "
            f"Selected and not ruled on:\n"
            + "\n".join(_line(by_id[i]) for i in unruled)
            + "\nA re-grade is permanent and the ruling says \"the three\"; "
            f"which to label is the operator's (docs/REPAIR_STATE.md).")
    return sorted(ruled)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GRIDIRON_REPAIR item 4: re-grade the recommendations the "
                    "yes-price divisor let through as 'would not have cleared'")
    parser.add_argument("--database", required=True,
                        help="the database whose recommendations are re-graded")
    parser.add_argument("--write", action="store_true",
                        help="write the re-grades; without it, only say what "
                             "they would be")
    parser.add_argument("--live", action="store_true",
                        help="the database is the operator's record, and this "
                             "is the run that writes to it")
    args = parser.parse_args(argv)
    path = Path(args.database)
    if not path.exists():
        raise Refused(f"there is no database at {path}")
    live = db.is_the_live_record_file(path)
    if args.live and not live:
        raise Refused(f"--live names the operator's record, and {path} is not "
                      f"the same file as it")
    if args.write and live and not args.live:
        raise Refused(
            f"{path} is the operator's record (the same file as the live "
            f"record, found by its identity). Its re-grades are written only "
            f"with --live, after the release that carries the table")

    why = ("GRIDIRON_REPAIR item 4: listing the recommendations the yes-price "
           "divisor let through, before re-grading them")
    # DRY MEANS READ-ONLY, whatever the file: the read-only door, which SQLite
    # itself will not write through. The write goes through `db.connect`,
    # which refuses the record under any verification, and applies no schema.
    conn = db.connect(path) if args.write else db.read_only(path, why)
    try:
        selected = recommend.let_through_by_the_yes_price(conn)
        print(f"{len(selected)} recommendation(s) cleared 5% of the yes price "
              f"and do not clear 5% of what their own side cost:")
        for got in selected:
            print(_line(got))
        ids = check(selected)
        print(f"the ruling's set, verified against the arithmetic: "
              f"{', '.join(str(i) for i in ids)}")
        if LEFT_BY_RULING:
            print(f"selected and left unlabelled by the ruling: "
                  f"{', '.join(str(i) for i in LEFT_BY_RULING)}")
        if not args.write:
            todo = [g for g in selected if g["id"] in ids and not g["already"]]
            print(f"nothing written. --write would re-grade {len(todo)} as "
                  f"'would not have cleared'.")
            return 0
        try:
            wrote = recommend.write_regrades(conn, ids)
        except (RuntimeError, ValueError) as exc:
            raise Refused(str(exc)) from None
        print(f"wrote {wrote['written']} re-grade(s); {wrote['already']} "
              f"already re-graded")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
