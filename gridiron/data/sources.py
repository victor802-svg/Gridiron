"""Upstream data sources, and the cache that means we fetch each one once.

Source of record: **nflverse-data** GitHub release artifacts
(https://github.com/nflverse/nflverse-data), published under CC BY 4.0. These
are the same artifacts the `nfl_data_py` package wraps; we read the CSVs
directly so the runtime needs no pandas/pyarrow stack and so the exact bytes we
trained on are cached verbatim in our own database.

Weather forecasts come from Open-Meteo (https://open-meteo.com), free for
non-commercial use, no API key, CC BY 4.0.

Caching policy (CLAUDE.md: "never refetch what is already stored"):
  * A completed season's file never changes -> stored `immutable`, fetched once,
    never revalidated.
  * Live files (the current schedule) are revalidated with If-None-Match after
    a short TTL, and a 304 costs no bytes.
"""

from __future__ import annotations

import csv
import gzip
import io
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .. import config
from ..db import utcnow

NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"

#: Full schedule + results, 1999-present, one row per game.
GAMES_URL = f"{NFLVERSE}/schedules/games.csv"
#: Weekly player box scores for one season. nflverse's current asset naming;
#: the older `player_stats/player_stats_{season}.csv` stops at 2024 and is not
#: used, because a source that silently ends is worse than one that is missing.
PLAYER_STATS_URL = f"{NFLVERSE}/stats_player/stats_player_week_{{season}}.csv"
#: Weekly injury/participation report for one season.
INJURIES_URL = f"{NFLVERSE}/injuries/injuries_{{season}}.csv"

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

#: How stale a mutable cache entry may get before we revalidate.
LIVE_TTL = timedelta(hours=6)


class SourceUnavailable(RuntimeError):
    """An upstream fetch failed and no cached copy exists to fall back on."""


def _http_get(url: str, etag: str | None) -> tuple[int, bytes, str | None]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": config.USER_AGENT,
            "Accept-Encoding": "gzip",
            **({"If-None-Match": etag} if etag else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return resp.status, body, resp.headers.get("ETag")
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return 304, b"", etag
        raise


def fetch(
    conn: sqlite3.Connection,
    url: str,
    *,
    immutable: bool = False,
    offline_ok: bool = True,
) -> bytes:
    """Return the bytes at `url`, from cache when we can.

    `immutable=True` marks content that can never change upstream (a completed
    season). Those are fetched exactly once in the lifetime of the database.
    """
    row = conn.execute(
        "SELECT fetched_utc, etag, immutable, body FROM http_cache WHERE url = ?",
        (url,),
    ).fetchone()

    if row is not None:
        if row["immutable"]:
            return row["body"]
        age_cutoff = (datetime.now(timezone.utc) - LIVE_TTL).strftime("%Y-%m-%dT%H:%M:%SZ")
        if row["fetched_utc"] >= age_cutoff:
            return row["body"]

    etag = row["etag"] if row is not None else None
    try:
        status, body, new_etag = _http_get(url, etag)
    except Exception as exc:  # noqa: BLE001 - any network failure is the same to us
        if row is not None and offline_ok:
            return row["body"]
        raise SourceUnavailable(f"{url}: {type(exc).__name__}: {exc}") from exc

    if status == 304 and row is not None:
        conn.execute("UPDATE http_cache SET fetched_utc = ? WHERE url = ?", (utcnow(), url))
        conn.commit()
        return row["body"]

    conn.execute(
        "INSERT INTO http_cache (url, fetched_utc, etag, immutable, body) VALUES (?,?,?,?,?)"
        " ON CONFLICT(url) DO UPDATE SET"
        " fetched_utc = excluded.fetched_utc, etag = excluded.etag,"
        " immutable = excluded.immutable, body = excluded.body",
        (url, utcnow(), new_etag, 1 if immutable else 0, body),
    )
    conn.commit()
    return body


def fetch_csv(
    conn: sqlite3.Connection, url: str, *, immutable: bool = False
) -> list[dict[str, str]]:
    raw = fetch(conn, url, immutable=immutable).decode("utf-8", "replace")
    return list(csv.DictReader(io.StringIO(raw)))


def cache_stats(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT url, fetched_utc, immutable, length(body) AS bytes"
        " FROM http_cache ORDER BY url"
    ).fetchall()
    return [dict(r) for r in rows]
