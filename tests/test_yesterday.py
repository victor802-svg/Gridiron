"""The yesterday strip is dated by the league day of the games (UI audit
finding 7, 2026-09-05).

It grouped settled picks by the UTC date of the resolver's run, so an
evening's games fell on tomorrow's date and the strip read "6 September: 10
right, 9 wrong" at 10 pm on the 5th. The fixture world resolves 2025 games
today, so the UTC date and the league day never agree -- which is exactly
the shape the fixture used not to contain.
"""
from __future__ import annotations

from gridiron import language, views


def test_the_yesterday_strip_is_dated_by_the_league_day(world_copy):
    conn = world_copy
    sport = conn.execute(
        "SELECT sport FROM predictions WHERE resolved_utc IS NOT NULL LIMIT 1").fetchone()[0]
    # The synthetic league records no league day; give its games one -- the
    # kickoff's date -- on this private copy, so the strip has a day to name.
    conn.execute("UPDATE games SET league_date = substr(kickoff_utc, 1, 10) WHERE league_date IS NULL")
    conn.commit()
    day = conn.execute(
        "SELECT MAX(g.league_date) FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL", (sport,)).fetchone()[0]
    assert day, "the fixture games carry no league day"
    utc_day = conn.execute(
        "SELECT MAX(substr(resolved_utc, 1, 10)) FROM predictions"
        " WHERE sport = ? AND resolved_utc IS NOT NULL", (sport,)).fetchone()[0]
    assert utc_day != day, "the fixture resolved its games on their league day; the test cannot tell the two apart"
    strip = views._yesterday(conn, sport)
    assert strip is not None
    assert strip["label"] == language.settled_day_label(day), strip["label"]
    n, right = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN p.outcome = 1 THEN 1 ELSE 0 END)"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL AND g.league_date = ?"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v WHERE v.prediction_id = p.id)",
        (sport, day)).fetchone()
    assert strip["right"] + strip["wrong"] == n
    assert strip["right"] == (right or 0)
