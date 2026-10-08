"""The line beside each blind curve: one forecaster's count, one card's for
UFC, each standing question once -- the curve's own count (operator question
14, ruled 2026-09-27, 3 of 3).

"Every count on the Record page that states a gate distance is rebuilt per
forecaster (per tier for UFC) and per distinct bet, through its record's
standing rule." Until this date the outlook counted every row of the market
this season -- a question's morning and final pass each, every card for UFC --
and said "330 of 100" beside a curve of 233 (MLB moneyline, 26 September).
"""

from __future__ import annotations

import copy

import pytest

from gridiron import audit, calibration, config, db, horizon, language

SEASON = 2026
GATE = config.MIN_SAMPLE_FOR_EDGE_CLAIM


def _game(conn, game: str, *, sport="mlb", week=1, season=SEASON,
          kickoff="2026-09-07T23:05:00Z", status="final") -> None:
    played = status == "final"
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES (?, ?, ?, ?, 'R', 'SEA', 'HOU', ?, ?, ?, ?, ?)",
        (game, sport, season, week, kickoff, status, kickoff[:10],
         5 if played else None, 3 if played else None))


def _forecast(conn, game: str, *, sport="mlb", market="moneyline", prop=None,
              predictor="statistical", pass_kind="final",
              written="2026-09-07T21:05:00Z", prob=0.6, subject="SEA",
              line=None, side="win", settled=True) -> int:
    """One blind forecast, settled as the resolver settles it unless told
    otherwise -- through the schema's own rules."""
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " pass_kind, factor_set_version, factors_json, reasoning,"
        " resolved_utc, outcome) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
        " 'fs2', '{}', 'test', ?, ?)",
        (written, sport, game, market, prop, subject, line, prob, side,
         predictor, pass_kind,
         "2026-09-08T03:00:00Z" if settled else None, 1 if settled else None))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]


def _one_game_three_passes(tmp_path):
    """THE SHAPE THE PAGE COUNTED TWICE: one MLB game's moneyline forecast by
    the statistical model's morning and final pass and by the reasoning pass,
    all settled, and one game still to play."""
    conn = db.open_db(tmp_path / "outlook.db")
    _game(conn, "m1")
    _game(conn, "m2", week=2, kickoff="2026-09-08T23:05:00Z", status="scheduled")
    early = _forecast(conn, "m1", pass_kind="early",
                      written="2026-09-07T03:05:00Z", prob=0.55)
    final = _forecast(conn, "m1", written="2026-09-07T21:05:00Z", prob=0.60)
    llm = _forecast(conn, "m1", predictor="llm", written="2026-09-07T21:05:01Z",
                    prob=0.58)
    return conn, early, final, llm


def _asked_at(monkeypatch, now: str) -> None:
    """THE CLOCK THE PAGE IS ASKED AT (operator question 33, ruled
    2026-09-30; built 2026-10-08): a slate is still to come only while a
    game on it is 'scheduled' and the clock is before its start, so a world
    whose games are dated in September 2026 is asked at a clock in it --
    where these tests always meant to stand -- rather than at the real one,
    after every game in it."""
    monkeypatch.setattr(db, "utcnow", lambda: now)


def _category(categories, market, predictor, tier=None):
    (found,) = [c for c in categories if c["market"] == market
                and c["filters"]["predictor"] == predictor
                and c.get("event_tier") == tier]
    return found


def _as_it_stood(conn, *, sport, market, predictor, event_tier=None,
                 ask_the_forecaster=True):
    """THE SHIPPED COUNT UNTIL 2026-09-27, as a door: every row of the market
    this season that is not withdrawn -- a question's passes each, every card
    -- with the fields the outlook reads, and nothing else.
    `ask_the_forecaster=False` asks nobody in particular."""
    prop = calibration.prop_type_of(sport, market)
    rows = conn.execute(
        "SELECT p.id, p.game_id, p.market_type, p.prop_type, p.subject,"
        " p.line_asked, p.predictor, p.resolved_utc, g.season, g.week,"
        " (SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
        "    ON e.id = b.event_id WHERE b.id = p.game_id) AS event_tier"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND p.market_type = ?"
        + (" AND p.predictor = ?" if ask_the_forecaster else "")
        + (" AND p.prop_type = ?" if prop else "")
        + " AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
          "                 WHERE v.prediction_id = p.id)",
        (sport, SEASON, calibration.market_type_of(sport, market))
        + ((predictor,) if ask_the_forecaster else ())
        + ((prop,) if prop else ())).fetchall()
    return [dict(r, market=market, settled=r["resolved_utc"] is not None)
            for r in rows]


