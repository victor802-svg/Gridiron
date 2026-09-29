"""A correction is in force only by its own dated row (operator question 32,
ruled 2026-09-29, second set; built the same day).

"Corrections activate through the same gate as model fits. Every correction
row is written inactive. Activation is its own dated append-only row, written
only when the holdout bootstrap interval of the Brier improvement excludes
zero, measured on distinct bets by the key, per forecaster; a tie goes to the
uncorrected probability. The recalibration task never activates anything; fix
its docstring to say what it does." And: "Fit 71: withdrawn now by a dated
append-only row, reason 'activated under the pre-Q32 rule: single holdout
comparison, pooled rows'. Then run the new gate on it read-only and report the
interval. If it passes, activation is a new dated row; if not, it stays
withdrawn."

The door is `correction.latest_activation` (and `active_correction`, it less
a withdrawal); the rows are `correction_activations`, their rules in the
schema; the measurement is `correction.measure`; the writers are
`activate_measured`, `withdraw` and `activate_in_a_scratch_world`; the tool is
`tools/correction_holdout.py`; the gate asks the door
(`audit.check_a_correction_is_in_force_only_by_its_own_row`).
"""
from __future__ import annotations

import importlib.util
import inspect
import random
import sqlite3

import pytest

from gridiron import audit, bet, config, correction, db, language, recount, views

FIT_AT = "2026-06-01T00:00:00Z"


def _world(tmp_path, name="q32.db"):
    conn = db.open_db(tmp_path / name)
    return conn


def _questions(conn, n, *, worth, market="moneyline", predictor="statistical",
               twice=False, first=1, seed=32, void_every=None):
    """`n` settled questions of one category, one game each, settling one
    hour apart in 2026 (so the time order is the questions' own); with
    `twice`, each answered by the morning and the final pass -- the final at
    a claim four points bolder. A claim is worth `worth` times what it says
    over a half: 1 is calibrated, under 1 overconfident."""
    rng = random.Random(seed)
    for i in range(first, first + n):
        gid = f"g{market}{i}"
        conn.execute(
            "INSERT OR IGNORE INTO games (id, sport, season, week, game_type,"
            " home, away, kickoff_utc, status, league_date, home_score,"
            " away_score) VALUES (?, 'nfl', 2025, 1, 'REG', 'AAA', 'BBB',"
            " '2025-12-01T18:00:00Z', 'final', '2025-12-01', 24, 17)", (gid,))
        claim = 0.55 + (i % 40) * 0.01
        outcome = 1 if rng.random() < 0.5 + (claim - 0.5) * worth else 0
        resolved = _hour(i)
        passes = (("early", claim - 0.04, "2025-12-01T06:00:00Z"),
                  ("final", claim, "2025-12-01T16:00:00Z"))
        for pass_kind, p, written in (passes if twice else passes[1:]):
            conn.execute(
                "INSERT INTO predictions (sport, created_utc, game_id,"
                " market_type, subject, line_asked, model_prob, model_side,"
                " predictor, pass_kind, factor_set_version, factors_json,"
                " reasoning, resolved_utc, outcome) VALUES ('nfl', ?, ?, ?,"
                " 'AAA', NULL, ?, 'win', ?, ?, 'fs2', '{}', 'q32', ?, ?)",
                (written, gid, market, round(p, 4), predictor, pass_kind,
                 resolved, outcome))
        if void_every and i % void_every == 0:
            conn.execute(
                "INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                " SELECT id, '2026-01-01T00:00:00Z', 'withdrawn in a test world'"
                "  FROM predictions WHERE game_id = ?", (gid,))
    conn.commit()


def _hour(i):
    from datetime import datetime, timedelta, timezone

    return (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fit(conn, *, market="moneyline", forecaster="statistical", n_train=500,
         fitted_utc=FIT_AT, slope=0.6, intercept=-0.05):
    version = correction.record_fit(
        conn, sport="nfl", market_type=market, forecaster=forecaster,
        model=correction.Platt(slope=slope, intercept=intercept, n_train=n_train),
        status="fitted in a test world", fitted_utc=fitted_utc)
    return conn.execute(
        "SELECT id FROM calibration_corrections WHERE market_type = ?"
        " AND forecaster = ? AND version = ?",
        (market, forecaster, version)).fetchone()[0]


def _served(conn, market="moneyline", forecaster="statistical", at=None):
    got = correction.active_correction(conn, sport="nfl", market_type=market,
                                       forecaster=forecaster, at_utc=at)
    return None if got is None else got["id"]


def _measured_row(fid, got, **over):
    low, high = got["interval"]
    values = dict(sport="nfl", market_type="moneyline", forecaster="statistical",
                  seq=1, correction_id=fid, activated_utc=db.utcnow(),
                  kind="measured", reason="a measured row in a test world",
                  holdout=got["holdout"], bets=got["bets"],
                  holdout_n=got["holdout_n"], brier_raw=got["brier_raw"],
                  brier_corrected=got["brier_corrected"],
                  improvement=got["improvement"], diff_low=low, diff_high=high,
                  bootstrap_seed=got["seed"], bootstrap_draws=got["draws"])
    values.update(over)
    return values


def _insert(conn, values):
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO correction_activations ({columns}) VALUES ({marks})",
                 tuple(values.values()))


# --- written inactive -------------------------------------------------------

