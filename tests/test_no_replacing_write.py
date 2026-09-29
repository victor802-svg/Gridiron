"""Operator question 15, ruled 2026-09-27 (third set), its second step: the
gate scan.

"Then one gate scan that refuses INSERT OR REPLACE, REPLACE and ON CONFLICT
DO UPDATE against every append-only table; any legitimate upsert (cache,
derived table) is named in a register that may only shrink." How the brief
is read is in `docs/briefs/2026-09-27-rulings-third-set.md`: the scan reads
every SQL statement the shipped code can issue and `schema.sql`; an
append-only table is one the schema gives a no-delete or no-update rule,
read from the schema; an unreadable target counts as append-only; tests and
plantings are outside it. The scan is `audit.replacing_write_faults`, run in
the gate as `audit.check_no_replacing_write_on_an_append_only_table`; its
plantings are the seven `plant.py::plant_*` named in `test_guards.py`.

And the one replacing write it found on an append-only table: `db.set_meta`
upserted `meta`, which carries the release instant's no-delete and
no-update rules. It is two plain statements now, with the same effect.
"""
from __future__ import annotations

import ast
import re
import sqlite3
import textwrap
from pathlib import Path

import pytest

from gridiron import audit, config, db


# --- a world of its own -----------------------------------------------------

#: `records` has a no-delete rule and `frozen` a no-update rule of one column
#: (both append-only); `cache` and `feed` have none, and a rule on `feed`
#: writes `records`.
_SCHEMA = """
    -- A comment naming INSERT OR REPLACE INTO records is not a statement.
    CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, v TEXT);
    CREATE TRIGGER IF NOT EXISTS records_no_delete
    BEFORE DELETE ON records
    BEGIN
        SELECT RAISE(ABORT, 'a record is never removed; INSERT OR REPLACE is refused');
    END;
    CREATE TABLE IF NOT EXISTS frozen (id INTEGER PRIMARY KEY, v TEXT);
    CREATE TRIGGER IF NOT EXISTS frozen_no_update
    BEFORE UPDATE OF v ON frozen
    WHEN OLD.v IS NOT NEW.v
    BEGIN
        SELECT RAISE(ABORT, CASE WHEN NEW.v IS NULL THEN 'gone' ELSE 'moved' END);
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
    """A package with `schema.sql` and whatever files are named beside it;
    its root."""
    (tmp_path / "gridiron").mkdir()
    (tmp_path / "gridiron" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "gridiron" / "schema.sql").write_text(
        textwrap.dedent(schema), encoding="utf-8")
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
    return tmp_path / "gridiron"


def _named(faults: list[str], marker: str) -> list[str]:
    return [f for f in faults if marker in f]


# --- the shipped code and the schema ----------------------------------------

def test_the_shipped_code_and_the_schema_replace_no_row_of_an_append_only_table():
    assert audit.replacing_write_faults() == []
    audit.check_no_replacing_write_on_an_append_only_table()


def test_the_gate_runs_the_scan_in_step_two():
    source = (config.REPO_ROOT / "tools" / "verify.py").read_text(encoding="utf-8")
    step = next(node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert ("audit.check_no_replacing_write_on_an_append_only_table"
            in ast.get_source_segment(source, step))


def test_the_append_only_tables_are_the_ones_sqlite_holds_a_rule_on(tmp_path):
    """Read from the schema, never a list -- and read as SQLite reads it: a
    fresh build's own rules, each table with a DELETE or UPDATE rule, name
    for name."""
    conn = db.open_db(tmp_path / "fresh.db")
    held: dict[str, set] = {}
    for name, table, sql in conn.execute(
            "SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'trigger'"):
        event = re.search(r"\b(?:BEFORE|AFTER|INSTEAD\s+OF)\s+(DELETE|INSERT|UPDATE)\b",
                          sql, re.I).group(1).upper()
        if event in ("DELETE", "UPDATE"):
            held.setdefault(table, set()).add(name)
    conn.close()
    protected, writes = audit._the_schemas_rules(
        audit._replace_scan_sources(config.PACKAGE_ROOT))
    assert protected == held
    # What the brief was read against on 2026-09-27: 21 tables with a delete
    # rule and one with an update rule only -- and from 2026-09-29 the
    # "fitted below its gate" labels (operator question 23), append-only
    # from the day they were declared: 23.
    assert len(protected) == 23
    assert protected["correction_gate_labels"] == {
        "correction_gate_labels_no_delete", "correction_gate_labels_no_update"}
    assert {"meta", "settings", "task_runs", "predictions", "recommendations",
            "market_snapshots", "prop_rung_claims"} <= set(protected)
    assert protected["prop_rung_claims"] == {"prop_rung_claims_no_update"}
    # No rule in the schema writes a table, so no write inherits a clause
    # through one today -- not even one whose name cannot be read (the
    # prover, 2026-09-27: `any` of a set holding only None is False).
    assert all(not written for written in writes.values())
    # ...and no foreign key declares an action, so no write reaches a child
    # through one today.
    assert audit._the_schemas_key_actions(
        audit._replace_scan_sources(config.PACKAGE_ROOT)) == {}


def test_every_registered_upsert_is_a_cache_or_a_derived_table_of_the_schema():
    """Each entry names a table the schema declares and gives no no-delete or
    no-update rule, with a dated reason in words."""
    schema = (config.PACKAGE_ROOT / "schema.sql").read_text(encoding="utf-8")
    declared = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", schema))
    protected, _ = audit._the_schemas_rules(
        audit._replace_scan_sources(config.PACKAGE_ROOT))
    assert audit.UPSERTS_REGISTERED
    for (where, function, table), reason in audit.UPSERTS_REGISTERED.items():
        assert (config.REPO_ROOT / where).is_file(), where
        assert table in declared, table
        assert table not in protected, table
        assert re.match(r"2026-09-27: \S.{20,}", reason), (where, function, reason)
    assert "meta" not in {t for _w, _f, t in audit.UPSERTS_REGISTERED}


# --- what the scan reads from a statement -----------------------------------

#: (what it is, Python source, the tables the scan finds a replacing write
#: on -- None where it cannot read the table).
READINGS = [
    ("an insert under OR REPLACE", 'x = "INSERT OR REPLACE INTO predictions (id) VALUES (1)"', ["predictions"]),
    ("lower case", 'x = "insert or replace into predictions (id) values (1)"', ["predictions"]),
    ("mixed case", 'x = "InSeRt Or RePlAcE InTo PreDictions VALUES (1)"', ["predictions"]),
    ("whitespace", 'x = "INSERT\\n\\t  OR\\n REPLACE\\n\\nINTO\\tpredictions VALUES (1)"', ["predictions"]),
    ("block comments", 'x = "INSERT/* a */OR/**/REPLACE/*x*/INTO/**/predictions VALUES (1)"', ["predictions"]),
    ("line comments", 'x = "INSERT -- note\\n OR REPLACE -- more\\n INTO predictions VALUES (1)"', ["predictions"]),
    ("implicit concatenation", 'x = ("INSERT OR "\n     "REPLACE INTO "\n     "predictions VALUES (1)")', ["predictions"]),
    ("joined with +", 'x = "INSERT OR " + "REPLACE INTO " + "predictions VALUES (1)"', ["predictions"]),
    ("a quoted name", 'x = \'INSERT OR REPLACE INTO "predictions" VALUES (1)\'', ["predictions"]),
    ("a bracketed name", 'x = "INSERT OR REPLACE INTO [predictions] VALUES (1)"', ["predictions"]),
    ("a backticked name", 'x = "INSERT OR REPLACE INTO `predictions` VALUES (1)"', ["predictions"]),
    ("a qualified name", 'x = \'INSERT OR REPLACE INTO main."PREDICTIONS" VALUES (1)\'', ["predictions"]),
    ("a REPLACE statement", 'x = "REPLACE INTO predictions VALUES (1)"', ["predictions"]),
    ("an update under OR REPLACE", 'x = "UPDATE OR REPLACE predictions SET id = 1 WHERE id = 2"', ["predictions"]),
    ("an upsert", 'x = "INSERT INTO predictions (id) VALUES (1) ON CONFLICT(id) DO UPDATE SET id = 2"', ["predictions"]),
    ("an upsert with no target", 'x = "INSERT INTO meta (key, value) VALUES (?,?) ON CONFLICT DO UPDATE SET value = 1"', ["meta"]),
    ("an upsert with a WHERE", 'x = "INSERT INTO t (a) SELECT a FROM u WHERE true ON CONFLICT(a) WHERE a > 0 DO UPDATE SET a = 1"', ["t"]),
    ("a WITH clause first", 'x = "WITH c AS (SELECT 1) INSERT OR REPLACE INTO predictions SELECT * FROM c"', ["predictions"]),
    ("executescript", 'conn.executescript("BEGIN; INSERT OR REPLACE INTO predictions VALUES (1); COMMIT;")', ["predictions"]),
    ("execute", 'conn.execute("REPLACE INTO recommendations VALUES (1)", ())', ["recommendations"]),
    ("a key that replaces", 'x = "CREATE TABLE t (id INTEGER PRIMARY KEY ON CONFLICT REPLACE)"', ["t"]),
    ("a table-level key that replaces", 'x = "CREATE TABLE IF NOT EXISTS main.t (a, UNIQUE (a) ON CONFLICT REPLACE)"', ["t"]),
    ("a rule's body", 'x = "CREATE TRIGGER r AFTER INSERT ON games BEGIN INSERT OR REPLACE INTO predictions VALUES (1); END"', ["predictions"]),
    # a part worked out at run time
    ("a formatted table", 'x = f"INSERT OR REPLACE INTO {table} VALUES (1)"', [None]),
    ("a formatted end of a name", 'x = f"INSERT OR REPLACE INTO pred{s} VALUES (1)"', [None]),
    ("a formatted start of a name", 'x = f"INSERT OR REPLACE INTO {p}_x VALUES (1)"', [None]),
    ("a formatted schema", 'x = f"INSERT OR REPLACE INTO {schema}.predictions VALUES (1)"', [None]),
    ("a formatted constant", 'x = f"INSERT OR {\'REPLACE\'} INTO predictions VALUES (1)"', ["predictions"]),
    ("a formatted conflict clause", 'x = f"INSERT OR {how} INTO predictions VALUES (1)"', ["predictions"]),
    ("a formatted clause after INSERT", 'x = f"INSERT {how} INTO predictions (id) VALUES (1)"', ["predictions"]),
    ("a formatted verb", 'x = f"{verb} INTO predictions (id) VALUES (1)"', ["predictions"]),
    ("a formatted verb and table", 'x = f"{verb} INTO {t} (id) VALUES (1)"', [None]),
    ("a formatted clause in an update", 'x = f"UPDATE {how} predictions SET id = 1"', ["predictions"]),
    ("a formatted upsert action", 'x = f"INSERT INTO predictions (id) VALUES (1) ON CONFLICT(id) DO {what}"', ["predictions"]),
    ("a formatted upsert target", 'x = f"INSERT INTO predictions (id) VALUES (1) ON CONFLICT({k}) DO UPDATE SET id = 2"', ["predictions"]),
    ("a formatted upsert clause", 'x = f"INSERT INTO predictions (id) VALUES (1) ON CONFLICT {rest}"', ["predictions"]),
    ("a % clause", 'x = "INSERT %s INTO predictions (id) VALUES (1)" % how', ["predictions"]),
    ("a % table", 'x = "INSERT OR REPLACE INTO %s VALUES (1)" % t', [None]),
    ("a .format table", 'x = "INSERT OR REPLACE INTO {} VALUES (1)".format(t)', [None]),
    ("a .format argument", 'x = "{} INTO predictions (id) VALUES (1)".format("REPLACE")', ["predictions"]),
    ("a statement handed to .format", 'x = "{}".format("INSERT OR REPLACE INTO predictions VALUES (1)")', ["predictions"]),
    ("a statement handed to %", 'x = "%s" % "INSERT OR REPLACE INTO predictions VALUES (1)"', ["predictions"]),
    ("pieces joined", 'x = " ".join(("INSERT", "OR", "REPLACE", "INTO", "predictions", "VALUES (1)"))', ["predictions"]),
    ("an upsert added on", 'x = "INSERT INTO predictions (id) VALUES (1)" + (" ON CONFLICT(id) DO UPDATE SET id = 2" if a else "")', [None]),
    # not a replacing write
    ("DO NOTHING", 'x = "INSERT INTO predictions (id) VALUES (1) ON CONFLICT DO NOTHING"', []),
    ("OR IGNORE", 'x = "INSERT OR IGNORE INTO predictions (id) VALUES (1)"', []),
    ("OR ABORT", 'x = "INSERT OR ABORT INTO predictions (id) VALUES (1)"', []),
    ("a key that ignores", 'x = "CREATE TABLE t (a UNIQUE ON CONFLICT IGNORE)"', []),
    ("the words in a string literal", "x = \"SELECT 'INSERT OR REPLACE INTO predictions'\"", []),
    ("the words in a comment", 'x = "SELECT 1 -- INSERT OR REPLACE INTO predictions"', []),
    ("a docstring", 'def f():\n    """INSERT OR REPLACE INTO predictions VALUES (1)"""\n', []),
    ("a plain insert", 'x = "INSERT INTO predictions (id) VALUES (1)"', []),
    ("a plain insert, every name formatted", 'x = f"INSERT INTO {t} ({cols}) SELECT {cols} FROM {old}"', []),
    ("a plain update", 'x = "UPDATE predictions SET resolved_utc = ? WHERE id = ?"', []),
    ("a plain update of a formatted table", 'x = f"UPDATE {table} SET id = 1"', []),
    ("the replace() function", 'x = "SELECT replace(a, \'x\', \'y\') FROM t"', []),
    ("prose", 'x = "a prediction is never replaced, or updated in place"', []),
    ("prose with an insert", 'x = f"insert the {n} rows into the table"', []),
    ("prose with an update", 'x = f"we update {n} records later"', []),
    ("prose with into", 'x = f"{n} went into the pot"', []),
    ("prose with on conflict", 'x = "a key that is on conflict"', []),
]


@pytest.mark.parametrize("what,source,tables", READINGS, ids=[r[0] for r in READINGS])
def test_what_the_scan_reads_from_a_statement(what, source, tables):
    found = [table
             for _node, text in audit._sql_strings_in(ast.parse(source))
             for _i, _form, table, _inherited in audit._replacing_statements(
                 audit._sql_tokens(text))]
    assert sorted(found, key=str) == sorted(tables, key=str), what


# --- the faults, by name ----------------------------------------------------

def test_a_replacing_write_on_an_append_only_table_is_refused_registered_or_not(tmp_path):
    root = _tree(tmp_path, {"gridiron/writer.py": """
        def replaced(conn):
            conn.execute("INSERT OR REPLACE INTO records (id, v) VALUES (1, 'x')")

        def by_update(conn):
            conn.execute("UPDATE OR REPLACE frozen SET id = 1 WHERE id = 2")

        def upserted(conn):
            conn.execute("INSERT INTO records (id, v) VALUES (1, 'x')"
                         " ON CONFLICT(id) DO UPDATE SET v = excluded.v")

        def unread(conn, table):
            conn.execute(f"REPLACE INTO {table} (id) VALUES (1)")
        """})
    register = {("gridiron/writer.py", "replaced", "records"): "2026-09-27: planted"}
    faults = audit.replacing_write_faults(root, register)
    for marker, words in (
            ("(replaced) an insert under OR REPLACE on `records`",
             "`records` is append-only: the schema gives it `records_no_delete`"),
            ("(by_update) an update under OR REPLACE on `frozen`",
             "`frozen` is append-only: the schema gives it `frozen_no_update`"),
            ("(upserted) an upsert whose conflict clause updates the stored row "
             "on `records`", "`records` is append-only"),
            ("(unread) a REPLACE statement", "cannot read the table it writes")):
        assert any(marker in f and words in f for f in faults), (marker, faults)
    # The register cannot hold it: the entry is refused as well.
    assert _named(faults, "gridiron/writer.py (replaced) on `records`: registered")
    assert len(faults) == 5, faults


def test_an_upsert_on_an_ordinary_table_needs_the_register(tmp_path):
    files = {"gridiron/loader.py": """
        def refresh(conn, k, v):
            conn.execute("INSERT INTO cache (k, v) VALUES (?, ?)"
                         " ON CONFLICT(k) DO UPDATE SET v = excluded.v", (k, v))
        """}
    root = _tree(tmp_path, files)
    faults = audit.replacing_write_faults(root, {})
    assert len(faults) == 1 and "gridiron/loader.py:3 (refresh)" in faults[0]
    assert "audit.UPSERTS_REGISTERED does not name" in faults[0]
    key = ("gridiron/loader.py", "refresh", "cache")
    assert audit.replacing_write_faults(root, {key: "2026-09-27: a cache"}) == []
    undated = audit.replacing_write_faults(root, {key: "a cache"})
    assert len(undated) == 1 and "without a dated reason" in undated[0]


def test_the_register_only_shrinks(tmp_path):
    """An entry whose statement is gone fails; so does a second statement
    under one entry, and an entry on an append-only table."""
    root = _tree(tmp_path, {"gridiron/loader.py": """
        def refresh(conn, k, v):
            conn.execute("INSERT OR REPLACE INTO cache (k, v) VALUES (?, ?)", (k, v))
            conn.execute("INSERT OR REPLACE INTO cache (k, v) VALUES (?, ?)", (v, k))
        """})
    register = {
        ("gridiron/loader.py", "refresh", "cache"): "2026-09-27: a cache",
        ("gridiron/loader.py", "gone", "cache"): "2026-09-27: a cache, once",
        ("gridiron/loader.py", "refresh", "frozen"): "2026-09-27: never lawful",
    }
    faults = audit.replacing_write_faults(root, register)
    assert _named(faults, "gridiron/loader.py:4 (refresh) a second replacing "
                          "write on `cache` under one register entry")
    assert _named(faults, "gridiron/loader.py (gone) on `cache`: registered in "
                          "audit.UPSERTS_REGISTERED and no longer found")
    assert _named(faults, "gridiron/loader.py (refresh) on `frozen`: registered "
                          "in audit.UPSERTS_REGISTERED, and `frozen` is append-only")
    assert len(faults) == 3, faults


def test_a_write_under_or_replace_is_aimed_at_what_its_tables_rules_write(tmp_path):
    """A rule's own writes run under the conflict clause of the statement
    that ran it, so an insert under OR REPLACE on `feed` -- whose rule
    writes `records` -- can replace a record. An upsert's clause is not
    inherited, and needs only the register."""
    root = _tree(tmp_path, {"gridiron/loader.py": """
        def fed(conn):
            conn.execute("INSERT OR REPLACE INTO feed (k, v) VALUES ('a', 'b')")

        def upserted(conn):
            conn.execute("INSERT INTO feed (k, v) VALUES ('a', 'b')"
                         " ON CONFLICT(k) DO UPDATE SET v = excluded.v")
        """})
    register = {("gridiron/loader.py", "fed", "feed"): "2026-09-27: planted",
                ("gridiron/loader.py", "upserted", "feed"): "2026-09-27: planted"}
    faults = audit.replacing_write_faults(root, register)
    assert len(_named(faults, "(fed) an insert under OR REPLACE on `feed` (its "
                              "rules write `records`")) == 1
    # Its entry is refused as well -- by its true reason, since the prover
    # (2026-09-27): the statement is there, not "no longer found".
    assert _named(faults, "gridiron/loader.py (fed) on `feed`: registered in "
                          "audit.UPSERTS_REGISTERED, and its statement is "
                          "refused above")
    assert not _named(faults, "no longer found")
    assert not _named(faults, "(upserted)")
    assert len(faults) == 2, faults


def test_the_schema_is_read_for_a_key_that_replaces(tmp_path):
    schema = _SCHEMA + """
        CREATE TABLE IF NOT EXISTS tallies (
            id INTEGER PRIMARY KEY ON CONFLICT REPLACE,
            n  INTEGER
        );
        CREATE TRIGGER IF NOT EXISTS tallies_no_delete BEFORE DELETE ON tallies
        BEGIN SELECT RAISE(ABORT, 'no'); END;
        CREATE TABLE IF NOT EXISTS mirror (k TEXT, v TEXT, UNIQUE (k) ON CONFLICT REPLACE);
        """
    root = _tree(tmp_path, {}, schema)
    faults = audit.replacing_write_faults(root, {})
    assert _named(faults, "(table tallies) a key declared to replace the stored "
                          "row whenever an insert meets it on `tallies`, and "
                          "`tallies` is append-only")
    line = next(n for n, text in enumerate(
        (root / "schema.sql").read_text(encoding="utf-8").splitlines(), 1)
        if "ON CONFLICT REPLACE," in text)
    assert _named(faults, f"gridiron/schema.sql:{line} (table tallies)")
    assert _named(faults, "(table mirror) a key declared to replace the stored "
                          "row whenever an insert meets it on `mirror`, which "
                          "audit.UPSERTS_REGISTERED does not name")
    assert len(faults) == 2, faults
    registered = {("gridiron/schema.sql", "table mirror", "mirror"): "2026-09-27: a mirror"}
    assert len(audit.replacing_write_faults(root, registered)) == 1


def test_the_tools_and_desktop_are_read_and_the_tests_and_plantings_are_not(tmp_path):
    statement = '''
        def w(conn):
            conn.execute("INSERT OR REPLACE INTO records (id) VALUES (1)")
        '''
    root = _tree(tmp_path, {
        "tests/test_scratch.py": statement,
        "tools/guards/plant.py": statement,
        "tools/rebuild_it.py": statement,
        "tools/deeper/step.py": statement,
        # only `tools/guards/` is outside, not a folder of that name elsewhere
        "tools/deeper/guards/step.py": statement,
        "desktop/guards/launcher.py": statement,
        "desktop/launcher.py": statement,
    })
    faults = audit.replacing_write_faults(root, {})
    assert sorted(f.split(":")[0] for f in faults) == [
        "desktop/guards/launcher.py", "desktop/launcher.py",
        "tools/deeper/guards/step.py", "tools/deeper/step.py", "tools/rebuild_it.py"]


def test_the_check_raises_naming_each_fault(tmp_path):
    root = _tree(tmp_path, {"gridiron/writer.py": """
        def replaced(conn):
            conn.execute("REPLACE INTO records (id) VALUES (1)")
        """})
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_no_replacing_write_on_an_append_only_table(root)
    assert "A WRITE CAN REPLACE A ROW OF AN APPEND-ONLY TABLE" in str(exc.value)
    assert "gridiron/writer.py:3 (replaced) a REPLACE statement on `records`" in str(exc.value)


# --- what the scan's prover found (2026-09-27) ------------------------------
#
# Each shape below got round the scan as first built: a template kept in a
# variable and filled in later, a clause kept apart from its verb, an upsert
# in two strings, a statement rewritten by `.replace`, a foreign key's action.
# The scan reads a string of Python twice -- its template placeholders as
# parts worked out at run time, and as written -- through
# `audit._replacing_writes_in`.

#: (what it is, Python source, the tables found -- None where unread).
PROVER_READINGS = [
    # a template, wherever it is filled in
    ("a template formatted later", 'T = "INSERT OR {} INTO predictions (id) VALUES (?)"', ["predictions"]),
    ("a template filled by % later", 'T = "INSERT %s INTO predictions (id) VALUES (?)"', ["predictions"]),
    ("a %(name)s template", 'T = "%(verb)s INTO predictions (id) VALUES (?)"', ["predictions"]),
    ("str.format of a template", 'x = str.format("INSERT OR {} INTO predictions (id) VALUES (?)", c)', ["predictions"]),
    ("format_map of a template", 'x = "INSERT OR {c} INTO predictions (id) VALUES (?)".format_map(d)', ["predictions"]),
    ("a string.Template", 'x = Template("INSERT OR $how INTO predictions (id) VALUES (?)")', ["predictions"]),
    ("a ${name} Template", 'x = Template("UPDATE OR ${how} market_snapshots SET id = 1")', ["market_snapshots"]),
    ("an f-string's doubled braces", 'x = f"INSERT OR {{}} INTO {t} (id) VALUES (1)"', [None]),
    ("a key with a space", 'T = "INSERT %(the verb)s INTO predictions (id) VALUES (?)"', ["predictions"]),
    ("a fill of a space", 'T = "INSERT OR {: >7} INTO predictions (id) VALUES (?)"', ["predictions"]),
    ("a bytes literal decoded", 'x = b"INSERT OR REPLACE INTO predictions (id) VALUES (1)".decode()', ["predictions"]),
    ("a bytes template", 'x = b"INSERT OR %s INTO predictions (id) VALUES (1)" % c', ["predictions"]),
    ("an upsert's action in a template", 'T = "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO {}"', ["meta"]),
    ("a REPLACE template's table", 'T = "REPLACE INTO {} (id) VALUES (?)"', [None]),
    # a clause kept apart from its verb, or after a part worked out at run time
    ("the clause, columns formatted", 'x = f"INSERT {clause} INTO predictions {cols} VALUES {marks}"', ["predictions"]),
    ("the verb, columns formatted", 'x = f"{verb} INTO predictions {cols} VALUES {marks}"', ["predictions"]),
    ("the clause in a string of its own", 'CLAUSE = "OR REPLACE"', [None]),
    ("the clause with spaces round it", 'CLAUSE = " OR REPLACE "', [None]),
    ("a hint before the clause", 'x = f"INSERT {hint} OR REPLACE INTO market_snapshots (id) VALUES (1)"', ["market_snapshots"]),
    ("a verb worked out before the clause", 'x = f"{verb} OR REPLACE INTO predictions (id) VALUES (1)"', ["predictions"]),
    ("a hint in an update", 'x = f"UPDATE {hint} OR REPLACE recommendations SET id = 1"', ["recommendations"]),
    ("a hint in a REPLACE", 'x = f"REPLACE {hint} INTO predictions (id) VALUES (1)"', ["predictions"]),
    ("a verb after a WITH worked out", 'x = f"{cte} {verb} INTO predictions (id) VALUES (1)"', ["predictions"]),
    ("a clause and a table worked out", 'x = f"UPDATE {clause} {table} SET id = 1"', [None]),
    ("INSERT OR where the string ends", 'x = "INSERT OR "', [None]),
    ("UPDATE OR where the string ends", 'x = "UPDATE OR "', [None]),
    ("a join with the clause worked out", 'x = " ".join(["INSERT", c, "INTO predictions", cols, "VALUES (1)"])', ["predictions"]),
    ("a rewrite by .replace", 'x = "INSERT OR IGNORE INTO prediction_voids (prediction_id) VALUES (1)".replace("IGNORE", "REPLACE")', ["prediction_voids"]),
    ("a rewrite worked out at run time", 'x = "INSERT OR IGNORE INTO predictions (id) VALUES (1)".replace("IGNORE", how)', ["predictions"]),
    # an upsert in two strings
    ("an insert that ends at its ON CONFLICT", 'x = "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key)"', ["meta"]),
    ("a piece that begins with ON CONFLICT", 'x = "ON CONFLICT(key)"', [None]),
    ("DO UPDATE SET on its own", 'x = " DO UPDATE SET value = excluded.value"', [None]),
    ("CONFLICT ... DO UPDATE on its own", 'x = "CONFLICT(key) DO UPDATE SET value = 1"', [None]),
    # other spellings of the table (SQLite takes a single-quoted name as a
    # name, measured 2026-09-27; the scan cannot say which, so it is unread)
    ("the temp schema's name", 'x = "INSERT OR REPLACE INTO temp.predictions (id) VALUES (1)"', ["predictions"]),
    ("a single-quoted name", "x = \"INSERT OR REPLACE INTO 'predictions' (id) VALUES (1)\"", [None]),
    ("a quoted schema and name", "x = 'UPDATE OR REPLACE \"main\".[market_snapshots] SET id = 1'", ["market_snapshots"]),
    # a placeholder can never swallow a statement
    ("braces round a statement in literals", "x = \"SELECT '{'; INSERT OR REPLACE INTO predictions VALUES (1); SELECT '}'\"", ["predictions"]),
    ("a % before a verb", 'x = "SELECT 1 %INSERT OR REPLACE INTO predictions VALUES (1)"', ["predictions"]),
    # not a replacing write
    ("prose: replace one with another", 'x = f"Replace {old} with {new}"', []),
    ("prose: keep or replace", 'x = f"{n} files: keep or replace them"', []),
    ("prose: a part worked out, or replace", 'x = f"Keep {what} or replace it"', []),
    ("prose: a parenthesis, or replace", 'x = "Delete the cache (it is safe) or replace it by hand"', []),
    ("prose: or replace, at the start", 'x = "Or replace the cache by hand"', []),
    ("prose: insert or update", 'x = "could not insert or update the row"', []),
    ("prose: do update", 'x = "we do update the page every minute"', []),
    ("prose: a percentage", 'x = f"100% sure: insert {n} rows into the table"', []),
    ("Python's errors='replace'", 'x = b.decode("utf-8", errors="replace")', []),
    ("the replace() function after OR", 'x = "SELECT a FROM t WHERE b OR replace(c, \'x\', \'y\') = d"', []),
    ("a JSON literal", "x = \"INSERT INTO settings (k, v) VALUES ('a', '{\\\"x\\\": 1}')\"", []),
    ("strftime in a literal", "x = \"INSERT INTO t (d) VALUES (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))\"", []),
    ("a plain insert, formatted", 'x = f"INSERT INTO {t} ({cols}) VALUES ({marks})"', []),
    ("OR IGNORE, formatted", 'x = f"INSERT OR IGNORE INTO {t} ({cols}) SELECT {cols} FROM {t}_narrow"', []),
    ("a plain update, formatted", 'x = f"UPDATE {t} SET {col} = ? WHERE id = ?"', []),
    ("a join ON a formatted condition", 'x = f"INSERT INTO t (a) SELECT a FROM b JOIN c ON {cond}"', []),
    ("DO NOTHING in a template", 'T = "INSERT INTO {} (k) VALUES (?) ON CONFLICT DO NOTHING"', []),
]


@pytest.mark.parametrize("what,source,tables", PROVER_READINGS,
                         ids=[r[0] for r in PROVER_READINGS])
def test_what_the_scan_reads_from_a_template_or_a_piece(what, source, tables):
    found = [table
             for _node, text in audit._sql_strings_in(ast.parse(source))
             for _start, _form, table, _inherited in audit._replacing_writes_in(
                 audit._sql_tokens(text), text, True)]
    assert sorted(found, key=str) == sorted(tables, key=str), what


def test_a_statement_read_both_ways_is_counted_once(tmp_path):
    """A registered upsert holding a `%` in a literal is found by both
    readings at one place, so it is one statement under its entry -- never
    'a second replacing write'."""
    root = _tree(tmp_path, {"gridiron/loader.py": """
        def refresh(conn, k):
            conn.execute("INSERT INTO cache (k, v) VALUES (?, strftime('%s', 'now'))"
                         " ON CONFLICT(k) DO UPDATE SET v = excluded.v", (k,))
        """})
    key = ("gridiron/loader.py", "refresh", "cache")
    assert audit.replacing_write_faults(root, {key: "2026-09-27: a cache"}) == []


#: `ledger` is append-only and keeps a key on `cache`, a table with no rule,
#: whose action SQLite runs when a replacing write removes or changes the
#: parent row.
_KEYED_SCHEMA = _SCHEMA + """
    CREATE TABLE IF NOT EXISTS ledger (
        id INTEGER PRIMARY KEY,
        k  TEXT REFERENCES cache (k) ON DELETE SET NULL,
        v  TEXT
    );
    CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
    BEGIN SELECT RAISE(ABORT, 'a ledger row is never removed'); END;
    CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE OF v ON ledger
    BEGIN SELECT RAISE(ABORT, 'a ledger row is never rewritten'); END;
