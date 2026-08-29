"""G4: resolution is idempotent, and no figure renders without its N."""

from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import calibration, config, db, resolve, run
from gridiron.factors import store
from gridiron.model import baseline


@pytest.fixture
def settled(league):
    """A trained league with week 7 predicted and resolved."""
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    run.run_week(league, 2025, 7, include_props=True, use_llm=False)
    resolve.resolve_all(league)
    return league


# --- resolution ------------------------------------------------------------

def test_resolution_settles_open_predictions(settled):
    summary = resolve.summary(settled)
    assert summary["predictions"] > 0
    assert summary["open"] == 0
    assert summary["resolved"] == summary["predictions"]


def test_resolution_is_idempotent(settled):
    """Resolve twice; assert one outcome, unchanged."""
    before = settled.execute(
        "SELECT id, resolved_utc, outcome FROM predictions ORDER BY id"
    ).fetchall()
    second = resolve.resolve_all(settled)
    third = resolve.resolve_all(settled)

    assert second["settled"] == 0, "a second pass must settle nothing"
    assert third["settled"] == 0
    after = settled.execute(
        "SELECT id, resolved_utc, outcome FROM predictions ORDER BY id"
    ).fetchall()
    assert [tuple(r) for r in before] == [tuple(r) for r in after], (
        "a second resolution changed an outcome"
    )


def test_a_half_finished_resolution_completes_rather_than_repeats(league):
    """Simulate a crash: settle half, then run again. The first half keeps its
    outcomes and only the rest are settled."""
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0)
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)

    open_rows = resolve.open_predictions(league)
    assert len(open_rows) == 4
    half = open_rows[:2]
    for pred in half:
        league.execute(
            "UPDATE predictions SET resolved_utc = ?, outcome = ?"
            " WHERE id = ? AND resolved_utc IS NULL",
            (db.utcnow(), resolve.outcome_for(league, pred), pred["id"]),
        )
    league.commit()
    frozen = league.execute(
        "SELECT id, outcome FROM predictions WHERE resolved_utc IS NOT NULL ORDER BY id"
    ).fetchall()

    result = resolve.resolve_all(league)
    assert result["settled"] == 2, "only the unsettled half should settle"
    for row in frozen:
        now = league.execute(
            "SELECT outcome FROM predictions WHERE id = ?", (row["id"],)
        ).fetchone()
        assert now["outcome"] == row["outcome"]


def test_resolution_never_touches_a_probability(settled):
    for r in settled.execute("SELECT model_prob, outcome FROM predictions"):
        assert 0.5 <= r["model_prob"] < 1.0
        assert r["outcome"] in (0, 1)
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        settled.execute("UPDATE predictions SET model_prob = 0.5 WHERE id = 1")


def test_an_unplayed_game_is_left_open(league):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0)
    run.run_week(league, 2025, 18, include_props=False, use_llm=False)  # scheduled
    result = resolve.resolve_all(league)
    assert result["settled"] == 0
    assert result["still_open"] == 4


def test_a_prop_for_a_player_who_did_not_appear_resolves_against_the_claim(settled):
    """The claim was that he would exceed a number. He recorded nothing."""
    game_id = settled.execute(
        "SELECT id FROM games WHERE week = 7 LIMIT 1"
    ).fetchone()["id"]
    pred = settled.execute(
        "INSERT INTO predictions (created_utc, game_id, market_type, subject, line_asked,"
        " model_prob, model_side, predictor, factor_set_version, factors_json, reasoning)"
        " VALUES (?,?,'prop','Ghost Player passing_yards',180.5,0.72,'over','statistical',"
        " 'fs1',?,'test')",
        (
            db.utcnow(),
            game_id,
            json.dumps({"question": {"player_id": "QB-NOBODY", "stat": "passing_yards",
                                     "yes_label": "over", "no_label": "under"}}),
        ),
    ).lastrowid
    settled.commit()
    resolve.resolve_all(settled)
    row = settled.execute(
        "SELECT outcome FROM predictions WHERE id = ?", (pred,)
    ).fetchone()
    assert row["outcome"] == 0


# --- LAW 4: no sample, no claim --------------------------------------------

def test_every_bucket_carries_its_n_even_when_empty(settled):
    c = calibration.curve(settled, market_type="spread", predictor="statistical")
    assert len(c["buckets"]) == len(calibration.BUCKETS)
    for b in c["buckets"]:
        assert "n" in b and isinstance(b["n"], int)


def test_the_validator_catches_a_claim_without_its_sample_size():
    payload = {"score": {"brier": 0.21, "log_loss": 0.61}}   # n removed
    with pytest.raises(calibration.MissingSampleSize, match="LAW 4"):
        calibration.assert_every_figure_has_n(payload)


def test_the_validator_reports_where_the_n_is_missing():
    payload = {"categories": [{"score": {"n": 3, "brier": 0.2}},
                              {"score": {"brier": 0.2}}]}
    with pytest.raises(calibration.MissingSampleSize) as exc:
        calibration.assert_every_figure_has_n(payload)
    assert "categories[1].score" in str(exc.value)


def test_a_full_scorecard_passes_its_own_validator(settled):
    payload = calibration.scorecard(settled)
    calibration.assert_every_figure_has_n(payload)      # must not raise
    assert payload["headline"]["n"] >= 0


