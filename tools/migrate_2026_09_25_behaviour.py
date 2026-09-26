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
backup, every sqlite_master row byte for byte, and every table's row count
and column checksums compared with the record at the instant of the copy.
If the backup does not verify, nothing is migrated.

THE LIVE RECORD IS KNOWN BY THE FILE'S IDENTITY (2026-09-25, the
adversarial review of 3603300): `db.is_the_live_record_file`, the door
`tools/reconstruct_prompts.py` uses -- the configured record, the default
one, this checkout's `var` and the main worktree's `var`, each compared with
`os.path.samefile`. It used to be the running checkout's `config.DB_PATH`
resolved, so from a worktree, through a hard link, or with GRIDIRON_DB,
GRIDIRON_HOME or GRIDIRON_STATE set, the record was "not the record" and was
migrated in place with no backup. And `--live` on any other file is refused.

WITH --live, THE DEFINITIONS ARE THE RELEASE'S OR NOTHING IS DONE (the same
review). The definitions are read from whatever `schema.sql` the running
checkout holds; nothing checked them against the release. Now `--live`
reads `gridiron/schema.sql` and `gridiron/market/lines.py` from the branch
`master` through `git show`, and refuses by name unless the definitions it
would write, the snapshot table's entry in the map, and the running tree's
`schema.sql` itself are exactly the release's (line endings apart).

--report IS A NEW FILE (the same review). It was written with
`Path.write_text` over whatever it named: `--report` on the backup turned
the verified backup into JSON, and on the record overwrote the record, even
from a rehearsal with nothing to do. It is refused now, before anything is
done, unless it is a new file in an existing folder and is not the
database, the record, the backup, the scratch copy or any file SQLite keeps
beside one of them (-wal, -shm, -journal), compared by the file's identity;
and it is created exclusively, so a file that appears meanwhile is never
written over. And no file this run creates -- report, backup or scratch
copy -- may be spelled as a place inside another file (2026-09-25, the
rehearsal of these fixes): a colon names a Windows stream INSIDE the file
before it, so `--report <record>:x`, `--backup <record>:x` and `--scratch
<record>:x` each wrote into the record's own file, and a name ending in a
dot or a space is another name. Nor may any of them be the database, the
record, or a -wal, -shm or -journal beside either: SQLite deletes such a
file when it next opens the database, and `--live --backup
<record>-journal` lost its verified backup to the migration's own open of
the record, exit 0. `db.not_a_file_of_its_own` refuses all of it.

THE BACKUP IS ONE INSTANT (note 9 of the same review, reported, not
changed). It holds the record as it was when it was copied. A scheduled
task that writes between that instant and the migration's write lock puts
rows in the record that the backup does not hold; restored, the backup
would lose them. The tool prints both instants. Run it at a quiet hour.

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
import ast
import json
import subprocess
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

from gridiron import db, rebuild  # noqa: E402
from gridiron.market import lines  # noqa: E402

#: THE MIGRATION MAP, in the order the tables are rebuilt: (table, what the
#: rebuild gives it, the commit that introduced the released definition).
#: The snapshot table's entry comes from the market package, the only one
#: that may name it in code (LAW 1's closure scan). Each table's indexes and
#: triggers come with its definition from `schema.sql`, the snapshot table's
#: five included: the two LAW 1 insert rules, the delete rule of ruling 4
#: and, from 2026-09-25, the two replace rules (`market_snapshots_never_replaced`
#: for an insert, `market_snapshots_never_replaced_by_update` for an update).
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

#: The branch the release is, as the gate's release comparison reads it.
RELEASED_BRANCH = "master"


class Refused(SystemExit):
    """The tool will not run as asked. Exit code 2, with the reason."""

    def __init__(self, why: str):
        print("REFUSED: " + why)
        super().__init__(2)


def _is_the_record(path: Path) -> bool:
    """Is `path` the operator's own record? By the FILE'S IDENTITY, through
    the one door (`db.is_the_live_record_file`), whatever checkout, link or
    environment this runs from; with no exception for the temp directory,
    which is the rule for scratch files, not for this question."""
    return db.is_the_live_record_file(path)


# ---------------------------------------------------------------------------
# the report is a new file (finding 1 of the review of 3603300)
# ---------------------------------------------------------------------------

