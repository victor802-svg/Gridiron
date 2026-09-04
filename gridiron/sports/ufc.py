"""UFC: the sport adapter.

THE TWO SIDES ARE NOT HOME AND AWAY. `games` stores them in columns called
`home` and `away` because that is the shape every other sport needs and ESPN
itself labels a bout's corners that way. **Nothing in the interface may say
home or away about a fight** -- a card reads "A vs B", and the pick sentences
go through `side_named` like every other sport's.

THE SLATE KEY IS THE DATE, as YYYYMMDD, the same shape college football uses.
UFC has no season structure at all: about 4.3 cards a month, no weeks, no
conferences, no playoffs. A card is a slate and its date is its name.

THREE MARKETS, IN THE OPERATOR'S ORDER: moneyline, rounds, distance. No
method-of-victory -- it was excluded by the brief and is not smuggled in.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from .. import config
from ..db import utcnow
from ..model import questions
from ..model.question import Question

SPORT = "ufc"
SLATE_WORD = "card"


def markets() -> tuple[str, ...]:
    return config.SPORT_MARKETS[SPORT]


# ---------------------------------------------------------------------------
# the bouts become games, so a prediction can reference one
# ---------------------------------------------------------------------------

def mirror_bouts(conn: sqlite3.Connection) -> int:
    """Copy `ufc_bouts` into `games`, which is what predictions reference.

    WHY A MIRROR RATHER THAN ONE TABLE. `ufc_bouts` carries what only a fight
    has -- the method, the round it ended in, how many rounds it was scheduled
    for -- and `games` carries what every sport shares. Folding the two would
    put five sports' worth of optional columns on one table, and the sport
    CHECK already showed what that costs.

    THE MIRROR IS THE SOURCE OF TRUTH FOR NOTHING. Every fact here comes from
    `ufc_bouts`; a row is updated in place when a bout resolves, which is
    ordinary for `games` and forbidden for `predictions`.
    """
    rows = conn.execute(
        "SELECT b.id, b.bout_utc, b.status, b.winner, b.fighter_a, b.fighter_b,"
        "       fa.name AS name_a, fb.name AS name_b, e.season"
        "  FROM ufc_bouts b"
        "  JOIN ufc_events e ON e.id = b.event_id"
        "  LEFT JOIN ufc_fighters fa ON fa.id = b.fighter_a"
        "  LEFT JOIN ufc_fighters fb ON fb.id = b.fighter_b"
        " WHERE b.bout_utc IS NOT NULL").fetchall()

    written = 0
    for row in rows:
        # THE TWO SIDES ARE NAMED, not numbered. A card reading "4848646 vs
        # 5324401" is a database talking to itself.
        name_a = row["name_a"] or row["fighter_a"]
        name_b = row["name_b"] or row["fighter_b"]
        day = str(row["bout_utc"])[:10]
        week = int(day.replace("-", ""))
        # A DECIDED BOUT SCORES 1-0 AND A DRAW 0-0. `games` has only scores to
        # express an outcome with, and a fight has no score at all -- this is
        # the minimum that lets the shared resolver see who won without
        # inventing a margin. `ufc_bouts` remains the real record.
        if row["status"] == "final" and row["winner"]:
            score_a = 1 if row["winner"] == row["fighter_a"] else 0
            score_b = 1 - score_a
        elif row["status"] == "final":
            score_a = score_b = 0        # a draw or no contest
        else:
            score_a = score_b = None
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
            " league_date, home, away, status, home_score, away_score)"
            " VALUES (?,?,?,?,'REG',?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET status = excluded.status,"
            "   home_score = excluded.home_score,"
            "   away_score = excluded.away_score,"
            "   kickoff_utc = excluded.kickoff_utc",
            (row["id"], SPORT, row["season"], week, row["bout_utc"], day,
             name_a, name_b, row["status"], score_a, score_b))
        written += 1
    conn.commit()
    return written


# ---------------------------------------------------------------------------
# the context a factor reads
# ---------------------------------------------------------------------------

@dataclass
class UfcContext:
    """Everything the UFC factors may read about one bout. Absent stays absent."""

    game_id: str
    sport: str = SPORT
    market_type: str = "moneyline"
    line_asked: float | None = None
    #: Ratings each fighter carried INTO this bout, from `ufc_ratings`.
    rating_a: float | None = None
    rating_b: float | None = None
    bouts_a: int | None = None
    bouts_b: int | None = None
    #: Days since each fighter last fought. None when there is no prior bout.
    layoff_a: float | None = None
    layoff_b: float | None = None
    age_a: float | None = None
    age_b: float | None = None
    reach_a: float | None = None
    reach_b: float | None = None
    #: Share of a fighter's decided bouts that ended inside the distance.
    finish_rate_a: float | None = None
    finish_rate_b: float | None = None
    scheduled_rounds: int | None = None
    #: The model's own expected length, in rounds. Set for the rounds market.
    expected_rounds: float | None = None
    notes: list = field(default_factory=list)


def build_context(conn: sqlite3.Connection, game_id: str,
                  line_asked=None, market_type: str = "moneyline") -> UfcContext:
    """Read what is knowable about a bout BEFORE it happens.

    EVERY WINDOW CUTS STRICTLY BEFORE THIS BOUT. A rolling figure that let the
    bout into its own window is the leak this project has already paid for
    once, on 76.8% of NBA rows.
    """
    bout = conn.execute(
        "SELECT b.*, e.season FROM ufc_bouts b JOIN ufc_events e"
        "  ON e.id = b.event_id WHERE b.id = ?", (game_id,)).fetchone()
    if bout is None:
        raise KeyError(f"no UFC bout {game_id!r}")

    ctx = UfcContext(game_id=game_id, line_asked=line_asked,
                     market_type=market_type,
                     scheduled_rounds=bout["scheduled_rounds"])

    ratings = {r["fighter_id"]: r for r in conn.execute(
        "SELECT fighter_id, rating_before, bouts_before FROM ufc_ratings"
        " WHERE bout_id = ?", (game_id,))}
    for side, ident in (("a", bout["fighter_a"]), ("b", bout["fighter_b"])):
        row = ratings.get(ident)
        if row is not None:
            setattr(ctx, f"rating_{side}", row["rating_before"])
            setattr(ctx, f"bouts_{side}", row["bouts_before"])
        _fill_fighter(conn, ctx, side, ident, bout["bout_utc"])
    return ctx


def _fill_fighter(conn, ctx, side, ident, when) -> None:
    who = conn.execute(
        "SELECT reach, born FROM ufc_fighters WHERE id = ?", (ident,)).fetchone()
    if who is not None:
        setattr(ctx, f"reach_{side}", who["reach"])
        if who["born"] and when:
            years = _years_between(who["born"], when)
            setattr(ctx, f"age_{side}", years)

    prior = conn.execute(
        "SELECT bout_utc, winner, method, end_round, scheduled_rounds"
        "  FROM ufc_bouts"
        " WHERE (fighter_a = ? OR fighter_b = ?) AND status = 'final'"
        "   AND bout_utc IS NOT NULL AND bout_utc < ?"
        " ORDER BY bout_utc DESC", (ident, ident, when)).fetchall()
    if not prior:
        # ABSENT, NOT ZERO. A debutant has no layoff and no finish rate; a
        # zero would read as "fought yesterday" and "never finishes anyone".
        return
    setattr(ctx, f"layoff_{side}", _days_between(prior[0]["bout_utc"], when))
    decided = [p for p in prior if p["winner"]]
    if decided:
        inside = sum(1 for p in decided
                     if p["end_round"] and p["scheduled_rounds"]
                     and p["end_round"] < p["scheduled_rounds"])
        setattr(ctx, f"finish_rate_{side}", inside / len(decided))


def _years_between(born: str, when: str) -> float | None:
    days = _days_between(born, when)
    return None if days is None else days / 365.25


def _days_between(earlier: str, later: str) -> float | None:
    from datetime import datetime

    try:
        a = datetime.fromisoformat(str(earlier).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(later).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return (b - a).total_seconds() / 86400.0


# ---------------------------------------------------------------------------
# the slate
# ---------------------------------------------------------------------------

def next_slate(conn: sqlite3.Connection, season: int) -> int | None:
    """The next card that has not started, as YYYYMMDD."""
    row = conn.execute(
        "SELECT MIN(week) AS week FROM games"
        " WHERE sport = ? AND season = ? AND status = 'scheduled'"
        "   AND kickoff_utc > ?", (SPORT, season, utcnow())).fetchone()
    return row["week"] if row and row["week"] else None


def slate_questions(conn: sqlite3.Connection, season: int, week: int,
                    *, include_props: bool = True) -> list[Question]:
    """Three questions per bout: who wins, how long, and does it go the distance."""
    bouts = conn.execute(
        "SELECT g.id, g.home, g.away, b.scheduled_rounds"
        "  FROM games g JOIN ufc_bouts b ON b.id = g.id"
        " WHERE g.sport = ? AND g.season = ? AND g.week = ?"
        " ORDER BY b.match_number, g.id", (SPORT, season, week)).fetchall()

    out: list[Question] = []
    for bout in bouts:
        a, b = bout["home"], bout["away"]
        out.append(Question(
            sport=SPORT, game_id=bout["id"], market_type="moneyline",
            market="moneyline", subject=a, line_asked=None,
            claim=f"{a} beats {b}", yes_label="win", no_label="lose"))

        rounds = bout["scheduled_rounds"]
        rung = questions.ufc_rounds_rung(rounds)
        if rung is not None:
            out.append(Question(
                sport=SPORT, game_id=bout["id"], market_type="rounds",
                market="rounds", subject=f"{a} vs {b}", line_asked=rung,
                claim=f"{a} vs {b} lasts more than {rung:g} rounds",
                yes_label="over", no_label="under"))

        if rounds:
            out.append(Question(
                sport=SPORT, game_id=bout["id"], market_type="distance",
                market="distance", subject=f"{a} vs {b}", line_asked=None,
                claim=f"{a} vs {b} goes the distance",
                yes_label="yes", no_label="no"))
    return out


def build_features(conn: sqlite3.Connection, q: Question, cache=None):
    from ..factors import compute

    ctx = build_context(conn, q.game_id, line_asked=q.line_asked,
                        market_type=q.market_type)
    # THE VECTOR AND THE CONTEXT, which is the contract every other adapter
    # follows: the caller needs the context to explain the pick, not only the
    # numbers to score it.
    return compute.feature_vector(ctx, q.market_type), ctx


def resolve_outcome(conn: sqlite3.Connection, pred: sqlite3.Row) -> int:
    from ..resolve import resolve_ufc_outcome

    return resolve_ufc_outcome(conn, pred)


def training_set(conn: sqlite3.Connection, seasons, market: str, *,
                 through_season: int | None = None,
                 through_week: int | None = None, progress=None):
    from ..factors import compute, registry
    from ..model import baseline
    from ..resolve import ufc_market_outcome

    marks = ",".join("?" for _ in seasons)
    sql = ("SELECT b.id, b.scheduled_rounds, b.winner, b.method, b.end_round,"
           "       b.fighter_a, e.season, g.week"
           "  FROM ufc_bouts b JOIN ufc_events e ON e.id = b.event_id"
           "  JOIN games g ON g.id = b.id"
           f" WHERE b.status = 'final' AND e.season IN ({marks})"
           "   AND b.bout_utc IS NOT NULL")
    params = list(seasons)
    if through_season is not None:
        sql += " AND (e.season < ? OR (e.season = ? AND g.week <= ?))"
        params += [through_season, through_season, through_week or 99999999]
    bouts = conn.execute(sql + " ORDER BY b.bout_utc, b.id", params).fetchall()
    baseline.assert_one_sport(
        [{"sport": SPORT} for _ in bouts], SPORT, "ufc.training_set")

    rows: list[dict] = []
    labels: list[int] = []
    for i, bout in enumerate(bouts):
        if progress and i % 250 == 0:
            progress(f"ufc {market} features {i}/{len(bouts)}")
        rung = (questions.ufc_rounds_rung(bout["scheduled_rounds"])
                if market == "rounds" else None)
        if market == "rounds" and rung is None:
            continue
        try:
            ctx = build_context(conn, bout["id"], line_asked=rung,
                                market_type=market)
        except KeyError:
            continue
        outcome = ufc_market_outcome(bout, market, rung)
        if outcome is None:
            # VOID IS NOT A LABEL. A draw has no moneyline answer and a no
            # contest has none for any market; training on either would teach
            # the model an outcome that did not happen.
            continue
        rows.append(compute.feature_vector(ctx, market).values)
        labels.append(outcome)

    names = [f.name for f in registry.active_factors(SPORT, market)]
    return rows, labels, names
