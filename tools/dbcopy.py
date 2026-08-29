"""Copying facts out of the live database into a scratch one.

This exists because the same eight lines were written twice — once in
`backtest.py`, once in `verify.py` — and carried the same bug twice. Fixing the
copy in the backtest left the verifier broken, and the verifier is the thing
that is supposed to catch that. One definition now, imported by both.

It deliberately lives in `tools/` rather than in the package: it names
`market_lines_raw`, which is a table no module inside the LAW 1 prediction
closure may mention, and putting it in `gridiron/` would make the closure audit
flag the package for a helper only the offline tools use.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

#: Tables carrying facts about the world, copied so a scratch database does not
#: refetch what is already on disk. Predictions are pointedly not in this list.
#:
#: `games` FIRST: every sport table carries a foreign key into it, and copying a
#: child before its parent fails the constraint.
#:
#: `nba_injuries` is deliberately absent. It is a snapshot of what is true now,
#: not a history, so carrying today's report into a backtest of a past season
#: would tell the fitted model which players are hurt today.
FACT_TABLES = (
    "games",
    "game_conditions",
    "team_week_stats",
    "player_week_stats",
    "injuries",
    "snap_counts",
    "market_lines_raw",
    "http_cache",
    "mlb_probables",
    "mlb_pitcher_starts",
    "mlb_team_games",
    "nba_team_games",
    "nba_player_games",
)


SEPARATOR = chr(10) + "  "


class TransposedCopy(RuntimeError):
    """A copied table does not match its source column for column."""


def _fingerprint(conn: sqlite3.Connection, table: str, columns: list[str],
                 prefix: str = "") -> dict[str, tuple]:
    """A per-COLUMN summary, which is what makes a shift detectable.

    Row counts do not catch transposition — a positional copy moves every value
    one place along and the count is unchanged. Summarising each column
    separately does catch it, because two adjacent columns almost never hold the
    same values.
    """
    out: dict[str, tuple] = {}
    for col in columns:
        row = conn.execute(
            f"SELECT COUNT({col}) AS n, SUM(LENGTH(CAST({col} AS TEXT))) AS bytes"
            f" FROM {prefix}{table}"
        ).fetchone()
        out[col] = (row[0], row[1])
    return out


def verify_copy(conn: sqlite3.Connection, tables=FACT_TABLES) -> dict:
    """Assert the copy in `conn` matches `live.` column for column.

    This exists because avoiding a bug and DETECTING it are different things.
    The positional copy was avoided by writing column names — but nothing would
    have noticed if a later edit reverted that, except by luck: the only reason
    the original was caught at all was a CHECK constraint that happened to
    reject a season number where a sport name belonged. Luck is not a guard.

    Requires `live` to still be attached; `copy_facts` calls it before detaching.
    """
    mismatches: list[str] = []
    for table in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        live_cols = {r[1] for r in conn.execute(f"PRAGMA live.table_info({table})")}
        shared = [c for c in cols if c in live_cols]
        if not shared:
            continue
        here = _fingerprint(conn, table, shared)
        there = _fingerprint(conn, table, shared, prefix="live.")
        for col in shared:
            if here[col] != there[col]:
                mismatches.append(
                    f"{table}.{col}: copy has {here[col]}, source has {there[col]}"
                )
    if mismatches:
        raise TransposedCopy(
            "the copied tables do not match their source column for column, "
            "which is what a POSITIONAL copy produces: a column added by "
            "migration sits at the end of the live table and in its declared "
            "position in a fresh schema, so every value after it shifts one "
            "place along. Mismatches:" + SEPARATOR + SEPARATOR.join(mismatches[:8])
        )
    return {"tables": len(tables), "ok": True}


def copy_facts(conn: sqlite3.Connection, source: Path | str, tables=FACT_TABLES) -> dict:
    """Copy the fact tables from `source` into the already-open `conn`.

    BY COLUMN NAME, never `SELECT *`. A positional copy looks correct and is
    not: a column added by migration lands at the END of the live table but sits
    in its declared position in a freshly created schema, so every value after
    it shifts one place along. The only reason the first instance was caught was
    a CHECK constraint rejecting a season number where a sport name belonged —
    had `sport` been declared without a CHECK, the backtest would have run
    happily on transposed data.
    """
    conn.execute("ATTACH DATABASE ? AS live", (str(source),))
    copied: dict[str, int] = {}
    try:
        for table in tables:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            live_cols = {r[1] for r in conn.execute(f"PRAGMA live.table_info({table})")}
            shared = [c for c in cols if c in live_cols]
            if not shared:
                continue
            joined = ", ".join(shared)
            cur = conn.execute(
                f"INSERT INTO {table} ({joined}) SELECT {joined} FROM live.{table}"
            )
            copied[table] = cur.rowcount
        conn.commit()
        # Checked, not assumed. The copy is the step that silently corrupted a
        # backtest and a verifier; it does not get to be trusted.
        verify_copy(conn, tables)
    finally:
        conn.execute("DETACH DATABASE live")
    return copied
