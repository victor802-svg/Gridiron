"""Operator ruling 1, 2026-09-24: what fits 91-94 published before the hold is
VOIDED -- one append-only row each, never counted in the closing line, a
curve, a correction, readiness or any gate, and shown on the page as
withdrawn, in those words, never deleted. A tap on a voided forecast stays and
is left out of the model's curves.

These are the pieces: the withdrawal table, the one door every reader of
`recommendations` goes through, the standing clause that no longer lets a
voided forecast be graded or displace one that stands, the page's words, the
two guards, and the tool that writes the voids.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3

import pytest

from gridiron import audit, calibration, config, correction, db, language, shortlist, views
from gridiron.market import at_the_line, recommend

REASON = ("published from an unvalidated fit before the hold; fit subsequently "
          "failed holdout")
DIST = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})


# --- a small world ----------------------------------------------------------

def _game(conn, gid, *, sport="nfl", kickoff="2026-09-07T02:00:00Z",
          status="scheduled", home="WAS", away="SEA", scores=(None, None)):
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES (?, ?, 2026, 3, 'REG', ?, ?, ?, ?, '2026-09-06', ?, ?)",
        (gid, sport, home, away, kickoff, status) + tuple(scores))


def _forecast(conn, gid, *, created="2026-09-07T00:00:00Z", fs="fs5",
              market="spread", subject="WAS", sport="nfl", predictor="statistical",
              line=7.5, pid=None, pass_kind="final"):
    conn.execute(
        "INSERT INTO predictions (id, created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " (?, ?, ?, ?, ?, ?, ?, 0.6, 'cover', ?, ?, ?, ?, 'x')",
        (pid, created, sport, gid, market, subject, line, predictor, pass_kind,
         fs, WHOLE))
    return conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0] \
        if pid is None else pid


def _priced(conn, gid, pid, *, closes=True):
    """A recommendation at 46c on its own contract, and -- when `closes` -- a
    later near-start read of that contract at 52c before the start."""
    at_the_line.ensure_read_kind(conn)
    reads = [("00:30", 0.45)] + ([("01:40", 0.51)] if closes else [])
    quotes = []
    for stamp, bid in reads:
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " volume, fetched_utc, read_kind) VALUES (?, ?, 'E', 'nfl', ?,"
            " 'spread', 'home_margin', 7.5, 'home', ?, ?, 900, ?, 'near_start')",
            (at_the_line.VENUE, f"T-{pid}", gid, bid, bid + 0.02,
             f"2026-09-07T{stamp}:00Z"))
        quotes.append(conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0])
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, ?, 'nfl', ?, 'spread', 'home_margin', 7.5, 'home',"
        " 'rung_matched', NULL, NULL, 0.6, 0.46, 0.46, 'mid',"
        " '2026-09-07T00:31:00Z')", (pid, quotes[0], at_the_line.VENUE, gid))
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc) VALUES (?, 'nfl', ?, 'spread', 'yes', 0.6, 0.46, 10.0,"
        " 'flat', 1.0, 0, '2026-09-07T00:32:00Z')", (pid, gid))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]


def _withdraw(conn, rec_id, reason=REASON):
    conn.execute("INSERT INTO recommendation_voids (recommendation_id, voided_utc,"
                 " reason) VALUES (?, '2026-09-24T08:00:00Z', ?)", (rec_id, reason))
    conn.commit()


def _void(conn, pid, reason=REASON):
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, '2026-09-24T08:00:00Z', ?)", (pid, reason))
    conn.commit()


def _three_closed(conn):
    """Three recommendations with measured closes (+6.0c each): one withdrawn
    by its own row, one made on a forecast that was voided, one standing."""
    ids = {}
    for name in ("own", "forecast", "stands"):
        _game(conn, f"g-{name}")
        pid = _forecast(conn, f"g-{name}")
        ids[name] = (pid, _priced(conn, f"g-{name}", pid))
    closed = recommend.record_closing_prices(conn)
    assert closed["closed"] == 3
    _withdraw(conn, ids["own"][1])
    _void(conn, ids["forecast"][0])
    return ids


# --- the table ---------------------------------------------------------------

def test_a_withdrawal_is_append_only_terminal_and_carries_a_reason(conn):
    _game(conn, "g1")
    rec = _priced(conn, "g1", _forecast(conn, "g1"), closes=False)
    with pytest.raises(sqlite3.IntegrityError):
        _withdraw(conn, rec, reason="because")          # a shrug is not a reason
    conn.rollback()
    _withdraw(conn, rec)
    with pytest.raises(sqlite3.IntegrityError, match="cannot be rewritten"):
        conn.execute("UPDATE recommendation_voids SET reason = 'something else entirely'")
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM recommendation_voids")
    with pytest.raises(sqlite3.IntegrityError):
        _withdraw(conn, rec)                            # one row each, terminal
    # AND THE RECOMMENDATION ITSELF IS UNTOUCHED: it was made.
    row = conn.execute("SELECT price, closed_utc FROM recommendations").fetchone()
    assert row["price"] == pytest.approx(0.46) and row["closed_utc"] is None


def test_a_forecast_void_is_never_deleted(conn):
    """"One append-only void row each." `prediction_voids` refused an edit and
    nothing else until 2026-09-24: a DELETE would have put a voided forecast
    back into every count."""
    _game(conn, "g1")
    pid = _forecast(conn, "g1")
    _void(conn, pid)
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM prediction_voids")
    with pytest.raises(sqlite3.IntegrityError, match="cannot be rewritten"):
        conn.execute("UPDATE prediction_voids SET reason = 'a different reason'")


def test_the_schema_comments_do_not_open_a_declaration():
    """`at_the_line._schema_statements` scans schema.sql for the two words that
    open a declaration; a comment carrying them would be read as one."""
    text = (config.PACKAGE_ROOT / "schema.sql").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lstrip().startswith("--"):
            assert "CREATE INDEX" not in line and "CREATE TRIGGER" not in line, line


# --- the closing line ------------------------------------------------------

def test_the_closing_line_never_counts_a_withdrawn_recommendation(conn):
    _three_closed(conn)
    report = calibration.clv_report(conn, sport="nfl")
    assert report["n"] == 1, "only the standing recommendation's close counts"
    entry = report["markets"][0]
    assert entry["n"] == 1 and entry["mean_cents"] == pytest.approx(6.0)
    assert entry["unmeasured"] == entry["restated"] == entry["unaccounted"] == 0
    # SHOWN, NEVER COUNTED: named beside the closing line, in the word.
    assert report["withdrawn"] == 2
    words = report["withdrawn_line"]["words"]
    assert words.startswith("2 recommendations withdrawn and never counted")
    assert REASON in words
    assert report["withdrawn_line"]["n"] == 2
    assert audit.plain_words_violations(words) == []
    assert audit.advice_word_faults(words) == []
    calibration.assert_every_figure_has_n(report)
    audit.check_no_withdrawn_recommendation_counted(conn, report)   # silent
    # and the payload the API serves carries the same guard
    assert views.scorecard(conn, "nfl")["closing_line"]["withdrawn"] == 2


def test_a_withdrawn_recommendation_is_not_awaiting_a_close_or_followed_to_one(conn):
    _game(conn, "g1")
    rec = _priced(conn, "g1", _forecast(conn, "g1"))
    _withdraw(conn, rec)
    assert calibration.clv_report(conn, sport="nfl")["awaiting_close"] == 0
    # The game has started; a standing recommendation would close here.
    assert recommend.record_closing_prices(conn) == {
        "closed": 0, "unmeasured": 0, "still_open": 0}
    row = conn.execute("SELECT closed_utc FROM recommendations").fetchone()
    assert row["closed_utc"] is None, "a withdrawn recommendation was closed"
    assert conn.execute("SELECT COUNT(*) FROM recommendation_closes").fetchone()[0] == 0


def test_the_door_answers_on_a_record_the_schema_has_not_reached(conn):
    """A query-only handle on a record older than the table: nothing can have
    been withdrawn there, and the readers must still answer."""
    conn.execute("DROP TABLE recommendation_voids")
    conn.commit()
    assert "recommendation_voids" not in recommend.not_withdrawn(conn)
    assert "prediction_voids" in recommend.not_withdrawn(conn)
    report = calibration.clv_report(conn, sport="nfl")
    assert report["withdrawn"] == 0 and report["withdrawn_line"] is None
    audit.check_no_withdrawn_recommendation_counted(conn, report)
    with pytest.raises(ValueError):
        recommend.not_withdrawn(conn, alias="r; DROP TABLE x")


def test_the_recount_names_a_withdrawn_recommendation_the_door_let_through(
        conn, monkeypatch):
    ids = _three_closed(conn)
    # THE MODULE IS LOOKED UP NOW, not at import: a blind window earlier in the
    # session drops the market package from `sys.modules`, and a patch on the
    # stale copy this file imported is a patch on nothing. Passed alone and
    # failed in the suite the first time -- the precedent in
    # test_near_start_reads.py said so, and was not read first.
    current = importlib.import_module(recommend.__name__)
    monkeypatch.setattr(current, "not_withdrawn", lambda conn, alias="r": "")
    counted = calibration.clv_report(conn, sport="nfl")
    assert counted["n"] == 3, "the planted report did not count them"
    with pytest.raises(audit.LawViolation,
                       match="A WITHDRAWN RECOMMENDATION IS COUNTED") as exc:
        audit.check_no_withdrawn_recommendation_counted(conn, counted)
    assert (f"make the difference: {ids['own'][1]}, {ids['forecast'][1]}."
            in str(exc.value))
    with pytest.raises(audit.LawViolation):
        views.scorecard(conn, "nfl")                   # cannot reach the API


# --- the source ----------------------------------------------------------------

def test_every_reader_of_recommendations_goes_through_the_door():
    audit.check_every_recommendation_reader_uses_the_door()


def test_a_reader_round_the_door_is_named_by_file_and_function(tmp_path):
    root = tmp_path / "gridiron"
    shutil.copytree(config.PACKAGE_ROOT, root)
    victim = root / "calibration.py"
    victim.write_text(
        victim.read_text(encoding="utf-8")
        + "\n\ndef planted(conn):\n"
          "    return conn.execute(\"SELECT r.id FROM predictions p\"\n"
          "                        \" JOIN recommendations r ON r.prediction_id = p.id\")\n",
        encoding="utf-8")
    faults = audit.recommendation_door_faults(root)
    assert len(faults) == 1 and "gridiron/calibration.py" in faults[0]
    assert "(planted)" in faults[0]
    with pytest.raises(audit.LawViolation, match="PAST THE DOOR"):
        audit.check_every_recommendation_reader_uses_the_door(root)


# --- the forecasts -----------------------------------------------------------

def _settled_question(conn):
    """One question asked twice, both rows settled -- an fs3 row, then an fs5
    row written later -- and the later one voided AFTER it settled, which is
    what a hand-written void can do and the resolver's never does."""
    _game(conn, "g1", kickoff="2026-09-07T17:00:00Z", status="final",
          scores=(24, 10))
    early = _forecast(conn, "g1", created="2026-09-06T00:00:00Z", fs="fs3")
    later = _forecast(conn, "g1", created="2026-09-07T05:32:00Z", fs="fs5")
    conn.execute("UPDATE predictions SET resolved_utc = '2026-09-07T21:00:00Z',"
                 " outcome = 1")
    conn.commit()
    _void(conn, later)
    return early, later


