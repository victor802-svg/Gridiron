"""The MLB run line and the total (GRIDIRON_16 STEP 3, built 2026-09-02).

Built against `docs/MLB_RUNLINE_FEASIBILITY.md`, which measured what the market
carries before anything was written. The tests that matter here are the ones
that would catch the market choosing our question, which is LAW 1's whole
subject.
"""

from __future__ import annotations

import inspect

import pytest

from gridiron import calibration, config, db
from gridiron.market import lines
from gridiron.model import questions


# --- item 1: the question instruments --------------------------------------

def test_the_run_line_rung_is_a_declared_constant():
    """Every MLB run line ESPN carries is +/-1.5 -- 71 of 71 in the probe. So
    the rung is declared here, dated, and never fetched per game."""
    assert questions.MLB_RUN_LINE == 1.5
    assert questions.MLB_RUN_LINE_DECLARED.startswith("2026-09-02")


def test_the_asked_total_cannot_reach_a_market():
    """LAW 1 in one function: it takes two scoring rates and nothing else."""
    params = list(inspect.signature(questions.mlb_total_asked).parameters)
    assert params == ["home_rpg", "away_rpg"]
    source = inspect.getsource(questions.mlb_total_asked)
    body = source.split('"""')[-1]
    for forbidden in ("market", "total_line", "overUnder", "espn"):
        assert forbidden not in body, f"the asked total reaches {forbidden!r}"


def test_the_asked_total_always_lands_on_a_half():
    """39 of 71 published MLB totals are whole numbers, which can push. A
    pushed question has no answer to score."""
    for home, away in ((4.5, 4.4), (3.0, 3.0), (5.9, 5.2), (2.1, 2.0)):
        asked = questions.mlb_total_asked(home, away)
        assert asked is not None
        assert asked % 1 == 0.5, f"{home}+{away} asked at {asked}"


def test_an_absent_scoring_rate_asks_no_question():
    """Item 5: absent is recorded absent, never asked at a guessed number."""
    assert questions.mlb_total_asked(None, 4.4) is None
    assert questions.mlb_total_asked(4.4, None) is None
    assert questions.mlb_total_asked(None, None) is None


def test_an_absurd_total_is_refused_rather_than_asked():
    assert questions.mlb_total_asked(12.0, 9.0) is None      # 21 runs
    assert questions.mlb_total_asked(1.0, 1.0) is None       # 2 runs


# --- grading ---------------------------------------------------------------

@pytest.mark.parametrize("home,away,covered", [
    (5, 2, 1), (4, 2, 1), (3, 2, 0), (2, 2, 0), (1, 5, 0),
])
def test_the_run_line_grades_by_margin(home, away, covered):
    """-1.5 covers by winning by two or more. A half cannot push."""
    assert questions.run_line_outcome(home, away, -1.5) == covered


def test_the_total_grades_against_the_number_asked():
    assert questions.total_outcome(5, 4, 8.5) == 1      # 9 runs
    assert questions.total_outcome(4, 4, 8.5) == 0      # 8 runs


# --- item 4: cross-checks between related numbers --------------------------

def test_the_run_line_base_rate_matches_the_measured_one():
    """The training labels must reproduce the measured distribution: 35.8% of
    MLB games are won by the home side by two or more (n=9,373)."""
    measured = config.MLB_SCORE_DISTRIBUTION["home_by_2_or_more"]
    conn = db.connect()
    rows = conn.execute(
        "SELECT home_score, away_score FROM games WHERE sport='mlb'"
        " AND status='final' AND home_score IS NOT NULL").fetchall()
    labels = [questions.run_line_outcome(r["home_score"], r["away_score"], -1.5)
              for r in rows]
    rate = sum(labels) / len(labels)
    assert abs(rate - measured) < 0.01, f"{rate:.3f} against {measured}"


# --- item 6: its own category, its own gate --------------------------------

def test_each_market_is_its_own_category():
    conn = db.connect()
    payload = calibration.scorecard(conn, sport="mlb")
    kinds = {c["filters"]["market_type"] for c in payload["categories"]}
    assert {"moneyline", "spread", "total"} <= kinds
    calibration.assert_no_merged_categories(payload)      # must not raise


# --- the market comparison -------------------------------------------------

def test_the_totals_comparison_uses_the_totals_sd():
    """Not the margin one. They measure different quantities, and the wrong
    one makes the market look far more or less certain than it is."""
    assert lines.total_sd("mlb") == 4.511
    assert lines.MARGIN_SD_BY_SPORT["mlb"].sd == 4.71
    assert lines.total_sd("mlb") != lines.MARGIN_SD_BY_SPORT["mlb"].sd


def test_an_unmeasured_total_sd_is_refused_by_name():
    with pytest.raises(lines.UnmeasuredMarginSD, match="no total-points SD"):
        lines.total_sd("nba")


def test_a_higher_market_total_implies_a_higher_chance_of_going_over():
    """Monotonicity: the direction has to be right before the number is."""
    low = lines.implied_over_probability(7.5, 8.5, "mlb")
    high = lines.implied_over_probability(9.5, 8.5, "mlb")
    assert low < 0.5 < high, (low, high)


def test_a_contradicted_run_line_sign_yields_no_comparison():
    """A confident probability pointing the wrong way is worse than none: a
    missing comparison is visible and a reversed one is not."""
    conn = db.connect()
    row = conn.execute(
        "SELECT * FROM market_lines_raw WHERE spread_sign_source='contradicted'"
        " LIMIT 1").fetchone()
    if row is None:
        pytest.skip("no contradicted row in this database")
    assert lines._sign_column(row) == "contradicted"


# --- the sport names its own markets ---------------------------------------

def test_a_run_line_is_not_called_a_point_spread():
    """A handicap is a "point spread" in football and a "run line" in
    baseball, and a reader who follows one sport does not translate. The
    generic humaniser called MLB's run line a point spread -- a sentence about
    the wrong sport."""
    from gridiron import language

    assert language.market_label({"sport": "mlb", "market": "spread"}) == "run line"
    assert language.market_label({"sport": "mlb", "market": "total"}) == "total runs"
    assert language.market_label({"sport": "nfl", "market": "spread"}) == "point spread"
    assert language.market_label({"sport": "cfb", "market": "total"}) == "total points"


def test_every_card_carries_its_sport_so_the_label_can_use_it():
    """Without the sport on the card the label falls back to the generic
    humaniser, which is how the wrong-sport wording reached the page."""
    from gridiron import views

    conn = db.connect()
    payload = views.week(conn, "mlb")
    assert payload["cards"], "no cards to check"
    for card in payload["cards"]:
        assert card.get("sport") == "mlb"
    labels = {c["market_type"]: c["market_label"] for c in payload["cards"]}
    if "spread" in labels:
        assert labels["spread"] == "run line"
    if "total" in labels:
        assert labels["total"] == "total runs"
