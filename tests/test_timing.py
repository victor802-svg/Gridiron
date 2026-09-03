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

from gridiron import calibration, config, db, language, run, tasks, views
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


# ---------------------------------------------------------------------------
# the surfaces (A3)
# ---------------------------------------------------------------------------

def _two_passes(conn, sport="nfl"):
    """One question, forecast early and again close to start."""
    game = conn.execute(
        "SELECT id, season, week, kickoff_utc FROM games"
        " WHERE sport = ? AND kickoff_utc IS NOT NULL LIMIT 1",
        (sport,)).fetchone()
    for pass_kind, shift, prob in (("early", -86400, 0.58), ("final", -3600, 0.71)):
        created = _shift(game["kickoff_utc"], shift)
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor,"
            " pass_kind, factor_set_version, factors_json, reasoning)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (created, sport, game["id"], "spread", "TWOPASS", -3.5, prob,
             "cover", "statistical", pass_kind, config.FACTOR_SET_VERSION,
             '{"values": {}, "present": [], "absent": []}', "seeded"))
    conn.commit()
    return game


def _shift(stamp, seconds):
    from datetime import datetime, timedelta
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return (moment + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_picks_shows_one_card_per_question_when_both_passes_ran(league):
    """The duplicate-slate defect of 2026-08-29, arriving by a different road."""
    game = _two_passes(league)
    payload = views.week(league, "nfl", game["season"], game["week"])
    mine = [c for c in payload["cards"] if c["subject"] == "TWOPASS"]
    assert len(mine) == 1, (
        f"{len(mine)} cards for one question; the final pass writes a second "
        f"forecast, so an unfiltered Picks list shows every game twice"
    )
    assert abs(mine[0]["model_prob"] - 0.71) < 1e-9, "Picks showed the EARLY row"
    assert mine[0]["is_early_view"] is False


def test_the_early_view_shows_the_other_row_and_labels_it(league):
    game = _two_passes(league)
    payload = views.week(league, "nfl", game["season"], game["week"],
                         early_view=True)
    mine = [c for c in payload["cards"] if c["subject"] == "TWOPASS"]
    assert len(mine) == 1
    assert abs(mine[0]["model_prob"] - 0.58) < 1e-9, "the early view showed the final row"
    assert mine[0]["is_early_view"] is True
    assert "Early view" in (mine[0]["pass_note"] or "")
    assert "stands in its place" in (mine[0]["pass_note"] or "")


def test_picks_offers_the_early_view_only_when_one_exists(league):
    game = _two_passes(league)
    assert views.week(league, "nfl", game["season"], game["week"])["has_early_view"] is True


def test_an_unreplaced_early_row_is_not_called_an_early_view(league):
    """MISSED: the early row IS the forecast, and must not read as superseded."""
    game = league.execute(
        "SELECT id, season, week, kickoff_utc FROM games WHERE sport='nfl'"
        "   AND kickoff_utc IS NOT NULL LIMIT 1").fetchone()
    league.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (_shift(game["kickoff_utc"], -86400), "nfl", game["id"], "spread",
         "ONLYEARLY", -3.5, 0.6, "cover", "statistical", "early",
         config.FACTOR_SET_VERSION,
         '{"values": {}, "present": [], "absent": []}', "seeded"))
    league.commit()
    payload = views.week(league, "nfl", game["season"], game["week"])
    mine = [c for c in payload["cards"] if c["subject"] == "ONLYEARLY"][0]
    assert mine["is_early_view"] is False
    assert "stands in its place" not in (mine["pass_note"] or ""), (
        "an early row nothing replaced was told it had been replaced"
    )
    assert "this one stands" in (mine["pass_note"] or "")


def test_the_results_mark_says_which_forecast_was_graded():
    assert language.pass_mark("final") == "final"
    assert language.pass_mark("early") == "early only"
    assert language.pass_mark(None) == "early only"


def test_the_settings_page_says_which_times_were_measured():
    from gridiron import settings
    rows = {r["name"]: r for r in settings.fenced()}
    assert "(not measured)" not in rows["FINAL_PASS[mlb]"]["value"]
    for sport in ("nfl", "cfb", "nba"):
        assert "(not measured)" in rows[f"FINAL_PASS[{sport}]"]["value"], sport


# ---------------------------------------------------------------------------
# A FORECASTER THAT STOPS IS A DEFECT, NOT A FOOTNOTE (S4, 2026-09-03)
# ---------------------------------------------------------------------------

def _seed_forecaster_rows(conn, predictor, created, n=3):
    game = conn.execute(
        "SELECT id FROM games WHERE sport='nfl' LIMIT 1").fetchone()["id"]
    for i in range(n):
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor,"
            " pass_kind, factor_set_version, factors_json, reasoning)"
            " VALUES (?,?,?,?,?,?,?,?,?,'early',?,?,?)",
            (created, "nfl", game, "spread", f"SEED{predictor}{i}", -3.5,
             0.6, "cover", predictor, config.FACTOR_SET_VERSION,
             '{"values": {}, "present": [], "absent": []}', "seeded"))
    conn.commit()


def test_a_forecaster_that_stopped_writing_reaches_the_front_page(league):
    """The LLM was absent for thirty hours and every screen looked healthy."""
    _seed_forecaster_rows(league, "llm", "2020-01-01T00:00:00Z")
    warnings = views._front_page_warnings(league)
    silent = [w for w in warnings if w.get("kind") == "forecaster-silent"]
    assert silent, (
        "a forecaster with rows on the record and nothing recent did not "
        "reach the front page"
    )
    said = silent[0]["text"]
    assert "reasoning pass" in said, "the panel named an internal identifier"
    assert "llm" not in said.lower().replace("reasoning", "")
    assert "3 forecasts" in said


def test_a_forecaster_writing_today_is_not_reported_silent(league):
    _seed_forecaster_rows(league, "llm", db.utcnow())
    silent = [w for w in views._front_page_warnings(league)
              if w.get("kind") == "forecaster-silent"]
    assert not silent, "a forecaster that wrote today was reported as stopped"


def test_a_forecaster_that_never_wrote_is_not_reported_silent(league):
    """Never having written is not the same as having stopped."""
    silent = [w for w in views._front_page_warnings(league)
              if w.get("kind") == "forecaster-silent"]
    assert not silent


def test_the_silence_reason_is_in_plain_words():
    said = language.forecaster_silent_line("llm", 40.0, 23, "bad_api_key")
    assert "its key was refused" in said
    assert "bad_api_key" not in said, "an internal token reached the sentence"
    # An unknown reason degrades to no reason rather than to the raw token.
    plain = language.forecaster_silent_line("llm", 40.0, 23, "something_new")
    assert "something_new" not in plain
