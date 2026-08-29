"""Fetch published lines for MLB and NBA from ESPN's public API.

**This module is inside the LAW 1 quarantine.** It lives in `gridiron.market`,
which no sport's prediction closure may import, and the blind window refuses to
let this package load at all while a prediction is being formed.

Source and its limits, stated because a comparison drawn from a source you
cannot describe is not a comparison anyone can check:

  * `sports.core.api.espn.com` — undocumented, public, no key. The friendlier
    `site.api.espn.com` returns 403; the core host answers.
  * **No licence is stated anywhere.** No published rate limit. No guarantee it
    continues to exist.
  * It republishes DraftKings prices. Gridiron holds no account and calls no
    book: this is a media API, and if scoring against the market ever required
    a betting account the comparison would be dropped rather than LAW 5 bent.

Because the licence is unstated, this is treated as a source that may vanish.
Every response is cached permanently, a settled game is never refetched, and a
failure degrades the comparison visibly rather than the record at all.
"""

from __future__ import annotations

import json
import sqlite3

from ..data import sources as http
from ..db import utcnow

CORE = "https://sports.core.api.espn.com/v2/sports"

LEAGUE_PATH = {
    "mlb": "baseball/leagues/mlb",
    "nba": "basketball/leagues/nba",
}

SOURCE_NAME = {sport: f"espn/{sport}" for sport in LEAGUE_PATH}

#: The two feeds abbreviate two clubs differently. Measured, not guessed: on a
#: sample date 13 of 15 games matched and the two that did not were exactly
#: these. Listed explicitly so an unmatched game stays a COUNTED failure rather
#: than being papered over by fuzzy name matching, which would eventually
#: attach the wrong line to the wrong game and nobody would notice.
ABBREVIATION_ALIASES = {
    "mlb": {"ARI": "AZ", "CHW": "CWS"},
    "nba": {"UTAH": "UTA", "NOP": "NO", "NY": "NYK", "GS": "GSW",
            "SA": "SAS", "WSH": "WAS", "PHX": "PHO"},
}


def events_url(sport: str, yyyymmdd: str) -> str:
    return f"{CORE}/{LEAGUE_PATH[sport]}/events?dates={yyyymmdd}&limit=100"


def _get(conn: sqlite3.Connection, url: str, *, immutable: bool) -> dict | None:
    try:
        return json.loads(http.fetch(conn, url, immutable=immutable))
    except (http.SourceUnavailable, json.JSONDecodeError):
        return None


def _first_odds(conn: sqlite3.Connection, competition: dict, immutable: bool) -> dict | None:
    ref = (competition.get("odds") or {}).get("$ref")
    if not ref:
        return None
    payload = _get(conn, ref, immutable=immutable)
    items = (payload or {}).get("items") or []
    return items[0] if items else None


def fetch_day(
    conn: sqlite3.Connection, sport: str, yyyymmdd: str, *, settled: bool = True
) -> dict[str, int]:
    """Load every line ESPN publishes for one date into `market_lines_raw`.

    `settled` marks the day's responses immutable: a finished game's closing
    numbers never change, so it is fetched once in the lifetime of the database.
    """
    if sport not in LEAGUE_PATH:
        raise ValueError(f"no ESPN league path for {sport!r}")

    counts = {"events": 0, "with_odds": 0, "written": 0, "unmatched": 0}
    listing = _get(conn, events_url(sport, yyyymmdd), immutable=settled)
    if listing is None:
        return counts

    for item in listing.get("items", []):
        event = _get(conn, item["$ref"], immutable=settled)
        if event is None:
            continue
        counts["events"] += 1
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        odds = _first_odds(conn, competitions[0], settled)
        if odds is None:
            continue
        counts["with_odds"] += 1

        game_id = _match_game(conn, sport, event, yyyymmdd)
        if game_id is None:
            counts["unmatched"] += 1
            continue

        home = odds.get("homeTeamOdds") or {}
        away = odds.get("awayTeamOdds") or {}
        conn.execute(
            "INSERT INTO market_lines_raw (game_id, fetched_utc, source, spread_line,"
            " total_line, home_moneyline, away_moneyline) VALUES (?,?,?,?,?,?,?)"
            " ON CONFLICT(game_id) DO UPDATE SET fetched_utc=excluded.fetched_utc,"
            " spread_line=excluded.spread_line, total_line=excluded.total_line,"
            " home_moneyline=excluded.home_moneyline,"
            " away_moneyline=excluded.away_moneyline",
            (
                game_id,
                utcnow(),
                f"{SOURCE_NAME[sport]}/{odds.get('provider', {}).get('name', 'unknown')}",
                _home_spread(odds),
                odds.get("overUnder"),
                home.get("moneyLine"),
                away.get("moneyLine"),
            ),
        )
        counts["written"] += 1

    conn.commit()
    return counts


