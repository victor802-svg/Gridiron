"""Each correction gate's count, per forecaster and distinct bet; and a fit
fitted below its gate, labelled and never in force.

Operator question 16, ruled (B) 2026-09-27: "(B), after Q17, on its key. Each
correction gate's count per forecaster and distinct bet, planting each."
Question 23, ruled (A) 2026-09-28: "The page's count and the fit's own gate
both move to the key, for fits from the release forward. The 63 existing fits
stay as written; any that falls short of its gate on the corrected count is
labelled 'fitted below its gate' and can never be activated." Built
2026-09-29 (docs/REPAIR_STATE.md questions 16, 23 and 31).

The one door is `correction.settled_rows`; every count of it is
`bet.count(rows)`. The guard is `calibration.assert_no_pooled_correction_counts`
inside `views.corrections_report` and `views.learning`, and the gate builds
every sport (`audit.check_the_correction_counts_are_never_pooled`). The label
is `correction_gate_labels`, its rules in the schema, written by
`correction.write_labels` from `correction.below_their_gates`, through
`tools/label_corrections_below_the_gate.py`.
"""
from __future__ import annotations

import importlib.util
import itertools
import sqlite3
import textwrap

import pytest

from gridiron import audit, bet, calibration, config, correction, db, language, views

FIT_AT = "2026-06-01T00:00:00Z"


def _world(tmp_path):
    conn = db.open_db(tmp_path / "q16.db")
    for i in range(1, 121):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES (?, 'nfl', 2025, 1, 'REG', 'AAA', 'BBB',"
            " '2025-12-01T18:00:00Z', 'final', '2025-12-01', 24, 17)",
            (f"g{i}",))
    conn.commit()
    return conn


def _forecast(conn, game, *, market="spread", subject="AAA", line=-3.5,
              predictor="statistical", pass_kind="early", outcome=1, prob=0.62,
              resolved="2026-01-05T00:00:00Z", version=None, prop_type=None):
    conn.execute(
        "INSERT INTO predictions (sport, created_utc, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " pass_kind, factor_set_version, factors_json, reasoning,"
        " resolved_utc, outcome, correction_version, calibrated_prob)"
        " VALUES ('nfl', ?, ?, ?, ?, ?, ?, ?, 'cover', ?, ?, 'fs3', '{}',"
        " 'test', ?, ?, ?, ?)",
        ("2025-12-01T06:00:00Z" if pass_kind == "early" else
         "2025-12-01T16:00:00Z", f"g{game}", market, prop_type, subject, line,
         prob, predictor, pass_kind, resolved, outcome, version,
         prob if version is not None else None))
    return conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]


def _twice(conn, games, **kw):
    """Each game's question answered by the morning and the final pass."""
    for g in games:
        for pass_kind in ("early", "final"):
            _forecast(conn, g, pass_kind=pass_kind, outcome=g % 2, **kw)
    conn.commit()


def _fit(conn, *, market="spread", forecaster="statistical", n_train=56,
         active_from=None, fitted_utc=FIT_AT, model=True) -> int:
    version = correction.record_fit(
        conn, sport="nfl", market_type=market, forecaster=forecaster,
        model=(correction.Platt(slope=0.8, intercept=0.1, n_train=n_train)
               if model else None),
        status="test", active_from=active_from, fitted_utc=fitted_utc)
    return conn.execute(
        "SELECT id FROM calibration_corrections WHERE market_type = ?"
        " AND forecaster = ? AND version = ?",
        (market, forecaster, version)).fetchone()[0]


def _category(report, market_type, forecaster):
    return next(c for c in report["categories"]
                if (c["market_type"], c["forecaster"]) == (market_type, forecaster))


# --- the one count ----------------------------------------------------------

def test_a_categorys_count_is_its_forecasters_questions(tmp_path):
    """Thirty questions answered twice, four games asked at two rungs, and the
    reasoning pass on twenty of the same games: the statistical model's line
    is 38 questions (68 forecasts), the reasoning pass's 20 -- where the page
    said 68 and 20."""
    conn = _world(tmp_path)
    _twice(conn, range(1, 31))
    for g in range(31, 35):
        _forecast(conn, g, line=-3.5, pass_kind="early")
        _forecast(conn, g, line=-6.5, pass_kind="final", outcome=0)
    for g in range(1, 21):
        _forecast(conn, g, predictor="llm", outcome=g % 2)
    conn.commit()
    report = views.corrections_report(conn, "nfl")
    stat, llm = _category(report, "spread", "statistical"), _category(report, "spread", "llm")
    assert (stat["settled"], stat["forecasts"], stat["recounted"]) == (38, 68, 38)
    assert (llm["settled"], llm["forecasts"]) == (20, 20)
    assert stat["forecasters_counted"] == ["statistical"]
    assert stat["progress"]["line"] == "38 of 50 settled questions"
    assert stat["progress"]["note"] == "12 more settled questions"
    assert stat["label"] == "point spread, statistical"
    assert llm["label"] == "point spread, reasoning pass"
    rows = correction.settled_rows(conn, sport="nfl", market_type="spread",
                                   forecaster="statistical")
    assert (len(rows), bet.count(rows)) == (68, 38)


def test_the_door_counts_one_forecasters_whole_category_and_nothing_else(tmp_path):
    conn = _world(tmp_path)
    for bad in (None, "both", "all"):
        with pytest.raises(correction.PooledCount):
            correction.settled_rows(conn, sport="nfl", market_type="spread",
                                    forecaster=bad)
    # ONE PROP TYPE IS NOT THE CATEGORY: a correction is fitted for them all
    with pytest.raises(correction.PooledCount, match="every prop type together"):
        correction.settled_rows(conn, sport="nfl", market_type="receiving_yards",
                                forecaster="statistical")
    with pytest.raises(config.CrossSportAggregation):
        correction.settled_rows(conn, sport=None, market_type="spread",
                                forecaster="statistical")


def test_a_row_counts_if_settled_before_the_instant_and_never_if_withdrawn(tmp_path):
    """A void never counts toward a gate (ruling 1, 2026-09-24): the record as
    it stands -- the page, the fit being made -- leaves out every void on it,
    whatever its stamp. Only a fit's own count, read as its gate read it
    (`as_it_stood`), keeps a row a void written after the fit withdrew."""
    conn = _world(tmp_path)
    kept = _forecast(conn, 1)
    late = _forecast(conn, 2, resolved="2026-07-01T00:00:00Z")
    voided = _forecast(conn, 3)
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, '2026-08-01T00:00:00Z', 'withdrawn in a test world')",
                 (voided,))
    conn.commit()

    def ids(at, **kw):
        return {r["id"] for r in correction.settled_rows(
            conn, sport="nfl", market_type="spread", forecaster="statistical",
            before_utc=at, **kw)}

    assert ids(FIT_AT) == {kept}
    assert ids("2026-09-01T00:00:00Z") == {kept, late}
    assert ids(FIT_AT, as_it_stood=True) == {kept, voided}   # the void came later
    assert ids("2026-09-01T00:00:00Z", as_it_stood=True) == {kept, late}
    assert late and kept


