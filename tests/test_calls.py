"""The operator's own calls: a third forecaster, on the same terms.

R1 says the operator calls a side and a tier, graded on the same buckets and
gates as the model. R2 says they see the model and the market first, so those
calls are INFORMED and are never merged with the blind record -- the same
separation `statistical` and `llm` already have, for the same reason.

LAW 5 is closer here than anywhere else in the project: the distance between
"how sure am I" and "how much would I put on it" is one column, and it is the
kind that arrives looking harmless.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from gridiron import audit, calls, config, db

PREDICTION_SQL = (
    "INSERT INTO predictions (sport, game_id, created_utc, market_type,"
    " subject, line_asked, model_prob, model_side, predictor,"
    " factor_set_version, factors_json, reasoning)"
    " VALUES ('cfb','cfb_c',?,'spread','AAA',-3.5,0.61,?,'statistical',"
    "'v1','{}','t')"
)


def _future(hours=6):
    return (dt.datetime.now(dt.timezone.utc)
            + dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _past(hours=6):
    return (dt.datetime.now(dt.timezone.utc)
            - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _question(conn, kickoff, status="scheduled", side="cover"):
    # A STARTED GAME CARRIES A SCORE. The schema says so (L1), and this helper
    # tripped over that constraint on its first run -- which is the constraint
    # doing its job: a game marked live with no score is a state the world
    # cannot be in.
    scores = (None, None) if status == "scheduled" else (7, 3)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, home_score, away_score)"
        " VALUES ('cfb_c','cfb',2026,20260905,'REG',?,'AAA','BBB',?,?,?)",
        (kickoff, status, scores[0], scores[1]))
    conn.execute(PREDICTION_SQL, (db.utcnow(), side))
    conn.commit()
    return conn.execute("SELECT id FROM predictions").fetchone()[0]


def test_a_tier_claims_the_midpoint_of_its_bucket():
    """Graded on the same buckets as the model, so the claim is the midpoint."""
    assert calls.TIER_CLAIM == {"LEAN": 0.55, "SOLID": 0.65, "STRONG": 0.75}
    for tier, claim in calls.TIER_CLAIM.items():
        assert 0.5 < claim < 0.8, f"{tier} claims outside the graded range"


def test_an_unknown_tier_is_refused_rather_than_guessed():
    with pytest.raises(calls.CallRefused) as caught:
        calls.claim_for("CERTAIN")
    assert "LEAN" in str(caught.value)


def test_the_claim_is_stored_on_the_row(conn):
    """A later change to the tier map must not rewrite what was claimed."""
    pid = _question(conn, _future())
    call = calls.record(conn, pid, "cover", "SOLID")
    assert call["claimed_prob"] == 0.65
    stored = conn.execute(
        "SELECT claimed_prob FROM operator_calls WHERE id = ?",
        (call["id"],)).fetchone()[0]
    assert stored == 0.65


def test_a_call_after_kickoff_is_refused(conn):
    """THE STRUCTURAL BOUND. A call made after the first pitch is not a
    forecast, it is a report."""
    pid = _question(conn, _past())
    with pytest.raises(calls.CallRefused) as caught:
        calls.record(conn, pid, "cover", "LEAN")
    assert "already started" in str(caught.value)
    assert conn.execute("SELECT COUNT(*) FROM operator_calls").fetchone()[0] == 0


def test_a_game_already_under_way_is_refused_even_before_its_kickoff(conn):
    """Status beats the clock: a game marked live has started, whatever the
    schedule says."""
    pid = _question(conn, _future(), status="in")
    with pytest.raises(calls.CallRefused):
        calls.record(conn, pid, "cover", "LEAN")


def test_a_revision_supersedes_and_the_old_row_stays(conn):
    """Append-only: revising writes a NEW row and the chain is kept."""
    pid = _question(conn, _future())
    calls.record(conn, pid, "cover", "LEAN")
    calls.record(conn, pid, "not_cover", "STRONG")
    chain = calls.chain(conn, pid)
    assert len(chain) == 2, "the revision replaced the original"
    assert calls.latest(conn, pid)["tier"] == "STRONG"
    assert chain[0]["tier"] == "LEAN"


def test_a_call_cannot_be_edited_or_deleted(conn):
    """LAW 3 does not care which forecaster made the claim."""
    pid = _question(conn, _future())
    call = calls.record(conn, pid, "cover", "LEAN")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE operator_calls SET tier='STRONG' WHERE id=?",
                     (call["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM operator_calls WHERE id=?", (call["id"],))


def test_a_call_resolves_once(conn):
    pid = _question(conn, _future())
    call = calls.record(conn, pid, "cover", "LEAN")
    conn.execute("UPDATE operator_calls SET resolved_utc=?, outcome=1"
                 " WHERE id=?", (db.utcnow(), call["id"]))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE operator_calls SET resolved_utc=?, outcome=0"
                     " WHERE id=?", (db.utcnow(), call["id"]))


def test_the_call_is_graded_on_its_own_side_not_the_models(conn):
    """THE DEFECT THIS PREVENTS would have been invisible.

    `predictions.outcome` says whether the MODEL's side was right. An operator
    who called the other side is right exactly when the model was wrong.
    Inheriting the model's outcome would score the operator on the model's
    opinion -- silently, and correctly in every row where they happened to
    agree.
    """
    pid = _question(conn, _future(), side="cover")
    calls.record(conn, pid, "not_cover", "SOLID")      # the opposite side
    settled = calls.resolve_for(conn, pid, model_outcome=1, model_side="cover")
    conn.commit()
    assert settled == 1
    outcome = conn.execute(
        "SELECT outcome FROM operator_calls WHERE prediction_id=?",
        (pid,)).fetchone()[0]
    assert outcome == 0, "the operator was scored on the model's side"


def test_agreeing_with_the_model_shares_its_outcome(conn):
    pid = _question(conn, _future(), side="cover")
    calls.record(conn, pid, "cover", "LEAN")
    calls.resolve_for(conn, pid, model_outcome=1, model_side="cover")
    conn.commit()
    assert conn.execute(
        "SELECT outcome FROM operator_calls").fetchone()[0] == 1


def test_only_the_latest_call_is_graded(conn):
    """A superseded call is history, not a claim."""
    pid = _question(conn, _future())
    calls.record(conn, pid, "cover", "LEAN")
    calls.record(conn, pid, "cover", "STRONG")
    calls.resolve_for(conn, pid, model_outcome=1, model_side="cover")
    conn.commit()
    resolved = conn.execute(
        "SELECT tier FROM operator_calls WHERE resolved_utc IS NOT NULL"
    ).fetchall()
    assert len(resolved) == 1 and resolved[0][0] == "STRONG"


def test_a_call_records_no_amount():
    """LAW 5, scanned rather than promised."""
    audit.check_a_call_is_not_a_stake()
    assert audit.call_stake_faults(audit.CALL_STAKE_FIXTURE_POSITIVE)


def test_the_operators_record_is_one_sport_at_a_time(conn):
    """LAW 6 applies to the operator exactly as it does to the model."""
    pid = _question(conn, _future())
    calls.record(conn, pid, "cover", "LEAN")
    summary = calls.record_summary(conn, "cfb")
    assert summary["sport"] == "cfb"
    assert summary["label"] == "you (informed)", (
        "the operator's numbers must say they were informed wherever they "
        "appear")
    with pytest.raises(config.CrossSportAggregation):
        calls.record_summary(conn, None)


def test_only_the_scanner_itself_is_exempt_from_the_staking_scan():
    """The exemption is one file wide, and must stay that way.

    `audit.py` holds the list of forbidden staking words, so its own
    identifiers contain every one of them -- the guard flagged itself the
    moment a call-stake guard was written. That is the same shape as two rules
    already in this project: `audit` sits outside the prediction closure
    because it names market columns, and the runtime missing-data check lives
    in `factors.compute` for the same reason.

    The danger is the generalisation, not the exemption: "the scanner may say
    the word" is one step from "the allowlist is where violations live".
    """
    assert audit.BETTING_SCAN_EXEMPT == ("audit.py",)
    assert audit.betting_surface() == [], (
        "a staking identifier reached the package outside the scanner itself")
