"""S2: baseball.

Three things are being tested here, and they are separable.

The first is arithmetic that has one right answer and is easy to get subtly
wrong: innings pitched are recorded base-3 (6.1 means six and a third), and a
moneyline is a price that has to be inverted correctly in both signs.

The second is the shape of a baseball question. A moneyline has no rungs, so
`line_asked` is NULL and the subject is always the home club — asking the
complement question would double-count every game.

The third, and the one that actually protects the record, is the unannounced
starter. A club names its pitcher anywhere from a week out to ninety minutes
before first pitch. When the name is missing the factor must be ABSENT from the
vector, never zero, and the absence must reach the card. A silently defaulted
starter is the exact failure D2 removed `Factor.default` to prevent, and it
would be invisible: the model would simply predict every unannounced game as if
both arms were league average.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import calibration, config, db, resolve
from gridiron.data import mlb_loader
from gridiron.factors import compute, context, registry
from gridiron.market import lines, sources
from gridiron.model import predict
from gridiron.sports import mlb as mlb_sport


# --- innings, which are base-3 ----------------------------------------------

@pytest.mark.parametrize(
    "recorded, real",
    [(6.0, 6.0), (6.1, 6 + 1 / 3), (6.2, 6 + 2 / 3), (0.1, 1 / 3), (7.2, 7 + 2 / 3)],
)
def test_innings_are_read_as_thirds_not_decimals(recorded, real):
    """6.1 innings is six and one THIRD, not six and one tenth. Read as a
    decimal it understates every start by a couple of percent, consistently and
    invisibly, and every rate derived from it inherits the error."""
    assert mlb_loader._innings(recorded) == pytest.approx(real)


def test_a_missing_innings_figure_stays_missing():
    assert mlb_loader._innings(None) is None


# --- the moneyline, which is a price ----------------------------------------

@pytest.mark.parametrize(
    "odds, prob",
    [(-110, 110 / 210), (+110, 100 / 210), (-200, 200 / 300), (+150, 100 / 250), (100, 0.5)],
)
def test_american_odds_invert_to_probability(odds, prob):
    assert lines.american_to_probability(odds) == pytest.approx(prob)


def test_devigging_a_pair_returns_two_probabilities_that_sum_to_one():
    home, away = lines.devig_pair(-150, +130)
    assert home + away == pytest.approx(1.0)
    assert home > away  # -150 is the favourite


def test_the_vig_is_removed_proportionally_and_that_is_an_assumption():
    """Proportional de-vigging assumes the book's margin is split evenly between
    the two sides. It is not the only method and it is not provably right; the
    raw pair is kept so a later reader can redo it another way."""
    raw_home = lines.american_to_probability(-150)
    raw_away = lines.american_to_probability(+130)
    assert raw_home + raw_away > 1.0  # the vig
    home, _ = lines.devig_pair(-150, +130)
    assert home == pytest.approx(raw_home / (raw_home + raw_away))


# --- the shape of the question ----------------------------------------------

def test_a_moneyline_question_asks_no_line(mlb_league):
    """The run line and the total joined the slate on 2026-09-02, so this
    filters to the market it is about rather than assuming there is one."""
    questions = list(mlb_sport.slate_questions(mlb_league, 2025, 20, include_props=False))
    moneylines = [q for q in questions if q.market_type == "moneyline"]
    assert moneylines
    for q in moneylines:
        assert q.line_asked is None, "a moneyline has no rungs to choose between"


def test_the_run_line_is_always_asked_at_the_same_rung(mlb_league):
    """The market's rung is fixed at +/-1.5, so ours is too -- declared, not
    fetched. Asked from the HOME side every game: letting the market pick the
    side would be the market choosing our question."""
    questions = list(mlb_sport.slate_questions(mlb_league, 2025, 20, include_props=False))
    run_lines = [q for q in questions if q.market_type == "spread"]
    assert run_lines
    for q in run_lines:
        assert q.line_asked == -1.5
        assert q.yes_label == "cover" and q.no_label == "not_cover"


def test_a_total_is_asked_at_our_own_number_or_not_at_all(mlb_league):
    """Self-generated from the two sides' form, always on a half so it cannot
    push, and absent when either side has no form yet."""
    questions = list(mlb_sport.slate_questions(mlb_league, 2025, 20, include_props=False))
    totals = [q for q in questions if q.market_type == "total"]
    for q in totals:
        assert q.line_asked % 1 == 0.5, f"a total that can push: {q.line_asked}"
        assert q.yes_label == "over" and q.no_label == "under"


def test_one_question_per_game_and_the_subject_is_the_home_club(mlb_league):
    """Asking 'does the away team win' as well would be the exact complement of
    the home question, so the model would learn a mirror of itself and every
    game would be counted twice in the record."""
    questions = [q for q in mlb_sport.slate_questions(
        mlb_league, 2025, 20, include_props=False) if q.market_type == "moneyline"]
    games = [q.game_id for q in questions]
    assert len(games) == len(set(games))
    for q in questions:
        home = mlb_league.execute(
            "SELECT home FROM games WHERE id = ?", (q.game_id,)
        ).fetchone()["home"]
        assert q.subject == home


def test_mlb_declares_a_moneyline_and_four_player_props():
    """Baseball asked only a moneyline until 2026-08-30, when the four player
    prop markets were declared. The moneyline stays first: it is the game
    market, and the props are additions to the sport rather than replacements."""
    # The run line and the total joined on 2026-09-02, on the evidence in
    # docs/MLB_RUNLINE_FEASIBILITY.md. The moneyline stays first: it is the
    # game market, and the others are additions rather than replacements.
    # `batter_strikeouts` joined 2026-09-04 as MARKET_ROSTER #3, the
    # best-balanced prop the roster measured (61.7% over its first rung).
    assert config.SPORT_MARKETS["mlb"] == (
        "moneyline", "spread", "total",
        "batter_hits", "batter_total_bases", "batter_home_runs",
        "batter_strikeouts", "pitcher_strikeouts",
    )
    # THE ORDER IS THE ROUND-ROBIN ORDER. `select_day_props` fills the day's
    # cap by walking this tuple, so a market's position decides when it is
    # served once the cap bites.
    assert config.SPORT_PROP_MARKETS["mlb"] == (
        "batter_hits", "batter_total_bases", "batter_home_runs",
        "batter_strikeouts", "pitcher_strikeouts",
    )
    # Every prop market has a declared, dated ladder and nothing else does.
    assert set(config.MLB_PROP_LADDER) == set(config.SPORT_PROP_MARKETS["mlb"])
    assert config.MLB_PROP_LADDER_DECLARED


def test_every_prop_rung_ends_in_a_half_so_nothing_can_push():
    for market, rungs in config.MLB_PROP_LADDER.items():
        assert rungs, f"{market} has an empty ladder"
        for rung in rungs:
            assert rung % 1 == 0.5, f"{market} rung {rung} could push"


# --- the factors ------------------------------------------------------------

def test_every_mlb_factor_is_namespaced_and_carries_a_rationale():
    mlb_factors = [f for f in registry.all_factors() if f.sport == "mlb"]
    moneyline = [f for f in mlb_factors if f.applies_to == ("moneyline",)]
    props = [f for f in mlb_factors if f.applies_to == ("prop",)]
    run_line = [f for f in mlb_factors if f.applies_to == ("spread",)]
    totals = [f for f in mlb_factors if f.applies_to == ("total",)]
    assert len(moneyline) == 7
    assert sum(f.active for f in moneyline) == 6, (
        "mlb_home_away is deactivated as a constant; see its note"
    )
    assert len(props) == 13
    # DECLARED FOR THEIR OWN MARKETS on 2026-09-02, not widened from the
    # moneyline's: the same quantity can matter differently to two questions,
    # and sharing one declaration would date both from the earlier market.
    assert len(run_line) == 5
    assert len(totals) == 6
    assert all(f.added_utc.startswith("2026-09-02") for f in run_line + totals)
    assert len(mlb_factors) == len(moneyline) + len(props) + len(run_line) + len(totals)
    for f in mlb_factors:
        assert f.name.startswith("mlb_"), f"{f.name} would collide across sports"
        assert len(f.rationale) > 80, f"{f.name} has a token rationale"
        # ONE MARKET EACH, and that is the point: a factor declared for two
        # markets would date from the earlier one and mix two measured
        # effects into a single number.
        assert f.applies_to in (("moneyline",), ("prop",), ("spread",), ("total",))
        assert len(f.applies_to) == 1, f"{f.name} spans two markets"


def test_the_batter_and_pitcher_markets_get_disjoint_instruments():
    """A batter's platoon split is not a weak instrument for a strikeout prop,
    it is not an instrument at all. Without the market scoping, every batter
    factor would be absent in every row of the strikeout fit -- which is item
    2's constant-across-training failure arriving as missing data."""
    batter = {f.name for f in registry.active_factors("mlb", "prop", "batter_hits")}
    pitcher = {
        f.name for f in registry.active_factors("mlb", "prop", "pitcher_strikeouts")
    }
    shared = batter & pitcher
    assert shared == {
        "mlb_prop_mean_vs_line", "mlb_prop_volatility", "mlb_prop_park_factor",
    }, "only the question instruments and the park serve both subjects"
    assert "mlb_batter_platoon" in batter - pitcher
    assert "mlb_pitcher_k_rate" in pitcher - batter


