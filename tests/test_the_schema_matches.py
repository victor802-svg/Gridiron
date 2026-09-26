"""The gate's schema diff (schema ruling 1 of 2026-09-24, built 2026-09-25).

The brief: "build a fresh database by migrating from nothing at the released
commit, and compare its schema object by object ... From then on, the gate
runs this diff read-only and fails on any difference." Gate step 2 runs it
twice -- the live record against the release, and the gate's migrated copy
against this tree -- through `audit.check_the_schema_matches`, with the
dated register of the differences ruling 2's migration will clear. These
hold the register, the fresh builds and the step's wiring to their word, on
stand-ins; the plantings hold the check to the record.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

from gridiron import audit, config, db, schema_diff

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def verify():
    module = _load("gridiron_verify_schema", REPO / "tools" / "verify.py")
    yield module
    module._drop_the_gate_copy()


@pytest.fixture(scope="module")
def plant():
    return _load("gridiron_plant_for_schema", REPO / "tools" / "guards" / "plant.py")


def test_every_register_entry_is_dated_and_says_what_clears_it():
    """"Until the migration of ruling 2 has run": each entry names its
    object, its property, the commit the reference's definition came from,
    and what clears it; nothing is registered without a reason."""
    for entry in audit.SCHEMA_DIFFERENCES_REGISTERED:
        assert entry.object.startswith(("table ", "index ", "trigger ", "view "))
        assert entry.property and entry.held_by in ("record", "reference")
        assert entry.released_in
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry.registered), entry
        assert entry.cleared_by.startswith("cleared by ")
        assert set(entry.comparisons) <= set(audit.SCHEMA_COMPARISONS)
    by_ruling_2 = [e for e in audit.SCHEMA_DIFFERENCES_REGISTERED
                   if e.cleared_by == "cleared by the dated migration of ruling 2"]
    tool = _load("gridiron_migrate_for_register",
                 REPO / "tools" / "migrate_2026_09_25_behaviour.py")
    migrated = {table for table, _what, _commit in tool.MIGRATION}
    assert {e.object.split(" ", 1)[1] for e in by_ruling_2} <= migrated, \
        "a difference registered as ruling 2's is in a table it does not rebuild"


def test_a_record_that_matches_passes_and_a_new_difference_fails_by_name(
        tmp_path):
    fresh = tmp_path / "fresh.db"
    db.open_db(fresh).close()
    record = tmp_path / "record.db"
    db.open_db(record).close()
    a = db.read_only(record, "a record that matches, compared")
    b = db.read_only(fresh, "a fresh build, compared")
    try:
        summary = audit.check_the_schema_matches(a, b, "tree", register=())
    finally:
        a.close()
        b.close()
    assert "0 registered difference(s) outstanding" in summary

    conn = db.connect(record)
    conn.execute("CREATE TRIGGER not_in_any_release BEFORE DELETE ON teams"
                 " BEGIN SELECT 1; END")
    conn.commit()
    conn.close()
    a = db.read_only(record, "a record with a trigger of its own, compared")
    b = db.read_only(fresh, "a fresh build, compared")
    try:
        with pytest.raises(audit.LawViolation) as failed:
            audit.check_the_schema_matches(a, b, "tree", register=())
    finally:
        a.close()
        b.close()
    assert ("NEW: trigger not_in_any_release, the whole object: the gate's "
            "migrated copy of the record has it and this tree does not"
            in str(failed.value))


def test_the_register_cannot_outlive_what_it_records(tmp_path):
    fresh = tmp_path / "fresh.db"
    db.open_db(fresh).close()
    stale = audit.RegisteredDifference(
        "table teams", "column is_fbs: default 0", "record", "nowhere",
        ("tree",), "2026-09-25", "cleared by nothing")
    a = db.read_only(fresh, "a record with none of the registered differences")
    b = db.read_only(fresh, "a fresh build, compared")
    try:
        faults, _summary = audit.schema_difference_faults(a, b, "tree", (stale,))
    finally:
        a.close()
        b.close()
    assert faults == [
        "CLEARED, STILL REGISTERED: table teams, column is_fbs: default 0: the "
        "gate's migrated copy of the record has it and this tree does not -- "
        "no longer found (registered 2026-09-25, cleared by nothing). Remove "
        "it from audit.SCHEMA_DIFFERENCES_REGISTERED."]


def test_the_tree_is_built_fresh_in_a_child_exactly_as_it_builds_in_process(
        tmp_path, verify):
    child = verify._this_tree_built_fresh()
    here = tmp_path / "here.db"
    db.open_db(here).close()
    a = db.read_only(child, "this tree built fresh in a child")
    b = db.read_only(here, "this tree built fresh here")
    try:
        master = "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY 1, 2"
        assert a.execute(master).fetchall() == b.execute(master).fetchall()
    finally:
        a.close()
        b.close()


def test_the_release_is_built_from_the_branch_master_and_nothing_else(verify):
    """git archive of master into the temp directory; the child asserts
    that the package it imported is the archive's."""
    fresh, commit = verify._the_release_built_fresh()
    expected = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short=12", "master"],
        capture_output=True, text=True).stdout.strip()
    assert commit == expected
    assert Path(verify._FRESH["folder"]) in fresh.parents
    conn = db.read_only(fresh, "the release built fresh")
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        conn.close()
    assert {"predictions", "market_snapshots", "fit_activations"} <= tables