def test_a_voided_forecast_is_never_graded_even_if_it_settled_first(conn):
    early, later = _settled_question(conn)
    graded = calibration.resolved(conn, sport="nfl")
    # THE VOIDED ROW IS OUT, AND IT DOES NOT TAKE THE QUESTION WITH IT: the
    # earlier forecast of the same question is the one that stands.
    assert [r.id for r in graded] == [early]
    assert calibration.resolved(conn, sport="nfl", factor_set_version="fs5") == []
    assert calibration.curve(conn, sport="nfl", market_type="spread")["n"] == 1
    # the gate count the ranker and the edge read is the same count
    assert shortlist.settled_for_gate(conn, "nfl", "spread", None, "statistical") == 1
    # and a correction never trains on it
    rows = correction.training_rows(conn, sport="nfl", market_type="spread",
                                    forecaster="statistical",
                                    before_utc="2026-12-01T00:00:00Z")
    assert len(rows) == 1


def test_the_counts_outside_the_standing_clause_leave_a_settled_void_out(conn):
    """Four counts of settled forecasts do not go through the standing
    clause; each was given the exclusion itself on 2026-09-24."""
    _game(conn, "g1", kickoff="2026-09-07T17:00:00Z", status="final",
          scores=(24, 10))
    _forecast(conn, "g1", created="2026-09-06T00:00:00Z", pass_kind="early")
    final = _forecast(conn, "g1", created="2026-09-07T05:32:00Z")
    conn.execute("UPDATE predictions SET resolved_utc = '2026-09-07T21:00:00Z',"
                 " outcome = 1")
    conn.commit()

    def settled():
        return {s["sport"]: s for s in views.login_glance(conn)["sports"]}["nfl"]["settled"]

    assert calibration.early_vs_final(conn, sport="nfl")["n"] == 1
    assert settled() == 2
    _void(conn, final)
    assert calibration.early_vs_final(conn, sport="nfl")["n"] == 0
    assert settled() == 1


