"""WHAT A PICK IS, AND THE ORDER EVERYTHING ELSE IS DRAWN IN (operator ruling
B, 2026-10-05; built 2026-10-07).

The ruling, whole (docs/briefs/2026-10-05-rulings.md):

  "B. Picks are ranked by edge, never by chance of hitting (every page).
  1. Edge = model's chance minus the price (Kalshi) or minus the break-even of
  the payout (pick'em), after fees. Chance of hitting alone never ranks
  anything.
  2. A leg is called a pick only if its edge after fees is 3 percentage points
  or more. Below that it is shown as a number, never as a pick.
  3. Every pick and every browse row shows its payout as a multiplier beside
  its chance and edge, e.g. "62% · 2-pick break-even 57.7% · edge +4.3".
  4. No filling. When nothing clears on a slate: "Nothing worth taking today".
  5. Kalshi game markets (spreads, moneylines, totals) stay on the board with
  their numbers, but none carries a pick badge, and none feeds a combo
  proposal, until its market passes its gate."

THE ONE DOOR FOR A PICK AT THE VENUE'S PRICE (`judge`). A priced entry
(`recommend.for_predictions`) is a pick only where all of these hold, the
conservative reading recorded in docs/REPAIR_STATE.md: the recommendation
writer's own bar picked a side for it (the fee and the five per cent return
of `recommend.clears_the_bar`, which stays in force -- B.2 says "only if", a
condition, not the whole of one); its edge after fees on that side is three
points or more (B.2, `config.PICK_MIN_EDGE`, C's bar, one for both venues);
and, being a Kalshi game market, its market has passed B.5's gate -- its
at-the-line record's settled comparisons, this forecaster's, on the
distinct-bet key, after A.2's exclusion, at `config.GAME_MARKET_PICK_GATE`
(`market_gate`). A Kalshi-priced market that is not a game market has no
at-the-line record to pass a gate on, and is no pick (none is priced today).
A pick'em leg is C's (`board._leg`), against the same bar.

THE WRITER IS NOT CHANGED (reading (d)): `recommend.record_for` records what
it recorded before, and the closing line's measurement rests on those rows.
The PAGE draws a recommendation that is not a pick with its numbers only --
no badge, no outline, no "Model's pick", no size, never in a combo -- and the
words beside it say why (`language.not_a_pick_words`).

THE ORDER (readings (a) and (b), with THE_SHORTLIST S1's "the edge moves no
ordering until its market has earned one"): a pick is ranked by its edge
after fees, best first; anything that is not a pick is ordered by its start
and then a fixed, declared market order (`config.SPORT_MARKETS`), never by
the model's chance and never by an edge its market has not earned
(`browse_key`). The shortlist ranker orders QUESTIONS for the shortlist by
its own declared inputs and rulings, and is not this; where a page draws in
its order, the page orders itself here.
"""

from __future__ import annotations

import math
import sqlite3

from . import config

#: THE KALSHI GAME MARKETS B.5 NAMES: spreads, moneylines, totals -- the
#: markets whose claims the at-the-line record counts as bets
#: (`at_the_line.BET_MARKETS`, held equal by a test).
GAME_MARKETS = ("spread", "total", "moneyline")

#: FLOAT NOISE, NOT A MARGIN (C's prover's rule, 2026-10-06): an edge of
#: exactly three points can be worked out a hair under it, and nothing a model
#: states is finer than a billionth of a probability.
FLOAT_NOISE = 1e-9


def clears_the_pick_bar(edge: float | None) -> bool:
    """B.2: three percentage points or more, read on the edge as worked out
    (a share of a dollar, 0.03), less float noise only. One bar for a
    pick'em leg (`board.clears_the_pick_bar`, which asks here) and a Kalshi
    pick (`judge`)."""
    return edge is not None and float(edge) >= config.PICK_MIN_EDGE - FLOAT_NOISE


def drawn_edge(points: float | None, shown: float | None = None) -> float | None:
    """The edge a page may DRAW, in points: the figure as the page has always
    drawn it (`shown`, the engine's two places, `recommend.edge_cents`, where
    it has one; `points` otherwise), except that an edge under the bar is
    never drawn at it (reading (c), 2026-10-07: C's prover found "edge +3.0"
    on legs at 2.95-2.99999 points, each of which rounds to 3.0 at a tenth
    and is no pick). Such a figure is drawn at the tenth below its unrounded
    `points` -- 2.97 as 2.9 -- and every other figure as it was, the
    composer rounding it to a tenth."""
    if points is None and shown is None:
        return None
    exact = float(points if points is not None else shown)
    said = float(shown if shown is not None else exact)
    bar = config.PICK_MIN_EDGE * 100.0
    if exact < bar - FLOAT_NOISE * 100.0 and round(said, 1) >= bar:
        return math.floor(exact * 10.0) / 10.0
    return said


