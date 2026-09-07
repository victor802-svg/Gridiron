"""Which markets the engine is allowed to price at all (THE_PRICED P2).

**BET FEW THINGS, ON PURPOSE.** Nobody beats five sports and twenty-nine
markets. NFL sides and totals are among the most efficiently priced markets in
existence, quoted by people with better data, better models and lower latency
than this project will ever have. If an edge exists here it exists where nobody
is looking, and the engine should be embarrassed by how few markets it covers.

**THE LIST IS MEASURED, NOT PICKED.** The operator's own winning tickets are
not evidence: four of them is a sample of four, and choosing a coverage list on
them is the discovery LAW 2 forbids with money attached. So coverage comes from
a structural proxy for inattention, measured from the venue's own published
ladders and dated:

  * **The spread a trade has to cross.** An edge of two cents cannot survive a
    four-cent spread, so a market whose quotes are wide is excluded however
    inattentive it looks.
  * **How much is traded.** Volume is the closest thing to an inattention
    measure available without an order book history: the market everybody is
    trading is the market whose price is already right.

  * **How often the price is repriced** is the third leg of the proxy and is
    NOT MEASURED YET. It needs two looks at the same ladder separated in time,
    and the near-start pass has only just begun collecting them. Recorded as a
    hole rather than approximated, and the coverage report says so.

**REVIEWED ON A CADENCE, NOT CONTINUOUSLY.** A list that can be edited the
moment a market loses is a list that chases results. The measurement window and
the review interval are declared below.
"""
from __future__ import annotations

import sqlite3
import statistics

from .. import config

#: Declared 2026-09-07, and reviewed no more often than this. A coverage list
#: revised the morning after a loss is a list fitted to noise.
COVERAGE_DECLARED = "2026-09-07T00:00:00Z"
REVIEW_EVERY_DAYS = 28

#: THE WIDEST QUOTE AN EDGE COULD SURVIVE, in cents. Three: the recommendation
#: engine will not act below one cent of fee-adjusted edge, and crossing more
#: than three cents of spread on top of the fee leaves nothing that a model
#: this unproven could reliably be right about.
MAX_SPREAD_CENTS = 3.0

#: HOW MUCH MEASUREMENT BEFORE A MARKET MAY BE COVERED AT ALL. Fifty quoted
#: strikes across at least three games; below that the medians are describing a
#: handful of ladders rather than a market.
MIN_QUOTES = 50
MIN_GAMES = 3


def measure(conn: sqlite3.Connection, sport: str) -> list[dict]:
    """The venue's own ladders, per market, as numbers with their N."""
    rows = conn.execute(
        "SELECT market, game_id, yes_bid, yes_ask, volume FROM venue_quotes"
        " WHERE sport = ? AND yes_bid IS NOT NULL AND yes_ask IS NOT NULL",
        (sport,)).fetchall()
    by_market: dict[str, list] = {}
    for row in rows:
        by_market.setdefault(row["market"], []).append(row)

    out = []
    for market in sorted(by_market):
        got = by_market[market]
        spreads = [(r["yes_ask"] - r["yes_bid"]) * 100.0 for r in got]
        volumes = [r["volume"] or 0.0 for r in got]
        out.append({
            "sport": sport,
            "market": market,
            "n": len(got),
            "games": len({r["game_id"] for r in got}),
            "median_spread_cents": round(statistics.median(spreads), 2),
            "median_volume": round(statistics.median(volumes), 1),
            "repricing_measured": False,
        })
    return out


def select(measured: list[dict]) -> list[dict]:
    """Which of the measured markets the engine may price, and why not.

    TWO CONDITIONS AND A FLOOR. Enough measurement to describe a market; a
    spread an edge could survive; and volume in the thinner half of what was
    measured for this sport, which is the inattention proxy standing in for the
    repricing frequency that is not measurable yet.
    """
    usable = [m for m in measured if m["n"] >= MIN_QUOTES and m["games"] >= MIN_GAMES]
    median_volume = (statistics.median([m["median_volume"] for m in usable])
                     if usable else None)
    decided = []
    for entry in measured:
        row = dict(entry)
        if entry["n"] < MIN_QUOTES or entry["games"] < MIN_GAMES:
            row.update(covered=False, why=(
                f"not measured enough: {entry['n']} quoted strikes across "
                f"{entry['games']} games, and {MIN_QUOTES} across {MIN_GAMES} "
                f"is the floor"))
        elif entry["median_spread_cents"] > MAX_SPREAD_CENTS:
            row.update(covered=False, why=(
                f"the quote is {entry['median_spread_cents']:.1f}¢ wide at the "
                f"middle, and an edge this project could measure would not "
                f"survive crossing it"))
        elif median_volume is not None and entry["median_volume"] > median_volume:
            row.update(covered=False, why=(
                f"the busiest half of what was measured: {entry['median_volume']:.0f} "
                f"contracts at the middle against {median_volume:.0f} for the "
                f"markets around it, and the market everybody is trading is the "
                f"one whose price is already right"))
        else:
            row.update(covered=True, why=(
                f"{entry['median_spread_cents']:.1f}¢ wide at the middle and "
                f"{entry['median_volume']:.0f} contracts traded, which is the "
                f"thinner half of what was measured for this sport"))
        decided.append(row)
    return decided


