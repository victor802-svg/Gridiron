"""Operator question 12, ruled 2026-09-27 (docs/briefs/2026-09-27-close-out-
rulings.md):

    "Q12: the record shows rows as written. Every measurement counts a
    same-side pair once (the earlier row). Recs 45/46, opposite sides of one
    total, count zero in every measurement and are labelled 'both sides, no
    position'."

A MEASUREMENT RULE, NOT AN EDIT: `recommend.counted_once` is the door every
count of recommendations reads through, `recommend.not_counted_once` lists
what it leaves out, and nothing is written. These are the rule, each
measurement it reaches (the closing line and all it feeds, the kill
criterion, the re-grade line, the empty-bar count), the page's label, the
record left as written, and the two guards.
"""
from __future__ import annotations

import importlib
import importlib.util
import shutil
from datetime import datetime, timedelta

import pytest

from gridiron import audit, calibration, config, db, language, views
from gridiron.market import recommend
from gridiron.priced import coverage

ON_THE_DAY = config.CLOSING_LINE_FIRST_CLEAN_READ + "T00:00:00Z"
DAY = datetime.fromisoformat(config.CLOSING_LINE_WINDOW_START
                             + "T01:00:00+00:00") + timedelta(days=1)


def _at(minutes: float) -> str:
    return (DAY + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _game(conn, gid: str, *, kickoff: float = 600) -> None:
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
        " 'MIA', 'NYM', ?, 'scheduled', ?)", (gid, _at(kickoff), _at(0)[:10]))


def _rec(conn, gid: str, *, market: str = "spread", side: str = "yes",
         at: float = 0, price: float = 0.46, close: float | None = 0.49,
         predictor: str = "statistical") -> int:
    """One recommendation on game `gid`, written `at` minutes into the day,
    priced from a near-start read of its own contract and -- when `close` is
    given -- closed on a later one before the start, measured, with its
    account written as the closer writes it. A second on one game and market
    is written only by a test that has set item 5's rule aside first. Each
    forecast's subject carries its minute, so two on one game and market are
    two questions to the forecasts' own key."""
    quantity, line, yes = (("home_margin", -1.5, "home") if market == "spread"
                           else ("total", 7.5, "over"))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES (?, 'mlb', ?, ?,"
        " ?, ?, 0.6, ?, ?, 'final', 'fs2', '{}', 'x')",
        (_at(at - 5), gid, market, f"MIA {at}", line,
         ("cover" if side == "yes" else "not_cover") if market == "spread"
         else ("over" if side == "yes" else "under"), predictor))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]

    def quote(mid: float, minutes: float) -> int:
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " volume, fetched_utc, read_kind) VALUES ('kalshi', ?, 'E', 'mlb',"
            " ?, ?, ?, ?, ?, ?, ?, 900, ?, 'near_start')",
            (f"T-{gid}-{market}", gid, market, quantity, line, yes,
             round(mid - 0.005, 4), round(mid + 0.005, 4), _at(minutes)))
        return conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]

    priced_by = quote(price, at - 2)
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', ?, ?, ?, ?, ?, 'rung_matched', NULL,"
        " NULL, 0.6, ?, ?, 'mid', ?)",
        (pid, priced_by, gid, market, quantity, line, yes, price, price,
         _at(at - 1)))
    if close is None:
        conn.execute(
            "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
            " side, fair_value, price, edge_cents, size_kind, size_units,"
            " gate_n, created_utc) VALUES (?, 'mlb', ?, ?, ?, 0.6, ?, 5.0,"
            " 'flat', 1.0, 0, ?)", (pid, gid, market, side, price, _at(at)))
        return conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
    closed_by = quote(close, 500)
    clv = round(((close - price) if side == "yes" else (price - close)) * 100, 2)
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc, close_price, clv_cents, closed_utc) VALUES (?, 'mlb', ?,"
        " ?, ?, 0.6, ?, 5.0, 'flat', 1.0, 0, ?, ?, ?, ?)",
        (pid, gid, market, side, price, _at(at), close, clv, _at(700)))
    rec = conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
    conn.execute(
        "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
        " pricing_quote_id, close_quote_id, close_price, clv_cents,"
        " minutes_before_start, restated, reason) VALUES (?, ?, ?, ?, ?, ?,"
        " 100.0, 0, 'the last near-start read of its own contract before the"
        " start')", (rec, _at(700), priced_by, closed_by, close, clv))
    return rec


