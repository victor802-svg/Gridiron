"""Surfaces the audit of 2026-09-05 found leaking, each pinned here.

Every one of these reached a page because the browser suite's world leaves
the surface EMPTY: no task_runs row, no baseball slate, no college slate on
Results, no tiered sport on Record. A plain-words scan cannot see a string
that is never rendered, so each string is composed here from a seeded shape
and scanned directly.
"""
from __future__ import annotations

import re

import pytest

from gridiron import audit, calibration, config, db, language, tasks, views


@pytest.fixture
def mlb_season(monkeypatch):
    """Point the tasks at the fixture's season, as test_scheduler does."""
    seasons = dict(config.SPORT_CURRENT_SEASON)
    seasons["mlb"] = 2025
    monkeypatch.setattr(config, "SPORT_CURRENT_SEASON", seasons)


# --- the Health panel's task detail -----------------------------------------

def test_counted_never_writes_a_bracketed_plural():
    assert language.counted(1, "prediction") == "1 prediction"
    assert language.counted(41, "prediction") == "41 predictions"
    assert language.counted(0, "warning") == "0 warnings"


def test_a_slate_key_never_reaches_a_task_detail(conn):
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, league_date) VALUES ('cfb_probe','cfb',2026,"
        " 20260905,'REG','2026-09-05T23:30:00Z','UGA','CLEM','scheduled',"
        " '2026-09-05')")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, league_date) VALUES ('mlb_probe','mlb',2026,"
        " 161,'REG','2026-09-05T02:10:00Z','SF','NYM','scheduled',"
        " '2026-09-04')")
    conn.commit()
    said = tasks._slate_words(conn, "cfb", 2026, 20260905)
    assert "20260905" not in said and "Saturday 5 September" in said
    said = tasks._slate_words(conn, "mlb", 2026, 161)
    assert "161" not in said and "Friday 4 September" in said, said
    assert audit.plain_words_violations(said) == []


def test_the_predict_task_reports_its_slate_in_words(mlb_league, mlb_season):
    out = tasks.run_task(mlb_league, "predict:mlb", use_llm=False)
    detail = out["detail"]
    assert "(s)" not in detail
    assert re.search(r"\bslate \d", detail) is None, detail
    assert audit.plain_words_violations(detail) == [], detail
