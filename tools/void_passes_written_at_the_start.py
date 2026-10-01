"""Void the passes written at or after their game's start (operator question
35, ruled 2026-09-30; built 2026-10-01).

    # what it would write; reads only, through the read-only door
    python tools/void_passes_written_at_the_start.py --database PATH

    # a scratch copy: write the voids
    python tools/void_passes_written_at_the_start.py --database PATH --write

    # the live record, AFTER the release that carries the rule
    python tools/void_passes_written_at_the_start.py --database var/gridiron.db --write --live

THE RULING, in the operator's words (docs/briefs/2026-09-30-rulings.md):
"Q35: a pass written at or after the start is not blind. Store and compare
starts as instants, never as text. The 18 are voided by append-only rows
under the existing void rule, and Q27's standing rule then falls back to their
early passes."

THE 18 (docs/REPAIR_STATE.md question 35; the re-read of 2026-09-29, G3):
forecasts 1014-1031, the statistical model's final passes on six bouts of UFC
Fight Night: Hooker vs. Parnasse (5 September), each in moneyline, rounds and
distance -- written by `final:ufc` (task run 131) at 19:00:02Z-19:00:03Z on a
main card whose start was stored to the minute, "2026-09-05T19:00Z". Compared
as text a colon sorts below a Z, so the standing rule read them as written
before the start and they stood over their early passes (520-537).

WHAT IT SELECTS, by rule and nothing else: every forecast written AT OR AFTER
its game's listed start, both read as instants -- `julianday()` on both sides
in SQL, and `db.instant` again in Python, the two readings required to agree
-- that no void withdraws, together with any this ruling's own reason already
withdraws (so a second run selects the same set and writes nothing). A
forecast already withdrawn for another reason is listed and left as it is:
measured on a verified copy of the record on 2026-10-01, the rule finds 24 --
these 18, and six MLB early passes (105-110) written at 19:17:55Z on 29
August after their first pitches, withdrawn at 19:19:07Z that day for that
very reason -- and none written exactly at its start's second. No
recommendation, claim at the venue's line or taken pick stands on any of the
18 (12 media snapshots and 54 ranker rows do, and stay as written).

THEN IT CHECKS the selection against the ruling: it writes ONLY when the
rule's selection is exactly `RULED`, and no recommendation stands on any of
them; anything else is refused, loudly, naming the difference and writing
nothing. A void is permanent, and a selection that has drifted from the one
the operator ruled on is the operator's, not this script's (the precedent of
`tools/void_fs5.py`, ruling 1 of 2026-09-24).

THE EXISTING VOID RULE: one append-only `prediction_voids` row each, dated
when it is written, with the reason below in words. The table refuses an edit
and a delete, and a voided forecast is never graded (`calibration.
standing_row_clause`, which then stands each question on its early pass --
written the day before, well before the start).

REFUSED ON THE LIVE RECORD without `--live`, and `--live` refused on anything
else; the record is known by the file's identity (`db.is_the_live_record_file`).
A backtest database is refused: every one of its forecasts is written after its
game, on purpose. It applies no schema.

IDEMPOTENT. A forecast this ruling has already voided is counted and skipped;
the table refuses a second row anyway, and the first stands. Every void is
written in one transaction, so the record never holds some of them.
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

#: The forecasts the ruling names: "The 18".
RULED = tuple(range(1014, 1032))

#: The reason each void carries, in words.
REASON = ("written at or after its game's start, read as an instant: the bout's "
          "start was stored to the minute and compared as text, so this pass "
          "stood as one written before it. A pass written at or after the "
          "start is not blind (operator ruling on question 35, 2026-09-30)")


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED, NOTHING WRITTEN: " + why)
        super().__init__(2)


def written_at_or_after_the_start(conn) -> list[dict]:
    """Every forecast written at or after its game's listed start, both read
    as instants, with its void's reason if one withdraws it. Read twice --
    by `julianday()` in SQL and by `db.instant` in Python -- and refused by
    name where the two readings disagree, or where a start or a stamp
    cannot be read at all (never guessed)."""
    rows = conn.execute(
        "SELECT p.id, p.sport, p.game_id, p.market_type, p.subject,"
        "       p.predictor, p.pass_kind, p.created_utc, g.kickoff_utc,"
        "       v.reason AS void_reason, v.voided_utc,"
        "       julianday(p.created_utc) >= julianday(g.kickoff_utc) AS after"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        "  LEFT JOIN prediction_voids v ON v.prediction_id = p.id"
        " WHERE g.kickoff_utc IS NOT NULL ORDER BY p.id").fetchall()
    out = []
    unreadable = []
    disagree = []
    for r in rows:
        try:
            after = db.instant(r["created_utc"]) >= db.instant(r["kickoff_utc"])
        except (ValueError, TypeError):
            unreadable.append(r["id"])
            continue
        if bool(r["after"]) != after:
            disagree.append(r["id"])
        if after:
            out.append(dict(r))
    if unreadable:
        raise Refused(
            f"forecast(s) {unreadable[:20]} sit on a start, or carry a stamp, "
            f"that cannot be read as an instant, so whether each was written "
            f"before its start cannot be told; nothing is guessed. This goes "
            f"back to the operator.")
    if disagree:
        raise Refused(
            f"forecast(s) {disagree[:20]}: julianday() and db.instant read "
            f"their stamps as different instants. This goes back to the "
            f"operator.")
    return out


def check(found: list[dict], recommended: dict[int, list[int]]) -> list[int]:
    """The ids to void -- when the rule's selection is exactly the ruling's
    -- or `Refused` naming how it differs."""
    selected = sorted(r["id"] for r in found
                      if r["void_reason"] is None or r["void_reason"] == REASON)
    if selected != sorted(RULED):
        extra = sorted(set(selected) - set(RULED))
        missing = sorted(set(RULED) - set(selected))
        raise Refused(
            f"the rule selects {len(selected)} forecast(s) written at or after "
            f"their start and not withdrawn, and the ruling names "
            f"{len(RULED)} (1014-1031). Selected and not ruled: "
            f"{extra or 'none'}. Ruled and not selected: {missing or 'none'}. "
            f"A void is permanent; which to void is the operator's "
            f"(docs/REPAIR_STATE.md).")
    standing = {pid: recs for pid, recs in recommended.items() if recs}
    if standing:
        raise Refused(
            f"recommendation(s) stand on {sorted(standing)}: {standing}. The "
            f"ruling voids forecasts and names no recommendation; this goes "
            f"back to the operator.")
    return selected


def _recommended(conn, ids: list[int]) -> dict[int, list[int]]:
    """Every recommendation written on each forecast, withdrawn or not --
    which is why this reads the table round `recommend.not_withdrawn`: a
    second run must still see one to prove the set is the ruling's."""
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    out: dict[int, list[int]] = {i: [] for i in ids}
    for r in conn.execute(
            f"SELECT id, prediction_id FROM recommendations"
            f" WHERE prediction_id IN ({marks}) ORDER BY id", ids):
        out[r["prediction_id"]].append(r["id"])
    return out


