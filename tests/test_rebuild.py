"""The dated migration of schema ruling 2 (2026-09-24, built 2026-09-25).

"The 8 behavioural differences are fixed by a dated migration that rebuilds
each affected table: new table with the released definition, copy every row,
verify the row count and a checksum of every column match exactly, recreate
every trigger and index, then swap, all in one transaction ... Take a
verified backup of the live record before running it. If any table fails
verification, the transaction rolls back and nothing is swapped."

Every test starts from a scratch record whose eight tables are in the live
record's own shapes (tests/fixtures/live_shapes_2026_09_25.sql, read through
the read-only door), with rows in them. The live record is never opened: the
tool's refusals are tested against a stand-in named as the record.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sqlite3
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from gridiron import config, db, rebuild, schema_diff

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    """A tool loaded by path. Registered first: plant.py's dataclasses look
    their module up while it is still loading."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def plant():
    return _load("gridiron_plant_for_rebuild", REPO / "tools" / "guards" / "plant.py")


@pytest.fixture(scope="module")
def tool():
    return _load("gridiron_migrate_ruling_2",
                 REPO / "tools" / "migrate_2026_09_25_behaviour.py")


def _tables(tool) -> list[str]:
    return [table for table, _what, _commit in tool.MIGRATION]


def _master(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name")]


def _a_record(path: Path, plant, tool):
    """A fresh build in the live shapes, with rows in every table that can
    take one without a network: factors from the registry, a fit, three
    forecasts with a snapshot and a rank each, lineups with a hole in their
    implicit rowids, a card, and two injuries; and a market_snapshots
    sequence above its highest id, as a hole at the end would leave it."""
    from gridiron.factors import store

    conn = plant._a_record_in_the_live_shapes(path, _tables(tool))
    store.sync_registry(conn)
    conn.execute(
        "INSERT INTO model_fits (sport, fitted_utc, factor_set_version,"
        " market_type, train_through, n_train, coefficients_json)"
        " VALUES ('mlb', '2026-09-01T00:00:00Z', 'fs2', 'moneyline',"
        " 'season:2025', 10, '{\"a\": 0.1}')")
    for i in range(3):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
            " home, away, status) VALUES (?, 'mlb', 2026, 1, 'REG',"
            " '2026-09-01T23:00:00Z', 'NYY', 'BOS', 'scheduled')", (f"g{i}",))
        pid = conn.execute(
            "INSERT INTO predictions (created_utc, game_id, sport, market_type,"
            " subject, line_asked, model_prob, model_side, predictor,"
            " factor_set_version, factors_json, reasoning) VALUES (?, ?, 'mlb',"
            " 'moneyline', 'NYY', NULL, 0.6, 'win', 'statistical', 'fs2', '{}',"
            " 'x')", (f"2026-09-01T18:00:0{i}Z", f"g{i}")).lastrowid
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " line, implied_prob, kind) VALUES (?, '2026-09-01T18:30:00Z',"
            " 'test', NULL, 0.1 + 0.2, 'open_at_predict')", (pid,))
        conn.execute(
            "INSERT INTO prediction_ranks (prediction_id, ranker_version, sport,"
            " market_type, rank_score, confidence, completeness, created_utc,"
            " on_shortlist) VALUES (?, 'r1', 'mlb', 'moneyline', 0.5, 0.5, 0.5,"
            " '2026-09-01T19:00:00Z', ?)", (pid, i % 2))
        conn.execute(
            "INSERT INTO mlb_lineups (game_id, side, slot, player_id,"
            " player_name, recorded_utc) VALUES ('g0', 'home', ?, ?, 'Someone',"
            " '2026-09-01T20:00:00Z')", (i + 1, 100 + i))
    conn.execute("DELETE FROM mlb_lineups WHERE slot = 2")
    conn.execute("UPDATE sqlite_sequence SET seq = 40"
                 " WHERE name = 'market_snapshots'")
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
        " event_tier) VALUES ('u1', 'UFC 1', NULL, 2026, '2026-09-01T00:00:00Z',"
        " 'numbered')")
    conn.execute(
        "INSERT INTO nba_injuries (player_id, player_name, team, status, detail,"
        " fetched_utc) VALUES (6430, 'A Player', 'BOS', 'Out', NULL,"
        " '2026-09-01T00:00:00Z'), (5289900, 'Another', 'NYK', 'Questionable',"
        " 'ankle', '2026-09-01T00:00:00Z')")
    conn.commit()
    return conn


def _state(conn, tables) -> tuple:
    return ({t: rebuild.column_checksums(conn, t) for t in tables},
            [tuple(r) for r in conn.execute(
                "SELECT name, seq FROM sqlite_sequence ORDER BY name")])


def test_the_eight_are_rebuilt_to_the_release_and_every_row_is_kept(
        tmp_path, plant, tool, capsys):
    path = tmp_path / "record.db"
    conn = _a_record(path, plant, tool)
    tables = _tables(tool)
    before = _state(conn, tables)
    rowids = [r[0] for r in conn.execute("SELECT rowid FROM mlb_lineups ORDER BY 1")]
    conn.close()
    assert rowids == [1, 3], "the fixture should leave a hole in the rowids"

    assert tool.main(["--database", str(path)]) == 0
    out = capsys.readouterr().out
    assert "COMMITTED: 8 table(s) rebuilt and verified in one transaction" in out
    assert "The write lock was held" in out

    fresh = tmp_path / "fresh.db"
    db.open_db(fresh).close()
    record = db.read_only(path, "the migrated record, compared")
    reference = db.read_only(fresh, "a fresh build, compared")
    try:
        assert _state(record, tables) == before
        assert [r[0] for r in record.execute(
            "SELECT rowid FROM mlb_lineups ORDER BY 1")] == [1, 3]
        assert record.execute("SELECT seq FROM sqlite_sequence"
                              " WHERE name = 'market_snapshots'").fetchone()[0] == 40
        assert record.execute("SELECT COUNT(*) FROM sqlite_sequence"
                              " WHERE name = 'factor_scores'").fetchone()[0] == 0
        # BYTE FOR BYTE, not only normalised: the eight tables and every
        # index and trigger on them are the release's own text.
        assert ({(r[0], r[1]): r[3] for r in _master(record) if r[2] in tables}
                == {(r[0], r[1]): r[3] for r in _master(reference)
                    if r[2] in tables})
        result = schema_diff.compare(record, reference)
        assert result.differences == []
    finally:
        record.close()
        reference.close()


