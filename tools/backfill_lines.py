"""Backfill closing lines for completed games, one date at a time.

WHY THIS EXISTS. `docs/DISTRIBUTIONAL.md` §7 requires the walk-forward to run
on games that carry a stored market line, and says of the NBA arm: *"NBA's
line coverage must be extended before the comparison is possible, and if it
cannot be, the NBA arm is reported as not run rather than quietly dropped."*
This is the extension. Before it ran the record held 13 lined NBA finals and
11 lined CFB finals, against NFL's 2,761.

IT WRITES ONLY `market_lines_raw`, which is the RAW side of the market module:
lines keyed by game, with no prediction attached and no snapshot created. LAW
1 is untouched -- `market_lines_raw` is the table the prediction path is
already forbidden to import, and nothing here is reachable from it.

SETTLED DAYS ARE IMMUTABLE. A finished game's closing numbers never change, so
every response is cached forever and a second run of this script is free.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gridiron import config, db  # noqa: E402
from gridiron.market import espn  # noqa: E402


def game_days(conn: sqlite3.Connection, sport: str,
              seasons: tuple[int, ...]) -> list[str]:
    """Every UTC date on which this sport has a completed game, in order.

    LOCAL DATES, NOT UTC ONES, and the shift is why: an NBA game at 02:30Z is
    the previous evening in North America, which is the date ESPN files it
    under. Fetching the UTC date would miss every late tip-off.
    """
    placeholders = ",".join("?" for _ in seasons)
    rows = conn.execute(
        f"SELECT DISTINCT kickoff_utc FROM games"
        f" WHERE sport = ? AND status = 'final' AND season IN ({placeholders})"
        f" ORDER BY kickoff_utc", (sport, *seasons)).fetchall()
    days = set()
    for r in rows:
        stamp = (r["kickoff_utc"] or "")[:19]
        if not stamp:
            continue
        try:
            when = dt.datetime.fromisoformat(stamp.replace("Z", ""))
        except ValueError:
            continue
        # ESPN files a game under its US date; anything before ~11:00Z belongs
        # to the previous day there.
        local = when - dt.timedelta(hours=8)
        days.add(local.strftime("%Y%m%d"))
    return sorted(days)


def already_lined(conn: sqlite3.Connection, sport: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT m.game_id FROM market_lines_raw m"
        " JOIN games g ON g.id = m.game_id"
        " WHERE g.sport = ? AND g.status = 'final')", (sport,)).fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sport")
    parser.add_argument("--seasons", default="",
                        help="comma-separated; defaults to the loaded seasons")
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after this many dates (0 = all)")
    args = parser.parse_args()

    seasons = (tuple(int(s) for s in args.seasons.split(",") if s.strip())
               or config.SPORT_LOAD_SEASONS[args.sport])

    conn = db.connect()
    before = already_lined(conn, args.sport)
    days = game_days(conn, args.sport, seasons)
    if args.limit:
        days = days[:args.limit]
    print(f"{args.sport}: {len(days)} game days across {seasons}; "
          f"{before} finals already carry a line", flush=True)

    started = time.time()
    totals = {"events": 0, "with_odds": 0, "written": 0, "unmatched": 0}
    for i, day in enumerate(days, 1):
        try:
            counts = espn.fetch_day(conn, args.sport, day, settled=True)
        except Exception as exc:                                  # noqa: BLE001
            print(f"  {day}: {type(exc).__name__}: {exc}", flush=True)
            continue
        for key in totals:
            totals[key] += counts.get(key, 0)
        conn.commit()
        if i % 25 == 0 or i == len(days):
            rate = i / max(time.time() - started, 1e-9)
            print(f"  {i}/{len(days)} days  {totals['written']} written  "
                  f"{rate:.1f} days/s", flush=True)

    after = already_lined(conn, args.sport)
    print(f"{args.sport}: {before} -> {after} lined finals "
          f"({totals['written']} rows written, {totals['unmatched']} unmatched)",
          flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
