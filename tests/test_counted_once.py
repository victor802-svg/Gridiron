"""Operator question 12, ruled 2026-09-27 (docs/briefs/2026-09-27-close-out-
rulings.md), and question 22, ruled 2026-09-28 (docs/briefs/2026-09-28-
rulings.md), on question 17's one distinct-bet function (`gridiron.bet`):

    "Q12: the record shows rows as written. Every measurement counts a
    same-side pair once (the earlier row). Recs 45/46, opposite sides of one
    total, count zero in every measurement and are labelled 'both sides, no
    position'."

    "Q22: (A). Recommendation counts split per forecaster, like every other
    count. This reverses Q12 for 45/46: each counts once in its own
    forecaster's line, and the 'Both sides, no position' row goes. Same-side
    pairs count once only within one forecaster."

A MEASUREMENT RULE, NOT AN EDIT: `recommend.counted_once` is the door every
count of recommendations reads through -- one forecaster's, named in the
door -- `recommend.not_counted_once` lists what it leaves out, and nothing is
written. These are the rule, each measurement it reaches (the closing line
and all it feeds, the kill criterion, the re-grade line, the empty-bar
count), the record left as written, and the guards.

WHAT QUESTION 22 REVERSED, said where it is tested (2026-09-28): two
forecasters on one side of one game were one pair counted once (this file's
`test_first_is_by_stamp_then_number...` wrote them so); they are two bets
now, each counted in its own forecaster's line. Recs 45/46's shape counted
zero under a label of its own; each counts once now, and no label is drawn.
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
         predictor: str = "statistical", subject: str | None = None,
         rung: float | None = None, pass_kind: str = "final",
         fs: str = "fs2") -> int:
    """One recommendation on game `gid`, written `at` minutes into the day,
    priced from a near-start read of its own contract and -- when `close` is
    given -- closed on a later one before the start, measured, with its
    account written as the closer writes it. A second on one game and market
    is written only by a test that has set item 5's rule aside first.

    ITS OWN FORECAST, whose key the counts read (operator questions 17 and
    22, 2026-09-28): `subject` and `rung` are the question asked -- by
    default a subject carrying the minute, so two on one game and market are
    two questions unless a test names one question for both -- and
    `predictor`, `pass_kind` and `fs` say whose answer and which pass (the
    forecasts' own unique key is game, market, subject, forecaster, factor
    set and pass)."""
    quantity, line, yes = (("home_margin", -1.5, "home") if market == "spread"
                           else ("total", 7.5, "over"))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES (?, 'mlb', ?, ?,"
        " ?, ?, 0.6, ?, ?, ?, ?, '{}', 'x')",
        (_at(at - 5), gid, market, subject or f"MIA {at}",
         line if rung is None else rung,
         ("cover" if side == "yes" else "not_cover") if market == "spread"
         else ("over" if side == "yes" else "under"), predictor, pass_kind, fs))
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


def _line(report: dict, who: str) -> dict:
    """One forecaster's block of a closing line."""
    return next(b for b in report["forecasters"] if b["predictor"] == who)


def _entry(report: dict, market: str, who: str) -> dict | None:
    return next((e for e in report["markets"]
                 if e["market"] == market and e["predictor"] == who), None)


@pytest.fixture
def shapes(conn):
    """Every shape the rule decides, in one sport.

      * `single`: one recommendation on its game and market;
      * `morning`/`final`: a same-side pair, the seventeen's shape -- one
        forecaster's morning and final pass on one question at one rung;
      * `over`/`under`: recs 45 and 46's shape -- the statistical model's
        over and the reasoning pass's under of one total, in one second;
      * `t1`/`t2`/`t3`: three of one forecaster on one side of one question
        (none on the record; the rule reads a group, not a pair);
      * `gone`/`after`: a withdrawn row and one written after it, NFL
        62/73's shape: no pair, because a withdrawn row never counts;
      * `spread_same_game`: another market of the total's game, its own;
      * `cross_stat`/`cross_llm`: the two forecasters on ONE SIDE of one
        question -- two bets (question 22), where question 12 counted one;
      * `rung_a`/`rung_b`: one forecaster on one side of one game asked at
        two rungs -- two questions (question 21), never a pair.
    """
    ids = {}
    for gid in ("g-single", "g-pair", "g-total", "g-three", "g-gone",
                "g-cross", "g-rungs"):
        _game(conn, gid)
    ids["single"] = _rec(conn, "g-single")
    _before_item_5(conn)
    ids["morning"] = _rec(conn, "g-pair", at=0, price=0.46, subject="MIA",
                          pass_kind="early")
    ids["final"] = _rec(conn, "g-pair", at=60, price=0.40, subject="MIA")
    ids["over"] = _rec(conn, "g-total", market="total", side="yes", at=30,
                       price=0.485, close=0.50, subject="NYM at MIA")
    ids["under"] = _rec(conn, "g-total", market="total", side="no", at=30,
                        price=0.485, close=0.50, predictor="llm",
                        subject="NYM at MIA")
    ids["t1"] = _rec(conn, "g-three", at=10, subject="MIA", pass_kind="early")
    ids["t2"] = _rec(conn, "g-three", at=20, subject="MIA")
    ids["t3"] = _rec(conn, "g-three", at=30, subject="MIA", fs="fs3")
    ids["gone"] = _rec(conn, "g-gone", at=0, subject="MIA", pass_kind="early")
    ids["after"] = _rec(conn, "g-gone", at=40, subject="MIA")
    ids["spread_same_game"] = _rec(conn, "g-total", market="spread", at=35)
    ids["cross_stat"] = _rec(conn, "g-cross", at=5, subject="MIA")
    ids["cross_llm"] = _rec(conn, "g-cross", at=6, price=0.44, subject="MIA",
                            predictor="llm")
    ids["rung_a"] = _rec(conn, "g-rungs", at=0, subject="MIA", rung=-1.5,
                         pass_kind="early")
    ids["rung_b"] = _rec(conn, "g-rungs", at=30, subject="MIA", rung=-2.5)
    _item_5_back(conn)
    _withdraw(conn, ids["gone"])
    return ids


