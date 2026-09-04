"""Choosing the questions — blind.

`line_asked` is *our* question, not the market's price. It has to be chosen
without any contact with a line, and it has to be chosen by a rule rather than
by taste, or the model gets to pick the questions it likes. Two rules, both
fixed in advance:

**Spreads.** Four pre-declared rungs. Each game is asked at exactly one of them,
selected by a stable hash of the game id. One question per game keeps the
predictions independent — three rungs of the same game are three correlated
looks at one result, and counting them as three would inflate every N on the
scorecard. Rotating across games instead means that over a season all four rungs
are exercised and the whole confidence range gets tested, without pretending a
sample is bigger than it is.

**Props, NFL and NBA.** The line is the player's own recent average, shifted by
one of three pre-declared offsets, again chosen by a stable hash. Asking exactly
at the average would make every answer 50% and the scorecard would learn
nothing.

**Props, MLB.** A DECLARED LADDER instead, and the rung is the one nearest the
subject's own rolling mean -- see `ladder_rung`. The mechanism differs by sport
because what is available differs by sport, and the difference is recorded
rather than smoothed over: nothing publishes NFL prop lines, so an NFL question
asked at 1.2 receptions costs nothing that a question asked at 1.5 would have
bought. Something does publish MLB prop lines, and they sit on a handful of
values, so asking anywhere else would throw away a market comparison this
project has never once been able to make on a prop.

Every rung ends in .5, so nothing can push and every prediction resolves 0 or 1.

Nothing in this module reads a market table, and nothing in it may. The MLB
ladder is a constant in `config`, declared in advance and dated; it is not a
line, it is not fetched, and it does not become one by describing where lines
happen to sit.
"""

from __future__ import annotations

import sqlite3
import zlib

from .. import config
from ..data import repo

#: Home-team spread rungs. Negative means the home side gives points.
#:
#: EXTENDED 2026-09-03 from `(-7.5, -3.5, 0.5, 3.5)` when the operator's
#: ruling brought NFL and NBA under the nearest-expected-margin rule (R4).
#: Four rungs were enough while the rung was chosen by hashing the game id --
#: any four numbers are, because the choice carried no meaning. Chosen by
#: nearest margin they have to REACH, and measured against the fitted
#: expected margins they did not:
#:
#:            refused as beyond the ladder     busiest rung
#:   old (4)        NFL 2.28%  NBA 7.83%       NFL 35.1%  NBA 25.4%
#:   new (11)       NFL 0.26%  NBA 0.60%       NFL 20.2%  NBA 15.2%
#:
#: SEVEN RUNGS WERE ADDED AND NONE WAS MOVED, which is the rule CFB-1 settled
#: on 2026-09-02: predictions already stand at -7.5, -3.5, +0.5 and +3.5, so
#: those numbers stay on the ladder they were asked against (LAW 3). A
#: re-spacing would have read slightly better and would have retired four
#: rungs the record already uses.
SPREAD_LADDER: tuple[float, ...] = (
    -15.5, -11.5, -9.5, -7.5, -5.5, -3.5, -1.5, 0.5, 3.5, 5.5, 7.5,
)

#: When the ladder above was extended, and what it was before.
SPREAD_LADDER_DECLARED = "2026-09-03T00:00:00Z"
SPREAD_LADDER_BEFORE: tuple[float, ...] = (-7.5, -3.5, 0.5, 3.5)

#: COLLEGE FOOTBALL'S OWN LADDER, because NFL's is far too narrow for it.
#: Measured 2026-08-31 over 260 completed 2025 games: home-margin SD is 22.46
#: against the NFL's 12.70, the median home margin is +10, and the quintiles of
#: the actual margin distribution are:
#:
#:      20%   35%   50%   65%   80%
#:     -7.0  +3.0  +10.0 +17.0 +29.0
#:
#: Asking college games at -7.5 to +3.5 would put almost every question on one
#: side of its own answer: 39% of games are decided by 21 points or more, and
#: only 28% by seven or fewer. These five rungs sit near those quintiles, so
#: the four questions land across the distribution instead of bunching under
#: it. Declared in advance and dated, like every other ladder here.
#: EXTENDED 2026-09-02, and the old ladder is kept here rather than replaced
#: in silence.
#:
#:     declared 2026-08-31:  (-24.5, -14.5, -7.5, -0.5, 6.5)
#:     extended 2026-09-02:  (-41.5, -31.5, -24.5, -14.5, -7.5, -0.5, 6.5)
#:
#: WHY. Measured over 1,618 completed 2024-25 games with a rating on both
#: sides, the expected home margin has mean +12.49 and SD 13.84, and its
#: percentiles run +23.2 at the 80th, +30.2 at the 90th and +37.1 at the 95th.
#: Against the old ladder the top rung was chosen for 27.1% of games -- more
#: than a quarter of the record asked the same question -- and on the college
#: slate of 2026-09-05 it was 45 of 60.
#:
#: A rung reached by a quarter of games is not a rung, it is a wall: every
#: mismatch past it collapses onto one number, so the record stops measuring
#: how well the model separates a 25-point favourite from a 45-point one.
#:
#: Two rungs were ADDED and none moved. The top rung is now reached by 5.5%
#: of games, under the 10% the ruling asks for. Moving an existing rung would
#: have made a slightly more even spread (21.4% on the busiest rung against
#: 24.2%) at the cost of retiring numbers that predictions were already asked
#: at -- and those rows stand (LAW 3), so the ladder they were asked against
#: stays on it.
CFB_SPREAD_LADDER: tuple[float, ...] = (
    -41.5, -31.5, -24.5, -14.5, -7.5, -0.5, 6.5)
