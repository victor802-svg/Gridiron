"""Packages the venue assembled, graded (GRIDIRON_COMBOS, 2026-09-08).

THE APP GRADES PACKAGES AND NEVER BUILDS THEM. LAW 5 as amended: the engine
may price a multi-leg package the venue publishes, and may never assemble one.
It does not choose legs, does not combine them, and does not compute a price
the venue has not printed.

WHY THAT DISTINCTION IS THE WHOLE DESIGN, and not a nicety. The first draft of
this brief had the app pick two legs by edge and then read "the venue's combo
price" for that pair. Measured against the venue on 2026-09-08, that pair is
not a product: every combo series it publishes is its OWN package. Either the
app assembles and the price must be invented, or the price is read and the
venue assembled. This module is the second.

PRICEABLE, AND EVERYTHING ELSE COUNTED:

  * every leg is a market this record forecasts;
  * every leg is from a DIFFERENT GAME -- a same-game package has no fair
    value here, because multiplying two probabilities from one game prices a
    correlation nobody declared (LAW 2), and the record holds no joint model;
  * all legs are one sport (LAW 6);
  * two or three legs.

Anything else is refused a number and counted with its reason. That is not a
gap in coverage: it is the honest answer, and on the day this shipped it was
the answer for every package the venue had open.
"""
from __future__ import annotations

import re
import sqlite3

from .. import config

#: The venue's combo series, and the sport each belongs to. Declared rather
#: than sniffed from a ticker: a series whose sport this project cannot name
#: is a series it cannot price, and guessing from a substring is how "MLB
#: AWARD combo" would be graded as a baseball game package.
#:
#: MEASURED 2026-09-08 from the venue's own series listing. `KXMLBAWARDCOMBO`
#: is deliberately absent: it pairs two season awards, which this record does
#: not forecast at all.
COMBO_SERIES: dict[str, str] = {
    "KXNBAPREPACK2ML": "nba",
    "KXNBAPREPACK3ML": "nba",
    "KXNFLCOMBO": "nfl",
    "KXNCAAMB2ML": "cbb",
    "KXNCAAMBSGP": "cbb",
}

#: THE SERIES THE VENUE ITSELF CALLS SAME-GAME (measured 2026-09-08). Every
#: market in one pairs two legs from a single game, which this record cannot
#: price at any price: multiplying two probabilities from one game prices a
#: correlation nobody declared (LAW 2), and there is no joint model here.
#:
#: DECLARED RATHER THAN INFERRED FROM THE LEGS, because inferring it fails on
#: exactly the packages it matters for. `KXNCAAMBSGP-26APR06CONNMICHSPREAD`
#: reads "Michigan -7.5 & Under 144.5 points": the second leg names no club,
#: so it lands in no game, and the package would be counted "with a leg this
#: record does not forecast" -- true, and not the fact a reader needs.
SAME_GAME_SERIES = frozenset({"KXNCAAMBSGP"})

#: Sports this record forecasts. A package in any other sport is unpriceable
#: for the plainest possible reason: there is no forecast to price it with.
#: College BASKETBALL is not college football and is not in this record.
#:
#: TAKEN FROM `config.SPORTS` rather than typed beside it, so a sport added to
#: this project cannot be silently absent here -- which would refuse every
#: package in it with the words "a sport this record does not forecast", a
#: sentence that would then be false.
FORECAST_SPORTS = config.SPORTS

#: How many legs a package may have and still be priced.
MIN_LEGS, MAX_LEGS = 2, 3

#: At most this many priced packages reach the screen in a day, ranked by
#: return on stake. Three, because a fourth is a fourth chance for the day's
#: noisiest number to look like a finding.
MAX_SHOWN = 3

#: THE REASONS A PACKAGE IS NOT PRICED, in the words the group heading uses.
#: Each one is a fact about the package rather than a failure of this module,
#: and each is counted separately so a reader can tell "the venue offers none"
#: from "the venue offers only same-game ones".
#: EACH READS AFTER A COUNT, because that is the only place they appear:
#: "2 same-game, not priceable". A phrase that only works alone would print as
#: "4 a sport this record does not forecast", which is how a heading meant to
#: be an answer becomes a thing a reader skips.
UNPRICEABLE = {
    "same_game": "same-game, not priceable",
    "cross_sport": "with legs in two sports, not priceable",
    "leg_count": "with more than three legs, not priceable",
    "unforecast_leg": "with a leg this record does not forecast",
    "unforecast_sport": "in a sport this record does not forecast",
    "unreadable": "whose legs the venue did not publish readably",
}

