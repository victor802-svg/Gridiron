"""Line drift: two looks at the same line, and the gate over what they say.

The question is whether a disagreement is the model seeing something early or
the model being wrong. Two snapshots can tell those apart; one cannot. Most of
what can go wrong here is the two snapshots not really being two.
"""

from __future__ import annotations

import copy

import pytest

from gridiron import audit, calibration, config, db, drift, views
from gridiron.data import sources
from gridiron.market import espn


def test_the_second_look_may_not_come_from_the_cache():
    """The invariant behind the whole measurement.

    `http.fetch` serves anything younger than LIVE_TTL from `http_cache`. A
    near-start window at or above that is a replay of the open snapshot, and
    every drift pair then reads exactly zero movement -- which is what shipped,
    over eight rows, before this was caught.
    """
    assert espn.NEAR_START_TTL < sources.LIVE_TTL, (
        "a near-start quote inside the live cache window is the open quote "
        "replayed, and the drift figure would describe the cache"
    )


def _pair(conn, *, claim, opened, near, game):
    """One statistical moneyline forecast with both looks, on the league's
    `game`-th game: ONE GAME PER PAIR, because from 2026-09-27 a game and
    market is one bet however many forecasts ask it (question 14)."""
    game_id = conn.execute("SELECT id FROM games ORDER BY id LIMIT 1 OFFSET ?",
                           (game,)).fetchone()["id"]
    cur = conn.execute(
        "INSERT INTO predictions (sport, created_utc, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) VALUES"
        " ('nfl','2025-12-01T00:00:00Z',?, 'moneyline', 'HOME', ?, 'win',"
        " 'statistical','fs2','{}','because')",
        (game_id, claim),
    )
    pid = cur.lastrowid
    for kind, implied, when in (("open_at_predict", opened, "2025-12-01T01:00:00Z"),
                                ("near_start", near, "2025-12-01T20:00:00Z")):
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " line, implied_prob, kind) VALUES (?,?,?,?,?,?)",
            (pid, when, "test", None, implied, kind),
        )
    conn.commit()
    return pid


def _moneyline_pairs(conn):
    return drift.standing_pairs(conn, sport="nfl", market="moneyline",
                                predictor="statistical")


def _moneyline_report(conn):
    return drift.report(conn, sport="nfl", market="moneyline",
                        predictor="statistical")


def test_a_small_disagreement_is_not_a_disagreement(league):
    """Below the threshold the two are saying the same thing.

    Counting those would fill the sample with games where the movement is noise
    about nothing, and the fraction would drift toward 50% for arithmetic
    reasons rather than for anything about the market.
    """
    _pair(league, claim=0.52, opened=0.50, near=0.60, game=0)
    assert _moneyline_pairs(league) == []


def test_movement_toward_the_model_is_signed_from_the_two_numbers(league):
    """`toward` must not be read off which side the model took.

    The model can disagree in either direction, and a sign taken from the side
    rather than from the numbers is the wrong-side defect in a new costume.
    """
    # Model above the market, line rises: toward.
    _pair(league, claim=0.70, opened=0.50, near=0.58, game=0)
    # Model BELOW the market, line falls: also toward.
    _pair(league, claim=0.30, opened=0.50, near=0.42, game=1)
    # Model below the market, line rises: away.
    _pair(league, claim=0.30, opened=0.50, near=0.61, game=2)

    found = {p["prediction_id"]: p for p in _moneyline_pairs(league)}
    tow = sorted(p["toward"] for p in found.values())
    assert len(tow) == 3
    assert tow[0] < 0, "a line moving away from a low claim must be negative"
    assert tow[1] > 0 and tow[2] > 0


def test_no_direction_is_reported_below_the_gate(league):
    """The count, and nothing else.

    "The market moved toward the model 61% of the time" over nine games is a
    sentence a reader remembers and the nine is not.
    """
    for i in range(5):
        _pair(league, claim=0.70, opened=0.50, near=0.60, game=i)
    report = _moneyline_report(league)
    assert report["n"] == 5
    assert "toward_fraction" not in report
    assert "moved_toward" not in report
    assert str(drift.MIN_PAIRS) in report["line"]