def test_every_correction_row_is_written_inactive(tmp_path):
    """The writer has no way to say "in force", the schema refuses a row that
    says it anyway, and the weekly refit fits and writes no activation."""
    conn = _world(tmp_path)
    assert "active_from" not in inspect.signature(correction.record_fit).parameters
    with pytest.raises(sqlite3.IntegrityError, match="written inactive"):
        conn.execute(
            "INSERT INTO calibration_corrections (sport, market_type,"
            " forecaster, version, fitted_utc, n_train, slope, intercept,"
            " active_from, status) VALUES ('nfl', 'moneyline', 'statistical',"
            " 1, ?, 300, 0.6, 0.0, ?, 'active')", (FIT_AT, FIT_AT))
    conn.rollback()
    _questions(conn, 500, worth=0.0)
    report = correction.refit_all(conn, now="2026-03-01T00:00:00Z")
    (cat,) = report["categories"]
    assert (cat["questions"], cat["n_train"]) == (500, 500)
    assert cat["status"] == correction.FITTED_NOT_IN_FORCE
    assert "activated" not in report and "active" not in cat
    stored = conn.execute("SELECT active_from, holdout_n FROM"
                          " calibration_corrections").fetchone()
    assert tuple(stored) == (None, None)
    assert conn.execute("SELECT COUNT(*) FROM correction_activations").fetchone()[0] == 0
    assert _served(conn) is None


def test_the_recalibration_task_activates_nothing_and_says_so(tmp_path):
    from gridiron import tasks

    conn = _world(tmp_path)
    _questions(conn, 500, worth=0.0)
    result, detail, report = tasks._run_recalibrate(conn)
    assert result == "ok" and report["eligible"] == 1
    assert conn.execute("SELECT COUNT(*) FROM correction_activations").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM calibration_corrections"
                        " WHERE active_from IS NOT NULL").fetchone()[0] == 0
    doc = " ".join(tasks._run_recalibrate.__doc__.split())
    assert "written INACTIVE" in doc and "puts nothing in force" in doc
    assert "Writes versions; activates nothing." not in doc.split("Until")[0]


# --- the door ---------------------------------------------------------------