def test_a_forecast_withdrawn_by_a_void_stamped_after_now_is_never_counted(tmp_path):
    """THE PROVER (2026-09-29): the door read only voids stamped at or before
    its instant, so a question withdrawn by a void stamped after now -- by
    hand, or a clock -- stayed on the page's count, in the recount beside it
    (which read it the same way, so the guard saw nothing), in a version's
    forward count and in the fit's own gate, while the fit's training rows
    left it out. Fifty questions, one withdrawn so: 49 everywhere, and the
    category is not fitted."""
    conn = _world(tmp_path)
    for g in range(1, 51):
        _forecast(conn, g, market="moneyline", line=None, outcome=g % 2,
                  version=1)
    withdrawn = _forecast(conn, 51, market="moneyline", line=None, outcome=1,
                          version=1)
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, '2099-01-01T00:00:00Z', 'withdrawn, stamped late')",
                 (withdrawn,))
    conn.commit()
    now = db.utcnow()
    page = _category(views.corrections_report(conn, "nfl"), "moneyline", "statistical")
    assert (page["settled"], page["recounted"], page["forecasts"]) == (50, 50, 50)
    rows = correction.settled_rows(conn, sport="nfl", market_type="moneyline",
                                   forecaster="statistical", before_utc=now)
    assert withdrawn not in {r["id"] for r in rows}
    from gridiron import recount
    assert recount.correction(conn, sport="nfl", market_type="moneyline",
                              predictor="statistical", before_utc=now) == 50
    # ... and one less, so the fifty is not reached: never fitted on 49
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " SELECT id, '2099-01-01T00:00:00Z', 'withdrawn, stamped late'"
                 "  FROM predictions WHERE game_id = 'g1'")
    conn.commit()
    report = correction.refit_all(conn, now=FIT_AT)
    cat = report["categories"][0]
    assert (cat["questions"], cat["n_train"]) == (49, 49)
    assert report["eligible"] == 0
    assert conn.execute("SELECT n_train FROM calibration_corrections").fetchone()[0] == 0
    page = _category(views.corrections_report(conn, "nfl"), "moneyline", "statistical")
    assert page["settled"] == 49
    assert page["progress"]["line"] == "49 of 50 settled questions"


# --- the fit's own gate -----------------------------------------------------

def test_the_fits_gate_counts_questions_and_the_page_states_that_count(tmp_path):
    """Sixty forecasts that are thirty questions are not fitted (the gate
    counts questions from question 16's release), and the page's line states
    the thirty the gate read, not the sixty."""
    conn = _world(tmp_path)
    _twice(conn, range(1, 31), market="moneyline", line=None)
    report = correction.refit_all(conn, now=FIT_AT)
    cat = report["categories"][0]
    assert (cat["questions"], cat["n_train"]) == (30, 60)
    assert cat["status"] == "corrections begin at 50 settled questions - 30 so far"
    assert report["eligible"] == 0
    stored = conn.execute("SELECT n_train, slope, intercept FROM"
                          " calibration_corrections").fetchone()
    assert tuple(stored) == (0, 1.0, 0.0)
    page = _category(views.corrections_report(conn, "nfl"), "moneyline", "statistical")
    assert page["settled"] == cat["questions"] == 30


def test_the_fit_is_still_made_from_every_settled_forecast(tmp_path):
    """The ruling moves the gate, not what a correction is fitted on: sixty
    questions answered twice clear the gate and are fitted on all 120."""
    conn = _world(tmp_path)
    _twice(conn, range(1, 61), market="moneyline", line=None)
    report = correction.refit_all(conn, now=FIT_AT)
    cat = report["categories"][0]
    assert (cat["questions"], cat["n_train"]) == (60, 120)
    assert conn.execute("SELECT n_train FROM calibration_corrections").fetchone()[0] == 120
    assert len(correction.training_rows(
        conn, sport="nfl", market_type="moneyline", forecaster="statistical",
        before_utc=FIT_AT)) == 120


def test_two_rungs_are_two_questions_at_the_gate(tmp_path):
    conn = _world(tmp_path)
    for g in range(1, 26):
        _forecast(conn, g, line=-3.5, pass_kind="early", outcome=g % 2)
        _forecast(conn, g, line=-6.5, pass_kind="final", outcome=(g + 1) % 2)
    conn.commit()
    cat = correction.refit_all(conn, now=FIT_AT)["categories"][0]
    assert (cat["questions"], cat["n_train"]) == (50, 50)
    assert conn.execute("SELECT n_train FROM calibration_corrections").fetchone()[0] == 50


def test_the_weekly_refit_says_it_counted_questions(tmp_path):
    from gridiron import tasks

    conn = _world(tmp_path)
    _twice(conn, range(1, 61), market="moneyline", line=None)
    _result, detail, _report = tasks._run_recalibrate(conn)
    assert "had at least 50 settled questions" in detail


# --- the forward count and the learning panel --------------------------------

def test_the_forward_count_is_each_question_once(tmp_path):
    conn = _world(tmp_path)
    _fit(conn, n_train=120, active_from="2025-11-01T00:00:00Z",
         fitted_utc="2025-11-01T00:00:00Z")
    _twice(conn, range(1, 11), version=1)
    for g in range(11, 16):
        _forecast(conn, g, line=-3.5, pass_kind="early", version=1)
        _forecast(conn, g, line=-6.5, pass_kind="final", version=1, outcome=0)
    conn.commit()
    forward = correction.version_report(conn, sport="nfl", market_type="spread",
                                        forecaster="statistical")[0]["forward"]
    assert (forward["n"], forward["forecasts"]) == (20, 30)
    assert forward["forecasters_counted"] == ["statistical"]
    report = views.corrections_report(conn, "nfl")
    assert _category(report, "spread", "statistical")["versions"][0]["forward"][
        "recounted"] == 20


