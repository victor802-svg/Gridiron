"""Basketball's declared factors. Availability- and schedule-centric.

Every factor is prefixed `nba_` so a name is self-describing wherever it prints
and no two sports can collide (LAW 6).

Basketball gets a FULLER set than baseball, and the reason is that basketball
games are far less random. Five players take almost every possession, the better
club wins about two thirds of the time rather than three fifths, and a single
absence moves the result more than any single absence in either other sport. So
there is more to know here, and the factors are chosen to say who is playing and
how tired they are — those two things, over and over, in different shapes.

The eight game factors apply to the spread. The five prop factors apply to all
four prop markets, which is deliberate: points, rebounds, assists and threes are
four different questions about the SAME underlying quantities — how long a player
is on the floor, how much of his team's work he does while there, and who else
is competing for it. Each market is still fitted, gated and scored entirely
separately (LAW 4 and LAW 6); only the vocabulary is shared.

One factor from the brief is declared in a changed shape and one measurement is
weaker than asked for. Both say so where they are defined, rather than quietly
being the thing that was easy.
"""

from __future__ import annotations

from .registry import factor

ADDED = "2026-08-29T00:00:00Z"


# ---------------------------------------------------------------------------
# the game: who is playing
# ---------------------------------------------------------------------------

@factor(
    added=ADDED,
    sport="nba",
    applies_to=("spread",),
    rationale=(
        "The load-management factor, and the one that matters most in this "
        "sport. Basketball is five men, so one absence is twenty percent of a "
        "lineup, and clubs now rest healthy stars outright. Measured as the "
        "minutes-weighted share of the club's recent rotation expected to be "
        "available: a rotation is whoever averaged twelve minutes or more over "
        "the last ten games, and each man is weighted by those minutes, so "
        "losing a thirty-six-minute starter costs three times what losing a "
        "twelve-minute reserve does. Signed home minus away. "
        "WHAT COUNTS AS UNAVAILABLE IS DEFINED TO BE THE SAME IN BOTH REGIMES, "
        "and that is the important part. A player is treated as out if he did "
        "not appear in his club's most recent game - strictly prior information, "
        "available identically to a forward prediction and to a backtest - and "
        "additionally if he is listed OUT on the current injury report, which "
        "exists only forward. The forward version therefore sees slightly MORE "
        "than the fitted version did, never less, so the backtest coefficient is "
        "a floor rather than a flattering ceiling. The alternative - reading who "
        "actually played from the box score of the game being predicted - would "
        "have fitted on hindsight the forward path can never have."
    ),
)
def nba_availability_index(ctx) -> float | None:
    if ctx.home_availability is None or ctx.away_availability is None:
        return None
    return ctx.home_availability - ctx.away_availability


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("spread",),
    rationale=(
        "The second night of a back-to-back is the most reliable schedule effect "
        "in basketball: legs are gone, and it is also when a club is most likely "
        "to sit a star. Measured as a differential of a zero-one flag, so it "
        "reads +1 when only the away side is on no rest and -1 when only the "
        "home side is. Declared separately from rest days rather than folded "
        "into it because zero days rest is a categorically different state, not "
        "one step on a continuum: 17.9% of team-games are on zero rest, so this "
        "has room to vary, which was measured before it was declared."
    ),
)
def nba_back_to_back(ctx) -> float | None:
    if ctx.home_rest_days is None or ctx.away_rest_days is None:
        return None
    return float((ctx.away_rest_days == 0) - (ctx.home_rest_days == 0))


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("spread",),
    rationale=(
        "Days since each club last played, home minus away, CLIPPED to four "
        "either way. Rest above about three days is the all-star break or a "
        "schedule quirk rather than more recovery, and the benefit saturates "
        "long before that; without the clip a single February gap would swamp "
        "the coefficient. The clip is a measurement choice made from how the "
        "schedule works, not a fit to what scored well - the same reasoning as "
        "MLB's starter rest."
    ),
)
def nba_rest_days_diff(ctx) -> float | None:
    if ctx.home_rest_days is None or ctx.away_rest_days is None:
        return None
    return float(max(-4, min(4, ctx.home_rest_days - ctx.away_rest_days)))


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("spread",),
    rationale=(
        "How much of the last fortnight each club spent on the road, as a count "
        "of away games, signed away minus home so a positive value favours the "
        "home side. A COUNT RATHER THAN A DISTANCE, and that is a deliberate "
        "weakening of what the brief asked for: real travel distance would need "
        "coordinates for thirty arenas, which is a reference table we would have "
        "to source and cite, and the count already captures the thing that wears "
        "a team down - consecutive nights in hotels rather than miles in the air. "
        "A long homestand and a long road trip are the two states this "
        "distinguishes, and they are the two that matter."
    ),
)
def nba_travel_recent(ctx) -> float | None:
    if ctx.home_road_games is None or ctx.away_road_games is None:
        return None
    return float(ctx.away_road_games - ctx.home_road_games) / 4.0


