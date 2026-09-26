"""The recommendation: fair value, the price, the edge after fees, and a size.

LAW 5 as amended 2026-09-07 permits this arithmetic and forbids the machinery
around it. Nothing here authenticates, places, cancels or reads an account, and
nothing here knows what a unit is worth in money -- the operator maps units to
money outside this codebase, which is where his ledger lives.

WHAT THE APP CAN ACTUALLY IMPROVE. The operator wagers either way. The two
failures a tool like this can reduce are paying a price that does not clear the
fee, and staking more on a signal because it feels stronger. So:

  * An edge is computed AFTER the venue's fee and is reported as no edge when
    it does not clear it. A one-cent edge that costs two cents to take is not
    a small edge; it is a loss with a decoration.
  * BELOW A MARKET'S GATE THE SIZE IS A FLAT UNIT, and the same flat unit for a
    62% claim as for a 92% one. This is the single most important line in the
    module. Variable sizing multiplies the consequences of a probability that
    has never been checked, and no market on this record has passed its
    hundred-resolution gate yet, so today every recommendation is a flat unit.
  * Above the gate the fraction is a QUARTER of Kelly, and full Kelly is not
    reachable from here at any sample size. Kelly assumes the probability is
    right; on a probability ten points wrong it compounds toward ruin rather
    than growth, and quarter-Kelly is the standard concession to that.
  * PACKAGES ARE GRADED, NEVER BUILT, and not here. `price_parlay` stood in
    this module until 2026-09-08 and refused every multi-leg price outright;
    LAW 5 as amended lets the engine price a package the VENUE published, so
    the blanket refusal was retired by name and replaced by four graded ones
    in `market.combos` -- same-game, cross-sport, four-leg, and a leg this
    record does not forecast. The arithmetic in the old refusal is not
    retracted: the fee per dollar is 1.67 to 2.8 times a single's, measured,
    which is why `combos.singles_alternative` prints on every package.
  * NOTHING IS SIZED IN-GAME. The poller's score can be ninety seconds stale
    while the venue prices off the live feed, so a live recommendation is
    adversely selected by construction.
"""
from __future__ import annotations

import sqlite3

from .. import config, correction
from ..db import just_after, transaction, utcnow
from ..priced import coverage
from . import paper


class NotSizedInGame(RuntimeError):
    """A live market was sized. The score this app holds is older than the price."""


def fair_value(model_prob: float | None) -> float | None:
    """The model's probability, as the price it corresponds to."""
    if model_prob is None:
        return None
    return round(float(model_prob), 4)


def fee(price: float) -> float:
    """The venue's charge on one contract at this price.

    One implementation, shared with the hypothetical ledger: a fee that differs
    between what the record reports and what a recommendation is priced on
    would make the two disagree about the same wager.
    """
    return paper.fee_per_contract(price)


def _cost_of(side: str, price: float) -> float:
    """What one contract of `side` costs, from the venue's YES price: the
    price itself on the yes side, the rest of the dollar on the no side.

    ONE ORIENTATION FOR THE EDGE AND THE RETURN (GRIDIRON_REPAIR item 4,
    2026-09-26). `edge_cents` worked the cost out for itself and the bar
    did not work it out at all -- it divided by the yes price whichever side
    the edge was on -- so the two disagreed about what a no-side contract
    costs. Both ask here now. A side that is neither is refused by name
    rather than read as the no side, which is what the old `else:` did.
    """
    if side == "yes":
        return float(price)
    if side == "no":
        return 1.0 - float(price)
    raise ValueError(f"a side is 'yes' or 'no', not {side!r}")


def edge_cents(model_prob: float | None, price: float | None,
               side: str) -> float | None:
    """What one contract is worth after the fee, in cents.

    The yes side costs `price` and returns a dollar if it happens; the no side
    costs the rest of the dollar. Both are the same subtraction, and the fee is
    charged either way -- which is the whole reason a small edge is usually not
    one. The side has no default (2026-09-26): the one caller names it, and a
    default is how the bar came to assume one.
    """
    if model_prob is None or price is None or not 0 < price < 1:
        return None
    cost = _cost_of(side, price)
    worth = float(model_prob) if side == "yes" else 1.0 - float(model_prob)
    return round((worth - cost - fee(cost)) * 100.0, 2)


def side_for(model_prob: float | None, price: float | None) -> dict:
    """Which side of a question clears the fee, if either does.

    MOST QUESTIONS GET NO SIDE, and that is the intended answer rather than a
    failure to find one. A page that produced twenty opinions a day would be
    manufacturing them.
    """
    yes, no = edge_cents(model_prob, price, "yes"), edge_cents(model_prob, price, "no")
    if yes is None or no is None:
        return {"side": None, "edge_cents": None,
                "why": "no recorded price to compare against"}
    best_side, best = ("yes", yes) if yes >= no else ("no", no)
    if best < config.MIN_EDGE_CENTS:
        return {"side": None, "edge_cents": round(best, 2),
                "why": (f"neither side clears the fee: the better of the two is "
                        f"{best:+.1f} cents after it")}
    return {"side": best_side, "edge_cents": round(best, 2),
            "why": f"{best:+.1f} cents a contract after the venue's fee"}


def return_on_stake(edge_cents: float | None, price: float | None, *,
                    side: str | None) -> float | None:
    """The edge as a share of the money put up, not as cents on a contract.

    THE TWO NUMBERS DISAGREE ABOUT WHICH BET IS BETTER, which is the whole
    reason this exists. Two cents on an 89-cent contract and two cents on a
    20-cent one are the same edge and are 2.2% and 10% on the stake; the
    second is worth four and a half times as much per dollar risked.

    THE MONEY PUT UP IS WHAT THE SIDE TAKEN COSTS (GRIDIRON_REPAIR item 4,
    the operator's ruling of 2026-09-23: "a no-side edge divides by the
    no-side cost"; built 2026-09-26). `price` is the venue's YES price, and
    until this date it was the divisor whichever side the edge was on. A
    no-side contract costs the rest of the dollar, so below a 50c yes price
    a no-side edge read larger than it was: THE READ of 2026-09-23 found
    recs 3, 10 and 26 cleared the 5% bar at 5.6%, 6.1% and 7.2% of the yes
    price and are 3.3%, 3.7% and 4.7% of what the no side cost -- and rec 56
    did the same on 24 September. Above 50c it read smaller, and a real edge
    was refused. `side` is required and has no default, so a caller that
    forgets it is a TypeError rather than a yes price.

    None where an input is missing or the side is not known, because absent
    and zero are different facts here as everywhere else in this project.
    """
    if edge_cents is None or price is None or side is None \
            or not 0 < price < 1:
        return None
    return round((float(edge_cents) / 100.0) / _cost_of(side, price), 4)


def payout_multiple(price: float | None) -> float | None:
    """What one unit returns if the contract settles at a dollar.

    A contract at 84 cents pays 1.19 times the stake. This is arithmetic on a
    published price and nothing else: no balance is read, nothing is placed,
    and the number is the same whether or not anybody acts on it.
    """
    if price is None or price <= 0:
        return None
    return round(1.0 / float(price), 3)