def test_no_other_table_is_repointed(tmp_path, plant, tool):
    """Children keep naming their parent: ufc_bouts names ufc_events,
    fit_activations names model_fits, and so on -- with foreign keys off
    and legacy_alter_table on, the rename aside rewrites nothing."""
    path = tmp_path / "record.db"
    conn = _a_record(path, plant, tool)
    others = [r for r in _master(conn) if r[2] not in _tables(tool)]
    conn.close()
    assert tool.main(["--database", str(path)]) == 0
    conn = db.read_only(path, "the migrated record's other objects")
    try:
        assert [r for r in _master(conn) if r[2] not in _tables(tool)] == others
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_a_second_run_changes_nothing_and_says_so(tmp_path, plant, tool, capsys):
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    assert tool.main(["--database", str(path)]) == 0
    conn = db.read_only(path, "the record after one run")
    once = _master(conn)
    conn.close()
    capsys.readouterr()
    assert tool.main(["--database", str(path)]) == 0
    out = capsys.readouterr().out
    assert out.count("skipped: already at its definition") >= 8
    assert "NOTHING TO DO" in out
    conn = db.read_only(path, "the record after two runs")
    try:
        assert _master(conn) == once
    finally:
        conn.close()


def test_a_report_asked_for_is_written_when_there_is_nothing_to_do(
        tmp_path, plant, tool, capsys):
    """--report is written on every exit that reaches a verdict (2026-09-25).
    The rehearsal of that day ran the tool a second time with --report on the
    migrated copy and got no file: the nothing-to-do exit returned before the
    report was written, so a run that was asked for its record left none, and
    an absent file reads as a run that never happened."""
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    assert tool.main(["--database", str(path)]) == 0
    report = tmp_path / "second-run.json"
    assert tool.main(["--database", str(path), "--report", str(report)]) == 0
    assert "NOTHING TO DO" in capsys.readouterr().out
    assert report.exists(), "a second run was asked for its report and left none"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["committed"] is False and payload["failure"] is None
    assert [(t["table"], t["action"]) for t in payload["tables"]] == [
        (t, "skipped: already at its definition") for t in _tables(tool)]


def test_a_report_asked_for_is_written_when_the_copy_does_not_verify(
        tmp_path, plant, tool, monkeypatch, capsys):
    """The same, for a verified copy that does not verify: the refusal is
    the verdict, and the report says so (2026-09-25)."""
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    real = rebuild.column_checksums

    def lying_about_the_copy(conn, table):
        count, sums = real(conn, table)
        name = conn.execute("PRAGMA database_list").fetchone()[2]
        if name.endswith("rehearsal.db") and table == "nba_injuries":
            sums = dict(sums, status="0" * 64)
        return count, sums

    monkeypatch.setattr(rebuild, "column_checksums", lying_about_the_copy)
    report = tmp_path / "rehearsal.json"
    assert tool.main(["--database", str(path), "--rehearse", "--scratch",
                      str(tmp_path / "rehearsal.db"), "--report", str(report)]) == 1
    assert "THE COPY DID NOT VERIFY" in capsys.readouterr().out
    assert report.exists(), "a refused copy was asked for its report and left none"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["committed"] is False
    assert "nba_injuries" in payload["failure"]


def test_a_rollback_that_is_not_proven_is_never_called_nothing_swapped(
        tmp_path, plant, tool, monkeypatch, capsys):
    """A schema change by another connection between the plan and the lock
    (a scheduled task's db.init creating a released object, on the live
    record) fails the in-transaction check and rolls back -- and then the
    schema is not what it was, so the library refuses WITHOUT the proof that
    nothing was swapped. The tool must not print that proof anyway. Found by
    the rehearsal's review, 2026-09-25: it printed "ROLLED BACK. NOTHING WAS
    SWAPPED: ROLLED BACK, AND THE SCHEMA IS NOT WHAT IT WAS"."""
    path = tmp_path / "record.db"
    conn = _a_record(path, plant, tool)
    schema = _master(conn)
    conn.close()
    real = rebuild._master
    calls = []

    def a_writer_slips_in(c):
        seen = real(c)
        if not calls:
            other = db.connect(path)
            other.execute("CREATE TABLE a_concurrent_object (x)")
            other.commit()
            other.close()
        calls.append(1)
        return seen

    monkeypatch.setattr(rebuild, "_master", a_writer_slips_in)
    report = tmp_path / "refused.json"
    assert tool.main(["--database", str(path), "--report", str(report)]) == 1
    out = capsys.readouterr().out
    assert "NOTHING WAS SWAPPED" not in out, "claimed a rollback it had not proved"
    assert "NOT COMMITTED: ROLLED BACK, AND THE SCHEMA IS NOT WHAT IT WAS" in out
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["committed"] is False
    assert "SCHEMA IS NOT WHAT IT WAS" in payload["failure"]
    after = db.read_only(path, "the record after an unproven rollback")
    try:
        assert [r for r in _master(after) if r[1] != "a_concurrent_object"] == schema
    finally:
        after.close()


@pytest.mark.parametrize("victim, corruption", [
    ("nba_injuries", "UPDATE nba_injuries SET status = 'Probable'"
                     " WHERE player_id = 6430"),
    ("factors", "DELETE FROM factors WHERE rowid = (SELECT MAX(rowid) FROM factors)"),
    ("mlb_lineups", "UPDATE mlb_lineups SET rowid = rowid + 100 WHERE slot = 3"),
])
def test_a_copy_that_is_not_exact_rolls_back_and_swaps_nothing(
        tmp_path, plant, tool, monkeypatch, victim, corruption):
    """An altered value, a lost row, a renumbered rowid: each fails its
    table's verification, and the whole transaction -- the tables already
    swapped before it included -- rolls back."""
    path = tmp_path / "record.db"
    conn = _a_record(path, plant, tool)
    tables = _tables(tool)
    schema, state = _master(conn), _state(conn, tables)
    copy = rebuild._copy_rows

    def corrupting(c, table, aside, columns, with_rowid):
        copy(c, table, aside, columns, with_rowid)
        if table == victim:
            c.execute(corruption)

    monkeypatch.setattr(rebuild, "_copy_rows", corrupting)
    definitions = rebuild.released_definitions(tables)
    with pytest.raises(rebuild.TableFailedVerification, match=victim):
        rebuild.rebuild_tables(conn, [definitions[t] for t in tables])
    assert _master(conn) == schema
    assert _state(conn, tables) == state
    conn.close()