# ---------------------------------------------------------------------------
# the game: how good, and how fast
# ---------------------------------------------------------------------------

@factor(
    added=ADDED,
    sport="nba",
    applies_to=("spread",),
    rationale=(
        "Possessions per forty-eight minutes over the last ten games, summed "
        "across both clubs rather than differenced, because pace is the thing "
        "that scales a margin. Two evenly matched fast teams produce a wider "
        "spread of final margins than two slow ones, so the same edge in quality "
        "is worth more points in a fast game. Expressed relative to the prior "
        "seasons' league average so the number is a deviation rather than a "
        "level. Possessions are ESTIMATED from the box score with the standard "
        "0.44 free-throw coefficient - the box score does not count them - and "
        "that estimate is stated in the accessor that computes it."
    ),
)
def nba_pace_rolling(ctx) -> float | None:
    if ctx.home_pace is None or ctx.away_pace is None or not ctx.league_pace:
        return None
    return ((ctx.home_pace + ctx.away_pace) / 2.0 - ctx.league_pace) / ctx.league_pace


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("spread",),
    rationale=(
        "Net points per hundred possessions over the last ten games, home minus "
        "away. This is the plainest statement of which club has been better, and "
        "it is per-possession rather than per-game so it does not simply "
        "re-measure pace. It is UNADJUSTED FOR OPPONENT, which is a real "
        "limitation over a ten-game window in an unbalanced schedule; it is "
        "declared as the rolling form measure it is rather than dressed up as a "
        "rating."
    ),
)
def nba_net_rating_rolling(ctx) -> float | None:
    if ctx.home_net_rating is None or ctx.away_net_rating is None:
        return None
    return (ctx.home_net_rating - ctx.away_net_rating) / 10.0


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("spread",),
    rationale=(
        "Home court, in the only shape that can actually vary. A factor that "
        "returns one for every home team is absorbed entirely into the intercept "
        "and fits nothing - that is why MLB's equivalent was deactivated. This "
        "reads 0 when the home club is not in its own building and 1 when it is, "
        "which is exactly how NFL's home_field escapes the same trap. MEASURED "
        "BEFORE BEING DECLARED, and the first measurement was wrong: taking each "
        "club's modal ARENA NAME as its home flagged 33 games in 2024-25, of "
        "which 26 were the same building renamed mid-season. Comparing the "
        "arena's CITY instead - which a sponsorship deal does not change and a "
        "trip to Mexico City does - gives 24 games across the four seasons "
        "2022-26, or 0.49%: Mexico City, London, Berlin, Manchester, Paris, Las "
        "Vegas, Austin. That is thin, four times thinner than football's 2.1%, "
        "and it may well come back as never having varied enough to fit. It is "
        "declared anyway because it CAN vary, the measurement is on record, and "
        "the fit's own bookkeeping will say plainly if it did not."
    ),
)
def nba_home_court(ctx) -> float:
    return 0.0 if ctx.neutral_site else 1.0


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("spread",),
    rationale=(
        "Which rung of the spread ladder this question was asked at. Unlike "
        "baseball's moneyline, a basketball spread question rotates across four "
        "pre-declared rungs, so the model must know WHICH question it is "
        "answering - without it, four different questions are averaged into one "
        "answer. Divided by ten so it sits on a similar scale to the other "
        "factors and the ridge penalty treats them comparably."
    ),
)
def nba_asked_line(ctx) -> float | None:
    if ctx.line_asked is None:
        return None
    return float(ctx.line_asked) / 10.0


# ---------------------------------------------------------------------------
# the props
# ---------------------------------------------------------------------------