def _before_item_5(conn) -> None:
    """Set item 5's rule aside, as every pair on the record was written."""
    conn.execute("DROP TRIGGER recommendation_one_per_game_and_market")


def _item_5_back(conn) -> None:
    conn.commit()
    db.init(conn)
    conn.commit()


def _withdraw(conn, rec_id: int) -> None:
    conn.execute("INSERT INTO recommendation_voids (recommendation_id,"
                 " voided_utc, reason) VALUES (?, ?, 'withdrawn in this test"
                 " world')", (rec_id, _at(800)))
    conn.commit()


@pytest.fixture
def shapes(conn):
    """Every shape the rule decides, in one sport.

      * `single`: one recommendation on its game and market;
      * `morning`/`final`: a same-side pair, the seventeen's shape;
      * `over`/`under`: both sides of one total in one second, 45/46's;
      * `t1`/`t2`/`t3`: three on one side (none on the record; the rule
        reads a group, not a pair);
      * `gone`/`after`: a withdrawn row and one written after it, NFL
        62/73's shape: no pair, because a withdrawn row never counts;
      * `spread_same_game`: another market of the pair's game, its own.
    """
    ids = {}
    for gid in ("g-single", "g-pair", "g-total", "g-three", "g-gone"):
        _game(conn, gid)
    ids["single"] = _rec(conn, "g-single")
    _before_item_5(conn)
    ids["morning"] = _rec(conn, "g-pair", at=0, price=0.46)
    ids["final"] = _rec(conn, "g-pair", at=60, price=0.40)
    ids["over"] = _rec(conn, "g-total", market="total", side="yes", at=30,
                       price=0.485, close=0.50)
    ids["under"] = _rec(conn, "g-total", market="total", side="no", at=30,
                        price=0.485, close=0.50, predictor="llm")
    ids["t1"] = _rec(conn, "g-three", at=10)
    ids["t2"] = _rec(conn, "g-three", at=20)
    ids["t3"] = _rec(conn, "g-three", at=30)
    ids["gone"] = _rec(conn, "g-gone", at=0)
    ids["after"] = _rec(conn, "g-gone", at=40)
    ids["spread_same_game"] = _rec(conn, "g-total", market="spread", at=35)
    _item_5_back(conn)
    _withdraw(conn, ids["gone"])
    return ids


def _counted(conn) -> set[int]:
    return {r[0] for r in conn.execute(
        "SELECT r.id FROM recommendations r WHERE r.sport = 'mlb'"
        + recommend.counted_once(conn))}


# --- the rule -----------------------------------------------------------------

def test_the_rule_counts_a_same_side_pair_once_and_both_sides_not_at_all(conn, shapes):
    got = _counted(conn)
    assert got == {shapes[k] for k in ("single", "morning", "t1", "after",
                                       "spread_same_game")}
    aside = {r["id"]: r["why"] for r in recommend.not_counted_once(conn, sport="mlb")}
    assert aside == {shapes["final"]: recommend.REPEAT,
                     shapes["t2"]: recommend.REPEAT,
                     shapes["t3"]: recommend.REPEAT,
                     shapes["over"]: recommend.BOTH_SIDES,
                     shapes["under"]: recommend.BOTH_SIDES}
    # EVERY STANDING ROW IS EXACTLY ONE OF THE THREE, and a withdrawn row is
    # none of them
    standing = {r[0] for r in conn.execute(
        "SELECT r.id FROM recommendations r WHERE 1 = 1" + recommend.not_withdrawn(conn))}
    assert got | set(aside) == standing and not (got & set(aside))
    assert shapes["gone"] not in standing | got | set(aside)


