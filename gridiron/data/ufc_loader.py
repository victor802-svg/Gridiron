"""UFC: events, bouts, results and fighters, from ESPN's core API.

WHY THE CORE API AND NOT THE SITE API. `site.api.espn.com` rate-limited this
project inside twenty requests during the U1 probe -- it returned 403 to the
very call that had worked minutes earlier. The core API served roughly 150
requests without complaint. Everything here goes through `sources.fetch`, so a
completed card is fetched exactly once in the lifetime of the database.

WHAT THIS MODULE DOES NOT DO. It does not make UFC a declared sport. `ufc` is
absent from `config.SPORTS` on purpose (see the schema comment): the loader and
the rating are built and tested first, and the bouts are mirrored into `games`
when the sport goes live. Nothing here writes a prediction or touches `games`.

Measured facts this module relies on, all from docs/UFC_FEASIBILITY.md:

  * `status.result.name` carries the method, on 94 of 94 sampled bouts.
  * `status.period` carries the round the bout ended in.
  * `format.regulation.periods` is 3 or 5 and says how long the bout was.
  * `competitors[].winner` is the moneyline outcome.
  * competitions[0] is NOT the main event -- the card is ordered from the
    bottom, so order by `matchNumber` and never by position.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

from . import sources
from ..db import utcnow
from ..sports import ufc as ufc_adapter

#: The one host this module talks to.
CORE = "https://sports.core.api.espn.com/v2/sports/mma/leagues/ufc"

#: A completed card never changes, so its bouts are fetched once and cached
#: forever. An upcoming card changes constantly -- fighters withdraw, bouts
#: are added -- so it gets a short life.
SETTLED_TTL = timedelta(days=3650)
UPCOMING_TTL = timedelta(minutes=30)


class NoUfcData(RuntimeError):
    """The source answered and carried no cards. LOUD, never a silent zero."""


def _get(conn: sqlite3.Connection, url: str, *, immutable: bool = False,
         ttl: timedelta | None = None) -> dict:
    raw = sources.fetch(conn, url, immutable=immutable, ttl=ttl)
    return json.loads(raw)


def _ref(node) -> str | None:
    """The `$ref` a core-API node points at, or None when it is inline."""
    if isinstance(node, dict):
        return node.get("$ref")
    return None


def _athlete_id(competitor: dict) -> str | None:
    """The ESPN athlete id, from the reference rather than from a name.

    IDENTITY IS NEVER A NAME MATCH HERE. Every competitor arrives with a
    numeric id, which is why the fighter-name collision problem the brief
    worried about does not arise on this path. If a future source ever forces
    a name match, two fighters sharing a normalised name are ambiguous and
    refused -- the rule the MLB crosswalk already follows.
    """
    athlete = competitor.get("athlete") or {}
    ref = _ref(athlete) or ""
    if "/athletes/" in ref:
        return ref.split("/athletes/")[1].split("?")[0].strip("/")
    ident = athlete.get("id")
    return str(ident) if ident else None


def load_season(conn: sqlite3.Connection, season: int) -> dict:
    """Every card in one year, with its bouts, results and fighters.

    Returns counts. Raises `NoUfcData` when the source answers with no cards
    at all -- a season that quietly loads zero is the failure mode that let a
    whole sport's first slate write nothing and report success.
    """
    listing = _get(conn, f"{CORE}/events?dates={season}&limit=500",
                   ttl=UPCOMING_TTL)
    items = listing.get("items") or []
    if not items:
        raise NoUfcData(
            f"the UFC source returned no cards for {season}. It answered, so "
            f"this is not an outage: either the season is wrong or the feed's "
            f"shape has changed. Nothing was written."
        )

    counts = {"events": 0, "bouts": 0, "results": 0, "fighters": 0}
    seen_fighters: set[str] = set()

    for entry in items:
        ref = _ref(entry)
        if not ref:
            continue
        card = _get(conn, ref, ttl=UPCOMING_TTL)
        event_id = str(card.get("id") or "")
        if not event_id:
            continue
        when = card.get("date")
        name = card.get("name") or "UFC"
        bouts = card.get("competitions") or []
        # WHICH KIND OF CARD, AND WHETHER IT IS ONE (E2, 2026-09-03). The tier
        # is derived from the name because the payload carries no tier field --
        # measured, see UFC_FEASIBILITY section 9.1 -- and an event whose name
        # matches none of the three declared patterns is stamped NULL rather
        # than guessed at. `is_card` is a fact about the event: a Ultimate
        # Fighter television episode carries one bout and no real card in five
        # seasons carries fewer than three.
        tier = ufc_adapter.event_tier(name)
        is_card = ufc_adapter.is_sanctioned_card(name, len(bouts), when, utcnow())
        # THE VENUE, as ESPN carries it on every competition of the card. The
        # event's local date comes from it (ruling 3 on the audit, 2026-09-05).
        address = ((bouts[0].get("venue") or {}).get("address") or {}) if bouts else {}
        conn.execute(
            "INSERT INTO ufc_events (id, name, event_utc, season, event_tier,"
            " is_card, fetched_utc, venue_country, venue_state, venue_city)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET name = excluded.name,"
            "   event_utc = excluded.event_utc, event_tier = excluded.event_tier,"
            "   is_card = excluded.is_card, fetched_utc = excluded.fetched_utc,"
            "   venue_country = excluded.venue_country,"
            "   venue_state = excluded.venue_state, venue_city = excluded.venue_city",
            (event_id, name, when, season, tier, 1 if is_card else 0, utcnow(),
             address.get("country") or None, address.get("state") or None,
             address.get("city") or None))
        counts["events"] += 1
        if not is_card:
            # NOT A CARD, SO ITS BOUTS DO NOT ENTER THE RECORD AT ALL. Skipped
            # here rather than filtered later, so a reload cannot readmit them
            # and no downstream reader has to remember the rule.
            counts.setdefault("skipped_not_a_card", 0)
            counts["skipped_not_a_card"] += 1
            continue

        for bout in bouts:
            wrote, resolved, fighters = _load_bout(
                conn, event_id, bout, seen_fighters)
            counts["bouts"] += wrote
            counts["results"] += resolved
            counts["fighters"] += fighters

    conn.commit()
    return counts


def _load_bout(conn: sqlite3.Connection, event_id: str, bout: dict,
               seen: set[str]) -> tuple[int, int, int]:
    bout_id = str(bout.get("id") or "")
    if not bout_id:
        return 0, 0, 0

    competitors = bout.get("competitors") or []
    if len(competitors) != 2:
        # A bout without exactly two sides is not a bout we can ask about.
        # Skipped rather than half-stored, and not counted as loaded.
        return 0, 0, 0

    ids = [_athlete_id(c) for c in competitors]
    if not all(ids):
        return 0, 0, 0

    status = bout.get("status")
    ref = _ref(status)
    if ref:
        status = _get(conn, ref, immutable=False, ttl=UPCOMING_TTL)
    status = status or {}
    stype = status.get("type") or {}
    state = stype.get("state") or "pre"
    settled = bool(stype.get("completed"))

    result = status.get("result") or {}
    method = result.get("name")
    end_round = status.get("period") if settled else None
    end_clock = status.get("clock") if settled else None

    winner = None
    for competitor, ident in zip(competitors, ids):
        if competitor.get("winner"):
            winner = ident
    # A DRAW OR NO CONTEST LEAVES `winner` NULL, and that is the stored truth
    # rather than a missing value: the moneyline is void for those bouts and
    # the rounds and distance markets still resolve. See the void rules in
    # docs/UFC_FEASIBILITY.md section 6.

    periods = ((bout.get("format") or {}).get("regulation") or {}).get("periods")
    weight = (bout.get("type") or {}).get("text")
    # `cardSegment` arrives as an object, not a string -- SQLite refused the
    # dict by name, which is the kind of thing a loader finds on its first
    # real run and a fixture would never have shown.
    segment = bout.get("cardSegment")
    if isinstance(segment, dict):
        segment = segment.get("description") or segment.get("name")

    conn.execute(
        "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
        " weight_class, card_segment, match_number, fighter_a, fighter_b,"
        " status, winner, method, end_round, end_clock, fetched_utc)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET"
        "   status = excluded.status, winner = excluded.winner,"
        "   method = excluded.method, end_round = excluded.end_round,"
        "   end_clock = excluded.end_clock, fetched_utc = excluded.fetched_utc",
        (bout_id, event_id, bout.get("date"), periods, weight,
         segment, bout.get("matchNumber"),
         ids[0], ids[1],
         "final" if settled else ("in" if state == "in" else "scheduled"),
         winner, method, end_round, end_clock, utcnow()))

    added = 0
    for competitor, ident in zip(competitors, ids):
        if ident in seen:
            continue
        seen.add(ident)
        if _load_fighter(conn, competitor, ident):
            added += 1
    return 1, (1 if settled else 0), added


def _load_fighter(conn: sqlite3.Connection, competitor: dict,
                  ident: str) -> bool:
    ref = _ref(competitor.get("athlete") or {})
    if not ref:
        return False
    # A FIGHTER'S PROFILE IS IMMUTABLE ENOUGH. Reach and stance do not change;
    # weight does, but not within a season in a way this build reads.
    athlete = _get(conn, ref, ttl=timedelta(days=30))
    name = athlete.get("displayName") or athlete.get("fullName")
    if not name:
        return False
    stance = (athlete.get("stance") or {})
    conn.execute(
        "INSERT INTO ufc_fighters (id, name, reach, height, weight, stance,"
        " born, fetched_utc) VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(id) DO UPDATE SET name = excluded.name,"
        "   reach = excluded.reach, height = excluded.height,"
        "   weight = excluded.weight, stance = excluded.stance,"
        "   born = excluded.born, fetched_utc = excluded.fetched_utc",
        (ident, name, athlete.get("reach"), athlete.get("height"),
         athlete.get("weight"),
         stance.get("text") if isinstance(stance, dict) else stance,
         athlete.get("dateOfBirth"), utcnow()))
    return True
