"""G1: the schema itself carries the laws."""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import db
from gridiron.data import reference


# --- LAW 1: the games table has no line on it ------------------------------

def test_games_table_has_no_market_columns(conn):
    cols = set(db.table_columns(conn, "games")) | set(
        db.table_columns(conn, "game_conditions")
    )
    forbidden = [c for c in cols if any(w in c for w in ("spread", "total", "moneyline", "odds"))]
    assert forbidden == [], (
        f"LAW 1 violation: market columns {forbidden} are reachable from the tables "
        "the prediction path reads"
    )


def test_market_columns_live_only_in_quarantine(conn):
    assert "spread_line" in db.table_columns(conn, "market_lines_raw")
    assert "line" in db.table_columns(conn, "market_snapshots")


# --- LAW 3: append-only ----------------------------------------------------

def test_prediction_cannot_be_deleted(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute("DELETE FROM predictions WHERE id = ?", (a_prediction,))


def test_prediction_probability_is_immutable(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute(
            "UPDATE predictions SET model_prob = 0.99 WHERE id = ?", (a_prediction,)
        )


def test_prediction_reasoning_is_immutable(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute(
            "UPDATE predictions SET reasoning = 'rewritten' WHERE id = ?", (a_prediction,)
        )


def test_resolution_is_the_one_permitted_write(a_prediction, league):
    league.execute(
        "UPDATE predictions SET resolved_utc = ?, outcome = 1 WHERE id = ?",
        (db.utcnow(), a_prediction),
    )
    league.commit()
    row = league.execute(
        "SELECT outcome, model_prob FROM predictions WHERE id = ?", (a_prediction,)
    ).fetchone()
    assert row["outcome"] == 1
    assert row["model_prob"] == 0.58, "resolution must not touch the probability"


def test_a_prediction_resolves_only_once(a_prediction, league):
    league.execute(
        "UPDATE predictions SET resolved_utc = ?, outcome = 1 WHERE id = ?",
        (db.utcnow(), a_prediction),
    )
    league.commit()
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute(
            "UPDATE predictions SET resolved_utc = ?, outcome = 0 WHERE id = ?",
            (db.utcnow(), a_prediction),
        )


# --- LAW 1: ordering -------------------------------------------------------

def test_snapshot_without_a_prediction_is_rejected(league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 1"):
        league.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line)"
            " VALUES (?,?,?,?)",
            (9999, db.utcnow(), "test", -3.5),
        )


def test_snapshot_timestamped_before_its_prediction_is_rejected(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 1"):
        league.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line)"
            " VALUES (?,?,?,?)",
            (a_prediction, "1999-01-01T00:00:00Z", "test", -3.5),
        )


# --- LAW 2: a factor needs a reason ----------------------------------------

def test_factor_without_rationale_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES (?,?,?)",
            ("mystery", "2026-08-28T00:00:00Z", None),
        )


def test_factor_with_a_token_rationale_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES (?,?,?)",
            ("mystery", "2026-08-28T00:00:00Z", "because"),
        )


def test_factor_without_a_date_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES (?,?,?)",
            ("mystery", "whenever", "Rest matters because tired bodies play worse."),
        )


def test_factor_cannot_be_deleted(conn):
    conn.execute(
        "INSERT INTO factors (name, added_utc, rationale) VALUES (?,?,?)",
        ("rest_days", "2026-08-28T00:00:00Z", "Short weeks compress recovery and preparation."),
    )
    with pytest.raises(sqlite3.IntegrityError, match="LAW 2"):
        conn.execute("DELETE FROM factors WHERE name = 'rest_days'")


# --- probabilities are probabilities ---------------------------------------

@pytest.mark.parametrize("bad", [0.0, 1.0, -0.2, 1.5])
def test_impossible_probabilities_are_rejected(league, bad):
    game_id = league.execute("SELECT id FROM games LIMIT 1").fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        league.execute(
            "INSERT INTO predictions (created_utc, game_id, market_type, subject, line_asked,"
            " model_prob, model_side, predictor, factor_set_version, factors_json, reasoning)"
            " VALUES (?,?,'spread','KC',-3.5,?,'cover','statistical','fs1','{}','x')",
            (db.utcnow(), game_id, bad),
        )


# --- reference data --------------------------------------------------------

def test_kickoff_converts_eastern_to_utc():
    # 13:00 ET on a September Sunday is EDT, UTC-4.
    assert reference.kickoff_to_utc("2026-09-13", "13:00") == "2026-09-13T17:00:00Z"
    # February is EST, UTC-5.
    assert reference.kickoff_to_utc("2026-02-08", "18:30") == "2026-02-08T23:30:00Z"


def test_kickoff_without_a_time_is_none_not_a_guess():
    assert reference.kickoff_to_utc("2026-09-13", "") is None
    assert reference.kickoff_to_utc("2026-09-13", None) is None


def test_travel_distance_is_sane():
    sea = reference.site_for("SEA")
    mia = reference.site_for("MIA")
    d = reference.haversine_miles(sea[0], sea[1], mia[0], mia[1])
    assert 2600 < d < 2800, d
    assert reference.haversine_miles(*sea[:2], *sea[:2]) == 0.0


def test_every_current_club_has_a_site():
    for team in ("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV "
                 "MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS").split():
        assert reference.site_for(team) is not None, team
