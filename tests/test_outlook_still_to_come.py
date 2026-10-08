"""The outlook counts only slates still to come, and says the most the count
can reach this season (operator question 33, ruled 2026-09-30; built
2026-10-08).

"Q33: the outlook counts only cards still to come; say the real maximum
reachable this season." The re-read of 29 September (finding G1): two Fight
Night cards already fought each kept one bout the source never marked over
(401913546, 401923433), and `horizon.slates_remaining` counted every week
holding a game still marked 'scheduled', so Fight Night's outlook multiplied
its pace by six cards where four were still to come and said "39 of 100 ·
~121 expected" of a gate the four could take only to ~94.

Each test here fails on c4014a9 (the release, `git archive`): there is no
`horizon.slates_to_come`, no recount of it, no guard, and the line says
"~N expected".
"""

from __future__ import annotations

import copy

import pytest

from gridiron import audit, calibration, config, db, horizon, language, recount
from gridiron.market import recommend

SEASON = config.SPORT_CURRENT_SEASON["ufc"]
GATE = config.MIN_SAMPLE_FOR_EDGE_CLAIM
ASKED_AT = "2026-10-08T03:50:00Z"


def _card(conn, event: str, tier: str, week: int, kickoff: str, bouts) -> None:
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier) VALUES (?, ?, ?, ?, '2026-09-01T00:00:00Z', ?)",
        (event, f"UFC {event}", kickoff, SEASON, tier))
    for bout, status in bouts:
        played = status == "final"
        conn.execute(
            "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
            " fighter_a, fighter_b, status, fetched_utc)"
            " VALUES (?, ?, ?, 3, 'A', 'B', ?, '2026-09-01T00:00:00Z')",
            (bout, event, kickoff, status))
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES (?, 'ufc', ?, ?, 'R', 'A', 'B', ?, ?, ?, ?, ?)",
            (bout, SEASON, week, kickoff, status, kickoff[:10],
             1 if played else None, 0 if played else None))


def _forecast(conn, game: str, *, settled: bool, written: str,
              sport: str = "ufc", market: str = "moneyline") -> int:
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
        " VALUES (?, ?, ?, ?, 'A', NULL, 0.6, 'win', 'statistical', 'final',"
        " 'fs2', '{}', 'test', ?, ?)",
        (written, sport, game, market,
         "2026-09-13T03:00:00Z" if settled else None, 1 if settled else None))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]


def _the_re_reads_world(tmp_path):
    """THE RE-READ'S SHAPE: a Fight Night card fought on 12 September whose
    third bout the source never marked over (its question waiting), and one
    Fight Night card still to come on 10 October; asked on 8 October."""
    conn = db.open_db(tmp_path / "q33.db")
    _card(conn, "fought", "fight_night", 1, "2026-09-12T18:00:00Z",
          (("f1", "final"), ("f2", "final"), ("f3", "scheduled")))
    _card(conn, "ahead", "fight_night", 2, "2026-10-10T21:00:00Z",
          (("a1", "scheduled"), ("a2", "scheduled")))
    for bout, settled in (("f1", True), ("f2", True), ("f3", False)):
        _forecast(conn, bout, settled=settled, written="2026-09-11T20:00:00Z")
    conn.commit()
    return conn


def _fight_night(conn):
    for c in calibration.blind_categories(conn, sport="ufc"):
        if (c["market"] == "moneyline" and c.get("event_tier") == "fight_night"
                and c["filters"]["predictor"] == "statistical"):
            return c["outlook"]
    raise AssertionError("no Fight Night moneyline category")


@pytest.fixture
def asked_on_8_october(monkeypatch):
    monkeypatch.setattr(db, "utcnow", lambda: ASKED_AT)


def test_a_card_already_fought_is_not_still_to_come(tmp_path, asked_on_8_october):
    """The fought card holds a bout still marked 'scheduled'; it is not to
    come, because every game on it has started. The card on 10 October is."""
    conn = _the_re_reads_world(tmp_path)
    assert horizon.slates_to_come(conn, "ufc", SEASON, "fight_night") == [2]
    assert horizon.slates_remaining(conn, "ufc", SEASON, "fight_night") == 1
    assert recount.slates_to_come(conn, sport="ufc", season=SEASON,
                                  event_tier="fight_night", now=ASKED_AT) == [2]
    # AS IT STOOD: both weeks held a game marked 'scheduled'.
    stood = conn.execute(
        "SELECT COUNT(DISTINCT week) FROM games WHERE sport = 'ufc'"
        " AND season = ? AND status = 'scheduled'", (SEASON,)).fetchone()[0]
    assert stood == 2
    # And the card on 10 October is no longer to come once it has started.
    assert horizon.slates_to_come(conn, "ufc", SEASON, "fight_night",
                                  now="2026-10-10T21:00:00Z") == []
    assert horizon.slates_to_come(conn, "ufc", SEASON, "fight_night",
                                  now="2026-10-10T20:59:59Z") == [2]


