"""A table rebuilt to a definition, verified, or not at all (schema ruling 2
of 2026-09-24, built 2026-09-25).

THE OPERATOR'S WORDS: "The 8 behavioural differences are fixed by a dated
migration that rebuilds each affected table: new table with the released
definition, copy every row, verify the row count and a checksum of every
column match exactly, recreate every trigger and index, then swap, all in one
transaction. Rehearse it on a scratch copy first and report counts and
checksums before and after. Take a verified backup of the live record before
running it. If any table fails verification, the transaction rolls back and
nothing is swapped."

THE ONE DOOR FOR IT. `rebuild_tables` rebuilds; `verified_backup` takes the
backup the ruling asks for first. Both name no table: the dated tool
(`tools/migrate_2026_09_25_behaviour.py`) names the eight, and the snapshot
table's entry comes from `gridiron.market.lines`, because LAW 1's closure
scan keeps a market table's name out of every module on a prediction path.
Whether a table is already at its definition is asked of `schema_diff`, the
door ruling 1's gate check uses, so "already migrated" and "the gate passes"
cannot disagree.

HOW A TABLE IS REBUILT, all inside one BEGIN IMMEDIATE:

  1. its row count and a SHA-256 of every column are taken, with its
     AUTOINCREMENT sequence (or the fact that it has none);
  2. it is renamed aside, with `legacy_alter_table` on and foreign keys off,
     so no other table's foreign key and no trigger on another table is
     rewritten to follow it -- measured 2026-09-25: either setting the other
     way repoints `ufc_bouts` and `fit_activations`, and with foreign keys on
     the drop of a parent with children fails;
  3. the new table is created from the definition's exact text, under its
     own name, so the record's stored text is byte for byte the release's;
  4. every row is copied by an explicit column list, with the rowid where
     the rowid is not itself a column (so implicit rowids survive);
  5. the count and every column's checksum are taken again, and any
     difference raises, naming the table and the column;
  6. the old table is dropped, the sequence restored exactly (a rebuild
     otherwise resets it to the highest id), and every index and trigger the
     definition gives the table is created from its text.

Then the whole database's `foreign_key_check` must equal what it was before,
each rebuilt table must pass `integrity_check`, and every schema object that
does not belong to a rebuilt table must be byte for byte what it was. Only
then COMMIT. Anything raised on the way is a ROLLBACK, and the schema is read
again to prove nothing was swapped.

`db.init` DOES NOT RUN THIS. See the note there.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import db, schema_diff

#: Where a table waits while its replacement is built. Never outlives the
#: transaction: it is dropped before COMMIT, or rolled back with it.
_ASIDE = "{}__before_rebuild"


class RebuildRefused(RuntimeError):
    """Nothing was swapped: the transaction rolled back, or never began."""

    #: The report as far as it got, when the refusal came from inside the
    #: transaction: every count and checksum taken before it failed.
    report = None


class TableFailedVerification(RebuildRefused):
    """A table's copy did not match its original, row count or checksum."""


class BackupFailedVerification(RuntimeError):
    """A backup did not match the database it was taken from."""


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@dataclass(frozen=True)
class Definition:
    """What a table should be: its CREATE text, and every index and trigger
    on it, each as (type, name, sql), exactly as sqlite_master stores them."""
    table: str
    create: str
    dependants: tuple[tuple[str, str, str], ...]
    automatic_indexes: int


def _definition_in(conn: sqlite3.Connection, table: str) -> Definition:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table'"
                       " AND name = ?", (table,)).fetchone()
    if row is None:
        raise RebuildRefused(f"{table}: the schema given does not define it")
    dependants = tuple(tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = ?"
        " AND type IN ('index', 'trigger') AND sql IS NOT NULL"
        " ORDER BY type, name", (table,)))
    automatic = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE tbl_name = ?"
        " AND type = 'index' AND sql IS NULL", (table,)).fetchone()[0]
    return Definition(table, row[0], dependants, automatic)


def released_definitions(tables, schema_sql: str | None = None) -> dict[str, Definition]:
    """Each table's definition as a schema script creates it: `schema.sql`
    unless another script is given, executed on an empty in-memory
    database, so the text is exactly what a fresh `db.init` stores."""
    conn = db.connect(":memory:")
    try:
        conn.executescript(schema_sql if schema_sql is not None
                           else db.SCHEMA_PATH.read_text(encoding="utf-8"))
        return {table: _definition_in(conn, table) for table in tables}
    finally:
        conn.close()


