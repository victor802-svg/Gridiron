"""Void what fits 91-94 published before the hold (operator ruling 1, 2026-09-24).

    python tools/void_fs5.py            # what it would write; reads only
    python tools/void_fs5.py --write    # write it

THE RULING, in the operator's words: "Recommendations 62-66 [amended: 62, 63,
64 and 66 only; 65 stands] and every NFL/NCAAF spread and moneyline forecast
written from fits 91-94 since 05:16Z are VOIDED: one append-only void row
each, dated, reason 'published from an unvalidated fit before the hold; fit
subsequently failed holdout'."

WHAT HAPPENED. Fits 91-94 (factor set fs5) were trained on the live record at
05:16-05:17Z on 24 September. The logon catch-up at 05:32-05:36Z published
from them before the hold existed: 31 statistical forecasts -- NFL spread 13,
NFL moneyline 16, NCAAF spread 1, NCAAF moneyline 1 -- and four
recommendations on them. The fits then failed their holdout.

WHAT IT SELECTS, by the ruling's criteria and nothing else: created at or
after 2026-09-24T05:16, NFL or NCAAF, spread or moneyline, the statistical
forecaster, factor set fs5. Then it CHECKS what it selected against the ids
measured on the day -- the 31 below, and recommendations {62, 63, 64, 66} --
and refuses, loudly and writing nothing, if either set differs by one row. A
void is permanent; a selection that has drifted since the ruling was measured
is a question for the operator, not for this script.

WHAT STANDS, AND WHY. Recommendation 65 is an NFL total from the reasoning
forecaster on fs2: not written from a fit, not voided (ruling 1 of the three
decisions, 2026-09-24). The 31 reasoning-forecaster rows written in the same
runs carry the run's fs5 label but no fit output in their prompts (ruling 2,
read prompt by prompt): they stand, and this reports their count beside the
voids. They exist only because fits 91-94 existed -- the catch-up that wrote
them was the one those fits set off -- which is recorded in FOLLOWUPS.

ONE REASON FOR ALL FOUR MARKETS. The morning ruling allowed "not yet
validated" for NFL moneyline, whose holdout point estimate was better than
the incumbent's. The three-decisions ruling then made ties go to the
incumbent, and under it NFL moneyline failed too, so the ruling's own reason
is true of every row here and is the one written.

IDEMPOTENT. A forecast already in `prediction_voids`, or a recommendation
already in `recommendation_voids`, is counted and skipped -- the tables would
refuse a second row anyway, and the first reason stands. Both kinds are
written in one transaction, so the record never holds half a withdrawal.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import db  # noqa: E402

#: The ruling's reason, exactly as the operator wrote it.
REASON = ("published from an unvalidated fit before the hold; fit subsequently "
          "failed holdout")

#: The ruling's criteria.
SINCE = "2026-09-24T05:16"
SPORTS = ("nfl", "cfb")
MARKETS = ("spread", "moneyline")
PREDICTOR = "statistical"
FACTOR_SET = "fs5"

#: What those criteria selected when the ruling was measured, 2026-09-24.
TAINTED_PREDICTIONS = (
    2225, 2228, 2230, 2233, 2235, 2238, 2240, 2243, 2245, 2248, 2251, 2254,
    2256, 2259, 2261, 2264, 2266, 2269, 2271, 2274, 2276, 2279, 2281, 2284,
    2287, 2289, 2292, 2294, 2297, 2299, 2301,
)
TAINTED_RECOMMENDATIONS = (62, 63, 64, 66)


class Refused(RuntimeError):
    """The record does not hold what the ruling was measured against."""


def _in(ids) -> str:
    return ",".join("?" for _ in ids)


def select_tainted(conn: sqlite3.Connection) -> dict:
    """The forecasts and recommendations the ruling voids, checked.

    Reads every recommendation on the tainted forecasts, withdrawn or not --
    which is why this function is named in audit.RECOMMENDATION_DOOR_EXEMPT:
    a second run must still see all four to prove the set is the ruling's.
    """
    rows = conn.execute(
        "SELECT p.id, p.sport, p.market_type, p.resolved_utc FROM predictions p"
        " WHERE p.created_utc >= ?"
        f"   AND p.sport IN ({_in(SPORTS)})"
        f"   AND p.market_type IN ({_in(MARKETS)})"
        "   AND p.predictor = ? AND p.factor_set_version = ?"
        " ORDER BY p.id",
        (SINCE, *SPORTS, *MARKETS, PREDICTOR, FACTOR_SET)).fetchall()
    ids = tuple(r["id"] for r in rows)
    if ids != TAINTED_PREDICTIONS:
        extra = sorted(set(ids) - set(TAINTED_PREDICTIONS))
        missing = sorted(set(TAINTED_PREDICTIONS) - set(ids))
        raise Refused(
            f"REFUSED, NOTHING WRITTEN: the ruling's criteria select {len(ids)} "
            f"forecasts, not the 31 measured on 2026-09-24. Selected and not "
            f"measured: {extra or 'none'}. Measured and not selected: "
            f"{missing or 'none'}. A void is permanent; this goes back to the "
            f"operator.")
    recs = tuple(r["id"] for r in conn.execute(
        "SELECT r.id FROM recommendations r"
        f" WHERE r.prediction_id IN ({_in(ids)}) ORDER BY r.id", ids))
    if recs != TAINTED_RECOMMENDATIONS:
        raise Refused(
            f"REFUSED, NOTHING WRITTEN: the tainted forecasts carry "
            f"recommendations {list(recs)}, not {list(TAINTED_RECOMMENDATIONS)} "
            f"as measured on 2026-09-24. A void is permanent; this goes back "
            f"to the operator.")

    voided = {r[0] for r in conn.execute(
        f"SELECT prediction_id FROM prediction_voids WHERE prediction_id IN ({_in(ids)})",
        ids)}
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        "   AND name = 'recommendation_voids'").fetchone() is not None
    withdrawn = {r[0] for r in conn.execute(
        f"SELECT recommendation_id FROM recommendation_voids"
        f" WHERE recommendation_id IN ({_in(recs)})", recs)} if has_table else set()
    by_market: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r["sport"], r["market_type"])
        by_market[key] = by_market.get(key, 0) + 1
    # THE ROWS BESIDE THEM THAT STAND: the reasoning forecaster's, same runs.
    standing = conn.execute(
        "SELECT COUNT(*) FROM predictions p WHERE p.created_utc >= ?"
        f"   AND p.sport IN ({_in(SPORTS)}) AND p.market_type IN ({_in(MARKETS)})"
        "   AND p.predictor = 'llm'", (SINCE, *SPORTS, *MARKETS)).fetchone()[0]
    return {
        "predictions": ids,
        "recommendations": recs,
        "already_voided": sorted(voided),
        "already_withdrawn": sorted(withdrawn),
        "settled": [r["id"] for r in rows if r["resolved_utc"] is not None],
        "by_market": by_market,
        "reasoning_rows_standing": standing,
    }


def write_voids(conn: sqlite3.Connection, chosen: dict) -> dict:
    """One void row each, dated now, in one transaction. Skips what is there."""
    now = db.utcnow()
    wrote = {"predictions": 0, "recommendations": 0}
    with db.transaction(conn):
        for pid in chosen["predictions"]:
            if pid in chosen["already_voided"]:
                continue
            conn.execute(
                "INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                " VALUES (?, ?, ?)", (pid, now, REASON))
            wrote["predictions"] += 1
        for rid in chosen["recommendations"]:
            if rid in chosen["already_withdrawn"]:
                continue
            conn.execute(
                "INSERT INTO recommendation_voids (recommendation_id, voided_utc,"
                " reason) VALUES (?, ?, ?)", (rid, now, REASON))
            wrote["recommendations"] += 1
    return wrote


_WORDS = {("nfl", "spread"): "NFL spread", ("nfl", "moneyline"): "NFL moneyline",
          ("cfb", "spread"): "NCAAF spread", ("cfb", "moneyline"): "NCAAF moneyline"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="write the voids; without it, only say what they would be")
    parser.add_argument("--database", default=None)
    args = parser.parse_args(argv)

    # DRY MEANS READ-ONLY, as in restate_closes: `open_db` applies the schema,
    # which is a write, so the dry run opens a query-only handle instead.
    if args.write:
        conn = db.open_db(args.database)
    elif args.database is None:
        conn = db.read_the_live_record(
            "listing the forecasts and recommendations ruling 1 of 2026-09-24 "
            "voids, before writing the voids")
    else:
        conn = sqlite3.connect(Path(args.database).resolve().as_uri() + "?mode=ro",
                               uri=True)
        conn.row_factory = sqlite3.Row

    try:
        chosen = select_tainted(conn)
    except Refused as exc:
        print(exc)
        conn.close()
        return 2

    parts = ", ".join(f"{_WORDS.get(k, ' '.join(k))} {n}"
                      for k, n in sorted(chosen["by_market"].items()))
    print(f"{len(chosen['predictions'])} forecasts from fits 91-94, as measured: {parts}")
    print(f"{len(chosen['recommendations'])} recommendations on them: "
          f"{', '.join(str(r) for r in chosen['recommendations'])}")
    print(f"reason: {REASON}")
    print(f"{chosen['reasoning_rows_standing']} reasoning-forecaster rows from the "
          f"same runs stand (no fit output in their prompts)")
    if chosen["settled"]:
        print(f"NOTE: {len(chosen['settled'])} of them had already settled before "
              f"the void ({', '.join(str(i) for i in chosen['settled'])}). The "
              f"standing clause leaves a voided row out of every graded count "
              f"whether or not it settled.")
    to_void = len(chosen["predictions"]) - len(chosen["already_voided"])
    to_withdraw = len(chosen["recommendations"]) - len(chosen["already_withdrawn"])
    print(f"already voided: {len(chosen['already_voided'])} forecasts, "
          f"{len(chosen['already_withdrawn'])} recommendations")
    if not args.write:
        print(f"nothing written. --write would void {to_void} forecasts and "
              f"withdraw {to_withdraw} recommendations.")
        conn.close()
        return 0
    wrote = write_voids(conn, chosen)
    print(f"wrote {wrote['predictions']} forecast voids and "
          f"{wrote['recommendations']} recommendation withdrawals")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