def test_a_tap_on_a_voided_forecast_stays_and_leaves_the_curves(conn):
    _, later = _settled_question(conn)
    conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc)"
                 " VALUES (?, '2026-09-07T06:00:00Z')", (later,))
    conn.commit()
    got = calibration.taken_comparison(conn, sport="nfl", market_type="spread")
    assert got["taken"]["n"] == 0, "a voided forecast is in the taken curve"
    assert got["n"] == 1
    # THE TAP STAYS: it was the operator's choice, and it is never deleted.
    assert conn.execute("SELECT COUNT(*) FROM picks_taken").fetchone()[0] == 1


def test_a_claim_on_a_voided_forecast_leaves_the_at_the_line_record(conn):
    _game(conn, "g1")
    pid = _forecast(conn, "g1")
    _priced(conn, "g1", pid, closes=False)
    assert len(at_the_line.standing_claims(conn, sport="nfl", market="spread")) == 1
    _void(conn, pid)
    assert at_the_line.standing_claims(conn, sport="nfl", market="spread") == []


def test_a_voided_forecast_is_never_priced_as_a_pick(conn, monkeypatch):
    from gridiron.priced import coverage

    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market: {
        "priceable": True, "market": market, "why": "covered, in this test"})
    _game(conn, "g1", kickoff="2026-09-09T00:00:00Z")
    pid = _forecast(conn, "g1")
    _priced(conn, "g1", pid, closes=False)
    shortlist.rank_rows(conn, [pid])
    assert recommend.for_predictions(conn, [pid]), "the fixture prices nothing"
    _void(conn, pid)
    assert recommend.for_predictions(conn, [pid]) == []


