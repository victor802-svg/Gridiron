"""The schema, compared by what it does (schema ruling 1 of 2026-09-24,
built 2026-09-25).

"The diff check compares after normalising quoting, whitespace, comments and
column order, and fails on any difference in behaviour." Each of the four is
normalised here on its own, and a CHECK, a DEFAULT, a trigger and an index
that differ are each caught; `tools/guards/plant.py` plants a new difference
on a whole record and requires the gate's check to name it.
"""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import db, rebuild, schema_diff

RELEASED = """CREATE TABLE factors (
    name          TEXT PRIMARY KEY,
    sport         TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb')),
    added_utc     TEXT NOT NULL,
    note          TEXT
)"""


def _props(record_sql: str, reference_sql: str) -> list[tuple[str, str]]:
    return [(d.property, d.held_by)
            for d in schema_diff.table_differences(record_sql, reference_sql)]


# --- the four things normalised, each on its own ----------------------------

def test_quoting_is_normalised():
    quoted = """CREATE TABLE "factors" (
    [name]        TEXT PRIMARY KEY,
    `sport`       TEXT NOT NULL DEFAULT 'nfl' CHECK ("sport" IN ('nfl','mlb')),
    "added_utc"   TEXT NOT NULL,
    note          TEXT
)"""
    assert _props(quoted, RELEASED) == []


def test_whitespace_and_case_are_normalised_but_a_string_is_not():
    reflowed = ("create   table factors(name text primary key,sport text not null"
                " default 'nfl' check(sport in('nfl','mlb')),added_utc text not"
                " null,note text)")
    assert _props(reflowed, RELEASED) == []
    shouted = RELEASED.replace("'nfl','mlb'", "'NFL','mlb'")
    assert ("column sport: check (sport in ('NFL', 'mlb'))", "record") \
        in _props(shouted, RELEASED)


def test_comments_are_normalised_wherever_they_sit():
    commented = """-- a comment before the statement is not stored, but one inside is
CREATE TABLE factors ( /* a block comment
    across lines */
    name          TEXT PRIMARY KEY,   -- inside the column list
    -- a line of its own, with a quote ' in it
    sport         TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb')),
    added_utc     TEXT NOT NULL,      /* between clauses */
    note          TEXT
)"""
    assert _props(commented, RELEASED) == []


def test_a_comment_marker_inside_a_string_is_the_string():
    text = RELEASED.replace("DEFAULT 'nfl'", "DEFAULT 'nfl -- not a comment'")
    assert ("column sport: default 'nfl -- not a comment'", "record") \
        in _props(text, RELEASED)


def test_column_order_is_normalised():
    reordered = """CREATE TABLE factors (
    name          TEXT PRIMARY KEY,
    added_utc     TEXT NOT NULL,
    note          TEXT
, sport TEXT NOT NULL DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb')))"""
    assert _props(reordered, RELEASED) == []


# --- what remains is behaviour, and is caught --------------------------------

def test_a_missing_check_is_caught_and_says_which_side_has_it():
    """The shape of seven of the eight registered differences: a column that
    reached the record by ALTER, with no CHECK and at the end."""
    altered = """CREATE TABLE factors (
    name          TEXT PRIMARY KEY,
    added_utc     TEXT NOT NULL,
    note          TEXT
, sport TEXT NOT NULL DEFAULT 'nfl')"""
    assert _props(altered, RELEASED) == [
        ("column sport: check (sport in ('nfl', 'mlb'))", "reference")]


def test_a_default_difference_is_caught():
    """The eighth: nba_injuries.player_name carries a DEFAULT '' on the live
    record that the release does not."""
    extra = RELEASED.replace("added_utc     TEXT NOT NULL",
                             "added_utc     TEXT NOT NULL DEFAULT ''")
    assert _props(extra, RELEASED) == [("column added_utc: default ''", "record")]