def _counted(conn, who: str) -> set[int]:
    return {r[0] for r in conn.execute(
        "SELECT r.id FROM recommendations r WHERE r.sport = 'mlb'"
        + recommend.counted_once(conn, predictor=who))}


# --- the rule -----------------------------------------------------------------

def test_the_rule_counts_a_pair_of_one_distinct_bet_once_and_nothing_else(conn, shapes):
    mine, theirs = _counted(conn, "statistical"), _counted(conn, "llm")
    assert mine == {shapes[k] for k in (
        "single", "morning", "over", "t1", "after", "spread_same_game",
        "cross_stat", "rung_a", "rung_b")}
    assert theirs == {shapes["under"], shapes["cross_llm"]}
    aside = {who: {r["id"]: r["why"] for r in
                   recommend.not_counted_once(conn, sport="mlb", predictor=who)}
             for who in ("statistical", "llm")}
    assert aside == {"statistical": {shapes["final"]: recommend.REPEAT,
                                     shapes["t2"]: recommend.REPEAT,
                                     shapes["t3"]: recommend.REPEAT},
                     "llm": {}}
    # EVERY STANDING ROW IS EXACTLY ONE FORECASTER'S, AND COUNTED OR A
    # REPEAT; a withdrawn row is neither
    standing = {r[0] for r in conn.execute(
        "SELECT r.id FROM recommendations r WHERE 1 = 1" + recommend.not_withdrawn(conn))}
    everything = mine | theirs | set(aside["statistical"])
    assert everything == standing and not (mine & theirs)
    assert not ((mine | theirs) & set(aside["statistical"]))
    assert shapes["gone"] not in everything


def test_first_is_by_stamp_then_number_whatever_order_sqlite_hands_back(conn):
    """Two passes of one question written in one second count as the lower
    number -- as `standing_recommendations` orders them.

    FLIPPED BY QUESTION 22 (2026-09-28): until then this test wrote the two
    FORECASTERS on one side in one second and counted them once, as the
    lower number; they are two distinct bets now, each counted in its own
    forecaster's line ("Same-side pairs count once only within one
    forecaster")."""
    _game(conn, "g")
    _before_item_5(conn)
    a = _rec(conn, "g", at=5, subject="MIA", pass_kind="early")
    b = _rec(conn, "g", at=5, price=0.44, subject="MIA")
    _game(conn, "h")
    c = _rec(conn, "h", at=5, subject="MIA")
    d = _rec(conn, "h", at=5, price=0.44, subject="MIA", predictor="llm")
    _item_5_back(conn)
    assert a < b and a in _counted(conn, "statistical")
    assert b not in _counted(conn, "statistical") | _counted(conn, "llm")
    assert [s["id"] for s in recommend.standing_recommendations(conn, "g", "spread")] == [a, b]
    # the two forecasters: two bets, each its own forecaster's
    assert c in _counted(conn, "statistical") and d in _counted(conn, "llm")


def test_the_door_is_one_forecasters_and_refuses_an_alias_it_would_shadow(conn):
    for alias in ("q12_other", "q12_other_forecast", "q12_own_forecast",
                  "q22_whose", "r; DROP TABLE x"):
        with pytest.raises(ValueError):
            recommend.counted_once(conn, alias=alias, predictor="statistical")
    # A COUNT ACROSS BOTH CANNOT BE WRITTEN BY LEAVING AN ARGUMENT OUT
    with pytest.raises(TypeError):
        recommend.counted_once(conn)                      # noqa: the point
    for who in (None, "both", "all", "LLM", "statistical' OR 1=1 --"):
        with pytest.raises(recommend.PooledCount):
            recommend.counted_once(conn, predictor=who)
        with pytest.raises(recommend.PooledCount):
            recommend.not_counted_once(conn, sport="mlb", predictor=who)
        with pytest.raises(recommend.PooledCount):
            recommend.regraded(conn, sport="mlb", predictor=who)
        with pytest.raises(recommend.PooledCount):
            recommend.withdrawn(conn, sport="mlb", predictor=who)


