"""The recommendation (THE_RECOMMENDATION R2-R4, 2026-09-07): an edge that
survives the fee, a size that refuses to vary on an unproven market, a parlay
that is refused, nothing sized in-game, and the closing line recorded once."""
from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import audit, calibration, config, db, language, shortlist
from gridiron.market import recommend

DIST = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})


def _world(tmp_path, *, status="scheduled", kickoff="2026-09-09T00:00:00Z"):
    conn = db.open_db(tmp_path / "rec.db")
    # A STARTED GAME CARRIES A SCORE, and the schema insists on it: the pair
    # (status, scores) is checked, so a live game with no score is refused.
    scores = (None, None) if status == "scheduled" else (2, 1)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('g0', 'mlb', 2026, 1, 'R', 'AAA', 'BBB', ?, ?, '2026-09-08',"
        " ?, ?)", (kickoff, status) + scores)
    conn.commit()
    return conn


@pytest.fixture(autouse=True)
def _covered(monkeypatch):
    """These tests are about the price, not about the coverage list.

    THE_PRICED (2026-09-07) put a measured coverage list in front of the
    recommendation engine, so a market nobody has measured is priced by nobody
    -- correct, and not what these tests are checking. Coverage has its own
    tests in `test_priced.py`.
    """
    from gridiron.priced import coverage

    monkeypatch.setattr(coverage, "priceable",
                        lambda conn, sport, market: {
                            "priceable": True, "market": market,
                            "why": "covered, in this test"})


def _pick(conn, *, prob=0.62, implied=0.46, subject="AAA", market="moneyline"):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'mlb', 'g0', ?, ?, NULL, ?, 'win',"
        " 'statistical', 'final', 'fs2', ?, 'test')",
        (market, subject, prob, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    if implied is not None:
        # THE VENUE'S OWN PRICE, through the at-the-line claim the engine reads.
        # A market snapshot is a bookmaker's line republished by a media API;
        # the recommendation is priced, fed and closed at one venue, so the
        # fixture provides that venue's row.
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " implied_prob, kind) VALUES (?, '2026-09-07T01:00:00Z', 'test', ?,"
            " 'open_at_predict')", (pid, implied))
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " fetched_utc) VALUES ('kalshi', ?, 'e', 'mlb', 'g0', ?,"
            " 'home_margin', -1.5, 'home', ?, ?, '2026-09-07T01:00:00Z')",
            (f"t{pid}", market, implied - 0.01, implied + 0.01))
        quote_id = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
            " sport, game_id, market, quantity, line, side, shape,"
            " dist_mean, dist_sd, model_prob, venue_price, venue_implied,"
            " price_basis, created_utc)"
            " VALUES (?, ?, 'kalshi', 'mlb', 'g0', ?, 'home_margin', -1.5,"
            " 'home', 'rung_differs_margin', 2.0, 13.0, ?, ?, ?, 'mid',"
            " '2026-09-07T01:30:00Z')",
            (pid, quote_id, market, prob, implied, implied))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    return pid


def test_an_edge_that_does_not_clear_the_fee_is_no_edge():
    # the fee is largest at a coin flip, which is where the raw disagreement
    # looks most tempting
    assert recommend.fee(0.5) > recommend.fee(0.9)
    got = recommend.side_for(0.51, 0.50)
    assert got["side"] is None
    assert "clears the fee" in got["why"]
    # a real gap survives it, and the number is what is left afterwards
    got = recommend.side_for(0.62, 0.46)
    assert got["side"] == "yes"
    assert got["edge_cents"] == pytest.approx(
        (0.62 - 0.46 - recommend.fee(0.46)) * 100, abs=1e-6)
    # the other side is the one that clears when the model is under the price
    assert recommend.side_for(0.30, 0.46)["side"] == "no"
    # no price, no opinion
    assert recommend.side_for(0.62, None)["side"] is None


def test_below_the_gate_the_size_does_not_move_with_confidence():
    lean = recommend.size_for(model_prob=0.62, price=0.50, settled=3)
    strong = recommend.size_for(model_prob=0.92, price=0.50, settled=3)
    assert lean["kind"] == strong["kind"] == "flat"
    assert lean["units"] == strong["units"] == config.FLAT_UNIT
    assert "no measured edge" in lean["why"]


