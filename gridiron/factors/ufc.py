"""UFC factors (U3), declared with rationales.

EXPLICIT-ABSENT THROUGHOUT. A debutant has no layoff and no finish rate; a
fighter whose reach the source does not carry has no reach gap. Every one of
those returns None and is recorded as absent, never as zero -- a zero layoff
would read as "fought yesterday" and a zero finish rate as "never finishes
anyone", and both are claims nobody made.

NO HOME ADVANTAGE ANYWHERE. Every other sport in this record carries a
home-field term; a fight has no home side, and adding one to match the shape
of the other sports' code would be inventing an effect.

WHAT IS NOT HERE, and why. The brief asks for a SHORT-NOTICE flag -- a bout
announced fewer than 21 days out -- and says to measure the announcement field
first. There is no announcement date on the bout object (docs/UFC_FEASIBILITY
section 8), so the factor is not declared at all rather than declared and
permanently absent. A factor that can never be measured is checklist item 2's
broken instrument: not a weak signal, nothing to fit.

MISSED WEIGHT is absent for the same reason -- the source carries no
weigh-in result, only a scheduled weight class.
"""

from __future__ import annotations

from .registry import factor

ADDED = "2026-09-03T00:00:00Z"

#: Every market a UFC factor may apply to. Named once so a new market cannot
#: quietly inherit a factor that was never thought about for it.
ALL_UFC = ("moneyline", "rounds", "distance")


@factor(
    added=ADDED,
    sport="ufc",
    applies_to=ALL_UFC,
    why="how good the two fighters have been",
    rationale=(
        "The difference between the two fighters' Elo ratings, divided by 100 "
        "so one unit is about a hundred rating points and the ridge penalty "
        "treats it comparably to the other factors. The rating is computed "
        "walk-forward from results only and stored as the number each fighter "
        "carried INTO the bout, so it cannot see the result it is being used "
        "to predict. Its K was FITTED at 80 over 1,091 held-out bouts rather "
        "than chosen, and what it is worth is stated where it is declared: it "
        "calls about 60% of decided bouts, an edge of 0.0136 in Brier over "
        "always saying 0.5. A real signal and a small one. ABSENT when either "
        "fighter has no stored rating -- a debutant has no record to rate."
    ),
)
def ufc_rating_diff(ctx) -> float | None:
    if ctx.rating_a is None or ctx.rating_b is None:
        return None
    return (ctx.rating_a - ctx.rating_b) / 100.0


@factor(
    added=ADDED,
    sport="ufc",
    applies_to=ALL_UFC,
    why="how long each fighter has been out",
    rationale=(
        "The difference in days since each fighter last fought, divided by 365 "
        "so one unit is a year out. Ring rust is one of the oldest claims in "
        "the sport and it is declared here as a claim to be MEASURED rather "
        "than assumed: the coefficient decides whether a long layoff hurts, "
        "and the record will say so from the date this factor was added. "
        "ABSENT when either fighter is making a debut, because a fighter who "
        "has never fought has no layoff -- zero would say the opposite."
    ),
)
def ufc_layoff_diff(ctx) -> float | None:
    if ctx.layoff_a is None or ctx.layoff_b is None:
        return None
    return (ctx.layoff_a - ctx.layoff_b) / 365.0


@factor(
    added=ADDED,
    sport="ufc",
    applies_to=ALL_UFC,
    why="the age difference between the two fighters",
    rationale=(
        "Fighter A's age minus fighter B's, in years, divided by 10. Age is "
        "the plainest available proxy for the part of a career that is behind "
        "somebody, and unlike a record it cannot be padded by matchmaking. It "
        "is declared as a difference rather than two separate ages because a "
        "34-year-old facing a 24-year-old and a 24-year-old facing a "
        "34-year-old are the same situation seen from two sides. ABSENT when "
        "the source carries no date of birth for either fighter."
    ),
)
def ufc_age_gap(ctx) -> float | None:
    if ctx.age_a is None or ctx.age_b is None:
        return None
    return (ctx.age_a - ctx.age_b) / 10.0


@factor(
    added=ADDED,
    sport="ufc",
    applies_to=ALL_UFC,
    why="the reach difference between the two fighters",
    rationale=(
        "Fighter A's reach minus fighter B's, in inches, divided by 10. Reach "
        "is a physical fact the source measures directly rather than a "
        "judgement, which makes it one of the few inputs here that cannot "
        "drift with reputation. Whether it MATTERS is exactly what the "
        "coefficient is for. ABSENT when the source carries no reach for "
        "either fighter, which it usually does -- all 954 stored fighters "
        "carry one."
    ),
)
def ufc_reach_gap(ctx) -> float | None:
    if ctx.reach_a is None or ctx.reach_b is None:
        return None
    return (ctx.reach_a - ctx.reach_b) / 10.0