def test_the_record_shows_rows_as_written(conn, shapes):
    """No row changes, none is added, and no table: every measurement is
    read, and the record is exactly as it was."""
    tables = ("recommendations", "recommendation_closes", "recommendation_voids",
              "recommendation_regrades")
    before = {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1")]
              for t in tables}
    schema = [tuple(r) for r in conn.execute("SELECT * FROM sqlite_master ORDER BY name")]
    views.scorecard(conn, "mlb")
    calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    coverage.stopped(conn, "mlb", now=ON_THE_DAY)
    for who in ("statistical", "llm"):
        recommend.regraded(conn, sport="mlb", predictor=who)
    assert {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1")]
            for t in tables} == before
    assert [tuple(r) for r in conn.execute(
        "SELECT * FROM sqlite_master ORDER BY name")] == schema
    # THE WRITE RULE STILL READS THE PAIRS AS THEY STAND (item 5): a write
    # rule, keyed by game and market across forecasters, which question 22
    # did not touch
    assert [s["id"] for s in recommend.standing_recommendations(
        conn, "g-total", "total")] == [shapes["over"], shapes["under"]]


# --- the closing line and all it feeds ---------------------------------------

def test_the_closing_line_counts_each_forecasters_bets_once(conn, shapes):
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    spread = _entry(report, "spread", "statistical")
    # single, morning, t1, after, the total game's own spread, the
    # statistical model's side of the cross pair and both rungs: eight at
    # +3.0 -- never the final (+9.0), t2, t3 or the withdrawn one
    assert spread["n"] == 8 and spread["mean_cents"] == 3.0
    assert spread["repeats"] == 3
    assert spread["category_label"] == "point spread, statistical"
    assert ("3 more repeat this forecaster's earlier recommendations on the "
            "same question and side and are counted once, as the earlier "
            "one") in spread["words"]
    # THE REASONING PASS'S SIDE OF THE CROSS PAIR IS ITS OWN (+5.0)
    theirs = _entry(report, "spread", "llm")
    assert theirs["n"] == 1 and theirs["mean_cents"] == 5.0
    assert theirs["repeats"] == 0 and "repeat" not in theirs["words"]
    assert theirs["category_label"] == "point spread, reasoning pass"
    # 45/46'S SHAPE: EACH ONCE, IN ITS OWN FORECASTER'S TOTAL
    assert _entry(report, "total", "statistical")["n"] == 1
    assert _entry(report, "total", "statistical")["mean_cents"] == 1.5
    assert _entry(report, "total", "llm")["n"] == 1
    assert _entry(report, "total", "llm")["mean_cents"] == -1.5
    # market by market, each forecaster's line under it
    assert [(e["market"], e["predictor"]) for e in report["markets"]] == [
        ("spread", "statistical"), ("spread", "llm"),
        ("total", "statistical"), ("total", "llm")]
    mine, other = _line(report, "statistical"), _line(report, "llm")
    assert mine["n"] == 9 and mine["repeats"] == 3
    assert other["n"] == 2 and other["repeats"] == 0
    assert mine["set_aside"] == {"n": 3, "measured": 3, "closed": 3,
                                 "awaiting_close": 0}
    assert mine["window_line"]["n"] == 9 and other["window_line"]["n"] == 2
    # NO TOTAL OVER BOTH, AND NO BOTH-SIDES ROW: the top level carries only
    # what the allow-list names
    assert set(report) <= set(audit.CLOSING_LINE_KEYS)
    for key in ("n", "window_line", "awaiting_close", "repeats", "both_sides",
                "both_sides_line", "withdrawn", "regraded", "set_aside"):
        assert key not in report, key
    calibration.assert_every_figure_has_n(report)
    audit.check_no_withdrawn_recommendation_counted(conn, report)
    audit.check_each_pair_counted_once(conn, report)


def test_45_and_46_count_once_each_in_their_own_forecasters_line(conn):
    """QUESTION 22 REVERSED QUESTION 12 FOR 45/46 (2026-09-28): "each counts
    once in its own forecaster's line, and the 'Both sides, no position' row
    goes." Their shape alone: the statistical model's over and the
    reasoning pass's under of one total, one quote, one second."""
    _game(conn, "g")
    _before_item_5(conn)
    over = _rec(conn, "g", market="total", side="yes", at=30, price=0.485,
                close=0.50, subject="TOR at BAL")
    under = _rec(conn, "g", market="total", side="no", at=30, price=0.485,
                 close=0.50, subject="TOR at BAL", predictor="llm")
    _item_5_back(conn)
    assert _counted(conn, "statistical") == {over}
    assert _counted(conn, "llm") == {under}
    for who in ("statistical", "llm"):
        assert recommend.not_counted_once(conn, sport="mlb", predictor=who) == []
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    assert _entry(report, "total", "statistical")["n"] == 1
    assert _entry(report, "total", "llm")["n"] == 1
    assert "both_sides_line" not in report and "both_sides" not in report
    served = views.scorecard(conn, "mlb")["closing_line"]
    assert "both_sides_line" not in served
    assert not hasattr(recommend, "BOTH_SIDES_LABEL")
    assert not hasattr(language, "both_sides_recommendations_line")


