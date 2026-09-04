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
from ..model import questions
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


# ===========================================================================
# PLAYER PROPS
# ===========================================================================
#
# Four markets, three about a batter and one about the pitcher facing him.
#
# THE VOID RULES ARE WRITTEN HERE, BEFORE THE FIRST PREDICTION (new-market
# checklist, item 7). Deciding after seeing results which non-answers count is
# choosing which losses to keep. In full:
#
#   * A BATTER WITH NO LINE IN THE GAME -> VOID. Scratched, rested, benched, a
#     late lineup change. He did not answer the question either way, and scoring
#     it as an under would credit the model for a manager's decision it never
#     forecast. Note the asymmetry that makes this necessary: a batter who
#     played and went 0-for-4 has a row full of zeros and settles normally. The
#     absence of a row and a row of zeros mean opposite things.
#   * AN ANNOUNCED STARTER WHO DID NOT START -> VOID. Scratched, pushed back, a
#     bullpen game. A strikeout question about a man who never took the mound
#     has no answer.
#   * A GAME THAT NEVER FINISHED -> VOID once it is clearly not going to.
#     Baseball postpones for weather and replays on another date under a new
#     game id, so the original fixture simply stops existing. Held open for
#     STALE_GAME_DAYS first, because a suspended game resumed two days later is
#     a game that did finish.
#   * A STAT LINE THAT CANNOT BE READ -> VOID with the reason recorded.
#
# A void is terminal and removes the prediction from every curve, and the void
# COUNT is reported beside each prop curve rather than buried: a model that
# keeps choosing players who do not play is telling you something.

#: A batter needs this many prior games before his rolling average is a number
#: rather than an anecdote. Higher than NBA's five because a baseball game is
#: three or four plate appearances, so ten games is a smaller sample of
#: opportunities than five basketball games is.
MIN_BATTER_HISTORY = 10
#: ...and must have played within this many days. A batter who has quietly
#: stopped appearing resolves VOID and teaches the scorecard nothing while
#: occupying a slot on a capped slate.
MAX_DAYS_SINCE_PLAYED = 5
#: A starter needs this many prior starts before his strikeout form is one.
MIN_STARTER_PROP_HISTORY = 4
#: How long a scheduled game is held open before it is voided as never played.
#: Long enough for a suspended game to resume, short enough that a postponement
#: does not sit unresolved for a month.
STALE_GAME_DAYS = 4


@dataclass
class MlbPropContext:
    """Everything an MLB prop factor may see. No market field exists on it."""

    game_id: str
    season: int
    day: int
    game_date: str
    kickoff_utc: str | None
    market: str
    subject_id: int
    subject_name: str
    team: str
    opponent: str
    is_home: bool
    line_asked: float

    sport: str = SPORT

    # the subject's own form
    rolling_mean: float | None = None
    rolling_sd: float | None = None
    rolling_n: int = 0
    stat_per_pa: float | None = None
    baseline_n: int = 0
    pa_per_game: float | None = None
    recent_slot: float | None = None

    # the matchup
    bat_side: str | None = None
    opposing_hand: str | None = None
    opposing_k_rate: float | None = None
    opposing_hr_rate: float | None = None
    opposing_starter_id: int | None = None

    # the pitcher's own form (strikeout market)
    pitcher_k_rate: float | None = None
    pitcher_innings: float | None = None
    pitcher_rest: int | None = None
    opponent_team_k_rate: float | None = None

    park_runs_pg: float | None = None
    park_n: int = 0
    league_runs_pg: float | None = None

    notes: list = field(default_factory=list)


def _opposing_starter(conn, game_id: str, subject_team: str):
    """The announced starter the BATTER will face, or None if not posted."""
    game = repo.game(conn, game_id)
    if game is None:
        return None
    side = "away" if game["home"] == subject_team else "home"
    row = repo.probables(conn, game_id).get(side)
    return row if row is not None and row["pitcher_id"] else None