"""


def test_a_foreign_keys_action_is_a_write_on_its_child(tmp_path):
    """Measured first: a replacing write on `cache` rewrites the append-only
    `ledger` row through the key's SET NULL, its update rule naming another
    column -- so the scan counts a replacing write as aimed at every table a
    key's action on its table writes, whatever its conflict clause."""
    conn = db.connect(tmp_path / "keyed.db")
    conn.executescript(textwrap.dedent(_KEYED_SCHEMA))
    conn.execute("INSERT INTO cache (k, v) VALUES ('a', 'x')")
    conn.execute("INSERT INTO ledger (id, k, v) VALUES (1, 'a', 'kept')")
    conn.execute("INSERT OR REPLACE INTO cache (k, v) VALUES ('a', 'y')")
    assert tuple(conn.execute("SELECT k, v FROM ledger").fetchone()) == (None, "kept")
    conn.close()

    writer = {"gridiron/loader.py": """
        def replaced(conn):
            conn.execute("INSERT OR REPLACE INTO cache (k, v) VALUES ('a', 'y')")

        def upserted(conn):
            conn.execute("INSERT INTO cache (k, v) VALUES ('a', 'y')"
                         " ON CONFLICT(k) DO UPDATE SET v = excluded.v")
        """}
    (tmp_path / "keyed").mkdir()
    root = _tree(tmp_path / "keyed", writer, _KEYED_SCHEMA)
    register = {("gridiron/loader.py", "replaced", "cache"): "2026-09-27: planted",
                ("gridiron/loader.py", "upserted", "cache"): "2026-09-27: planted"}
    faults = audit.replacing_write_faults(root, register)
    for function, form in (("replaced", "an insert under OR REPLACE"),
                           ("upserted", "an upsert whose conflict clause")):
        assert _named(faults, f"({function}) {form}")
        assert any(f"({function})" in f and "(its keys write `ledger`, and a "
                   "foreign key's action writes its child" in f
                   and "`ledger` is append-only: the schema gives it "
                   "`ledger_no_delete`, `ledger_no_update`" in f for f in faults), faults
        assert _named(faults, f"gridiron/loader.py ({function}) on `cache`: registered "
                              "in audit.UPSERTS_REGISTERED, and its statement is "
                              "refused above")
    assert len(faults) == 4, faults
    # With no action on the key, the same writes need only the register.
    (tmp_path / "plain").mkdir()
    plain = _tree(tmp_path / "plain", writer, _KEYED_SCHEMA.replace(" ON DELETE SET NULL", ""))
    assert audit.replacing_write_faults(plain, register) == []