def test_the_sentence_appears_only_once_the_gate_is_cleared(league):
    for i in range(drift.MIN_PAIRS):
        _pair(league, claim=0.70, opened=0.50, near=0.60, game=i)
    report = _moneyline_report(league)
    assert report["n"] >= drift.MIN_PAIRS
    assert report["toward_fraction"] == 1.0
    assert "moved toward it 100% of the time" in report["line"]
    assert str(report["n"]) in report["line"], "the sentence must carry its N"
    assert f"over {report['n']} games" in report["line"]


def test_a_prediction_with_one_look_is_not_a_pair(league):
    """A near-start line with nothing to compare against says nothing."""
    game = league.execute("SELECT id FROM games LIMIT 1").fetchone()["id"]
    cur = league.execute(
        "INSERT INTO predictions (sport, created_utc, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) VALUES"
        " ('nfl','2025-12-01T00:00:00Z',?, 'moneyline', 'ONE', 0.7, 'win',"
        " 'statistical','fs2','{}','because')",
        (game,),
    )
    league.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
        " line, implied_prob, kind) VALUES (?,?,?,?,?,?)",
        (cur.lastrowid, "2025-12-01T01:00:00Z", "test", None, 0.5,
         "open_at_predict"),
    )
    league.commit()
    assert _moneyline_pairs(league) == []


def test_only_one_snapshot_of_each_kind_per_prediction(league):
    """A second 'open_at_predict' would overwrite what the first one means."""
    import sqlite3

    pid = _pair(league, claim=0.70, opened=0.50, near=0.60, game=0)
    with pytest.raises(sqlite3.IntegrityError):
        league.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " line, implied_prob, kind) VALUES (?,?,?,?,?,?)",
            (pid, "2025-12-01T02:00:00Z", "test", None, 0.55, "open_at_predict"),
        )


# ---------------------------------------------------------------------------
# ONE PAIR PER BET, PER FORECASTER, THROUGH THE STANDING RULE (operator
# question 14, ruled 2026-09-27, 2 of 3): "Every count on the Record page
# that states a gate distance is rebuilt per forecaster (per tier for UFC)
# and per distinct bet, through its record's standing rule."
# ---------------------------------------------------------------------------

KICKOFF = "2026-09-09T00:00:00Z"


def _world(tmp_path, *, sport="nfl", games=("g0",)):
    conn = db.open_db(tmp_path / "drift.db")
    for game in games:
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, ?, 2026, 1, 'REG',"
            " 'SEA', 'NE', ?, 'scheduled', '2026-09-08')", (game, sport, KICKOFF))
    conn.commit()
    return conn


def _looked(conn, *, game="g0", sport="nfl", market="moneyline", prop=None,
            predictor="statistical", pass_kind="final",
            written="2026-09-08T12:00:00Z", prob=0.66, opened=0.50, near=0.56,
            subject="SEA", line=None, side="win", second_look=True):
    """One blind forecast with its first look at the line, and (unless told
    otherwise) its second near the start -- through the snapshot triggers."""
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " pass_kind, factor_set_version, factors_json, reasoning)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'fs5', '{}', 'test')",
        (written, sport, game, market, prop, subject, line, prob, side,
         predictor, pass_kind))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line,"
        " implied_prob, kind) VALUES (?, ?, 'test', ?, ?, 'open_at_predict')",
        (pid, db.just_after(written), line, opened))
    if second_look:
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " line, implied_prob, kind) VALUES (?, '2026-09-08T23:30:00Z',"
            " 'test', ?, ?, 'near_start')", (pid, line, near))
    conn.commit()
    return pid


def _one_game_three_passes(tmp_path):
    """THE SHAPE THE PAGE COUNTED TWICE: one game's moneyline forecast by the
    statistical model's morning and final pass and by the reasoning pass,
    each with both looks at the line and each disagreeing with the first."""
    conn = _world(tmp_path)
    early = _looked(conn, pass_kind="early", written="2026-09-07T12:00:00Z",
                    prob=0.62, near=0.46)
    final = _looked(conn, written="2026-09-08T12:00:00Z", prob=0.66, near=0.56)
    llm = _looked(conn, predictor="llm", written="2026-09-08T12:00:01Z",
                  prob=0.70, near=0.56)
    return conn, early, final, llm