def test_a_type_a_not_null_and_a_missing_column_are_each_caught():
    changed = """CREATE TABLE factors (
    name          INTEGER PRIMARY KEY,
    sport         TEXT DEFAULT 'nfl' CHECK (sport IN ('nfl','mlb')),
    added_utc     TEXT NOT NULL
)"""
    found = _props(changed, RELEASED)
    assert ("column name: type integer", "record") in found
    assert ("column name: type text", "reference") in found
    assert ("column sport: not null", "reference") in found
    assert ("column note (text)", "reference") in found


def test_a_table_constraint_is_caught():
    with_key = RELEASED.replace("    note          TEXT\n)",
                                "    note          TEXT,\n    UNIQUE (sport, note)\n)")
    assert _props(with_key, RELEASED) == [
        ("table constraint unique (sport, note)", "record")]


def test_default_null_and_set_null_stay_inside_their_clause():
    """A NULL after DEFAULT, or inside ON DELETE SET NULL, is not the bare
    NULL constraint; parsed as one, `DEFAULT NULL` would read as a default
    with no value beside a separate clause."""
    kind, clauses = schema_diff._column(schema_diff.tokens(
        "TEXT DEFAULT NULL REFERENCES teams (id) ON DELETE SET NULL"))
    assert kind == ("text",)
    assert clauses == [("default", "null"),
                       ("references", "teams", "(", "id", ")", "on", "delete",
                        "set", "null")]


# --- whole databases ---------------------------------------------------------

def _two(tmp_path, record_sql: str, reference_sql: str):
    record, reference = tmp_path / "record.db", tmp_path / "reference.db"
    for path, sql in ((record, record_sql), (reference, reference_sql)):
        conn = db.connect(path)
        conn.executescript(sql)
        conn.close()
    return (db.read_only(record, "the record side of a schema test"),
            db.read_only(reference, "the reference side of a schema test"))


BASE = RELEASED + """;
CREATE INDEX factors_sport ON factors (sport, added_utc);
CREATE TRIGGER factors_no_delete BEFORE DELETE ON factors
BEGIN SELECT RAISE(ABORT, 'never deleted'); END;
"""


def test_an_equal_schema_written_differently_is_cosmetic_not_a_difference(tmp_path):
    rewritten = BASE.replace("CREATE INDEX factors_sport ON factors",
                             'CREATE INDEX "factors_sport"\n    ON [factors]')
    a, b = _two(tmp_path, rewritten, BASE)
    try:
        result = schema_diff.compare(a, b)
    finally:
        a.close()
        b.close()
    assert result.differences == []
    assert result.cosmetic == ["index factors_sport"]


def test_a_trigger_body_an_index_and_a_whole_object_are_caught(tmp_path):
    changed = (BASE.replace("(sport, added_utc)", "(sport)")
                   .replace("'never deleted'", "'never, ever deleted'")
               + "CREATE TABLE planted (id INTEGER PRIMARY KEY);")
    a, b = _two(tmp_path, changed, BASE)
    try:
        found = {(d.object, d.held_by): d.property
                 for d in schema_diff.compare(a, b).differences}
    finally:
        a.close()
        b.close()
    assert found[("table planted", "record")] == "the whole object"
    assert "(sport)" in found[("index factors_sport", "record")]
    assert "(sport, added_utc)" in found[("index factors_sport", "reference")]
    assert "never, ever" in found[("trigger factors_no_delete", "record")]


def test_the_pragmas_check_the_parser(tmp_path, monkeypatch):
    """A difference SQLite itself reports is found even where the text
    comparison is blind -- here blinded on purpose."""
    extra = BASE.replace("added_utc     TEXT NOT NULL",
                         "added_utc     TEXT NOT NULL DEFAULT ''")
    monkeypatch.setattr(schema_diff, "table_differences",
                        lambda *args, **kwargs: [])
    a, b = _two(tmp_path, extra, BASE)
    try:
        found = [d for d in schema_diff.compare(a, b).differences]
    finally:
        a.close()
        b.close()
    assert [d.held_by for d in found] == ["record", "reference"]
    assert all(d.property.startswith("column added_utc, as SQLite reads it:")
               for d in found)
    assert "default ''" in found[0].property


