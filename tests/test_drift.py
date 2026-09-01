"""Line drift: two looks at the same line, and the gate over what they say.

The question is whether a disagreement is the model seeing something early or
the model being wrong. Two snapshots can tell those apart; one cannot. Most of
what can go wrong here is the two snapshots not really being two.
"""

from __future__ import annotations

import pytest

from gridiron import drift
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


def _pair(conn, *, claim, opened, near, subject):
    game = conn.execute("SELECT id FROM games LIMIT 1").fetchone()["id"]
    cur = conn.execute(
        "INSERT INTO predictions (sport, created_utc, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) VALUES"
        " ('nfl','2025-12-01T00:00:00Z',?, 'moneyline', ?, ?, 'win',"
        " 'statistical','fs2','{}','because')",
        (game, subject, claim),
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


def test_a_small_disagreement_is_not_a_disagreement(league):
    """Below the threshold the two are saying the same thing.

    Counting those would fill the sample with games where the movement is noise
    about nothing, and the fraction would drift toward 50% for arithmetic
    reasons rather than for anything about the market.
    """
    _pair(league, claim=0.52, opened=0.50, near=0.60, subject="A")
    assert drift.pairs(league, sport="nfl", market_type="moneyline") == []


def test_movement_toward_the_model_is_signed_from_the_two_numbers(league):
    """`toward` must not be read off which side the model took.

    The model can disagree in either direction, and a sign taken from the side
    rather than from the numbers is the wrong-side defect in a new costume.
    """
    # Model above the market, line rises: toward.
    _pair(league, claim=0.70, opened=0.50, near=0.58, subject="B")
    # Model BELOW the market, line falls: also toward.
    _pair(league, claim=0.30, opened=0.50, near=0.42, subject="C")
    # Model below the market, line rises: away.
    _pair(league, claim=0.30, opened=0.50, near=0.61, subject="D")

    found = {p["prediction_id"]: p for p in
             drift.pairs(league, sport="nfl", market_type="moneyline")}
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
        _pair(league, claim=0.70, opened=0.50, near=0.60, subject=f"E{i}")
    report = drift.report(league, sport="nfl", market_type="moneyline")
    assert report["n"] == 5
    assert "toward_fraction" not in report
    assert "moved_toward" not in report
    assert str(drift.MIN_PAIRS) in report["line"]


def test_the_sentence_appears_only_once_the_gate_is_cleared(league):
    for i in range(drift.MIN_PAIRS):
        _pair(league, claim=0.70, opened=0.50, near=0.60, subject=f"F{i}")
    report = drift.report(league, sport="nfl", market_type="moneyline")
    assert report["n"] >= drift.MIN_PAIRS
    assert report["toward_fraction"] == 1.0
    assert "moved toward it 100% of the time" in report["line"]
    assert str(report["n"]) in report["line"], "the sentence must carry its N"


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
    assert drift.pairs(league, sport="nfl", market_type="moneyline") == []


def test_only_one_snapshot_of_each_kind_per_prediction(league):
    """A second 'open_at_predict' would overwrite what the first one means."""
    import sqlite3

    pid = _pair(league, claim=0.70, opened=0.50, near=0.60, subject="G")
    with pytest.raises(sqlite3.IntegrityError):
        league.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " line, implied_prob, kind) VALUES (?,?,?,?,?,?)",
            (pid, "2025-12-01T02:00:00Z", "test", None, 0.55, "open_at_predict"),
        )