def test_the_learning_panel_states_the_categorys_count_every_prop_type_together(tmp_path):
    """Question 31's note: each prop row states the category's count and says
    it is every prop type together; no category split."""
    conn = _world(tmp_path)
    for g in range(1, 31):
        for pass_kind in ("early", "final"):
            _forecast(conn, g, market="prop", prop_type="receiving_yards",
                      subject=f"Player {g} receiving_yards", line=55.5,
                      pass_kind=pass_kind, outcome=g % 2)
    for g in range(31, 56):
        for pass_kind in ("early", "final"):
            _forecast(conn, g, market="prop", prop_type="rushing_yards",
                      subject=f"Player {g} rushing_yards", line=44.5,
                      pass_kind=pass_kind, outcome=g % 2)
    conn.commit()
    got = views.learning(conn, "nfl")
    props = [r for r in got["categories"]
             if r["market"] in config.SPORT_PROP_MARKETS["nfl"]]
    assert props and all(r["n"] == 55 for r in props)
    for r in props:
        assert "55 settled questions, every prop type together" in r["status_words"]
        assert audit.plain_words_violations(r["status_words"]) == []
    assert got["n"] == len(got["categories"])
    report = views.corrections_report(conn, "nfl")
    prop = _category(report, "prop", "statistical")
    assert prop["label"] == "player props, every prop type together, statistical"
    assert prop["settled"] == 55


def test_a_prop_settled_between_two_prop_rows_is_no_fault(tmp_path, monkeypatch):
    """ONE INSTANT (the prover, 2026-09-29; question 22's precedent): every
    prop row states the one prop category's count, and the guard refuses one
    category stated two ways. Each row read its count in an instant of its
    own, so a prop forecast settled between two rows -- the resolver writes
    while the Record page is read -- made an honest panel say 10 and 11 and
    answer 500. The panel counts the instant it read; the next read counts
    the new one."""
    from gridiron import drift

    path = tmp_path / "q16.db"
    conn = _world(tmp_path)
    for g in range(1, 11):
        _forecast(conn, g, market="prop", prop_type="receiving_yards",
                  subject=f"Player {g} receiving_yards", line=55.5,
                  outcome=g % 2)
    conn.commit()
    shipped = drift.report
    written = []

    def a_row_then_a_settled_prop(conn, **kw):
        report = shipped(conn, **kw)
        # once, after the first prop row: the resolver runs once
        if not written and kw.get("market") in config.SPORT_PROP_MARKETS["nfl"]:
            other = db.connect(path)
            _forecast(other, 11, market="prop", prop_type="rushing_yards",
                      subject="Player 11 rushing_yards", line=44.5)
            other.commit()
            other.close()
            written.append(True)
        return report

    monkeypatch.setattr(drift, "report", a_row_then_a_settled_prop)
    props = [r for r in views.learning(conn, "nfl")["categories"]
             if r["market"] in config.SPORT_PROP_MARKETS["nfl"]]
    assert written and len(props) > 1 and {r["n"] for r in props} == {10}
    monkeypatch.setattr(drift, "report", shipped)
    props = [r for r in views.learning(conn, "nfl")["categories"]
             if r["market"] in config.SPORT_PROP_MARKETS["nfl"]]
    assert {r["n"] for r in props} == {11}


def test_a_ufc_category_says_its_cards_are_counted_together():
    assert language.correction_category_label("ufc", "moneyline", "statistical") == \
        "moneyline, every card together, statistical"
    line = language.correction_status_line(False, 49, 50, None, False,
                                           scope=language.EVERY_CARD)
    assert "49 of 50 settled questions, every card together" in line
    assert language.correction_gate_progress(49, 50)["note"] == "1 more settled question"


def test_a_fit_is_never_called_not_yet_fitted_and_is_described_by_its_forecasts():
    """UFC's fits of 28 September: 85 forecasts beside 49 questions. The line
    said "not yet fitted: 49 of 50 settled rows" while a fit stood."""
    line = language.correction_status_line(
        True, 49, 50, "2026-09-28T13:00:01Z", False, n_train=85)
    assert "not yet fitted" not in line
    assert line.startswith("49 of 50 settled questions; fitted on Monday 28 "
                           "September on 85 settled forecasts, and NOT in force")
    active = language.correction_status_line(
        True, 260, 50, "2026-09-28T13:00:01Z", True, n_train=364)
    assert active == ("260 settled questions; in force since Monday 28 "
                      "September, fitted on 364 settled forecasts")


# --- the guard, the API and the gate ----------------------------------------

def _broken_doors():
    real = correction.settled_rows

    def every_forecast(conn, **kw):
        return [dict(dict(r), subject=f"{r['subject']} #{r['id']}")
                for r in real(conn, **kw)]

    def without_the_forecaster(conn, *, forecaster, **kw):
        return [r for f in correction.FORECASTERS
                for r in real(conn, forecaster=f, **kw)]

    def without_the_rung(conn, **kw):
        return [dict(dict(r), line_asked=None) for r in real(conn, **kw)]

    return {"counts 68 settled questions where the recount": every_forecast,
            "two forecasters pooled": without_the_forecaster,
            "counts 34 settled questions where the recount": without_the_rung}


def test_a_pooled_or_duplicated_count_is_refused_by_the_builders_the_api_and_the_gate(
        tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn = _world(tmp_path)
    _twice(conn, range(1, 31))
    for g in range(31, 35):
        _forecast(conn, g, line=-3.5, pass_kind="early")
        _forecast(conn, g, line=-6.5, pass_kind="final", outcome=0)
    for g in range(1, 21):
        _forecast(conn, g, predictor="llm", outcome=g % 2)
    conn.commit()
    audit.check_the_correction_counts_are_never_pooled(conn)        # lawful
    for words, door in _broken_doors().items():
        monkeypatch.setattr(correction, "settled_rows", door)
        for build in (views.corrections_report, views.learning):
            with pytest.raises(calibration.MergedCurve, match=words):
                build(conn, "nfl")
        with pytest.raises(audit.LawViolation, match="A CORRECTION COUNT IS POOLED"):
            audit.check_the_correction_counts_are_never_pooled(conn)
        monkeypatch.undo()
    # A BUILDER STATING THE FORECASTS WHERE THE QUESTIONS GO
    real = views._correction_count

    def stating_forecasts(conn, **kw):
        got = real(conn, **kw)
        got["settled"] = got["forecasts"]
        return got

    monkeypatch.setattr(views, "_correction_count", stating_forecasts)
    with pytest.raises(calibration.MergedCurve, match="counts 68 settled for 38"):
        views.corrections_report(conn, "nfl")
    # THE API ANSWERS 500 rather than serve it
    token = "test-token-for-the-correction-counts"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "q16.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            answers = {route: client.get(route, params={"sport": "nfl"})
                       for route in ("/api/scorecard", "/api/learning")}
    finally:
        api.set_database(None)
    for route, response in answers.items():
        assert response.status_code == 500, route
        assert "IN THE CORRECTION GATES" in response.json()["detail"], route