#: A package market's legs are written into its subtitle, joined by "&" or the
#: word "and": "Michigan -7.5 & Under 144.5 points". Measured against
#: `KXNCAAMBSGP-26APR06CONNMICHSPREAD-MICHU144` on 2026-09-08.
_LEG_SPLIT = re.compile(r"\s*(?:&|\band\b)\s+", re.I)


#: The columns a club's names live in, on a game row joined to `teams`. One
#: list, used by the fetch and by the screen, so the two cannot disagree about
#: which names count as naming a club.
NAME_COLUMNS = ("home", "away", "home_name", "away_name", "home_club",
                "away_club", "home_location", "away_location")

def series_sport(ticker: str) -> str | None:
    """Which sport a package ticker belongs to, or None if undeclared."""
    for series, sport in COMBO_SERIES.items():
        if ticker.startswith(series):
            return sport
    return None


def read_legs(subtitle: str | None) -> list[str]:
    """The legs as the venue wrote them. Never interpreted, only split."""
    if not subtitle:
        return []
    parts = [p.strip() for p in _LEG_SPLIT.split(str(subtitle)) if p.strip()]
    return parts


def _game_of(leg: str, games: dict[str, str]) -> str | None:
    """Which of our games a leg names, by any name the record holds for a club.

    THE VENUE WRITES CLUBS IN FULL. "Denver -7.5", "Michigan -7.5" -- not the
    tricodes this record stores, which is what the first version matched on
    and why every package came back unreadable. `games` therefore maps every
    name the record holds for a club -- tricode, location, short name, display
    name -- to the game it plays in.

    NEVER BY POSITION, and never on two matches. A leg belongs to a game only
    when exactly one game's names appear in it; none or several is an
    unreadable leg, counted rather than guessed. Two Los Angeles clubs on one
    slate is the case that rule exists for, and guessing there would price a
    proposition nobody offered.
    """
    hits = set()
    for name, game_id in games.items():
        if not name:
            continue
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])",
                     leg, re.I):
            hits.add(game_id)
    return next(iter(hits)) if len(hits) == 1 else None


def club_index(rows) -> dict[str, str]:
    """Every name the record holds for the clubs in these games.

    A NAME SHARED BY TWO GAMES IS DROPPED rather than pointed at one of them:
    "Los Angeles" on a slate with both LA clubs identifies nothing, and a map
    that answered anyway would place a leg in the wrong game.

    NAMED `club_index` FOR A REASON. Its first name used the word LAW 5's
    credential scan refuses inside a market module, and
    `audit.venue_credential_faults` fired on it on 2026-09-08. The scan is one
    of the four things that law marks not amendable by a later session, so the
    code moved and the scan did not -- a scan that can be argued out of a
    false positive can be argued out of a real one.
    """
    seen: dict[str, set] = {}
    for row in rows:
        keys = row.keys() if hasattr(row, "keys") else row
        for field in NAME_COLUMNS:
            if field not in keys:
                continue
            name = (row[field] or "").strip()
            if name:
                seen.setdefault(name, set()).add(row["id"])
    return {name: next(iter(ids)) for name, ids in seen.items()
            if len(ids) == 1}


