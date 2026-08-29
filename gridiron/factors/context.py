"""Everything a factor is allowed to see, gathered once per prediction.

A context is built from stored non-market data only. Factor functions read
attributes off it and do no I/O of their own, which keeps each factor a small
readable expression and makes it obvious what any of them could possibly know.

Two invariants, both load-bearing:

* No market field exists on a context. There is nowhere for a line to sit.
* Every historical query is cut off strictly before the game being predicted.
  A context for week 7 is assembled from weeks 1-6 and nothing else.
"""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass, field

from ..data import reference, repo

#: Injury report statuses, mapped to a share of availability lost. Read straight
#: off the report; no judgement about how badly hurt anyone is (LAW 2 note in
#: registry.injury_out_diff).
STATUS_PENALTY = {
    "Out": 1.0,
    "Doubtful": 0.5,
    "Questionable": 0.25,
}

RECENT_WINDOW = 4
PROP_WINDOW = 8


@dataclass
class GameContext:
    game_id: str
    season: int
    week: int
    home: str
    away: str
    kickoff_utc: str | None

    #: Which sport's factor registry applies. Every context carries it, so
    #: NFL's factors can never reach a baseball model by omission (LAW 6).
    sport: str = "nfl"

    #: The line OUR question is about, chosen blind. It is not the market's
    #: price and never becomes one; see the module docstring.
    line_asked: float | None = None

    neutral_site: bool = False
    div_game: float | None = None
    home_rest: int | None = None
    away_rest: int | None = None

    #: Miles travelled by the subject of the prediction. For a spread that is
    #: the visiting club; the home club travels nothing.
    subject_travel_miles: float | None = None
    #: Time-zone hours crossed by that same subject, west-to-east positive.
    subject_tz_delta: float | None = None

    home_srs: float | None = None
    away_srs: float | None = None
    srs_basis: str = "none"          # 'season' | 'prior_season' | 'none'
    home_recent_margin: float | None = None
    away_recent_margin: float | None = None
    home_pace: float | None = None
    away_pace: float | None = None
    home_games_played: int = 0
    away_games_played: int = 0

    home_out: int | None = None
    away_out: int | None = None
    home_qb_out: int | None = None
    away_qb_out: int | None = None

    indoors: bool = False
    wind_mph: float | None = None
    temp_f: float | None = None
    precip_pct: float | None = None
    weather_basis: str = "none"      # 'forecast' | 'observed' | 'indoors' | 'none'

    notes: list[str] = field(default_factory=list)


@dataclass
class PropContext(GameContext):
    """A game context plus the player-specific view. Inherits the shared
    factors (travel, weather) so they are computed once and read the same way."""

    player_id: str = ""
    player_name: str = ""
    position: str = ""
    team: str = ""
    opponent: str = ""
    stat: str = ""

    volume_recent: float | None = None
    efficiency_recent: float | None = None
    rolling_mean: float | None = None
    rolling_sd: float | None = None
    rolling_n: int = 0
    allowance: float | None = None
    allowance_n: int = 0
    allowance_league_avg: float | None = None
    player_status_penalty: float | None = None
    #: The player's share of his own offence's volume in this market.
    volume_share: float | None = None
    #: Recent offensive snap share, and the games it was measured over.
    snap_share: float | None = None
    snap_share_n: int = 0
    #: Expected margin for the PLAYER'S team, positive when they are favoured.
    game_script: float | None = None


# ---------------------------------------------------------------------------
# opponent-adjusted ratings
# ---------------------------------------------------------------------------

def srs_ratings(rows, iterations: int = 12) -> dict[str, float]:
    """Simple Rating System: a team's rating is its average margin plus the
    average rating of the teams it played, solved by iteration.

    This is the cheap opponent adjustment. It is fully inspectable — the whole
    method is the four lines below — and it removes the main distortion in a raw
    point differential, which is that some clubs have played nobody yet.
    """
    games: dict[str, list[tuple[float, str]]] = {}
    for r in rows:
        if r["points_for"] is None or not r["opponent"]:
            continue
        games.setdefault(r["team"], []).append(
            (float(r["points_for"] - r["points_against"]), r["opponent"])
        )
    if not games:
        return {}

    rating = {t: sum(m for m, _ in g) / len(g) for t, g in games.items()}
    for _ in range(iterations):
        updated = {
            t: sum(m + rating.get(opp, 0.0) for m, opp in g) / len(g)
            for t, g in games.items()
        }
        mean = sum(updated.values()) / len(updated)
        rating = {t: v - mean for t, v in updated.items()}
    return rating