def test_a_view_written_through_an_instead_of_rule_reaches_its_table(tmp_path):
    """A write under OR REPLACE on a view is aimed at what the view's rule
    writes: the rule's statements carry the outer clause."""
    schema = _SCHEMA + """
        CREATE VIEW IF NOT EXISTS records_seen AS SELECT id, v FROM records;
        CREATE TRIGGER IF NOT EXISTS records_seen_insert INSTEAD OF INSERT ON records_seen
        BEGIN INSERT INTO records (id, v) VALUES (NEW.id, NEW.v); END;
        """
    root = _tree(tmp_path, {"gridiron/writer.py": """
        def through_the_view(conn):
            conn.execute("INSERT OR REPLACE INTO records_seen (id, v) VALUES (1, 'x')")
        """}, schema)
    faults = audit.replacing_write_faults(root, {})
    assert len(faults) == 1, faults
    assert ("(through_the_view) an insert under OR REPLACE on `records_seen` (its "
            "rules write `records`") in faults[0]
    assert "`records` is append-only" in faults[0]


@pytest.mark.parametrize("action", ["ON DELETE CASCADE", "ON DELETE SET NULL",
                                    "ON DELETE SET DEFAULT", "ON UPDATE CASCADE",
                                    "ON UPDATE SET NULL", "MATCH FULL ON DELETE CASCADE"])