def build_prop_context(
    conn: sqlite3.Connection,
    game_id: str,
    market: str,
    subject_id: int,
    line_asked: float,
) -> MlbPropContext:
    """One prop question's context, from stored data strictly before the game."""
    from ..model.questions import assert_on_ladder

    # A rung off the declared ladder is refused here rather than fitted: it
    # would be incomparable with the market AND with the rest of its category.
    assert_on_ladder(line_asked, market)

    game = repo.game(conn, game_id)
    if game is None:
        raise KeyError(f"unknown MLB game {game_id!r}")
    on_date = repo.game_date(conn, game_id)
    if on_date is None:
        raise KeyError(f"MLB game {game_id!r} has no date")

    is_pitcher = market == "pitcher_strikeouts"
    team, opponent, is_home = _subject_team(conn, game, market, subject_id, on_date)

    ctx = MlbPropContext(
        game_id=game_id,
        season=game["season"],
        day=game["week"],
        game_date=on_date,
        kickoff_utc=game["kickoff_utc"],
        market=market,
        subject_id=subject_id,
        subject_name=_subject_name(conn, subject_id),
        team=team,
        opponent=opponent,
        is_home=is_home,
        line_asked=line_asked,
    )

    if is_pitcher:
        mean, sd, n = repo.starter_workload(conn, subject_id, on_date)
        ctx.rolling_mean, ctx.rolling_sd, ctx.rolling_n = mean, sd, n
        suppression = repo.starter_suppression(conn, subject_id, on_date)
        ctx.pitcher_k_rate = suppression["k_rate"]
        ctx.pitcher_innings, _ = repo.starter_innings_form(conn, subject_id, on_date)
        last = repo.starter_last_appearance(conn, subject_id, on_date)
        ctx.pitcher_rest = _days_between(on_date, last)
        ctx.opponent_team_k_rate, _ = repo.team_strikeout_rate(
            conn, opponent, on_date
        )
    else:
        mean, sd, n = repo.batter_rolling(conn, subject_id, market, on_date)
        ctx.rolling_mean, ctx.rolling_sd, ctx.rolling_n = mean, sd, n

        # The ESTABLISHED rate, over sixty games rather than the mean's
        # fifteen. Measured over the same window it was not an instrument at
        # all -- rate x plate appearances reconstructed the mean exactly.
        ctx.stat_per_pa, ctx.baseline_n = repo.batter_baseline_rate(
            conn, subject_id, market, on_date
        )
        ctx.pa_per_game, _ = repo.batter_pa_per_game(conn, subject_id, on_date)
        ctx.recent_slot, _ = repo.batter_recent_slot(conn, subject_id, on_date)
        ctx.bat_side = repo.batter_handedness(conn, subject_id)

        starter = _opposing_starter(conn, game_id, team)
        if starter is None:
            ctx.notes.append(
                "the opposing starter was not posted when this forecast was "
                "made; his handedness and his rates are absent, not assumed"
            )
        else:
            ctx.opposing_starter_id = starter["pitcher_id"]
            ctx.opposing_hand = repo.pitcher_handedness(conn, starter["pitcher_id"])
            suppression = repo.starter_suppression(
                conn, starter["pitcher_id"], on_date
            )
            ctx.opposing_k_rate = suppression["k_rate"]
            ctx.opposing_hr_rate = suppression["hr_rate"]

    ctx.park_runs_pg, ctx.park_n = repo.park_run_environment(
        conn, game["stadium"], game["season"]
    )
    ctx.league_runs_pg = repo.league_run_environment(conn, game["season"])
    if ctx.rolling_n and ctx.rolling_n < 10:
        ctx.notes.append(
            f"the rolling average behind this question is {ctx.rolling_n} games"
        )
    return ctx


