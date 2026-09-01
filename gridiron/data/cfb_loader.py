"""College football: schedule, finals and team game stats, from ESPN's core API.

THE SLATE IS THE UNION OF THE PER-TEAM SCHEDULES, and this is the whole reason
the loader is shaped the way it is. The league-wide weekly endpoint
(`/seasons/{y}/types/2/weeks/{n}/events`) returns about twenty events a week
against the 888 a season actually holds — under a third, with `pageCount: 1`,
so it is not pagination. A loader built on it would have filled the database
with a fraction of the season and looked complete doing it. Measured
2026-08-31; see docs/CFB_FEASIBILITY.md section 1.

So: FBS teams come from group 80's conferences, each team's own schedule is
fetched, and the events are de-duplicated by id.

WHAT COUNTS AS FBS is read from the feed too. Group 80 is named `FBS` and group
81 `FCS`, and a team document carries a `groups` ref — so an FCS opponent is
recognised rather than guessed at. Those games are loaded and resolved like any
other, because they were played and the model will be asked about them; a
factor may know the opponent is non-FBS, and that is B3's business.

SLATES ARE DAYS, NOT WEEKS. `week` is null on every 2026 event, so a week
ordinal cannot be read from the feed for the live season. A CFB week is also
three different slates — Saturday's 60 games, Sunday's 16, Friday's 8 — and
merging them would ask one question of three different cards.
"""

from __future__ import annotations

import json
import sqlite3

from .. import config
from ..db import utcnow
from . import sources

CORE = "https://sports.core.api.espn.com/v2/sports"
LEAGUE = "football/leagues/college-football"

#: Read from the feed, not assumed: group 80 is named "FBS", 81 is "FCS".
FBS_GROUP = 80


class EmptyLoad(RuntimeError):
    """A season that should have games returned none.

    Loud on empty, per checklist item 8. A source that quietly ends is worse
    than one plainly missing: nflverse's legacy player asset stopped at 2024
    and produced a database that looked fine with no 2025 box scores in it.
    """


def _get(conn, url: str, *, immutable: bool):
    try:
        return json.loads(sources.fetch(conn, url, immutable=immutable))
    except (sources.SourceUnavailable, json.JSONDecodeError):
        return None


def fbs_team_refs(conn, season: int) -> list[str]:
    """Every FBS team's document ref for one season, via group 80."""
    settled = season < config.SPORT_CURRENT_SEASON["cfb"]
    group = _get(conn, f"{CORE}/{LEAGUE}/seasons/{season}/types/2/"
                       f"groups/{FBS_GROUP}?lang=en", immutable=settled)
    if not group:
        raise EmptyLoad(
            f"CFB {season}: the FBS group document could not be fetched, so "
            "there is no team list to build a schedule from"
        )
    children = _get(conn, (group.get("children") or {}).get("$ref") or "",
                    immutable=settled) or {}
    refs = []
    for item in children.get("items") or []:
        conf = _get(conn, item["$ref"], immutable=settled) or {}
        teams_ref = (conf.get("teams") or {}).get("$ref")
        if not teams_ref:
            continue
        sep = "&" if "?" in teams_ref else "?"
        listing = _get(conn, f"{teams_ref}{sep}limit=50", immutable=settled) or {}
        refs.extend(t["$ref"] for t in (listing.get("items") or []))
    if not refs:
        raise EmptyLoad(
            f"CFB {season}: group {FBS_GROUP} returned no teams. The division "
            "structure has changed or the feed is broken; a schedule built "
            "from nothing would look like a quiet off-season"
        )
    return sorted(set(refs))