CFB_SPREAD_LADDER_DECLARED = "2026-08-31T00:00:00Z"
CFB_SPREAD_LADDER_EXTENDED = "2026-09-02T00:00:00Z"

#: How far past the top rung a game may sit before it is REFUSED rather than
#: clamped. A mismatch the ladder cannot reach is not a question the ladder
#: can ask, and silently answering it at the nearest rung would record a
#: confident claim about a number nobody chose. Half the widest gap, so a
#: game inside the ladder's own resolution is still asked.
CFB_RUNG_TOLERANCE = 5.0


class RungOffTheLadder(ValueError):
    """An expected margin the declared ladder cannot ask about."""

#: How far a self-generated total may sit from the two teams' combined scoring
#: form before the question is refused. The total is derived from stored
#: scoring, so a wild value means the inputs are wrong, not that the game is
#: unusual.
CFB_TOTAL_MIN = 20.0
CFB_TOTAL_MAX = 100.0


#: When rung selection stopped being a rotation (ruling R4). Predictions
#: written before this date were asked at a rotated rung and STAND AS WRITTEN
#: (LAW 3): the 60 college spreads of 2026-09-05 are a record of what was
#: claimed, not a draft.
CFB_RUNG_RULE_ACTIVATED = "2026-09-01T00:00:00Z"

#: RETIRED 2026-09-03 as an input, kept as a record of what was assumed.
#:
#: 9.79 was the mean home margin over a 260-game sample, used as the INTERCEPT
#: of the expected margin with an ASSUMED SLOPE OF 1.0 -- that a ten-point
#: rating edge buys ten points of margin. Neither number reproduced when both
#: were measured together over 1,625 games:
#:
#:      assumed    margin = 9.790 + 1.0000 x rating_diff
#:      measured   margin = 4.848 + 0.9351 x rating_diff   (R^2 0.357)
#:
#: THE INTERCEPT WAS NEARLY DOUBLE what the data supports, which is the whole
#: of the defect recorded in FOLLOWUPS as "the college spread base rate is
#: 0.371, not 0.5". A rung chosen against an expectation that runs five points
#: high is a rung the favourite quietly fails, and the record filled with them.
#:
#: THE ASSUMED PAIR DID NOT REPRODUCE. It is kept here in the same words the
#: registry uses for a retired factor, because a reader who finds 9.79 in an
#: old commit needs to know it was a measurement of the wrong thing rather
#: than a number somebody invented.
CFB_HOME_MARGIN_ASSUMED = 9.79
CFB_HOME_MARGIN_ASSUMED_SLOPE = 1.0


#: WHAT THE MODEL EXPECTS THE HOME SIDE TO WIN BY, per sport (2026-09-03).
#:
#: `expected margin = intercept + slope x (home rating - away rating)`, both
#: numbers MEASURED by least squares of the actual margin on the rating
#: difference, over every completed game in the loaded seasons.
#:
#:   nfl  +1.932 + 0.4426 x rating_diff   n=2725  R^2 0.095  resid sd 13.50
#:   nba  +2.078 + 0.5963 x rating_diff   n=4841  R^2 0.148  resid sd 14.29
#:   cfb  +4.848 + 0.9351 x rating_diff   n=1625  R^2 0.357  resid sd 17.39
#:
#: THE SLOPE IS THE PART THAT MATTERS, and assuming it is 1.0 is what went
#: wrong before. A rating difference of ten points does not buy ten points of
#: margin: it buys 4.4 in the NFL and 6.0 in the NBA, because a rating is an
#: average over a season and any single game regresses hard toward it. An
#: instrument built on slope 1.0 expects blowouts that do not arrive, picks a
#: rung too far out, and asks a question the favourite quietly fails.
#:
#: THIS IS NOT FACTOR DISCOVERY (LAW 2). It calibrates the instrument that
#: CHOOSES THE QUESTION -- which rung to ask at -- and never touches a
#: probability. Two numbers per sport, declared in advance and dated, with no
#: search over variants: the same act as measuring CFB_HOME_MARGIN, carried
#: one term further.
#:
#: CFB'S ENTRY IS RECORDED AND NOT YET USED. `cfb_expected_margin` still runs
#: on its original slope of 1.0 and intercept of 9.79, and changing it would
#: change which questions college football asks -- a bigger act than this
#: ruling authorises. The measurement above is the first quantification of the
#: defect already recorded in FOLLOWUPS (spread base rate 0.371, not 0.5): the
#: intercept is roughly double what the data says and the slope is 6% high.
#: It needs an operator ruling, not a quiet edit.
EXPECTED_MARGIN_FIT: dict[str, tuple[float, float]] = {
    "nfl": (1.932, 0.4426),
    "nba": (2.078, 0.5963),
    "cfb": (4.848, 0.9351),
}

