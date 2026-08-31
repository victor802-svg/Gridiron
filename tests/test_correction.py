"""The calibration correction: what it must do, and what it must never see.

A correction is fitted ON OUTCOMES. That is the only way to learn what a claim
has been worth, and it is also one short step from a second model fitted on the
result wearing a calibration label. Most of these tests are about the step.
"""

from __future__ import annotations

import random
import sqlite3

import pytest

from gridiron import correction as C
from gridiron import config, db


# --- the fit does what the method says --------------------------------------

def test_an_overconfident_forecaster_gets_a_slope_below_one():
    """The shape miscalibration actually takes, recovered from data.

    A forecaster whose claims are worth 60% of what it says should be pulled
    toward the middle -- that is `slope < 1` -- and its corrected claims should
    score better on the very rows it was fitted on.
    """
    rng = random.Random(7)
    rows = []
    for _ in range(3000):
        claim = rng.uniform(0.55, 0.95)
        worth = 0.5 + (claim - 0.5) * 0.6
        rows.append((claim, 1 if rng.random() < worth else 0, "2026-01-01T00:00:00Z"))

    model = C.fit_platt(rows)
    assert model is not None
    assert model.slope < 1.0, f"expected shrinkage, got slope={model.slope}"
    assert model.apply(0.90) < 0.90
    assert model.brier_corrected < model.brier_raw


def test_a_shy_forecaster_gets_a_slope_above_one():
    """The other direction, which must not be assumed away.

    A model whose claims are worth MORE than it says is miscalibrated too, and
    a correction that could only shrink would be a hardcoded opinion about
    which way the error runs.
    """
    rng = random.Random(11)
    rows = []
    for _ in range(3000):
        claim = rng.uniform(0.55, 0.80)
        worth = min(0.5 + (claim - 0.5) * 1.8, 0.99)
        rows.append((claim, 1 if rng.random() < worth else 0, "2026-01-01T00:00:00Z"))

    model = C.fit_platt(rows)
    assert model is not None
    assert model.slope > 1.0, f"expected expansion, got slope={model.slope}"
    assert model.apply(0.70) > 0.70


def test_a_category_that_never_lost_is_refused():
    """Separable data has no correction, only an absence of counter-examples.

    Every outcome the same fits perfectly at any large slope. Returning a
    number there would put a confident-looking correction on the strength of
    having seen nothing go wrong yet.
    """
    rows = [(0.7, 1, "2026-01-01T00:00:00Z") for _ in range(80)]
    assert C.fit_platt(rows) is None


def test_a_claim_at_the_extreme_does_not_break_the_fit():
    """The boundary, tested AT the boundary (MENTOR 3).

    A stored probability of exactly 1.0 has infinite log-odds. The model does
    not produce them today; `EPS` is here so that one which someday does fails
    visibly rather than poisoning a slope with an infinity.
    """
    rows = [(1.0, 1, "2026-01-01T00:00:00Z"), (0.0, 0, "2026-01-01T00:00:00Z")]
    rows += [(0.6, 1, "2026-01-01T00:00:00Z"), (0.6, 0, "2026-01-01T00:00:00Z")] * 20
    model = C.fit_platt(rows)
    assert model is not None
    for value in (model.slope, model.intercept):
        assert value == value and abs(value) != float("inf")


# --- what the training set may contain --------------------------------------

def _a_game(conn) -> str:
    """A real game id from the fixture. `predictions.game_id` is a foreign key,
    and inventing one fails the constraint rather than the test's point."""
    row = conn.execute("SELECT id FROM games LIMIT 1").fetchone()
    assert row, "the fixture has no games"
    return row["id"]


#: `predictions` is unique on (game, market, subject, predictor, factor set),
#: which is the rule that stops one question being answered twice. These
#: helpers vary the subject so each write is a different question.
_NEXT = [0]