def clears_the_bar(edge_cents: float | None, price: float | None, *,
                   side: str | None) -> dict:
    """Both conditions, in one place, with the reason it failed in words.

    ONE DOOR, for the same reason `refuse_in_game` is one: two callers deciding
    what "clears the bar" means is how a page starts disagreeing with itself
    about which group a pick belongs in.

    `price` is the yes price and `side` the side the edge is on; the return is
    on what that side costs (`return_on_stake`, 2026-09-26), and the words
    name that cost, to the tenth of a cent where it has one -- the yes price
    rounded to a whole cent named 62c for a contract that cost 62.5c, and 50c
    for one that cost 49.5c.
    """
    got = return_on_stake(edge_cents, price, side=side)
    if got is None:
        return {"clears": False, "return_on_stake": None,
                "why": "no recorded price to compare against"}
    cost = _cents(_cost_of(side, price))
    if got < config.MIN_RETURN_ON_STAKE:
        return {
            "clears": False,
            "return_on_stake": got,
            "why": (f"the price is wrong by {edge_cents:+.1f}¢ and that is "
                    f"{got * 100:.1f}% of the {cost}¢ it costs, "
                    f"under the {config.MIN_RETURN_ON_STAKE * 100:.0f}% this "
                    f"app asks for before it calls something worth the click"),
        }
    return {"clears": True, "return_on_stake": got,
            "why": (f"{got * 100:.1f}% of the {cost}¢ it costs, "
                    f"after the venue's fee")}


def _cents(share: float) -> str:
    """A cost in cents as a reader says it: 62.5, 89, never 89.0."""
    return f"{share * 100:.1f}".rstrip("0").rstrip(".")


def kelly_fraction(model_prob: float, price: float) -> float:
    """The full Kelly fraction, which this module never recommends.

    Computed because a quarter of it has to come from somewhere, and named
    honestly so nobody has to reverse-engineer what the quarter is a quarter
    of. `size_for` is the only caller and it always takes the quarter.
    """
    if not 0 < price < 1:
        return 0.0
    odds = (1.0 - price) / price          # net return per unit staked
    edge = odds * model_prob - (1.0 - model_prob)
    return max(0.0, edge / odds) if odds else 0.0


def size_for(*, model_prob: float | None, price: float | None,
             settled: int, measured_edge: bool | None = None) -> dict:
    """How much, in units, and why.

    TWO CONDITIONS, NOT ONE, and the second was missing for an afternoon. The
    fraction needs a market with its hundred settled questions AND a measured
    edge that is in the model's favour. A hundred settled questions is how an
    edge gets measured; it is not what makes one positive, and baseball
    moneyline is exactly the case where sizing on the sample alone would stake
    more BECAUSE the record has proved the model behind: on the 74 settled
    questions that had a price beside them, the model's Brier score is 0.2527
    against the market's 0.2412, lower being better.

    THE NUMBER IN THIS PARAGRAPH WAS 286 UNTIL 2026-09-07, and it was the
    sport's settled count across every market rather than this comparison's N.
    Re-measured against the live record, which `meta.kind` confirms is the
    forward database and not a backtest.

    BELOW EITHER CONDITION, THE ANSWER DOES NOT DEPEND ON THE PROBABILITY. A
    92% claim and a 62% claim get the same flat unit, and a caller cannot ask
    for more: the function takes no multiplier and returns the declared unit
    unchanged. `plant.py` proves it by asking twice with different confidence.
    """
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    if model_prob is None or price is None or not 0 < price < 1:
        return {"kind": "none", "units": 0.0, "fraction": 0.0, "gate_n": settled,
                "gated": settled >= gate,
                "why": "no recorded price, so nothing is sized"}
    if settled < gate:
        return {
            "kind": "flat",
            "units": config.FLAT_UNIT,
            "fraction": None,
            "gate_n": settled,
            "gated": False,
            "why": (f"no measured edge yet: {settled} of {gate} settled in "
                    f"this market"),
        }
    if not measured_edge:
        return {
            "kind": "flat",
            "units": config.FLAT_UNIT,
            "fraction": None,
            "gate_n": settled,
            "gated": False,
            "why": (f"measured and NOT ahead: {settled} settled here, and the "
                    f"market's own prices score at least as well as the "
                    f"model's on them"),
        }
    quarter = config.KELLY_FRACTION * kelly_fraction(model_prob, price)
    capped = min(quarter, config.MAX_FRACTION)
    return {
        "kind": "fraction",
        "units": round(capped * config.BANKROLL_UNITS, 3),
        "fraction": round(capped, 5),
        "gate_n": settled,
        "gated": True,
        "why": (f"a quarter of Kelly, capped at {config.MAX_FRACTION:.1%} of the "
                f"declared bankroll ({settled} settled in this market)"),
    }


# RETIRED 2026-09-08: `price_parlay` and its `SinglesOnly` stood here and
# refused to put a number on any multi-leg price at all. LAW 5 as amended
# permits pricing a package the venue itself published, so a function whose
# whole body was a refusal now refuses something the law allows. It is gone,
# and `market.combos.classify` carries the four refusals that replaced it --
# each one about a shape rather than about the count of legs.
#
# The four are planted: `plant_a_priced_same_game_package`,
# `plant_a_priced_cross_sport_package`, `plant_a_priced_four_leg_package`,
# `plant_a_priced_package_with_an_unforecast_leg`.


#: WHAT THIS RECORD CALLS A GAME THAT HAS STARTED. The schema's own word is
#: "in", and the first version of this rule looked for "in_progress" -- a
#: status this database cannot hold. The guard would have passed every live
#: game in the record. Caught by a test that used a real status.
IN_PLAY_STATUSES = ("in", "in_progress", "live", "in progress")


def refuse_in_game(game_status: str | None) -> None:
    """Nothing is sized once a game is under way."""
    if (game_status or "").lower() in IN_PLAY_STATUSES:
        raise NotSizedInGame(
            "NOT SIZED IN-GAME (LAW 5): the score this app holds can be ninety "
            "seconds behind the venue's, which prices off the live feed. A "
            "recommendation made from the slower of two clocks is adversely "
            "selected by construction; the live win probability is shown and "
            "never sized.")


def correction_instant(claim_utc: str | None, status: str | None,
                       kickoff_utc: str | None) -> str | None:
    """Which correction a number read from this claim is corrected by: None,
    meaning the one in force now, before the game starts; the claim's own
    instant once it has.

    ONE RULE FOR THE PICK AND THE WORDS BESIDE IT (the prover of
    GRIDIRON_REPAIR item 3, 2026-09-26). `for_predictions` prices every
    shortlisted question whose game is not being played -- a finished one
    included, which the Today block and the recommendation lines still show
    -- and it corrected all of them by the correction in force NOW. Measured
    on a scratch world: a baseball pick on a game that ended on 9 September,
    on the no side as written and recorded, moved to the yes side when a
    correction activated on the 20th, while the at-the-line sentence on the
    same card, which already read the claim's own instant once the game had
    started, kept the claim's 43%. That is a finished game re-derived by a
    correction that did not exist when it was played, which the ruling
    forbids ("Re-derive nothing retroactively (LAW 3)").

    BEFORE THE START, NOW: that is the correction a recommendation written
    now carries (`record_for`). ONCE IT HAS STARTED, the claim's own instant:
    nothing can be recommended on a game in play or over, so the number is
    the one the claim stood for when it was written, and an activation
    afterwards never reaches it. `views` reads the at-the-line sentence by
    this rule too, so the pick and the words beside it cannot disagree.
    """
    started = ((status or "").lower() in IN_PLAY_STATUSES + ("final",)
               or (kickoff_utc is not None and kickoff_utc <= utcnow()))
    return claim_utc if started else None


