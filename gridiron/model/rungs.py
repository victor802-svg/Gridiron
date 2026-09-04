"""What the model would have said at every rung it was OFFERED.

Ruling, 2026-08-31, on six MLB prop questions that fell below the 70% floor in
one night: "The ladder question gets MEASURED before it gets retuned. Add to
the props slate log the model's claim at every OFFERED rung, written or not.
After two weeks: if below-floor claims cluster at 60-69 near the mean rung,
that is the floor working as designed, not a mis-set ladder. Four days is not
evidence."

A count of below-floor questions cannot tell those two apart. The distribution
of the claims that failed can: claims bunched just under the floor mean the
questions were nearly askable and the floor is doing exactly its job, while
claims scattered at 52-58 across every rung would mean the ladder is set where
the model has nothing to say.

WHAT THIS IS NOT
================
It is not a prediction log, and nothing here may ever be scored. A row is what
the model would have claimed at a rung it was not asked about; it has no
outcome, gets no resolution, and enters no curve, Brier score or N. Scoring
these would let the model be judged on the questions it liked, which is the one
thing the entire record exists to prevent -- and it would do it while looking
like more data.

It is also not a change to anything. The floor stands, the ladder stands, and
the rung actually asked is chosen exactly as before. This only writes down what
was already computed and thrown away.

BLIND (LAW 1)
=============
The only inputs are the declared ladder -- a dated constant -- and the model's
own probability from stored stats. No market line is consulted, and this module
imports nothing that could reach one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace

from .. import config
from ..db import utcnow


def declared_rungs(sport: str, market: str) -> tuple[float, ...]:
    """Every rung the ladder OFFERS for this market, or () where none is declared.

    MLB is the only sport with a declared ladder today, which is why the ruling
    is about MLB. Returning () elsewhere means the log stays empty for sports
    whose rungs come from somewhere else, rather than inventing a ladder to
    have something to record.
    """
    if sport != "mlb":
        return ()
    return tuple(config.MLB_PROP_LADDER.get(market) or ())


def claims_across_the_ladder(conn, adapter, fits, q, *, chosen_stat, baseline):
    """The model's claim at each offered rung. The chosen rung is not recomputed.

    Returns [] when the market has no declared ladder, which keeps this silent
    rather than approximate for anything but MLB.
    """
    rungs = declared_rungs(q.sport, q.market)
    if not rungs or q.market_key not in fits:
        return []

    out = []
    for rung in rungs:
        if q.line_asked is not None and abs(rung - q.line_asked) < 1e-9:
            stat = chosen_stat
        else:
            try:
                fv, _ctx = adapter.build_features(conn, replace(q, line_asked=rung), None)
                stat = baseline.predict(fits[q.market_key], fv, rung=q.line_asked)
            except (KeyError, ValueError):
                # A rung whose features cannot be built is ABSENT from the log,
                # not a zero in it: the explicit-absent rule. A gap in the
                # distribution is readable; a fabricated point is not.
                continue
        side, claimed = baseline.stated_side(stat["prob_yes"], q.yes_label, q.no_label)
        out.append({
            "rung": float(rung),
            "prob_yes": float(stat["prob_yes"]),
            "claimed": float(claimed),
            "side": side,
            "asked": bool(q.line_asked is not None
                          and abs(rung - q.line_asked) < 1e-9),
        })
    return out


def record(conn: sqlite3.Connection, q, claims, *, season: int, week: int | None,
           rolling_mean: float | None, written: bool) -> int:
    """Write the claims for one subject. Append-only; a rerun adds nothing.

    The unique index is on the timestamp too, so re-running a slate inside the
    same second is the only case it collapses -- which is the case that would
    be a duplicate rather than a second measurement.
    """
    if not claims:
        return 0
    now = utcnow()
    rows = 0
    for c in claims:
        try:
            conn.execute(
                "INSERT INTO prop_rung_claims (sport, season, week, game_id,"
                " subject, market, rung, chosen_rung, rolling_mean, prob_yes,"
                " claimed, side, asked, written, floor_applied,"
                " factor_set_version, created_utc)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (q.sport, season, week, q.game_id, q.subject, q.market,
                 c["rung"], q.line_asked, rolling_mean, c["prob_yes"],
                 c["claimed"], c["side"], int(c["asked"]),
                 int(bool(written) and c["asked"]), config.PROPS_MIN_CLAIM,
                 config.FACTOR_SET_VERSION, now),
            )
            rows += 1
        except sqlite3.IntegrityError:
            # The same rung already recorded for this subject this second.
            continue

    # COMMITTED HERE, and it has to be. The only commit in the prediction loop
    # is inside `write_prediction`, so a run that writes NOTHING -- every
    # question already answered, or every prop below the floor -- commits
    # nothing at all. The first live run of this log lost all fifteen
    # below-floor measurements exactly that way: the rows were inserted, the
    # run reported success, and the connection closed on an open transaction.
    #
    # Committing separately is also correct in principle. This log is not part
    # of the prediction it sits beside: a measurement is kept whether or not a
    # forecast was written, which is the entire point of recording the rungs
    # that were never asked.
    if rows:
        conn.commit()
    return rows


#: The ruling's window. Two weeks of slates, then the distribution decides.
DECIDE_AFTER_DAYS = 14

#: The band the ruling names as "the floor working as designed": claims that
#: fell just short rather than claims the model never had.
NEARLY_BAND = (0.60, 0.70)


def distribution(conn: sqlite3.Connection, *, sport: str) -> dict:
    """The shape of what the model claimed, for the ladder decision.

    Reports and does not conclude. The ruling sets the test -- below-floor
    claims clustering at 60-69 near the mean rung means the floor is working --
    and sets the window at two weeks, so this says how much of that window has
    passed and refuses to call it either way before then.
    """
    config.require_sport(sport, "rungs.distribution")

    rows = list(conn.execute(
        "SELECT rung, chosen_rung, claimed, asked, written, floor_applied,"
        " created_utc, market FROM prop_rung_claims WHERE sport = ?"
        " ORDER BY created_utc",
        (sport,),
    ))
    if not rows:
        return {"sport": sport, "n": 0, "days": 0, "decide_after_days": DECIDE_AFTER_DAYS,
                "verdict": "nothing logged yet"}

    days = sorted({r["created_utc"][:10] for r in rows})
    asked = [r for r in rows if r["asked"]]
    floor = asked[0]["floor_applied"] if asked else None
    below = [r for r in asked if floor is not None and r["claimed"] < floor]
    nearly = [r for r in below if NEARLY_BAND[0] <= r["claimed"] < NEARLY_BAND[1]]

    bands: dict[str, int] = {}
    for r in asked:
        low = int(r["claimed"] * 10) * 10
        bands[f"{low}-{low + 9}%"] = bands.get(f"{low}-{low + 9}%", 0) + 1

    # Where the ladder COULD have been asked and cleared the floor, per
    # subject-day: evidence that a different rung was available, which is the
    # other half of "mis-set".
    better = conn.execute(
        "SELECT COUNT(*) AS n FROM ("
        "  SELECT game_id, subject, market, created_utc"
        "  FROM prop_rung_claims WHERE sport = ?"
        "  GROUP BY game_id, subject, market, created_utc"
        "  HAVING MAX(CASE WHEN asked = 1 AND claimed < floor_applied"
        "                  THEN 1 ELSE 0 END) = 1"
        "     AND MAX(CASE WHEN asked = 0 AND claimed >= floor_applied"
        "                  THEN 1 ELSE 0 END) = 1)",
        (sport,),
    ).fetchone()["n"]

    return {
        "sport": sport,
        "n": len(rows),
        "questions": len(asked),
        "days": len(days),
        "first_day": days[0],
        "last_day": days[-1],
        "decide_after_days": DECIDE_AFTER_DAYS,
        "floor": floor,
        "below_floor": len(below),
        "below_floor_nearly": len(nearly),
        "bands": bands,
        "subjects_with_a_rung_that_would_have_cleared": better,
        "verdict": (
            f"{len(days)} day(s) of {DECIDE_AFTER_DAYS}: not enough to decide, "
            "and a shape read early is the thing the ruling forbids"
            if len(days) < DECIDE_AFTER_DAYS else
            "the window is complete; read the bands and decide"
        ),
    }
