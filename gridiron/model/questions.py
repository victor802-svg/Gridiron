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

**Props.** The line is the player's own recent average, shifted by one of three
pre-declared offsets, again chosen by a stable hash. Asking exactly at the
average would make every answer 50% and the scorecard would learn nothing.

Every rung ends in .5, so nothing can push and every prediction resolves 0 or 1.

Nothing in this module reads a market table, and nothing in it may.
"""

from __future__ import annotations

import sqlite3
import zlib

from .. import config
from ..data import repo

#: Home-team spread rungs. Negative means the home side gives points.
SPREAD_LADDER: tuple[float, ...] = (-7.5, -3.5, 0.5, 3.5)

#: Prop line offsets, as a fraction of the player's rolling average.
PROP_OFFSETS: tuple[float, ...] = (-0.30, 0.0, 0.30)

#: A player needs this many prior games before we will ask a question about them.
MIN_PROP_HISTORY = 3


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
    offset = PROP_OFFSETS[stable_index(key, len(PROP_OFFSETS))]
    step = 5.0 if stat == "passing_yards" else 5.0
    base = _round_to(max(rolling_mean * (1.0 + offset), step), step)
    return base + 0.5


def prop_outcome(actual: float, line_asked: float) -> int:
    return 1 if actual > line_asked else 0


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

#: Which position supplies which stat. Fixed so the selection cannot drift
#: towards whoever happens to look good.
STAT_POSITIONS = {
    "passing_yards": ("QB",),
    "rushing_yards": ("RB",),
    "receiving_yards": ("WR", "TE"),
}
STAT_VOLUME_COLUMN = {
    "passing_yards": "att",
    "rushing_yards": "car",
    "receiving_yards": "tgt",
}
STAT_MEAN_COLUMN = {
    "passing_yards": "pass_yds",
    "rushing_yards": "rush_yds",
    "receiving_yards": "rec_yds",
}


def prop_candidates(
    conn: sqlite3.Connection, game: sqlite3.Row
) -> list[dict]:
    """Every prop question this game could support, in a deterministic order.

    Eligibility is by usage only: the player with the most attempts, carries or
    targets at their position. No filtering on how interesting the answer might
    be, because that would be choosing the questions after seeing the data.
    """
    out: list[dict] = []
    for team in (game["home"], game["away"]):
        roster = repo.team_players(conn, game["season"], team, game["week"])
        for stat in config.PROP_MARKETS:
            positions = STAT_POSITIONS[stat]
            volume_col = STAT_VOLUME_COLUMN[stat]
            eligible = [
                r
                for r in roster
                if (r["position"] or "") in positions
                and r["games"] >= MIN_PROP_HISTORY
                and (r[volume_col] or 0) > 0
            ]
            if not eligible:
                continue
            best = max(eligible, key=lambda r: (r[volume_col], r["player_id"]))
            mean = best[STAT_MEAN_COLUMN[stat]] or 0.0
            if mean <= 0:
                continue
            out.append(
                {
                    "player_id": best["player_id"],
                    "player_name": best["player_name"],
                    "position": best["position"],
                    "team": team,
                    "stat": stat,
                    "rolling_mean_hint": float(mean),
                }
            )
    out.sort(key=lambda c: (c["stat"], c["team"], c["player_id"]))
    return out


def select_props(
    conn: sqlite3.Connection, game: sqlite3.Row, per_game: int | None = None
) -> list[dict]:
    """Pick `per_game` questions from the candidates, rotating the starting
    point by game id so the slate is not all quarterbacks."""
    per_game = config.PROPS_PER_GAME if per_game is None else per_game
    candidates = prop_candidates(conn, game)
    if not candidates or per_game <= 0:
        return []
    start = stable_index(game["id"], len(candidates))
    picked = [candidates[(start + i) % len(candidates)] for i in range(min(per_game, len(candidates)))]
    for c in picked:
        c["line_asked"] = prop_line_asked(
            c["rolling_mean_hint"], f"{game['id']}:{c['player_id']}:{c['stat']}", c["stat"]
        )
    return picked
