"""Persist the declared registry into the `factors` table.

The table is the durable record; the registry is the declaration. Sync is
insert-mostly and deliberately refuses to move a factor's activation date,
because "when did this start counting" is the whole basis of Law 2 scoring and
a factor that could quietly change its own start date could be backfitted.
"""

from __future__ import annotations

import sqlite3

from ..db import utcnow
from . import registry


class RegistryConflict(RuntimeError):
    """The code and the database disagree about a factor's history."""


def sync_registry(conn: sqlite3.Connection) -> dict[str, int]:
    added = updated = unchanged = 0
    with conn:
        for f in registry.REGISTRY.values():
            row = conn.execute(
                "SELECT * FROM factors WHERE name = ?", (f.name,)
            ).fetchone()

            if row is None:
                conn.execute(
                    "INSERT INTO factors (name, added_utc, rationale, active,"
                    " deactivated_utc, note) VALUES (?,?,?,?,?,?)",
                    (
                        f.name,
                        f.added_utc,
                        f.rationale,
                        1 if f.active else 0,
                        f.deactivated_utc,
                        f.note,
                    ),
                )
                added += 1
                continue

            if row["added_utc"] != f.added_utc:
                raise RegistryConflict(
                    f"factor {f.name!r} is recorded as added {row['added_utc']} but the "
                    f"registry now declares {f.added_utc}. A factor's activation date is "
                    "the basis of its score and cannot be moved; declare a new factor "
                    "instead (LAW 2)."
                )

            changed = (
                row["active"] != (1 if f.active else 0)
                or (row["rationale"] or "") != f.rationale
                or (row["note"] or None) != f.note
                or (row["deactivated_utc"] or None) != f.deactivated_utc
            )
            if changed:
                conn.execute(
                    "UPDATE factors SET rationale = ?, active = ?, deactivated_utc = ?,"
                    " note = ? WHERE name = ?",
                    (
                        f.rationale,
                        1 if f.active else 0,
                        f.deactivated_utc,
                        f.note,
                        f.name,
                    ),
                )
                updated += 1
            else:
                unchanged += 1

    return {"added": added, "updated": updated, "unchanged": unchanged}


def stored_factors(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM factors ORDER BY active DESC, name").fetchall()
    out = []
    for r in rows:
        entry = dict(r)
        declared = registry.REGISTRY.get(r["name"])
        entry["applies_to"] = list(declared.applies_to) if declared else []
        entry["declared_in_code"] = declared is not None
        out.append(entry)
    return out


def record_factor_score(
    conn: sqlite3.Connection,
    factor: str,
    window: str,
    n: int,
    brier: float | None,
    log_loss: float | None,
    note: str | None = None,
) -> int:
    """LAW 4: `n` is a required positional argument, not an optional extra."""
    if n is None:
        raise ValueError("LAW 4: a factor score cannot be recorded without its sample size")
    cur = conn.execute(
        "INSERT INTO factor_scores (computed_utc, factor, window, n, brier, log_loss, note)"
        " VALUES (?,?,?,?,?,?,?)",
        (utcnow(), factor, window, int(n), brier, log_loss, note),
    )
    conn.commit()
    return cur.lastrowid
