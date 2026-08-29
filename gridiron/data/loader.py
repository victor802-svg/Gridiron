"""Ingest nflverse CSVs into the local database.

This module is the *only* place where a market column is read off an upstream
row, and it immediately routes those columns into the quarantined
`market_lines_raw` table (LAW 1). Note what is absent from `games`: no spread,
no total, no moneyline. The prediction path reads `games` and physically cannot
find a line there.

The loader is not on the prediction path and must never be imported by it.
Prediction reads through `gridiron.data.repo` instead.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from .. import config
from ..db import utcnow
from . import reference, sources

# Columns on the upstream games row that are market prices. Named here so the
# split is auditable in one place.
MARKET_COLUMNS = (
    "spread_line",
    "total_line",
    "home_moneyline",
    "away_moneyline",
    "away_spread_odds",
    "home_spread_odds",
    "under_odds",
    "over_odds",
)


def _num(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value in ("", "NA", "NaN", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    n = _num(value)
    return None if n is None else int(n)


def load_games(conn: sqlite3.Connection, seasons: tuple[int, ...]) -> dict[str, int]:
    """Load schedules and results. Returns row counts by table."""
    rows = sources.fetch_csv(conn, sources.GAMES_URL)
    wanted = set(seasons)
    counts = {"games": 0, "game_conditions": 0, "market_lines_raw": 0}
    now = utcnow()

    with conn:
        for r in rows:
            season = _int(r.get("season"))
            if season is None or season not in wanted:
                continue
            home_score, away_score = _int(r.get("home_score")), _int(r.get("away_score"))
            final = home_score is not None and away_score is not None
            neutral = 1 if (r.get("location") or "").strip().lower() == "neutral" else 0

            conn.execute(
                "INSERT INTO games (id, season, week, game_type, kickoff_utc, home, away,"
                " status, home_score, away_score) VALUES (?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET kickoff_utc=excluded.kickoff_utc,"
                " status=excluded.status, home_score=excluded.home_score,"
                " away_score=excluded.away_score",
                (
                    r["game_id"],
                    season,
                    _int(r.get("week")),
                    (r.get("game_type") or "REG").strip(),
                    reference.kickoff_to_utc(r.get("gameday", ""), r.get("gametime")),
                    r["home_team"],
                    r["away_team"],
                    "final" if final else "scheduled",
                    home_score,
                    away_score,
                ),
            )
            counts["games"] += 1

            conn.execute(
                "INSERT INTO game_conditions (game_id, home_rest, away_rest, roof, surface,"
                " neutral_site, div_game, stadium, temp_f, wind_mph) VALUES (?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(game_id) DO UPDATE SET home_rest=excluded.home_rest,"
                " away_rest=excluded.away_rest, roof=excluded.roof, surface=excluded.surface,"
                " neutral_site=excluded.neutral_site, div_game=excluded.div_game,"
                " stadium=excluded.stadium, temp_f=excluded.temp_f, wind_mph=excluded.wind_mph",
                (
                    r["game_id"],
                    _int(r.get("home_rest")),
                    _int(r.get("away_rest")),
                    (r.get("roof") or "").strip() or None,
                    (r.get("surface") or "").strip() or None,
                    neutral,
                    _int(r.get("div_game")),
                    (r.get("stadium") or "").strip() or None,
                    _num(r.get("temp")),
                    _num(r.get("wind")),
                ),
            )
            counts["game_conditions"] += 1

            # --- LAW 1 quarantine ------------------------------------------
            # These four numbers came off the same upstream row as everything
            # above. They go here and nowhere else.
            spread = _num(r.get("spread_line"))
            total = _num(r.get("total_line"))
            if spread is not None or total is not None:
                conn.execute(
                    "INSERT INTO market_lines_raw (game_id, fetched_utc, source, spread_line,"
                    " total_line, home_moneyline, away_moneyline) VALUES (?,?,?,?,?,?,?)"
                    " ON CONFLICT(game_id) DO UPDATE SET fetched_utc=excluded.fetched_utc,"
                    " spread_line=excluded.spread_line, total_line=excluded.total_line,"
                    " home_moneyline=excluded.home_moneyline,"
                    " away_moneyline=excluded.away_moneyline",
                    (
                        r["game_id"],
                        now,
                        "nflverse/schedules",
                        spread,
                        total,
                        _int(r.get("home_moneyline")),
                        _int(r.get("away_moneyline")),
                    ),
                )
                counts["market_lines_raw"] += 1

    return counts


def load_player_stats(conn: sqlite3.Connection, season: int) -> int:
    """Weekly box scores for one season. Completed seasons are cached forever.

    Returns the row count. A zero for a season that has completed games is a
    problem, not a quiet nothing — `load_all` turns it into a warning.
    """
    url = sources.PLAYER_STATS_URL.format(season=season)
    immutable = season < config.CURRENT_SEASON
    try:
        rows = sources.fetch_csv(conn, url, immutable=immutable)
    except sources.SourceUnavailable:
        return 0  # a season with no file yet (the upcoming one) is not an error

    n = 0
    with conn:
        for r in rows:
            if (r.get("season_type") or "REG") not in ("REG", "POST"):
                continue
            conn.execute(
                "INSERT INTO player_week_stats (season, week, player_id, player_name, position,"
                " team, opponent, attempts, completions, passing_yards, passing_tds, carries,"
                " rushing_yards, rushing_tds, targets, receptions, receiving_yards,"
                " receiving_tds) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(season, week, player_id) DO UPDATE SET"
                " passing_yards=excluded.passing_yards, rushing_yards=excluded.rushing_yards,"
                " receiving_yards=excluded.receiving_yards, attempts=excluded.attempts,"
                " carries=excluded.carries, targets=excluded.targets,"
                " receptions=excluded.receptions",
                (
                    _int(r.get("season")),
                    _int(r.get("week")),
                    r.get("player_id"),
                    r.get("player_display_name") or r.get("player_name"),
                    r.get("position"),
                    r.get("team") or r.get("recent_team"),
                    r.get("opponent_team"),
                    _num(r.get("attempts")),
                    _num(r.get("completions")),
                    _num(r.get("passing_yards")),
                    _num(r.get("passing_tds")),
                    _num(r.get("carries")),
                    _num(r.get("rushing_yards")),
                    _num(r.get("rushing_tds")),
                    _num(r.get("targets")),
                    _num(r.get("receptions")),
                    _num(r.get("receiving_yards")),
                    _num(r.get("receiving_tds")),
                ),
            )
            n += 1
    return n


def load_injuries(conn: sqlite3.Connection, season: int) -> int:
    """Participation status only. We record what the report says and stop there;
    modelling injury *severity* from a one-word status is invention."""
    url = sources.INJURIES_URL.format(season=season)
    immutable = season < config.CURRENT_SEASON
    try:
        rows = sources.fetch_csv(conn, url, immutable=immutable)
    except sources.SourceUnavailable:
        return 0

    n = 0
    with conn:
        for r in rows:
            name = r.get("full_name")
            if not name:
                continue
            conn.execute(
                "INSERT INTO injuries (season, week, team, player_id, player_name, position,"
                " report_status, practice_status) VALUES (?,?,?,?,?,?,?,?)"
                " ON CONFLICT(season, week, team, player_name) DO UPDATE SET"
                " report_status=excluded.report_status,"
                " practice_status=excluded.practice_status",
                (
                    _int(r.get("season")),
                    _int(r.get("week")),
                    r.get("team"),
                    r.get("gsis_id") or None,
                    name,
                    r.get("position"),
                    (r.get("report_status") or "").strip() or None,
                    (r.get("practice_status") or "").strip() or None,
                ),
            )
            n += 1
    return n


def rebuild_team_week_stats(conn: sqlite3.Connection, seasons: tuple[int, ...]) -> int:
    """Derive one row per team per played week: points for/against, and plays.

    `plays` is passing attempts + carries — plays from scrimmage, excluding
    sacks and special teams. It is a proxy for pace and is named as one. It is
    computed from the box scores we already store rather than pulled from a
    separate feed, because one fewer dependency is worth more than the handful
    of sacks it misses.
    """
    placeholders = ",".join("?" for _ in seasons)
    games = conn.execute(
        f"SELECT id, season, week, home, away, home_score, away_score FROM games"
        f" WHERE status = 'final' AND season IN ({placeholders})",
        seasons,
    ).fetchall()

    plays: dict[tuple[int, int, str], float] = defaultdict(float)
    for r in conn.execute(
        f"SELECT season, week, team, COALESCE(attempts,0) + COALESCE(carries,0) AS p"
        f" FROM player_week_stats WHERE season IN ({placeholders})",
        seasons,
    ):
        if r["team"]:
            plays[(r["season"], r["week"], r["team"])] += r["p"] or 0.0

    n = 0
    with conn:
        for g in games:
            for team, opp, pf, pa in (
                (g["home"], g["away"], g["home_score"], g["away_score"]),
                (g["away"], g["home"], g["away_score"], g["home_score"]),
            ):
                conn.execute(
                    "INSERT INTO team_week_stats (season, week, team, game_id, opponent,"
                    " points_for, points_against, plays) VALUES (?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(season, week, team) DO UPDATE SET"
                    " points_for=excluded.points_for, points_against=excluded.points_against,"
                    " plays=excluded.plays, game_id=excluded.game_id, opponent=excluded.opponent",
                    (
                        g["season"],
                        g["week"],
                        team,
                        g["id"],
                        opp,
                        pf,
                        pa,
                        int(plays.get((g["season"], g["week"], team), 0)) or None,
                    ),
                )
                n += 1
    return n


def seasons_expecting_data(conn: sqlite3.Connection, seasons: tuple[int, ...]) -> set[int]:
    """Seasons with at least one completed game, so we know which ones ought to
    have box scores. The upcoming season legitimately has none."""
    placeholders = ",".join("?" for _ in seasons)
    rows = conn.execute(
        f"SELECT DISTINCT season FROM games WHERE status = 'final' AND season IN ({placeholders})",
        seasons,
    ).fetchall()
    return {r["season"] for r in rows}


def load_all(
    conn: sqlite3.Connection,
    seasons: tuple[int, ...] = config.DEFAULT_LOAD_SEASONS,
    *,
    progress=None,
) -> dict:
    def say(msg: str) -> None:
        if progress:
            progress(msg)

    say(f"schedules 1999-present, keeping {min(seasons)}-{max(seasons)}")
    totals: dict[str, int] = dict(load_games(conn, seasons))
    totals["player_week_stats"] = 0
    totals["injuries"] = 0
    warnings: list[str] = []
    expected = seasons_expecting_data(conn, seasons)

    for season in seasons:
        say(f"player stats {season}")
        n_players = load_player_stats(conn, season)
        totals["player_week_stats"] += n_players
        if n_players == 0 and season in expected:
            warnings.append(
                f"{season}: zero player-week rows for a season that has completed "
                f"games. Check {sources.PLAYER_STATS_URL.format(season=season)} — "
                "pace and every prop factor will be blank for this season."
            )

        say(f"injuries {season}")
        n_injuries = load_injuries(conn, season)
        totals["injuries"] += n_injuries
        if n_injuries == 0 and season in expected and season >= 2009:
            warnings.append(
                f"{season}: zero injury rows for a season that has completed games. "
                f"Check {sources.INJURIES_URL.format(season=season)}."
            )

    say("deriving team-week stats")
    totals["team_week_stats"] = rebuild_team_week_stats(conn, seasons)

    return {"rows": totals, "warnings": warnings}
