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

VOID is a terminal state, and it is not a loss. A prop whose stat cannot be
read - the player did not appear, or the box score carries no value for him -
is voided with a stated reason rather than settled on a guess.

This reverses an earlier choice, and the reason is worth writing down. It used
to resolve as a loss, on the reasoning that a player who did not play recorded
zero, so "more than 180.5 yards" was false. True as arithmetic, wrong as
measurement: it scores a production forecast on whether somebody was active,
which is a different question from the one that was asked. The selection rule
now excludes players already ruled Out, so a non-appearance is a genuine
surprise rather than something we walked into - and the void COUNT is reported
beside every prop curve, because a model that keeps choosing players who do not
play is telling you something, and burying it in the loss column would hide it.

Voids live in `prediction_voids`, not in a nullable outcome, so `predictions`
keeps its CHECK constraints exactly as strict as they were and stays
append-only. A trigger refuses to resolve a voided prediction afterwards.
"""

from __future__ import annotations

import json
import sqlite3

from . import calls, subjects
from .db import utcnow
from .model import questions


class Unresolvable(RuntimeError):
    """The prediction cannot be settled from the data we hold."""


class Void(RuntimeError):
    """The question cannot be answered from real data, and will not be guessed."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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

    if not player_id:
        raise Void(
            f"no player id recorded on prediction {pred['id']}; the stat cannot "
            "be looked up without guessing who it was about"
        )
    row = conn.execute(
        f"SELECT {stat} AS v FROM player_week_stats"
        " WHERE season = ? AND week = ? AND player_id = ?",
        (game["season"], game["week"], player_id),
    ).fetchone()
    # A void reason is SHOWN, so it obeys the plain-words rule like any other
    # sentence: the stored subject of a prop carries the stat as a suffix
    # ("FERNANDO TATIS JR. BATTER_HITS") and the reader gets the person.
    who = subjects.strip_market_suffix(pred["subject"], pred["prop_type"])
    if row is None:
        raise Void(
            f"{who} has no box score for {game['season']} week "
            f"{game['week']}: the player did not appear, so the question has no "
            "answer and is not being given one"
        )
    if row["v"] is None:
        raise Void(
            f"{who} appeared but {stat} is not reported for "
            f"{game['season']} week {game['week']}"
        )
    return float(row["v"])


def outcome_for(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    """1 if the side the model stated is what happened.

    Dispatches to the sport's own adapter: a baseball moneyline and a football
    spread are settled by different arithmetic, and neither should know about
    the other.
    """
    from . import sports

    sport = pred["sport"] if "sport" in pred.keys() else "nfl"
    return sports.get(sport).resolve_outcome(conn, pred)


def resolve_nfl_outcome(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    """NFL: a spread cover, or a player prop over/under."""
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
    """Unresolved predictions on finished games, excluding those already void."""
    return conn.execute(
        "SELECT p.* FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.resolved_utc IS NULL AND g.status = 'final'"
        " AND NOT EXISTS (SELECT 1 FROM prediction_voids v WHERE v.prediction_id = p.id)"
        " ORDER BY p.id"
    ).fetchall()


def void_prediction(conn: sqlite3.Connection, prediction_id: int, reason: str) -> bool:
    """Mark a prediction unanswerable. Idempotent: the first reason stands."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO prediction_voids (prediction_id, voided_utc, reason)"
        " VALUES (?,?,?)",
        (prediction_id, utcnow(), reason),
    )
    # A VOIDED PREDICTION VOIDS ITS CALLS, for the same reason and by the same
    # act: the question was never answered, so nothing anyone said about it can
    # be right or wrong. Left UNRESOLVED rather than marked lost -- exactly the
    # treatment the prediction itself gets.
    open_calls = calls.void_for(conn, prediction_id)
    conn.commit()
    if open_calls:
        _voided_calls[prediction_id] = open_calls
    return cur.rowcount == 1


#: How many of the operator's calls each void took with it, for the report.
_voided_calls: dict[int, int] = {}


def resolve_all(conn: sqlite3.Connection, *, progress=None) -> dict:
    """Settle every open prediction whose game has finished."""
    settled = 0
    calls_settled = 0
    already = 0
    voided = 0
    void_reasons: list[str] = []
    failures: list[str] = []

    for pred in open_predictions(conn):
        try:
            outcome = outcome_for(conn, pred)
        except Void as exc:
            if void_prediction(conn, pred["id"], exc.reason):
                voided += 1
                void_reasons.append(f"prediction {pred['id']}: {exc.reason}")
            continue
        except Unresolvable as exc:
            failures.append(f"prediction {pred['id']}: {exc}")
            continue

        cur = conn.execute(
            "UPDATE predictions SET resolved_utc = ?, outcome = ?"
            " WHERE id = ? AND resolved_utc IS NULL",
            (utcnow(), outcome, pred["id"]),
        )
        if cur.rowcount == 1:
            # THE OPERATOR'S CALL SETTLES IN THE SAME PASS, by the same code,
            # at the same instant (GRIDIRON_12). A separate resolver for calls
            # would be a second thing that decides what happened, and the two
            # would eventually disagree about a game.
            calls_settled += calls.resolve_for(
                conn, pred["id"], outcome, pred["model_side"])
        conn.commit()          # settle one at a time; a crash resumes cleanly
        if cur.rowcount == 1:
            settled += 1
        else:
            already += 1
        if progress and settled % 50 == 0 and settled:
            progress(f"settled {settled}")

    total_open = conn.execute(
        "SELECT COUNT(*) FROM predictions p WHERE p.resolved_utc IS NULL"
        " AND NOT EXISTS (SELECT 1 FROM prediction_voids v WHERE v.prediction_id = p.id)"
    ).fetchone()[0]
    return {
        "settled": settled,
        # Reported separately and never added to `settled`: one is the model's
        # record and the other is the operator's, and they are different
        # forecasters (ruling R2).
        "calls_settled": calls_settled,
        "already_resolved": already,
        "voided": voided,
        "void_reasons": void_reasons[:20],
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
    voided = conn.execute("SELECT COUNT(*) FROM prediction_voids").fetchone()[0]
    resolved = row["resolved"] or 0
    return {
        "predictions": row["total"],
        "resolved": resolved,
        "voided": voided,
        "open": row["total"] - resolved - voided,
        "correct": row["correct"] or 0,
        "hit_rate": round((row["correct"] or 0) / resolved, 4) if resolved else None,
    }
