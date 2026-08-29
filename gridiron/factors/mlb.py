"""MLB's declared factors. Lean and pitcher-centric.

Every factor is prefixed `mlb_` so a name is self-describing wherever it prints
and no two sports can collide (LAW 6). Every one is a differential — home minus
away — because a moneyline question is about which side wins, and a level that
moves both clubs together says nothing about that.

Baseball gets FEWER factors than football on purpose. A single game is close to
a coin flip: the best team in a season wins about 60% of its games and the worst
wins about 40%, so the signal available per game is small, and a wide factor set
would mostly be fitting noise with more parameters. Depth here is in the
starting pitcher, who is the one input that changes a baseball game more than
anything else and changes completely every day.

One factor from the brief is deliberately absent; see `mlb_asked_line` at the
bottom of this file for why.
"""

from __future__ import annotations

from .registry import factor

ADDED = "2026-08-29T00:00:00Z"


@factor(
    added=ADDED,
    sport="mlb",
    applies_to=("moneyline",),
    rationale=(
        "The starting pitcher is the single largest lever in a baseball game and "
        "he changes every day, which is what makes baseball different from every "
        "other sport here. Runs allowed per start over a rolling ten starts is "
        "the plainest statement of how a starter has been going. Signed home "
        "minus away, so a positive value means the home side has the better arm."
    ),
)
def mlb_starter_rolling_perf(ctx) -> float | None:
    if ctx.home_starter_ra9 is None or ctx.away_starter_ra9 is None:
        return None
    # Away minus home: fewer runs allowed is better, so this reads positive when
    # the HOME starter is the stronger one.
    return (ctx.away_starter_ra9 - ctx.home_starter_ra9) / 2.0


@factor(
    added=ADDED,
    sport="mlb",
    applies_to=("moneyline",),
    rationale=(
        "Days between starts. A pitcher on short rest has not finished "
        "recovering, and one on unusually long rest has lost rhythm; the "
        "standard five-day turn exists because both extremes cost something. "
        "Signed home minus away, in days, and CLIPPED to six either way: a "
        "starter on sixteen days is not four times as rested as one on four, he "
        "is a man returning from the injured list or being called up, and the "
        "effect of rest saturates long before that. Clipping is a measurement "
        "choice made from how baseball works, not a fit to what scored well."
    ),
)
def mlb_starter_rest_days(ctx) -> float | None:
    if ctx.home_starter_rest is None or ctx.away_starter_rest is None:
        return None
    raw = float(ctx.home_starter_rest - ctx.away_starter_rest)
    return max(-6.0, min(6.0, raw))


@factor(
    added=ADDED,
    sport="mlb",
    applies_to=("moneyline",),
    rationale=(
        "A bullpen that threw six innings over the last three days is short of "
        "its best arms tonight: the leverage relievers are unavailable or "
        "limited, and the innings fall to whoever is left. Derived as innings "
        "played minus the announced starter's innings across the club's games in "
        "the window, so it is an estimate of relief workload rather than a "
        "roster report. Signed away minus home, so positive favours the home side."
    ),
)
def mlb_bullpen_recent_load(ctx) -> float | None:
    if ctx.home_bullpen_innings is None or ctx.away_bullpen_innings is None:
        return None
    return (ctx.away_bullpen_innings - ctx.home_bullpen_innings) / 5.0


@factor(
    added=ADDED,
    sport="mlb",
    applies_to=("moneyline",),
    rationale=(
        "Runs scored per game over a rolling fifteen games. Offence is the other "
        "half of a result and it is far steadier than run prevention across a "
        "short window, because a lineup turns over nine times a night while a "
        "pitcher is one man. Signed home minus away."
    ),
)
def mlb_team_offense_rolling(ctx) -> float | None:
    if ctx.home_runs_pg is None or ctx.away_runs_pg is None:
        return None
    return (ctx.home_runs_pg - ctx.away_runs_pg) / 2.0