def test_first_is_by_stamp_then_number_whatever_order_sqlite_hands_back(conn):
    """45 and 46 share a second, and a same-side pair written in one second
    counts as the lower number -- as `standing_recommendations` orders it."""
    _game(conn, "g")
    _before_item_5(conn)
    a = _rec(conn, "g", at=5)
    b = _rec(conn, "g", at=5, price=0.44, predictor="llm")
    _item_5_back(conn)
    assert a < b and a in _counted(conn) and b not in _counted(conn)
    assert [s["id"] for s in recommend.standing_recommendations(conn, "g", "spread")] == [a, b]


def test_the_door_refuses_an_alias_it_would_shadow(conn):
    with pytest.raises(ValueError):
        recommend.counted_once(conn, alias="q12_other")
    with pytest.raises(ValueError):
        recommend.counted_once(conn, alias="r; DROP TABLE x")


def test_the_record_shows_rows_as_written(conn, shapes):
    """No row changes, none is added, and no table: every measurement is
    read, the label derived, and the record is exactly as it was."""
    tables = ("recommendations", "recommendation_closes", "recommendation_voids",
              "recommendation_regrades")
    before = {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1")]
              for t in tables}
    schema = [tuple(r) for r in conn.execute("SELECT * FROM sqlite_master ORDER BY name")]
    views.scorecard(conn, "mlb")
    calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    coverage.stopped(conn, "mlb", now=ON_THE_DAY)
    recommend.regraded(conn, sport="mlb")
    assert {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1")]
            for t in tables} == before
    assert [tuple(r) for r in conn.execute(
        "SELECT * FROM sqlite_master ORDER BY name")] == schema
    # THE WRITE RULE STILL READS THE PAIRS AS THEY STAND (item 5)
    assert [s["id"] for s in recommend.standing_recommendations(
        conn, "g-total", "total")] == [shapes["over"], shapes["under"]]


# --- the closing line and all it feeds ---------------------------------------

def test_the_closing_line_counts_the_pair_once_as_its_earlier_row(conn, shapes):
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    spread = next(e for e in report["markets"] if e["market"] == "spread")
    # single +3.0, morning +3.0, t1 +3.0, after +3.0, the total game's own
    # spread +3.0: five, never the final (+9.0), t2, t3 or the withdrawn one
    assert spread["n"] == 5 and spread["mean_cents"] == 3.0
    assert spread["repeats"] == 3
    assert ("3 more repeat an earlier recommendation on the same game and "
            "side and are counted once, as the earlier one") in spread["words"]
    # BOTH SIDES OF THE TOTAL ARE IN NO FIGURE: no total entry at all
    assert [e["market"] for e in report["markets"]] == ["spread"]
    assert report["n"] == 5 and report["repeats"] == 3 and report["both_sides"] == 2
    assert report["set_aside"] == {"n": 5, "measured": 5, "closed": 5,
                                   "awaiting_close": 0}
    assert report["window_line"]["n"] == 5
    calibration.assert_every_figure_has_n(report)
    audit.check_no_withdrawn_recommendation_counted(conn, report)
    audit.check_each_pair_counted_once(conn, report)


def test_both_sides_are_labelled_in_the_ruling_s_words_with_their_n(conn, shapes):
    report = calibration.clv_report(conn, sport="mlb")
    line = report["both_sides_line"]
    assert line["label"] == "Both sides, no position" == recommend.BOTH_SIDES_LABEL
    assert line["label"].lower() == "both sides, no position"
    assert line["n"] == 2
    day = language.date_words_from_iso(_at(0)[:10])
    assert line["words"] == (
        f"2 recommendations took both sides of one game's total on {day}, so "
        f"between them they hold no position: neither is counted in any figure "
        f"here, and each stays on the record as written")
    assert audit.plain_words_violations(line["words"]) == []
    assert audit.advice_word_faults(line["words"]) == []
    # AND THE PAGE CARRIES IT, through the API's own guards
    served = views.scorecard(conn, "mlb")["closing_line"]
    assert served["both_sides_line"] == line


