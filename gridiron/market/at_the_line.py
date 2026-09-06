"""The frozen distribution, read at the venue's number (AT_THE_LINE E4).

**Arithmetic on a blind artifact, not a second prediction.** Every game
prediction carries a margin or total distribution written inside the blind
window and frozen with its row (E3). This module reads that distribution at a
number the venue published afterwards, and records the pair -- what the model
says about a proposition, and what the venue's price says about the same
proposition -- as a claim of its own kind.

Three properties hold it in place, and each one is in the schema rather than in
this docstring:

  * The claim is stamped after the prediction and after the quote. A row that
    could be read as blind is refused by a trigger.
  * The claim needs the frozen distribution; a prediction without one gets no
    claim, and the hole is counted by name rather than filled with a guess.
  * ONE FIXED PROPOSITION, NEVER A CHOSEN SIDE. A spread claim is always about
    the home side covering the venue's number, a total claim always about the
    over. The record holds two probabilities for the same question and stops
    there. It does not hold a side to take, which is what LAW 5 forbids.

WHICH RUNG OF THE LADDER. A venue quotes a ladder -- twenty-five strikes on one
game -- and one of them is what a reader means by "the line": the strike priced
nearest a coin flip. That is the rung this reads, declared here and dated,
because picking the strike where the model looks best would be choosing the
comparison after seeing the answer, which is the same error as fitting a factor
to the data it will be scored on.
"""
from __future__ import annotations

import json
import math
import sqlite3

from ..db import utcnow

#: The venue whose ladder is read. One venue today; the column carries the name
#: on every row so a second one never merges into the first.
VENUE = "kalshi"

RUNG_CHOICE_DECLARED = "2026-09-06T00:00:00Z"
RUNG_CHOICE_RATIONALE = (
    "The strike priced nearest an even chance is the venue's own line -- the "
    "number a reader means by 'the line'. Declared before any claim was "
    "written, because choosing the rung where the model looks best would be "
    "choosing the comparison after seeing the answer."
)

PRICE_BASIS_MID = "the midpoint of the venue's yes bid and ask"
PRICE_BASIS_LAST = "the venue's last traded price, with no two-sided quote up"

#: A probability is stored strictly inside (0, 1): the schema says so, and a
#: normal tail rounds to zero long before the event becomes impossible.
_FLOOR = 0.0001
_CEIL = 0.9999

#: The three game markets a claim can be made in, and the proposition each one
#: is always about.
CLAIM_SIDE = {"spread": "home", "moneyline": "home", "total": "over"}


def normal_cdf(z: float) -> float:
    """The standard normal's cumulative probability, from the error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def model_probability(quantity: str, mean: float, sd: float,
                      line: float | None) -> float | None:
    """The frozen distribution's answer to the venue's question.

    `home_margin` at a line of -6.5: the chance the home margin clears 6.5.
    `total` at 47.5: the chance the combined score goes over it. `home_win`:
    the chance the margin is positive at all. A line the shape does not need,
    or a spread with no line, answers None rather than something.
    """
    if sd is None or sd <= 0 or mean is None:
        return None
    if quantity == "home_win":
        z = mean / sd
    elif quantity == "home_margin":
        if line is None:
            return None
        # home covers L  <=>  margin + L > 0  <=>  margin > -L
        z = (mean + line) / sd
    elif quantity == "total":
        if line is None:
            return None
        z = (mean - line) / sd
    else:
        return None
    return min(_CEIL, max(_FLOOR, normal_cdf(z)))


def _price(quote: sqlite3.Row) -> tuple[float, str] | None:
    """The venue's price for its own yes side, and what that price is."""
    bid, ask = quote["yes_bid"], quote["yes_ask"]
    if bid is not None and ask is not None and 0 < (bid + ask) / 2 < 1:
        return (bid + ask) / 2, PRICE_BASIS_MID
    last = quote["last_price"]
    if last is not None and 0 < last < 1:
        return last, PRICE_BASIS_LAST
    return None


