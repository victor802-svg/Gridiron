"""The hypothetical unit ledger (operator ruling D1, 2026-09-06).

LAW 5 was amended, narrowly, to permit ONE thing this module does and nothing
else: against recorded snapshots only, what the record would have come to had
every qualifying forecast been carried at one unit, labelled "hypothetical"
wherever it appears, gated behind the same hundred-settled rule as every other
figure, with a fee-adjusted figure beside it using the venue's published
formula. Everything else the law forbids stays forbidden. There is no size
here, no advice, no account, no placement, and nothing in this file knows what
a unit is worth.

WHY IT IS SEPARATE FROM THE CURVES. A calibration curve answers "when it says
58%, is it?", which is a question about the forecast. This answers "and what
would that have come to?", which is a question about the venue's prices as
much as the model -- a well-calibrated forecaster loses units against a price
that is better calibrated still. Reporting them side by side without the fee
line would flatter, because the fee is the part a reader forgets and the venue
never does.

THE FEE IS DECLARED, NOT MEASURED. The venue's published schedule would not
load from this machine on 2026-09-06 (the page answered HTTP 429 twice), so
the formula below is the one stated in the brief this work was commissioned
from, recorded with that provenance and marked to verify. A figure computed
from an unverified fee is labelled as such in the payload, so the label
travels with the number rather than living in a docstring.
"""
from __future__ import annotations

import math
import sqlite3

from .. import config

#: One unit, one contract. The ledger counts contracts, and a contract's worth
#: is not this project's business.
UNIT = 1.0

FEE_FORMULA_DECLARED = "2026-09-06T00:00:00Z"
FEE_RATE = 0.07
FEE_SOURCE = (
    "the venue's published trading-fee formula as stated in the brief of "
    "2026-09-06: seven per cent of the price times one minus the price, per "
    "contract, rounded up to the cent. NOT VERIFIED against the venue's own "
    "schedule -- that page answered HTTP 429 on the day -- so every figure "
    "computed with it says so."
)
FEE_VERIFIED = False


def fee_per_contract(price: float) -> float:
    """The venue's charge on one contract at this price, rounded up to the cent.

    Highest at an even chance and vanishing at the extremes, which is the shape
    of the published formula: the fee is a fraction of the uncertainty, not of
    the money.
    """
    if price is None or not 0 < price < 1:
        return 0.0
    return math.ceil(FEE_RATE * price * (1.0 - price) * 100.0) / 100.0


def units_from_one_contract(price: float, outcome: int) -> float:
    """What one contract at `price` comes to, before fees.

    A binary contract settles at one or nothing, so a right answer returns the
    rest of the dollar and a wrong one returns nothing. Both directions are
    the same arithmetic; the caller decides which side of the proposition it is
    carrying by passing the price of that side.
    """
    if outcome:
        return round(UNIT * (1.0 - price), 6)
    return round(-UNIT * price, 6)


def qualifying(model_prob: float, venue_implied: float,
               threshold: float | None = None) -> str | None:
    """Which side of the proposition the model disagrees on, or None.

    "Disagreement" is the project's existing declared threshold, unchanged and
    not tuned for this: the model is more confident than the price by more than
    the threshold, or less. Below it there is nothing to count, and a ledger
    that counted every row would be measuring the venue's margin.
    """
    threshold = config.EDGE_DISAGREEMENT_THRESHOLD if threshold is None else threshold
    if model_prob - venue_implied > threshold:
        return "yes"
    if venue_implied - model_prob > threshold:
        return "no"
    return None


def ledger(conn: sqlite3.Connection, *, sport: str, market: str,
           threshold: float | None = None) -> dict:
    """The hypothetical one-unit record for one sport and one market.

    Gated: below `config.MIN_SAMPLE_FOR_EDGE_CLAIM` settled qualifying rows the
    figures are ABSENT from the payload, replaced by the shortfall, exactly as
    the edge figure is. A number this suggestive at n=9 is worse than no
    number.
    """
    from . import at_the_line

    config.require_sport(sport, "paper.ledger")
    claims = [c for c in at_the_line.standing_claims(conn, sport=sport, market=market)
              if c["resolved_utc"] is not None and c["outcome"] is not None]

    counted = 0
    units = 0.0
    units_after_fees = 0.0
    right = 0
    for claim in claims:
        side = qualifying(claim["model_prob"], claim["venue_implied"], threshold)
        if side is None:
            continue
        counted += 1
        # THE PRICE OF THE SIDE THE MODEL DISAGREES ON. `venue_implied` is the
        # venue's price read for OUR proposition, so the complement costs the
        # rest of the dollar and settles on the opposite answer.
        if side == "yes":
            price, outcome = claim["venue_implied"], claim["outcome"]
        else:
            price, outcome = 1.0 - claim["venue_implied"], 1 - claim["outcome"]
        price = min(0.99, max(0.01, round(price, 4)))
        gained = units_from_one_contract(price, outcome)
        units += gained
        units_after_fees += gained - fee_per_contract(price)
        right += 1 if outcome else 0

    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    payload = {
        "sport": sport,
        "market": market,
        "record": "at_the_line",
        "hypothetical": True,
        "threshold": threshold if threshold is not None else config.EDGE_DISAGREEMENT_THRESHOLD,
        "n": counted,
        "minimum_for_a_claim": gate,
        "fee_source": FEE_SOURCE,
        "fee_declared": FEE_FORMULA_DECLARED,
        "fee_verified": FEE_VERIFIED,
        # THE FRIENDLIER OF THE TWO PRICES, said out loud. A claim's price is
        # the midpoint of the venue's quote; carrying the position in earnest
        # would cross the spread and cost more. The ledger is therefore an
        # upper bound on a hypothetical it already labels hypothetical.
        "price_basis_note": (
            "priced at the midpoint of the venue's quote, which is friendlier "
            "than the price an entry would actually meet"),
    }
    if counted < gate:
        payload["renderable"] = False
        payload["shortfall"] = gate - counted
        return payload
    payload["renderable"] = True
    payload["right"] = right
    payload["units"] = round(units, 3)
    payload["units_after_fees"] = round(units_after_fees, 3)
    payload["units_per_forecast"] = round(units / counted, 4)
    payload["units_per_forecast_after_fees"] = round(units_after_fees / counted, 4)
    return payload