def _home_spread(odds: dict) -> float | None:
    """ESPN's `spread` is stated from the FAVOURITE's side; we store the home
    team's expected margin, which is the convention every other line in this
    project uses."""
    spread = odds.get("spread")
    if spread is None:
        return None
    home = odds.get("homeTeamOdds") or {}
    # `spread` is negative for the favourite. Expected home margin is +ve when
    # the home side is favoured.
    return -float(spread) if home.get("favorite") else float(spread)


def _match_game(conn: sqlite3.Connection, sport: str, event: dict, yyyymmdd: str) -> str | None:
    """Find our game row for an ESPN event.

    Matched on date plus the two clubs rather than on an id, because ESPN's ids
    are its own and share nothing with MLB's gamePk or the NBA's game id. A
    match that cannot be made returns None and is counted, never guessed.
    """
    date = f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    competitors = (event.get("competitions") or [{}])[0].get("competitors") or []
    abbrevs = {}
    for c in competitors:
        team = c.get("team") or {}
        ref = team.get("$ref")
        name = team.get("abbreviation")
        if not name and ref:
            fetched = _get(conn, ref, immutable=True) or {}
            name = fetched.get("abbreviation")
        if name:
            upper = name.upper()
            abbrevs[c.get("homeAway")] = ABBREVIATION_ALIASES.get(sport, {}).get(
                upper, upper
            )
    if "home" not in abbrevs or "away" not in abbrevs:
        return None

    row = conn.execute(
        "SELECT id FROM games WHERE sport = ? AND substr(kickoff_utc, 1, 10) IN (?, ?)"
        " AND home = ? AND away = ? LIMIT 1",
        (sport, date, _shift(date, 1), abbrevs["home"], abbrevs["away"]),
    ).fetchone()
    return row["id"] if row else None


def _shift(date: str, days: int) -> str:
    from datetime import date as _d, timedelta

    return (_d.fromisoformat(date) + timedelta(days=days)).isoformat()


def fetch_for_games(
    conn: sqlite3.Connection, sport: str, game_ids: list[str]
) -> dict[str, int]:
    """Fetch lines for the dates the given games fall on."""
    if not game_ids:
        return {"days": 0, "written": 0, "unmatched": 0}
    placeholders = ",".join("?" for _ in game_ids)
    days = [
        r["d"]
        for r in conn.execute(
            f"SELECT DISTINCT substr(kickoff_utc, 1, 10) AS d, status FROM games"
            f" WHERE id IN ({placeholders}) AND kickoff_utc IS NOT NULL",
            game_ids,
        )
    ]
    totals = {"days": 0, "written": 0, "unmatched": 0}
    for day in sorted(set(days)):
        settled = conn.execute(
            "SELECT COUNT(*) AS n FROM games WHERE sport = ?"
            " AND substr(kickoff_utc, 1, 10) = ? AND status = 'scheduled'",
            (sport, day),
        ).fetchone()["n"] == 0
        counts = fetch_day(conn, sport, day.replace("-", ""), settled=settled)
        totals["days"] += 1
        totals["written"] += counts["written"]
        totals["unmatched"] += counts["unmatched"]
    return totals