@factor(
    added=ADDED,
    sport="mlb",
    applies_to=("moneyline",),
    rationale=(
        "Parks are not the same size or the same altitude, and the run "
        "environment they produce differs by a third between the extremes. A "
        "high-scoring park compresses the gap between two clubs, because more "
        "runs means more variance and more variance favours the weaker side. "
        "Measured as runs per game at this venue in PRIOR seasons relative to "
        "the league, which makes it reproducible from data already loaded and "
        "cutoff-safe by construction."
    ),
)
def mlb_park_factor(ctx) -> float | None:
    if ctx.park_runs_pg is None or not ctx.league_runs_pg:
        return None
    return (ctx.park_runs_pg - ctx.league_runs_pg) / ctx.league_runs_pg


@factor(
    added=ADDED,
    sport="mlb",
    applies_to=("moneyline",),
    active=False,
    deactivated="2026-08-29T00:00:00Z",
    note=(
        "DEACTIVATED 2026-08-29 as a broken instrument, not as a refuted idea, "
        "and caught the same way short_week_diff was: the backtest reported it "
        "CONSTANT across all 4,859 training rows, so there was nothing to fit. "
        "It returns 1.0 unconditionally, because every MLB question asks whether "
        "the HOME club wins and the home club is at home. "
        "A REPAIR WAS AVAILABLE AND WAS MEASURED BEFORE BEING DECLINED. NFL's "
        "home_field is the same idea and does vary, because it reads 0 at a "
        "neutral site and 65 of 3,033 NFL games - 2.1% - are played at one. "
        "Baseball has that case too: Tokyo, Bristol Motor Speedway, Journey Bank "
        "Ballpark. But it was FOUR games out of 2,430 in 2025, 0.16%, which is "
        "the short_week_diff situation again - a differential that varies in one "
        "row in six hundred is not an instrument, it is a rounding error with a "
        "name. The repair was not made because measuring it first showed it "
        "would not work, and that measurement is recorded here so nobody "
        "re-derives it. "
        "The quantity itself is not lost. It is absorbed into the intercept, "
        "which fitted at 0.0913 and puts a league-average home club at 52.3% - "
        "baseball's home-field advantage, measured rather than assumed, and "
        "smaller than football's as expected. History stays; the deactivation is "
        "recorded rather than the declaration being deleted."
    ),
    rationale=(
        "The home team bats last, which is worth real outs in a close game, and "
        "plays without travel on a familiar field. Baseball's home edge is the "
        "smallest of the three sports here - around 54% rather than football's "
        "57% - and it is declared so that its size is measured rather than "
        "assumed."
    ),
)
def mlb_home_away(ctx) -> float:
    return 1.0


@factor(
    added=ADDED,
    sport="mlb",
    applies_to=("moneyline",),
    rationale=(
        "Rest and travel, kept as ONE factor because baseball barely has either: "
        "clubs play almost daily and travel between series rather than between "
        "games. Days since each side last played, signed home minus away. It is "
        "declared rather than assumed to be nil, so the record can say whether "
        "the little that exists matters."
    ),
)
def mlb_team_rest_travel(ctx) -> float | None:
    if ctx.home_team_rest is None or ctx.away_team_rest is None:
        return None
    return float(ctx.home_team_rest - ctx.away_team_rest)


# ---------------------------------------------------------------------------
# NOT DECLARED, and why
# ---------------------------------------------------------------------------
#
# `mlb_asked_line` was asked for in the brief, by analogy with NFL's
# `asked_line`. It is not declared, and the reason is the same one that stopped
# a duplicate `rest_days_diff` in D2: an instrument that cannot vary is not an
# instrument.
#
# NFL's `asked_line` exists because the spread question rotates across four
# pre-declared rungs, and a model that cannot see WHICH rung it was asked is
# averaging four different questions into one answer. A moneyline has no rungs.
# "Does the home team win?" is fully specified by the matchup; there is no line
# to choose, so `line_asked` is NULL for every MLB prediction and any factor
# reading it would return the same value every time.
#
# The alternative — rotating the subject between home and away — is worse, not
# better: "does the away team win" is the exact complement of "does the home
# team win", so the model would learn a mirror of itself and the record would
# double-count every game.
#
# Confidence spread, which is what NFL's ladder buys, comes free here: a
# moneyline sits anywhere from about 35% to 70%, so the calibration buckets fill
# without a ladder to fill them.
