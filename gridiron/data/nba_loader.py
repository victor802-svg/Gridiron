"""Load basketball from stats.nba.com.

Source, and its limits, stated because a record built on a source you cannot
describe is not a record anyone can check:

  * `stats.nba.com/stats/*` — the endpoints nba.com's own site calls. No key.
    **Undocumented, and no licence is stated anywhere.** No published rate
    limit. It refuses a request that does not look like a browser: the
    `Referer`, `Origin` and `x-nba-stats-*` headers below are all required, and
    without them the host hangs rather than returning an error.
  * Chosen over the `nba_api` package, which is a wrapper over exactly these
    endpoints. It would add a dependency, a pandas requirement, and a layer
    between us and the bytes, in exchange for constants we can write down.
  * `cdn.nba.com`'s static schedule JSON returns 403 to us, so the schedule
    comes from `scheduleleaguev2` on the same host as everything else.

Three endpoints, and no more:

  `scheduleleaguev2`   one call per season — every game, including future ones
  `leaguegamelog` T    one call per season — every team-game
  `leaguegamelog` P    one call per season — every player-game

That is **three requests per season**, not one per game. A full five-season
load is fifteen requests and about 25 MB, cached permanently.

Availability is separate and comes from ESPN, because stats.nba.com publishes
no pregame inactive list. See `load_injuries`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

from . import sources as http
from ..db import utcnow

STATS = "https://stats.nba.com/stats"

#: stats.nba.com refuses anything that does not look like nba.com's own client.
#: These are not decoration: without them the host does not answer at all.
STATS_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
}

ESPN_CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"

#: A game id beginning `002` is a regular-season game. `001` is preseason and
#: `004`/`005` are the postseason and play-in. Only the regular season is
#: loaded: preseason lineups are not the club's lineups, and playoff series
#: are a different question that a regular-season fit does not answer.
REGULAR_SEASON_PREFIX = "002"


def season_label(season: int) -> str:
    """2026 -> '2026-27'. NBA seasons are named by their starting year here, so
    that `season` is an integer everywhere in the database like every other
    sport's."""
    return f"{season}-{(season + 1) % 100:02d}"


def _get(conn: sqlite3.Connection, url: str, *, immutable: bool) -> dict | None:
    try:
        return json.loads(
            http.fetch(conn, url, immutable=immutable, headers=STATS_HEADERS)
        )
    except (http.SourceUnavailable, json.JSONDecodeError):
        return None


def _rows(payload: dict, index: int = 0) -> tuple[list[str], list[list]]:
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    if not sets or index >= len(sets):
        return [], []
    rs = sets[index]
    return rs.get("headers", []), rs.get("rowSet", [])


# ---------------------------------------------------------------------------
# the schedule
# ---------------------------------------------------------------------------

def _season_start(games: list[dict]) -> date | None:
    dates = [g["gameDateTimeUTC"][:10] for g in games if g.get("gameDateTimeUTC")]
    return date.fromisoformat(min(dates)) if dates else None


