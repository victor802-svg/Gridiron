"""Reading college football out of the record. No market data, ever.

Every function here takes `sport='cfb'` implicitly and reads only `games` and
`teams`. It is inside the LAW 1 prediction closure, so it may not name a market
column and the closure scan enforces that.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SPORT = "cfb"


def game(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM games WHERE id = ? AND sport = 'cfb'", (game_id,)
    ).fetchone()


def slate(conn: sqlite3.Connection, season: int, day: int) -> list[sqlite3.Row]:
    """Every game on one day's slate, in kickoff order.

    A CFB slate is a DAY. `week` on a stored row is the day as YYYYMMDD, which
    is what the loader writes -- the feed's `week.number` is null for the live
    season and would merge Saturday's 60 games with Friday's 8 anyway.
    """
    return conn.execute(
        "SELECT * FROM games WHERE sport = 'cfb' AND season = ? AND week = ?"
        " ORDER BY kickoff_utc, id",
        (season, day),
    ).fetchall()


def next_slate(conn: sqlite3.Connection, season: int, *,
               after_utc: str | None = None) -> int | None:
    """The next day that has an unplayed game, or None.

    Ordered by the DAY, not by kickoff: a slate is answered as a unit, and a
    late Saturday game does not make Saturday a different slate from the noon
    one.
    """
    row = conn.execute(
        "SELECT MIN(week) AS day FROM games WHERE sport = 'cfb' AND season = ?"
        "  AND status = 'scheduled'"
        + (" AND kickoff_utc > ?" if after_utc else ""),
        (season, after_utc) if after_utc else (season,),
    ).fetchone()
    return int(row["day"]) if row and row["day"] is not None else None


def completed(conn: sqlite3.Connection, season: int | None = None) -> list[sqlite3.Row]:
    sql = ("SELECT * FROM games WHERE sport = 'cfb' AND status = 'final'"
           "  AND home_score IS NOT NULL AND away_score IS NOT NULL")
    params: tuple = ()
    if season is not None:
        sql += " AND season = ?"
        params = (season,)
    return conn.execute(sql + " ORDER BY kickoff_utc, id", params).fetchall()


def scoring_form(conn: sqlite3.Connection, team: str, *, before_utc: str,
                 window: int = 5) -> dict:
    """Points scored and allowed per game over a team's last `window` games.

    STRICTLY BEFORE `before_utc`. A rolling window that can see the game it is
    about is the leak that made an NBA model appear to beat the market by 14%,
    and it is invisible in the output -- so the bound is a parameter here
    rather than a convention someone has to remember.

    Returns counts of None when the team has no completed games yet, which the
    caller must treat as ABSENT rather than as zero.
    """
    rows = conn.execute(
        "SELECT home, away, home_score, away_score FROM games"
        " WHERE sport = 'cfb' AND status = 'final'"
        "   AND home_score IS NOT NULL AND away_score IS NOT NULL"
        "   AND kickoff_utc < ?"
        "   AND (home = ? OR away = ?)"
        " ORDER BY kickoff_utc DESC LIMIT ?",
        (before_utc, team, team, window),
    ).fetchall()
    if not rows:
        return {"games": 0, "for_pg": None, "against_pg": None}

    scored = allowed = 0.0
    for r in rows:
        if r["home"] == team:
            scored += r["home_score"]
            allowed += r["away_score"]
        else:
            scored += r["away_score"]
            allowed += r["home_score"]
    n = len(rows)
    return {"games": n, "for_pg": scored / n, "against_pg": allowed / n}


def days_rest(conn: sqlite3.Connection, team: str, *, before_utc: str) -> int | None:
    """Days since this team last played, or None if it has not played yet."""
    row = conn.execute(
        "SELECT kickoff_utc FROM games WHERE sport = 'cfb' AND status = 'final'"
        "   AND kickoff_utc < ? AND (home = ? OR away = ?)"
        " ORDER BY kickoff_utc DESC LIMIT 1",
        (before_utc, team, team),
    ).fetchone()
    if not row or not row["kickoff_utc"]:
        return None
    try:
        last = datetime.strptime(row["kickoff_utc"], "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.strptime(before_utc, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return (now.replace(tzinfo=timezone.utc) - last.replace(tzinfo=timezone.utc)).days


def is_fbs(conn: sqlite3.Connection, team: str) -> bool:
    """Whether a code belongs to a team the FBS loader wrote.

    `teams` is filled from group 80 only, so a code that is not there belongs
    to an opponent from a lower division. That is a real and useful fact about
    a game -- not a data error -- and B3's factors may read it.
    """
    return conn.execute(
        "SELECT 1 FROM teams WHERE sport = 'cfb' AND tricode = ?", (team,)
    ).fetchone() is not None
