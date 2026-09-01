"""Does the market move toward the model, or away from it?

THE QUESTION D1 COULD NOT TEST. When the model disagrees with the published
line, two stories fit the same data and they have opposite meanings:

  * the model sees something early and the market later agrees — the line
    drifts TOWARD the model's number, and the model's disagreements are
    information arriving before the market prices it;
  * the market's information is simply better — the line drifts AWAY, and the
    disagreement was the model being wrong in a way the market was not.

A single snapshot taken when the prediction is written cannot tell them apart,
because it has nothing to compare against. Two snapshots can: the line when the
forecast was made, and the line near kickoff.

WHAT THIS MODULE MUST NOT DO
============================
It must not conclude. The gate is fifty drift pairs in a category, and below it
this reports the count and nothing else — no direction, no fraction, no
adjective. That is not modesty, it is the same rule as everywhere else in the
record: a number without a sample behind it is a claim, and the interesting
direction is the one a reader will remember whether or not it was earned.

There are deliberately no conclusions written into these comments either. The
number decides, later, with an N beside it.

BOTH LOOKS HAPPEN AFTER THE PREDICTION EXISTS
=============================================
LAW 1 is untouched and its structure is unchanged: `market_snapshots` rows
still require a prediction that predates them, enforced by trigger, and the
second look obeys that exactly as the first does. The blind window is about
what the model may see BEFORE it commits; this is about what the market did
afterwards, which the model never sees at all.
"""

from __future__ import annotations

import sqlite3

from . import config

#: Drift pairs needed in a category before any direction is reported.
MIN_PAIRS = 50

#: How far apart the model and the market must be for a game to count as a
#: DISAGREEMENT. Below this the two are saying the same thing and the movement
#: between them is noise about nothing.
MIN_DISAGREEMENT = 0.05


def pairs(conn: sqlite3.Connection, *, sport: str, market_type: str,
          predictor: str = "statistical") -> list[dict]:
    """Every prediction with both looks at the line, and what moved.

    `toward` is the signed movement of the market's implied probability in the
    direction the model was pointing: positive means the line moved toward the
    model's number, negative away from it. The sign is derived from the two
    stored numbers rather than assumed from which side the model took.
    """
    config.require_sport(sport, "drift.pairs")
    rows = conn.execute(
        "SELECT p.id, p.model_prob, p.calibrated_prob,"
        " o.implied_prob AS opened, n.implied_prob AS near,"
        " o.fetched_utc AS opened_utc, n.fetched_utc AS near_utc"
        " FROM predictions p"
        " JOIN market_snapshots o"
        "   ON o.prediction_id = p.id AND o.kind = 'open_at_predict'"
        " JOIN market_snapshots n"
        "   ON n.prediction_id = p.id AND n.kind = 'near_start'"
        " WHERE p.sport = ? AND p.market_type = ? AND p.predictor = ?"
        "   AND o.implied_prob IS NOT NULL AND n.implied_prob IS NOT NULL"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)",
        (sport, market_type, predictor),
    ).fetchall()

    out = []
    for r in rows:
        claim = r["calibrated_prob"] if r["calibrated_prob"] is not None else r["model_prob"]
        disagreement = claim - r["opened"]
        if abs(disagreement) < MIN_DISAGREEMENT:
            continue
        movement = r["near"] - r["opened"]
        # Toward the model is movement sharing the sign of the disagreement.
        toward = movement if disagreement > 0 else -movement
        out.append({
            "prediction_id": r["id"],
            "claim": claim,
            "opened": r["opened"],
            "near": r["near"],
            "disagreement": round(disagreement, 6),
            "movement": round(movement, 6),
            "toward": round(toward, 6),
        })
    return out


def report(conn: sqlite3.Connection, *, sport: str, market_type: str,
           predictor: str = "statistical") -> dict:
    """The drift figure for one category, or the count and nothing else.

    Below `MIN_PAIRS` this returns no direction and no fraction. A reader who
    is told "the market moved toward the model 61% of the time" over nine games
    will remember the 61% and not the nine.
    """
    found = pairs(conn, sport=sport, market_type=market_type,
                  predictor=predictor)
    n = len(found)
    base = {
        "sport": sport,
        "market_type": market_type,
        "predictor": predictor,
        "n": n,
        "min_pairs": MIN_PAIRS,
        "min_disagreement": MIN_DISAGREEMENT,
    }
    if n < MIN_PAIRS:
        base["line"] = (
            f"{n} of {MIN_PAIRS} disagreements have a second look at the line. "
            "Nothing is reported about direction until there are enough."
        )
        return base

    moved_toward = sum(1 for p in found if p["toward"] > 0)
    base.update({
        "toward_fraction": round(moved_toward / n, 4),
        "moved_toward": moved_toward,
        "mean_movement": round(sum(p["toward"] for p in found) / n, 6),
        "line": (
            f"When the model disagreed by {MIN_DISAGREEMENT:.0%} or more, the "
            f"market moved toward it {moved_toward / n:.0%} of the time over "
            f"{n} games."
        ),
    })
    return base