def write_voids(conn, ids: list[int], found: list[dict]) -> dict:
    """One void row each, dated now, in one transaction. Skips what this
    ruling already voided."""
    done = {r["id"] for r in found if r["void_reason"] == REASON}
    now = db.utcnow()
    wrote = 0
    with db.transaction(conn):
        for pid in ids:
            if pid in done:
                continue
            conn.execute(
                "INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                " VALUES (?, ?, ?)", (pid, now, REASON))
            wrote += 1
    return {"written": wrote, "already": len(done), "voided_utc": now}


def _line(r: dict) -> str:
    return (f"  forecast {r['id']}: {r['sport']} {r['market_type']} {r['subject']}"
            f" ({r['predictor']}, {r['pass_kind']} pass) on {r['game_id']},"
            f" written {r['created_utc']}, start stored {r['kickoff_utc']!r}"
            + (f"  [withdrawn {r['voided_utc']}: {r['void_reason'][:70]}...]"
               if r["void_reason"] else ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator question 35: void, by append-only rows, the "
                    "passes written at or after their game's start")
    parser.add_argument("--database", required=True,
                        help="the database whose forecasts are voided")
    parser.add_argument("--write", action="store_true",
                        help="write the voids; without it, only say what they "
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
            f"record, found by its identity). Its voids are written only with "
            f"--live, after the release that carries the rule")

    why = ("operator question 35: listing the passes written at or after their "
           "game's start, before voiding them")
    # DRY MEANS READ-ONLY, whatever the file: the read-only door, which SQLite
    # itself will not write through. The write goes through `db.connect`,
    # which refuses the record under any verification, and applies no schema.
    conn = db.connect(path) if args.write else db.read_only(path, why)
    try:
        kind = db.database_kind(conn)["kind"]
        if kind != "live":
            raise Refused(
                f"{path} is a {kind} database: every forecast in it is written "
                f"after its game, on purpose. The ruling is about the record.")
        found = written_at_or_after_the_start(conn)
        print(f"{len(found)} forecast(s) were written at or after their game's "
              f"start, read as instants:")
        for r in found:
            print(_line(r))
        other = [r["id"] for r in found
                 if r["void_reason"] not in (None, REASON)]
        if other:
            print(f"already withdrawn for another reason, and left as they "
                  f"are: {other}")
        candidates = [r["id"] for r in found if r["void_reason"] in (None, REASON)]
        ids = check(found, _recommended(conn, candidates))
        print(f"the ruling's set (question 35, \"the 18\"), selected by the "
              f"rule: {ids[0]}-{ids[-1]} ({len(ids)})")
        print(f"reason: {REASON}")
        if not args.write:
            todo = [r for r in found if r["id"] in ids and r["void_reason"] is None]
            print(f"nothing written. --write would void {len(todo)}.")
            return 0
        wrote = write_voids(conn, ids, found)
        print(f"wrote {wrote['written']} void(s) at {wrote['voided_utc']}; "
              f"{wrote['already']} already voided by this ruling")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