def test_the_tool_reports_a_rollback_with_what_it_measured(
        tmp_path, plant, tool, monkeypatch, capsys):
    path = tmp_path / "record.db"
    conn = _a_record(path, plant, tool)
    schema = _master(conn)
    conn.close()
    copy = rebuild._copy_rows

    def corrupting(c, table, aside, columns, with_rowid):
        copy(c, table, aside, columns, with_rowid)
        if table == "ufc_events":
            c.execute("UPDATE ufc_events SET name = 'UFC 2'")

    monkeypatch.setattr(rebuild, "_copy_rows", corrupting)
    assert tool.main(["--database", str(path)]) == 1
    out = capsys.readouterr().out
    assert "ROLLED BACK. NOTHING WAS SWAPPED: ufc_events FAILED VERIFICATION" in out
    assert "  rows 1 -> 1\n" in out, "the failing table's counts are reported"
    assert re.search(r"^    name +[0-9a-f]{16} -> [0-9a-f]{16}  DIFFERS$", out,
                     re.MULTILINE), "the altered column is named"
    assert out.count("rolled back; nothing swapped") == 8
    conn = db.read_only(path, "the record after a rolled-back run")
    try:
        assert _master(conn) == schema
    finally:
        conn.close()


def test_a_sequence_the_failure_never_reached_is_not_reported_as_lost(
        tmp_path, plant, tool, monkeypatch, capsys):
    """Found by the rehearsal's forced failure, 2026-09-25: market_snapshots
    failed verification and the report printed "sequence 2355 -> None" -- a
    high-water mark that reads as lost, when it was never measured (the
    failure came before the sequence is carried) and the rollback kept it.
    One REAL moved by 1e-12 is the corruption, so the test also shows the
    checksum telling two close reals apart."""
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    copy = rebuild._copy_rows

    def corrupting(c, table, aside, columns, with_rowid):
        copy(c, table, aside, columns, with_rowid)
        if table == "market_snapshots":
            c.execute("UPDATE market_snapshots SET implied_prob = implied_prob"
                      " + 1e-12 WHERE id = (SELECT MIN(id) FROM market_snapshots)")

    monkeypatch.setattr(rebuild, "_copy_rows", corrupting)
    assert tool.main(["--database", str(path)]) == 1
    out = capsys.readouterr().out
    assert "market_snapshots FAILED VERIFICATION" in out
    assert "checksums differ in implied_prob" in out
    assert "sequence 40 -> None" not in out, "an unmeasured sequence reported as lost"
    assert "sequence 40 -> not reached" in out
    conn = db.read_only(path, "the record after the rolled-back run")
    try:
        assert conn.execute("SELECT seq FROM sqlite_sequence"
                            " WHERE name = 'market_snapshots'").fetchone()[0] == 40
    finally:
        conn.close()


def test_a_row_the_release_refuses_stops_the_copy(tmp_path, plant, tool):
    """Every live row satisfies the released CHECKs (measured); one that did
    not would stop the copy, and the transaction would roll back."""
    path = tmp_path / "record.db"
    conn = _a_record(path, plant, tool)
    conn.execute("INSERT INTO ufc_events (id, name, season, fetched_utc,"
                 " event_tier) VALUES ('u2', 'x', 2026, 'x', 'no such tier')")
    conn.commit()
    schema = _master(conn)
    tables = _tables(tool)
    definitions = rebuild.released_definitions(tables)
    with pytest.raises(rebuild.RebuildRefused, match="CHECK constraint failed"):
        rebuild.rebuild_tables(conn, [definitions[t] for t in tables])
    assert _master(conn) == schema
    conn.close()


def test_the_rebuild_refuses_to_drop_an_object_the_release_does_not_recreate(
        tmp_path, plant, tool):
    path = tmp_path / "record.db"
    conn = _a_record(path, plant, tool)
    conn.execute("CREATE INDEX an_index_of_its_own ON nba_injuries (status)")
    conn.commit()
    schema = _master(conn)
    tables = _tables(tool)
    definitions = rebuild.released_definitions(tables)
    with pytest.raises(rebuild.RebuildRefused, match="an_index_of_its_own"):
        rebuild.rebuild_tables(conn, [definitions[t] for t in tables])
    assert _master(conn) == schema
    conn.close()


def test_db_init_does_not_run_the_migration(tmp_path, plant, tool):
    """The operator runs it, with a backup, at a quiet hour; a scheduled
    task opening the record must not race to do it."""
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    conn = db.connect(path)
    before = _master(conn)
    conn.close()
    db.open_db(path).close()
    conn = db.read_only(path, "the record after this tree's db.init")
    try:
        assert _master(conn) == before
    finally:
        conn.close()


# --- the live record: refused, unless --live with a verified backup ---------

def _as_the_record(monkeypatch, path: Path) -> None:
    """Name a scratch file as the operator's record, for this test only."""
    monkeypatch.setattr(config, "DB_PATH", path)


def _release_is_this_tree(monkeypatch, tool, **changed) -> None:
    """--live reads the release from the branch master through git
    (2026-09-25); here the release is this tree's own files, as it is on the
    main checkout after the merge -- with any file in `changed` (a path, as
    git names it, with `/` written `__`) transformed, to make the release
    differ. Set without raising, so a test also runs on a tool that has no
    such reader."""
    wanted = {name.replace("__", "/"): how for name, how in changed.items()}

    def released(path: str) -> str:
        text = (REPO / path).read_text(encoding="utf-8")
        return wanted[path](text) if path in wanted else text

    monkeypatch.setattr(tool, "_released_file", released, raising=False)


def test_the_record_is_refused_without_live(tmp_path, plant, tool, monkeypatch,
                                            capsys):
    path = tmp_path / "gridiron.db"
    conn = _a_record(path, plant, tool)
    schema = _master(conn)
    conn.close()
    _as_the_record(monkeypatch, path)
    with pytest.raises(SystemExit) as refused:
        tool.main(["--database", str(path)])
    assert refused.value.code == 2
    assert "is the operator's record" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        tool.main(["--database", str(path), "--live"])
    assert "--live needs --backup" in capsys.readouterr().out
    conn = db.read_only(path, "the stand-in, after the refusals")
    try:
        assert _master(conn) == schema
    finally:
        conn.close()


def test_live_is_refused_on_a_file_that_is_not_the_record(
        tmp_path, plant, tool, monkeypatch, capsys):
    path = tmp_path / "scratch.db"
    _a_record(path, plant, tool).close()
    _as_the_record(monkeypatch, tmp_path / "gridiron.db")
    with pytest.raises(SystemExit):
        tool.main(["--database", str(path), "--live", "--backup",
                   str(tmp_path / "b.db")])
    assert "is not it" in capsys.readouterr().out


