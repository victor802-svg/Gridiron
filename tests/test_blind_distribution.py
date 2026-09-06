"""The frozen distribution (AT_THE_LINE E3, 2026-09-06): every game question
carries the model's own margin or total expectation and its measured spread,
written inside the blind window and frozen with the row; absent, never
guessed, where there is no rating or no measured spread."""
from __future__ import annotations

import json
import types

from gridiron import audit, config, run
from gridiron.model import questions
from tests.test_predict import trained  # noqa: F401  (the fixture)


def test_a_game_question_carries_its_distribution_and_a_prop_or_llm_row_does_not(trained):
    result = run.run_week(trained, 2025, 7, include_props=False, use_llm=False)
    rows = trained.execute(
        "SELECT market_type, predictor, factors_json FROM predictions").fetchall()
    assert rows
    seen = set()
    for r in rows:
        payload = json.loads(r["factors_json"])
        dist = payload.get("margin_distribution")
        if r["predictor"] != "statistical" or r["market_type"] == "prop":
            assert dist is None
            continue
        assert dist is not None, f"a {r['market_type']} question carries no distribution"
        seen.add(r["market_type"])
        assert dist["family"] == "normal" and dist["written_blind"] is True
        assert dist["declared"] == questions.FORECAST_SPREAD_DECLARED
        if r["market_type"] == "total":
            assert dist["quantity"] == "total"
            assert dist["sd"] == questions.FORECAST_SPREAD[("nfl", "total")]
        else:
            assert dist["quantity"] == "home_margin"
            assert dist["sd"] == questions.FORECAST_SPREAD[("nfl", "spread")]
        assert isinstance(dist["mean"], float)
    # the fixture trains the spread alone, so the spread is the one game market
    # certain to be written; the others carry a distribution when they are
    assert "spread" in seen
    counts = result["distributions"]
    assert counts["written"] == sum(1 for r in rows if r["predictor"] == "statistical" and r["market_type"] != "prop")
    audit.check_prediction_closure()


def test_absent_never_guessed():
    ctx = types.SimpleNamespace(home_srs=3.0, away_srs=-1.0, expected_total=44.0)
    d = questions.blind_distribution("nfl", "home_margin", ctx)
    assert d["quantity"] == "home_margin"
    assert d["mean"] == round(questions.expected_margin("nfl", 3.0, -1.0), 3)
    assert questions.blind_distribution("nfl", "total", ctx)["mean"] == 44.0
    # no rating: no expectation
    assert questions.blind_distribution("nfl", "home_margin", types.SimpleNamespace()) is None
    # a college total has no measured spread; baseball's margins are counts
    assert questions.blind_distribution("cfb", "total", ctx) is None
    assert questions.blind_distribution("mlb", "home_margin", types.SimpleNamespace(home_srs=1.0, away_srs=0.0)) is None
    # a quantity that is not a game quantity
    assert questions.blind_distribution("nfl", "passing_yards", ctx) is None
    # college football reads its own rating field
    cfb = types.SimpleNamespace(home_rating=10.0, away_rating=-5.0)
    d = questions.blind_distribution("cfb", "home_margin", cfb)
    assert d and d["sd"] == questions.FORECAST_SPREAD[("cfb", "spread")]


def test_the_distribution_is_frozen_with_the_row():
    from gridiron import fingerprint
    assert "factors_json" in fingerprint.PROTECTED