def test_the_line_counts_the_cards_still_to_come_and_says_the_most(
        tmp_path, asked_on_8_october):
    """2 settled, the fought card's third question waiting to settle, and
    the card still to come at the pace (3 a card): at most 6, under the
    gate -- where the line said "~8 expected" of two cards to come."""
    conn = _the_re_reads_world(tmp_path)
    out = _fight_night(conn)
    assert (out["resolved"], out["written"], out["slates_used"]) == (2, 3, 1)
    assert out["slates_to_come"] == out["slates_to_come_recounted"] == [2]
    assert out["to_come"] == [{"slate": 2, "settled": 0, "waiting": 0}]
    assert out["waiting_elsewhere"] == 1 and out["on_slates_to_come"] == 3.0
    assert out["expected"] == horizon.expected_from(out) == 6
    assert out["reachable"] is False
    assert out["message"] == (
        f"2 of {GATE} · at most ~6 this season (1 waiting to settle, ~3 more "
        f"on the 1 card still to come) · season ends 10-10 · THIS GATE "
        f"CANNOT CLEAR THIS SEASON")
    assert audit.plain_words_violations(out["message"]) == []


def test_a_slate_of_any_sport_whose_games_have_all_started_is_not_to_come(
        tmp_path):
    """Every sport, one rule: a week whose games have all started is not to
    come whatever their status says; a week with one game still to start
    is; a game seen truly under way before its listed start has started."""
    conn = db.open_db(tmp_path / "every.db")
    for gid, week, kickoff in (
            ("w1a", 1, "2026-10-04T17:00:00Z"),       # played, still listed
            ("w1b", 1, "2026-10-05T00:20:00Z"),
            ("w2a", 2, "2026-10-08T00:15:00Z"),       # started at the clock
            ("w2b", 2, "2026-10-12T17:00:00Z"),       # still to come
            ("w3a", 3, "2026-10-19T17:00:00Z")):      # seen under way early
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'nfl', 2026, ?,"
            " 'REG', 'HOM', 'AWY', ?, 'scheduled', ?)",
            (gid, week, kickoff, kickoff[:10]))
    conn.execute(
        "INSERT INTO live_first_under_way (game_id, sport, under_way_utc,"
        " feed_status, evidence) VALUES ('w3a', 'nfl', '2026-10-08T01:00:00Z',"
        " 'In Progress', 'a period of 1 recorded')")
    conn.commit()
    now = "2026-10-08T03:50:00Z"
    assert horizon.slates_to_come(conn, "nfl", 2026, now=now) == [2]
    assert recount.slates_to_come(conn, sport="nfl", season=2026,
                                  event_tier=None, now=now) == [2]
    # THE SAME RULE AS THE ENGINE'S ONE DOOR, game by game.
    for r in conn.execute("SELECT id, week, status, kickoff_utc FROM games"):
        under = conn.execute("SELECT under_way_utc FROM live_first_under_way"
                             " WHERE game_id = ?", (r["id"],)).fetchone()
        upcoming = recommend.not_still_upcoming(
            r["status"], r["kickoff_utc"], under[0] if under else None, now) is None
        assert upcoming == (r["id"] == "w2b"), r["id"]


def test_a_game_with_no_start_time_is_still_to_come_and_one_unread_is_not(
        tmp_path):
    conn = db.open_db(tmp_path / "start.db")
    for gid, week, kickoff in (("n1", 1, None), ("u1", 2, "not a time")):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, ?, 'R',"
            " 'HOM', 'AWY', ?, 'scheduled', '2026-10-09')", (gid, week, kickoff))
    conn.commit()
    now = "2026-10-08T03:50:00Z"
    assert horizon.slates_to_come(conn, "mlb", 2026, now=now) == [1]
    assert recount.slates_to_come(conn, sport="mlb", season=2026,
                                  event_tier=None, now=now) == [1]