def for_predictions(conn: sqlite3.Connection, prediction_ids: list[int]) -> list[dict]:
    """One recommendation per shortlisted question that has a recorded price.

    Reads the frozen prediction, the price already stored beside it and the
    market's settled count. Computes nothing about a game in progress and
    writes nothing anywhere: a recommendation is a reading of rows that already
    exist.

    The model's number is the claim at the line CORRECTED by the correction in
    force now, through `correction.shown_proposition` (2026-09-26); the raw
    claim's number and the version travel with each entry. NOW BEFORE THE
    START, and the claim's own instant once the game has started
    (`correction_instant`, the prover of 2026-09-26), so a finished game's
    pick is never re-derived by a correction that activated after it.
    """
    from .. import shortlist as ranker
    from ..priced import shape as _shapes

    if not prediction_ids:
        return []
    placeholders = ",".join("?" for _ in prediction_ids)
    # ONE VENUE, END TO END. The price comes from the at-the-line claim -- the
    # model's own frozen distribution read at the venue's number, and the
    # venue's price for that same proposition -- so the fee subtracted below
    # belongs to the venue whose price it is.
    #
    # IT USED TO READ `market_snapshots`, which on this record is mostly a
    # bookmaker's line republished by a media API. Pricing against that while
    # charging an exchange's fee and measuring coverage from the exchange's
    # ladders is three venues in one sentence, and the middle one is not
    # tradeable: a book's implied probability carries its own margin.
    rows = conn.execute(
        "SELECT p.id, p.sport, p.game_id, p.market_type, p.prop_type, p.subject,"
        " p.line_asked, p.model_prob, p.model_side, p.predictor, p.created_utc,"
        " g.status, g.kickoff_utc, g.home, g.away,"
        " c.model_prob AS claim_prob, c.venue_implied AS implied_prob,"
        " c.line AS venue_line, c.venue AS venue, c.created_utc AS claim_utc"
        f" FROM predictions p JOIN games g ON g.id = p.game_id"
        " LEFT JOIN at_the_line_claims c ON c.id = ("
        "     SELECT c2.id FROM at_the_line_claims c2"
        "      WHERE c2.prediction_id = p.id"
        "        AND (g.kickoff_utc IS NULL OR c2.created_utc < g.kickoff_utc)"
        "      ORDER BY c2.created_utc DESC, c2.id DESC LIMIT 1)"
        f" WHERE p.id IN ({placeholders})"
        # A VOIDED FORECAST IS NEVER A LIVE PICK (ruling 1, 2026-09-24). The
        # page passes only standing cards, but a caller handed a voided id
        # must get nothing back rather than a price and a size for it.
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)",
        list(prediction_ids)).fetchall()
    ranks = ranker.ranks_for(conn, prediction_ids)

    out = []
    for row in rows:
        rank = ranks.get(row["id"])
        if rank is None or not rank["on_shortlist"]:
            continue
        try:
            # ONE DOOR FOR THE IN-GAME RULE. The check could be inlined here in
            # a line, and then there would be two places that decide what
            # "under way" means. `refuse_in_game` raises; this is the only
            # caller that turns the refusal into a skip.
            refuse_in_game(row["status"])
        except NotSizedInGame:
            continue
        price = row["implied_prob"]
        # THE MODEL'S NUMBER FOR THE VENUE'S QUESTION, which is not the same as
        # its number for our own. The claim carries the frozen distribution
        # read at the venue's line; the prediction's probability answers a
        # question asked at ours, and comparing that with the venue's price
        # would be comparing two different propositions.
        #
        # CORRECTED, THROUGH THE ONE DOOR (GRIDIRON_REPAIR item 3; the
        # operator's ruling of 2026-09-23, built 2026-09-26: "recommend.py:324
        # reads the corrected probability, never the raw claim"). Until this
        # date the raw claim went straight to the side, the edge, the bar and
        # the size, so a category whose correction was in force would have
        # shown one number on the forecast and priced another. The correction
        # in force for this forecaster's category NOW -- which, for the row
        # `record_for` writes, is no later than the row's own stamp -- turned
        # to the side the claim favours and back (`shown_proposition`). A fit
        # the holdout did not activate is never applied. The raw claim stays
        # beside it, and is what `fair_value` stores.
        #
        # NOW ONLY BEFORE THE START (the prover, 2026-09-26). A finished game
        # is priced here too, and "now" let a correction activated after the
        # game turn its pick; once the game has started the number is the
        # claim's as it stood when written (`correction_instant`), the rule
        # the at-the-line sentence beside it already read.
        raw_claim = row["claim_prob"]
        model_prob, correction_version = (
            (None, None) if raw_claim is None else correction.shown_proposition(
                conn, sport=row["sport"], market_type=row["market_type"],
                forecaster=row["predictor"], proposition=raw_claim,
                at_utc=correction_instant(row["claim_utc"], row["status"],
                                          row["kickoff_utc"])))
        settled = rank["edge_gate_n"] or 0
        # COVERAGE FIRST (THE_PRICED P2/P5, 2026-09-07). A market the engine is
        # not allowed to price gets a forecast and no opinion, and the reason
        # travels with it: not measured, too busy, too wide, or stopped by its
        # own closing line.
        allowed = coverage.priceable(conn, row["sport"],
                                     row["prop_type"] or row["market_type"])
        chosen = (side_for(model_prob, price) if allowed["priceable"]
                  else {"side": None, "edge_cents": None, "why": allowed["why"]})
        # THE SECOND CONDITION (F2b, 2026-09-07). Applied AFTER the side is
        # chosen and never inside `side_for`, because the edge in cents is
        # still true and still shown -- what changes is whether the pick is
        # called worth taking. The edge survives into the watched group with
        # its number on its face.
        # WHICH SIDE THE EDGE IS ON, kept whatever happens next. A pick that
        # fails the return test is still shown, with the same number on its
        # face, and a number with no side is the defect this project has had
        # more often than any other.
        edge_side = chosen["side"]
        # ON WHAT THE SIDE COSTS (GRIDIRON_REPAIR item 4, 2026-09-26). This
        # line asked the bar with the yes price whichever side the edge was
        # on; a no-side edge is now divided by the no side's cost. With no
        # side -- the fee not cleared, or the market not covered -- there is
        # no return to state, and none is (`chosen` already says why).
        stake = clears_the_bar(chosen.get("edge_cents"), price, side=edge_side)
        if chosen["side"] is not None and not stake["clears"]:
            chosen = {"side": None, "edge_cents": chosen["edge_cents"],
                      "why": stake["why"]}
        ahead = measured_edge(conn, sport=row["sport"],
                              market_type=row["market_type"],
                              prop_type=row["prop_type"],
                              predictor=row["predictor"])
        size = size_for(model_prob=model_prob, price=price,
                        settled=settled, measured_edge=ahead["ahead"])
        out.append({
            "prediction_id": row["id"],
            "sport": row["sport"],
            "game_id": row["game_id"],
            "market": row["prop_type"] or row["market_type"],
            "subject": row["subject"],
            "line_asked": row["line_asked"],
            "model_side": row["model_side"],
            # THE NUMBER THE SIDE WAS CHOSEN FROM, corrected where a
            # correction is in force: the card's model chip, the recommendation
            # line, a combo's legs and a package's legs all read this, so they
            # agree with the pick without a second door (2026-09-26).
            "fair_value": fair_value(model_prob),
            # ...and the raw claim's number beside it, with the version that
            # made the difference (None while the category is raw). The record
            # keeps both, as a forecast keeps its raw and its shown claim.
            "raw_fair_value": fair_value(raw_claim),
            "correction_version": correction_version,
            "venue": row["venue"],
            "venue_line": row["venue_line"],
            "price": round(price, 4) if price is not None else None,
            "edge_cents": chosen["edge_cents"],
            "side": chosen["side"],
            # The side the EDGE belongs to, which outlives the recommendation:
            # `side` is None for a pick that does not clear the bar and this
            # is not, because the card still shows the number.
            "edge_side": edge_side,
            "side_why": chosen["why"],
            # WHAT THE EDGE IS WORTH PER DOLLAR RISKED, and what the contract
            # pays if it settles at a dollar. Both are arithmetic on the
            # recorded price, carried here so the card does not do arithmetic
            # of its own (F2b).
            # WHICH SIDE THE CARD'S WORDS NAME. A claim is stored from one
            # fixed proposition so a curve compares like with like; a card
            # names the side the model took. When those are opposites, a card
            # that shows the claim's numbers under the question's words names
            # one team and prices the other -- which it did on the first slate
            # that ever produced a recommendation.
            "question_takes_the_proposition": _shapes.question_takes_the_proposition(
                row, row, quantity=_quantity_of(row)),
            "return_on_stake": stake["return_on_stake"],
            "return_minimum": config.MIN_RETURN_ON_STAKE,
            "payout": payout_multiple(price),
            "size": size,
            "gate_n": settled,
            "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
            "measured_edge": ahead,
            "coverage": allowed,
            "written_utc": row["created_utc"],
        })
    return out