def classify(package: dict, games: dict[str, str]) -> dict:
    """PRICEABLE, or the reason it is not. No package is ever half-priced.

    `package` carries the venue's own fields: its ticker, its sport, the legs
    it printed, and the price it published. `games` maps a team code to the
    game it plays in, for the slate being read.
    """
    sport = package.get("sport")
    legs = package.get("legs") or []
    # THE SPORT FIRST, and the order is deliberate: a package in a sport this
    # record does not forecast cannot be priced whatever its shape, so that is
    # the fact worth printing. A same-game package in an unforecast sport is
    # both, and this counts it under the refusal that would still stand if the
    # other were fixed.
    if sport not in FORECAST_SPORTS:
        return {"priceable": False, "why": "unforecast_sport", "legs": []}
    # THEN THE VENUE'S OWN WORD FOR IT. A series the venue calls same-game is
    # same-game, and saying so is better than the reason the leg matcher would
    # have reached for.
    if package.get("series") in SAME_GAME_SERIES:
        return {"priceable": False, "why": "same_game", "legs": legs}
    if not legs:
        return {"priceable": False, "why": "unreadable", "legs": []}
    if not MIN_LEGS <= len(legs) <= MAX_LEGS:
        return {"priceable": False, "why": "leg_count", "legs": legs}

    placed = [_game_of(leg, games) for leg in legs]
    if any(game is None for game in placed):
        return {"priceable": False, "why": "unforecast_leg", "legs": legs}
    if len(set(placed)) != len(placed):
        # THE ONE THE VENUE ACTUALLY SELLS. Every package market readable on
        # 2026-09-08 was one of these.
        return {"priceable": False, "why": "same_game", "legs": legs,
                "games": placed}
    return {"priceable": True, "why": None, "legs": legs, "games": placed}


def fair_value(leg_probabilities: list[float]) -> float | None:
    """The product of the legs' published probabilities.

    THE PUBLISHED ONES, which are the corrected ones where a correction is in
    force: a package is priced against what the reader was shown, not against
    a raw claim they never saw.

    Independence is ASSUMED and is only defensible because `classify` has
    already refused every same-game package. Two games on one evening are not
    perfectly independent either, and this is the closest thing to a joint
    model this record can honestly offer -- which is why the singles
    alternative is printed on every card.
    """
    if not leg_probabilities or any(p is None for p in leg_probabilities):
        return None
    product = 1.0
    for p in leg_probabilities:
        product *= float(p)
    return round(product, 6)


def legs_multiply_to(leg_prices: list[float]) -> float | None:
    """What the legs' own prices multiply to.

    Printed beside the venue's package price so its margin -- or its discount
    -- is one visible number instead of an inference.
    """
    return fair_value(leg_prices)


def package_edge(fair: float | None, price: float | None) -> dict:
    """The same arithmetic a single gets, at the package's price."""
    from . import recommend

    if fair is None or price is None:
        return {"edge_cents": None, "return_on_stake": None, "fee": None}
    fee = recommend.fee(price)
    edge = (fair - price - fee) * 100.0
    return {
        "edge_cents": round(edge, 2),
        "return_on_stake": recommend.return_on_stake(round(edge, 2), price),
        "fee": fee,
    }


def size_for(legs: int, *, settled: int, gate: int, fair: float | None = None,
             price: float | None = None, measured_edge: bool | None = None) -> dict:
    """Half a unit on two legs, a quarter on three, below the gate.

    NOT ADJUSTED BY ODDS OR BY THE MODEL'S OWN PROBABILITY, which is the same
    rule a single follows and for the same reason: an unproven number may not
    set a stake. The fractions are smaller than a single's flat unit because a
    package's cost per dollar is 1.67 to 2.8 times a single's, measured.
    """
    from .. import config
    from . import recommend

    flat = config.FLAT_UNIT * (0.5 if legs == 2 else 0.25)
    if settled < gate or not measured_edge:
        return {"kind": "flat", "units": round(flat, 4), "legs": legs,
                "why": ("no measured edge in this market yet"
                        if settled < gate else
                        "the record does not show this market beating its price")}
    sized = recommend.size_for(model_prob=fair, price=price, settled=settled,
                               measured_edge=measured_edge)
    # CAPPED AT THE FLAT FRACTION, so a package can never be staked above what
    # an unproven one would have been.
    return {"kind": sized["kind"], "legs": legs,
            "units": round(min(sized["units"], flat), 4),
            "why": sized.get("why")}


