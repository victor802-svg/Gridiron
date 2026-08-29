"""SQLite access. One connection factory, one schema loader, no ORM."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config

SCHEMA_PATH = config.PACKAGE_ROOT / "schema.sql"


def utcnow() -> str:
    """The one timestamp format in this project: ISO-8601, UTC, Z-suffixed."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path is not None else config.DB_PATH
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


#: Columns added to existing tables after the first release. Additive only:
#: nothing here drops or rewrites a column, because a migration that could
#: rewrite `predictions` would be a way around LAW 3.
MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("predictions", "prop_type", "TEXT"),
    # S1: every record belongs to exactly one sport (LAW 6). Existing rows
    # backfill to 'nfl' via the column default, which is correct: they are all
    # NFL, and there was no other sport when they were written.
    ("games", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("predictions", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("factors", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("factor_scores", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
    ("model_fits", "sport", "TEXT NOT NULL DEFAULT 'nfl'"),
)


def _migrate(conn: sqlite3.Connection) -> list[str]:
    """Widen existing tables before the schema script runs.

    Order matters: the script creates indexes over columns these migrations
    add, so on an already-populated database the ALTERs must land first. On a
    fresh database the tables do not exist yet, `PRAGMA table_info` returns
    nothing, and each migration is skipped — the CREATE TABLE statements
    already carry the column.
    """
    applied = []
    for table, column, decl in MIGRATIONS:
        info = list(conn.execute(f"PRAGMA table_info({table})"))
        if not info:
            continue            # fresh database; the schema script defines it
        if column not in {r[1] for r in info}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            applied.append(f"{table}.{column}")
    return applied


def init(conn: sqlite3.Connection) -> None:
    """Create the schema. Idempotent — every object is IF NOT EXISTS."""
    _migrate(conn)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('kind', 'live')"
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return default if row is None else row["value"]


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?,?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def database_kind(conn: sqlite3.Connection) -> dict:
    """`live` = predictions made before kickoff. `backtest` = made afterwards
    over completed games, which proves the pipeline works and nothing else."""
    return {
        "kind": get_meta(conn, "kind", "live"),
        "note": get_meta(conn, "kind_note"),
    }


def open_db(path: Path | str | None = None) -> sqlite3.Connection:
    conn = connect(path)
    init(conn)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> object:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]