def test_the_door_reads_the_activation_rows_alone(tmp_path):
    """A row carrying active_from -- as fit 71 does -- is served by nobody;
    a correction's own row puts it in force from its instant; a withdrawal
    takes it out, and the page reads why."""
    conn = _world(tmp_path)
    old = _fit(conn, fitted_utc="2026-01-01T00:00:00Z")
    conn.execute("DROP TRIGGER calibration_corrections_written_inactive")
    conn.execute(
        "INSERT INTO calibration_corrections (sport, market_type, forecaster,"
        " version, fitted_utc, n_train, slope, intercept, active_from, status)"
        " VALUES ('nfl', 'total', 'statistical', 1, ?, 300, 0.6, 0.0, ?,"
        " 'active - the old rule')", ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
    conn.commit()
    db.init(conn)
    assert _served(conn, market="total") is None
    assert correction.latest_activation(conn, sport="nfl", market_type="total",
                                        forecaster="statistical") is None
    # a database holding a row written in force the old way is a record
    with pytest.raises(correction.ScratchWorldRefused, match="is a record"):
        correction.activate_in_a_scratch_world(conn, old, now="2026-02-01T00:00:00Z")

    fresh = _world(tmp_path, "fresh.db")
    fid = _fit(fresh, fitted_utc="2026-01-01T00:00:00Z")
    assert _served(fresh) is None
    correction.activate_in_a_scratch_world(fresh, fid, now="2026-02-01T00:00:00Z")
    assert db.get_meta(fresh, "kind") == "scratch"
    assert _served(fresh) == fid
    assert _served(fresh, at="2026-01-31T23:59:59Z") is None
    correction.withdraw(fresh, fid, reason="taken out of force in a test",
                        now="2026-03-01T00:00:00Z")
    assert _served(fresh) is None
    assert _served(fresh, at="2026-02-15T00:00:00Z") == fid
    latest = correction.latest_activation(fresh, sport="nfl",
                                          market_type="moneyline",
                                          forecaster="statistical")
    assert (latest["activation_kind"], latest["activation_reason"]) == (
        "withdrawn", "taken out of force in a test")
    # every stamp the reader sees came from a row, and the rows are in order
    rows = correction.activations(fresh, sport="nfl", market_type="moneyline",
                                  forecaster="statistical")
    assert [(r["seq"], r["kind"]) for r in rows] == [(1, "scratch"), (2, "withdrawn")]


def test_the_gate_asks_the_door_and_refuses_one_reading_active_from(tmp_path, monkeypatch):
    conn = _world(tmp_path)
    fid = _fit(conn, fitted_utc="2026-01-01T00:00:00Z")
    correction.activate_in_a_scratch_world(conn, fid, now="2026-02-01T00:00:00Z")
    audit.check_a_correction_is_in_force_only_by_its_own_row(conn)       # lawful
    audit.check_a_correction_is_in_force_only_by_its_own_row()

    def reading_active_from(conn, *, sport, market_type, forecaster, at_utc=None):
        return conn.execute(
            "SELECT * FROM calibration_corrections WHERE sport = ? AND"
            " market_type = ? AND forecaster = ? AND active_from IS NOT NULL"
            " AND active_from <= ? ORDER BY version DESC LIMIT 1",
            (sport, market_type, forecaster, at_utc or db.utcnow())).fetchone()

    monkeypatch.setattr(correction, "active_correction", reading_active_from)
    with pytest.raises(audit.LawViolation, match="IN FORCE WITHOUT ITS OWN ROW"):
        audit.check_a_correction_is_in_force_only_by_its_own_row()
    with pytest.raises(audit.LawViolation, match="the door serves correction None"):
        audit.check_a_correction_is_in_force_only_by_its_own_row(conn)


# --- the measurement --------------------------------------------------------

def test_the_measurement_counts_distinct_bets_per_forecaster(tmp_path):
    """Three hundred questions, each answered by the morning and the final
    pass, and the reasoning pass on the same games: measured on the three
    hundred -- each once, on its latest written forecast -- and on nothing of
    the other forecaster's; the latest fifth held out."""
    conn = _world(tmp_path)
    _questions(conn, 500, worth=0.0, twice=True)
    _questions(conn, 500, worth=1.0, predictor="llm", seed=7)
    fid = _fit(conn, n_train=1000)
    got = correction.measure(conn, fid)
    assert (got["bets"], got["fitted_on"], got["holdout_n"]) == (500, 400, 100)
    rows = correction.holdout_questions(
        conn, conn.execute("SELECT * FROM calibration_corrections WHERE id = ?",
                           (fid,)).fetchone())
    assert len(rows) == bet.count(rows) == 500
    assert {r["predictor"] for r in rows} == {"statistical"}
    kept = {r["id"] for r in rows}
    finals = {r[0] for r in conn.execute(
        "SELECT id FROM predictions WHERE predictor = 'statistical'"
        " AND pass_kind = 'final'")}
    assert kept == finals
    # the order is the order they settled
    assert [r["resolved_utc"] for r in rows] == sorted(r["resolved_utc"] for r in rows)
    # and it is the blind record's standing rule, read with the start
    assert got["standing"] == recount.correction_standing(
        conn, sport="nfl", market_type="moneyline", predictor="statistical",
        before_utc=FIT_AT)
    # a withdrawn question is measured by nobody
    conn2 = _world(tmp_path, "voided.db")
    _questions(conn2, 500, worth=0.0, void_every=10)
    got2 = correction.measure(conn2, _fit(conn2))
    assert got2["bets"] == 450


def test_a_correction_is_activated_only_when_its_interval_clears_zero(tmp_path):
    """A badly overconfident category passes and is put in force by a dated
    measured row carrying every number; a calibrated one is a tie and is
    not, and nothing is written."""
    conn = _world(tmp_path)
    _questions(conn, 500, worth=0.0)
    fid = _fit(conn)
    got = correction.measure(conn, fid)
    low, high = got["interval"]
    assert got["passed"] and low > 0 and low <= got["improvement"] <= high
    assert got["improvement"] == pytest.approx(got["brier_raw"] - got["brier_corrected"],
                                               abs=2e-6)
    assert (got["seed"], got["draws"]) == (correction.BOOTSTRAP_SEED,
                                            correction.BOOTSTRAP_DRAWS)
    wrote = correction.activate_measured(conn, fid, reason="measured in a test world")
    row = conn.execute("SELECT * FROM correction_activations").fetchone()
    assert (row["kind"], row["correction_id"], row["seq"]) == ("measured", fid, 1)
    assert (row["bets"], row["holdout_n"], row["diff_low"], row["diff_high"]) == (
        500, 100, low, high)
    assert (row["bootstrap_seed"], row["bootstrap_draws"]) == (20260923, 1000)
    assert row["activated_utc"] == wrote["written"]["activated_utc"]
    assert _served(conn) == fid

    calm = _world(tmp_path, "calm.db")
    _questions(calm, 300, worth=1.0, seed=5)
    cid = _fit(calm, slope=1.0, intercept=0.0)
    tie = correction.measure(calm, cid)
    assert not tie["passed"] and tie["interval"][0] <= 0
    assert "a tie" in tie["why"]
    with pytest.raises(correction.ActivationRefused, match="a tie"):
        correction.activate_measured(calm, cid, reason="measured in a test world")
    assert calm.execute("SELECT COUNT(*) FROM correction_activations").fetchone()[0] == 0
    assert _served(calm) is None


def test_the_measurement_scores_the_latest_fifth_as_they_settled_drawn_as_the_gate_draws(tmp_path):
    """THE PROVER (2026-09-29). The schema recounts the questions a
    measurement counts, and cannot tell WHICH it held out or which forecast
    of each it scored: a measurement that shuffled its questions, split them
    by number, kept each question's first pass, or drew its bootstrap
    unseeded wrote rows every rule accepted. So the measurement is worked
    out again here, from the rows, on a world where the order the questions
    were written in is not the order they settled in: each question on its
    latest written forecast, the latest fifth AS THEY SETTLED held out, a
    correction refit on the rest, and `tools/holdout.py`'s own bootstrap of
    the differences -- and measured twice, the same.

    FROM OPERATOR QUESTION 27 (2026-09-29) each question on its FINAL PASS,
    and every fifth question of the world has its early pass written after
    its final (the sixteen NFL totals' shape, both before the start), so a
    measurement keeping the latest written scores another set of forecasts
    and is told apart below."""
    conn = _world(tmp_path)
    order = list(range(1, 301))
    random.Random(9).shuffle(order)          # the hour each question settles
    rng = random.Random(3)
    for i, hour in enumerate(order, start=1):
        gid = f"s{i}"
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score) VALUES"
            " (?, 'nfl', 2025, 1, 'REG', 'AAA', 'BBB', '2025-12-01T18:00:00Z',"
            " 'final', '2025-12-01', 24, 17)", (gid,))
        claim = 0.55 + (i % 40) * 0.01
        outcome = 1 if rng.random() < 0.5 + (claim - 0.5) * (0.2 if hour > 150 else 1.0) else 0
        early_written = "2025-12-01T17:00:00Z" if i % 5 == 0 else "2025-12-01T06:00:00Z"
        for pass_kind, p, written in (("early", claim - 0.04, early_written),
                                      ("final", claim, "2025-12-01T16:00:00Z")):
            conn.execute(
                "INSERT INTO predictions (sport, created_utc, game_id,"
                " market_type, subject, line_asked, model_prob, model_side,"
                " predictor, pass_kind, factor_set_version, factors_json,"
                " reasoning, resolved_utc, outcome) VALUES ('nfl', ?, ?,"
                " 'moneyline', 'AAA', NULL, ?, 'win', 'statistical', ?, 'fs2',"
                " '{}', 'q32', ?, ?)",
                (written, gid, round(p, 4), pass_kind, _hour(hour), outcome))
    conn.commit()
    fid = _fit(conn, n_train=600)
    got = correction.measure(conn, fid)

    finals = sorted(conn.execute(
        "SELECT model_prob, outcome, resolved_utc, id FROM predictions"
        " WHERE pass_kind = 'final'").fetchall(), key=lambda r: (r[2], r[3]))
    train, test = finals[:240], finals[240:]
    assert (got["bets"], got["fitted_on"], got["holdout_n"]) == (300, 240, 60)
    assert got["brier_raw"] == correction.brier([r[0] for r in test], [r[1] for r in test])
    model = correction.fit_platt([(r[0], r[1], r[2]) for r in train])
    diffs = [(r[0] - r[1]) ** 2 - (model.apply(r[0]) - r[1]) ** 2 for r in test]
    assert got["brier_corrected"] == correction.brier(
        [model.apply(r[0]) for r in test], [r[1] for r in test])
    path = config.PACKAGE_ROOT.parent / "tools" / "holdout.py"
    spec = importlib.util.spec_from_file_location("q32_holdout_split", path)
    holdout = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(holdout)
    assert got["interval"] == holdout.paired_bootstrap(diffs)
    assert correction.measure(conn, fid)["interval"] == got["interval"]
    # the held-out fifth by NUMBER is another set, so the check can tell
    by_number = sorted(finals, key=lambda r: r[3])[240:]
    assert correction.brier([r[0] for r in by_number],
                            [r[1] for r in by_number]) != got["brier_raw"]
    # and so is each question's LATEST WRITTEN forecast (question 27): the
    # early pass wherever it was written after the final
    latest = {}
    for r in conn.execute("SELECT game_id, model_prob, outcome, resolved_utc, id,"
                          " created_utc FROM predictions").fetchall():
        if r[0] not in latest or (r[5], r[4]) > (latest[r[0]][5], latest[r[0]][4]):
            latest[r[0]] = r
    by_write_time = sorted(latest.values(), key=lambda r: (r[3], r[4]))[240:]
    assert correction.brier([r[1] for r in by_write_time],
                            [r[2] for r in by_write_time]) != got["brier_raw"]


