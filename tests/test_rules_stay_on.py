"""Operator questions 25 and 29, ruled 2026-09-28 (question 29's reading
confirmed 2026-09-29), built 2026-09-29: the gate refuses code that switches
the rules off or rewrites their marks.

Question 25: "yes. The scan also refuses any code that turns the rules off by
connection setting or registers a function under a built-in's name."
Question 29: "folded into Q25's scan: refuse any code that writes
sqlite_sequence, and any multi-row INSERT OR FAIL / OR IGNORE / OR ROLLBACK
on an append-only table. No separate item." -- except `gridiron.rebuild`,
which carries the mark exactly and is the verified rebuild door, named in a
register with its dated reason.

The scan is `audit.rule_switch_faults`, run in the gate as
`audit.check_no_code_switches_the_rules_off_or_rewrites_their_marks`; its
plantings are the six `plant.py::plant_*` named in `test_guards.py`. The
first block below measures, on scratch worlds, that each thing it refuses
does what its reason says; the rest hold the scan to what it reads. And the
two migration copies it found in the shipped code are plain inserts now, to
the same effect -- tested side by side at the end.
"""
from __future__ import annotations

import ast
import sqlite3
import textwrap
from pathlib import Path

import pytest

from gridiron import audit, config, db


# --- what a connection can do to a rule, measured -----------------------------

_RULED = """
    CREATE TABLE rec (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT,
                      added TEXT CHECK (added LIKE '____-__-__T%'));
    CREATE TRIGGER rec_no_delete BEFORE DELETE ON rec
    BEGIN SELECT RAISE(ABORT, 'a record is never removed'); END;
    CREATE TRIGGER rec_is_json AFTER INSERT ON rec WHEN NOT json_valid(NEW.v)
    BEGIN SELECT RAISE(ABORT, 'not json'); END;
    CREATE TABLE guard (flag INTEGER);
    INSERT INTO guard VALUES (1);
    CREATE TABLE picks (id INTEGER PRIMARY KEY, v TEXT);
    CREATE TRIGGER picks_guarded BEFORE INSERT ON picks
    WHEN (SELECT flag FROM guard) = 1
    BEGIN SELECT RAISE(ABORT, 'guarded'); END;
    INSERT INTO rec (v, added) VALUES ('{}', '2026-09-29T00:00:00Z');
"""


def _ruled(path) -> sqlite3.Connection:
    conn = db.connect(path)
    conn.executescript(textwrap.dedent(_RULED))
    conn.commit()
    return conn


def _lands(conn, sql: str, *args) -> bool:
    try:
        conn.execute(sql, args)
        conn.commit()
        return True
    except sqlite3.DatabaseError:
        conn.rollback()
        return False


_A_ROW = "INSERT INTO rec (v, added) VALUES (?, ?)"


def test_with_the_trigger_switch_off_no_rule_runs():
    conn = _ruled(":memory:")
    assert not _lands(conn, "DELETE FROM rec")
    conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, False)
    assert _lands(conn, "DELETE FROM rec"), "no rule ran"
    assert _lands(conn, _A_ROW, "not json", "2026-09-29T00:00:00Z")


def test_recursive_triggers_runs_a_delete_rule_for_a_replaced_row():
    replace = "INSERT OR REPLACE INTO rec (id, v, added) VALUES (1, '[]', '2026-09-29T00:00:01Z')"
    conn = _ruled(":memory:")
    assert _lands(conn, replace), "off, SQLite's default: no delete rule runs"
    conn = _ruled(":memory:")
    conn.execute("PRAGMA recursive_triggers = ON")
    assert not _lands(conn, replace), "on, the delete rule runs"


def test_ignore_check_constraints_stores_what_a_check_refuses():
    conn = _ruled(":memory:")
    assert not _lands(conn, _A_ROW, "{}", "yesterday")
    conn.execute("PRAGMA ignore_check_constraints = ON")
    assert _lands(conn, _A_ROW, "{}", "yesterday")


def test_case_sensitive_like_changes_what_a_like_check_accepts(tmp_path):
    """`factors.added_utc`'s CHECK reads LIKE: measured on the table itself."""
    factor = ("INSERT INTO factors (name, sport, added_utc, rationale)"
              " VALUES ('q25_like', 'nfl', '2026-09-29t00:00:00Z', ?)")
    why = "a rationale long enough to be stored"
    conn = db.open_db(tmp_path / "default.db")
    assert _lands(conn, factor, why)
    conn.close()
    conn = db.open_db(tmp_path / "sensitive.db")
    conn.execute("PRAGMA case_sensitive_like = ON")
    assert not _lands(conn, factor, why)
    conn.close()


@pytest.mark.parametrize("name", ["json_valid", "JSON_VALID", "Json_Valid"])
def test_a_function_under_a_builtins_name_answers_the_rule_in_sqlites_place(name):
    conn = _ruled(":memory:")
    assert not _lands(conn, _A_ROW, "not json", "2026-09-29T00:00:00Z")
    conn.create_function(name, 1, lambda v: 1)
    assert _lands(conn, _A_ROW, "not json", "2026-09-29T00:00:00Z")


def test_trusted_schema_decides_which_functions_a_rule_may_call():
    conn = _ruled(":memory:")
    conn.create_function("json_valid", 1, lambda v: 1)
    conn.execute("PRAGMA trusted_schema = OFF")
    with pytest.raises(sqlite3.OperationalError, match="unsafe use"):
        conn.execute(_A_ROW, ("not json", "2026-09-29T00:00:00Z"))


def test_a_collation_under_a_builtins_name_answers_every_comparison():
    conn = db.connect(":memory:")
    assert conn.execute("SELECT 'a' = 'b' COLLATE NOCASE").fetchone()[0] == 0
    conn.create_collation("NOCASE", lambda a, b: 0)
    assert conn.execute("SELECT 'a' = 'b' COLLATE NOCASE").fetchone()[0] == 1


def test_an_authorizer_hands_a_rules_read_back_as_null():
    conn = _ruled(":memory:")
    assert not _lands(conn, "INSERT INTO picks (v) VALUES ('x')")

    def blind(action, arg1, _arg2, _db, _source):
        if action == sqlite3.SQLITE_READ and arg1 == "guard":
            return sqlite3.SQLITE_IGNORE
        return sqlite3.SQLITE_OK

    conn.set_authorizer(blind)
    assert _lands(conn, "INSERT INTO picks (v) VALUES ('x')")


def test_reverse_unordered_selects_changes_what_a_rule_reads():
    conn = db.connect(":memory:")
    conn.executescript("""
        CREATE TABLE two (id INTEGER PRIMARY KEY, v TEXT);
        INSERT INTO two VALUES (1, 'first'), (2, 'second');
        CREATE TABLE seen (v TEXT);
        CREATE TABLE t (id INTEGER PRIMARY KEY);
        CREATE TRIGGER t_reads_one AFTER INSERT ON t
        BEGIN INSERT INTO seen SELECT v FROM two LIMIT 1; END;
    """)
    conn.execute("INSERT INTO t DEFAULT VALUES")
    conn.execute("PRAGMA reverse_unordered_selects = ON")
    conn.execute("INSERT INTO t DEFAULT VALUES")
    assert [r[0] for r in conn.execute("SELECT v FROM seen ORDER BY rowid")] == [
        "first", "second"]


def test_writable_schema_lets_a_rule_be_removed_by_a_statement_naming_no_rule():
    conn = _ruled(":memory:")
    remove = "DELETE FROM sqlite_master WHERE name = 'rec_no_delete'"
    assert not _lands(conn, remove)
    conn.execute("PRAGMA writable_schema = ON")
    assert _lands(conn, remove)


def test_schema_version_set_back_hides_a_new_rule_from_another_connection(tmp_path):
    path = tmp_path / "v.db"
    a = db.connect(path)
    a.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    a.commit()
    b = db.connect(path)
    b.execute("SELECT * FROM t").fetchall()
    version = a.execute("PRAGMA schema_version").fetchone()[0]
    a.execute("CREATE TRIGGER t_no_delete BEFORE DELETE ON t BEGIN SELECT RAISE(ABORT, 'no'); END")
    a.execute("INSERT INTO t VALUES (1, 'x')")
    a.commit()
    a.execute("PRAGMA writable_schema = ON")
    a.execute(f"PRAGMA schema_version = {version}")
    assert _lands(b, "DELETE FROM t"), "the other connection never ran the new rule"
    a.close()
    b.close()


