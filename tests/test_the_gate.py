"""The gate is visible while it runs, and cannot flatter a partial run.

TWO FAILURES THIS CLOSES, both observed rather than imagined:

  * On 2026-09-01 `verify.py` ran the suite with `capture_output=True`, so for
    twenty-eight minutes there was nothing on screen. A slow suite and a hung
    one look identical through a blank terminal, and that cost a wrong call:
    the run was killed as "stuck" on the evidence of a CPU reading, and it was
    healthy, and had in fact just passed.

  * Earlier the same week the suite was split in two to fit a timeout. Both
    halves passed. The whole suite failed. The split was never declared, so
    nothing in the output said which half had not been run.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _verify():
    spec = importlib.util.spec_from_file_location(
        "gridiron_verify", REPO / "tools" / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_skipped_tier_is_never_a_pass():
    """THE POINT OF THE WHOLE PHASE.

    Every step that ran passed. A tier did not run. That is not a pass, and
    the exit code has to say so -- a green summary is carried into a commit
    message that outlives the memory of which tier produced it.
    """
    verify = _verify()
    code, lines = verify.summarise(
        {"1. test suite": True, "2. planted violations": True}, ["browser"])
    assert code != 0, "a skipped tier was reported as a pass"
    assert any("INCOMPLETE" in line for line in lines)


def test_the_skipped_tier_is_named_not_merely_counted():
    """"a tier was skipped" tells you to worry; naming it tells you what."""
    verify = _verify()
    _, lines = verify.summarise({"2. planted violations": True}, ["browser"])
    joined = "\n".join(lines)
    assert "browser" in joined
    assert verify.TIERS["browser"] in joined


def test_every_way_of_skipping_has_a_name():
    """A tier the summary cannot name would print as an empty accusation."""
    verify = _verify()
    for tier in ("browser", "slow", "tests", "end to end"):
        assert tier in verify.TIERS, f"{tier} can be skipped but has no description"
        assert verify.TIERS[tier].strip()


def test_a_full_run_that_passes_is_a_pass():
    """The guard must not be so eager that it fails a clean run."""
    verify = _verify()
    code, lines = verify.summarise(
        {"1. test suite": True, "2. planted violations": True}, [])
    assert code == 0
    assert not any("INCOMPLETE" in line for line in lines)


def test_a_full_run_that_fails_is_still_a_failure():
    verify = _verify()
    code, _ = verify.summarise(
        {"1. test suite": False, "2. planted violations": True}, [])
    assert code != 0


def test_the_suite_is_not_run_with_its_output_captured():
    """Progress you cannot see is progress you end up guessing about.

    Asserted against the CALL, not the text. The first version of this test
    searched the source for "capture_output" and failed immediately -- on the
    docstring above `step_1_tests`, which explains why capturing was removed.
    A scan that cannot tell code from prose about code is the defect this
    project has met four times in other guards; here it took one run to
    reappear.
    """
    import ast

    tree = ast.parse((REPO / "tools" / "verify.py").read_text(encoding="utf-8"))
    step = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "step_1_tests")
    for node in ast.walk(step):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            assert keyword.arg != "capture_output", (
                "the test suite's output is captured again, so a slow run and "
                "a hung one will look identical from outside"
            )


# ---------------------------------------------------------------------------
# THE GATE READS THE LIVE RECORD, NEVER WRITES IT (operator ruling 2026-09-24)
#
# On 24 September a gate run from a worktree created a trigger on the
# operator's record before its code merged. The plantings in
# `tools/guards/plant.py` drive `verify.main` against a stand-in; these hold
# the pieces to their own contracts, each on a scratch file.
# ---------------------------------------------------------------------------

def _a_record_at(path: Path) -> Path:
    """A small record at an OLD schema: one table, one row, in WAL."""
    import sqlite3

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO meta (key, value) VALUES ('kind', 'live')")
    conn.commit()
    conn.close()
    return path


def test_a_schema_change_is_named_object_by_object():
    verify = _verify()
    before = {("table", "games"): "CREATE TABLE games (id)",
              ("trigger", "old"): "CREATE TRIGGER old ..."}
    after = {("table", "games"): "CREATE TABLE games (id, sport)",
             ("table", "recommendation_voids"): "CREATE TABLE ..."}
    assert verify.schema_changes(before, after) == [
        "table games was redefined",
        "table recommendation_voids was created",
        "trigger old was dropped",
    ]
    assert verify.schema_changes(after, dict(after)) == []


def test_an_added_column_changes_the_recorded_schema(tmp_path):
    """A migration that only adds a column is still a schema change."""
    import sqlite3

    verify = _verify()
    conn = sqlite3.connect(str(_a_record_at(tmp_path / "r.db")))
    before = verify.record_schema(conn)
    conn.execute("ALTER TABLE meta ADD COLUMN note TEXT")
    assert verify.schema_changes(before, verify.record_schema(conn)) == [
        "table meta was redefined"]
    conn.close()


def test_the_gate_reads_a_migrated_copy_and_leaves_the_record_alone(
        tmp_path, monkeypatch):
    """One copy, backed up through the read-only door and migrated in the
    temp directory: the checks see the tree's tables, the record does not."""
    from gridiron import config

    verify = _verify()
    record = _a_record_at(tmp_path / "gridiron.db")
    monkeypatch.setattr(config, "DB_PATH", record)
    before = verify._the_live_schema()

    copy = verify._gate_copy_path()
    try:
        assert copy != record
        conn = verify._record_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"recommendation_voids", "predictions"} <= tables
        assert conn.execute(
            "SELECT value FROM meta WHERE key = 'kind'").fetchone()[0] == "live"
        assert verify._gate_copy_path() == copy, "a second backup was made"
    finally:
        folder = verify._GATE_COPY["folder"]
        verify._drop_the_gate_copy()
    assert not folder.exists(), "the gate left its copy behind"
    assert verify.schema_changes(before, verify._the_live_schema()) == []
    assert verify.the_record_is_as_found(before) is True


