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

from . import config, language

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
        # HOW CLOSE THIS MARKET IS to having a direction worth reporting
        # (GRIDIRON_13 P1). The same component the tier rows and the
        # correction gates use, so "close" means one thing on this page.
        "progress": language.progress(
            n, MIN_PAIRS, noun="pairs",
            cleared_note="enough pairs to report a direction"),
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


# ---------------------------------------------------------------------------
# THE VENUE'S OWN PAIR: OPEN TO CLOSE (GRIDIRON_OPENING_READ, 2026-09-09)
# ---------------------------------------------------------------------------
#
# The near-start half of this pair is the at-the-line claim, which already
# carries the venue's price read as a probability for a FIXED proposition --
# the home side, or the over -- with the model's probability for that same
# proposition beside it. Reusing it is not a shortcut: those mappings were
# measured, and re-deriving them here would be a second implementation of the
# thing most likely to be wrong.
#
# The open half is the EARLIEST opening read of the same game and market. Not
# the latest: "the open" means the first time this project looked, and a
# re-read twelve hours later is a later look at the same market, not a new
# opening.


def venue_pairs(conn: sqlite3.Connection, *, sport: str,
                market_type: str) -> list[dict]:
    """Every at-the-line claim that also has an opening read to compare with.

    `toward` carries the same meaning as in `pairs()`: positive is movement in
    the direction the model was pointing. The sign comes from the two stored
    probabilities, both written for the same fixed proposition.
    """
    from .market import at_the_line

    config.require_sport(sport, "drift.venue_pairs")
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "at_the_line_claims" not in tables:
        return []
    columns = {r[1] for r in conn.execute("PRAGMA table_info(venue_quotes)")}
    if "read_kind" not in columns:
        # A RECORD OLDER THAN THE OPENING READ has no opening reads in it, so
        # there is no pair to report. Migrating here would make a reporting
        # function write to the database it is reading -- which is what the
        # gate's query-only handle refused, correctly, the first time this ran.
        return []

    claims = conn.execute(
        "SELECT c.id, c.game_id, c.market, c.model_prob, c.venue_implied,"
        "       c.prediction_id"
        "  FROM at_the_line_claims c"
        "  JOIN predictions p ON p.id = c.prediction_id"
        " WHERE c.sport = ? AND c.market = ?"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = c.prediction_id)"
        " ORDER BY c.id",
        (sport, market_type)).fetchall()

    out = []
    for claim in claims:
        first = conn.execute(
            "SELECT MIN(fetched_utc) FROM venue_quotes"
            " WHERE game_id = ? AND market = ? AND read_kind = 'open'",
            (claim["game_id"], claim["market"])).fetchone()[0]
        if first is None:
            continue
        ladder = conn.execute(
            "SELECT * FROM venue_quotes"
            " WHERE game_id = ? AND market = ? AND read_kind = 'open'"
            "   AND fetched_utc = ?",
            (claim["game_id"], claim["market"], first)).fetchall()
        opened = at_the_line.rung_for(list(ladder))
        if opened is None:
            continue
        disagreement = claim["model_prob"] - opened["implied"]
        if abs(disagreement) < MIN_DISAGREEMENT:
            continue
        movement = claim["venue_implied"] - opened["implied"]
        toward = movement if disagreement > 0 else -movement
        out.append({
            "claim_id": claim["id"],
            "prediction_id": claim["prediction_id"],
            "claim": claim["model_prob"],
            "opened": opened["implied"],
            "opened_utc": first,
            "near": claim["venue_implied"],
            "disagreement": round(disagreement, 6),
            "movement": round(movement, 6),
            "toward": round(toward, 6),
        })
    return out


def venue_report(conn: sqlite3.Connection, *, sport: str,
                 market_type: str) -> dict:
    """The venue's open-to-close drift for one category, or the count alone.

    Same gate as `report`, and it is the same rule rather than a copy of it:
    below fifty pairs a direction is a number a reader will remember and the
    sample is not.
    """
    found = venue_pairs(conn, sport=sport, market_type=market_type)
    n = len(found)
    base = {
        "sport": sport,
        "market_type": market_type,
        "source": "venue",
        "n": n,
        "min_pairs": MIN_PAIRS,
        "min_disagreement": MIN_DISAGREEMENT,
        "progress": language.progress(
            n, MIN_PAIRS, noun="pairs",
            cleared_note="enough pairs to report a direction"),
    }
    if n < MIN_PAIRS:
        base["line"] = (
            f"{n} of {MIN_PAIRS} disagreements have both the venue's opening "
            f"read and its price at the line. Nothing is reported about "
            f"direction until there are enough.")
        return base
    moved_toward = sum(1 for p in found if p["toward"] > 0)
    base.update({
        "toward_fraction": round(moved_toward / n, 4),
        "moved_toward": moved_toward,
        "mean_movement": round(sum(p["toward"] for p in found) / n, 6),
        "line": (
            f"Between the venue's opening read and its price at the line, and "
            f"where the model disagreed by {MIN_DISAGREEMENT:.0%} or more, the "
            f"price moved toward the model {moved_toward / n:.0%} of the time "
            f"over {n} games."),
    })
    return base