def _subject_name(conn: sqlite3.Connection, subject_id: int) -> str:
    row = conn.execute(
        "SELECT full_name FROM mlb_people WHERE player_id = ?", (subject_id,)
    ).fetchone()
    if row and row["full_name"]:
        return row["full_name"]
    row = conn.execute(
        "SELECT player_name FROM mlb_batter_games WHERE player_id = ?"
        " ORDER BY game_date DESC LIMIT 1",
        (subject_id,),
    ).fetchone()
    if row and row["player_name"]:
        return row["player_name"]
    row = conn.execute(
        "SELECT pitcher_name FROM mlb_probables WHERE pitcher_id = ? LIMIT 1",
        (subject_id,),
    ).fetchone()
    return (row["pitcher_name"] if row and row["pitcher_name"] else str(subject_id))


def _subject_team(conn, game, market: str, subject_id: int, on_date: str):
    """(team, opponent, is_home) for the subject of a prop question."""
    if market == "pitcher_strikeouts":
        for side in ("home", "away"):
            row = repo.probables(conn, game["id"]).get(side)
            if row is not None and row["pitcher_id"] == subject_id:
                is_home = side == "home"
                return (
                    game["home"] if is_home else game["away"],
                    game["away"] if is_home else game["home"],
                    is_home,
                )
        raise KeyError(
            f"pitcher {subject_id} is not an announced starter for {game['id']}"
        )

    recent = repo.batter_recent(conn, subject_id, on_date, limit=1)
    team = recent[0]["team"] if recent else None
    if team == game["home"]:
        return game["home"], game["away"], True
    if team == game["away"]:
        return game["away"], game["home"], False
    raise KeyError(
        f"batter {subject_id} last played for {team!r}, which is neither club "
        f"in {game['id']}"
    )


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def prop_candidates(conn: sqlite3.Connection, game: sqlite3.Row) -> list[dict]:
    """Every prop question this game could support, deterministically ordered.

    Eligibility is by history and recency only -- never by how interesting the
    answer looks, which would be choosing the questions after seeing the data.
    """
    from ..model.questions import ladder_rung

    on_date = repo.game_date(conn, game["id"])
    if on_date is None:
        return []
    out: list[dict] = []

    for team in (game["home"], game["away"]):
        # Batters who have started recently for this club. Read from the game
        # logs rather than a roster, so a player we hold no history for cannot
        # be asked about.
        rows = conn.execute(
            "SELECT player_id, MAX(game_date) AS last, COUNT(*) AS games,"
            " SUM(plate_appearances) AS pa FROM mlb_batter_games"
            " WHERE team = ? AND game_date < ? AND season = ?"
            " GROUP BY player_id HAVING games >= ? ORDER BY pa DESC, player_id",
            (team, on_date, game["season"], MIN_BATTER_HISTORY),
        ).fetchall()
        for row in rows:
            gap = _days_between(on_date, row["last"])
            if gap is None or gap > MAX_DAYS_SINCE_PLAYED:
                continue
            # He must have STARTED recently, not merely appeared. The training
            # set is built from batters who were in a posted lineup, so asking
            # about a pinch-hitter would put a question to the model that
            # nothing in its fit resembles -- and it would arrive with the
            # lineup-slot factor absent, which is how a live slate quietly
            # becomes a different population from the one that was fitted.
            slot, _n = repo.batter_recent_slot(conn, row["player_id"], on_date)
            if slot is None:
                continue
            for market in ("batter_hits", "batter_total_bases",
                           "batter_home_runs"):
                mean, _sd, n = repo.batter_rolling(
                    conn, row["player_id"], market, on_date
                )
                if mean is None or n < MIN_BATTER_HISTORY:
                    continue
                out.append({
                    "game_id": game["id"],
                    "market": market,
                    "subject_id": int(row["player_id"]),
                    "team": team,
                    "volume": float(row["pa"] or 0),
                    "line_asked": ladder_rung(mean, market),
                })

    for side in ("home", "away"):
        row = repo.probables(conn, game["id"]).get(side)
        if row is None or not row["pitcher_id"]:
            continue
        mean, _sd, n = repo.starter_workload(conn, row["pitcher_id"], on_date)
        if mean is None or n < MIN_STARTER_PROP_HISTORY:
            continue
        out.append({
            "game_id": game["id"],
            "market": "pitcher_strikeouts",
            "subject_id": int(row["pitcher_id"]),
            "team": game["home"] if side == "home" else game["away"],
            # Starters are ranked among themselves by recent strikeouts, which
            # is the closest thing this market has to a volume measure.
            "volume": float(mean),
            "line_asked": ladder_rung(mean, "pitcher_strikeouts"),
        })

    out.sort(key=lambda c: (c["market"], c["team"], c["subject_id"]))
    return out