def test_the_outlook_counts_the_curves_standing_questions_per_forecaster(
        tmp_path, monkeypatch):
    """One game forecast by two passes and two forecasters is one standing
    question for each, and the outlook beside the statistical curve says the
    curve's own count: 1, not 2 (the morning pass) or 3 (the reasoning pass).

    ASKED THE DAY BEFORE THE GAME STILL TO PLAY (operator question 33,
    2026-10-08: a slate is still to come only before its start), and from
    that date the line says the most the count can reach, "at most", where
    it said "~2 expected"."""
    _asked_at(monkeypatch, "2026-09-08T00:00:00Z")
    conn, early, final, llm = _one_game_three_passes(tmp_path)
    mine = horizon.standing_questions(conn, sport="mlb", market="moneyline",
                                      predictor="statistical")
    theirs = horizon.standing_questions(conn, sport="mlb", market="moneyline",
                                        predictor="llm")
    assert [r["id"] for r in mine] == [final]
    assert [r["id"] for r in theirs] == [llm]
    categories = calibration.blind_categories(conn, sport="mlb")
    moneyline = _category(categories, "moneyline", "statistical")
    outlook = moneyline["outlook"]
    assert moneyline["n"] == outlook["resolved"] == outlook["n"] == 1
    assert outlook["distinct_bets"] == outlook["written"] == 1
    assert outlook["distinct_bets_written"] == outlook["slates_used"] == 1
    assert outlook["predictor"] == "statistical" and outlook["record"] == "rung"
    assert outlook["forecasters_counted"] == ["statistical"]
    assert outlook["slates_remaining"] == 1
    # 1 settled + 1 a slate x 1 slate to come
    assert outlook["expected"] == 2
    assert outlook["message"] == language.market_outlook_line(
        1, GATE, 2, outlook["season_ends"], to_come=1, on_to_come=1.0,
        sport="mlb")
    assert outlook["message"].startswith(
        f"1 of {GATE} · at most ~2 this season (~1 more on the 1 day still "
        f"to come)")
    assert audit.plain_words_violations(outlook["message"]) == []
    # THE REASONING PASS'S CURVE in a market it is still asked carries its N
    # and no projection, as it always has.
    assert "outlook" not in _category(categories, "moneyline", "llm")
    theirs = horizon.market_outlook(conn, "mlb", "moneyline", predictor="llm")
    assert theirs["resolved"] == 1 and theirs["forecasters_counted"] == ["llm"]
    # AND THE WHOLE RECORD PAGE builds the same row
    page = calibration.scorecard(conn, sport="mlb")
    assert _category(page["categories"], "moneyline", "statistical")["outlook"] == outlook


def test_a_withdrawn_final_pass_leaves_the_morning_pass_standing(tmp_path):
    """A withdrawal takes back that forecast, not the question (ruling 1,
    2026-09-24): the morning pass stands again and is the one counted."""
    conn, early, final, _ = _one_game_three_passes(tmp_path)
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc,"
                 " reason) VALUES (?, ?, 'withdrawn by hand for the test')",
                 (final, db.utcnow()))
    conn.commit()
    rows = horizon.standing_questions(conn, sport="mlb", market="moneyline",
                                      predictor="statistical")
    assert [r["id"] for r in rows] == [early]
    outlook = _category(calibration.blind_categories(conn, sport="mlb"),
                        "moneyline", "statistical")["outlook"]
    assert outlook["resolved"] == outlook["written"] == 1


