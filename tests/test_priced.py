"""The priced forecaster (THE_PRICED P1-P5, 2026-09-07): a second forecaster
that reads the price, kept apart from the blind one at every level; a coverage
list measured rather than picked; and a kill criterion written before it fired."""
from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import audit, calibration, config, db
from gridiron.priced import coverage, forecast

WHOLE = json.dumps({"coverage": 1.0})


def _world(tmp_path, games=1):
    conn = db.open_db(tmp_path / "priced.db")
    for i in range(games):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'nfl', 2026, 1, 'REG',"
            " 'SEA', 'NE', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')",
            (f"g{i}",))
    conn.commit()
    return conn


def _blind(conn, *, prob=0.62, implied=0.46, game="g0", subject="SEA",
           market="spread"):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'nfl', ?, ?, ?, -3.5, ?, 'cover',"
        " 'statistical', 'final', 'fs5', ?, 'test')",
        (game, market, subject, prob, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    if implied is not None:
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " line, implied_prob, kind) VALUES (?, '2026-09-07T01:00:00Z', 'test',"
            " -3.5, ?, 'open_at_predict')", (pid, implied))
    conn.commit()
    return pid


def test_the_blend_is_declared_and_leans_toward_the_market():
    # the weight is the model's share; the rest is the price
    assert 0 < config.PRICED_MODEL_WEIGHT < 0.5
    got = forecast.blended(0.62, 0.46)
    assert got == pytest.approx(0.35 * 0.62 + 0.65 * 0.46)
    # it sits between the two numbers it came from, always
    assert 0.46 < got < 0.62
    # absent stays absent: a priced forecast with no price in it is a blind one
    assert forecast.blended(0.62, None) is None
    assert forecast.blended(None, 0.46) is None