@factor(
    added=ADDED,
    sport="ufc",
    applies_to=ALL_UFC,
    why="how often each fighter finishes a fight early",
    rationale=(
        "The difference between the two fighters' finishing rates -- the share "
        "of their decided bouts that ended before the final round -- computed "
        "strictly from bouts before this one. It is declared for ALL THREE "
        "markets on purpose: it is an obvious input to how long a bout lasts, "
        "and a plausible one for who wins, and the coefficients decide which. "
        "ABSENT when either fighter has no prior decided bout, because a "
        "finishing rate over zero fights is not a rate."
    ),
)
def ufc_finish_rate_diff(ctx) -> float | None:
    if ctx.finish_rate_a is None or ctx.finish_rate_b is None:
        return None
    return ctx.finish_rate_a - ctx.finish_rate_b


@factor(
    added=ADDED,
    sport="ufc",
    applies_to=ALL_UFC,
    why="how often the two fighters finish fights between them",
    rationale=(
        "The SUM of the two fighters' finishing rates, halved so it sits on a "
        "0-1 scale. The difference above says who is likelier to finish; this "
        "says whether the bout is likely to be finished AT ALL, which is a "
        "different question and the one the rounds and distance markets "
        "actually ask. Two heavy finishers make a short fight regardless of "
        "which of them ends it. ABSENT when either rate is."
    ),
)
def ufc_finish_rate_sum(ctx) -> float | None:
    if ctx.finish_rate_a is None or ctx.finish_rate_b is None:
        return None
    return (ctx.finish_rate_a + ctx.finish_rate_b) / 2.0


@factor(
    added=ADDED,
    sport="ufc",
    applies_to=("rounds", "distance"),
    why="how many rounds the bout is scheduled for",
    rationale=(
        "Three or five, scaled so five reads as 1 and three as 0. A main event "
        "is a different question from a prelim: half of five-round bouts reach "
        "the fifth and just over half of three-round bouts reach the third, so "
        "the two lengths are not one population and a model blind to which it "
        "was given would be averaging them. NOT declared for the moneyline, "
        "where scheduled length says nothing about who wins. ABSENT when the "
        "source does not carry a length -- 19 stored bouts claim FOUR rounds, "
        "which is not a UFC bout length, and those are refused rather than "
        "believed."
    ),
)
def ufc_scheduled_rounds(ctx) -> float | None:
    if ctx.scheduled_rounds not in (3, 5):
        return None
    return 1.0 if ctx.scheduled_rounds == 5 else 0.0


@factor(
    added=ADDED,
    sport="ufc",
    applies_to=("rounds",),
    active=False,
    deactivated=ADDED,
    note=(
        "DECLARED AND RETIRED THE SAME DAY, which is worth explaining rather "
        "than hiding. The brief asked for an asked-line factor on the rounds "
        "market. Under the declared ladder there is exactly ONE rung per bout "
        "length -- 2.5 for a three-round bout, 4.5 for a five -- so the asked "
        "line is a function of `ufc_scheduled_rounds` and carries nothing it "
        "does not. That is precisely the dependency the spread asked-line "
        "ruling of 2026-09-03 spent a session removing, and reintroducing it "
        "in a new sport on the same day would be the same mistake with a "
        "different name. "
        "IT WAS ALSO EMPTY: the fit reported it DROPPED with 0 measured rows, "
        "because `expected_rounds` is never computed -- the only honest source "
        "for it would be the model's own output, and a factor fed by the model "
        "it feeds is circular. "
        "IT COMES BACK when the ladder carries more than one rung per length, "
        "at which point the distance between the rung and the expectation is a "
        "real quantity again."
    ),
    why="how far the question sits from what the model expects",
    rationale=(
        "The rung the rounds question was asked at, minus the length the model "
        "expects, in rounds. This is the same instrument the spread sports use "
        "-- the signed distance between the question and the expectation, not "
        "the question's absolute value -- and it is declared that way here "
        "from the start rather than after a ruling. Under the declared ladder "
        "one rung serves each bout length, so the distance is currently a "
        "function of length alone and will carry more once the expectation "
        "moves per bout. ABSENT when either the rung or the expectation is."
    ),
)
def ufc_asked_distance(ctx) -> float | None:
    if ctx.line_asked is None or ctx.expected_rounds is None:
        return None
    return float(ctx.line_asked) - float(ctx.expected_rounds)
