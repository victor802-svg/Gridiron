"""The record's fingerprint (ruling 4 on the audit, 2026-09-05)."""
from __future__ import annotations

import pytest

from gridiron import config, db, fingerprint, resolve

ROW = ("INSERT INTO predictions (created_utc, sport, game_id, market_type,"
       " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
       " factor_set_version, factors_json, reasoning)"
       " VALUES ('2026-09-01T00:00:00Z','nfl',?,'spread','HOM',-3.5,?,'cover',"
       " 'statistical','early','fs2','{}','test')")


def _game(conn, gid="fp_game", status="scheduled"):
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, home_score, away_score) VALUES (?,'nfl',2026,1,'REG',"
        " '2026-09-13T17:00:00Z','HOM','AWY',?,?,?)",
        (gid, status, 30 if status == "final" else None, 20 if status == "final" else None))


def test_a_row_through_the_door_matches_its_fingerprint(conn):
    _game(conn)
    pid = conn.execute(ROW, ("fp_game", 0.61)).lastrowid
    fingerprint.write(conn, pid)
    conn.commit()
    assert fingerprint.drift(conn) == []


def test_an_edit_behind_a_dropped_trigger_is_named(conn):
    _game(conn)
    pid = conn.execute(ROW, ("fp_game", 0.61)).lastrowid
    fingerprint.write(conn, pid)
    conn.commit()
    conn.execute("DROP TRIGGER predictions_no_update")
    conn.execute("UPDATE predictions SET model_prob = 0.91 WHERE id = ?", (pid,))
    conn.commit()
    faults = fingerprint.drift(conn)
    assert faults and faults[0].startswith(f"prediction {pid}:") and "changed" in faults[0]


def test_a_row_written_around_the_door_is_named(conn):
    _game(conn)
    pid = conn.execute(ROW, ("fp_game", 0.61)).lastrowid
    conn.commit()
    faults = fingerprint.drift(conn)
    assert faults == [f"prediction {pid} has no fingerprint: it was written around write_prediction"]


def test_a_resolution_is_recorded_once_and_a_rewrite_is_named(conn):
    _game(conn, status="final")
    pid = conn.execute(ROW, ("fp_game", 0.61)).lastrowid
    fingerprint.write(conn, pid)
    conn.commit()
    resolve.resolve_all(conn)
    fp = conn.execute("SELECT resolved_utc, outcome FROM prediction_fingerprints"
                      " WHERE prediction_id = ?", (pid,)).fetchone()
    assert fp["resolved_utc"] and fp["outcome"] in (0, 1)
    assert fingerprint.drift(conn) == []
    conn.execute("DROP TRIGGER predictions_resolve_once")
    conn.execute("DROP TRIGGER predictions_no_update")
    conn.execute("UPDATE predictions SET outcome = 1 - outcome WHERE id = ?", (pid,))
    conn.commit()
    faults = fingerprint.drift(conn)
    assert any("resolution was rewritten" in f for f in faults), faults


def test_the_fingerprint_table_keeps_its_own_law(conn):
    _game(conn)
    pid = conn.execute(ROW, ("fp_game", 0.61)).lastrowid
    fingerprint.write(conn, pid)
    conn.commit()
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM prediction_fingerprints WHERE prediction_id = ?", (pid,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE prediction_fingerprints SET substance_sha256 = 'x'"
                     " WHERE prediction_id = ?", (pid,))


def test_the_backfill_covers_only_the_baseline_rows(conn):
    _game(conn)
    first = conn.execute(ROW, ("fp_game", 0.61)).lastrowid
    second = conn.execute(ROW.replace("'HOM',-3.5", "'AWY',3.5"), ("fp_game", 0.58)).lastrowid
    conn.commit()
    assert fingerprint.backfill(conn, first) == 1
    assert fingerprint.backfill(conn, first) == 0, "idempotent"
    faults = fingerprint.drift(conn)
    assert faults == [f"prediction {second} has no fingerprint: it was written around write_prediction"]


def test_the_baseline_is_declared_and_dated():
    b = config.RECORD_BASELINE
    assert b["rows"] == 765 and b["taken_utc"].startswith("2026-09-05")
    assert len(b["audited_sha256"]) == 64 and len(b["substance_sha256"]) == 64
    assert b["audited_sha256"].startswith("b15a9f6f")


def test_a_moved_baseline_is_named(conn):
    _game(conn)
    pid = conn.execute(ROW, ("fp_game", 0.61)).lastrowid
    fingerprint.write(conn, pid)
    conn.commit()
    digest, n = fingerprint.record_hash(conn, pid)
    assert n == 1
    assert fingerprint.drift(conn, {"rows": 1, "substance_sha256": digest,
                                    "taken_utc": "2026-09-05T00:00:00Z"}) == []
    faults = fingerprint.drift(conn, {"rows": 1, "substance_sha256": "0" * 64,
                                      "taken_utc": "2026-09-05T00:00:00Z"})
    assert faults and "declared baseline" in faults[0]