def test_the_most_holds_what_is_written_where_it_is_more_than_the_pace(
        tmp_path, asked_on_8_october):
    """A slate still to come already written beyond the pace holds what it
    holds; one written below it holds the pace -- never under either."""
    conn = db.open_db(tmp_path / "most.db")
    _card(conn, "played", "fight_night", 1, "2026-09-12T18:00:00Z",
          (("p1", "final"), ("p2", "final")))
    _card(conn, "next", "fight_night", 2, "2026-10-10T21:00:00Z",
          (("n1", "scheduled"), ("n2", "scheduled"), ("n3", "scheduled")))
    _card(conn, "later", "fight_night", 3, "2026-10-17T21:00:00Z",
          (("l1", "scheduled"),))
    for bout in ("p1", "p2"):
        _forecast(conn, bout, settled=True, written="2026-09-11T20:00:00Z")
    for bout in ("n1", "n2", "n3"):
        _forecast(conn, bout, settled=False, written="2026-10-07T18:00:00Z")
    out = _fight_night(conn)
    # pace 5 written over 2 cards = 2.5: the next card holds its 3 written,
    # the later one the pace, 2.5 -- 2 + 3 + 2.5 = 7.5, said ~8.
    assert out["to_come"] == [{"slate": 2, "settled": 0, "waiting": 3},
                              {"slate": 3, "settled": 0, "waiting": 0}]
    assert out["waiting_elsewhere"] == 0 and out["on_slates_to_come"] == 5.5
    assert out["expected"] == horizon.expected_from(out) == 8
    assert "at most ~8 this season (~6 more on the 2 cards still to come)" \
        in out["message"]


def test_a_retired_or_routed_off_outlook_counts_no_slate(tmp_path, monkeypatch):
    conn = db.open_db(tmp_path / "routed.db")
    for market in ("rounds", "distance"):
        out = horizon.llm_routed_off_outlook(conn, "ufc", market,
                                             event_tier="fight_night")
        assert out["slates_remaining"] == 0 and out["to_come"] == []
        calibration.refuse_slates_not_still_to_come(out, "the routed-off line")


