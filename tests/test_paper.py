"""The hypothetical unit ledger (operator ruling D1, 2026-09-06): the
arithmetic, the fee, the gate, and the label the ruling requires -- and LAW 5's
staking scan still clean with all of it in the tree."""
from __future__ import annotations

import json

import pytest

from gridiron import audit, config, db, language, tasks
from gridiron.market import at_the_line, paper

DIST = {"quantity": "home_margin", "family": "normal", "mean": 3.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}


def _slate(tmp_path, n, *, home_wins_every=2, price=0.40):
    """n finished games, each with a forecast, a quote and an outcome.

    The venue is priced at 0.40 for the home side and the model's frozen
    distribution answers about 0.58 at the same number, so every row is a
    disagreement -- which is what the ledger counts.
    """
    conn = db.open_db(tmp_path / "paper.db")
    for i in range(n):
        gid = f"2026_01_G{i:03d}"
        home, away = (34, 20) if i % home_wins_every == 0 else (17, 24)
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES (?, 'nfl', 2026, 1, 'REG', 'SEA', 'NE', '2026-09-10T00:20:00Z',"
            " 'final', '2026-09-09', ?, ?)", (gid, home, away))
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
            " line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES ('2026-09-06T00:00:00Z', 'nfl', ?, 'spread', 'SEA', -3.5, 0.58,"
            " 'cover', 'statistical', 'final', 'fs5', ?, 'test')",
            (gid, json.dumps({"margin_distribution": DIST})))
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
            " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
            " VALUES ('kalshi', ?, 'e', 'nfl', ?, 'spread', 'home_margin', -3.5,"
            " 'home', ?, ?, '2026-09-07T00:00:00Z')",
            (f"t{i}", gid, price - 0.01, price + 0.01))
    conn.commit()
    at_the_line.evaluate(conn)
    tasks.settle_everything(conn)
    return conn


def test_the_fee_is_the_declared_formula_and_says_where_it_came_from():
    # seven per cent of the price times one minus the price, rounded up to the
    # cent: largest at an even chance, vanishing at both ends
    assert paper.fee_per_contract(0.5) == 0.02
    assert paper.fee_per_contract(0.9) == 0.01
    assert paper.fee_per_contract(0.99) == 0.01
    assert paper.fee_per_contract(0.0) == 0.0 and paper.fee_per_contract(1.0) == 0.0
    assert paper.fee_per_contract(None) == 0.0
    # rounded UP, never down: 0.07 * 0.5 * 0.5 is 0.0175
    assert paper.fee_per_contract(0.5) > 0.07 * 0.25
    assert paper.FEE_VERIFIED is False and "429" in paper.FEE_SOURCE


def test_one_contract_settles_at_one_or_nothing():
    assert paper.units_from_one_contract(0.4, 1) == pytest.approx(0.6)
    assert paper.units_from_one_contract(0.4, 0) == pytest.approx(-0.4)
    # the complement of a 0.4 proposition costs 0.6 and wins 0.4
    assert paper.units_from_one_contract(0.6, 1) == pytest.approx(0.4)
    assert paper.units_from_one_contract(0.6, 0) == pytest.approx(-0.6)


def test_only_a_disagreement_is_counted():
    assert paper.qualifying(0.60, 0.52) == "yes"
    assert paper.qualifying(0.45, 0.58) == "no"
    # inside the declared threshold there is nothing to count
    assert paper.qualifying(0.53, 0.52) is None
    assert paper.qualifying(0.52, 0.53) is None
    assert paper.qualifying(0.60, 0.52, 0.20) is None


def test_the_ledger_is_absent_below_the_gate_and_says_how_far_short(tmp_path):
    conn = _slate(tmp_path, 4)
    led = paper.ledger(conn, sport="nfl", market="spread")
    assert led["n"] == 4 and led["renderable"] is False
    assert led["shortfall"] == config.MIN_SAMPLE_FOR_EDGE_CLAIM - 4
    # the figures are ABSENT, not zeroed
    assert "units" not in led and "units_after_fees" not in led
    words = language.paper_ledger_line(led)
    assert words.startswith("hypothetical") and "4 of 100" in words


def test_past_the_gate_the_figures_appear_with_the_fee_beside_them(tmp_path, monkeypatch):
    conn = _slate(tmp_path, 4)
    monkeypatch.setattr(config, "MIN_SAMPLE_FOR_EDGE_CLAIM", 4)
    led = paper.ledger(conn, sport="nfl", market="spread")
    assert led["renderable"] is True and led["n"] == 4 and led["hypothetical"] is True
    # two of the four home sides covered -3.5, each carried at 0.40
    assert led["right"] == 2
    assert led["units"] == pytest.approx(2 * 0.6 - 2 * 0.4, abs=1e-6)
    # the fee is charged on every one of them and never returned
    assert led["units_after_fees"] == pytest.approx(
        led["units"] - 4 * paper.fee_per_contract(0.4), abs=1e-6)
    assert led["units_after_fees"] < led["units"]
    assert led["units_per_forecast"] == pytest.approx(led["units"] / 4, abs=1e-6)
    words = language.paper_ledger_line(led)
    assert words.startswith("hypothetical:") and "after the venue's fee" in words
    assert "not been checked" in language.paper_fee_line(led)


def test_the_label_and_the_law_survive_the_ledger(tmp_path):
    conn = _slate(tmp_path, 2)
    from gridiron import calibration

    card = calibration.at_the_line_scorecard(conn, sport="nfl")
    rows = {row["market"]: row for row in card["paper"]}
    assert rows["spread"]["hypothetical"] is True
    assert rows["spread"]["words"].startswith("hypothetical")
    # LAW 5's staking scan reads the whole package, this module included
    assert audit.betting_surface() == []
    audit.check_not_a_betting_tool()
    # and the words are still a forecast rather than advice
    audit.check_the_at_the_line_words_are_a_forecast(card)
    for row in card["paper"]:
        assert audit.plain_words_violations(row["words"]) == []
        assert audit.plain_words_violations(row["fee_words"]) == []