def test_the_bootstrap_is_the_model_gates():
    path = config.PACKAGE_ROOT.parent / "tools" / "holdout.py"
    spec = importlib.util.spec_from_file_location("q32_holdout_under_test", path)
    holdout = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(holdout)
    assert (correction.BOOTSTRAP_DRAWS, correction.BOOTSTRAP_SEED) == (
        holdout.BOOTSTRAP_DRAWS, holdout.BOOTSTRAP_SEED)
    rng = random.Random(1)
    for n in (40, 52, 73):
        diffs = [rng.uniform(-0.2, 0.25) for _ in range(n)]
        assert correction.paired_bootstrap(diffs) == holdout.paired_bootstrap(diffs)


def test_a_placeholder_is_never_measured_or_activated(tmp_path):
    """(A labelled fit: `test_correction_gate.py::test_a_labelled_fit_is_never_activated`.)"""
    conn = _world(tmp_path)
    _questions(conn, 30, worth=0.3)
    correction.refit_all(conn, now="2026-03-01T00:00:00Z")
    placeholder = conn.execute("SELECT id FROM calibration_corrections").fetchone()[0]
    got = correction.measure(conn, placeholder)
    assert not got["passed"] and "a placeholder" in got["why"]
    with pytest.raises(correction.ActivationRefused, match="placeholder"):
        correction.activate_in_a_scratch_world(conn, placeholder,
                                               now="2026-03-02T00:00:00Z")


# --- the rules --------------------------------------------------------------

