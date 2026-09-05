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


# ---------------------------------------------------------------------------
# THE LEAGUE'S OWN DAY (ruling 3 on the audit, 2026-09-05)
# ---------------------------------------------------------------------------
#
# A game is filed under the calendar day the league plays it on, never under
# the UTC date. Until 2026-09-05 college football and UFC used the UTC date,
# so a 7:30 PM Pacific kickoff was the next day's slate and a Las Vegas card
# was a Sunday. The convention, declared once and dated:
#
#   nfl  -- nflverse publishes `gameday`; the loader stores it as given.
#   mlb  -- statsapi publishes the schedule date; the loader stores it as given.
#   nba  -- the NBA schedule publishes the game date; stored as given.
#   cfb  -- the US Eastern date of kickoff. College football is scheduled and
#           talked about in Eastern time, and ESPN's feed carries no local date.
#   ufc  -- the EVENT'S local date, from the venue ESPN reports. A card is a
#           local evening wherever it is held, and 157 of the 268 events in the
#           record are Las Vegas nights that ended after midnight UTC.
#
# The three loaders that take the feed's own day never call this. The two that
# derive it call `league_day`, and nothing else decides.

LEAGUE_DAY_DECLARED = "2026-09-05"

#: Where UFC has held a card, to the timezone the venue keeps. Keyed by
#: (country, state) for the three countries that span zones and by country
#: otherwise; every place in the record on 2026-09-05 is here. An unknown
#: venue returns None rather than a guess, and the mirror says so.
VENUE_TIMEZONES: dict[tuple[str, str | None], str] = {
    ("USA", "NV"): "America/Los_Angeles",
    ("USA", "CA"): "America/Los_Angeles",
    ("USA", "WA"): "America/Los_Angeles",
    ("USA", "AZ"): "America/Phoenix",
    ("USA", "UT"): "America/Denver",
    ("USA", "CO"): "America/Denver",
    ("USA", "TX"): "America/Chicago",
    ("USA", "MO"): "America/Chicago",
    ("USA", "TN"): "America/Chicago",
    ("USA", "LA"): "America/Chicago",
    ("USA", "IL"): "America/Chicago",
    ("USA", "IA"): "America/Chicago",
    ("USA", "OK"): "America/Chicago",
    ("USA", "NY"): "America/New_York",
    ("USA", "NJ"): "America/New_York",
    ("USA", "FL"): "America/New_York",
    ("USA", "GA"): "America/New_York",
    ("USA", "MA"): "America/New_York",
    ("USA", "NC"): "America/New_York",
    ("USA", "OH"): "America/New_York",
    ("USA", "PA"): "America/New_York",
    ("USA", "DC"): "America/New_York",
    ("USA", "KY"): "America/New_York",
    ("Canada", "BC"): "America/Vancouver",
    ("Canada", "AB"): "America/Edmonton",
    ("Canada", "MB"): "America/Winnipeg",
    ("Canada", "ON"): "America/Toronto",
    ("Canada", "PQ"): "America/Toronto",
    ("Canada", "QC"): "America/Toronto",
    ("Australia", "WA"): "Australia/Perth",
    ("Australia", "NSW"): "Australia/Sydney",
    ("Australia", "VIC"): "Australia/Melbourne",
    ("Australia", "QLD"): "Australia/Brisbane",
    ("United Arab Emirates", None): "Asia/Dubai",
    ("England", None): "Europe/London",
    ("Scotland", None): "Europe/London",
    ("France", None): "Europe/Paris",
    ("Germany", None): "Europe/Berlin",
    ("Netherlands", None): "Europe/Amsterdam",
    ("Spain", None): "Europe/Madrid",
    ("Italy", None): "Europe/Rome",
    ("Sweden", None): "Europe/Stockholm",
    ("Poland", None): "Europe/Warsaw",
    ("Serbia", None): "Europe/Belgrade",
    ("Mexico", None): "America/Mexico_City",
    ("Brazil", None): "America/Sao_Paulo",
    ("Argentina", None): "America/Argentina/Buenos_Aires",
    ("Chile", None): "America/Santiago",
    ("Saudi Arabia", None): "Asia/Riyadh",
    ("Qatar", None): "Asia/Qatar",
    ("Azerbaijan", None): "Asia/Baku",
    ("China", None): "Asia/Shanghai",
    ("Macau", None): "Asia/Macau",
    ("Singapore", None): "Asia/Singapore",
    ("Japan", None): "Asia/Tokyo",
    ("South Korea", None): "Asia/Seoul",
    ("New Zealand", None): "Pacific/Auckland",
}

LEAGUE_TIMEZONES: dict[str, str] = {
    "nfl": "America/New_York",
    "mlb": "America/New_York",
    "nba": "America/New_York",
    "cfb": "America/New_York",
}


def venue_timezone(country: str | None, state: str | None = None) -> str | None:
    """The zone a venue keeps, or None when the venue is not declared above."""
    if not country:
        return None
    return VENUE_TIMEZONES.get((country, state)) or VENUE_TIMEZONES.get((country, None))


def league_day(sport: str, when_utc: str | None, *, country: str | None = None,
               state: str | None = None) -> str | None:
    """The calendar day `sport` files a game starting at `when_utc` under.

    "2026-09-06T02:30:00Z" is Saturday 5 September for college football and
    for a Las Vegas card, Sunday 6 September for a card in Abu Dhabi. None
    when there is no start time, or when a UFC venue is not declared above --
    an absence, never a guess.
    """
    if not when_utc or len(when_utc) < 16:
        return None
    from zoneinfo import ZoneInfo

    if sport == "ufc":
        zone = venue_timezone(country, state)
        if zone is None:
            return None
    else:
        zone = LEAGUE_TIMEZONES.get(sport)
        if zone is None:
            raise ValueError(f"no league day convention is declared for {sport!r}")
    text = when_utc.rstrip("Z")
    try:
        moment = datetime.strptime(text[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return moment.astimezone(ZoneInfo(zone)).strftime("%Y-%m-%d")


def slate_key(day: str | None) -> int | None:
    """"2026-09-05" -> 20260905, the integer form the `week` column keeps."""
    return int(day.replace("-", "")) if day else None
