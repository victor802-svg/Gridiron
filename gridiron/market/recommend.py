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

from .. import config
from ..db import just_after, utcnow
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


def edge_cents(model_prob: float | None, price: float | None,
               side: str = "yes") -> float | None:
    """What one contract is worth after the fee, in cents.

    The yes side costs `price` and returns a dollar if it happens; the no side
    costs the rest of the dollar. Both are the same subtraction, and the fee is
    charged either way -- which is the whole reason a small edge is usually not
    one.
    """
    if model_prob is None or price is None or not 0 < price < 1:
        return None
    if side == "yes":
        raw = float(model_prob) - float(price)
        cost = float(price)
    else:
        raw = (1.0 - float(model_prob)) - (1.0 - float(price))
        cost = 1.0 - float(price)
    return round((raw - fee(cost)) * 100.0, 2)


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


def return_on_stake(edge_cents: float | None, price: float | None) -> float | None:
    """The edge as a share of the money put up, not as cents on a contract.

    THE TWO NUMBERS DISAGREE ABOUT WHICH BET IS BETTER, which is the whole
    reason this exists. Two cents on an 89-cent contract and two cents on a
    20-cent one are the same edge and are 2.2% and 10% on the stake; the
    second is worth four and a half times as much per dollar risked.

    None where either input is missing, because absent and zero are different
    facts here as everywhere else in this project.
    """
    if edge_cents is None or price is None or price <= 0:
        return None
    return round((float(edge_cents) / 100.0) / float(price), 4)


def payout_multiple(price: float | None) -> float | None:
    """What one unit returns if the contract settles at a dollar.

    A contract at 84 cents pays 1.19 times the stake. This is arithmetic on a
    published price and nothing else: no balance is read, nothing is placed,
    and the number is the same whether or not anybody acts on it.
    """
    if price is None or price <= 0:
        return None
    return round(1.0 / float(price), 3)


def clears_the_bar(edge_cents: float | None, price: float | None) -> dict:
    """Both conditions, in one place, with the reason it failed in words.

    ONE DOOR, for the same reason `refuse_in_game` is one: two callers deciding
    what "clears the bar" means is how a page starts disagreeing with itself
    about which group a pick belongs in.
    """
    got = return_on_stake(edge_cents, price)
    if got is None:
        return {"clears": False, "return_on_stake": None,
                "why": "no recorded price to compare against"}
    if got < config.MIN_RETURN_ON_STAKE:
        return {
            "clears": False,
            "return_on_stake": got,
            "why": (f"the price is wrong by {edge_cents:+.1f}¢ and that is "
                    f"{got * 100:.1f}% of the {round(price * 100)}¢ it costs, "
                    f"under the {config.MIN_RETURN_ON_STAKE * 100:.0f}% this "
                    f"app asks for before it calls something worth the click"),
        }
    return {"clears": True, "return_on_stake": got,
            "why": (f"{got * 100:.1f}% of the {round(price * 100)}¢ it costs, "
                    f"after the venue's fee")}


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


def for_predictions(conn: sqlite3.Connection, prediction_ids: list[int]) -> list[dict]:
    """One recommendation per shortlisted question that has a recorded price.

    Reads the frozen prediction, the price already stored beside it and the
    market's settled count. Computes nothing about a game in progress and
    writes nothing anywhere: a recommendation is a reading of rows that already
    exist.
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
        " c.line AS venue_line, c.venue AS venue"
        f" FROM predictions p JOIN games g ON g.id = p.game_id"
        " LEFT JOIN at_the_line_claims c ON c.id = ("
        "     SELECT c2.id FROM at_the_line_claims c2"
        "      WHERE c2.prediction_id = p.id"
        "        AND (g.kickoff_utc IS NULL OR c2.created_utc < g.kickoff_utc)"
        "      ORDER BY c2.created_utc DESC, c2.id DESC LIMIT 1)"
        f" WHERE p.id IN ({placeholders})", list(prediction_ids)).fetchall()
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
        model_prob = row["claim_prob"]
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
        stake = clears_the_bar(chosen.get("edge_cents"), price)
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
            "fair_value": fair_value(model_prob),
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


def record_for(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict:
    """Write down what was recommended, at the price it was recommended at.

    ONLY WHERE THERE IS A SIDE. A question the engine had no opinion on is not
    a recommendation, and storing it would make every count of "how often were
    we right" quietly wrong.

    The price is stored because the closing line cannot be compared with
    anything otherwise, and closing-line value is the first honest verdict this
    project can reach: fifty observations rather than several hundred.
    """
    counts = {"recommended": 0, "no_side": 0, "already": 0, "in_game": 0}
    for entry in for_predictions(conn, prediction_ids):
        if entry["side"] is None:
            counts["no_side"] += 1
            continue
        size = entry["size"]
        if size["kind"] not in ("flat", "fraction"):
            counts["no_side"] += 1
            continue
        try:
            conn.execute(
                "INSERT INTO recommendations (prediction_id, sport, game_id,"
                " market, side, fair_value, price, edge_cents, size_kind,"
                " size_units, gate_n, created_utc)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (entry["prediction_id"], entry["sport"], entry["game_id"],
                 entry["market"], entry["side"], entry["fair_value"],
                 entry["price"], entry["edge_cents"], size["kind"],
                 size["units"], entry["gate_n"],
                 just_after(entry.get("written_utc"))))
            counts["recommended"] += 1
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" not in str(exc):
                raise
            counts["already"] += 1
    conn.commit()
    return counts


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
    rows = conn.execute(
        "SELECT r.id, r.prediction_id, r.side, r.price, r.created_utc,"
        "       g.kickoff_utc"
        "  FROM recommendations r JOIN games g ON g.id = r.game_id"
        " WHERE r.closed_utc IS NULL").fetchall()
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
    rows = conn.execute(
        "SELECT r.id, r.prediction_id, r.sport, r.market, r.side, r.price,"
        "       r.created_utc, r.close_price, g.kickoff_utc"
        "  FROM recommendations r JOIN games g ON g.id = r.game_id"
        " WHERE r.closed_utc IS NOT NULL" + unaccounted +
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