def test_a_build_that_cannot_be_made_fails_by_name(verify, monkeypatch):
    monkeypatch.setattr(verify, "RELEASED_BRANCH", "no-such-branch-2026-09-25")
    with pytest.raises(verify.FreshBuildFailed, match="git rev-parse"):
        verify._the_release_built_fresh()


def test_the_tree_comparison_on_a_stand_in_passes_then_names_a_new_difference(
        tmp_path, verify, plant, monkeypatch, capsys):
    """The step's own function, on a stand-in named as the record: in the
    live shapes it passes with the register; with a column that lost its
    CHECK it fails, printing every difference, not only the first line."""
    record = tmp_path / "gridiron.db"
    plant._a_record_in_the_live_shapes(
        record, plant._registered_tables("tree")).close()
    monkeypatch.setattr(config, "DB_PATH", record)
    verify._the_schema_matches("tree")
    out = capsys.readouterr().out
    assert "registered difference(s) outstanding" in out
    verify._drop_the_gate_copy()

    conn = db.connect(record)
    plant._reshaped(conn, "session_seen", [plant._SESSION_SEEN_WITHOUT_ITS_CHECK])
    conn.close()
    with pytest.raises(audit.LawViolation):
        verify._the_schema_matches("tree")
    assert ("NEW: table session_seen, column sport: check (sport in ('nfl', "
            "'mlb', 'nba', 'cfb', 'ufc')): this tree has it and the gate's "
            "migrated copy of the record does not" in capsys.readouterr().out)


def test_step_2_runs_both_comparisons_and_names_a_failed_build():
    verify = _load("gridiron_verify_source", REPO / "tools" / "verify.py")
    source = inspect.getsource(verify.step_2_guards)
    assert '_the_schema_matches("release")' in source
    assert '_the_schema_matches("tree")' in source
    assert "FreshBuildFailed" in source


def test_the_normaliser_is_the_one_door():
    """The gate and the migration both ask `schema_diff`; neither carries a
    comparison of its own."""
    rebuild_source = (REPO / "gridiron" / "rebuild.py").read_text(encoding="utf-8")
    audit_source = inspect.getsource(audit.schema_difference_faults)
    assert "schema_diff.table_differences" in rebuild_source
    assert "schema_diff.object_tokens" in rebuild_source
    assert "schema_diff.compare" in audit_source
    # A QUOTED WORD IS A NAME ONLY WHERE ONLY A NAME CAN STAND (2026-09-25):
    # after REFERENCES it is the table; alone, it may be a string.
    assert schema_diff.tokens('-- x\nREFERENCES "A"') == ["references", "a"]
    assert schema_diff.tokens('-- x\n"A"') == ['"A"']
