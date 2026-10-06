"""Void the recommendations priced across two contracts (operator ruling A.2
of 2026-10-05, on question 36 (ii); built 2026-10-05).

    # what it would write; reads only, through the read-only door
    python tools/void_two_contract_recommendations.py --database PATH

    # a scratch copy: write the voids
    python tools/void_two_contract_recommendations.py --database PATH --write

    # the live record, AFTER the release that carries the rule
    python tools/void_two_contract_recommendations.py --database var/gridiron.db --write --live

THE RULING, in the operator's words (docs/briefs/2026-10-05-rulings.md):
"Void the 54 recommendations by append-only rows (reason: 'priced across two
contracts, Q36'). The 269 claims stay in the blind record (model against
outcome at its own line) and are excluded by a dated rule from every price
comparison: at-the-line record, closing line, edge figures, combos. List
every released number that moves."

THE 54 (docs/REPAIR_STATE.md question 36): MLB run lines 6, 8, 11, 14, 16,
20, 25, 30, 32, 34, 38-42, 44, 48, 50, 51, 53-55, 57, 59, 60, 79, 84-87,
93-98, 100, 106-109; NFL 62, 63, 66, 68-70, 73, 75, 77, 78; NCAAF 88, 90,
91 -- each priced from a claim whose model number was read at -s off a
venue contract naming the visiting side, which sells +s: its side, edge and
size were worked out across two contracts.

WHAT IT SELECTS, by rule and nothing else: every recommendation, withdrawn
or not, whose PRICING CLAIM -- the latest claim on its forecast written by
its own stamp and before the start, the close's own rule
(`recommend.pricing_claim`) -- is priced across two contracts: its stored
line is not the line its contract sells (`at_the_line.
priced_across_two_contracts`, the one place). Read straight off the tables,
never through `recommend.counted_once`, whose rule it shares. Measured on a
verified copy of the record on 2026-10-05, the rule selects 56: the 54 and
recs 114 and 115 (NFL week 4, PIT at CLE and GB at TB), written by
`predict:nfl` (run 8464) at 18:05Z on 30 September, 44 minutes before Q36.1
was released -- the same case, found after question 36 was written.

WHAT IT WRITES, and nothing else: one append-only `recommendation_voids` row
for each recommendation of THE RULED SET -- `RULED`, the 54, and
`ON_THE_OPERATORS_WORD`, 114 and 115 from the operator's word of
2026-10-06 (question 31's precedent: a set the rule selects beyond the
ruling's words is listed and written only on the operator's word) -- dated when it is
written, with the ruling's reason, `recommend.TWO_CONTRACTS_VOID_REASON`.
Every other recommendation the rule selects is LISTED, as selected and
waiting for the operator's word, and not written.

A RECOMMENDATION ALREADY WITHDRAWN is left as it is and listed: 62, 63 and
66 were voided under ruling 1 of 2026-09-24 ("published from an unvalidated
fit before the hold"), and a recommendation is withdrawn once
(`recommendation_voids` is keyed by it, and refuses an edit). It counts in
no measurement either way.

IT REFUSES, writing nothing: a ruled recommendation the rule does not select
(a void the rule does not support is the operator's, not this script's);
any write outside the ruled set (`write_voids` asks again, row by row); a
database that is not a record (a backtest); the live record without
`--live`, and `--live` on any other file -- the record is known by the
file's identity (`db.is_the_live_record_file`). It applies no schema.

ONE TRANSACTION, IDEMPOTENT: a recommendation this ruling already voided is
counted and skipped, so a second run writes nothing and selects the same
set; the record never holds some of the voids and not the rest.

NOTHING COUNTED MOVES WHEN IT RUNS: the read rule of the same ruling
(`recommend.priced_on_one_contract`, in the measurement door) already leaves
every selected recommendation out of every measurement, withdrawn or not.
What moves is which line names each: the 51 it writes move from the closing
line's "Priced across two contracts" row to its "Withdrawn" row.
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
from gridiron.market import at_the_line, recommend  # noqa: E402

#: THE 54 THE RULING NAMES (docs/REPAIR_STATE.md question 36): "Void the 54
#: recommendations by append-only rows".
RULED = (
    # MLB run lines
    6, 8, 11, 14, 16, 20, 25, 30, 32, 34, 38, 39, 40, 41, 42, 44, 48, 50, 51,
    53, 54, 55, 57, 59, 60, 79, 84, 85, 86, 87, 93, 94, 95, 96, 97, 98, 100,
    106, 107, 108, 109,
    # NFL spreads
    62, 63, 66, 68, 69, 70, 73, 75, 77, 78,
    # NCAAF spreads
    88, 90, 91,
)

#: THE OPERATOR'S WORD, beyond the 54: empty until he ruled. Recs 114 and
#: 115 are selected by the same rule and were listed as waiting (the brief's
#: reading, docs/briefs/2026-10-05-rulings.md, "How this brief is read";
#: question 31's precedent). His word adds them here, and nothing else does.
#: RULED 2026-10-06 (docs/briefs/2026-10-06-rulings.md): "Recs 114 and 115:
#: void them, same reason as the 51 ('priced across two contracts, Q36'). Dry
#: run first, then the write."
ON_THE_OPERATORS_WORD: tuple[int, ...] = (114, 115)

#: The reason each void carries, exactly as the operator wrote it.
REASON = recommend.TWO_CONTRACTS_VOID_REASON


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED, NOTHING WRITTEN: " + why)
        super().__init__(2)


class OutsideTheRuledSet(RuntimeError):
    """A void was about to be written for a recommendation the ruling does
    not name -- refused by name, nothing written."""


def ruled_set() -> tuple[int, ...]:
    """The recommendations this tool may void: the 54 and the operator's word."""
    return tuple(sorted(set(RULED) | set(ON_THE_OPERATORS_WORD)))