def test_a_sport_with_no_pair_names_none(conn):
    _game(conn, "g")
    _rec(conn, "g")
    report = calibration.clv_report(conn, sport="mlb")
    assert report["both_sides_line"] is None and report["both_sides"] == 0
    assert report["repeats"] == 0 and report["markets"][0]["repeats"] == 0
    assert "repeat" not in report["markets"][0]["words"]


def test_the_words_for_several_games_and_one_repeat():
    assert language.both_sides_recommendations_line([
        {"market": "total", "day": "2026-09-21", "n": 2},
        {"market": "point spread", "day": "2026-09-22", "n": 3}]) == (
        "5 recommendations took both sides of 2 games and markets (one game's "
        "total on Monday 21 September and one game's point spread on Tuesday "
        "22 September), so between them they hold no position: none is "
        "counted in any figure here, and each stays on the record as written")
    assert language.clv_line(2, None, None, 50, repeats=1).endswith(
        " · 1 more repeats an earlier recommendation on the same game and side "
        "and is counted once, as the earlier one")


def test_an_open_repeat_is_not_awaiting_a_close(conn):
    _game(conn, "g")
    _before_item_5(conn)
    _rec(conn, "g", at=0, close=None)
    _rec(conn, "g", at=30, close=None)
    _item_5_back(conn)
    report = calibration.clv_report(conn, sport="mlb")
    assert report["awaiting_close"] == 1
    assert report["set_aside"]["awaiting_close"] == 1 and report["repeats"] == 1
    assert report["markets"][0]["repeats"] == 1 and report["markets"][0]["n"] == 0
    audit.check_no_withdrawn_recommendation_counted(conn, report)
    audit.check_each_pair_counted_once(conn, report)


def test_the_kill_criterion_counts_a_pair_once(conn, monkeypatch):
    """Forty-eight singles and one same-side pair, every close -1.0c: 49
    counted, so the kill (fifty) stops nothing; counted twice, it would
    have stopped the market on a close it read twice."""
    for i in range(48):
        _game(conn, f"g{i}")
        _rec(conn, f"g{i}", at=i, price=0.50, close=0.49)
    _game(conn, "g-pair")
    _before_item_5(conn)
    _rec(conn, "g-pair", at=100, price=0.50, close=0.49)
    _rec(conn, "g-pair", at=160, price=0.50, close=0.49)
    _item_5_back(conn)
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    assert report["n"] == 49
    assert coverage.stopped(conn, "mlb", now=ON_THE_DAY) == {}
    # the rule removed, as it was until 2026-09-27: fifty, and stopped
    current = importlib.import_module(recommend.__name__)
    door = current.not_withdrawn
    monkeypatch.setattr(current, "counted_once",
                        lambda conn, alias="r": door(conn, alias))
    monkeypatch.setattr(current, "not_counted_once", lambda conn, *, sport: [])
    assert calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)["n"] == 50
    assert "spread" in coverage.stopped(conn, "mlb", now=ON_THE_DAY)


def test_a_withdrawn_earlier_row_leaves_its_later_row_counted(conn, shapes):
    """PAIRED AFTER THE WITHDRAWALS: NFL 73, 75, 76 and 78's shape."""
    assert shapes["after"] in _counted(conn)
    assert shapes["after"] not in {r["id"] for r in
                                   recommend.not_counted_once(conn, sport="mlb")}


def test_withdrawing_the_first_of_a_pair_makes_the_second_count(conn):
    _game(conn, "g")
    _before_item_5(conn)
    first = _rec(conn, "g", at=0)
    second = _rec(conn, "g", at=30)
    _item_5_back(conn)
    assert _counted(conn) == {first}
    _withdraw(conn, first)
    assert _counted(conn) == {second}
    assert recommend.not_counted_once(conn, sport="mlb") == []


# --- the re-grade line --------------------------------------------------------