def test_an_outlook_counting_a_fought_card_is_refused_by_the_builder_the_api_and_the_gate(
        tmp_path, asked_on_8_october, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn = _the_re_reads_world(tmp_path)
    audit.check_the_blind_outlook_is_never_pooled(conn)          # lawful: passes

    def as_it_stood(conn, sport, season, event_tier=None, *, now=None):
        sql = ("SELECT DISTINCT week FROM games WHERE sport = ? AND season = ?"
               " AND status = 'scheduled'")
        params = [sport, season]
        if event_tier is not None:
            sql += (" AND EXISTS (SELECT 1 FROM ufc_bouts b JOIN ufc_events e"
                    " ON e.id = b.event_id WHERE b.id = games.id"
                    " AND e.event_tier = ?)")
            params.append(event_tier)
        return sorted(int(r[0]) for r in conn.execute(sql, params))

    monkeypatch.setattr(horizon, "slates_to_come", as_it_stood)
    for build in (calibration.blind_categories, calibration.scorecard,
                  calibration.at_the_line_scorecard):
        with pytest.raises(calibration.SlateNotStillToCome,
                           match=r"every game on \[1\] has started"):
            build(conn, sport="ufc")
    with pytest.raises(audit.LawViolation, match="ONLY SLATES STILL TO COME"):
        audit.check_the_blind_outlook_is_never_pooled(conn)
    token = "test-token-for-the-slates-still-to-come"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "q33.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            response = client.get("/api/scorecard", params={"sport": "ufc"})
    finally:
        api.set_database(None)
    assert response.status_code == 500
    assert "ONLY SLATES STILL TO COME" in response.json()["detail"]


def test_the_arithmetic_and_the_words_as_they_stood_are_refused(
        tmp_path, asked_on_8_october, monkeypatch):
    """The guard works the most out in its own spelling and reads the words
    apart from the one composition, so either put back is seen."""
    conn = _the_re_reads_world(tmp_path)
    monkeypatch.setattr(horizon, "most_reachable",
                        lambda resolved, waiting, to_come, pace:
                        (resolved + pace * len(to_come), pace * len(to_come)))
    with pytest.raises(calibration.MergedCurve,
                       match="expects 5 where its own counts project 6"):
        calibration.blind_categories(conn, sport="ufc")
    monkeypatch.undo()
    monkeypatch.setattr(db, "utcnow", lambda: ASKED_AT)
    real = language.market_outlook_line

    def expected_words(n, gate, expected, ends, **kw):
        if expected is None:
            return real(n, gate, expected, ends, **kw)
        line = f"{n} of {gate} · ~{expected} expected · season ends {ends[5:]}"
        return line if expected >= gate else f"{line} · THIS GATE CANNOT CLEAR THIS SEASON"

    monkeypatch.setattr(language, "market_outlook_line", expected_words)
    with pytest.raises(calibration.SlateNotStillToCome, match="'at most'"):
        calibration.blind_categories(conn, sport="ufc")


def test_the_guard_refuses_each_slate_and_count_by_name(tmp_path, asked_on_8_october):
    conn = _the_re_reads_world(tmp_path)
    honest = {"sport": "ufc", "record": "rung",
              "categories": calibration.blind_categories(conn, sport="ufc")}
    calibration.assert_no_pooled_outlooks(honest)
    index = next(i for i, c in enumerate(honest["categories"])
                 if c["market"] == "moneyline" and c.get("event_tier") == "fight_night"
                 and c["filters"]["predictor"] == "statistical")

    def refused(change, match, *, consistent=False):
        payload = copy.deepcopy(honest)
        out = payload["categories"][index]["outlook"]
        change(out)
        if consistent:
            # THE OUTLOOK'S OWN ARITHMETIC AND WORDS MADE TO AGREE WITH THE
            # CHANGE, so only the recount the guard holds them to can see it.
            out["on_slates_to_come"] = horizon.on_slates_to_come_from(out)
            out["expected"] = horizon.expected_from(out)
            out["reachable"] = out["expected"] >= out["gate"]
            out["message"] = horizon.outlook_words(out)
        with pytest.raises(calibration.MergedCurve, match=match):
            calibration.assert_no_pooled_outlooks(payload)

    refused(lambda o: o.update(slates_to_come=[1, 2]), "every game on")
    refused(lambda o: o.update(slates_to_come_recounted=None), "no recount")
    refused(lambda o: o.update(slates_remaining=2), "beside a list of 1")
    refused(lambda o: o["to_come"][0].update(waiting=4), "finds 0 and 0",
            consistent=True)
    refused(lambda o: o.update(waiting_elsewhere=0), "where the recount finds 1",
            consistent=True)
    refused(lambda o: (o.update(on_slates_to_come=13.25),
                       o.update(message=horizon.outlook_words(o))),
            "its own counts make 3.0")
    refused(lambda o: o.update(reachable=True), "reachable=True")


def test_the_at_the_line_outlook_reads_the_one_rule_and_its_card(
        tmp_path, asked_on_8_october):
    """The at-the-line outlook multiplied its pace by every card's slates
    holding a game marked 'scheduled'; it reads the one rule, for its own
    card, and carries the recount."""
    conn = _the_re_reads_world(tmp_path)
    _card(conn, "cs_ahead", "contender", 3, "2026-10-13T23:00:00Z",
          (("c1", "scheduled"),))
    conn.commit()
    out = horizon.at_the_line_outlook(conn, "ufc", "moneyline",
                                      predictor="statistical", bets=[],
                                      event_tier="fight_night")
    assert out["slates_to_come"] == out["slates_to_come_recounted"] == [2]
    assert out["slates_remaining"] == 1
    calibration.refuse_slates_not_still_to_come(out, "the at-the-line outlook")


def test_the_unit_scan_names_a_rule_without_the_start():
    from pathlib import Path

    source = (Path(config.PACKAGE_ROOT) / "horizon.py").read_text(encoding="utf-8")
    assert audit.horizon_unit_faults(source) == []
    anchor = "f\"   AND {live.before_the_start('clock.now_utc', 'g', conn)}\")"
    assert anchor in source
    broken = source.replace(anchor, "\"   AND 1 = 1\")", 1)
    assert any("before_the_start" in f for f in audit.horizon_unit_faults(broken))
    counted_again = source.replace(
        "return len(slates_to_come(conn, sport, season, event_tier, now=now))",
        "return int(conn.execute(\"SELECT COUNT(DISTINCT week) FROM games\")"
        ".fetchone()[0])", 1)
    assert counted_again != source
    assert any("two rules" in f for f in audit.horizon_unit_faults(counted_again))