def _write(conn, *, sport="nfl", market="moneyline", predictor="statistical",
           prob=0.7, outcome=1, resolved="2026-01-01T00:00:00Z", void=False):
    _NEXT[0] += 1
    cur = conn.execute(
        "INSERT INTO predictions (sport, created_utc, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sport, "2025-12-01T00:00:00Z", _a_game(conn), market,
         f"SUB{_NEXT[0]}", None, prob, "win",
         predictor, "fs2", "{}", "because", resolved, outcome),
    )
    if void:
        conn.execute(
            "INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
            " VALUES (?,?,?)",
            (cur.lastrowid, "2026-01-02T00:00:00Z", "no stat line exists for it"),
        )
    conn.commit()
    return cur.lastrowid


def test_the_training_set_excludes_the_unsettled_the_void_and_the_future(league):
    settled = _write(league, resolved="2026-01-01T00:00:00Z")
    _write(league, resolved=None, outcome=None)                 # still open
    _write(league, resolved="2026-01-01T00:00:00Z", void=True)  # terminal
    _write(league, resolved="2026-06-01T00:00:00Z")             # after the bound

    rows = C.training_rows(league, sport="nfl", market_type="moneyline",
                           forecaster="statistical",
                           before_utc="2026-02-01T00:00:00Z")
    assert len(rows) == 1, (
        "the fit saw an unsettled row, a void, or a row from its own future: "
        f"{rows}"
    )
    assert settled


def test_categories_are_never_merged():
    """LAW 6 inside the correction, not only outside it."""
    with pytest.raises(config.CrossSportAggregation):
        C.category_of("all", "moneyline", "statistical")
    with pytest.raises(ValueError):
        C.category_of("mlb", "", "statistical")
    with pytest.raises(ValueError):
        C.category_of("mlb", "moneyline", "")


def test_two_forecasters_in_one_category_do_not_share_a_correction(league):
    for _ in range(4):
        _write(league, predictor="statistical", prob=0.8, outcome=1)
        _write(league, predictor="llm", prob=0.8, outcome=0)
    stat = C.training_rows(league, sport="nfl", market_type="moneyline",
                           forecaster="statistical",
                           before_utc="2026-02-01T00:00:00Z")
    llm = C.training_rows(league, sport="nfl", market_type="moneyline",
                          forecaster="llm", before_utc="2026-02-01T00:00:00Z")
    assert {o for _p, o, _t in stat} == {1}
    assert {o for _p, o, _t in llm} == {0}


# --- the record of a fit is append-only -------------------------------------

def test_a_refit_writes_a_new_version_and_never_edits_one(league):
    model = C.Platt(slope=0.8, intercept=0.1, n_train=60,
                    brier_raw=0.24, brier_corrected=0.22)
    v1 = C.record_fit(league, sport="nfl", market_type="moneyline",
                      forecaster="statistical", model=model, status="fitted")
    v2 = C.record_fit(league, sport="nfl", market_type="moneyline",
                      forecaster="statistical", model=model, status="fitted")
    assert (v1, v2) == (1, 2)

    with pytest.raises(sqlite3.IntegrityError):
        league.execute("UPDATE calibration_corrections SET slope = 9.9")
    with pytest.raises(sqlite3.IntegrityError):
        league.execute("DELETE FROM calibration_corrections")


def test_a_fitted_correction_is_inert_until_it_is_activated(league):
    """Fitting is not activating, and the difference is the whole of C2.

    A fit that activated itself would mean the only way to look at a
    correction was to have it already applied to live claims.
    """
    model = C.Platt(slope=0.8, intercept=0.1, n_train=60)
    C.record_fit(league, sport="nfl", market_type="moneyline",
                 forecaster="statistical", model=model, status="fitted")
    assert C.active_correction(league, sport="nfl", market_type="moneyline",
                               forecaster="statistical") is None


def test_a_category_under_the_gate_is_recorded_with_its_shortfall_in_words(league):
    for _ in range(3):
        _write(league, prob=0.7, outcome=1)
        _write(league, prob=0.6, outcome=0)
    report = C.refit_all(league, now="2026-02-01T00:00:00Z")
    assert report["eligible"] == 0
    status = report["categories"][0]["status"]
    assert str(C.MIN_TRAIN) in status and "6 so far" in status, status