def test_the_door_will_not_count_for_nobody_every_prop_or_across_cards(tmp_path):
    conn = db.open_db(tmp_path / "door.db")
    for who in (None, "all", "priced"):
        with pytest.raises(horizon.PooledCount, match="never pooled"):
            horizon.standing_questions(conn, sport="mlb", market="moneyline",
                                       predictor=who)
    with pytest.raises(horizon.PooledCount, match="every prop type in one count"):
        horizon.standing_questions(conn, sport="mlb", market="prop",
                                   predictor="statistical")
    with pytest.raises(horizon.PooledCount, match="LAW 6"):
        horizon.standing_questions(conn, sport="ufc", market="moneyline",
                                   predictor="statistical")
    with pytest.raises(horizon.PooledCount, match="LAW 6"):
        horizon.standing_questions(conn, sport="mlb", market="moneyline",
                                   predictor="statistical", event_tier="numbered")
    with pytest.raises(config.CrossSportAggregation):
        horizon.standing_questions(conn, sport=None, market="moneyline",
                                   predictor="statistical")
    with pytest.raises(TypeError):
        horizon.market_outlook(conn, "mlb", "moneyline")        # nobody named
    with pytest.raises(horizon.PooledCount, match="LAW 6"):
        horizon.llm_routed_off_outlook(conn, "ufc", "rounds")  # every card


def test_the_rate_is_this_seasons_standing_questions_over_their_slates(
        tmp_path, monkeypatch):
    """The pace counts standing questions, never a superseded pass: two games
    on two slates, one of them forecast twice, write 2 a pace of 1 a slate --
    where every row made it 3 over 2.

    AND THE MOST IT CAN REACH (operator question 33, 2026-10-08): asked
    before the three slates still to play, 1 settled, m2's question waiting
    to settle on a slate already played, and 1 a slate on each of the three
    -- 5, where the pace times the slates alone said 4."""
    _asked_at(monkeypatch, "2026-09-09T00:00:00Z")
    conn = db.open_db(tmp_path / "rate.db")
    _game(conn, "m1", week=1)
    _game(conn, "m2", week=2, kickoff="2026-09-08T23:05:00Z")
    for week in (3, 4, 5):
        _game(conn, f"s{week}", week=week, kickoff=f"2026-09-{6 + week:02d}T23:05:00Z",
              status="scheduled")
    _forecast(conn, "m1", pass_kind="early", written="2026-09-07T03:05:00Z")
    _forecast(conn, "m1", written="2026-09-07T21:05:00Z")
    _forecast(conn, "m2", written="2026-09-08T21:05:00Z", settled=False)
    out = horizon.market_outlook(conn, "mlb", "moneyline", predictor="statistical")
    assert (out["resolved"], out["written"], out["slates_used"]) == (1, 2, 2)
    assert out["slates_remaining"] == 3 and out["per_slate"] == 1.0
    assert out["waiting_elsewhere"] == 1 and out["on_slates_to_come"] == 3.0
    assert out["expected"] == horizon.expected_from(out) == 5


def test_nothing_this_season_is_not_nothing_ever(tmp_path):
    """`resolved` is the curve's n, every season's; the pace is this season's.
    A count from an earlier season and no rate says "this season", never
    "yet" -- a count and its denial in one sentence."""
    conn = db.open_db(tmp_path / "seasons.db")
    _game(conn, "old", season=SEASON - 1, kickoff="2025-09-07T23:05:00Z")
    _forecast(conn, "old", written="2025-09-07T21:05:00Z")
    categories = calibration.blind_categories(conn, sport="mlb")
    moneyline = _category(categories, "moneyline", "statistical")
    outlook = moneyline["outlook"]
    assert moneyline["n"] == outlook["resolved"] == 1
    assert outlook["written"] == 0 and outlook["reachable"] is None
    assert outlook["written_before"] is True
    assert outlook["message"] == (f"1 of {GATE} · nothing written in this "
                                  f"market this season, so there is no rate "
                                  f"to project from")
    empty = _category(categories, "total", "statistical")["outlook"]
    assert "nothing written in this market yet" in empty["message"]


def _ufc_card(conn, event: str, tier: str, bouts, *, week: int, status: str) -> None:
    kickoff = f"2026-{9 + week // 30:02d}-{(week % 30) + 1:02d}T23:00:00Z"
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier) VALUES (?, ?, ?, 2026, ?, ?)",
        (event, f"UFC {event}", kickoff, db.utcnow(), tier))
    for bout in bouts:
        conn.execute(
            "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
            " fighter_a, fighter_b, status, fetched_utc)"
            " VALUES (?, ?, ?, 3, 'A', 'B', ?, ?)",
            (bout, event, kickoff, status, db.utcnow()))
        _game(conn, bout, sport="ufc", week=week, kickoff=kickoff, status=status)
    conn.commit()