def test_the_schema_refuses_every_activation_the_ruling_does_not_allow(tmp_path):
    """Each refused by its rule, on the measurement of a category that
    passes: a tie, no interval, the pooled count, the wrong category, a
    labelled fit, a placeholder, a scratch row on a live record, a
    withdrawal of what is not in force, a stamp out of order, and an edit, a
    delete and a replacing insert of a stored row."""
    conn = _world(tmp_path)
    _questions(conn, 500, worth=0.0, twice=True)
    fid = _fit(conn, n_train=1000)
    got = correction.measure(conn, fid)
    assert got["passed"]
    refused = {
        "an interval touching zero": (dict(diff_low=0.0), "a tie goes to the uncorrected"),
        "an interval below zero": (dict(diff_low=-0.01, diff_high=0.02),
                                   "a tie goes to the uncorrected"),
        "no interval": (dict(diff_low=None, diff_high=None), "without its measurement"),
        "no seed": (dict(bootstrap_seed=None), "without its measurement"),
        "an interval written as words": (dict(diff_low="clear", diff_high="clear"),
                                         "without its measurement|a tie goes"),
        "forty held out, short": (dict(holdout_n=39, bets=195),
                                  "without its measurement|measured on distinct bets"),
        "the pooled forecasts counted": (dict(bets=1000, holdout_n=200),
                                         "measured on distinct bets"),
        "another holdout than the fifth": (dict(holdout_n=61), "measured on distinct bets"),
        "an improvement the Briers do not give": (dict(improvement=0.5),
                                                  "without its measurement"),
        "another category than its correction's": (dict(market_type="total"),
                                                   "of its own category"),
        "stamped ahead": (dict(activated_utc="2099-01-01T00:00:00Z"),
                          "stamped when it is written"),
        "stamped before its fit": (dict(activated_utc="2026-05-01T00:00:00Z"),
                                   "stamped when it is written"),
        # THE PROVER (2026-09-29): each of these three landed as first built
        "stamped a month back, after its fit": (
            dict(activated_utc="2026-06-01T00:00:01Z"),
            "never more than a minute before it is written"),
        "one resample": (dict(bootstrap_draws=1), "drawn as the gate draws it"),
        "another seed": (dict(bootstrap_seed=7), "drawn as the gate draws it"),
        "a place not the next": (dict(seq=3), "append-only"),
        "a measurement on a withdrawal": (dict(kind="withdrawn"),
                                         "is a measured activation|a withdrawal names"),
    }
    for name, (over, words) in refused.items():
        with pytest.raises(sqlite3.IntegrityError, match=words):
            _insert(conn, _measured_row(fid, got, **over))
        conn.rollback()
    # a withdrawal naming what is not in force
    with pytest.raises(correction.ActivationRefused, match="the correction in force"):
        correction.withdraw(conn, fid, reason="nothing is in force to withdraw")
    # a scratch row on a live record
    assert db.get_meta(conn, "kind") == "live"
    with pytest.raises(sqlite3.IntegrityError, match="refused on a live"):
        _insert(conn, dict(sport="nfl", market_type="moneyline",
                           forecaster="statistical", seq=1, correction_id=fid,
                           activated_utc=db.utcnow(), kind="scratch",
                           reason="a scratch row on a live database"))
    conn.rollback()
    # the lawful row lands; then it is permanent
    _insert(conn, _measured_row(fid, got))
    conn.commit()
    stored = [tuple(r) for r in conn.execute("SELECT * FROM correction_activations")]
    for sql, words in (
            ("UPDATE correction_activations SET reason = 'rewritten afterwards'",
             "append-only"),
            ("DELETE FROM correction_activations", "never deleted"),
            ("INSERT OR REPLACE INTO correction_activations (sport, market_type,"
             " forecaster, seq, correction_id, activated_utc, kind, reason)"
             f" VALUES ('nfl', 'moneyline', 'statistical', 1, {fid},"
             f" '{db.utcnow()}', 'withdrawn', 'written over the activation')",
             "append-only"),
            ("REPLACE INTO correction_activations (sport, market_type,"
             " forecaster, seq, correction_id, activated_utc, kind, reason)"
             f" VALUES ('nfl', 'moneyline', 'statistical', '1', {fid},"
             f" '{db.utcnow()}', 'withdrawn', 'written over, spelled as text')",
             "append-only")):
        with pytest.raises(sqlite3.IntegrityError, match=words):
            conn.execute(sql)
        conn.rollback()
    # AND THE CORRECTION IT NAMES IS NEVER WRITTEN OVER, by its number or by
    # its category and version
    for sql in (
            "INSERT OR REPLACE INTO calibration_corrections (id, sport,"
            " market_type, forecaster, version, fitted_utc, n_train, slope,"
            f" intercept, status) VALUES ({fid}, 'nfl', 'moneyline',"
            f" 'statistical', 1, '{FIT_AT}', 600, 3.0, 1.0, 'written over')",
            "REPLACE INTO calibration_corrections (sport, market_type,"
            " forecaster, version, fitted_utc, n_train, slope, intercept,"
            f" status) VALUES ('nfl', 'moneyline', 'statistical', 1,"
            f" '{FIT_AT}', 600, 3.0, 1.0, 'written over')"):
        with pytest.raises(sqlite3.IntegrityError, match="never written over"):
            conn.execute(sql)
        conn.rollback()
    assert [tuple(r) for r in conn.execute("SELECT * FROM correction_activations")] == stored
    assert conn.execute("SELECT slope FROM calibration_corrections").fetchone()[0] == 0.6
    # a labelled fit is never put in force, and a fit put in force is never
    # labelled
    with pytest.raises(sqlite3.IntegrityError, match="carries an activation"):
        conn.execute(
            "INSERT INTO correction_gate_labels (correction_id, labelled_utc,"
            " verdict, gate, count_used, corrected_count, reason) VALUES"
            f" ({fid}, '{db.utcnow()}', 'fitted_below_its_gate', 50, 1000, 500,"
            " 'a label on a fit in force')")
    conn.rollback()
    # A RECORD STAYS A RECORD WHATEVER ITS KIND SAYS (the prover,
    # 2026-09-29): with a measured row stored, the kind set to scratch by
    # hand lets no scratch row land
    conn.execute("UPDATE meta SET value = 'scratch' WHERE key = 'kind'")
    with pytest.raises(sqlite3.IntegrityError, match="whatever its kind says"):
        _insert(conn, dict(sport="nfl", market_type="moneyline",
                           forecaster="statistical", seq=2, correction_id=fid,
                           activated_utc=db.utcnow(), kind="scratch",
                           reason="planted after the kind was changed by hand"))
    conn.rollback()
    assert db.get_meta(conn, "kind") == "live"