def test_the_words_name_both_sides():
    d = schema_diff.Difference("table factors", "column sport: check (x)",
                               "reference")
    assert d.words("the live record", "the release") == (
        "table factors, column sport: check (x): the release has it and the "
        "live record does not")


# --- quoted text is a name only where only a name can stand (2026-09-25) ----
#
# The adversarial review of 3603300: double-quoted and bracketed text was
# lower-cased and read as a name everywhere, but SQLite reads a double-quoted
# word as a STRING wherever it does not resolve to a name, and a bare word
# after DEFAULT is a string with its case. Each pair below does two different
# things in SQLite -- shown first, on a scratch database, so the test cannot
# pass on a pair that happens to behave the same -- and must be reported, by
# the text comparison, by the migration's own question, and by the whole
# comparison the gate runs.

def _outcome(create: str, dml: str, probe: str):
    conn = db.connect(":memory:")
    try:
        conn.execute(create)
        try:
            conn.executescript(dml)
        except sqlite3.Error as exc:
            return f"refused: {exc}"
        return [tuple(r) for r in conn.execute(probe)]
    finally:
        conn.close()


BEHAVIOURAL_PAIRS = [
    ("a keyword default against the same word quoted",
     "CREATE TABLE t (id INTEGER PRIMARY KEY, at TEXT DEFAULT CURRENT_TIMESTAMP)",
     'CREATE TABLE t (id INTEGER PRIMARY KEY, at TEXT DEFAULT "CURRENT_TIMESTAMP")',
     "INSERT INTO t (id) VALUES (1)", "SELECT at = 'CURRENT_TIMESTAMP' FROM t"),
    ("a double-quoted literal in a CHECK, in two cases",
     'CREATE TABLE t (id INTEGER PRIMARY KEY, sport TEXT CHECK (sport IN ("nfl")))',
     'CREATE TABLE t (id INTEGER PRIMARY KEY, sport TEXT CHECK (sport IN ("NFL")))',
     "INSERT INTO t (id, sport) VALUES (1, 'nfl')", "SELECT sport FROM t"),
    ("NULL against the string \"NULL\" in a CHECK",
     "CREATE TABLE t (id INTEGER PRIMARY KEY, s TEXT CHECK (s != NULL))",
     'CREATE TABLE t (id INTEGER PRIMARY KEY, s TEXT CHECK (s != "NULL"))',
     "INSERT INTO t (id, s) VALUES (1, 'NULL')", "SELECT s FROM t"),
    ("a bare word default, in two cases",
     "CREATE TABLE t (id INTEGER PRIMARY KEY, src TEXT DEFAULT live)",
     "CREATE TABLE t (id INTEGER PRIMARY KEY, src TEXT DEFAULT LIVE)",
     "INSERT INTO t (id) VALUES (1)", "SELECT src FROM t"),
    ("two COLLATE clauses, swapped: the last one wins",
     "CREATE TABLE t (id INTEGER PRIMARY KEY,"
     " n TEXT COLLATE NOCASE COLLATE BINARY UNIQUE)",
     "CREATE TABLE t (id INTEGER PRIMARY KEY,"
     " n TEXT COLLATE BINARY COLLATE NOCASE UNIQUE)",
     "INSERT INTO t (id, n) VALUES (1, 'a'); INSERT INTO t (id, n) VALUES (2, 'A')",
     "SELECT COUNT(*) FROM t"),
    # FOUND BY THE PROVER OF THESE FIXES (2026-09-26): NOT DEFERRABLE and
    # SET DEFAULT, each the tail of a REFERENCES clause, were read as a
    # second NOT NULL and a second DEFAULT, and only the last of those is
    # kept -- so the column's own NOT NULL, and its own DEFAULT, vanished.
    ("a NOT NULL before a REFERENCES that ends NOT DEFERRABLE",
     "CREATE TABLE t (id INTEGER PRIMARY KEY,"
     " up INTEGER NOT NULL REFERENCES t (id) NOT DEFERRABLE)",
     "CREATE TABLE t (id INTEGER PRIMARY KEY,"
     " up INTEGER REFERENCES t (id) NOT DEFERRABLE)",
     "INSERT INTO t (id, up) VALUES (1, NULL)", "SELECT id, up FROM t"),
    ("a DEFAULT before a REFERENCES that ends ON DELETE SET DEFAULT",
     "CREATE TABLE t (id INTEGER PRIMARY KEY,"
     " up INTEGER DEFAULT 5 REFERENCES t (id) ON DELETE SET DEFAULT)",
     "CREATE TABLE t (id INTEGER PRIMARY KEY,"
     " up INTEGER REFERENCES t (id) ON DELETE SET DEFAULT)",
     "INSERT INTO t (id, up) VALUES (5, NULL); INSERT INTO t (id) VALUES (7)",
     "SELECT id, up FROM t ORDER BY id"),
]


