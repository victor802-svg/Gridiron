"""What line source exists for each sport, stated honestly — including "none".

Checked on 2026-08-29. Every claim here was verified against the live endpoint
before it was written down, and the limitations are recorded because a
comparison drawn from a source you cannot describe is not a comparison anyone
can check.

LAW 5 and where lines come from
-------------------------------
Gridiron reads *media* APIs that republish lines. It holds no account,
authenticates to no book, and calls no exchange or sportsbook endpoint. ESPN's
public API republishes DraftKings prices; nflverse publishes closing numbers in
a research dataset. Neither is a betting integration, and if scoring against the
market ever required one, the market comparison would be dropped rather than the
law bent.

The degradation rule
--------------------
Where no reliable free source exists, the comparison degrades VISIBLY: the card
says "no line available", the dumbbell is absent rather than drawn against an
invented number, and the edge figure for that market states it cannot be
computed. **Predictions still run blind and resolve honestly regardless.** A
missing line source degrades the comparison, never the record. Same rule that
keeps `public_bet_pct` inactive: no proxies, no inventions.
"""

from __future__ import annotations

from .. import config

#: One descriptor per sport per market family. `available` is the only field the
#: interface branches on; the rest is what a reader needs to judge the number.
LINE_SOURCES: dict[str, dict] = {
    "nfl": {
        "available": True,
        "name": "nflverse-data (schedules release)",
        "url": "https://github.com/nflverse/nflverse-data",
        "licence": "CC BY 4.0",
        "rate_limit": "none; a static CSV, cached permanently once fetched",
        "markets": ["spread"],
        "prices": "closing spread, published after the fact by a research dataset",
        "note": (
            "Historical closing lines only. There is no opening line for the "
            "seasons in this record, which is why the D1 diagnosis could not "
            "test its line-movement hypothesis."
        ),
    },
    "mlb": {
        "available": True,
        "name": "ESPN public API (sports.core.api.espn.com)",
        "url": "https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb",
        "licence": (
            "NONE STATED. Undocumented public endpoint. No published terms, no "
            "published rate limit, and no guarantee it continues to exist."
        ),
        "rate_limit": (
            "unpublished. Gridiron fetches one odds document per game, caches "
            "every response permanently, and never refetches a settled game."
        ),
        "markets": ["moneyline", "batter_hits", "batter_total_bases",
                    "batter_home_runs", "pitcher_strikeouts"],
        "prices": (
            "DraftKings moneyline and player props, republished by ESPN"
        ),
        "note": (
            "Verified 2026-08-29: 15 of 15 games on a sample date carried "
            "moneylines. The site.api.espn.com host returns 403; the core API "
            "host answers. "
            "PLAYER PROPS RE-CHECKED 2026-08-30 and the earlier finding was "
            "WRONG: the `propBets` link does return prop quotes for MLB. One "
            "14-game slate carried 1,306 prop rows, 1,084 of them naming an "
            "athlete, covering all four markets -- 216 Total Hits, 81 Total "
            "Bases, 108 Home Runs Milestones, 24 Total Strikeouts. "
            "The rows carry a line and a price but NO over/under label, so the "
            "side is derived rather than assumed; see `market/props.py`. "
            "Because the licence is unstated, this is treated as "
            "a source that may vanish: if it does, MLB's market comparison "
            "degrades visibly and the record continues unaffected."
        ),
    },
    "nba": {
        "available": True,
        "name": "ESPN public API (sports.core.api.espn.com)",
        "url": "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba",
        "licence": (
            "NONE STATED. Undocumented public endpoint. No published terms, no "
            "published rate limit, and no guarantee it continues to exist."
        ),
        "rate_limit": (
            "unpublished. One odds document per game, cached permanently."
        ),
        "markets": ["spread"],
        "prices": "DraftKings spread and moneyline, republished by ESPN",
        "note": (
            "Verified 2026-08-29 against a 2025-26 game: spread, over/under and "
            "both moneylines present. Same unstated-licence caveat as MLB."
        ),
    },
}

#: Prop markets with no free line source at all. Named rather than left to be
#: inferred from silence.
#:
#: THIS WAS A BLANKET CLAIM AND THE BLANKET WAS WRONG. It read "no free source
#: publishes player prop lines", derived from one look at one NFL odds document
#: on 2026-08-29, and it was applied to every prop market of every sport by a
#: comprehension over `SPORT_PROP_MARKETS`. Re-checked on 2026-08-30, ESPN
#: publishes MLB player props in quantity. The mistake was not the reading; it
#: was generalising one sport's reading to three and writing the generalisation
#: down as a checked fact.
#:
#: So the exclusion is now stated per market, and a market is on this list only
#: if its own absence was looked at. MLB's four are NOT here. NFL's five and
#: NBA's four are, and NBA's entry says plainly that it has not been re-checked
#: since the MLB finding -- an untested market is not a market with no source,
#: and the two must not read the same.
_NFL_PROP_REASON = (
    "No free source publishes NFL player prop lines. nflverse carries closing "
    "spreads only, and ESPN's NFL odds documents were checked on 2026-08-29 "
    "without finding usable prop quotes. Every NFL prop in the record therefore "
    "carries a snapshot reading `unavailable:no-free-prop-line-source`: we "
    "looked, and there was nothing. The model still predicts and still "
    "resolves; only the comparison is absent, and it is shown as absent rather "
    "than faked."
)
_NBA_PROP_REASON = (
    "No prop line source is wired up for NBA. NOT RE-CHECKED since ESPN was "
    "found to publish MLB props on 2026-08-30, and the two facts must not be "
    "confused: this says nothing has been built, not that nothing exists. "
    "Until it is checked and built, the comparison is absent and shown as "
    "absent."
)
NO_LINE_MARKETS: dict[str, str] = {
    **{m: _NFL_PROP_REASON for m in config.SPORT_PROP_MARKETS.get("nfl", ())},
    **{m: _NBA_PROP_REASON for m in config.SPORT_PROP_MARKETS.get("nba", ())},
}


def for_sport(sport: str) -> dict:
    """The line-source descriptor a card or a scorecard should display."""
    entry = LINE_SOURCES.get(sport)
    if entry is None:
        return {
            "available": False,
            "sport": sport,
            "name": None,
            "reason": f"no line source is declared for {sport!r}",
        }
    return {"sport": sport, **entry}


def for_market(sport: str, market: str) -> dict:
    """Whether THIS market of this sport has a line, and why not when it does not."""
    if market in NO_LINE_MARKETS:
        return {
            "sport": sport,
            "market": market,
            "available": False,
            "reason": NO_LINE_MARKETS[market],
        }
    entry = for_sport(sport)
    if not entry.get("available"):
        return {"sport": sport, "market": market, "available": False,
                "reason": entry.get("reason", "no source")}
    if market not in entry.get("markets", []):
        return {
            "sport": sport,
            "market": market,
            "available": False,
            "reason": (
                f"{entry['name']} carries {entry['markets']} for this sport, not "
                f"{market!r}. The comparison is absent rather than approximated "
                "from a different market."
            ),
        }
    return {"sport": sport, "market": market, "available": True, **entry}