#: When the fit above was measured.
EXPECTED_MARGIN_FIT_DECLARED = "2026-09-03T00:00:00Z"


#: THE ROUNDS LADDER, one rung per bout length (2026-09-03).
#:
#: MEASURED over 2,482 stored bouts, on how bouts actually END rather than on
#: what a book posted -- and the difference is stated because it matters. The
#: probe saw an `overUnder` of 1.5 on the one bout it inspected; the
#: distribution of POSTED lines across a season was not measured, because
#: reaching it costs an odds fetch per bout and the outcome distribution
#: answers the question a rung has to answer: where does this split evenly?
#:
#:     3-round bouts (n=2,398)   ended R1 27.9%  R2 16.6%  R3 55.5%
#:     5-round bouts (n=240)     ended R1 16.7%  R2 16.7%  R3 9.6%
#:                               R4 6.7%   R5 50.4%
#:
#: So a 3-round bout is asked at 2.5 -- "does it reach the final round" -- which
#: the record says happens 55.5% of the time. A 5-round bout is asked at 4.5,
#: which splits 50.4/49.6. Both are as close to a coin flip as a whole-round
#: ladder can get, which is the entire job of a rung.
#:
#: NOT 1.5, though a book posted it: over 1.5 on a three-round bout is 72.1% in
#: this record, and a rung that is right three times in four measures the
#: schedule rather than the model.
UFC_ROUNDS_LADDER: dict[int, float] = {3: 2.5, 5: 4.5}
UFC_ROUNDS_LADDER_DECLARED = "2026-09-03T00:00:00Z"


def ufc_rounds_rung(scheduled_rounds: int | None) -> float | None:
    """The declared rung for a bout of this length, or None.

    REFUSED, NOT GUESSED, for any length the ladder does not declare. The
    stored record contains 19 bouts claiming FOUR scheduled rounds, which is
    not a UFC bout length -- the source is wrong about them. Asking a rounds
    question about a bout whose length we do not believe would be a confident
    claim resting on a number nobody can defend, so those bouts get no rounds
    question at all and the absence is recorded as an absence.
    """
    if scheduled_rounds is None:
        return None
    return UFC_ROUNDS_LADDER.get(int(scheduled_rounds))


def expected_margin(sport: str, home_rating: float | None,
                    away_rating: float | None) -> float | None:
    """The home side's expected winning margin, from stored ratings only.

    BLIND BY CONSTRUCTION, and that is why it is built from ratings rather
    than from anything better: the rung has to be chosen BEFORE the model
    runs, because the rung is one of the model's inputs. Anything that could
    see a published line here would make the market an input to the question,
    which LAW 1 forbids and the closure scan would catch.

    ABSENT, not zero, when either rating is missing. A game with no rating has
    no expected margin, and a zero would read as "an even game" -- which is a
    claim, and the wrong one.
    """
    if home_rating is None or away_rating is None:
        return None
    fit = EXPECTED_MARGIN_FIT.get(sport)
    if fit is None:
        return None
    intercept, slope = fit
    return intercept + slope * (home_rating - away_rating)