def _regraded_world(conn) -> dict:
    """Recs 3/10 and 21/26 as the record holds them -- each pair on one game,
    both on the no side -- and rec 56 on its own. 3, 10, 26 and 56 were let
    through by the yes price (question 9's four); 21 cleared on its cost."""
    for game in ("p1", "p2", "p3"):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " 'AAA', 'BBB', '2026-09-26T00:00:00Z', 'scheduled', '2026-09-08')",
            (game,))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-07T00:00:00Z', 'mlb', 'p1', 'spread', 'AAA', -1.5, 0.62,"
        " 'cover', 'statistical', 'final', 'fs2', '{}', 'test')")
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    _before_item_5(conn)
    for rid, game, price, edge, created in (
            (3, "p1", 0.375, 2.09, "2026-09-07T20:52:31Z"),
            (10, "p1", 0.375, 2.30, "2026-09-08T21:33:31Z"),
            (21, "p2", 0.375, 3.50, "2026-09-09T12:09:23Z"),
            (26, "p2", 0.395, 2.84, "2026-09-09T21:32:20Z"),
            (56, "p3", 0.39, 3.03, "2026-09-24T05:21:25Z")):
        conn.execute(
            "INSERT INTO recommendations (id, prediction_id, sport, game_id,"
            " market, side, fair_value, price, edge_cents, size_kind,"
            " size_units, gate_n, created_utc) VALUES (?, ?, 'mlb', ?,"
            " 'spread', 'no', 0.40, ?, ?, 'flat', 1.0, 53, ?)",
            (rid, pid, game, price, edge, created))
    _item_5_back(conn)
    assert [g["id"] for g in recommend.let_through_by_the_yes_price(conn)] == [3, 10, 26, 56]
    assert recommend.write_regrades(conn, [3, 10, 26, 56]) == {"written": 4, "already": 0}


def test_the_regrade_line_counts_a_pair_once(conn):
    """Question 9's four labels stay on the record; the line beside the
    closing line counts the labelled rows the rule counts: rec 3 (its
    pair's first) and rec 56. Rec 10 is its pair's second, and rec 26's pair
    counts as rec 21, which cleared."""
    _regraded_world(conn)
    assert conn.execute("SELECT COUNT(*) FROM recommendation_regrades").fetchone()[0] == 4
    assert [g["id"] for g in recommend.regraded(conn, sport="mlb")] == [3, 56]
    report = calibration.clv_report(conn, sport="mlb")
    assert report["regraded"] == 2 and report["regraded_line"]["n"] == 2
    assert "3.34% and 4.97%" in report["regraded_line"]["words"]
    audit.check_each_pair_counted_once(conn, report)
    # the recount knows the rule for the line too: counting all four is caught
    with pytest.raises(audit.LawViolation, match="would not have cleared"):
        audit.check_each_pair_counted_once(conn, dict(report, regraded=4))
    # the selection that writes labels still reads the rows as written
    assert [g["id"] for g in recommend.let_through_by_the_yes_price(conn)] == [3, 10, 26, 56]


# --- the empty-bar count --------------------------------------------------------