@pytest.mark.parametrize("label, record_sql, reference_sql, dml, probe",
                         BEHAVIOURAL_PAIRS, ids=[p[0] for p in BEHAVIOURAL_PAIRS])
def test_quoted_text_that_changes_behaviour_is_a_difference(
        tmp_path, label, record_sql, reference_sql, dml, probe):
    assert _outcome(record_sql, dml, probe) != _outcome(reference_sql, dml, probe), \
        f"{label}: the pair does not behave differently, so it proves nothing"
    assert schema_diff.table_differences(record_sql, reference_sql), label
    a, b = _two(tmp_path, record_sql, reference_sql)
    try:
        assert schema_diff.compare(a, b).differences, label
        definition = rebuild.Definition("t", reference_sql, (), 0 if "UNIQUE"
                                        not in reference_sql else 1)
        assert rebuild.differences_from(a, definition), (
            f"{label}: the migration would call the table already at its "
            f"definition, and skip it")
    finally:
        a.close()
        b.close()


def test_the_pragma_check_keeps_a_default_word_and_its_case(tmp_path, monkeypatch):
    """The check on the parser read PRAGMA's default text through the same
    lower-casing, so `live` and `LIVE` agreed there too. Blinded text, as in
    `test_the_pragmas_check_the_parser`: SQLite's own reading must name it."""
    monkeypatch.setattr(schema_diff, "table_differences",
                        lambda *args, **kwargs: [])
    a, b = _two(tmp_path,
                "CREATE TABLE t (id INTEGER PRIMARY KEY, src TEXT DEFAULT live)",
                "CREATE TABLE t (id INTEGER PRIMARY KEY, src TEXT DEFAULT LIVE)")
    try:
        found = schema_diff.compare(a, b).differences
    finally:
        a.close()
        b.close()
    assert [d.held_by for d in found] == ["record", "reference"]
    assert "default live," in found[0].property
    assert "default LIVE," in found[1].property
    assert schema_diff.default_tokens('"CURRENT_TIMESTAMP"') \
        != schema_diff.default_tokens("CURRENT_TIMESTAMP")
    assert schema_diff.default_tokens("current_timestamp") \
        == schema_diff.default_tokens("CURRENT_TIMESTAMP")


SNAPSHOTS = """CREATE TABLE snaps (
    id INTEGER PRIMARY KEY, prediction_id INTEGER NOT NULL, kind TEXT NOT NULL);
"""