def test_a_sport_with_no_pair_names_none(conn):
    _game(conn, "g")
    _rec(conn, "g")
    report = calibration.clv_report(conn, sport="mlb")
    for block in report["forecasters"]:
        assert block["repeats"] == 0
    assert report["markets"][0]["repeats"] == 0
    assert "repeat" not in report["markets"][0]["words"]


def test_the_words_for_one_repeat():
    assert language.clv_line(2, None, None, 50, repeats=1).endswith(
        " · 1 more repeats this forecaster's earlier recommendation on the "
        "same question and side and is counted once, as the earlier one")
    for words in (language.clv_line(2, None, None, 50, repeats=1),
                  language.clv_line(2, None, None, 50, repeats=3)):
        assert audit.plain_words_violations(words) == []
        assert audit.advice_word_faults(words) == []


def test_an_open_repeat_is_not_awaiting_a_close(conn):
    _game(conn, "g")
    _before_item_5(conn)
    _rec(conn, "g", at=0, close=None, subject="MIA", pass_kind="early")
    _rec(conn, "g", at=30, close=None, subject="MIA")
    _item_5_back(conn)
    report = calibration.clv_report(conn, sport="mlb")
    mine = _line(report, "statistical")
    assert mine["awaiting_close"] == 1
    assert mine["set_aside"]["awaiting_close"] == 1 and mine["repeats"] == 1
    assert report["markets"][0]["repeats"] == 1 and report["markets"][0]["n"] == 0
    audit.check_no_withdrawn_recommendation_counted(conn, report)
    audit.check_each_pair_counted_once(conn, report)


def test_the_kill_criterion_counts_a_pair_once(conn, monkeypatch):
    """Forty-eight singles and one same-side pair of one question, every
    close -1.0c: 49 counted, so the kill (fifty) stops nothing; counted
    twice, it would have stopped the market on a close it read twice."""
    for i in range(48):
        _game(conn, f"g{i}")
        _rec(conn, f"g{i}", at=i, price=0.50, close=0.49)
    _game(conn, "g-pair")
    _before_item_5(conn)
    _rec(conn, "g-pair", at=100, price=0.50, close=0.49, subject="MIA",
         pass_kind="early")
    _rec(conn, "g-pair", at=160, price=0.50, close=0.49, subject="MIA")
    _item_5_back(conn)
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    assert _line(report, "statistical")["n"] == 49
    assert coverage.stopped(conn, "mlb", now=ON_THE_DAY) == {}
    # the rule removed, as it was until 2026-09-27: fifty, and stopped
    current = importlib.import_module(recommend.__name__)
    monkeypatch.setattr(current, "_an_earlier_row_of_the_same_bet",
                        lambda conn, alias: "0")
    assert _line(calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY),
                 "statistical")["n"] == 50
    assert ("spread", "statistical") in coverage.stopped(conn, "mlb", now=ON_THE_DAY)


def test_the_kill_criterion_reads_each_forecasters_line(conn):
    """QUESTION 22 (2026-09-28): the kill reads each forecaster's closing
    line. Thirty of each forecaster's closes at -1.0c: neither line holds
    fifty, so nothing stops -- where the line as it was, both forecasters in
    one count, held sixty and stopped the market for both."""
    for i in range(30):
        for who in ("statistical", "llm"):
            gid = f"{who}-{i}"
            _game(conn, gid)
            _rec(conn, gid, at=i, price=0.50, close=0.49, predictor=who)
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    assert _line(report, "statistical")["n"] == _line(report, "llm")["n"] == 30
    assert coverage.stopped(conn, "mlb", now=ON_THE_DAY) == {}
    for who in ("statistical", "llm"):
        verdict = coverage.priceable(conn, "mlb", "spread", predictor=who,
                                     now=ON_THE_DAY)
        assert "stopped after" not in verdict["why"]
    # and twenty more of the statistical model's stop ITS picks alone
    for i in range(30, 50):
        _game(conn, f"statistical-{i}")
        _rec(conn, f"statistical-{i}", at=i, price=0.50, close=0.49)
    stopped = coverage.stopped(conn, "mlb", now=ON_THE_DAY)
    assert set(stopped) == {("spread", "statistical")}
    assert "stopped after 50" in coverage.priceable(
        conn, "mlb", "spread", predictor="statistical", now=ON_THE_DAY)["why"]
    assert "stopped after" not in coverage.priceable(
        conn, "mlb", "spread", predictor="llm", now=ON_THE_DAY)["why"]


def test_a_withdrawn_earlier_row_leaves_its_later_row_counted(conn, shapes):
    """PAIRED AFTER THE WITHDRAWALS: NFL 73, 75, 76 and 78's shape."""
    assert shapes["after"] in _counted(conn, "statistical")
    assert shapes["after"] not in {r["id"] for r in recommend.not_counted_once(
        conn, sport="mlb", predictor="statistical")}


def test_withdrawing_the_first_of_a_pair_makes_the_second_count(conn):
    _game(conn, "g")
    _before_item_5(conn)
    first = _rec(conn, "g", at=0, subject="MIA", pass_kind="early")
    second = _rec(conn, "g", at=30, subject="MIA")
    _item_5_back(conn)
    assert _counted(conn, "statistical") == {first}
    _withdraw(conn, first)
    assert _counted(conn, "statistical") == {second}
    assert recommend.not_counted_once(conn, sport="mlb", predictor="statistical") == []