def _as_it_stood(conn, *, sport, market, predictor, event_tier=None,
                 ask_the_forecaster=True, standing_only=False):
    """THE SHIPPED COUNT UNTIL 2026-09-27, as a door: every forecast of the
    market TYPE with both looks and a disagreement -- every pass, every rung,
    every prop type, every card -- with the fields the report reads, and
    nothing else. `standing_only` keeps one per QUESTION (the standing rule
    without the bet); `ask_the_forecaster=False` asks nobody in particular."""
    rows = conn.execute(
        "SELECT p.id, p.predictor, p.game_id, p.subject, p.line_asked,"
        " p.model_prob, p.calibrated_prob,"
        " o.implied_prob AS opened, n.implied_prob AS near"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " JOIN market_snapshots o"
        "   ON o.prediction_id = p.id AND o.kind = 'open_at_predict'"
        " JOIN market_snapshots n"
        "   ON n.prediction_id = p.id AND n.kind = 'near_start'"
        " WHERE p.sport = ? AND p.market_type = ?"
        + (" AND p.predictor = ?" if ask_the_forecaster else "")
        + (calibration.standing_row_clause(False) if standing_only else
           " AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
           "                 WHERE v.prediction_id = p.id)"),
        (sport, calibration.market_type_of(sport, market))
        + ((predictor,) if ask_the_forecaster else ())).fetchall()
    out = []
    for r in rows:
        claim = r["calibrated_prob"] if r["calibrated_prob"] is not None else r["model_prob"]
        if abs(claim - r["opened"]) < drift.MIN_DISAGREEMENT:
            continue
        movement = r["near"] - r["opened"]
        out.append({"prediction_id": r["id"], "predictor": r["predictor"],
                    "sport": sport, "market": market,
                    "prop_type": calibration.prop_type_of(sport, market),
                    "game_id": r["game_id"], "subject": r["subject"],
                    "line_asked": r["line_asked"], "event_tier": None,
                    "toward": movement if claim > r["opened"] else -movement})
    return out


def test_where_the_line_went_counts_one_bet_per_forecaster(tmp_path):
    """A question's morning and final pass were two pairs: MLB moneyline
    said "over 75 games", past the fifty, for 48 standing rows on 26
    September. One game is one bet per forecaster, its last standing
    forecast's pair."""
    conn, early, final, llm = _one_game_three_passes(tmp_path)
    mine = drift.standing_pairs(conn, sport="nfl", market="moneyline",
                                predictor="statistical")
    theirs = drift.standing_pairs(conn, sport="nfl", market="moneyline",
                                  predictor="llm")
    assert [p["prediction_id"] for p in mine] == [final]
    assert [p["prediction_id"] for p in theirs] == [llm]
    assert mine[0]["toward"] == pytest.approx(0.06)
    # THE GATE LIST: one row, the statistical model's, naming it
    page = views.drift_report(conn, "nfl")
    assert "n" not in page, "a total across the markets is nobody's record"
    (moneyline,) = [c for c in page["categories"] if c["market"] == "moneyline"]
    assert moneyline["n"] == moneyline["distinct_bets"] == 1
    assert moneyline["forecasters_counted"] == ["statistical"]
    assert moneyline["category_label"] == "moneyline, statistical"
    assert moneyline["progress"]["line"] == f"1 of {drift.MIN_PAIRS} pairs"
    assert not audit.plain_words_violations(moneyline["category_label"])
    # THE LEARNING PANEL: the same count, the same words
    learned = views.learning(conn, "nfl")
    row = next(r for r in learned["categories"] if r["market"] == "moneyline")
    assert [d["n"] for d in row["drift"]] == [1]
    assert row["drift"][0]["line"] == moneyline["line"]
    assert "drift_words" not in row and "drift_n" not in row