def test_no_edge_is_claimed_below_the_threshold(settled):
    e = calibration.edge(settled, market_type="spread", predictor="statistical")
    assert e["minimum_for_a_claim"] == config.MIN_SAMPLE_FOR_EDGE_CLAIM
    assert e["renderable"] is False
    assert "model_more_confident" not in e, "a figure leaked below the threshold"
    assert e["shortfall"] == config.MIN_SAMPLE_FOR_EDGE_CLAIM - e["n_disagreements"]
    assert "more before this figure will be shown" in e["message"]


def test_the_edge_note_stands_whether_or_not_it_renders(settled):
    e = calibration.edge(settled)
    assert "luck" in e["standing_note"]


def test_the_edge_shows_both_directions_once_it_renders(settled, monkeypatch):
    monkeypatch.setattr(config, "MIN_SAMPLE_FOR_EDGE_CLAIM", 1)
    e = calibration.edge(settled, market_type="spread", predictor="statistical")
    if e["renderable"]:
        assert "model_more_confident" in e
        assert "market_more_confident" in e, (
            "showing only the flattering half of the comparison is how a record lies"
        )


# --- the curve reports the worst thing it knows ----------------------------

def test_the_headline_sentence_names_the_largest_gap_not_the_best_bucket():
    buckets = [
        {"label": "50-60%", "n": 500, "claimed": 0.55, "actual": 0.55, "gap": 0.0},
        {"label": "60-70%", "n": 400, "claimed": 0.65, "actual": 0.50, "gap": -0.15},
        {"label": "70-80%", "n": 300, "claimed": 0.75, "actual": 0.76, "gap": 0.01},
        {"label": "80%+", "n": 0, "claimed": None, "actual": None, "gap": None},
    ]
    sentence = calibration.largest_gap_sentence(buckets)
    assert "60-70%" in sentence
    assert "overconfident" in sentence
    assert "400" in sentence


def test_the_sentence_says_so_when_there_is_nothing_to_say():
    empty = [{"label": b[2], "n": 0, "claimed": None, "actual": None, "gap": None}
             for b in calibration.BUCKETS]
    assert "Nothing has resolved yet" in calibration.largest_gap_sentence(empty)


def test_a_thin_bucket_does_not_get_to_be_the_headline():
    buckets = [
        {"label": "50-60%", "n": 500, "claimed": 0.55, "actual": 0.52, "gap": -0.03},
        {"label": "80%+", "n": 2, "claimed": 0.85, "actual": 0.0, "gap": -0.85},
    ]
    sentence = calibration.largest_gap_sentence(buckets, minimum_n=20)
    assert "50-60%" in sentence, "a two-sample bucket must not drive the headline"


# --- categories stay separate ----------------------------------------------

def test_categories_are_never_merged(settled):
    payload = calibration.scorecard(settled)
    labels = {c["category"] for c in payload["categories"]}
    assert labels == {
        "spread / statistical",
        "spread / llm",
        "prop / statistical",
        "prop / llm",
    }
    for c in payload["categories"]:
        assert c["filters"]["market_type"] in ("spread", "prop")
        assert c["filters"]["predictor"] in ("statistical", "llm")


def test_the_market_baseline_is_scored_on_the_same_questions(settled):
    c = calibration.curve(settled, market_type="spread", predictor="statistical")
    market = c["baselines"]["market"]
    if market["n"]:
        same = c["baselines"]["model_on_market_subset"]
        assert same["n"] == market["n"], (
            "the model and market must be compared over one shared question set"
        )


def test_the_always_fifty_baseline_is_stated(settled):
    c = calibration.curve(settled, market_type="spread")
    assert c["baselines"]["always_50"]["brier"] == pytest.approx(0.25)


# --- factor scoring --------------------------------------------------------

def test_factors_are_scored_only_from_their_activation_date(settled, monkeypatch):
    from gridiron.factors import registry

    original = registry.REGISTRY["srs_diff"]
    monkeypatch.setitem(
        registry.REGISTRY,
        "srs_diff",
        registry.Factor(
            name="srs_diff",
            added_utc="2999-01-01T00:00:00Z",       # activated in the future
            rationale=original.rationale,
            applies_to=original.applies_to,
            fn=original.fn,
        ),
    )
    report = calibration.factor_report(settled)
    entry = next(f for f in report["factors"] if f["factor"] == "srs_diff")
    assert entry["n"] == 0, "a factor cannot be scored on predictions older than itself"


def test_the_factor_report_separates_the_kinds_of_nothing(settled):
    report = calibration.factor_report(settled)
    verdicts = {f["factor"]: f["verdict"] for f in report["factors"]}
    assert verdicts["public_bet_pct"] == "inactive; never used in a prediction"
    for f in report["factors"]:
        assert "n" in f
    assert "attribution within the fitted model" in report["method"]


def test_a_factor_whose_input_never_varies_is_untested_not_disproved(settled):
    """`short_week_diff` is zero in almost every real game because the schedule
    puts both clubs on a short week together. That is a fact about the NFL
    calendar, and the verdict must not read as a verdict on the idea."""
    report = calibration.factor_report(settled)
    entry = next(f for f in report["factors"] if f["factor"] == "short_week_diff")
    if entry["n"]:
        assert entry["nonzero_share"] == 0.0
        assert "untested rather than disproved" in entry["verdict"]