def selected_by_the_rule(conn) -> list[dict]:
    """Every recommendation, withdrawn or not, priced from a claim across two
    contracts -- its pricing claim by the close's rule, read through the one
    place -- with its game, market, forecaster, the claim's line and the line
    its contract sells, and any withdrawal's reason. Read straight off the
    tables, round `recommend.not_withdrawn` on purpose: a second run must
    still see a recommendation this ruling voided."""
    recs = conn.execute(
        "SELECT r.id, r.sport, r.game_id, r.market, r.side, r.created_utc,"
        "       p.predictor,"
        "       (SELECT w.reason FROM recommendation_voids w"
        "         WHERE w.recommendation_id = r.id) AS void_reason,"
        "       (SELECT v.reason FROM prediction_voids v"
        "         WHERE v.prediction_id = r.prediction_id) AS forecast_void"
        "  FROM recommendations r"
        "  JOIN predictions p ON p.id = r.prediction_id ORDER BY r.id").fetchall()
    priced_from = recommend.pricing_claim_ids(conn, [r["id"] for r in recs])
    across = set(at_the_line.across_two_contracts_among(conn, priced_from.values()))
    out = []
    for r in recs:
        claim_id = priced_from.get(r["id"])
        if claim_id not in across:
            continue
        claim = conn.execute(
            "SELECT c.line, c.created_utc, q.line AS sold, q.yes_side, q.ticker"
            "  FROM at_the_line_claims c JOIN venue_quotes q ON q.id = c.quote_id"
            " WHERE c.id = ?", (claim_id,)).fetchone()
        out.append(dict(r, claim_id=claim_id, claim_line=claim["line"],
                        sold_line=claim["sold"], contract_side=claim["yes_side"],
                        ticker=claim["ticker"], claim_utc=claim["created_utc"]))
    return out


def check(found: list[dict]) -> dict:
    """What to write and what to list -- or `Refused`, naming the difference,
    when a ruled recommendation is not one the rule selects."""
    selected = {r["id"] for r in found}
    ruled = set(ruled_set())
    missing = sorted(ruled - selected)
    if missing:
        raise Refused(
            f"the ruling names recommendation(s) {missing}, which the rule does "
            f"not select: their pricing claim is not priced across two "
            f"contracts on this database. A void is permanent and needs the "
            f"rule behind it; which to void is the operator's "
            f"(docs/REPAIR_STATE.md question 36).")
    by_id = {r["id"]: r for r in found}
    withdrawn_otherwise = sorted(
        i for i in ruled if (by_id[i]["void_reason"] not in (None, REASON))
        or (by_id[i]["void_reason"] is None and by_id[i]["forecast_void"]))
    already = sorted(i for i in ruled if by_id[i]["void_reason"] == REASON)
    to_write = sorted(ruled - set(withdrawn_otherwise) - set(already))
    waiting = sorted(selected - ruled)
    return {"to_write": to_write, "already": already,
            "withdrawn_otherwise": withdrawn_otherwise, "waiting": waiting}


