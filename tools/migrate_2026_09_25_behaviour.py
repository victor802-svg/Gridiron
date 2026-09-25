"""The dated migration of schema ruling 2 (2026-09-24), built 2026-09-25.

    # a scratch database: migrate it in place
    python tools/migrate_2026_09_25_behaviour.py --database PATH

    # the rehearsal: a verified backup of PATH (the live record allowed, read
    # through the read-only door) into a scratch file, then migrate THAT
    python tools/migrate_2026_09_25_behaviour.py --database PATH --rehearse
        [--scratch FILE]

    # the live record: a verified backup to a named file first, then migrate
    python tools/migrate_2026_09_25_behaviour.py --database var/gridiron.db
        --live --backup FILE

THE OPERATOR'S WORDS: "The 8 behavioural differences are fixed by a dated
migration that rebuilds each affected table: new table with the released
definition, copy every row, verify the row count and a checksum of every
column match exactly, recreate every trigger and index, then swap, all in one
transaction. Rehearse it on a scratch copy first and report counts and
checksums before and after. Take a verified backup of the live record before
running it. If any table fails verification, the transaction rolls back and
nothing is swapped."

WHAT IT CHANGES. Eight tables, each to the definition this tree's
`schema.sql` gives it -- the release's, once this tree is merged -- and
nothing else: seven CHECKs the live record's copies lack, because each column
reached the record by ALTER, and one DEFAULT it has that the release does not
(`audit.SCHEMA_DIFFERENCES_REGISTERED` holds all eight, measured). Every row
is copied, and every stored row already satisfies every released constraint
(measured 2026-09-25); a row that did not would stop the copy, and the
transaction would roll back.

HOW (`gridiron.rebuild`, the one door): all eight in ONE transaction; per
table a row count and a SHA-256 of every column before and after, compared
exactly; every index and trigger recreated from the released text; the
AUTOINCREMENT sequence carried; foreign keys off and `legacy_alter_table` on,
so no other table is repointed; `foreign_key_check`, `integrity_check` and
the rest of the schema byte for byte checked before COMMIT. Any failure
ROLLS BACK and nothing is swapped.

IDEMPOTENT. A table already at its released definition -- quoting,
whitespace, comments and column order apart, as ruling 1 compares -- is
skipped, and the report says so. Run twice, the second run changes nothing.

REFUSED ON THE LIVE RECORD unless `--live` is given AND a verified backup
was made in the same run: the sqlite backup API into the named `--backup`
file (never over an existing one), then `PRAGMA integrity_check` on the
backup and every table's row count and column checksums compared with the
record at the instant of the copy. If the backup does not verify, nothing is
migrated.

NOT RUN BY `db.init`, and not by the gate. The operator runs it, from the
main checkout, after the release that carries it: at a quiet hour (10:15Z
measured quietest on 2026-09-25; never at :05 or :35, never during a gate,
never within half an hour of a logon), after a `--rehearse` on a fresh copy.
Rehearsed 2026-09-25 on a verified copy of the record: every table's rows and
column checksums equal before and after, and the write lock held 3.18 s,
against the scheduler's 30-second busy timeout (FOLLOWUPS). The commit after
it runs empties `audit.SCHEMA_DIFFERENCES_REGISTERED`, which the gate then
requires.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import config, db, rebuild  # noqa: E402
from gridiron.market import lines  # noqa: E402

#: THE MIGRATION MAP, in the order the tables are rebuilt: (table, what the
#: rebuild gives it, the commit that introduced the released definition).
#: The snapshot table's entry comes from the market package, the only one
#: that may name it in code (LAW 1's closure scan).
MIGRATION = (
    ("factors", "CHECK (sport IN the five declared sports) on sport",
     "9c0bc64 (five sports from b09e1c2)"),
    ("factor_scores", "CHECK (sport IN the five declared sports) on sport",
     "9c0bc64 (five sports from b09e1c2)"),
    ("model_fits", "CHECK (sport IN the five declared sports) on sport",
     "9c0bc64 (five sports from b09e1c2)"),
    lines.SNAPSHOT_REBUILD,
    ("mlb_lineups", "CHECK (source IN ('live', 'backfill')) on source",
     "8002a38"),
    ("prediction_ranks", "CHECK (on_shortlist IN (0, 1)) on on_shortlist",
     "63d998c"),
    ("ufc_events", "CHECK (event_tier IS NULL OR event_tier IN ('numbered', "
                   "'fight_night', 'contender')) on event_tier",
     "c78af51 (and bdfaddc)"),
    ("nba_injuries", "no DEFAULT on player_name, as released", "719004d"),
)


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED: " + why)
        super().__init__(2)


def _is_the_record(path: Path) -> bool:
    """Is `path` the operator's own record? Compared resolved, so a junction
    or a relative spelling of the same file is the same file -- and with no
    exception for the temp directory, which is the rule for scratch files,
    not for this question."""
    return path.resolve() == Path(config.DB_PATH).resolve()


def _print_backup(report: rebuild.BackupReport) -> None:
    rows = sum(count for count, _digest in report.tables.values())
    print(f"VERIFIED BACKUP: {report.source} -> {report.target}")
    print(f"  integrity_check on the backup: {', '.join(report.integrity)}")
    print(f"  {len(report.tables)} tables, {rows:,} rows: every row count and "
          f"every column checksum equal on both sides, at the instant copied")
    print(f"  {report.seconds:.1f}s")


def _print_tables(report: rebuild.RebuildReport) -> None:
    whats = {table: (what, commit) for table, what, commit in MIGRATION}
    for entry in report.tables:
        what, commit = whats.get(entry.table, ("", ""))
        print()
        print(f"{entry.table} -- {what}; released in {commit}")
        print(f"  {entry.action}")
        for line in entry.differences:
            print(f"    {line}")
        if entry.rows_before is None:
            continue
        print(f"  rows {entry.rows_before:,} -> "
              + (f"{entry.rows_after:,}" if entry.rows_after is not None else "--"))
        print(f"  table checksum {rebuild.table_digest(entry.checksums_before)}"
              f" -> {rebuild.table_digest(entry.checksums_after) if entry.checksums_after else '--'}")
        for column in sorted(entry.checksums_before):
            after = entry.checksums_after.get(column, "")
            same = "equal" if after == entry.checksums_before[column] else "DIFFERS"
            print(f"    {column:24s} {entry.checksums_before[column][:16]}"
                  f" -> {after[:16] or '--':16s}  {same}")
        # ONLY A MEASURED "AFTER" IS PRINTED (2026-09-25). A table that failed
        # part way never had its sequence carried or measured; its None used
        # to print as "sequence 2355 -> None", which reads as a high-water
        # mark lost -- in a rollback that had kept it.
        if entry.finished:
            print(f"  sequence {entry.sequence_before} -> {entry.sequence_after}"
                  f"; {entry.seconds:.2f}s")
        else:
            print(f"  sequence {entry.sequence_before} -> not reached: this "
                  f"table failed before its sequence was carried")


def _report_json(path: Path, backup, report: rebuild.RebuildReport) -> None:
    payload = {
        "backup": None if backup is None else backup.__dict__,
        "committed": report.committed,
        "lock_seconds": report.lock_seconds,
        "failure": report.failure,
        "foreign_key_check_rows": report.foreign_key_check,
        "tables": [entry.__dict__ for entry in report.tables],
    }
    path.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Schema ruling 2: rebuild the eight tables to their "
                    "released definitions, verified, in one transaction")
    parser.add_argument("--database", required=True,
                        help="the database to migrate (or, with --rehearse, "
                             "to copy and migrate the copy of)")
    parser.add_argument("--live", action="store_true",
                        help="the database is the operator's record, and "
                             "this is the run that changes it")
    parser.add_argument("--backup", help="with --live: the new file the "
                                         "verified backup is written to")
    parser.add_argument("--rehearse", action="store_true",
                        help="migrate a verified scratch copy, never the "
                             "database named")
    parser.add_argument("--scratch", help="with --rehearse: where the copy goes "
                                          "(default: a new temp directory)")
    parser.add_argument("--report", help="also write the report as JSON here")
    args = parser.parse_args(argv)

    # --report IS WRITTEN ON EVERY EXIT THAT REACHES A VERDICT (2026-09-25).
    # The rehearsal of that day ran this tool a second time with --report on
    # the migrated copy and got no file: the nothing-to-do exit and the
    # unverified-copy exits returned before the report was written. A run
    # asked for its record must leave one; an absent file reads as a run
    # that never happened.
    def write_report(backup, report: rebuild.RebuildReport) -> None:
        if args.report:
            _report_json(Path(args.report), backup, report)
            print(f"report written to {args.report}")

    database = Path(args.database)
    live = _is_the_record(database)
    if not database.exists():
        raise Refused(f"there is no database at {database}")
    if args.live and args.rehearse:
        raise Refused("--live and --rehearse ask for opposite things")
    if args.live and not live:
        raise Refused(f"--live names the operator's record, {config.DB_PATH}, "
                      f"and {database} is not it")
    if live and not args.rehearse and not args.live:
        raise Refused(
            f"{database} is the operator's record. It is migrated only with "
            f"--live and a verified --backup made in the same run; to see "
            f"what would happen, --rehearse migrates a verified copy instead")
    if args.live and not args.backup:
        raise Refused("--live needs --backup FILE: the ruling requires a "
                      "verified backup of the record before it is changed")
    if args.live and Path(args.backup).exists():
        raise Refused(f"{args.backup} already exists; the verified backup is "
                      f"a new file, never one written over")

    definitions = rebuild.released_definitions([t for t, _w, _c in MIGRATION])
    print(f"schema ruling 2 -- the released definitions are {db.SCHEMA_PATH}")
    # WHAT IS THERE TO DO, asked read-only before anything is copied: a
    # record already at the release needs no gigabyte backup to say so.
    reader = db.read_only(database, "what schema ruling 2's migration would "
                                    "change, asked before anything is copied")
    try:
        todo = [t for t, _w, _c in MIGRATION
                if rebuild.differences_from(reader, definitions[t])]
    finally:
        reader.close()
    if not todo:
        for table, _what, _commit in MIGRATION:
            print(f"  {table}: skipped: already at its definition")
        print(f"NOTHING TO DO: every table is already at its released "
              f"definition. {database} was not copied and not changed.")
        write_report(None, rebuild.RebuildReport(tables=[
            rebuild.TableReport(table, "skipped: already at its definition")
            for table, _what, _commit in MIGRATION]))
        return 0
    print(f"to rebuild: {', '.join(todo)}")
    backup = None
    target = database
    if args.rehearse:
        scratch = Path(args.scratch) if args.scratch else (
            Path(tempfile.mkdtemp(prefix="gridiron-ruling-2-")) / "rehearsal.db")
        print(f"REHEARSAL: {database} is copied, verified, and the COPY is "
              f"migrated; {database} is only read")
        try:
            backup = rebuild.verified_backup(
                database, scratch,
                "the rehearsal of schema ruling 2's migration, on a verified "
                "copy")
        except rebuild.BackupFailedVerification as exc:
            print(f"THE COPY DID NOT VERIFY; nothing was migrated. {exc}")
            write_report(None, rebuild.RebuildReport(
                failure=f"the copy did not verify; nothing was migrated: {exc}"))
            return 1
        _print_backup(backup)
        target = scratch
    elif args.live:
        print(f"THE LIVE RECORD: {database}. A verified backup first.")
        try:
            backup = rebuild.verified_backup(
                database, Path(args.backup),
                "the verified backup schema ruling 2 requires before the "
                "migration changes the live record")
        except rebuild.BackupFailedVerification as exc:
            print(f"THE BACKUP DID NOT VERIFY; nothing was migrated. {exc}")
            write_report(None, rebuild.RebuildReport(
                failure=f"the backup did not verify; nothing was migrated: {exc}"))
            return 1
        _print_backup(backup)

    conn = db.connect(target)
    started = time.perf_counter()
    try:
        report = rebuild.rebuild_tables(
            conn, [definitions[t] for t, _w, _c in MIGRATION],
            announce=lambda line: print("  " + line))
    except rebuild.RebuildRefused as exc:
        # "NOTHING WAS SWAPPED" ONLY WHERE IT WAS PROVED (2026-09-25). The
        # library attaches its report to a refusal exactly when it rolled
        # back and then read the schema again and found it as it was. A
        # refusal without one either came before any transaction or rolled
        # back into a schema that is NOT as it was -- another connection
        # changed it between the plan and the lock -- and the tool used to
        # print "ROLLED BACK. NOTHING WAS SWAPPED" over that too, contradicting
        # the refusal's own words. Found by the rehearsal's review.
        proved = getattr(exc, "report", None)
        if proved is not None:
            _print_tables(proved)
        print()
        if proved is not None:
            print(f"ROLLED BACK. NOTHING WAS SWAPPED: {exc}")
        else:
            print(f"NOT COMMITTED: {exc}")
        write_report(backup, proved if proved is not None
                     else rebuild.RebuildReport(failure=str(exc)))
        return 1
    finally:
        conn.close()
    _print_tables(report)
    print()
    if not any(e.action == "rebuilt" for e in report.tables):
        print(f"NOTHING TO DO: every table is already at its released "
              f"definition. {target} was not changed.")
    else:
        rebuilt = [e.table for e in report.tables if e.action == "rebuilt"]
        print(f"COMMITTED: {len(rebuilt)} table(s) rebuilt and verified in one "
              f"transaction ({', '.join(rebuilt)}); foreign_key_check "
              f"{report.foreign_key_check} row(s), as before.")
        print(f"The write lock was held {report.lock_seconds:.2f}s "
              f"(the scheduler's busy timeout is 30s).")
    print(f"{time.perf_counter() - started:.1f}s in all, on {target}")
    write_report(backup, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
