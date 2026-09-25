"""Schema ruling 6 of 2026-09-24: one way into a database file.

"Add a scan that refuses a raw sqlite3.connect to the live record path outside
the approved handles, with a planting." A scan of the source cannot know which
file a call will open, so it refuses every raw open outside `db.connect`, and
the doors built on `connect` are the approved handles: `db.read_only`,
`db.read_the_live_record` and `db.back_up_the_live_record`. Built 2026-09-25.
The planting is `plant.py::plant_a_raw_connect_past_the_door`.
"""
from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path

import pytest

from gridiron import audit, config, db


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    """A package with whatever files are named beside it; its root."""
    (tmp_path / "gridiron").mkdir()
    (tmp_path / "gridiron" / "__init__.py").write_text("", encoding="utf-8")
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
    return tmp_path / "gridiron"


def test_the_real_tree_opens_no_database_raw():
    audit.check_no_raw_connect_to_the_live_record()


def test_every_spelling_of_a_raw_open_is_named(tmp_path):
    root = _tree(tmp_path, {
        "gridiron/views.py": """
            import sqlite3
            from sqlite3 import connect as opener, Connection

            def plain():
                return sqlite3.connect("x.db")

            def aliased():
                return opener("x.db")

            def handed_on(factory=sqlite3.connect):
                return factory

            def constructed():
                return Connection("x.db")

            def reached():
                return getattr(sqlite3, "connect")
            """,
        "tools/reader.py": """
            def inside():
                import sqlite3.dbapi2 as d
                return d.connect("x.db")
            """,
        "tests/test_reader.py": """
            import sqlite3 as s

            def test_it():
                s.dbapi2.connect(":memory:")
            """,
        "desktop/other.py": "import apsw\n",
    })
    faults = audit.raw_connect_faults(root)
    for where in ("gridiron/views.py", "(plain)", "(aliased)", "(handed_on)",
                  "(constructed)", "(reached)", "tools/reader.py", "(inside)",
                  "tests/test_reader.py", "(test_it)", "desktop/other.py"):
        assert any(where in f for f in faults), (where, faults)
    assert len(faults) == 8, faults


def test_a_star_import_and_the_driver_underneath_are_named(tmp_path):
    """TWO MORE SPELLINGS (2026-09-25, found proving the ruling 6 build).
    `from sqlite3 import *` brings `connect` in under a bare name that no
    import line shows, and `_sqlite3` is the C driver `sqlite3` wraps; both
    opened a database past the first version of the scan. Each is refused at
    its import. A module named at run time (`importlib.import_module`,
    `__import__`) stays out of a static scan's reach (FOLLOWUPS)."""
    root = _tree(tmp_path, {
        "gridiron/views.py": """
            from sqlite3 import *

            def starred():
                return connect("x.db")
            """,
        "tools/under.py": """
            def underneath():
                import _sqlite3
                return _sqlite3.connect("x.db")
            """,
        "tests/test_under.py": """
            from _sqlite3 import connect as c

            def test_it():
                c(":memory:")
            """,
    })
    faults = audit.raw_connect_faults(root)
    assert any(f.startswith("gridiron/views.py:2 (module level)")
               and "imports * from sqlite3" in f for f in faults), faults
    assert any(f.startswith("tools/under.py:") and "(underneath)" in f
               and "_sqlite3" in f for f in faults), faults
    assert any(f.startswith("tests/test_under.py:2 (module level)")
               and "_sqlite3" in f for f in faults), faults
    assert len(faults) == 3, faults


def test_a_type_an_error_and_a_row_factory_are_not_opens(tmp_path):
    root = _tree(tmp_path, {"gridiron/uses.py": """
        import sqlite3
        from sqlite3 import Connection

        def reads(conn: sqlite3.Connection, other: Connection) -> None:
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("SELECT 1")
            except sqlite3.Error:
                pass
            # sqlite3.connect is named here, in a comment, and nowhere else
            return isinstance(other, sqlite3.Connection)
        """})
    assert audit.raw_connect_faults(root) == []


def test_only_the_connection_factory_itself_may_open_raw(tmp_path):
    root = _tree(tmp_path, {"gridiron/db.py": """
        import sqlite3

        def connect(path):
            return sqlite3.connect(path)

        def another(path):
            return sqlite3.connect(path)
        """})
    faults = audit.raw_connect_faults(root)
    assert [f.split(" ")[0] for f in faults] == ["gridiron/db.py:8"], faults
    assert "(another)" in faults[0]


def test_an_exemption_names_a_file_and_a_function(tmp_path, monkeypatch):
    root = _tree(tmp_path, {"tools/keep.py": """
        import sqlite3

        def kept():
            return sqlite3.connect("x.db")
        """})
    assert len(audit.raw_connect_faults(root)) == 1
    monkeypatch.setitem(audit.RAW_CONNECT_EXEMPT, "tools/keep.py:kept",
                        "2026-09-25: a reason, for the test")
    assert audit.raw_connect_faults(root) == []


def test_the_read_only_door_opens_any_file_and_cannot_write(tmp_path):
    path = tmp_path / "some.db"
    conn = db.connect(path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    with pytest.raises(db.LiveRecordTouched, match="NEEDS A REASON"):
        db.read_only(path, "short")
    read = db.read_only(path, "reading a scratch file, to prove the door")
    try:
        assert read.execute("SELECT x FROM t").fetchone()["x"] == 1
        read.execute("PRAGMA query_only = OFF")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            read.execute("INSERT INTO t VALUES (2)")
    finally:
        read.close()


def test_the_backup_door_copies_the_record_and_never_over_it(tmp_path, monkeypatch):
    record = tmp_path / "gridiron.db"
    conn = db.connect(record)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('kind', 'live')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "DB_PATH", record)
    copy = db.back_up_the_live_record(
        tmp_path / "copies" / "record.db", "proving the backup door copies")
    got = db.connect(copy)
    try:
        assert got.execute("SELECT value FROM meta").fetchone()[0] == "live"
    finally:
        got.close()
    if db._LIVE_PATH is None:
        pytest.skip("this deployment has no file-backed record")
    # Refused before anything is opened: the target resolves to the record.
    with pytest.raises(db.LiveRecordTouched, match="A BACKUP MAY NOT"):
        db.back_up_the_live_record(db._LIVE_PATH, "a backup over its own source")
