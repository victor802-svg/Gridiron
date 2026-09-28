"""The priced forecaster (THE_PRICED P1-P5, 2026-09-07): a second forecaster
that reads the price, kept apart from the blind one at every level; a coverage
list measured rather than picked; and a kill criterion written before it fired."""
from __future__ import annotations

import copy
import json
import sqlite3

import pytest

from gridiron import audit, calibration, config, db
from gridiron.priced import coverage, forecast

WHOLE = json.dumps({"coverage": 1.0})


def _world(tmp_path, games=1, kickoff="2026-09-09T00:00:00Z",
           league_date="2026-09-08"):
    conn = db.open_db(tmp_path / "priced.db")
    for i in range(games):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'nfl', 2026, 1, 'REG',"
            " 'SEA', 'NE', ?, 'scheduled', ?)",
            (f"g{i}", kickoff, league_date))
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


def _fifty_bought_rich(tmp_path):
    """Fifty closes at -4.0c on NFL totals, every one written after the
    closing line was repaired (2026-09-24), so every one is counted."""
    # FIFTY GAMES, ONE RECOMMENDATION EACH (GRIDIRON_REPAIR item 5,
    # 2026-09-26). This was fifty rows on one game and market, which the
    # ruling -- one recommendation per game and market -- now refuses at the
    # second; fifty recommendations are fifty games.
    #
    # INSIDE THE CLOSING LINE'S WINDOW (the operator's ruling 8 of
    # 2026-09-23, 2026-09-27): dated 7 to 9 September, as this was until
    # then, the fifty would be named beside the count and none counted.
    conn = _world(tmp_path, games=coverage.KILL_AFTER,
                  kickoff="2026-09-27T00:00:00Z", league_date="2026-09-26")
    for i in range(coverage.KILL_AFTER):
        game = f"g{i}"
        pid = _blind(conn, game=game)
        # THE CLOSE IS A LATER READ OF ITS OWN CONTRACT (2026-09-23), and only
        # a close measured that way is counted, so the fixture reads the venue
        # twice.
        reads = []
        for stamp, bid in (("2026-09-25T01:00:00Z", 0.49),
                           ("2026-09-26T23:00:00Z", 0.45)):
            conn.execute(
                "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
                " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
                " fetched_utc, read_kind) VALUES ('kalshi', ?, 'E', 'nfl', ?,"
                " 'total', 'total', 44.5, 'over', ?, ?, ?, 'near_start')",
                (f"T{i}", game, bid, bid + 0.02, stamp))
            reads.append(conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0])
        # AND THE CLAIM THE PRICE CAME FROM: a close must cite the read its own
        # recommendation was priced from, at the recommended price.
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
            " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
            " model_prob, venue_price, venue_implied, price_basis, created_utc)"
            " VALUES (?, ?, 'kalshi', 'nfl', ?, 'total', 'total', 44.5, 'over',"
            " 'rung_matched', NULL, NULL, 0.6, 0.5, 0.5, 'mid',"
            " '2026-09-25T01:30:00Z')", (pid, reads[0], game))
        # a recommendation that bought richer than the close
        conn.execute(
            "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
            " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
            " created_utc, close_price, clv_cents, closed_utc)"
            " VALUES (?, 'nfl', ?, 'total', 'yes', 0.6, 0.5, 3.0, 'flat', 1.0,"
            " 0, '2026-09-25T02:00:00Z', 0.46, -4.0, '2026-09-27T00:00:00Z')",
            (pid, game))
        rec = conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
        conn.execute(
            "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
            " pricing_quote_id, close_quote_id, close_price, clv_cents,"
            " minutes_before_start, restated, reason) VALUES (?,"
            " '2026-09-27T00:00:00Z', ?, ?, 0.46, -4.0, 60.0, 0,"
            " 'the last near-start read of its own contract')",
            (rec, reads[0], reads[1]))
    conn.commit()
    return conn


def test_the_kill_criterion_stops_a_market_on_its_closing_line(tmp_path):
    conn = _fifty_bought_rich(tmp_path)
    # ON THE FIRST CLEAN READ (the operator's ruling 8 of 2026-09-23): the
    # closing line may be read, so the kill may fire on it.
    read = config.CLOSING_LINE_FIRST_CLEAN_READ + "T00:00:00Z"
    stopped = coverage.stopped(conn, "nfl", now=read)
    # EACH FORECASTER'S LINE (operator question 22, 2026-09-28): the fifty
    # are the statistical model's, and it is their line that stops
    assert set(stopped) == {("total", "statistical")}
    halted = stopped[("total", "statistical")]
    assert halted["n"] == coverage.KILL_AFTER
    assert halted["category_label"] == "total, statistical"
    assert "buying rich" in halted["why"]
    assert "dated ruling" in halted["why"]
    # and the engine refuses to price its picks, whatever the coverage
    # measurement says -- and only its picks: the reasoning pass's own line
    # holds nothing, and is not stopped by the other forecaster's closes
    verdict = coverage.priceable(conn, "nfl", "total", predictor="statistical",
                                 now=read)
    assert verdict["priceable"] is False and "stopped after" in verdict["why"]
    assert "stopped after" not in coverage.priceable(
        conn, "nfl", "total", predictor="llm", now=read)["why"]
    # a forecaster that is not one of the two has no line, and is refused
    from gridiron.market import recommend

    with pytest.raises(recommend.PooledCount):
        coverage.priceable(conn, "nfl", "total", predictor="both", now=read)