def test_a_measured_sample_is_not_a_measured_edge():
    """286 settled questions on a market the model is BEHIND on is not a
    licence to size up. Both conditions or the flat unit."""
    behind = recommend.size_for(model_prob=0.62, price=0.50, settled=400,
                                measured_edge=False)
    assert behind["kind"] == "flat" and behind["units"] == config.FLAT_UNIT
    assert "NOT ahead" in behind["why"]
    unknown = recommend.size_for(model_prob=0.62, price=0.50, settled=400,
                                 measured_edge=None)
    assert unknown["kind"] == "flat"
    ahead = recommend.size_for(model_prob=0.62, price=0.50, settled=400,
                               measured_edge=True)
    assert ahead["kind"] == "fraction" and ahead["units"] > 0


def test_the_fraction_is_a_quarter_of_kelly_and_capped():
    full = recommend.kelly_fraction(0.62, 0.50)
    sized = recommend.size_for(model_prob=0.62, price=0.50, settled=400,
                               measured_edge=True)
    assert sized["fraction"] == pytest.approx(
        min(config.KELLY_FRACTION * full, config.MAX_FRACTION))
    assert sized["fraction"] < full          # never full Kelly
    # a wild claim is capped rather than trusted
    wild = recommend.size_for(model_prob=0.97, price=0.30, settled=400,
                              measured_edge=True)
    assert wild["fraction"] == config.MAX_FRACTION


def test_the_blanket_refusal_is_retired_by_name_and_says_what_replaced_it():
    """RETIRED 2026-09-08, not quietly deleted.

    `price_parlay` refused every multi-leg price. LAW 5 as amended permits
    pricing a package the venue published, so the blanket refusal is gone --
    and this test fails if it comes back, or if the note saying where it went
    is removed.
    """
    from pathlib import Path

    assert not hasattr(recommend, "price_parlay")
    assert not hasattr(recommend, "SinglesOnly")
    source = Path(recommend.__file__).read_text(encoding="utf-8")
    assert "RETIRED 2026-09-08" in source
    assert "market.combos.classify" in source, "the note must say what replaced it"


def test_the_four_shapes_that_replaced_it_are_each_refused():
    """One refusal per shape, and none of them counts legs alone."""
    from gridiron.market import combos

    games = {"Kansas City": "g1", "Buffalo": "g1", "Miami": "g2"}
    same_game = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Buffalo over 44"]}, games)
    assert same_game == {"priceable": False, "why": "same_game",
                         "legs": ["Kansas City -3", "Buffalo over 44"],
                         "games": ["g1", "g1"]}
    four = combos.classify(
        {"sport": "nfl", "legs": ["a", "b", "c", "d"]}, games)
    assert four["why"] == "leg_count"
    unforecast_leg = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Sunderland to win"]}, games)
    assert unforecast_leg["why"] == "unforecast_leg"
    unforecast_sport = combos.classify(
        {"sport": "cbb", "legs": ["Michigan -7.5", "UConn -2"]}, games)
    assert unforecast_sport["why"] == "unforecast_sport"
    # and the shape the law permits still passes
    good = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Miami moneyline"]}, games)
    assert good["priceable"] and good["games"] == ["g1", "g2"]


def test_nothing_is_sized_once_a_game_is_under_way(tmp_path):
    recommend.refuse_in_game("scheduled")       # must not raise
    with pytest.raises(recommend.NotSizedInGame, match="ninety seconds"):
        recommend.refuse_in_game("in")          # this record's own word
    with pytest.raises(recommend.NotSizedInGame):
        recommend.refuse_in_game("in_progress")  # and the ones it is not
    conn = _world(tmp_path, status="in")
    pid = _pick(conn)
    assert recommend.for_predictions(conn, [pid]) == []