# --- the page ------------------------------------------------------------------

def test_the_page_says_withdrawn_with_its_reason_and_never_deletes(conn):
    _game(conn, "g1")
    pid = _forecast(conn, "g1")
    _void(conn, pid)
    got = views.history(conn, sport="nfl", outcome="withdrawn")
    assert got["n"] == 1
    item = got["items"][0]
    assert item["result"] == "WITHDRAWN"
    assert item["withdrawn_words"] == f"withdrawn: {REASON}"
    assert audit.plain_words_violations(item["withdrawn_words"]) == []
    # a link written before the word changed still answers
    assert views.history(conn, sport="nfl", outcome="void")["n"] == 1
    # the detail says so too; until 2026-09-24 it read like a pending forecast
    detail = views.prediction_detail(conn, pid)
    assert detail["result"] == "WITHDRAWN" and detail["voided"] is True
    assert detail["withdrawn_words"] == f"withdrawn: {REASON}"
    # never on the slate as a live pick
    assert pid not in {c["prediction_id"] for c in views.week(conn, "nfl")["cards"]}
    assert language.verdict_word(None, voided=True) == "WITHDRAWN"
    assert "1 withdrawn" in language.calendar_day_line("2026-09-06", 0, 0, 1)
    assert language.withdrawn_words(None) is None