def test_the_guard_refuses_a_total_a_twice_stated_category_and_a_line_of_another_count(tmp_path):
    conn = _world(tmp_path)
    _twice(conn, range(1, 11))
    report = views.corrections_report(conn, "nfl")
    for planted, words in (
            (dict(report, settled=10), "carries \\['settled'\\]"),
            (dict(report, categories=report["categories"] * 2, n=2), "stated twice"),
            (dict(report, categories=[dict(report["categories"][0],
                                            progress=language.correction_gate_progress(20, 50))]),
             "not its own count"),
            (dict(report, categories=[dict(report["categories"][0],
                                            label="spread, statistical")]),
             "not named for its category"),
            (dict(report, n=5), "a sum of their counts")):
        with pytest.raises(calibration.MergedCurve, match=words):
            calibration.assert_no_pooled_correction_counts(planted)


# --- the label --------------------------------------------------------------

def _label(conn, fid, *, at="2026-06-02T00:00:00Z", gate=50, used=56, corrected=28):
    conn.execute(
        "INSERT INTO correction_gate_labels (correction_id, labelled_utc,"
        " verdict, gate, count_used, corrected_count, reason) VALUES"
        " (?, ?, 'fitted_below_its_gate', ?, ?, ?, 'a label in a test world')",
        (fid, at, gate, used, corrected))


def _labelled_world(tmp_path):
    """A fit of 56 forecasts on 28 questions (short), one of 120 on 60
    (clear), a placeholder, and a short fit carrying an activation."""
    conn = _world(tmp_path)
    _twice(conn, range(1, 29))
    short = _fit(conn)
    _twice(conn, range(1, 61), market="moneyline", line=None, predictor="llm")
    clear = _fit(conn, market="moneyline", forecaster="llm", n_train=120)
    for g in range(1, 21):
        _forecast(conn, g, market="total", line=44.5, outcome=g % 2)
    conn.commit()
    placeholder = _fit(conn, market="total", model=False)
    _twice(conn, range(61, 89), predictor="llm")
    in_force = _fit(conn, forecaster="llm", active_from=FIT_AT)
    return conn, short, clear, placeholder, in_force


def test_the_selection_is_by_rule_from_each_fits_own_record(tmp_path):
    conn, short, clear, placeholder, in_force = _labelled_world(tmp_path)
    got = {g["id"]: g for g in correction.below_their_gates(conn)}
    assert set(got) == {short, in_force}
    assert (got[short]["count_used"], got[short]["counted"],
            got[short]["corrected_count"], got[short]["gate"]) == (56, 56, 28, 50)
    assert got[in_force]["active"] and not got[short]["active"]
    # A FIT FROM THE RELEASE ON is gated on the key, so it is never selected
    _twice(conn, range(89, 119), market="moneyline", line=None)
    correction.refit_all(conn, now="2026-07-01T00:00:00Z")
    assert set(g["id"] for g in correction.below_their_gates(conn)) == {short, in_force}


def test_a_label_is_true_of_its_fits_own_record(tmp_path):
    conn, short, clear, placeholder, in_force = _labelled_world(tmp_path)
    for fid, kw, words in (
            (clear, dict(used=120, corrected=60), "only by its own"),
            (clear, dict(used=120, corrected=40), "only by its own"),
            (placeholder, dict(used=0, corrected=20), "only by its own"),
            (short, dict(corrected=27), "only by its own"),
            (short, dict(used=50), "only by its own"),
            (short, dict(gate=40), "only by its own"),
            (short, dict(at="2026-05-31T00:00:00Z"), "after the fit"),
            (in_force, {}, "operator")):
        with pytest.raises(sqlite3.IntegrityError, match=words):
            _label(conn, fid, **kw)
        conn.rollback()
    for ids in ([clear], [placeholder], [in_force]):
        with pytest.raises(correction.Refused):
            correction.write_labels(conn, ids)
    assert conn.execute("SELECT COUNT(*) FROM correction_gate_labels").fetchone()[0] == 0
    assert correction.write_labels(conn, [short], now="2026-06-02T00:00:00Z") == \
        {"written": 1, "already": 0}
    assert correction.write_labels(conn, [short]) == {"written": 0, "already": 1}
    row = conn.execute("SELECT * FROM correction_gate_labels").fetchone()
    assert (row["gate"], row["count_used"], row["corrected_count"],
            row["verdict"]) == (50, 56, 28, correction.FITTED_BELOW_ITS_GATE)


def test_a_label_is_permanent(tmp_path):
    conn, short, *_ = _labelled_world(tmp_path)
    correction.write_labels(conn, [short], now="2026-06-02T00:00:00Z")
    for sql, words in (
            ("INSERT INTO correction_gate_labels (correction_id, labelled_utc,"
             " verdict, gate, count_used, corrected_count, reason) VALUES"
             f" ({short}, '2026-06-05T00:00:00Z', 'fitted_below_its_gate', 50,"
             " 56, 28, 'a second label, refused')", "never replaced"),
            ("INSERT OR REPLACE INTO correction_gate_labels (correction_id,"
             " labelled_utc, verdict, gate, count_used, corrected_count, reason)"
             f" VALUES ({short}, '2026-06-05T00:00:00Z', 'fitted_below_its_gate',"
             " 50, 56, 28, 'a replacing label, refused')", "never replaced"),
            ("UPDATE correction_gate_labels SET reason = 'rewritten afterwards'",
             "cannot be rewritten"),
            ("DELETE FROM correction_gate_labels", "never deleted")):
        with pytest.raises(sqlite3.IntegrityError, match=words):
            conn.execute(sql)
        conn.rollback()


def _reads_as(conn, first, then):
    """A function the connection defines, answering `first` the first time
    it is asked and `then` after: a number read twice, as SQLite reads a
    rowid for one row of values (question 13's finding)."""
    asked = {"n": 0}

    def number():
        asked["n"] += 1
        return first if asked["n"] == 1 else then
    conn.create_function("the_number", 0, number)
    return asked