def test_live_takes_a_verified_backup_first_and_keeps_it(
        tmp_path, plant, tool, monkeypatch, capsys):
    path = tmp_path / "gridiron.db"
    conn = _a_record(path, plant, tool)
    tables = _tables(tool)
    old_shapes, state = _master(conn), _state(conn, tables)
    conn.close()
    _as_the_record(monkeypatch, path)
    _release_is_this_tree(monkeypatch, tool)
    backup = tmp_path / "gridiron.before-ruling-2.db"
    assert tool.main(["--database", str(path), "--live",
                      "--backup", str(backup)]) == 0
    out = capsys.readouterr().out
    assert "VERIFIED BACKUP" in out and "integrity_check on the backup: ok" in out
    assert out.index("VERIFIED BACKUP") < out.index("COMMITTED")
    kept = db.read_only(backup, "the backup, after the migration")
    try:
        assert _master(kept) == old_shapes, "the backup is the record before"
        assert _state(kept, tables) == state
    finally:
        kept.close()
    with pytest.raises(SystemExit):
        tool.main(["--database", str(path), "--live", "--backup", str(backup)])
    assert "already exists" in capsys.readouterr().out
    # AND ONCE MIGRATED, NOTHING IS COPIED: the plan is asked read-only first.
    again = tmp_path / "a-second-backup.db"
    assert tool.main(["--database", str(path), "--live",
                      "--backup", str(again)]) == 0
    assert "NOTHING TO DO" in capsys.readouterr().out
    assert not again.exists()


def test_a_backup_is_never_written_over_an_existing_file(tmp_path, plant, tool):
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    existing = tmp_path / "existing.db"
    existing.write_bytes(b"the operator's other file")
    with pytest.raises(rebuild.BackupFailedVerification, match="already exists"):
        rebuild.verified_backup(path, existing, "a backup over an existing file")
    assert existing.read_bytes() == b"the operator's other file"


def test_a_backup_that_does_not_match_its_source_is_refused(
        tmp_path, plant, tool, monkeypatch):
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    real = rebuild.column_checksums

    def lying_about_the_copy(conn, table):
        count, sums = real(conn, table)
        name = conn.execute("PRAGMA database_list").fetchone()[2]
        if name.endswith("copy.db") and table == "nba_injuries":
            sums = dict(sums, status="0" * 64)
        return count, sums

    monkeypatch.setattr(rebuild, "column_checksums", lying_about_the_copy)
    with pytest.raises(rebuild.BackupFailedVerification, match="nba_injuries"):
        rebuild.verified_backup(path, tmp_path / "copy.db", "a backup, proved")


def test_the_rehearsal_migrates_a_verified_copy_and_only_reads_the_source(
        tmp_path, plant, tool, monkeypatch, capsys):
    path = tmp_path / "gridiron.db"
    conn = _a_record(path, plant, tool)
    schema = _master(conn)
    conn.close()
    _as_the_record(monkeypatch, path)
    scratch = tmp_path / "rehearsal.db"
    assert tool.main(["--database", str(path), "--rehearse",
                      "--scratch", str(scratch)]) == 0
    out = capsys.readouterr().out
    assert "REHEARSAL" in out and "VERIFIED BACKUP" in out
    assert "The write lock was held" in out
    source = db.read_only(path, "the rehearsal's source, afterwards")
    rehearsed = db.read_only(scratch, "the rehearsed copy")
    try:
        assert _master(source) == schema, "the rehearsal changed its source"
        assert _master(rehearsed) != schema
    finally:
        source.close()
        rehearsed.close()


# ---------------------------------------------------------------------------
# THE ADVERSARIAL REVIEW OF 3603300 (2026-09-25): eight findings, each held
# here by a test that fails on the code the review read.
# ---------------------------------------------------------------------------

def _is_a_database(path: Path) -> bool:
    return path.read_bytes()[:16] == b"SQLite format 3\x00"


# --- 1. --report is a new file, never the record, the backup or a database --

def test_a_report_is_never_written_over_the_record_the_backup_or_a_database(
        tmp_path, plant, tool, monkeypatch, capsys):
    """The review's reproductions: `--live --backup X --report X` turned the
    verified backup into JSON; `--report <record>` overwrote the record; a
    rehearsal with nothing to do overwrote it too, exit 0. Each is refused
    now, before anything is done: no backup written, no copy made, the
    record as it was."""
    path = tmp_path / "gridiron.db"
    conn = _a_record(path, plant, tool)
    schema = _master(conn)
    conn.close()
    _as_the_record(monkeypatch, path)
    _release_is_this_tree(monkeypatch, tool)
    backup, scratch = tmp_path / "before.db", tmp_path / "rehearsal.db"
    live = ["--database", str(path), "--live", "--backup", str(backup)]
    for argv in (
            live + ["--report", str(backup)],
            live + ["--report", str(tmp_path / "elsewhere" / ".." / "before.db")],
            live + ["--report", str(backup) + "-wal"],
            live + ["--report", str(path)],
            live + ["--report", str(path) + "-journal"],
            live + ["--report", str(tmp_path / "no-such-folder" / "report.json")],
            # A "folder" that is a file, the record itself (the prover of
            # these fixes, 2026-09-26): passed `exists()`, and the run ended
            # in a traceback where the report was to be written.
            live + ["--report", str(path / "report.json")],
            ["--database", str(path), "--rehearse", "--scratch", str(scratch),
             "--report", str(scratch)],
            ["--database", str(path), "--rehearse", "--report", str(path)]):
        with pytest.raises(SystemExit) as refused:
            tool.main(argv)
        assert refused.value.code == 2, argv
        assert "REFUSED: --report" in capsys.readouterr().out, argv
        assert not backup.exists() and not scratch.exists(), argv
        assert _is_a_database(path), argv
    conn = db.read_only(path, "the stand-in, after every refused report")
    try:
        assert _master(conn) == schema
    finally:
        conn.close()