def asked_distance(line_asked: float | None,
                   expected: float | None) -> float | None:
    """How far the question sits from what the model expects, in points.

    THE SIGN CONVENTION, WRITTEN DOWN BECAUSE GUESSING IT IS THE CLASSIC
    FAILURE HERE. A rung is a spread from the home side's view: the question
    is whether `(home - away) + rung` clears zero, so a rung of -14.5 asks
    "does the home side win by more than 14.5". The margin the question
    DEMANDS is therefore `-rung`.

        distance = (margin demanded) - (margin expected) = -rung - expected

    Positive means the question asks for MORE than the model expects, so the
    model should lean to the under side of it; negative means the question is
    easier than the model's own expectation. A home side expected to win by
    14, asked at -14.5, gives +0.5: the question sits half a point above the
    expectation, which is exactly the rounding the ladder imposes.

    WHY THIS IS ORTHOGONAL TO THE RATING, by construction rather than by
    luck: the rung is CHOSEN as the ladder point nearest `-expected`, so this
    quantity is the rounding residual of that choice. It carries how far the
    ladder had to round, and nothing about how good the teams are. Under the
    old definition -- the rung itself -- it carried the rating twice, once as
    `srs_diff` and once coarsened, which is what `cfb_asked_line` had become.

    This is the same instrument `mlb_prop_mean_vs_line` already is for props:
    the question's distance from the model's own expectation.
    """
    if line_asked is None or expected is None:
        return None
    return -float(line_asked) - float(expected)


def cfb_expected_margin(home_rating: float | None,
                        away_rating: float | None) -> float | None:
    """The home side's expected winning margin, from stored ratings only.

    MEASURED, NOT ASSUMED, from 2026-09-03 by operator ruling. It now reads
    the same `EXPECTED_MARGIN_FIT` table the other two sports use, so college
    football is no longer the one sport running on a slope nobody measured.
    `CFB_HOME_MARGIN_ASSUMED` above records what it used to be and why that
    did not reproduce.

    BLIND BY CONSTRUCTION and that is the whole reason it is built from
    ratings rather than from anything better: the rung has to be chosen BEFORE
    the model runs, because the rung is one of the model's inputs. Anything
    that could see a published line here would make the market an input to the
    question, which LAW 1 forbids and the closure scan would catch.
    """
    return expected_margin("cfb", home_rating, away_rating)


def cfb_spread_rung(game_id: str, expected_margin: float | None = None) -> float:
    """The declared rung NEAREST to a coin flip for this game (ruling R4).

    WHY THE ROTATION WAS REPLACED, measured on the college slate of
    2026-09-05: 76% of all 177 picks claimed 70% or better, and on the spread
    the confidence was concentrated exactly where the rung was furthest from
    the answer -- 77% of cross-division games claimed 90%+, against 20% of
    FBS-against-FBS ones. Asking "does North Dakota State cover -0.5 against
    Fordham" when the expected margin is sixty points is not a question, and a
    record full of them measures the schedule rather than the model.

    It was NOT a scale bug. The probability path is a logistic over fitted
    contributions and contains no standard deviation at all; the measured
    22.46 reaches only the market comparison, where it produces a sane mean
    implied probability of 0.739 across the same sixty games.

    The rung is chosen nearest to MINUS the expected margin, because the
    question is whether `(home - away) + line` clears zero: a home side
    expected to win by fourteen is asked at -14.5, which is the rung that
    actually asks something.

    Falls back to the rotation ONLY when no rating exists -- the first games
    of a team's life in the record -- and that fallback is a declared absence
    rather than a preference.
    """
    if expected_margin is None:
        return CFB_SPREAD_LADDER[stable_index(game_id, len(CFB_SPREAD_LADDER))]
    target = -float(expected_margin)
    nearest = min(CFB_SPREAD_LADDER, key=lambda rung: (abs(rung - target), rung))
    # FAIL LOUDLY, NEVER CLAMP (ruling CFB-1, 2026-09-02). A game the ladder
    # cannot reach is refused and recorded absent; clamping it to the end rung
    # would store a confident claim about a number nobody chose, and would do
    # it precisely on the games where the model is least tested.
    if abs(nearest - target) > CFB_RUNG_TOLERANCE:
        raise RungOffTheLadder(
            f"{game_id}: an expected margin of {expected_margin:+.1f} wants a "
            f"rung near {target:+.1f}, and the declared ladder's nearest is "
            f"{nearest:+.1f} -- {abs(nearest - target):.1f} away. The ladder "
            f"runs {CFB_SPREAD_LADDER[0]:+.1f} to {CFB_SPREAD_LADDER[-1]:+.1f} "
            f"and is extended by a dated declaration, never stretched to fit "
            f"one game. No spread question is asked here."
        )
    return nearest