def test_the_kill_criterion_waits_for_the_first_clean_read(tmp_path):
    """"The first clean CLV read is 21 days after that, not before" (the
    operator's ruling 8 of 2026-09-23). The kill reads the closing line's
    mean and prints it, so it waits for the same date: the last second before
    it stops nothing, on the same fifty closes that stop the market after."""
    conn = _fifty_bought_rich(tmp_path)
    eve = "2026-10-14T23:59:59Z"
    assert eve[:10] < config.CLOSING_LINE_FIRST_CLEAN_READ
    assert coverage.stopped(conn, "nfl", now=eve) == {}
    assert coverage.priceable(conn, "nfl", "total", predictor="statistical",
                              now=eve)["why"] != ""
    assert "stopped after" not in coverage.priceable(
        conn, "nfl", "total", predictor="statistical", now=eve)["why"]
    report = calibration.clv_report(conn, sport="nfl", now=eve)
    entry = report["markets"][0]
    mine = next(b for b in report["forecasters"]
                if b["predictor"] == "statistical")
    # THE COUNT, WITH ITS N, AND NO FIGURE -- one forecaster's (question 22)
    assert entry["predictor"] == "statistical"
    assert entry["n"] == coverage.KILL_AFTER and mine["n"] == coverage.KILL_AFTER
    assert entry["mean_cents"] is None and entry["beat_the_close"] is None
    assert "finding" not in entry and entry["renderable"] is False
    assert "Thursday 15 October" in entry["words"]


def test_the_blind_path_still_refuses_the_price_after_the_exemption():
    """The exemption lets `gridiron.priced` read the market. It does not let the
    blind path read `gridiron.priced`, and it does not loosen the scan for
    anything else."""
    audit.check_all_prediction_closures()          # must not raise
    assert audit.CLOSURE_EXEMPT_PACKAGE == "gridiron.priced"
    assert "gridiron.market" in audit.FORBIDDEN_MODULES


# ---------------------------------------------------------------------------
# ONE STANDING QUESTION PER FORECASTER (operator question 14, ruled
# 2026-09-27, 1 of 3): "Every count on the Record page that states a gate
# distance is rebuilt per forecaster (per tier for UFC) and per distinct bet,
# through its record's standing rule."
# ---------------------------------------------------------------------------

def _asked(conn, *, game="g0", sport="nfl", predictor="statistical",
           pass_kind="final", written="2026-09-08T12:00:00Z", prob=0.62,
           implied=0.5, market="spread", subject="SEA", line=-3.5,
           side="cover"):
    """One blind forecast of one question, a price read after it, and the
    priced row blended from the two -- through `forecast.write_for`."""
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'fs5', ?, 'test')",
        (written, sport, game, market, subject, line, prob, side, predictor,
         pass_kind, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line,"
        " implied_prob, kind) VALUES (?, ?, 'test', ?, ?, 'open_at_predict')",
        (pid, db.just_after(written), line, implied))
    conn.commit()
    assert forecast.write_for(conn, [pid])["written"] == 1
    return pid


def _settle(conn, outcome=1):
    """Settle every open forecast, and copy the outcome onto its priced row."""
    conn.execute("UPDATE predictions SET resolved_utc = '2026-09-10T00:00:00Z',"
                 " outcome = ? WHERE resolved_utc IS NULL", (outcome,))
    conn.commit()
    forecast.resolve_forecasts(conn)


def _one_game_three_passes(tmp_path):
    """THE SHAPE THE PAGE COUNTED THREE TIMES: one game's point spread asked
    by the statistical model's morning and final pass and by the reasoning
    pass, each priced, all settled. Returns the connection and the ids."""
    conn = _world(tmp_path)
    early = _asked(conn, pass_kind="early", written="2026-09-07T12:00:00Z",
                   prob=0.55)
    final = _asked(conn, pass_kind="final", written="2026-09-08T12:00:00Z",
                   prob=0.66)
    llm = _asked(conn, predictor="llm", written="2026-09-08T12:00:01Z",
                 prob=0.7)
    _settle(conn)
    return conn, early, final, llm