# --- the re-grade line --------------------------------------------------------

def _regraded_world(conn) -> dict:
    """Recs 3/10 and 21/26 as the record holds them -- each pair one
    forecaster's morning and final pass on one question of its game, both
    on the no side -- and rec 56 on its own. 3, 10, 26 and 56 were let
    through by the yes price (question 9's four); 21 cleared on its cost."""
    for game in ("p1", "p2", "p3"):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " 'AAA', 'BBB', '2026-09-26T00:00:00Z', 'scheduled', '2026-09-08')",
            (game,))

    def forecast(game: str, pass_kind: str) -> int:
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES"
            " ('2026-09-07T00:00:00Z', 'mlb', ?, 'spread', 'AAA', -1.5, 0.62,"
            " 'cover', 'statistical', ?, 'fs2', '{}', 'test')", (game, pass_kind))
        return conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]

    _before_item_5(conn)
    for rid, game, pass_kind, price, edge, created in (
            (3, "p1", "early", 0.375, 2.09, "2026-09-07T20:52:31Z"),
            (10, "p1", "final", 0.375, 2.30, "2026-09-08T21:33:31Z"),
            (21, "p2", "early", 0.375, 3.50, "2026-09-09T12:09:23Z"),
            (26, "p2", "final", 0.395, 2.84, "2026-09-09T21:32:20Z"),
            (56, "p3", "final", 0.39, 3.03, "2026-09-24T05:21:25Z")):
        conn.execute(
            "INSERT INTO recommendations (id, prediction_id, sport, game_id,"
            " market, side, fair_value, price, edge_cents, size_kind,"
            " size_units, gate_n, created_utc) VALUES (?, ?, 'mlb', ?,"
            " 'spread', 'no', 0.40, ?, ?, 'flat', 1.0, 53, ?)",
            (rid, forecast(game, pass_kind), game, price, edge, created))
    _item_5_back(conn)
    assert [g["id"] for g in recommend.let_through_by_the_yes_price(conn)] == [3, 10, 26, 56]
    assert recommend.write_regrades(conn, [3, 10, 26, 56]) == {"written": 4, "already": 0}


def test_the_regrade_line_counts_a_pair_once(conn):
    """Question 9's four labels stay on the record; the line beside the
    closing line counts the labelled rows the rule counts: rec 3 (its
    pair's first) and rec 56. Rec 10 is its pair's second, and rec 26's pair
    counts as rec 21, which cleared. All the statistical model's: the
    reasoning pass's line holds none."""
    _regraded_world(conn)
    assert conn.execute("SELECT COUNT(*) FROM recommendation_regrades").fetchone()[0] == 4
    assert [g["id"] for g in recommend.regraded(
        conn, sport="mlb", predictor="statistical")] == [3, 56]
    assert recommend.regraded(conn, sport="mlb", predictor="llm") == []
    report = calibration.clv_report(conn, sport="mlb")
    mine = _line(report, "statistical")
    assert mine["regraded"] == 2 and mine["regraded_line"]["n"] == 2
    assert mine["regraded_line"]["label"] == "Would not have cleared, statistical"
    assert "3.34% and 4.97%" in mine["regraded_line"]["words"]
    assert _line(report, "llm")["regraded_line"] is None
    audit.check_each_pair_counted_once(conn, report)
    # the recount knows the rule for the line too: counting all four is caught
    planted = dict(report, forecasters=[
        dict(b, regraded=4) if b["predictor"] == "statistical" else b
        for b in report["forecasters"]])
    with pytest.raises(audit.LawViolation, match="would not have cleared"):
        audit.check_each_pair_counted_once(conn, planted)
    # the selection that writes labels still reads the rows as written
    assert [g["id"] for g in recommend.let_through_by_the_yes_price(conn)] == [3, 10, 26, 56]


# --- the empty-bar count --------------------------------------------------------