def test_a_labels_number_is_read_once_so_the_rules_read_the_row_that_lands(tmp_path):
    """THE PROVER (2026-09-29). Keyed by the table's rowid, the fit's number
    in one row of values was worked out twice -- once for the rules, once for
    the row -- so a label every rule read as the short fit's landed on the
    fit in force, and the door then passed over the only correction in
    force; and under OR REPLACE, read as an unlabelled fit with the same
    counts, it wrote over a stored label. WITHOUT ROWID, the number is worked
    out once: the label lands on the fit the rules read."""
    conn, short, clear, placeholder, in_force = _labelled_world(tmp_path)
    table = conn.execute("SELECT sql FROM sqlite_master WHERE name ="
                         " 'correction_gate_labels'").fetchone()[0]
    assert " ".join(table.split()).endswith(") WITHOUT ROWID")
    served = correction.active_correction(conn, sport="nfl", market_type="spread",
                                          forecaster="llm",
                                          at_utc="2026-06-04T00:00:00Z")
    assert served["id"] == in_force
    label = ("INSERT{how} INTO correction_gate_labels (correction_id,"
             " labelled_utc, verdict, gate, count_used, corrected_count, reason)"
             " VALUES (the_number(), ?, 'fitted_below_its_gate', 50, 56, 28,"
             " 'a label read twice in a test world')")
    asked = _reads_as(conn, short, in_force)
    conn.execute(label.format(how=""), ("2026-06-02T00:00:00Z",))
    conn.commit()
    assert asked["n"] == 1
    assert [r[0] for r in conn.execute(
        "SELECT correction_id FROM correction_gate_labels")] == [short]
    assert correction.active_correction(
        conn, sport="nfl", market_type="spread", forecaster="llm",
        at_utc="2026-06-04T00:00:00Z")["id"] == in_force
    # A TWIN: another short fit with the same counts, unlabelled. Read as the
    # twin, the replacing insert labels the twin -- the short fit's label,
    # its stamp and its reason stay exactly as written.
    _twice(conn, range(89, 117), market="moneyline", line=None)
    twin = _fit(conn, market="moneyline")
    stored = [tuple(r) for r in conn.execute("SELECT * FROM correction_gate_labels")]
    asked = _reads_as(conn, twin, short)
    conn.execute(label.format(how=" OR REPLACE"), ("2026-06-09T00:00:00Z",))
    conn.commit()
    assert asked["n"] == 1
    rows = {r["correction_id"]: tuple(r) for r in conn.execute(
        "SELECT * FROM correction_gate_labels")}
    assert set(rows) == {short, twin} and [rows[short]] == stored
    # NAMED OUTRIGHT, a text or a real number is the fit's own, and refused
    for spelled in (f"'{short}'", f"{short}.0"):
        with pytest.raises(sqlite3.IntegrityError, match="never replaced"):
            conn.execute(label.replace("the_number()", spelled).format(
                how=" OR REPLACE"), ("2026-06-09T00:00:00Z",))
        conn.rollback()


def test_a_label_is_stamped_when_it_is_written_in_the_one_format(tmp_path):
    """THE PROVER (2026-09-29): a label stamped in 2099, and one stamped
    '2026-06-02 by hand' (which sorts after the fit), were stored."""
    conn, short, *_ = _labelled_world(tmp_path)
    for stamp in ("2099-01-01T00:00:00Z", "2026-06-02 by hand",
                  "2026-06-02T00:00:00", "2026-06-02T00:00:00.5Z"):
        with pytest.raises(sqlite3.IntegrityError, match="stamped when it is written"):
            _label(conn, short, at=stamp)
        conn.rollback()
    _label(conn, short, at=db.utcnow())
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM correction_gate_labels").fetchone()[0] == 1


def test_a_labelled_fit_is_never_activated(tmp_path):
    conn, short, *_ = _labelled_world(tmp_path)
    correction.write_labels(conn, [short], now="2026-06-02T00:00:00Z")
    later = "2026-06-03T00:00:00Z"
    for sql, params in (
            ("INSERT OR REPLACE INTO calibration_corrections (id, sport,"
             " market_type, forecaster, version, fitted_utc, n_train, slope,"
             " intercept, active_from, status) VALUES (?, 'nfl', 'spread',"
             " 'statistical', 1, ?, 56, 0.8, 0.1, ?, 'active')", (short, FIT_AT, later)),
            ("REPLACE INTO calibration_corrections (sport, market_type,"
             " forecaster, version, fitted_utc, n_train, slope, intercept,"
             " active_from, status) VALUES ('nfl', 'spread', 'statistical', 1,"
             " ?, 56, 0.8, 0.1, ?, 'active')", (FIT_AT, later)),
            ("REPLACE INTO calibration_corrections (rowid, sport, market_type,"
             " forecaster, version, fitted_utc, n_train, slope, intercept,"
             " active_from, status) VALUES (?, 'nfl', 'spread', 'statistical',"
             " 9, ?, 56, 0.8, 0.1, ?, 'active')", (short, FIT_AT, later))):
        with pytest.raises(sqlite3.IntegrityError, match="can never be activated"):
            conn.execute(sql, params)
        conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE calibration_corrections SET active_from = ?"
                     " WHERE id = ?", (later, short))
    conn.rollback()
    # A NEW VERSION of the category is a new fit and lands as ever
    correction.record_fit(conn, sport="nfl", market_type="spread",
                          forecaster="statistical",
                          model=correction.Platt(slope=0.9, intercept=0.0, n_train=60),
                          status="active", active_from=later, fitted_utc=later)
    # THE DOOR, ON A RECORD PUT IN FORCE BY HAND: the labelled fit is passed
    # over, and the newest activation that is not labelled is in force
    conn.execute("DROP TRIGGER calibration_corrections_no_update")
    conn.execute("UPDATE calibration_corrections SET active_from = ?"
                 " WHERE id = ?", ("2026-06-02T12:00:00Z", short))
    conn.commit()
    at = "2026-06-02T18:00:00Z"
    assert correction.active_correction(conn, sport="nfl", market_type="spread",
                                        forecaster="statistical", at_utc=at) is None
    got = correction.active_correction(conn, sport="nfl", market_type="spread",
                                       forecaster="statistical",
                                       at_utc="2026-06-04T00:00:00Z")
    assert got["version"] == 2


def test_a_record_the_schema_has_not_reached_holds_no_label(tmp_path):
    conn = _world(tmp_path)
    _fit(conn, n_train=60, active_from=FIT_AT)
    conn.execute("DROP TRIGGER calibration_corrections_labelled_never_replaced")
    conn.execute("DROP TABLE correction_gate_labels")
    conn.commit()
    got = correction.active_correction(conn, sport="nfl", market_type="spread",
                                       forecaster="statistical")
    assert got["version"] == 1
    assert correction.labels(conn, sport="nfl", market_type="spread",
                             forecaster="statistical") == {}
    with pytest.raises(RuntimeError, match="has not been opened"):
        correction.write_labels(conn, [1])


def test_the_label_rule_pins_the_gate_and_the_key_as_declared():
    """The rule pins fifty as the re-grade pins its bar, and counts a
    question by the one key, written out: both held to their sources."""
    assert correction.MIN_TRAIN == 50
    rule = " ".join(audit._schema_rule_text(audit.LABEL_KEY_RULE).split())
    assert "NEW.gate = 50" in rule
    assert bet.same("q", "p") in rule
    assert audit.distinct_bet_key_faults() == []
    # a rule keyed without the rung is seen
    schema = (config.PACKAGE_ROOT / "schema.sql").read_text(encoding="utf-8")
    widened = schema.replace("AND q.line_asked IS p.line_asked", "", 1)
    assert bet.same("q", "p") not in " ".join(
        audit._schema_rule_text(audit.LABEL_KEY_RULE, widened).split())


