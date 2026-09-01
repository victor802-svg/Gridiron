"""College football: three team markets, and its own calibration families.

Spread, moneyline and total. No player props — the probe found zero prop rows
on completed and upcoming games alike, and a CFB event carries exactly one odds
provider whose `propBets` endpoint 404s. Player game statistics exist and would
resolve props; the gap is the lines (docs/CFB_FEASIBILITY.md section 6).

WHERE THIS ADAPTER DIFFERS FROM THE OTHERS
==========================================
**A slate is a day.** `week` is null on every 2026 event, so the loader stores
the day as YYYYMMDD and slates are drawn by day. It is also the honest unit:
Saturday holds 60 games, Sunday 16 and Friday 8, and a week ordinal would ask
one question of three different cards.

**Its spread ladder is its own.** CFB's home-margin SD is 22.46 against the
NFL's 12.70 and 39% of games are decided by 21 or more, so the NFL's rungs
would sit on one side of nearly every answer.

**Totals are a new question shape.** "Do the two teams combine for more than
52.5 points" is not a margin question and shares no calibration family with
one — it is right and wrong for different reasons, and the market prices it
separately. It gets its own category and its own gate, per checklist item 6.

ON R-A AND LAW 1
================
The brief asks for questions "only for lined games". **That cannot be done
inside the blind window**, and it is not a small technicality:

    LAW 1: the model's probability is computed and WRITTEN TO THE DATABASE
    before any market line is fetched or passed into the prediction path.

Choosing WHICH questions to ask by whether the market has priced them makes the
market an input to the prediction path — the audit's closure scan forbids this
module from naming a market table at all, and would fail the build.

So questions are formed blind for every game on the slate, and the R-A number
is REPORTED rather than enforced: after the snapshot step (which runs once the
prediction rows exist), the record says how many of the slate's games carried a
line. The measured coverage makes the practical gap small — spread and total
are at ~100%, so only the moneyline's ~73% differs — and a game with no line
already renders as "no line" rather than as a missing prediction.

This is flagged for a ruling rather than worked around.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from .. import config
from ..data import cfb_repo as repo
from ..data import cfb_venues as venues
from ..data import weather
from ..factors import compute
from ..model import questions
from ..model.question import Question

SPORT = "cfb"


class Void(RuntimeError):
    """The question cannot be answered, so it is not given an answer."""


@dataclass
class CfbContext:
    """Everything a CFB factor may see. No market field exists on it."""

    game_id: str
    season: int
    day: int
    home: str
    away: str
    kickoff_utc: str | None
    game_date: str

    sport: str = SPORT
    line_asked: float | None = None
    market: str | None = None

    #: Scoring form for each side, strictly before this kickoff.
    home_form: dict = field(default_factory=dict)
    away_form: dict = field(default_factory=dict)
    home_rest: int | None = None
    away_rest: int | None = None
    #: Opponent-adjusted scoring margin, from games completed before kickoff.
    home_rating: float | None = None
    away_rating: float | None = None
    #: Great-circle miles between the two schools. None when either venue
    #: could not be placed -- absent, never zero.
    travel_miles: float | None = None
    #: Mean game-to-game swing in each side's combined score (totals market).
    home_swing: float | None = None
    away_swing: float | None = None
    #: Forecast wind at kickoff, outdoor venues only.
    wind_mph: float | None = None
    #: A game against a lower division is a different question, and saying so
    #: is more honest than letting a factor average it in silently.
    home_is_fbs: bool = True
    away_is_fbs: bool = True
    notes: list[str] = field(default_factory=list)


def build_context(conn: sqlite3.Connection, game_id: str,
                  *, market: str | None = None,
                  line_asked: float | None = None) -> CfbContext:
    game = repo.game(conn, game_id)
    if game is None:
        raise KeyError(f"unknown CFB game {game_id!r}")
    kickoff = game["kickoff_utc"]
    if not kickoff:
        raise KeyError(f"CFB game {game_id!r} has no kickoff time")

    rating = repo.ratings(conn, game["season"], before_utc=kickoff)
    return CfbContext(
        game_id=game_id,
        season=game["season"],
        day=game["week"],
        home=game["home"],
        away=game["away"],
        kickoff_utc=kickoff,
        game_date=(game["league_date"] or kickoff[:10]),
        market=market,
        line_asked=line_asked,
        home_form=repo.scoring_form(conn, game["home"], before_utc=kickoff),
        away_form=repo.scoring_form(conn, game["away"], before_utc=kickoff),
        home_rest=repo.days_rest(conn, game["home"], before_utc=kickoff),
        away_rest=repo.days_rest(conn, game["away"], before_utc=kickoff),
        home_is_fbs=repo.is_fbs(conn, game["home"]),
        away_is_fbs=repo.is_fbs(conn, game["away"]),
        home_rating=rating.get(game["home"]),
        away_rating=rating.get(game["away"]),
        travel_miles=_travel(conn, game["home"], game["away"]),
        home_swing=repo.score_swing(conn, game["home"], before_utc=kickoff),
        away_swing=repo.score_swing(conn, game["away"], before_utc=kickoff),
        wind_mph=_wind(conn, game["home"], kickoff),
    )


def _travel(conn: sqlite3.Connection, home: str, away: str) -> float | None:
    """Miles the visitors travelled, or None when either venue is unplaced."""
    here, there = venues.site(conn, home), venues.site(conn, away)
    if here is None or there is None:
        return None
    return venues.miles_between(here, there)


def _wind(conn: sqlite3.Connection, home: str, kickoff: str) -> float | None:
    """Forecast wind at an OUTDOOR venue, or None.

    None covers three different situations on purpose, and all three are
    absences rather than calm: the venue is indoors, we do not know whether it
    is indoors, or no forecast exists for that kickoff. Returning 0 for any of
    them would put a real number about the wrong thing into the fit.
    """
    if venues.indoor(conn, home) is not False:
        return None
    site = venues.site(conn, home)
    if site is None:
        return None
    return weather.wind_at(conn, site[0], site[1], kickoff)


def slate_questions(conn: sqlite3.Connection, season: int, day: int,
                    *, include_props: bool = True) -> list[Question]:
    """Up to three questions per game: the spread, the moneyline, the total.

    `include_props` is accepted and ignored: CFB has no prop markets, and the
    adapter protocol is shared. Silently accepting it is better than a signature
    that differs from every other sport's for a market that does not exist.
    """
    out: list[Question] = []
    for game in repo.slate(conn, season, day):
        gid = game["id"]
        home, away = game["home"], game["away"]

        rung = questions.cfb_spread_rung(gid)
        out.append(Question(
            sport=SPORT, game_id=gid, market_type="spread", market="spread",
            subject=home, line_asked=rung,
            claim=f"{home} covers {rung:+.1f} against {away}",
            yes_label="cover", no_label="fail to cover",
        ))
        out.append(Question(
            sport=SPORT, game_id=gid, market_type="moneyline",
            market="moneyline", subject=home, line_asked=None,
            claim=f"{home} (home) beat {away}",
            yes_label="win", no_label="lose",
        ))

        # THE TOTAL, at a line we generate from our own stored scoring. Absent
        # when either side has no completed games yet -- the first weekend of a
        # season, or a team new to the record. Absent is recorded as absent; it
        # is never asked at a guessed number.
        ctx = build_context(conn, gid)
        asked = questions.cfb_total_asked(
            (ctx.home_form or {}).get("for_pg"),
            (ctx.away_form or {}).get("for_pg"),
        )
        if asked is not None:
            out.append(Question(
                sport=SPORT, game_id=gid, market_type="total", market="total",
                subject=f"{away} @ {home}", line_asked=asked,
                claim=f"{away} and {home} combine for more than {asked}",
                yes_label="over", no_label="under",
            ))
    return out


def build_features(conn: sqlite3.Connection, q: Question, cache=None):
    ctx = build_context(conn, q.game_id, market=q.market,
                        line_asked=q.line_asked)
    return compute.feature_vector(ctx, q.market_type, q.market), ctx


def next_slate(conn: sqlite3.Connection, season: int) -> int | None:
    return repo.next_slate(conn, season)


def resolve_outcome(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    """1 if the stated side happened. Void when the game gives no answer.

    THE VOID RULES ARE IN docs/CFB.md AND WERE WRITTEN BEFORE THE FIRST
    PREDICTION, per checklist item 7. In short: a game that was cancelled or
    abandoned has no result to grade, and a line that vanished before kickoff
    does NOT void anything -- the forecast stands and only the comparison is
    absent.
    """
    game = repo.game(conn, pred["game_id"])
    if game is None:
        raise Void(f"the game {pred['game_id']} is no longer in the record, so "
                   "this question cannot be answered either way")
    if game["status"] in ("canceled", "postponed"):
        raise Void(f"the game was {game['status']} and never produced a result; "
                   "scoring it would credit the model for a schedule change it "
                   "never forecast")
    if game["status"] != "final" or game["home_score"] is None:
        raise Void("the game has no final score, so there is nothing to grade")

    home, away = int(game["home_score"]), int(game["away_score"])
    market = pred["market_type"]

    if market == "moneyline":
        outcome = 1 if home > away else 0
    elif market == "spread":
        outcome = questions.spread_outcome(home, away, pred["line_asked"])
    elif market == "total":
        outcome = questions.total_outcome(home, away, pred["line_asked"])
    else:
        raise Void(f"CFB has no market called {market!r}")

    yes = {"moneyline": "win", "spread": "cover", "total": "over"}[market]
    return outcome if pred["model_side"] == yes else 1 - outcome


def training_set(conn: sqlite3.Connection, seasons, market: str, **kwargs):
    """(rows, labels, names) for one market, by the same rules as a forecast.

    Built in B4 with the factors B3 declares. Raising here rather than
    returning an empty set: a fit on nothing would report a converged model
    with no coefficients, which reads like a working model.
    """
    raise NotImplementedError(
        "CFB training sets arrive with the factors in B3/B4. An empty set here "
        "would fit a model with no coefficients and report success"
    )
