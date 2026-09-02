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

The player-prop factors are declared further down, dated 2026-08-30, and they
are a separate set rather than an extension of this one: a moneyline asks which
club wins and a prop asks what one man does, and no instrument serves both.
"""

from __future__ import annotations

from .. import config
from .registry import factor

ADDED = "2026-08-29T00:00:00Z"


@factor(
    added=ADDED,
    sport="mlb",
    applies_to=("moneyline",),
    why="the starting pitching matchup",
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
    why="how much rest the two starters have had",
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
    why="how hard the bullpens have been worked lately",
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
    why="how the two offences have been scoring",
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
    why="how much scoring this park allows",
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
    why="playing at home",
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
    why="rest and travel between the two clubs",
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


# ===========================================================================
# PLAYER PROPS — declared 2026-08-30
# ===========================================================================
#
# Four markets, and they are NOT four variations on one question. Three ask
# about a batter and one asks about the pitcher facing him, so the factor sets
# are disjoint except for the two instruments every prop market needs. That
# split is enforced by the `markets=` argument rather than by a factor returning
# None for questions it has nothing to say about: an always-absent factor is
# item 2's "constant across training" failure arriving by the back door.
#
# THE FIRST TWO FACTORS HERE ARE THE CHECKLIST'S FIRST ITEM, and they are first
# in the file for the same reason they are first in the list. NBA's props
# shipped without them, the fit converged, the coefficients looked reasonable,
# and nothing was visibly wrong. Refitted, `mean_vs_line` became the largest
# coefficient in all four markets.

PROP_ADDED = "2026-08-30T00:00:00Z"

#: The three batting markets, which share a subject and an instrument set.
BATTER_MARKETS = ("batter_hits", "batter_total_bases", "batter_home_runs")
#: All four, for the two instruments every prop question needs.
ALL_PROP_MARKETS = BATTER_MARKETS + ("pitcher_strikeouts",)


#: Markets whose declared ladder has exactly one rung. In these,
#: `mlb_prop_mean_vs_line` reduces to (mean - rung) / rung with `rung` fixed --
#: an affine function of the mean, carrying NO information about which question
#: was asked, because only one question is ever asked.
#:
#: It stays declared, because checklist item 1 requires the question instrument
#: to exist in every market from the first fit and because a market can gain a
#: rung later. But it is LABELLED here rather than left for a reader to work out
#: from a coefficient near zero: in batter_total_bases it fitted at -0.0534,
#: sixth of nine, and that is what an inert instrument looks like rather than a
#: refuted one.
SINGLE_RUNG_MARKETS = tuple(
    m for m, rungs in config.MLB_PROP_LADDER.items() if len(rungs) == 1
)


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=ALL_PROP_MARKETS,
    note=(
        "INERT IN SINGLE-RUNG MARKETS, and that is a property of the ladder "
        "rather than a defect in the factor. Where a market declares one rung "
        f"-- currently {', '.join(SINGLE_RUNG_MARKETS)} -- this reduces to an "
        "affine function of the rolling mean, because the only other term is a "
        "constant. It cannot tell the model which question was asked when only "
        "one question is ever asked. "
        "Measured 2026-08-30: it fitted at -0.0534 in batter_total_bases, sixth "
        "of nine factors, against +2.07 in batter_hits and +1.96 in "
        "pitcher_strikeouts, both of which have real ladders. "
        "RUNGS WERE NOT ADDED TO REPAIR IT. A rung exists because the market "
        "quotes it, not because the model would like more spread; manufacturing "
        "one would be choosing the questions to flatter the instrument. It "
        "stays declared because item 1 requires it in every market from the "
        "first fit, and because a market that gains a rung gains the "
        "instrument back with no code change."
    ),
    why="where the line sits against his recent average",
    rationale=(
        "WHICH RUNG WAS ASKED. A model that cannot see where the line sits "
        "relative to the subject's own recent average is averaging several "
        "different questions into one answer: a batter asked about 0.5 hits and "
        "the same batter asked about 1.5 are not the same question, and neither "
        "are a pitcher's 3.5 and 6.5 strikeouts. Expressed as the gap between "
        "the rolling mean and the asked line, scaled by the line, so it is "
        "comparable across a market asked at half a hit and one asked at six "
        "strikeouts. This is the factor NBA's props shipped without; refitted "
        "with it, it became the dominant coefficient in all four of those "
        "markets, which is why it is declared before anything else here."
    ),
)
def mlb_prop_mean_vs_line(ctx) -> float | None:
    if ctx.rolling_mean is None or not ctx.line_asked:
        return None
    return (ctx.rolling_mean - ctx.line_asked) / max(ctx.line_asked, 1.0)


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=ALL_PROP_MARKETS,
    why="how much his numbers swing from game to game",
    rationale=(
        "Two subjects with the same average are not the same question. A "
        "high-variance batter clears a high line more often than a steady one "
        "with identical output and misses a low one more often too, so "
        "dispersion moves the answer in opposite directions on either side of "
        "the mean. Measured as the standard deviation over the window divided "
        "by the mean, which makes it comparable between a market that lives at "
        "half a hit and one that lives at five strikeouts. Baseball needs this "
        "more than basketball does, not less: a single game is a handful of "
        "plate appearances, so the spread around a batter's mean is enormous "
        "relative to the mean itself."
    ),
)
def mlb_prop_volatility(ctx) -> float | None:
    if ctx.rolling_sd is None or ctx.rolling_mean is None or ctx.rolling_mean <= 0:
        return None
    return ctx.rolling_sd / ctx.rolling_mean


# --- the batter's own inputs ------------------------------------------------

@factor(
    added=PROP_ADDED,
    sport="mlb",
    markets=BATTER_MARKETS,
    applies_to=("prop",),
    note=(
        "REDECLARED 2026-08-31 over a SIXTY-game window, having been declared "
        "on 2026-08-30 over the same fifteen games the rolling mean uses. This "
        "is a REPAIR OF A BROKEN INSTRUMENT, not a refinement of a working one, "
        "and the distinction matters because a later reader who mistakes one "
        "for the other will draw the wrong conclusion from both. "
        "WHAT WAS WRONG: measured over the mean's own window, this factor times "
        "`mlb_batter_expected_pa` reconstructed the rolling mean EXACTLY. Hits "
        "per plate appearance times plate appearances per game is hits per "
        "game. Measured on 2,444 sampled batter-games, corr(rate x pa, mean) = "
        "+1.000 -- not close to one, one. So three declared factors were two "
        "instruments and an identity, and the fit had to reconcile terms that "
        "were algebraically dependent. It did so by making them corrections: "
        "in batter_hits this factor fitted at -5.39 and expected_pa at -0.27, "
        "both causally backwards, which is not something a reader can "
        "interpret. "
        "IT WAS NOT ORDINARY COLLINEARITY and no pairwise check would have "
        "found it -- rate against mean_vs_line correlated -0.077, pa against "
        "mean_vs_line +0.082. The dependency ran through the product. "
        "WHY THE REPAIR IS A LONGER WINDOW: sixty games is what this batter "
        "usually does; fifteen is what he is doing now. The gap between them is "
        "information the mean does not contain, which is what an instrument has "
        "to be. "
        "TIMING: made while all four prop markets stood at ZERO resolutions, "
        "which is the only window in which it is free. A factor redeclared "
        "after a record exists splits that record permanently (LAW 2), so the "
        "choice was to fix it now or live with it."
    ),
    why="what he usually does at the plate",
    rationale=(
        "What the batter USUALLY does, per trip to the plate, over a rolling "
        "sixty games -- his established level, against which the fifteen-game "
        "mean the question is asked about is current form. The gap between the "
        "two is the instrument: a batter whose recent average sits above his "
        "own baseline is having a good fortnight, and a good fortnight predicts "
        "less than an established level does. "
        "The window is deliberately four times the mean's, and that is the "
        "whole design. Measured over the SAME window it is not a second "
        "instrument at all: rate times plate appearances per game IS the mean, "
        "so it would restate what `mlb_prop_mean_vs_line` already reads rather "
        "than adding to it. See the note."
    ),
)
def mlb_batter_rate(ctx) -> float | None:
    if ctx.stat_per_pa is None:
        return None
    return ctx.stat_per_pa


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=BATTER_MARKETS,
    why="how many times he has been getting to the plate",
    rationale=(
        "Plate appearances per game over the window: how many chances the "
        "question gets. THIS IS THE VOLUME INSTRUMENT AND IT STANDS WHERE "
        "TONIGHT'S LINEUP SLOT CANNOT. A scheduled game carries no lineup -- "
        "measured 2026-08-30, zero of 41 games across three future dates had "
        "one, because lineups post about two hours before first pitch -- so the "
        "slot a batter will occupy tonight is not knowable when the forecast is "
        "written, and a factor reading it would be reading the future. Plate "
        "appearances per game is a fact about games already played and carries "
        "the same information directly: a leadoff hitter gets more trips than a "
        "nine-hole hitter, which is what the slot was a proxy for."
    ),
)
def mlb_batter_expected_pa(ctx) -> float | None:
    if ctx.pa_per_game is None:
        return None
    return ctx.pa_per_game


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=BATTER_MARKETS,
    why="where he has been batting in the order",
    rationale=(
        "The batter's average batting-order slot across his most recent five "
        "STARTS, signed so that a higher number means a better slot: 5 minus "
        "the slot, so a leadoff hitter reads +4 and a nine-hole hitter reads "
        "-4. Games he did not start are excluded rather than counted as slot "
        "zero, because he did not have a slot. This is the batter's ROLE, which "
        "is not the same quantity as his recent plate appearances: a three-hole "
        "hitter in a club that goes down in order gets fewer trips than a "
        "leadoff hitter in one that does not, and the two factors separate a "
        "manager's judgement about the player from the traffic in front of him."
    ),
)
def mlb_batter_lineup_slot(ctx) -> float | None:
    if ctx.recent_slot is None:
        return None
    return 5.0 - ctx.recent_slot


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=BATTER_MARKETS,
    why="the left-right matchup against tonight's starter",
    rationale=(
        "The platoon split, as a plain statement of whether the batter has the "
        "advantage: +1 when a left-handed batter faces a right-handed pitcher "
        "or the reverse, -1 when they match, 0 for a switch hitter, who by "
        "definition takes the good side of every matchup and so has neither the "
        "advantage nor the disadvantage the other two describe. The effect is "
        "one of the oldest measured facts in the sport and is why managers "
        "carry a bench. ABSENT, not neutral, when either hand is unknown or the "
        "starter has not been announced -- an unannounced starter has no "
        "handedness, and guessing at one would put a real number where there is "
        "no information at all."
    ),
)
def mlb_batter_platoon(ctx) -> float | None:
    if not ctx.bat_side or not ctx.opposing_hand:
        return None
    if ctx.bat_side == "S":
        return 0.0
    return 1.0 if ctx.bat_side != ctx.opposing_hand else -1.0


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=("batter_hits", "batter_total_bases"),
    why="how often tonight's starter strikes hitters out",
    rationale=(
        "The opposing starter's strikeout rate per batter faced, over his "
        "rolling ten starts. A strikeout is the one out that puts no ball in "
        "play, so a high-strikeout arm removes the chances a hit could come "
        "from before fielding, park or luck get a say. Signed negative so the "
        "factor reads in the direction of the question: a higher value means a "
        "better night for the batter. Per batter faced rather than per nine "
        "innings, because what a hitter faces is one trip to the plate, not a "
        "notional nine innings the starter will not pitch."
    ),
)
def mlb_batter_opposing_k_rate(ctx) -> float | None:
    if ctx.opposing_k_rate is None:
        return None
    return -ctx.opposing_k_rate


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=("batter_total_bases", "batter_home_runs"),
    why="how many home runs tonight's starter gives up",
    rationale=(
        "The opposing starter's home runs allowed per batter faced, over his "
        "rolling ten starts. This is the single most direct input to a home-run "
        "question and a strong one for total bases, where a home run is four of "
        "them at once. Counted only when EVERY start in the window reported the "
        "figure: a partial sum over a full denominator would understate the "
        "rate and read as a stingier pitcher than he is, so a gap makes the "
        "factor absent rather than optimistic."
    ),
)
def mlb_batter_opposing_hr_rate(ctx) -> float | None:
    if ctx.opposing_hr_rate is None:
        return None
    return ctx.opposing_hr_rate


# --- the pitcher's own inputs -----------------------------------------------

@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=("pitcher_strikeouts",),
    why="how often he strikes hitters out",
    rationale=(
        "The starter's own strikeout rate per batter faced over his rolling ten "
        "starts. The rate half of the strikeout question: how often he gets one "
        "when he has the chance. Separated from how many chances he gets, which "
        "is the innings factor, because a pitcher whose rate is holding but "
        "whose outings are being cut short is a different forecast from one "
        "whose rate is falling."
    ),
)
def mlb_pitcher_k_rate(ctx) -> float | None:
    if ctx.pitcher_k_rate is None:
        return None
    return ctx.pitcher_k_rate


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=("pitcher_strikeouts",),
    why="how deep into games he has been going",
    rationale=(
        "Innings per start over the rolling ten: the workload the strikeouts "
        "have to come out of. A strikeout market is bounded by how long a "
        "manager leaves the starter in, and that has been falling across the "
        "sport for a decade, so it is declared rather than assumed to be six "
        "innings. This is the volume half of the same decomposition the batting "
        "markets use, and it is why the rate factor is a rate."
    ),
)
def mlb_pitcher_innings_form(ctx) -> float | None:
    if ctx.pitcher_innings is None:
        return None
    return ctx.pitcher_innings


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=("pitcher_strikeouts",),
    why="how often this lineup strikes out",
    rationale=(
        "The opposing club's strikeouts per plate appearance over its last "
        "thirty games. Lineups differ enormously in how often they strike out, "
        "that difference is a property of a roster rather than of a night, and "
        "it is the other half of every strikeout: someone has to take it. "
        "Thirty games rather than fifteen because plate discipline moves slowly "
        "and a shorter window would mostly measure which pitchers a club "
        "happened to face."
    ),
)
def mlb_pitcher_opponent_k_rate(ctx) -> float | None:
    if ctx.opponent_team_k_rate is None:
        return None
    return ctx.opponent_team_k_rate


@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=("pitcher_strikeouts",),
    why="how much rest he has had",
    rationale=(
        "Days since the starter last pitched, CLIPPED to six either way for the "
        "same reason `mlb_starter_rest_days` clips: a man on sixteen days is not "
        "three times as rested as one on five, he is returning from the injured "
        "list. Rest belongs in a strikeout question specifically because it acts "
        "on workload rather than on quality -- a short-rest starter is on a "
        "shorter leash, and a shorter leash is fewer batters faced."
    ),
)
def mlb_pitcher_prop_rest(ctx) -> float | None:
    if ctx.pitcher_rest is None:
        return None
    return max(-6.0, min(6.0, float(ctx.pitcher_rest)))


# --- shared context ---------------------------------------------------------

@factor(
    added=PROP_ADDED,
    sport="mlb",
    applies_to=("prop",),
    markets=ALL_PROP_MARKETS,
    # DISTINCT FROM THE MONEYLINE FACTOR'S PHRASE, which is the same
    # measurement asked of a different question. Both said "how much
    # scoring this park allows", and the Versions page listed the line
    # twice with nothing to tell them apart -- which reads as a
    # rendering fault. A plain name has to identify ONE factor.
    why="the park's effect on his numbers",
    rationale=(
        "The park's run environment relative to the league, measured over PRIOR "
        "seasons only, exactly as the moneyline factor measures it. Parks differ by "
        "roughly a third between the extremes in runs allowed, and that acts on "
        "every one of these markets: more balls falling in is more hits and "
        "total bases, a smaller park is more home runs, and both are fewer "
        "strikeouts because contact is being rewarded. Restricting it to earlier "
        "seasons makes it cutoff-safe by construction rather than by remembering."
    ),
)
def mlb_prop_park_factor(ctx) -> float | None:
    if ctx.park_runs_pg is None or not ctx.league_runs_pg:
        return None
    return (ctx.park_runs_pg - ctx.league_runs_pg) / ctx.league_runs_pg


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


# ---------------------------------------------------------------------------
# THE RUN LINE AND THE TOTAL (GRIDIRON_16 STEP 3, declared 2026-09-02)
# ---------------------------------------------------------------------------
#
# DECLARED FOR THEIR OWN MARKETS, not widened from the moneyline's. A factor
# carries the date it was added and is scored from it (LAW 2), and the same
# quantity can matter differently to two questions: park run environment
# nudges a moneyline by compressing the gap between clubs, and drives a TOTAL
# directly. Sharing one declaration would mix two measured effects into one
# number and date both from the earlier market.
#
# WIND IS NOT DECLARED, and the reason is the evidence. The brief asks for
# wind at first pitch for outdoor parks through the existing Open-Meteo path.
# That path exists but `weather_forecasts` holds NINE rows, all football: there
# is no stored history for a fit to see, so the factor would be absent on
# essentially every training row. Declaring it would produce exactly the
# broken instrument the constant-factor check and the missing-data rule exist
# to catch. Recorded in FOLLOWUPS with its reason instead.

MARKETS_ADDED = "2026-09-02T00:00:00Z"


# --- the run line ----------------------------------------------------------
#
# The question is "does the home side win by two or more", asked at the fixed
# -1.5 rung for every game. What moves it is not quite what moves a moneyline:
# a run line is won by MARGIN, so anything that widens the distribution of
# margins matters as much as anything that shifts its centre.

@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("spread",),
    why="how much better tonight's starter is than the other one",
    rationale=(
        "The starting pitchers are the largest single input to a baseball "
        "margin, and the run line is a question about margin. Measured as the "
        "difference in runs allowed per nine over each starter's rolling ten "
        "starts, home minus away, so a positive value means the home side has "
        "the worse starter and is less likely to win by two. Declared for the "
        "run line on 2026-09-02, separately from the moneyline's version of "
        "the same input, because a margin question and a win question weight "
        "it differently."
    ),
)
def mlb_runline_starter_edge(ctx) -> float | None:
    if ctx.home_starter_ra9 is None or ctx.away_starter_ra9 is None:
        return None
    return float(ctx.home_starter_ra9) - float(ctx.away_starter_ra9)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("spread",),
    why="how much better one offence has been than the other",
    rationale=(
        "Runs per game over the rolling window, home minus away. A club that "
        "scores more than its opponent concedes wins by more, and winning by "
        "MORE is the whole of the run line question. Declared 2026-09-02."
    ),
)
def mlb_runline_offense_edge(ctx) -> float | None:
    if ctx.home_runs_pg is None or ctx.away_runs_pg is None:
        return None
    return float(ctx.home_runs_pg) - float(ctx.away_runs_pg)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("spread",),
    why="which bullpen is more tired",
    rationale=(
        "Relief innings thrown over the last three days, home minus away. A "
        "tired bullpen concedes late runs, and late runs are where one-run "
        "games become three-run games. 28% of MLB games are decided by a "
        "single run (measured 2026-09-02 over 9,373 finals), so what happens "
        "at the edge of that band decides the run line. Declared 2026-09-02."
    ),
)
def mlb_runline_bullpen_edge(ctx) -> float | None:
    if ctx.home_bullpen_innings is None or ctx.away_bullpen_innings is None:
        return None
    return float(ctx.home_bullpen_innings) - float(ctx.away_bullpen_innings)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("spread",),
    why="how much this park widens the margin",
    rationale=(
        "A high-scoring park widens the distribution of margins: more runs "
        "means more variance, and more variance means more games decided by "
        "two or more. This is the same measured quantity the moneyline uses "
        "and a DIFFERENT claim about it -- there it compresses the gap "
        "between clubs, here it widens the margin. Measured as runs per game "
        "at this venue in PRIOR seasons relative to the league, which is "
        "cutoff-safe by construction. Declared 2026-09-02."
    ),
)
def mlb_runline_park(ctx) -> float | None:
    if ctx.park_runs_pg is None or not ctx.league_runs_pg:
        return None
    return (float(ctx.park_runs_pg) - float(ctx.league_runs_pg)) / float(ctx.league_runs_pg)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("spread",),
    why="how much scoring the two sides produce together",
    rationale=(
        "THE VOLATILITY INSTRUMENT for this market (checklist item 1). The "
        "combined run environment of the two clubs: more total scoring means "
        "a wider margin distribution and more two-run wins, independently of "
        "WHO is better. A margin question needs a measure of spread as well "
        "as one of centre, and this is it. Declared 2026-09-02."
    ),
)
def mlb_runline_volatility(ctx) -> float | None:
    if ctx.home_runs_pg is None or ctx.away_runs_pg is None:
        return None
    return float(ctx.home_runs_pg) + float(ctx.away_runs_pg)


# --- the total -------------------------------------------------------------
#
# The asked total is SELF-GENERATED from the two sides' scoring form, rounded
# to a half. So `mlb_total_vs_line` is not a comparison against somebody
# else's number -- it is the rounding residual, which is real and bounded and
# tells the fit where inside the half-run band the question was asked.

@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("total",),
    why="where the asked total sits against the two sides' form",
    rationale=(
        "THE ASKED-LINE INSTRUMENT for this market (checklist item 1). The "
        "total is asked at the combined scoring form rounded DOWN to a half, "
        "so this is the rounding residual: how far above the asked number the "
        "raw form actually sat, between 0 and 1 runs. It is not a comparison "
        "against a published total -- the question is ours and no market is "
        "consulted to form it (LAW 1). It matters because a question asked at "
        "8.5 off a form of 8.6 is a very different question from one asked at "
        "8.5 off a form of 9.4. Declared 2026-09-02."
    ),
)
def mlb_total_vs_line(ctx) -> float | None:
    if ctx.home_runs_pg is None or ctx.away_runs_pg is None:
        return None
    if ctx.line_asked is None:
        return None
    return (float(ctx.home_runs_pg) + float(ctx.away_runs_pg)) - float(ctx.line_asked)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("total",),
    why="how much the two offences have been scoring",
    rationale=(
        "Combined runs per game over the rolling window: the single largest "
        "input to how many runs a game produces. Declared for the total on "
        "2026-09-02, separately from the moneyline's one-sided version, "
        "because a total is about the SUM and a moneyline about the "
        "difference."
    ),
)
def mlb_total_combined_offense(ctx) -> float | None:
    if ctx.home_runs_pg is None or ctx.away_runs_pg is None:
        return None
    return float(ctx.home_runs_pg) + float(ctx.away_runs_pg)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("total",),
    why="how well the two starters have been suppressing runs",
    rationale=(
        "Both starters' runs allowed per nine, added. Two starters who have "
        "been giving up runs produce a higher-scoring game whichever side is "
        "better, which is precisely what a total asks and what a moneyline "
        "does not. Declared 2026-09-02."
    ),
)
def mlb_total_starter_suppression(ctx) -> float | None:
    if ctx.home_starter_ra9 is None or ctx.away_starter_ra9 is None:
        return None
    return float(ctx.home_starter_ra9) + float(ctx.away_starter_ra9)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("total",),
    why="how tired both bullpens are",
    rationale=(
        "Relief innings thrown by BOTH sides over the last three days. Two "
        "tired bullpens concede more late runs, and late runs are runs. Added "
        "rather than differenced, because a total does not care which side "
        "scores them. Declared 2026-09-02."
    ),
)
def mlb_total_bullpen_load(ctx) -> float | None:
    if ctx.home_bullpen_innings is None or ctx.away_bullpen_innings is None:
        return None
    return float(ctx.home_bullpen_innings) + float(ctx.away_bullpen_innings)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("total",),
    why="how much this park adds to the score",
    rationale=(
        "The most direct input a total has: parks differ by about a third in "
        "the run environment they produce between the extremes. Measured as "
        "runs per game at this venue in PRIOR seasons relative to the league, "
        "cutoff-safe by construction. Declared for the total 2026-09-02."
    ),
)
def mlb_total_park_factor(ctx) -> float | None:
    if ctx.park_runs_pg is None or not ctx.league_runs_pg:
        return None
    return (float(ctx.park_runs_pg) - float(ctx.league_runs_pg)) / float(ctx.league_runs_pg)


@factor(
    added=MARKETS_ADDED,
    sport="mlb",
    applies_to=("total",),
    why="how uneven the two offences are",
    rationale=(
        "THE VOLATILITY INSTRUMENT for this market (checklist item 1). The "
        "absolute difference between the two clubs' scoring rates. Two evenly "
        "matched offences produce a tighter total than a mismatch does, "
        "because a lopsided game can end early in effect -- a side ahead by "
        "eight stops pressing and the other stops facing its best relievers. "
        "A spread instrument, not a centre one. Declared 2026-09-02."
    ),
)
def mlb_total_volatility(ctx) -> float | None:
    if ctx.home_runs_pg is None or ctx.away_runs_pg is None:
        return None
    return abs(float(ctx.home_runs_pg) - float(ctx.away_runs_pg))
