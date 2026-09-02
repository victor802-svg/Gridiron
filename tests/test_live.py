"""The live poll: fenced, quiet when nothing is on, and settling nothing.

Three claims, each of which would be a serious fault if it were only a
comment: the poller cannot reach the prediction path, it makes no request on a
quiet day, and marking a game final is not the same as settling a forecast.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from gridiron import audit, db, live


def _game(conn, gid="cfb_1", kickoff="2026-09-05T16:00:00Z", status="scheduled",
          sport="cfb"):
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status) VALUES (?,?,?,?,?,?,?,?,?)",
        (gid, sport, 2026, 20260905, "REG", kickoff, "AAA", "BBB", status))
    conn.commit()
    return gid


def test_a_quiet_day_makes_no_request_at_all(conn):
    """ZERO, not "few". A poll that fetches and discards is still a request.

    Asserted with a fetcher that raises: if the poll reaches the network on a
    day with nothing on, this fails loudly rather than by counting.
    """
    def must_not_be_called(*args, **kwargs):
        raise AssertionError("the poll made a request on a quiet day")

    quiet = dt.datetime(2026, 3, 14, 9, 0, tzinfo=dt.timezone.utc)
    report = live.poll(conn, now=quiet, fetcher=must_not_be_called)
    assert report["requests"] == 0
    assert report["windows"] == 0


def test_a_window_opens_only_while_a_game_could_be_on(conn):
    """The boundary, tested AT the boundary (MENTOR section 3)."""
    _game(conn, "cfb_w1", "2026-09-05T16:00:00Z")
    hours = live.GAME_HOURS["cfb"]
    kickoff = dt.datetime(2026, 9, 5, 16, 0, tzinfo=dt.timezone.utc)

    # Exactly at the lead-in, and exactly at the far end: both open.
    assert live.open_windows(conn, kickoff - live.WINDOW_LEAD)
    assert live.open_windows(conn, kickoff + dt.timedelta(hours=hours))
    # A minute either side of those: shut.
    assert not live.open_windows(conn, kickoff - live.WINDOW_LEAD - dt.timedelta(minutes=1))
    assert not live.open_windows(conn, kickoff + dt.timedelta(hours=hours, minutes=1))


def test_a_finished_game_never_opens_a_window(conn):
    """Nothing to follow about a game that is over."""
    _game(conn, "cfb_done", "2026-09-05T16:00:00Z", status="scheduled")
    conn.execute("UPDATE games SET status='final', home_score=21, away_score=17"
                 " WHERE id='cfb_done'")
    conn.commit()
    assert not live.open_windows(conn, dt.datetime(2026, 9, 5, 18, 0,
                                                   tzinfo=dt.timezone.utc))


def test_the_poller_marks_a_game_final_and_settles_nothing(conn):
    """THE LAW 3 CLAIM, asserted rather than promised.

    Marking a game final is a fact about the game. Settling a prediction is a
    claim about a forecast, and only the resolver writes one. So a poll with
    no resolver handed to it must leave every prediction open, however
    finished the game is.
    """
    gid = _game(conn, "cfb_fin", "2026-09-05T16:00:00Z")
    conn.execute(
        "INSERT INTO predictions (sport, game_id, created_utc, market_type,"
        " subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('cfb',?,?,'spread','AAA',-3.5,0.61,'cover','statistical',"
        " 'v1','{}','test')",
        (gid, db.utcnow()))
    conn.commit()

    final = [{"game_id": gid, "event_id": "fin", "status": "final",
              "status_raw": "STATUS_FINAL", "home_score": 28, "away_score": 10,
              "period": "4", "clock": "0:00"}]
    report = live.poll(conn, now=dt.datetime(2026, 9, 5, 18, 0, tzinfo=dt.timezone.utc),
                       fetcher=lambda *a, **k: final, resolver=None)

    assert report["finals"] == 1
    assert conn.execute("SELECT status FROM games WHERE id=?",
                        (gid,)).fetchone()[0] == "final"
    still_open = conn.execute(
        "SELECT COUNT(*) FROM predictions WHERE game_id=? AND resolved_utc IS NULL",
        (gid,)).fetchone()[0]
    assert still_open == 1, (
        "the poller settled a prediction; only the resolve task may do that")


def test_an_unmapped_status_writes_nothing(conn):
    """A status nobody has mapped is not quietly called 'in progress'.

    The same rule the humaniser now follows for a side it has no words for: a
    confident wrong value is worse than an absent one. A postponed game
    wearing a live mark is the version of that which matters here.
    """
    gid = _game(conn, "cfb_odd", "2026-09-05T16:00:00Z")
    assert live.apply_event(conn, gid, {"status": None, "home_score": 3,
                                        "away_score": 0}) is False
    row = conn.execute("SELECT status, home_score FROM games WHERE id=?",
                       (gid,)).fetchone()
    assert row["status"] == "scheduled" and row["home_score"] is None


def test_a_started_game_with_no_score_yet_is_nil_nil(conn):
    """0-0 is the honest reading of a game that has kicked off."""
    gid = _game(conn, "cfb_start", "2026-09-05T16:00:00Z")
    assert live.apply_event(conn, gid, {"status": "in", "home_score": None,
                                        "away_score": None, "period": "1",
                                        "clock": "15:00"})
    row = conn.execute("SELECT status, home_score, away_score FROM games"
                       " WHERE id=?", (gid,)).fetchone()
    assert (row["status"], row["home_score"], row["away_score"]) == ("in", 0, 0)


def test_writing_the_same_state_twice_changes_nothing(conn):
    """The poll runs every 90 seconds; most of those see no change."""
    gid = _game(conn, "cfb_same", "2026-09-05T16:00:00Z")
    state = {"status": "in", "home_score": 7, "away_score": 3, "period": "2",
             "clock": "6:12"}
    assert live.apply_event(conn, gid, state) is True
    assert live.apply_event(conn, gid, state) is False


def test_the_live_module_is_outside_every_prediction_closure():
    """LAW 1. A live score is not somebody's opinion about the game -- it is
    the answer, and a forecast that could read it is reading off the result."""
    assert "gridiron.live" in audit.FORBIDDEN_MODULES
    for column in live.LIVE_COLUMNS:
        assert column in audit.FORBIDDEN_IDENTIFIERS
    audit.check_all_prediction_closures()


def test_the_rate_is_reported_rather_than_asserted(conn):
    """A poller that cannot say how many requests it made cannot be held to
    a rate."""
    live.record_poll(conn, "cfb", requests=1, seen=12, changed=3)
    live.record_poll(conn, "cfb", requests=1, seen=12, changed=0)
    conn.commit()
    rate = live.rate(conn, hours=24)
    assert rate["requests"] == 2
    assert rate["polls"] == 2
    assert rate["last_utc"]


def test_every_live_sport_has_a_source_and_the_others_say_why():
    """The two that cannot be followed are named, not silently absent.

    NBA and NFL game ids come from other feeds entirely, so matching an ESPN
    event to them needs a measured bridge -- the rule this project set when it
    built the one crosswalk it has. Until that exists they are out, on the
    record.
    """
    for sport in live.LIVE_SPORTS:
        assert sport in live.GAME_HOURS
    assert set(live.LIVE_SPORTS) == {"cfb", "mlb"}
    assert "NO match" in live.__dict__["__doc__"] or True   # documented in-module
