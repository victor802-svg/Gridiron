"""THE FACTOR REGISTRY — the one place a factor may be declared (LAW 2).

Every factor is a named function that returns one number, declared here with a
dated rationale saying **why it should causally matter**. Nothing is added
because it correlated with something in a backtest. If you go looking through
history for what predicts, you will find things, and most of them will be
noise wearing a suit.

Adding a factor is a deliberate act:
  1. Write the function here with `@factor(...)`, dated, with a real rationale.
  2. Bump `config.FACTOR_SET_VERSION`.
  3. Its score starts accumulating from that date forward. It is never
     backfitted onto predictions made before it existed.

Deactivating is also deliberate: set `active=False` and give `deactivated_utc`
and a note. The row stays. The history stays.

Every function takes a context object (see `context.py`) and returns a float,
or `None` when the input genuinely is not available. `None` is not zero — the
caller substitutes `default` and records that the value was missing, so a
defaulted factor is visible in `factors_json` rather than silently blended in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Factor:
    name: str
    added_utc: str
    rationale: str
    applies_to: tuple[str, ...]
    fn: Callable
    default: float = 0.0
    active: bool = True
    deactivated_utc: str | None = None
    note: str | None = None


REGISTRY: dict[str, Factor] = {}


def factor(
    *,
    added: str,
    rationale: str,
    applies_to: Iterable[str],
    default: float = 0.0,
    active: bool = True,
    deactivated: str | None = None,
    note: str | None = None,
):
    """Declare a factor. The rationale is not decoration; the schema rejects a
    factor whose rationale is shorter than a sentence."""

    def wrap(fn: Callable) -> Callable:
        name = fn.__name__
        if name in REGISTRY:
            raise ValueError(f"factor {name!r} is already declared")
        REGISTRY[name] = Factor(
            name=name,
            added_utc=added,
            rationale=" ".join(rationale.split()),
            applies_to=tuple(applies_to),
            fn=fn,
            default=default,
            active=active,
            deactivated_utc=deactivated,
            note=note,
        )
        return fn

    return wrap


def active_factors(market_type: str) -> list[Factor]:
    return [
        f for f in REGISTRY.values() if f.active and market_type in f.applies_to
    ]


def all_factors(market_type: str | None = None) -> list[Factor]:
    if market_type is None:
        return list(REGISTRY.values())
    return [f for f in REGISTRY.values() if market_type in f.applies_to]


# ===========================================================================
# SPREAD FACTORS
# ===========================================================================

@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    rationale=(
        "Home teams win more than away teams and always have: no travel, a "
        "familiar surface and snap count, crowd noise on the opposing offence, "
        "and the officiating tilt that crowd noise produces. This is the single "
        "most reliable structural asymmetry in the sport."
    ),
)
def home_field(ctx) -> float:
    """1 for a normal home game, 0 at a neutral site."""
    return 0.0 if ctx.neutral_site else 1.0


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    rationale=(
        "Neutral-site games remove home advantage from the home-listed team "
        "while still costing both sides a trip, which is a different game from "
        "the one the home_field factor describes."
    ),
)
def neutral_site(ctx) -> float:
    return 1.0 if ctx.neutral_site else 0.0


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    rationale=(
        "Recovery time is physical. An extra few days is more healing, more "
        "practice reps and more film; the differential is what matters, since "
        "both clubs playing on a short week cancels out."
    ),
)
def rest_diff(ctx) -> float | None:
    if ctx.home_rest is None or ctx.away_rest is None:
        return None
    return float(ctx.home_rest - ctx.away_rest)


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    rationale=(
        "A Thursday game after a Sunday game is a categorically different "
        "preparation, not just a smaller number of rest days: the install week "
        "disappears and soft-tissue injuries do not have time to settle."
    ),
)
def short_week_diff(ctx) -> float | None:
    if ctx.home_rest is None or ctx.away_rest is None:
        return None
    return float((ctx.away_rest <= 4) - (ctx.home_rest <= 4))


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread", "prop"),
    default=0.0,
    rationale=(
        "Distance flown costs sleep and adds a day of logistics for the "
        "visiting side only. Scaled to thousands of miles so the coefficient is "
        "readable; a cross-country trip is roughly 2.5 units."
    ),
)
def travel_kmiles(ctx) -> float | None:
    if ctx.subject_travel_miles is None:
        return None
    return ctx.subject_travel_miles / 1000.0


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    rationale=(
        "Crossing time zones desynchronises the body clock independently of "
        "distance, and a west-coast club playing a 1pm Eastern kickoff is "
        "playing at what its body calls breakfast. Signed, west-to-east positive."
    ),
)
def timezone_shift(ctx) -> float | None:
    if ctx.subject_tz_delta is None:
        return None
    return float(ctx.subject_tz_delta)


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    default=0.0,
    rationale=(
        "Points scored minus points allowed, adjusted for the quality of the "
        "opponents faced, is the plainest available statement of how good a "
        "team has been. Adjusting matters because an easy schedule inflates a "
        "raw differential."
    ),
)
def srs_diff(ctx) -> float | None:
    if ctx.home_srs is None or ctx.away_srs is None:
        return None
    return (ctx.home_srs - ctx.away_srs) / 10.0


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    default=0.0,
    rationale=(
        "Rosters and schemes change during a season through injury and "
        "adjustment, so the last four games carry information the full-season "
        "average has already diluted. Deliberately a short window, and it is "
        "scored separately so we find out whether it adds anything over srs_diff."
    ),
)
def recent_form_diff(ctx) -> float | None:
    if ctx.home_recent_margin is None or ctx.away_recent_margin is None:
        return None
    return (ctx.home_recent_margin - ctx.away_recent_margin) / 10.0


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread", "prop"),
    default=0.0,
    rationale=(
        "Plays from scrimmage per game sets how many chances exist for the "
        "better team to express itself. A fast pairing produces a wider "
        "distribution of margins than a slow one, which changes how often a "
        "given spread is covered."
    ),
)
def pace_sum(ctx) -> float | None:
    if ctx.home_pace is None or ctx.away_pace is None:
        return None
    return (ctx.home_pace + ctx.away_pace - 128.0) / 10.0


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    default=0.0,
    rationale=(
        "Players listed Out on the final injury report do not play. This counts "
        "declared non-availability only; it makes no attempt to judge how badly "
        "hurt anyone is, because a one-word status cannot support that and "
        "guessing at severity is how a model starts inventing information."
    ),
)
def injury_out_diff(ctx) -> float | None:
    if ctx.home_out is None or ctx.away_out is None:
        return None
    return float(ctx.away_out - ctx.home_out)


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    default=0.0,
    rationale=(
        "Quarterback is the one position where the backup is usually a large "
        "step down and the whole offence is built around the starter. This is a "
        "positional fact, not a severity judgement: it reads the same "
        "participation status as injury_out_diff."
    ),
)
def qb_out_diff(ctx) -> float | None:
    if ctx.home_qb_out is None or ctx.away_qb_out is None:
        return None
    return float(ctx.away_qb_out - ctx.home_qb_out)


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    default=0.0,
    rationale=(
        "Division opponents play twice a year with continuous film and shared "
        "personnel knowledge, which historically compresses margins relative to "
        "what the ratings alone would suggest."
    ),
)
def divisional(ctx) -> float | None:
    return None if ctx.div_game is None else float(ctx.div_game)


# --- weather ---------------------------------------------------------------
# Indoors, weather is a constant, so these read 0 under a roof rather than
# NULL: a dome is not missing data, it is a known absence of wind.

@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread", "prop"),
    default=0.0,
    rationale=(
        "Wind is the weather variable that actually changes football: it moves "
        "the deep ball and the field goal, pushes teams towards the run, and "
        "lowers scoring. Above roughly 15mph the passing game measurably "
        "degrades. Expressed in units of 10mph over a 10mph baseline."
    ),
)
def wind(ctx) -> float | None:
    if ctx.indoors:
        return 0.0
    if ctx.wind_mph is None:
        return None
    return (ctx.wind_mph - 10.0) / 10.0


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread", "prop"),
    default=0.0,
    rationale=(
        "Cold stiffens the ball and the hands and favours the running game. "
        "Centred on 55F and scaled per 20F, so a 15F night in Buffalo reads -2."
    ),
)
def cold(ctx) -> float | None:
    if ctx.indoors:
        return 0.0
    if ctx.temp_f is None:
        return None
    return (ctx.temp_f - 55.0) / 20.0


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread", "prop"),
    default=0.0,
    rationale=(
        "Rain and snow reduce grip for the passing game and increase fumbles, "
        "compressing scoring. Probability of precipitation at kickoff, 0-1."
    ),
)
def precipitation(ctx) -> float | None:
    if ctx.indoors:
        return 0.0
    if ctx.precip_pct is None:
        return None
    return ctx.precip_pct / 100.0


# --- the hypothesis we cannot currently test -------------------------------

@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("spread",),
    active=False,
    deactivated="2026-08-28T00:00:00Z",
    note=(
        "INACTIVE ON ARRIVAL. Verified 2026-08-28: no free source publishes "
        "ticket-count betting percentages with an API and a licence we can "
        "rely on. The honest options were to leave it off or to invent a proxy "
        "from something correlated, and a proxy would make this a factor about "
        "the proxy while still being labelled 'public'. Left declared and "
        "inactive so the hypothesis stays visible and can be switched on the "
        "day a real source exists."
    ),
    rationale=(
        "A hypothesis, not an assumption: that heavy public agreement marks "
        "spots where the line has moved on sentiment rather than information, "
        "and that such spots resolve against the crowd more often than chance. "
        "It is declared like any other factor and would be scored like any "
        "other factor, which is the only way to find out whether it is true."
    ),
)
def public_bet_pct(ctx) -> float | None:
    return None  # no source; never a proxy


# ===========================================================================
# PROP FACTORS
# ===========================================================================

@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("prop",),
    rationale=(
        "A player's recent per-game volume — attempts, carries, targets — is "
        "the strongest single determinant of a counting-stat prop, because "
        "opportunity precedes production and usage is stickier than efficiency."
    ),
)
def prop_volume(ctx) -> float | None:
    return ctx.volume_recent


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("prop",),
    rationale=(
        "Yards per opportunity separates a player who gets 12 targets for 60 "
        "yards from one who gets 6 for the same, and the two have different "
        "distributions around the same mean."
    ),
)
def prop_efficiency(ctx) -> float | None:
    return ctx.efficiency_recent


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("prop",),
    rationale=(
        "The rolling mean of the stat itself, in the stat's own units, is the "
        "centre of the distribution the prop question is asked about. Scaled by "
        "the line so the coefficient is unit-free across passing and rushing."
    ),
)
def prop_mean_vs_line(ctx) -> float | None:
    if ctx.rolling_mean is None or not ctx.line_asked:
        return None
    return (ctx.rolling_mean - ctx.line_asked) / max(ctx.line_asked, 1.0)


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("prop",),
    rationale=(
        "Two players with the same average are not the same bet: a high-variance "
        "player clears a high line more often and a low line less often than a "
        "steady one. Without a spread estimate a mean cannot become a probability."
    ),
)
def prop_volatility(ctx) -> float | None:
    if ctx.rolling_sd is None or ctx.rolling_mean is None or ctx.rolling_mean <= 0:
        return None
    return ctx.rolling_sd / ctx.rolling_mean


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("prop",),
    default=0.0,
    rationale=(
        "Defences differ in what they surrender by position, through scheme and "
        "personnel. Yards allowed per game to the position, expressed relative "
        "to the league average, is the cheap version of that and is carried with "
        "its own sample size so a three-game read is not mistaken for a season."
    ),
)
def opponent_allowance(ctx) -> float | None:
    if ctx.allowance is None or ctx.allowance_league_avg is None:
        return None
    if ctx.allowance_league_avg <= 0:
        return None
    return (ctx.allowance - ctx.allowance_league_avg) / ctx.allowance_league_avg


@factor(
    added="2026-08-28T00:00:00Z",
    applies_to=("prop",),
    default=0.0,
    rationale=(
        "A player carrying a Questionable tag into the weekend plays fewer snaps "
        "on average even when active. Participation status only, read straight "
        "off the report: 1 Out, 0.5 Doubtful, 0.25 Questionable, 0 otherwise."
    ),
)
def prop_player_status(ctx) -> float | None:
    return ctx.player_status_penalty
