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

#: THE MARKETS A GAME FACTOR APPLIES TO (roster #1, 2026-09-04).
#:
#: Named once rather than written into each decorator, so a third game market
#: is added in one place. Eight factors carried `("spread",)` literally and the
#: moneyline needed all eight; editing eight and forgetting the ninth is how a
#: factor set comes to differ from the one its rationale describes.
#:
#: `nba_asked_distance` IS NOT IN HERE and must not be. It measures how far the
#: rung sits from the model's own expectation, and a moneyline has no rung --
#: there is no line to be a distance from. A factor that cannot be measured for
#: a market does not apply to it.
GAME_MARKETS = ("spread", "moneyline")



# ---------------------------------------------------------------------------
# the game: who is playing
# ---------------------------------------------------------------------------

@factor(
    added=ADDED,
    sport="nba",
    applies_to=GAME_MARKETS,
    why="who is available to play",
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
    applies_to=GAME_MARKETS,
    active=False,
    deactivated="2026-08-29T00:00:00Z",
    note=(
        "DEACTIVATED 2026-08-29 in favour of nba_b2b_either, which measures the "
        "LEVEL rather than the difference. "
        "THE NUMBER THAT ORIGINALLY JUSTIFIED THIS WAS WRONG, and the correction "
        "is recorded rather than quietly dropped. The backtest reported the "
        "differential non-zero in only 4.4% of games and the verdict read 'input "
        "almost never varies'. That 4.4% was an ARTEFACT OF THE ROLLING-WINDOW "
        "LEAK: with the cutoff taken on the UTC date, a game fell inside its own "
        "window, days-since-last-game collapsed to zero for both clubs, and the "
        "differential cancelled. Measured on leak-free data it is non-zero in "
        "21.3% of games - not a broken instrument at all. "
        "The replacement is still the better shape: both clubs are on the second "
        "night together in 5.7% of games, where a differential says nothing and "
        "a level says plenty, so the level fires in 27.0% against the "
        "differential's 21.3%. But this is a REFINEMENT, not the rescue of a "
        "dead instrument, and calling it the latter would have entered a false "
        "finding into the record. Compare short_week_diff, which genuinely never "
        "varied (1 game in 544)."
    ),
    why="playing a second night in a row",
    rationale=(
        "The second night of a back-to-back is the most reliable schedule effect "
        "in basketball: legs are gone, and it is also when a club is most likely "
        "to sit a star. Measured as a differential of a zero-one flag, so it "
        "reads +1 when only the away side is on no rest and -1 when only the "
        "home side is."
    ),
)
def nba_back_to_back(ctx) -> float | None:
    if ctx.home_rest_days is None or ctx.away_rest_days is None:
        return None
    return float((ctx.away_rest_days == 0) - (ctx.home_rest_days == 0))


@factor(
    added="2026-08-29T00:00:00Z",
    sport="nba",
    applies_to=GAME_MARKETS,
    why="whether either side is on a second night in a row",
    rationale=(
        "REPAIR of nba_back_to_back, which the schedule cancelled. Measures the "
        "LEVEL rather than the difference: 1 when EITHER side is on the second "
        "night of a back-to-back, 0 when neither is. The hypothesis was never "
        "that tired legs favour one team - it is that a game with a tired team "
        "in it is a different game, higher variance and more prone to a rested "
        "side pulling away, and that shows up in whether a spread is covered "
        "regardless of which club is tired. Zero-rest team-games are 17.9%, so "
        "this fires in roughly a third of games where the differential fired in "
        "4.4%. Same repair, same reasoning, as NFL's short_week_either."
    ),
)
def nba_b2b_either(ctx) -> float | None:
    if ctx.home_rest_days is None or ctx.away_rest_days is None:
        return None
    return float(ctx.home_rest_days == 0 or ctx.away_rest_days == 0)


