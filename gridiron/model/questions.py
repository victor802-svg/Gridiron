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
SPREAD_LADDER: tuple[float, ...] = (-7.5, -3.5, 0.5, 3.5)

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
CFB_SPREAD_LADDER: tuple[float, ...] = (-24.5, -14.5, -7.5, -0.5, 6.5)
CFB_SPREAD_LADDER_DECLARED = "2026-08-31T00:00:00Z"

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

#: Mean home margin in college football, measured 2026-08-31 over the same
#: 260-game sample that produced the margin SD. Used to turn a rating
#: difference into an expected margin, which is what the rung is chosen
#: against.
CFB_HOME_MARGIN = 9.79


def cfb_expected_margin(home_rating: float | None,
                        away_rating: float | None) -> float | None:
    """The home side's expected winning margin, from stored ratings only.

    BLIND BY CONSTRUCTION and that is the whole reason it is built from
    ratings rather than from anything better: the rung has to be chosen BEFORE
    the model runs, because the rung is one of the model's inputs. Anything
    that could see a published line here would make the market an input to the
    question, which LAW 1 forbids and the closure scan would catch.
    """
    if home_rating is None or away_rating is None:
        return None
    return (home_rating - away_rating) + CFB_HOME_MARGIN


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
    return min(CFB_SPREAD_LADDER, key=lambda rung: (abs(rung - target), rung))


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


def spread_rung(game_id: str) -> float:
    return SPREAD_LADDER[stable_index(game_id, len(SPREAD_LADDER))]


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