def test_every_action_that_writes_the_child_is_read(action):
    tokens = audit._sql_tokens(
        f"CREATE TABLE IF NOT EXISTS main.child (id INTEGER PRIMARY KEY,"
        f" p TEXT, FOREIGN KEY (p) REFERENCES \"Parent\" (k) {action}, v TEXT);")
    assert audit._sql_key_actions(tokens) == [("parent", "child")]


@pytest.mark.parametrize("sql", [
    "CREATE TABLE c (p TEXT REFERENCES parent (k))",
    "CREATE TABLE c (p TEXT REFERENCES parent (k) ON DELETE RESTRICT ON UPDATE NO ACTION)",
    "CREATE TABLE c (p TEXT REFERENCES parent (k), q TEXT UNIQUE ON CONFLICT ABORT)",
])
def test_a_key_whose_action_writes_nothing_is_not_read_as_a_write(sql):
    assert audit._sql_key_actions(audit._sql_tokens(sql)) == []


def test_a_rule_or_a_key_onto_a_table_the_scan_cannot_read_counts_as_append_only(tmp_path):
    """A table a rule's body or a key's action writes, named at run time, is
    counted as append-only: it was dropped until the prover (2026-09-27)."""
    root = _tree(tmp_path, {"gridiron/loader.py": """
        def ruled(conn, t):
            conn.execute(f"CREATE TRIGGER IF NOT EXISTS feed_copies AFTER INSERT ON feed"
                         f" BEGIN INSERT INTO {t} (v) VALUES (NEW.v); END")

        def keyed(conn, t):
            conn.execute(f"CREATE TABLE IF NOT EXISTS {t} (k TEXT REFERENCES cache (k)"
                         f" ON DELETE CASCADE)")

        def fed(conn):
            conn.execute("INSERT OR REPLACE INTO feed (k, v) VALUES ('a', 'b')")

        def cached(conn):
            conn.execute("INSERT INTO cache (k, v) VALUES ('a', 'b')"
                         " ON CONFLICT(k) DO UPDATE SET v = excluded.v")
        """})
    register = {("gridiron/loader.py", "fed", "feed"): "2026-09-27: planted",
                ("gridiron/loader.py", "cached", "cache"): "2026-09-27: planted"}
    faults = audit.replacing_write_faults(root, register)
    assert any("(fed) an insert under OR REPLACE on `feed` (its rules write "
               "`records`, a table the scan cannot read" in f
               and "a table it reaches that the scan cannot read is counted as "
               "append-only" in f for f in faults), faults
    assert any("(cached) an upsert whose conflict clause updates the stored row "
               "on `cache` (its keys write a table the scan cannot read" in f
               for f in faults), faults
    assert len(faults) == 4, faults


