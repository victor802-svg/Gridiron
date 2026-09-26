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


def test_every_way_round_the_first_scan_is_named(tmp_path):
    """THE REVIEW OF 3603300 (2026-09-25) opened a database seven ways the
    first scan did not see -- the module bound to another name, a subclass of
    the connection called, the driver imported by name at run time twice,
    `vars`, a `getattr` with a computed name -- and an eighth through a
    helper named `connect` nested in db.py, which the connection factory's
    exemption, keyed on the bare name, let through. Each is named by file
    and QUALIFIED function, and nothing else is."""
    root = _tree(tmp_path, {
        "tools/bypasses.py": """
            import importlib
            import sqlite3
            import sys
            from importlib import import_module as fetch


            def a(path):
                return importlib.import_module("sqlite3").connect(path)


            def b(path):
                return __import__("sqlite3").connect(path)


            def c(path):
                s = sqlite3
                return s.connect(path)


            def d(path):
                return vars(sqlite3)["connect"](path)


            def e(path):
                return getattr(sqlite3, "conn" + "ect")(path)


            class Record(sqlite3.Connection):
                pass


            def f(path):
                return Record(path)


            def g(path):
                return fetch("sqlite3.dbapi2").connect(path)


            def h(path):
                return sys.modules["sqlite3"].connect(path)


            def i(path):
                return sqlite3.__dict__["connect"](path)


            def j(path, maker=sqlite3.Connection):
                return maker(path)
            """,
        "gridiron/db.py": """
            import sqlite3


            def connect(path):
                return sqlite3.connect(path)


            def back_up(source, target):
                def connect(p):
                    return sqlite3.connect(p)
                return connect(target)


            class Factory:
                def connect(self, path):
                    return sqlite3.connect(path)
            """,
    })
    faults = audit.raw_connect_faults(root)
    for where in ("(a) imports `sqlite3` at run time",
                  "(b) imports `sqlite3` at run time",
                  "(c) binds the `sqlite3` module", "(c) opens a database with",
                  "(d) hands the `sqlite3` module on as a value",
                  "(e) reaches an attribute of `sqlite3` through getattr, by a "
                  "name computed",
                  "(module level) subclasses `sqlite3.Connection`",
                  "(f) opens a database by calling `Record`",
                  "(g) imports `sqlite3.dbapi2` at run time",
                  "(h) reaches `sqlite3` through sys.modules",
                  "(i) reads `sqlite3.__dict__`",
                  "(j) hands `sqlite3.Connection` on as a value",
                  "gridiron/db.py:11 (back_up.connect) opens",
                  "(Factory.connect) opens"):
        assert any(where in f for f in faults), (where, faults)
    assert len(faults) == 14, faults
    assert not any("gridiron/db.py:6 " in f for f in faults), \
        "the connection factory itself is the one place a raw open belongs"


def test_the_driver_read_off_another_module_is_named(tmp_path):
    """THE REHEARSAL OF THOSE FIXES (2026-09-25): every module that imports
    sqlite3 holds it as an attribute, and eight shapes opened a database past
    the scan by reading it there -- each measured on a scratch file. Each is
    named now; a type, an error class and an isinstance through another
    module still are not opens."""
    root = _tree(tmp_path, {
        "tools/through.py": """
            import sys

            import gridiron.db
            from gridiron import db
            from gridiron.db import sqlite3 as lite


            def h(path):
                return db.sqlite3.connect(path)


            def i(path):
                return lite.connect(path)


            def j(path):
                return gridiron.db.sqlite3.connect(path)


            def k(path):
                return vars(db)["sqlite3"].connect(path)


            def m(path):
                return getattr(db, "sqlite3").connect(path)


            def n(path):
                return db.__dict__["sqlite3"].connect(path)


            def o(path):
                return sys.modules["gridiron.db"].sqlite3.connect(path)


            def p(path):
                return vars(db).get("sqlite3").connect(path)


            def q(conn: db.sqlite3.Connection) -> bool:
                try:
                    conn.execute("SELECT 1")
                except db.sqlite3.Error:
                    pass
                return isinstance(conn, db.sqlite3.Connection)
            """,
        "gridiron/db.py": """
            import sqlite3


            def connect(path):
                return sqlite3.connect(path)
            """,
    })
    faults = audit.raw_connect_faults(root)
    for name in "hijkmnop":
        assert any(f"({name}) " in f for f in faults), (name, faults)
    assert not any("(q) " in f for f in faults), faults
    assert len(faults) == 8, faults


BY_NAME_THROUGH_ANY_CALL = """
    import builtins
    import importlib
    import importlib.util
    import logging


    def r(path):
        load = importlib.import_module
        return load("sqlite3").connect(path)


    def s(path):
        load = builtins.__import__
        return load("sqlite3").connect(path)


    def t(path):
        return builtins.__dict__["__import__"]("sqlite3").connect(path)


    def u(path):
        return getattr(builtins, "__import__")("sqlite3").connect(path)


    def v(path):
        spec = importlib.util.find_spec("sqlite3")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.connect(path)


    def w(path):
        return importlib.import_module(name="sqlite3").connect(path)


    def x(path):
        logging.getLogger("gridiron.db").info("a raw sqlite3.connect is refused")
        return path
    """


def test_the_driver_fetched_by_name_through_any_call_is_named(tmp_path):
    """THE PROVER OF THOSE FIXES (2026-09-26): the importer was known only by
    the names `import_module` and `__import__` were written with, and only
    with the driver's name as its first positional argument. Six shapes --
    each shown here to open a database -- went past the scan. A constant
    naming the driver handed to any call is named now; a string that merely
    mentions it is not."""
    namespace: dict = {}
    exec(textwrap.dedent(BY_NAME_THROUGH_ANY_CALL), namespace)
    for name in "rstuvw":
        conn = namespace[name](":memory:")
        try:
            assert isinstance(conn, sqlite3.Connection), name
        finally:
            conn.close()
    root = _tree(tmp_path, {"tools/by_name.py": BY_NAME_THROUGH_ANY_CALL})
    faults = audit.raw_connect_faults(root)
    for name in "rstuvw":
        assert any(f"({name}) " in f for f in faults), (name, faults)
    assert not any("(x) " in f for f in faults), faults
    assert len(faults) == 6, faults


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

        def more(conns: list[sqlite3.Connection]) -> dict[str, Connection]:
            held: sqlite3.Connection | None = None
            ok = issubclass(type(held), (sqlite3.Connection, object))
            return {"version": sqlite3.sqlite_version, "ok": ok}
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