def test_a_standing_forecast_with_no_second_look_is_not_counted(tmp_path):
    """THROUGH THE STANDING RULE: a question whose standing forecast has no
    second look is not counted, even if a superseded pass of it had one --
    the 58 questions and 48 standing rows of question 14."""
    conn = _world(tmp_path)
    _looked(conn, pass_kind="early", written="2026-09-07T12:00:00Z")
    _looked(conn, written="2026-09-08T22:00:00Z", second_look=False)
    assert _moneyline_pairs(conn) == []
    assert views.drift_report(conn, "nfl")["categories"][0]["n"] == 0


def test_a_withdrawn_final_pass_leaves_the_morning_pass_standing(tmp_path):
    """A withdrawal takes back that forecast, not the question (ruling 1,
    2026-09-24): the morning pass stands again, and its pair is counted."""
    conn, early, final, _ = _one_game_three_passes(tmp_path)
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc,"
                 " reason) VALUES (?, ?, 'withdrawn by hand for the test')",
                 (final, db.utcnow()))
    conn.commit()
    (pair,) = _moneyline_pairs(conn)
    assert pair["prediction_id"] == early
    assert pair["toward"] == pytest.approx(-0.04)


def test_two_standing_rungs_of_one_game_are_one_bet(tmp_path):
    """The live NCAAF point spread record holds twelve games asked at two
    rungs, the morning pass's and a later pass's -- two standing questions,
    one line moving once. One bet, on the last standing forecast; and if
    that forecast agreed with the line, the bet has no disagreement to
    count, whatever the earlier rung said."""
    conn = _world(tmp_path, sport="cfb", games=("g0", "g1"))
    _looked(conn, sport="cfb", market="spread", side="cover", line=-14.5,
            pass_kind="early", written="2026-09-01T06:58:58Z", prob=0.95,
            opened=0.41, near=0.50)
    later = _looked(conn, sport="cfb", market="spread", side="cover",
                    line=-24.5, written="2026-09-08T15:00:56Z", prob=0.76,
                    opened=0.33, near=0.33)
    # THE LAST WORD AGREED WITH THE LINE on the second game: nothing to count
    _looked(conn, game="g1", sport="cfb", market="spread", side="cover",
            line=-14.5, pass_kind="early", written="2026-09-01T06:58:58Z",
            prob=0.95, opened=0.41, near=0.50)
    _looked(conn, game="g1", sport="cfb", market="spread", side="cover",
            line=-20.5, written="2026-09-08T16:00:00Z", prob=0.52,
            opened=0.50, near=0.60)
    pairs = drift.standing_pairs(conn, sport="cfb", market="spread",
                                 predictor="statistical")
    assert [p["prediction_id"] for p in pairs] == [later]
    (spread,) = views.drift_report(conn, "cfb")["categories"]
    assert spread["n"] == spread["distinct_bets"] == 1


def test_each_prop_type_is_its_own_count_and_a_player_is_the_bet(tmp_path):
    """A prop was counted by its market TYPE, 'prop' for every one, so each
    prop row of the learning panel showed the drift of all of them. Each
    type is now its own count, and within it a bet is one player's line in
    one game, however many rungs asked it."""
    conn = _world(tmp_path)
    for prop, player, rung, pass_kind in (
            ("passing_yards", "Geno Smith passing_yards", 240.5, "early"),
            ("passing_yards", "Geno Smith passing_yards", 260.5, "final"),
            ("passing_yards", "Drake Maye passing_yards", 210.5, "final"),
            ("rushing_yards", "Ken Walker rushing_yards", 70.5, "final")):
        _looked(conn, market="prop", prop=prop, subject=player, line=rung,
                side="over", pass_kind=pass_kind,
                written=("2026-09-07T12:00:00Z" if pass_kind == "early"
                         else "2026-09-08T12:00:00Z"))
    counts = {c["market"]: c["n"]
              for c in views.drift_report(conn, "nfl")["categories"]}
    assert counts == {"passing_yards": 2, "rushing_yards": 1}
    learned = {r["market"]: r["drift"][0]["n"]
               for r in views.learning(conn, "nfl")["categories"]}
    assert learned["passing_yards"] == 2 and learned["rushing_yards"] == 1
    assert learned["receptions"] == 0