#: The proposition a claim in each market is stored from, which is what the
#: quantity names. Declared here rather than read off the claim row, because a
#: question with no claim still has to be oriented on the card.
_QUANTITY = {"spread": "home_margin", "moneyline": "home_win",
             "total": "total", "prop": "count"}


def _quantity_of(row) -> str:
    return _QUANTITY.get(row["market_type"], "")


def measured_edge(conn: sqlite3.Connection, *, sport: str, market_type: str,
                  prop_type: str | None, predictor: str) -> dict:
    """Is the model actually ahead of the market on this market's own record?

    THE COMPARISON THE RECORD PAGE ALREADY MAKES: the model's Brier score
    against the market's, on the same questions, where a line existed. Lower is
    better, so the model is ahead when its score is the smaller one.

    None where nothing has settled with a line beside it -- absent, not false,
    because "we have never checked" and "we checked and it lost" are different
    facts and only one of them is a finding.
    """
    from .. import calibration

    curve = calibration.curve(conn, sport=sport, market_type=market_type,
                              prop_type=prop_type, predictor=predictor)
    market = (curve.get("baselines") or {}).get("market") or {}
    ours = (curve.get("baselines") or {}).get("model_on_market_subset") or {}
    n = market.get("n") or 0
    if not n or market.get("brier") is None or ours.get("brier") is None:
        return {"ahead": None, "n": n, "model_brier": ours.get("brier"),
                "market_brier": market.get("brier"),
                "why": "nothing has settled here with a price beside it"}
    ahead = ours["brier"] < market["brier"]
    return {
        "ahead": ahead,
        "n": n,
        "model_brier": ours["brier"],
        "market_brier": market["brier"],
        "why": (f"on {n} settled questions with a price, the model scores "
                f"{ours['brier']} against the market's {market['brier']}, "
                f"lower being better"),
    }


# ---------------------------------------------------------------------------
# ONE RECOMMENDATION PER GAME AND MARKET, AND NEVER BOTH SIDES
# (GRIDIRON_REPAIR item 5, the operator's ruling of 2026-09-23, built
# 2026-09-26: "One recommendation per game and market, and never both sides.
# Recs 45 and 46 are the planting.")
# ---------------------------------------------------------------------------
#
# THE DEFECT. `record_for` wrote a row for every forecast whose pick cleared
# the bar, and the only refusal on the table was one forecast written twice
# in one second. So the morning and final passes each recorded the same game
# and market -- twelve pairs by THE READ of 2026-09-23, seventeen by
# 2026-09-26 -- and two forecasters in one pass each recorded their own
# side: recs 45 and 46, Toronto at Baltimore over 7.5 from the statistical
# pass and under 7.5 from the reasoning pass, both at 48.5c, a certain loss
# of two fees.
#
# THE RULE IS DECIDED HERE, ONCE (`one_per_game_and_market`), and the
# schema's `recommendation_one_per_game_and_market` refuses a second row
# however it is written:
#   * a game and market that already hold a standing recommendation get no
#     second one, on either side, from any later pass or forecaster;
#   * when one pass would recommend BOTH sides of a game and market -- two
#     forecasters, or two rungs, disagreeing -- it recommends NEITHER, and
#     says so: the conservative default, because the ruling names no
#     survivor, and the app's two opinions cancelling is not an opinion;
#   * several picks on one side in one pass: the forecast written first is
#     recommended, and the others are not added.
# "The market" is the table's own `market` -- the market type, or the prop
# type for a prop -- whatever the rung or the player: the ruling's words
# read literally, which is also the stricter reading. No prop is priced
# today, so no case on the record turns on it.
#
# A WITHDRAWN RECOMMENDATION DOES NOT STAND (`not_withdrawn`): a game and
# market whose only recommendation was withdrawn may be recommended again,
# as NFL spreads 73, 75, 76 and 78 were after 62, 63, 64 and 66.
#
# NOTHING ALREADY WRITTEN IS TOUCHED (LAW 3). The pairs written before the
# fix stand as written and are counted as written: the ruling names none of
# them, and whether they should be counted once is the operator's question
# (docs/REPAIR_STATE.md, question 12). Whether the page follows the record
# is question 11; until it is ruled, the rule binds what is written.

#: THE RULING'S WORDS, which the schema's refusal carries too: `record_for`
#: knows that refusal by them, never by "UNIQUE", which would file it under
#: a forecast written twice.
ONE_PER_GAME_AND_MARKET = "one recommendation per game and market"

#: Why a pick that cleared the bar was not written, in words. Kept with the
#: run (`record_for`'s `refused`, in the predict and final tasks' payload).
STANDS_WHY = ("not written: " + ONE_PER_GAME_AND_MARKET + ", and this one "
              "already has recommendation {id} standing -- the {side} side "
              "at {price}¢, written {when} -- so no second is added on "
              "either side (the operator's ruling of 2026-09-23)")
FIRST_IN_THE_PASS_WHY = ("not written: " + ONE_PER_GAME_AND_MARKET + ", and "
                         "this pass recommends this one once, on the {side} "
                         "side, from the forecast it wrote first (the "
                         "operator's ruling of 2026-09-23)")
BOTH_SIDES_WHY = ("not written: this pass's forecasts take both sides of "
                  "this game and market -- {yes} on the yes side and {no} "
                  "on the no side -- and a game and market are never "
                  "recommended on both sides, so neither side is (the "
                  "operator's ruling of 2026-09-23)")
REFUSED_BY_THE_RECORD_WHY = ("not written: the record refused it -- "
                             + ONE_PER_GAME_AND_MARKET + ", and another was "
                             "written on this game and market first")


def standing_recommendations(conn: sqlite3.Connection, game_id: str,
                             market: str) -> list[dict]:
    """The recommendations standing on one game and market, first first.

    FIRST BY ITS STAMP, THEN ITS ID: recs 45 and 46 were written in the same
    second, and "first" must not depend on the order SQLite hands rows back.
    Through the door (`not_withdrawn`), so a withdrawn one never stands.
    More than one comes back only for a pair written before 2026-09-26,
    which stands as written.
    """
    return [dict(r) for r in conn.execute(
        "SELECT r.id, r.prediction_id, r.side, r.price, r.created_utc"
        "  FROM recommendations r"
        " WHERE r.game_id = ? AND r.market = ?" + not_withdrawn(conn) +
        " ORDER BY r.created_utc, r.id", (game_id, market))]


