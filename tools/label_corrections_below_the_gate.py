"""Label the corrections fitted below their gate (operator question 16, ruled
(B) 2026-09-27; question 23, ruled (A) 2026-09-28; built 2026-09-29).

    # what it would write; reads only, through the read-only door
    python tools/label_corrections_below_the_gate.py --database PATH

    # a scratch copy: write the labels
    python tools/label_corrections_below_the_gate.py --database PATH --write

    # the live record, AFTER the release that carries the table
    python tools/label_corrections_below_the_gate.py --database var/gridiron.db --write --live

THE RULING, in the operator's words (question 23): "(A). The page's count and
the fit's own gate both move to the key, for fits from the release forward.
The 63 existing fits stay as written; any that falls short of its gate on the
corrected count is labelled 'fitted below its gate' and can never be
activated."

WHAT IT SELECTS, by rule and nothing else (`correction.below_their_gates`),
from each fit's own record: a row that was FITTED -- not a placeholder, whose
`n_train` under the gate says nothing was fitted -- whose corrected count,
the distinct bets on question 17's key among the settled forecasts its gate
counted (its category's, settled before its own fitted instant), is below its
gate of fifty. A fit written from question 16's release on was gated on that
count and cannot be selected.

THEN IT CHECKS the selection against the ruling. The ruled POPULATION is the
fits on the record when question 23 was ruled -- written before
`RULED_AMONG_THE_FITS_WRITTEN_BEFORE`, which must be exactly the 63 the
ruling names -- and the ruled SET is `RULED`: it writes ONLY when the rule's
selection restricted to that population is exactly `RULED`, every one of them
selected by the arithmetic, none carrying an activation, and each fit's own
`n_train` given back by the record as the forecasts its gate counted.
Anything else is refused, loudly and writing nothing: a label is permanent,
and a selection that has drifted from the ruling is the operator's, not this
script's (question 9's precedent, `tools/regrade_return_on_stake.py`).

WHAT IT LEAVES, NAMED. The rule also selects fits written after the ruling
and before the release -- 81, 85, 86, 87 and 89 on 2026-09-29, written by the
weekly refit of 28 September on the gate as it then counted -- and whether
they are "the 63 existing fits" is question 31 (docs/REPAIR_STATE.md). They
are listed as waiting for it and none is written. The placeholders are never
selected: "fitted below its gate" would be false of a row never fitted, and
the schema refuses the label on one. A later ruling changes a constant here
and the tool is run again (labels only add; the ones written stand).

REFUSED ON THE LIVE RECORD without `--live`, and `--live` refused on anything
else; the record is known by the file's identity (`db.is_the_live_record_file`).
It applies no schema: a record not yet opened under the schema that carries
`correction_gate_labels` is refused by name (any scheduled pass or the
server's start after the release opens it so, through `db.init`).

IDEMPOTENT. A fit already labelled is counted and skipped; the table refuses a
second label anyway, and the first stands. All the labels are written in one
transaction, so the record never holds some of them.
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

from gridiron import correction, db  # noqa: E402

#: THE POPULATION QUESTION 23 RULED ON: "The 63 existing fits" -- the fits on
#: the record when the ruling was saved (docs/briefs/2026-09-28-rulings.md,
#: 01:50:37Z on 28 September), fits 1-63, written 31 August to 21 September.
#: Read by this instant from each fit's own `fitted_utc`, and checked to be
#: sixty-three, so the population is the ruling's and never a list.
RULED_AMONG_THE_FITS_WRITTEN_BEFORE = "2026-09-28T01:50:37Z"
RULED_POPULATION_SIZE = 63

#: THE FOUR EVERY READING OF QUESTION 31 COVERS (the default taken in the
#: operator's absence, 2026-09-29 ~01:50Z, docs/REPAIR_STATE.md question 31):
#: among the 63 existing when ruled, fitted, and short of the gate on the key
#: -- fit 33, MLB total, reasoning pass, version 1 (76 forecasts, 48
#: questions); fits 59, 61 and 63, UFC distance, moneyline and rounds,
#: statistical, version 3 (56 forecasts, 32 questions each).
RULED = (33, 59, 61, 63)

#: SELECTED BY THE RULE AMONG THE 63 AND LEFT UNLABELLED BY THE OPERATOR'S
#: WORDS. Empty: the ruling labels every one of them the rule selects.
LEFT_BY_RULING: tuple[int, ...] = ()


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED, NOTHING WRITTEN: " + why)
        super().__init__(2)


def _line(got: dict) -> str:
    return (f"  fit {got['id']} ({got['sport']} {got['market_type']}, "
            f"{got['forecaster']}, version {got['version']}, fitted "
            f"{got['fitted_utc']}): {got['count_used']} settled forecasts "
            f"past its gate of {got['gate']}, {got['corrected_count']} "
            f"questions on the key"
            + ("  [carries an activation]" if got["active"] else "")
            + ("  [already labelled]" if got["already"] else ""))


def population(conn) -> set[int]:
    """The fits question 23 ruled on, read by their own instant."""
    return {r[0] for r in conn.execute(
        "SELECT id FROM calibration_corrections WHERE fitted_utc < ?",
        (RULED_AMONG_THE_FITS_WRITTEN_BEFORE,))}


def check(selected: list[dict], ruled_on: set[int]) -> tuple[list[int], list[dict]]:
    """(the ids to write, the selected fits waiting for question 31), or
    `Refused` naming how the selection differs from the ruling."""
    if len(ruled_on) != RULED_POPULATION_SIZE:
        raise Refused(
            f"the record holds {len(ruled_on)} fits written before "
            f"{RULED_AMONG_THE_FITS_WRITTEN_BEFORE}, not the "
            f"{RULED_POPULATION_SIZE} the ruling names: the population is not "
            f"the ruling's, and this goes back to the operator.")
    by_id = {g["id"]: g for g in selected}
    within = {i for i in by_id if i in ruled_on}
    ruled, left = set(RULED), set(LEFT_BY_RULING)
    unsupported = sorted((ruled | left) - within)
    if unsupported:
        raise Refused(
            f"fit(s) {unsupported} are named by the ruling, and the rule does "
            f"not select them among the {RULED_POPULATION_SIZE}: on the record "
            f"as it stands each is a placeholder, clear of its gate on the key, "
            f"or not among the fits ruled on. A label is permanent; this goes "
            f"back to the operator.")
    unruled = sorted(within - ruled - left)
    if unruled:
        raise Refused(
            f"among the {RULED_POPULATION_SIZE} the rule selects "
            f"{len(within)} fits and the ruling names {len(ruled)} "
            f"({', '.join(str(i) for i in sorted(ruled))}). Selected and not "
            f"ruled on:\n" + "\n".join(_line(by_id[i]) for i in unruled)
            + "\nA label is permanent; which to label is the operator's "
            "(docs/REPAIR_STATE.md).")
    in_force = sorted(i for i in ruled if by_id[i]["active"])
    if in_force:
        raise Refused(
            f"fit(s) {in_force} carry an activation. The ruling says a labelled "
            f"fit can never be activated, not that one in force is taken out "
            f"of force: that is the operator's question.")
    off = sorted(i for i in ruled if by_id[i]["count_used"] != by_id[i]["counted"])
    if off:
        raise Refused(
            f"fit(s) {off}: the record does not give back the fit's own "
            f"n_train as the forecasts its gate counted, so 'the count the fit "
            f"used' cannot be read off its record. This goes back to the "
            f"operator.")
    waiting = [by_id[i] for i in sorted(set(by_id) - ruled_on)]
    return sorted(ruled), waiting


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator question 23: label the correction fits whose "
                    "count on the key is below their gate 'fitted below its "
                    "gate'")
    parser.add_argument("--database", required=True,
                        help="the database whose correction fits are labelled")
    parser.add_argument("--write", action="store_true",
                        help="write the labels; without it, only say what "
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
            f"record, found by its identity). Its labels are written only "
            f"with --live, after the release that carries the table")

    why = ("operator question 23: listing the correction fits whose count on "
           "the key is below their gate, before labelling them")
    # DRY MEANS READ-ONLY, whatever the file: the read-only door, which SQLite
    # itself will not write through. The write goes through `db.connect`,
    # which refuses the record under any verification, and applies no schema.
    conn = db.connect(path) if args.write else db.read_only(path, why)
    try:
        if not db.table_columns(conn, correction.LABELS):
            raise Refused(
                f"{path} has no {correction.LABELS} table: it has not been "
                f"opened under the schema that carries it (db.init does that, "
                f"on any scheduled pass or the server's start after the "
                f"release)")
        selected = correction.below_their_gates(conn)
        print(f"{len(selected)} fit(s) on the record were fitted on the "
              f"settled forecasts past their gate and are short of it on the "
              f"key:")
        for got in selected:
            print(_line(got))
        ids, waiting = check(selected, population(conn))
        print(f"the ruling's set among the {RULED_POPULATION_SIZE} fits written "
              f"before {RULED_AMONG_THE_FITS_WRITTEN_BEFORE}, verified against "
              f"each fit's record: {', '.join(str(i) for i in ids)}")
        if LEFT_BY_RULING:
            print(f"selected and left unlabelled by the ruling: "
                  f"{', '.join(str(i) for i in LEFT_BY_RULING)}")
        if waiting:
            print(f"selected by the rule, written after the ruling, and "
                  f"WAITING FOR QUESTION 31 (none is written): "
                  f"{', '.join(str(g['id']) for g in waiting)}")
        if not args.write:
            todo = [g for g in selected if g["id"] in ids and not g["already"]]
            print(f"nothing written. --write would label {len(todo)} "
                  f"'fitted below its gate'.")
            return 0
        try:
            wrote = correction.write_labels(conn, ids)
        except (RuntimeError, ValueError) as exc:
            raise Refused(str(exc)) from None
        print(f"wrote {wrote['written']} label(s); {wrote['already']} already "
              f"labelled")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