def cfb_total_asked(home_ppg: float | None, away_ppg: float | None) -> float | None:
    """The total to ask about: the two teams' combined scoring form, to a half.

    BLIND BY CONSTRUCTION. The only inputs are points-per-game computed from
    our own stored results; no published total is consulted, and this module
    cannot reach one. That is the whole difference between asking our question
    and grading ourselves against the market's.

    Returns None when either side has no scoring history yet -- the first
    weekend of a season, or a team new to the record. An absent question is
    recorded as absent; it is never asked at a guessed number, which would be a
    strong claim wearing a missing value's clothes (checklist item 5).

    The half-point is not decoration: a whole number can push, and a pushed
    question has no answer to score.
    """
    if home_ppg is None or away_ppg is None:
        return None
    combined = float(home_ppg) + float(away_ppg)
    if not CFB_TOTAL_MIN <= combined <= CFB_TOTAL_MAX:
        return None
    return _round_to(combined, 1.0) + 0.5


# ---------------------------------------------------------------------------
# MLB run line and totals (GRIDIRON_16 STEP 3, built 2026-09-02)
# ---------------------------------------------------------------------------
#
# THE VOID RULES ARE WRITTEN HERE, BEFORE THE FIRST PREDICTION (checklist item
# 7). Deciding after seeing results which non-answers count is choosing which
# losses to keep.
#
#   * A GAME THAT NEVER FINISHED -> VOID once it is clearly not going to. A
#     postponement is the ordinary case in baseball and it is not a loss: the
#     question was never answered.
#
#   * A GAME SHORTENED BEFORE REGULATION -> resolves by THE LEAGUE'S RULING,
#     which is the score in the record. A rain-shortened game called after five
#     innings is an official game with an official result; both the run line
#     and the total are settled against it exactly as a nine-inning game is.
#     This is the one rule that could reasonably have gone the other way, and
#     it goes this way because the league's own answer is the answer: inventing
#     a second standard would mean the record disagreed with the sport.
#
#   * A SUSPENDED GAME COMPLETED ON A LATER DATE -> settles on the final score
#     whenever it is completed, on the same rule: the league's ruling is the
#     answer. It does not become a different question for having taken two
#     days.
#
#   * A GAME WITH NO SCORE RECORDED after it is final -> VOID with the reason
#     stated. An unreadable result is not a zero.
#
# The bound on "never going to finish" is the same four days the prop rules
# use, so the two cannot drift apart and disagree about when a game is gone.

#: The market's rung, and it is FIXED. Every MLB run line ESPN carries is
#: +/-1.5 -- 71 of 71 in the feasibility probe, no exceptions. So the question
#: is asked at exactly the rung the market asks at, without consulting the
#: market to find it: the number is declared here, dated, from measured
#: history, exactly as a prop ladder is (LAW 1).
MLB_RUN_LINE = 1.5
MLB_RUN_LINE_DECLARED = "2026-09-02T00:00:00Z"

#: Bounds on a self-generated total, so an absurd one is refused rather than
#: asked. From `config.MLB_SCORE_DISTRIBUTION`: mean 8.97, sd 4.511 over 9,373
#: games. These are roughly the mean +/- three standard deviations, rounded
#: outward to whole runs, and a combined form outside them means the inputs are
#: wrong rather than the game being remarkable.
MLB_TOTAL_MIN = 4.0
MLB_TOTAL_MAX = 18.0


def mlb_total_asked(home_rpg: float | None, away_rpg: float | None) -> float | None:
    """The total to ask about: the two sides' combined scoring form, to a half.

    BLIND BY CONSTRUCTION, exactly as `cfb_total_asked` is. The only inputs are
    runs per game computed from our own stored results; no published total is
    consulted and this module cannot reach one. That is the whole difference
    between asking our question and grading ourselves against the market's.

    Returns None when either side has no scoring history -- the first days of a
    season, or a club new to the record. An absent question is recorded absent;
    it is never asked at a guessed number, which would be a strong claim
    wearing a missing value's clothes (checklist item 5).

    THE HALF IS NOT DECORATION. The probe found 39 of 71 published MLB totals
    are whole numbers, which can push: 8 runs against a total of 8 is neither
    over nor under, and a pushed question has no answer to score. Asking at a
    half means this question always has one.
    """
    if home_rpg is None or away_rpg is None:
        return None
    combined = float(home_rpg) + float(away_rpg)
    if not MLB_TOTAL_MIN <= combined <= MLB_TOTAL_MAX:
        return None
    return float(int(combined)) + 0.5


def run_line_outcome(home_score: int, away_score: int, line_asked: float) -> int:
    """1 if the home side covered the run line it was asked to give.

    `line_asked` is the home team's handicap: -1.5 means the home side gives a
    run and a half, so it covers by winning by two or more. A half-run line
    cannot push, which is why the market uses one and why this has no third
    state.

    THE QUESTION IS ALWAYS ASKED FROM THE HOME SIDE, at -1.5, for every game.
    Which team the MARKET makes the favourite is not consulted -- that would
    be the market choosing our question, and LAW 1 forbids it. The market's
    own side is read afterwards, when the comparison is drawn.
    """
    return 1 if (home_score - away_score) + line_asked > 0 else 0


