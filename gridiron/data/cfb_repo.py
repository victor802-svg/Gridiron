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
    """Whether this school is in the FBS, from the stored flag.

    READS THE FLAG, NOT MERE PRESENCE. Lower-division opponents now get a row
    too -- they have to, or the travel factor is absent for half of every
    September slate -- so "is it in the table" stopped meaning "is it FBS" the
    moment that changed. A team with no row at all is treated as non-FBS,
    which is what an unseen school is.
    """
    row = conn.execute(
        "SELECT is_fbs FROM teams WHERE sport = 'cfb' AND tricode = ?", (team,)
    ).fetchone()
    return bool(row and row["is_fbs"])


#: How many passes the ratings solver makes. Ten is far past convergence at
#: this size and costs milliseconds; it is fixed rather than tuned so the same
#: games always produce the same ratings.
RATING_PASSES = 10

#: Margins are clipped before they enter the ratings. A 70-0 result says the
#: winner is better; it does not say it is seventy points better than a team
#: that won by 35, and without a clip a handful of blowouts dominate every
#: rating in the system.
RATING_MARGIN_CLIP = 28.0


#: How far back the ratings look. A rolling YEAR rather than a season, and the
#: reason is the first weekend: ratings built only from the current season are
#: absent for every game until several weeks in, and the mandatory factor being
#: absent is worse than it being slightly stale. A year carries last season's
#: twelve games plus whatever this one has, and the newer games dominate simply
#: by being more numerous as the season goes on.
#:
#: It is not free: a roster turns over, a coach leaves, and September's ratings
#: are partly about a team that no longer exists. That is a known weakness of
#: the instrument, stated here rather than discovered later.
RATING_LOOKBACK_DAYS = 400


def ratings(conn: sqlite3.Connection, season: int, *, before_utc: str) -> dict:
    """Opponent-adjusted scoring margin per team, from games BEFORE a moment.

    The Simple Rating System in its plainest form: a team's rating is its
    average margin plus the average rating of the opponents it played. Solved
    by iteration, which converges quickly and is inspectable line by line --
    the same reason this project fits its own logistic regression rather than
    importing one.

    THE TIME BOUND IS THE WHOLE THING. Ratings computed from the full season
    and then used to predict a game inside that season is the rolling-window
    leak that once made an NBA model appear to beat the market by 14%. Every
    caller passes the kickoff it is predicting.

    Returns {} when nothing has been played in the window, which the caller
    treats as absent -- there is no rating for a team that has no games.

    `season` is accepted for the caller's convenience and is deliberately NOT
    used to filter: the window crosses the season boundary on purpose. See
    `RATING_LOOKBACK_DAYS`.
    """
    since = _days_before(before_utc, RATING_LOOKBACK_DAYS)
    rows = conn.execute(
        "SELECT home, away, home_score, away_score FROM games"
        " WHERE sport = 'cfb' AND status = 'final'"
        "   AND home_score IS NOT NULL AND away_score IS NOT NULL"
        "   AND kickoff_utc < ? AND kickoff_utc >= ?",
        (before_utc, since),
    ).fetchall()
    if not rows:
        return {}

    played: dict[str, list[tuple[str, float]]] = {}
    for r in rows:
        margin = float(r["home_score"]) - float(r["away_score"])
        margin = max(-RATING_MARGIN_CLIP, min(RATING_MARGIN_CLIP, margin))
        played.setdefault(r["home"], []).append((r["away"], margin))
        played.setdefault(r["away"], []).append((r["home"], -margin))

    rating = {team: 0.0 for team in played}
    for _ in range(RATING_PASSES):
        nxt = {}
        for team, games in played.items():
            nxt[team] = sum(m + rating.get(opp, 0.0) for opp, m in games) / len(games)
        # Re-centre on zero each pass. Without it the whole system drifts and
        # the numbers stop being comparable between seasons.
        mean = sum(nxt.values()) / len(nxt)
        rating = {t: v - mean for t, v in nxt.items()}
    return rating


def score_swing(conn: sqlite3.Connection, team: str, *, before_utc: str,
                window: int = 5) -> float | None:
    """Mean absolute game-to-game change in a team's COMBINED score.

    The totals market's volatility instrument. Needs at least two completed
    games to have a change at all, and returns None below that rather than a
    zero that would read as "perfectly steady".
    """
    rows = conn.execute(
        "SELECT home_score, away_score FROM games"
        " WHERE sport = 'cfb' AND status = 'final'"
        "   AND home_score IS NOT NULL AND away_score IS NOT NULL"
        "   AND kickoff_utc < ? AND (home = ? OR away = ?)"
        " ORDER BY kickoff_utc DESC LIMIT ?",
        (before_utc, team, team, window),
    ).fetchall()
    totals = [float(r["home_score"]) + float(r["away_score"]) for r in rows]
    if len(totals) < 2:
        return None
    changes = [abs(totals[i] - totals[i + 1]) for i in range(len(totals) - 1)]
    return sum(changes) / len(changes)


def _days_before(stamp: str, days: int) -> str:
    from datetime import timedelta
    try:
        when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return "0000-01-01T00:00:00Z"
    return (when - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