class WeekCache:
    """Memoises the per-(season, week) league view.

    Every game in a week shares the same history and therefore the same ratings.
    Training over ten seasons builds ~2,700 contexts across ~190 distinct weeks,
    so without this the same SRS is solved fourteen times per week for nothing.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[int, int], tuple[dict[str, float], dict[str, list]]] = {}
        self._prior: dict[tuple[int, str], float | None] = {}

    def league(self, conn: sqlite3.Connection, season: int, week: int):
        key = (season, week)
        if key not in self._cache:
            rows = repo.league_history(conn, season, week)
            played: dict[str, list] = {}
            for r in rows:
                played.setdefault(r["team"], []).append(r)
            self._cache[key] = (srs_ratings(rows), played)
        return self._cache[key]

    def prior_margin(self, conn: sqlite3.Connection, season: int, team: str):
        key = (season, team)
        if key not in self._prior:
            self._prior[key] = repo.prior_season_margin(conn, season, team)
        return self._prior[key]


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def _travel(game: sqlite3.Row) -> tuple[float | None, float | None]:
    """Miles and time zones crossed by the visiting club."""
    venue = reference.venue_site(
        game["home"], game["stadium"], bool(game["neutral_site"])
    )
    origin = reference.site_for(game["away"])
    if venue is None or origin is None:
        return None, None
    miles = reference.haversine_miles(origin[0], origin[1], venue[0], venue[1])
    return miles, float(venue[2] - origin[2])


def _injury_counts(
    conn: sqlite3.Connection, season: int, week: int, team: str
) -> tuple[int | None, int | None]:
    """(players declared Out, starter-QB declared Out).

    An empty report is `None`, not zero. No report published is missing data;
    a published report with nobody Out is a real zero. Conflating the two would
    quietly tell the model that every unreported week was a healthy week.
    """
    rows = repo.injuries_for(conn, season, week, team)
    if not rows:
        return None, None
    out = sum(1 for r in rows if (r["report_status"] or "") == "Out")
    qb_out = sum(
        1 for r in rows if (r["report_status"] or "") == "Out" and (r["position"] or "") == "QB"
    )
    return out, min(qb_out, 1)


def _weather(conn: sqlite3.Connection, game: sqlite3.Row) -> tuple[bool, float | None, float | None, float | None, str]:
    roof = (game["roof"] or "").lower()
    if roof in ("dome", "closed"):
        return True, 0.0, None, 0.0, "indoors"

    forecast = repo.weather_for(conn, game["id"])
    if forecast is not None:
        return False, forecast["wind_mph"], forecast["temp_f"], forecast["precip_pct"], "forecast"

    # Observed conditions, which the source only fills in after the game. Fine
    # for backtesting; for an upcoming game these are simply absent.
    if game["wind_mph"] is not None or game["temp_f"] is not None:
        return False, game["wind_mph"], game["temp_f"], None, "observed"

    return False, None, None, None, "none"


def build_game_context(
    conn: sqlite3.Connection,
    game_id: str,
    cache: "WeekCache | None" = None,
    line_asked: float | None = None,
) -> GameContext:
    game = repo.game(conn, game_id)
    if game is None:
        raise KeyError(f"unknown game {game_id!r}")

    season, week = game["season"], game["week"]
    cache = cache or WeekCache()
    ratings, played = cache.league(conn, season, week)

    ctx = GameContext(
        game_id=game_id,
        season=season,
        week=week,
        home=game["home"],
        away=game["away"],
        kickoff_utc=game["kickoff_utc"],
        line_asked=line_asked,
        neutral_site=bool(game["neutral_site"]),
        div_game=None if game["div_game"] is None else float(game["div_game"]),
        home_rest=game["home_rest"],
        away_rest=game["away_rest"],
    )

    ctx.subject_travel_miles, ctx.subject_tz_delta = _travel(game)

    for side, team in (("home", game["home"]), ("away", game["away"])):
        history = played.get(team, [])
        setattr(ctx, f"{side}_games_played", len(history))

        if len(history) >= 2:
            setattr(ctx, f"{side}_srs", ratings.get(team))
        else:
            setattr(ctx, f"{side}_srs", cache.prior_margin(conn, season, team))

        recent = history[-RECENT_WINDOW:]
        if recent:
            setattr(
                ctx,
                f"{side}_recent_margin",
                sum(r["points_for"] - r["points_against"] for r in recent) / len(recent),
            )
        paces = [r["plays"] for r in history if r["plays"]]
        if paces:
            setattr(ctx, f"{side}_pace", sum(paces) / len(paces))

        out, qb_out = _injury_counts(conn, season, week, team)
        setattr(ctx, f"{side}_out", out)
        setattr(ctx, f"{side}_qb_out", qb_out)

    if ctx.home_games_played >= 2 and ctx.away_games_played >= 2:
        ctx.srs_basis = "season"
    elif ctx.home_srs is not None and ctx.away_srs is not None:
        ctx.srs_basis = "prior_season"
        ctx.notes.append(
            f"week {week}: too few games this season, ratings fall back to "
            f"{season - 1} average margin"
        )
    else:
        ctx.srs_basis = "none"
        ctx.notes.append("no rating available for at least one side")

    ctx.indoors, ctx.wind_mph, ctx.temp_f, ctx.precip_pct, ctx.weather_basis = _weather(
        conn, game
    )
    if ctx.weather_basis == "observed":
        ctx.notes.append("weather is the observed post-game reading, not a forecast")
    elif ctx.weather_basis == "none":
        ctx.notes.append("no weather available for an outdoor game")

    return ctx


# The stat -> column maps live in `model.questions` and are imported, not
# copied. They were duplicated here once; the copy fell behind when two markets
# were added, and `receptions` and `passing_tds` raised KeyError and were
# silently skipped by every caller that catches KeyError. One source of truth.
def _stat_maps():
    from ..model.questions import STAT_POSITIONS, STAT_VOLUME_STAT

    return STAT_VOLUME_STAT, STAT_POSITIONS


def build_prop_context(
    conn: sqlite3.Connection,
    game_id: str,
    player_id: str,
    stat: str,
    line_asked: float,
    cache: "WeekCache | None" = None,
) -> PropContext:
    base = build_game_context(conn, game_id, cache, line_asked)
    game = repo.game(conn, game_id)

    history = repo.player_history(conn, player_id, base.season, base.week, PROP_WINDOW)
    if not history:
        raise KeyError(f"no history for player {player_id!r} before {base.season} wk{base.week}")

    latest = history[0]
    team = latest["team"] or ""
    opponent = game["away"] if team == game["home"] else game["home"]
    position = latest["position"] or (position_map.get(stat) or ("",))[0]

    volume_map, position_map = _stat_maps()
    if stat not in volume_map:
        raise KeyError(f"undeclared prop market {stat!r}")
    values = [float(r[stat] or 0.0) for r in history]
    volume_col = volume_map[stat]
    volumes = [float(r[volume_col] or 0.0) for r in history]

    ctx = PropContext(
        **{k: getattr(base, k) for k in GameContext.__dataclass_fields__},
    )
    ctx.player_id = player_id
    ctx.player_name = latest["player_name"] or player_id
    ctx.position = position
    ctx.team = team
    ctx.opponent = opponent
    ctx.stat = stat
    ctx.line_asked = line_asked

    volume_stat = volume_map.get(stat)
    if volume_stat and team:
        team_total = repo.team_volume(conn, base.season, team, base.week, volume_stat)
        player_mean = sum(float(r[volume_stat] or 0.0) for r in history) / len(history)
        if team_total and team_total > 0:
            ctx.volume_share = player_mean / team_total

    ctx.snap_share, ctx.snap_share_n = repo.snap_share(
        conn, base.season, team, ctx.player_name, base.week
    )

    # Game script from the spread question's own ratings, signed for the
    # player's team. No market number is involved, and none could be.
    if base.home_srs is not None and base.away_srs is not None:
        margin = base.home_srs - base.away_srs
        ctx.game_script = margin if team == game["home"] else -margin

    ctx.rolling_n = len(values)
    ctx.rolling_mean = sum(values) / len(values)
    ctx.rolling_sd = statistics.stdev(values) if len(values) > 1 else None
    ctx.volume_recent = sum(volumes) / len(volumes) if volumes else None
    if ctx.volume_recent:
        ctx.efficiency_recent = ctx.rolling_mean / ctx.volume_recent

    # The player travels only if their club is the visitor.
    if team == game["home"]:
        ctx.subject_travel_miles = 0.0
        ctx.subject_tz_delta = 0.0

    allowance, allowance_n = repo.positional_allowance(
        conn, base.season, opponent, position, base.week
    )
    ctx.allowance, ctx.allowance_n = allowance, allowance_n
    if allowance is not None:
        league_rows = conn.execute(
            "SELECT SUM(COALESCE(passing_yards,0) + COALESCE(rushing_yards,0)"
            "          + COALESCE(receiving_yards,0)) AS yds, COUNT(DISTINCT opponent || week) AS n"
            " FROM player_week_stats WHERE position = ? AND season = ? AND week < ?",
            (position, base.season, base.week),
        ).fetchone()
        if league_rows and league_rows["n"]:
            ctx.allowance_league_avg = float(league_rows["yds"]) / league_rows["n"]

    status_rows = [
        r
        for r in repo.injuries_for(conn, base.season, base.week, team)
        if (r["player_name"] or "") == ctx.player_name
    ]
    if repo.injuries_for(conn, base.season, base.week, team):
        status = (status_rows[0]["report_status"] if status_rows else "") or ""
        ctx.player_status_penalty = STATUS_PENALTY.get(status, 0.0)

    if ctx.rolling_n < 4:
        ctx.notes.append(f"only {ctx.rolling_n} prior games for this player")
    if 0 < ctx.allowance_n < 4:
        ctx.notes.append(f"opponent allowance is a {ctx.allowance_n}-game sample")

    return ctx
