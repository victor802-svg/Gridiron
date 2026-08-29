"""Read-only basketball accessors for the prediction path.

Same two guarantees as `repo` and `mlb_repo`:

1. **No market data.** Nothing here reads `market_lines_raw` or
   `market_snapshots`, and the words do not appear.
2. **No future data.** Every accessor takes a date cutoff and returns only rows
   *strictly before* it. Basketball is played almost daily, so the cutoff is a
   date rather than a week ordinal — a week-level cutoff would leak the results
   of games played earlier in the same week.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

#: Rolling windows, in games. Ten is roughly three weeks of an NBA schedule:
#: long enough to be a number, short enough to still be about this team.
TEAM_WINDOW = 10
PLAYER_WINDOW = 10
#: Travel and back-to-backs are properties of the recent schedule, not the season.
SCHEDULE_WINDOW_DAYS = 14
#: A club's rotation is whoever took a real share of the minutes lately.
ROTATION_MIN_MINUTES = 12.0


def game(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT g.*, c.stadium, c.neutral_site FROM games g"
        " LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.id = ? AND g.sport = 'nba'",
        (game_id,),
    ).fetchone()


def game_date(conn: sqlite3.Connection, game_id: str) -> str | None:
    """The LEAGUE's own calendar date for this game, which is the cutoff every
    rolling window must use.

    NOT the UTC date, and the difference is not cosmetic. A game tipping at
    02:00 UTC is the previous evening where it is played, so its own row in the
    game log is dated the day before its `kickoff_utc`. Cutting a window at
    `game_date < utc_date` therefore let the game being predicted into its own
    rolling form, availability and pace — 76.8% of NBA games and 25.1% of MLB
    ones. The model was reading the result it was forecasting.

    Falls back to the UTC date only when no league date was recorded, which is
    the pre-migration case; the loaders now always write one.
    """
    row = conn.execute(
        "SELECT league_date, substr(kickoff_utc, 1, 10) AS utc_date"
        " FROM games WHERE id = ?",
        (game_id,),
    ).fetchone()
    if row is None:
        return None
    return row["league_date"] or row["utc_date"]

def games_in_week(conn: sqlite3.Connection, season: int, week: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM games WHERE sport = 'nba' AND season = ? AND week = ?"
        " ORDER BY kickoff_utc, id",
        (season, week),
    ).fetchall()


# ---------------------------------------------------------------------------
# team form
# ---------------------------------------------------------------------------

def team_recent(
    conn: sqlite3.Connection, team: str, before: str, limit: int = TEAM_WINDOW
) -> list[sqlite3.Row]:
    """The club's most recent completed games, newest first, strictly before
    `before`. Crosses the season boundary backwards, because a club in October
    has no current-season sample and last April is the honest prior."""
    return conn.execute(
        "SELECT * FROM nba_team_games WHERE team = ? AND game_date < ?"
        " ORDER BY game_date DESC LIMIT ?",
        (team, before, limit),
    ).fetchall()


def team_games_between(
    conn: sqlite3.Connection, team: str, start: str, before: str
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM nba_team_games WHERE team = ? AND game_date >= ?"
        " AND game_date < ? ORDER BY game_date DESC",
        (team, start, before),
    ).fetchall()


def possessions(row: sqlite3.Row) -> float | None:
    """The standard estimate: FGA + 0.44*FTA - OREB + TOV.

    The 0.44 is the conventional coefficient for the share of free throws that
    end a possession, and it is an ESTIMATE rather than a count — the box score
    does not record possessions. Stated here rather than buried, because every
    pace and rating figure downstream inherits it.
    """
    if row["fga"] is None or row["turnovers"] is None:
        return None
    return (
        float(row["fga"])
        + 0.44 * float(row["fta"] or 0)
        - float(row["oreb"] or 0)
        + float(row["turnovers"])
    )


def pace_and_rating(rows: list[sqlite3.Row]) -> tuple[float | None, float | None, int]:
    """Possessions per 48 minutes, and net points per 100 possessions.

    Both are returned together because both need the same possession estimate,
    and both are ABSENT rather than partial when the window is too short.
    """
    if not rows:
        return None, None, 0
    poss = 0.0
    minutes = 0.0
    diff = 0
    for r in rows:
        p = possessions(r)
        if p is None or not r["minutes"]:
            return None, None, len(rows)
        poss += p
        # Team minutes are five players' worth: 240 in regulation. Divide back
        # to game-length so pace is per 48 rather than per 240.
        minutes += float(r["minutes"]) / 5.0
        diff += (r["points_for"] or 0) - (r["points_against"] or 0)
    if poss <= 0 or minutes <= 0:
        return None, None, len(rows)
    return poss * 48.0 / minutes, diff * 100.0 / poss, len(rows)


def days_of_rest(conn: sqlite3.Connection, team: str, before: str) -> int | None:
    """Nights off between the club's last game and this one.

    DAYS OF REST, not days since the last game, and the difference is one that
    already cost a factor. A back-to-back is a game the night after a game, so
    the two dates are one day apart and "days since" reads 1. A factor written
    to detect zero days rest therefore never fired, and the fit reported it
    constant across 4,911 rows. Returning rest directly makes the factor's name,
    its rationale and its arithmetic all say the same thing.
    """
    recent = team_recent(conn, team, before, limit=1)
    if not recent:
        return None
    gap = (date.fromisoformat(before) - date.fromisoformat(recent[0]["game_date"])).days
    return max(gap - 1, 0)


def road_games_recent(conn: sqlite3.Connection, team: str, before: str) -> int | None:
    """How many of the club's last fortnight of games were away.

    A count rather than a distance. Real travel distance would need airport
    coordinates for thirty arenas, and the count captures the thing that
    actually wears a team out — consecutive nights in hotels — without a
    reference table we would have to source and cite.
    """
    start = (date.fromisoformat(before) - timedelta(days=SCHEDULE_WINDOW_DAYS)).isoformat()
    rows = team_games_between(conn, team, start, before)
    if not rows:
        return None
    return sum(1 for r in rows if not r["is_home"])


# ---------------------------------------------------------------------------
# availability
# ---------------------------------------------------------------------------

def rotation(
    conn: sqlite3.Connection, team: str, before: str, window: int = TEAM_WINDOW
) -> list[sqlite3.Row]:
    """The club's rotation: players averaging real minutes over the recent
    window, with those minutes, newest window only. Strictly before the cutoff."""
    start_rows = team_recent(conn, team, before, limit=window)
    if not start_rows:
        return []
    earliest = min(r["game_date"] for r in start_rows)
    return conn.execute(
        "SELECT player_id, player_name, AVG(minutes) AS mpg, COUNT(*) AS games"
        " FROM nba_player_games WHERE team = ? AND game_date >= ? AND game_date < ?"
        " GROUP BY player_id HAVING AVG(minutes) >= ?"
        " ORDER BY mpg DESC",
        (team, earliest, before, ROTATION_MIN_MINUTES),
    ).fetchall()


def played_in_last_game(
    conn: sqlite3.Connection, team: str, before: str
) -> set[int] | None:
    """Who appeared in the club's most recent completed game.

    This is the availability signal that exists in BOTH regimes — forward and
    backtest — because it is strictly prior information either way. See
    `nba_availability_index` for why that symmetry is the whole point.
    """
    last = team_recent(conn, team, before, limit=1)
    if not last:
        return None
    rows = conn.execute(
        "SELECT player_id FROM nba_player_games WHERE game_id = ? AND team = ?",
        (last[0]["game_id"], team),
    ).fetchall()
    return {r["player_id"] for r in rows}


def listed_out(conn: sqlite3.Connection, team: str) -> set[str]:
    """Player NAMES listed OUT on the current injury report, upper-cased.

    Names, not ids: ESPN's athlete ids and stats.nba.com's player ids are
    different numbering systems and no verifiable mapping between them is
    published. Joining on a normalised name is the honest option; inventing an
    id mapping would attach the wrong player's absence to the wrong club and
    nobody would notice.
    """
    rows = conn.execute(
        "SELECT player_name, status FROM nba_injuries WHERE team = ?", (team,)
    ).fetchall()
    return {
        r["player_name"].strip().upper()
        for r in rows
        if r["player_name"] and r["status"].strip().lower().startswith("out")
    }


def injury_report_names(conn: sqlite3.Connection, team: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM nba_injuries WHERE team = ?", (team,)
    ).fetchall()


# ---------------------------------------------------------------------------
# players
# ---------------------------------------------------------------------------

def player_recent(
    conn: sqlite3.Connection, player_id: int, before: str, limit: int = PLAYER_WINDOW
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM nba_player_games WHERE player_id = ? AND game_date < ?"
        " ORDER BY game_date DESC LIMIT ?",
        (player_id, before, limit),
    ).fetchall()


#: Window aggregates memoised for the life of a process. Every player on a
#: slate shares an opponent and a date, so the same aggregate is otherwise
#: recomputed once per player. Keyed on every argument that changes the answer,
#: and read-only, so it cannot go stale within a run.
_ALLOWANCE_CACHE: dict[tuple[str, str, str], tuple[float | None, int]] = {}


def opponent_allowance(
    conn: sqlite3.Connection, opponent: str, stat: str, before: str
) -> tuple[float | None, int]:
    """What this opponent has allowed per game in one stat, over the window.

    A LEAGUE-WIDE allowance rather than a positional one, and the difference is
    worth stating because the brief asked for positional. stats.nba.com's game
    log carries no position, and deriving one from a player's stat line would be
    inventing a classification and then measuring against it. So this is the
    honest version of the same idea: how much of this stat the opponent's
    defence gives up in total. It is a weaker instrument than positional
    allowance and it is labelled as such rather than dressed up as the thing
    that was asked for.
    """
    key = (opponent, stat, before)
    if key in _ALLOWANCE_CACHE:
        return _ALLOWANCE_CACHE[key]
    column = {
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
        "threes": "threes",
    }[stat]
    start = (date.fromisoformat(before) - timedelta(days=45)).isoformat()
    row = conn.execute(
        f"SELECT AVG(total) AS mean, COUNT(*) AS n FROM ("
        f"  SELECT game_id, SUM({column}) AS total FROM nba_player_games"
        "   WHERE opponent = ? AND game_date >= ? AND game_date < ?"
        "   GROUP BY game_id)",
        (opponent, start, before),
    ).fetchone()
    result = (
        (None, 0)
        if row is None or not row["n"] or row["mean"] is None
        else (float(row["mean"]), int(row["n"]))
    )
    _ALLOWANCE_CACHE[key] = result
    return result


def teammate_volume(
    conn: sqlite3.Connection, team: str, player_id: int, stat: str, before: str
) -> tuple[float | None, int]:
    """The club's total in this stat, minus the player's own, per recent game.

    This is the "teammates competing for the same touches" measurement: a
    scorer's ceiling depends on who else is taking shots. Absent when the club
    has no window rather than defaulted to zero, because zero would read as
    "nobody else on this team scores".
    """
    column = {
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
        "threes": "threes",
    }[stat]
    games = team_recent(conn, team, before)
    if not games:
        return None, 0
    ids = [g["game_id"] for g in games]
    placeholders = ",".join("?" for _ in ids)
    row = conn.execute(
        f"SELECT SUM({column}) AS total, COUNT(DISTINCT game_id) AS n"
        f" FROM nba_player_games WHERE team = ? AND player_id != ?"
        f" AND game_id IN ({placeholders})",
        [team, player_id, *ids],
    ).fetchone()
    if row is None or not row["n"] or row["total"] is None:
        return None, 0
    return float(row["total"]) / row["n"], int(row["n"])


def league_pace(conn: sqlite3.Connection, season: int) -> float | None:
    """League-average possessions per 48, from PRIOR seasons only, so it is
    cutoff-safe by construction."""
    rows = conn.execute(
        "SELECT * FROM nba_team_games WHERE season < ? ORDER BY season DESC LIMIT 5000",
        (season,),
    ).fetchall()
    pace, _rating, _n = pace_and_rating(rows)
    return pace