def test_a_report_that_appears_during_the_run_is_not_written_over(
        tmp_path, plant, tool, monkeypatch, capsys):
    """Created exclusively: a file that turns up at the report's path while
    the migration runs is left as it is, and the run says so."""
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    report = tmp_path / "report.json"
    real = rebuild.rebuild_tables

    def someone_writes_there(*args, **kwargs):
        report.write_text("the operator's own notes", encoding="utf-8")
        return real(*args, **kwargs)

    monkeypatch.setattr(rebuild, "rebuild_tables", someone_writes_there)
    tool.main(["--database", str(path), "--report", str(report)])
    assert report.read_text(encoding="utf-8") == "the operator's own notes"
    assert "REPORT NOT WRITTEN" in capsys.readouterr().out


def test_a_report_that_cannot_be_created_is_named_not_a_traceback(
        tmp_path, plant, tool, monkeypatch, capsys):
    """The prover of these fixes (2026-09-26): a report whose folder is gone
    by the time it is written ended the run in a traceback, after the COMMIT
    on a live run. The run's verdict stands and the missing report is
    named."""
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    folder = tmp_path / "reports"
    folder.mkdir()
    report = folder / "report.json"
    real = rebuild.rebuild_tables

    def the_folder_goes(*args, **kwargs):
        folder.rmdir()
        return real(*args, **kwargs)

    monkeypatch.setattr(rebuild, "rebuild_tables", the_folder_goes)
    assert tool.main(["--database", str(path), "--report", str(report)]) == 0
    out = capsys.readouterr().out
    assert any(line.startswith("COMMITTED:") for line in out.splitlines()), out
    assert f"REPORT NOT WRITTEN: {report} could not be created" in out
    assert not report.exists()


@pytest.mark.skipif(os.name != "nt",
                    reason="a stream and a stripped dot are Windows spellings")
def test_a_file_the_run_creates_is_never_a_stream_or_another_name(
        tmp_path, plant, tool, monkeypatch, capsys):
    """The rehearsal of these fixes (2026-09-25), on a scratch install:
    `--report <record>:report` wrote the report INTO the record's own file,
    as an NTFS alternate data stream; `--backup <record>:backup` put the
    verified backup inside the record it was to protect;
    `--rehearse --scratch <record>:scratch` wrote the whole rehearsal copy
    into it; and `--report <backup>.` passed every name check and was
    refused only after the migration had committed. Each exited 0. Each is
    refused now, before anything is done, and the backup door refuses a
    stream for every other caller too."""
    path = tmp_path / "gridiron.db"
    conn = _a_record(path, plant, tool)
    schema = _master(conn)
    conn.close()
    _as_the_record(monkeypatch, path)
    _release_is_this_tree(monkeypatch, tool)
    backup, scratch = tmp_path / "before.db", tmp_path / "rehearsal.db"
    live = ["--database", str(path), "--live", "--backup", str(backup)]
    rehearse = ["--database", str(path), "--rehearse", "--scratch", str(scratch)]
    timed = tmp_path / "gridiron.before-ruling-2.2026-09-26T10:15.db"
    cases = (
        (rehearse + ["--report", str(path) + ":report"], "--report"),
        (live + ["--report", str(backup) + ":report"], "--report"),
        (live + ["--report", str(backup) + "."], "--report"),
        (live + ["--report", str(tmp_path / "report.json ")], "--report"),
        (["--database", str(path), "--live", "--backup", str(path) + ":backup"],
         "--backup"),
        (["--database", str(path), "--live", "--backup", str(timed)], "--backup"),
        (["--database", str(path), "--rehearse", "--scratch",
          str(path) + ":scratch"], "--scratch"),
    )
    streams = [str(path) + ":report", str(path) + ":backup",
               str(path) + ":scratch", str(backup) + ":report"]
    for argv, flag in cases:
        with pytest.raises(SystemExit) as refused:
            tool.main(argv)
        assert refused.value.code == 2, argv
        out = capsys.readouterr().out
        assert f"REFUSED: {flag}" in out and "of its own" in out, (argv, out)
        assert not backup.exists() and not scratch.exists(), argv
        assert not any(os.path.exists(s) for s in streams), argv
        assert not (tmp_path / "gridiron.before-ruling-2.2026-09-26T10").exists(), argv
        assert _is_a_database(path), argv
    conn = db.read_only(path, "the stand-in, after every refused spelling")
    try:
        assert _master(conn) == schema
    finally:
        conn.close()
    with pytest.raises(db.LiveRecordTouched, match="A BACKUP IS A FILE OF ITS OWN"):
        db.back_up(path, str(tmp_path / "copy.db") + ":stream",
                   "a backup into a stream, refused")
    assert not (tmp_path / "copy.db").exists()


def test_a_backup_or_a_copy_is_never_a_file_sqlite_keeps_beside_a_database(
        tmp_path, plant, tool, monkeypatch, capsys):
    """The rehearsal of these fixes (2026-09-26): SQLite deletes a file at a
    database's -wal, -shm or -journal the next time it opens the database
    (measured), and takes a -journal for a hot journal at once. On a scratch
    install `--live --backup <record>-journal` wrote and verified the
    backup, then the migration's own open of the record deleted it: exit 0,
    the record migrated, no backup anywhere. -wal and -shm mangled it, and
    `--rehearse --scratch <record>-journal` lost its copy the same way. Only
    --report was held to the rule. Each is refused now, before anything is
    done; so is the backup door, for every caller."""
    path = tmp_path / "gridiron.db"
    conn = _a_record(path, plant, tool)
    schema = _master(conn)
    conn.close()
    _as_the_record(monkeypatch, path)
    _release_is_this_tree(monkeypatch, tool)
    copy = tmp_path / "copy.db"
    db.back_up(path, copy, "a scratch copy of the stand-in")
    for argv, flag, named in (
            (["--database", str(path), "--live", "--backup", str(path) + "-journal"],
             "--backup", "journal"),
            (["--database", str(path), "--live", "--backup", str(path) + "-wal"],
             "--backup", "wal"),
            (["--database", str(path), "--live", "--backup", str(path) + "-shm"],
             "--backup", "shm"),
            (["--database", str(path), "--rehearse", "--scratch", str(path) + "-journal"],
             "--scratch", "journal"),
            (["--database", str(copy), "--rehearse", "--scratch", str(copy) + "-wal"],
             "--scratch", "wal"),
            (["--database", str(copy), "--rehearse", "--scratch", str(path) + "-journal"],
             "--scratch", "journal"),
            (["--database", str(copy), "--rehearse", "--scratch", str(path)],
             "--scratch", "itself")):
        with pytest.raises(SystemExit) as refused:
            tool.main(argv)
        assert refused.value.code == 2, argv
        out = capsys.readouterr().out
        assert f"REFUSED: {flag}" in out and named in out, (argv, out)
        # SQLite's own -wal and -shm may be there; no copy of ours may be.
        for beside in (path, copy):
            assert not Path(str(beside) + "-journal").exists(), argv
            for suffix in ("-wal", "-shm"):
                kept = Path(str(beside) + suffix)
                assert not kept.exists() or not _is_a_database(kept), (argv, kept)
    conn = db.read_only(path, "the stand-in, after every refused sidecar")
    try:
        assert _master(conn) == schema, "the record was migrated"
    finally:
        conn.close()
    for target in (str(copy) + "-journal", str(path) + "-wal"):
        with pytest.raises(db.LiveRecordTouched, match="A BACKUP IS A FILE OF ITS OWN"):
            db.back_up(copy, target, "a backup beside a database, refused")


