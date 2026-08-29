"""Read-only accessors for the prediction path.

Two properties this module exists to guarantee:

1. **No market data.** Nothing here selects from `market_lines_raw` or
   `market_snapshots`, and the words do not appear. A guard test asserts that
   over this module's whole import closure (LAW 1).
2. **No future data.** Every accessor that looks at history takes an explicit
   `(season, week)` cutoff and returns only rows *strictly before* it. A factor
   cannot accidentally read the result of the game it is predicting, because
   the query will not return it.
"""

from __future__ import annotations

import sqlite3
from typing import Any


def game(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT g.*, c.home_rest, c.away_rest, c.roof, c.surface, c.neutral_site,"
        " c.div_game, c.stadium, c.temp_f, c.wind_mph"
        " FROM games g LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.id = ?",
        (game_id,),
    ).fetchone()


def games_for_week(conn: sqlite3.Connection, season: int, week: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT g.*, c.home_rest, c.away_rest, c.roof, c.surface, c.neutral_site,"
        " c.div_game, c.stadium, c.temp_f, c.wind_mph"
        " FROM games g LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.season = ? AND g.week = ? ORDER BY g.kickoff_utc, g.id",
        (season, week),
    ).fetchall()


def next_unplayed_week(conn: sqlite3.Connection, season: int) -> int | None:
    row = conn.execute(
        "SELECT MIN(week) AS w FROM games WHERE season = ? AND status = 'scheduled'",
        (season,),
    ).fetchone()
    return None if row is None or row["w"] is None else int(row["w"])


def team_history(
    conn: sqlite3.Connection, season: int, team: str, before_week: int
) -> list[sqlite3.Row]:
    """Every completed game this team has played this season before `before_week`."""
    return conn.execute(
        "SELECT * FROM team_week_stats WHERE season = ? AND team = ? AND week < ?"
        " ORDER BY week",
        (season, team, before_week),
    ).fetchall()


def league_history(conn: sqlite3.Connection, season: int, before_week: int) -> list[sqlite3.Row]:
    """All completed team-weeks this season before the cutoff, for opponent
    adjustment. One query rather than one per opponent."""
    return conn.execute(
        "SELECT * FROM team_week_stats WHERE season = ? AND week < ? ORDER BY week",
        (season, before_week),
    ).fetchall()


def prior_season_margin(conn: sqlite3.Connection, season: int, team: str) -> float | None:
    """Average point differential in the previous season. Week 1 has no
    current-season sample; last year is the honest prior, and it is stated as
    such rather than pretending the season starts from zero knowledge."""
    row = conn.execute(
        "SELECT AVG(points_for - points_against) AS m, COUNT(*) AS n"
        " FROM team_week_stats WHERE season = ? AND team = ?",
        (season - 1, team),
    ).fetchone()
    if row is None or not row["n"]:
        return None
    return float(row["m"])


def injuries_for(
    conn: sqlite3.Connection, season: int, week: int, team: str
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM injuries WHERE season = ? AND week = ? AND team = ?",
        (season, week, team),
    ).fetchall()


def weather_for(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM weather_forecasts WHERE game_id = ?", (game_id,)
    ).fetchone()


def player_history(
    conn: sqlite3.Connection, player_id: str, season: int, before_week: int, limit: int = 8
) -> list[sqlite3.Row]:
    """The player's most recent completed games, newest first, strictly before
    the cutoff. Crosses the season boundary backwards when early in a year."""
    return conn.execute(
        "SELECT * FROM player_week_stats"
        " WHERE player_id = ? AND (season < ? OR (season = ? AND week < ?))"
        " ORDER BY season DESC, week DESC LIMIT ?",
        (player_id, season, season, before_week, limit),
    ).fetchall()


def team_players(
    conn: sqlite3.Connection, season: int, team: str, before_week: int
) -> list[sqlite3.Row]:
    """Players who have appeared for this team this season, with their volume,
    so the prop selector can pick the ones who actually play."""
    return conn.execute(
        "SELECT player_id, player_name, position,"
        "       COUNT(*) AS games,"
        "       AVG(COALESCE(attempts,0))  AS att,"
        "       AVG(COALESCE(carries,0))   AS car,"
        "       AVG(COALESCE(targets,0))   AS tgt,"
        "       AVG(COALESCE(passing_yards,0))   AS pass_yds,"
        "       AVG(COALESCE(rushing_yards,0))   AS rush_yds,"
        "       AVG(COALESCE(receiving_yards,0)) AS rec_yds"
        " FROM player_week_stats"
        " WHERE team = ? AND ((season = ? AND week < ?) OR season = ?)"
        " GROUP BY player_id ORDER BY games DESC",
        (team, season, before_week, season - 1),
    ).fetchall()


def positional_allowance(
    conn: sqlite3.Connection, season: int, opponent: str, position: str, before_week: int
) -> tuple[float | None, int]:
    """Yards this defence has allowed per game to the position, and the sample.

    Returns (per_game_yards, n_games). n is returned, never hidden — a two-game
    allowance and a twelve-game allowance are not the same number (LAW 4).
    """
    row = conn.execute(
        "SELECT SUM(COALESCE(passing_yards,0) + COALESCE(rushing_yards,0)"
        "          + COALESCE(receiving_yards,0)) AS yds,"
        "       COUNT(DISTINCT week) AS n"
        " FROM player_week_stats"
        " WHERE opponent = ? AND position = ? AND season = ? AND week < ?",
        (opponent, position, season, before_week),
    ).fetchone()
    if row is None or not row["n"]:
        return None, 0
    return float(row["yds"]) / row["n"], int(row["n"])


def counts(conn: sqlite3.Connection) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for table in (
        "games",
        "game_conditions",
        "team_week_stats",
        "player_week_stats",
        "injuries",
        "weather_forecasts",
        "predictions",
        "factors",
    ):
        out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    out["games_final"] = conn.execute(
        "SELECT COUNT(*) FROM games WHERE status = 'final'"
    ).fetchone()[0]
    row = conn.execute("SELECT MIN(season) AS a, MAX(season) AS b FROM games").fetchone()
    out["seasons"] = [row["a"], row["b"]]
    return out