def test_reset_database_empties_the_record_with_no_rule_run(tmp_path):
    conn = _ruled(tmp_path / "r.db")
    conn.setconfig(sqlite3.SQLITE_DBCONFIG_RESET_DATABASE, True)
    conn.execute("VACUUM")
    conn.setconfig(sqlite3.SQLITE_DBCONFIG_RESET_DATABASE, False)
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0] == 0
    conn.close()


def test_a_stopped_insert_of_several_rows_under_or_fail_leaves_rows_above_the_mark():
    """Question 29's hole, measured: the rows before the failing one stand,
    and SQLite never writes the mark back for a statement that stopped.
    (OR IGNORE and OR ROLLBACK leave none; the ruling names all three.)"""
    def world():
        conn = db.connect(":memory:")
        conn.isolation_level = None          # each statement its own, as SQLite runs it
        conn.executescript("""
            CREATE TABLE p (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT NOT NULL);
            INSERT INTO p (v) VALUES ('a'), ('b');
        """)
        return conn

    def run(conn, sql):
        try:
            conn.execute(sql)
            return True
        except sqlite3.IntegrityError:
            return False

    def state(conn):
        return ([tuple(r) for r in conn.execute("SELECT id, v FROM p")],
                conn.execute("SELECT seq FROM sqlite_sequence").fetchone()[0])

    conn = world()
    assert not run(conn, "INSERT OR FAIL INTO p (v) VALUES ('c'), ('d'), (NULL)")
    assert state(conn) == ([(1, "a"), (2, "b"), (3, "c"), (4, "d")], 2)
    conn = world()
    assert run(conn, "INSERT OR IGNORE INTO p (v) VALUES ('c'), (NULL), ('d')")
    rows, mark = state(conn)
    assert mark >= max(r[0] for r in rows)
    conn = world()
    assert not run(conn, "INSERT OR ROLLBACK INTO p (v) VALUES ('c'), (NULL), ('d')")
    assert state(conn) == ([(1, "a"), (2, "b")], 2)


def _two_rows_and_a_rule(path) -> sqlite3.Connection:
    """A file world, each statement its own: two rows under a mark of 2, a
    no-delete rule, and a rule refusing the value 'bad' after it lands."""
    conn = db.connect(path)
    conn.isolation_level = None
    conn.executescript("""
        CREATE TABLE p (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT NOT NULL);
        CREATE TRIGGER p_no_delete BEFORE DELETE ON p BEGIN SELECT RAISE(ABORT, 'kept'); END;
        CREATE TRIGGER p_refuses AFTER INSERT ON p WHEN NEW.v = 'bad'
        BEGIN SELECT RAISE(ABORT, 'refused'); END;
        INSERT INTO p (v) VALUES ('a'), ('b');
    """)
    return conn


def _refused_inside_a_transaction(conn, sql) -> tuple[list, int]:
    conn.execute("BEGIN")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)
    conn.execute("COMMIT")
    return ([tuple(r) for r in conn.execute("SELECT id, v FROM p")],
            conn.execute("SELECT seq FROM sqlite_sequence").fetchone()[0])


@pytest.mark.parametrize("first", ["DELETE", "WAL"])
def test_journal_mode_off_keeps_a_statement_a_rule_refused(tmp_path, first):
    """The prover's (2026-09-29): with no rollback journal, a statement a rule
    refuses inside a transaction keeps its rows, the refused one among them,
    above the mark -- from a DELETE journal and from a WAL file. WAL, MEMORY
    and TRUNCATE keep the refusal whole."""
    conn = _two_rows_and_a_rule(tmp_path / "off.db")
    conn.execute(f"PRAGMA journal_mode = {first}")
    assert conn.execute("PRAGMA journal_mode = OFF").fetchone()[0] == "off"
    assert _refused_inside_a_transaction(conn, "INSERT INTO p (v) VALUES ('c'), ('bad')") == (
        [(1, "a"), (2, "b"), (3, "c"), (4, "bad")], 2)
    conn.close()
    for kept in ("WAL", "MEMORY", "TRUNCATE"):
        conn = _two_rows_and_a_rule(tmp_path / f"{kept}.db")
        conn.execute(f"PRAGMA journal_mode = {kept}")
        assert _refused_inside_a_transaction(
            conn, "INSERT INTO p (v) VALUES ('c'), ('bad')") == ([(1, "a"), (2, "b")], 2)
        conn.close()


def test_a_rule_raising_fail_stops_a_plain_insert_of_several_rows_part_way():
    """The prover's (2026-09-29): a rule raising FAIL -- a temporary one here,
    as code could create -- stops a plain insert part way, and the rows before
    it stand above the mark, as under OR FAIL."""
    conn = db.connect(":memory:")
    conn.isolation_level = None
    conn.executescript("""
        CREATE TABLE p (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT);
        INSERT INTO p (v) VALUES ('a'), ('b');
        CREATE TEMP TRIGGER p_stops BEFORE INSERT ON main.p WHEN NEW.v = 'stop'
        BEGIN SELECT RAISE(FAIL, 'stopped'); END;
    """)
    with pytest.raises(sqlite3.IntegrityError, match="stopped"):
        conn.execute("INSERT INTO p (v) VALUES ('c'), ('d'), ('stop')")
    assert [tuple(r) for r in conn.execute("SELECT id, v FROM p")] == [
        (1, "a"), (2, "b"), (3, "c"), (4, "d")]
    assert conn.execute("SELECT seq FROM sqlite_sequence").fetchone()[0] == 2


@pytest.mark.parametrize("clause,above_the_mark", [
    ("FAIL", True), ("IGNORE", False), ("ROLLBACK", False), ("ABORT", False), ("", False)])
def test_one_row_under_a_clause_runs_a_rules_insert_of_several_under_it(clause, above_the_mark):
    """The prover's (2026-09-29): SQLite runs a rule's statements under the
    conflict clause of the statement that fired it, so one row under OR FAIL
    into a table whose rule inserts several rows into an append-only one
    stops that insert part way, its rows above the mark."""
    conn = db.connect(":memory:")
    conn.isolation_level = None
    conn.executescript("""
        CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT NOT NULL);
        CREATE TRIGGER records_no_delete BEFORE DELETE ON records
        BEGIN SELECT RAISE(ABORT, 'kept'); END;
        INSERT INTO records (v) VALUES ('a'), ('b');
        CREATE TABLE source (v TEXT);
        INSERT INTO source VALUES ('c'), ('d'), (NULL);
        CREATE TABLE feed (k INTEGER);
        CREATE TRIGGER feed_copies AFTER INSERT ON feed
        BEGIN INSERT INTO records (v) SELECT v FROM source; END;
    """)
    verb = f"INSERT OR {clause}" if clause else "INSERT"
    try:
        conn.execute(f"{verb} INTO feed (k) VALUES (1)")
    except sqlite3.IntegrityError:
        pass
    ids = [r[0] for r in conn.execute("SELECT id FROM records")]
    mark = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'records'").fetchone()[0]
    assert (max(ids) > mark) is above_the_mark, (clause, ids, mark)
    if above_the_mark:
        assert ids == [1, 2, 3, 4] and mark == 2


def test_sqlite_calls_a_function_by_a_quoted_name():
    """The prover's (2026-09-29): so the SQL function that loads an extension
    is read by a quoted name too."""
    conn = db.connect(":memory:")
    for spelled in ('"abs"', "[abs]", "`abs`"):
        assert conn.execute(f"SELECT {spelled}(-1)").fetchone()[0] == 1


