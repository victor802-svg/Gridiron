"""Team names, READ FROM THE FEED and never typed from memory.

The interface says "TB to win" where it should say "Tampa Bay to win", because
the record stores tricodes and nothing anywhere stores a name. The obvious fix
is a dictionary of a hundred and twenty teams written by hand, and that is
exactly the thing this project has been burned by twice:

  * two NBA aliases written from memory were reversed, leaving 7 of 53 games
    unmatched, and the reference set written to CHECK them was itself wrong
    (`ARI`/`CHW` where the feed gives `AZ`/`CWS`);
  * a blanket claim about prop lines, generalised from one sport's reading and
    written down as measured, was enforced by a test and a guard for two days.

So the names come from the feed, are stored with the URL they came from and the
time they were fetched, and a name nobody could fetch is ABSENT rather than
guessed -- the row simply keeps showing the tricode, which is honest and which
is what it does today.

ESPN's team document carries `abbreviation` and `displayName` together, which is
what makes this one request per sport rather than a research project. The
abbreviations are ESPN's, not ours, so they are resolved through the SAME
measured alias map the odds matcher uses -- one implementation, because a second
copy of that map is how the reversed aliases happened.
"""

from __future__ import annotations

import json
import sqlite3

from ..db import utcnow
from . import sources

CORE = "https://sports.core.api.espn.com/v2/sports"

#: One league path per sport. NFL is here and not in the odds module because
#: this is reference data: who a club is, not what a book thinks of them.
LEAGUE_PATH = {
    "nfl": "football/leagues/nfl",
    "mlb": "baseball/leagues/mlb",
    "nba": "basketball/leagues/nba",
}


def teams_url(sport: str, season: int) -> str:
    return f"{CORE}/{LEAGUE_PATH[sport]}/seasons/{season}/teams?limit=60"


def _alias(sport: str, abbrev: str) -> str:
    """ESPN's tricode mapped onto ours, through the measured map.

    Imported from the odds module rather than copied. That map was MEASURED --
    thirty team records fetched and diffed -- and it carries the note about the
    two entries that were once backwards. A second copy would drift from it,
    and drift is precisely how the first version went wrong.
    """
    from ..market.espn import ABBREVIATION_ALIASES

    upper = (abbrev or "").upper()
    return ABBREVIATION_ALIASES.get(sport, {}).get(upper, upper)


def load_teams(conn: sqlite3.Connection, sport: str, season: int,
               *, progress=None) -> dict:
    """Fetch and store every club's display name for one sport.

    One request for the listing plus one per club, all cached permanently: a
    club's name does not change during a season, and when it does (a relocation)
    the fetched date on the row says how old the name is.
    """
    if sport not in LEAGUE_PATH:
        return {"written": 0, "skipped": f"no league path for {sport!r}"}

    url = teams_url(sport, season)
    try:
        listing = json.loads(sources.fetch(conn, url, immutable=False))
    except (sources.SourceUnavailable, json.JSONDecodeError) as exc:
        return {"written": 0, "skipped": f"{type(exc).__name__}: {exc}"}

    now = utcnow()
    written = 0
    for i, item in enumerate(listing.get("items", [])):
        ref = item.get("$ref")
        if not ref:
            continue
        if progress and i % 10 == 0:
            progress(f"{sport} team names {i}/{listing.get('count', '?')}")
        try:
            team = json.loads(sources.fetch(conn, ref, immutable=True))
        except (sources.SourceUnavailable, json.JSONDecodeError):
            continue
        abbrev = team.get("abbreviation")
        display = team.get("displayName")
        if not abbrev or not display:
            continue
        conn.execute(
            "INSERT INTO teams (sport, tricode, espn_abbrev, display_name,"
            " short_name, location, source_url, fetched_utc)"
            " VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(sport, tricode) DO UPDATE SET"
            " display_name=excluded.display_name,"
            " short_name=excluded.short_name, location=excluded.location,"
            " espn_abbrev=excluded.espn_abbrev,"
            " source_url=excluded.source_url, fetched_utc=excluded.fetched_utc",
            (sport, _alias(sport, abbrev), abbrev.upper(), display,
             team.get("shortDisplayName") or team.get("name"),
             team.get("location"), ref, now),
        )
        written += 1
    conn.commit()
    return {"written": written, "source": url, "fetched_utc": now}


def names(conn: sqlite3.Connection, sport: str) -> dict[str, dict]:
    """tricode -> {"full": ..., "city": ...}. Empty when nothing is loaded.

    TWO FORMS, because prose and headings want different ones: "the market has
    St. Louis at 48%" reads naturally, "the market has St. Louis Cardinals at
    48%" does not, and a heading wants the whole name. Both come from the feed
    -- `displayName` and `location` -- so neither is composed here.
    """
    return {
        r["tricode"]: {"full": r["display_name"], "city": r["location"],
                       # THE CLUB'S OWN NAME (cards UI, 2026-09-04). "Padres at
                       # Reds" is what the brief writes and what a person says
                       # aloud; the full name repeats the city on both sides of
                       # a matchup heading and the city alone drops the club.
                       # From `shortName` in the feed, like the other two.
                       "club": r["short_name"]}
        for r in conn.execute(
            "SELECT tricode, display_name, location, short_name FROM teams"
            " WHERE sport = ?",
            (sport,),
        )
    }


def coverage(conn: sqlite3.Connection, sport: str) -> dict:
    """How many of the tricodes actually in the record have a name.

    Reported rather than assumed: a name table that covers 28 of 30 clubs is a
    different thing from one that covers all of them, and the two must not look
    alike.
    """
    used = {
        r["t"]
        for r in conn.execute(
            "SELECT home AS t FROM games WHERE sport = ?"
            " UNION SELECT away AS t FROM games WHERE sport = ?",
            (sport, sport),
        )
    }
    have = set(names(conn, sport))
    missing = sorted(used - have)
    return {
        "sport": sport,
        "tricodes_in_the_record": len(used),
        "named": len(used & have),
        "missing": missing,
        "n": len(used),
    }
