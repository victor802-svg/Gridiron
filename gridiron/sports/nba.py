"""The NBA adapter: spreads on a ladder, and four player prop markets.

Nothing here imports `gridiron.market`, and nothing it imports does either. The
LAW 1 scan walks this module as basketball's own closure.

Two things about basketball shape everything below.

**Availability is the question.** Five men take almost every possession, so one
absence is a fifth of a lineup, and clubs rest healthy stars deliberately. The
availability measurement is therefore defined to use only information that
exists BEFORE tip in both the forward and the backtest regimes — see
`nba_availability_index` for the full argument. Getting that wrong would have
fitted the model on hindsight it can never have on a Tuesday night in November.

**The season has not started.** At the time this was written the 2026-27 season
tips on 2026-10-20. `first_slate_note` exists so the interface can say that
plainly rather than rendering an empty page that looks broken.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from .. import config
from ..data import nba_repo as repo
from ..factors import compute, context
from ..model import baseline
from ..model import questions
from ..model.question import Question
from .. import subjects

SPORT = "nba"
SLATE_WORD = "week"

#: Home-team spread rungs, in points. Wider than football's because basketball
#: margins are wider: a four-point NBA spread is a coin flip, a fourteen-point
#: one is a heavy favourite. Every rung ends in .5 so nothing can push.
#:
#: EXTENDED 2026-09-03, when the operator's ruling brought the NBA under the
#: nearest-expected-margin rule (R4). Four rungs were enough while the rung
#: was chosen by hashing the game id; chosen by nearest margin they have to
#: REACH, and against the fitted expected margins the old four did not:
#:
#:                  refused as beyond the ladder     busiest rung
#:     old (4)                    3.84%                  31.4%
#:     new (12)                   0.12%                  18.8%
#:
#: EIGHT RUNGS ADDED, NONE MOVED -- the rule CFB-1 settled on 2026-09-02.
#: The original four stay on the ladder they were asked against (LAW 3).
SPREAD_LADDER: tuple[float, ...] = (
    -19.5, -14.5, -11.5, -9.5, -7.5, -4.5, -2.5, 0.5, 3.5, 5.5, 8.5, 10.5,
)

#: When the ladder above was extended, and what it was before.
SPREAD_LADDER_DECLARED = "2026-09-03T00:00:00Z"
SPREAD_LADDER_BEFORE: tuple[float, ...] = (-9.5, -4.5, 0.5, 5.5)

#: A club needs this many completed games before its rolling form is a number.
MIN_TEAM_HISTORY = 5

#: HOW MANY LEAGUE GAMES BEFORE AN OPPONENT ADJUSTMENT MEANS ANYTHING.
#:
#: The Simple Rating System solves each club's rating against the ratings of
#: the clubs it played, so on opening night every rating is zero and after one
#: round they are just margins. 150 team-games is roughly the first ten days of
#: a season -- about five games a club -- which is the point at which the
#: schedule has begun to differ between clubs and the adjustment has something
#: to adjust. Below it the factor is ABSENT rather than zero: "we cannot tell
#: yet who has played whom" is not the same claim as "the schedules were equal".
#:
#: DECLARED, NOT FITTED. It is a statement about when the instrument starts
#: working, and it is one number in one place so it can be argued with.
MIN_LEAGUE_GAMES_FOR_SRS = 150
MIN_LEAGUE_GAMES_DECLARED = "2026-09-03T00:00:00Z"


class SeasonRatings:
    """Opponent-adjusted ratings for one season, memoised by date (D1).

    Every game on a given night shares the same history and therefore the same
    ratings. Training over four seasons builds contexts for ~4,900 games across
    ~600 distinct dates; without this the whole league is re-solved once per
    game, which is 4,900 solves for 600 answers.

    THE SAME SHAPE AS THE NFL'S `WeekCache` and deliberately a SEPARATE class:
    the NFL's league view is keyed by week and basketball's is keyed by date,
    because clubs play different numbers of games in a week. Sharing one cache
    would have meant a key that is a week for one sport and a date for another,
    which is the kind of quiet ambiguity that produces a rating computed from
    the wrong day.
    """

    def __init__(self) -> None:
        self._by_date: dict[tuple[int, str], dict[str, float]] = {}

    def on(self, conn: sqlite3.Connection, season: int,
           before: str) -> dict[str, float]:
        key = (season, before)
        if key not in self._by_date:
            rows = repo.league_history(conn, season, before)
            # BELOW THE FLOOR THERE IS NO RATING AT ALL, rather than a table of
            # zeroes that would read as "every club is exactly average".
            if len(rows) < MIN_LEAGUE_GAMES_FOR_SRS:
                self._by_date[key] = {}
            else:
                self._by_date[key] = context.srs_ratings(rows)
        return self._by_date[key]


#: One cache for the process. Ratings are a pure function of (season, date) and
#: the stored record before that date, and the record before a past date does
#: not change, so this is safe to share and worth sharing.
_RATINGS = SeasonRatings()
#: A player needs this many before we will ask a question about him...
MIN_PROP_HISTORY = 5
#: ...and must have played within this many days. A player who has quietly
#: stopped appearing resolves VOID and teaches the scorecard nothing while
#: occupying a slot on a capped slate. Basketball's version of the NFL rule,
#: in days rather than weeks because the schedule is daily.
MAX_DAYS_SINCE_PLAYED = 10
#: Below this many projected minutes a prop is not worth asking: the answer is
#: dominated by whether he plays at all, which is not what the question is about.
MIN_PROP_MINUTES = 20.0

PROP_STATS = ("points", "rebounds", "assists", "threes")


@dataclass
class NbaGameContext:
    """Everything an NBA spread factor may see. No market field exists on it."""

    game_id: str
    season: int
    week: int
    home: str
    away: str
    kickoff_utc: str | None
    game_date: str

    sport: str = SPORT
    line_asked: float | None = None
    neutral_site: bool = False

    home_availability: float | None = None
    away_availability: float | None = None
    home_rest_days: int | None = None
    away_rest_days: int | None = None
    home_road_games: int | None = None
    away_road_games: int | None = None
    home_pace: float | None = None
    away_pace: float | None = None
    #: SCORING FORM, for the totals market (roster #2, 2026-09-04). Points
    #: scored and allowed per game, and how variable each club's combined
    #: score has been. Absent, not zero, with no history.
    home_points_for: float | None = None
    home_points_against: float | None = None
    away_points_for: float | None = None
    away_points_against: float | None = None
    home_total_sd: float | None = None
    away_total_sd: float | None = None
    #: The combined score the model expects, and the rung it was asked at.
    expected_total: float | None = None
    home_net_rating: float | None = None
    away_net_rating: float | None = None
    league_pace: float | None = None

    home_rotation_n: int = 0
    away_rotation_n: int = 0
    injury_report_seen: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class NbaPropContext:
    """Everything an NBA prop factor may see."""

    game_id: str
    season: int
    week: int
    player_id: int
    player_name: str
    team: str
    opponent: str
    stat: str
    game_date: str

    sport: str = SPORT
    line_asked: float | None = None

    minutes_mean: float | None = None
    rolling_mean: float | None = None
    rolling_sd: float | None = None
    usage_rate: float | None = None
    stat_per_minute: float | None = None
    opponent_allowance: float | None = None
    league_allowance: float | None = None
    teammate_volume: float | None = None
    team_availability: float | None = None

    games: int = 0
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# availability — the measurement the whole sport turns on
# ---------------------------------------------------------------------------

def availability(conn: sqlite3.Connection, team: str, before: str) -> tuple[float | None, int]:
    """Minutes-weighted share of the club's rotation expected to be available.

    Defined so that it means the same thing in a backtest and in a forward
    prediction. A rotation player counts as unavailable if:

      * he did not appear in the club's most recent completed game — strictly
        prior information, identical in both regimes; or
      * he is listed OUT on the current injury report — which exists only
        forward, and so can only ever ADD information to a live prediction.

    That asymmetry is deliberate and one-directional: the fitted coefficient
    comes from the weaker of the two measurements, so it is a floor rather than
    a ceiling. Reading who actually played from the box score of the game being
    predicted would have been the easy version and would have fitted on
    hindsight the forward path can never have.
    """
    rot = repo.rotation(conn, team, before)
    if not rot:
        return None, 0
    played = repo.played_in_last_game(conn, team, before)
    if played is None:
        return None, len(rot)
    out_names = repo.listed_out(conn, team)

    total = 0.0
    available = 0.0
    for player in rot:
        weight = float(player["mpg"] or 0.0)
        total += weight
        if player["player_id"] not in played:
            continue
        if (player["player_name"] or "").strip().upper() in out_names:
            continue
        available += weight
    if total <= 0:
        return None, len(rot)
    return available / total, len(rot)


# ---------------------------------------------------------------------------
# contexts
# ---------------------------------------------------------------------------

def build_context(conn: sqlite3.Connection, game_id: str, line_asked=None) -> NbaGameContext:
    game = repo.game(conn, game_id)
    if game is None:
        raise KeyError(f"unknown NBA game {game_id!r}")
    on_date = repo.game_date(conn, game_id)
    if on_date is None:
        raise KeyError(f"NBA game {game_id!r} has no date")

    ctx = NbaGameContext(
        game_id=game_id,
        season=game["season"],
        week=game["week"],
        home=game["home"],
        away=game["away"],
        kickoff_utc=game["kickoff_utc"],
        game_date=on_date,
        line_asked=line_asked,
        neutral_site=bool(game["neutral_site"]),
    )
    ctx.injury_report_seen = bool(
        conn.execute("SELECT 1 FROM nba_injuries LIMIT 1").fetchone()
    )

    for side, team in (("home", game["home"]), ("away", game["away"])):
        share, n = availability(conn, team, on_date)
        setattr(ctx, f"{side}_availability", share)
        setattr(ctx, f"{side}_rotation_n", n)
        setattr(ctx, f"{side}_rest_days", repo.days_of_rest(conn, team, on_date))
        setattr(ctx, f"{side}_road_games", repo.road_games_recent(conn, team, on_date))

        recent = repo.team_recent(conn, team, on_date)
        if len(recent) >= MIN_TEAM_HISTORY:
            pace, rating, _n = repo.pace_and_rating(recent)
            setattr(ctx, f"{side}_pace", pace)
            setattr(ctx, f"{side}_net_rating", rating)
            # SCORING FORM for the totals market. Read from the same window as
            # the rating so the two describe the same stretch of basketball.
            pf, pa, sd, _rows = repo.scoring_form(conn, team, on_date)
            setattr(ctx, f"{side}_points_for", pf)
            setattr(ctx, f"{side}_points_against", pa)
            setattr(ctx, f"{side}_total_sd", sd)

    # OPPONENT-ADJUSTED RATINGS (D1, 2026-09-03). Solved over every completed
    # game this season BEFORE this one, so a rating cannot see the result it is
    # being used to predict. Absent for both clubs or neither: a game where one
    # side has a rating and the other does not has no rating DIFFERENCE, and
    # filling the gap with zero would silently claim the unrated club is exactly
    # league average.
    ratings = _RATINGS.on(conn, game["season"], on_date)
    home_srs, away_srs = ratings.get(game["home"]), ratings.get(game["away"])
    if home_srs is not None and away_srs is not None:
        ctx.home_srs, ctx.away_srs = home_srs, away_srs

    # THE EXPECTATION THE TOTAL IS ASKED AGAINST. Computed here so the rung
    # and the asked-distance factor read the same number -- two derivations of
    # one quantity is two chances to disagree about it.
    ctx.expected_total = questions.nba_expected_total(
        ctx.home_points_for, ctx.home_points_against,
        ctx.away_points_for, ctx.away_points_against)

    ctx.league_pace = repo.league_pace(conn, game["season"])
    if ctx.neutral_site:
        ctx.notes.append("neutral site: the home club is not in its own building")
    if not ctx.injury_report_seen:
        ctx.notes.append(
            "no injury report was loaded, so availability is measured only from "
            "who appeared in each club's last game"
        )
    return ctx


def build_prop_context(
    conn: sqlite3.Connection, game_id: str, player_id: int, stat: str, line_asked: float
) -> NbaPropContext:
    game = repo.game(conn, game_id)
    if game is None:
        raise KeyError(f"unknown NBA game {game_id!r}")
    on_date = repo.game_date(conn, game_id)
    if on_date is None:
        raise KeyError(f"NBA game {game_id!r} has no date")

    history = repo.player_recent(conn, player_id, on_date)
    if not history:
        raise KeyError(f"no history for NBA player {player_id}")
    team = history[0]["team"]
    if team not in (game["home"], game["away"]):
        # He was traded since his last appearance, so the club he most recently
        # played for is not in tonight's game. Raised rather than resolved to
        # the home side, which is what taking the else-branch would silently
        # have done: it would have named the wrong opponent and every
        # opponent-facing factor would then be measuring the wrong defence.
        raise KeyError(
            f"player {player_id} last played for {team}, which is not in "
            f"{game['away']} @ {game['home']}"
        )
    opponent = game["away"] if team == game["home"] else game["home"]

    ctx = NbaPropContext(
        game_id=game_id,
        season=game["season"],
        week=game["week"],
        player_id=player_id,
        player_name=history[0]["player_name"],
        team=team,
        opponent=opponent,
        stat=stat,
        game_date=on_date,
        line_asked=line_asked,
        games=len(history),
    )

    minutes = [float(r["minutes"]) for r in history if r["minutes"] is not None]
    if minutes:
        ctx.minutes_mean = sum(minutes) / len(minutes)

    total_minutes = sum(minutes) if minutes else 0.0
    values = [float(r[stat] or 0) for r in history]
    stat_total = sum(values)
    if total_minutes > 0:
        ctx.stat_per_minute = stat_total / total_minutes
    if values:
        ctx.rolling_mean = stat_total / len(values)
    if len(values) > 1 and ctx.rolling_mean is not None:
        var = sum((v - ctx.rolling_mean) ** 2 for v in values) / (len(values) - 1)
        ctx.rolling_sd = var ** 0.5

    # Usage: this player's shot-and-turnover load per minute, against his club's
    # per-minute load over the same window.
    player_load = sum(
        float(r["fga"] or 0) + 0.44 * float(r["fta"] or 0) + float(r["turnovers"] or 0)
        for r in history
    )
    team_games = repo.team_recent(conn, team, on_date)
    team_load = 0.0
    team_minutes = 0.0
    for g in team_games:
        p = repo.possessions(g)
        if p is None or not g["minutes"]:
            team_load = 0.0
            break
        team_load += p
        team_minutes += float(g["minutes"]) / 5.0
    if total_minutes > 0 and team_load > 0 and team_minutes > 0:
        ctx.usage_rate = (player_load / total_minutes) / (team_load / team_minutes)

    ctx.opponent_allowance, _n = repo.opponent_allowance(conn, opponent, stat, on_date)
    ctx.league_allowance = _league_allowance(conn, stat, game["season"])
    ctx.teammate_volume, _tn = repo.teammate_volume(conn, team, player_id, stat, on_date)
    ctx.team_availability, _rn = availability(conn, team, on_date)

    if ctx.games < repo.PLAYER_WINDOW:
        ctx.notes.append(f"only {ctx.games} prior games in the window")
    return ctx


_LEAGUE_ALLOWANCE: dict[tuple[str, int], float | None] = {}


def _league_allowance(conn: sqlite3.Connection, stat: str, season: int) -> float | None:
    """League-average team total in this stat, from PRIOR seasons only, so it is
    cutoff-safe by construction."""
    key = (stat, season)
    if key in _LEAGUE_ALLOWANCE:
        return _LEAGUE_ALLOWANCE[key]
    row = conn.execute(
        f"SELECT AVG(total) AS mean FROM ("
        f"  SELECT game_id, team, SUM({stat}) AS total FROM nba_player_games"
        "   WHERE season < ? GROUP BY game_id, team)",
        (season,),
    ).fetchone()
    value = float(row["mean"]) if row and row["mean"] is not None else None
    _LEAGUE_ALLOWANCE[key] = value
    return value


# ---------------------------------------------------------------------------
# the adapter surface
# ---------------------------------------------------------------------------

def next_slate(conn: sqlite3.Connection, season: int) -> int | None:
    from ..db import utcnow

    row = conn.execute(
        "SELECT MIN(week) AS w FROM games WHERE sport = 'nba' AND season = ?"
        " AND status = 'scheduled' AND kickoff_utc > ?",
        (season, utcnow()),
    ).fetchone()
    return None if row is None or row["w"] is None else int(row["w"])


def first_slate_note(conn: sqlite3.Connection, season: int) -> dict | None:
    """What the interface should say when the season has not started.

    Returns None once basketball is under way. Until then it returns the date of
    the first slate and how far off it is, so the NBA tab states plainly when it
    begins rather than rendering an empty page that reads as broken.
    """
    from ..db import utcnow

    played = conn.execute(
        "SELECT COUNT(*) AS n FROM games WHERE sport = 'nba' AND season = ?"
        " AND status = 'final'",
        (season,),
    ).fetchone()["n"]
    if played:
        return None
    row = conn.execute(
        "SELECT MIN(kickoff_utc) AS first FROM games WHERE sport = 'nba'"
        " AND season = ? AND kickoff_utc IS NOT NULL",
        (season,),
    ).fetchone()
    if row is None or not row["first"]:
        return {
            "state": "no_schedule",
            "message": (
                "The NBA schedule for this season has not been published yet. "
                "Nothing is being forecast, and nothing is being hidden."
            ),
        }
    first = row["first"]
    days = (date.fromisoformat(first[:10]) - date.fromisoformat(utcnow()[:10])).days
    scheduled = conn.execute(
        "SELECT COUNT(*) AS n FROM games WHERE sport = 'nba' AND season = ?", (season,)
    ).fetchone()["n"]
    return {
        "state": "preseason",
        "first_game_utc": first,
        "days_away": days,
        "games_scheduled": scheduled,
        "message": (
            f"The NBA season starts on {first[:10]}, {days} days from now. "
            f"{scheduled:,} games are loaded and waiting; the first forecasts are "
            "written the morning of the first slate. Nothing is predicted before "
            "then, because there is nothing yet to predict."
        ),
    }


def slate_questions(
    conn: sqlite3.Connection, season: int, week: int, *, include_props: bool = True
) -> list[Question]:
    games = repo.games_in_week(conn, season, week)
    out: list[Question] = []
    for game in games:
        # THE MONEYLINE IS ASKED FIRST AND ALWAYS (roster #1, 2026-09-04). It
        # has no rung, so nothing can disqualify it -- and asking it before the
        # spread's rung selection matters: a game whose expected margin falls
        # off the declared ladder is skipped for the spread and still gets a
        # moneyline. Two markets, two questions, and one of them is always
        # answerable.
        out.append(_moneyline_question(game))

        # THE RUNG IS CHOSEN AGAINST THE EXPECTED MARGIN (R4, extended to the
        # NBA by operator ruling 2026-09-03). The context is built first
        # because the rung now depends on it; the ratings it reads are stored
        # and blind.
        ctx = build_context(conn, game["id"])

        # THE TOTAL, asked at the half-point nearest the expected combined
        # score and REFUSED outside the declared band (roster #2). A game whose
        # expectation falls outside 185-278 -- the 1st and 99th percentiles of
        # 4,920 stored games -- gets no total question and still gets the other
        # two.
        total_rung = questions.nba_total_asked(ctx.expected_total)
        if total_rung is not None:
            out.append(
                Question(
                    sport=SPORT,
                    game_id=game["id"],
                    market_type="total",
                    market="total",
                    subject=f"{game['away']} @ {game['home']}",
                    line_asked=total_rung,
                    claim=(f"{game['away']} at {game['home']} goes over "
                           f"{total_rung:g} total points"),
                    yes_label="over",
                    no_label="under",
                )
            )

        expected = questions.expected_margin(
            SPORT, ctx.home_net_rating, ctx.away_net_rating)
        try:
            line = questions.spread_rung(game["id"], expected, SPREAD_LADDER)
        except questions.RungOffTheLadder:
            # Refused, not clamped (CFB-1). Measured at 0.60% of NBA games on
            # the extended ladder.
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

    for pick in select_week_props(conn, games):
        out.append(
            Question(
                sport=SPORT,
                game_id=pick["game_id"],
                # `prop` is the CLASS of question, the stat is WHICH prop. That
                # split is football's and it is kept: the schema's market_type
                # CHECK enforces the class, and (market_type, prop_type) is the
                # pair calibration already keys a category on, so basketball's
                # four markets are four separate curves without new machinery.
                market_type="prop",
                market=pick["stat"],
                subject=f"{pick['player_name']} {pick['stat']}",
                line_asked=pick["line_asked"],
                claim=(
                    f"{pick['player_name']} ({pick['team']}) records more than "
                    f"{pick['line_asked']:g} {pick['stat']}"
                ),
                yes_label="over",
                no_label="under",
                player_id=str(pick["player_id"]),
                stat=pick["stat"],
            )
        )
    return out


def prop_candidates(conn: sqlite3.Connection, game: sqlite3.Row) -> list[dict]:
    """Every prop question worth asking about one game.

    Eligibility only — which questions are worth asking, never what the answer
    is. A player must have a real recent sample, must have played recently
    enough that the question will actually resolve, and must project to enough
    minutes that the question is about his production rather than about whether
    he plays at all.
    """
    on_date = repo.game_date(conn, game["id"])
    if on_date is None:
        return []
    picks: list[dict] = []
    for team in (game["home"], game["away"]):
        for player in repo.rotation(conn, team, on_date):
            history = repo.player_recent(conn, player["player_id"], on_date)
            if len(history) < MIN_PROP_HISTORY:
                continue
            last = history[0]["game_date"]
            gap = (date.fromisoformat(on_date) - date.fromisoformat(last)).days
            if gap > MAX_DAYS_SINCE_PLAYED:
                continue
            mpg = float(player["mpg"] or 0.0)
            if mpg < MIN_PROP_MINUTES:
                continue
            # ONE stat per player per game, chosen by a stable rotation.
            # Sorting the four and taking the first would have asked every
            # player about assists forever - alphabetical order is not a
            # sampling strategy, and three of the four markets would have sat
            # permanently empty while looking merely unlucky.
            order = questions.stable_index(
                f"{game['id']}:{player['player_id']}", len(PROP_STATS)
            )
            for offset in range(len(PROP_STATS)):
                stat = PROP_STATS[(order + offset) % len(PROP_STATS)]
                values = [float(r[stat] or 0) for r in history]
                mean = sum(values) / len(values)
                if mean < 1.0:
                    # A question about a stat he does not record is not a
                    # question, it is a formality with a known answer. Fall
                    # through to the next stat in the rotation rather than
                    # dropping the player.
                    continue
                picks.append(
                    {
                        "game_id": game["id"],
                        "player_id": player["player_id"],
                        "player_name": player["player_name"],
                        "team": team,
                        "stat": stat,
                        "rolling_mean": mean,
                        "minutes": mpg,
                        "line_asked": questions.prop_line_asked(
                            mean, f"{game['id']}:{player['player_id']}:{stat}", stat
                        ),
                    }
                )
                break
    return picks


def select_week_props(conn: sqlite3.Connection, games) -> list[dict]:
    """Fill the slate's prop budget across the week's games.

    ROUND-ROBIN across games, not a global sort by minutes. The difference
    matters: a global sort hands all forty slots to the highest-minutes players
    in the league, which on an NBA week means the same three dozen stars every
    time. The resulting record would be about those players rather than about
    the model, and their rows would be heavily correlated week to week. Taking
    each game's best candidate first, then each game's second, spreads the same
    budget across the league.

    Within a game, candidates are ordered by projected minutes, because minutes
    are what make a prop resolvable at all. This is an eligibility rule - which
    questions are worth asking - never a claim about what the answer is.
    """
    per_game = config.PROPS_PER_GAME
    budget = config.PROPS_PER_WEEK
    ranked: list[list[dict]] = []
    for game in games:
        candidates = prop_candidates(conn, game)
        candidates.sort(key=lambda c: (-c["minutes"], c["player_name"], c["stat"]))
        seen: set[int] = set()
        chosen: list[dict] = []
        for c in candidates:
            if len(chosen) >= per_game:
                break
            # One question per player per game: four questions about the same
            # man are four correlated rows dressed up as four observations.
            if c["player_id"] in seen:
                continue
            seen.add(c["player_id"])
            chosen.append(c)
        if chosen:
            ranked.append(chosen)

    out: list[dict] = []
    for rank in range(per_game):
        for game_picks in ranked:
            if rank < len(game_picks):
                out.append(game_picks[rank])
                if len(out) >= budget:
                    return out
    return out


def build_features(conn: sqlite3.Connection, q: Question, cache=None):
    if q.market_type == "moneyline":
        # NO LINE. A moneyline question carries none, and passing one would
        # put a number on the context that no factor is declared to read.
        ctx = build_context(conn, q.game_id)
        return compute.feature_vector(ctx, "moneyline"), ctx
    if q.market_type == "total":
        ctx = build_context(conn, q.game_id, line_asked=q.line_asked)
        return compute.feature_vector(ctx, "total"), ctx
    if q.market_type == "spread":
        ctx = build_context(conn, q.game_id, line_asked=q.line_asked)
        return compute.feature_vector(ctx, "spread"), ctx
    ctx = build_prop_context(
        conn, q.game_id, int(q.player_id), q.stat, q.line_asked
    )
    # Every prop market shares one factor vocabulary and is fitted separately;
    # `prop` is the vocabulary's name, `q.market_type` is the category's.
    return compute.feature_vector(ctx, "prop"), ctx


def training_set(
    conn: sqlite3.Connection,
    seasons,
    market: str,
    *,
    through_season: int | None = None,
    through_week: int | None = None,
    progress=None,
):
    from ..factors import registry

    if market == "total":
        return _total_training_set(
            conn, seasons, through_season, through_week, progress
        )
    if market == "moneyline":
        return _moneyline_training_set(
            conn, seasons, through_season, through_week, progress
        )
    if market == "spread":
        return _spread_training_set(
            conn, seasons, through_season, through_week, progress
        )
    if market in PROP_STATS:
        return _prop_training_set(
            conn, seasons, market, through_season, through_week, progress
        )
    raise ValueError(f"NBA has no {market!r} market")


def _completed_games(conn, seasons, through_season, through_week):
    placeholders = ",".join("?" for _ in seasons)
    sql = (
        f"SELECT id, sport, season, week FROM games"
        f" WHERE sport = 'nba' AND status = 'final'"
        f" AND season IN ({placeholders})"
    )
    params: list = list(seasons)
    if through_season is not None:
        sql += " AND (season < ? OR (season = ? AND week <= ?))"
        params += [through_season, through_season, through_week or 999]
    games = conn.execute(sql + " ORDER BY season, week, id", params).fetchall()
    baseline.assert_one_sport(games, "nba", "nba._completed_games")
    return games




# ---------------------------------------------------------------------------
# the moneyline (MARKET_ROSTER #1, 2026-09-04)
# ---------------------------------------------------------------------------

def _moneyline_question(game) -> Question:
    """One question per game: does the home club win?

    NO RUNG, NO LADDER, NO FLOOR. A moneyline is the only question in this
    project with nothing to choose -- there is no line to place, so there is
    no rung to get wrong and no ladder to fall off. Every other market's
    hardest decision is which question to ask; this one asks the only question
    there is.

    NO CONFIDENCE FLOOR EITHER. `config.PROPS_MIN_CLAIM` exists because a
    player-prop slate offers hundreds of questions and asking the ones the
    model is unsure about is asking for noise. A moneyline slate offers one
    question per game, they are the whole slate, and dropping the close ones
    would leave a record made only of blowouts -- which is the flattering
    selection LAW 4 exists to prevent. Every game is asked.
    """
    return Question(
        sport=SPORT,
        game_id=game["id"],
        market_type="moneyline",
        market="moneyline",
        subject=game["home"],
        line_asked=None,
        claim=f"{game['home']} (home) beats {game['away']}",
        yes_label="win",
        no_label="lose",
    )


def _total_training_set(conn, seasons, through_season, through_week, progress):
    """One row per completed game whose expectation was inside the band.

    THE SAME RULE THE FORWARD PATH USES. A training set asked at every game's
    total and a live slate that refuses the ones outside 185-278 would be two
    different questions sharing a coefficient -- and the refused ones are
    exactly the games whose behaviour the model has least evidence about, so
    training on them would teach it the tail it is not allowed to price.
    """
    from ..factors import registry

    games = _completed_games(conn, seasons, through_season, through_week)
    rows: list[dict] = []
    labels: list[int] = []
    for i, g in enumerate(games):
        if progress and i % 500 == 0:
            progress(f"nba total features {i}/{len(games)}")
        try:
            ctx = build_context(conn, g["id"])
        except KeyError:
            continue
        rung = questions.nba_total_asked(ctx.expected_total)
        if rung is None:
            continue                      # refused here exactly as live
        ctx.line_asked = rung
        fv = compute.feature_vector(ctx, "total")
        score = conn.execute(
            "SELECT home_score, away_score FROM games WHERE id = ?", (g["id"],)
        ).fetchone()
        if score["home_score"] is None or score["away_score"] is None:
            continue
        combined = score["home_score"] + score["away_score"]
        rows.append(fv.values)
        labels.append(1 if combined > rung else 0)

    names = [f.name for f in registry.active_factors(SPORT, "total")]
    return rows, labels, names


def _moneyline_training_set(conn, seasons, through_season, through_week,
                            progress):
    """One row per completed game: the factor vector, and whether home won.

    THE SAME CONTEXT THE SPREAD USES, and deliberately the same factors: how
    good the two clubs have been, how they have played lately, who is
    available, who is rested, who travelled. Those are the things that decide a
    basketball game, and they do not become different things because the
    question is asked without a handicap.

    WHAT IS NOT SHARED IS THE FIT. The two markets get separate coefficients,
    separate categories and separate gates, because "does the home club win"
    and "does it win by more than 4.5" are different questions and a curve
    covering both would describe neither.

    A DRAW IS NOT POSSIBLE. Basketball plays overtime until somebody wins, so
    unlike a football moneyline there is no third outcome to rule on. That is
    stated rather than assumed: the resolution path below has no draw branch
    and this is the reason.
    """
    from ..factors import registry

    games = _completed_games(conn, seasons, through_season, through_week)
    rows: list[dict] = []
    labels: list[int] = []
    for i, g in enumerate(games):
        if progress and i % 500 == 0:
            progress(f"nba moneyline features {i}/{len(games)}")
        try:
            ctx = build_context(conn, g["id"])
        except KeyError:
            continue
        # NO LINE ON THE CONTEXT. `nba_asked_distance` is declared for the
        # spread only, so the moneyline's factor set does not contain it and
        # nothing here has a rung to set. Leaving `line_asked` as None is what
        # makes the absence explicit rather than incidental.
        fv = compute.feature_vector(ctx, "moneyline")
        score = conn.execute(
            "SELECT home_score, away_score FROM games WHERE id = ?", (g["id"],)
        ).fetchone()
        if score["home_score"] is None or score["away_score"] is None:
            continue
        rows.append(fv.values)
        labels.append(1 if score["home_score"] > score["away_score"] else 0)

    names = [f.name for f in registry.active_factors(SPORT, "moneyline")]
    return rows, labels, names


class DisagreesWithTheSpread(AssertionError):
    """The two game markets contradict each other about the same game."""


def assert_markets_agree(win_p: float | None, cover_p: float | None,
                         rung: float | None, label: str = "this game") -> None:
    """CHECKLIST ITEM 4: two numbers describing one world must agree.

    THE RELATION IS LOGICAL, NOT STATISTICAL, which is what makes it worth
    asserting. Writing the margin as M:

        P(home wins)   = P(M > 0)
        P(home covers) = P(M + rung > 0) = P(M > -rung)

    So a home club GIVING points -- a negative rung -- must be less likely to
    cover than to win, because every game it covers it also wins and not the
    other way round. A home club RECEIVING points must be more likely to cover
    than to win, for the mirror reason. THERE IS NO ESTIMATION IN THIS. A model
    that breaks it is contradicting itself, not being slightly off, and the
    contradiction is invisible on a card showing one market at a time.

    THIS IS THE SHAPE OF CHECK THAT CAUGHT THE ESPN SIGN ERROR: a stored spread
    whose direction its own favourite flag denied. The second number is what
    makes the first checkable.

    A FIRST VERSION OF THIS COMPARED THE MONEYLINE TO `expected_margin` AND WAS
    WRONG TO. That device is deliberately blind and rating-only -- it exists to
    choose a rung before the model runs -- so it reads a different set of
    inputs from the eight-factor moneyline. It fired on 9 of 200 real games,
    and every one of them was two instruments legitimately disagreeing rather
    than one being broken. A cross-check between numbers that are not
    comparable is a check that will be silenced rather than believed.

    THE TOLERANCE IS FOR ARITHMETIC, NOT FOR JUDGEMENT. Both probabilities come
    from separately fitted logistics, so they carry independent estimation
    error; `MARKET_AGREEMENT_SLACK` is the width at which a difference stops
    being rounding and starts being a contradiction.
    """
    if win_p is None or cover_p is None or rung is None:
        return
    if rung < 0 and cover_p > win_p + MARKET_AGREEMENT_SLACK:
        raise DisagreesWithTheSpread(
            f"{label}: the home club is giving {abs(rung):g} points, so it "
            f"cannot be likelier to cover ({cover_p:.1%}) than to win "
            f"({win_p:.1%}). Every game it covers it also wins.")
    if rung > 0 and cover_p < win_p - MARKET_AGREEMENT_SLACK:
        raise DisagreesWithTheSpread(
            f"{label}: the home club is receiving {rung:g} points, so it "
            f"cannot be less likely to cover ({cover_p:.1%}) than to win "
            f"({win_p:.1%}). Every game it wins it also covers.")


#: How far the two fitted models may differ before they are contradicting each
#: other rather than carrying independent estimation error. Five points of
#: probability. Declared 2026-09-04, not tuned: it is the width at which a
#: difference stops being arithmetic and starts being a claim.
MARKET_AGREEMENT_SLACK = 0.05


def _spread_training_set(conn, seasons, through_season, through_week, progress):
    from ..factors import registry

    games = _completed_games(conn, seasons, through_season, through_week)
    rows: list[dict] = []
    labels: list[int] = []
    for i, g in enumerate(games):
        if progress and i % 500 == 0:
            progress(f"nba spread features {i}/{len(games)}")
        # THE SAME RULE THE FORWARD PATH USES (R4, 2026-09-03). A training set
        # asked at rotated rungs and a live slate asked at margin-chosen ones
        # would be two different questions sharing a coefficient. The context
        # comes first because the rung now depends on it.
        try:
            ctx = build_context(conn, g["id"])
        except KeyError:
            continue
        expected = questions.expected_margin(
            SPORT, ctx.home_net_rating, ctx.away_net_rating)
        try:
            line = questions.spread_rung(g["id"], expected, SPREAD_LADDER)
        except questions.RungOffTheLadder:
            # The training set skips what the live slate would skip.
            continue
        ctx.line_asked = line
        fv = compute.feature_vector(ctx, "spread")
        score = conn.execute(
            "SELECT home_score, away_score FROM games WHERE id = ?", (g["id"],)
        ).fetchone()
        if score["home_score"] is None or score["away_score"] is None:
            continue
        rows.append(fv.values)
        labels.append(
            questions.spread_outcome(score["home_score"], score["away_score"], line)
        )
    names = [f.name for f in registry.active_factors(SPORT, "spread")]
    return rows, labels, names


def _prop_training_set(conn, seasons, stat, through_season, through_week, progress):
    """Rows for one prop market.

    Note what this trains on. `prop_candidates` gives each player ONE stat per
    game, chosen by a stable hash of the two ids, so a given market sees roughly
    a quarter of all eligible player-games — 15,076 for points, 11,866 for
    rebounds. That is a RANDOM SUBSAMPLE, not a selection effect: the hash is a
    crc32 of two identifiers and knows nothing about how anyone played. It costs
    a little precision on the coefficients and buys a training set that matches
    the shape of the questions actually asked. Training on all four stats for
    every player would quadruple the rows and the runtime, and would fit on
    questions the live slate never puts.
    """
    from ..factors import registry

    games = _completed_games(conn, seasons, through_season, through_week)
    rows: list[dict] = []
    labels: list[int] = []
    for i, g in enumerate(games):
        if progress and i % 200 == 0:
            progress(f"nba {stat} features {i}/{len(games)}")
        game = repo.game(conn, g["id"])
        for pick in prop_candidates(conn, game):
            if pick["stat"] != stat:
                continue
            actual = conn.execute(
                f"SELECT {stat} AS v FROM nba_player_games WHERE game_id = ?"
                " AND player_id = ?",
                (g["id"], pick["player_id"]),
            ).fetchone()
            if actual is None or actual["v"] is None:
                continue          # did not play: VOID forward, excluded here
            try:
                ctx = build_prop_context(
                    conn, g["id"], pick["player_id"], stat, pick["line_asked"]
                )
            except KeyError:
                continue
            fv = compute.feature_vector(ctx, "prop")
            rows.append(fv.values)
            labels.append(questions.prop_outcome(float(actual["v"]), pick["line_asked"]))
    names = [f.name for f in registry.active_factors(SPORT, "prop")]
    return rows, labels, names


def resolve_outcome(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    """Settle one NBA prediction, or raise Void when the question has no answer."""
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

    if pred["market_type"] == "total":
        # NO PUSH IS POSSIBLE. Every rung is a half-point, so a combined score
        # is strictly above or strictly below it and the question always has an
        # answer. That is why the half is in `nba_total_asked` and not a
        # rounding convenience.
        outcome = questions.total_outcome(
            game["home_score"], game["away_score"], pred["line_asked"])
        return outcome if pred["model_side"] == "over" else 1 - outcome

    if pred["market_type"] == "moneyline":
        # NO DRAW BRANCH, AND THAT IS A FACT ABOUT BASKETBALL rather than an
        # omission: the NBA plays overtime until somebody wins, so a final
        # score with equal points does not exist. If one ever appears it is a
        # bad row rather than a tie, and it VOIDS -- the question would have no
        # answer, and inventing one is what this project refuses to do.
        if game["home_score"] == game["away_score"]:
            raise Void(
                f"{pred['game_id']} is final with the scores level, which the "
                f"NBA does not produce. The row is wrong rather than the game "
                f"being drawn, and a wrong row gets no outcome.")
        home_won = 1 if game["home_score"] > game["away_score"] else 0
        return home_won if pred["model_side"] == "win" else 1 - home_won

    if pred["market_type"] == "spread":
        outcome = questions.spread_outcome(
            game["home_score"], game["away_score"], pred["line_asked"]
        )
        return outcome if pred["model_side"] == "cover" else 1 - outcome

    stat = pred["prop_type"]
    player_id = _player_of(pred)
    if player_id is None:
        raise Unresolvable(
            f"prediction {pred['id']} carries no player id, so there is nothing "
            "to look up"
        )
    row = conn.execute(
        f"SELECT {stat} AS v, minutes FROM nba_player_games WHERE game_id = ?"
        " AND player_id = ?",
        (pred["game_id"], player_id),
    ).fetchone()
    if row is None or row["v"] is None:
        # Same as resolve.py: a shown sentence gets the person, not the stored
        # subject with its stat suffix.
        who = subjects.strip_market_suffix(pred["subject"], pred["prop_type"])
        raise Void(
            f"{who} did not appear in {pred['game_id']}. The question "
            "asked how much he would record, and a man who did not play did not "
            "answer it either way; scoring it as an under would credit the model "
            "for a roster decision it never forecast."
        )
    outcome = questions.prop_outcome(float(row["v"]), pred["line_asked"])
    return outcome if pred["model_side"] == "over" else 1 - outcome


def _player_of(pred: sqlite3.Row) -> int | None:
    import json

    try:
        payload = json.loads(pred["factors_json"])
    except (TypeError, ValueError):
        return None
    player = (payload.get("question") or {}).get("player_id")
    return int(player) if player else None


def markets() -> tuple[str, ...]:
    """The markets this sport asks about.

    ADDED 2026-09-03. `run.already_answered` has called this on every sport
    since the duplicate-slate guard was written (ruling R4, 2026-09-02), and
    neither this module nor the NBA's defined it -- so the guard raised
    AttributeError before it could refuse anything. The protection that stopped
    NFL week 1 being forecast twice has never covered these two sports.
    """
    return config.SPORT_MARKETS[SPORT]