def total_outcome(home_score: int, away_score: int, line_asked: float) -> int:
    """1 if the combined score went OVER the total asked.

    A half-point line cannot push, so there is no third state -- which is why
    `cfb_total_asked` always returns one.
    """
    return 1 if (home_score + away_score) > line_asked else 0

#: Prop line offsets, as a fraction of the player's rolling average.
PROP_OFFSETS: tuple[float, ...] = (-0.30, 0.0, 0.30)

#: A player needs this many prior games before we will ask a question about them.
MIN_PROP_HISTORY = 3

#: ...and must have actually played within this many completed weeks. A player
#: who has quietly stopped appearing - benched, on a new team, hurt but not yet
#: on the report - resolves VOID and teaches the scorecard nothing while
#: occupying a slot on a capped slate. Quality of resolution over quantity of
#: predictions. This is an eligibility rule, not a model change: it decides
#: which questions are worth asking, never what the answer is.
MAX_WEEKS_SINCE_PLAYED = 2


def stable_index(key: str, modulus: int) -> int:
    """A deterministic, platform-independent rotation.

    `hash()` is salted per process and would silently change which question was
    asked between runs, which would make the record irreproducible.
    """
    return zlib.crc32(key.encode("utf-8")) % modulus


def spread_rung(game_id: str, expected: float | None = None,
                ladder: tuple[float, ...] | None = None) -> float:
    """The declared rung nearest to a coin flip for this game.

    R4 EXTENDED TO NFL AND NBA by operator ruling, 2026-09-03. The rung is
    chosen nearest to MINUS the expected margin, because the question is
    whether `(home - away) + rung` clears zero: a home side expected to win
    by fourteen is asked at -14.5, which is the rung that actually asks
    something. College football has worked this way since 2026-09-02 and this
    is the same rule, on the same reasoning, for the other two.

    WHAT THE ROTATION WAS DOING WRONG. Hashing the game id spreads questions
    evenly across the ladder, which sounds fair and is not: it asks "does the
    home side cover -7.5" as often of a team expected to lose as of one
    expected to win by twenty. Those are not hard questions, they are
    unbalanced ones, and a record full of them measures the fixture list.

    Falls back to the rotation ONLY when no expected margin exists -- a team
    with no rating yet -- and that fallback is a declared absence rather than
    a preference.
    """
    # EACH SPORT ON ITS OWN LADDER. Basketball's rungs are spaced for
    # basketball -- a four-point NBA spread is a coin flip where a four-point
    # NFL one is not -- and routing the NBA through football's ladder would
    # undo a deliberate choice. The default is football's because this
    # function has always been football's.
    rungs = SPREAD_LADDER if ladder is None else ladder
    if expected is None:
        return rungs[stable_index(game_id, len(rungs))]
    target = -float(expected)
    nearest = min(rungs, key=lambda rung: (abs(rung - target), rung))
    # FAIL LOUDLY, NEVER CLAMP (ruling CFB-1, 2026-09-02), and the same
    # exception type college football raises. A game the ladder cannot reach
    # is refused and recorded absent; clamping it to the end rung would store
    # a confident claim about a number nobody chose, precisely on the games
    # where the model is least tested. Measured refusal rate on the extended
    # ladder: 0.26% of NFL games and 0.60% of NBA ones.
    if abs(nearest - target) > CFB_RUNG_TOLERANCE:
        raise RungOffTheLadder(
            f"{game_id}: an expected margin of {expected:+.1f} wants a rung "
            f"near {target:+.1f}, and the declared ladder's nearest is "
            f"{nearest:+.1f} -- {abs(nearest - target):.1f} away. The ladder "
            f"runs {rungs[0]:+.1f} to {rungs[-1]:+.1f} and is "
            f"not stretched to fit a game beyond it."
        )
    return nearest


def spread_outcome(home_score: int, away_score: int, line_asked: float) -> int:
    """1 if the home team covered `line_asked`.

    Convention is the ordinary one: `-3.5` means home must win by four or more.
    """
    return 1 if (home_score - away_score) + line_asked > 0 else 0


def _round_to(value: float, step: float) -> float:
    return round(value / step) * step


def prop_line_asked(rolling_mean: float, key: str, stat: str) -> float:
    """The player's own recent average, shifted by a pre-declared offset.

    Rounded in the stat's own units - to five for yardage, to one for receptions
    and touchdowns - then given a trailing .5 so nothing can push.
    """
    offset = PROP_OFFSETS[stable_index(key, len(PROP_OFFSETS))]
    step = config.PROP_LINE_STEP[stat]
    base = _round_to(max(rolling_mean * (1.0 + offset), 0.0), step)
    if stat in ("receptions", "passing_tds"):
        # Counting stats sit at 0.5, 1.5, 2.5 ... never below half.
        return max(base, 1.0) - 0.5
    return max(base, step) + 0.5