def test_a_schema_change_during_the_gate_fails_it_by_name(
        tmp_path, monkeypatch, capsys):
    import sqlite3

    from gridiron import config

    verify = _verify()
    record = _a_record_at(tmp_path / "gridiron.db")
    monkeypatch.setattr(config, "DB_PATH", record)
    found = verify._the_live_schema()
    conn = sqlite3.connect(str(record))
    conn.execute("CREATE TRIGGER recommendation_close_cites_its_own_priced_read"
                 " BEFORE DELETE ON meta BEGIN SELECT 1; END")
    conn.commit()
    conn.close()
    assert verify.the_record_is_as_found(found) is False
    assert ("FAIL  the live record changed during the gate: trigger "
            "recommendation_close_cites_its_own_priced_read was created"
            in capsys.readouterr().out)


def test_a_step_that_reaches_for_the_live_record_fails_by_name(capsys):
    from gridiron import db

    verify = _verify()

    def planted():
        raise db.LiveRecordTouched("VERIFICATION MAY NOT OPEN THE LIVE RECORD. x")

    assert verify._refused_by_name(planted) is False
    assert "FAIL  VERIFICATION MAY NOT OPEN THE LIVE RECORD" in capsys.readouterr().out


def test_the_read_door_cannot_be_switched_back_to_writing(tmp_path, monkeypatch):
    """`query_only` is a setting its holder can turn off; `mode=ro` is not."""
    import sqlite3

    from gridiron import config, db

    record = _a_record_at(tmp_path / "gridiron.db")
    monkeypatch.setattr(config, "DB_PATH", record)
    conn = db.read_the_live_record("proving the door stays shut when asked")
    try:
        conn.execute("PRAGMA query_only = OFF")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TABLE planted (x INTEGER)")
    finally:
        conn.close()


def test_the_read_door_creates_no_record_where_there_was_none(
        tmp_path, monkeypatch):
    import sqlite3

    from gridiron import config, db

    missing = tmp_path / "var" / "gridiron.db"
    monkeypatch.setattr(config, "DB_PATH", missing)
    with pytest.raises(sqlite3.OperationalError):
        db.read_the_live_record("reading a record that is not there")
    assert not missing.exists()
    assert not missing.parent.exists()


def test_verification_may_not_attach_the_live_record():
    """The gate's step 3 attached the record, writable, on every run."""
    import sqlite3

    from gridiron import config, db

    spec = importlib.util.spec_from_file_location(
        "gridiron_dbcopy", REPO / "tools" / "dbcopy.py")
    dbcopy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dbcopy)
    conn = sqlite3.connect(":memory:")
    try:
        with pytest.raises(db.LiveRecordTouched, match="tried to attach"):
            dbcopy.copy_facts(conn, config.DB_PATH)
        assert conn.execute("PRAGMA database_list").fetchall()[-1][1] == "main"
    finally:
        conn.close()
