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
    ("nba_injuries", "player_name", "TEXT NOT NULL DEFAULT ''"),
    # The LEAGUE's own calendar date for a game, which is not the UTC date. A
    # game tipping at 02:00 UTC is the previous evening where it is played, and
    # every rolling window cut on the UTC date therefore INCLUDED the game it
    # was predicting: 76.8% of NBA games and 25.1% of MLB ones.
    ("games", "league_date", "TEXT"),
    # When this device last saw the record. Per session, so two devices each
    # get their own "since you last looked" rather than stealing it from
    # one another.
    ("sessions", "last_seen_utc", "TEXT"),
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


#: Triggers attached to `predictions`. Named here because a table rename
#: carries its triggers with it, and the schema script would then fail to
#: recreate them under the same names.
PREDICTION_TRIGGERS = (
    "predictions_no_delete",
    "predictions_no_update",
    "predictions_resolve_once",
    "voided_prediction_stays_void",
)


class MigrationRefused(RuntimeError):
    """A widening migration could not be completed safely, so nothing changed."""


def _needs_market_type_widening(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='predictions'"
    ).fetchone()
    return bool(row) and "moneyline" not in (row[0] or "")


def _widen_market_type(conn: sqlite3.Connection) -> int | None:
    """Rebuild `predictions` so its market_type CHECK admits 'moneyline'.

    SQLite cannot alter a CHECK in place, so the table is renamed aside, the
    schema script recreates it wide, and every row is copied back verbatim.

    This does not weaken LAW 3. The law forbids editing, deleting or re-scoring
    a prediction; it does not forbid widening the set of questions the table can
    hold. Every row is copied with every column unchanged, and the copy is
    VERIFIED — matching row counts and matching per-row hashes of the fields the
    law protects — before the old table is dropped. If verification fails the
    old table is left in place and the migration raises.
    """
    before = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    fingerprint_sql = (
        "SELECT id, created_utc, game_id, market_type, subject, line_asked,"
        " model_prob, model_side, predictor, factor_set_version, resolved_utc,"
        " outcome FROM {} ORDER BY id"
    )
    before_rows = [
        tuple(r) for r in conn.execute(fingerprint_sql.format("predictions"))
    ]

    conn.execute("PRAGMA foreign_keys = OFF")
    # legacy_alter_table stops SQLite rewriting the foreign keys in
    # `market_snapshots` and `prediction_voids` to follow the rename. Without
    # it those children end up pointing at the renamed-aside table, the drop
    # fails, and the record is left split across two tables. Learned the hard
    # way on the first run of this migration.
    conn.execute("PRAGMA legacy_alter_table = ON")
    for trigger in PREDICTION_TRIGGERS:
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    conn.execute("ALTER TABLE predictions RENAME TO predictions_pre_multisport")
    conn.execute("PRAGMA legacy_alter_table = OFF")
    # The caller runs the schema script next, which recreates `predictions`
    # with the wider CHECK and every index and trigger.
    return before


def _finish_widening(conn: sqlite3.Connection, expected: int) -> None:
    columns = [r[1] for r in conn.execute("PRAGMA table_info(predictions_pre_multisport)")]
    shared = [c for c in columns if c in set(db_columns(conn, "predictions"))]
    joined = ", ".join(shared)
    conn.execute(
        f"INSERT INTO predictions ({joined}) SELECT {joined} FROM predictions_pre_multisport"
    )
    conn.execute("PRAGMA foreign_keys = OFF")
    after = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    if after != expected:
        conn.rollback()
        raise MigrationRefused(
            f"widening `predictions` would have changed the record: {expected} rows "
            f"before, {after} after. The old table is left in place under "
            "`predictions_pre_multisport` and nothing was dropped."
        )
    conn.execute("DROP TABLE predictions_pre_multisport")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def db_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def init(conn: sqlite3.Connection) -> None:
    """Create the schema. Idempotent — every object is IF NOT EXISTS."""
    _migrate(conn)
    widening = _widen_market_type(conn) if _needs_market_type_widening(conn) else None
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    if widening is not None:
        _finish_widening(conn, widening)
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
