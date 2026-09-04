"""The NFL adapter.

Delegates to the modules the NFL was built with. It exists so the shared blind
loop can treat every sport the same way, and so `gridiron.audit` has an NFL
entrypoint to walk alongside the other two.

Nothing here imports `gridiron.market`, and nothing it imports does either.
"""

from __future__ import annotations

import sqlite3

from .. import config
from ..data import repo
from ..factors import compute, context
from ..model import questions
from ..model.question import Question

SPORT = "nfl"

#: NFL's slate ordinal is the league's own week number.
SLATE_WORD = "week"


def next_slate(conn: sqlite3.Connection, season: int) -> int | None:
    return repo.next_unplayed_week(conn, season, sport=SPORT)


def slate_questions(
    conn: sqlite3.Connection, season: int, week: int, *, include_props: bool = True
) -> list[Question]:
    games = repo.games_for_week(conn, season, week, sport=SPORT)
    out: list[Question] = []
    for game in games:
        # THE RUNG IS CHOSEN AGAINST THE EXPECTED MARGIN (R4, extended to the
        # NFL by operator ruling 2026-09-03), which means the context has to
        # be built before the spread question rather than after it. The
        # ratings it reads are stored and blind.
        ctx = context.build_game_context(conn, game["id"])
        expected = questions.expected_margin(
            SPORT, ctx.home_srs, ctx.away_srs)
        try:
            line = questions.spread_rung(game["id"], expected)
        except questions.RungOffTheLadder:
            # A MISMATCH THE LADDER CANNOT REACH ASKS NOTHING (CFB-1). The
            # absence is recorded as an absence rather than clamped to the end
            # rung. Measured at 0.26% of NFL games on the extended ladder.
            continue
        sign = "+" if line > 0 else ""
        out.append(
            Question(
                sport=SPORT,
                game_id=game["id"],
                market_type="spread",
                market="spread",
                subject=game["home"],
                line_asked=line,
                claim=(
                    f"{game['home']} (home) covers {sign}{line:g} against "
                    f"{game['away']}"
                ),
                yes_label="cover",
                no_label="not_cover",
            )
        )

    if not include_props:
        return out

    # Props are chosen for the WEEK, not per game: the cap and the liquidity
    # ordering are properties of the slate a person has to read.
    for pick in questions.select_week_props(conn, games):
        out.append(
            Question(
                sport=SPORT,
                game_id=pick["game_id"],
                market_type="prop",
                market=pick["stat"],
                subject=f"{pick['player_name']} {pick['stat']}",
                line_asked=pick["line_asked"],
                claim=(
                    f"{pick['player_name']} ({pick['position']}, {pick['team']}) "
                    f"records more than {pick['line_asked']:g} "
                    f"{pick['stat'].replace('_', ' ')}"
                ),
                yes_label="over",
                no_label="under",
                player_id=pick["player_id"],
                stat=pick["stat"],
            )
        )
    return out


def build_features(conn: sqlite3.Connection, q: Question, cache=None):
    if q.market_type == "spread":
        ctx = context.build_game_context(conn, q.game_id, cache, line_asked=q.line_asked)
    else:
        ctx = context.build_prop_context(
            conn, q.game_id, q.player_id, q.stat, q.line_asked, cache
        )
    return compute.feature_vector(ctx, q.market_type), ctx


def training_set(conn: sqlite3.Connection, seasons, market: str, *,
                 with_counts: bool = False, **kwargs):
    """`with_counts` adds the ACTUAL COUNT behind each label, for a rate model.

    Declared in the signature rather than swallowed by `**kwargs` because a
    caller checks for it there. A spread has no count, so asking for one is
    refused by name rather than answered with a silent logistic.
    """
    from ..model import baseline

    if market == "spread":
        if with_counts:
            raise ValueError(
                "nfl 'spread' is not a count market; there is no count behind "
                "its label to return")
        return baseline.spread_training_set(conn, seasons, **kwargs)
    return baseline.prop_training_set(
        conn, seasons, market, with_counts=with_counts, **kwargs)


def resolve_outcome(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    from ..resolve import resolve_nfl_outcome

    return resolve_nfl_outcome(conn, pred)


def markets() -> tuple[str, ...]:
    return config.SPORT_MARKETS[SPORT]