def test_the_door_will_not_count_for_nobody_every_prop_or_across_cards(tmp_path):
    conn = _world(tmp_path)
    for who in (None, "all", "priced"):
        with pytest.raises(drift.PooledCount, match="never pooled"):
            drift.standing_pairs(conn, sport="nfl", market="moneyline",
                                 predictor=who)
    with pytest.raises(drift.PooledCount, match="every prop type in one count"):
        drift.standing_pairs(conn, sport="nfl", market="prop",
                             predictor="statistical")
    with pytest.raises(drift.PooledCount, match="LAW 6"):
        drift.standing_pairs(conn, sport="ufc", market="moneyline",
                             predictor="statistical")
    with pytest.raises(drift.PooledCount, match="LAW 6"):
        drift.standing_pairs(conn, sport="nfl", market="moneyline",
                             predictor="statistical", event_tier="numbered")
    with pytest.raises(config.CrossSportAggregation):
        drift.standing_pairs(conn, sport=None, market="moneyline",
                             predictor="statistical")
    with pytest.raises(TypeError):
        drift.report(conn, sport="nfl", market="moneyline")   # nobody named


def test_a_pooled_drift_count_is_refused_by_name(tmp_path):
    from gridiron import language

    conn, _, _, _ = _one_game_three_passes(tmp_path)
    honest = views.drift_report(conn, "nfl")
    drift.assert_no_pooled_drift_counts(honest)

    def refused(change, match, error=calibration.MergedCurve):
        payload = copy.deepcopy(honest)
        change(payload)
        with pytest.raises(error, match=match):
            drift.assert_no_pooled_drift_counts(payload)

    def first(payload):
        return payload["categories"][0]

    def twice(payload):
        entry = first(payload)
        entry.update(n=2, progress=language.progress(
            2, drift.MIN_PAIRS, noun="pairs",
            cleared_note="enough pairs to report a direction"),
            line=language.drift_line("nfl", entry["market"], 2, None,
                                     drift.MIN_PAIRS, drift.MIN_DISAGREEMENT))

    refused(lambda p: first(p)["filters"].update(predictor=None),
            "merges the statistical and LLM forecasters")
    refused(lambda p: first(p).update(predictor="llm"),
            "names forecaster 'llm'")
    refused(lambda p: first(p).update(forecasters_counted=["llm", "statistical"]),
            "two forecasters pooled")
    refused(twice, "counts 2 pairs for 1 distinct bet")
    refused(lambda p: p["categories"].append(copy.deepcopy(first(p))),
            "counted twice")
    refused(lambda p: first(p).update(
        toward_fraction=1.0, moved_toward=1, mean_movement=0.06),
        "reports a direction on 1 of the 50")
    refused(lambda p: first(p)["progress"].update(line="75 pairs"),
            "progress line")
    refused(lambda p: first(p).update(
        line="When the model disagreed by 5% or more, the market moved toward "
             "it 33% of the time over 75 games."), "not its own count")
    refused(lambda p: first(p).update(event_tier="numbered"), "declares none")
    refused(lambda p: first(p).update(market="prop"),
            "not one of nfl's declared markets")
    refused(lambda p: p.update(n=2), "a total 'n'")
    refused(lambda p: first(p).update(record="rung"),
            "filed under the line's drift", error=calibration.MergedRecord)


def test_the_count_as_it_stood_is_refused_by_the_builders_the_api_and_the_gate(
        tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn, _, _, _ = _one_game_three_passes(tmp_path)
    audit.check_the_drift_record_is_never_pooled(conn)          # lawful: passes
    # THE COUNT AS IT STOOD: every forecast with both looks, both passes
    monkeypatch.setattr(drift, "standing_pairs", _as_it_stood)
    for build in (views.drift_report, views.learning):
        with pytest.raises(calibration.MergedCurve,
                           match="counts 2 pairs for 1 distinct bet"):
            build(conn, "nfl")
    with pytest.raises(audit.LawViolation, match="A DRIFT COUNT IS POOLED"):
        audit.check_the_drift_record_is_never_pooled(conn)
    # AND ASKING NOBODY IN PARTICULAR: both forecasters in one count
    monkeypatch.setattr(
        drift, "standing_pairs",
        lambda conn, **kw: _as_it_stood(conn, ask_the_forecaster=False, **kw))
    with pytest.raises(calibration.MergedCurve, match="two forecasters pooled"):
        views.learning(conn, "nfl")
    # THE API ANSWERS 500 rather than serve it
    monkeypatch.setattr(drift, "standing_pairs", _as_it_stood)
    token = "test-token-for-the-drift-counts"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "drift.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            answers = {route: client.get(route, params={"sport": "nfl"})
                       for route in ("/api/scorecard", "/api/learning")}
    finally:
        api.set_database(None)
    for route, response in answers.items():
        assert response.status_code == 500, route
        assert "IN THE LINE'S DRIFT" in response.json()["detail"], route