def one_per_game_and_market(conn: sqlite3.Connection,
                            entries: list[dict]) -> dict[int, dict]:
    """What one pass may write: the ruling, applied in one place.

    `entries` are one pass's picks that cleared the bar (`for_predictions`
    entries with a side). Returns each one's verdict by its prediction id:
    "write"; "already", its own recommendation stands; "second", another
    stands on its game and market, or this pass's first on the same side is
    written instead; or "both_sides", the pass took both sides of its game
    and market and neither is written. Every verdict that writes nothing
    carries why, in words; `standing` is the recommendation that stands,
    where one does.

    A STANDING RECOMMENDATION DECIDES FIRST: a pass that takes both sides of
    a game and market already recommended adds nothing to it, and is
    counted as a second, not as both sides.

    THE FIRST IN A PASS IS THE FORECAST WRITTEN FIRST (its stamp, then its
    id): the statistical row of a question is written before the reasoning
    row, so it is the statistical pick that stands when both clear one side.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for entry in sorted(entries, key=lambda e: (e.get("written_utc") or "",
                                                e["prediction_id"])):
        groups.setdefault((entry["game_id"], entry["market"]), []).append(entry)
    verdicts: dict[int, dict] = {}
    for (game_id, market), group in groups.items():
        standing = standing_recommendations(conn, game_id, market)
        if standing:
            first = standing[0]
            own = {s["prediction_id"] for s in standing}
            why = STANDS_WHY.format(
                id=first["id"], side=first["side"], price=_cents(first["price"]),
                when=_stamp_words(first["created_utc"]))
            for entry in group:
                mine = entry["prediction_id"] in own
                verdicts[entry["prediction_id"]] = {
                    "verdict": "already" if mine else "second",
                    "why": None if mine else why, "standing": first}
            continue
        sides = [entry["side"] for entry in group]
        if len(set(sides)) > 1:
            why = BOTH_SIDES_WHY.format(yes=sides.count("yes"),
                                        no=sides.count("no"))
            for entry in group:
                verdicts[entry["prediction_id"]] = {
                    "verdict": "both_sides", "why": why, "standing": None}
            continue
        verdicts[group[0]["prediction_id"]] = {
            "verdict": "write", "why": None, "standing": None}
        for entry in group[1:]:
            verdicts[entry["prediction_id"]] = {
                "verdict": "second", "standing": None,
                "why": FIRST_IN_THE_PASS_WHY.format(side=group[0]["side"])}
    return verdicts


def _stamp_words(stamp: str) -> str:
    """"2026-09-21T22:13:03Z" -> "2026-09-21 at 22:13 UTC"."""
    return f"{stamp[:10]} at {stamp[11:16]} UTC" if len(stamp) >= 16 else stamp


def _refusal(entry: dict, why: str) -> dict:
    """One pick the ruling kept off the record, and why."""
    return {"prediction_id": entry["prediction_id"], "game_id": entry["game_id"],
            "market": entry["market"], "side": entry["side"], "why": why}


def record_for(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict:
    """Write down what was recommended, at the price it was recommended at.

    ONLY WHERE THERE IS A SIDE. A question the engine had no opinion on is not
    a recommendation, and storing it would make every count of "how often were
    we right" quietly wrong.

    The price is stored because the closing line cannot be compared with
    anything otherwise, and closing-line value is the first honest verdict this
    project can reach: fifty observations rather than several hundred.

    AND THE CORRECTION THAT WAS CURRENT (GRIDIRON_REPAIR item 3, 2026-09-26:
    "from the fix forward, every recommendation carries the correction that
    was current"). `fair_value` keeps the meaning it has on every row before
    this date, the raw claim's number; beside it, `calibrated_fair_value` --
    the number the side, the edge and the size were computed from -- and
    `correction_version`, both NULL when no correction was in force, which is
    what they say on every earlier row because none ever was. The same shape
    as a forecast's `model_prob`, `calibrated_prob` and `correction_version`.
    The version is looked up before the row is stamped, so it is never one
    that activated after the row. Nothing already written is touched (LAW 3),
    and `recommendation_correction_is_frozen` refuses an edit of either.

    ONE PER GAME AND MARKET, NEVER BOTH SIDES (GRIDIRON_REPAIR item 5, the
    operator's ruling of 2026-09-23, built 2026-09-26). Until this date every
    pick that cleared the bar was written, so a morning and a final pass
    each recorded one game and market, and recs 45 and 46 recorded both
    sides of one total in one pass. The ids handed in are one pass, and
    `one_per_game_and_market` decides, before anything is written, which of
    their picks may be: none on a game and market that already hold a
    standing recommendation, neither side where the pass took both, and the
    first written where several took one side. Each one not written is
    counted by name -- `already`, `second_on_game_market`, `both_sides` --
    and said in words in `refused`. The schema's
    `recommendation_one_per_game_and_market` refuses a second row however it
    is written, and a refusal from it -- another writer got there between
    the look and the insert -- is counted as a second by the ruling's words,
    never as `already`, which means a forecast written twice.
    """
    counts = {"recommended": 0, "no_side": 0, "already": 0, "in_game": 0,
              "second_on_game_market": 0, "both_sides": 0}
    refused: list[dict] = []
    entries = for_predictions(conn, prediction_ids)
    decided = one_per_game_and_market(conn, [
        e for e in entries
        if e["side"] is not None and e["size"]["kind"] in ("flat", "fraction")])
    for entry in entries:
        if entry["side"] is None:
            counts["no_side"] += 1
            continue
        size = entry["size"]
        if size["kind"] not in ("flat", "fraction"):
            counts["no_side"] += 1
            continue
        verdict = decided[entry["prediction_id"]]
        if verdict["verdict"] == "already":
            counts["already"] += 1
            continue
        if verdict["verdict"] != "write":
            counts["both_sides" if verdict["verdict"] == "both_sides"
                   else "second_on_game_market"] += 1
            refused.append(_refusal(entry, verdict["why"]))
            continue
        corrected = entry["correction_version"] is not None
        try:
            conn.execute(
                "INSERT INTO recommendations (prediction_id, sport, game_id,"
                " market, side, fair_value, price, edge_cents, size_kind,"
                " size_units, gate_n, created_utc, correction_version,"
                " calibrated_fair_value)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (entry["prediction_id"], entry["sport"], entry["game_id"],
                 entry["market"], entry["side"], entry["raw_fair_value"],
                 entry["price"], entry["edge_cents"], size["kind"],
                 size["units"], entry["gate_n"],
                 just_after(entry.get("written_utc")),
                 entry["correction_version"],
                 entry["fair_value"] if corrected else None))
            counts["recommended"] += 1
        except sqlite3.IntegrityError as exc:
            # THE SCHEMA'S REFUSAL, BY THE RULING'S WORDS, before the
            # forecast-twice one: a second on the game and market is not a
            # forecast written twice, and is counted and said as what it is.
            if ONE_PER_GAME_AND_MARKET in str(exc):
                counts["second_on_game_market"] += 1
                refused.append(_refusal(entry, REFUSED_BY_THE_RECORD_WHY))
                continue
            if "UNIQUE" not in str(exc):
                raise
            counts["already"] += 1
    conn.commit()
    counts["refused"] = refused
    return counts


# ---------------------------------------------------------------------------
# A RECOMMENDATION WITHDRAWN (operator ruling 1, 2026-09-24)
# ---------------------------------------------------------------------------
#
# Recommendations 62, 63, 64 and 66 were published from fits 91-94 before the
# hold, and the fits then failed their holdout. The ruling voids them: they
# stay in the record and are never counted -- not in the closing line, a
# curve, a correction, readiness or any gate.
#
# ONE DOOR, because "never counted" is only true if every count agrees on it.
# Until this date seven statements in six functions read `recommendations`
# straight off the table (the closing line and its awaiting count, the closer,
# the restatement, the near-start reader, the taken rail's edge, the empty-bar
# tool), and every one of them would have treated a withdrawn recommendation
# as standing without anybody seeing it happen.
# `audit.check_every_recommendation_reader_uses_the_door` reads the source and
# refuses a reader that goes round this; `audit.withdrawn_counted_faults`
# recomputes the closing line's counts without it and refuses a difference.


def not_withdrawn(conn: sqlite3.Connection, alias: str = "r") -> str:
    """` AND ...`: the recommendation `alias` still stands.

    TWO WAYS TO BE WITHDRAWN, and a reader asks neither itself: a row in
    `recommendation_voids`, or a void on the prediction it was made from --
    a recommendation on a forecast that no longer stands cannot stand either.

    A RECORD WITHOUT THE TABLE HAS WITHDRAWN NOTHING, which is exact rather
    than an approximation: the table is the only place a withdrawal can be
    written. It matters on a query-only handle to a record the schema has not
    reached yet -- the gate and the dry-run tools read the live record without
    applying the schema, and a clause naming a missing table would stop them.
    """
    if not alias.isidentifier():
        raise ValueError(f"{alias!r} is not a table alias")
    clause = (f" AND NOT EXISTS (SELECT 1 FROM prediction_voids wp"
              f"                 WHERE wp.prediction_id = {alias}.prediction_id)")
    if _has_withdrawals(conn):
        clause += (f" AND NOT EXISTS (SELECT 1 FROM recommendation_voids wr"
                   f"                 WHERE wr.recommendation_id = {alias}.id)")
    return clause


def _has_withdrawals(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        "   AND name = 'recommendation_voids'").fetchone() is not None


def withdrawn(conn: sqlite3.Connection, *, sport: str) -> list[dict]:
    """The recommendations the door leaves out, each with its reason.

    THE OTHER SIDE OF THE DOOR, and the only reader allowed round it: it lists
    what `not_withdrawn` excludes so the page can say so, in words, rather
    than letting a withdrawn recommendation vanish. Never deleted, never
    counted, always shown as withdrawn.
    """
    config.require_sport(sport, "recommend.withdrawn")
    own = (" LEFT JOIN recommendation_voids wr ON wr.recommendation_id = r.id"
           if _has_withdrawals(conn) else "")
    reason = "wr.reason" if own else "NULL"
    rows = conn.execute(
        f"SELECT r.id, r.market, r.prediction_id,"
        f"       COALESCE({reason}, wp.reason) AS reason"
        f"  FROM recommendations r{own}"
        f"  LEFT JOIN prediction_voids wp ON wp.prediction_id = r.prediction_id"
        f" WHERE r.sport = ?"
        f"   AND ({reason} IS NOT NULL OR wp.prediction_id IS NOT NULL)"
        f" ORDER BY r.id", (sport,)).fetchall()
    return [{"id": r["id"], "market": r["market"],
             "prediction_id": r["prediction_id"], "reason": r["reason"]}
            for r in rows]


# ---------------------------------------------------------------------------
# A RECOMMENDATION THE BAR SHOULD HAVE REFUSED (GRIDIRON_REPAIR item 4, the
# operator's ruling of 2026-09-23, built 2026-09-26)
# ---------------------------------------------------------------------------
#
# "Return-on-stake denominator: a no-side edge divides by the no-side cost.
# Re-grade the three recommendations it let through as 'would not have
# cleared'." Until 2026-09-26 the bar divided every edge by the yes price, so
# a no-side pick below a 50c yes price could clear 5% of the yes price while
# returning less than 5% of what it cost. THE READ of 2026-09-23 counted
# three: recs 3, 10 and 26. Measured again on 2026-09-26, the rule selects
# four -- rec 56, written on 24 September by the code still carrying the
# defect, is the fourth -- which is a question for the operator
# (docs/REPAIR_STATE.md), so `tools/regrade_return_on_stake.py` writes only
# the set he names and refuses a difference.
#
# A LABEL, NEVER AN EDIT (LAW 3). The recommendation stays exactly as it was
# written; `recommendation_regrades` holds a second row beside it, and the
# schema checks the label against the row's own frozen side, price and edge.
# A re-grade is not a withdrawal: it takes nothing out of any count, and the
# closing line names it beside itself, in the words "would not have cleared".

#: The one verdict a re-grade carries, as `recommendation_regrades` admits it.
WOULD_NOT_HAVE_CLEARED = "would_not_have_cleared"

#: What every re-grade says, in words, with its own numbers -- to the
#: hundredth of a per cent, because rec 56 is 4.97% of its cost and one place
#: would print it as 5.0% "under the 5%".
REGRADE_WHY = ("the bar divided this {side}-side edge of {edge:+.2f}¢ by the "
               "{price}¢ yes price and passed it at {on_yes:.2%}; on the "
               "{cost}¢ the {side} side cost it is {on_cost:.2%}, under the "
               "{minimum:.0%} declared on {declared} (GRIDIRON_REPAIR item 4, "
               "the operator's ruling of 2026-09-23)")


def _has_regrades(conn: sqlite3.Connection) -> bool:
    """A record the schema has not reached holds no re-grade -- exactly, as
    `_has_withdrawals` says of a withdrawal: the dry-run tools and the gate
    read the live record without applying the schema."""
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        "   AND name = 'recommendation_regrades'").fetchone() is not None


def let_through_by_the_yes_price(conn: sqlite3.Connection) -> list[dict]:
    """Every standing recommendation the bar passed on the yes price and
    refuses on the cost of the side it was on, each with its arithmetic.

    BY RULE, FROM THE FROZEN ROW, NEVER BY OUTCOME: the side, the price and
    the edge as written, divided the way the bar divided them until
    2026-09-26 -- by the yes price, whatever the side -- and the way it
    divides now, through `clears_the_bar` itself, so the rule that selects a
    re-grade is the rule that decides a pick. Only rows written once the bar
    had been declared: before that nothing was let through, because nothing
    was asked. Withdrawn rows go through the door like every other reader:
    a withdrawn recommendation is already never counted, and is shown as
    withdrawn rather than labelled twice.
    """
    has = _has_regrades(conn)
    labelled = ("EXISTS (SELECT 1 FROM recommendation_regrades g"
                "        WHERE g.recommendation_id = r.id)" if has else "0")
    rows = conn.execute(
        f"SELECT r.id, r.sport, r.market, r.side, r.price, r.edge_cents,"
        f"       r.created_utc, {labelled} AS already"
        f"  FROM recommendations r"
        f" WHERE r.created_utc >= ?" + not_withdrawn(conn) +
        " ORDER BY r.id", (config.MIN_RETURN_ON_STAKE_DECLARED,)).fetchall()
    out = []
    for row in rows:
        # WHAT THE BAR COMPUTED UNTIL 2026-09-26: the edge over the yes
        # price, whatever the side. Written out here and nowhere else, as the
        # record of a divisor that is no longer used.
        on_yes = round((float(row["edge_cents"]) / 100.0) / float(row["price"]), 4)
        now = clears_the_bar(row["edge_cents"], row["price"], side=row["side"])
        if now["clears"] or on_yes < config.MIN_RETURN_ON_STAKE:
            continue
        cost = round(_cost_of(row["side"], row["price"]), 4)
        out.append({
            "id": row["id"], "sport": row["sport"], "market": row["market"],
            "side": row["side"], "price": row["price"],
            "edge_cents": row["edge_cents"], "created_utc": row["created_utc"],
            "side_cost": cost, "return_on_cost": now["return_on_stake"],
            "return_on_yes_price": on_yes,
            "minimum_return": config.MIN_RETURN_ON_STAKE,
            "already": bool(row["already"]),
            "reason": REGRADE_WHY.format(
                side=row["side"], edge=row["edge_cents"],
                price=_cents(row["price"]), on_yes=on_yes, cost=_cents(cost),
                on_cost=now["return_on_stake"],
                minimum=config.MIN_RETURN_ON_STAKE,
                declared=config.MIN_RETURN_ON_STAKE_DECLARED[:10]),
        })
    return out


def write_regrades(conn: sqlite3.Connection, ids: list[int], *,
                   now: str | None = None) -> dict:
    """One re-grade for each of `ids`, in one transaction, or none at all.

    EVERY ID IS CHECKED AGAINST THE ARITHMETIC FIRST: an id the rule does
    not select (`let_through_by_the_yes_price`, read in the same call) is
    refused by name and nothing is written. The schema checks each row's
    numbers again as it is written. IDEMPOTENT: an id already re-graded is
    counted and skipped -- the table would refuse a second row anyway, and
    the first stands.
    """
    if not _has_regrades(conn):
        raise RuntimeError(
            "the record has no recommendation_regrades table: it has not been "
            "opened under the schema that carries it (db.init does that, on "
            "any scheduled pass or the server's start after the release)")
    chosen = {r["id"]: r for r in let_through_by_the_yes_price(conn)}
    stray = sorted(set(ids) - set(chosen))
    if stray:
        raise ValueError(
            f"recommendation(s) {stray} would have cleared on the cost of "
            f"their own side, or are withdrawn, or were never let through by "
            f"the yes price: nothing written")
    stamp = now or utcnow()
    counts = {"written": 0, "already": 0}
    with transaction(conn):
        for rid in sorted(set(ids)):
            got = chosen[rid]
            if got["already"]:
                counts["already"] += 1
                continue
            conn.execute(
                "INSERT INTO recommendation_regrades (recommendation_id,"
                " regraded_utc, verdict, side_cost, return_on_cost,"
                " return_on_yes_price, minimum_return, reason)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (rid, stamp, WOULD_NOT_HAVE_CLEARED, got["side_cost"],
                 got["return_on_cost"], got["return_on_yes_price"],
                 got["minimum_return"], got["reason"]))
            counts["written"] += 1
    return counts


def regraded(conn: sqlite3.Connection, *, sport: str) -> list[dict]:
    """This sport's standing recommendations that carry a re-grade.

    WHAT THE PAGE SAYS BESIDE THE CLOSING LINE: named, with the return on
    the side's own cost, and counted where they always were -- a label, not
    a withdrawal. Through the door: a withdrawn recommendation is shown as
    withdrawn, once.
    """
    config.require_sport(sport, "recommend.regraded")
    if not _has_regrades(conn):
        return []
    rows = conn.execute(
        "SELECT r.id, r.market, g.side_cost, g.return_on_cost,"
        "       g.return_on_yes_price, g.minimum_return, g.reason"
        "  FROM recommendation_regrades g"
        "  JOIN recommendations r ON r.id = g.recommendation_id"
        " WHERE r.sport = ?" + not_withdrawn(conn) +
        " ORDER BY r.id", (sport,)).fetchall()
    return [{"id": r["id"], "market": r["market"], "side_cost": r["side_cost"],
             "return_on_cost": r["return_on_cost"],
             "return_on_yes_price": r["return_on_yes_price"],
             "minimum_return": r["minimum_return"], "reason": r["reason"]}
            for r in rows]


#: What a close with no later read of its own contract says about itself.
UNMEASURED_WHY = ("no near-start read of the same contract after the price it "
                  "was recommended at, before the start")

#: And one whose price cannot be traced to the quote it came from.
UNTRACEABLE_WHY = ("the price it was recommended at cannot be traced to the "
                   "quote it was read from")

#: What every restated row says: the close the old closer recorded was the
#: recommendation's own price, not a later read.
RESTATED_WHY = ("the close recorded at the time was the recommendation's own "
                "price, not a later read; restated on {day} from quotes the "
                "record held before the start")


def close_of(conn: sqlite3.Connection, rec: sqlite3.Row,
             kickoff: str | None) -> dict:
    """The close of one recommendation, by the one rule, or why it has none.

    THE RULE (GRIDIRON_REPAIR item 1, 2026-09-23): the close is the LAST
    NEAR-START READ OF THE RECOMMENDATION'S OWN CONTRACT, taken after the read
    it was priced from and before the game started. Priced the way its claim
    was (`at_the_line.implied_of`), so the two cannot orient differently.

    NEVER "THE LAST CLAIM", which is what it was until this date. A later claim
    sits on whichever rung is nearest 50/50 at that look, which can be another
    strike; and for a recommended prediction no later claim was ever written,
    so the close was the price compared with itself -- 0.00c on 49 of 49 rows.

    The contract is found through the pricing claim: the latest claim on the
    prediction written by the time of the recommendation, whose price must be
    the recommendation's price. Anything that does not trace is UNMEASURED
    with its reason, never guessed.
    """
    from . import at_the_line

    out = {"pricing_quote_id": None, "close_quote_id": None,
           "close_price": None, "clv_cents": None,
           "minutes_before_start": None}
    claim = conn.execute(
        "SELECT quote_id, venue_implied FROM at_the_line_claims"
        " WHERE prediction_id = ? AND created_utc <= ?"
        "   AND (? IS NULL OR created_utc < ?)"
        " ORDER BY created_utc DESC, id DESC LIMIT 1",
        (rec["prediction_id"], rec["created_utc"], kickoff, kickoff)).fetchone()
    if claim is None or round(claim["venue_implied"], 4) != round(rec["price"], 4):
        return {**out, "why": UNTRACEABLE_WHY}
    pricing = conn.execute("SELECT * FROM venue_quotes WHERE id = ?",
                           (claim["quote_id"],)).fetchone()
    if pricing is None:
        return {**out, "why": UNTRACEABLE_WHY}
    out["pricing_quote_id"] = claim["quote_id"]
    if kickoff is None:
        return {**out, "why": UNMEASURED_WHY}
    for quote in conn.execute(
            "SELECT * FROM venue_quotes WHERE venue = ? AND ticker = ?"
            "   AND read_kind = 'near_start'"
            "   AND fetched_utc > ? AND fetched_utc < ?"
            " ORDER BY fetched_utc DESC, id DESC",
            (pricing["venue"], pricing["ticker"], pricing["fetched_utc"],
             kickoff)):
        if all(_same(quote[k], pricing[k]) for k in _READ_CONTENT):
            # INDISTINGUISHABLE FROM THE READ IT WAS PRICED FROM -- the same
            # bid, ask, last price and volume -- which is what a cached body
            # re-stamped as a new read looks like. Not evidence of a later
            # price, so it cannot be one.
            continue
        read = at_the_line.implied_of(quote)
        if read is None:
            continue           # an unpriced read; the one before it may be priced
        close = round(read[0], 4)
        return {**out, "close_quote_id": quote["id"], "close_price": close,
                "clv_cents": clv_cents(rec["side"], rec["price"], close),
                "minutes_before_start": _minutes_between(quote["fetched_utc"],
                                                         kickoff),
                "why": "the last near-start read of its own contract before "
                       "the start"}
    return {**out, "why": UNMEASURED_WHY}


#: What makes two reads of one contract different reads.
_READ_CONTENT = ("yes_bid", "yes_ask", "last_price", "volume")


def _same(a, b) -> bool:
    """Equal as prices are: absent matches absent, and a number matches a
    number to far below a tenth of a cent -- never by float representation."""
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) < 1e-9


def _minutes_between(earlier: str, later: str) -> float:
    from datetime import datetime

    fmt = "%Y-%m-%dT%H:%M:%SZ"
    delta = datetime.strptime(later, fmt) - datetime.strptime(earlier, fmt)
    return round(delta.total_seconds() / 60.0, 1)


def _write_close(conn: sqlite3.Connection, rec_id: int, got: dict, *,
                 restated: bool, now: str, reason: str) -> None:
    conn.execute(
        "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
        " pricing_quote_id, close_quote_id, close_price, clv_cents,"
        " minutes_before_start, restated, reason)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (rec_id, now, got["pricing_quote_id"], got["close_quote_id"],
         got["close_price"], got["clv_cents"], got["minutes_before_start"],
         1 if restated else 0, reason))


def record_closing_prices(conn: sqlite3.Connection) -> dict:
    """The price at the close, beside the price that was recommended.

    CLOSING-LINE VALUE IS THE FAST VERDICT. A win rate needs several hundred
    settled questions before it says anything; the closing line says something
    at around fifty, because it compares the app's price against the market's
    own final estimate rather than against one noisy outcome.

    The close is `close_of`: its own contract's last near-start read before
    kickoff. A recommendation with none closes UNMEASURED -- `closed_utc` set,
    no price, no CLV -- and is counted beside the closing line, never inside
    it at 0.00c. Either way the close and how it was measured are written in
    one transaction, so no close exists without its account.
    """
    counts = {"closed": 0, "unmeasured": 0, "still_open": 0}
    # A WITHDRAWN RECOMMENDATION IS NOT FOLLOWED TO ITS CLOSE (2026-09-24).
    # Its close would never be counted, and closing it would write an account
    # -- "no later read", say -- about a recommendation nobody stands behind.
    # It stays open, withdrawn, and said so.
    rows = conn.execute(
        "SELECT r.id, r.prediction_id, r.side, r.price, r.created_utc,"
        "       g.kickoff_utc"
        "  FROM recommendations r JOIN games g ON g.id = r.game_id"
        " WHERE r.closed_utc IS NULL" + not_withdrawn(conn)).fetchall()
    now = utcnow()
    for row in rows:
        # A START NOBODY KNOWS YET IS STILL AHEAD. Closing it now would write,
        # once and for good, that no read came before a start that has not
        # been scheduled.
        if not row["kickoff_utc"] or row["kickoff_utc"] > now:
            counts["still_open"] += 1
            continue
        got = close_of(conn, row, row["kickoff_utc"])
        if got["close_price"] is None:
            cur = conn.execute("UPDATE recommendations SET closed_utc = ?"
                               " WHERE id = ? AND closed_utc IS NULL",
                               (now, row["id"]))
        else:
            cur = conn.execute(
                "UPDATE recommendations SET close_price = ?, clv_cents = ?,"
                " closed_utc = ? WHERE id = ? AND closed_utc IS NULL",
                (got["close_price"], got["clv_cents"], now, row["id"]))
        # ANOTHER FIRING GOT THERE FIRST. Refresh and the near-start task both
        # call this; if one closed the row between this one's read and its
        # write, the account is already written and a second would abort the
        # whole pass on the primary key.
        if cur.rowcount != 1:
            continue
        counts["closed" if got["close_price"] is not None else "unmeasured"] += 1
        _write_close(conn, row["id"], got, restated=False, now=now,
                     reason=got["why"])
    conn.commit()
    return counts


def restate_old_closes(conn: sqlite3.Connection, *, write: bool) -> dict:
    """Every close the old closer made, restated by the one rule.

    A closed recommendation with no `recommendation_closes` row is one the
    closer of before 2026-09-23 closed, on its own price. Its recorded close
    stands (LAW 3; the trigger would refuse a second write anyway), and this
    writes the companion row beside it: the true close where the record holds
    a later read of the same contract from before the start, UNMEASURED where
    it does not. Every one is marked `restated`, and nothing counts it inside
    the closing line.

    Reported PER SPORT AND MARKET, never pooled (LAW 6). Dry by default, and a
    dry run reads only: it works on a query-only handle, and on a record that
    has no account table yet it treats every close as unaccounted.
    """
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        "   AND name = 'recommendation_closes'").fetchone() is not None
    unaccounted = (" AND NOT EXISTS (SELECT 1 FROM recommendation_closes c"
                   "                  WHERE c.recommendation_id = r.id)"
                   if has_table else "")
    # THROUGH THE DOOR (2026-09-24): a withdrawn recommendation's close is
    # never counted, so there is nothing to restate for one.
    rows = conn.execute(
        "SELECT r.id, r.prediction_id, r.sport, r.market, r.side, r.price,"
        "       r.created_utc, r.close_price, g.kickoff_utc"
        "  FROM recommendations r JOIN games g ON g.id = r.game_id"
        " WHERE r.closed_utc IS NOT NULL" + unaccounted + not_withdrawn(conn) +
        " ORDER BY r.id").fetchall()
    if write and not has_table:
        raise RuntimeError("the record has no recommendation_closes table; "
                           "open it with db.open_db so the schema is applied")
    now = utcnow()
    reason = RESTATED_WHY.format(day=now[:10])
    report: dict = {"rows": 0, "by": {}, "written": 0}
    for row in rows:
        if row["close_price"] is not None and abs(row["close_price"] - row["price"]) > 1e-9:
            raise ValueError(
                f"recommendation {row['id']} closed at {row['close_price']} "
                f"against a price of {row['price']}: the old closer never did "
                f"that, so this row is not what this restatement is for")
        got = close_of(conn, row, row["kickoff_utc"])
        bucket = report["by"].setdefault(
            (row["sport"], row["market"]),
            {"measured": 0, "unmeasured": 0, "clv": []})
        report["rows"] += 1
        if got["close_price"] is None:
            bucket["unmeasured"] += 1
        else:
            bucket["measured"] += 1
            bucket["clv"].append(got["clv_cents"])
        if write:
            _write_close(conn, row["id"], got, restated=True, now=now,
                         reason=f"{reason}; {got['why']}")
            report["written"] += 1
    if write:
        conn.commit()
    return report


def clv_cents(side: str, taken: float, close: float) -> float:
    """How much better than the close the recommended price was, in cents.

    Positive means the app bought cheaper than the market's own final estimate.
    On the no side the arithmetic mirrors: buying the other half of the dollar
    is cheap when the yes price rose.
    """
    if side == "yes":
        return round((float(close) - float(taken)) * 100.0, 2)
    return round((float(taken) - float(close)) * 100.0, 2)