def select_day_props(
    conn: sqlite3.Connection, games: list, cap: int | None = None
) -> list[dict]:
    """The day's prop slate: capped, market-balanced, deterministic.

    Filled by round-robin across `config.MLB_PROP_MARKETS`, which is ordered by
    the liquidity measured on a real slate. When the cap bites it bites on the
    thinnest market first, which is strikeouts -- roughly one qualifying subject
    per game against two hundred-odd batting candidates.

    One question per subject per day. Asking the same batter about hits AND
    total bases is two correlated looks at one afternoon, and counting them as
    two would inflate every N on the scorecard.
    """
    cap = config.MLB_PROPS_PER_DAY if cap is None else cap
    if cap <= 0:
        return []

    by_market: dict[str, list[dict]] = {m: [] for m in config.MLB_PROP_MARKETS}
    for game in games:
        for candidate in prop_candidates(conn, game):
            by_market[candidate["market"]].append(candidate)
    for market in by_market:
        by_market[market].sort(
            key=lambda c: (-c["volume"], c["game_id"], c["subject_id"])
        )

    chosen: list[dict] = []
    cursors = {m: 0 for m in config.MLB_PROP_MARKETS}
    seen_subjects: set[int] = set()
    progressed = True

    while len(chosen) < cap and progressed:
        progressed = False
        for market in config.MLB_PROP_MARKETS:
            if len(chosen) >= cap:
                break
            pool = by_market[market]
            while cursors[market] < len(pool):
                candidate = pool[cursors[market]]
                cursors[market] += 1
                progressed = True
                if candidate["subject_id"] in seen_subjects:
                    continue
                seen_subjects.add(candidate["subject_id"])
                chosen.append(dict(candidate))
                break

    chosen.sort(key=lambda c: (c["game_id"], c["market"], c["subject_id"]))
    return chosen


# ---------------------------------------------------------------------------
# the adapter surface
# ---------------------------------------------------------------------------

def next_slate(conn: sqlite3.Connection, season: int) -> int | None:
    """The earliest slate that still has a game nobody has played yet.

    THE `kickoff_utc > now` CLAUSE IS LOAD-BEARING and MLB was missing it while
    NBA had it. Without it, a day whose games have all started but whose rows
    have not yet been refreshed to `final` stays the "next" slate forever: on
    2026-08-30, five games from the previous evening were still marked scheduled
    twelve hours after first pitch, so the daily task kept selecting that day,
    skipped all five as already under way, and wrote nothing. Two consecutive
    `predict:mlb` runs recorded `noop` for exactly this reason, and the next
    day's card was never reached.

    A slate that is only PARTLY under way is still returned, because
    `predict_slate` skips started games one at a time and the rest are
    legitimately forecastable.
    """
    from ..db import utcnow

    row = conn.execute(
        "SELECT MIN(week) AS w FROM games"
        " WHERE sport = 'mlb' AND season = ? AND status = 'scheduled'"
        " AND kickoff_utc > ?",
        (season, utcnow()),
    ).fetchone()
    return None if row is None or row["w"] is None else int(row["w"])