def singles_alternative(leg_prices: list[float], leg_fairs: list[float]) -> dict:
    """The same money as singles, so the comparison is on the card.

    THE COST IS THE POINT. Measured 2026-09-08: the fee per dollar staked is
    1.67 times the singles' rate on two 60c legs and 2.8 times on three. A
    package that shows only its own edge is a page arguing one side.
    """
    from . import recommend

    if not leg_prices or len(leg_prices) != len(leg_fairs):
        return {}
    singles_edge = sum((f - p - recommend.fee(p)) * 100.0
                       for f, p in zip(leg_fairs, leg_prices)) / len(leg_prices)
    singles_fee = sum(recommend.fee(p) / p for p in leg_prices) / len(leg_prices)
    combo_price = fair_value(leg_prices)
    combo_fee = (recommend.fee(combo_price) / combo_price) if combo_price else None
    return {
        "singles_edge_cents": round(singles_edge, 2),
        "singles_fee_share": round(singles_fee, 4),
        "combo_fee_share": round(combo_fee, 4) if combo_fee else None,
        "ratio": (round(combo_fee / singles_fee, 2)
                  if combo_fee and singles_fee else None),
    }


#: HOW MANY THE APP WILL PROPOSE IN A DAY, PER SPORT (ruled 2026-09-09).
#: Three is a ceiling on a list, not a target: a day with two qualifying pairs
#: proposes two, and a day with none proposes none and says so.
MAX_PROPOSALS_PER_SPORT = 3

#: HOW MANY LEGS THE APP PROPOSES. The ruling permits two or three; this
#: proposes TWO, and the reason is the cost printed on every card: the fee per
#: dollar staked is 1.67 times the singles' rate on two 60c legs and 2.8 times
#: on three, measured 2026-09-08. Nothing in the record yet argues for the
#: more expensive shape, and choosing it would be the app taking a view it
#: cannot support. Three-leg proposals are permitted by the ruling and are not
#: made; say so rather than let the absence look like an oversight.
PROPOSAL_LEGS = 2


def price_ceiling(fair: float | None) -> dict:
    """The highest price worth paying for a combo worth `fair`.

    A price is worth paying when what the combo is worth, less the venue's fee
    at that price, beats the price by at least the declared return on stake:

        fair - price - fee(price) >= MIN_RETURN_ON_STAKE * price

    THE SAME TEST A SINGLE FACES, at the same threshold, so "worth taking" is
    one rule in this app rather than two. The search is cent by cent because
    the fee is rounded up to the cent and is therefore a step function; a
    closed form would be a smooth answer to a stepped question.

    Returns the ceiling as a probability and in cents, or None when no price
    clears -- which is the honest answer for a combo whose fair value is so
    low that the fee eats it at every price.
    """
    from .. import config
    from . import recommend

    if fair is None or not 0 < fair < 1:
        return {"ceiling": None, "ceiling_cents": None,
                "minimum_return": config.MIN_RETURN_ON_STAKE}
    best = None
    for cents in range(1, 100):
        price = cents / 100.0
        if fair - price - recommend.fee(price) >= config.MIN_RETURN_ON_STAKE * price:
            best = cents
    return {
        "ceiling": (best / 100.0) if best else None,
        "ceiling_cents": best,
        "minimum_return": config.MIN_RETURN_ON_STAKE,
    }