def test_the_page_names_a_labelled_fit_in_plain_words_with_its_counts(tmp_path):
    conn, short, *_ = _labelled_world(tmp_path)
    correction.write_labels(conn, [short], now="2026-06-02T00:00:00Z")
    category = _category(views.corrections_report(conn, "nfl"), "spread", "statistical")
    assert category["below_its_gate"] == [
        "Version 1, fitted on Monday 1 June, was fitted below its gate: its 56 "
        "settled forecasts are 28 questions, under the 50 it needs, so it can "
        "never be in force."]
    assert audit.plain_words_violations(category["below_its_gate"][0]) == []
    gates = views.scorecard(conn, "nfl")["gates"]
    named = [g for g in gates if g["name"] == "A correction for point spread, statistical"]
    assert named and "fitted below its gate" in named[0]["why"]
    row = next(r for r in views.learning(conn, "nfl")["categories"]
               if r["market"] == "spread")
    assert "was fitted below its gate" in row["status_words"]
    assert "can never be in force" in row["status_words"]


# --- the schema reaches an older record through db.init ----------------------

_NEW_OBJECTS = {
    ("table", "correction_gate_labels"),
    ("trigger", "correction_gate_label_is_its_fits_own_record"),
    ("trigger", "correction_gate_label_comes_after_its_fit"),
    ("trigger", "correction_gate_labels_never_replaced"),
    ("trigger", "correction_gate_label_never_on_a_fit_in_force"),
    ("trigger", "correction_gate_labels_no_update"),
    ("trigger", "correction_gate_labels_no_delete"),
    ("trigger", "calibration_corrections_labelled_never_replaced"),
}


def test_an_older_record_gains_the_label_and_its_rules_through_init_and_no_row_moves(tmp_path):
    conn = _world(tmp_path)
    _twice(conn, range(1, 29))
    _fit(conn)
    for kind, name in sorted(_NEW_OBJECTS, reverse=True):
        conn.execute(f"DROP {kind.upper()} {name}")
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
    assert set(after) - set(before) == _NEW_OBJECTS
    assert all(after[k] == before[k] for k in before)
    fresh = db.open_db(tmp_path / "fresh.db")
    try:
        for key in _NEW_OBJECTS:
            assert after[key] == objects(fresh)[key]
        order = "SELECT name FROM sqlite_master WHERE type = 'trigger' AND" \
                " tbl_name IN ('calibration_corrections', 'correction_gate_labels')" \
                " ORDER BY rowid"
        assert [r[0] for r in conn.execute(order)] == [r[0] for r in fresh.execute(order)]
    finally:
        fresh.close()
    assert rows(conn) == stored
    db.init(conn)
    assert objects(conn) == after and rows(conn) == stored


# --- the isolation scan reads the door ---------------------------------------

def test_the_isolation_scan_reads_a_query_written_as_an_fstring(tmp_path):
    """The count door selects `bet.columns('p')` in an f-string, which the
    scan did not read until 2026-09-29: its tables and bounds are read now,
    and a table worked out at run time is refused by name."""
    assert audit.correction_reaches() == []
    assert audit.correction_training_is_bounded() == []
    planted = tmp_path / "correction.py"
    planted.write_text(textwrap.dedent('''
        def door(conn, bet, table):
            conn.execute(f"SELECT {bet} FROM predictions p JOIN games g"
                         " ON g.id = p.game_id WHERE p.outcome = 1")
            conn.execute(f"SELECT {bet} FROM {table} p")
    '''), encoding="utf-8")
    reaches = audit.correction_reaches(planted)
    assert any("'games'" in r for r in reaches)
    assert any(audit.FSTRING_PART in r for r in reaches)
    assert audit.correction_training_is_bounded(planted)


# --- the tool ------------------------------------------------------------------