@pytest.mark.parametrize("sql", [
    "DELETE FROM 'sqlite_sequence'",
    "UPDATE 'sqlite_sequence' SET seq = 0",
    "INSERT INTO 'sqlite_sequence' (name, seq) VALUES ('x', 1)",
])
def test_sqlite_takes_a_string_literal_as_a_writes_table(sql):
    conn = db.connect(":memory:")
    conn.executescript("CREATE TABLE p (id INTEGER PRIMARY KEY AUTOINCREMENT);"
                       "INSERT INTO p DEFAULT VALUES;")
    assert _lands(conn, sql)


# --- the names are SQLite's own --------------------------------------------------

def test_the_built_in_names_are_read_from_sqlite_itself():
    functions, collations, settings = audit._sqlite_own_names()
    conn = db.connect(":memory:")
    assert functions == {str(r[0]).casefold() for r in conn.execute("PRAGMA function_list")}
    assert collations == {str(r[1]).casefold() for r in conn.execute("PRAGMA collation_list")}
    assert settings == {str(r[0]).casefold() for r in conn.execute("PRAGMA pragma_list")}
    # the ones the schema's rules call, and question 25's two
    assert {"json_valid", "json_extract", "coalesce"} <= functions
    assert {"binary", "nocase", "rtrim"} == collations


def test_every_refused_setting_is_one_sqlite_knows_and_every_switch_is_the_drivers():
    _functions, _collations, settings = audit._sqlite_own_names()
    assert set(audit.RULE_SETTINGS) <= settings
    numbers = audit._dbconfig_numbers()
    assert set(numbers.values()) == set(audit.RULE_DBCONFIG)
    assert numbers == {
        sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER: "SQLITE_DBCONFIG_ENABLE_TRIGGER",
        sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA: "SQLITE_DBCONFIG_TRUSTED_SCHEMA",
        sqlite3.SQLITE_DBCONFIG_WRITABLE_SCHEMA: "SQLITE_DBCONFIG_WRITABLE_SCHEMA",
        sqlite3.SQLITE_DBCONFIG_RESET_DATABASE: "SQLITE_DBCONFIG_RESET_DATABASE",
        sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION: "SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION"}
    assert numbers[1003] == "SQLITE_DBCONFIG_ENABLE_TRIGGER"
    assert set(audit.RULE_SETTINGS).isdisjoint(
        {"foreign_keys", "legacy_alter_table", "query_only", "defer_foreign_keys"})
    # the prover's (2026-09-29): journal_mode, refused at OFF alone -- the
    # schema's own WAL is lawful
    assert set(audit.RULE_SETTING_VALUES) == {"journal_mode"} and set(
        audit.RULE_SETTING_VALUES) <= settings
    assert audit.RULE_SETTING_VALUES["journal_mode"][0] == "OFF"
    assert set(audit.RULE_SETTING_VALUES).isdisjoint(audit.RULE_SETTINGS)


def test_every_value_of_the_audit_holding_a_word_the_scan_looks_for_is_a_holder(monkeypatch):
    """The prover's (2026-09-29): the calls' and the settings' names are held
    by named values, named nowhere but the scan -- proved at import, and a
    new value holding one fails that proof."""
    assert {"_REGISTERING_CALLS", "_RULE_SWITCH_CALLS", "RULE_SETTINGS",
            "RULE_SETTING_VALUES", "SEQUENCE_WRITES_AS_MADE_ON_2026_09_29"} <= set(
        audit._RULE_WORD_HOLDERS)
    audit._check_the_rule_scan_names_the_store_once()
    for held in ("setconfig", ("create_function",), {"journal_mode": 1}):
        monkeypatch.setattr(audit, "_PLANTED_HOLDER", held, raising=False)
        with pytest.raises(audit.LawViolation, match="_PLANTED_HOLDER"):
            audit._check_the_rule_scan_names_the_store_once()
        monkeypatch.delattr(audit, "_PLANTED_HOLDER")


# --- the shipped code and the schema ------------------------------------------

def test_the_shipped_code_and_the_schema_switch_no_rule_off_and_move_no_mark():
    assert audit.rule_switch_faults() == []
    audit.check_no_code_switches_the_rules_off_or_rewrites_their_marks()