def test_the_register_may_only_shrink_past_the_entries_frozen_on_2026_09_27(tmp_path):
    """'A register that may only shrink': the module's register holds no
    entry the frozen one does not, the frozen one holds the 35 of
    2026-09-27, and an entry added after it -- however it is dated -- fails
    by name while the statement it names passes the rest."""
    assert set(audit.UPSERTS_REGISTERED) <= audit.UPSERTS_REGISTERED_ON_2026_09_27
    assert len(audit.UPSERTS_REGISTERED_ON_2026_09_27) == 35
    root = _tree(tmp_path, {"gridiron/loader.py": """
        def refresh(conn, k, v):
            conn.execute("INSERT INTO cache (k, v) VALUES (?, ?)"
                         " ON CONFLICT(k) DO UPDATE SET v = excluded.v", (k, v))
        """})
    key = ("gridiron/loader.py", "refresh", "cache")
    register = {key: "2026-09-27: a cache, and dated as if it always was"}
    assert audit.replacing_write_faults(root, register) == []
    faults = audit.replacing_write_faults(root, register, frozen=frozenset())
    assert len(faults) == 1, faults
    assert ("gridiron/loader.py (refresh) on `cache`: registered in "
            "audit.UPSERTS_REGISTERED and not among the entries frozen on "
            "2026-09-27") in faults[0]
    assert audit.replacing_write_faults(root, register, frozen=frozenset({key})) == []