def slate_questions(
    conn: sqlite3.Connection, season: int, week: int, *, include_props: bool = True
) -> list[Question]:
    """One moneyline question per game, plus the day's capped prop slate."""
    games = repo.games_on_day(conn, season, week)
    out: list[Question] = []
    for game in games:
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

        # THE RUN LINE, at the market's own rung and asked blind (STEP 3).
        #
        # -1.5 FROM THE HOME SIDE, EVERY GAME. Which club the market makes the
        # favourite is not consulted: that would be the market choosing our
        # question, which LAW 1 forbids. The rung itself is a declared
        # constant measured from history -- every MLB run line ESPN carries is
        # +/-1.5, 71 of 71 in the probe -- so asking at it is asking the
        # market's question without reading the market.
        out.append(
            Question(
                sport=SPORT,
                game_id=game["id"],
                market_type="spread",
                market="run_line",
                subject=game["home"],
                line_asked=-questions.MLB_RUN_LINE,
                claim=(f"{game['home']} (home) beat {game['away']} by two runs "
                       f"or more"),
                yes_label="cover",
                no_label="not_cover",
            )
        )

        # THE TOTAL, at a number we generate ourselves.
        #
        # Absent when either side has no scoring history: an absent question is
        # recorded absent and never asked at a guessed number (item 5).
        asked = questions.mlb_total_asked(
            *_combined_form(conn, game))
        if asked is not None:
            out.append(
                Question(
                    sport=SPORT,
                    game_id=game["id"],
                    market_type="total",
                    market="total",
                    subject=f"{game['away']} at {game['home']}",
                    line_asked=asked,
                    claim=(f"{game['away']} at {game['home']} produces more "
                           f"than {asked} runs between them"),
                    yes_label="over",
                    no_label="under",
                )
            )

    if not include_props:
        return out

    for pick in select_day_props(conn, games):
        name = _subject_name(conn, pick["subject_id"])
        stat_words = PROP_WORDS[pick["market"]]
        out.append(
            Question(
                sport=SPORT,
                game_id=pick["game_id"],
                # `prop` is the CLASS of question; the market says WHICH prop.
                # The schema's CHECK enforces the class, and
                # (market_type, prop_type) is the scoring category.
                market_type="prop",
                market=pick["market"],
                subject=f"{name} {pick['market']}",
                line_asked=pick["line_asked"],
                claim=(
                    f"{name} ({pick['team']}) records more than "
                    f"{pick['line_asked']} {stat_words}"
                ),
                yes_label="over",
                no_label="under",
                player_id=str(pick["subject_id"]),
                stat=pick["market"],
            )
        )
    return out


#: What each market is called inside a claim sentence. The interface never
#: reads these -- `gridiron.language` humanises for display -- but a claim is
#: stored permanently on the prediction row and a reader should be able to read
#: it without decoding an identifier.
PROP_WORDS = {
    "batter_hits": "hits",
    "batter_total_bases": "total bases",
    "batter_home_runs": "home runs",
    "pitcher_strikeouts": "strikeouts",
}


def _combined_form(conn: sqlite3.Connection, game) -> tuple:
    """Both sides' runs per game, from stored results strictly before today.

    The same numbers `build_context` puts on the context, read once here so
    the asked total and the factor that measures it against the form cannot
    come from two different windows.
    """
    ctx = build_context(conn, game["id"])
    return ctx.home_runs_pg, ctx.away_runs_pg


def build_features(conn: sqlite3.Connection, q: Question, cache=None):
    if q.market_type == "prop":
        ctx = build_prop_context(
            conn, q.game_id, q.stat, int(q.player_id), q.line_asked
        )
        return compute.feature_vector(ctx, "prop", q.stat), ctx
    ctx = build_context(conn, q.game_id)
    # THE ASKED TOTAL IS PART OF THE QUESTION, so it has to be in the context
    # the factors read: `mlb_total_vs_line` is the rounding residual between
    # the two sides' combined form and the number we asked at.
    if q.line_asked is not None:
        ctx.line_asked = q.line_asked
    return compute.feature_vector(ctx, q.market_type), ctx


