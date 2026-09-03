"""College football's declared factors. Schedule-adjusted, and lean.

Every factor is prefixed `cfb_` so a name is self-describing wherever it prints
and no two sports can collide (LAW 6).

WHY THIS SPORT NEEDS AN OPPONENT ADJUSTMENT AND THE OTHERS DO NOT
=================================================================
This is the one thing college football gets structurally right or gets
completely wrong, so it is stated before any factor is declared.

In the NFL, thirty-two clubs play a schedule that is deliberately balanced:
every team plays its own division twice, two full divisions, and a pair of
same-place finishers. Raw scoring margin is therefore roughly comparable
between clubs — it is measured against similar opposition.

**In college football it is not.** 136 FBS teams play twelve games, almost all
of them inside their own conference, and the conferences are not remotely of
equal strength. A team can go 11-1 at +25 points a game against opposition that
would lose to half the other conference, while a team in a hard league goes 8-4
at +6 having played nobody easy. Their raw margins say the first team is four
times better. It is not; the numbers are measuring the schedule.

Worse, the two never meet, so nothing in the raw record corrects it. A model
fitted on unadjusted margin in this sport does not have a weak instrument — it
has a **systematically misleading** one, and it will be most wrong precisely
about the teams a reader most wants to know about.

So `cfb_srs_diff` is the mandatory factor: a simple ratings adjustment that
solves for each team's strength given who it actually played, in the same
spirit as the Simple Rating System. It is the only factor here that could not
be replaced by something simpler.

RANKINGS ARE NOT A FACTOR (ruling R-D)
======================================
The AP and coaches' polls are the obvious thing to reach for and they are not
here. They are votes: they respond to results with a delay, they carry
preseason expectation for weeks after it is refuted, and they are influenced by
who plays on television. A model that reads them is partly modelling the
opinions of sportswriters, and when it beats the market it will not be possible
to say which part did it. Everything a poll knows about a team's results, the
opponent-adjusted margin knows sooner and without the opinions.

WHAT IS DELIBERATELY ABSENT
===========================
No player-level factors, because there are no player prop markets to need them
and because 136 rosters of 85 is a data problem out of proportion to three team
markets. No injury data: there is no free feed with college injury reports at
anything like full coverage, and a factor covering a fifth of the slate would
be worse than none.
"""

from __future__ import annotations

from .registry import factor

ADDED = "2026-08-31T00:00:00Z"

#: Markets these factors instrument. Spread and moneyline are both questions
#: about the MARGIN; totals are a question about the combined score, and get a
#: different set below.
MARGIN_MARKETS = ("spread", "moneyline")


# ---------------------------------------------------------------------------
# the margin markets
# ---------------------------------------------------------------------------

@factor(
    added=ADDED,
    sport="cfb",
    applies_to=("spread", "moneyline"),
    why="how good the two teams have been, adjusted for who they played",
    rationale=(
        "THE MANDATORY ONE, and the reason is at the top of this module. "
        "136 teams play twelve games almost entirely inside conferences of "
        "wildly different strength, and the strong and weak leagues barely "
        "meet, so raw scoring margin is not a weak measure of quality here -- "
        "it is a systematically misleading one, and it misleads most about the "
        "teams a reader most wants to know about. A team at +25 against a soft "
        "schedule and one at +6 against a hard one are not four apart. "
        "Solved as a ratings system: each team's rating is its average scoring "
        "margin adjusted by the ratings of the opponents it actually faced, "
        "iterated to convergence. Signed home minus away, and computed "
        "strictly from games completed BEFORE this kickoff -- the "
        "rolling-window leak that once made an NBA model appear to beat the "
        "market by 14% was exactly this computation without that bound. "
        "THE WINDOW IS A ROLLING YEAR, not the current season, and that is a "
        "trade made with open eyes: season-only ratings are ABSENT for every "
        "game until several weeks in, and the mandatory factor being missing "
        "is worse than it being slightly stale. The cost is that September's "
        "ratings are partly about last year's roster."
    ),
)
def cfb_srs_diff(ctx) -> float | None:
    if ctx.home_rating is None or ctx.away_rating is None:
        return None
    return ctx.home_rating - ctx.away_rating