def test_a_record_is_a_record_whatever_its_kind_says(tmp_path):
    """THE PROVER (2026-09-29). The record holds fit 71 written in force the
    old way and, from the release, its withdrawal; the kind is a meta value
    no rule holds. With the kind set to scratch by hand, a scratch row and a
    row dated back each landed as first built, and the door served the
    scratch row's correction. Both are refused on a database holding a
    record's own rows; a world that is only a scratch world keeps both."""
    conn = _world(tmp_path)
    _questions(conn, 60, worth=0.3)
    other = _fit(conn, n_train=60, fitted_utc="2026-05-01T00:00:00Z")
    conn.execute("DROP TRIGGER calibration_corrections_written_inactive")
    conn.execute(
        "INSERT INTO calibration_corrections (sport, market_type, forecaster,"
        " version, fitted_utc, n_train, slope, intercept, active_from, status)"
        " VALUES ('nfl', 'total', 'statistical', 1, ?, 364, 1.0, -0.2, ?,"
        " 'active - as the weekly refit wrote fit 71')", (FIT_AT, FIT_AT))
    conn.commit()
    db.init(conn)
    old = conn.execute("SELECT id FROM calibration_corrections"
                       " WHERE market_type = 'total'").fetchone()[0]
    conn.execute("UPDATE meta SET value = 'scratch' WHERE key = 'kind'")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="whatever its kind says"):
        _insert(conn, dict(sport="nfl", market_type="moneyline",
                           forecaster="statistical", seq=1, correction_id=other,
                           activated_utc=db.utcnow(), kind="scratch",
                           reason="a scratch row on a record, its kind changed"))
    conn.rollback()
    with pytest.raises(correction.ActivationRefused,
                       match="never more than a minute before it is written"):
        correction.withdraw(conn, old, reason="dated a month back on a record",
                            now="2026-06-02T00:00:00Z")
    assert _served(conn) is None and _served(conn, market="total") is None
    correction.withdraw(conn, old, reason="withdrawn when it is written")
    # A SCRATCH WORLD, and only that, may date its rows as it likes
    world = _world(tmp_path, "scratch.db")
    fid = _fit(world, fitted_utc="2026-01-01T00:00:00Z")
    correction.activate_in_a_scratch_world(world, fid, now="2026-02-01T00:00:00Z")
    correction.withdraw(world, fid, reason="taken out in a scratch world",
                        now="2026-02-02T00:00:00Z")
    assert _served(world, at="2026-02-01T12:00:00Z") == fid and _served(world) is None


def test_the_rules_pin_the_gate_as_the_code_declares_it():
    rule = " ".join(audit._schema_rule_text(
        "correction_activation_carries_its_measurement").split())
    assert f"NEW.holdout_n < {correction.HOLDOUT_MIN}" in rule
    # THE BOOTSTRAP AS THE GATE DRAWS IT (the prover, 2026-09-29)
    assert f"NEW.bootstrap_seed <> {correction.BOOTSTRAP_SEED}" in rule
    assert f"NEW.bootstrap_draws <> {correction.BOOTSTRAP_DRAWS}" in rule
    rule = " ".join(audit._schema_rule_text(audit.ACTIVATION_KEY_RULE).split())
    assert f"NEW.bets * {correction.HOLDOUT_TRAIN_SHARE} AS INTEGER" in rule
    assert bet.same("q", "p") in rule
    rule = " ".join(audit._schema_rule_text(
        "correction_activation_never_a_labelled_fit_or_a_placeholder").split())
    assert f"< {correction.MIN_TRAIN})" in rule
    assert audit.distinct_bet_key_faults() == []
    schema = (config.PACKAGE_ROOT / "schema.sql").read_text(encoding="utf-8")
    widened = schema.replace("AND q.line_asked IS p.line_asked", "")
    assert bet.same("q", "p") not in " ".join(
        audit._schema_rule_text(audit.ACTIVATION_KEY_RULE, widened).split())
    # WITHOUT ROWID: the key is worked out once, so every rule reads the row
    # that lands (question 16's prover)
    probe = db.connect(":memory:")
    try:
        db.init(probe)
        table = probe.execute("SELECT sql FROM sqlite_master WHERE name ="
                              " 'correction_activations'").fetchone()[0]
    finally:
        probe.close()
    assert " ".join(table.split()).endswith(") WITHOUT ROWID")


def test_a_withdrawal_names_the_correction_in_force_and_a_withdrawn_one_can_return(tmp_path):
    conn = _world(tmp_path)
    _questions(conn, 500, worth=0.0)
    first = _fit(conn)
    second = _fit(conn, fitted_utc="2026-06-02T00:00:00Z")
    correction.activate_measured(conn, second, reason="measured in a test world")
    with pytest.raises(correction.ActivationRefused, match="the correction in force"):
        correction.withdraw(conn, first, reason="not the one in force")
    correction.withdraw(conn, second, reason="taken out by a ruling in a test")
    with pytest.raises(correction.ActivationRefused, match="the correction in force"):
        correction.withdraw(conn, second, reason="withdrawn a second time")
    assert _served(conn) is None
    # a withdrawn correction measured again and passing is a new dated row
    correction.activate_measured(conn, second, reason="measured again")
    assert _served(conn) == second
    kinds = [r["kind"] for r in correction.activations(
        conn, sport="nfl", market_type="moneyline", forecaster="statistical")]
    assert kinds == ["measured", "withdrawn", "measured"]


# --- the schema reaches an older record through db.init ----------------------