def rung_for(quotes: list[sqlite3.Row]) -> dict | None:
    """The venue's own line out of one look at one ladder.

    Returns the quote, the price the venue showed, and that price read as a
    probability for OUR fixed proposition -- the home side, or the over. A
    strike quoted from the away side answers the complementary question, so
    its price is complemented too; the stored line is already written from the
    home side's view, which is what makes that a subtraction and not a guess.
    """
    best = None
    for quote in quotes:
        priced = _price(quote)
        if priced is None:
            continue
        price, basis = priced
        implied = price if quote["yes_side"] in ("home", "over") else 1.0 - price
        if not 0 < implied < 1:
            continue
        distance = abs(implied - 0.5)
        if best is None or distance < best["distance"]:
            best = {"quote": quote, "price": round(price, 6),
                    "implied": round(implied, 6), "basis": basis,
                    "distance": distance}
    return best


def _looks(conn: sqlite3.Connection, game_id: str, market: str) -> list[list[sqlite3.Row]]:
    """One ladder per look, oldest first."""
    rows = conn.execute(
        "SELECT * FROM venue_quotes WHERE game_id = ? AND market = ? AND venue = ?"
        " ORDER BY fetched_utc, line",
        (game_id, market, VENUE)).fetchall()
    looks: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        looks.setdefault(row["fetched_utc"], []).append(row)
    return [looks[stamp] for stamp in sorted(looks)]


def evaluate(conn: sqlite3.Connection,
             prediction_ids: list[int] | None = None) -> dict:
    """Write a claim for every prediction whose frozen distribution can be read
    at a price the venue actually showed.

    Every hole is counted by its own name. A market that never gets a claim is
    a coverage fact, and a coverage fact that is silently zero is the failure
    this counting exists to prevent.
    """
    counts = {"claims": 0, "already": 0, "no_distribution": 0,
              "no_quotes": 0, "no_priced_rung": 0, "unusable_distribution": 0,
              "predictions": 0}
    where = "p.market_type IN ('spread', 'total', 'moneyline')"
    params: list = []
    if prediction_ids is not None:
        if not prediction_ids:
            return counts
        where += " AND p.id IN (%s)" % ",".join("?" for _ in prediction_ids)
        params = list(prediction_ids)
    rows = conn.execute(
        "SELECT p.id, p.sport, p.game_id, p.market_type, p.created_utc,"
        "       p.factors_json FROM predictions p"
        f" WHERE {where} ORDER BY p.id", params).fetchall()

    for pred in rows:
        counts["predictions"] += 1
        try:
            dist = (json.loads(pred["factors_json"]) or {}).get("margin_distribution")
        except ValueError:
            dist = None
        if not dist:
            counts["no_distribution"] += 1
            continue
        market = pred["market_type"]
        looks = _looks(conn, pred["game_id"], market)
        if not looks:
            counts["no_quotes"] += 1
            continue
        priced = False
        for ladder in looks:
            best = rung_for(ladder)
            if best is None:
                continue
            priced = True
            quote = best["quote"]
            prob = model_probability(quote["quantity"], dist.get("mean"),
                                     dist.get("sd"), quote["line"])
            if prob is None:
                counts["unusable_distribution"] += 1
                break
            stamp = max(utcnow(), quote["fetched_utc"])
            try:
                conn.execute(
                    "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
                    " sport, game_id, market, quantity, line, side, dist_mean, dist_sd,"
                    " model_prob, venue_price, venue_implied, price_basis, created_utc)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pred["id"], quote["id"], VENUE, pred["sport"], pred["game_id"],
                     market, quote["quantity"], quote["line"], CLAIM_SIDE[market],
                     round(float(dist["mean"]), 4), round(float(dist["sd"]), 4),
                     round(prob, 6), best["price"], best["implied"], best["basis"],
                     stamp))
            except sqlite3.IntegrityError as exc:
                if "UNIQUE" not in str(exc):
                    raise
                counts["already"] += 1
                continue
            counts["claims"] += 1
        if not priced:
            counts["no_priced_rung"] += 1
        conn.commit()
    return counts


