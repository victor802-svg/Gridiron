"""What KIND of comparison a claim is (AT_THE_PRICE Q1, 2026-09-07).

A claim pairs what the model says about a proposition with what the venue's
price says about the same one. Until today the writer assumed one way of
getting the model's number -- read a frozen margin distribution at the venue's
line -- and refused every question that could not supply one. That is right for
a spread or total quoted at a number the model did not ask about, and wrong for
everything else.

FOUR SHAPES, AND THEY ARE FOUR DIFFERENT KINDS OF COMPARISON:

  LINE-LESS         a winner contract. There is no number to move to, so the
                    blind probability IS the model's answer to the venue's
                    question. Nothing is evaluated, nothing is interpolated,
                    and there is no distribution error in the claim at all.

  RUNG-MATCHED      the venue quotes the number the model was asked about.
                    Same as above: the two questions are the same question.

  RUNG-DIFFERS,     a counting-stat prop at a strike off the model's rung.
  COUNT             The count model's blind-written rate is evaluated at the
                    venue's strike through `model.counts.p_over`.

  RUNG-DIFFERS,     a spread or total at a number off the model's. The frozen
  MARGIN            margin distribution, read at the venue's line (E3/E4).

THEY NEVER MERGE. LAW 6 keeps one sport's curve away from another's because a
mixed number describes neither and flatters reliably; the same argument holds
here one level down. A line-less claim carries no distribution error, so a
curve mixing it with a rung-differing claim would report the distribution as
better than it is. The shape is stored on every claim row so the record can be
read four ways and never as one.

REFUSING IS AN ORDINARY OUTCOME. A question whose shape cannot be determined
gets no claim and is counted by name. The failure this guards against is a
claim assembled from whatever was to hand -- a rate fitted after the line was
visible, a probability about one side used for the other -- which would look
exactly like the others in the table.
"""
from __future__ import annotations

#: The four shapes, and the refusal.
LINE_LESS = "line_less"
RUNG_MATCHED = "rung_matched"
RUNG_DIFFERS_COUNT = "rung_differs_count"
RUNG_DIFFERS_MARGIN = "rung_differs_margin"

SHAPES = (LINE_LESS, RUNG_MATCHED, RUNG_DIFFERS_COUNT, RUNG_DIFFERS_MARGIN)

#: How close two numbers must be to be the same rung. A venue writes 8.5 and so
#: do we; this exists so a float that arrived through JSON does not make two
#: identical numbers look different.
SAME_RUNG = 1e-9

#: The quantities a frozen margin distribution can answer.
MARGIN_QUANTITIES = ("home_margin", "total")


def claim_shape(prediction, venue_line, *, quantity: str) -> dict:
    """Which of the four shapes this question and this quote make, or a refusal.

    `venue_line` is the venue's number FROM THE FIXED PROPOSITION'S SIDE --
    the home view for a spread, the over for a total -- because that is the
    only view the claim is ever about. The caller converts; this function does
    not guess a sign.
    """
    from ..model import counts

    asked = prediction["line_asked"]
    market = prediction["market_type"]
    prop_type = prediction["prop_type"] if "prop_type" in prediction.keys() else None

    if asked is None and venue_line is None:
        return {"shape": LINE_LESS, "why": (
            "the venue's contract has no line and neither did the question, so "
            "the blind probability answers the venue's question exactly")}
    if (asked is None) != (venue_line is None):
        return {"shape": None, "refused": "line_presence_differs", "why": (
            "one of the two has a line and the other does not, so they are not "
            "about the same proposition")}

    if abs(float(asked) - float(venue_line)) <= SAME_RUNG:
        return {"shape": RUNG_MATCHED, "why": (
            f"the venue quotes {float(venue_line):g}, which is the number the "
            f"question was asked at, so the two are the same proposition")}

    if market == "prop":
        if counts.is_count_market(prop_type):
            return {"shape": RUNG_DIFFERS_COUNT, "why": (
                f"a counting stat asked at {float(asked):g} and quoted at "
                f"{float(venue_line):g}, so the count model's own rate is read "
                f"at the venue's strike")}
        return {"shape": None, "refused": "no_distribution_for_this_market", "why": (
            f"{prop_type or 'this market'} is not a counting stat, so nothing "
            f"in the record can move its probability from {float(asked):g} to "
            f"{float(venue_line):g}")}

    if quantity in MARGIN_QUANTITIES:
        return {"shape": RUNG_DIFFERS_MARGIN, "why": (
            f"asked at {float(asked):g} and quoted at {float(venue_line):g}, so "
            f"the frozen margin distribution is read at the venue's number")}

    return {"shape": None, "refused": "unclassifiable", "why": (
        f"a {market or 'nameless'} question with a line, against a "
        f"{quantity or 'nameless'} contract with one, is a pair this writer "
        f"has no rule for")}


