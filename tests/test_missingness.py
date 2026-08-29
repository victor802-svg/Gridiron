"""D2: missing is an explicit state, and the repaired instruments.

The centrepiece is `test_exclusion_and_zero_imputation_give_the_same_fit`. It
exists to stop a future reader — or a future session — from believing the v2
exclusion changed the model's coefficients. It did not, and the honest claim is
narrower and still worth making: exclusion changes what the record says, what
gets scored, and what an explanation is allowed to assert.
"""

from __future__ import annotations

import json
import random

import pytest

from gridiron import calibration, config, db, run
from gridiron.factors import compute, context, registry, store
from gridiron.model import baseline, logistic


# --- the honest limit of the change ----------------------------------------

def test_exclusion_and_zero_imputation_give_the_same_fit():
    """For a LINEAR model these are arithmetically identical, and saying so is
    the difference between a repair and a story about a repair."""
    rng = random.Random(4)
    rows, labels = [], []
    for _ in range(2500):
        row = {"a": rng.gauss(0, 1)}
        z = 0.2 + 1.1 * row["a"]
        if rng.random() < 0.35:
            row["sparse"] = rng.random()          # non-zero mean, on purpose
            z += 0.9 * row["sparse"]
        rows.append(row)
        labels.append(1 if rng.random() < logistic.sigmoid(z) else 0)

    excluded = logistic.fit(rows, labels, ["a", "sparse"], l2=0.5)
    imputed = logistic.fit(
        [{**r, "sparse": r.get("sparse", 0.0)} for r in rows],
        labels, ["a", "sparse"], l2=0.5,
    )
    for name in ("a", "sparse"):
        assert excluded.as_dict()[name] == pytest.approx(
            imputed.as_dict()[name], abs=1e-4
        ), "the v2 change must not be sold as a change to the coefficients"
    assert excluded.intercept == pytest.approx(imputed.intercept, abs=1e-4)


def test_but_the_two_are_distinguishable_on_the_record():
    """...which is the whole point of making the change anyway."""
    rng = random.Random(4)
    rows, labels = [], []
    for _ in range(2500):
        row = {"a": rng.gauss(0, 1)}
        if rng.random() < 0.35:
            row["sparse"] = rng.random()
        rows.append(row)
        labels.append(rng.randint(0, 1))
    fit = logistic.fit(rows, labels, ["a", "sparse"], l2=0.5)

    measured_zero = {"a": 0.5, "sparse": 0.0}
    unmeasured = {"a": 0.5}
    assert fit.predict(measured_zero) == pytest.approx(fit.predict(unmeasured))
    # Same probability, different record: one game says "no rain", the other
    # says "we could not look".
    assert any(c[0] == "sparse" for c in fit.contributions(measured_zero))
    assert not any(c[0] == "sparse" for c in fit.contributions(unmeasured))


# --- presence is recorded ---------------------------------------------------

def test_the_fit_records_how_many_rows_carried_each_factor():
    rng = random.Random(5)
    rows = [{"a": rng.gauss(0, 1)} for _ in range(600)]
    for r in rows[:200]:
        r["sometimes"] = rng.gauss(0, 1)
    labels = [rng.randint(0, 1) for _ in rows]

    fit = logistic.fit(rows, labels, ["a", "sometimes"], l2=1.0, min_rows_per_factor=50)
    assert fit.presence["a"] == 600
    assert fit.presence["sometimes"] == 200
    assert fit.n == 600, "n is the row count, not the count for any one factor"


def test_a_factor_measured_too_rarely_is_dropped_and_named():
    rng = random.Random(6)
    rows = [{"a": rng.gauss(0, 1)} for _ in range(600)]
    for r in rows[:9]:
        r["barely"] = rng.gauss(0, 1)
    labels = [rng.randint(0, 1) for _ in rows]

    fit = logistic.fit(rows, labels, ["a", "barely"], l2=1.0, min_rows_per_factor=50)
    assert "barely" not in fit.names
    assert fit.dropped == {"barely": 9}
    assert "barely" not in fit.as_dict()