@factor(
    added=ADDED,
    sport="cfb",
    # SPREAD ONLY, and the moneyline's absence from this list is deliberate.
    # A moneyline is not asked at a rung, so this factor would be absent on
    # every single moneyline row -- which is checklist item 2's broken
    # instrument: not a weak signal, nothing to fit at all.
    applies_to=("spread",),
    active=False,
    deactivated="2026-09-03T00:00:00Z",
    why="which number the question was asked at",
    rationale=(
        "CHECKLIST ITEM 1: the model must be told which rung it was asked at, "
        "or it averages several different questions into one answer. College "
        "football's ladder spans -41.5 to +6.5 because its margins do -- 39% "
        "of games are decided by 21 or more -- so the rungs are further apart "
        "here than in any other sport in this record, and a model blind to "
        "which one it was given would be answering a question it cannot see."
    ),
    note=(
        "RETIRED 2026-09-03 by operator ruling and REPLACED, not refuted. "
        "Its successor is `cfb_asked_distance`: the SIGNED DISTANCE between "
        "the rung and the expected margin, which is what this factor was "
        "reaching for and could not express while it carried the rung's "
        "absolute value. A NEW NAME RATHER THAN A NEW DATE ON THE OLD ONE, "
        "because LAW 2's registry refuses to move a factor's activation date "
        "and is right to: the instrument changed, so its forward record "
        "starts today rather than inheriting a score earned by a different "
        "measurement. Rows already written under this factor stand, with "
        "their factor-set version attached. The measured before-and-after "
        "correlation is in docs/closeouts/2026-09-03-asked-line.md. "
        "WHAT FOLLOWS IS THE 2026-09-02 DIAGNOSIS THAT LED HERE, kept "
        "verbatim because the ruling it asked for has now been made. "
        "DOCUMENTED 2026-09-02, NOT CHANGED at the time (ruling CFB-2, "
        "deliberately BLOCKED). Under the nearest-margin rung rule this "
        "factor is a "
        "COARSENED FUNCTION OF `cfb_srs_diff`: the rung is chosen as the "
        "ladder entry nearest minus the expected margin, and the expected "
        "margin is computed from the rating difference. So `cfb_asked_line` "
        "carries almost no information the ratings do not already carry -- it "
        "is the rating difference, rounded to one of seven values. "
        "ITS COEFFICIENT CANNOT BE READ AS AN INDEPENDENT EFFECT, and a "
        "reader comparing it against `cfb_srs_diff` is looking at two views "
        "of one quantity. What this factor is FOR under the nearest-margin "
        "rule -- whether it should be retired, kept as the question's own "
        "label, or replaced by the residual between the rung and the expected "
        "margin -- is an OPERATOR RULING and is not taken here. The ladder "
        "extension of 2026-09-02 changed the coarseness (five rungs to seven) "
        "and not the dependency."
    ),
)
def cfb_asked_line(ctx) -> float | None:
    return None if ctx.line_asked is None else float(ctx.line_asked)


@factor(
    added="2026-09-03T00:00:00Z",
    sport="cfb",
    applies_to=("spread",),
    why="how far the question sits from what the model expects",
    rationale=(
        "HOW FAR THE QUESTION SITS FROM WHAT THE MODEL EXPECTS, in points: the margin the rung demands minus the margin the ratings imply. A home side expected to win by fourteen, asked at -14.5, reads +0.5 -- the question wants half a point more than the model does. Positive means the question asks for MORE than expected, negative means it is easier than expected. Declared 2026-09-03 by operator ruling, replacing the rung itself. WHY THE RUNG ITSELF HAD TO GO. Under the nearest-expected-margin rule the rung is CHOSEN as the ladder point nearest minus the expected margin, so asking the model which rung it was given told it the rating difference a second time, coarsened -- measured at a correlation of -0.94 with cfb_srs_diff. Its coefficient could not be read as an independent effect, because it was not one. WHY THIS IS ORTHOGONAL BY CONSTRUCTION AND NOT BY LUCK: what remains after subtracting the expectation is the ROUNDING RESIDUAL of the ladder's own choice. It carries how far the ladder had to round and nothing about how good the teams are, which is precisely the quantity a model needs in order to know whether it was handed an easy question or a hard one. This is the same instrument mlb_prop_mean_vs_line already is for props: the question's distance from the model's own expectation. ABSENT, not zero, when either rating is missing -- a game with no expected margin has no distance from one, and a zero would read as 'the question sits exactly where the model expects', which is a claim."
    ),
)
def cfb_asked_distance(ctx) -> float | None:
    from ..model import questions

    return questions.asked_distance(
        ctx.line_asked,
        questions.cfb_expected_margin(ctx.home_rating, ctx.away_rating))


@factor(
    added=ADDED,
    sport="cfb",
    applies_to=("spread", "moneyline"),
    why="how much rest each side has had",
    rationale=(
        "College schedules are far less regular than professional ones: a team "
        "may play six days after its last game or nineteen, and open dates are "
        "scattered rather than assigned. The difference is real preparation "
        "time, not just recovery -- a bye week in this sport is a fortnight of "
        "practice against one opponent. Signed home minus away, in days, and "
        "CLIPPED to a fortnight either way: a team returning from a month off "
        "is not three times as prepared as one off a bye, and without the clip "
        "the early-season games where one side has no prior game at all would "
        "dominate the coefficient."
    ),
)
def cfb_rest_diff(ctx) -> float | None:
    if ctx.home_rest is None or ctx.away_rest is None:
        return None
    clip = 14.0
    home = min(float(ctx.home_rest), clip)
    away = min(float(ctx.away_rest), clip)
    return home - away


