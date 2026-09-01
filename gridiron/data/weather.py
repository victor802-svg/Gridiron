"""Kickoff weather forecasts for upcoming outdoor games.

Source: Open-Meteo (https://open-meteo.com), free, no API key, CC BY 4.0.

Only fetched for games that are outdoors and inside the forecast horizon. A
forecast we do not have is recorded as absent rather than guessed: the weather
factors then return None, the feature vector defaults them, and the prediction
carries the fact in its `missing` list forever.

Stored separately from the observed post-game readings in `game_conditions`, so
a forecast that was wrong stays distinguishable from the weather that happened.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
from datetime import datetime, timezone

from ..db import utcnow
from . import reference, sources

SOURCE = "open-meteo"
INDOOR_ROOFS = ("dome", "closed")


def _forecast_url(lat: float, lon: float) -> str:
    query = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.3f}",
            "longitude": f"{lon:.3f}",
            "hourly": "temperature_2m,wind_speed_10m,precipitation_probability",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": 16,
            "timezone": "UTC",
        }
    )
    return f"{sources.OPEN_METEO_URL}?{query}"


def _nearest_hour(payload: dict, kickoff_utc: str) -> tuple[float | None, float | None, float | None]:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return None, None, None
    target = kickoff_utc[:13]  # YYYY-MM-DDTHH
    for i, stamp in enumerate(times):
        if stamp[:13] == target:
            def at(key):
                values = hourly.get(key) or []
                return values[i] if i < len(values) else None

            return at("temperature_2m"), at("wind_speed_10m"), at("precipitation_probability")
    return None, None, None


def fetch_week(conn: sqlite3.Connection, season: int, week: int) -> dict[str, int]:
    """Forecast every outdoor game in the week that we can reach."""
    games = conn.execute(
        "SELECT g.id, g.home, g.kickoff_utc, c.roof, c.stadium, c.neutral_site"
        " FROM games g LEFT JOIN game_conditions c ON c.game_id = g.id"
        " WHERE g.season = ? AND g.week = ?",
        (season, week),
    ).fetchall()

    counts = {"fetched": 0, "indoors": 0, "out_of_range": 0, "unavailable": 0}
    for g in games:
        if (g["roof"] or "").lower() in INDOOR_ROOFS:
            counts["indoors"] += 1
            continue
        if not g["kickoff_utc"]:
            counts["out_of_range"] += 1
            continue
        site = reference.venue_site(g["home"], g["stadium"], bool(g["neutral_site"]))
        if site is None:
            counts["unavailable"] += 1
            continue

        try:
            raw = sources.fetch(conn, _forecast_url(site[0], site[1]))
            payload = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001 - no forecast is a recorded absence
            counts["unavailable"] += 1
            continue

        temp, wind, precip = _nearest_hour(payload, g["kickoff_utc"])
        if temp is None and wind is None:
            counts["out_of_range"] += 1
            continue

        conn.execute(
            "INSERT INTO weather_forecasts (game_id, fetched_utc, source, temp_f,"
            " wind_mph, precip_pct) VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(game_id) DO UPDATE SET fetched_utc=excluded.fetched_utc,"
            " temp_f=excluded.temp_f, wind_mph=excluded.wind_mph,"
            " precip_pct=excluded.precip_pct",
            (g["id"], utcnow(), SOURCE, temp, wind, precip),
        )
        counts["fetched"] += 1

    conn.commit()
    return counts


def wind_at(conn: sqlite3.Connection, lat: float, lon: float,
            kickoff_utc: str) -> float | None:
    """Forecast wind in mph at one place and hour, or None.

    Used by college football, whose venues are geocoded rather than read from a
    published coordinate table. Returns None for a kickoff outside the forecast
    horizon or a fetch that failed -- an absent forecast, which the feature
    vector records as absent. It is never zero: "no wind" and "no reading" are
    different facts and a fit told the wrong one would learn from calm days
    that never happened.
    """
    try:
        payload = json.loads(sources.fetch(conn, _forecast_url(lat, lon)))
    except (sources.SourceUnavailable, json.JSONDecodeError):
        return None
    _temp, wind, _precip = _nearest_hour(payload, kickoff_utc)
    return None if wind is None else float(wind)


#: Open-Meteo's historical archive. Same provider, same CC BY 4.0 licence as
#: the forecast endpoint already in use, so no new source enters the project.
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _archive_url(lat: float, lon: float, day: str) -> str:
    query = urllib.parse.urlencode({
        "latitude": f"{lat:.3f}",
        "longitude": f"{lon:.3f}",
        "start_date": day,
        "end_date": day,
        "hourly": "wind_speed_10m",
        "wind_speed_unit": "mph",
        "timezone": "UTC",
    })
    return f"{ARCHIVE_URL}?{query}"


def wind_observed(conn: sqlite3.Connection, lat: float, lon: float,
                  kickoff_utc: str) -> float | None:
    """What the wind ACTUALLY was, for a kickoff that has already happened.

    THIS EXISTS BECAUSE THE FORECAST ENDPOINT HAS NO PAST, and that made the
    wind factor unfittable: it was measured on 0 of 873 training rows and the
    fit dropped it, while being present on 54 of 57 live ones. A factor that
    exists forward and not backward has no coefficient to apply -- it would
    have sat in the registry doing nothing, looking like an instrument.

    The two are different quantities and the difference is worth stating: a
    forecast is what we knew before kickoff, an observation is what happened.
    Fitting on observations and predicting on forecasts means the coefficient
    is estimated from slightly better information than it will be applied to,
    so it is a CEILING on what the factor is worth, not a flattering estimate.
    The alternative -- no wind factor at all in a sport where weather moves
    totals -- is worse, and the direction of the error is stated rather than
    hidden.
    """
    day = kickoff_utc[:10]
    if not day:
        return None
    try:
        payload = json.loads(
            sources.fetch(conn, _archive_url(lat, lon, day), immutable=True))
    except (sources.SourceUnavailable, json.JSONDecodeError):
        return None
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    winds = hourly.get("wind_speed_10m") or []
    target = kickoff_utc[:13]
    for i, stamp in enumerate(times):
        if stamp[:13] == target:
            return None if i >= len(winds) or winds[i] is None else float(winds[i])
    return None
