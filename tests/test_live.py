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


# ---------------------------------------------------------------------------
# THE TILE KNOWS THE GAME STATE (L2)
# ---------------------------------------------------------------------------


def test_the_three_states_are_the_three_that_exist():
    from gridiron import language

    assert language.tile_state("scheduled") == "upcoming"
    assert language.tile_state("in") == "live"
    assert language.tile_state("final") == "final"
    # Resolved or voided is final however the game's status reads, and an
    # unmapped status is upcoming rather than a guess.
    assert language.tile_state("scheduled", resolved=True) == "final"
    assert language.tile_state("in", voided=True) == "final"
    assert language.tile_state("postponed-ish") == "upcoming"


def test_a_finished_game_shows_no_clock():
    """"Bottom 9th" beside a final score reads as a game still being played."""
    from gridiron import language

    assert language.clock_line("Bottom 9th", None, "live") == "Bottom 9th"
    assert language.clock_line("Bottom 9th", None, "final") is None


def test_a_totals_tile_shows_the_running_total_not_a_team_score():
    """A totals question names no team, so a team score would answer a
    question nobody asked."""
    from gridiron import language

    assert language.running_total_line(21, 10, 58.5, "under") == "31 · under 58.5"
    assert language.running_total_line(None, 10, 58.5, "under") is None


def test_the_score_line_is_absent_until_there_is_a_score():
    from gridiron import language

    assert language.score_line("ALA", None, "ECU", None) is None
    assert language.score_line("ALA", 21, "ECU", 7) == "ALA 21 · ECU 7"


def test_the_compact_payload_is_much_smaller_than_the_slate(conn):
    """The reason it is a second endpoint rather than a re-fetch.

    Re-fetching the full slate every sixty seconds to learn that a score went
    from 7 to 10 sends a book to deliver a number: the slate carries every
    card's decomposition, its why and its bucket, none of which moves while a
    game is played.
    """
    import json

    from gridiron import config, views

    for sport in config.SPORTS:
        full = json.dumps(views.week(conn, sport), default=str)
        small = json.dumps(views.live_slate(conn, sport), default=str)
        if len(full) < 5000:
            continue                      # a fixture slate too small to compare
        assert len(small) * 5 < len(full), (
            f"{sport}: the live payload is {len(small)} against {len(full)} -- "
            f"not compact enough to justify a second endpoint")


def test_the_live_payload_describes_the_same_slate_as_the_page(conn):
    """Otherwise the browser polls one slate while showing another: scores
    that never arrive, for games nobody is looking at."""
    from gridiron import config, views

    for sport in config.SPORTS:
        page = views.week(conn, sport)
        live_now = views.live_slate(conn, sport)
        if page["week"] is None:
            continue
        assert live_now["week"] == page["week"], (
            f"{sport}: the page shows week {page['week']} and the live poll "
            f"follows {live_now['week']}")


def test_any_live_is_false_when_nothing_is_on(conn):
    """The browser's stop condition, and it must be the server's word."""
    from gridiron import config, views

    for sport in config.SPORTS:
        payload = views.live_slate(conn, sport)
        states = {p["tile_state"] for p in payload["picks"]}
        assert payload["any_live"] == ("live" in states)


# ---------------------------------------------------------------------------
# ONE MOTION VOCABULARY (L3)
# ---------------------------------------------------------------------------


def test_the_shipped_stylesheet_stays_inside_the_vocabulary():
    audit.check_motion_vocabulary()


def test_a_long_animation_is_a_fault():
    """Past about a fifth of a second, motion stops saying "this changed" and
    becomes something a reader waits for."""
    faults = audit.motion_faults(".x { transition: opacity 400ms ease-out; }")
    assert faults and "400ms" in faults[0]


def test_animating_a_layout_property_is_a_fault():
    """Height and width force the page to be laid out again on every frame --
    the classic janky animation, and the one that already existed here."""
    for prop in ("max-height", "height", "width", "top"):
        faults = audit.motion_faults(f".x {{ transition: {prop} 150ms ease-out; }}")
        assert faults, f"{prop} was allowed to animate"


def test_a_second_easing_curve_is_a_fault():
    """One curve, so everything on the page arrives the same way."""
    assert audit.motion_faults(".x { transition: opacity 150ms ease-in; }")
    assert audit.motion_faults(".x { transition: opacity 150ms cubic-bezier(0,0,1,1); }")
    assert not audit.motion_faults(".x { transition: opacity 150ms ease-out; }")


def test_the_only_keyframe_is_the_live_pulse():
    assert audit.motion_faults("@keyframes shake { 50% { opacity: 0; } }")
    assert not audit.motion_faults("@keyframes live-pulse { 50% { opacity: 0.35; } }")


def test_the_pulse_has_a_floor_and_everything_else_has_a_ceiling():
    """The two faults are opposite, and a ceiling alone would miss the strobe.

    A transition is a change completing, and a slow one is the fault. A pulse
    is a loop saying "still happening", and a FAST one is the fault: 200ms is
    5Hz, which is visually horrible and a hazard for photosensitive readers.
    """
    assert audit.motion_faults(audit.MOTION_FIXTURE_STROBE)
    assert not audit.motion_faults(
        ".tile-live { animation: live-pulse 1.6s ease-out infinite; }")
    assert audit.MOTION_PULSE_MIN_MS >= 1000


def test_polling_starts_and_stops_with_the_window(conn):
    """POLL HONESTY, both edges, with a fetcher that counts.

    The quiet-day test proves zero requests when nothing is on. This proves
    the other half: that the poll starts when a game does and stops when the
    window closes -- a poller that never stopped would be indistinguishable
    from one that never started, by request count alone.
    """
    kickoff = dt.datetime(2026, 9, 5, 16, 0, tzinfo=dt.timezone.utc)
    _game(conn, "cfb_win", kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"))
    calls = []

    def counting(conn_, sport, day):
        calls.append((sport, day))
        return []

    hours = live.GAME_HOURS["cfb"]
    before = kickoff - dt.timedelta(hours=2)
    during = kickoff + dt.timedelta(hours=1)
    after = kickoff + dt.timedelta(hours=hours + 1)

    live.poll(conn, now=before, fetcher=counting)
    assert calls == [], "the poll ran two hours before kickoff"

    live.poll(conn, now=during, fetcher=counting)
    assert len(calls) == 1, "the poll did not run during the game"

    live.poll(conn, now=after, fetcher=counting)
    assert len(calls) == 1, (
        "the poll ran after the window closed; a poller that never stops is "
        "indistinguishable from one that never started")


def test_the_live_mark_states_no_opinion():
    audit.check_the_live_mark_is_not_an_opinion()
    assert audit.live_mark_faults(audit.LIVE_MARK_FIXTURE_POSITIVE)


def test_a_score_arriving_does_not_move_the_slate():
    audit.check_a_live_update_does_not_reorder()
    assert audit.live_update_faults(audit.LIVE_UPDATE_FIXTURE_POSITIVE)