def test_an_older_record_gains_question_32s_objects_through_init_and_no_row_moves(tmp_path):
    """The record as question 16's release left it -- fit 71 written in force
    by the weekly refit -- opened under this schema: exactly the new table
    and rules, each as a fresh build has it and in its order, no stored row
    moved, fit 71 served by nobody, and a second open changes nothing."""
    from tests.test_correction_gate import _Q32_OBJECTS

    conn = _world(tmp_path)
    _questions(conn, 60, worth=0.3)
    for kind, name in sorted(_Q32_OBJECTS, reverse=True):
        conn.execute(f"DROP {kind.upper()} {name}")
    conn.execute(
        "INSERT INTO calibration_corrections (sport, market_type, forecaster,"
        " version, fitted_utc, n_train, slope, intercept, active_from, status)"
        " VALUES ('nfl', 'moneyline', 'statistical', 1, ?, 60, 0.8, 0.1, ?,"
        " 'active - as the weekly refit wrote fit 71')", (FIT_AT, FIT_AT))
    conn.commit()

    def objects(c):
        return {(r[0], r[1]): r[2] for r in c.execute(
            "SELECT type, name, sql FROM sqlite_master")}

    def rows(c):
        return [tuple(r) for r in c.execute(
            "SELECT * FROM calibration_corrections ORDER BY id")] + [
            tuple(r) for r in c.execute("SELECT * FROM predictions ORDER BY id")]

    before, stored = objects(conn), rows(conn)
    db.init(conn)
    after = objects(conn)
    assert set(after) - set(before) == _Q32_OBJECTS
    assert all(after[k] == before[k] for k in before)
    fresh = db.open_db(tmp_path / "fresh.db")
    try:
        for key in _Q32_OBJECTS:
            assert after[key] == objects(fresh)[key]
        order = ("SELECT name FROM sqlite_master WHERE type = 'trigger' AND"
                 " tbl_name IN ('calibration_corrections', 'correction_gate_labels',"
                 " 'correction_activations') ORDER BY rowid")
        assert [r[0] for r in conn.execute(order)] == [r[0] for r in fresh.execute(order)]
    finally:
        fresh.close()
    assert rows(conn) == stored
    assert _served(conn) is None
    db.init(conn)
    assert objects(conn) == after and rows(conn) == stored


# --- the page ----------------------------------------------------------------

def test_the_page_says_each_state_in_plain_words(tmp_path):
    """Fitted and not in force; in force since its row, with its interval;
    withdrawn since its row, with its reason -- the ruled one in plain words."""
    conn = _world(tmp_path)
    _questions(conn, 500, worth=0.0)
    fid = _fit(conn)

    # NAMED BY THE DAY IT WAS FITTED, ITS VERSION IN THE ROW'S TOOLTIP
    # (operator question 19, ruled 2026-09-27: "internal version names only
    # in a tooltip"; the board merge, 2026-09-29). Each line said "Version 1
    # ..." until then; each says "the correction fitted on Monday 1 June ...",
    # and the tooltip of the gate row, the learning row and the category
    # carries "Version 1: ...".
    tip = language.version_tip("correction", 1)

    def said():
        category = next(c for c in views.corrections_report(conn, "nfl")["categories"]
                        if c["market_type"] == "moneyline")
        row = next(r for r in views.learning(conn, "nfl")["categories"]
                   if r["market"] == "moneyline")
        gate = next(g for g in views.scorecard(conn, "nfl")["gates"]
                    if g["name"] == "A correction for moneyline, statistical")
        assert category["version_tip"] == tip and row["version_tip"] == tip
        assert gate.get("version_tip") == tip
        return category["state"], row["status_words"], gate.get("why")

    state, words, why = said()
    assert state == ("The correction fitted on Monday 1 June on 500 settled "
                     "forecasts is not in force: " + language.NOT_IN_FORCE_WORDS + ".")
    assert words.startswith("500 settled questions; the correction fitted on "
                            "Monday 1 June on 500 settled forecasts is not in force")
    assert why == state
    got = correction.activate_measured(conn, fid, reason="measured in a test world")
    since = language.date_words_from_iso(got["written"]["activated_utc"][:10])
    state, words, why = said()
    low, high = got["interval"]
    assert state == (
        f"The correction fitted on Monday 1 June is in force since {since}: on "
        f"the 500 settled questions before it was fitted, one fitted on the "
        f"earliest 400 lowered the Brier score on the latest 100 by "
        f"{got['improvement']:.4f} (95% interval {low:.4f} to {high:.4f}, "
        f"clear of zero).")
    # NEVER "which it was not fitted on" of the version itself (the render of
    # 2026-09-29): it was fitted on all of them; the gate's refit was not
    assert "not fitted on" not in state
    assert words == "500 settled questions; " + state[0].lower() + state[1:-1]
    correction.withdraw(conn, fid, reason="taken out of force by a test ruling")
    state, words, why = said()
    assert state == (f"The correction fitted on Monday 1 June has been withdrawn "
                     f"since {since}: taken out of force by a test ruling; "
                     f"nothing is in force.")
    for text in (state, words, why):
        assert audit.plain_words_violations(text) == []
        assert "ersion" not in text, text
    assert audit.plain_words_violations(tip, in_a_tooltip=True) == []
    assert audit.plain_words_violations(tip), "a version name outside a tooltip passed"
    # THE RULED REASON, stored as ruled and said in plain words
    assert language.withdrawal_reason_words(correction.FIT_71_WITHDRAWAL_REASON) \
        == language.RULED_WITHDRAWAL_WORDS
    assert "Q32" not in language.RULED_WITHDRAWAL_WORDS
    assert "pooled" not in language.RULED_WITHDRAWAL_WORDS