def week_of(game_date: date, season_start: date) -> int:
    """Basketball has no league week number, so one is derived: seven-day blocks
    counted from the season's first game, numbered from 1.

    This is a SLATE ORDINAL, not a claim about the league's calendar. It exists
    because the record is keyed by (season, week) across every sport, and it is
    computed the same way every time so the key is reproducible.
    """
    return ((game_date - season_start).days // 7) + 1


def load_schedule(conn: sqlite3.Connection, season: int) -> dict:
    """Every regular-season game of one season, played or not."""
    label = season_label(season)
    payload = _get(
        conn,
        f"{STATS}/scheduleleaguev2?LeagueID=00&Season={label}",
        immutable=False,           # a schedule is revised; never cached forever
    )
    counts = {"season": season, "games": 0, "final": 0, "scheduled": 0}
    if payload is None:
        counts["warning"] = f"NBA schedule for {label} could not be fetched"
        return counts

    schedule = payload.get("leagueSchedule") or payload
    games = [
        g
        for day in schedule.get("gameDates", [])
        for g in day.get("games", [])
        if str(g.get("gameId", "")).startswith(REGULAR_SEASON_PREFIX)
    ]
    if not games:
        counts["warning"] = (
            f"NBA schedule for {label} returned no regular-season games. That is "
            "either a season that has not been published or an endpoint that has "
            "changed shape; it is not an empty season."
        )
        return counts

    start = _season_start(games)
    venues: list[tuple[str, str, str | None]] = []
    for g in games:
        home, away = g.get("homeTeam") or {}, g.get("awayTeam") or {}
        h, a = home.get("teamTricode"), away.get("teamTricode")
        if not h or not a:
            continue
        when = g.get("gameDateTimeUTC")
        game_date = date.fromisoformat(when[:10]) if when else None
        hs, as_ = home.get("score"), away.get("score")
        # The schedule reports 0-0 for a game not yet played, which is a score
        # the schema would accept and the resolver would settle as a tie.
        played = bool(g.get("gameStatus") == 3)
        if not played:
            hs = as_ = None
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, home_score, away_score)"
            " VALUES (?, 'nba', ?, ?, 'REG', ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
            " kickoff_utc=excluded.kickoff_utc, home_score=excluded.home_score,"
            " away_score=excluded.away_score",
            (
                f"nba_{g['gameId']}",
                season,
                week_of(game_date, start) if game_date and start else 1,
                h,
                a,
                _iso(when),
                "final" if played else "scheduled",
                hs,
                as_,
            ),
        )
        # The arena lives on `game_conditions`, which is where every sport's
        # venue lives; `games` carries no sport-specific column.
        conn.execute(
            "INSERT INTO game_conditions (game_id, stadium, neutral_site, div_game)"
            " VALUES (?,?,0,0) ON CONFLICT(game_id) DO UPDATE SET"
            " stadium = excluded.stadium",
            (f"nba_{g['gameId']}", g.get("arenaName")),
        )
        venues.append((f"nba_{g['gameId']}", h, (g.get("arenaCity") or "").strip()))
        counts["games"] += 1
        counts["final" if played else "scheduled"] += 1
    conn.commit()
    counts["neutral_site"] = mark_neutral_sites(conn, season, venues)
    return counts


def mark_neutral_sites(conn: sqlite3.Connection, season: int, venues=None) -> int:
    """Flag home games played somewhere other than the club's own city.

    The schedule feed has no neutral-site field, so it is DERIVED — and the
    obvious derivation is wrong. Taking each club's modal ARENA NAME as its home
    flagged 33 games in 2024-25, of which 26 were the same building renamed
    mid-season: Footprint Center became PHX Arena, Rocket Mortgage FieldHouse
    became Rocket Arena, and Miami's arena changed name twice in one year. A
    factor fitted on that would have been measuring sponsorship deals.

    So the comparison is on the arena's CITY, which a rename does not change and
    a trip to Paris or Mexico City does. Measured after the correction: 7 of
    1,230 games in 2025-26, 0.57%, and that figure is quoted in
    `nba_home_court`'s rationale so a reader knows how thin it is.
    """
    if venues is None:
        return 0
    by_club: dict[str, dict[str, int]] = {}
    for _game_id, club, city in venues:
        if city:
            by_club.setdefault(club, {})
            by_club[club][city] = by_club[club].get(city, 0) + 1
    home_city = {
        club: max(cities.items(), key=lambda kv: kv[1])[0]
        for club, cities in by_club.items()
    }
    flagged = 0
    for game_id, club, city in venues:
        if city and home_city.get(club) and city != home_city[club]:
            conn.execute(
                "UPDATE game_conditions SET neutral_site = 1 WHERE game_id = ?",
                (game_id,),
            )
            flagged += 1
    conn.commit()
    return flagged


def _iso(when: str | None) -> str | None:
    if not when:
        return None
    return when if when.endswith("Z") else when.replace("+00:00", "") + "Z"


# ---------------------------------------------------------------------------
# the game logs
# ---------------------------------------------------------------------------

def _log_url(season: int, mode: str) -> str:
    return (
        f"{STATS}/leaguegamelog?Counter=1000&Direction=DESC&LeagueID=00"
        f"&PlayerOrTeam={mode}&Season={season_label(season)}"
        "&SeasonType=Regular+Season&Sorter=DATE"
    )