def load_teams(conn: sqlite3.Connection, season: int, *, progress=None) -> dict:
    """Team codes and names, from the feed, with collisions REFUSED.

    138 FBS abbreviations were measured distinct on 2026-08-31, but FCS
    opponents appear in the schedule too and nothing guarantees their codes do
    not collide with an FBS one. A collision would attach two schools to one
    row in `games` and the record would be wrong in a way nothing prints, so
    the pair is reported and the loader raises rather than picking a winner.
    """
    settled = season < config.SPORT_CURRENT_SEASON["cfb"]
    seen: dict[str, dict] = {}
    collisions: dict[str, list[str]] = {}
    now = utcnow()

    for i, ref in enumerate(fbs_team_refs(conn, season)):
        team = _get(conn, ref, immutable=settled)
        if not team:
            continue
        code = (team.get("abbreviation") or "").upper()
        name = team.get("displayName")
        if not code or not name:
            continue
        if code in seen and seen[code]["name"] != name:
            collisions.setdefault(code, [seen[code]["name"]]).append(name)
            continue
        venue = team.get("venue") or {}
        if isinstance(venue, dict) and venue.get("$ref"):
            venue = _get(conn, venue["$ref"], immutable=settled) or {}
        address = (venue.get("address") or {}) if isinstance(venue, dict) else {}
        seen[code] = {"name": name, "location": team.get("location"),
                      "espn_id": team.get("id"), "ref": ref,
                      # The venue carries no coordinates -- see cfb_venues --
                      # so what is stored is the city, the state and whether it
                      # is indoors. The lat/lon arrive from the geocoder.
                      "venue_name": venue.get("fullName") if isinstance(venue, dict) else None,
                      "venue_city": address.get("city"),
                      "venue_state": address.get("state"),
                      "venue_indoor": (1 if venue.get("indoor") else 0)
                                      if isinstance(venue, dict) and venue.get("indoor") is not None
                                      else None}
        if progress and i % 25 == 0:
            progress(f"cfb {season} teams {i}")

    if collisions:
        raise EmptyLoad(
            "CFB team codes collide, so two schools would share one row in the "
            f"record: {collisions}. Codes come from the feed and are not ours "
            "to reassign; this needs a ruling, not a default."
        )

    for code, info in seen.items():
        conn.execute(
            "INSERT INTO teams (sport, tricode, espn_abbrev, display_name,"
            " short_name, location, source_url, fetched_utc, is_fbs)"
            " VALUES ('cfb',?,?,?,?,?,?,?,1)"
            " ON CONFLICT(sport, tricode) DO UPDATE SET"
            " display_name=excluded.display_name,"
            " location=excluded.location, source_url=excluded.source_url,"
            " fetched_utc=excluded.fetched_utc, is_fbs=1",
            (code, code, info["name"], info["name"], info["location"],
             info["ref"], now),
        )
        conn.execute(
            "UPDATE teams SET venue_name = ?, venue_city = ?, venue_state = ?,"
            " venue_indoor = ? WHERE sport = 'cfb' AND tricode = ?",
            (info["venue_name"], info["venue_city"], info["venue_state"],
             info["venue_indoor"], code),
        )
    conn.commit()
    return {"season": season, "teams": len(seen)}


def season_event_refs(conn, season: int, *, progress=None) -> dict[str, str]:
    """Every event any FBS team plays, de-duplicated. THE SLATE.

    Never the weekly endpoint -- see this module's docstring.
    """
    settled = season < config.SPORT_CURRENT_SEASON["cfb"]
    refs: dict[str, str] = {}
    team_refs = fbs_team_refs(conn, season)
    for n, ref in enumerate(team_refs):
        tid = ref.split("/teams/")[-1].split("?")[0]
        listing = _get(
            conn,
            f"{CORE}/{LEAGUE}/seasons/{season}/types/2/teams/{tid}/events?limit=60",
            immutable=settled,
        ) or {}
        for item in listing.get("items") or []:
            eid = item["$ref"].split("/events/")[-1].split("?")[0]
            refs[eid] = item["$ref"]
        if progress and n % 20 == 0:
            progress(f"cfb {season} schedules {n}/{len(team_refs)} "
                     f"-> {len(refs)} games")
    if not refs:
        raise EmptyLoad(
            f"CFB {season}: {len(team_refs)} FBS teams returned no events at "
            "all. A season with no games is a broken feed, not a quiet year"
        )
    return refs


