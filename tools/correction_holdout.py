"""Measure a correction under the gate, and write its dated row: a measured
activation only when it passes, or the ruled withdrawal (operator question 32,
ruled 2026-09-29, second set; built the same day).

    # the measurement, read only, through the read-only door
    python tools/correction_holdout.py --database PATH --correction 71

    # a copy: write its measured activation -- only if it passes
    python tools/correction_holdout.py --database PATH --correction 71 --write

    # the ruled withdrawal: what it would write, then write it
    python tools/correction_holdout.py --database PATH --correction 71 --withdraw
    python tools/correction_holdout.py --database PATH --correction 71 --withdraw --write

    # the live record, AFTER the release that carries the table: the
    # withdrawal first, then the measurement, which activates only on a pass
    python tools/correction_holdout.py --database var/gridiron.db --correction 71 --withdraw --write --live
    python tools/correction_holdout.py --database var/gridiron.db --correction 71 --write --live

THE RULING, in the operator's words: "Q32: corrections activate through the
same gate as model fits. Every correction row is written inactive. Activation
is its own dated append-only row, written only when the holdout bootstrap
interval of the Brier improvement excludes zero, measured on distinct bets by
the key, per forecaster; a tie goes to the uncorrected probability." And:
"Fit 71: withdrawn now by a dated append-only row, reason 'activated under
the pre-Q32 rule: single holdout comparison, pooled rows'. Then run the new
gate on it read-only and report the interval. If it passes, activation is a
new dated row; if not, it stays withdrawn."

WHAT IT MEASURES (`correction.measure`): the correction's category's settled
questions before it was fitted, one forecast per distinct bet on the key,
in the order they settled; a correction refit on the earliest four fifths and
scored on the latest fifth; the Brier improvement (raw minus corrected) on
those questions and its paired bootstrap 95% interval, seeded as the model
gate's is. It passes only when the lower bound is above zero.

AND WHICH FORECAST STANDS FOR EACH QUESTION, CHECKED. The measurement keeps
each question's final pass if one settled, otherwise its latest written
forecast, read by pass alone, because the correction may not read a game's
start; the blind record's standing rule is a final pass written before the
start, otherwise the latest written before the start
(`recount.correction_standing`). This tool asks both, and measures nothing --
writes nothing -- where they differ, naming each question. (Question 27,
ruled 2026-09-28 and built 2026-09-29, changed the standing pass in both at
once: until then each kept the latest written, before the start or not.)

WHAT IT WRITES: nothing without --write. With it, ONE ROW in one transaction
through the door: `correction.activate_measured`, which measures again on the
connection it writes through and writes only a pass, or `correction.withdraw`,
only for a withdrawal the ruling names (`RULED_WITHDRAWALS`) of the very fit
the ruling is about (its sport, market, forecaster, version and instant), and
only before its measured activation (the ruling's order: withdrawn now, then
measured). IDEMPOTENT: a withdrawal already on the record with the ruled
reason, or an activation already in force for the correction, is said and
not written again. The schema's rules decide every row as it lands.

REFUSED ON THE LIVE RECORD without --live, and --live refused on anything
else; the record is known by the file's identity (`db.is_the_live_record_file`).
It applies no schema: a record not yet opened under the schema that carries
`correction_activations` is refused by name.
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

from gridiron import correction, db, recount  # noqa: E402

#: THE WITHDRAWALS THE OPERATOR RULED (question 32, 2026-09-29), each keyed by
#: the correction's number and written only on the record whose correction of
#: that number is exactly this one: fit 71, the only correction ever put in
#: force, by the weekly recalibration at 2026-09-28T13:00:01Z (task run 6173).
RULED_WITHDRAWALS: dict[int, dict] = {
    71: {"sport": "mlb", "market_type": "moneyline",
         "forecaster": "statistical", "version": 8,
         "fitted_utc": "2026-09-28T13:00:01Z",
         "reason": correction.FIT_71_WITHDRAWAL_REASON},
}

#: The reason a measured activation carries, in words.
MEASURED_REASON = (
    "measured under the gate of operator question 32 (ruled 2026-09-29): the "
    "bootstrap interval of its Brier improvement on its category's settled "
    "questions, each once, lies wholly above zero "
    "(tools/correction_holdout.py)")


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED, NOTHING WRITTEN: " + why)
        super().__init__(2)


def identity_faults(fit, ruled: dict) -> list[str]:
    """Why this database's correction of the ruled number is not the ruled
    one, in words; [] when it is exactly that correction."""
    if fit is None:
        return ["there is no such correction on this database"]
    return [f"its {field} is {fit[field]!r}, and the ruling's is {want!r}"
            for field, want in ruled.items()
            if field != "reason" and fit[field] != want]


def standing_faults(conn, measured: dict) -> list[str]:
    """Where the measurement's forecast for a question is not the one the
    blind record's standing rule keeps (`recount.correction_standing`), or
    the two disagree about which questions there are; [] when one answer."""
    theirs = recount.correction_standing(
        conn, sport=measured["sport"], market_type=measured["market_type"],
        predictor=measured["forecaster"], before_utc=measured["fitted_utc"])
    ours = measured.get("standing") or {}
    faults = []
    for key in sorted(set(ours) | set(theirs), key=repr):
        if ours.get(key) != theirs.get(key):
            faults.append(
                f"question {key}: the measurement keeps forecast "
                f"{ours.get(key)} and the standing rule keeps "
                f"{theirs.get(key)}")
    return faults


def _report(got: dict) -> None:
    print(f"correction {got['correction_id']}: {got['sport']} "
          f"{got['market_type']}, {got['forecaster']}, version "
          f"{got['version']}, fitted {got['fitted_utc']} on {got['n_train']} "
          f"settled forecasts")
    if "bets" in got:
        print(f"  its category's settled questions before the fit, each once "
              f"(distinct bets on the key): {got['bets']}; refit on the "
              f"earliest {got['fitted_on']}, scored on the latest "
              f"{got['holdout_n']}")
    if got.get("interval"):
        low, high = got["interval"]
        print(f"  Brier on the {got['holdout_n']} held out: raw "
              f"{got['brier_raw']:.6f}, corrected {got['brier_corrected']:.6f}; "
              f"improvement {got['improvement']:+.6f}")
        print(f"  paired bootstrap 95% interval of the improvement "
              f"[{low:+.6f}, {high:+.6f}] ({got['draws']} resamples, seed "
              f"{got['seed']})")
    print(("  PASSES: " if got["passed"] else "  DOES NOT PASS: ") + got["why"])


def _latest(conn, fit):
    return correction.latest_activation(
        conn, sport=fit["sport"], market_type=fit["market_type"],
        forecaster=fit["forecaster"])


def _withdrawn_as_ruled(conn, fit, ruled: dict):
    for row in correction.activations(conn, sport=fit["sport"],
                                      market_type=fit["market_type"],
                                      forecaster=fit["forecaster"]):
        if (row["correction_id"] == fit["id"]
                and row["kind"] == correction.WITHDRAWN
                and row["reason"] == ruled["reason"]):
            return row
    return None


def _withdraw(conn, fit, ruled: dict, write: bool) -> int:
    done = _withdrawn_as_ruled(conn, fit, ruled)
    if done is not None:
        print(f"already withdrawn, as ruled, at {done['activated_utc']}: "
              f"nothing to write")
        return 0
    latest = _latest(conn, fit)
    in_force = (latest is not None and latest["id"] == fit["id"]
                and latest["activation_kind"] != correction.WITHDRAWN)
    under_the_old_rule = latest is None and fit["active_from"] is not None
    if not (in_force or under_the_old_rule):
        raise Refused(
            f"correction {fit['id']} is not the one in force for its category "
            f"(neither put in force by its category's latest row nor written in "
            f"force under the rule before 29 September 2026), so there is "
            f"nothing to withdraw: this goes back to the operator")
    print(f"the withdrawal the ruling names: correction {fit['id']}, reason "
          f"{ruled['reason']!r}"
          + (f" (written in force under the rule before this one, at "
             f"{fit['active_from']})" if under_the_old_rule else ""))
    if not write:
        print("nothing written. --write would write this one withdrawal.")
        return 0
    try:
        row = correction.withdraw(conn, fit["id"], reason=ruled["reason"])
    except correction.ActivationRefused as exc:
        raise Refused(f"the record refused the withdrawal: {exc}") from None
    print(f"wrote the withdrawal of correction {fit['id']} at "
          f"{row['activated_utc']}")
    return 0


def _measure(conn, fit, write: bool) -> int:
    ruled = RULED_WITHDRAWALS.get(fit["id"])
    got = correction.measure(conn, fit["id"])
    faults = standing_faults(conn, got) if "standing" in got else []
    if faults:
        raise Refused(
            f"the measurement's forecast for {len(faults)} question(s) is not "
            f"the one the blind record's standing rule keeps, so it would "
            f"measure other forecasts than the record stands on:\n  "
            + "\n  ".join(faults[:20]))
    _report(got)
    if "standing" in got:
        print(f"  each of the {got['bets']} questions stands on the forecast "
              f"the blind record's standing rule keeps")
    latest = _latest(conn, fit)
    if (latest is not None and latest["id"] == fit["id"]
            and latest["activation_kind"] == correction.MEASURED):
        print(f"already in force by its measured activation of "
              f"{latest['activated_utc']}: nothing to write")
        return 0
    if not write:
        print("nothing written" + (
            ": --write would write its measured activation"
            if got["passed"] else ": it would stay out of force (a tie goes "
            "to the uncorrected probability)") + ".")
        return 0
    if ruled is not None and _withdrawn_as_ruled(conn, fit, ruled) is None:
        raise Refused(
            f"correction {fit['id']}'s ruled withdrawal is not on the record "
            f"yet. The ruling's order is the withdrawal first, then the gate "
            f"(--withdraw --write)")
    if not got["passed"]:
        print("NOT ACTIVATED, NOTHING WRITTEN: a tie goes to the uncorrected "
              "probability" + (", so it stays withdrawn" if ruled else ""))
        return 1
    try:
        wrote = correction.activate_measured(conn, fit["id"],
                                             reason=MEASURED_REASON)
    except correction.ActivationRefused as exc:
        raise Refused(f"the activation was refused: {exc}") from None
    print(f"wrote the measured activation of correction {fit['id']} at "
          f"{wrote['written']['activated_utc']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator question 32: measure a correction under the "
                    "gate, and write its dated activation only when it "
                    "passes, or the ruled withdrawal")
    parser.add_argument("--database", required=True,
                        help="the database whose correction is measured")
    parser.add_argument("--correction", type=int, required=True,
                        help="the correction's number, as stored")
    parser.add_argument("--withdraw", action="store_true",
                        help="the withdrawal the ruling names, instead of "
                             "the measurement")
    parser.add_argument("--write", action="store_true",
                        help="write the row; without it, only say what it "
                             "would be")
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
            f"record, found by its identity). Its rows are written only with "
            f"--live, after the release that carries the table")
    ruled = RULED_WITHDRAWALS.get(args.correction)
    if args.withdraw and ruled is None:
        raise Refused(f"no ruling withdraws correction {args.correction}; the "
                      f"ruled withdrawals are {sorted(RULED_WITHDRAWALS)}")

    why = ("operator question 32: measuring a correction under the gate, or "
           "reading what its withdrawal would write, before writing anything")
    # DRY MEANS READ-ONLY, whatever the file: the read-only door, which SQLite
    # itself will not write through. The write goes through `db.connect`,
    # which refuses the record under any verification, and applies no schema.
    conn = db.connect(path) if args.write else db.read_only(path, why)
    try:
        if not db.table_columns(conn, correction.ACTIVATIONS):
            raise Refused(
                f"{path} has no {correction.ACTIVATIONS} table: it has not "
                f"been opened under the schema that carries it (db.init does "
                f"that, on any scheduled pass or the server's start after the "
                f"release)")
        if args.write:
            # ONE TRANSACTION, the read and the row: nothing lands between.
            conn.execute("BEGIN IMMEDIATE")
        fit = conn.execute("SELECT * FROM calibration_corrections WHERE id = ?",
                           (args.correction,)).fetchone()
        if fit is None:
            raise Refused(f"there is no correction {args.correction} on {path}")
        if ruled is not None:
            faults = identity_faults(fit, ruled)
            if faults:
                raise Refused(
                    f"correction {args.correction} on {path} is not the one "
                    f"the ruling is about: " + "; ".join(faults))
        if args.withdraw:
            return _withdraw(conn, fit, ruled, args.write)
        return _measure(conn, fit, args.write)
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