# --- 2. the live record is known by the file's identity, from anywhere -------

def test_the_record_is_known_by_its_identity_whatever_runs_the_tool(
        tmp_path, plant, tool, monkeypatch, capsys):
    """The review ran the tool from a worktree (GRIDIRON_HOME there, so its
    configured record was another file) and through a hard link: the record
    was "not the record", and without --live it was migrated in place with
    no backup. Here the stand-in is the MAIN worktree's record, and this
    process's settings name another file."""
    main = tmp_path / "main"
    (main / "var").mkdir(parents=True)
    record = main / "var" / "gridiron.db"
    conn = _a_record(record, plant, tool)
    schema = _master(conn)
    conn.close()
    elsewhere = tmp_path / "worktree" / "var" / "gridiron.db"
    monkeypatch.setattr(config, "DB_PATH", elsewhere)
    monkeypatch.setattr(config, "DEFAULT_DB", elsewhere)
    monkeypatch.setattr(db, "the_main_worktree", lambda: main, raising=False)
    linked = tmp_path / "another-name.db"
    os.link(record, linked)
    for name in (record, linked, tmp_path / "main" / "var" / ".." / "var" / "gridiron.db"):
        with pytest.raises(SystemExit) as refused:
            tool.main(["--database", str(name)])
        assert refused.value.code == 2, name
        assert "is the operator's record" in capsys.readouterr().out, name
    copy = tmp_path / "copy.db"
    db.back_up(record, copy, "a copy of the stand-in, which is not the record")
    with pytest.raises(SystemExit):
        tool.main(["--database", str(copy), "--live", "--backup",
                   str(tmp_path / "b.db")])
    assert "is not it" in capsys.readouterr().out
    conn = db.read_only(record, "the stand-in, after the refusals")
    try:
        assert _master(conn) == schema, "the record was migrated without --live"
    finally:
        conn.close()
    assert not (tmp_path / "b.db").exists()


def test_the_migration_and_the_prompt_reconstruction_ask_one_door():
    """"Exactly as tools/reconstruct_prompts.py does": both tools ask
    `db.is_the_live_record_file`, so the rule is written once."""
    source = (REPO / "tools" / "migrate_2026_09_25_behaviour.py").read_text(
        encoding="utf-8")
    other = (REPO / "tools" / "reconstruct_prompts.py").read_text(encoding="utf-8")
    assert "db.is_the_live_record_file(path)" in source
    assert "db.is_the_live_record_file(path)" in other
    assert "config.DB_PATH).resolve()" not in source


# --- 3. with --live, the definitions are the release's or nothing is done ----

@pytest.mark.parametrize("changed, named", [
    ({"gridiron__schema.sql": lambda text: text.replace(
        "('numbered', 'fight_night', 'contender')",
        "('numbered', 'fight_night')")},
     ["ufc_events: its CREATE text is not the release's", "schema.sql"]),
    ({"gridiron__schema.sql": lambda text: text.replace(
        "one look of '\n        || 'each kind per forecast, written once'",
        "one look of each kind'")},
     ["market_snapshots: trigger market_snapshots_never_replaced is not the "
      "release's"]),
    ({"gridiron__schema.sql": lambda text: text + "\n-- a line the release has\n"},
     ["is not master's gridiron/schema.sql"]),
    ({"gridiron__market__lines.py": lambda text: text.replace(
        '"2d0e98f",\n)', '"0000000",\n)')},
     ["lines.SNAPSHOT_REBUILD"]),
], ids=["a table's CHECK", "a trigger", "the file outside the eight",
        "the map's snapshot entry"])
def test_live_refuses_definitions_that_are_not_the_release(
        tmp_path, plant, tool, monkeypatch, capsys, changed, named):
    """The review: the "released definitions" were whatever schema.sql the
    running checkout held, and nothing checked them against the release.
    With --live the tool reads master's schema.sql and lines.py through git
    and refuses, by name, before the backup, unless what it would write is
    exactly the release's."""
    path = tmp_path / "gridiron.db"
    conn = _a_record(path, plant, tool)
    schema = _master(conn)
    conn.close()
    _as_the_record(monkeypatch, path)
    _release_is_this_tree(monkeypatch, tool, **changed)
    for key in changed:
        text = (REPO / key.replace("__", "/")).read_text(encoding="utf-8")
        assert changed[key](text) != text, "the planted release is this tree"
    backup = tmp_path / "before.db"
    with pytest.raises(SystemExit) as refused:
        tool.main(["--database", str(path), "--live", "--backup", str(backup)])
    assert refused.value.code == 2
    out = capsys.readouterr().out
    assert "REFUSED: --live writes the RELEASED definitions" in out
    for words in named:
        assert words in out, (words, out)
    assert not backup.exists()
    conn = db.read_only(path, "the stand-in, after a refused --live")
    try:
        assert _master(conn) == schema
    finally:
        conn.close()


def test_the_release_is_read_from_the_branch_master_through_git(
        tmp_path, tool, monkeypatch):
    """The reader itself, on a scratch repository: master's file as git
    holds it, whatever the working tree says; no master, refused by name."""
    repo = tmp_path / "repo"
    (repo / "gridiron").mkdir(parents=True)

    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True,
                       capture_output=True)

    git("init", "-q")
    git("symbolic-ref", "HEAD", "refs/heads/master")
    (repo / "gridiron" / "schema.sql").write_text("-- as released\n",
                                                   encoding="utf-8")
    git("add", "gridiron/schema.sql")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "r")
    (repo / "gridiron" / "schema.sql").write_text("-- as edited since\n",
                                                   encoding="utf-8")
    monkeypatch.setattr(tool, "REPO", repo)
    assert tool._released_file("gridiron/schema.sql").replace("\r\n", "\n") \
        == "-- as released\n"
    monkeypatch.setattr(tool, "RELEASED_BRANCH", "no-such-branch-2026-09-25")
    with pytest.raises(SystemExit) as refused:
        tool._released_file("gridiron/schema.sql")
    assert refused.value.code == 2