@pytest.mark.parametrize("stored, shown", [
    ("mlb_824785 finished level, which a completed baseball game cannot do",
     "withdrawn: the game finished level, which a completed baseball game cannot do"),
    ("2025_08_DAL_SEA finished level. The question was whether the home side "
     "would win", "withdrawn: the game finished level. The question was whether "
     "the home side would win"),
    ("Tua Tagovailoa passing_yards has no box score for 2026 week 1",
     "withdrawn: Tua Tagovailoa passing yards has no box score for 2026 week 1"),
    (REASON, f"withdrawn: {REASON}"),
])
def test_a_stored_reason_reaches_the_page_in_plain_words(stored, shown):
    """The reason left the hover on 2026-09-24 and went onto the page, where
    six of the live record's 38 distinct reasons would have put a game key or
    a code name in front of a reader. Humanised at render; never rewritten."""
    assert language.withdrawn_words(stored) == shown
    assert audit.plain_words_violations(shown) == []


def test_the_renderer_shows_the_reason_rather_than_hiding_it_in_a_hover():
    js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "item.withdrawn_words" in js and "'withdrawn-why'" in js
    assert "line.withdrawn_line" in js
    assert "'VOID'" not in js, "the renderer still branches on the old word"
    html = (config.PACKAGE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert '<option value="withdrawn">withdrawn</option>' in html


# --- the tool ------------------------------------------------------------------

def _tool():
    path = config.PACKAGE_ROOT.parent / "tools" / "void_fs5.py"
    spec = importlib.util.spec_from_file_location("void_fs5_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NFL_MONEYLINE = (2225, 2230, 2235, 2240, 2245, 2248, 2251, 2256, 2261, 2266,
                 2271, 2276, 2281, 2284, 2289, 2294)
NFL_SPREAD = (2228, 2233, 2238, 2243, 2254, 2259, 2264, 2269, 2274, 2279, 2287,
              2292, 2297)


def _the_morning(path):
    """The record as the ruling measured it: 31 statistical fs5 forecasts
    after 05:16Z, recommendations 62-66 with 65 on a reasoning-forecaster
    total, reasoning rows beside them, and rows the criteria must not take."""
    conn = db.open_db(path)
    at = "2026-09-24T05:3{}:00Z"
    for n, pid in enumerate(NFL_MONEYLINE + NFL_SPREAD):
        gid = f"nfl-{pid}"
        _game(conn, gid, kickoff="2026-09-27T17:00:00Z")
        market = "moneyline" if pid in NFL_MONEYLINE else "spread"
        _forecast(conn, gid, pid=pid, created=at.format(n % 7), market=market,
                  line=None if market == "moneyline" else 7.5)
        _forecast(conn, gid, pid=pid + 1, created=at.format(n % 7),
                  market=market, predictor="llm",
                  line=None if market == "moneyline" else 7.5)
    for pid, market in ((2299, "spread"), (2301, "moneyline")):
        _game(conn, f"cfb-{pid}", sport="cfb", kickoff="2026-09-24T23:30:00Z")
        for row, predictor in ((pid, "statistical"), (pid + 1, "llm")):
            _forecast(conn, f"cfb-{pid}", pid=row, sport="cfb", market=market,
                      created="2026-09-24T05:36:52Z", predictor=predictor,
                      line=None if market == "moneyline" else -0.5)
    # rec 65's forecast: the reasoning forecaster, a total, fs2
    _forecast(conn, "nfl-2297", pid=2296, market="total", predictor="llm",
              fs="fs2", created="2026-09-24T05:36:00Z", line=44.5)
    # what the criteria must leave alone: before 05:16, and another set
    _game(conn, "nfl-early", kickoff="2026-09-27T17:00:00Z")
    _forecast(conn, "nfl-early", pid=2200, created="2026-09-24T05:10:00Z")
    _forecast(conn, "nfl-early", pid=2201, fs="fs3", created="2026-09-24T06:00:00Z")
    for rid, pid in ((62, 2264), (63, 2279), (64, 2287), (65, 2296), (66, 2297)):
        conn.execute(
            "INSERT INTO recommendations (id, prediction_id, sport, game_id,"
            " market, side, fair_value, price, edge_cents, size_kind,"
            " size_units, gate_n, created_utc) SELECT ?, id, sport, game_id,"
            " market_type, 'yes', 0.6, 0.46, 10.0, 'flat', 1.0, 0,"
            " '2026-09-24T05:36:49Z' FROM predictions WHERE id = ?", (rid, pid))
    conn.commit()
    return conn


def test_the_tool_reads_only_until_told_to_write(tmp_path, capsys):
    tool = _tool()
    path = tmp_path / "morning.db"
    _the_morning(path).close()
    assert tool.main(["--database", str(path)]) == 0
    out = capsys.readouterr().out
    assert "31 forecasts" in out and "62, 63, 64, 66" in out
    assert "31 reasoning-forecaster rows" in out and "nothing written" in out
    check = db.connect(path)
    assert check.execute("SELECT COUNT(*) FROM prediction_voids").fetchone()[0] == 0
    assert check.execute("SELECT COUNT(*) FROM recommendation_voids").fetchone()[0] == 0


def test_the_tool_writes_the_ruling_once_and_leaves_65_and_the_reasoning_rows(tmp_path):
    tool = _tool()
    path = tmp_path / "morning.db"
    _the_morning(path).close()
    assert tool.main(["--database", str(path), "--write"]) == 0
    conn = db.connect(path)
    voids = conn.execute("SELECT prediction_id, reason FROM prediction_voids"
                         " ORDER BY prediction_id").fetchall()
    assert tuple(v["prediction_id"] for v in voids) == tool.TAINTED_PREDICTIONS
    assert {v["reason"] for v in voids} == {REASON}
    gone = conn.execute("SELECT recommendation_id, reason FROM recommendation_voids"
                        " ORDER BY recommendation_id").fetchall()
    assert [g["recommendation_id"] for g in gone] == [62, 63, 64, 66]
    assert {g["reason"] for g in gone} == {REASON}
    # 65 STANDS, and so does every reasoning-forecaster row
    report = calibration.clv_report(conn, sport="nfl")
    assert report["awaiting_close"] == 1 and report["withdrawn"] == 4
    assert conn.execute(
        "SELECT COUNT(*) FROM prediction_voids v JOIN predictions p"
        " ON p.id = v.prediction_id WHERE p.predictor = 'llm'").fetchone()[0] == 0
    conn.close()
    # IDEMPOTENT: a second run finds everything written and writes nothing.
    assert tool.main(["--database", str(path), "--write"]) == 0
    conn = db.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM prediction_voids").fetchone()[0] == 31
    assert conn.execute("SELECT COUNT(*) FROM recommendation_voids").fetchone()[0] == 4


@pytest.mark.parametrize("drift", ["an extra forecast", "an extra recommendation"])
def test_the_tool_refuses_a_record_that_has_drifted_from_the_ruling(
        tmp_path, capsys, drift):
    tool = _tool()
    path = tmp_path / "morning.db"
    conn = _the_morning(path)
    if drift == "an extra forecast":
        _game(conn, "nfl-late", kickoff="2026-09-27T17:00:00Z")
        _forecast(conn, "nfl-late", pid=2400, created="2026-09-24T09:00:00Z")
    else:
        conn.execute(
            "INSERT INTO recommendations (id, prediction_id, sport, game_id,"
            " market, side, fair_value, price, edge_cents, size_kind,"
            " size_units, gate_n, created_utc) SELECT 70, id, sport, game_id,"
            " market_type, 'yes', 0.6, 0.46, 10.0, 'flat', 1.0, 0,"
            " '2026-09-24T09:00:00Z' FROM predictions WHERE id = 2225")
    conn.commit()
    conn.close()
    assert tool.main(["--database", str(path), "--write"]) == 2
    assert "REFUSED, NOTHING WRITTEN" in capsys.readouterr().out
    check = db.connect(path)
    assert check.execute("SELECT COUNT(*) FROM prediction_voids").fetchone()[0] == 0
    assert check.execute("SELECT COUNT(*) FROM recommendation_voids").fetchone()[0] == 0