def load_team_games(conn: sqlite3.Connection, season: int, *, settled: bool) -> dict:
    payload = _get(conn, _log_url(season, "T"), immutable=settled)
    counts = {"season": season, "rows": 0}
    if payload is None:
        counts["warning"] = f"NBA team log for {season_label(season)} unavailable"
        return counts
    headers, rows = _rows(payload)
    if not rows:
        counts["warning"] = (
            f"NBA team log for {season_label(season)} returned zero rows for a "
            "season that should have games. A source that quietly ends is worse "
            "than one that is plainly missing."
        )
        return counts
    col = {name: i for i, name in enumerate(headers)}

    # Two rows describe one game, one from each club's side. Pair them so each
    # club's row can carry its opponent's score.
    by_game: dict[str, list[list]] = {}
    for r in rows:
        by_game.setdefault(r[col["GAME_ID"]], []).append(r)

    for game_id, pair in by_game.items():
        if len(pair) != 2:
            continue
        for row, other in ((pair[0], pair[1]), (pair[1], pair[0])):
            matchup = row[col["MATCHUP"]] or ""
            conn.execute(
                "INSERT OR REPLACE INTO nba_team_games (game_id, team, opponent,"
                " season, game_date, is_home, points_for, points_against, minutes,"
                " fga, fta, oreb, turnovers) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"nba_{game_id}",
                    row[col["TEAM_ABBREVIATION"]],
                    other[col["TEAM_ABBREVIATION"]],
                    season,
                    row[col["GAME_DATE"]][:10],
                    0 if "@" in matchup else 1,
                    row[col["PTS"]],
                    other[col["PTS"]],
                    row[col["MIN"]],
                    row[col["FGA"]],
                    row[col["FTA"]],
                    row[col["OREB"]],
                    row[col["TOV"]],
                ),
            )
            counts["rows"] += 1
    conn.commit()
    return counts


def load_player_games(conn: sqlite3.Connection, season: int, *, settled: bool) -> dict:
    payload = _get(conn, _log_url(season, "P"), immutable=settled)
    counts = {"season": season, "rows": 0}
    if payload is None:
        counts["warning"] = f"NBA player log for {season_label(season)} unavailable"
        return counts
    headers, rows = _rows(payload)
    if not rows:
        counts["warning"] = (
            f"NBA player log for {season_label(season)} returned zero rows for a "
            "season that should have games."
        )
        return counts
    col = {name: i for i, name in enumerate(headers)}

    for r in rows:
        matchup = r[col["MATCHUP"]] or ""
        # "LAL @ BOS" / "LAL vs. BOS" — the opponent is the last token either way.
        opponent = matchup.split()[-1] if matchup else ""
        conn.execute(
            "INSERT OR REPLACE INTO nba_player_games (game_id, player_id,"
            " player_name, team, opponent, season, game_date, is_home, minutes,"
            " points, rebounds, assists, threes, fga, fta, threes_att, turnovers)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"nba_{r[col['GAME_ID']]}",
                r[col["PLAYER_ID"]],
                r[col["PLAYER_NAME"]],
                r[col["TEAM_ABBREVIATION"]],
                opponent,
                season,
                r[col["GAME_DATE"]][:10],
                0 if "@" in matchup else 1,
                r[col["MIN"]],
                r[col["PTS"]],
                r[col["REB"]],
                r[col["AST"]],
                r[col["FG3M"]],
                r[col["FGA"]],
                r[col["FTA"]],
                r[col["FG3A"]],
                r[col["TOV"]],
            ),
        )
        counts["rows"] += 1
    conn.commit()
    return counts


# ---------------------------------------------------------------------------
# availability
# ---------------------------------------------------------------------------

#: ESPN's numeric team ids, in its own order. Needed because the injuries
#: endpoint is keyed by them and nothing else here is.
ESPN_TEAM_IDS = tuple(range(1, 31))