# --- 5. the replace rule comes with the snapshot table ----------------------

def test_the_migrated_snapshot_table_refuses_a_replacing_insert(
        tmp_path, plant, tool):
    """INSERT OR REPLACE removed a stored snapshot round the delete rule
    (the review of 3603300). The migration's definition of the table carries
    `market_snapshots_never_replaced`, so the rebuilt table refuses it."""
    definition = rebuild.released_definitions(["market_snapshots"])["market_snapshots"]
    assert "market_snapshots_never_replaced" in {n for _k, n, _s in definition.dependants}
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    assert tool.main(["--database", str(path)]) == 0
    conn = db.connect(path)
    try:
        before = [tuple(r) for r in conn.execute(
            "SELECT id, prediction_id, kind, fetched_utc FROM market_snapshots"
            " ORDER BY id")]
        pid = before[0][1]
        for statement in (
                "INSERT OR REPLACE INTO market_snapshots (prediction_id,"
                " fetched_utc, source, line, implied_prob, kind) VALUES (?,"
                " '2026-09-01T23:00:00Z', 'test', NULL, 0.5, 'open_at_predict')",
                "INSERT OR REPLACE INTO market_snapshots (id, prediction_id,"
                " fetched_utc, source, line, implied_prob, kind) VALUES ("
                + str(before[0][0]) + ", ?, '2026-09-01T23:00:00Z', 'test', NULL,"
                " 0.5, 'near_start')"):
            with pytest.raises(sqlite3.IntegrityError, match="never replaced"):
                conn.execute(statement, (pid,))
            conn.rollback()
        # A new look of the other kind is still written, plainly.
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " line, implied_prob, kind) VALUES (?, '2026-09-01T23:00:00Z',"
            " 'test', NULL, 0.5, 'near_start')", (pid,))
        conn.commit()
        after = [tuple(r) for r in conn.execute(
            "SELECT id, prediction_id, kind, fetched_utc FROM market_snapshots"
            " ORDER BY id")]
    finally:
        conn.close()
    assert after[:len(before)] == before and len(after) == len(before) + 1


def test_the_migrated_snapshot_table_refuses_an_update_that_replaces(
        tmp_path, plant, tool):
    """The rehearsal of these fixes (2026-09-25): UPDATE OR REPLACE moving
    one snapshot onto another's forecast and look, or onto another's id,
    removed that other row round the delete rule exactly as the replacing
    insert did -- measured on the fixed definitions, the other row went and
    its id became a hole. `market_snapshots_never_replaced_by_update` comes
    with the table and refuses it; and it freezes nothing else (question 6):
    an update that takes no other row's place still lands."""
    definition = rebuild.released_definitions(["market_snapshots"])["market_snapshots"]
    assert "market_snapshots_never_replaced_by_update" in {
        n for _k, n, _s in definition.dependants}
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    assert tool.main(["--database", str(path)]) == 0
    conn = db.connect(path)
    try:
        first, second = [tuple(r) for r in conn.execute(
            "SELECT id, prediction_id FROM market_snapshots ORDER BY id LIMIT 2")]
        later = conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " line, implied_prob, kind) VALUES (?, '2026-09-01T23:00:00Z',"
            " 'test', NULL, 0.5, 'near_start')", (first[1],)).lastrowid
        conn.commit()

        def rows():
            return [tuple(r) for r in conn.execute(
                "SELECT id, prediction_id, kind, fetched_utc, implied_prob"
                " FROM market_snapshots ORDER BY id")]

        stored = rows()
        for statement in (
                f"UPDATE OR REPLACE market_snapshots SET kind = 'open_at_predict'"
                f" WHERE id = {later}",
                f"UPDATE OR REPLACE market_snapshots SET id = {second[0]}"
                f" WHERE id = {first[0]}",
                f"UPDATE OR REPLACE market_snapshots SET prediction_id = {second[1]},"
                f" kind = 'open_at_predict' WHERE id = {later}"):
            with pytest.raises(sqlite3.IntegrityError, match="never replaced"):
                conn.execute(statement)
            conn.rollback()
            assert rows() == stored, statement
        # NOTHING ELSE IS FROZEN: question 6 is open, and this rule is not it.
        conn.execute(f"UPDATE market_snapshots SET implied_prob = 0.25 WHERE id = {later}")
        conn.commit()
        assert [r[4] for r in rows() if r[0] == later] == [0.25]
    finally:
        conn.close()


# --- 7. the checksum sees every stored value; the backup, every object ------

#: Values `quote()` could not tell apart, and their neighbours, as SQL.
EDGE_VALUES = ("-0.0", "0.0", "0", "'0'", "'a' || char(0) || 'b'",
               "'a' || char(0) || 'c'", "'a'", "x'61'", "x'00ff10'", "x'00ff11'",
               "9223372036854775807", "-9223372036854775808",
               "9223372036854775806", "NULL", "''", "x''")


def test_the_checksum_tells_every_stored_value_apart(tmp_path):
    """On a scratch table whose column has no affinity, so each value is
    stored exactly as given (-0.0 included: a REAL column would store it as
    the integer 0). The first checksum hashed `quote()`, under which -0.0
    and 0.0 are both 0.0 and a text ends at its first NUL."""
    conn = db.connect(tmp_path / "values.db")
    try:
        conn.execute("CREATE TABLE t (v)")
        conn.execute("INSERT INTO t (v) VALUES (NULL)")
        conn.commit()
        seen = {}
        for value in EDGE_VALUES:
            conn.execute(f"UPDATE t SET v = {value}")
            if value == "-0.0":
                stored = conn.execute("SELECT v FROM t").fetchone()[0]
                assert struct.pack(">d", stored) == b"\x80" + bytes(7), \
                    "the scratch table did not keep the sign of zero"
            seen[value] = rebuild.column_checksums(conn, "t")[1]["v"]
    finally:
        conn.close()
    clashes = [(a, b) for i, a in enumerate(EDGE_VALUES) for b in EDGE_VALUES[i + 1:]
               if seen[a] == seen[b]]
    assert clashes == [], f"stored values the checksum cannot tell apart: {clashes}"


