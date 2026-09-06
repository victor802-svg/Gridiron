"""A slate of voided rows is not offered, and an empty pinned week says why
(UI audit finding 13, 2026-09-05). The NBA picker read "Week 1, 2026 (47)"
beside "0 picks" -- 47 voided rows -- and, with the week pinned, the page
lost the season-start sentence and gained four quiet-market reasons that
were not true of a season that had not begun."""
from __future__ import annotations

from gridiron import resolve, views


def test_a_slate_of_voided_rows_is_not_offered_and_the_empty_week_says_why(world_copy):
    conn = world_copy
    row = conn.execute(
        "SELECT p.sport, g.season, g.week FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.resolved_utc IS NULL GROUP BY p.sport, g.season, g.week"
        " ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    sport, season, week = row["sport"], row["season"], row["week"]
    ids = [r[0] for r in conn.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ?", (sport, season, week))]
    assert ids
    listed = [w for w in views.available_weeks(conn, sport) if w["season"] == season and w["week"] == week]
    assert listed and listed[0]["n"] == len(ids)
    for pid in ids:
        resolve.void_prediction(conn, pid, "test: the whole slate voided")
    conn.commit()
    listed = [w for w in views.available_weeks(conn, sport) if w["season"] == season and w["week"] == week]
    assert listed == [], "a slate with nothing but voided rows is still offered"
    data = views.week(conn, sport, season=season, wk=week)
    assert data["cards"] == []
    assert data["message"], "an empty pinned week says nothing about why"
    assert data["quiet_markets"] == [], "quiet-market reasons on a slate that asked no questions"


def test_a_slate_with_forecasts_carries_no_message(world_copy):
    sport = world_copy.execute("SELECT sport FROM predictions LIMIT 1").fetchone()[0]
    data = views.week(world_copy, sport)
    if data["cards"]:
        assert data["message"] is None