@factor(
    added=ADDED,
    sport="cfb",
    applies_to=("spread", "moneyline"),
    why="how far the visitors travelled",
    rationale=(
        "Distances in this sport are extreme in a way the NFL's are not: a "
        "conference can now span three time zones, and a team may fly 2,500 "
        "miles for a Saturday noon kick-off. Measured as great-circle miles "
        "between the two schools' home cities, in thousands so the coefficient "
        "reads on the same scale as the others. "
        "ABSENT, NOT ZERO, where either venue could not be placed: the "
        "coordinates come from Open-Meteo's geocoder with a mandatory state "
        "filter, and a venue that does not resolve has no distance rather than "
        "a distance of nothing."
    ),
)
def cfb_travel_kmiles(ctx) -> float | None:
    return None if ctx.travel_miles is None else ctx.travel_miles / 1000.0


@factor(
    added=ADDED,
    sport="cfb",
    applies_to=("spread", "moneyline"),
    why="whether the visitor is from a lower division",
    rationale=(
        "A cross-division game is a different question, and the record knows "
        "it: the loader walks FBS schedules, so an FCS opponent appears only "
        "through the games it played against FBS teams -- disproportionately "
        "its heavy losses. Its rating here is therefore built from partial and "
        "unflattering evidence, and a model that treated it as an ordinary "
        "rating would be confidently wrong in a knowable direction. "
        "This factor is the flag that lets the fit price that separately: 1 "
        "when the visitor is not an FBS team, 0 when it is. It says nothing "
        "about how good the team is -- only that what we know about it is of a "
        "different kind."
    ),
)
def cfb_non_fbs_visitor(ctx) -> float | None:
    if ctx.away_is_fbs is None:
        return None
    return 0.0 if ctx.away_is_fbs else 1.0


# ---------------------------------------------------------------------------
# the totals market — a different question, and its own instruments
# ---------------------------------------------------------------------------

@factor(
    added=ADDED,
    sport="cfb",
    applies_to=("total",),
    why="how much the two teams have been scoring between them",
    rationale=(
        "The totals equivalent of scoring form, and it is a SUM rather than a "
        "difference -- which is the whole distinction between this market and "
        "the margin ones. Two teams that both score 35 and concede 35 produce "
        "a very different total from two that score 17 and concede 17, and "
        "the margin factors cannot tell those apart because both are level. "
        "Measured as the two sides' combined points-for and points-against per "
        "game over their last five completed games, strictly before kickoff."
    ),
)
def cfb_combined_scoring(ctx) -> float | None:
    home, away = ctx.home_form or {}, ctx.away_form or {}
    parts = [home.get("for_pg"), home.get("against_pg"),
             away.get("for_pg"), away.get("against_pg")]
    if any(p is None for p in parts):
        return None
    return sum(parts) / 2.0


@factor(
    added=ADDED,
    sport="cfb",
    applies_to=("total",),
    why="where the total sits against what the two teams usually manage",
    rationale=(
        "CHECKLIST ITEM 1 for the totals market: where the asked line sits "
        "relative to the subject's own recent scoring. Without it, a total set "
        "at the two teams' combined average and one set ten points above it "
        "are the same question to the model. Expressed as a fraction of the "
        "line so it is comparable between a 38-point game and a 70-point one."
    ),
)
def cfb_total_vs_form(ctx) -> float | None:
    if ctx.line_asked is None:
        return None
    home, away = ctx.home_form or {}, ctx.away_form or {}
    parts = [home.get("for_pg"), home.get("against_pg"),
             away.get("for_pg"), away.get("against_pg")]
    if any(p is None for p in parts):
        return None
    expected = sum(parts) / 2.0
    line = float(ctx.line_asked)
    return (expected - line) / max(line, 1.0)


@factor(
    added=ADDED,
    sport="cfb",
    applies_to=("total",),
    why="how much the two teams' scores swing from game to game",
    rationale=(
        "CHECKLIST ITEM 1's second half: two matchups with the same expected "
        "total are not the same question if one is steady and the other swings "
        "by thirty points a week. A volatile pair clears a high total more "
        "often than a steady pair with the same average, and misses a low one "
        "more often. Measured as the mean absolute game-to-game change in each "
        "side's combined score over its last five, averaged across the two."
    ),
)
def cfb_total_volatility(ctx) -> float | None:
    swings = [s for s in (ctx.home_swing, ctx.away_swing) if s is not None]
    if len(swings) < 2:
        return None
    return sum(swings) / len(swings)


@factor(
    added=ADDED,
    sport="cfb",
    applies_to=("total",),
    why="the wind at kickoff",
    rationale=(
        "WEATHER IS A TOTALS FACTOR BEFORE IT IS ANYTHING ELSE. Wind moves the "
        "passing and kicking game, which moves the score, and it moves both "
        "teams' scores the same way -- so it belongs to the question about the "
        "combined total and not to the question about which side wins. "
        "Only asked for OUTDOOR venues: 4 of the 136 FBS stadiums are indoors, "
        "and a wind reading for a dome would be a real number about the wrong "
        "place. A venue whose indoor flag is unknown is treated as unknown, "
        "not as outdoors -- absent rather than assumed. Forecast from "
        "Open-Meteo at the venue's geocoded coordinates."
    ),
)
def cfb_wind_mph(ctx) -> float | None:
    return ctx.wind_mph
