"""The record's fingerprint: every protected field on every prediction, hashed
when the row is written, and checked in the gate.

RULING 4 ON THE AUDIT (2026-09-05). LAW 3 is enforced by triggers, and a
trigger can be dropped. The audit computed one hash over the whole record
(`b15a9f6f...`, 765 rows) and found nothing to compare it with; this is the
mechanism that keeps one. Two hashes, because the record legitimately changes
in exactly one way after a row is written:

* THE SUBSTANCE of a prediction -- the fields `predictions_no_update` freezes,
  plus the sport, the prop and the pass -- is hashed once, at the moment
  `write_prediction` inserts it, into `prediction_fingerprints`. It must never
  change. A row that has no fingerprint was written around the door.
* THE RESOLUTION -- `resolved_utc` and `outcome` -- is recorded on the
  fingerprint once, when `resolve_all` writes it, and must never change after.

The declared baseline in `config.RECORD_BASELINE` is the substance hash over
the rows that existed when the audit ran, and the gate recomputes it: those
rows cannot drift without the hash moving, and the per-row hashes say WHICH
row moved. A whole-record hash including resolutions goes stale with every
settled game, which is why the audit's own figure is recorded there as a
reading and not rechecked.

This module imports nothing from the market and nothing from `audit`: it sits
inside the prediction closure because `write_prediction` calls it.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .db import utcnow

#: Every field a prediction may not change after it is written: the set the
#: `predictions_no_update` trigger freezes, and the three that identify the
#: question beside them.
PROTECTED: tuple[str, ...] = (
    "created_utc", "sport", "game_id", "market_type", "prop_type", "subject",
    "line_asked", "model_prob", "model_side", "predictor", "pass_kind",
    "factor_set_version", "factors_json", "calibrated_prob",
    "correction_version", "reasoning",
)

_SELECT = "SELECT id, " + ", ".join(PROTECTED) + " FROM predictions"


def substance_hash(row: sqlite3.Row) -> str:
    """One row's protected fields, as a hex digest. Floats go through JSON,
    which round-trips them exactly; NULL stays NULL."""
    payload = json.dumps([row[field] for field in PROTECTED], separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(conn: sqlite3.Connection, prediction_id: int) -> str:
    """Fingerprint one freshly written prediction. The door `write_prediction`
    walks through; nothing else should call it."""
    row = conn.execute(_SELECT + " WHERE id = ?", (prediction_id,)).fetchone()
    if row is None:
        raise ValueError(f"prediction {prediction_id} does not exist")
    digest = substance_hash(row)
    conn.execute(
        "INSERT INTO prediction_fingerprints (prediction_id, substance_sha256,"
        " taken_utc) VALUES (?,?,?)", (prediction_id, digest, utcnow()))
    return digest


def record_resolution(conn: sqlite3.Connection, prediction_id: int) -> None:
    """Copy a prediction's resolution onto its fingerprint, once. The door
    `resolve_all` walks through."""
    conn.execute(
        "UPDATE prediction_fingerprints"
        "   SET resolved_utc = (SELECT resolved_utc FROM predictions WHERE id = ?),"
        "       outcome = (SELECT outcome FROM predictions WHERE id = ?)"
        " WHERE prediction_id = ? AND resolved_utc IS NULL",
        (prediction_id, prediction_id, prediction_id))


def backfill(conn: sqlite3.Connection, up_to_id: int) -> int:
    """Fingerprint the rows that existed before this mechanism did.

    Only rows up to the declared baseline's last id: a later row with no
    fingerprint is a row written around `write_prediction`, and backfilling
    it would hide exactly the thing the gate is for. Idempotent.
    """
    if not _table_exists(conn):
        return 0
    rows = conn.execute(
        _SELECT + " WHERE id <= ? AND id NOT IN"
        " (SELECT prediction_id FROM prediction_fingerprints) ORDER BY id",
        (up_to_id,)).fetchall()
    for row in rows:
        conn.execute(
            "INSERT INTO prediction_fingerprints (prediction_id, substance_sha256,"
            " taken_utc, resolved_utc, outcome)"
            " SELECT id, ?, ?, resolved_utc, outcome FROM predictions WHERE id = ?",
            (substance_hash(row), utcnow(), row["id"]))
    if rows:
        conn.commit()
    return len(rows)


def record_hash(conn: sqlite3.Connection, up_to_id: int | None = None) -> tuple[str, int]:
    """(hash over every row's substance in id order, rows). What the baseline
    declares and what the gate recomputes."""
    sql = _SELECT + (" WHERE id <= ?" if up_to_id is not None else "") + " ORDER BY id"
    rows = conn.execute(sql, (up_to_id,) if up_to_id is not None else ()).fetchall()
    digest = hashlib.sha256()
    for row in rows:
        digest.update(substance_hash(row).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), len(rows)


def drift(conn: sqlite3.Connection, baseline: dict | None = None) -> list[str]:
    """Every way the record differs from its fingerprints, each by name."""
    faults: list[str] = []
    if not _table_exists(conn):
        return ["prediction_fingerprints does not exist; nothing has been fingerprinted"]
    stored = {
        r["prediction_id"]: r for r in conn.execute(
            "SELECT prediction_id, substance_sha256, resolved_utc, outcome"
            "  FROM prediction_fingerprints")
    }
    live = conn.execute(_SELECT + ", resolved_utc, outcome FROM predictions"
                        if False else
                        "SELECT id, " + ", ".join(PROTECTED) + ", resolved_utc, outcome"
                        " FROM predictions ORDER BY id").fetchall()
    for row in live:
        fp = stored.get(row["id"])
        if fp is None:
            faults.append(f"prediction {row['id']} has no fingerprint: it was "
                          f"written around write_prediction")
            continue
        if substance_hash(row) != fp["substance_sha256"]:
            faults.append(
                f"prediction {row['id']}: a protected field changed since it was "
                f"written (one of {', '.join(PROTECTED)})")
        if fp["resolved_utc"] is not None and (
                row["resolved_utc"] != fp["resolved_utc"] or row["outcome"] != fp["outcome"]):
            faults.append(f"prediction {row['id']}: its resolution was rewritten "
                          f"(recorded {fp['outcome']} at {fp['resolved_utc']}, "
                          f"now {row['outcome']} at {row['resolved_utc']})")
        if fp["resolved_utc"] is None and row["resolved_utc"] is not None:
            faults.append(f"prediction {row['id']} was resolved around resolve_all: "
                          f"the fingerprint never saw it")
    orphans = set(stored) - {r["id"] for r in live}
    for pid in sorted(orphans):
        faults.append(f"prediction {pid} has a fingerprint and no row: it was deleted")
    if baseline:
        digest, n = record_hash(conn, baseline["rows"])
        if n != baseline["rows"]:
            faults.append(f"the baseline covers {baseline['rows']} rows and the "
                          f"record holds {n} of them")
        elif digest != baseline["substance_sha256"]:
            faults.append(
                f"the substance hash over the first {n} rows is {digest[:16]}..., "
                f"the declared baseline of {baseline['taken_utc'][:10]} is "
                f"{baseline['substance_sha256'][:16]}...")
    return faults


def _table_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table'"
        " AND name='prediction_fingerprints'").fetchone() is not None
