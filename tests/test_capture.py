"""S1: what was knowable, and when.

The timing probe of 2026-09-02 could not measure three sports out of four, and
not because the data was missing -- because it carried no capture time, or was
backfilled after the fact and looked identical to a live capture. These tests
cover the tables and the pass that make the difference recordable.
"""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import capture, config, db, language, tasks


def _an_injury(conn, season, week=1, name="A. Player", status="Questionable"):
    conn.execute(
        "INSERT OR REPLACE INTO injuries (season, week, team, player_id,"
        " player_name, position, report_status, practice_status)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (season, week, "KC", "p1", name, "WR", status, "LP"))
    conn.commit()


# ---------------------------------------------------------------------------
# the report's history becomes data
# ---------------------------------------------------------------------------

def test_a_capture_stamps_the_injury_report(league):
    season = config.SPORT_CURRENT_SEASON.get("nfl", config.CURRENT_SEASON)
    _an_injury(league, season)
    assert capture.capture_injuries(league, "nfl") == 1
    row = league.execute(
        "SELECT player_name, report_status, captured_utc"
        "  FROM injury_reports").fetchone()
    assert row["player_name"] == "A. Player"
    assert row["captured_utc"], "a captured row carries no capture time"


def test_the_report_becomes_a_sequence_rather_than_a_snapshot(league):
    """A player questionable and later out is the thing a probe needs."""
    season = config.SPORT_CURRENT_SEASON.get("nfl", config.CURRENT_SEASON)
    _an_injury(league, season, status="Questionable")
    capture.capture_injuries(league, "nfl")

    # A later capture, after the report changed. The stamp differs, so the
    # first observation is NOT overwritten -- which is the whole point.
    league.execute("UPDATE injuries SET report_status = 'Out'")
    league.commit()
    league.execute(
        "INSERT OR IGNORE INTO injury_reports (sport, season, week, team,"
        " player_name, report_status, captured_utc)"
        " VALUES ('nfl', ?, 1, 'KC', 'A. Player', 'Out', ?)",
        (season, "2099-01-01T00:00:00Z"))
    league.commit()

    seen = league.execute(
        "SELECT report_status FROM injury_reports"
        " ORDER BY captured_utc").fetchall()
    assert [r["report_status"] for r in seen] == ["Questionable", "Out"], (
        "the later capture overwrote the earlier one; the report's history "
        "is exactly what this table exists to keep"
    )


def test_an_injury_row_cannot_be_stored_without_a_capture_time(league):
    """The column is NOT NULL, so the defect cannot come back by omission."""
    with pytest.raises(sqlite3.IntegrityError):
        league.execute(
            "INSERT INTO injury_reports (sport, season, week, team,"
            " player_name, captured_utc) VALUES ('nfl',2026,1,'KC','X',NULL)")


# ---------------------------------------------------------------------------
# a backfill may never pose as a live capture
# ---------------------------------------------------------------------------

def test_every_stored_lineup_is_marked_backfill_until_one_is_captured_live(league):
    """125,244 rows arrived from one historical load, and say so."""
    rows = league.execute(
        "SELECT DISTINCT source FROM mlb_lineups").fetchall()
    assert all(r["source"] == "backfill" for r in rows), (
        "a historically loaded lineup is not marked as one"
    )


def test_a_lineup_capture_must_declare_which_it_is(league):
    game = league.execute("SELECT id FROM games LIMIT 1").fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        league.execute(
            "INSERT INTO lineup_captures (game_id, side, slot, player_id,"
            " captured_utc, source) VALUES (?,'home',1,1,?,'invented')",
            (game, db.utcnow()))


def test_a_lineup_after_first_pitch_is_not_captured_as_live(league):
    """Storing it live would put the backfill's lie back."""
    game = league.execute(
        "SELECT id FROM games WHERE kickoff_utc IS NOT NULL LIMIT 1").fetchone()
    league.execute(
        "UPDATE games SET kickoff_utc = '2000-01-01T00:00:00Z',"
        " status = 'final' WHERE id = ?", (game["id"],))
    league.execute(
        "INSERT INTO mlb_lineups (game_id, side, slot, player_id, player_name,"
        " recorded_utc, source) VALUES (?,'home',1,1,'X',?,'backfill')",
        (game["id"], db.utcnow()))
    league.commit()
    assert capture.capture_lineups(league) == 0


# ---------------------------------------------------------------------------
# loud on empty, but only when something was there
# ---------------------------------------------------------------------------

def test_a_quiet_day_is_not_a_failure(league):
    """Out of season there is nothing to stamp, and that is not a fault."""
    league.execute("DELETE FROM injuries")
    league.commit()
    counts = capture.run(league)
    assert counts["eligible"] == 0
    assert not any(counts[k] for k in ("injuries", "lineups", "weather"))


def test_something_eligible_and_nothing_captured_is_loud(league, monkeypatch):
    season = config.SPORT_CURRENT_SEASON.get("nfl", config.CURRENT_SEASON)
    _an_injury(league, season)
    monkeypatch.setattr(capture, "capture_injuries", lambda *a, **k: 0)
    monkeypatch.setattr(capture, "capture_lineups", lambda *a, **k: 0)
    with pytest.raises(capture.NothingCaptured) as exc:
        capture.run(league)
    assert "eligible" in str(exc.value)


def test_the_weather_tables_are_kept_apart(league):
    """A forecast copied into an observations table is the confusion the two
    tables exist to prevent, so the capture pass writes none."""
    assert capture.capture_weather(league) == 0
    assert league.execute(
        "SELECT COUNT(*) FROM weather_observed").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# the task
# ---------------------------------------------------------------------------

def test_the_capture_task_is_registered_with_a_plain_name():
    assert "capture" in tasks.TASKS
    assert tasks.TASKS["capture"].every_hours == 4.0
    said = language.task_name("capture")
    assert said and ":" not in said
    assert "capture" not in said.lower(), (
        "the Health panel would show the task's internal name"
    )