def question_takes_the_proposition(prediction, game, *, quantity: str) -> bool | None:
    """Does the question name the same side the claim is stored from?

    THE CARD NEEDS THIS AND THE RECORD DOES NOT. A claim row is stored from
    one fixed proposition -- the home side, or the over -- so that a curve
    compares like with like; a card names the side the model took. When those
    are opposites, a card that shows the claim's numbers under the question's
    words names one team and prices the other, which is what it did on the
    first slate that produced a recommendation.

    None where the mapping cannot say, which is the same answer
    `blind_probability` gives and for the same reasons.
    """
    got = blind_probability(prediction, game, quantity=quantity)
    if got["prob"] is None:
        return None
    return not got.get("complemented", False)


def needs_margin_distribution(shape: str | None) -> bool:
    """Only one shape does, which is the whole finding behind this module."""
    return shape == RUNG_DIFFERS_MARGIN


def needs_count_rate(shape: str | None) -> bool:
    return shape == RUNG_DIFFERS_COUNT


def blind_probability(prediction, game, *, quantity: str) -> dict:
    """The blind probability, restated for the claim's FIXED proposition.

    NO GUESSED SIDES. A prediction's probability is about the side the model
    took, for the subject it named; a claim is always about the home side or
    the over. Converting between them is a mapping, and every branch of it is
    written out -- because the one failure this project has had more than any
    other is a number shown against the opposite side of the question it
    answers.

    Anything not covered here is refused rather than assumed.
    """
    prob = prediction["model_prob"]
    side = prediction["model_side"]
    subject = prediction["subject"]
    if prob is None:
        return {"prob": None, "why": "the prediction carries no probability"}

    if quantity == "home_win":
        # TWO INDEPENDENT FLIPS, and the first version of this read only one.
        # WHICH TEAM the question names, and WHETHER it says that team wins or
        # loses. Six of today's twenty-two baseball moneylines say 'lose', and
        # reading the subject alone turned "the home side loses, 62%" into
        # "the home side wins, 62%".
        if side == "win":
            about_subject = float(prob)
        elif side == "lose":
            about_subject = 1.0 - float(prob)
        else:
            return {"prob": None, "why": (
                f"side {side!r} is neither winning nor losing, so what the "
                f"probability is about cannot be established")}
        if subject == game["home"]:
            return {"prob": about_subject, "complemented": side != "win", "why": (
                f"the question was asked about the home side and took the "
                f"{side} side")}
        if subject == game["away"]:
            return {"prob": 1.0 - about_subject, "complemented": side == "win",
                    "why": (
                f"the question was asked about the away side taking the {side} "
                f"side, so the claim's probability is its complement")}
        return {"prob": None, "why": (
            f"the question names {subject!r}, which is neither side of this "
            f"game, so which team it is about cannot be established")}

    if quantity == "home_margin":
        if subject != game["home"]:
            return {"prob": None, "why": (
                f"the question is about {subject!r} covering, and the claim is "
                f"about the home side covering the venue's number; those are "
                f"the same only when the subject is the home side")}
        if side == "cover":
            return {"prob": float(prob), "complemented": False,
                    "why": "the question took the cover side"}
        if side == "not_cover":
            return {"prob": 1.0 - float(prob), "complemented": True, "why": (
                "the question took the not-cover side, so the claim's "
                "probability is its complement")}
        return {"prob": None, "why": f"side {side!r} is not a spread side"}

    if quantity in ("total", "count"):
        if side == "over":
            return {"prob": float(prob), "complemented": False,
                    "why": "the question took the over"}
        if side == "under":
            return {"prob": 1.0 - float(prob), "complemented": True, "why": (
                "the question took the under, so the claim's probability is "
                "its complement")}
        return {"prob": None, "why": f"side {side!r} is not an over-or-under side"}

    return {"prob": None, "why": f"{quantity!r} is a quantity this mapping has no rule for"}
