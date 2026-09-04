"""UFC moneyline quotes, read-only (E4, 2026-09-03).

LAW 5. This module records what a market SAID. It sizes nothing, recommends
nothing, and holds no account. It lives inside the market quarantine, which the
LAW 1 import-closure scan walks: nothing on the prediction path may reach it,
and a snapshot may only be written after the prediction row exists.

WHY UFC IS THE EASIEST COMPARISON IN THIS RECORD, and the hardest to get.

The moneyline needs NO DISTRIBUTIONAL ASSUMPTION. Every spread and total in
this project turns a posted line into a probability through a measured standard
deviation, and that SD is an assumption doing real work. A fight moneyline is a
binary question with two prices and an explicit `favorite` flag, so the implied
probability comes straight off the price and the flag is a free cross-check on
the arithmetic.

AND THE SOURCE STOPPED CARRYING IT. Measured 2026-09-03 over a stratified
sample of the whole stored record:

    season   sampled   priced
    2022        18       18
    2023        18       18
    2024        18       18
    2025        18       18
    2026        18        0

Month by month across the boundary: full coverage through November 2025, three
of five in December, and one priced bout in forty-five sampled from January
2026 onward. Fifteen providers appear in the historical data -- Bet365, ESPN
BET, Caesars, Unibet, Consensus and others -- and none of them price a 2026
bout.

WHAT THAT MEANS FOR THIS MODULE, said plainly rather than discovered later:
every bout Gridiron is currently forecasting is unpriced, so no live UFC card
will show a market comparison. The fetcher is still built and still correct.
It works on the historical record, where it makes a question testable that
`docs/DIAGNOSIS.md` records as NOT TESTABLE -- opening lines exist here and
nowhere else in this project -- and it will start working on live cards the day
coverage returns, without anyone having to notice that it has.
"""

from __future__ import annotations

import json
import sqlite3

from ..data import sources as http
from ..db import utcnow

CORE = "https://sports.core.api.espn.com/v2/sports/mma/leagues/ufc"

SOURCE_NAME = "espn/ufc"

#: WHICH PROVIDER'S PRICE IS THE ONE WE RECORD, in order.
#:
#: A bout carries up to fifteen, and "whichever came first in the list" is not
#: a decision -- it makes the recorded price depend on the order a feed happens
#: to return, which can change without notice and would show up as unexplained
#: movement in a record that is supposed to measure movement.
#:
#: Consensus first because it is the average of the others and is therefore the
#: least sensitive to any single book; then the two that appear most often in
#: the sampled record (Caesars NJ and Titanbets, 41 bouts each of 90 sampled),
#: then ESPN BET, which is the one the earlier probe measured. The order is
#: declared here so a changed price is a changed market and never a changed
#: preference.
PROVIDER_PRIORITY = (
    "Consensus",
    "Caesars Sportsbook (NJ)",
    "Titanbets",
    "Unibet",
    "ESPN BET",
    "Bet365",
)
PROVIDER_PRIORITY_DECLARED = "2026-09-03T00:00:00Z"


class ContradictedFavourite(ValueError):
    """The posted price and the favourite flag disagree about who is favoured."""


def odds_url(event_id: str, bout_id: str) -> str:
    return f"{CORE}/events/{event_id}/competitions/{bout_id}/odds"


def _get(conn: sqlite3.Connection, url: str, *, immutable: bool) -> dict | None:
    try:
        return json.loads(http.fetch(conn, url, immutable=immutable))
    except (http.SourceUnavailable, json.JSONDecodeError):
        return None


def _pick_provider(items: list) -> dict | None:
    """The highest-priority provider present, or None.

    A provider outside the declared list is NOT used as a fallback. The point
    of the priority is that the recorded price does not depend on which books
    happened to publish; falling back to an undeclared one would give that back
    with extra steps.
    """
    by_name = {}
    for item in items:
        name = (item.get("provider") or {}).get("name")
        if name and name not in by_name:
            by_name[name] = item
    for name in PROVIDER_PRIORITY:
        if name in by_name:
            return by_name[name]
    return None


def _moneylines(item: dict) -> tuple[int, int]:
    """The two American prices, checked against the feed's own favourite flag.

    THE FLAG IS A FREE CROSS-CHECK AND IT IS USED. ESPN publishes both a price
    and an explicit `favorite` boolean, so the feed can be caught contradicting
    itself, and it has been in another sport: three MLB rows carried a run line
    whose direction the price and the flag disagreed about, and the ruling
    there was that a contradicted sign is NOT a comparison. The same rule
    applies here, for the same reason -- a reversed comparison is worse than a
    missing one, because a missing one is visible.
    """
    away = item.get("awayAthleteOdds") or {}
    home = item.get("homeAthleteOdds") or {}
    a, h = away.get("moneyLine"), home.get("moneyLine")
    if a is None or h is None:
        raise KeyError("no moneyline on either side")
    a, h = int(a), int(h)
    flagged_home = bool(home.get("favorite"))
    flagged_away = bool(away.get("favorite"))

    # A PICK'EM IS A MARKET STATE, NOT A FAULT, and the first version of this
    # got it wrong. Both fighters at -110 with neither flagged as favourite is
    # a real bout the books called even -- it happened on the first live run,
    # was refused as a contradiction, and threw away the most informative kind
    # of comparison there is: the market saying it does not know either.
    #
    # Both prices equal AND neither side flagged is agreement, not conflict.
    if a == h:
        if flagged_home != flagged_away:
            raise ContradictedFavourite(
                f"both fighters are priced at {a} and the feed still flags one "
                f"of them as the favourite. Equal prices name no favourite.")
        return a, h

    # A shorter price is the favourite. American odds: -300 is shorter than
    # +250, and -300 is shorter than -150.
    price_favours_home = h < a
    if flagged_home == flagged_away:
        # Neither flagged or both flagged, on unequal prices: the feed states
        # no opinion, so the price stands alone. A silence, not a conflict.
        return a, h
    if price_favours_home != flagged_home:
        raise ContradictedFavourite(
            f"the price makes {'home' if price_favours_home else 'away'} the "
            f"favourite ({h} against {a}) and the feed's own flag makes it the "
            f"other one. A comparison pointing the wrong way is worse than none.")
    return a, h