def test_a_copy_that_changes_a_text_after_its_nul_fails_verification(
        tmp_path, plant, tool, monkeypatch):
    path = tmp_path / "record.db"
    conn = _a_record(path, plant, tool)
    conn.execute("UPDATE nba_injuries SET detail = 'ankle' || char(0) || 'left'"
                 " WHERE player_id = 6430")
    conn.commit()
    tables = _tables(tool)
    schema = _master(conn)
    copy = rebuild._copy_rows

    def after_the_nul(c, table, aside, columns, with_rowid):
        copy(c, table, aside, columns, with_rowid)
        if table == "nba_injuries":
            c.execute("UPDATE nba_injuries SET detail = 'ankle' || char(0) ||"
                      " 'right' WHERE player_id = 6430")

    monkeypatch.setattr(rebuild, "_copy_rows", after_the_nul)
    definitions = rebuild.released_definitions(tables)
    with pytest.raises(rebuild.TableFailedVerification, match="detail"):
        rebuild.rebuild_tables(conn, [definitions[t] for t in tables])
    assert _master(conn) == schema
    conn.close()


def test_a_backup_whose_schema_differs_from_its_source_is_refused(
        tmp_path, plant, tool, monkeypatch):
    """Every table equal, and an index and a trigger not: the first backup
    verified it, and a restore would have brought the record back without
    the rule. Every sqlite_master row is compared now, byte for byte."""
    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    real = db.back_up

    def a_copy_with_other_rules(source, target, why, *, then=None):
        def tampered(original):
            copy = db.connect(target)
            copy.execute("DROP INDEX snap_pred")
            copy.execute("CREATE INDEX snap_pred ON market_snapshots (fetched_utc)")
            copy.execute("DROP TRIGGER market_snapshots_no_delete")
            copy.commit()
            copy.close()
            then(original)
        return real(source, target, why, then=tampered)

    monkeypatch.setattr(db, "back_up", a_copy_with_other_rules)
    with pytest.raises(rebuild.BackupFailedVerification) as failed:
        rebuild.verified_backup(path, tmp_path / "copy.db", "a backup, proved")
    assert "index snap_pred" in str(failed.value)
    assert "trigger market_snapshots_no_delete" in str(failed.value)


# --- 8. a sixth sport after the migration repoints nothing ------------------

def test_a_sixth_sport_after_the_migration_repoints_nothing_and_changes_no_row(
        tmp_path, plant, tool, monkeypatch):
    """After the migration, factors, factor_scores and model_fits carry
    "sport IN", so the next declared sport makes `db.init` widen them. It
    renamed each aside with foreign keys on, which repoints every child
    whatever legacy_alter_table says: fit_activations ended up naming the
    dropped `model_fits_narrow` (the review's e8). Simulated here with a
    sixth sport declared in the config and in a copy of schema.sql."""
    from gridiron.model import activation

    path = tmp_path / "record.db"
    _a_record(path, plant, tool).close()
    assert tool.main(["--database", str(path)]) == 0
    conn = db.connect(path)
    activation.bootstrap_incumbents(conn)
    conn.commit()
    fit = conn.execute("SELECT fit_id FROM fit_activations").fetchone()
    assert fit is not None, "the record should hold an activation of its fit"
    conn.close()

    text = db.SCHEMA_PATH.read_text(encoding="utf-8")
    assert text.count("'ufc')") == 6
    sixth = tmp_path / "schema_with_a_sixth_sport.sql"
    sixth.write_text(text.replace("'ufc')", "'ufc','xfl')"), encoding="utf-8")
    monkeypatch.setattr(config, "SPORTS", tuple(config.SPORTS) + ("xfl",))
    monkeypatch.setattr(db, "SCHEMA_PATH", sixth)

    conn = db.connect(path)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        rows = {t: rebuild.column_checksums(conn, t) for t in tables}
        sequence = sorted(tuple(r) for r in conn.execute(
            "SELECT name, seq FROM sqlite_sequence"))
        widened = db.widen_sport_checks(conn)
        assert sorted(w.split(" ")[0] for w in widened) == sorted(
            ("session_seen", "games", "factors", "factor_scores", "model_fits"))
        now = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table in tables:
            for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
                assert fk[2] in now, f"{table} now references {fk[2]}, which is gone"
        assert {fk[2] for fk in conn.execute(
            "PRAGMA foreign_key_list(fit_activations)")} == {"model_fits"}
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert {t: rebuild.column_checksums(conn, t) for t in tables} == rows
        assert sorted(tuple(r) for r in conn.execute(
            "SELECT name, seq FROM sqlite_sequence")) == sequence
        # And the parent is really there to write against, with foreign keys on.
        activation.activate_incumbent(conn, fit[0], reason="a second incumbent row, "
                                      "written after the sixth sport to prove the key")
        conn.commit()
        for table in ("factors", "factor_scores", "model_fits", "games", "session_seen"):
            assert "'xfl'" in conn.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0]
    finally:
        conn.close()


# --- note 9: the backup is one instant, and the run says so ----------------

def test_the_live_run_says_what_the_backup_does_not_hold(
        tmp_path, plant, tool, monkeypatch, capsys):
    path = tmp_path / "gridiron.db"
    _a_record(path, plant, tool).close()
    _as_the_record(monkeypatch, path)
    _release_is_this_tree(monkeypatch, tool)
    assert tool.main(["--database", str(path), "--live", "--backup",
                      str(tmp_path / "before.db")]) == 0
    out = capsys.readouterr().out
    assert "THE BACKUP IS ONE INSTANT" in out
    assert "THE BACKUP IS NOT THE RECORD AS MIGRATED" in out
    assert "quiet hour" in out


def test_a_rehearsal_does_not_say_its_copy_lost_rows(
        tmp_path, plant, tool, monkeypatch, capsys):
    """The rehearsal of these fixes (2026-09-25): a --rehearse printed THE
    BACKUP IS NOT THE RECORD AS MIGRATED -- rows "in the migrated record and
    not in the backup" -- of a scratch copy it had just migrated, which no
    task writes. Note 9 is about the live record, and is said on that run."""
    path = tmp_path / "gridiron.db"
    _a_record(path, plant, tool).close()
    _as_the_record(monkeypatch, path)
    assert tool.main(["--database", str(path), "--rehearse", "--scratch",
                      str(tmp_path / "rehearsal.db")]) == 0
    out = capsys.readouterr().out
    assert "COMMITTED" in out and "THE BACKUP IS ONE INSTANT" in out
    assert "THE BACKUP IS NOT THE RECORD AS MIGRATED" not in out