def test_a_ufc_outlook_is_one_cards(tmp_path, monkeypatch):
    """LAW 6 one level down: each card's curve carries its own card's outlook,
    paced by that card's slates -- never one count across three cards beside
    each (UFC said "62 of 100" beside a Numbered-card curve of 0).

    Asked on 10 September, before the three cards still to fight (operator
    question 33, 2026-10-08: a card is still to come only before its
    start)."""
    _asked_at(monkeypatch, "2026-09-10T00:00:00Z")
    conn = db.open_db(tmp_path / "ufc.db")
    _ufc_card(conn, "fn1", "fight_night", ("u1", "u2"), week=1, status="final")
    _ufc_card(conn, "cs1", "contender", ("u3",), week=2, status="final")
    _ufc_card(conn, "fn2", "fight_night", ("u4",), week=10, status="scheduled")
    _ufc_card(conn, "fn3", "fight_night", ("u5",), week=11, status="scheduled")
    _ufc_card(conn, "nc1", "numbered", ("u6",), week=12, status="scheduled")
    for bout, pass_kind, written in (("u1", "early", "2026-09-01T03:00:00Z"),
                                     ("u1", "final", "2026-09-01T21:00:00Z"),
                                     ("u2", "final", "2026-09-01T21:00:00Z"),
                                     ("u3", "final", "2026-09-02T21:00:00Z")):
        _forecast(conn, bout, sport="ufc", subject="A", pass_kind=pass_kind,
                  written=written)
    categories = calibration.blind_categories(conn, sport="ufc")
    got = {c["event_tier"]: c for c in categories
           if c["market"] == "moneyline" and c["filters"]["predictor"] == "statistical"}
    assert set(got) == set(config.event_tiers("ufc"))
    fight_night, contender, numbered = (got[t]["outlook"] for t in
                                        ("fight_night", "contender", "numbered"))
    assert (fight_night["resolved"], fight_night["tiers_counted"]) == (2, ["fight_night"])
    assert fight_night["slates_remaining"] == 2      # its own cards, not all three
    assert fight_night["expected"] == 2 + 2 * 2
    assert (contender["resolved"], contender["slates_remaining"]) == (1, 0)
    assert (numbered["resolved"], numbered["reachable"]) == (0, None)
    assert numbered["slates_remaining"] == 1
    assert horizon.slates_remaining(conn, "ufc", SEASON) == 3
    # A DOOR THAT STOPPED FILTERING BY CARD is seen off the rows themselves
    real = horizon.standing_questions
    monkeypatch.setattr(
        horizon, "standing_questions",
        lambda conn, *, sport, market, predictor, event_tier=None: [
            r for tier in config.event_tiers(sport)
            for r in real(conn, sport=sport, market=market,
                          predictor=predictor, event_tier=tier)])
    with pytest.raises(calibration.MergedCurve, match="never summed"):
        calibration.blind_categories(conn, sport="ufc")