def test_the_gate_holds_the_module_register_to_the_frozen_one(monkeypatch):
    """The gate's own call reads the module's register against the frozen
    one: an entry added to it is named, though its statement is gone too."""
    added = ("gridiron/auth.py", "record_failure", "auth_failures")
    monkeypatch.setitem(audit.UPSERTS_REGISTERED, added,
                        "2026-09-27: a later entry, dated as if it always was")
    faults = audit.replacing_write_faults()
    assert _named(faults, "gridiron/auth.py (record_failure) on `auth_failures`: "
                          "registered in audit.UPSERTS_REGISTERED and not among "
                          "the entries frozen on 2026-09-27")
    with pytest.raises(audit.LawViolation, match="not among the entries frozen"):
        audit.check_no_replacing_write_on_an_append_only_table()


# --- set_meta, written plainly ----------------------------------------------

def _set_meta_as_released(conn, key, value):
    """`db.set_meta` as it shipped until question 15, for comparison."""
    conn.execute("INSERT INTO meta (key, value) VALUES (?,?)"
                 " ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    conn.commit()


_META_WRITES = [("kind", "live"), ("kind_note", "first"), ("kind", "backtest"),
                ("kind", "backtest"), ("other", "1"),
                ("prompt_record_binds_from", "2026-09-28T00:00:00Z"),
                ("prompt_record_binds_from", "not a time"), ("other", "2")]


def test_set_meta_writes_what_the_upsert_wrote(tmp_path):
    """The same writes through the old upsert and through `set_meta`, on two
    worlds built alike: the same rows under the same row numbers, refused at
    the same writes."""
    outcomes = {}
    for label, write in (("released", _set_meta_as_released), ("now", db.set_meta)):
        conn = db.open_db(tmp_path / f"{label}.db")
        refused = []
        for key, value in _META_WRITES:
            try:
                write(conn, key, value)
            except sqlite3.IntegrityError:
                refused.append((key, value))
                conn.rollback()
        rows = [tuple(r) for r in conn.execute(
            "SELECT rowid, key, value FROM meta WHERE key <> 'prompt_record_binds_from'"
            " ORDER BY key")]
        instant = conn.execute("SELECT value FROM meta"
                               " WHERE key = 'prompt_record_binds_from'").fetchone()
        outcomes[label] = (rows, refused, instant is not None)
        conn.close()
    assert outcomes["now"] == outcomes["released"]
    rows, refused, instant = outcomes["now"]
    assert dict((k, v) for _r, k, v in rows) == {
        "kind": "backtest", "kind_note": "first", "other": "2"}
    assert refused == [("prompt_record_binds_from", "2026-09-28T00:00:00Z"),
                       ("prompt_record_binds_from", "not a time")]
    assert instant


def test_set_meta_still_refuses_the_release_instant(tmp_path):
    conn = db.open_db(tmp_path / "w.db")
    stored = db.get_meta(conn, "prompt_record_binds_from")
    assert stored
    with pytest.raises(sqlite3.IntegrityError, match="GRIDIRON PROMPT RECORD"):
        db.set_meta(conn, "prompt_record_binds_from", "2030-01-01T00:00:00Z")
    conn.rollback()
    assert db.get_meta(conn, "prompt_record_binds_from") == stored
    # With no instant stored, one that is not a time is refused on insert.
    fresh = db.connect(tmp_path / "bare.db")
    fresh.executescript((config.PACKAGE_ROOT / "schema.sql").read_text(encoding="utf-8"))
    with pytest.raises(sqlite3.IntegrityError, match="written once, as a UTC"):
        db.set_meta(fresh, "prompt_record_binds_from", "soon")
    fresh.rollback()
    db.set_meta(fresh, "prompt_record_binds_from", "2026-09-27T00:00:00Z")
    assert db.get_meta(fresh, "prompt_record_binds_from") == "2026-09-27T00:00:00Z"
    fresh.close()
    conn.close()


def test_set_meta_is_one_step_and_commits_as_before(tmp_path):
    """The update takes the write lock before the insert on any connection,
    so no other writer stores the key between them; and a caller's pending
    write is committed with it, as the upsert's commit did."""
    path = tmp_path / "w.db"
    conn = db.open_db(path)
    other = db.connect(path)
    other.execute("PRAGMA busy_timeout = 0")
    for isolation in ("", None):
        conn.isolation_level = isolation
        conn.execute("SAVEPOINT probe")
        assert conn.execute("UPDATE meta SET value = 'x' WHERE key = 'absent'").rowcount == 0
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            other.execute("INSERT INTO meta (key, value) VALUES ('absent', 'y')")
        other.rollback()
        conn.execute("RELEASE probe")
    conn.isolation_level = ""
    conn.execute("INSERT INTO meta (key, value) VALUES ('pending', 'yes')")
    db.set_meta(conn, "kind_note", "set")
    seen = dict(other.execute("SELECT key, value FROM meta").fetchall())
    assert seen["pending"] == "yes" and seen["kind_note"] == "set"
    assert not conn.in_transaction
    other.close()
    conn.close()


def test_a_refused_set_meta_leaves_a_callers_pending_write_as_the_upsert_did(tmp_path):
    for label, write in (("released", _set_meta_as_released), ("now", db.set_meta)):
        conn = db.open_db(tmp_path / f"{label}.db")
        conn.execute("INSERT INTO meta (key, value) VALUES ('pending', 'yes')")
        with pytest.raises(sqlite3.IntegrityError):
            write(conn, "prompt_record_binds_from", "2031-01-01T00:00:00Z")
        assert conn.in_transaction, label
        assert db.get_meta(conn, "pending") == "yes", label
        conn.rollback()
        assert db.get_meta(conn, "pending") is None, label
        conn.close()