def differences_from(conn: sqlite3.Connection, definition: Definition) -> list[str]:
    """How a table as stored differs in behaviour from its definition, in
    words: the table, then each index and trigger the definition gives it
    and each one it has that the definition does not. Empty means already
    there -- quoting, whitespace, comments and column order apart."""
    here = _definition_in(conn, definition.table)
    found = [d.words("this database", "the definition")
             for d in schema_diff.table_differences(
                 here.create, definition.create, f"table {definition.table}")]
    mine = {name: (kind, sql) for kind, name, sql in here.dependants}
    theirs = {name: (kind, sql) for kind, name, sql in definition.dependants}
    for name in sorted(set(mine) | set(theirs)):
        if name not in theirs:
            found.append(f"{mine[name][0]} {name}: this database has it and "
                         f"the definition does not")
        elif name not in mine:
            found.append(f"{theirs[name][0]} {name}: the definition has it and "
                         f"this database does not")
        elif (schema_diff.tokens(mine[name][1])
              != schema_diff.tokens(theirs[name][1])):
            found.append(f"{mine[name][0]} {name}: defined differently")
    if here.automatic_indexes != definition.automatic_indexes:
        found.append(f"table {definition.table}: {here.automatic_indexes} "
                     f"automatic indexes against {definition.automatic_indexes}")
    return found


def _has_rowid(conn: sqlite3.Connection, table: str) -> bool:
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table'"
                       " AND name = ?", (table,)).fetchone()[0]
    return "without" not in schema_diff.table_shape(sql).options


def _rowid_is_a_column(conn: sqlite3.Connection, table: str) -> bool:
    """Is the rowid one of the table's own columns (an INTEGER PRIMARY KEY)?
    If not, it is copied explicitly, or the rebuild would renumber it."""
    key = [r for r in conn.execute(f"PRAGMA table_info({_q(table)})") if r[5] > 0]
    return len(key) == 1 and (key[0][2] or "").strip().upper() == "INTEGER"


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({_q(table)})")]


def column_checksums(conn: sqlite3.Connection, table: str) -> tuple[int, dict[str, str]]:
    """The table's row count, and a SHA-256 of every column by name.

    Each column's digest runs over its rows in rowid order, one line per
    row: the rowid, a unit separator, and SQLite's own `quote()` of the
    value -- which tells 1 from 1.0 from '1', a NULL from '', and a real
    from any other real to the last bit. The rowids get a digest of their
    own. A lost row, a changed value, a changed type or a renumbered rowid
    each change at least one digest. Keyed by name, so a new column order
    compares equal when every value is where it was.
    """
    names = _columns(conn, table)
    digests = {name: hashlib.sha256() for name in names}
    rowid = _has_rowid(conn, table)
    order = "rowid" if rowid else ", ".join(
        _q(r[1]) for r in sorted(
            (r for r in conn.execute(f"PRAGMA table_info({_q(table)})") if r[5]),
            key=lambda r: r[5]))
    if rowid:
        digests["<rowid>"] = hashlib.sha256()
    select = ", ".join(f"quote({_q(n)})" for n in names)
    lead = "rowid, " if rowid else "NULL, "
    count = 0
    for row in conn.execute(
            f"SELECT {lead}{select} FROM {_q(table)} ORDER BY {order}"):
        key = str(row[0]).encode()
        if rowid:
            digests["<rowid>"].update(key + b"\n")
        for name, value in zip(names, row[1:]):
            digests[name].update(key + b"\x1f"
                                 + value.encode("utf-8", "surrogatepass") + b"\n")
        count += 1
    return count, {name: h.hexdigest() for name, h in sorted(digests.items())}