def test_the_gate_runs_the_scan_in_step_two():
    source = (config.REPO_ROOT / "tools" / "verify.py").read_text(encoding="utf-8")
    step = next(node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert ("audit.check_no_code_switches_the_rules_off_or_rewrites_their_marks"
            in ast.get_source_segment(source, step))


def test_the_register_holds_the_rebuild_doors_two_statements_and_nothing_else():
    assert set(audit.SEQUENCE_WRITES_REGISTERED) == set(
        audit.SEQUENCE_WRITES_REGISTERED_ON_2026_09_29) == {
        ("gridiron/rebuild.py", "_rebuild_one", "DELETE"),
        ("gridiron/rebuild.py", "_rebuild_one", "INSERT")}
    for reason in audit.SEQUENCE_WRITES_REGISTERED.values():
        assert reason.startswith("2026-09-29: ") and "rebuild" in reason


# --- a world of its own -----------------------------------------------------------

#: `records` has a no-delete rule and `frozen` a no-update rule (both
#: append-only); `cache` and `feed` have none, and a rule on `feed` writes
#: `records`.
_SCHEMA = """
    CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT);
    CREATE TRIGGER IF NOT EXISTS records_no_delete
    BEFORE DELETE ON records
    BEGIN
        SELECT RAISE(ABORT, 'a record is never removed');
    END;
    CREATE TABLE IF NOT EXISTS frozen (id INTEGER PRIMARY KEY, v TEXT);
    CREATE TRIGGER IF NOT EXISTS frozen_no_update
    BEFORE UPDATE OF v ON frozen
    BEGIN
        SELECT RAISE(ABORT, 'moved');
    END;
    CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS feed (k TEXT PRIMARY KEY, v TEXT);
    CREATE TRIGGER IF NOT EXISTS feed_is_recorded
    AFTER INSERT ON feed
    BEGIN
        INSERT INTO records (v) VALUES (NEW.v);
    END;
"""


def _tree(tmp_path: Path, files: dict[str, str], schema: str = _SCHEMA) -> Path:
    (tmp_path / "gridiron").mkdir()
    (tmp_path / "gridiron" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "gridiron" / "schema.sql").write_text(
        textwrap.dedent(schema), encoding="utf-8")
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
    return tmp_path / "gridiron"


def _scan(tmp_path: Path, source: str, schema: str = _SCHEMA) -> list[str]:
    body = "import sqlite3\n\n\ndef f(conn, a, b, t, r, x, v, name, op, flag, clause, verb, what, rows, cb):\n" \
        + textwrap.indent(textwrap.dedent(source), "    ") + "\n"
    return audit.rule_switch_faults(_tree(tmp_path, {"gridiron/mod.py": body}, schema),
                                    register={}, frozen=frozenset())


# --- what the scan reads -------------------------------------------------------------

#: (what it is, Python source inside a function, the words each fault must
#: carry -- one fault per entry; [] for none).
READINGS = [
    # 1. settings
    ("recursive_triggers set", 'conn.execute("PRAGMA recursive_triggers = ON")', ["sets `recursive_triggers`"]),
    ("set to its default too", 'conn.execute("PRAGMA recursive_triggers = 0")', ["sets `recursive_triggers`"]),
    ("case and a schema's prefix", 'conn.execute("pragma MAIN.Recursive_Triggers=1")', ["sets `recursive_triggers`"]),
    ("a comment between the words", 'conn.execute("PRAGMA/* x */recursive_triggers -- y\\n = 1")', ["sets `recursive_triggers`"]),
    ("the call form", 'conn.execute("PRAGMA ignore_check_constraints(1)")', ["sets `ignore_check_constraints`"]),
    ("in executescript", 'conn.executescript("BEGIN; PRAGMA writable_schema = ON; COMMIT;")', ["sets `writable_schema`"]),
    ("a value worked out", 'conn.execute(f"PRAGMA trusted_schema = {v}")', ["sets `trusted_schema`"]),
    ("a value added on", 'conn.execute("PRAGMA reverse_unordered_selects " + v)', ["sets `reverse_unordered_selects`"]),
    ("a value added on, touching", 'conn.execute("PRAGMA reverse_unordered_selects" + v)', ["a setting whose name the scan cannot read"]),
    ("a listed name ending a kept string", 'q = "PRAGMA case_sensitive_like"', ["sets `case_sensitive_like`"]),
    ("schema_version", 'conn.execute("PRAGMA schema_version = 1")', ["sets `schema_version`"]),
    # (the prover, 2026-09-29: the constant argument, a listed name kept in a
    # string with no verb before it, is a setting of its own too)
    ("a template filled in with constants", 'conn.execute("PRAGMA {} = ON".format("recursive_triggers"))', ["a setting whose name the scan cannot read", "sets `recursive_triggers`:", "sets `recursive_triggers` with no verb before it"]),
    ("a name worked out", 'conn.execute(f"PRAGMA {name} = ON")', ["a setting whose name the scan cannot read"]),
    ("a name partly worked out", 'conn.execute(f"PRAGMA recursive_{x} = ON")', ["a setting whose name the scan cannot read"]),
    ("the word alone, kept", 'p = "PRAGMA"', ["a setting whose name the scan cannot read"]),
    ("a read handed whole to execute", 'conn.execute("PRAGMA recursive_triggers").fetchone()', []),
    ("foreign keys are left", 'conn.execute("PRAGMA foreign_keys = OFF")', []),
    ("legacy_alter_table is left", 'conn.execute("PRAGMA legacy_alter_table = ON")', []),
    ("query_only is left", 'conn.execute("PRAGMA query_only = ON")', []),
    ("a formatted argument", 'conn.execute(f"PRAGMA table_info({t})")', []),
    ("in a comment", 'conn.execute("SELECT 1 -- PRAGMA recursive_triggers = ON")', []),
    ("in a literal", "conn.execute(\"SELECT 'PRAGMA recursive_triggers = ON'\")", []),
    ("a docstring", '"""PRAGMA recursive_triggers = ON"""', []),
    # 1. settings -- the prover's (2026-09-29): journal_mode refused at OFF,
    # and a listed name whose verb is worked out, in pieces or kept apart
    ("journal_mode off", 'conn.execute("PRAGMA journal_mode = OFF")', ["sets `journal_mode`: at OFF"]),
    ("journal_mode off, qualified, the call form, a literal", "conn.execute(\"PRAGMA main.journal_mode('off')\")", ["sets `journal_mode`: at OFF"]),
    ("journal_mode at a value worked out", 'conn.execute(f"PRAGMA journal_mode = {v}")', ["sets `journal_mode`: at OFF"]),
    ("journal_mode kept to be finished", 'q = "PRAGMA journal_mode"', ["sets `journal_mode`: at OFF"]),
    ("journal_mode WAL is left", 'conn.execute("PRAGMA journal_mode = WAL")', []),
    ("journal_mode MEMORY is left", 'conn.execute("PRAGMA journal_mode=memory")', []),
    ("journal_mode read", 'conn.execute("PRAGMA journal_mode").fetchone()', []),
    ("a setting's verb worked out", 'conn.execute(verb + " recursive_triggers = 1")', ["sets `recursive_triggers` with no verb before it"]),
    ("a setting's verb in pieces", 'conn.execute(v + "MA ignore_check_constraints(1)")', ["sets `ignore_check_constraints` with no verb before it"]),
    ("a setting kept apart from its verb", 't = "writable_schema = ON"', ["sets `writable_schema` with no verb before it"]),
    ("journal off, its verb apart", 'conn.execute(verb + " journal_mode = off")', ["sets `journal_mode` with no verb before it"]),
    ("journal WAL, its verb apart", 'conn.execute(verb + " journal_mode = WAL")', []),
    ("a setting's name in prose", 'x = "the schema_version, read"', []),
    # 1. switches
    ("the trigger switch off", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, False)", ["`SQLITE_DBCONFIG_ENABLE_TRIGGER` off"]),
    ("by its bare name", "from sqlite3 import SQLITE_DBCONFIG_ENABLE_TRIGGER\nconn.setconfig(SQLITE_DBCONFIG_ENABLE_TRIGGER, 0)", ["`SQLITE_DBCONFIG_ENABLE_TRIGGER` off"]),
    # (the prover, 2026-09-29: a switch is named only off the driver itself)
    ("a bare name not the driver's", "conn.setconfig(SQLITE_DBCONFIG_DEFENSIVE, 0)", ["a connection switch the scan cannot read"]),
    ("the trigger switch under a harmless switch's name", "from sqlite3 import SQLITE_DBCONFIG_ENABLE_TRIGGER as SQLITE_DBCONFIG_DEFENSIVE\nconn.setconfig(SQLITE_DBCONFIG_DEFENSIVE, 0)", ["a connection switch the scan cannot read"]),
    ("a class attribute under a harmless switch's name", "class K:\n    SQLITE_DBCONFIG_DEFENSIVE = 1003\nconn.setconfig(K.SQLITE_DBCONFIG_DEFENSIVE, False)", ["a connection switch the scan cannot read"]),
    ("the driver under another name", "import sqlite3 as lite\nconn.setconfig(lite.SQLITE_DBCONFIG_ENABLE_TRIGGER, False)", ["a connection switch the scan cannot read"]),
    ("the driver's name for a switch rebound", "sqlite3.SQLITE_DBCONFIG_DEFENSIVE = 1003", ["binds `SQLITE_DBCONFIG_DEFENSIVE`"]),
    ("rebound by setattr", 'setattr(sqlite3, "SQLITE_DBCONFIG_DEFENSIVE", 1003)', ["binds a name of the driver's connection switches by `setattr`"]),
    ("a harmless switch off the driver's dbapi2", "conn.setconfig(sqlite3.dbapi2.SQLITE_DBCONFIG_DEFENSIVE, True)", []),
    ("by its number", "conn.setconfig(1003, False)", ["`SQLITE_DBCONFIG_ENABLE_TRIGGER` off"]),
    ("to a value worked out", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, flag)", ["to a value worked out when it runs"]),
    ("a switch worked out", "conn.setconfig(op, False)", ["a connection switch the scan cannot read"]),
    ("the schema writable", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_WRITABLE_SCHEMA, True)", ["`SQLITE_DBCONFIG_WRITABLE_SCHEMA` on"]),
    ("the trusted schema either way", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False)", ["`SQLITE_DBCONFIG_TRUSTED_SCHEMA` off"]),
    ("the reset", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_RESET_DATABASE, 1)", ["`SQLITE_DBCONFIG_RESET_DATABASE` on"]),
    ("extensions allowed", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, True)", ["`SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION` on"]),
    ("the trigger switch on", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, True)", []),
    ("the trigger switch by default", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER)", []),
    ("the schema not writable", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_WRITABLE_SCHEMA, False)", []),
    ("defensive", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)", []),
    ("foreign keys by switch", "conn.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_FKEY, False)", []),
    ("a read of a switch", "conn.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER)", []),
    ("setconfig bound", "turn = conn.setconfig", ["reaches `setconfig` by another name"]),
    ("setconfig by name", 'getattr(conn, "setconfig")(1003, 0)', ["names `setconfig` in a string"]),
    ("an authorizer", "conn.set_authorizer(cb)", ["sets an authorizer"]),
    ("an authorizer taken off", "conn.set_authorizer(None)", []),
    # (the prover, 2026-09-29: a lookup by any string the scan can render)
    ("setconfig in pieces", 'getattr(conn, "set" + "config")(1003, 0)', ["names `setconfig` in a string"]),
    ("setconfig from a template filled in", 'getattr(conn, "{}config".format("set"))(1003, 0)', ["names `setconfig` in a string"]),
    ("setconfig as bytes", 'getattr(conn, b"setconfig".decode())(1003, 0)', ["names `setconfig` in a string"]),
    ("setconfig in capitals, lowered", 'getattr(conn, "SETCONFIG".lower())(1003, 0)', ["names `setconfig` in a string"]),
    ("setconfig partly worked out", 'getattr(conn, f"set{x}")(1003, 0)', ["what could be `setconfig`", "what could be `set_authorizer`"]),
    ("a call in a string handed to exec", 'exec("conn.setconfig(1003, False)")', ["names `setconfig` in a string"]),
    ("a quoted lookup in a string handed to exec", "exec(\"getattr(conn, 'setconfig')(1003, 0)\")", ["names `setconfig` in a string"]),
    ("audit's names of the switching calls", "from gridiron.audit import _RULE_SWITCH_CALLS as calls\ngetattr(conn, calls[0])(1003, 0)", ["names `_RULE_SWITCH_CALLS`"]),
    ("audit's names of the registering calls", "import gridiron.audit as a\ngetattr(conn, next(iter(a._REGISTERING_CALLS)))('json_valid', 1, cb)", ["names `_REGISTERING_CALLS`"]),
    # 2. functions and collations
    ("json_valid", 'conn.create_function("json_valid", 1, lambda v: 1)', ["name `json_valid`, which SQLite lists"]),
    ("by case", 'conn.create_function("JSON_EXTRACT", 2, cb)', ["name `JSON_EXTRACT`, which SQLite lists"]),
    ("by keyword", 'conn.create_function(name="lower", narg=1, func=cb)', ["name `lower`, which SQLite lists"]),
    ("joined constants", 'conn.create_function("json_" + "valid", 1, cb)', ["name `json_valid`, which SQLite lists"]),
    ("an aggregate", 'conn.create_aggregate("sum", 1, cb)', ["name `sum`, which SQLite lists"]),
    ("a window function", 'conn.create_window_function("row_number", 0, cb)', ["name `row_number`, which SQLite lists"]),
    ("a collation", 'conn.create_collation("NoCase", cb)', ["name `NoCase`, which SQLite lists"]),
    ("an operator's function", 'conn.create_function("->>", 2, cb)', ["name `->>`, which SQLite lists"]),
    ("a name worked out", "conn.create_function(name, 1, cb)", ["under a name the scan cannot read"]),
    ("a name partly worked out", 'conn.create_function(f"json_{x}", 1, cb)', ["under a name the scan cannot read"]),
    ("unbound", 'sqlite3.Connection.create_function(conn, "abs", 1, cb)', ["under a name the scan cannot read"]),
    ("bound", "register = conn.create_function", ["reaches `create_function` by another name"]),
    ("looked up", 'getattr(conn, "create_collation")("NOCASE", cb)', ["names `create_collation` in a string"]),
    ("looked up in pieces", 'getattr(conn, "create_" + "function")("json_valid", 1, cb)', ["names `create_function` in a string"]),
    ("a function of its own", 'conn.create_function("gridiron_rank", 1, cb)', []),
    ("a collation of its own", 'conn.create_collation("by_club", cb)', []),
    ("an extension loaded", 'conn.load_extension("x")', ["loads an extension"]),
    ("extensions allowed", "conn.enable_load_extension(True)", ["lets the connection load an extension"]),
    ("extensions allowed, worked out", "conn.enable_load_extension(flag)", ["lets the connection load an extension"]),
    ("extensions refused", "conn.enable_load_extension(False)", []),
    ("an extension from SQL", 'conn.execute("SELECT load_extension(?)", (x,))', ["loads an extension from SQL"]),
    ("an extension from SQL by a quoted name", "conn.execute('SELECT \"load_extension\"(?)', (x,))", ["loads an extension from SQL"]),
    # 3. the sequence store
    ("a delete", 'conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))', ["writes `sqlite_sequence` (DELETE)"]),
    ("an update", 'conn.execute("UPDATE sqlite_sequence SET seq = 0")', ["writes `sqlite_sequence` (UPDATE)"]),
    ("quoted, qualified, by case", 'conn.execute(\'UPDATE main."SQLITE_SEQUENCE" SET seq = 0\')', ["writes `sqlite_sequence` (UPDATE)"]),
    ("bracketed", 'conn.execute("INSERT INTO [sqlite_sequence] (name, seq) VALUES (?, ?)", r)', ["writes `sqlite_sequence` (INSERT)"]),
    ("backticked, under OR REPLACE", 'conn.execute("INSERT OR REPLACE INTO `sqlite_sequence` VALUES (?, ?)", r)', ["writes `sqlite_sequence` (INSERT)"]),
    ("a REPLACE", 'conn.execute("REPLACE INTO sqlite_sequence VALUES (?, ?)", r)', ["writes `sqlite_sequence` (REPLACE)"]),
    ("a string literal for the table", "conn.execute(\"DELETE FROM 'sqlite_sequence'\")", ["writes `sqlite_sequence` (DELETE)"]),
    ("an update under a clause", 'conn.execute("UPDATE OR IGNORE sqlite_sequence SET seq = 0")', ["writes `sqlite_sequence` (UPDATE)"]),
    ("a clause worked out", 'conn.execute(f"UPDATE {clause} sqlite_sequence SET seq = 0")', ["writes `sqlite_sequence` (UPDATE)"]),
    ("a name partly worked out", 'conn.execute(f"DELETE FROM sqlite_{what}")', ["writes `sqlite_sequence` (DELETE)"]),
    ("a verb worked out, FROM", 'conn.execute(f"{verb} FROM sqlite_sequence")', ["writes `sqlite_sequence` (a verb worked out when it runs)"]),
    ("a verb worked out, INTO", 'conn.execute(f"{verb} INTO sqlite_sequence VALUES (?, ?)", r)', ["writes `sqlite_sequence` (a verb worked out when it runs)"]),
    ("the bare name", 't = "sqlite_sequence"', ["writes `sqlite_sequence` (a name the scan cannot place)"]),
    ("a rule's body", 'conn.execute("CREATE TEMP TRIGGER z AFTER INSERT ON x BEGIN UPDATE sqlite_sequence SET seq = 0; END")', ["writes `sqlite_sequence` (UPDATE)"]),
    ("a template filled in", 'conn.execute("DELETE FROM {}".format("sqlite_sequence"))', ["writes `sqlite_sequence` (a name the scan cannot place)", "writes `sqlite_sequence` (DELETE)"]),
    ("audit's value, imported", "from gridiron.audit import SEQUENCE_STORE as s\nconn.execute(f\"DELETE FROM {s}\")", ["names `SEQUENCE_STORE`"]),
    ("audit's value, read off it", "import gridiron.audit as a\nconn.execute('DELETE FROM ' + a.SEQUENCE_STORE)", ["names `SEQUENCE_STORE`"]),
    ("audit's setting word", "import gridiron.audit as a\nconn.execute(a._SETTING_VERB + ' recursive_triggers = 1')", ["names `_SETTING_VERB`", "sets `recursive_triggers` with no verb before it"]),
    ("audit's settings' names", "import gridiron.audit as a\nfor n in a.RULE_SETTINGS:\n    x = n", ["names `RULE_SETTINGS`"]),
    # (the prover, 2026-09-29: the store's name kept apart from its verb)
    ("the name with its condition, kept", "t = \"sqlite_sequence WHERE name = 'predictions'\"", ["writes `sqlite_sequence` (a name the scan cannot place)"]),
    ("a FROM beginning a kept string", 't = "FROM sqlite_sequence WHERE name = ?"', ["writes `sqlite_sequence` (a verb worked out when it runs)"]),
    ("the verb in pieces, a delete", 'conn.execute(v + "TE FROM sqlite_sequence")', ["writes `sqlite_sequence` (a verb worked out when it runs)"]),
    ("the verb in pieces, an update", 'conn.execute(v + "DATE sqlite_sequence SET seq = 0")', ["writes `sqlite_sequence` (a name the scan cannot place)"]),
    ("the verb in pieces, an update under a clause", 'conn.execute(v + "DATE OR IGNORE sqlite_sequence SET seq = 0")', ["writes `sqlite_sequence` (a name the scan cannot place)"]),
    ("the verb in pieces, an insert", 'conn.execute(v + "RT INTO sqlite_sequence VALUES (?, ?)", r)', ["writes `sqlite_sequence` (a verb worked out when it runs)"]),
    ("audit's value looked up in pieces", "import gridiron.audit as a\nconn.execute('DELETE FROM ' + getattr(a, 'SEQUENCE' + '_STORE'))", ["names `SEQUENCE_STORE`"]),
    ("a read with a join", 'conn.execute("SELECT s.seq FROM sqlite_master AS m JOIN sqlite_sequence AS s ON s.name = m.name")', []),
    ("prose after a whole word", 'x = f"the {t} sqlite_sequence mark"', []),
    ("a read", 'conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (t,))', []),
    ("a read with its columns worked out", 'conn.execute(f"SELECT {x} FROM sqlite_sequence")', []),
    ("its name as data", "conn.execute(\"SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'\")", []),
    ("prose", 'x = f"{t}: sqlite_sequence holds {r} rows"', []),
    ("another table", 'conn.execute("DELETE FROM sqlite_sequence_log")', []),
    ("a table wholly worked out", 'conn.execute(f"DELETE FROM {t}")', []),
    # 4. several rows under OR FAIL, OR IGNORE, OR ROLLBACK
    ("a VALUES list", 'conn.execute("INSERT OR FAIL INTO records (v) VALUES (?), (?)", (a, b))', ["several rows (a VALUES list of 2) under FAIL on `records`"]),
    ("a SELECT", 'conn.execute("INSERT OR IGNORE INTO records (v) SELECT v FROM cache")', ["(rows a SELECT gives) under IGNORE on `records`"]),
    ("a WITH", 'conn.execute("WITH c AS (SELECT 1) INSERT OR IGNORE INTO records (v) SELECT * FROM c")', ["(rows a SELECT gives) under IGNORE on `records`"]),
    ("rows worked out", 'conn.execute(f"INSERT OR ROLLBACK INTO records (v) VALUES {rows}")', ["under ROLLBACK on `records`"]),
    ("a row, then more worked out", 'conn.execute("INSERT OR FAIL INTO records (v) VALUES (?)" + rows)', ["under FAIL on `records`"]),
    ("a row, then a compound", 'conn.execute("INSERT OR FAIL INTO records (v) VALUES (1) UNION ALL SELECT 2")', ["(a VALUES list with more rows after it) under FAIL on `records`"]),
    ("one row, then an upsert", 'conn.execute("INSERT OR IGNORE INTO records (id, v) VALUES (1, ?) RETURNING id", (v,))', []),
    ("executemany", 'conn.executemany("INSERT OR FAIL INTO records (v) VALUES (?)", rows)', ["handed to executemany"]),
    ("kept, not handed to execute", 'sql = "INSERT OR IGNORE INTO records (v) VALUES (?)"', ["not handed whole to execute"]),
    ("a string ending before its rows", 'conn.execute("INSERT OR FAIL INTO records (v)" + rows)', ["under FAIL on `records`"]),
    ("an upsert that does nothing", 'conn.execute("INSERT INTO records (id, v) VALUES (1, ?), (2, ?) ON CONFLICT DO NOTHING", r)', ["under DO NOTHING on `records`"]),
    ("by case, quoted", "conn.execute('insert or fail into \"RECORDS\" (v) values (1), (2)')", ["under FAIL on `records`"]),
    ("a table worked out", 'conn.execute(f"INSERT OR IGNORE INTO {t} (v) SELECT v FROM old")', ["on a table worked out when it runs, and a table the scan cannot read is counted as append-only"]),
    ("through a rule", 'conn.execute("INSERT OR FAIL INTO feed (k, v) VALUES (1, 2), (3, 4)")', ["on `feed`, and `records` is append-only"]),
    ("the no-update table", 'conn.execute("INSERT OR IGNORE INTO frozen (v) SELECT v FROM cache")', ["on `frozen`"]),
    ("one row handed to execute", 'conn.execute("INSERT OR IGNORE INTO records (v) VALUES (?)", (v,))', []),
    ("default values", 'conn.execute("INSERT OR FAIL INTO records DEFAULT VALUES")', []),
    ("an ordinary table", 'conn.execute("INSERT OR FAIL INTO cache (k, v) VALUES (1, 2), (3, 4)")', []),
    ("OR ABORT", 'conn.execute("INSERT OR ABORT INTO records (v) VALUES (1), (2)")', []),
    ("plain", 'conn.execute("INSERT INTO records (v) SELECT v FROM cache")', []),
    ("prose", 'x = "insert or fail the rows into records"', []),
    # (the prover, 2026-09-29: the insert's verb in pieces or kept apart)
    ("the verb in pieces", 'conn.execute(v + "RT OR FAIL INTO records (v) SELECT v FROM cache")', ["under FAIL on `records`"]),
    ("its head kept apart", 't = "INSERT OR IGNORE"', ["under IGNORE on a table worked out when it runs"]),
    ("its tail kept apart", 't = "OR FAIL INTO records (v) SELECT v FROM cache"', ["under FAIL on `records`"]),
    ("its head kept apart, OR ABORT", 't = "INSERT OR ABORT"', []),
    # 4. a rule raising FAIL, IGNORE or ROLLBACK (the prover, 2026-09-29)
    ("a temporary rule raising FAIL", "conn.execute(\"CREATE TEMP TRIGGER z BEFORE INSERT ON main.records BEGIN SELECT RAISE(FAIL, 'x'); END\")", ["a rule on `records` raising FAIL"]),
    ("raising IGNORE on a table whose rule writes one", 'conn.execute("CREATE TEMP TRIGGER z BEFORE INSERT ON feed BEGIN SELECT RAISE(IGNORE); END")', ["a rule on `feed` raising IGNORE, and an insert on `feed` writes the append-only `records`"]),
    ("a rule's clause worked out", "conn.execute(f\"CREATE TEMP TRIGGER z BEFORE INSERT ON frozen BEGIN SELECT RAISE({clause}, 'x'); END\")", ["a rule on `frozen` raising a clause worked out when it runs"]),
    ("a RAISE with no rule of its string", "s = \"SELECT RAISE(ROLLBACK, 'x');\"", ["a rule whose table the scan cannot read raising ROLLBACK"]),
    ("raising ABORT", "conn.execute(\"CREATE TEMP TRIGGER z BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT, 'x'); END\")", []),
    ("raising FAIL on an ordinary table", "conn.execute(\"CREATE TEMP TRIGGER z BEFORE INSERT ON cache BEGIN SELECT RAISE(FAIL, 'x'); END\")", []),
    # 4. a key declared to fail, ignore or roll back
    ("a key of a table worked out", 'conn.execute(f"CREATE TABLE {t} (a UNIQUE ON CONFLICT ROLLBACK)")', ["a key of a table the scan cannot read declared to roll back"]),
    ("a key of an ordinary table", 'conn.execute("CREATE TABLE t (a UNIQUE ON CONFLICT IGNORE)")', []),
]


@pytest.mark.parametrize("what,source,wanted", READINGS, ids=[r[0] for r in READINGS])
def test_what_the_scan_reads(tmp_path, what, source, wanted):
    faults = _scan(tmp_path, source)
    assert len(faults) == len(wanted), (what, faults)
    for words in wanted:
        assert [f for f in faults if words in f], (what, words, faults)
    for fault in faults:
        assert "gridiron/mod.py:" in fault and "(f)" in fault, fault


def test_the_schema_is_read_for_a_statement_and_a_key(tmp_path):
    schema = _SCHEMA + """
    CREATE TABLE IF NOT EXISTS keyed (id INTEGER PRIMARY KEY, k TEXT UNIQUE ON CONFLICT IGNORE);
    CREATE TRIGGER IF NOT EXISTS keyed_no_delete BEFORE DELETE ON keyed
    BEGIN SELECT RAISE(ABORT, 'no'); END;
    CREATE TRIGGER IF NOT EXISTS cache_copies AFTER INSERT ON cache
    BEGIN
        INSERT OR IGNORE INTO records (v) SELECT v FROM feed;
        INSERT OR IGNORE INTO records (v) VALUES (NEW.v);
        UPDATE sqlite_sequence SET seq = 0;
    END;
    """
    faults = audit.rule_switch_faults(_tree(tmp_path, {}, schema), register={},
                                      frozen=frozenset())
    assert len(faults) == 3, faults
    assert [f for f in faults if "(table keyed)" in f and "declared to ignore" in f]
    assert [f for f in faults if "(trigger cache_copies)" in f
            and "(rows a SELECT gives) under IGNORE on `records`" in f]
    assert [f for f in faults if "(trigger cache_copies)" in f
            and "writes `sqlite_sequence` (UPDATE)" in f]


def test_the_schema_is_read_for_its_journal_and_a_rule_raising_fail(tmp_path):
    """The prover's (2026-09-29): journal_mode OFF in the schema, and a rule of
    the schema raising FAIL on an append-only table; WAL and a rule raising
    ABORT beside them are named by nothing."""
    schema = _SCHEMA + """
    PRAGMA journal_mode = WAL;
    PRAGMA journal_mode = OFF;
    CREATE TRIGGER IF NOT EXISTS records_stop BEFORE INSERT ON records
    WHEN NEW.v IS NULL
    BEGIN SELECT RAISE(FAIL, 'stopped part way'); END;
    CREATE TRIGGER IF NOT EXISTS records_refuse BEFORE INSERT ON records
    WHEN NEW.v = ''
    BEGIN SELECT RAISE(ABORT, 'refused whole'); END;
    """
    faults = audit.rule_switch_faults(_tree(tmp_path, {}, schema), register={},
                                      frozen=frozenset())
    assert len(faults) == 2, faults
    assert [f for f in faults if "(module level) sets `journal_mode`: at OFF" in f]
    assert [f for f in faults if "(trigger records_stop) a rule on `records` raising FAIL" in f]


#: A rule on `fan` that inserts several rows into `records` (the prover's
#: world, 2026-09-29).
_FANNING = _SCHEMA + """
    CREATE TABLE IF NOT EXISTS fan (k TEXT PRIMARY KEY, v TEXT);
    CREATE TRIGGER IF NOT EXISTS fan_copies AFTER INSERT ON fan
    BEGIN
        INSERT INTO records (v) SELECT v FROM cache;
    END;
"""


@pytest.mark.parametrize("source,wanted", [
    ('conn.execute("INSERT OR FAIL INTO fan (k, v) VALUES (?, ?)", r)',
     ["(one row, and a rule on `fan` inserts rows a SELECT gives into `records` under "
      "this statement's clause) under FAIL on `fan`"]),
    ('conn.execute("INSERT OR IGNORE INTO fan (k, v) VALUES (?, ?)", r)', ["under IGNORE on `fan`"]),
    ('conn.execute("INSERT OR ABORT INTO fan (k, v) VALUES (?, ?)", r)', []),
    ('conn.execute("INSERT INTO fan (k, v) VALUES (?, ?)", r)', []),
    # `feed`'s rule inserts one row for each row inserted
    ('conn.execute("INSERT OR FAIL INTO feed (k, v) VALUES (?, ?)", r)', []),
    # a temporary rule the code creates, on an ordinary table
    ('conn.executescript("CREATE TEMP TRIGGER z AFTER INSERT ON cache BEGIN '
     'INSERT INTO frozen (v) SELECT v FROM feed; END")\n'
     'conn.execute("INSERT OR ROLLBACK INTO cache (k, v) VALUES (?, ?)", r)',
     ["a rule on `cache` inserts rows a SELECT gives into `frozen`"]),
], ids=["fail", "ignore", "abort", "plain", "one row a row", "a temporary rule"])
def test_one_row_into_a_table_whose_rule_inserts_several_is_several(tmp_path, source, wanted):
    """The prover's (2026-09-29): a ruled clause on one row, where a rule of
    the table (or of one it reaches) inserts several rows into an
    append-only table, is an insert of several rows under that clause."""
    faults = _scan(tmp_path, source, _FANNING)
    assert len(faults) == len(wanted), faults
    for words in wanted:
        assert [f for f in faults if words in f], (words, faults)


def test_the_tools_and_desktop_are_read_and_the_tests_and_plantings_are_not(tmp_path):
    line = 'import sqlite3\n\ndef f(conn):\n    conn.execute("PRAGMA recursive_triggers = ON")\n'
    root = _tree(tmp_path, {"tools/x.py": line, "desktop/x.py": line,
                            "tests/x.py": line, "tools/guards/x.py": line})
    faults = audit.rule_switch_faults(root, register={}, frozen=frozenset())
    assert sorted(f.split(":")[0] for f in faults) == ["desktop/x.py", "tools/x.py"]


def test_the_check_raises_naming_each_fault(tmp_path):
    root = _tree(tmp_path, {"gridiron/mod.py":
                            'def f(conn):\n    conn.execute("PRAGMA recursive_triggers = ON")\n'})
    with pytest.raises(audit.LawViolation, match="recursive_triggers") as caught:
        audit.check_no_code_switches_the_rules_off_or_rewrites_their_marks(root)
    assert "question 25" in str(caught.value) and "question 29" in str(caught.value)


# --- the register -----------------------------------------------------------------

_REBUILD = '''
def _rebuild_one(conn, table, seq):
    conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
    conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (table, seq))
'''
# Read by `getattr` so the file collects on a tree without the scan, where
# every test of it fails by name instead (the prover, 2026-09-29).
_REGISTER = dict(getattr(audit, "SEQUENCE_WRITES_REGISTERED", {}))


def test_the_rebuild_doors_statements_are_held_by_the_register(tmp_path):
    root = _tree(tmp_path, {"gridiron/rebuild.py": _REBUILD})
    assert audit.rule_switch_faults(root, register=_REGISTER) == []
    assert len(audit.rule_switch_faults(root, register={}, frozen=frozenset())) == 2


def test_a_second_write_under_one_entry_is_named(tmp_path):
    root = _tree(tmp_path, {"gridiron/rebuild.py": _REBUILD + (
        '    conn.execute("DELETE FROM sqlite_sequence")\n')})
    faults = audit.rule_switch_faults(root, register=_REGISTER)
    assert len(faults) == 1 and "a second write of `sqlite_sequence`" in faults[0], faults


def test_a_register_entry_no_longer_found_undated_or_added_is_named(tmp_path):
    root = _tree(tmp_path, {"gridiron/rebuild.py": _REBUILD})
    stale = dict(_REGISTER)
    stale[("gridiron/rebuild.py", "_rebuild_one", "UPDATE")] = "2026-09-29: a third"
    faults = audit.rule_switch_faults(root, register=stale,
                                      frozen=audit.SEQUENCE_WRITES_REGISTERED_ON_2026_09_29)
    assert [f for f in faults if "no longer found" in f]
    assert [f for f in faults if "not among the entries it was made with" in f]
    undated = {k: "the rebuild" for k in _REGISTER}
    faults = audit.rule_switch_faults(root, register=undated)
    assert len([f for f in faults if "without a dated reason" in f]) == 2, faults


def test_a_registered_statement_rewritten_is_a_second_door(tmp_path):
    """The prover's (2026-09-29): the register held a place and a verb, so
    the door's DELETE widened to every mark -- or its INSERT given a second
    row -- passed under the entry. Each entry holds its statement as made."""
    assert set(audit.SEQUENCE_WRITES_AS_MADE_ON_2026_09_29) == set(
        audit.SEQUENCE_WRITES_REGISTERED_ON_2026_09_29)
    def tree(name: str, source: str) -> Path:
        (tmp_path / name).mkdir()
        return _tree(tmp_path / name, {"gridiron/rebuild.py": source})

    for k, rewritten in enumerate((
            _REBUILD.replace('"DELETE FROM sqlite_sequence WHERE name = ?", (table,)',
                             '"DELETE FROM sqlite_sequence"'),
            _REBUILD.replace("VALUES (?, ?)\", (table, seq)",
                             "VALUES (?, ?), ('predictions', 0)\", (table, seq)"))):
        assert rewritten != _REBUILD
        faults = audit.rule_switch_faults(tree(f"rewritten{k}", rewritten), register=_REGISTER)
        assert len(faults) == 1 and "not the one the register was made with" in faults[0], faults
    # the same statement spelled another way, as SQLite reads it, is the same
    spaced = _REBUILD.replace("WHERE name = ?", "where  name=?")
    assert spaced != _REBUILD
    assert audit.rule_switch_faults(tree("spaced", spaced), register=_REGISTER) == []


def test_the_gate_holds_the_module_register_to_the_one_it_was_made_with(monkeypatch):
    grown = dict(audit.SEQUENCE_WRITES_REGISTERED)
    grown[("gridiron/db.py", "init", "DELETE")] = "2026-09-29: a second door"
    monkeypatch.setattr(audit, "SEQUENCE_WRITES_REGISTERED", grown)
    with pytest.raises(audit.LawViolation, match="not among the entries it was made with"):
        audit.check_no_code_switches_the_rules_off_or_rewrites_their_marks()


# --- the two migration copies the scan found, plain now, side by side -------------

_OR_IGNORE_TAKEN = ("INSERT OR IGNORE INTO picks_taken (id, prediction_id, taken_utc)"
                    " SELECT id, prediction_id, taken_utc FROM picks_taken_pre_packages")


def _taken_before_packages(path: Path, taps, unique: bool = True) -> sqlite3.Connection:
    """A record whose `picks_taken` is the shape before packages (C4,
    2026-09-08), holding `taps`."""
    conn = db.open_db(path)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE picks_taken")
    conn.execute(
        "CREATE TABLE picks_taken (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " prediction_id INTEGER NOT NULL REFERENCES predictions (id),"
        " taken_utc TEXT NOT NULL" + (", UNIQUE (prediction_id)" if unique else "") + ")")
    conn.executemany("INSERT INTO picks_taken (id, prediction_id, taken_utc) VALUES (?,?,?)",
                     taps)
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _as_the_or_ignore_copy_did(conn: sqlite3.Connection) -> list:
    """The C4 widening as it stood until 2026-09-29, its copy under OR
    IGNORE, on a record of the old shape -- the rows it left, or the refusal
    it raised."""
    conn.execute("PRAGMA legacy_alter_table = ON")
    for trigger in db.TAKEN_TRIGGERS:
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    conn.execute("ALTER TABLE picks_taken RENAME TO picks_taken_pre_packages")
    conn.execute("PRAGMA legacy_alter_table = OFF")
    conn.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
    expected = conn.execute("SELECT COUNT(*) FROM picks_taken_pre_packages").fetchone()[0]
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(_OR_IGNORE_TAKEN)
    after = conn.execute("SELECT COUNT(*) FROM picks_taken").fetchone()[0]
    if after != expected:
        conn.rollback()
        raise db.MigrationRefused("refused")
    conn.execute("DROP TABLE picks_taken_pre_packages")
    conn.commit()
    return _taps(conn)


def _taps(conn):
    return [tuple(r) for r in conn.execute(
        "SELECT id, prediction_id, package_id, taken_utc FROM picks_taken ORDER BY id")]


_TAPS = [(1, 11, "2026-09-01T10:00:00Z"), (4, 12, "2026-09-02T10:00:00Z"),
         (9, 30, "2026-09-03T10:00:00Z")]


def test_the_taken_widening_copies_what_the_or_ignore_copy_did(tmp_path):
    old = _as_the_or_ignore_copy_did(_taken_before_packages(tmp_path / "old.db", _TAPS))
    conn = _taken_before_packages(tmp_path / "new.db", _TAPS)
    assert db.widen_taken_for_packages(conn) is True
    assert _taps(conn) == old == [(1, 11, None, "2026-09-01T10:00:00Z"),
                                  (4, 12, None, "2026-09-02T10:00:00Z"),
                                  (9, 30, None, "2026-09-03T10:00:00Z")]
    assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'picks_taken'"
                        ).fetchone()[0] == 9
    assert db.widen_taken_for_packages(conn) is False, "and it is done once"