def standing_claims(conn: sqlite3.Connection, *, sport: str,
                    market: str) -> list[sqlite3.Row]:
    """ONE CLAIM PER PREDICTION: the last one written before the game started.

    The same rule the rung record uses for a superseded answer, for the same
    reason. A ladder read twice would otherwise put two correlated rows in one
    curve and call the sample twice the size it is.
    """
    return conn.execute(
        "SELECT c.* FROM at_the_line_claims c"
        " JOIN games g ON g.id = c.game_id"
        " WHERE c.sport = ? AND c.market = ?"
        "   AND c.created_utc = (SELECT MAX(c2.created_utc) FROM at_the_line_claims c2"
        "                        WHERE c2.prediction_id = c.prediction_id"
        "                          AND c2.created_utc < g.kickoff_utc)"
        " ORDER BY c.id", (sport, market)).fetchall()


def resolve_claims(conn: sqlite3.Connection) -> dict:
    """Settle every open claim whose game has finished.

    A level game leaves a winner-market claim open and says so: "did the home
    side win" has no answer on a draw, and the rung record voids those rather
    than inventing one. The count is reported so an open row is never mistaken
    for a missing one.
    """
    from ..model import questions

    counts = {"settled": 0, "unanswerable_level_game": 0, "still_open": 0}
    rows = conn.execute(
        "SELECT c.*, g.home_score, g.away_score FROM at_the_line_claims c"
        " JOIN games g ON g.id = c.game_id"
        " WHERE c.resolved_utc IS NULL AND g.status = 'final'"
        " ORDER BY c.id").fetchall()
    for claim in rows:
        home, away = claim["home_score"], claim["away_score"]
        if home is None or away is None:
            continue
        if claim["quantity"] == "home_margin":
            outcome = questions.spread_outcome(home, away, claim["line"])
        elif claim["quantity"] == "total":
            outcome = questions.total_outcome(home, away, claim["line"])
        else:
            if home == away:
                counts["unanswerable_level_game"] += 1
                continue
            outcome = 1 if home > away else 0
        cur = conn.execute(
            "UPDATE at_the_line_claims SET resolved_utc = ?, outcome = ?"
            " WHERE id = ? AND resolved_utc IS NULL",
            (utcnow(), outcome, claim["id"]))
        conn.commit()
        counts["settled"] += cur.rowcount
    counts["still_open"] = conn.execute(
        "SELECT COUNT(*) FROM at_the_line_claims WHERE resolved_utc IS NULL"
    ).fetchone()[0]
    return counts


def coverage(conn: sqlite3.Connection, *, sport: str) -> list[dict]:
    """Per market: how many predictions could be read at the venue's line, and
    the named reason for every one that could not.

    A share with no reasons beside it is a number that hides its own holes.
    """
    out = []
    for market in ("spread", "total", "moneyline"):
        rows = conn.execute(
            "SELECT p.id, p.factors_json,"
            "  (SELECT COUNT(*) FROM at_the_line_claims c WHERE c.prediction_id = p.id) AS claims,"
            "  (SELECT COUNT(*) FROM venue_quotes q WHERE q.game_id = p.game_id"
            "     AND q.market = p.market_type) AS quotes"
            " FROM predictions p WHERE p.sport = ? AND p.market_type = ?",
            (sport, market)).fetchall()
        if not rows:
            continue
        with_claim = sum(1 for r in rows if r["claims"])
        no_dist = sum(1 for r in rows if not r["claims"]
                      and '"margin_distribution"' not in (r["factors_json"] or ""))
        no_quotes = sum(1 for r in rows if not r["claims"] and not r["quotes"]
                        and '"margin_distribution"' in (r["factors_json"] or ""))
        rest = len(rows) - with_claim - no_dist - no_quotes
        out.append({
            "market": market,
            "n": len(rows),
            "with_a_claim": with_claim,
            "share": round(with_claim / len(rows), 4) if rows else None,
            "holes": [
                {"reason": "the prediction carries no frozen distribution",
                 "n": no_dist},
                {"reason": "the venue quoted nothing for the game", "n": no_quotes},
                {"reason": "the venue's ladder carried no usable price", "n": rest},
            ],
        })
    return out