def table_digest(checksums: dict[str, str]) -> str:
    """One short fingerprint of a table's column checksums, for a report."""
    joined = "".join(f"{k}={v};" for k, v in sorted(checksums.items()))
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def _sequence(conn: sqlite3.Connection, table: str):
    """The table's AUTOINCREMENT high-water mark, or None when it has none."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'"
                    " AND name = 'sqlite_sequence'").fetchone() is None:
        return None
    rows = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?",
                        (table,)).fetchall()
    if len(rows) > 1:
        raise RebuildRefused(f"{table}: sqlite_sequence holds {len(rows)} rows "
                             f"for it; nothing can say which one is true")
    return rows[0][0] if rows else None


def _master(conn: sqlite3.Connection) -> list[tuple]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name")]


def _copy_rows(conn: sqlite3.Connection, table: str, aside: str,
               columns: list[str], with_rowid: bool) -> None:
    """Every row of `aside` into `table`, by an explicit column list."""
    listed = ", ".join(_q(c) for c in columns)
    lead = "rowid, " if with_rowid else ""
    conn.execute(f"INSERT INTO {_q(table)} ({lead}{listed})"
                 f" SELECT {lead}{listed} FROM {_q(aside)}")


@dataclass
class TableReport:
    """What happened to one table."""
    table: str
    action: str
    differences: list[str] = field(default_factory=list)
    rows_before: int | None = None
    rows_after: int | None = None
    checksums_before: dict[str, str] = field(default_factory=dict)
    checksums_after: dict[str, str] = field(default_factory=dict)
    sequence_before: object = None
    sequence_after: object = None
    seconds: float = 0.0
    #: Whether the table's rebuild ran to its end, where the sequence after
    #: and the seconds are measured. A table that failed part way has no
    #: "after" for them, and a report must not print its None as one: the
    #: rehearsal's forced failure of 2026-09-25 printed "sequence 2355 ->
    #: None" for a high-water mark that was never measured and was kept.
    finished: bool = False


@dataclass
class RebuildReport:
    """What happened to all of them, and whether it was kept."""
    tables: list[TableReport] = field(default_factory=list)
    committed: bool = False
    lock_seconds: float | None = None
    failure: str | None = None
    foreign_key_check: int | None = None


def _rebuild_one(conn: sqlite3.Connection, definition: Definition,
                 entry: TableReport) -> None:
    table = definition.table
    aside = _ASIDE.format(table)
    started = time.perf_counter()
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?",
                    (aside,)).fetchone():
        raise RebuildRefused(f"{table}: {aside} already exists; a rebuild "
                             f"left it, and it is not this one's to drop")
    theirs = {name for _kind, name, _sql in definition.dependants}
    lost = sorted(name for _kind, name, _sql in _definition_in(conn, table).dependants
                  if name not in theirs)
    if lost:
        raise RebuildRefused(
            f"{table}: {', '.join(lost)} would be dropped with the old table "
            f"and the definition does not recreate them")
    columns = _columns(conn, table)
    with_rowid = _has_rowid(conn, table) and not _rowid_is_a_column(conn, table)
    entry.rows_before, entry.checksums_before = column_checksums(conn, table)
    entry.sequence_before = _sequence(conn, table)

    conn.execute(f"ALTER TABLE {_q(table)} RENAME TO {_q(aside)}")
    conn.execute(definition.create)
    if sorted(_columns(conn, table)) != sorted(columns):
        raise RebuildRefused(
            f"{table}: the definition's columns {sorted(_columns(conn, table))} "
            f"are not the stored table's {sorted(columns)}; a rebuild copies "
            f"every column and invents none")
    _copy_rows(conn, table, aside, columns, with_rowid)
    entry.rows_after, entry.checksums_after = column_checksums(conn, table)
    if entry.rows_after != entry.rows_before \
            or entry.checksums_after != entry.checksums_before:
        changed = sorted(k for k in set(entry.checksums_before)
                         | set(entry.checksums_after)
                         if entry.checksums_before.get(k)
                         != entry.checksums_after.get(k))
        raise TableFailedVerification(
            f"{table} FAILED VERIFICATION: {entry.rows_before} rows before, "
            f"{entry.rows_after} after; checksums differ in "
            f"{', '.join(changed) or 'no column'}")
    conn.execute(f"DROP TABLE {_q(aside)}")
    if _sequence(conn, table) is not None or entry.sequence_before is not None:
        conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
        if entry.sequence_before is not None:
            conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                         (table, entry.sequence_before))
    for _kind, _name, sql in definition.dependants:
        conn.execute(sql)

    now = _definition_in(conn, table)
    if now.create != definition.create:
        raise RebuildRefused(f"{table}: its stored text is not the definition's")
    if now.dependants != definition.dependants \
            or now.automatic_indexes != definition.automatic_indexes:
        raise RebuildRefused(f"{table}: its indexes and triggers are not the "
                             f"definition's")
    entry.sequence_after = _sequence(conn, table)
    if entry.sequence_after != entry.sequence_before:
        raise RebuildRefused(f"{table}: sequence {entry.sequence_before} "
                             f"became {entry.sequence_after}")
    entry.seconds = time.perf_counter() - started
    entry.finished = True


def rebuild_tables(conn: sqlite3.Connection, definitions: list[Definition],
                   *, announce=None) -> RebuildReport:
    """Rebuild every table that differs in behaviour from its definition, in
    the order given, in ONE transaction; skip, and say so, every table that
    is already there. Raises `RebuildRefused` -- the transaction rolled back
    and nothing swapped -- when any table fails verification.

    `conn` is a writable handle from `db.connect`, outside any transaction.
    `announce`, if given, is called with each line of the report as it is
    made, so a long run shows progress.
    """
    say = announce or (lambda line: None)
    report = RebuildReport()
    if conn.in_transaction:
        raise RebuildRefused("the handle is inside a transaction already; a "
                             "rebuild must be the whole of its own")
    plan: list[Definition] = []
    for definition in definitions:
        found = differences_from(conn, definition)
        entry = TableReport(definition.table,
                            "rebuild" if found else
                            "skipped: already at its definition", found)
        report.tables.append(entry)
        if found:
            plan.append(definition)
        say(f"{definition.table}: {entry.action}")
        for line in found:
            say(f"    {line}")
    if not plan:
        return report

    isolation = conn.isolation_level
    conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys = OFF")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        conn.isolation_level = isolation
        raise RebuildRefused("foreign keys are still on; renaming a parent "
                             "aside would repoint its children")
    conn.execute("PRAGMA legacy_alter_table = ON")
    before = _master(conn)
    entries = {e.table: e for e in report.tables}
    locked = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        locked = time.perf_counter()
        broken_before = conn.execute("PRAGMA foreign_key_check").fetchall()
        for definition in plan:
            _rebuild_one(conn, definition, entries[definition.table])
            say(f"{definition.table}: rebuilt and verified, "
                f"{entries[definition.table].rows_after} rows")
        broken_after = conn.execute("PRAGMA foreign_key_check").fetchall()
        if [tuple(r) for r in broken_after] != [tuple(r) for r in broken_before]:
            raise RebuildRefused(
                f"foreign_key_check changed: {len(broken_before)} rows before, "
                f"{len(broken_after)} after")
        report.foreign_key_check = len(broken_after)
        for definition in plan:
            verdict = [r[0] for r in conn.execute(
                f"PRAGMA integrity_check({_q(definition.table)})")]
            if verdict != ["ok"]:
                raise RebuildRefused(f"{definition.table}: integrity_check "
                                     f"says {verdict[:3]}")
        rebuilt = {d.table for d in plan}
        if [r for r in _master(conn) if r[2] not in rebuilt] \
                != [r for r in before if r[2] not in rebuilt]:
            raise RebuildRefused("a schema object on another table changed")
        conn.execute("COMMIT")
        report.committed = True
        for definition in plan:
            entries[definition.table].action = "rebuilt"
    except BaseException as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        report.failure = str(exc)
        if _master(conn) != before:
            raise RebuildRefused(
                f"ROLLED BACK, AND THE SCHEMA IS NOT WHAT IT WAS: {exc}") from exc
        for definition in plan:
            entries[definition.table].action = "rolled back; nothing swapped"
        if not isinstance(exc, Exception):
            raise
        refused = exc if isinstance(exc, RebuildRefused) else RebuildRefused(
            f"rolled back, nothing swapped: {exc}")
        # WHAT WAS MEASURED BEFORE IT FAILED goes with the refusal, so the
        # report still shows every count and checksum taken.
        refused.report = report
        if refused is exc:
            raise
        raise refused from exc
    finally:
        if locked is not None:
            report.lock_seconds = time.perf_counter() - locked
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.isolation_level = isolation
    return report


@dataclass
class BackupReport:
    """A backup, and the proof it matches its source."""
    source: str
    target: str
    integrity: list[str]
    tables: dict[str, tuple[int, str]]
    mismatched: list[str]
    seconds: float


def verified_backup(source: Path | str, target: Path | str, why: str) -> BackupReport:
    """Back `source` up into `target` through the backup door, then prove
    the copy: `PRAGMA integrity_check` on it, and every table's row count
    and column checksums equal on both sides.

    ONE INSTANT, BOTH SIDES. The source's checksums are read inside the same
    read transaction the backup copied, so a scheduled task writing to the
    record meanwhile cannot make a true copy look false. Raises
    `BackupFailedVerification`, naming each table, when anything differs;
    the target is left where it is, for the operator to look at.
    """
    source, target = Path(source), Path(target)
    if target.exists():
        raise BackupFailedVerification(
            f"{target} already exists; a verified backup is a new file, never "
            f"one written over")
    started = time.perf_counter()
    report = BackupReport(str(source), str(target), [], {}, [], 0.0)

    def prove(original: sqlite3.Connection) -> None:
        copy = db.read_only(target, "proving a backup matches its source")
        try:
            report.integrity = [r[0] for r in copy.execute("PRAGMA integrity_check")]
            tables = [r[0] for r in original.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
            copied = [r[0] for r in copy.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
            if copied != tables:
                report.mismatched.append(f"the tables differ: {tables} against {copied}")
            for table in tables:
                count, sums = column_checksums(original, table)
                report.tables[table] = (count, table_digest(sums))
                if table in copied and column_checksums(copy, table) != (count, sums):
                    report.mismatched.append(table)
        finally:
            copy.close()

    db.back_up(source, target, why, then=prove)
    report.seconds = time.perf_counter() - started
    if report.integrity != ["ok"] or report.mismatched:
        raise BackupFailedVerification(
            f"the backup at {target} does not match {source}: integrity_check "
            f"{report.integrity[:3]}; tables that differ: "
            f"{', '.join(report.mismatched) or 'none'}")
    return report