# --- the tool -----------------------------------------------------------------

def _tool():
    path = config.PACKAGE_ROOT.parent / "tools" / "correction_holdout.py"
    spec = importlib.util.spec_from_file_location("q32_tool_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_tool_withdraws_fit_71_as_ruled_then_measures_it(tmp_path, capsys):
    """On the record's shape (question 31's rehearsal world): the dry run
    writes nothing; the withdrawal is written once, with the ruled reason, and
    not again; the measurement is reported; it does not pass there (too few
    questions held out), so nothing is written and it stays withdrawn."""
    from tests.test_correction_gate import _rehearsal_world

    tool = _tool()
    assert tool.RULED_WITHDRAWALS[71]["reason"] == (
        "activated under the pre-Q32 rule: single holdout comparison, pooled rows")
    conn, path = _rehearsal_world(tmp_path)
    conn.close()
    args = ["--database", str(path), "--correction", "71"]
    assert tool.main(args + ["--withdraw"]) == 0
    out = capsys.readouterr().out
    assert "written in force under the rule before this one, at 2026-09-28T13:00:01Z" in out
    assert "nothing written. --write would write this one withdrawal." in out
    # THE RULING'S ORDER: no activation before the withdrawal
    with pytest.raises(SystemExit) as exc:
        tool.main(args + ["--write"])
    assert exc.value.code == 2
    assert "ruled withdrawal is not on the record yet" in capsys.readouterr().out
    assert tool.main(args + ["--withdraw", "--write"]) == 0
    assert "wrote the withdrawal of correction 71" in capsys.readouterr().out
    assert tool.main(args + ["--withdraw", "--write"]) == 0
    assert "already withdrawn, as ruled" in capsys.readouterr().out
    assert tool.main(args) == 0
    out = capsys.readouterr().out
    assert "DOES NOT PASS" in out and "would stay out of force" in out
    assert tool.main(args + ["--write"]) == 1
    assert "NOT ACTIVATED, NOTHING WRITTEN" in capsys.readouterr().out
    conn = db.connect(path)
    try:
        rows = correction.activations(conn, sport="mlb", market_type="moneyline",
                                      forecaster="statistical")
        assert [(r["kind"], r["correction_id"], r["reason"]) for r in rows] == [
            ("withdrawn", 71, correction.FIT_71_WITHDRAWAL_REASON)]
        assert correction.active_correction(conn, sport="mlb", market_type="moneyline",
                                            forecaster="statistical") is None
    finally:
        conn.close()


def test_the_tool_refuses_what_the_ruling_does_not_name(tmp_path, capsys):
    tool = _tool()
    conn = _world(tmp_path)
    _questions(conn, 500, worth=0.0)
    fid = _fit(conn)
    conn.close()
    path = tmp_path / "q32.db"
    for argv, words in (
            (["--correction", str(fid), "--withdraw"], "no ruling withdraws"),
            (["--correction", str(fid), "--write", "--live"], "--live names"),
            (["--correction", "71", "--withdraw"], "there is no correction 71")):
        with pytest.raises(SystemExit) as exc:
            tool.main(["--database", str(path)] + argv)
        assert exc.value.code == 2
        assert words in capsys.readouterr().out
    # an unruled correction is measured, and activated only on a pass
    assert tool.main(["--database", str(path), "--correction", str(fid)]) == 0
    out = capsys.readouterr().out
    assert "PASSES" in out and "--write would write its measured activation" in out
    assert "each of the 500 questions stands on the forecast" in out
    assert tool.main(["--database", str(path), "--correction", str(fid), "--write"]) == 0
    assert "wrote the measured activation" in capsys.readouterr().out
    assert tool.main(["--database", str(path), "--correction", str(fid), "--write"]) == 0
    assert "already in force by its measured activation" in capsys.readouterr().out


def test_the_tool_names_a_question_whose_standing_forecast_is_not_its_latest(tmp_path, capsys):
    """A forecast written after its game began and withdrawn by no void: the
    measurement, which reads no start, and the standing rule part, and the
    tool measures nothing.

    FROM OPERATOR QUESTION 27 (2026-09-29) both keep a final pass first --
    the measurement by pass alone -- so an EARLY pass written after the
    start over a final pass before it (this test's first world until that
    date) no longer parts them: both keep the final, and the tool measures.
    A FINAL pass written after the start does: the measurement keeps it, the
    standing rule keeps the final pass written before the start."""
    tool = _tool()
    conn = _world(tmp_path)
    _questions(conn, 500, worth=0.0)
    late = ("INSERT INTO predictions (sport, created_utc, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
            " VALUES ('nfl', '2025-12-01T19:00:00Z', 'gmoneyline7', 'moneyline',"
            " 'AAA', NULL, 0.9, 'win', 'statistical', ?, ?, '{}', 'late', ?, 1)")
    conn.execute(late, ("early", "fs2", _hour(7)))
    conn.commit()
    fid = _fit(conn)
    conn.close()
    assert tool.main(["--database", str(tmp_path / "q32.db"),
                      "--correction", str(fid)]) == 0
    assert "each of the 500 questions stands on the forecast" in capsys.readouterr().out
    conn = db.open_db(tmp_path / "q32.db")
    conn.execute(late, ("final", "fs3", _hour(7)))
    conn.commit()
    conn.close()
    with pytest.raises(SystemExit) as exc:
        tool.main(["--database", str(tmp_path / "q32.db"), "--correction", str(fid)])
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "is not the one the blind record's standing rule keeps" in out
    assert "'gmoneyline7'" in out
