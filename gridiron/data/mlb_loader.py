"""Ingest MLB from the MLB Stats API.

Source: **statsapi.mlb.com**, MLB's own public Stats API. Free, no key, no
published rate limit. It carries MLB's copyright notice and is not offered
under an open licence; Gridiron uses it read-only for personal forecasting and
caches every response so a season is fetched once. Verified 2026-08-29: the
schedule endpoint returned 15 games for a sample date with final scores,
linescores and probable pitchers.

Three fetch shapes, in descending order of how much they cost:

  * the schedule, one request per date range — games, scores, venues, probables;
  * a pitcher's game log, one request per pitcher per season, fetched only for
    pitchers who actually appear as a probable starter and cached forever;
  * nothing else. There is no per-game boxscore fetch, because 2,430 games a
    season times six seasons is not a request budget, it is an outage.

The loader is loud on an empty season, per the nflverse lesson: a source that
quietly stops is worse than one that is plainly missing.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

from .. import config
from ..db import utcnow
from . import sources

STATSAPI = "https://statsapi.mlb.com/api/v1"

#: Regular season only. Spring training and exhibitions are a different sport
#: wearing the same uniforms.
GAME_TYPES = ("R",)


def schedule_url(start: str, end: str) -> str:
    return (
        f"{STATSAPI}/schedule?sportId=1&startDate={start}&endDate={end}"
        "&gameType=R&hydrate=probablePitcher,linescore"
    )


TEAMS_URL = f"{STATSAPI}/teams?sportId=1"


def team_abbreviations(conn: sqlite3.Connection) -> dict[int, str]:
    """MLB team id -> abbreviation.

    The schedule payload names teams but does not abbreviate them, and a card
    reading "109 @ 137" is a card nobody can check. One cached request.
    """
    payload = json.loads(sources.fetch(conn, TEAMS_URL))
    return {
        t["id"]: (t.get("abbreviation") or t.get("teamCode") or str(t["id"])).upper()
        for t in payload.get("teams", [])
    }


def gamelog_url(pitcher_id: int, season: int) -> str:
    return (
        f"{STATSAPI}/people/{pitcher_id}/stats"
        f"?stats=gameLog&group=pitching&season={season}&sportId=1"
    )


def _num(value) -> float | None:
    if value in (None, "", "-.--", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _innings(value) -> float | None:
    """MLB writes innings as 6.1 meaning six and one THIRD, not six and a tenth."""
    raw = _num(value)
    if raw is None:
        return None
    whole = int(raw)
    outs = round((raw - whole) * 10)
    return whole + outs / 3.0


def _season_bounds(season: int) -> tuple[str, str]:
    # Wide enough to catch every regular-season date without guessing at the
    # calendar, which moves every year.
    return f"{season}-03-01", f"{season}-11-15"


def load_season(conn: sqlite3.Connection, season: int, *, progress=None) -> dict[str, int]:
    """Schedule, results, probables and team game rows for one season."""
    start, end = _season_bounds(season)
    immutable = season < config.SPORT_CURRENT_SEASON["mlb"]

    # One request per month keeps any single response small enough to cache and
    # lets a part-finished season refetch only its live tail.
    counts = {"games": 0, "probables": 0, "team_games": 0}
    abbrev = team_abbreviations(conn)
    cursor = datetime.strptime(start, "%Y-%m-%d").date()
    finish = datetime.strptime(end, "%Y-%m-%d").date()
    days_seen: set[str] = set()

    while cursor <= finish:
        chunk_end = min(cursor + timedelta(days=30), finish)
        url = schedule_url(cursor.isoformat(), chunk_end.isoformat())
        if progress:
            progress(f"mlb schedule {cursor} to {chunk_end}")
        try:
            payload = json.loads(sources.fetch(conn, url, immutable=immutable))
        except sources.SourceUnavailable:
            cursor = chunk_end + timedelta(days=1)
            continue

        for day in payload.get("dates", []):
            for game in day.get("games", []):
                if game.get("gameType") not in GAME_TYPES:
                    continue
                days_seen.add(game["officialDate"])
                counts["games"] += 1
        cursor = chunk_end + timedelta(days=1)

    # Day ordinal: the slate key. A baseball slate is a day's card, so "week"
    # counts days from the season's first game rather than weeks from anything.
    day_index = {d: i + 1 for i, d in enumerate(sorted(days_seen))}

    cursor = datetime.strptime(start, "%Y-%m-%d").date()
    with conn:
        while cursor <= finish:
            chunk_end = min(cursor + timedelta(days=30), finish)
            url = schedule_url(cursor.isoformat(), chunk_end.isoformat())
            try:
                payload = json.loads(sources.fetch(conn, url, immutable=immutable))
            except sources.SourceUnavailable:
                cursor = chunk_end + timedelta(days=1)
                continue

            for day in payload.get("dates", []):
                for game in day.get("games", []):
                    if game.get("gameType") not in GAME_TYPES:
                        continue
                    _write_game(conn, game, season, day_index, counts, abbrev)
            cursor = chunk_end + timedelta(days=1)

    return counts


def _write_game(conn, game, season: int, day_index: dict, counts: dict,
                abbrev: dict[int, str]) -> None:
    game_id = f"mlb_{game['gamePk']}"
    official = game["officialDate"]
    home = game["teams"]["home"]
    away = game["teams"]["away"]
    home_abbr = abbrev.get(home["team"]["id"]) or str(home["team"]["id"])
    away_abbr = abbrev.get(away["team"]["id"]) or str(away["team"]["id"])
    final = (game.get("status", {}).get("abstractGameState") == "Final")
    home_runs = home.get("score") if final else None
    away_runs = away.get("score") if final else None
    if final and (home_runs is None or away_runs is None):
        final = False

    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc, home,"
        " away, status, home_score, away_score) VALUES (?, 'mlb', ?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET kickoff_utc=excluded.kickoff_utc,"
        " status=excluded.status, home_score=excluded.home_score,"
        " away_score=excluded.away_score, week=excluded.week,"
        " home=excluded.home, away=excluded.away",
        (
            game_id, season, day_index.get(official, 0), "REG",
            game.get("gameDate"), home_abbr, away_abbr,
            "final" if final else "scheduled", home_runs, away_runs,
        ),
    )
    conn.execute(
        "INSERT INTO game_conditions (game_id, neutral_site, stadium)"
        " VALUES (?, 0, ?) ON CONFLICT(game_id) DO UPDATE SET stadium=excluded.stadium",
        (game_id, (game.get("venue") or {}).get("name")),
    )

    for side, block in (("home", home), ("away", away)):
        pitcher = block.get("probablePitcher")
        if pitcher:
            conn.execute(
                "INSERT INTO mlb_probables (game_id, side, pitcher_id, pitcher_name,"
                " recorded_utc) VALUES (?,?,?,?,?)"
                " ON CONFLICT(game_id, side) DO UPDATE SET"
                " pitcher_id=excluded.pitcher_id, pitcher_name=excluded.pitcher_name",
                (game_id, side, pitcher.get("id"), pitcher.get("fullName"), utcnow()),
            )
            counts["probables"] += 1

    if not final:
        return

    innings = len((game.get("linescore") or {}).get("innings") or []) or 9.0
    for team, opp, is_home, rf, ra in (
        (home_abbr, away_abbr, 1, home_runs, away_runs),
        (away_abbr, home_abbr, 0, away_runs, home_runs),
    ):
        conn.execute(
            "INSERT INTO mlb_team_games (game_id, team, opponent, season, game_date,"
            " is_home, runs_for, runs_against, innings_played) VALUES (?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(game_id, team) DO UPDATE SET runs_for=excluded.runs_for,"
            " runs_against=excluded.runs_against,"
            " innings_played=excluded.innings_played, opponent=excluded.opponent",
            (game_id, team, opp, season, official, is_home, rf, ra, float(innings)),
        )
        counts["team_games"] += 1


def load_pitcher_logs(
    conn: sqlite3.Connection, season: int, *, progress=None
) -> int:
    """Game logs for every pitcher who appears as a probable starter this season.

    One request per pitcher per season, cached permanently. Only probables are
    fetched: a reliever who never starts contributes nothing to
    `mlb_starter_rolling_perf`, and fetching every pitcher would multiply the
    request count by five for data no declared factor reads.
    """
    ids = [
        r["pitcher_id"]
        for r in conn.execute(
            "SELECT DISTINCT p.pitcher_id FROM mlb_probables p"
            " JOIN games g ON g.id = p.game_id"
            " WHERE g.season = ? AND p.pitcher_id IS NOT NULL",
            (season,),
        )
    ]
    immutable = season < config.SPORT_CURRENT_SEASON["mlb"]
    written = 0

    for i, pitcher_id in enumerate(ids):
        if progress and i % 50 == 0:
            progress(f"mlb pitcher logs {season}: {i}/{len(ids)}")
        try:
            payload = json.loads(
                sources.fetch(conn, gamelog_url(pitcher_id, season), immutable=immutable)
            )
        except sources.SourceUnavailable:
            continue
        groups = payload.get("stats") or []
        splits = groups[0].get("splits", []) if groups else []
        with conn:
            for split in splits:
                stat = split.get("stat") or {}
                conn.execute(
                    "INSERT INTO mlb_pitcher_starts (pitcher_id, season, game_date,"
                    " game_pk, is_start, innings, runs, earned_runs, batters_faced)"
                    " VALUES (?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(pitcher_id, season, game_date, game_pk) DO UPDATE SET"
                    " innings=excluded.innings, runs=excluded.runs,"
                    " earned_runs=excluded.earned_runs,"
                    " batters_faced=excluded.batters_faced",
                    (
                        pitcher_id,
                        season,
                        split.get("date"),
                        (split.get("game") or {}).get("gamePk"),
                        1 if (stat.get("gamesStarted") or 0) else 0,
                        _innings(stat.get("inningsPitched")),
                        stat.get("runs"),
                        stat.get("earnedRuns"),
                        stat.get("battersFaced"),
                    ),
                )
                written += 1
    return written


def load_all(
    conn: sqlite3.Connection,
    seasons: tuple[int, ...] = config.SPORT_LOAD_SEASONS["mlb"],
    *,
    progress=None,
) -> dict:
    totals = {"games": 0, "probables": 0, "team_games": 0, "pitcher_starts": 0}
    warnings: list[str] = []

    for season in seasons:
        counts = load_season(conn, season, progress=progress)
        for key, value in counts.items():
            totals[key] += value
        if counts["games"] == 0 and season <= config.SPORT_CURRENT_SEASON["mlb"]:
            warnings.append(
                f"{season}: zero MLB games returned for a season that should have "
                f"them. Check {schedule_url(*_season_bounds(season))}."
            )
            continue

        totals["pitcher_starts"] += load_pitcher_logs(conn, season, progress=progress)

        finals = conn.execute(
            "SELECT COUNT(*) FROM games WHERE sport='mlb' AND season=? AND status='final'",
            (season,),
        ).fetchone()[0]
        starts = conn.execute(
            "SELECT COUNT(*) FROM mlb_pitcher_starts WHERE season = ?", (season,)
        ).fetchone()[0]
        if finals and not starts:
            warnings.append(
                f"{season}: {finals} completed games but zero pitcher game-log rows. "
                "Every starter factor will be absent for this season."
            )

    return {"rows": totals, "warnings": warnings}
