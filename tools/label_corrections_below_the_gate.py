"""Label the corrections fitted below their gate (operator question 16, ruled
(B) 2026-09-27; question 23, ruled (A) 2026-09-28; question 31, ruled (B) and
(B) 2026-09-29; built 2026-09-29).

    # what it would write; reads only, through the read-only door
    python tools/label_corrections_below_the_gate.py --database PATH

    # a scratch copy: write the labels
    python tools/label_corrections_below_the_gate.py --database PATH --write

    # the live record, AFTER the release that carries the table
    python tools/label_corrections_below_the_gate.py --database var/gridiron.db --write --live

THE RULINGS, in the operator's words. Question 23: "(A). The page's count and
the fit's own gate both move to the key, for fits from the release forward.
The 63 existing fits stay as written; any that falls short of its gate on the
corrected count is labelled 'fitted below its gate' and can never be
activated." Question 31 (docs/briefs/2026-09-29-rulings.md): "(i): (B). Label
every fitted row written before Q16's release that falls short on the key:
33, 59, 61, 63, 81, 85, 86, 87, 89." and "(ii): (B). No labels on
placeholders; they were never fitted."

WHAT IT SELECTS, by rule and nothing else (`correction.below_their_gates`),
from each fit's own record: a row that was FITTED -- not a placeholder, whose
`n_train` under the gate says nothing was fitted -- whose corrected count,
the distinct bets on question 17's key among the settled forecasts its gate
counted (its category's, settled before its own fitted instant), is below its
gate of fifty.

THE POPULATION IS EVERY FIT ON THE RECORD, AND THAT IS THE RULING'S (question
31, 2026-09-29): "every fitted row written before Q16's release". A fit
written from the release on was gated on the key at its own instant
(`correction.refit_all`), so it cannot be short as of that instant and the
rule never selects it: the rule's selection over every fit IS the fits
written before the release that fall short on the key. No instant is read
and no size is checked -- until 2026-09-29 the population was "the 63" read
by the instant question 23 was ruled, and the five the weekly refit of 28
September wrote after it waited for question 31; the ruling ended both.

THEN IT CHECKS the selection against the ruling: it writes ONLY when the
rule's selection is exactly `RULED`, every one of them selected by the
arithmetic, none carrying an activation, and each fit's own `n_train` given
back by the record as the forecasts its gate counted. Anything else is
refused, loudly, naming the difference and writing nothing: a fit the weekly
recalibration writes before the release that falls short on the key is
selected by the same rule and refused until ruled, and so is a fit written
from the release on that the rule selects all the same (a void stamped back
before it, or a row written by hand; neither is on the record). A label is
permanent, and a selection that has drifted from the ruling is the
operator's, not this script's (question 9's precedent,
`tools/regrade_return_on_stake.py`).

THE PLACEHOLDERS are never selected: "fitted below its gate" would be false
of a row never fitted, and the schema refuses the label on one. A later
ruling changes a constant here and the tool is run again (labels only add;
the ones written stand).

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

#: THE POPULATION, in the ruling's words (question 31, 2026-09-29). Read as
#: every fit on the record: a fit written from question 16's release on is
#: gated on the key at its own instant and cannot be selected.
POPULATION = "every fitted row written before question 16's release"

#: THE NINE QUESTION 31 RULED (B) AND (B) ON 2026-09-29, replacing the four
#: the default of 01:50Z labelled: every fitted row written before question
#: 16's release that falls short of its gate on the key. Fit 33, MLB total,
#: reasoning pass, version 1 (76 forecasts, 48 questions); fits 59, 61 and
#: 63, UFC distance, moneyline and rounds, statistical, version 3 (56
#: forecasts, 32 questions each) -- the four among the 63 on the record when
#: question 23 was ruled; and, written by the weekly refit of 28 September
#: 13:00:01Z, fit 81, NFL point spread, statistical, version 3 (60, 41), fits
#: 85, 87 and 89, UFC distance, moneyline and rounds, statistical, version 4
#: (85, 49 each), and fit 86, UFC moneyline, reasoning pass, version 4 (63,
#: 49). None is in force.
RULED = (33, 59, 61, 63, 81, 85, 86, 87, 89)

#: SELECTED BY THE RULE AND LEFT UNLABELLED BY THE OPERATOR'S WORDS. Empty:
#: the ruling labels every one of them the rule selects, and no placeholder
#: (question 31 (ii)), which the rule never selects.
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


def check(selected: list[dict]) -> list[int]:
    """The ids to write -- the rule's selection over every fit on the
    record, when it is exactly the ruling's -- or `Refused` naming how the
    selection differs from the ruling."""
    by_id = {g["id"]: g for g in selected}
    ruled, left = set(RULED), set(LEFT_BY_RULING)
    unsupported = sorted((ruled | left) - set(by_id))
    if unsupported:
        raise Refused(
            f"fit(s) {unsupported} are named by the ruling, and the rule does "
            f"not select them: on the record as it stands each is a "
            f"placeholder, clear of its gate on the key, or no fit at all. A "
            f"label is permanent; this goes back to the operator.")
    unruled = sorted(set(by_id) - ruled - left)
    if unruled:
        raise Refused(
            f"the rule selects {len(by_id)} fits and the ruling names "
            f"{len(ruled)} ({', '.join(str(i) for i in sorted(ruled))}), "
            f"{POPULATION} that falls short on the key. Selected and not "
            f"ruled on:\n" + "\n".join(_line(by_id[i]) for i in unruled)
            + "\nA fit written before the release that falls short on the "
            "key is selected by the same rule, and one written from it on was "
            "gated on the key and is selected only if its record was made "
            "otherwise. A label is permanent; which to label is the "
            "operator's (docs/REPAIR_STATE.md).")
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
    return sorted(ruled)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator questions 23 and 31: label the correction fits "
                    "whose count on the key is below their gate 'fitted below "
                    "its gate'")
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

    why = ("operator questions 23 and 31: listing the correction fits whose "
           "count on the key is below their gate, before labelling them")
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
        ids = check(selected)
        print(f"the ruling's set (question 31), {POPULATION} that falls short "
              f"on the key -- the rule's selection over every fit on the "
              f"record, since a fit from the release on is gated on the key -- "
              f"verified against each fit's record: "
              f"{', '.join(str(i) for i in ids)}")
        if LEFT_BY_RULING:
            print(f"selected and left unlabelled by the ruling: "
                  f"{', '.join(str(i) for i in LEFT_BY_RULING)}")
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
