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
  * SINGLES ONLY. `price_parlay` exists to refuse: each leg pays the spread,
    so an N-leg parlay multiplies the cost of being right by roughly N, and
    correlated legs price worse than they look.
  * NOTHING IS SIZED IN-GAME. The poller's score can be ninety seconds stale
    while the venue prices off the live feed, so a live recommendation is
    adversely selected by construction.
"""
from __future__ import annotations

import sqlite3

from .. import config
from . import paper


class SinglesOnly(RuntimeError):
    """A parlay was priced. It is not, and the reason is arithmetic."""


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
             settled: int) -> dict:
    """How much, in units, and why.

    BELOW THE GATE, THE ANSWER DOES NOT DEPEND ON THE PROBABILITY. A 92% claim
    and a 62% claim on an unproven market get the same flat unit, and a caller
    cannot ask for more: the function takes no multiplier and returns the
    declared unit unchanged. `plant.py` proves it by asking twice with
    different confidence and comparing.
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
            "why": (f"no measured edge — flat unit ({settled} of {gate} settled "
                    f"in this market)"),
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


def price_parlay(legs) -> None:
    """Refuse, and say why in the same breath.

    A function that exists to say no. Its argument is accepted so that a caller
    reaching for a parlay finds this rather than a missing name and writes their
    own.
    """
    raise SinglesOnly(
        f"SINGLES ONLY (LAW 5): a {len(list(legs))}-leg parlay is not priced "
        f"here. Each leg pays the spread and the fee, so the cost of being "
        f"right multiplies with the legs, and legs about the same game are "
        f"correlated -- which prices worse than the product of the parts "
        f"suggests, not better.")


def refuse_in_game(game_status: str | None) -> None:
    """Nothing is sized once a game is under way."""
    if (game_status or "").lower() in ("in_progress", "live", "in progress"):
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

    if not prediction_ids:
        return []
    placeholders = ",".join("?" for _ in prediction_ids)
    rows = conn.execute(
        "SELECT p.id, p.sport, p.game_id, p.market_type, p.prop_type, p.subject,"
        " p.line_asked, p.model_prob, p.model_side, p.predictor, g.status,"
        " g.kickoff_utc,"
        " (SELECT s.implied_prob FROM market_snapshots s"
        "   WHERE s.prediction_id = p.id ORDER BY s.id LIMIT 1) AS implied_prob"
        f" FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE p.id IN ({placeholders})", list(prediction_ids)).fetchall()
    ranks = ranker.ranks_for(conn, prediction_ids)

    out = []
    for row in rows:
        rank = ranks.get(row["id"])
        if rank is None or not rank["on_shortlist"]:
            continue
        if (row["status"] or "").lower() in ("in_progress", "live"):
            continue
        price = row["implied_prob"]
        settled = rank["edge_gate_n"] or 0
        chosen = side_for(row["model_prob"], price)
        size = size_for(model_prob=row["model_prob"], price=price, settled=settled)
        out.append({
            "prediction_id": row["id"],
            "sport": row["sport"],
            "game_id": row["game_id"],
            "market": row["prop_type"] or row["market_type"],
            "subject": row["subject"],
            "line_asked": row["line_asked"],
            "model_side": row["model_side"],
            "fair_value": fair_value(row["model_prob"]),
            "price": round(price, 4) if price is not None else None,
            "edge_cents": chosen["edge_cents"],
            "side": chosen["side"],
            "side_why": chosen["why"],
            "size": size,
            "gate_n": settled,
            "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
        })
    return out
