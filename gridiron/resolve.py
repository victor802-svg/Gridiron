"""Settling predictions against what actually happened.

Idempotent by construction. The update carries `AND resolved_utc IS NULL`, so a
second pass over the same prediction matches zero rows rather than overwriting
an outcome; the database trigger `predictions_resolve_once` is the backstop if
some other code path ever tries. Each row is committed as it settles, so a
process killed halfway leaves the first half resolved and the rest open, and
the next run finishes them. Late, never twice.

Resolution writes an outcome. It never touches a probability, a factor vector
or a piece of reasoning (LAW 3), and the trigger will abort the transaction if
it tries.

A note on props where the player did not appear: the question asked was
"does this player record more than N", and a player who did not play recorded
zero, so the claim is false and the prediction resolves against it. That is the
honest reading of our own question, and failing to anticipate an absence is a
real forecasting error rather than an excuse. The training set counts these the
same way, so the model is fitted against the world it is scored in.
"""

from __future__ import annotations

import json
import sqlite3

from .db import utcnow
from .model import questions


class Unresolvable(RuntimeError):
    """The prediction cannot be settled from the data we hold."""


def _prop_actual(conn: sqlite3.Connection, pred: sqlite3.Row) -> float:
    payload = json.loads(pred["factors_json"])
    question = payload.get("question") or {}
    player_id, stat = question.get("player_id"), question.get("stat")
    if not stat:
        raise Unresolvable(
            f"prediction {pred['id']} has no recorded stat; it cannot be settled "
            "without guessing what it meant"
        )

    game = conn.execute(
        "SELECT season, week FROM games WHERE id = ?", (pred["game_id"],)
    ).fetchone()

    row = None
    if player_id:
        row = conn.execute(
            f"SELECT {stat} AS v FROM player_week_stats"
            " WHERE season = ? AND week = ? AND player_id = ?",
            (game["season"], game["week"], player_id),
        ).fetchone()
    if row is None or row["v"] is None:
        return 0.0  # did not appear; recorded nothing
    return float(row["v"])


def outcome_for(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    """1 if the side the model stated is what happened."""
    game = conn.execute(
        "SELECT home_score, away_score, status FROM games WHERE id = ?",
        (pred["game_id"],),
    ).fetchone()
    if game is None or game["status"] != "final":
        raise Unresolvable(f"game {pred['game_id']} is not final")

    if pred["market_type"] == "spread":
        yes = questions.spread_outcome(
            game["home_score"], game["away_score"], pred["line_asked"]
        )
        return yes if pred["model_side"] == "cover" else 1 - yes

    actual = _prop_actual(conn, pred)
    yes = questions.prop_outcome(actual, pred["line_asked"])
    return yes if pred["model_side"] == "over" else 1 - yes


def open_predictions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT p.* FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.resolved_utc IS NULL AND g.status = 'final'"
        " ORDER BY p.id"
    ).fetchall()


def resolve_all(conn: sqlite3.Connection, *, progress=None) -> dict:
    """Settle every open prediction whose game has finished."""
    settled = 0
    already = 0
    failures: list[str] = []

    for pred in open_predictions(conn):
        try:
            outcome = outcome_for(conn, pred)
        except Unresolvable as exc:
            failures.append(f"prediction {pred['id']}: {exc}")
            continue

        cur = conn.execute(
            "UPDATE predictions SET resolved_utc = ?, outcome = ?"
            " WHERE id = ? AND resolved_utc IS NULL",
            (utcnow(), outcome, pred["id"]),
        )
        conn.commit()          # settle one at a time; a crash resumes cleanly
        if cur.rowcount == 1:
            settled += 1
        else:
            already += 1
        if progress and settled % 50 == 0 and settled:
            progress(f"settled {settled}")

    total_open = conn.execute(
        "SELECT COUNT(*) FROM predictions WHERE resolved_utc IS NULL"
    ).fetchone()[0]
    return {
        "settled": settled,
        "already_resolved": already,
        "unresolvable": failures,
        "still_open": total_open,
    }


def summary(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS total,"
        " SUM(CASE WHEN resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved,"
        " SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) AS correct"
        " FROM predictions"
    ).fetchone()
    resolved = row["resolved"] or 0
    return {
        "predictions": row["total"],
        "resolved": resolved,
        "open": row["total"] - resolved,
        "correct": row["correct"] or 0,
        "hit_rate": round((row["correct"] or 0) / resolved, 4) if resolved else None,
    }