def prop_outcome(actual: float, line_asked: float) -> int:
    return 1 if actual > line_asked else 0


class RungOffLadder(ValueError):
    """A question was formed at a line the declared ladder does not contain."""


def ladder_rung(rolling_mean: float, market: str) -> float:
    """The declared rung nearest the subject's own rolling mean (ruling R1).

    Blind by construction: the only input that moves the answer is a number
    computed from our own stored stats. The candidate set comes from
    `config.MLB_PROP_LADDER`, which is a constant declared in advance and dated,
    and this function cannot reach anything else.

    Ties go to the LOWER rung, stated here rather than left to whichever way
    `min` happens to break them. A tie means the mean sits exactly between two
    questions; the lower rung is the one more of the distribution clears, so it
    is the question with the larger sample behind it on both sides.
    """
    rungs = config.MLB_PROP_LADDER.get(market)
    if not rungs:
        raise RungOffLadder(f"no declared ladder for market {market!r}")
    return min(rungs, key=lambda rung: (abs(rolling_mean - rung), rung))


def assert_on_ladder(line_asked: float, market: str) -> None:
    """Refuse a line the ladder does not contain.

    A question formed off the ladder is not a smaller version of the same
    record: it is asked at a rung nothing published a price for, so it cannot be
    compared with the market, and it is asked at a rung no other prediction in
    its category shares, so it is not comparable with them either. Both halves
    of what the ladder buys are lost silently, which is why this raises rather
    than warns.
    """
    rungs = config.MLB_PROP_LADDER.get(market)
    if not rungs:
        raise RungOffLadder(f"no declared ladder for market {market!r}")
    if line_asked not in rungs:
        raise RungOffLadder(
            f"{market} was asked at {line_asked}, which is not on the declared "
            f"ladder {rungs}. The ladder is declared in config, dated "
            f"{config.MLB_PROP_LADDER_DECLARED}, and a rung outside it makes the "
            "prediction incomparable with both the market and the rest of its "
            "own category."
        )


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

#: Which position supplies which market. Fixed so selection cannot drift
#: towards whoever happens to look good.
STAT_POSITIONS = {
    "passing_yards": ("QB",),
    "passing_tds": ("QB",),
    "rushing_yards": ("RB",),
    "receiving_yards": ("WR", "TE"),
    "receptions": ("WR", "TE", "RB"),
}
STAT_VOLUME_COLUMN = {
    "passing_yards": "att",
    "passing_tds": "att",
    "rushing_yards": "car",
    "receiving_yards": "tgt",
    "receptions": "tgt",
}
STAT_MEAN_COLUMN = {
    "passing_yards": "pass_yds",
    "passing_tds": "pass_tds",
    "rushing_yards": "rush_yds",
    "receiving_yards": "rec_yds",
    "receptions": "rec",
}
#: The volume column on `player_week_stats` behind each market, used for a
#: player's share of his own offence.
STAT_VOLUME_STAT = {
    "passing_yards": "attempts",
    "passing_tds": "attempts",
    "rushing_yards": "carries",
    "receiving_yards": "targets",
    "receptions": "targets",
}


def players_ruled_out(
    conn: sqlite3.Connection, season: int, week: int, team: str
) -> set[str]:
    """Names the injury report lists as Out.

    They are excluded from selection. This is not the model ducking a hard
    question: a prediction about a player already ruled out would resolve VOID
    and teach the scorecard nothing, while consuming a slot on a slate that is
    deliberately capped.
    """
    return {
        r["player_name"]
        for r in repo.injuries_for(conn, season, week, team)
        if (r["report_status"] or "") == "Out" and r["player_name"]
    }