def test_two_rungs_counted_as_two_questions_are_refused(tmp_path, monkeypatch):
    """The standing rule alone keeps one pair per QUESTION, and two rungs of
    one game are two questions: the builder counts bets."""
    conn = _world(tmp_path, sport="cfb")
    for rung, written, pass_kind in ((-14.5, "2026-09-01T06:58:58Z", "early"),
                                     (-24.5, "2026-09-08T15:00:56Z", "final")):
        _looked(conn, sport="cfb", market="spread", side="cover", line=rung,
                written=written, pass_kind=pass_kind, prob=0.8, opened=0.4,
                near=0.45)
    monkeypatch.setattr(
        drift, "standing_pairs",
        lambda conn, **kw: _as_it_stood(conn, standing_only=True, **kw))
    with pytest.raises(calibration.MergedCurve,
                       match="counts 2 pairs for 1 distinct bet"):
        views.drift_report(conn, "cfb")


def _ufc_bout(conn, bout: str, event: str, tier: str) -> None:
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier) VALUES (?, ?, ?, 2026, ?, ?)",
        (event, f"UFC {event}", KICKOFF, db.utcnow(), tier))
    conn.execute(
        "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
        " fighter_a, fighter_b, status, fetched_utc)"
        " VALUES (?, ?, ?, 3, 'A', 'B', 'scheduled', ?)",
        (bout, event, KICKOFF, db.utcnow()))
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES (?, 'ufc', 2026, 1, 'REG',"
        " 'A', 'B', ?, 'scheduled', '2026-09-08')", (bout, KICKOFF))


def test_a_ufc_drift_count_is_one_cards(tmp_path, monkeypatch):
    """LAW 6 one level down: a numbered-card bout and a Fight Night bout are
    two counts, each naming its card, on the gate list and on the learning
    panel -- never one moneyline count."""
    conn = db.open_db(tmp_path / "ufc.db")
    _ufc_bout(conn, "u1", "e1", "numbered")
    _ufc_bout(conn, "u2", "e2", "fight_night")
    for bout in ("u1", "u2"):
        _looked(conn, game=bout, sport="ufc", subject="A")
    page = views.drift_report(conn, "ufc")
    got = {(c["market"], c["event_tier"]): c for c in page["categories"]}
    assert set(got) == {("moneyline", t) for t in config.event_tiers("ufc")}
    for tier in ("numbered", "fight_night"):
        assert got[("moneyline", tier)]["n"] == 1
        assert got[("moneyline", tier)]["tiers_counted"] == [tier]
    assert got[("moneyline", "contender")]["n"] == 0
    assert got[("moneyline", "fight_night")]["category_label"] == (
        "moneyline, Fight Night, statistical")
    lines = [d["line"] for r in views.learning(conn, "ufc")["categories"]
             if r["market"] == "moneyline" for d in r["drift"]]
    assert [line.split(":")[0] for line in lines] == [
        "Numbered card", "Fight Night", "Contender Series"]
    # A DOOR THAT STOPPED FILTERING BY CARD is seen off the pairs themselves
    real = drift.standing_pairs
    monkeypatch.setattr(
        drift, "standing_pairs",
        lambda conn, *, sport, market, predictor, event_tier=None: [
            p for tier in config.event_tiers(sport)
            for p in real(conn, sport=sport, market=market,
                          predictor=predictor, event_tier=tier)])
    with pytest.raises(calibration.MergedCurve, match="never summed"):
        views.drift_report(conn, "ufc")