def _as_it_stood(conn, *, sport, predictor, event_tier=None,
                 ask_the_forecaster=False):
    """THE SHIPPED COUNT OF 2026-09-07 TO 2026-09-27, as a door: every priced
    row of the sport, whoever's forecast it blended and whichever pass --
    with the columns the builder reads, and nothing else."""
    return conn.execute(
        "SELECT f.*, COALESCE(NULLIF(f.prop_type, ''), f.market_type) AS market,"
        " p.predictor, p.market_type AS question_market, p.subject,"
        " p.line_asked, NULL AS event_tier"
        " FROM priced_forecasts f JOIN predictions p ON p.id = f.prediction_id"
        " WHERE f.sport = ? AND f.blend_version = ?"
        + (" AND p.predictor = ?" if ask_the_forecaster else ""),
        (sport, config.PRICED_VERSION)
        + ((predictor,) if ask_the_forecaster else ())).fetchall()


def test_the_priced_record_counts_one_standing_question_per_forecaster(tmp_path):
    """A question's morning and final pass, and the two forecasters, were one
    count of three: MLB moneyline said "261 settled comparisons, past the 100"
    on 26 September for 96 and 84 standing questions."""
    conn, _, _, _ = _one_game_three_passes(tmp_path)
    card = calibration.priced_scorecard(conn, sport="nfl")
    # NO TOTAL, AND NO POOLED "AWAITING" COUNT
    assert "n" not in card and "awaiting_outcome" not in card
    got = {(c["market"], c["predictor"]): c for c in card["categories"]}
    assert list(got) == [("spread", "statistical"), ("spread", "llm")]
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    for (_, who), c in got.items():
        assert c["n"] == c["distinct_bets"] == 1
        assert c["forecasters_counted"] == [who] and c["event_tier"] is None
        assert c["forecaster"] == "priced" and c["filters"]["predictor"] == who
        assert c["gate_line"].startswith(f"1 of {gate} settled comparisons")
        for key in calibration.PRICED_SCORES:
            assert c[key]["n"] == 1, key
        assert not audit.plain_words_violations(c["category_label"])
    # THE STANDING FORECAST'S ROW IS THE ONE COUNTED: the final pass's
    statistical = got[("spread", "statistical")]
    assert statistical["blind_on_the_same_questions"]["brier"] == round(
        (0.66 - 1) ** 2, 4)
    assert statistical["category_label"] == (
        "point spread blended with the price, statistical")
    assert got[("spread", "llm")]["category_label"] == (
        "point spread blended with the price, reasoning pass")


def test_a_withdrawn_final_pass_leaves_the_morning_pass_standing(tmp_path):
    """Through the blind record's own standing rule: a voided forecast is
    never counted, even one that settled first, and a withdrawal takes back
    that forecast and not the question (ruling 1, 2026-09-24)."""
    conn, _, final, _ = _one_game_three_passes(tmp_path)
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc,"
                 " reason) VALUES (?, ?, 'withdrawn by hand after it settled')",
                 (final, db.utcnow()))
    conn.commit()
    card = calibration.priced_scorecard(conn, sport="nfl")
    statistical = next(c for c in card["categories"]
                       if c["predictor"] == "statistical")
    assert statistical["n"] == 1
    assert statistical["blind_on_the_same_questions"]["brier"] == round(
        (0.55 - 1) ** 2, 4)


def test_the_door_will_not_count_for_nobody_in_particular_or_across_cards(tmp_path):
    conn = _world(tmp_path)
    for who in (None, "all", "priced"):
        with pytest.raises(forecast.PooledCount, match="never pooled"):
            forecast.standing_forecasts(conn, sport="nfl", predictor=who)
    with pytest.raises(forecast.PooledCount, match="LAW 6"):
        forecast.standing_forecasts(conn, sport="ufc", predictor="statistical")
    with pytest.raises(forecast.PooledCount, match="LAW 6"):
        forecast.standing_forecasts(conn, sport="nfl", predictor="statistical",
                                    event_tier="numbered")
    with pytest.raises(config.CrossSportAggregation):
        forecast.standing_forecasts(conn, sport=None, predictor="statistical")