def test_the_question_instruments_exist_in_every_prop_market():
    """New-market checklist, item 1. NBA shipped without these, the fit
    converged, and mean_vs_line turned out to be the largest coefficient in all
    four markets once it was added."""
    for market in config.SPORT_PROP_MARKETS["mlb"]:
        names = {f.name for f in registry.active_factors("mlb", "prop", market)}
        assert "mlb_prop_mean_vs_line" in names, market
        assert "mlb_prop_volatility" in names, market


def test_the_asked_line_factor_is_not_declared():
    """Declared deliberately absent, not forgotten. A moneyline has no rungs, so
    the factor could not vary, and an instrument that cannot vary is not an
    instrument. The reasoning is written out at the foot of factors/mlb.py."""
    names = {f.name for f in registry.all_factors() if f.sport == "mlb"}
    assert "mlb_asked_line" not in names


def test_the_constant_home_factor_is_deactivated_with_its_reason_recorded():
    """It could never vary: every MLB question asks whether the HOME club wins,
    so the factor returns 1.0 in one hundred percent of rows and is absorbed
    into the intercept. Deactivated as a broken instrument, not as a refuted
    idea, and the note has to say which."""
    f = next(x for x in registry.all_factors() if x.name == "mlb_home_away")
    assert f.active is False
    assert f.deactivated_utc
    assert "broken instrument" in f.note and "refuted idea" in f.note