def _tool():
    path = config.PACKAGE_ROOT.parent / "tools" / "label_corrections_below_the_gate.py"
    spec = importlib.util.spec_from_file_location("q16_label_tool_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _selected(fid, **kw):
    return dict({"id": fid, "sport": "ufc", "market_type": "moneyline",
                 "forecaster": "statistical", "version": 3,
                 "fitted_utc": "2026-09-21T22:11:39Z", "gate": 50,
                 "count_used": 56, "counted": 56, "corrected_count": 32,
                 "active": False, "already": False, "reason": "test"}, **kw)


def test_the_tool_writes_only_the_ruled_set_and_names_the_rest(capsys):
    """Question 31, ruled (B) and (B) 2026-09-29: "Label every fitted row
    written before Q16's release that falls short on the key: 33, 59, 61, 63,
    81, 85, 86, 87, 89." THE POPULATION IS EVERY FIT ON THE RECORD, read by
    the rule: a fit from the release on is gated on the key and never
    selected. Until that ruling the population was the 63 read by the instant
    question 23 was ruled (checked to be 63), the ruled set the four among
    them, and 81, 85, 86, 87 and 89 waited."""
    tool = _tool()
    assert tool.RULED == (33, 59, 61, 63, 81, 85, 86, 87, 89)
    assert tool.LEFT_BY_RULING == ()
    assert tool.POPULATION == "every fitted row written before question 16's release"
    # NO INSTANT AND NO SIZE: the 63-by-instant check is gone, not left idle
    for gone in ("RULED_AMONG_THE_FITS_WRITTEN_BEFORE", "RULED_POPULATION_SIZE",
                 "population"):
        assert not hasattr(tool, gone), gone
    selected = [_selected(i) for i in (33, 59, 61, 63, 81, 85, 86, 87, 89)]
    assert tool.check(selected) == [33, 59, 61, 63, 81, 85, 86, 87, 89]
    for broken, words in (
            (selected + [_selected(40)], "Selected and not ruled on"),
            ([g for g in selected if g["id"] != 59], "does not select them"),
            ([g for g in selected if g["id"] != 86], "does not select them"),
            ([dict(g, active=g["id"] == 61) for g in selected], "carry an activation"),
            ([dict(g, active=g["id"] == 87) for g in selected], "carry an activation"),
            ([dict(g, counted=55) if g["id"] == 33 else g for g in selected],
             "does not give back"),
            ([dict(g, counted=84) if g["id"] == 89 else g for g in selected],
             "does not give back")):
        with pytest.raises(SystemExit) as exc:
            tool.check(broken)
        assert exc.value.code == 2
        assert words in capsys.readouterr().out
    # A TENTH, written by the next weekly refit before the release and short
    # on the key, is selected by the same rule and refused, named, until ruled
    tenth = _selected(90, fitted_utc="2026-10-05T13:00:01Z", count_used=58,
                      counted=58, corrected_count=45)
    with pytest.raises(SystemExit) as exc:
        tool.check(selected + [tenth])
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "the rule selects 10 fits and the ruling names 9" in out
    assert "Selected and not ruled on:\n  fit 90 (ufc moneyline, statistical, " \
           "version 3, fitted 2026-10-05T13:00:01Z): 58 settled forecasts past " \
           "its gate of 50, 45 questions on the key\n" in out


# --- the rehearsal's shape (question 31) --------------------------------------

#: The instants the record's fits were written at (FOLLOWUPS, question 16's
#: measurement): six early refits, fit 33's at 06:29:40Z and UFC's at
#: 22:11:39Z on 21 September, and the weekly refit of 28 September 13:00:01Z,
#: after question 23 was ruled at 01:50:37Z that day.
_EARLY = ("2026-08-31T13:00:00Z", "2026-09-02T13:00:00Z", "2026-09-04T13:00:00Z",
          "2026-09-07T13:00:00Z", "2026-09-10T13:00:00Z", "2026-09-14T13:00:00Z")
_AT_33, _AT_UFC, _AT_WEEKLY = ("2026-09-21T06:29:40Z", "2026-09-21T22:11:39Z",
                               "2026-09-28T13:00:01Z")
_Q23_RULED = "2026-09-28T01:50:37Z"

_UFC_DIST, _UFC_ML, _UFC_RDS = (("ufc", m, "statistical")
                                for m in ("distance", "moneyline", "rounds"))
_UFC_ML_LLM = ("ufc", "moneyline", "llm")
_NFL_SPREAD = ("nfl", "spread", "statistical")
_MLB_TOTAL_LLM = ("mlb", "total", "llm")
_MLB_ML = ("mlb", "moneyline", "statistical")
_MLB_SPREAD = ("mlb", "spread", "statistical")
_UFC_DIST_LLM, _UFC_RDS_LLM = ("ufc", "distance", "llm"), ("ufc", "rounds", "llm")

#: The 26 categories the weekly refit of 28 September wrote, in its own order
#: (`categories_in_the_record`: sport, market type, forecaster) -- fits 64-89.
_WEEKLY = sorted(
    [("cfb", m, f) for m in ("moneyline", "spread", "total")
     for f in ("llm", "statistical")]
    + [("mlb", "moneyline", "llm"), _MLB_ML, ("mlb", "prop", "llm"),
       ("mlb", "prop", "statistical"), _MLB_SPREAD, _MLB_TOTAL_LLM,
       ("mlb", "total", "statistical"),
       ("nfl", "moneyline", "llm"), ("nfl", "moneyline", "statistical"),
       ("nfl", "prop", "statistical"), ("nfl", "spread", "llm"), _NFL_SPREAD,
       ("nfl", "total", "llm"), ("nfl", "total", "statistical")]
    + [("ufc", m, f) for m in ("distance", "moneyline", "rounds")
       for f in ("llm", "statistical")])

#: What each category settled and when: (resolved, questions answered by both
#: passes, questions answered once), a game each. The nine's counts are the
#: record's (76 forecasts on 48 questions at fit 33's instant; UFC's 56 on 32
#: at 22:11:39Z and 85 on 49 at the weekly refit; NFL spread 60 on 41; UFC
#: moneyline, reasoning pass, 63 on 49); MLB moneyline is clear, and in force.
_SETTLED = {
    **{c: (("2026-09-21T12:00:00Z", 24, 8), ("2026-09-27T05:00:00Z", 12, 5))
       for c in (_UFC_DIST, _UFC_ML, _UFC_RDS)},
    _UFC_ML_LLM: (("2026-09-27T05:00:00Z", 14, 35),),
    _NFL_SPREAD: (("2026-09-27T05:00:00Z", 19, 22),),
    _MLB_TOTAL_LLM: (("2026-09-20T05:00:00Z", 28, 20), ("2026-09-27T05:00:00Z", 0, 10)),
    _MLB_ML: (("2026-09-20T05:00:00Z", 60, 0), ("2026-09-27T05:00:00Z", 10, 0)),
    _MLB_SPREAD: (("2026-09-12T05:00:00Z", 0, 55), ("2026-09-27T05:00:00Z", 0, 10)),
    # short on any count, so written as a placeholder: never labelled
    _UFC_DIST_LLM: (("2026-09-27T05:00:00Z", 15, 0),),
}


def _rehearsal_world(tmp_path):
    """The record's correction rows in the shape question 16's rehearsal read
    (2026-09-29): 89, numbered 1-89 in the record's order, each written as
    the record's refits wrote it -- FITTED on every settled forecast of its
    category when fifty or more had settled by its instant, a placeholder
    otherwise -- so the nine short on the key land at 33, 59, 61, 63, 81, 85,
    86, 87 and 89 in their categories and versions, and 71 (MLB moneyline,
    statistical, version 8) is in force, clear on the key."""
    path = tmp_path / "q31.db"
    conn = db.open_db(path)
    for sport in ("nfl", "mlb", "ufc"):
        for i in range(1, 81):
            conn.execute(
                "INSERT INTO games (id, sport, season, week, game_type, home,"
                " away, kickoff_utc, status, league_date, home_score, away_score)"
                " VALUES (?, ?, 2026, 1, 'REG', 'AAA', 'BBB',"
                " '2026-09-01T18:00:00Z', 'final', '2026-09-01', 3, 1)",
                (f"{sport}{i}", sport))
    rung = {"spread": -1.5, "total": 8.5, "rounds": 2.5}
    for (sport, market, forecaster), batches in _SETTLED.items():
        game = 0
        for resolved, twice, once in batches:
            for k in range(twice + once):
                game += 1
                for pass_kind in ("early", "final")[:2 if k < twice else 1]:
                    conn.execute(
                        "INSERT INTO predictions (sport, created_utc, game_id,"
                        " market_type, subject, line_asked, model_prob,"
                        " model_side, predictor, pass_kind, factor_set_version,"
                        " factors_json, reasoning, resolved_utc, outcome)"
                        " VALUES (?, ?, ?, ?, 'AAA', ?, 0.62, 'cover', ?, ?,"
                        " 'fs3', '{}', 'test', ?, ?)",
                        (sport, "2026-08-20T06:00:00Z" if pass_kind == "early"
                         else "2026-08-20T16:00:00Z", f"{sport}{game}", market,
                         rung.get(market), forecaster, pass_kind, resolved,
                         game % 2))
    conn.commit()

    def settled_by(category, at):
        return conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE sport = ? AND market_type = ?"
            " AND predictor = ? AND resolved_utc < ?", (*category, at)).fetchone()[0]

    special = {_UFC_DIST, _UFC_ML, _UFC_RDS, _UFC_ML_LLM, _NFL_SPREAD,
               _MLB_TOTAL_LLM, _MLB_ML, _MLB_SPREAD}
    fillers = itertools.cycle([c for c in _WEEKLY if c not in special])
    rounds = (
        (_EARLY[0], [_MLB_ML, _MLB_SPREAD, _NFL_SPREAD], 3),
        (_EARLY[1], [_MLB_ML], 4),
        (_EARLY[2], [_MLB_ML], 4),
        (_EARLY[3], [_MLB_ML, _UFC_DIST, _UFC_ML, _UFC_RDS, _UFC_ML_LLM], 1),
        (_EARLY[4], [_MLB_ML], 4),
        (_EARLY[5], [_MLB_ML, _MLB_SPREAD], 3),
        (_AT_33, [_MLB_TOTAL_LLM, _MLB_ML, _MLB_SPREAD, _NFL_SPREAD, _UFC_DIST,
                  _UFC_ML, _UFC_RDS, _UFC_ML_LLM], 17),
        (_AT_UFC, [_UFC_DIST_LLM, _UFC_DIST, _UFC_ML_LLM, _UFC_ML, _UFC_RDS_LLM,
                   _UFC_RDS], 0),
        (_AT_WEEKLY, _WEEKLY, 0))
    for at, categories, n_fillers in rounds:
        for category in list(categories) + [next(fillers) for _ in range(n_fillers)]:
            n = settled_by(category, at)
            sport, market, forecaster = category
            correction.record_fit(
                conn, sport=sport, market_type=market, forecaster=forecaster,
                model=(correction.Platt(slope=0.8, intercept=0.1, n_train=n)
                       if n >= correction.MIN_TRAIN else None),
                status="written as the record's refits wrote it",
                active_from=at if (category, at) == (_MLB_ML, _AT_WEEKLY) else None,
                fitted_utc=at)
    return conn, path


