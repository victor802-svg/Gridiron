"""The MLB adapter: moneyline only, and pitcher-centric.

One question per game: **does the home team win?** There is no line to choose,
so `line_asked` is NULL — see the note at the foot of `factors/mlb.py` for why
no `mlb_asked_line` factor is declared.

Nothing here imports `gridiron.market`, and nothing it imports does either. The
LAW 1 scan walks this module as MLB's own closure.

**The unannounced starter is the big absence.** Probable pitchers are posted a
day or two ahead, and a slate forecast before they are posted genuinely does not
know who is pitching. That is recorded as an absent factor rather than guessed
at, and it is surfaced on the card, because it will happen often and a reader
should see when the model was working blind about the most important input in
the sport.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from .. import config
from ..data import mlb_repo as repo
from ..factors import compute
from ..model.question import Question

SPORT = "mlb"
SLATE_WORD = "day"

#: A starter needs this many prior starts before his rolling form is a number
#: rather than an anecdote.
MIN_STARTER_HISTORY = 3
#: ...and a club this many prior games before its offence is one.
MIN_TEAM_HISTORY = 5


@dataclass
class MlbContext:
    """Everything an MLB factor may see. No market field exists on it."""

    game_id: str
    season: int
    day: int
    home: str
    away: str
    kickoff_utc: str | None
    game_date: str

    sport: str = SPORT
    line_asked: float | None = None

    home_starter_id: int | None = None
    away_starter_id: int | None = None
    home_starter_name: str | None = None
    away_starter_name: str | None = None
    home_starter_ra9: float | None = None
    away_starter_ra9: float | None = None
    home_starter_n: int = 0
    away_starter_n: int = 0
    home_starter_rest: int | None = None
    away_starter_rest: int | None = None

    home_bullpen_innings: float | None = None
    away_bullpen_innings: float | None = None

    home_runs_pg: float | None = None
    away_runs_pg: float | None = None
    home_team_rest: int | None = None
    away_team_rest: int | None = None

    park_runs_pg: float | None = None
    park_n: int = 0
    league_runs_pg: float | None = None

    starters_announced: bool = False
    notes: list[str] = field(default_factory=list)


def _runs_allowed_per_nine(starts) -> tuple[float | None, int]:
    innings = sum((s["innings"] or 0.0) for s in starts)
    runs = sum((s["runs"] or 0) for s in starts)
    if len(starts) < MIN_STARTER_HISTORY or innings <= 0:
        return None, len(starts)
    return runs * 9.0 / innings, len(starts)


def _days_between(later: str, earlier: str | None) -> int | None:
    if not earlier:
        return None
    try:
        a = date.fromisoformat(later[:10])
        b = date.fromisoformat(earlier[:10])
    except ValueError:
        return None
    return (a - b).days


def _bullpen_innings(conn, team: str, on_date: str) -> float | None:
    """Relief innings over the recent window, or None if it cannot be measured.

    Derived as (innings played - announced starter's innings) per game. Where a
    starter's own log is missing for one of those games the whole figure is
    ABSENT rather than part-counted, because a partial sum would understate the
    load and read as a fresher bullpen than the club has.
    """
    window_start = (date.fromisoformat(on_date) - timedelta(days=repo.BULLPEN_WINDOW_DAYS)).isoformat()
    games = repo.team_games_between(conn, team, window_start, on_date)
    if not games:
        return 0.0            # a club with no games in the window is fully rested
    total = 0.0
    for g in games:
        starter_ip = repo.starter_innings_in_game(conn, g["game_id"], team)
        if starter_ip is None:
            return None
        played = g["innings_played"] or 9.0
        total += max(played - starter_ip, 0.0)
    return total


def build_context(conn: sqlite3.Connection, game_id: str) -> MlbContext:
    game = repo.game(conn, game_id)
    if game is None:
        raise KeyError(f"unknown MLB game {game_id!r}")
    on_date = repo.game_date(conn, game_id)
    if on_date is None:
        raise KeyError(f"MLB game {game_id!r} has no date")

    ctx = MlbContext(
        game_id=game_id,
        season=game["season"],
        day=game["week"],
        home=game["home"],
        away=game["away"],
        kickoff_utc=game["kickoff_utc"],
        game_date=on_date,
    )

    announced = repo.probables(conn, game_id)
    ctx.starters_announced = {"home", "away"} <= set(announced)
    if not ctx.starters_announced:
        ctx.notes.append(
            "probable starters were not posted when this forecast was made; every "
            "starter factor is absent, not assumed"
        )

    for side, team in (("home", game["home"]), ("away", game["away"])):
        row = announced.get(side)
        if row is not None and row["pitcher_id"]:
            setattr(ctx, f"{side}_starter_id", row["pitcher_id"])
            setattr(ctx, f"{side}_starter_name", row["pitcher_name"])
            starts = repo.starter_recent(conn, row["pitcher_id"], on_date)
            ra9, n = _runs_allowed_per_nine(starts)
            setattr(ctx, f"{side}_starter_ra9", ra9)
            setattr(ctx, f"{side}_starter_n", n)
            last = repo.starter_last_appearance(conn, row["pitcher_id"], on_date)
            setattr(ctx, f"{side}_starter_rest", _days_between(on_date, last))

        recent = repo.team_recent(conn, team, on_date)
        if len(recent) >= MIN_TEAM_HISTORY:
            setattr(
                ctx, f"{side}_runs_pg",
                sum((r["runs_for"] or 0) for r in recent) / len(recent),
            )
        if recent:
            setattr(ctx, f"{side}_team_rest", _days_between(on_date, recent[0]["game_date"]))
        setattr(ctx, f"{side}_bullpen_innings", _bullpen_innings(conn, team, on_date))

    ctx.park_runs_pg, ctx.park_n = repo.park_run_environment(
        conn, game["stadium"], game["season"]
    )
    ctx.league_runs_pg = repo.league_run_environment(conn, game["season"])
    if ctx.park_n and ctx.park_n < 60:
        ctx.notes.append(f"park run environment is a {ctx.park_n}-game sample")
    return ctx


# ---------------------------------------------------------------------------
# the adapter surface
# ---------------------------------------------------------------------------

def next_slate(conn: sqlite3.Connection, season: int) -> int | None:
    row = conn.execute(
        "SELECT MIN(week) AS w FROM games"
        " WHERE sport = 'mlb' AND season = ? AND status = 'scheduled'",
        (season,),
    ).fetchone()
    return None if row is None or row["w"] is None else int(row["w"])


def slate_questions(
    conn: sqlite3.Connection, season: int, week: int, *, include_props: bool = True
) -> list[Question]:
    """One moneyline question per game. MLB has no prop markets declared."""
    out: list[Question] = []
    for game in repo.games_on_day(conn, season, week):
        out.append(
            Question(
                sport=SPORT,
                game_id=game["id"],
                market_type="moneyline",
                market="moneyline",
                subject=game["home"],
                line_asked=None,
                claim=f"{game['home']} (home) beat {game['away']}",
                yes_label="win",
                no_label="lose",
            )
        )
    return out


def build_features(conn: sqlite3.Connection, q: Question, cache=None):
    ctx = build_context(conn, q.game_id)
    return compute.feature_vector(ctx, q.market_type), ctx


def training_set(
    conn: sqlite3.Connection,
    seasons,
    market: str,
    *,
    through_season: int | None = None,
    through_week: int | None = None,
    progress=None,
):
    """One row per completed game: the factor vector, and whether home won."""
    from ..factors import registry

    if market != "moneyline":
        raise ValueError(f"MLB has no {market!r} market")

    placeholders = ",".join("?" for _ in seasons)
    sql = (
        f"SELECT id, season, week FROM games WHERE sport = 'mlb' AND status = 'final'"
        f" AND season IN ({placeholders})"
    )
    params: list = list(seasons)
    if through_season is not None:
        sql += " AND (season < ? OR (season = ? AND week <= ?))"
        params += [through_season, through_season, through_week or 999]
    sql += " ORDER BY season, week, id"

    games = conn.execute(sql, params).fetchall()
    rows: list[dict] = []
    labels: list[int] = []
    for i, g in enumerate(games):
        if progress and i % 500 == 0:
            progress(f"mlb features {i}/{len(games)}")
        try:
            ctx = build_context(conn, g["id"])
        except KeyError:
            continue
        fv = compute.feature_vector(ctx, "moneyline")
        scores = conn.execute(
            "SELECT home_score, away_score FROM games WHERE id = ?", (g["id"],)
        ).fetchone()
        if scores["home_score"] is None or scores["away_score"] == scores["home_score"]:
            continue          # no ties in baseball; a NULL is a data gap
        rows.append(fv.values)
        labels.append(1 if scores["home_score"] > scores["away_score"] else 0)

    names = [f.name for f in registry.active_factors(SPORT, "moneyline")]
    return rows, labels, names


def resolve_outcome(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    """Did the stated side win? Baseball has no ties, so every played game
    settles 0 or 1."""
    from ..resolve import Unresolvable, Void

    game = conn.execute(
        "SELECT home, away, home_score, away_score, status FROM games WHERE id = ?",
        (pred["game_id"],),
    ).fetchone()
    if game is None or game["status"] != "final":
        raise Unresolvable(f"game {pred['game_id']} is not final")
    if game["home_score"] is None or game["away_score"] is None:
        raise Void(
            f"{pred['game_id']} is marked final but carries no score; the "
            "question has no answer and is not being given one"
        )
    if game["home_score"] == game["away_score"]:
        raise Void(
            f"{pred['game_id']} finished level, which a completed baseball game "
            "cannot do; the row is not trustworthy enough to settle"
        )

    home_won = 1 if game["home_score"] > game["away_score"] else 0
    subject_is_home = pred["subject"] == game["home"]
    subject_won = home_won if subject_is_home else 1 - home_won
    return subject_won if pred["model_side"] == "win" else 1 - subject_won


def markets() -> tuple[str, ...]:
    return config.SPORT_MARKETS[SPORT]