def test_a_recommendation_is_recorded_with_the_price_it_was_made_at(tmp_path):
    conn = _world(tmp_path)
    pid = _pick(conn)
    counts = recommend.record_for(conn, [pid])
    assert counts["recommended"] == 1
    row = conn.execute("SELECT * FROM recommendations").fetchone()
    assert row["side"] == "yes" and row["price"] == pytest.approx(0.46)
    assert row["size_kind"] == "flat" and row["size_units"] == config.FLAT_UNIT
    assert row["close_price"] is None
    # append-only, and stamped after the prediction it is about
    assert row["created_utc"] > "2026-09-07T00:00:00Z"
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE recommendations SET price = 0.1 WHERE id = ?",
                     (row["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM recommendations WHERE id = ?", (row["id"],))


def test_a_question_with_no_side_is_not_recorded(tmp_path):
    conn = _world(tmp_path)
    pid = _pick(conn, prob=0.51, implied=0.50)
    counts = recommend.record_for(conn, [pid])
    assert counts["recommended"] == 0 and counts["no_side"] == 1
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 0


def test_the_closing_line_is_measured_once_and_can_report_bad_news(tmp_path):
    conn = _world(tmp_path, kickoff="2026-09-07T02:00:00Z")
    pid = _pick(conn)
    recommend.record_for(conn, [pid])
    # THE NEAR-START LOOK AT THE SAME VENUE, taken before the game started.
    # The closing line is that venue's last word on the same proposition, not
    # another venue's.
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
        " VALUES ('kalshi', 'near', 'e', 'mlb', 'g0', 'moneyline', 'home_margin',"
        " -1.5, 'home', 0.51, 0.53, '2026-09-07T01:50:00Z')")
    near_quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', 'g0', 'moneyline', 'home_margin', -1.5,"
        " 'home', 'rung_differs_margin', 2.0, 13.0, 0.62, 0.52, 0.52, 'mid',"
        " '2026-09-07T01:55:00Z')",
        (pid, near_quote))
    conn.commit()
    counts = recommend.record_closing_prices(conn)
    assert counts["closed"] == 1
    row = conn.execute("SELECT * FROM recommendations").fetchone()
    # bought at 46, closed at 52: six cents better than the market's own last word
    assert row["clv_cents"] == pytest.approx(6.0)
    assert row["closed_utc"]
    # measured once
    assert recommend.record_closing_prices(conn)["closed"] == 0
    with pytest.raises(sqlite3.IntegrityError, match="measured once"):
        conn.execute("UPDATE recommendations SET close_price = 0.9,"
                     " clv_cents = 1.0, closed_utc = '2026-09-08T00:00:00Z'"
                     " WHERE id = ?", (row["id"],))


def test_the_closing_line_claims_nothing_from_a_small_sample(tmp_path):
    conn = _world(tmp_path, kickoff="2026-09-07T02:00:00Z")
    pid = _pick(conn)
    recommend.record_for(conn, [pid])
    conn.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
        " implied_prob, kind) VALUES (?, '2026-09-07T01:50:00Z', 'test', 0.52,"
        " 'near_start')", (pid,))
    conn.commit()
    recommend.record_closing_prices(conn)
    report = calibration.clv_report(conn, sport="mlb")
    entry = report["markets"][0]
    assert entry["n"] == 1 and entry["renderable"] is False
    assert "nothing is claimed" in entry["words"]
    assert "finding" not in entry
    # and the sentence for bad news exists before it is needed
    bad = language.clv_finding_line(-2.4, 60)
    assert "BUYING RICH" in bad and audit.advice_word_faults(bad) == []


def test_the_words_are_plain_and_recommend_without_tipping():
    line = language.recommendation_line(
        question="Seattle covering -4.5", fair_value=0.58, price=0.46,
        edge_cents=8.6, side="yes", units=1.0, flat=True,
        size_why="no measured edge yet: 3 of 100 settled in this market")
    assert "flat unit" in line and "8.6" in line
    for words in (line, language.nothing_priced_line(18, 4, 14),
                  language.nothing_priced_line(0, 0, 0),
                  language.clv_line(10, None, None, 50)):
        assert audit.advice_word_faults(words) == [], words
        assert audit.plain_words_violations(words) == [], words
