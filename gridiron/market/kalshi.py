"""Kalshi's published prices, read only (operator ruling D3, 2026-09-06).

**This module is inside the LAW 1 quarantine.** It lives in `gridiron.market`,
which no sport's prediction closure may import, and the blind window refuses
to let this package load while a prediction is being formed. Everything here
runs AFTER the prediction rows exist -- the trigger on `venue_quotes` refuses
a quote for a game with no prediction written before the fetch -- and nothing
here authenticates: the public trade API answers market, series and event
reads without a key, which was measured before this file was written.

The source and its limits, stated because a comparison drawn from a source you
cannot describe is not a comparison anyone can check:

  * `api.elections.kalshi.com/trade-api/v2` -- public, no key for market data
    (measured 2026-09-06: `markets`, `series`, `events` all HTTP 200
    unauthenticated). The terms of use and the API documentation could not be
    fetched from this machine the same day (429 and 404), so the terms are
    recorded as unstated and the source is treated as one that may vanish: if
    the public endpoint ever requires an account or a key, THE SOURCE IS
    DROPPED and `docs/DECISIONS_MADE.md` records it. This code never holds an
    account, a key, or a cookie.
  * Per game the venue quotes a LADDER of binary markets -- "Seattle wins by
    over 4.5 points", one per strike -- with a yes bid and ask in dollars, a
    total ("Over 63.5 points scored") and a winner series. Prices are stored
    as quoted; the at-the-line step reads them.
  * Rate limits for unauthenticated reads are unpublished. One event's ladder
    is fetched per game per look, every response is cached, and a finished
    game is never refetched.

THE CROSSWALK IS MEASURED, NEVER GUESSED. An event ticker is the series, the
league date, and the away code followed by the home code
(`KXNFLSPREAD-26SEP09NESEA`). Our codes match the venue's for 14 of 16 NFL
week-1 games and 41 of 50 open college events; the differences are listed in
`CODE_ALIASES` by name, so an unmatched game stays a COUNTED failure rather
than a fuzzy match that attaches the wrong ladder to a game.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import timedelta

from .. import config
from ..data import sources as http
from ..db import utcnow

VENUE = "kalshi"
BASE = "https://api.elections.kalshi.com/trade-api/v2"

#: The series that carries each market of each sport. A pair absent here is a
#: market the venue does not quote in a shape this project reads; it is a
#: counted hole in the coverage report, not an error.
SERIES: dict[tuple[str, str], str] = {
    ("nfl", "spread"): "KXNFLSPREAD",
    ("nfl", "total"): "KXNFLTOTAL",
    ("nfl", "moneyline"): "KXNFLGAME",
    ("cfb", "spread"): "KXNCAAFSPREAD",
    ("cfb", "total"): "KXNCAAFTOTAL",
    ("cfb", "moneyline"): "KXNCAAFGAME",
    ("nba", "spread"): "KXNBASPREAD",
    ("nba", "total"): "KXNBATOTAL",
    ("nba", "moneyline"): "KXNBAGAME",
    ("mlb", "spread"): "KXMLBSPREAD",
    ("mlb", "total"): "KXMLBTOTAL",
    ("mlb", "moneyline"): "KXMLBGAME",
}

#: THE VENUE'S CODE -> OURS, where they differ. Measured 2026-09-06 against the
#: record's own slates: NFL week 1 matched 14 of 16 tickers on date + away +
#: home, and the two that did not were exactly these; the open college events
#: matched 41 of 50, six more paired by elimination (one unmatched event and
#: one unmatched game on the same date), and the last three are FCS games this
#: record does not carry. Listed explicitly so an unmatched game stays counted.
CODE_ALIASES: dict[str, dict[str, str]] = {
    "nfl": {"LAR": "LA", "JAC": "JAX"},
    "cfb": {"NCST": "NCSU", "MIZZ": "MIZ", "TXAM": "TA&M", "OKLA": "OU",
            "STON": "STBK", "BSU": "BOIS"},
    "nba": {},
    "mlb": {},
}
CROSSWALK_MEASURED = {
    "nfl": {"matched": 16, "of": 16, "slate": "week 1, 2026", "with_aliases": 2,
            "measured_utc": "2026-09-06T00:00:00Z"},
    # BASEBALL, measured 2026-09-07 against the venue's 42 open events and the
    # 22 games this record holds inside that window. 20 matched exactly on
    # date, start time, away and home, with NO aliases: the codes agree. The
    # two misses are a 2024 row still marked scheduled and one game the venue
    # had not opened -- neither is a naming disagreement.
    "mlb": {"matched": 20, "of": 22, "slate": "open events, 7-9 September 2026",
            "with_aliases": 0, "measured_utc": "2026-09-07T19:30:00Z",
            "note": "the ticker carries the first pitch on the venue's clock"},
    "cfb": {"matched": 47, "of": 50, "slate": "open events, 5-13 September 2026",
            "with_aliases": 6, "not_carried": 3,
            "measured_utc": "2026-09-06T00:00:00Z"},
}

#: How fresh a quote must be. The open look accepts the cache's live window;
#: the near-start look asks again, the way the ESPN second look does.
OPEN_TTL = timedelta(hours=6)
NEAR_START_TTL = timedelta(minutes=10)

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

_SPREAD_SUFFIX = re.compile(r"^([A-Z&]+?)(\d+)$")


def venue_code(sport: str, our_code: str) -> str:
    """Our code as the venue writes it in a ticker."""
    for theirs, ours in CODE_ALIASES.get(sport, {}).items():
        if ours == our_code:
            return theirs
    return our_code


def our_code(sport: str, theirs: str) -> str:
    return CODE_ALIASES.get(sport, {}).get(theirs, theirs)


#: Sports whose event ticker carries the START TIME as well as the date,
#: and the timezone it is written in.
#:
#: BASEBALL PLAYS DOUBLEHEADERS. One pair of teams can meet twice on one date,
#: so date and teams do not identify a game and the venue puts the first pitch
#: in the ticker: `KXMLBGAME-26SEP071310NYMMIA`. Football never does, which is
#: why the same builder matched 16 of 16 NFL events while matching 0 of 22
#: baseball ones -- measured 2026-09-07, when this was found.
#:
#: The venue writes the time on the US Eastern clock, which is a fact about
#: the venue rather than about the game, so it is declared here beside the
#: sports that need it.
TICKER_CARRIES_START = {"mlb": "America/New_York"}
TICKER_START_MEASURED = "2026-09-07T19:30:00Z"


def event_ticker(sport: str, market: str, game) -> str | None:
    """The venue's event ticker for one of our games, or None when the venue
    has no series for the market or the game has no date.

    THE DATE IS THE LEAGUE'S AND THE TIME IS THE VENUE'S. A game's league date
    is the day the sport files it under; the ticker's time is the first pitch
    on the venue's own clock, and the two can disagree for a late start. Both
    come from the same kickoff instant so they cannot drift apart.
    """
    series = SERIES.get((sport, market))
    day = game["league_date"] or (game["kickoff_utc"] or "")[:10]
    if series is None or not day:
        return None
    zone = TICKER_CARRIES_START.get(sport)
    if zone:
        kickoff = game["kickoff_utc"]
        if not kickoff:
            return None
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo

        local = datetime.strptime(kickoff, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc).astimezone(ZoneInfo(zone))
        stem = (f"{local:%y}{MONTHS[local.month - 1]}{local:%d%H%M}")
    else:
        yy, mm, dd = day[2:4], int(day[5:7]), day[8:10]
        stem = f"{yy}{MONTHS[mm - 1]}{dd}"
    return (f"{series}-{stem}"
            f"{venue_code(sport, game['away'])}{venue_code(sport, game['home'])}")


def markets_url(ticker: str) -> str:
    return f"{BASE}/markets?event_ticker={ticker}&limit=200"


def _dollars(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_markets(sport: str, market: str, game, payload: dict) -> tuple[list[dict], list[str]]:
    """The venue's markets for one event as quote rows, and the tickers that
    could not be read -- a team code that is neither side, a shape this
    reader does not know. Never guessed: an unreadable market is counted."""
    quotes: list[dict] = []
    unreadable: list[str] = []
    for m in payload.get("markets") or []:
        ticker = m.get("ticker") or ""
        suffix = ticker.rsplit("-", 1)[-1]
        strike = m.get("floor_strike")
        if market == "spread":
            hit = _SPREAD_SUFFIX.match(suffix)
            if hit is None or strike is None:
                unreadable.append(ticker); continue
            team = our_code(sport, hit.group(1))
            if team == game["home"]:
                side, line = "home", -float(strike)
            elif team == game["away"]:
                side, line = "away", float(strike)
            else:
                unreadable.append(ticker); continue
            quantity = "home_margin"
        elif market == "total":
            if strike is None:
                unreadable.append(ticker); continue
            side, line, quantity = "over", float(strike), "total"
        elif market == "moneyline":
            team = our_code(sport, suffix)
            if team == game["home"]:
                side = "home"
            elif team == game["away"]:
                side = "away"
            else:
                unreadable.append(ticker); continue
            line, quantity = None, "home_win"
        else:
            unreadable.append(ticker); continue
        quotes.append({
            "ticker": ticker,
            "event_ticker": m.get("event_ticker") or "",
            "market": market,
            "quantity": quantity,
            "line": line,
            "yes_side": side,
            "yes_bid": _dollars(m.get("yes_bid_dollars")),
            "yes_ask": _dollars(m.get("yes_ask_dollars")),
            "last_price": _dollars(m.get("last_price_dollars")),
            "volume": _dollars(m.get("volume_fp")),
            "close_time": m.get("close_time"),
            "status": m.get("status"),
        })
    return quotes, unreadable


def capture_for_games(conn: sqlite3.Connection, sport: str, game_ids: list[str],
                      *, ttl: timedelta | None = None) -> dict:
    """Fetch and store the venue's ladders for these games. Every count is a
    fact about the fetch: events with no markets, unreadable tickers, sources
    that did not answer. Writes happen only where a prediction already exists
    (the trigger refuses anything else)."""
    counts = {"games": 0, "events": 0, "quotes": 0, "no_event": 0,
              "unreadable": 0, "unavailable": 0, "no_series": 0}
    if not game_ids:
        return counts
    placeholders = ",".join("?" for _ in game_ids)
    games = conn.execute(
        f"SELECT id, home, away, league_date, kickoff_utc FROM games"
        f" WHERE id IN ({placeholders})", game_ids).fetchall()
    for game in games:
        counts["games"] += 1
        for market in ("spread", "total", "moneyline"):
            ticker = event_ticker(sport, market, game)
            if ticker is None:
                counts["no_series"] += 1
                continue
            try:
                body = http.fetch(conn, markets_url(ticker), ttl=ttl or OPEN_TTL)
            except http.SourceUnavailable:
                counts["unavailable"] += 1
                continue
            try:
                payload = json.loads(body)
            except ValueError:
                counts["unreadable"] += 1
                continue
            quotes, unreadable = parse_markets(sport, market, game, payload)
            counts["unreadable"] += len(unreadable)
            if not quotes:
                counts["no_event"] += 1
                continue
            counts["events"] += 1
            stamp = utcnow()
            for q in quotes:
                conn.execute(
                    "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
                    " market, quantity, line, yes_side, yes_bid, yes_ask, last_price,"
                    " volume, close_time, fetched_utc)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (VENUE, q["ticker"], q["event_ticker"] or ticker, sport, game["id"],
                     q["market"], q["quantity"], q["line"], q["yes_side"], q["yes_bid"],
                     q["yes_ask"], q["last_price"], q["volume"], q["close_time"], stamp))
                counts["quotes"] += 1
            conn.commit()
    return counts


def capture_for_predictions(conn: sqlite3.Connection, prediction_ids: list[int],
                            *, ttl: timedelta | None = None) -> dict:
    """The ladders for the games behind these predictions, one sport at a time.
    THE ROWS EXIST BEFORE THE FETCH: this is called after the blind window has
    closed, and the trigger on the table holds the order regardless."""
    counts = {"games": 0, "events": 0, "quotes": 0, "no_event": 0,
              "unreadable": 0, "unavailable": 0, "no_series": 0}
    if not config.VENUE_CAPTURE:
        # Switched off (the test suite's network guard, or a machine that
        # should never ask): say so, rather than count a fetch that never went.
        counts["disabled"] = 1
        return counts
    if not prediction_ids:
        return counts
    placeholders = ",".join("?" for _ in prediction_ids)
    by_sport: dict[str, list[str]] = {}
    for r in conn.execute(
        f"SELECT DISTINCT sport, game_id FROM predictions WHERE id IN ({placeholders})"
        " AND market_type <> 'prop'", prediction_ids):
        by_sport.setdefault(r["sport"], []).append(r["game_id"])
    for sport, game_ids in by_sport.items():
        if not any(key[0] == sport for key in SERIES):
            counts["no_series"] += len(game_ids)
            continue
        part = capture_for_games(conn, sport, game_ids, ttl=ttl)
        for key, value in part.items():
            counts[key] = counts.get(key, 0) + value
    return counts


# ---------------------------------------------------------------------------
# THE VENUE'S PACKAGES (GRIDIRON_COMBOS, 2026-09-08)
# ---------------------------------------------------------------------------
#
# The venue assembles multi-leg packages and sells them; this reads the ones
# it has open. LAW 5 as amended: the engine grades a package and never builds
# one, so nothing here combines anything -- it fetches what is published and
# hands it to `combos.classify`.


def packages_url(series: str) -> str:
    return f"{BASE}/markets?series_ticker={series}&status=open&limit=200"


def read_packages(sport: str | None = None) -> tuple[list[dict], list[str]]:
    """Every open package market in the venue's declared combo series.

    Returns the packages and the series that answered nothing, because "the
    venue has none open" is a fact the group heading states and a silent empty
    list is not.
    """
    from . import combos

    out, quiet = [], []
    for series, series_sport in combos.COMBO_SERIES.items():
        if sport is not None and series_sport != sport:
            continue
        try:
            payload = _get(packages_url(series))
        except Exception:  # noqa: BLE001 - a source that does not answer is a fact
            quiet.append(series)
            continue
        markets = payload.get("markets") or []
        if not markets:
            quiet.append(series)
            continue
        for m in markets:
            out.append({
                "ticker": m.get("ticker") or "",
                "event_ticker": m.get("event_ticker") or "",
                "series": series,
                "sport": series_sport,
                "legs": combos.read_legs(
                    m.get("yes_sub_title") or m.get("title")),
                "legs_text": (m.get("yes_sub_title") or m.get("title") or ""),
                "yes_bid": _dollars(m.get("yes_bid_dollars")),
                "yes_ask": _dollars(m.get("yes_ask_dollars")),
                "last_price": _dollars(m.get("last_price_dollars")),
                "volume": _dollars(m.get("volume_fp")),
            })
    return out, quiet


def capture_packages(conn, sport: str, game_ids: list[str]) -> dict:
    """Store every package the venue has open for a sport, with its verdict.

    EVERY PACKAGE IS STORED, priced or not. The unpriceable ones are the
    group heading's counts and are the answer on most days -- on the day this
    shipped they were the answer on every day the venue had open.
    """
    from ..db import utcnow
    from . import combos

    counts = {"packages": 0, "priceable": 0, "quiet_series": 0}
    for reason in combos.UNPRICEABLE:
        counts[reason] = 0
    packages, quiet = read_packages(sport)
    counts["quiet_series"] = len(quiet)
    if not packages:
        return counts

    # EVERY NAME THE RECORD HOLDS FOR EACH CLUB, because the venue writes
    # them in full: "Denver -7.5", not "DEN". One query, shared with the
    # screen, so the fetch and the card cannot disagree about which names name
    # a club.
    codes = combos.club_index(combos.club_rows(conn, list(game_ids)))

    stamp = utcnow()
    for package in packages:
        # THE TICKER MUST AGREE WITH THE SERIES IT ARRIVED UNDER. A venue that
        # answers a series query with a market from another series would have
        # this record price a basketball package as a football one; the ticker
        # is the venue's own statement of which product it is, so it is read
        # rather than assumed from the query.
        by_ticker = combos.series_sport(package["ticker"])
        if by_ticker is not None and by_ticker != package["sport"]:
            package = dict(package, sport=by_ticker)
        verdict = combos.classify(package, codes)
        counts["packages"] += 1
        if verdict["priceable"]:
            counts["priceable"] += 1
        else:
            counts[verdict["why"]] = counts.get(verdict["why"], 0) + 1
        conn.execute(
            "INSERT OR IGNORE INTO venue_packages (venue, ticker, event_ticker,"
            " series, sport, legs_text, leg_count, game_ids, yes_bid, yes_ask,"
            " last_price, volume, priceable, why_not, fetched_utc)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (VENUE, package["ticker"], package["event_ticker"],
             package["series"], package["sport"], package["legs_text"],
             len(package["legs"]),
             ",".join(verdict.get("games") or []) if verdict["priceable"] else "",
             package["yes_bid"], package["yes_ask"], package["last_price"],
             package["volume"], 1 if verdict["priceable"] else 0,
             verdict["why"], stamp))
    conn.commit()
    return counts