def test_a_dropped_factor_survives_a_round_trip_through_json():
    rng = random.Random(7)
    rows = [{"a": rng.gauss(0, 1)} for _ in range(300)]
    for r in rows[:5]:
        r["barely"] = 1.0
    fit = logistic.fit(rows, [rng.randint(0, 1) for _ in rows], ["a", "barely"], l2=1.0)
    restored = logistic.Fit.from_json(fit.to_json())
    assert restored.dropped == fit.dropped
    assert restored.presence == fit.presence


def test_fitting_refuses_when_nothing_is_measured_enough():
    rows = [{"a": 1.0} for _ in range(10)]
    with pytest.raises(ValueError, match="nothing to fit"):
        logistic.fit(rows, [0] * 10, ["a"], min_rows_per_factor=50)


# --- the feature vector -----------------------------------------------------

def test_absent_factors_are_named_not_defaulted(league):
    game_id = league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1"
    ).fetchone()["id"]
    ctx = context.build_game_context(league, game_id)
    ctx.wind_mph = None
    ctx.temp_f = None
    ctx.precip_pct = None
    ctx.indoors = False
    fv = compute.feature_vector(ctx, "spread")

    for name in ("wind", "cold", "precipitation"):
        assert name not in fv.values
        assert name in fv.absent
    assert 0.0 < fv.coverage < 1.0


def test_describe_tells_the_reader_what_could_not_be_seen(league):
    game_id = league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1"
    ).fetchone()["id"]
    ctx = context.build_game_context(league, game_id)
    ctx.home_rest = None
    fv = compute.feature_vector(ctx, "spread")

    rows = compute.describe(fv)
    absent_row = next(r for r in rows if r["factor"] == "rest_diff")
    assert absent_row["present"] is False
    assert absent_row["value"] is None
    assert absent_row["why_absent"]


def test_the_absent_reader_understands_both_factor_sets():
    """v1 wrote `missing`; v2 writes `absent`. Both records are permanent."""
    assert compute.absent_factors({"missing": ["wind"]}) == ["wind"]
    assert compute.absent_factors({"absent": ["cold"]}) == ["cold"]
    assert compute.absent_factors({}) == []


def test_a_prediction_records_present_and_absent(league):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="d2")
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    row = league.execute("SELECT factors_json, reasoning FROM predictions LIMIT 1").fetchone()
    payload = json.loads(row["factors_json"])
    assert set(payload["present"]) == set(payload["values"])
    assert "absent" in payload and "coverage" in payload
    assert set(payload["present"]) & set(payload["absent"]) == set()


def test_the_narrative_names_what_was_unmeasurable(league):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="d2")
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    rows = league.execute("SELECT reasoning, factors_json FROM predictions").fetchall()
    with_absent = [
        r for r in rows if json.loads(r["factors_json"])["absent"]
    ]
    if with_absent:
        assert "excluded rather than assumed" in with_absent[0]["reasoning"]


# --- the repaired instruments ----------------------------------------------

def test_short_week_diff_is_deactivated_with_a_measured_reason():
    f = registry.REGISTRY["short_week_diff"]
    assert not f.active
    assert f.deactivated_utc
    assert "1 game of 544" in f.note
    assert "not as a refuted idea" in f.note, (
        "a broken instrument and a refuted hypothesis must not read the same"
    )
    assert f.name not in {g.name for g in registry.active_factors("nfl", "spread")}


def test_the_replacement_measures_the_level_not_the_difference():
    f = registry.REGISTRY["short_week_either"]
    assert f.active
    assert f.added_utc.startswith("2026-08-29")
    assert "REPAIR" in f.rationale

    class Ctx:
        home_rest = 4
        away_rest = 4
    assert f.fn(Ctx()) == 1.0, "both clubs short is exactly what the differential missed"

    class Rested:
        home_rest = 7
        away_rest = 7
    assert f.fn(Rested()) == 0.0

    class Unknown:
        home_rest = None
        away_rest = 7
    assert f.fn(Unknown()) is None, "unknown rest must be absent, not zero"