def test_starter_rest_is_clipped_at_six_days_either_way():
    """A starter on sixteen days is a man returning from the injured list, not
    someone four times as rested as one on four days. The clip is a measurement
    choice made from how baseball works, not a fit to what scored well."""
    from gridiron.factors import mlb as mlb_factors

    class Ctx:
        home_starter_rest = 20
        away_starter_rest = 1

    assert mlb_factors.mlb_starter_rest_days(Ctx()) == 6.0
    Ctx.home_starter_rest, Ctx.away_starter_rest = 1, 20
    assert mlb_factors.mlb_starter_rest_days(Ctx()) == -6.0


# --- the unannounced starter, which is the case that matters ----------------

def test_an_unannounced_starter_leaves_the_factor_absent_not_zero():
    from gridiron.factors import mlb as mlb_factors

    class Ctx:
        home_starter_ra9 = None
        away_starter_ra9 = 4.1
        home_starter_rest = None
        away_starter_rest = 5

    assert mlb_factors.mlb_starter_rolling_perf(Ctx()) is None
    assert mlb_factors.mlb_starter_rest_days(Ctx()) is None


def test_a_vector_missing_a_starter_records_it_as_absent(mlb_league):
    questions = list(mlb_sport.slate_questions(mlb_league, 2025, 20, include_props=False))
    fv, _ = mlb_sport.build_features(mlb_league, questions[0], context.WeekCache())
    payload = fv.to_json_dict()
    assert "absent" in payload
    # Whatever is absent must be absent by NAME, and must not appear among the
    # values with a stand-in number.
    for name in payload["absent"]:
        assert name not in payload["values"]


def test_a_defaulted_starter_is_caught_at_runtime(mlb_league):
    """The planted version of the failure. If a future edit reintroduced a
    fallback, this is what would fire."""
    questions = list(mlb_sport.slate_questions(mlb_league, 2025, 20, include_props=False))
    fv, _ = mlb_sport.build_features(mlb_league, questions[0], context.WeekCache())
    fv.absent.append("mlb_starter_rolling_perf")
    fv.values["mlb_starter_rolling_perf"] = 0.0
    with pytest.raises(compute.MissingDataDefaulted):
        compute.assert_missing_is_explicit(fv)


# --- resolution -------------------------------------------------------------

def test_the_schema_refuses_a_final_game_that_carries_no_score(mlb_league):
    """The void branch for a scoreless final exists in `resolve_outcome`, but it
    is unreachable through the database, and that is the stronger guard: the
    CHECK makes the state impossible rather than merely unresolvable. Both are
    kept — belt and braces, and the code branch still protects a row arriving
    from a future loader that bypasses this path."""
    game = mlb_league.execute(
        "SELECT id FROM games WHERE sport='mlb' LIMIT 1"
    ).fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        mlb_league.execute(
            "UPDATE games SET status='final', home_score=NULL, away_score=NULL"
            " WHERE id=?",
            (game,),
        )