def propose(entries: list[dict], *, sport: str) -> list[dict]:
    """Up to three combos the app puts forward, from one sport's own legs.

    THE RULES, ALL DECLARED, NONE ABOUT THE ANSWER (ruled 2026-09-09):

      * every leg CLEARS THE BAR ALONE. Not "is interesting" -- the same test
        the Clears group applies, read off the same entry, so a combo can
        never contain a leg the app would not recommend on its own.
      * DIFFERENT GAMES. Two legs from one game price a correlation nobody
        declared, which LAW 2 forbids and no joint model here can supply.
      * ONE SPORT, which is this function's argument and LAW 6's rule: a
        number that mixes two sports describes neither.
      * NO LEG REUSED. A leg in one proposal is spent; the same pick appearing
        in three combos would be one opinion sold three times.

    THE ORDER IS THE LEGS' OWN EDGE, best first, and the pairing is greedy
    from that order. It is not tuned and it is not an optimiser: an optimiser
    would be choosing combinations to make a number look good, which is the
    discovery-by-scanning LAW 2 exists to prevent.
    """
    clearing = [e for e in entries
                if e.get("side") is not None
                and e.get("sport") == sport
                and e.get("fair_value") is not None
                and e.get("game_id")]
    clearing.sort(key=lambda e: (-(e.get("edge_cents") or 0.0),
                                 e.get("prediction_id") or 0))

    proposals: list[dict] = []
    used_games: set[str] = set()
    spent: set[int] = set()
    pool = list(clearing)
    while len(proposals) < MAX_PROPOSALS_PER_SPORT:
        legs: list[dict] = []
        games: set[str] = set()
        for entry in pool:
            if entry["prediction_id"] in spent:
                continue
            if entry["game_id"] in games:
                continue
            legs.append(entry)
            games.add(entry["game_id"])
            if len(legs) == PROPOSAL_LEGS:
                break
        if len(legs) < PROPOSAL_LEGS:
            break
        for entry in legs:
            spent.add(entry["prediction_id"])
        used_games |= games
        fair = fair_value([e["fair_value"] for e in legs])
        ceiling = price_ceiling(fair)
        proposals.append({
            "sport": sport,
            "legs": [{
                "prediction_id": e["prediction_id"],
                "game_id": e["game_id"],
                "market": e.get("market"),
                "fair_value": e["fair_value"],
                "price": e.get("price"),
                "edge_cents": e.get("edge_cents"),
            } for e in legs],
            "leg_ids": [e["prediction_id"] for e in legs],
            "fair": fair,
            **ceiling,
            "singles": singles_alternative(
                [e["price"] for e in legs if e.get("price") is not None],
                [e["fair_value"] for e in legs if e.get("price") is not None]),
        })
    return proposals


def stored_packages(conn: sqlite3.Connection, sport: str,
                    game_ids: list[str]) -> list[sqlite3.Row]:
    """Every package the record has read for these games, newest look first."""
    if not game_ids:
        return []
    placeholders = ",".join("?" for _ in game_ids)
    return conn.execute(
        "SELECT * FROM venue_packages WHERE sport = ?"
        f"   AND (game_ids = '' OR EXISTS (SELECT 1 FROM games g"
        f"        WHERE g.id IN ({placeholders}) AND instr(venue_packages.game_ids, g.id) > 0))"
        " ORDER BY fetched_utc DESC, id DESC",
        [sport] + list(game_ids)).fetchall()


_GAME_NAMES_SQL = (
    "SELECT g.id, g.home, g.away,"
    "       th.display_name AS home_name, ta.display_name AS away_name,"
    "       th.short_name AS home_club, ta.short_name AS away_club,"
    "       th.location AS home_location, ta.location AS away_location"
    "  FROM games g"
    "  LEFT JOIN teams th ON th.sport = g.sport AND th.tricode = g.home"
    "  LEFT JOIN teams ta ON ta.sport = g.sport AND ta.tricode = g.away"
    " WHERE g.id IN (%s)"
)


def club_rows(conn, game_ids: list[str]):
    """Every name the record holds for the clubs in these games, as rows."""
    if not game_ids:
        return []
    return conn.execute(_GAME_NAMES_SQL % ",".join("?" for _ in game_ids),
                        list(game_ids)).fetchall()


def sides_for(rows) -> dict:
    """Which names belong to the home club and which to the away one.

    A LEG NAMES A SIDE, not just a game. "Denver moneyline" and "Kansas City
    moneyline" are the same game and opposite propositions, and a package
    priced without that distinction would be priced on the wrong team half the
    time -- which is the defect this project has already shipped four times in
    other forms.
    """
    out = {}
    for row in rows:
        keys = row.keys() if hasattr(row, "keys") else row
        sides = {"home": [], "away": []}
        for field in NAME_COLUMNS:
            if field not in keys:
                continue
            name = (row[field] or "").strip()
            if name:
                sides["home" if field.startswith("home") else "away"].append(name)
        out[row["id"]] = sides
    return out


def leg_side(leg: str, sides: dict) -> str | None:
    """Which side of its game a leg names, or None when it names both or none."""
    hit = {which for which, names in sides.items()
           for name in names
           if re.search(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])",
                        leg, re.I)}
    return next(iter(hit)) if len(hit) == 1 else None