def test_a_pooled_outlook_is_refused_by_name(tmp_path, monkeypatch):
    # ASKED THE DAY BEFORE THE GAME STILL TO PLAY (operator question 33,
    # 2026-10-08), so the honest outlook projects 2, as it did.
    _asked_at(monkeypatch, "2026-09-08T00:00:00Z")
    conn, _, _, _ = _one_game_three_passes(tmp_path)
    honest = {"sport": "mlb", "record": "rung",
              "categories": calibration.blind_categories(conn, sport="mlb")}
    calibration.assert_no_pooled_outlooks(honest)
    index = next(i for i, c in enumerate(honest["categories"])
                 if c["market"] == "moneyline"
                 and c["filters"]["predictor"] == "statistical")

    def refused(change, match):
        payload = copy.deepcopy(honest)
        change(payload["categories"][index]["outlook"], payload)
        with pytest.raises(calibration.MergedCurve, match=match):
            calibration.assert_no_pooled_outlooks(payload)

    def reworded(out):
        out["message"] = horizon.outlook_words(out)

    def passes(out, _):
        out.update(resolved=2, n=2)
        reworded(out)

    def stood(out, _):
        out.update(resolved=2, n=2, distinct_bets=2)
        reworded(out)

    refused(passes, "counts 2 settled forecasts for 1 distinct question")
    refused(stood, "counts 2 settled beside a curve of 1: two counts of one record")
    refused(lambda o, _: o.update(predictor=None), "names forecaster None")
    refused(lambda o, _: o.update(predictor="llm"), "beside the 'statistical'")
    refused(lambda o, _: o.update(forecasters_counted=["llm", "statistical"]),
            "two forecasters pooled")
    refused(lambda o, _: o.update(written=2), "a rate from every pass")
    refused(lambda o, _: o.update(expected=367), "own counts project 2")
    refused(lambda o, _: o.update(
        message="350 of 100 · ~367 expected · season ends 09-27"),
        "not its own count of 1")
    refused(lambda o, _: o.update(record="at_the_line"),
            "filed beside a blind curve")
    refused(lambda o, _: o.update(event_tier="numbered"), "names event tier")
    refused(lambda o, _: o.update(tiers_counted=["numbered"]), "declares none")
    # THE REASONING PASS'S CURVE given the statistical model's outlook
    refused(lambda _, p: p["categories"][index + 1].update(
        outlook=copy.deepcopy(p["categories"][index]["outlook"])),
        "names forecaster 'statistical' beside the 'llm'")
    # A COUNT THE RECOUNT DOES NOT MAKE (operator question 17, 2026-09-28):
    # the curve and the outlook agree, and the recount made without their
    # door, one per distinct bet, does not -- or is not there
    refused(lambda o, _: o.update(recounted=2),
            "where the recount made without its door finds 2 and 1")
    refused(lambda o, _: o.update(recounted_written=None),
            "where the recount made without its door finds 1 and None")


def test_the_count_as_it_stood_is_refused_by_the_builder_the_api_and_the_gate(
        tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn, _, _, _ = _one_game_three_passes(tmp_path)
    audit.check_the_blind_outlook_is_never_pooled(conn)          # lawful: passes
    # THE COUNT AS IT STOOD: every row of the market, both passes
    monkeypatch.setattr(horizon, "standing_questions", _as_it_stood)
    for build in (calibration.blind_categories, calibration.scorecard):
        with pytest.raises(calibration.MergedCurve,
                           match="counts 2 settled forecasts for 1 distinct question"):
            build(conn, sport="mlb")
    with pytest.raises(audit.LawViolation, match="A BLIND OUTLOOK IS POOLED"):
        audit.check_the_blind_outlook_is_never_pooled(conn)
    # AND ASKING NOBODY IN PARTICULAR: both forecasters in one count
    monkeypatch.setattr(
        horizon, "standing_questions",
        lambda conn, **kw: _as_it_stood(conn, ask_the_forecaster=False, **kw))
    with pytest.raises(calibration.MergedCurve, match="two forecasters pooled"):
        calibration.blind_categories(conn, sport="mlb")
    # THE API ANSWERS 500 rather than serve it
    monkeypatch.setattr(horizon, "standing_questions", _as_it_stood)
    token = "test-token-for-the-outlook-counts"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "outlook.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            response = client.get("/api/scorecard", params={"sport": "mlb"})
    finally:
        api.set_database(None)
    assert response.status_code == 500
    assert "IN THE BLIND RECORD'S OUTLOOK" in response.json()["detail"]


def test_the_unit_scan_reads_the_door_and_the_count(tmp_path):
    """The rate's slates are read off the door's rows from 2026-09-27, so the
    unit scan reads the door (`g.week`) and the count (`week`)."""
    from pathlib import Path

    source = (Path(config.PACKAGE_ROOT) / "horizon.py").read_text(encoding="utf-8")
    assert audit.horizon_unit_faults(source) == []
    by_day = source.replace(
        "g.season, g.week,", "g.season, g.league_date AS week,", 1)
    assert by_day != source
    assert any("standing_questions" in f for f in audit.horizon_unit_faults(by_day))
    by_key = source.replace('slates = {r["week"] for r in this_season}',
                            'slates = {r["id"] for r in this_season}', 1)
    assert by_key != source
    assert any("_written_so_far" in f for f in audit.horizon_unit_faults(by_key))