def test_a_pooled_priced_count_is_refused_by_name(tmp_path):
    from gridiron import language

    conn, _, _, _ = _one_game_three_passes(tmp_path)
    honest = calibration.priced_scorecard(conn, sport="nfl")
    calibration.assert_no_pooled_priced_counts(honest)

    def refused(change, match, error=calibration.MergedCurve):
        payload = copy.deepcopy(honest)
        change(payload)
        with pytest.raises(error, match=match):
            calibration.assert_no_pooled_priced_counts(payload)

    def first(payload):
        return payload["categories"][0]

    def twice(payload):
        entry = first(payload)
        entry.update(n=2, gate_line=language.at_the_line_gate_line(2, entry["gate"]))
        for key in calibration.PRICED_SCORES:
            entry[key]["n"] = 2

    refused(lambda p: first(p)["filters"].update(predictor=None),
            "merges the statistical and LLM forecasters")
    refused(lambda p: first(p).update(predictor="priced"),
            "names forecaster 'priced'")
    refused(lambda p: first(p).update(forecasters_counted=["llm", "statistical"]),
            "two forecasters pooled")
    refused(twice, "counts 2 settled priced rows for 1 distinct bet")
    refused(lambda p: first(p)["blind_on_the_same_questions"].update(n=3),
            "two counts of one record")
    refused(lambda p: first(p).update(
        gate_line="261 settled comparisons, past the 100 this record needs"),
        "not its own count")
    refused(lambda p: first(p).update(event_tier="numbered"), "declares none")
    refused(lambda p: p.update(n=2), "a total 'n'")
    refused(lambda p: p.update(awaiting_outcome=49), "a total 'awaiting_outcome'")
    refused(lambda p: first(p).update(record="rung"), "filed under the priced one",
            error=calibration.MergedRecord)


def test_the_count_as_it_stood_is_refused_by_the_builder_the_api_and_the_gate(
        tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn, _, _, _ = _one_game_three_passes(tmp_path)
    audit.check_the_priced_record_is_never_pooled(conn)          # lawful: passes
    # THE COUNT AS IT STOOD: both forecasters and both passes in one count
    monkeypatch.setattr(forecast, "standing_forecasts", _as_it_stood)
    with pytest.raises(calibration.MergedCurve, match="two forecasters pooled"):
        calibration.priced_scorecard(conn, sport="nfl")
    with pytest.raises(audit.LawViolation, match="A PRICED COUNT IS POOLED"):
        audit.check_the_priced_record_is_never_pooled(conn)
    # AND AS IT WOULD STAND ASKING THE FORECASTER: one row per pass
    monkeypatch.setattr(
        forecast, "standing_forecasts",
        lambda conn, **kw: _as_it_stood(conn, ask_the_forecaster=True, **kw))
    with pytest.raises(calibration.MergedCurve,
                       match="counts 2 settled priced rows for 1 distinct bet"):
        calibration.priced_scorecard(conn, sport="nfl")
    # THE API ANSWERS 500 rather than serve it
    token = "test-token-for-the-priced-counts"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "priced.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            response = client.get("/api/scorecard", params={"sport": "nfl"})
    finally:
        api.set_database(None)
    assert response.status_code == 500
    assert "IN THE PRICED RECORD" in response.json()["detail"]


def _ufc_bout(conn, bout: str, event: str, tier: str, when: str) -> None:
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier) VALUES (?, ?, ?, 2026, ?, ?)",
        (event, f"UFC {event}", when, db.utcnow(), tier))
    conn.execute(
        "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
        " fighter_a, fighter_b, status, fetched_utc)"
        " VALUES (?, ?, ?, 3, 'A', 'B', 'final', ?)",
        (bout, event, when, db.utcnow()))
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES (?, 'ufc', 2026, 1, 'REG',"
        " 'A', 'B', ?, 'scheduled', '2026-09-08')", (bout, when))


def test_a_ufc_priced_count_is_one_cards(tmp_path, monkeypatch):
    """LAW 6 one level down: a numbered-card bout and a Fight Night bout are
    two categories, each naming its card, never one moneyline count."""
    conn = db.open_db(tmp_path / "ufc.db")
    _ufc_bout(conn, "u1", "e1", "numbered", "2026-09-09T03:00:00Z")
    _ufc_bout(conn, "u2", "e2", "fight_night", "2026-09-09T03:00:00Z")
    for bout in ("u1", "u2"):
        _asked(conn, game=bout, sport="ufc", market="moneyline", subject="A",
               line=None, side="win")
    _settle(conn)
    card = calibration.priced_scorecard(conn, sport="ufc")
    got = {(c["event_tier"], c["predictor"]): c for c in card["categories"]}
    assert set(got) == {("numbered", "statistical"), ("fight_night", "statistical")}
    for (tier, _), c in got.items():
        assert c["n"] == 1 and c["tiers_counted"] == [tier]
    assert "Fight Night" in got[("fight_night", "statistical")]["category_label"]
    assert "Numbered card" in got[("numbered", "statistical")]["category_label"]
    # A DOOR THAT STOPPED FILTERING BY CARD is seen off the rows themselves
    real = forecast.standing_forecasts
    monkeypatch.setattr(
        forecast, "standing_forecasts",
        lambda conn, *, sport, predictor, event_tier=None: [
            r for tier in config.event_tiers(sport)
            for r in real(conn, sport=sport, predictor=predictor, event_tier=tier)])
    with pytest.raises(calibration.MergedCurve, match="never summed"):
        calibration.priced_scorecard(conn, sport="ufc")