def load_season(conn: sqlite3.Connection, season: int, *, progress=None) -> dict:
    """Schedule and finals for one season. Loud on empty at every stage."""
    load_teams(conn, season, progress=progress)
    settled = season < config.SPORT_CURRENT_SEASON["cfb"]
    refs = season_event_refs(conn, season, progress=progress)

    written, finals, skipped = 0, 0, 0
    for n, (eid, ref) in enumerate(sorted(refs.items())):
        event = _get(conn, ref, immutable=settled)
        if not event:
            skipped += 1
            continue
        comps = event.get("competitions") or []
        if not comps:
            skipped += 1
            continue
        comp = comps[0]

        home = away = None
        scores: dict[str, float] = {}
        for c in comp.get("competitors") or []:
            side = c.get("homeAway")
            code = _team_code(conn, c, immutable=settled)
            if side == "home":
                home = code
            elif side == "away":
                away = code
            sref = (c.get("score") or {}).get("$ref")
            if sref:
                sc = _get(conn, sref, immutable=settled) or {}
                if sc.get("value") is not None and side:
                    scores[side] = float(sc["value"])
        if not home or not away:
            skipped += 1
            continue

        status = _status(conn, comp, immutable=settled)
        final = status == "final" and len(scores) == 2
        if final:
            finals += 1

        kickoff = (event.get("date") or "").replace("Z", ":00Z")
        if kickoff.count(":") == 3:            # 2026-09-05T18:30:00Z
            kickoff = kickoff[:19] + "Z"
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type,"
            " kickoff_utc, home, away, status, home_score, away_score,"
            " league_date) VALUES (?,'cfb',?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
            " home_score=excluded.home_score, away_score=excluded.away_score,"
            " kickoff_utc=excluded.kickoff_utc",
            (eid, season, _slate_ordinal(event), "REG", kickoff, home, away,
             "final" if final else "scheduled",
             scores.get("home") if final else None,
             scores.get("away") if final else None,
             (event.get("date") or "")[:10]),
        )
        written += 1
        if progress and n % 50 == 0:
            progress(f"cfb {season} games {n}/{len(refs)}")
    conn.commit()

    if written == 0:
        raise EmptyLoad(
            f"CFB {season}: {len(refs)} events were found and none could be "
            "written. Every one was missing a competitor or a competition"
        )
    return {"season": season, "games": written, "finals": finals,
            "skipped": skipped, "events": len(refs)}


def _slate_ordinal(event: dict) -> int:
    """The slate a game belongs to, as YYYYMMDD.

    NOT `week.number`, which is null on every 2026 event. A day is also the
    honest unit here: Saturday's 60 games, Sunday's 16 and Friday's 8 are three
    slates, and a week ordinal would ask one question of all three.
    """
    day = (event.get("date") or "")[:10]
    return int(day.replace("-", "")) if day else 0


def _team_code(conn, competitor: dict, *, immutable: bool) -> str | None:
    """The competitor's abbreviation, and its venue if we have never seen it.

    OPPONENTS FROM LOWER DIVISIONS ARE RECORDED HERE and nowhere else. The
    loader walks FBS schedules, so an FCS school never appears in the team
    list -- but it does appear as a competitor, and its team document is
    already being fetched to get its code. Recording it costs nothing extra.

    It matters because half of an early-September slate is FBS-vs-FCS: 30 of
    Saturday's 60 games. Without this the travel factor is absent for every one
    of them, not because the distance is unknowable but because we never wrote
    down where the visitors were coming from.

    `is_fbs` still distinguishes them -- that reads the FBS flag, not mere
    presence -- so a lower-division team gaining a row here does not quietly
    become an FBS team.
    """
    ref = (competitor.get("team") or {}).get("$ref")
    if not ref:
        return None
    team = _get(conn, ref, immutable=immutable) or {}
    code = (team.get("abbreviation") or "").upper()
    if not code:
        return None

    known = conn.execute(
        "SELECT 1 FROM teams WHERE sport = 'cfb' AND tricode = ?", (code,)
    ).fetchone()
    if known is None:
        venue = team.get("venue") or {}
        if isinstance(venue, dict) and venue.get("$ref"):
            venue = _get(conn, venue["$ref"], immutable=immutable) or {}
        address = (venue.get("address") or {}) if isinstance(venue, dict) else {}
        conn.execute(
            "INSERT INTO teams (sport, tricode, espn_abbrev, display_name,"
            " short_name, location, source_url, fetched_utc, is_fbs,"
            " venue_name, venue_city, venue_state, venue_indoor)"
            " VALUES ('cfb',?,?,?,?,?,?,?,0,?,?,?,?)"
            " ON CONFLICT(sport, tricode) DO NOTHING",
            (code, code, team.get("displayName") or code,
             team.get("displayName") or code, team.get("location"), ref,
             utcnow(),
             venue.get("fullName") if isinstance(venue, dict) else None,
             address.get("city"), address.get("state"),
             (1 if venue.get("indoor") else 0)
             if isinstance(venue, dict) and venue.get("indoor") is not None
             else None),
        )
    return code


def _status(conn, competition: dict, *, immutable: bool) -> str:
    ref = (competition.get("status") or {}).get("$ref")
    if not ref:
        return "scheduled"
    payload = _get(conn, ref, immutable=immutable) or {}
    name = ((payload.get("type") or {}).get("name") or "").upper()
    if name == "STATUS_FINAL":
        return "final"
    if name in ("STATUS_CANCELED", "STATUS_POSTPONED"):
        return name.split("_")[-1].lower()
    return "scheduled"