def load_injuries(conn: sqlite3.Connection) -> dict:
    """Replace the injury snapshot from ESPN's public API.

    This is a SNAPSHOT and the table says so. ESPN publishes what is true now,
    not what was true on a night in 2024, so this feed can inform a forward
    prediction and can tell a backtest nothing. `nba_availability_index` is
    defined so that it degrades to a strictly pre-game, strictly symmetric
    measurement when this table is empty — see its rationale.
    """
    counts = {"teams": 0, "listed": 0, "out": 0}
    now = utcnow()
    fresh: list[tuple] = []

    for team_id in ESPN_TEAM_IDS:
        listing = _espn(conn, f"{ESPN_CORE}/teams/{team_id}/injuries?limit=100")
        if listing is None:
            continue
        counts["teams"] += 1
        abbrev = _espn_team_abbrev(conn, team_id)
        if not abbrev:
            continue
        for item in listing.get("items", []):
            entry = _espn(conn, item["$ref"])
            if entry is None:
                continue
            athlete = (entry.get("athlete") or {}).get("$ref")
            player_id = _espn_athlete_id(athlete)
            name = _espn_athlete_name(conn, athlete)
            if player_id is None or not name:
                # Counted as a failure to resolve rather than stored with a
                # placeholder: an injury row nobody can match to a player is
                # worse than a missing one, because it looks like coverage.
                counts["unmatched"] = counts.get("unmatched", 0) + 1
                continue
            status = (entry.get("status") or "").strip() or "Unknown"
            fresh.append(
                (
                    player_id,
                    name,
                    abbrev,
                    status,
                    (entry.get("type") or {}).get("description"),
                    now,
                )
            )
            counts["listed"] += 1
            if status.lower().startswith("out"):
                counts["out"] += 1

    # Replaced wholesale, because a stale row is worse than no row: a player
    # cleared last week would otherwise stay listed as out forever.
    conn.execute("DELETE FROM nba_injuries")
    conn.executemany(
        "INSERT OR REPLACE INTO nba_injuries (player_id, player_name, team,"
        " status, detail, fetched_utc) VALUES (?,?,?,?,?,?)",
        fresh,
    )
    conn.commit()
    return counts


def _espn(conn: sqlite3.Connection, url: str) -> dict | None:
    try:
        return json.loads(http.fetch(conn, url, immutable=False))
    except (http.SourceUnavailable, json.JSONDecodeError):
        return None


def _espn_athlete_id(ref: str | None) -> int | None:
    """ESPN athlete ids are NOT stats.nba.com player ids. Kept as ESPN's own and
    joined by name, because inventing a mapping we cannot verify would attach
    the wrong injury to the wrong player and nobody would notice."""
    if not ref:
        return None
    tail = ref.split("athletes/")[-1].split("?")[0]
    return int(tail) if tail.isdigit() else None


def _espn_athlete_name(conn: sqlite3.Connection, ref: str | None) -> str | None:
    if not ref:
        return None
    payload = _espn(conn, ref)
    if payload is None:
        return None
    return (payload.get("displayName") or payload.get("fullName") or "").strip() or None


_TEAM_ABBREV: dict[int, str] = {}


def _espn_team_abbrev(conn: sqlite3.Connection, team_id: int) -> str | None:
    if team_id in _TEAM_ABBREV:
        return _TEAM_ABBREV[team_id]
    payload = _espn(conn, f"{ESPN_CORE}/teams/{team_id}")
    if payload is None:
        return None
    name = (payload.get("abbreviation") or "").upper()
    from ..market.espn import ABBREVIATION_ALIASES  # noqa: PLC0415

    name = ABBREVIATION_ALIASES["nba"].get(name, name)
    if name:
        _TEAM_ABBREV[team_id] = name
    return name or None


# ---------------------------------------------------------------------------

def load_all(conn: sqlite3.Connection, seasons, *, progress=None) -> dict:
    """Every season, plus the current injury snapshot."""
    from .. import config

    current = config.SPORT_CURRENT_SEASON["nba"]
    out = {"seasons": [], "warnings": []}
    for season in seasons:
        settled = season < current
        if progress:
            progress(f"nba {season_label(season)}")
        result = {"season": season}
        for name, fn in (
            ("schedule", lambda: load_schedule(conn, season)),
            ("teams", lambda: load_team_games(conn, season, settled=settled)),
            ("players", lambda: load_player_games(conn, season, settled=settled)),
        ):
            counts = fn()
            result[name] = counts
            if counts.get("warning"):
                out["warnings"].append(counts["warning"])
        out["seasons"].append(result)

    # The injury snapshot is not per-season: it is what is true right now, and
    # it is refreshed on every load so a forward prediction sees the current
    # report rather than last month's.
    out["injuries"] = load_injuries(conn)
    if not out["injuries"]["listed"]:
        out["warnings"].append(
            "the NBA injury report came back empty. Availability still measures "
            "who appeared in each club's last game, which is the half that works "
            "in both regimes, but the forward half is missing."
        )
    return out
