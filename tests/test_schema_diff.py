"""The schema, compared by what it does (schema ruling 1 of 2026-09-24,
built 2026-09-25).

"The diff check compares after normalising quoting, whitespace, comments and
column order, and fails on any difference in behaviour." Each of the four is
normalised here on its own, and a CHECK, a DEFAULT, a trigger and an index
that differ are each caught; `tools/guards/plant.py` plants a new difference
on a whole record and requires the gate's check to name it.
"""

from __future__ import annotations

from gridiron import db, schema_diff

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
