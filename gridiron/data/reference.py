"""Static reference data: where each club plays, and how to read a kickoff time.

The coordinates are the club's home-market airport, which is what nflverse
publishes (`nfldata/data/airports.csv`, CC BY 4.0 attribution to nflverse). It
is the city, not the stadium car park — good to a few miles, which is far below
the resolution at which travel distance could plausibly matter. Embedded rather
than fetched because it is 32 rows that change roughly never, and a factor
should not fail because a CSV moved.

`time_zone` is the club's offset relative to US Eastern, as nflverse publishes
it: 0 = Eastern, -1 = Central, -2 = Mountain, -3 = Pacific.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

#: team -> (airport, latitude, longitude, hours_from_eastern)
TEAM_SITES: dict[str, tuple[str, float, float, int]] = {
    "ARI": ("PHX", 33.434, -112.008, -2),
    "ATL": ("ATL", 33.640, -84.427, 0),
    "BAL": ("BWI", 39.175, -76.668, 0),
    "BUF": ("BUF", 42.940, -78.732, 0),
    "CAR": ("CLT", 35.214, -80.943, 0),
    "CHI": ("ORD", 41.979, -87.904, -1),
    "CIN": ("CVG", 39.046, -84.662, 0),
    "CLE": ("CLE", 41.412, -81.850, 0),
    "DAL": ("DFW", 32.896, -97.037, -1),
    "DEN": ("DEN", 39.858, -104.667, -2),
    "DET": ("DTW", 42.212, -83.353, 0),
    "GB": ("GRB", 44.485, -88.129, -1),
    "HOU": ("IAH", 29.980, -95.340, -1),
    "IND": ("IND", 39.717, -86.294, 0),
    "JAX": ("JAX", 30.494, -81.688, 0),
    "KC": ("MCI", 39.297, -94.714, -1),
    "LA": ("LAX", 33.942, -118.408, -3),
    "LAC": ("LAX", 33.942, -118.408, -3),
    "LV": ("LAS", 36.080, -115.152, -3),
    "MIA": ("MIA", 25.793, -80.291, 0),
    "MIN": ("MSP", 44.880, -93.217, -1),
    "NE": ("PVD", 41.724, -71.428, 0),
    "NO": ("MSY", 29.993, -90.258, -1),
    "NYG": ("EWR", 40.692, -74.169, 0),
    "NYJ": ("EWR", 40.692, -74.169, 0),
    "PHI": ("PHL", 39.872, -75.241, 0),
    "PIT": ("PIT", 40.491, -80.233, 0),
    "SEA": ("SEA", 47.449, -122.309, -3),
    "SF": ("SFO", 37.619, -122.375, -3),
    "TB": ("TPA", 27.975, -82.533, 0),
    "TEN": ("BNA", 36.124, -86.678, -1),
    "WAS": ("DCA", 38.852, -77.037, 0),
    # Relocated/renamed franchises that appear in older seasons.
    "OAK": ("OAK", 37.721, -122.221, -3),
    "SD": ("SAN", 32.733, -117.190, -3),
    "STL": ("STL", 38.748, -90.370, -1),
}

#: Neutral-site venues that recur (international series, Super Bowls elsewhere).
#: Only needed so travel distance is not silently computed to the wrong city.
NEUTRAL_VENUES: dict[str, tuple[float, float, int]] = {
    "Tottenham Hotspur Stadium": (51.604, -0.066, 5),
    "Wembley Stadium": (51.556, -0.280, 5),
    "Allianz Arena": (48.219, 11.625, 6),
    "Deutsche Bank Park": (50.069, 8.646, 6),
    "Estadio Azteca": (19.303, -99.150, -1),
    "Melbourne Cricket Ground": (-37.820, 144.983, 14),
    "Santiago Bernabeu Stadium": (40.453, -3.688, 6),
    "Croke Park": (53.361, -6.251, 5),
}

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance. The plane does not fly a straight line, but the
    difference between a great circle and an actual flight path is noise next to
    the difference between a 300-mile trip and a 2,700-mile one."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def site_for(team: str) -> tuple[float, float, int] | None:
    entry = TEAM_SITES.get(team)
    if entry is None:
        return None
    _airport, lat, lon, tz = entry
    return lat, lon, tz


def venue_site(home_team: str, stadium: str | None, neutral: bool) -> tuple[float, float, int] | None:
    """Where the game is actually played."""
    if neutral and stadium and stadium in NEUTRAL_VENUES:
        return NEUTRAL_VENUES[stadium]
    return site_for(home_team)


# --- kickoff times ---------------------------------------------------------
# nflverse publishes `gameday` (YYYY-MM-DD) and `gametime` (HH:MM) in US
# Eastern. We store UTC everywhere, so this is the one conversion point.

def _eastern_offset_hours(naive: datetime) -> int:
    """US Eastern UTC offset. Tries the IANA database, falls back to the
    post-2007 US rule (DST from the 2nd Sunday in March to the 1st Sunday in
    November) so a PyInstaller build without tzdata still gets it right."""
    try:
        from zoneinfo import ZoneInfo

        return int(naive.replace(tzinfo=ZoneInfo("America/New_York")).utcoffset().total_seconds() // 3600)
    except Exception:  # noqa: BLE001 - no tzdata available
        year = naive.year
        march = datetime(year, 3, 1)
        second_sunday = march + timedelta(days=(6 - march.weekday()) % 7 + 7)
        november = datetime(year, 11, 1)
        first_sunday = november + timedelta(days=(6 - november.weekday()) % 7)
        dst = second_sunday.replace(hour=2) <= naive < first_sunday.replace(hour=2)
        return -4 if dst else -5


def eastern_hour(kickoff_utc: str | None) -> int | None:
    """The hour of a kickoff ON THE LEAGUE'S OWN CLOCK, or None.

    Deliberately not the reader's clock. Every other time in this interface is
    rendered where the reader is, because a card saying 6:40 PM should mean
    their evening -- but a SLATE is organised by the league: college football
    has a noon window, a 3:30 window and a night window, and those are facts
    about the schedule rather than about who is looking at it. Grouping a
    Saturday by the reader's timezone would split the same broadcast window in
    two for anyone west of Ohio.

    Returns None rather than guessing when the kickoff is unknown; a game with
    no time belongs in no window, and is counted as such.
    """
    if not kickoff_utc:
        return None
    try:
        moment = datetime.strptime(kickoff_utc[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None
    return (moment + timedelta(hours=_eastern_offset_hours(moment))).hour


def kickoff_to_utc(gameday: str, gametime: str | None) -> str | None:
    """'2026-09-13' + '13:00' (Eastern) -> '2026-09-13T17:00:00Z'.

    A missing time means the slot is not yet announced; we return None rather
    than guess, because a wrong kickoff time silently corrupts rest-day maths.
    """
    if not gameday:
        return None
    if not gametime:
        return None
    try:
        naive = datetime.strptime(f"{gameday} {gametime}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    offset = _eastern_offset_hours(naive)
    return (naive - timedelta(hours=offset)).replace(tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