def prop_candidates(conn: sqlite3.Connection, game: sqlite3.Row) -> list[dict]:
    """Every prop question this game could support, in a deterministic order.

    Eligibility is by usage only: the highest-volume qualifying player at the
    position, with enough history to have a rolling average. No filtering on how
    interesting the answer might be, because that would be choosing the
    questions after seeing the data.
    """
    out: list[dict] = []
    for team in (game["home"], game["away"]):
        roster = repo.team_players(conn, game["season"], team, game["week"])
        ruled_out = players_ruled_out(conn, game["season"], game["week"], team)
        for stat in config.PROP_MARKETS:
            positions = STAT_POSITIONS[stat]
            volume_col = STAT_VOLUME_COLUMN[stat]
            eligible = [
                r
                for r in roster
                if (r["position"] or "") in positions
                and r["games"] >= MIN_PROP_HISTORY
                and (r[volume_col] or 0) > 0
                and (r["player_name"] or "") not in ruled_out
                # Prior-season rows are kept for early-season coverage, but past
                # week 1 a player must have actually appeared for THIS club this
                # season. Without it, a traded player stays on his old team's
                # slate and can be asked the same question twice in one week.
                and (game["week"] <= 1 or (r["games_this_season"] or 0) >= 1)
                and (
                    game["week"] <= 1
                    or (
                        r["last_week_played"] is not None
                        and game["week"] - r["last_week_played"] <= MAX_WEEKS_SINCE_PLAYED
                    )
                )
            ]
            if not eligible:
                continue
            best = max(eligible, key=lambda r: (r[volume_col], r["player_id"]))
            mean = best[STAT_MEAN_COLUMN[stat]] or 0.0
            if mean <= 0:
                continue
            out.append(
                {
                    "game_id": game["id"],
                    "player_id": best["player_id"],
                    "player_name": best["player_name"],
                    "position": best["position"],
                    "team": team,
                    "stat": stat,
                    "volume": float(best[volume_col] or 0.0),
                    "rolling_mean_hint": float(mean),
                }
            )
    out.sort(key=lambda c: (c["stat"], c["team"], c["player_id"]))
    return out


def _attach_line(candidate: dict) -> dict:
    candidate["line_asked"] = prop_line_asked(
        candidate["rolling_mean_hint"],
        f"{candidate['game_id']}:{candidate['player_id']}:{candidate['stat']}",
        candidate["stat"],
    )
    return candidate


def select_props(
    conn: sqlite3.Connection, game: sqlite3.Row, per_game: int | None = None
) -> list[dict]:
    """Questions from one game, rotating the starting point by game id so a
    single-game slate is not all quarterbacks."""
    per_game = config.PROPS_PER_GAME if per_game is None else per_game
    candidates = prop_candidates(conn, game)
    if not candidates or per_game <= 0:
        return []
    start = stable_index(game["id"], len(candidates))
    picked = [
        candidates[(start + i) % len(candidates)]
        for i in range(min(per_game, len(candidates)))
    ]
    return [_attach_line(dict(c)) for c in picked]


def select_week_props(
    conn: sqlite3.Connection,
    games: list,
    cap: int | None = None,
    per_game: int | None = None,
) -> list[dict]:
    """The week's prop slate: capped, balanced, deterministic.

    Filled by round-robin across `config.PROP_MARKETS`, which is ordered by
    real-world liquidity. Within a market, candidates are taken by usage. Two
    consequences, both intended:

      * When the cap bites it bites on the thinnest market first, so what
        survives is the part of the slate a person could actually check.
      * The slate is never all quarterbacks, because the round-robin takes one
        from each market before it takes a second from any.

    A per-game ceiling stops one marquee fixture eating the whole week. Quality
    of resolution beats quantity of predictions: a forecast nobody reads is not
    a forecast anybody can check.
    """
    cap = config.PROPS_PER_WEEK if cap is None else cap
    per_game = config.PROPS_PER_GAME if per_game is None else per_game
    if cap <= 0:
        return []

    by_stat: dict[str, list[dict]] = {stat: [] for stat in config.PROP_MARKETS}
    for game in games:
        for candidate in prop_candidates(conn, game):
            by_stat[candidate["stat"]].append(candidate)
    for stat in by_stat:
        # Deterministic: volume descending, then ids. Never a random tiebreak.
        by_stat[stat].sort(key=lambda c: (-c["volume"], c["game_id"], c["player_id"]))

    chosen: list[dict] = []
    per_game_count: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()      # (player_id, stat), once per week
    cursors = {stat: 0 for stat in config.PROP_MARKETS}

    progressed = True
    while len(chosen) < cap and progressed:
        progressed = False
        for stat in config.PROP_MARKETS:
            if len(chosen) >= cap:
                break
            pool = by_stat[stat]
            while cursors[stat] < len(pool):
                candidate = pool[cursors[stat]]
                cursors[stat] += 1
                progressed = True
                key = (candidate["player_id"], candidate["stat"])
                if key in seen:
                    continue        # one question per player per market per week
                if per_game_count.get(candidate["game_id"], 0) >= per_game:
                    continue
                seen.add(key)
                per_game_count[candidate["game_id"]] = (
                    per_game_count.get(candidate["game_id"], 0) + 1
                )
                chosen.append(_attach_line(dict(candidate)))
                break

    chosen.sort(key=lambda c: (c["game_id"], c["stat"], c["player_id"]))
    return chosen