def training_set(
    conn: sqlite3.Connection,
    seasons,
    market: str,
    *,
    through_season: int | None = None,
    through_week: int | None = None,
    progress=None,
    with_counts: bool = False,
):
    """One row per completed game: the factor vector, and whether home won.

    `with_counts` adds a fourth return: the ACTUAL COUNT behind each label,
    which a rate model needs and a logistic does not. Only the prop path can
    answer it -- a moneyline has no count -- so asking for it anywhere else is
    refused by name rather than answered with an empty list.
    """
    from ..factors import registry

    if market in config.MLB_PROP_MARKETS:
        return _prop_training_set(
            conn, seasons, market,
            through_season=through_season, through_week=through_week,
            progress=progress, with_counts=with_counts,
        )
    if with_counts:
        raise ValueError(
            f"mlb {market!r} is not a count market; there is no count behind "
            f"its label to return")
    if market not in ("moneyline", "spread", "total"):
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
        scores = conn.execute(
            "SELECT home_score, away_score FROM games WHERE id = ?", (g["id"],)
        ).fetchone()
        if scores["home_score"] is None:
            continue          # a NULL is a data gap, not a result
        home, away = scores["home_score"], scores["away_score"]

        if market == "total":
            # THE TRAINING ROW IS ASKED THE SAME WAY THE LIVE ONE IS. The
            # total is self-generated, so a fit trained against a fixed number
            # would be fitting a different question from the one asked. A game
            # whose sides have no form yet produces no question, live or in
            # training -- the same rule, so the fit sees the same population.
            asked = questions.mlb_total_asked(ctx.home_runs_pg, ctx.away_runs_pg)
            if asked is None:
                continue
            ctx.line_asked = asked
            fv = compute.feature_vector(ctx, "total")
            rows.append(fv.values)
            labels.append(questions.total_outcome(home, away, asked))
            continue

        if market == "spread":
            ctx.line_asked = -questions.MLB_RUN_LINE
            fv = compute.feature_vector(ctx, "spread")
            rows.append(fv.values)
            labels.append(questions.run_line_outcome(
                home, away, -questions.MLB_RUN_LINE))
            continue

        if away == home:
            continue          # no ties in baseball
        fv = compute.feature_vector(ctx, "moneyline")
        rows.append(fv.values)
        labels.append(1 if home > away else 0)

    names = [f.name for f in registry.active_factors(SPORT, market)]
    return rows, labels, names