def market_gate(conn: sqlite3.Connection, *, sport: str, market: str | None,
                predictor: str | None, game_id: str | None,
                cache: dict | None = None) -> dict:
    """B.5's gate for one Kalshi game market, one forecaster and -- for a
    sport that splits below the market -- the card `game_id` is on: the
    at-the-line record's settled comparisons, through its one door
    (`at_the_line.standing_claims`, one claim per distinct bet, none priced
    across two contracts), against `config.GAME_MARKET_PICK_GATE`.

    THE CARD'S OWN COUNT (`views._at_the_line`'s, the curve's on the Record
    page), asked once per market, forecaster and card (`cache`). A market
    that is not a game market, or a forecaster neither of the two, has no
    such record: `game_market` False and nothing counted."""
    from . import calibration
    from .market import at_the_line

    gate = config.GAME_MARKET_PICK_GATE
    if market not in GAME_MARKETS or predictor not in at_the_line.FORECASTERS:
        return {"game_market": False, "market": market, "predictor": predictor,
                "event_tier": None, "n": 0, "gate": gate, "passes": False}
    tier = at_the_line.event_tier_of(conn, sport, game_id) if game_id else None
    key = (sport, market, predictor, tier)
    if cache is not None and key in cache:
        return cache[key]
    if config.event_tiers(sport) and tier is None:
        n = 0            # a bout on a card of no declared tier is in no count
    else:
        standing = at_the_line.standing_claims(
            conn, sport=sport, market=market, predictor=predictor, event_tier=tier)
        calibration.refuse_a_comparison_across_two_contracts(
            conn, [c["id"] for c in standing],
            what=f"B.5's gate for {sport} {market}, {predictor}")
        n = len(at_the_line.settled(standing))
    out = {"game_market": True, "market": market, "predictor": predictor,
           "event_tier": tier, "n": n, "gate": gate, "passes": n >= gate}
    if cache is not None:
        cache[key] = out
    return out


def judge(conn: sqlite3.Connection, entry: dict, *, sport: str,
          predictor: str | None = None, cache: dict | None = None) -> dict:
    """Whether a priced entry is a pick, and in words why it is not.

    `entry` is `recommend.for_predictions`' (as the page draws it): its side
    (the writer's bar), its unrounded edge in points (`edge_points`), its
    market and game. Returns {pick, why, edge_points, gate, words}: `why` is
    'pick', 'no_side' (the writer's bar picked no side -- a watched card,
    whose figure on its face says so), 'not_a_game_market', 'gate' or 'bar';
    `words` say it for a recommendation that is not a pick (reading (d)),
    and are None otherwise."""
    from . import language

    side = entry.get("side")
    points = entry.get("edge_points")
    if points is None and entry.get("edge_cents") is not None and side is not None:
        # AN ENTRY MADE BEFORE `edge_points` OR BY HAND: its two places are
        # the nearest the page can come, and are read as they are.
        points = float(entry["edge_cents"])
    gate = market_gate(conn, sport=sport, market=entry.get("market"),
                       predictor=predictor or entry.get("predictor"),
                       game_id=entry.get("game_id"), cache=cache)
    under = not clears_the_pick_bar(None if points is None else points / 100.0)
    if side not in ("yes", "no"):
        why = "no_side"
    elif not gate["game_market"]:
        why = "not_a_game_market"
    elif not gate["passes"]:
        why = "gate"
    elif under:
        why = "bar"
    else:
        why = "pick"
    words = None
    if why in ("not_a_game_market", "gate", "bar"):
        # WHOSE COUNT, IN THE RECORD PAGE'S LABEL (the prover of ruling B,
        # 2026-10-07): the market at the venue's line, its card for UFC and
        # the forecaster -- the curve whose n the gate is.
        category = (language.at_the_line_category_label(
            gate["market"], gate["predictor"], gate["event_tier"])
            if gate["game_market"] else None)
        words = language.not_a_pick_words(
            game_market=gate["game_market"], n=gate["n"], gate=gate["gate"],
            passes=gate["passes"], edge_points=drawn_edge(points),
            under_the_bar=under, category=category)
    return {"pick": why == "pick", "why": why, "edge_points": points,
            "gate": gate, "words": words}


def market_rank(sport: str, market: str | None) -> int:
    """A market's place in its sport's declared order (`config.SPORT_MARKETS`:
    a prop by its type), a market not declared after every one that is."""
    order = config.SPORT_MARKETS.get(sport, ())
    return order.index(market) if market in order else len(order)


def browse_key(sport: str, *, start_order: tuple, game_id: str | None,
               market: str | None, subject: str | None, line,
               prediction_id) -> tuple:
    """THE ORDER OF EVERYTHING THAT IS NOT A PICK (reading (b), 2026-10-07):
    its start (`start_order`, an instant's sort key -- `board._start_order`)
    and its game (two games starting together, as the board's rows order
    them), then the sport's declared market order, then the question's
    subject and the line it was asked at, then its number -- never the
    model's chance, and never an edge, which in a market that has not passed
    its gate is mostly the model's error (S1)."""
    try:
        at = float(line)
    except (TypeError, ValueError):
        at = math.inf
    return (start_order, str(game_id or ""), market_rank(sport, market),
            str(subject or ""), at,
            prediction_id if prediction_id is not None else 0)


def pick_key(edge_points: float | None, prediction_id) -> tuple:
    """THE ORDER OF PICKS: by edge after fees, best first, the question's
    number breaking a tie (B.1: "Chance of hitting alone never ranks
    anything")."""
    return (-(edge_points if edge_points is not None else -math.inf),
            prediction_id if prediction_id is not None else 0)