def test_a_game_not_yet_played_is_unresolvable_not_void(mlb_league):
    """The distinction matters. Unresolvable means ask again later; void is
    terminal and removes the prediction from every curve forever. A game that
    simply has not started must never take the terminal branch."""
    game = mlb_league.execute(
        "SELECT id FROM games WHERE sport='mlb' AND status='scheduled' LIMIT 1"
    ).fetchone()["id"]
    with pytest.raises(resolve.Unresolvable):
        mlb_sport.resolve_outcome(mlb_league, _fake_prediction(mlb_league, game))


def test_a_tie_voids_because_the_question_has_no_answer(mlb_league):
    """Baseball does not tie, but a suspended game can be recorded as one, and a
    moneyline asks a question that a tie does not answer."""
    game = mlb_league.execute(
        "SELECT id FROM games WHERE sport='mlb' LIMIT 1"
    ).fetchone()["id"]
    mlb_league.execute(
        "UPDATE games SET status='final', home_score=3, away_score=3 WHERE id=?", (game,)
    )
    with pytest.raises(resolve.Void):
        mlb_sport.resolve_outcome(
            mlb_league, _fake_prediction(mlb_league, game)
        )


def _fake_prediction(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row:
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " model_prob, model_side, predictor, factor_set_version, factors_json, reasoning)"
        " VALUES (?, 'mlb', ?, 'moneyline', (SELECT home FROM games WHERE id=?),"
        " 0.55, 'win', 'statistical', ?, '{}', 'x')",
        (db.utcnow(), game_id, game_id, config.FACTOR_SET_VERSION),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM predictions WHERE game_id = ? ORDER BY id DESC LIMIT 1", (game_id,)
    ).fetchone()


# --- the line source, stated honestly ---------------------------------------

def test_the_mlb_moneyline_has_a_named_source_with_its_licence_stated():
    source = sources.for_market("mlb", "moneyline")
    assert source["available"] is True
    assert "espn" in source["name"].lower()
    assert source["licence"], "a source with no licence field is a source nobody can check"
    assert "none" in source["licence"].lower() or "stated" in source["licence"].lower()


def test_a_market_with_no_source_says_so_rather_than_reporting_a_number():
    """Both halves of an availability claim must be backed.

    This test used to assert that EVERY prop market reports no source. That was
    true when it was written and became false on 2026-08-30, when ESPN was found
    to publish MLB player props in quantity -- 1,084 athlete rows on one slate.
    The old assertion was a measurement promoted to a law, and the measurement
    was one look at one sport generalised to three.

    What matters, and stays true as sources come and go: a market claiming a
    line must have a fetch path behind it, and one claiming none must say why.
    """
    from gridiron.market import props as prop_lines

    wired = set(prop_lines.TOTAL_MARKETS.values()) | set(
        prop_lines.MILESTONE_MARKETS.values()
    )
    for sport, markets in config.SPORT_PROP_MARKETS.items():
        for market in markets:
            source = sources.for_market(sport, market)
            if source["available"]:
                assert market in wired, (
                    f"{sport}/{market} claims a line with no fetch path behind it"
                )
            else:
                assert source["reason"], f"{sport}/{market} degrades silently"


# --- blind first, for baseball too ------------------------------------------

def test_the_mlb_prediction_closure_cannot_reach_the_market(conn):
    from gridiron import audit

    report = audit.check_all_prediction_closures()["mlb"]
    reached = [m for m in report.modules if m.startswith("gridiron.market")]
    assert reached == [], report.path_to(reached[0]) if reached else None
    assert len(report.modules) > 1, "a closure of one module is not a closure"


def test_a_prediction_written_after_first_pitch_is_not_written_live(mlb_league):
    """BLIND FIRST implies BEFORE. A live database may not contain a forecast of
    a game already under way; a backtest database may, because retrospection is
    its entire purpose and it is marked as such."""
    db.set_meta(mlb_league, "kind", "live")
    mlb_league.execute(
        "UPDATE games SET kickoff_utc = '2000-01-01T00:00:00Z' WHERE sport='mlb' AND week=20"
    )
    mlb_league.commit()
    run = predict.predict_slate(
        mlb_league, "mlb", 2025, 20, include_props=False, use_llm=False
    )
    assert run.written == []
    assert any("already under way" in s for s in run.skipped)


# --- LAW 6, from baseball's side --------------------------------------------

def test_a_baseball_figure_never_carries_a_football_prediction(mlb_league):
    payload = calibration.scorecard(mlb_league, sport="mlb")
    calibration.assert_single_sport(payload, "mlb")


def test_asking_for_every_sport_at_once_fires_the_tripwire(mlb_league):
    with pytest.raises(calibration.CrossSportAggregation):
        calibration.curve(mlb_league, sport="all")