@factor(
    added=ADDED,
    sport="nba",
    applies_to=GAME_MARKETS,
    why="the rest difference between the two clubs",
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
    applies_to=GAME_MARKETS,
    why="how much of the last fortnight each club spent away",
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
    applies_to=GAME_MARKETS,
    why="how fast both clubs play",
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
    applies_to=GAME_MARKETS,
    note=(
        "JOINTLY FITTED WITH `nba_net_rating_rolling`, MEASURED "
        "2026-09-03. Standardised, this factor is worth +0.200 fitted "
        "alone and +0.536 with the rolling net rating beside it; the "
        "rolling rating is -0.040 alone and -0.440 together. Both inflate "
        "-- by 2.7x and 11x -- and take opposite signs, at a correlation "
        "of 0.791 over 4,594 games. The model is using their DIFFERENCE, "
        "so NEITHER COEFFICIENT MAY BE READ AS ITS OWN FACTOR'S EFFECT. "
        "The pair is named in `config.JOINTLY_READ_FACTORS` and the card "
        "describes it as one reason. Not retired: together they reach a "
        "Brier of .2403 against .2448 for the adjusted factor alone and "
        ".2467 for the rolling rating alone."
    ),
    why="how the two clubs have been playing lately",
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
    added="2026-09-03T00:00:00Z",
    sport="nba",
    applies_to=GAME_MARKETS,
    note=(
        "JOINTLY FITTED WITH `nba_net_rating_rolling`, MEASURED "
        "2026-09-03. Standardised, this factor is worth +0.200 fitted "
        "alone and +0.536 with the rolling net rating beside it; the "
        "rolling rating is -0.040 alone and -0.440 together. Both inflate "
        "-- by 2.7x and 11x -- and take opposite signs, at a correlation "
        "of 0.791 over 4,594 games. The model is using their DIFFERENCE, "
        "so NEITHER COEFFICIENT MAY BE READ AS ITS OWN FACTOR'S EFFECT. "
        "The pair is named in `config.JOINTLY_READ_FACTORS` and the card "
        "describes it as one reason. Not retired: together they reach a "
        "Brier of .2403 against .2448 for the adjusted factor alone and "
        ".2467 for the rolling rating alone."
    ),
    why="how good the two clubs have been, adjusted for who they played",
    rationale=(
        "The difference between the two clubs' Simple Rating System ratings, "
        "in points, divided by ten. A club's rating is its average margin plus "
        "the average rating of the clubs it played, solved by iteration over "
        "every completed game this season -- the same four-line method college "
        "football already uses, and it is fully inspectable for the same "
        "reason. "
        "WHY IT IS DECLARED BESIDE `nba_net_rating_rolling` RATHER THAN "
        "REPLACING IT. The rolling net rating says how a club has played "
        "LATELY, over ten games, and says so unadjusted -- its own rationale "
        "has admitted the limitation since the day it was declared. This says "
        "how good a club has been ALL SEASON against the schedule it actually "
        "faced. Those are different questions and a 4-0 club that has played "
        "nobody answers them differently, which is exactly the case this "
        "factor exists for. Both are active for one factor-set version so the "
        "coefficients can say which carries what, and the variance bookkeeping "
        "that follows is what decides whether both survive. "
        "ABSENT, not zero, before the league has played "
        "`nba.MIN_LEAGUE_GAMES_FOR_SRS` games: on opening night every rating "
        "is zero and a zero difference would read as 'these clubs are equally "
        "good', which is a claim nobody has the evidence to make. Absent too "
        "when either club is unrated."
    ),
)
def nba_srs_diff(ctx) -> float | None:
    if ctx.home_srs is None or ctx.away_srs is None:
        return None
    return (ctx.home_srs - ctx.away_srs) / 10.0



@factor(
    added=ADDED,
    sport="nba",
    applies_to=GAME_MARKETS,
    why="home court",
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
    active=False,
    deactivated="2026-09-03T00:00:00Z",
    note=(
        "RETIRED 2026-09-03 by operator ruling and REPLACED, not refuted. Under the nearest-expected-margin rung rule this factor became a coarsened copy of the rating difference: the rung is chosen as the ladder entry nearest minus the expected margin, and the expected margin is computed from the ratings, so the model was handed the same quantity twice. Measured correlation with the sport's rating factor before retirement is recorded in docs/closeouts/2026-09-03-asked-line.md. ITS SUCCESSOR IS THE SIGNED DISTANCE between the rung and the expected margin, which is what this factor was reaching for and could not express while it carried the rung's absolute value. A NEW NAME RATHER THAN A NEW DATE ON THE OLD ONE, because LAW 2's registry refuses to move a factor's activation date and is right to: the instrument changed, so its forward record starts today rather than inheriting a score earned by a different measurement. Rows already written under this factor stand, with their factor-set version attached."
    ),
    why="which number the question was asked at",
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


@factor(
    added="2026-09-03T00:00:00Z",
    sport="nba",
    applies_to=("spread",),
    why="how far the question sits from what the model expects",
    rationale=(
        "HOW FAR THE QUESTION SITS FROM WHAT THE MODEL EXPECTS, in points: the margin the rung demands minus the margin the ratings imply. A home side expected to win by fourteen, asked at -14.5, reads +0.5 -- the question wants half a point more than the model does. Positive means the question asks for MORE than expected, negative means it is easier than expected. Declared 2026-09-03 by operator ruling, replacing the rung itself. WHY THE RUNG ITSELF HAD TO GO. Under the nearest-expected-margin rule the rung is CHOSEN as the ladder point nearest minus the expected margin, so asking the model which rung it was given told it the rating difference a second time, coarsened -- measured at a correlation of -0.94 with cfb_srs_diff. Its coefficient could not be read as an independent effect, because it was not one. WHY THIS IS ORTHOGONAL BY CONSTRUCTION AND NOT BY LUCK: what remains after subtracting the expectation is the ROUNDING RESIDUAL of the ladder's own choice. It carries how far the ladder had to round and nothing about how good the teams are, which is precisely the quantity a model needs in order to know whether it was handed an easy question or a hard one. This is the same instrument mlb_prop_mean_vs_line already is for props: the question's distance from the model's own expectation. ABSENT, not zero, when either rating is missing -- a game with no expected margin has no distance from one, and a zero would read as 'the question sits exactly where the model expects', which is a claim."
    ),
)
def nba_asked_distance(ctx) -> float | None:
    from ..model import questions

    return questions.asked_distance(
        ctx.line_asked,
        questions.expected_margin("nba", ctx.home_net_rating, ctx.away_net_rating))


# ---------------------------------------------------------------------------
# the props
# ---------------------------------------------------------------------------

@factor(
    added=ADDED,
    sport="nba",
    applies_to=("prop",),
    why="how many minutes he has been playing",
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
    why="how much of the offence runs through him",
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
    why="how fast he produces while he is on the floor",
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
    why="how much this defence gives up in that stat",
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
    why="the teammates competing for the same shots",
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
    why="where the line sits against his recent average",
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
    why="how much his numbers swing from game to game",
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
