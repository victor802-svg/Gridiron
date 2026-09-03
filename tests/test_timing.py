"""The final pass: a second forecast close to start, and one standing row.

The model's confident disagreements lose, and D1 could not test whether that
is because the market knows late news (docs/DIAGNOSIS.md). What the record
does show is that the model guarantees itself the disadvantage by asking
early -- NBA's median lead is 55 days. These tests cover the mechanism that
moves the graded forecast close to start; whether it HELPS is a separate
question that `calibration.early_vs_final` measures rather than assumes.
"""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import calibration, config, db, language, run, tasks
from gridiron.model import predict


def _question_rows(conn, game_id):
    return conn.execute(
        "SELECT id, created_utc, model_prob FROM predictions"
        " WHERE game_id = ? ORDER BY created_utc, id", (game_id,)).fetchall()


# ---------------------------------------------------------------------------
# the constants
# ---------------------------------------------------------------------------

def test_every_sport_has_a_declared_final_pass():
    assert set(config.FINAL_PASS) == set(config.SPORTS)


def test_a_time_that_was_not_measured_says_so():
    """A declared constant may be a judgement; it may not look like a fact."""
    assert config.FINAL_PASS["mlb"].measured is True
    for sport in ("nfl", "cfb", "nba"):
        spec = config.FINAL_PASS[sport]
        assert spec.measured is False, sport
        assert "not measured" in spec.basis.lower(), (
            f"{sport}'s final-pass time is unmeasured and does not say so"
        )


def test_the_mlb_time_matches_what_the_probe_measured():
    """T-1h30m, not the brief's T-2h30m: 85% of lineups vs 46%."""
    assert config.FINAL_PASS["mlb"].minutes_before_first == 90


def test_there_is_a_final_task_for_every_sport_and_it_has_plain_words():
    for sport in config.SPORTS:
        name = f"final:{sport}"
        assert name in tasks.TASKS, sport
        assert name in language.TASK_WORDS, (
            f"{name} would reach the Health panel as an internal identifier"
        )
        assert ":" not in language.TASK_WORDS[name]


# ---------------------------------------------------------------------------
# the write
# ---------------------------------------------------------------------------

def _a_question(conn):
    """One real question about a scheduled game, built the way predict does."""
    from gridiron.factors.compute import FeatureVector
    from gridiron.model.question import Question

    game_id = conn.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1").fetchone()["id"]
    q = Question(sport="nfl", game_id=game_id, market_type="spread",
                 market="spread", subject="KC", line_asked=-3.5,
                 claim="KC cover -3.5", yes_label="cover", no_label="not cover")
    fv = FeatureVector(sport="nfl", market_type="spread")
    fv.values["home_field"] = 1.0
    fv.raw["home_field"] = 1.0
    return q, fv


def test_an_ordinary_rerun_is_still_refused(league):
    """R4 (2026-09-02) is intact: a plain second write is a no-op."""
    q, fv = _a_question(league)
    first = predict.write_prediction(
        league, q, predictor="statistical", prob_yes=0.58, fv=fv,
        reasoning="the early look")
    assert first is not None, "the first write failed; the test proves nothing"
    again = predict.write_prediction(
        league, q, predictor="statistical", prob_yes=0.71, fv=fv,
        reasoning="a plain rerun")
    assert again is None, "a rerun wrote a second opinion"
    assert len(_question_rows(league, q.game_id)) == 1


def test_the_final_pass_writes_a_second_row_for_the_same_question(league):
    """LAW 3: the early row stands untouched and a new row goes beside it."""
    q, fv = _a_question(league)
    early = predict.write_prediction(
        league, q, predictor="statistical", prob_yes=0.58, fv=fv,
        reasoning="the early look")
    assert early is not None
    before = _question_rows(league, q.game_id)

    late = predict.write_prediction(
        league, q, predictor="statistical", prob_yes=0.71, fv=fv,
        reasoning="the late look", final=True)
    assert late is not None, "the final pass wrote nothing"

    after = _question_rows(league, q.game_id)
    assert len(after) == 2, "the second forecast did not land"
    assert after[0]["id"] == before[0]["id"], "the early row was replaced"
    assert abs(after[0]["model_prob"] - 0.58) < 1e-9, "the early claim moved"
    assert abs(after[1]["model_prob"] - 0.71) < 1e-9


def test_the_later_row_is_the_standing_one(league):
    """The record is graded on the late forecast, not the early one."""
    q, fv = _a_question(league)
    predict.write_prediction(league, q, predictor="statistical", prob_yes=0.58,
                             fv=fv, reasoning="early")
    predict.write_prediction(league, q, predictor="statistical", prob_yes=0.71,
                             fv=fv, reasoning="late", final=True)
    rows = _question_rows(league, q.game_id)
    league.execute("UPDATE games SET status='final', home_score=30, away_score=20"
                   " WHERE id = ?", (q.game_id,))
    for r in rows:
        league.execute("UPDATE predictions SET resolved_utc = ?, outcome = 1"
                       " WHERE id = ?", (db.utcnow(), r["id"]))
    league.commit()

    standing = calibration.resolved(league, sport="nfl")
    mine = [r for r in standing if r.game_id == q.game_id]
    assert len(mine) == 1, (
        f"{len(mine)} standing rows for one question; exactly one forecast is "
        f"graded per question"
    )
    assert mine[0].id == rows[-1]["id"], "the EARLY row was graded"
    assert abs(mine[0].model_prob - 0.71) < 1e-9
