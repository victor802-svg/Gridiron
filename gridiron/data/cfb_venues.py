"""Where each college team plays, resolved from the feed plus a geocoder.

ESPN'S CFB VENUE DOCUMENTS CARRY NO COORDINATES. They have `fullName`, an
address of city / state / zipCode / country, `grass` and `indoor`, and nothing
else — 919 venues, checked 2026-08-31. That blocks two factors at once: wind at
kickoff, and travel distance, both of which the NFL takes from nflverse's
published airports table. College football has no equivalent here, and 136
stadium coordinates typed from memory is exactly what checklist item 3 exists
to forbid.

Open-Meteo's geocoder closes the gap. It is the same provider and the same
CC BY 4.0 licence as the forecast path already in use, so no new source enters
the project.

THE STATE FILTER IS MANDATORY AND THE MEASUREMENT SAYS WHY
==========================================================
Open-Meteo orders results by population. A bare lookup for `Auburn` returns
Auburn, **New York** ahead of Auburn, **Alabama** — the wrong Auburn by about
900 miles. Measured over all 136 FBS home venues:

    resolved to a city in the right state    136 of 136
    where the FIRST US result was wrong      23 (17%)

So one in six venues would be placed in the wrong state by a name lookup, and
every wind reading and travel distance drawn from it would be wrong while
looking perfectly reasonable.

`admin1` is the full state NAME and ESPN gives the two-letter code, so a
code-to-name map is needed. Every code appearing in the feed was checked
against it (0 unknown), which makes it a round trip rather than a memory.

WHAT IS STORED, AND WHAT IS NOT
===============================
A resolved venue keeps its coordinates, the query that produced them, and the
date. **A venue that does not resolve is ABSENT** — never a state centroid,
never a nearby city. An absent coordinate means the travel and wind factors are
absent for that game, which the feature vector records permanently; a guessed
one would be a strong claim wearing a missing value's clothes.
"""

from __future__ import annotations

import json
import math
import sqlite3
import urllib.parse

from ..db import utcnow
from . import sources

GEOCODER = "https://geocoding-api.open-meteo.com/v1/search"

#: Two-letter code to the full state name the geocoder returns in `admin1`.
#: A stable public standard, and every code in the feed was checked against it.
US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

EARTH_MILES = 3958.8


def geocode(conn: sqlite3.Connection, city: str, state: str) -> tuple[float, float] | None:
    """(lat, lon) for a US city IN THE GIVEN STATE, or None.

    Returns None rather than a best guess. Twenty-three of 136 FBS venues would
    take the wrong state from a bare name lookup, so "the closest thing we
    found" is not an acceptable answer here.
    """
    want = US_STATES.get((state or "").upper())
    if not city or not want:
        return None
    query = urllib.parse.urlencode(
        {"name": city, "count": 20, "language": "en", "format": "json"})
    try:
        payload = json.loads(sources.fetch(conn, f"{GEOCODER}?{query}"))
    except (sources.SourceUnavailable, json.JSONDecodeError):
        return None
    for row in payload.get("results") or []:
        if row.get("country_code") == "US" and row.get("admin1") == want:
            return float(row["latitude"]), float(row["longitude"])
    return None


def resolve_all(conn: sqlite3.Connection, *, progress=None) -> dict:
    """Coordinates for every CFB venue we can place. Reports what it could not.

    Idempotent and cheap after the first run: every lookup goes through the
    HTTP cache, and a venue already carrying coordinates is skipped.
    """
    rows = conn.execute(
        "SELECT tricode, venue_city, venue_state FROM teams"
        " WHERE sport = 'cfb' AND venue_city IS NOT NULL"
        "   AND (venue_lat IS NULL OR venue_lon IS NULL)"
    ).fetchall()

    resolved, unresolved = 0, []
    now = utcnow()
    for n, row in enumerate(rows):
        coords = geocode(conn, row["venue_city"], row["venue_state"])
        if coords is None:
            unresolved.append(f"{row['tricode']} ({row['venue_city']}, "
                              f"{row['venue_state']})")
            continue
        conn.execute(
            "UPDATE teams SET venue_lat = ?, venue_lon = ?,"
            " venue_geocoded_utc = ? WHERE sport = 'cfb' AND tricode = ?",
            (coords[0], coords[1], now, row["tricode"]),
        )
        resolved += 1
        if progress and n % 20 == 0:
            progress(f"cfb venues {n}/{len(rows)}")
    conn.commit()
    return {"considered": len(rows), "resolved": resolved,
            "unresolved": unresolved}


def site(conn: sqlite3.Connection, team: str) -> tuple[float, float] | None:
    """A team's home coordinates, or None when it has none stored."""
    row = conn.execute(
        "SELECT venue_lat, venue_lon FROM teams WHERE sport = 'cfb'"
        "   AND tricode = ? AND venue_lat IS NOT NULL",
        (team,),
    ).fetchone()
    return (row["venue_lat"], row["venue_lon"]) if row else None


def miles_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance. The same haversine the NFL travel factor uses."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * EARTH_MILES * math.asin(math.sqrt(h))


def indoor(conn: sqlite3.Connection, team: str) -> bool | None:
    """Whether this team's home venue is indoors, or None if unknown.

    Four of 136 FBS venues are indoor. Wind is not asked about for those, and
    "unknown" is kept apart from "outdoors" so a missing flag never quietly
    becomes a weather reading.
    """
    row = conn.execute(
        "SELECT venue_indoor FROM teams WHERE sport = 'cfb' AND tricode = ?",
        (team,),
    ).fetchone()
    if row is None or row["venue_indoor"] is None:
        return None
    return bool(row["venue_indoor"])