def test_a_tap_the_rebuilt_table_refuses_refuses_the_widening_as_before(tmp_path):
    """Two taps of one forecast, from a shape without the key: OR IGNORE
    dropped the second and the count refused the copy; the plain copy stops
    on it and is refused in words. Either way nothing is dropped."""
    taps = _TAPS + [(10, 11, "2026-09-04T10:00:00Z")]
    with pytest.raises(db.MigrationRefused):
        _as_the_or_ignore_copy_did(_taken_before_packages(tmp_path / "old.db", taps, unique=False))
    conn = _taken_before_packages(tmp_path / "new.db", taps, unique=False)
    with pytest.raises(db.MigrationRefused, match="picks_taken_pre_packages"):
        db.widen_taken_for_packages(conn)
    kept = conn.execute("SELECT COUNT(*) FROM picks_taken_pre_packages").fetchone()[0]
    assert kept == 4 and conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


_FACTOR = ("INSERT INTO {table} (name, sport, added_utc, rationale, active)"
           " VALUES (?,?,?,?,1)")


def _half_widened_factors(path: Path, stored, narrow) -> sqlite3.Connection:
    """A record left half way through widening `factors`, as on 2026-09-03:
    the table rebuilt holding `stored`, the original under `factors_narrow`
    holding `narrow` (made without its checks, as a narrower one was)."""
    conn = db.open_db(path)
    conn.executemany(_FACTOR.format(table="factors"), stored)
    conn.execute("CREATE TABLE factors_narrow AS SELECT * FROM factors WHERE 0")
    conn.executemany(_FACTOR.format(table="factors_narrow"), narrow)
    conn.commit()
    return conn