def test_the_nine_are_what_the_rule_selects_on_the_rehearsal_shape(tmp_path, capsys):
    """Question 31, ruled (B) and (B) 2026-09-29, on the record's shape: the
    rule selects exactly the nine the ruling names -- four written before
    question 23 was ruled, five by the weekly refit after it -- and no
    placeholder, though a placeholder is short on any count; the tool says it
    would write nine, writes nine, then none; the fit in force stays in force;
    and a refit from the release on, gated on the key, adds nothing the rule
    selects, so the selection over every fit stays the pre-release nine."""
    tool = _tool()
    conn, path = _rehearsal_world(tmp_path)
    fits = conn.execute("SELECT * FROM calibration_corrections ORDER BY id").fetchall()
    assert [f["id"] for f in fits] == list(range(1, 90))
    assert [f["id"] for f in fits if f["active_from"]] == [71]
    got = {g["id"]: g for g in correction.below_their_gates(conn)}
    assert tuple(sorted(got)) == tool.RULED
    assert {i: (g["sport"], g["market_type"], g["forecaster"], g["version"],
                g["count_used"], g["corrected_count"]) for i, g in got.items()} == {
        33: ("mlb", "total", "llm", 1, 76, 48),
        59: ("ufc", "distance", "statistical", 3, 56, 32),
        61: ("ufc", "moneyline", "statistical", 3, 56, 32),
        63: ("ufc", "rounds", "statistical", 3, 56, 32),
        81: ("nfl", "spread", "statistical", 3, 60, 41),
        85: ("ufc", "distance", "statistical", 4, 85, 49),
        86: ("ufc", "moneyline", "llm", 4, 63, 49),
        87: ("ufc", "moneyline", "statistical", 4, 85, 49),
        89: ("ufc", "rounds", "statistical", 4, 85, 49)}
    assert all(g["counted"] == g["count_used"] and not g["active"]
               and not g["already"] for g in got.values())
    assert sorted(i for i, g in got.items() if g["fitted_utc"] < _Q23_RULED) == \
        [33, 59, 61, 63]
    # THE PLACEHOLDERS ARE NEVER SELECTED, one short on any count among them
    placeholders = {f["id"] for f in fits if f["n_train"] < correction.MIN_TRAIN}
    assert not placeholders & set(got)
    assert 84 in placeholders and bet.count(correction.settled_rows(
        conn, sport="ufc", market_type="distance", forecaster="llm",
        before_utc=_AT_WEEKLY, as_it_stood=True)) == 15
    with pytest.raises(correction.Refused):
        correction.write_labels(conn, [84])
    conn.close()

    assert tool.main(["--database", str(path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("9 fit(s) on the record were fitted")
    assert "verified against each fit's record: 33, 59, 61, 63, 81, 85, 86, 87, 89" in out
    assert "nothing written. --write would label 9 'fitted below its gate'." in out
    assert tool.main(["--database", str(path), "--write"]) == 0
    assert "wrote 9 label(s); 0 already labelled" in capsys.readouterr().out
    assert tool.main(["--database", str(path), "--write"]) == 0
    assert "wrote 0 label(s); 9 already labelled" in capsys.readouterr().out

    conn = db.connect(path)
    try:
        assert tuple(r[0] for r in conn.execute(
            "SELECT correction_id FROM correction_gate_labels ORDER BY correction_id")) \
            == tool.RULED
        assert correction.active_correction(conn, sport="mlb", market_type="moneyline",
                                            forecaster="statistical")["id"] == 71
        # FROM THE RELEASE ON a refit is gated on the key: nothing it writes is
        # selected, so the rule's selection over every fit is still the nine
        report = correction.refit_all(conn)
        assert report["n"] == 9 and report["eligible"] == 3
        assert {g["id"] for g in correction.below_their_gates(conn)} == set(tool.RULED)
    finally:
        conn.close()
    assert tool.main(["--database", str(path)]) == 0
    assert "--write would label 0 'fitted below its gate'." in capsys.readouterr().out


def test_the_tool_refuses_live_on_a_copy_and_a_record_without_the_table(tmp_path, capsys):
    tool = _tool()
    conn = _world(tmp_path)
    conn.close()
    with pytest.raises(SystemExit) as exc:
        tool.main(["--database", str(tmp_path / "q16.db"), "--write", "--live"])
    assert exc.value.code == 2
    conn = db.connect(tmp_path / "q16.db")
    conn.execute("DROP TRIGGER calibration_corrections_labelled_never_replaced")
    conn.execute("DROP TABLE correction_gate_labels")
    conn.commit()
    conn.close()
    with pytest.raises(SystemExit):
        tool.main(["--database", str(tmp_path / "q16.db")])
    assert "has no correction_gate_labels table" in capsys.readouterr().out
