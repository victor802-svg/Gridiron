"""Published player-prop lines, and the derivation of which side is which.

**This module is inside the LAW 1 quarantine.** It runs only after prediction
rows exist.

THE PROBLEM
-----------
ESPN publishes MLB player props -- measured 2026-08-30, 1,084 athlete rows
across one 14-game slate -- but a prop row carries a line and a price and **no
over/under label**. The union of keys on a prop row is `athlete, competition,
current, lastUpdated, odds, open, provider, type`, and none of them says which
way it points. A market with the line 5.5 appears twice for one pitcher, at
-136 and +107, and nothing in either row says which is the over.

That is the ESPN spread-sign shape exactly: a number that looks right and is
right about half the time. Checklist item 4 was written for it.

WHAT WAS RULED OUT, AND WHY
---------------------------
*"The shorter price is the over."* Forbidden as a method, and measurably worse
than it sounds: the first row in document order carries the shorter price in
62.7% of pairs, which is close enough to noise to be indistinguishable from it,
and the underlying claim -- that a book's favourite side is the over -- is
simply false for any subject whose line sits above their mean.

*Cross-rung monotonicity*, the originally specified derivation: P(over) must
fall as the line rises, so a subject quoted at two rungs identifies its own
sides. Correct reasoning, no data: measured on a full slate, **zero of 354
subjects were quoted at more than one rung**. Every subject gets exactly one
line. There is nothing to compare.

THE DERIVATION THAT WORKS
-------------------------
The slate carries two KINDS of prop market, and only one of them is ambiguous:

  * **Totals** -- "Total Hits", "Total Bases", "Total Strikeouts" -- two rows
    per subject, one line, no labels.
  * **Milestones** -- "Hits Milestones", "Total Bases Milestones", "Home Runs
    Milestones", "Strikeouts Thrown Milestones" -- ONE row per subject,
    displayed as "1+", "2+", "6+". A milestone is one-sided by construction:
    "2+ total bases" has no other half. Its side is known, not inferred.

And a milestone at K+ is the *same question* as the over at K-0.5. "6 or more
strikeouts" and "over 5.5 strikeouts" are one event with two names. So the
milestone's price states P(over) directly, and the member of the ambiguous pair
that matches it is the over.

Measured on the 2026-08-30 slate:

    market            anchored pairs   resolved   mean gap (match vs other)
    Total Hits                   112        112       0.001  vs  0.187
    Total Bases                   49         49       0.001  vs  0.178
    Total Strikeouts              12         11       0.001  vs  0.097

The separation is three orders of magnitude. The one strikeout pair that did not
resolve is a subject whose two sides were priced near enough to each other that
the anchor could not tell them apart -- and it is REFUSED, recorded with side
`unknown` and no implied probability, rather than being assigned the likelier
half. A prop with an undetermined side gets no market comparison and says so.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from ..data import sources as http
from ..db import utcnow
from . import crosswalk

CORE = "https://sports.core.api.espn.com/v2/sports"
LEAGUE_PATH = {"mlb": "baseball/leagues/mlb"}

#: ESPN's provider id for the book whose prices it republishes.
PROVIDER = 100

#: ESPN's name for the two-sided market behind each of ours.
TOTAL_MARKETS = {
    "Total Hits": "batter_hits",
    "Total Bases": "batter_total_bases",
    "Total Strikeouts": "pitcher_strikeouts",
}

#: ESPN's name for the ONE-SIDED milestone that anchors it. A milestone at K+
#: is the same event as the over at K-0.5, which is what makes it an anchor.
MILESTONE_MARKETS = {
    "Hits Milestones": "batter_hits",
    "Total Bases Milestones": "batter_total_bases",
    "Strikeouts Thrown Milestones": "pitcher_strikeouts",
    # Home runs are published ONLY as a milestone -- one row per subject, "1+".
    # There is no pair to disambiguate, so the side is known by construction
    # and no derivation is involved at all.
    "Home Runs Milestones": "batter_home_runs",
}

#: Markets whose only published form is one-sided.
ONE_SIDED = {"batter_home_runs"}

#: How close a pair member's implied probability must be to its anchor's to be
#: called the over. Measured separation on a real slate was 0.001 for the
#: matching member against 0.10-0.19 for the other, so this is two orders of
#: magnitude of headroom rather than a tuned threshold.
SIDE_TOLERANCE = 0.02
#: ...and how much further away the OTHER member must be. Both conditions have
#: to hold: a pair whose two sides are priced alike carries no information about
#: which is which, and is refused rather than guessed.
SIDE_MARGIN = 0.03


def american_to_probability(price: int) -> float:
    """A price as an implied probability, vig included.

    The vig is not removed, for the same reason `lines.american_to_probability`
    does not remove it: splitting a book's margin between two sides requires an
    assumption that would be ours rather than the market's.
    """
    if price < 0:
        return (-price) / ((-price) + 100.0)
    return 100.0 / (price + 100.0)


def _get(conn: sqlite3.Connection, url: str, *, immutable: bool):
    try:
        return json.loads(http.fetch(conn, url, immutable=immutable))
    except (http.SourceUnavailable, json.JSONDecodeError):
        return None


def _target(row: dict) -> float | None:
    """The rung this row is about, from `current.target`.

    A milestone displays "2+" and carries `target: 2.0`; a total displays "1.5"
    and carries `target: 1.5`. Reading the numeric target rather than parsing
    the display string means "1+" and "1.5" cannot be confused for one another.
    """
    target = ((row.get("current") or {}).get("target") or {}).get("value")
    if target is None:
        total = (row.get("odds") or {}).get("total") or {}
        target = total.get("value")
    try:
        return float(str(target).rstrip("+"))
    except (TypeError, ValueError):
        return None


def _price(row: dict) -> int | None:
    raw = ((row.get("odds") or {}).get("american") or {}).get("value")
    try:
        return int(str(raw).replace("+", ""))
    except (TypeError, ValueError):
        return None


def collect(conn: sqlite3.Connection, sport: str, yyyymmdd: str,
            *, settled: bool) -> dict:
    """Every prop quote ESPN publishes for one date, grouped by subject.

    Returns `{(espn_event_id, market, athlete_id): {"totals": [...],
    "milestones": [...]}}`. No side is assigned here; that is `derive_sides`.
    """
    listing = _get(conn, f"{CORE}/{LEAGUE_PATH[sport]}/events?"
                         f"dates={yyyymmdd}&limit=100", immutable=settled)
    grouped: dict[tuple, dict] = defaultdict(lambda: {"totals": [], "milestones": []})
    if listing is None:
        return grouped

    for item in listing.get("items", []):
        event = _get(conn, item["$ref"], immutable=settled)
        if event is None:
            continue
        cid = event["id"]
        payload = _get(
            conn,
            f"{CORE}/{LEAGUE_PATH[sport]}/events/{cid}/competitions/{cid}"
            f"/odds/{PROVIDER}/propBets?limit=300",
            immutable=settled,
        )
        if payload is None:
            continue
        for row in payload.get("items", []):
            name = (row.get("type") or {}).get("name")
            ref = (row.get("athlete") or {}).get("$ref")
            if not ref:
                continue            # a team prop; not our business
            athlete = ref.split("/athletes/")[1].split("?")[0]
            target, price = _target(row), _price(row)
            if target is None or price is None:
                continue
            entry = {
                "line": target,
                "price": price,
                "prob": american_to_probability(price),
                "event": cid,
                "athlete": athlete,
            }
            if name in TOTAL_MARKETS:
                grouped[(cid, TOTAL_MARKETS[name], athlete)]["totals"].append(entry)
            elif name in MILESTONE_MARKETS:
                grouped[(cid, MILESTONE_MARKETS[name], athlete)]["milestones"].append(
                    entry
                )
    return grouped


def derive_sides(market: str, group: dict) -> list[dict]:
    """Label a subject's quotes over/under, or refuse.

    The whole argument of this module lives in this function. Nothing here reads
    the sign of a price to decide a side.
    """
    totals = group.get("totals") or []
    milestones = group.get("milestones") or []
    out: list[dict] = []

    # A market published only as a milestone is one-sided: the quote IS the
    # over, at half a unit below the milestone. No derivation involved.
    if market in ONE_SIDED or (milestones and not totals):
        for m in milestones:
            out.append({
                "line": m["line"] - 0.5,
                "side": "over",
                "price": m["price"],
                "implied_prob": m["prob"],
                "method": "one_sided_milestone",
            })
        return out

    by_line: dict[float, list[dict]] = defaultdict(list)
    for t in totals:
        by_line[t["line"]].append(t)

    for line, pair in by_line.items():
        if len(pair) == 1:
            # A single quote with no partner and no anchor says nothing about
            # its own direction.
            out.append({
                "line": line, "side": "unknown", "price": pair[0]["price"],
                "implied_prob": None,
                "method": "refused_no_pair",
            })
            continue
        if len(pair) != 2:
            out.append({
                "line": line, "side": "unknown", "price": None,
                "implied_prob": None,
                "method": f"refused_{len(pair)}_quotes_at_one_line",
            })
            continue

        # The anchor: a milestone at line + 0.5 is the same event as the over.
        anchor = next(
            (m for m in milestones if abs(m["line"] - (line + 0.5)) < 1e-9), None
        )
        if anchor is None:
            out.append({
                "line": line, "side": "unknown", "price": None,
                "implied_prob": None,
                "method": "refused_no_milestone_anchor",
            })
            continue

        gaps = sorted(
            ((abs(q["prob"] - anchor["prob"]), q) for q in pair),
            key=lambda g: g[0],
        )
        (best_gap, best), (other_gap, other) = gaps
        if best_gap > SIDE_TOLERANCE or (other_gap - best_gap) < SIDE_MARGIN:
            # The two sides are priced too alike for the anchor to separate
            # them. Refused, with the numbers that failed recorded.
            out.append({
                "line": line, "side": "unknown", "price": None,
                "implied_prob": None,
                "method": (
                    f"refused_anchor_ambiguous(best={best_gap:.4f},"
                    f"other={other_gap:.4f})"
                ),
            })
            continue

        out.append({
            "line": line, "side": "over", "price": best["price"],
            "implied_prob": best["prob"], "method": "milestone_anchor",
        })
        out.append({
            "line": line, "side": "under", "price": other["price"],
            "implied_prob": other["prob"], "method": "milestone_anchor",
        })
    return out


def fetch_day(conn: sqlite3.Connection, sport: str, yyyymmdd: str,
              *, settled: bool = True) -> dict:
    """Load one date's prop lines into `market_prop_lines_raw`, sides derived.

    Athletes are resolved through the measured crosswalk. An id the crosswalk
    refused writes no line and is counted: we know a price exists and cannot say
    whose it is, which is a different fact from there being no price, and the
    two must not be recorded the same way.
    """
    counts = {"quotes": 0, "written": 0, "unknown_side": 0,
              "unmatched_athlete": 0, "unmatched_game": 0}
    grouped = collect(conn, sport, yyyymmdd, settled=settled)
    if not grouped:
        return counts

    athletes = sorted({key[2] for key in grouped})
    crosswalk.resolve(conn, sport, athletes)
    now = utcnow()

    for (event_id, market, athlete), group in grouped.items():
        quotes = derive_sides(market, group)
        counts["quotes"] += len(quotes)
        game_id = _match_game(conn, sport, event_id, yyyymmdd, settled)
        if game_id is None:
            counts["unmatched_game"] += 1
            continue
        if crosswalk.lookup(conn, sport, athlete) is None:
            counts["unmatched_athlete"] += 1
            continue
        for quote in quotes:
            if quote["side"] == "unknown":
                counts["unknown_side"] += 1
                continue
            conn.execute(
                "INSERT INTO market_prop_lines_raw (game_id, market, espn_id,"
                " line, side, price, implied_prob, side_method, source,"
                " fetched_utc) VALUES (?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(game_id, market, espn_id, line, side) DO UPDATE SET"
                " price=excluded.price, implied_prob=excluded.implied_prob,"
                " side_method=excluded.side_method",
                (game_id, market, athlete, quote["line"], quote["side"],
                 quote["price"], quote["implied_prob"], quote["method"],
                 f"espn/{sport}/DraftKings", now),
            )
            counts["written"] += 1
    conn.commit()
    return counts


def _match_game(conn, sport: str, event_id: str, yyyymmdd: str,
                settled: bool) -> str | None:
    """Our game row for an ESPN event id, via the clubs and the date."""
    from . import espn

    event = _get(
        conn,
        f"{CORE}/{LEAGUE_PATH[sport]}/events/{event_id}",
        immutable=settled,
    )
    if event is None:
        return None
    return espn._match_game(conn, sport, event, yyyymmdd)


def line_for(
    conn: sqlite3.Connection, game_id: str, market: str, espn_id: str,
    line_asked: float, side: str,
) -> sqlite3.Row | None:
    """The published quote for exactly the question we asked.

    Exactly: same game, same market, same line, same side. A quote at a
    different rung is a different question and is not a substitute -- attaching
    a 1.5-hit price to a 0.5-hit forecast would compare two things that are not
    comparable and nothing on the page would say so.
    """
    return conn.execute(
        "SELECT * FROM market_prop_lines_raw WHERE game_id = ? AND market = ?"
        " AND espn_id = ? AND line = ? AND side = ?",
        (game_id, market, str(espn_id), line_asked, side),
    ).fetchone()


def espn_id_for(conn: sqlite3.Connection, sport: str, source_id: int) -> str | None:
    """The ESPN athlete id for one of our player ids, if the crosswalk made it."""
    row = conn.execute(
        "SELECT espn_id FROM player_crosswalk WHERE sport = ? AND source_id = ?"
        " AND method IN ('exact', 'normalised')",
        (sport, int(source_id)),
    ).fetchone()
    return row["espn_id"] if row else None