def _factors(conn):
    return [tuple(r) for r in conn.execute(
        "SELECT name, sport, added_utc, rationale FROM factors"
        " WHERE name LIKE 'q29_%' ORDER BY name")]


def _as_the_or_ignore_copy_did_on(conn: sqlite3.Connection, table: str):
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    joined = ", ".join(columns)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(f"INSERT OR IGNORE INTO {table} ({joined}) SELECT {joined} FROM {table}_narrow")
    conn.execute(f"DROP TABLE {table}_narrow")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


_WHY = "a declared reason long enough to be one"
_STORED = [("q29_first", "nfl", "2026-09-03T00:00:00Z", "the one stored first, " + _WHY)]
_NARROW = [("q29_first", "nfl", "2026-09-01T00:00:00Z", "the narrow copy's, " + _WHY),
           ("q29_second", "nfl", "2026-09-01T00:00:00Z", "the second, " + _WHY),
           ("q29_third", "mlb", "2026-09-02T00:00:00Z", "the third, " + _WHY)]


def test_the_narrow_copy_writes_the_rows_or_ignore_wrote(tmp_path):
    """A row already stored under the key stands, and the narrow copy's
    twin of it is left out -- what OR IGNORE was written for."""
    old = _half_widened_factors(tmp_path / "old.db", _STORED, _NARROW)
    _as_the_or_ignore_copy_did_on(old, "factors")
    conn = _half_widened_factors(tmp_path / "new.db", _STORED, _NARROW)
    assert db._finish_widening_table(conn, "factors").startswith("factors (")
    assert _factors(conn) == _factors(old) == [
        _STORED[0], _NARROW[1], _NARROW[2]]
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'factors_narrow'"
                            ).fetchone()


def test_the_narrow_copy_refuses_a_row_or_ignore_would_have_dropped(tmp_path):
    """A narrow row the table's CHECK refuses: OR IGNORE dropped it, and the
    count let that through because the rows stored first made up the
    number; the plain copy refuses, and the original stays whole."""
    bad = ("q29_bad", "nfl", "yesterday", "no date at all, " + _WHY)
    stored = _STORED + [("q29_extra", "nfl", "2026-09-03T00:00:00Z", "another, " + _WHY)]
    old = _half_widened_factors(tmp_path / "old.db", stored, _NARROW + [bad])
    _as_the_or_ignore_copy_did_on(old, "factors")
    assert bad[0] not in [r[0] for r in _factors(old)], "OR IGNORE lost it"
    conn = _half_widened_factors(tmp_path / "new.db", stored, _NARROW + [bad])
    with pytest.raises(db.MigrationRefused, match="factors_narrow"):
        db._finish_widening_table(conn, "factors")
    assert conn.execute("SELECT COUNT(*) FROM factors_narrow").fetchone()[0] == 4
    assert _factors(conn) == sorted(stored)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
