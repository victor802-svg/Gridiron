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


# ---------------------------------------------------------------------------
# ONE PRICED ROW PER STANDING QUESTION, PER FORECASTER (operator question 14,
# ruled 2026-09-27: "Every count on the Record page that states a gate
# distance is rebuilt per forecaster (per tier for UFC) and per distinct bet,
# through its record's standing rule.")
# ---------------------------------------------------------------------------

#: THE TWO BLIND FORECASTERS A PRICED ROW CAN BLEND -- `predictions.predictor`'s
#: own CHECK. A priced row names no forecaster of its own (its forecaster is
#: always `priced`); it is the blend of ONE blind forecast and is counted as
#: that forecast's forecaster's (2026-09-27), as an at-the-line claim is.
BLIND_FORECASTERS = ("statistical", "llm")


class PooledCount(ValueError):
    """A count of priced forecasts asked for without saying whose, or across
    tiers."""


def refuse_a_pooled_count(sport: str, predictor, event_tier) -> None:
    """The questions every count of priced forecasts must answer first.

    ONE FORECASTER, AND FOR A SPORT THAT SPLITS BELOW THE MARKET, ONE TIER
    (LAW 4, LAW 6; operator question 14, 2026-09-27). Asked in the door, so a
    pooled count cannot be made by leaving an argument out.
    """
    config.require_sport(sport, "priced.forecast.standing_forecasts")
    if predictor not in BLIND_FORECASTERS:
        raise PooledCount(
            f"LAW 4 / LAW 6: a count of {sport} priced forecasts was asked for "
            f"forecaster {predictor!r}. A priced row blends one blind forecast, "
            f"and the statistical model's and the reasoning pass's are counted "
            f"apart and never pooled: name one of {list(BLIND_FORECASTERS)}.")
    tiers = config.event_tiers(sport)
    if tiers and event_tier not in tiers:
        raise PooledCount(
            f"LAW 6: a count of {sport} priced forecasts names event tier "
            f"{event_tier!r}, not one of {sport}'s declared tiers "
            f"{list(tiers)}; tiers are reported side by side, never summed.")
    if not tiers and event_tier is not None:
        raise PooledCount(
            f"LAW 6: {sport} declares no event tiers, so a count naming tier "
            f"{event_tier!r} counts nothing that exists.")


def standing_forecasts(conn: sqlite3.Connection, *, sport: str, predictor: str,
                       event_tier: str | None = None) -> list[sqlite3.Row]:
    """THE ONE DOOR every count of the priced record goes through: this
    version's priced row on each STANDING question of ONE blind forecaster
    (and, for a sport that splits below the market, one tier), settled or not.

    A PRICED ROW BELONGS TO ONE BLIND FORECAST, and is written for every
    forecast that had a price -- a question's morning pass and its final pass
    each get one, and so does each forecaster's. So the record counts them
    through the BLIND RECORD'S OWN STANDING RULE, `calibration.
    standing_row_clause`: the row counted is the one on the question's
    standing forecast (the latest written before the start, a withdrawn one
    never), and a question is counted once per forecaster. A question whose
    standing forecast carried no price has no priced row and is not counted,
    even if a superseded pass of it was priced (none on the record on
    2026-09-27): a superseded forecast is not the record's, blind or priced.

    THE OPERATOR'S RULING of 2026-09-27 (question 14, 1 of 3). Until this
    date `calibration.priced_scorecard` counted every settled priced row of
    the sport in one category per market -- both forecasters, both passes --
    and worded its gate on that: MLB moneyline said "261 settled comparisons,
    past the 100 this record needs" on 26 September, which were 139 rows on
    the statistical model's forecasts (96 standing questions) and 122 on the
    reasoning pass's (84).

    Every row carries its market as the record names it (`market`: the prop
    type, or the market), its blind forecaster, the question's own keys and
    its card's tier, so a payload can say how many distinct bets it counts
    (`count_of_bets`) and whose -- counted beside the door, not by it.
    """
    from ..calibration import standing_row_clause

    refuse_a_pooled_count(sport, predictor, event_tier)
    tiers = config.event_tiers(sport)
    # THE CARD, READ OFF THE ROW'S OWN GAME, so a door that stopped filtering
    # by tier is seen in the payload rather than trusted (item 6's open
    # finding, 2026-09-26: its tier was checked by label only).
    tier_column = (
        "(SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
        "   ON e.id = b.event_id WHERE b.id = p.game_id)"
        if tiers else "NULL")
    tier_clause, params = "", [sport, config.PRICED_VERSION, predictor]
    if event_tier is not None:
        # LAW 6 ONE LEVEL DOWN (R2, 2026-09-03), reached through the bout to
        # the card, exactly as `calibration.resolved` reaches it.
        tier_clause = (
            " AND EXISTS (SELECT 1 FROM ufc_bouts b JOIN ufc_events e"
            "               ON e.id = b.event_id"
            "              WHERE b.id = p.game_id AND e.event_tier = ?)")
        params.append(event_tier)
    return conn.execute(
        "SELECT f.id, f.prediction_id, f.sport, f.game_id, f.market_type,"
        "       f.prop_type,"
        "       COALESCE(NULLIF(f.prop_type, ''), f.market_type) AS market,"
        "       f.priced_prob, f.blind_prob, f.price_at_write, f.outcome,"
        "       f.resolved_utc, p.predictor, p.market_type AS question_market,"
        "       p.subject, p.line_asked,"
        f"      {tier_column} AS event_tier"
        "  FROM priced_forecasts f"
        "  JOIN predictions p ON p.id = f.prediction_id"
        "  JOIN games g ON g.id = p.game_id"
        " WHERE f.sport = ? AND f.blend_version = ? AND p.predictor = ?"
        f"{tier_clause}{standing_row_clause(False)}"
        " ORDER BY f.id", params).fetchall()


def bet_of(row) -> tuple:
    """Which bet a priced row is on: the blind QUESTION it priced -- its game,
    market, subject and rung -- without the forecaster who asked it.

    The standing rule keeps one row per question PER FORECASTER, so within
    one forecaster's count this key is unique; two forecasters, or two passes
    of one question, in one count put two rows on one key, which is what
    `calibration.assert_no_pooled_priced_counts` compares with the count.
    """
    return (row["game_id"], row["question_market"], row["subject"],
            row["line_asked"])


def count_of_bets(rows) -> int:
    """How many distinct bets a list of priced rows is on."""
    return len({bet_of(r) for r in rows})


def settled(rows) -> list:
    """The priced rows that carry their blind row's outcome: ONE predicate for
    every settled count of the priced record."""
    return [r for r in rows if r["outcome"] is not None]


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
