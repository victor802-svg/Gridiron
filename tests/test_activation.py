"""THE ACTIVATION GATE (operator rulings of 2026-09-24).

"Training a fit must not make it live. Fits are written inactive. A fit
becomes the active model for a market only by an explicit, dated activation
that records its holdout scores against the incumbent. The predict path reads
only activated fits." And: "ties go to the incumbent ... the bootstrap interval
of the difference in log loss excluding zero."

The plantings in `tools/guards/plant.py` break each rule on purpose; these hold
the pieces to their contracts on a scratch league.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import audit, config, db, run
from gridiron.factors import store
from gridiron.model import activation, baseline, logistic

BEFORE = "2026-09-05T11:16:52Z"            # fitted before the rule's birthday


def _train(conn, l2: float = 1.0) -> int:
    baseline.train(conn, "spread", (2025,), l2=l2, note="test")
    return conn.execute("SELECT MAX(id) FROM model_fits").fetchone()[0]


def _fit(conn, fit_id: int) -> logistic.Fit:
    return logistic.Fit.from_json(json.loads(conn.execute(
        "SELECT coefficients_json FROM model_fits WHERE id = ?",
        (fit_id,)).fetchone()[0]))


def _old_fit(conn, sport: str, market_type: str, version: str,
             fitted: str = BEFORE) -> int:
    """A fit row as the record holds them from before the gate."""
    blob = {"intercept": 0.1, "coefficients": {"home_field": 0.2}, "n": 100}
    conn.execute(
        "INSERT INTO model_fits (sport, fitted_utc, factor_set_version,"
        " market_type, train_through, n_train, coefficients_json, note)"
        " VALUES (?,?,?,?,'seasons:2016-2025',100,?,'from before the gate')",
        (sport, fitted, version, market_type, json.dumps(blob)))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM model_fits").fetchone()[0]


def _measure(conn, candidate, incumbent, interval, **overrides):
    scores = dict(holdout="fit through 2024, scored on 2025", holdout_n=272,
                  log_loss=0.661, brier=0.231, incumbent_log_loss=0.684,
                  incumbent_brier=0.245)
    scores.update(overrides)
    return activation.activate_measured(
        conn, candidate, incumbent_fit_id=incumbent, interval=interval,
        reason="test: measured on the holdout", **scores)


@pytest.fixture
def world(league):
    store.sync_registry(league)
    return league


# --- the rule's birthday is one value --------------------------------------

def test_the_birthday_in_the_config_is_the_one_in_the_schema():
    schema = db.SCHEMA_PATH.read_text(encoding="utf-8")
    trigger = schema[schema.index("fit_activation_incumbent_predates_the_rule"):]
    trigger = trigger[:trigger.index("END;")]
    assert f"'{config.ACTIVATION_GATE_BIRTHDAY}'" in trigger


# --- written inactive -------------------------------------------------------

def test_training_writes_a_fit_and_activates_nothing(world):
    _train(world)
    assert world.execute("SELECT COUNT(*) FROM model_fits").fetchone()[0] == 1
    assert world.execute("SELECT COUNT(*) FROM fit_activations").fetchone()[0] == 0
    with pytest.raises(baseline.NotTrained, match="no activated model for nfl:spread"):
        baseline.load_fit(world, "nfl:spread")


def test_the_predict_path_reads_the_active_fit_not_the_newest(world):
    """A catch-up after a training step publishes from the incumbent."""
    first = _train(world, l2=1.0)
    activation.activate_in_a_scratch_world(world)
    fresh = _train(world, l2=400.0)
    loaded = baseline.load_fit(world, "nfl:spread")
    assert loaded.intercept == pytest.approx(_fit(world, first).intercept)
    assert loaded.intercept != pytest.approx(_fit(world, fresh).intercept)

    run.run_week(world, 2025, 7, include_props=False, use_llm=False)
    for row in world.execute("SELECT factors_json FROM predictions"):
        payload = json.loads(row["factors_json"])
        assert _fit(world, first).predict(payload["values"]) == pytest.approx(
            payload["prob_yes"], abs=1e-5)


# --- measured: the holdout, and ties go to the incumbent -------------------

def test_a_candidate_that_beats_the_incumbent_is_activated(world):
    incumbent = _train(world)
    activation.activate_in_a_scratch_world(world)
    candidate = _train(world, l2=400.0)
    written = _measure(world, candidate, incumbent, (-0.041, -0.006))
    row = world.execute("SELECT * FROM fit_activations WHERE id = ?",
                        (written,)).fetchone()
    assert row["kind"] == "measured" and row["incumbent_fit_id"] == incumbent
    assert (row["diff_low"], row["diff_high"]) == (-0.041, -0.006)
    assert row["activated_utc"].endswith("Z")
    assert activation.active_fit(world, "nfl", "spread")["fit_id"] == candidate


@pytest.mark.parametrize("interval", [(-0.0094, 0.0205), (-0.02, 0.0),
                                      (0.001, 0.02)])
def test_a_tie_goes_to_the_incumbent(world, interval):
    incumbent = _train(world)
    activation.activate_in_a_scratch_world(world)
    candidate = _train(world, l2=400.0)
    with pytest.raises(activation.ActivationRefused, match="ties go to the incumbent"):
        _measure(world, candidate, incumbent, interval)
    assert activation.active_fit(world, "nfl", "spread")["fit_id"] == incumbent


@pytest.mark.parametrize("missing", ["holdout", "holdout_n", "log_loss",
                                     "brier", "incumbent_log_loss",
                                     "incumbent_brier"])
def test_a_measured_activation_without_every_score_is_refused(world, missing):
    incumbent = _train(world)
    activation.activate_in_a_scratch_world(world)
    candidate = _train(world, l2=400.0)
    with pytest.raises(activation.ActivationRefused,
                       match="holdout|without its holdout scores"):
        _measure(world, candidate, incumbent, (-0.04, -0.01), **{missing: None})


def test_an_interval_that_is_not_an_interval_is_refused(world):
    incumbent = _train(world)
    activation.activate_in_a_scratch_world(world)
    candidate = _train(world, l2=400.0)
    with pytest.raises(activation.ActivationRefused, match="without its holdout scores"):
        _measure(world, candidate, incumbent, (-0.01, -0.04))


def test_the_incumbent_is_the_fit_active_now(world):
    straw = _train(world)
    incumbent = _train(world, l2=2.0)
    activation.activate_in_a_scratch_world(world)          # activates the newest
    candidate = _train(world, l2=400.0)
    with pytest.raises(activation.ActivationRefused, match="active for that market now"):
        _measure(world, candidate, straw, (-0.04, -0.01))
    with pytest.raises(activation.ActivationRefused, match="active for that market now"):
        _measure(world, incumbent, incumbent, (-0.04, -0.01))


def test_a_market_with_no_incumbent_cannot_be_measured_in(world):
    """Ties go to the incumbent, and there is none: the operator rules."""
    candidate = _train(world)
    other = _train(world, l2=400.0)
    with pytest.raises(activation.ActivationRefused, match="waits for the"):
        _measure(world, candidate, other, (-0.04, -0.01))


# --- incumbent: before the birthday only ------------------------------------

def test_an_incumbent_fitted_after_the_birthday_is_refused(world):
    fresh = _train(world)
    with pytest.raises(activation.ActivationRefused, match="on or after 2026-09-24T05:16:00Z"):
        activation.activate_incumbent(world, fresh, reason="test: a revert, too late")
    boundary = _old_fit(world, "nfl", "total", "fs2",
                        fitted=config.ACTIVATION_GATE_BIRTHDAY)
    with pytest.raises(activation.ActivationRefused, match="on or after"):
        activation.activate_incumbent(world, boundary, reason="test: at the minute")


def test_an_incumbent_from_before_the_birthday_is_recorded_with_its_holdout(world):
    old = _old_fit(world, "nfl", "total", "fs2")
    written = activation.activate_incumbent(
        world, old, reason="test: the revert to the last trained set",
        holdout="fit through 2024, scored on 2025", holdout_n=272,
        log_loss=0.68361, brier=0.24535)
    row = world.execute("SELECT * FROM fit_activations WHERE id = ?",
                        (written,)).fetchone()
    assert row["kind"] == "incumbent" and row["log_loss"] == 0.68361
    assert baseline.load_fit(world, "nfl:total").intercept == 0.1


def test_a_holdout_is_whole_or_absent(world):
    old = _old_fit(world, "nfl", "total", "fs2")
    with pytest.raises(activation.ActivationRefused, match="recorded whole"):
        activation.activate_incumbent(world, old, reason="test: half a holdout",
                                      log_loss=0.68)


def test_only_a_measured_activation_carries_a_comparison(world):
    old = _old_fit(world, "nfl", "total", "fs2")
    with pytest.raises(sqlite3.IntegrityError, match="is a measured"):
        world.execute(
            "INSERT INTO fit_activations (fit_id, sport, market_type,"
            " factor_set_version, activated_utc, kind, reason, diff_low,"
            " diff_high) VALUES (?, 'nfl', 'total', 'fs2',"
            " '2026-09-24T12:00:00Z', 'incumbent', 'a comparison smuggled in',"
            " -0.2, -0.1)", (old,))


def test_an_activation_names_a_fit_of_its_own_market(world):
    fit = _train(world)
    with pytest.raises(sqlite3.IntegrityError, match="of its own sport"):
        world.execute(
            "INSERT INTO fit_activations (fit_id, sport, market_type,"
            " factor_set_version, activated_utc, kind, reason) VALUES"
            " (?, 'nfl', 'moneyline', 'fs5', '2026-09-24T12:00:00Z',"
            " 'scratch', 'a spread fit filed under the moneyline')", (fit,))


# --- append-only ------------------------------------------------------------

def test_an_activation_is_never_edited_or_deleted(world):
    _train(world)
    activation.activate_in_a_scratch_world(world)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        world.execute("UPDATE fit_activations SET reason = 'rewritten afterwards'")
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        world.execute("DELETE FROM fit_activations")


# --- scratch: never on a live database --------------------------------------

def test_a_scratch_activation_on_a_live_database_is_refused(conn):
    """`conn` is a fresh file, and a fresh file says 'live'."""
    store.sync_registry(conn)
    assert db.get_meta(conn, "kind") == "live"
    conn.execute(
        "INSERT INTO model_fits (sport, fitted_utc, factor_set_version,"
        " market_type, train_through, n_train, coefficients_json) VALUES"
        " ('nfl', '2026-09-24T12:00:00Z', 'fs5', 'spread', 'x', 1, '{}')")
    with pytest.raises(sqlite3.IntegrityError, match="refused on a live database"):
        conn.execute(
            "INSERT INTO fit_activations (fit_id, sport, market_type,"
            " factor_set_version, activated_utc, kind, reason) SELECT id,"
            " sport, market_type, factor_set_version, '2026-09-24T12:00:00Z',"
            " 'scratch', 'the holdout skipped' FROM model_fits")


def test_the_scratch_helper_declares_its_world_before_it_activates(conn):
    from tests.conftest import seed_league

    store.sync_registry(conn)
    seed_league(conn)
    db.set_meta(conn, "kind", "live")
    _train(conn)
    activation.activate_in_a_scratch_world(conn)
    assert db.database_kind(conn)["kind"] == "scratch"
    assert "without a holdout" in db.database_kind(conn)["note"]


def test_a_backtest_world_keeps_its_name(world):
    _train(world)
    activation.activate_in_a_scratch_world(world)
    assert db.database_kind(world)["kind"] == "backtest"


def test_the_scratch_helper_refuses_the_live_record(world, monkeypatch):
    _train(world)
    monkeypatch.setattr(db, "_is_the_live_record", lambda path: True)
    with pytest.raises(activation.ScratchWorldRefused, match="is the live record"):
        activation.activate_in_a_scratch_world(world)
    assert world.execute("SELECT COUNT(*) FROM fit_activations").fetchone()[0] == 0


def test_the_scratch_helper_refuses_a_record(world):
    old = _old_fit(world, "nfl", "total", "fs2")
    activation.activate_incumbent(world, old, reason="test: the record's own")
    _train(world)
    with pytest.raises(activation.ScratchWorldRefused, match="is a record"):
        activation.activate_in_a_scratch_world(world)


def test_the_scratch_helper_is_safe_to_call_after_every_training_step(world):
    _train(world)
    first = activation.activate_in_a_scratch_world(world)
    assert len(first) == 1
    assert activation.activate_in_a_scratch_world(world) == []
    newest = _train(world, l2=3.0)
    assert len(activation.activate_in_a_scratch_world(world)) == 1
    assert activation.active_fit(world, "nfl", "spread")["fit_id"] == newest


# --- the declared factor set ------------------------------------------------

def test_an_active_fit_of_another_factor_set_is_refused_by_name(world, monkeypatch):
    _train(world)
    activation.activate_in_a_scratch_world(world)
    assert audit.active_fit_faults(world) == []
    monkeypatch.setitem(config.FACTOR_SET_VERSIONS, ("nfl", "spread"), "fs-other")
    with pytest.raises(baseline.ActiveFitIsAnotherSet, match="ANOTHER FACTOR SET"):
        baseline.load_fit(world, "nfl:spread")
    faults = audit.active_fit_faults(world)
    assert len(faults) == 1 and faults[0].startswith("NFL spread")
    with pytest.raises(audit.LawViolation, match="ANOTHER FACTOR SET"):
        audit.check_every_active_fit_is_the_declared_set(world)
    result = run.run_week(world, 2025, 7, include_props=False, use_llm=False)
    assert result["written"] == 0
    assert any("ANOTHER FACTOR SET" in s for s in result["skipped"])


# --- the birthday bootstrap -------------------------------------------------

def test_the_bootstrap_activates_what_each_market_was_reading(conn):
    """The newest fit of the declared set, when it predates the rule. A newer
    one -- the four fs5 markets on the record -- is left unactivated."""
    total_old = _old_fit(conn, "nfl", "total", "fs2", fitted="2026-09-04T12:01:56Z")
    total_new = _old_fit(conn, "nfl", "total", "fs2")
    _old_fit(conn, "nfl", "spread", "fs3")                     # not the declared set
    spread_fs5 = _old_fit(conn, "nfl", "spread",
                          config.factor_set_version("nfl", "spread"),
                          fitted="2026-09-24T05:16:46Z")
    retired = _old_fit(conn, "mlb", "prop:batter_home_runs",
                       config.factor_set_version("mlb", "prop:batter_home_runs"))
    db.init(conn)
    rows = {(r["sport"], r["market_type"]): r for r in conn.execute(
        "SELECT * FROM fit_activations")}
    assert set(rows) == {("nfl", "total")}
    assert rows[("nfl", "total")]["fit_id"] == total_new != total_old
    assert rows[("nfl", "total")]["kind"] == "incumbent"
    assert "birthday bootstrap" in rows[("nfl", "total")]["reason"]
    assert rows[("nfl", "total")]["log_loss"] is None      # predates the rule
    with pytest.raises(baseline.NotTrained, match="no activated model"):
        baseline.load_fit(conn, "nfl:spread")
    assert spread_fs5 and retired

    # IDEMPOTENT, and a market once activated is never bootstrapped again
    db.init(conn)
    later = _old_fit(conn, "nfl", "total", "fs2", fitted="2026-09-06T00:00:00Z")
    db.init(conn)
    assert conn.execute("SELECT COUNT(*) FROM fit_activations").fetchone()[0] == 1
    assert activation.active_fit(conn, "nfl", "total")["fit_id"] == total_new != later


def test_the_bootstrap_leaves_a_fresh_world_alone(world):
    _train(world)
    assert activation.bootstrap_incumbents(world) == []


# --- the measurement tool ---------------------------------------------------

def _holdout_tool():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "tools" / "holdout.py"
    spec = importlib.util.spec_from_file_location("holdout_tool", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_tool_reads_the_tie_rule_the_way_the_schema_does():
    tool = _holdout_tool()
    assert tool.beats_the_incumbent((-0.03, -0.001))
    for tie in ((-0.0094, 0.0205), (-0.02, 0.0), (0.001, 0.02)):
        assert not tool.beats_the_incumbent(tie)


def test_the_paired_bootstrap_is_reproducible_and_brackets_the_mean():
    tool = _holdout_tool()
    diffs = [(-1) ** i * 0.05 - 0.02 for i in range(300)]
    low, high = tool.paired_bootstrap(diffs)
    assert (low, high) == tool.paired_bootstrap(diffs)
    assert low < sum(diffs) / len(diffs) < high < 0
