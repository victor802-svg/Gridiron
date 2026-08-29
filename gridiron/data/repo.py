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


def games_for_week(
    conn: sqlite3.Connection, season: int, week: int, sport: str = "nfl"
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT g.*, c.home_rest, c.away_rest, c.roof, c.surface, c.neutral_site,"
        " c.div_game, c.stadium, c.temp_f, c.wind_mph"
        " FROM games g LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.sport = ? AND g.season = ? AND g.week = ?"
        " ORDER BY g.kickoff_utc, g.id",
        (sport, season, week),
    ).fetchall()


def next_unplayed_week(
    conn: sqlite3.Connection, season: int, sport: str = "nfl"
) -> int | None:
    row = conn.execute(
        "SELECT MIN(week) AS w FROM games"
        " WHERE sport = ? AND season = ? AND status = 'scheduled'",
        (sport, season),
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
    """Players on this club, with their volume, so the selector can pick the ones
    who actually play.

    `games_this_season` is returned separately from `games` because prior-season
    rows are included for early-season coverage, and a player who has since been
    traded away would otherwise still look like a member of his old team. That
    is not hypothetical: it put the same quarterback on two different teams'
    slates in the same week.
    """
    return conn.execute(
        "SELECT player_id, player_name, position,"
        "       COUNT(*) AS games,"
        "       SUM(CASE WHEN season = ? THEN 1 ELSE 0 END) AS games_this_season,"
        "       MAX(CASE WHEN season = ? THEN week END) AS last_week_played,"
        "       AVG(COALESCE(attempts,0))  AS att,"
        "       AVG(COALESCE(carries,0))   AS car,"
        "       AVG(COALESCE(targets,0))   AS tgt,"
        "       AVG(COALESCE(passing_yards,0))   AS pass_yds,"
        "       AVG(COALESCE(rushing_yards,0))   AS rush_yds,"
        "       AVG(COALESCE(receiving_yards,0)) AS rec_yds,"
        "       AVG(COALESCE(receptions,0))      AS rec,"
        "       AVG(COALESCE(passing_tds,0))     AS pass_tds"
        " FROM player_week_stats"
        " WHERE team = ? AND ((season = ? AND week < ?) OR season = ?)"
        " GROUP BY player_id ORDER BY games DESC",
        (season, season, team, season, before_week, season - 1),
    ).fetchall()


def team_volume(
    conn: sqlite3.Connection, season: int, team: str, before_week: int, column: str
) -> float | None:
    """The club's average per-game total of a volume stat, before the cutoff.

    Used as the denominator for a player's share of his own offence, which is
    what makes 8 targets on a 40-target team different from 8 on a 20-target one.
    """
    if column not in ("attempts", "carries", "targets"):
        raise ValueError(f"not a volume column: {column!r}")
    row = conn.execute(
        f"SELECT SUM(COALESCE({column},0)) AS total, COUNT(DISTINCT week) AS n"
        " FROM player_week_stats WHERE team = ? AND season = ? AND week < ?",
        (team, season, before_week),
    ).fetchone()
    if row is None or not row["n"] or not row["total"]:
        return None
    return float(row["total"]) / row["n"]


def snap_share(
    conn: sqlite3.Connection, season: int, team: str, player_name: str, before_week: int,
    window: int = 4,
) -> tuple[float | None, int]:
    """Recent offensive snap share, and how many games it was measured over.

    The upstream source keys on player NAME, so about 5% of skill players do not
    match. Those return (None, 0) and the factor is absent for that game rather
    than assumed.
    """
    rows = conn.execute(
        "SELECT offense_pct FROM snap_counts"
        " WHERE season = ? AND team = ? AND player_name = ? AND week < ?"
        " AND offense_pct IS NOT NULL ORDER BY week DESC LIMIT ?",
        (season, team, player_name, before_week, window),
    ).fetchall()
    if not rows:
        return None, 0
    values = [r["offense_pct"] for r in rows]
    return sum(values) / len(values), len(values)


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
