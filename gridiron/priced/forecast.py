"""What the priced forecaster says, and why it says it that way.

THE STARTING POINT IS DECLARED, NOT FITTED. A market-aware forecaster could be
trained on the record, and training one today would fit 1,142 rows of which
none has settled in a market where the model is ahead of the price. So the
first version is a stated blend of two numbers that already exist -- the blind
model's probability and the market's implied probability -- with a weight
declared in config and dated, exactly as the rating decay and the forecast
spreads are.

THE WEIGHT LEANS TOWARD THE MARKET, and the measurement is the reason. On the
73 settled baseball moneyline questions that had a price beside them, the
market's own prices scored 0.2419 against the model's 0.2533, lower being
better. A blend that leaned toward the model would be asserting the opposite of
what this record says. The tilt toward the model is what makes the blend
capable of disagreeing at all, and its size is the declared judgement here.

WHAT THIS IS FOR. Not a better Brier score -- the market will win that for a
long time yet. It is for finding the questions where the model's disagreement
survives being averaged with the price, which is a much smaller set than the
questions where it merely disagrees.
"""
from __future__ import annotations

import sqlite3

from .. import config
from ..db import just_after, utcnow

FORECASTER = "priced"


def blended(model_prob: float | None, implied_prob: float | None) -> float | None:
    """The blind forecast and the market's price, in the declared proportion.

    None where either half is missing. ABSENT STAYS ABSENT: a priced forecast
    with no price in it is a blind forecast wearing another name, and the two
    records exist precisely so that nobody has to guess which is which.
    """
    if model_prob is None or implied_prob is None:
        return None
    weight = config.PRICED_MODEL_WEIGHT
    blend = weight * float(model_prob) + (1.0 - weight) * float(implied_prob)
    return round(min(0.999, max(0.001, blend)), 6)


def movement(opened: float | None, latest: float | None) -> float | None:
    """How far the price has travelled since the blind row was written.

    Reported and stored; it does not move the blend. A line that has already
    moved toward the model is evidence the model was early, and evidence that
    the price it is now being compared against is no longer the one it beat --
    which is a thing to measure before it is a thing to trade on.
    """
    if opened is None or latest is None:
        return None
    return round((float(latest) - float(opened)) * 100.0, 2)


def write_for(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict:
    """One priced row per blind row that has a price to read.

    THE ROW CANNOT BE MISTAKEN FOR A BLIND ONE. It lives in its own table, it
    names the blind prediction it came from, it carries the snapshot it read,
    and a trigger refuses it if it is stamped at or before either. The forecaster
    column says `priced` and every figure that reads it is filtered by that name.
    """
    counts = {"written": 0, "already": 0, "no_price": 0, "considered": 0}
    if not prediction_ids:
        return counts
    placeholders = ",".join("?" for _ in prediction_ids)
    rows = conn.execute(
        "SELECT p.id, p.sport, p.game_id, p.market_type, p.prop_type,"
        " p.model_prob, p.created_utc,"
        " (SELECT s.id FROM market_snapshots s WHERE s.prediction_id = p.id"
        "   AND s.implied_prob IS NOT NULL ORDER BY s.id LIMIT 1) AS snapshot_id,"
        " (SELECT s.implied_prob FROM market_snapshots s WHERE s.prediction_id = p.id"
        "   AND s.implied_prob IS NOT NULL ORDER BY s.id LIMIT 1) AS opened,"
        " (SELECT s.implied_prob FROM market_snapshots s WHERE s.prediction_id = p.id"
        "   AND s.implied_prob IS NOT NULL ORDER BY s.fetched_utc DESC, s.id DESC"
        "   LIMIT 1) AS latest"
        f" FROM predictions p WHERE p.id IN ({placeholders})"
        "   AND NOT EXISTS (SELECT 1 FROM priced_forecasts f"
        "                   WHERE f.prediction_id = p.id"
        "                     AND f.blend_version = ?)",
        list(prediction_ids) + [config.PRICED_VERSION]).fetchall()

    for row in rows:
        counts["considered"] += 1
        prob = blended(row["model_prob"], row["opened"])
        if prob is None:
            counts["no_price"] += 1
            continue
        try:
            conn.execute(
                "INSERT INTO priced_forecasts (prediction_id, snapshot_id,"
                " blend_version, sport, game_id, market_type, prop_type,"
                " blind_prob, price_at_write, price_latest, price_move_cents,"
                " priced_prob, created_utc)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["id"], row["snapshot_id"], config.PRICED_VERSION,
                 row["sport"], row["game_id"], row["market_type"],
                 row["prop_type"], row["model_prob"], row["opened"],
                 row["latest"], movement(row["opened"], row["latest"]), prob,
                 just_after(row["created_utc"])))
            counts["written"] += 1
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" not in str(exc):
                raise
            counts["already"] += 1
    conn.commit()
    return counts


def forecasts_for(conn: sqlite3.Connection,
                  prediction_ids: list[int]) -> dict[int, sqlite3.Row]:
    """This version's priced row per blind prediction."""
    if not prediction_ids:
        return {}
    placeholders = ",".join("?" for _ in prediction_ids)
    return {
        r["prediction_id"]: r
        for r in conn.execute(
            f"SELECT * FROM priced_forecasts WHERE blend_version = ?"
            f" AND prediction_id IN ({placeholders})",
            [config.PRICED_VERSION] + list(prediction_ids))
    }


def resolve_forecasts(conn: sqlite3.Connection) -> dict:
    """Copy the blind row's outcome onto the priced row it came from.

    THE SAME OUTCOME, NEVER A SECOND JUDGEMENT. The two forecasters answered
    the same question about the same game; if they could disagree about what
    happened, every comparison between them would be meaningless.
    """
    counts = {"settled": 0, "still_open": 0}
    rows = conn.execute(
        "SELECT f.id, p.outcome FROM priced_forecasts f"
        " JOIN predictions p ON p.id = f.prediction_id"
        " WHERE f.resolved_utc IS NULL AND p.resolved_utc IS NOT NULL"
        "   AND p.outcome IS NOT NULL").fetchall()
    now = utcnow()
    for row in rows:
        cur = conn.execute(
            "UPDATE priced_forecasts SET resolved_utc = ?, outcome = ?"
            " WHERE id = ? AND resolved_utc IS NULL", (now, row["outcome"], row["id"]))
        counts["settled"] += cur.rowcount
    conn.commit()
    counts["still_open"] = conn.execute(
        "SELECT COUNT(*) FROM priced_forecasts WHERE resolved_utc IS NULL"
    ).fetchone()[0]
    return counts
