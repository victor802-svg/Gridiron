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
import re
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