def _empty_bar():
    path = config.PACKAGE_ROOT.parent / "tools" / "empty_bar.py"
    spec = importlib.util.spec_from_file_location("empty_bar_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_day_whose_only_recommendation_repeats_one_cleared_nothing(conn):
    """A pair written a day apart: the later day holds only the repeat, and
    nothing that counts cleared the bar that day."""
    _game(conn, "g", kickoff=2000)
    _before_item_5(conn)
    _rec(conn, "g", at=0, close=None)
    _rec(conn, "g", at=24 * 60, close=None)
    _item_5_back(conn)
    # each recommendation's own claim makes its day one the bar was tested
    second = _at(24 * 60)[:10]
    spans = _empty_bar().spans(conn, "mlb")["spans"]
    tested = [s for s in spans if s["days_the_bar_could_be_tested"]]
    assert [s["days_the_bar_could_be_tested"] for s in tested] == [2]
    assert tested[0]["empty_days"] == [second]


# --- the guards -----------------------------------------------------------------

def test_the_recount_names_a_pair_the_door_let_through(conn, shapes, monkeypatch):
    current = importlib.import_module(recommend.__name__)
    door = current.not_withdrawn
    monkeypatch.setattr(current, "counted_once",
                        lambda conn, alias="r": door(conn, alias))
    monkeypatch.setattr(current, "not_counted_once", lambda conn, *, sport: [])
    counted = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    # the withdrawn recount's question is withdrawal, and it is silent
    assert audit.withdrawn_counted_faults(conn, counted) == []
    with pytest.raises(audit.LawViolation,
                       match="A PAIR IS COUNTED TWICE, OR BOTH SIDES AT ALL") as exc:
        audit.check_each_pair_counted_once(conn, counted)
    aside = sorted(shapes[k] for k in ("final", "over", "under", "t2", "t3"))
    assert ("make the difference: " + ", ".join(map(str, aside)) + "."
            in str(exc.value))
    with pytest.raises(audit.LawViolation):
        views.scorecard(conn, "mlb")                   # cannot reach the API


def test_a_report_that_counts_a_repeat_and_names_it_too_is_caught(conn, shapes,
                                                                    monkeypatch):
    """Only the counting door broken, its other side intact: the repeat is
    in the count and beside it. The pair recount sees the count; the
    withdrawn recount sees a row added up twice."""
    current = importlib.import_module(recommend.__name__)
    door = current.not_withdrawn
    monkeypatch.setattr(current, "counted_once",
                        lambda conn, alias="r": door(conn, alias))
    counted = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    assert audit.pair_counted_faults(conn, counted)
    assert audit.withdrawn_counted_faults(conn, counted)


def test_a_report_that_hides_what_it_set_aside_is_caught(conn, shapes):
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    for key, value in (("repeats", 0), ("both_sides", 0),
                       ("set_aside", {"n": 0, "measured": 0, "closed": 0,
                                      "awaiting_close": 0})):
        assert audit.pair_counted_faults(conn, dict(report, **{key: value})), key
    # the withdrawn recount adds the set-aside rows back; without them it
    # finds standing rows missing
    assert audit.withdrawn_counted_faults(conn, dict(report, set_aside={}))


def test_every_measurement_reads_the_counted_once_door():
    audit.check_every_measurement_counts_each_pair_once()
    audit.check_every_recommendation_reader_uses_the_door()


def test_every_reader_kept_as_a_record_reader_exists_and_reads_the_table():
    """A register entry naming a function that no longer reads the table
    would be an exemption nobody can see the reason for."""
    import ast

    base = config.PACKAGE_ROOT.parent
    for key, reason in audit.RECORD_READERS.items():
        path, function = key.split(":")
        tree = ast.parse((base / path).read_text(encoding="utf-8"))
        found = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == function]
        assert found, key
        source = ast.get_source_segment((base / path).read_text(encoding="utf-8"),
                                        found[0])
        assert "recommendations" in source, key
        assert len(reason) > 40, key


def test_a_measurement_round_the_door_is_named_by_file_and_function(tmp_path):
    root = tmp_path / "gridiron"
    shutil.copytree(config.PACKAGE_ROOT, root)
    victim = root / "views.py"
    victim.write_text(
        victim.read_text(encoding="utf-8")
        + "\n\ndef planted(conn):\n"
          "    from .market import recommend\n"
          "    return conn.execute(\"SELECT COUNT(*) FROM recommendations r\"\n"
          "                        \" WHERE 1 = 1\" + recommend.not_withdrawn(conn))\n",
        encoding="utf-8")
    faults = audit.measurement_door_faults(root)
    assert len(faults) == 1 and "gridiron/views.py" in faults[0]
    assert "(planted)" in faults[0]
    assert audit.recommendation_door_faults(root) == []
    with pytest.raises(audit.LawViolation, match="COUNTED-ONCE DOOR"):
        audit.check_every_measurement_counts_each_pair_once(root)


def test_the_renderer_draws_the_label_beside_the_closing_line():
    js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    at = js.index("line.both_sides_line")
    assert "requireN(both" in js[at:at + 300]
    assert js.index("line.withdrawn_line") < at < js.index("line.regraded_line")
