"""Ingest MLB from the MLB Stats API.

Source: **statsapi.mlb.com**, MLB's own public Stats API. Free, no key, no
published rate limit. It carries MLB's copyright notice and is not offered
under an open licence; Gridiron uses it read-only for personal forecasting and
caches every response so a season is fetched once. Verified 2026-08-29: the
schedule endpoint returned 15 games for a sample date with final scores,
linescores and probable pitchers.

Three fetch shapes, in descending order of how much they cost:

  * the schedule, one request per date range — games, scores, venues, probables;
  * the schedule again with `hydrate=lineups`, one request per date range, which
    returns every game's posted batting order on that date;
  * a player's game log, one request per player per season, cached forever —
    pitchers who appear as probable starters, and batters who appear in a
    lineup;
  * nothing else. There is still no per-game boxscore fetch, because a boxscore
    is 178 KB and there are 2,430 games in a season: a third of a gigabyte of
    cache per season, for numbers the game log already carries. That is not a
    request budget, it is an outage.

Two things about lineups were MEASURED before anything was built on them, and
both are recorded on the tables in `schema.sql`: the hydrated arrays really are
in batting order (checked against 12 boxscores, 12 agree), and a scheduled game
carries no lineup at all (0 of 41 across three future dates). The second is why
no factor reads tonight's slot — only the batter's recent one.

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


def lineups_url(start: str, end: str) -> str:
    """The schedule again, hydrated with the posted batting orders.

    A separate URL from `schedule_url` on purpose. The cache is keyed by URL, so
    folding `lineups` into the existing one would invalidate every schedule
    response already stored — six seasons of them — to add a field only the prop
    markets need.
    """
    return (
        f"{STATSAPI}/schedule?sportId=1&startDate={start}&endDate={end}"
        "&gameType=R&hydrate=lineups"
    )


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


def gamelog_url(pitcher_id: int, season: int, group: str = "pitching") -> str:
    return (
        f"{STATSAPI}/people/{pitcher_id}/stats"
        f"?stats=gameLog&group={group}&season={season}&sportId=1"
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
            payload = json.loads(
                sources.fetch(
                    conn,
                    url,
                    immutable=immutable,
                    # Minutes for a chunk that reaches today, hours for one
                    # wholly in the past. Baseball finishes games all evening
                    # and this is the fetch resolution depends on.
                    ttl=sources.ttl_for_range(cursor.isoformat(), chunk_end.isoformat()),
                )
            )
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
        " away, status, home_score, away_score, league_date)"
        " VALUES (?, 'mlb', ?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET kickoff_utc=excluded.kickoff_utc,"
        " status=excluded.status, home_score=excluded.home_score,"
        " away_score=excluded.away_score, week=excluded.week,"
        " home=excluded.home, away=excluded.away,"
        " league_date=excluded.league_date",
        (
            game_id, season, day_index.get(official, 0), "REG",
            game.get("gameDate"), home_abbr, away_abbr,
            "final" if final else "scheduled", home_runs, away_runs,
            # `officialDate` is the league's own calendar date and is what every
            # game log is keyed on. It is NOT the UTC date: a night game on the
            # west coast is the next day in UTC, and cutting a rolling window on
            # the UTC date let that game into its own window.
            official,
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
                    " game_pk, is_start, innings, runs, earned_runs, batters_faced,"
                    " strike_outs, home_runs_allowed)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(pitcher_id, season, game_date, game_pk) DO UPDATE SET"
                    " innings=excluded.innings, runs=excluded.runs,"
                    " earned_runs=excluded.earned_runs,"
                    " batters_faced=excluded.batters_faced,"
                    " strike_outs=excluded.strike_outs,"
                    " home_runs_allowed=excluded.home_runs_allowed",
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
                        stat.get("strikeOuts"),
                        # A PITCHER's `homeRuns` is home runs ALLOWED; the field
                        # is named from the box score's point of view, not his.
                        # The BOXSCORE path returns None for it, which is what
                        # the feasibility probe saw; the GAME LOG carries it, and
                        # the game log is what this loader reads. Where it is
                        # still missing the column stays NULL and the factor is
                        # absent -- there is nothing to derive it from that does
                        # not attribute the bullpen's home runs to the starter.
                        stat.get("homeRuns"),
                    ),
                )
                written += 1
    return written


def load_lineups(
    conn: sqlite3.Connection, season: int, *, progress=None
) -> int:
    """The posted batting order for every completed game in a season.

    One request per date chunk, not per game. The hydrated `homePlayers` /
    `awayPlayers` arrays are in batting order -- that is the load-bearing
    assumption here and it was measured rather than believed: on 2026-08-29,
    twelve team-games were compared against the boxscore's own `battingOrder`
    field and twelve agreed, none disagreed.

    Only games our `games` table already holds get rows, so a lineup can never
    introduce a fixture the schedule loader did not.
    """
    start, end = _season_bounds(season)
    immutable = season < config.SPORT_CURRENT_SEASON["mlb"]
    written = 0
    cursor = datetime.strptime(start, "%Y-%m-%d").date()
    finish = datetime.strptime(end, "%Y-%m-%d").date()
    now = utcnow()

    while cursor <= finish:
        # Ten days rather than thirty: a hydrated day is roughly 90 KB, so a
        # month-wide response is megabytes and a part-finished season would
        # refetch all of it to pick up one evening.
        chunk_end = min(cursor + timedelta(days=10), finish)
        if progress:
            progress(f"mlb lineups {cursor} to {chunk_end}")
        try:
            payload = json.loads(
                sources.fetch(
                    conn,
                    lineups_url(cursor.isoformat(), chunk_end.isoformat()),
                    immutable=immutable,
                    ttl=sources.ttl_for_range(
                        cursor.isoformat(), chunk_end.isoformat()
                    ),
                )
            )
        except sources.SourceUnavailable:
            cursor = chunk_end + timedelta(days=1)
            continue

        with conn:
            for day in payload.get("dates", []):
                for game in day.get("games", []):
                    if game.get("gameType") not in GAME_TYPES:
                        continue
                    game_id = "mlb_" + str(game["gamePk"])
                    known = conn.execute(
                        "SELECT 1 FROM games WHERE id = ?", (game_id,)
                    ).fetchone()
                    if not known:
                        continue
                    lineups = game.get("lineups") or {}
                    for side, key in (("home", "homePlayers"),
                                      ("away", "awayPlayers")):
                        players = lineups.get(key) or []
                        for slot, player in enumerate(players[:9], start=1):
                            if not player.get("id"):
                                continue
                            conn.execute(
                                "INSERT INTO mlb_lineups (game_id, side, slot,"
                                " player_id, player_name, recorded_utc)"
                                " VALUES (?,?,?,?,?,?)"
                                " ON CONFLICT(game_id, side, slot) DO UPDATE SET"
                                " player_id=excluded.player_id,"
                                " player_name=excluded.player_name",
                                (game_id, side, slot, player["id"],
                                 player.get("fullName"), now),
                            )
                            written += 1
        cursor = chunk_end + timedelta(days=1)
    return written


def batter_cohort(conn: sqlite3.Connection, season: int) -> list[int]:
    """Which batters to fetch game logs for: everyone who started a game.

    Taken from the lineups already loaded rather than from a leaderboard, and
    the difference matters. A leaderboard is a list of players who accumulated
    counting stats, which is a selection made AFTER the season -- fetching only
    those would quietly bias the training set towards batters who stayed healthy
    and kept their jobs. Everyone written into a batting order is the set of
    players the questions could have been asked about.
    """
    return [
        int(r["player_id"])
        for r in conn.execute(
            "SELECT DISTINCT l.player_id FROM mlb_lineups l"
            " JOIN games g ON g.id = l.game_id"
            " WHERE g.season = ? ORDER BY l.player_id",
            (season,),
        )
    ]


def load_batter_logs(
    conn: sqlite3.Connection, season: int, *, progress=None
) -> int:
    """Per-game batting lines for every batter who started a game this season.

    One request per batter per season, cached forever once the season is over.
    The game log carries no opponent -- the field is present and null -- so the
    opponent and the home/away flag are read from our own `games` row via the
    game pk, which also means a log entry for a game we do not hold is skipped
    rather than inventing a fixture.

    Lineup slot is attached from `mlb_lineups` and stays NULL where the game has
    no recorded lineup. A NULL here is an absence, never a zero: slot 0 does not
    exist, and a batter who came off the bench genuinely had no slot.
    """
    ids = batter_cohort(conn, season)
    immutable = season < config.SPORT_CURRENT_SEASON["mlb"]
    written = 0

    slots = {
        (r["game_id"], r["player_id"]): r["slot"]
        for r in conn.execute(
            "SELECT l.game_id, l.player_id, l.slot FROM mlb_lineups l"
            " JOIN games g ON g.id = l.game_id WHERE g.season = ?",
            (season,),
        )
    }
    sides = {
        r["id"]: (r["home"], r["away"])
        for r in conn.execute(
            "SELECT id, home, away FROM games WHERE sport='mlb' AND season = ?",
            (season,),
        )
    }

    for i, player_id in enumerate(ids):
        if progress and i % 50 == 0:
            progress(f"mlb batter logs {season}: {i}/{len(ids)}")
        try:
            payload = json.loads(
                sources.fetch(
                    conn,
                    gamelog_url(player_id, season, group="hitting"),
                    immutable=immutable,
                )
            )
        except sources.SourceUnavailable:
            continue
        groups = payload.get("stats") or []
        splits = groups[0].get("splits", []) if groups else []
        with conn:
            for split in splits:
                if split.get("gameType") not in GAME_TYPES:
                    continue
                game_pk = (split.get("game") or {}).get("gamePk")
                if game_pk is None:
                    continue
                game_id = "mlb_" + str(game_pk)
                if game_id not in sides:
                    continue
                home, away = sides[game_id]
                is_home = 1 if split.get("isHome") else 0
                team = home if is_home else away
                opponent = away if is_home else home
                stat = split.get("stat") or {}
                slot = slots.get((game_id, player_id))
                conn.execute(
                    "INSERT INTO mlb_batter_games (player_id, season, game_date,"
                    " game_pk, player_name, team, opponent, is_home, hits,"
                    " total_bases, home_runs, doubles, triples, at_bats,"
                    " plate_appearances, strike_outs, walks, rbi, lineup_slot,"
                    " is_substitute) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(player_id, season, game_date, game_pk)"
                    " DO UPDATE SET hits=excluded.hits,"
                    " total_bases=excluded.total_bases,"
                    " home_runs=excluded.home_runs, doubles=excluded.doubles,"
                    " triples=excluded.triples, at_bats=excluded.at_bats,"
                    " plate_appearances=excluded.plate_appearances,"
                    " strike_outs=excluded.strike_outs, walks=excluded.walks,"
                    " rbi=excluded.rbi, lineup_slot=excluded.lineup_slot,"
                    " is_substitute=excluded.is_substitute,"
                    " team=excluded.team, opponent=excluded.opponent",
                    (
                        player_id, season, split.get("date"), game_pk,
                        (split.get("player") or {}).get("fullName"),
                        team, opponent, is_home,
                        stat.get("hits"), stat.get("totalBases"),
                        stat.get("homeRuns"), stat.get("doubles"),
                        stat.get("triples"), stat.get("atBats"),
                        stat.get("plateAppearances"), stat.get("strikeOuts"),
                        stat.get("baseOnBalls"), stat.get("rbi"),
                        slot,
                        # He appeared but was not in the posted order.
                        0 if slot is not None else 1,
                    ),
                )
                written += 1
    return written


def people_url(player_ids) -> str:
    joined = ",".join(str(i) for i in player_ids)
    return f"{STATSAPI}/people?personIds={joined}"


#: How many ids go in one `/people` request. Verified 2026-08-30: a 300-id URL
#: is accepted and answers in full. Kept at 200 so a handful of extra ids can
#: never push a URL over a length limit nobody has published.
PEOPLE_BATCH = 200


def load_people(conn: sqlite3.Connection, *, progress=None) -> int:
    """Handedness for every player the record holds, in batches.

    Batting side and throwing hand are the platoon-split factor's only inputs
    and they never change, so a player is fetched once and never again. Missing
    players are left missing: a NULL here makes the platoon factor ABSENT for
    that matchup, which is the correct reading of "we do not know which way he
    bats" and is not the same as a neutral matchup.
    """
    wanted = [
        int(r["pid"])
        for r in conn.execute(
            "SELECT DISTINCT player_id AS pid FROM mlb_batter_games"
            " UNION SELECT DISTINCT pitcher_id AS pid FROM mlb_pitcher_starts"
            " UNION SELECT DISTINCT pitcher_id AS pid FROM mlb_probables"
            "  WHERE pitcher_id IS NOT NULL"
        )
    ]
    have = {
        int(r["player_id"])
        for r in conn.execute(
            "SELECT player_id FROM mlb_people WHERE bat_side IS NOT NULL"
            " OR pitch_hand IS NOT NULL"
        )
    }
    todo = sorted(set(wanted) - have)
    now = utcnow()
    written = 0

    for start in range(0, len(todo), PEOPLE_BATCH):
        batch = todo[start:start + PEOPLE_BATCH]
        if progress:
            progress(f"mlb people {start}/{len(todo)}")
        try:
            payload = json.loads(
                sources.fetch(conn, people_url(batch), immutable=True)
            )
        except sources.SourceUnavailable:
            continue
        with conn:
            for person in payload.get("people", []):
                conn.execute(
                    "INSERT INTO mlb_people (player_id, full_name, bat_side,"
                    " pitch_hand, primary_position, fetched_utc)"
                    " VALUES (?,?,?,?,?,?)"
                    " ON CONFLICT(player_id) DO UPDATE SET"
                    " full_name=excluded.full_name, bat_side=excluded.bat_side,"
                    " pitch_hand=excluded.pitch_hand,"
                    " primary_position=excluded.primary_position",
                    (
                        person["id"],
                        person.get("fullName"),
                        (person.get("batSide") or {}).get("code"),
                        (person.get("pitchHand") or {}).get("code"),
                        (person.get("primaryPosition") or {}).get("abbreviation"),
                        now,
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
    totals = {"games": 0, "probables": 0, "team_games": 0, "pitcher_starts": 0,
              "lineup_slots": 0, "batter_games": 0, "people": 0}
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

        # Player-level rows are only fetched for the seasons the prop markets
        # are fitted over. They are by far the largest part of the request
        # budget, and a season nothing reads is a season not worth fetching.
        if season in config.MLB_PLAYER_SEASONS:
            slots = load_lineups(conn, season, progress=progress)
            totals["lineup_slots"] += slots
            if not slots:
                warnings.append(
                    f"{season}: zero lineup rows for a season declared in "
                    "MLB_PLAYER_SEASONS. Every batter's lineup slot will be "
                    f"absent. Check {lineups_url(*_season_bounds(season))}."
                )
            batters = load_batter_logs(conn, season, progress=progress)
            totals["batter_games"] += batters
            totals["people"] = totals.get("people", 0) + load_people(
                conn, progress=progress
            )
            if slots and not batters:
                warnings.append(
                    f"{season}: {slots} lineup slots but zero batter game rows. "
                    "All four batting prop markets are unfittable for this "
                    "season and would resolve nothing."
                )

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