@pytest.mark.parametrize("record_obj, reference_obj", [
    ("CREATE TRIGGER snaps_guard BEFORE DELETE ON snaps FOR EACH ROW"
     ' WHEN OLD.kind = "near_start" BEGIN SELECT RAISE(ABORT, \'kept\'); END',
     "CREATE TRIGGER snaps_guard BEFORE DELETE ON snaps FOR EACH ROW"
     ' WHEN OLD.kind = "NEAR_START" BEGIN SELECT RAISE(ABORT, \'kept\'); END'),
    ('CREATE INDEX snaps_near ON snaps (prediction_id) WHERE kind = "near_start"',
     'CREATE INDEX snaps_near ON snaps (prediction_id) WHERE kind = "NEAR_START"'),
], ids=["a trigger's WHEN", "an index's WHERE"])
def test_a_quoted_literal_in_a_trigger_or_an_index_keeps_its_case(
        tmp_path, record_obj, reference_obj):
    a, b = _two(tmp_path, SNAPSHOTS + record_obj + ";",
                SNAPSHOTS + reference_obj + ";")
    try:
        found = schema_diff.compare(a, b).differences
    finally:
        a.close()
        b.close()
    assert {d.held_by for d in found} == {"record", "reference"}
    assert any('"near_start"' in d.property for d in found)
    assert any('"NEAR_START"' in d.property for d in found)


def test_a_quoted_name_where_only_a_name_can_stand_is_still_cosmetic(tmp_path):
    """The live record's own cosmetic shapes (measured 2026-09-25): a table
    created under a quoted name, `REFERENCES "predictions"`, a trigger
    reading `FROM "predictions"`, and a quoted column in a CHECK and in an
    index -- where SQLite resolves it to the column -- stay cosmetic."""
    reference = """
CREATE TABLE predictions (id INTEGER PRIMARY KEY, created_utc TEXT NOT NULL);
CREATE TABLE snaps (
    id INTEGER PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions (id),
    kind TEXT NOT NULL CHECK (kind IN ('open', 'near')) COLLATE NOCASE,
    fetched_utc TEXT NOT NULL);
CREATE INDEX snaps_kind ON snaps (kind, prediction_id) WHERE kind != 'open';
CREATE TRIGGER snaps_after BEFORE INSERT ON snaps FOR EACH ROW
WHEN NEW.fetched_utc < (SELECT created_utc FROM predictions WHERE id = NEW.prediction_id)
BEGIN SELECT RAISE(ABORT, 'too early'); END;
"""
    record = """
CREATE TABLE predictions (id INTEGER PRIMARY KEY, created_utc TEXT NOT NULL);
CREATE TABLE "snaps" (
    [id] INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK ("kind" IN ('open', 'near')) COLLATE "NOCASE",
    fetched_utc TEXT NOT NULL,
    "prediction_id" INTEGER NOT NULL REFERENCES "predictions" ("id"));
CREATE INDEX "snaps_kind" ON [snaps] ("kind", `prediction_id`) WHERE "kind" != 'open';
CREATE TRIGGER snaps_after BEFORE INSERT ON "snaps" FOR EACH ROW
WHEN NEW."fetched_utc" < (SELECT created_utc FROM "predictions" WHERE id = NEW.prediction_id)
BEGIN SELECT RAISE(ABORT, 'too early'); END;
"""
    a, b = _two(tmp_path, record, reference)
    try:
        result = schema_diff.compare(a, b)
    finally:
        a.close()
        b.close()
    assert result.differences == []
    assert result.cosmetic == ["index snaps_kind", "table snaps",
                               "trigger snaps_after"]


def test_a_quoted_column_name_is_never_read_as_a_keyword():
    """A column named "check" is a column: only a bare word opens a clause."""
    shape = schema_diff.table_shape(
        'CREATE TABLE t ("check" TEXT, "default" INTEGER NOT NULL)')
    assert shape.order == ["check", "default"]
    assert shape.constraints == []
    assert shape.columns["default"] == (("integer",), [("not", "null")])