def opening_prices(item: dict) -> tuple[int | None, int | None]:
    """The two OPENING American prices, where the provider carries them.

    THE ONLY OPENING LINES IN THIS PROJECT. `docs/DIAGNOSIS.md` records H1a --
    "the model disagrees most when it is MISSING information the market has" --
    as NOT TESTABLE, because every market number Gridiron holds for its other
    sports is a closing number and no free source publishes the openers. UFC
    carries `open` and `close` on the same object.

    Returned rather than stored: nothing in this session acts on it, and a
    column written by nothing is a column that will be wrong when something
    finally reads it.
    """
    out = []
    for side in ("awayAthleteOdds", "homeAthleteOdds"):
        opened = ((item.get(side) or {}).get("open") or {}).get("moneyLine") or {}
        american = opened.get("american")
        try:
            out.append(int(str(american).replace("+", "")) if american else None)
        except ValueError:
            out.append(None)
    return out[0], out[1]


def fetch_for_bouts(conn: sqlite3.Connection, bout_ids: list[str]) -> dict:
    """Read quotes for these bouts into `market_lines_raw`. Counts only.

    IDEMPOTENT AND CACHED. A settled bout's odds never change, so its document
    is fetched once and kept forever; a bout that has not happened is refetched
    within the ordinary TTL.

    NOTHING HERE TOUCHES A PREDICTION. This fills the raw table; the snapshot
    that attaches a quote to a forecast is written by `lines.snapshot_prediction`
    and only ever after the prediction row exists.
    """
    counts = {"asked": 0, "fetched": 0, "priced": 0, "unpriced": 0,
              "contradicted": 0, "no_provider": 0, "with_opening_price": 0}
    for bout_id in bout_ids:
        counts["asked"] += 1
        row = conn.execute(
            "SELECT b.id, b.event_id, b.status FROM ufc_bouts b WHERE b.id = ?",
            (bout_id,)).fetchone()
        if row is None:
            continue
        settled = row["status"] == "final"
        doc = _get(conn, odds_url(row["event_id"], row["id"]), immutable=settled)
        if doc is None:
            continue
        counts["fetched"] += 1
        items = doc.get("items") or []
        if not items:
            # THE ORDINARY CASE FOR EVERY 2026 BOUT. Recorded as a count, not
            # as an error: the source answered and carried no price.
            counts["unpriced"] += 1
            continue
        item = _pick_provider(items)
        if item is None:
            counts["no_provider"] += 1
            continue
        try:
            away, home = _moneylines(item)
        except ContradictedFavourite:
            counts["contradicted"] += 1
            continue
        except KeyError:
            counts["unpriced"] += 1
            continue

        # COUNTED, NOT STORED. The opening price is the one thing this source
        # has that no other in the project does, and `docs/DIAGNOSIS.md` has a
        # hypothesis waiting on it. Nothing acts on it yet, so it is reported
        # rather than written to a column nothing reads -- but the count is
        # what will say whether the data is there when something does.
        opened_away, opened_home = opening_prices(item)
        if opened_away is not None and opened_home is not None:
            counts["with_opening_price"] += 1

        provider = (item.get("provider") or {}).get("name") or "unknown"
        conn.execute(
            "INSERT INTO market_lines_raw (game_id, fetched_utc, source,"
            " spread_line, total_line, home_moneyline, away_moneyline)"
            " VALUES (?,?,?,NULL,NULL,?,?)"
            " ON CONFLICT(game_id) DO UPDATE SET"
            "   fetched_utc = excluded.fetched_utc, source = excluded.source,"
            "   home_moneyline = excluded.home_moneyline,"
            "   away_moneyline = excluded.away_moneyline",
            (row["id"], utcnow(), f"{SOURCE_NAME}/{provider}", home, away))
        counts["priced"] += 1
    conn.commit()
    return counts


def coverage(conn: sqlite3.Connection) -> dict:
    """How many stored bouts carry a quote, per tier. Reported, never assumed.

    THE HONEST NUMBER FOR THE INTERFACE. "No line" on a UFC card is a fact
    about the source, not about the bout, and this is what says so.
    """
    out = {}
    for row in conn.execute(
        "SELECT COALESCE(e.event_tier, 'unclassified') AS tier,"
        "       COUNT(*) AS bouts,"
        "       SUM(CASE WHEN r.game_id IS NOT NULL THEN 1 ELSE 0 END) AS priced"
        "  FROM ufc_bouts b"
        "  JOIN ufc_events e ON e.id = b.event_id"
        "  LEFT JOIN market_lines_raw r ON r.game_id = b.id"
        " GROUP BY tier ORDER BY bouts DESC"
    ):
        out[row["tier"]] = {"bouts": row["bouts"], "priced": row["priced"]}
    return out