def test_rest_diff_was_kept_rather_than_duplicated():
    """The brief proposed adding REST_DAYS_DIFF. `rest_diff` already is it, and
    a second identical factor would be collinear with the first."""
    assert registry.REGISTRY["rest_diff"].active
    assert "signed difference in actual rest days" in registry.REGISTRY["rest_diff"].rationale
    # Football's registry only. Baseball declares its own rest instruments —
    # a pitcher's days between starts and a club's days between games — and
    # they are different measurements of a different sport, not duplicates of
    # this one. Scanning every sport's names for the substring found them and
    # called them a regression.
    duplicates = [
        f.name
        for f in registry.REGISTRY.values()
        if f.sport == "nfl" and "rest" in f.name and f.name != "short_week_either"
    ]
    assert duplicates == ["rest_diff"], f"a duplicate rest instrument appeared: {duplicates}"


def test_precipitation_records_where_its_value_came_from(league):
    game_id = league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1"
    ).fetchone()["id"]
    league.execute(
        "INSERT INTO weather_forecasts (game_id, fetched_utc, source, temp_f,"
        " wind_mph, precip_pct) VALUES (?,?,?,?,?,?)",
        (game_id, db.utcnow(), "open-meteo", 48.0, 14.0, 60.0),
    )
    league.commit()

    fv = compute.feature_vector(
        context.build_game_context(league, game_id), "spread"
    )
    assert "precipitation" in fv.values
    assert fv.values["precipitation"] == pytest.approx(0.60)
    assert fv.sources["precipitation"] == "forecast"
    assert fv.to_json_dict()["sources"]["precipitation"] == "forecast"


def test_precipitation_carries_the_repair_note():
    note = registry.REGISTRY["precipitation"].note
    assert note and "REPAIRED" in note
    assert "66%" in note


# --- factor set versions ----------------------------------------------------

def test_the_current_version_is_v2():
    assert config.FACTOR_SET_VERSION == "fs2"
    assert config.FACTOR_SET_ACTIVATED["fs2"].startswith("2026-08-29")
    assert "fs1" in config.FACTOR_SET_HISTORY


def test_a_closed_version_is_reported_not_erased(league):
    league.execute(
        "INSERT INTO predictions (created_utc, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) SELECT ?, id, 'spread', home, -3.5, 0.6,"
        " 'cover', 'statistical', 'fs1', '{}', 'v1 row' FROM games LIMIT 1",
        (db.utcnow(),),
    )
    league.commit()
    payload = calibration.version_comparison(league, sport="nfl")
    versions = {e["version"]: e for e in payload["versions"]}
    assert "fs1" in versions
    assert versions["fs1"]["status"] == "closed"
    assert versions["fs1"]["predictions_written"] == 1
    assert versions["fs2"]["status"] == "current"


def test_the_new_version_says_it_starts_at_zero(league):
    payload = calibration.version_comparison(league, sport="nfl")
    current = next(e for e in payload["versions"] if e["version"] == "fs2")
    assert current["n"] == 0
    assert "begins at N=0" in current["message"]
    assert "nothing wrong" in current["message"]


def test_versions_are_never_summed(league):
    payload = calibration.version_comparison(league, sport="nfl")
    assert payload["never_summed"] is True
    assert "NEVER added together" in payload["note"]
    calibration.assert_every_figure_has_n(payload)


def test_every_scoring_surface_can_filter_by_version(league):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="d2")
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)

    current = calibration.curve(league, sport="nfl", factor_set_version="fs2")
    closed = calibration.curve(league, sport="nfl", factor_set_version="fs1")
    assert current["filters"]["factor_set_version"] == "fs2"
    assert closed["n"] == 0, "a version with no record must report zero, not everything"

    report = calibration.factor_report(league, sport="nfl", factor_set_version="fs1")
    assert report["factor_set_version"] == "fs1"