def test_a_priced_row_names_the_blind_row_and_comes_after_it(tmp_path):
    conn = _world(tmp_path)
    pid = _blind(conn)
    counts = forecast.write_for(conn, [pid])
    assert counts["written"] == 1
    row = conn.execute("SELECT * FROM priced_forecasts").fetchone()
    assert row["prediction_id"] == pid and row["snapshot_id"] is not None
    assert row["blend_version"] == config.PRICED_VERSION
    assert row["created_utc"] > "2026-09-07T00:00:00Z"
    assert row["blind_prob"] == pytest.approx(0.62)
    assert row["priced_prob"] == pytest.approx(forecast.blended(0.62, 0.46))
    # written once per version, append-only, never deleted
    assert forecast.write_for(conn, [pid])["written"] == 0
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE priced_forecasts SET priced_prob = 0.9 WHERE id = ?",
                     (row["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM priced_forecasts WHERE id = ?", (row["id"],))
    # and a row stamped at its blind row's moment is refused
    with pytest.raises(sqlite3.IntegrityError, match="LAW 1"):
        conn.execute(
            "INSERT INTO priced_forecasts (prediction_id, blend_version, sport,"
            " game_id, market_type, blind_prob, price_at_write, priced_prob,"
            " created_utc) VALUES (?, 'b0', 'nfl', 'g0', 'spread', 0.6, 0.5, 0.55,"
            " '2026-09-07T00:00:00Z')", (pid,))


def test_a_question_with_no_price_gets_no_priced_row(tmp_path):
    conn = _world(tmp_path)
    pid = _blind(conn, implied=None)
    counts = forecast.write_for(conn, [pid])
    assert counts["written"] == 0 and counts["no_price"] == 1


def test_the_priced_row_takes_the_blind_row_s_outcome(tmp_path):
    conn = _world(tmp_path)
    pid = _blind(conn)
    forecast.write_for(conn, [pid])
    conn.execute("UPDATE predictions SET resolved_utc = '2026-09-10T00:00:00Z',"
                 " outcome = 1 WHERE id = ?", (pid,))
    conn.commit()
    assert forecast.resolve_forecasts(conn)["settled"] == 1
    assert conn.execute("SELECT outcome FROM priced_forecasts").fetchone()[0] == 1
    # once, and never a second judgement
    assert forecast.resolve_forecasts(conn)["settled"] == 0


def test_the_two_forecasters_are_scored_apart(tmp_path):
    conn = _world(tmp_path, games=4)
    for i in range(4):
        pid = _blind(conn, game=f"g{i}", prob=0.6 + i * 0.05, implied=0.5)
        conn.execute("UPDATE games SET status = 'final', home_score = 27,"
                     " away_score = 20 WHERE id = ?", (f"g{i}",))
        conn.execute("UPDATE predictions SET resolved_utc = '2026-09-10T00:00:00Z',"
                     " outcome = 1 WHERE id = ?", (pid,))
        forecast.write_for(conn, [pid])
    conn.commit()
    forecast.resolve_forecasts(conn)
    card = calibration.priced_scorecard(conn, sport="nfl")
    entry = card["categories"][0]
    assert entry["forecaster"] == "priced" and entry["n"] == 4
    # three scores on the same questions, reported side by side and never summed
    assert entry["priced"]["n"] == entry["blind_on_the_same_questions"]["n"] == 4
    assert entry["market_on_the_same_questions"]["n"] == 4
    assert entry["priced"]["brier"] != entry["blind_on_the_same_questions"]["brier"]
    assert card["blend_version"] == config.PRICED_VERSION


def test_coverage_is_measured_and_says_why_a_market_is_out(tmp_path):
    conn = _world(tmp_path, games=4)
    # A QUOTE NEEDS A PREDICTION FOR ITS GAME (LAW 1's own trigger), so every
    # game in this fixture is forecast before the venue is read for it.
    for game in range(4):
        _blind(conn, game=f"g{game}", subject=f"SEA{game}")
    # a thin market with a narrow quote, and a busy one with the same quote
    # enough strikes to clear the measurement floor: fifty quoted strikes
    # across at least three games is what `coverage.MIN_QUOTES` asks for
    for game in range(4):
        for strike in range(30):
            conn.execute(
                "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
                " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
                " volume, fetched_utc) VALUES ('kalshi', ?, 'e', 'nfl', ?,"
                " ?, 'home_margin', ?, 'home', 0.49, 0.51, ?,"
                " '2026-09-07T02:00:00Z')",
                (f"t{game}-{strike}", f"g{game}",
                 "spread" if strike % 2 else "total",
                 -strike - 0.5, 900 if strike % 2 else 90))
    conn.commit()
    measured = {m["market"]: m for m in coverage.measure(conn, "nfl")}
    assert measured["spread"]["median_spread_cents"] == pytest.approx(2.0)
    decided = {e["market"]: e for e in coverage.select(list(measured.values()))}
    # both are narrow; the busier one is excluded on volume
    assert decided["total"]["covered"] is True
    assert decided["spread"]["covered"] is False
    assert "busiest half" in decided["spread"]["why"]
    # and a market nobody measured is out with its own reason
    thin = coverage.select([{"sport": "nfl", "market": "moneyline", "n": 4,
                             "games": 1, "median_spread_cents": 1.0,
                             "median_volume": 10.0}])
    assert thin[0]["covered"] is False and "not measured enough" in thin[0]["why"]


def test_a_wide_quote_is_never_covered_however_thin():
    wide = coverage.select([{"sport": "nfl", "market": "total", "n": 200,
                             "games": 9, "median_spread_cents": 6.0,
                             "median_volume": 1.0}])
    assert wide[0]["covered"] is False
    assert "survive crossing it" in wide[0]["why"]


def test_the_kill_criterion_stops_a_market_on_its_closing_line(tmp_path):
    conn = _world(tmp_path, games=1)
    pid = _blind(conn)
    # fifty recommendations that all bought richer than the close
    for i in range(coverage.KILL_AFTER):
        conn.execute(
            "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
            " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
            " created_utc, close_price, clv_cents, closed_utc)"
            " VALUES (?, 'nfl', 'g0', 'total', 'yes', 0.6, 0.5, 3.0, 'flat', 1.0,"
            " 0, ?, 0.46, -4.0, '2026-09-09T00:00:00Z')",
            (pid, f"2026-09-07T02:{i:02d}:00Z"))
    conn.commit()
    stopped = coverage.stopped(conn, "nfl")
    assert "total" in stopped
    assert stopped["total"]["n"] == coverage.KILL_AFTER
    assert "buying rich" in stopped["total"]["why"]
    assert "dated ruling" in stopped["total"]["why"]
    # and the engine refuses to price it, whatever the coverage measurement says
    verdict = coverage.priceable(conn, "nfl", "total")
    assert verdict["priceable"] is False and "stopped after" in verdict["why"]


def test_the_blind_path_still_refuses_the_price_after_the_exemption():
    """The exemption lets `gridiron.priced` read the market. It does not let the
    blind path read `gridiron.priced`, and it does not loosen the scan for
    anything else."""
    audit.check_all_prediction_closures()          # must not raise
    assert audit.CLOSURE_EXEMPT_PACKAGE == "gridiron.priced"
    assert "gridiron.market" in audit.FORBIDDEN_MODULES
