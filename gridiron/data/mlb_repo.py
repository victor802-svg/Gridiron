"""Read-only MLB accessors for the prediction path.

Same two guarantees as `data.repo`:

1. **No market data.** Nothing here selects a price, and the words do not
   appear. The LAW 1 scan walks this module as part of MLB's own closure.
2. **No future data.** Every historical query takes an explicit date cutoff and
   returns only rows strictly BEFORE it. A factor cannot read the result of the
   game it is predicting because the query does not return it.

The cutoff is a date rather than a week because a baseball season is a
continuous calendar, and two games on the same day must not see each other.
"""

from __future__ import annotations

import sqlite3

#: Rolling windows, declared here so the factor rationales can cite them.
STARTER_WINDOW = 10       # starts
OFFENSE_WINDOW = 15       # games
BULLPEN_WINDOW_DAYS = 3   # days


def game(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT g.*, c.stadium FROM games g"
        " LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.id = ? AND g.sport = 'mlb'",
        (game_id,),
    ).fetchone()


def games_on_day(conn: sqlite3.Connection, season: int, day: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT g.*, c.stadium FROM games g"
        " LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.sport = 'mlb' AND g.season = ? AND g.week = ?"
        " ORDER BY g.kickoff_utc, g.id",
        (season, day),
    ).fetchall()


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

def probables(conn: sqlite3.Connection, game_id: str) -> dict[str, sqlite3.Row]:
    """Announced starters by side. An empty dict means not yet announced, which
    is a fact about the world and is recorded as one."""
    return {
        r["side"]: r
        for r in conn.execute(
            "SELECT * FROM mlb_probables WHERE game_id = ?", (game_id,)
        )
    }


def starter_recent(
    conn: sqlite3.Connection, pitcher_id: int, before_date: str, limit: int = STARTER_WINDOW
) -> list[sqlite3.Row]:
    """The pitcher's most recent STARTS before the cutoff, newest first."""
    return conn.execute(
        "SELECT * FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND is_start = 1 AND game_date < ?"
        " ORDER BY game_date DESC LIMIT ?",
        (pitcher_id, before_date, limit),
    ).fetchall()


def starter_last_appearance(
    conn: sqlite3.Connection, pitcher_id: int, before_date: str
) -> str | None:
    row = conn.execute(
        "SELECT MAX(game_date) AS d FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND game_date < ?",
        (pitcher_id, before_date),
    ).fetchone()
    return row["d"] if row and row["d"] else None


def team_recent(
    conn: sqlite3.Connection, team: str, before_date: str, limit: int = OFFENSE_WINDOW
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM mlb_team_games WHERE team = ? AND game_date < ?"
        " ORDER BY game_date DESC LIMIT ?",
        (team, before_date, limit),
    ).fetchall()


def team_games_between(
    conn: sqlite3.Connection, team: str, start_date: str, before_date: str
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM mlb_team_games"
        " WHERE team = ? AND game_date >= ? AND game_date < ? ORDER BY game_date",
        (team, start_date, before_date),
    ).fetchall()


def starter_innings_in_game(
    conn: sqlite3.Connection, game_id: str, team: str
) -> float | None:
    """Innings thrown by the announced starter in a completed game.

    Used to derive relief innings as (innings played - starter innings). Where
    the starter's own log is missing, this returns None and the bullpen factor
    is ABSENT for that game rather than assuming a full start.
    """
    side = conn.execute(
        "SELECT CASE WHEN home = ? THEN 'home' ELSE 'away' END AS side"
        " FROM games WHERE id = ?",
        (team, game_id),
    ).fetchone()
    if side is None:
        return None
    probable = conn.execute(
        "SELECT pitcher_id FROM mlb_probables WHERE game_id = ? AND side = ?",
        (game_id, side["side"]),
    ).fetchone()
    if probable is None or probable["pitcher_id"] is None:
        return None
    date = game_date(conn, game_id)
    row = conn.execute(
        "SELECT innings FROM mlb_pitcher_starts"
        " WHERE pitcher_id = ? AND game_date = ? AND is_start = 1 LIMIT 1",
        (probable["pitcher_id"], date),
    ).fetchone()
    return row["innings"] if row else None


def park_run_environment(
    conn: sqlite3.Connection, stadium: str | None, season: int
) -> tuple[float | None, int]:
    """Runs per game at this venue in PRIOR seasons, and the games behind it.

    Measured rather than taken from a published table, for two reasons: a
    measurement is reproducible from data already loaded, and restricting it to
    seasons strictly before the one being predicted makes it cutoff-safe by
    construction. Returns (runs_per_game, n_games); `n` is returned, never
    hidden, because a park with forty games behind it and one with four hundred
    are not the same number (LAW 4).
    """
    if not stadium:
        return None, 0
    row = conn.execute(
        "SELECT AVG(t.runs_for + t.runs_against) AS rpg, COUNT(*) AS n"
        " FROM mlb_team_games t"
        " JOIN games g ON g.id = t.game_id"
        " JOIN game_conditions c ON c.game_id = g.id"
        " WHERE c.stadium = ? AND g.season < ? AND t.is_home = 1",
        (stadium, season),
    ).fetchone()
    if row is None or not row["n"]:
        return None, 0
    return float(row["rpg"]), int(row["n"])


def league_run_environment(conn: sqlite3.Connection, season: int) -> float | None:
    row = conn.execute(
        "SELECT AVG(runs_for + runs_against) AS rpg, COUNT(*) AS n"
        " FROM mlb_team_games t JOIN games g ON g.id = t.game_id"
        " WHERE g.season < ? AND g.season >= ? AND t.is_home = 1",
        (season, season - 3),
    ).fetchone()
    if row is None or not row["n"]:
        return None
    return float(row["rpg"])


def counts(conn: sqlite3.Connection) -> dict:
    out = {}
    for table in ("mlb_probables", "mlb_pitcher_starts", "mlb_team_games"):
        out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    row = conn.execute(
        "SELECT COUNT(*) AS n, SUM(CASE WHEN status='final' THEN 1 ELSE 0 END) AS final,"
        " MIN(season) AS a, MAX(season) AS b FROM games WHERE sport='mlb'"
    ).fetchone()
    out["games"] = row["n"]
    out["games_final"] = row["final"] or 0
    out["seasons"] = [row["a"], row["b"]]
    return out