@factor(
    added=ADDED,
    sport="nba",
    applies_to=("prop",),
    rationale=(
        "Minutes. Everything a basketball player does is bounded by how long he "
        "is on the floor, and minutes move before production does when a role "
        "changes - a starter cut to twenty-two minutes will miss his number "
        "before his rate says anything is wrong. Rolling mean over the last ten "
        "games, divided by thirty-six so a full starter's load sits near one."
    ),
)
def nba_prop_minutes(ctx) -> float | None:
    if ctx.minutes_mean is None:
        return None
    return ctx.minutes_mean / 36.0


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("prop",),
    rationale=(
        "Usage: the share of his club's shooting and turnovers that this player "
        "accounts for while on the floor. Minutes say how long he plays; usage "
        "says how much of the offence runs through him while he does. The two "
        "together are the volume half of every prop question, and they move "
        "independently - a player can gain minutes and lose usage when a "
        "teammate returns."
    ),
)
def nba_prop_usage(ctx) -> float | None:
    return ctx.usage_rate


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("prop",),
    rationale=(
        "Rate of production per minute in the stat actually being asked about, "
        "over the same ten-game window. This is the efficiency half: two players "
        "with identical minutes and usage still differ in what they convert, and "
        "this is the only prop factor that is specific to the market rather than "
        "shared across all four. Expressed relative to the line asked, so it is "
        "a projection against the question rather than a level."
    ),
)
def nba_prop_rate(ctx) -> float | None:
    if ctx.stat_per_minute is None:
        return None
    return ctx.stat_per_minute


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("prop",),
    rationale=(
        "How much of this stat the opponent's defence has been giving up, "
        "relative to the league. A LEAGUE-WIDE ALLOWANCE, NOT A POSITIONAL ONE, "
        "and the difference from what the brief asked for is stated rather than "
        "glossed: the league's game log carries no position, and deriving one "
        "from a player's own stat line would mean inventing a classification and "
        "then measuring against it - discovering a factor by scanning, which is "
        "what LAW 2 exists to prevent. This is the honest weaker version of the "
        "same idea, and it is labelled as weaker."
    ),
)
def nba_prop_opponent_allowance(ctx) -> float | None:
    if ctx.opponent_allowance is None or not ctx.league_allowance:
        return None
    return (ctx.opponent_allowance - ctx.league_allowance) / ctx.league_allowance


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("prop",),
    rationale=(
        "The teammates competing for the same touches. A scorer's ceiling "
        "depends on who else is taking shots, and a rebounder's on who else is "
        "under the rim; when a co-star sits, the remaining volume has to go "
        "somewhere. Measured as the club's recent total in this stat excluding "
        "the player himself, scaled by the same club's availability tonight, so "
        "it moves when a teammate is ruled out. Absent rather than zero when the "
        "club has no recent window, because zero would read as 'nobody else on "
        "this team scores', which is a strong claim disguised as a missing value."
    ),
)
def nba_prop_teammate_competition(ctx) -> float | None:
    if ctx.teammate_volume is None or ctx.team_availability is None:
        return None
    return (ctx.teammate_volume / 100.0) * ctx.team_availability


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("prop",),
    rationale=(
        "Where the line sits relative to the player's own recent average, as a "
        "fraction of the line. This is the prop equivalent of nba_asked_line and "
        "it exists for the same reason: the line is set at one of three "
        "pre-declared offsets around the player's rolling mean, so without "
        "knowing WHICH offset was asked the model averages three different "
        "questions into one answer. It was missing from the first fit, and the "
        "fit still converged and still looked reasonable - which is precisely "
        "why it is declared explicitly rather than left implicit in the others."
    ),
)
def nba_prop_mean_vs_line(ctx) -> float | None:
    if ctx.rolling_mean is None or not ctx.line_asked:
        return None
    return (ctx.rolling_mean - ctx.line_asked) / max(ctx.line_asked, 1.0)


@factor(
    added=ADDED,
    sport="nba",
    applies_to=("prop",),
    rationale=(
        "Two players with the same average are not the same question. A "
        "high-variance player clears a high line more often than a steady one "
        "with identical output, and misses a low one more often too, so "
        "dispersion changes the answer in opposite directions on either side of "
        "the mean. Measured as the standard deviation of the stat over the "
        "window divided by its mean, which makes it comparable across players "
        "who score twenty and players who score five."
    ),
)
def nba_prop_volatility(ctx) -> float | None:
    if ctx.rolling_sd is None or ctx.rolling_mean is None or ctx.rolling_mean <= 0:
        return None
    return ctx.rolling_sd / ctx.rolling_mean