def resolve_outcome(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    """Did the stated side win? Baseball has no ties, so every played game
    settles 0 or 1."""
    from ..resolve import Unresolvable, Void

    if pred["market_type"] == "prop":
        return _resolve_prop(conn, pred)

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

    if pred["market_type"] == "spread":
        # THE LEAGUE'S RULING IS THE ANSWER, including a game called early.
        # A rain-shortened game that is official has an official score, and
        # inventing a second standard would mean the record disagreed with the
        # sport. Written before the first prediction; see `questions.py`.
        covered = questions.run_line_outcome(
            game["home_score"], game["away_score"], pred["line_asked"])
        return covered if pred["model_side"] == "cover" else 1 - covered

    if pred["market_type"] == "total":
        over = questions.total_outcome(
            game["home_score"], game["away_score"], pred["line_asked"])
        return over if pred["model_side"] == "over" else 1 - over

    home_won = 1 if game["home_score"] > game["away_score"] else 0
    subject_is_home = pred["subject"] == game["home"]
    subject_won = home_won if subject_is_home else 1 - home_won
    return subject_won if pred["model_side"] == "win" else 1 - subject_won


def markets() -> tuple[str, ...]:
    return config.SPORT_MARKETS[SPORT]


def _prop_training_set(
    conn: sqlite3.Connection,
    seasons,
    market: str,
    *,
    through_season: int | None = None,
    through_week: int | None = None,
    progress=None,
    with_counts: bool = False,
):
    """One row per completed prop question, built by exactly the rules a live
    slate uses.

    The line is drawn from the same declared ladder at the same rung the live
    selector would choose, so a fitted coefficient describes the questions the
    model will actually be asked. A training set asked at different rungs from
    the live one is a model fitted to a question nobody puts to it.
    """
    from ..factors import registry
    from ..model.questions import ladder_rung

    placeholders = ",".join("?" for _ in seasons)
    sql = (
        "SELECT id, season, week, home, away FROM games WHERE sport = 'mlb'"
        f" AND status = 'final' AND season IN ({placeholders})"
    )
    params: list = list(seasons)
    if through_season is not None:
        sql += " AND (season < ? OR (season = ? AND week <= ?))"
        params += [through_season, through_season, through_week or 999]
    sql += " ORDER BY season, week, id"
    games = conn.execute(sql, params).fetchall()

    rows: list[dict] = []
    labels: list[int] = []
    extras: list[dict] = []
    is_pitcher = market == "pitcher_strikeouts"
    column = None if is_pitcher else repo.BATTER_STAT_COLUMN[market]

    for i, game in enumerate(games):
        if progress and i % 250 == 0:
            progress(f"mlb {market} features {i}/{len(games)}")
        game_pk = _game_pk(game["id"])
        if game_pk is None:
            continue
        on_date = repo.game_date(conn, game["id"])
        if on_date is None:
            continue

        if is_pitcher:
            subjects = [
                (r["pitcher_id"], r["strike_outs"])
                for r in conn.execute(
                    "SELECT pitcher_id, strike_outs FROM mlb_pitcher_starts"
                    " WHERE game_pk = ? AND is_start = 1"
                    " AND strike_outs IS NOT NULL",
                    (game_pk,),
                )
            ]
        else:
            subjects = [
                (r["player_id"], r[column])
                for r in conn.execute(
                    f"SELECT player_id, {column} FROM mlb_batter_games"
                    " WHERE game_pk = ? AND lineup_slot IS NOT NULL"
                    f" AND {column} IS NOT NULL",
                    (game_pk,),
                )
            ]

        for subject_id, actual in subjects:
            if is_pitcher:
                mean, _sd, n = repo.starter_workload(conn, subject_id, on_date)
                if mean is None or n < MIN_STARTER_PROP_HISTORY:
                    continue
            else:
                mean, _sd, n = repo.batter_rolling(
                    conn, subject_id, market, on_date
                )
                if mean is None or n < MIN_BATTER_HISTORY:
                    continue
            line = ladder_rung(mean, market)
            try:
                ctx = build_prop_context(
                    conn, game["id"], market, int(subject_id), line
                )
            except KeyError:
                continue
            fv = compute.feature_vector(ctx, "prop", market)
            rows.append(fv.values)
            labels.append(1 if float(actual) > line else 0)
            if with_counts:
                extras.append({"count": float(actual), "rung": line,
                               "season": game["season"], "week": game["week"]})

    names = [f.name for f in registry.active_factors(SPORT, "prop", market)]
    if with_counts:
        return rows, labels, names, extras
    return rows, labels, names


class NonMonotoneLadder(AssertionError):
    """A model said a higher rung was easier to clear than a lower one."""


def rung_probabilities(conn: sqlite3.Connection, fit, game_id: str,
                       market: str, subject_id: int) -> list[tuple[float, float]]:
    """P(over) at every rung of the declared ladder, for one subject.

    Everything except the line is held fixed, which is the point: the only
    thing that changes between rungs is the question being asked.
    """
    from ..model import baseline

    out = []
    for rung in config.MLB_PROP_LADDER[market]:
        ctx = build_prop_context(conn, game_id, market, subject_id, rung)
        fv = compute.feature_vector(ctx, "prop", market)
        out.append((rung, baseline.predict(fit, fv, rung=rung)["prob_yes"]))
    return out


def assert_monotone_across_rungs(pairs: list[tuple[float, float]],
                                 label: str = "this subject") -> None:
    """P(over) must FALL as the rung rises. CHECKLIST ITEM 4.

    Clearing 6.5 strikeouts is strictly harder than clearing 5.5 -- every game
    that does the first does the second, so the probabilities are ordered by
    logic, not by estimation. A model that says otherwise is not slightly
    miscalibrated, it is contradicting itself, and the contradiction would be
    invisible on a card showing one rung at a time.

    This is the same shape of check as the spread-versus-moneyline one that
    caught the ESPN sign error: two stored numbers that describe the same world
    must agree about it.
    """
    for (low_line, low_p), (high_line, high_p) in zip(pairs, pairs[1:]):
        if high_p > low_p:
            raise NonMonotoneLadder(
                f"{label}: the model gives {high_p:.4f} of clearing "
                f"{high_line} and only {low_p:.4f} of clearing {low_line}. "
                "Every outcome that clears the higher rung clears the lower "
                "one, so this is a self-contradiction rather than a close call."
            )


def _game_pk(game_id: str) -> int | None:
    """`mlb_776543` -> 776543. The player tables are keyed on MLB's own pk."""
    try:
        return int(game_id.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def _resolve_prop(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    """Settle one prop, or VOID it with a stated reason.

    Every void case here was decided and written down before the first MLB prop
    prediction existed (see the rules at the top of the props section). Nothing
    in this function chooses which non-answers to count after seeing them.
    """
    import json

    from ..resolve import Unresolvable, Void

    payload = json.loads(pred["factors_json"])
    question = payload.get("question") or {}
    subject_id = question.get("player_id")
    market = pred["prop_type"] or question.get("stat")
    if not subject_id or not market:
        raise Void(
            f"prediction {pred['id']} records no subject or market, so there is "
            "nothing to look up; it is voided rather than guessed at"
        )
    subject_id = int(subject_id)

    game = conn.execute(
        "SELECT status, league_date, kickoff_utc FROM games WHERE id = ?",
        (pred["game_id"],),
    ).fetchone()
    if game is None:
        raise Void(f"game {pred['game_id']} is no longer in the record")
    if game["status"] != "final":
        stale = _days_between(
            _today_utc(), game["league_date"] or (game["kickoff_utc"] or "")[:10]
        )
        if stale is not None and stale > STALE_GAME_DAYS:
            raise Void(
                f"{pred['game_id']} was scheduled for "
                f"{game['league_date']} and has not finished {stale} days later. "
                "Baseball replays a postponement under a new game id, so this "
                "fixture is not going to settle and is voided rather than left "
                "open forever."
            )
        raise Unresolvable(f"game {pred['game_id']} is not final")

    game_pk = _game_pk(pred["game_id"])
    if game_pk is None:
        raise Void(f"{pred['game_id']} carries no MLB game pk to look up")

    if market == "pitcher_strikeouts":
        started, actual = repo.pitcher_start_in_game(conn, subject_id, game_pk)
        if not started:
            raise Void(
                f"{question.get('claim') or subject_id}: the announced starter "
                "did not start this game. A strikeout question about a man who "
                "never took the mound has no answer, and scoring it as an under "
                "would credit the model for a scratch it never forecast."
            )
    else:
        column = repo.BATTER_STAT_COLUMN.get(market)
        if column is None:
            raise Void(f"{market!r} has no resolvable column")
        played, actual = repo.batter_stat_in_game(conn, subject_id, game_pk, column)
        if not played:
            raise Void(
                f"{question.get('claim') or subject_id}: no batting line exists "
                "for this player in this game -- scratched, rested or a late "
                "lineup change. He did not answer the question either way. Note "
                "that a batter who played and went hitless DOES have a line, "
                "full of zeros, and settles normally."
            )
    if actual is None:
        raise Void(
            f"{question.get('claim') or subject_id}: the game finished and a "
            "line exists, but the stat itself is missing from it"
        )

    from ..model.questions import prop_outcome

    over = prop_outcome(float(actual), pred["line_asked"])
    return over if pred["model_side"] == "over" else 1 - over


def _today_utc() -> str:
    from ..db import utcnow

    return utcnow()[:10]