def coverage(conn: sqlite3.Connection, sport: str) -> dict:
    """The declared coverage for one sport, with the measurement behind it."""
    entries = select(measure(conn, sport))
    covered = [e for e in entries if e["covered"]]
    return {
        "sport": sport,
        "declared": COVERAGE_DECLARED,
        "reviewed_every_days": REVIEW_EVERY_DAYS,
        "n": sum(e["n"] for e in entries),
        "covered": [e["market"] for e in covered],
        "entries": entries,
        "repricing_measured": False,
        "note": (
            "Coverage is measured from the venue's own ladders, not chosen from "
            "which bets have won. A market is priced only if the quote is narrow "
            "enough for an edge to survive crossing it and thin enough that "
            "somebody might not have looked. How often a price is repriced is "
            "the third leg of that proxy and is not measured yet: it needs two "
            "looks at one ladder separated in time, and those have only just "
            "begun to be collected."
        ),
    }


def is_covered(conn: sqlite3.Connection, sport: str, market: str) -> bool:
    """May the engine price this market at all?"""
    return market in coverage(conn, sport)["covered"]


#: HOW MANY RECOMMENDATIONS BEFORE THE KILL CRITERION CAN FIRE, and it is the
#: brief's own number, declared 2026-09-07. Fifty, because that is roughly
#: where the closing line starts to say something; a win rate would need
#: several hundred and by then the money is spent.
KILL_AFTER = 50


def stopped(conn: sqlite3.Connection, sport: str) -> dict[str, dict]:
    """Coverage entries the closing line has stopped, and on what number.

    WRITTEN BEFORE IT WAS NEEDED, which is the whole point: nobody has ever
    wanted to compose this rule on the morning it fired. When a covered
    market's mean closing-line value is negative over fifty recommendations,
    the engine stops recommending that market and the page says so. Blind
    forecasting on it continues untouched -- only the money stops.

    RE-ENTRY IS NOT AUTOMATIC. Nothing here turns a stopped entry back on: that
    takes a dated operator ruling, because a rule that switches itself off and
    on again with the next fifty rows is a rule that chases noise in both
    directions.
    """
    from .. import calibration

    out: dict[str, dict] = {}
    report = calibration.clv_report(conn, sport=sport)
    for entry in report["markets"]:
        if entry["n"] < KILL_AFTER:
            continue
        if entry["mean_cents"] is not None and entry["mean_cents"] < 0:
            out[entry["market"]] = {
                "market": entry["market"],
                "n": entry["n"],
                "mean_cents": entry["mean_cents"],
                "why": (f"stopped after {entry['n']} recommendations: "
                        f"{entry['mean_cents']:+.1f}¢ a contract against the "
                        f"close, which is buying rich. Re-entry needs a dated "
                        f"ruling; the blind forecast on this market continues."),
            }
    return out


def priceable(conn: sqlite3.Connection, sport: str, market: str) -> dict:
    """May this market be priced right now, and if not, why not.

    Two gates in one door: the measured coverage list, and the kill criterion.
    A market can fail either and the caller is told which.
    """
    # THE KILL CRITERION IS ASKED FIRST. A market its own closing line has
    # stopped is stopped whatever the coverage measurement now says about it,
    # and that is the more useful sentence to hand a reader: "this was priced
    # fifty times and bought rich" says more than "this is not on the list".
    halted = stopped(conn, sport).get(market)
    if halted:
        return {"priceable": False, "market": market, "why": halted["why"]}
    if not is_covered(conn, sport, market):
        entries = {e["market"]: e for e in coverage(conn, sport)["entries"]}
        entry = entries.get(market)
        return {"priceable": False, "market": market,
                "why": (entry["why"] if entry else
                        "the venue's ladders have never been measured for this "
                        "market, so it is not covered")}
    return {"priceable": True, "market": market,
            "why": "covered by the measured list and not stopped"}