def _refuse_a_new_file_over_anything(flag: str, path: Path, keep: list[Path]) -> None:
    """Refuse, before anything is done, a file this run would create that is
    not a file of its own: a stream inside another file, a name Windows reads
    as another, or any database in `keep` or a file SQLite keeps beside one
    -- compared by the folder's identity and the name, through the one door,
    `db.not_a_file_of_its_own`. For --report from the review of 3603300; for
    --backup and --scratch from the rehearsal of its fixes (2026-09-26),
    which found `--live --backup <record>-journal` deleted by SQLite before
    the run ended, the record migrated with no backup anywhere."""
    elsewhere = db.not_a_file_of_its_own(path, beside=keep)
    if elsewhere:
        raise Refused(f"{flag} {path} {elsewhere}; every file this run creates "
                      f"is a new file of its own, and nothing was done")


def _refuse_a_report_over_anything(report: Path, keep: list[Path]) -> None:
    """Refuse, before anything is done, a report that is not a new file in an
    existing folder, or that names any file in `keep` or one SQLite writes
    beside it -- compared by the file's identity."""
    if report.exists() or report.is_symlink():
        raise Refused(
            f"--report {report} already exists; the report is a new file, "
            f"never one written over -- the record, the backup and every "
            f"other file are left as they are")
    # A FOLDER, NOT A FILE (2026-09-26, found by the prover of these fixes):
    # `exists()` let `--report <record>/report.json` through -- its "folder"
    # is the record, a file -- and the run went ahead and ended in a
    # traceback where the report was to be written, after the COMMIT on a
    # live run.
    if not report.parent.is_dir():
        raise Refused(f"--report {report}: its folder {report.parent} is not a "
                      f"folder that exists, so the report could not be written "
                      f"after the run")
    _refuse_a_new_file_over_anything("--report", report, keep)


def _write_report(path: Path, payload: dict) -> bool:
    """Create the report exclusively: a file that appeared since the check
    is not written over. True when written."""
    try:
        with open(path, "x", encoding="utf-8") as out:
            out.write(json.dumps(payload, indent=1, default=str))
    except FileExistsError:
        print(f"REPORT NOT WRITTEN: {path} appeared during the run, and is "
              f"not written over")
        return False
    except OSError as exc:
        # SAID, NOT RAISED (2026-09-26, the prover of these fixes): the run's
        # verdict is already printed, and on a live run the COMMIT is done;
        # a report that cannot be written is named, never a traceback in its
        # place.
        print(f"REPORT NOT WRITTEN: {path} could not be created: {exc}")
        return False
    return True


def _report_payload(backup, report: rebuild.RebuildReport) -> dict:
    return {
        "backup": None if backup is None else backup.__dict__,
        "committed": report.committed,
        "lock_seconds": report.lock_seconds,
        "failure": report.failure,
        "foreign_key_check_rows": report.foreign_key_check,
        "tables": [entry.__dict__ for entry in report.tables],
    }


# ---------------------------------------------------------------------------
# with --live, the definitions are the release's (finding 3)
# ---------------------------------------------------------------------------