def _empty_bar():
    path = config.PACKAGE_ROOT.parent / "tools" / "empty_bar.py"
    spec = importlib.util.spec_from_file_location("empty_bar_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tested(report: dict, who: str) -> list[dict]:
    block = next(b for b in report["forecasters"] if b["predictor"] == who)
    return [s for s in block["spans"] if s["days_the_bar_could_be_tested"]]


def test_a_day_whose_only_recommendation_repeats_one_cleared_nothing(conn):
    """A pair of one question written a day apart: the later day holds only
    the repeat, and nothing that counts cleared the bar that day."""
    _game(conn, "g", kickoff=2000)
    _before_item_5(conn)
    _rec(conn, "g", at=0, close=None, subject="MIA", pass_kind="early")
    _rec(conn, "g", at=24 * 60, close=None, subject="MIA")
    _item_5_back(conn)
    # each recommendation's own claim makes its day one the bar was tested
    second = _at(24 * 60)[:10]
    tested = _tested(_empty_bar().spans(conn, "mlb"), "statistical")
    assert [s["days_the_bar_could_be_tested"] for s in tested] == [2]
    assert tested[0]["empty_days"] == [second]


def test_a_day_cleared_by_the_other_forecaster_is_empty_for_this_one(conn):
    """ONE FORECASTER'S DAYS (question 22, 2026-09-28): the statistical
    model's bar was tested on a day only the reasoning pass cleared. Pooled,
    the day cleared; the statistical model's own count says it did not."""
    _game(conn, "g")
    _game(conn, "h")
    _rec(conn, "g", at=0, close=None, predictor="llm")
    # the statistical model's forecast on another game that day, its claim
    # written and its recommendation withdrawn: nothing of its stands
    _withdraw(conn, _rec(conn, "h", at=5, close=None))
    report = _empty_bar().spans(conn, "mlb")
    day = _at(0)[:10]
    assert day == _at(5)[:10]
    theirs = _tested(report, "llm")
    assert theirs[0]["days_the_bar_could_be_tested"] == 1
    assert theirs[0]["empty_days"] == []
    mine = _tested(report, "statistical")
    assert mine[0]["days_the_bar_could_be_tested"] == 1
    assert mine[0]["empty_days"] == [day]


# --- the guards -----------------------------------------------------------------

def _patched(monkeypatch, name, value):
    current = importlib.import_module(recommend.__name__)
    monkeypatch.setattr(current, name, value)
    return current


def test_the_recount_names_a_pair_the_door_let_through(conn, shapes, monkeypatch):
    """The rule removed, the forecaster kept: every repeat counted."""
    _patched(monkeypatch, "_an_earlier_row_of_the_same_bet",
             lambda conn, alias: "0")
    counted = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    # the withdrawn recount's question is withdrawal, and it is silent
    assert audit.withdrawn_counted_faults(conn, counted) == []
    with pytest.raises(audit.LawViolation,
                       match="A RECOMMENDATION COUNT IS POOLED, OR A PAIR "
                             "COUNTED TWICE") as exc:
        audit.check_each_pair_counted_once(conn, counted)
    aside = sorted(shapes[k] for k in ("final", "t2", "t3"))
    assert ("make the difference: " + ", ".join(map(str, aside)) + "."
            in str(exc.value))
    with pytest.raises(audit.LawViolation):
        views.scorecard(conn, "mlb")                   # cannot reach the API


def _q12_pairing(alias: str) -> str:
    """QUESTION 12'S PAIR, as it stood until 2026-09-28: one game and market
    across forecasters and rungs, on one side, earlier."""
    o = recommend._OTHER
    return (f"{o}.game_id = {alias}.game_id AND {o}.market = {alias}.market"
            f" AND {o}.side = {alias}.side AND {o}.id <> {alias}.id"
            f" AND ({o}.created_utc < {alias}.created_utc"
            f"      OR ({o}.created_utc = {alias}.created_utc"
            f"          AND {o}.id < {alias}.id))")


def _no_rung_pairing(alias: str) -> str:
    """A pair keyed without the rung: two rungs of one game one question."""
    o, of, mine = (recommend._OTHER, recommend._OTHER_FORECAST,
                   recommend._OWN_FORECAST)
    return (f"{of}.predictor IS {mine}.predictor AND {of}.game_id IS {mine}.game_id"
            f" AND {of}.market_type IS {mine}.market_type"
            f" AND {of}.subject IS {mine}.subject"
            f" AND {o}.side = {alias}.side AND {o}.id <> {alias}.id"
            f" AND ({o}.created_utc < {alias}.created_utc"
            f"      OR ({o}.created_utc = {alias}.created_utc"
            f"          AND {o}.id < {alias}.id))")


def test_a_pair_keyed_across_forecasters_is_named(conn, shapes, monkeypatch):
    """QUESTION 12'S KEY RESTORED (the reversal's planting in small): the
    reasoning pass's side of the cross pair is set aside as a repeat of the
    statistical model's. Each forecaster's count still adds up to itself;
    the recount by the one key names the row."""
    _patched(monkeypatch, "pairs_with", _q12_pairing)
    counted = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    assert _entry(counted, "spread", "llm") is not None
    assert _entry(counted, "spread", "llm")["n"] == 0
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_each_pair_counted_once(conn, counted)
    assert f"make the difference: {shapes['cross_llm']}." in str(exc.value)
    # and the source scan reads the rule's own text
    assert any("pairs_with" in f for f in audit.distinct_bet_key_faults())


def test_a_pair_keyed_without_the_rung_is_named(conn, shapes, monkeypatch):
    _patched(monkeypatch, "pairs_with", _no_rung_pairing)
    counted = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_each_pair_counted_once(conn, counted)
    assert str(shapes["rung_b"]) in str(exc.value)
    assert any("pairs_with" in f for f in audit.distinct_bet_key_faults())


def test_a_count_pooling_the_forecasters_is_named(conn, shapes, monkeypatch):
    """Three ways a count pools: a door that forgets whose, a report with a
    total over both, a line that names no forecaster. Each refused by name."""
    # 1. THE DOOR COUNTS BOTH FORECASTERS' ROWS IN EACH LINE
    current = importlib.import_module(recommend.__name__)
    shipped = current.counted_once

    def forgetful(conn, alias="r", *, predictor):
        return (current.not_withdrawn(conn, alias) + " AND NOT "
                + current._an_earlier_row_of_the_same_bet(conn, alias))

    monkeypatch.setattr(current, "counted_once", forgetful)
    pooled = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    monkeypatch.setattr(current, "counted_once", shipped)
    assert _line(pooled, "statistical")["n"] == 11
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_each_pair_counted_once(conn, pooled)
    # the statistical spread line holds the reasoning pass's side of the
    # cross pair, and the statistical total its under: each named
    assert (f"the spread line for statistical reports 9 measured closes in "
            f"its count or before its window where that forecaster's "
            f"distinct bets counted once hold 8. A row that would make the "
            f"difference: {shapes['cross_llm']}.") in str(exc.value)
    assert f"make the difference: {shapes['under']}." in str(exc.value)
    # 2. A TOTAL OVER BOTH, AS THE PAYLOAD CARRIED ONE UNTIL 2026-09-28
    lawful = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    audit.check_each_pair_counted_once(conn, lawful)
    total = dict(lawful, n=sum(b["n"] for b in lawful["forecasters"]))
    with pytest.raises(audit.LawViolation, match="for both forecasters at once"):
        audit.check_each_pair_counted_once(conn, total)
    # 3. ONE MARKET'S LINE NAMING NOBODY, ITS TWO LINES SUMMED
    merged = [e for e in lawful["markets"] if e["market"] != "total"] + [
        dict(_entry(lawful, "total", "statistical"), predictor=None, n=2)]
    with pytest.raises(audit.LawViolation, match="not one of"):
        audit.check_each_pair_counted_once(conn, dict(lawful, markets=merged))


def test_two_sides_of_one_distinct_bet_are_refused_by_name(conn):
    """Item 5's rule cannot write this and none is on the record; the rule
    pairs a side only with itself, and no ruling says how two sides of one
    question are counted -- so the recount refuses and says it needs one."""
    _game(conn, "g")
    _before_item_5(conn)
    over = _rec(conn, "g", market="total", side="yes", at=0, subject="Q",
                pass_kind="early")
    under = _rec(conn, "g", market="total", side="no", at=30, subject="Q")
    _item_5_back(conn)
    report = calibration.clv_report(conn, sport="mlb")
    with pytest.raises(audit.LawViolation, match="needs the operator's") as exc:
        audit.check_each_pair_counted_once(conn, report)
    assert f"recommendations {[over, under]} take both sides" in str(exc.value)


def test_a_report_that_counts_a_repeat_and_names_it_too_is_caught(conn, shapes,
                                                                    monkeypatch):
    """Only the counting door broken, its other side intact: the repeat is
    in the count and beside it. The pair recount sees the count; the
    withdrawn recount sees a row added up twice."""
    current = importlib.import_module(recommend.__name__)
    rule = current._an_earlier_row_of_the_same_bet
    shipped = current.counted_once

    def door_only(conn, alias="r", *, predictor):
        monkeypatch.setattr(current, "_an_earlier_row_of_the_same_bet",
                            lambda conn, alias: "0")
        try:
            return shipped(conn, alias, predictor=predictor)
        finally:
            monkeypatch.setattr(current, "_an_earlier_row_of_the_same_bet", rule)

    monkeypatch.setattr(current, "counted_once", door_only)
    counted = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    assert audit.pair_counted_faults(conn, counted)
    assert audit.withdrawn_counted_faults(conn, counted)


def test_a_report_that_hides_what_it_set_aside_is_caught(conn, shapes):
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    for key, value in (("repeats", 0),
                       ("set_aside", {"n": 0, "measured": 0, "closed": 0,
                                      "awaiting_close": 0})):
        planted = dict(report, forecasters=[
            dict(b, **{key: value}) if b["predictor"] == "statistical" else b
            for b in report["forecasters"]])
        assert audit.pair_counted_faults(conn, planted), key
    # the withdrawn recount adds the set-aside rows back; without them it
    # finds standing rows missing
    planted = dict(report, forecasters=[
        dict(b, set_aside={}) if b["predictor"] == "statistical" else b
        for b in report["forecasters"]])
    assert audit.withdrawn_counted_faults(conn, planted)
    # a forecaster's line missing altogether is named
    only_one = dict(report, forecasters=[_line(report, "statistical")])
    assert any("no line for LLM" in f
               for f in audit.pair_counted_faults(conn, only_one))


# --- the prover's (2026-09-28): what got past the first guards -----------------

def _later_pairing(alias: str) -> str:
    """The pair keyed by the one function, but its LATER row counted."""
    from gridiron import bet

    o = recommend._OTHER
    return (bet.same(recommend._OTHER_FORECAST, recommend._OWN_FORECAST)
            + f" AND {o}.side = {alias}.side AND {o}.id <> {alias}.id"
            f" AND ({o}.created_utc > {alias}.created_utc"
            f"      OR ({o}.created_utc = {alias}.created_utc"
            f"          AND {o}.id > {alias}.id))")


def test_a_door_counting_the_later_row_is_named(conn, shapes, monkeypatch):
    """Every count kept -- one of each pair counted, one set aside -- and the
    mean moved: the morning's +3.0c out, the final's +9.0c in. The recount
    works out each line's mean and share, and the source scan pins the
    earlier row, which is all it can see before the first clean read."""
    _patched(monkeypatch, "pairs_with", _later_pairing)
    later = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    assert _entry(later, "spread", "statistical")["n"] == 8
    assert _entry(later, "spread", "statistical")["mean_cents"] == 3.75
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_each_pair_counted_once(conn, later)
    assert "gives its mean as 3.75 where the rows the rule counts give 3.0" \
        in str(exc.value)
    assert any("not its earlier one" in f for f in audit.distinct_bet_key_faults())


def test_a_sentence_stating_another_count_than_its_figure_is_named(conn, shapes):
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    audit.check_each_pair_counted_once(conn, report)
    entries = [dict(e, words=e["words"].replace("8 of 50", "11 of 50"))
               if (e["market"], e["predictor"]) == ("spread", "statistical")
               else e for e in report["markets"]]
    with pytest.raises(audit.LawViolation, match="gives its words as"):
        audit.check_each_pair_counted_once(conn, dict(report, markets=entries))
    # and a window line saying the two forecasters' sum
    blocks = [dict(b, window_line=dict(b["window_line"], words=b["window_line"][
        "words"].replace("9 recommendations", "11 recommendations")))
        if b["predictor"] == "statistical" else b for b in report["forecasters"]]
    with pytest.raises(audit.LawViolation, match="window line reads"):
        audit.check_each_pair_counted_once(conn, dict(report, forecasters=blocks))
    # and a line labelled for nobody
    entries = [dict(e, category_label="point spread")
               if (e["market"], e["predictor"]) == ("spread", "llm") else e
               for e in report["markets"]]
    with pytest.raises(audit.LawViolation, match="gives its label as"):
        audit.check_each_pair_counted_once(conn, dict(report, markets=entries))


def test_a_total_over_both_under_a_new_name_is_named(conn, shapes):
    report = calibration.clv_report(conn, sport="mlb", now=ON_THE_DAY)
    both = sum(b["n"] for b in report["forecasters"])
    with pytest.raises(audit.LawViolation, match="for both forecasters at once"):
        audit.check_each_pair_counted_once(
            conn, dict(report, recommendations_so_far=both))


def test_a_pair_rule_widened_beside_the_key_is_named(monkeypatch):
    shipped = recommend.pairs_with

    def widened(alias: str) -> str:
        o = recommend._OTHER
        return (shipped(alias) + f" OR ({o}.game_id = {alias}.game_id"
                f" AND {o}.market = {alias}.market)")

    _patched(monkeypatch, "pairs_with", widened)
    assert any("pairs_with" in f and "one distinct-bet key" in f
               for f in audit.distinct_bet_key_faults())


def test_a_close_written_between_the_line_and_its_recount_is_no_fault(
        tmp_path, monkeypatch):
    """ONE INSTANT (the prover of question 22, 2026-09-28; step 1's
    precedent): on the live record the closer writes while the Record page
    is read. A recommendation closed and measured between the closing
    line's read and its recount's made an honest page refuse itself -- "the
    statistical closing line reports 1 ... holds 2", a 500 for nothing --
    until the line, the kill read of it and both recounts were read in one
    instant (`calibration.scorecard`, `db.one_instant`). The line counts the
    instant it read, and the next read counts the new close."""
    path = tmp_path / "race.db"
    conn = db.open_db(path)
    _game(conn, "g")
    _rec(conn, "g")
    conn.commit()
    current = importlib.import_module(calibration.__name__)
    shipped = current.clv_report
    written = []

    def line_then_a_close(conn, **kw):
        report = shipped(conn, **kw)
        if not written:                    # once: the closer runs once
            other = db.connect(path)
            _game(other, "h")
            _rec(other, "h", at=90)
            other.commit()
            other.close()
            written.append(True)
        return report

    monkeypatch.setattr(current, "clv_report", line_then_a_close)
    served = views.scorecard(conn, "mlb")["closing_line"]
    assert _line(served, "statistical")["n"] == 1
    monkeypatch.setattr(current, "clv_report", shipped)
    assert _line(views.scorecard(conn, "mlb")["closing_line"], "statistical")["n"] == 2


def test_every_measurement_reads_the_counted_once_door():
    audit.check_every_measurement_counts_each_pair_once()
    audit.check_every_recommendation_reader_uses_the_door()


def test_the_pair_is_keyed_by_the_one_function():
    from gridiron import bet

    assert bet.same(recommend._OTHER_FORECAST, recommend._OWN_FORECAST) in \
        recommend.pairs_with("r")
    assert audit.distinct_bet_key_faults() == []


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


def test_the_renderer_draws_each_forecasters_line_and_no_both_sides_row():
    js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "both_sides_line" not in js
    at = js.index("line.forecasters")
    assert js.index("block.window_line") > at
    assert "entry.category_label" in js[at:at + 3000]
    assert js.index("block.withdrawn_line") < js.index("block.regraded_line")
    assert "stop.category_label" in js