def write_voids(conn, ids: list[int]) -> dict:
    """One `recommendation_voids` row for each of `ids`, dated now, with the
    ruling's reason, in one transaction -- and only for a recommendation of
    the ruled set: any other id refuses the whole write by name
    (`OutsideTheRuledSet`), before a row is written."""
    ruled = set(ruled_set())
    outside = sorted(set(ids) - ruled)
    if outside:
        raise OutsideTheRuledSet(
            f"a void for recommendation(s) {outside}, which the ruling of "
            f"2026-10-05 does not name ({len(RULED)} named; the operator's word "
            f"adds {list(ON_THE_OPERATORS_WORD) or 'none'}). Nothing was "
            f"written.")
    now = db.utcnow()
    wrote = 0
    with db.transaction(conn):
        for rec_id in ids:
            conn.execute(
                "INSERT INTO recommendation_voids (recommendation_id, voided_utc,"
                " reason) VALUES (?, ?, ?)", (rec_id, now, REASON))
            wrote += 1
    return {"written": wrote, "voided_utc": now}


def _line(r: dict) -> str:
    state = ""
    if r["void_reason"] == REASON:
        state = "  [already voided by this ruling]"
    elif r["void_reason"]:
        state = f"  [withdrawn: {r['void_reason'][:60]}]"
    elif r["forecast_void"]:
        state = f"  [its forecast withdrawn: {r['forecast_void'][:60]}]"
    def signed(line) -> str:
        return "no line" if line is None else f"{float(line):+g}"

    return (f"  rec {r['id']}: {r['sport']} {r['market']} {r['side']} "
            f"({r['predictor']}) on {r['game_id']}, written {r['created_utc']};"
            f" priced from claim {r['claim_id']} at {signed(r['claim_line'])} "
            f"off {r['ticker']} ({r['contract_side']} contract, sells "
            f"{signed(r['sold_line'])}), written {r['claim_utc']}{state}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator ruling A.2 of 2026-10-05: void, by append-only "
                    "rows, the 54 recommendations priced across two contracts")
    parser.add_argument("--database", required=True,
                        help="the database whose recommendations are voided")
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

    why = ("operator ruling A.2 of 2026-10-05: listing the recommendations "
           "priced across two contracts, before voiding the 54")
    # DRY MEANS READ-ONLY, whatever the file: the read-only door, which SQLite
    # itself will not write through. The write goes through `db.connect`,
    # which refuses the record under any verification, and applies no schema.
    conn = db.connect(path) if args.write else db.read_only(path, why)
    try:
        kind = db.database_kind(conn)["kind"]
        if kind != "live":
            raise Refused(
                f"{path} is a {kind} database, not a record: the ruling is "
                f"about the recommendations the record holds.")
        found = selected_by_the_rule(conn)
        print(f"{len(found)} recommendation(s) were priced from a claim across "
              f"two contracts (their pricing claim's line is not the line its "
              f"contract sells):")
        for r in found:
            print(_line(r))
        plan = check(found)
        print(f"the ruled set ({len(RULED)} named by question 36"
              + (f", and {list(ON_THE_OPERATORS_WORD)} on the operator's word"
                 if ON_THE_OPERATORS_WORD else "")
              + f"), every one selected by the rule")
        if plan["withdrawn_otherwise"]:
            print(f"already withdrawn for another reason, and left as they "
                  f"are: {plan['withdrawn_otherwise']}")
        if plan["already"]:
            print(f"already voided by this ruling: {plan['already']}")
        if plan["waiting"]:
            print(f"selected by the rule and waiting for the operator's word, "
                  f"NOT written: {plan['waiting']}")
        print(f"reason: {REASON}")
        if not args.write:
            print(f"nothing written. --write would void {len(plan['to_write'])}: "
                  f"{plan['to_write']}")
            return 0
        wrote = write_voids(conn, plan["to_write"])
        stamp = f" at {wrote['voided_utc']}" if wrote["written"] else ""
        print(f"wrote {wrote['written']} void(s){stamp}; "
              f"{len(plan['already'])} already voided by this ruling")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