def _released_file(path: str) -> str:
    """A file as the release holds it: `git show master:<path>`, from this
    checkout's repository. Refused by name when git cannot answer."""
    try:
        done = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{RELEASED_BRANCH}:{path}"],
            capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refused(f"--live reads the release from git, and git did not "
                      f"run: {exc}")
    if done.returncode != 0:
        raise Refused(
            f"--live reads {path} from {RELEASED_BRANCH} through git, and git "
            f"said: {done.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return done.stdout.decode("utf-8")


def _lf(text: str | None) -> str | None:
    return None if text is None else text.replace("\r\n", "\n")


def _definition_words(d: rebuild.Definition) -> tuple:
    return (_lf(d.create), tuple((k, n, _lf(s)) for k, n, s in d.dependants),
            d.automatic_indexes)


def _snapshot_entry(source: str):
    """`SNAPSHOT_REBUILD` as a file of the market package declares it."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "SNAPSHOT_REBUILD"
                for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def release_faults(definitions: dict[str, rebuild.Definition]) -> list[str]:
    """Every way the definitions this run would write, the map's snapshot
    entry, or the running tree's schema.sql differ from the release's,
    named. Empty when they are exactly the release's, line endings apart."""
    faults = []
    released_schema = _released_file("gridiron/schema.sql")
    released = rebuild.released_definitions(list(definitions), released_schema)
    for table, mine in definitions.items():
        theirs = released[table]
        if _lf(mine.create) != _lf(theirs.create):
            faults.append(f"{table}: its CREATE text is not the release's")
        ours = {n: (k, _lf(s)) for k, n, s in mine.dependants}
        its = {n: (k, _lf(s)) for k, n, s in theirs.dependants}
        for name in sorted(set(ours) | set(its)):
            if ours.get(name) != its.get(name):
                kind = (ours.get(name) or its.get(name))[0]
                faults.append(f"{table}: {kind} {name} is not the release's")
        if mine.automatic_indexes != theirs.automatic_indexes:
            faults.append(f"{table}: its automatic indexes are not the release's")
    entry = _snapshot_entry(_released_file("gridiron/market/lines.py"))
    if tuple(entry or ()) != tuple(lines.SNAPSHOT_REBUILD):
        faults.append(f"the snapshot table's entry in the map, "
                      f"lines.SNAPSHOT_REBUILD {lines.SNAPSHOT_REBUILD!r}, is "
                      f"not the release's {entry!r}")
    if _lf(db.SCHEMA_PATH.read_text(encoding="utf-8")) != _lf(released_schema):
        faults.append(f"the running tree's {db.SCHEMA_PATH} is not "
                      f"{RELEASED_BRANCH}'s gridiron/schema.sql")
    return faults


def _released_commit() -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short=12", RELEASED_BRANCH],
            capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
        return done.stdout.decode().strip() or "(unknown)"
    except (OSError, subprocess.SubprocessError):
        return "(unknown)"


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------

def _print_backup(report: rebuild.BackupReport, instant: str) -> None:
    rows = sum(count for count, _digest in report.tables.values())
    print(f"VERIFIED BACKUP: {report.source} -> {report.target}")
    print(f"  integrity_check on the backup: {', '.join(report.integrity)}")
    print(f"  {len(report.tables)} tables, {rows:,} rows: every row count and "
          f"every column checksum equal on both sides, and every schema "
          f"object byte for byte, at the instant copied")
    print(f"  {report.seconds:.1f}s")
    print(f"  THE BACKUP IS ONE INSTANT: the record as it was when copied, "
          f"about {instant}. Rows a scheduled task writes after it are in the "
          f"record and not in this backup.")


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
    parser.add_argument("--report", help="also write the report as JSON to "
                                         "this new file")
    args = parser.parse_args(argv)

    # --report IS WRITTEN ON EVERY EXIT THAT REACHES A VERDICT (2026-09-25).
    # The rehearsal of that day ran this tool a second time with --report on
    # the migrated copy and got no file: the nothing-to-do exit and the
    # unverified-copy exits returned before the report was written. A run
    # asked for its record must leave one; an absent file reads as a run
    # that never happened. AND ONLY AS A NEW FILE (the review of 3603300):
    # checked below before anything is done, and created exclusively.
    def write_report(backup, report: rebuild.RebuildReport) -> None:
        if args.report and _write_report(Path(args.report),
                                         _report_payload(backup, report)):
            print(f"report written to {args.report}")

    database = Path(args.database)
    # EVERY FILE THIS RUN CREATES IS A FILE OF ITS OWN (2026-09-25/26, the
    # rehearsal of these fixes): not a stream inside another file, the
    # record's above all, not a name Windows reads as another, and not the
    # database, the record or a -wal, -shm or -journal beside either --
    # asked of `db.not_a_file_of_its_own`, the backup door's own rule,
    # before anything is done. The rehearsal wrote a report, a "verified
    # backup" and a whole rehearsal copy INSIDE a stand-in record, and saw a
    # backup named as the record's -journal deleted by SQLite before the
    # migration ended; each exit 0.
    around = [database, *db.live_record_candidates()]
    for flag, value in (("--report", args.report), ("--backup", args.backup),
                        ("--scratch", args.scratch)):
        if value:
            _refuse_a_new_file_over_anything(flag, Path(value), around)
    if not database.exists():
        raise Refused(f"there is no database at {database}")
    live = _is_the_record(database)
    if args.live and args.rehearse:
        raise Refused("--live and --rehearse ask for opposite things")
    if args.live and not live:
        raise Refused(
            f"--live names the operator's record, and {database} is not it: "
            f"it is not the same file as any place the record is reached from "
            f"({', '.join(str(p) for p in db.live_record_candidates())}), "
            f"compared by the file's identity")
    if live and not args.rehearse and not args.live:
        raise Refused(
            f"{database} is the operator's record (the same file as the live "
            f"record, found by its identity). It is migrated only with --live "
            f"and a verified --backup made in the same run; to see what would "
            f"happen, --rehearse migrates a verified copy instead")
    if args.live and not args.backup:
        raise Refused("--live needs --backup FILE: the ruling requires a "
                      "verified backup of the record before it is changed")
    if args.live and Path(args.backup).exists():
        raise Refused(f"{args.backup} already exists; the verified backup is "
                      f"a new file, never one written over")
    if args.report:
        keep = [database, *db.live_record_candidates()]
        if args.backup:
            keep.append(Path(args.backup))
        if args.scratch:
            keep.append(Path(args.scratch))
        _refuse_a_report_over_anything(Path(args.report), keep)

    definitions = rebuild.released_definitions([t for t, _w, _c in MIGRATION])
    if args.live:
        faults = release_faults(definitions)
        if faults:
            raise Refused(
                f"--live writes the RELEASED definitions, and these are not "
                f"{RELEASED_BRANCH}'s ({_released_commit()}): "
                + "; ".join(faults)
                + ". Run it from the main checkout, after the release that "
                  "carries it, with nothing uncommitted in either file")
        print(f"schema ruling 2 -- the released definitions: {db.SCHEMA_PATH}, "
              f"checked equal to {RELEASED_BRANCH} ({_released_commit()})")
    else:
        print(f"schema ruling 2 -- the definitions are this tree's "
              f"{db.SCHEMA_PATH} (with --live they must be {RELEASED_BRANCH}'s)")
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
    backup_instant = None
    target = database
    if args.rehearse:
        scratch = Path(args.scratch) if args.scratch else (
            Path(tempfile.mkdtemp(prefix="gridiron-ruling-2-")) / "rehearsal.db")
        print(f"REHEARSAL: {database} is copied, verified, and the COPY is "
              f"migrated; {database} is only read")
        try:
            backup_instant = db.utcnow()
            backup = rebuild.verified_backup(
                database, scratch,
                "the rehearsal of schema ruling 2's migration, on a verified "
                "copy")
        except rebuild.BackupFailedVerification as exc:
            print(f"THE COPY DID NOT VERIFY; nothing was migrated. {exc}")
            write_report(None, rebuild.RebuildReport(
                failure=f"the copy did not verify; nothing was migrated: {exc}"))
            return 1
        _print_backup(backup, backup_instant)
        target = scratch
    elif args.live:
        print(f"THE LIVE RECORD: {database}. A verified backup first.")
        try:
            backup_instant = db.utcnow()
            backup = rebuild.verified_backup(
                database, Path(args.backup),
                "the verified backup schema ruling 2 requires before the "
                "migration changes the live record")
        except rebuild.BackupFailedVerification as exc:
            print(f"THE BACKUP DID NOT VERIFY; nothing was migrated. {exc}")
            write_report(None, rebuild.RebuildReport(
                failure=f"the backup did not verify; nothing was migrated: {exc}"))
            return 1
        _print_backup(backup, backup_instant)

    conn = db.connect(target)
    started = time.perf_counter()
    lock_instant = db.utcnow()
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
        if backup is not None and args.live:
            # NOTE 9 OF THE REVIEW OF 3603300 (2026-09-25), reported, not
            # changed: the backup is the record at one instant, and anything
            # written between that instant and the write lock is in the
            # record and not in it. Said here, in the run's own output, so the
            # operator reads it beside the file it is about. ONLY ON THE LIVE
            # RUN (the rehearsal of these fixes, 2026-09-25): a rehearsal's
            # "backup" is the scratch copy it then migrated, which no task
            # writes, and the rehearsal printed that rows were in "the
            # migrated record" and "not in the backup" -- false of it.
            print(f"THE BACKUP IS NOT THE RECORD AS MIGRATED: it holds the "
                  f"record as it was at about {backup_instant}; the migration "
                  f"took the write lock at about {lock_instant}. Rows a "
                  f"scheduled task wrote between the two are in the migrated "
                  f"record and not in the backup, and a restore from it would "
                  f"lose them. That is why this runs at a quiet hour.")
    print(f"{time.perf_counter() - started:.1f}s in all, on {target}")
    write_report(backup, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
