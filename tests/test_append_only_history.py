"""The history tables hold to their words by rule (operator question 26).

Ruled 2026-09-28: "each of the five tables either gets the rules or its
description changes to what the code does; mlb_people's description changes
and it joins the upsert register." Built 2026-09-29. Found by question 15's
scan, which reads the append-only set from the schema's own rules:
`factor_scores` and `llm_calls` (CLAUDE.md, "Append-only history") and
`injury_reports`, `lineup_captures` and `weather_observed` ("append-only and
stamped", `schema.sql`) had no delete or update rule, so it read them as
ordinary tables.

MEASURED FIRST (FOLLOWUPS, "The history tables hold to their words"): the
shipped code only ever inserts into four of them and writes nothing to the
fifth, so all five got the rules -- no delete, no update, no replacement --
and `mlb_people`, which `mlb_loader.load_people` upserts at every load while
its comment said a row is written once, got words saying so. Each test here
builds its own scratch world with this tree's `db.init`; none opens the
record. The plantings are `plant.py::plant_a_deleted_row_of_the_append_only_
history`, `::plant_an_updated_row_...` and `::plant_a_replaced_row_...`.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from gridiron import audit, capture, config, db, rebuild, schema_diff
from gridiron.data import mlb_loader
from gridiron.factors import store
from gridiron.model import llm

TABLES = ("factor_scores", "llm_calls", "injury_reports", "lineup_captures",
          "weather_observed")
KINDS = ("no_delete", "no_update", "never_replaced",
         "never_replaced_by_the_number_written")
RULES = tuple(f"{t}_{k}" for t in TABLES for k in KINDS)

#: The number each table's rows are kept under: its own `id`, or the rowid
#: SQLite keeps for a table with none.
NUMBER = {"factor_scores": "id", "llm_calls": "id", "injury_reports": "rowid",
          "lineup_captures": "rowid", "weather_observed": "rowid"}

COLUMNS = {
    "factor_scores": ("sport", "computed_utc", "factor", "window", "n", "brier",
                      "log_loss", "note"),
    "llm_calls": ("called_utc", "day_utc", "purpose", "model", "input_tokens",
                  "output_tokens", "usd", "game_id", "ok", "error"),
    "injury_reports": ("sport", "season", "week", "team", "player_name",
                       "player_id", "position", "report_status",
                       "practice_status", "captured_utc"),
    "lineup_captures": ("game_id", "side", "slot", "player_id", "player_name",
                        "captured_utc", "source"),
    "weather_observed": ("game_id", "observed_utc", "source", "temp_f",
                         "wind_mph", "precip_pct"),
}


def _row(table: str, i: int) -> tuple:
    """Row `i` of a table in the test world (1 to 3 stored; 9 a newcomer)."""
    return {
        "factor_scores": ("nfl", f"2026-09-0{i}T00:00:00Z", "planted_factor",
                          "since_activation", 10 * i, 0.2, 0.6, None),
        "llm_calls": (f"2026-09-0{i}T00:00:00Z", f"2026-09-0{i}", "reasoning",
                      "a-model", 100, 10, 0.01 * i, "g1", 1, None),
        "injury_reports": ("nfl", 2026, 1, "KC", f"Player {i}", f"p{i}", "WR",
                           "Questionable", "LP", "2026-09-01T00:00:00Z"),
        "lineup_captures": ("g1", "home", i, 100 + i, f"Batter {i}",
                            "2026-09-01T00:00:00Z", "live"),
        "weather_observed": ("g1", f"2026-09-0{i}T00:00:00Z", "a source",
                             60.0 + i, 5.0, 0.0),
    }[table]


def _insert(table: str, verb: str = "INSERT", number: str | None = None) -> str:
    marks = ", ".join("?" for _ in COLUMNS[table])
    head = "" if number is None else f"{number.split('=')[0]}, "
    lead = "" if number is None else f"{number.split('=', 1)[1]}, "
    return (f"{verb} INTO {table} ({head}{', '.join(COLUMNS[table])})"
            f" VALUES ({lead}{marks})")


class _Handed:
    """Answers the rules' reading of a number with `first` and the row's
    with `then`: SQLite works a number named in a one-row insert out twice."""

    def __init__(self, first, then):
        self.first, self.then, self.calls = first, then, 0

    def __call__(self):
        self.calls += 1
        return self.first if self.calls == 1 else self.then


def _world(path: Path) -> sqlite3.Connection:
    """A scratch record with a game, a factor and rows 1-3 of each table."""
    conn = db.open_db(path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g1', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-10-01T23:00:00Z', 'scheduled', '2026-10-01')")
    conn.execute(
        "INSERT INTO factors (name, sport, added_utc, rationale) VALUES"
        " ('planted_factor', 'nfl', '2026-08-31T00:00:00Z',"
        " 'a factor made up only so that a score of it can be written')")
    for table in TABLES:
        for i in (1, 2, 3):
            conn.execute(_insert(table), _row(table, i))
    conn.commit()
    return conn


def _stored(conn: sqlite3.Connection, table: str) -> list[tuple]:
    n = NUMBER[table]
    return [tuple(r) for r in conn.execute(f"SELECT {n}, * FROM {table} ORDER BY {n}")]


def _everything(conn: sqlite3.Connection) -> dict:
    return {t: _stored(conn, t) for t in TABLES}


#: Per table, a stored value an update rewrites, and a column whose value
#: row 9 (the newcomer) does not share with row 1, which an upsert rewrites.
REWRITE = {"factor_scores": ("brier", 0.01, "computed_utc"),
           "llm_calls": ("usd", 99.0, "day_utc"),
           "injury_reports": ("report_status", "Out", "player_name"),
           "lineup_captures": ("player_id", 999, "slot"),
           "weather_observed": ("temp_f", -40.0, "observed_utc")}


#: (words the refusal says, statement, parameters) per table: a delete, an
#: update and a replacement of each kind the rules refuse, each of which
#: lands on 3c36861 (`test_every_form_lands_without_the_rules`).
def _forms(table: str) -> dict[str, tuple[str, str, tuple]]:
    n = NUMBER[table]
    new = _row(table, 9)
    column, value, upserted = REWRITE[table]
    forms = {
        "a row deleted": ("never deleted", f"DELETE FROM {table} WHERE {n} = 2", ()),
        "every row deleted": ("never deleted", f"DELETE FROM {table}", ()),
        "a value rewritten": ("never rewritten",
                              f"UPDATE {table} SET {column} = ? WHERE {n} = 1",
                              (value,)),
        "a number moved above every other by rowid":
            ("never rewritten", f"UPDATE {table} SET rowid = 90 WHERE {n} = 1", ()),
        "UPDATE OR REPLACE onto another's number by oid":
            ("never rewritten", f"UPDATE OR REPLACE {table} SET oid = 1 WHERE {n} = 2", ()),
        "INSERT OR REPLACE naming a stored number":
            ("never replaced", _insert(table, "INSERT OR REPLACE", f"{n}=1"), new),
        "REPLACE naming the newest number as _rowid_":
            ("never replaced", _insert(table, "REPLACE", "_rowid_=3"), new),
        "INSERT OR REPLACE naming a stored number as a real":
            ("never replaced", _insert(table, "INSERT OR REPLACE", f"{n}=2.0"), new),
        "an upsert naming a stored number":
            ("never replaced", _insert(table, "INSERT", f"{n}=1")
             + f" ON CONFLICT DO UPDATE SET {upserted} = excluded.{upserted}", new),
        "the number read as nothing to the rules and row 1's to the row":
            ("never replaced", _insert(table, "INSERT OR REPLACE",
                                       f"{n}=handed_nothing_then_1()"), new),
        "the number read as a free 99 to the rules and row 2's to the row":
            ("never replaced", _insert(table, "REPLACE",
                                       f"{n}=handed_free_then_2()"), new),
    }
    if n == "id":
        forms["the number read as nothing to the rules and the newest's to the row"] = (
            "never replaced", _insert(table, "INSERT OR REPLACE",
                                      "id=handed_nothing_then_3()"), new)
    else:
        key = list(_row(table, 1))
        forms["INSERT OR REPLACE on a stored key"] = (
            "never replaced", _insert(table, "INSERT OR REPLACE"),
            tuple(key[:3] + [999] + key[4:]) if table != "injury_reports"
            else tuple(key[:7] + ["Out"] + key[8:]))
        forms["a plain insert of a stored key"] = (
            "never replaced", _insert(table), _row(table, 1))
        forms["INSERT OR IGNORE of a stored key"] = (
            "never replaced", _insert(table, "INSERT OR IGNORE"), _row(table, 1))
    return forms


def _handed(conn) -> dict:
    functions = {"handed_nothing_then_1": _Handed(None, 1),
                 "handed_free_then_2": _Handed(99, 2),
                 "handed_nothing_then_3": _Handed(None, 3)}
    for name, function in functions.items():
        conn.create_function(name, 0, function)
    return functions


CASES = [(t, label) for t in TABLES for label in _forms(t)]


# --- the rules ---------------------------------------------------------------

def test_each_table_carries_the_four_rules_and_is_in_the_append_only_set(tmp_path):
    conn = db.open_db(tmp_path / "fresh.db")
    try:
        held = {r[0]: r[1] for r in conn.execute(
            "SELECT name, tbl_name FROM sqlite_master WHERE type = 'trigger'"
            " AND tbl_name IN ({})".format(", ".join("?" for _ in TABLES)), TABLES)}
    finally:
        conn.close()
    assert sorted(held) == sorted(RULES)
    assert all(held[f"{t}_{k}"] == t for t in TABLES for k in KINDS)
    protected, _writes = audit._the_schemas_rules(
        audit._replace_scan_sources(config.PACKAGE_ROOT))
    for table in TABLES:
        assert protected[table] == {f"{table}_no_delete", f"{table}_no_update"}
    # mlb_people is a cache, not history: no rule, and not in the set.
    assert "mlb_people" not in protected


def test_the_rules_carry_the_words_and_name_no_columns():
    """A rule naming a column is not run for an update naming rowid, oid or
    _rowid_ (question 13, measured): the update rules name none."""
    schema = db.SCHEMA_PATH.read_text(encoding="utf-8")
    for table in TABLES:
        update = re.search(
            rf"TRIGGER IF NOT EXISTS {table}_no_update\s+BEFORE UPDATE (\w+)", schema)
        assert update and update.group(1) == "ON", update and update.group(0)
        for kind in KINDS:
            body = re.search(rf"TRIGGER IF NOT EXISTS {table}_{kind}\b(.*?)END;",
                             schema, re.S).group(1)
            assert "GRIDIRON APPEND-ONLY HISTORY" in body


@pytest.mark.parametrize("table,label", CASES, ids=[f"{t}: {l}" for t, l in CASES])
def test_no_row_is_deleted_rewritten_or_replaced(tmp_path, table, label):
    conn = _world(tmp_path / "world.db")
    _handed(conn)
    words, statement, params = _forms(table)[label]
    before = _everything(conn)
    try:
        with pytest.raises(sqlite3.IntegrityError) as refused:
            conn.execute(statement, params)
        conn.rollback()
        assert "APPEND-ONLY HISTORY" in str(refused.value)
        assert words in str(refused.value), str(refused.value)
        assert _everything(conn) == before
    finally:
        conn.close()


@pytest.mark.parametrize("table,label", CASES, ids=[f"{t}: {l}" for t, l in CASES])
def test_every_form_lands_without_the_rules(tmp_path, table, label):
    """Proof the forms are real: on the world as 3c36861 builds it -- these
    five tables with no rule -- each changes the table (a duplicate of a
    stored key is refused by the key itself, and OR IGNORE skips it)."""
    conn = _world(tmp_path / "world.db")
    _handed(conn)
    for name in RULES:
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
    _words, statement, params = _forms(table)[label]
    before = _stored(conn, table)
    try:
        if label == "a plain insert of a stored key":
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
                conn.execute(statement, params)
        elif label == "INSERT OR IGNORE of a stored key":
            assert conn.execute(statement, params).rowcount == 0
        else:
            conn.execute(statement, params)
            assert _stored(conn, table) != before, label
    finally:
        conn.close()


def test_the_rule_on_the_number_written_is_what_stops_a_number_read_twice(tmp_path):
    """With it alone dropped, each form read twice writes over a stored row."""
    conn = _world(tmp_path / "world.db")
    functions = _handed(conn)
    for table in TABLES:
        conn.execute(f"DROP TRIGGER {table}_never_replaced_by_the_number_written")
    try:
        for table in TABLES:
            for label, (_w, statement, params) in _forms(table).items():
                if "read as" not in label:
                    continue
                for function in functions.values():
                    function.calls = 0
                before = _stored(conn, table)
                conn.execute(statement, params)
                assert _stored(conn, table) != before
                assert len(_stored(conn, table)) == len(before), (table, label)
                conn.rollback()
    finally:
        conn.close()


def _empty_world(path: Path) -> sqlite3.Connection:
    """A scratch record with a game and a factor and no row of the five
    tables -- as a fresh build has them, and the record `weather_observed`."""
    conn = db.open_db(path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g1', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-10-01T23:00:00Z', 'scheduled', '2026-10-01')")
    conn.execute(
        "INSERT INTO factors (name, sport, added_utc, rationale) VALUES"
        " ('planted_factor', 'nfl', '2026-08-31T00:00:00Z',"
        " 'a factor made up only so that a score of it can be written')")
    conn.commit()
    return conn


@pytest.mark.parametrize("table", TABLES)
def test_no_row_under_minus_one_is_ever_written_over(tmp_path, table):
    """THE -1 FORM (2026-09-29, question 26's prover; measured getting past
    the rules as first built). The insert rule is shown -1 when SQLite
    chooses a number, so it cannot look up a row stored under -1. On a
    table holding no row, a first row named -1 landed, and a one-row INSERT
    OR REPLACE naming -1 -- a plain number, read once -- then wrote another
    row over it on the three tables with no mark. The rule on the number
    written refuses a row landing under -1 there; on the two numbered
    tables SQLite's mark, written at 0 by the first insert, holds it. A
    first row numbered by SQLite still lands either way."""
    conn = _empty_world(tmp_path / "world.db")
    n = NUMBER[table]
    try:
        if n == "rowid":
            with pytest.raises(sqlite3.IntegrityError, match="never under -1"):
                conn.execute(_insert(table, "INSERT", "rowid=-1"), _row(table, 1))
            conn.rollback()
        else:
            conn.execute(_insert(table, "INSERT", "id=-1"), _row(table, 1))
            conn.commit()
            assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?",
                                (table,)).fetchone()[0] == 0
        before = _stored(conn, table)
        with pytest.raises(sqlite3.IntegrityError, match="never replaced"):
            conn.execute(_insert(table, "INSERT OR REPLACE", f"{n}=-1"),
                         _row(table, 9))
        conn.rollback()
        assert _stored(conn, table) == before
        conn.execute(_insert(table), _row(table, 2))
        conn.commit()
        assert len(_stored(conn, table)) == len(before) + 1
    finally:
        conn.close()


@pytest.mark.parametrize("table", TABLES)
def test_the_minus_one_form_writes_over_a_row_without_the_rule_on_the_number_written(
        tmp_path, table):
    """Proof the -1 form is real: with the rule on the number written
    dropped (as 3c36861 has none), the second insert writes over the first
    on every table."""
    conn = _empty_world(tmp_path / "world.db")
    n = NUMBER[table]
    try:
        conn.execute(f"DROP TRIGGER IF EXISTS {table}_never_replaced_by_the_number_written")
        conn.execute(_insert(table, "INSERT", f"{n}=-1"), _row(table, 1))
        first = _stored(conn, table)
        conn.execute(_insert(table, "INSERT OR REPLACE", f"{n}=-1"), _row(table, 9))
        after = _stored(conn, table)
        assert len(first) == len(after) == 1 and after != first
        assert after[0][0] == -1
    finally:
        conn.close()


MARK_MOVED = {"set back": "UPDATE sqlite_sequence SET seq = 0 WHERE name = ?",
              "removed": "DELETE FROM sqlite_sequence WHERE name = ?"}


@pytest.mark.parametrize("moved", MARK_MOVED)
@pytest.mark.parametrize("table", ("factor_scores", "llm_calls"))
def test_with_the_mark_moved_a_row_below_the_newest_is_still_held(tmp_path, table, moved):
    """THE MARK MOVED FIRST (2026-09-29, question 26's prover; question 24's
    shape). On the two numbered tables the mark alone refused every form,
    so the rule on the number written's "below any stored one" was proved
    by none: with the mark set back to 0, or its row removed, by a
    statement first, a number read as nothing to the rules and row 1's to
    the row is held by that clause alone -- and lands without the rule."""
    for rules in (True, False):
        conn = _world(tmp_path / f"world_{rules}.db")
        _handed(conn)
        if not rules:
            conn.execute(f"DROP TRIGGER {table}_never_replaced_by_the_number_written")
        before = _stored(conn, table)
        try:
            conn.execute(MARK_MOVED[moved], (table,))
            statement = _insert(table, "INSERT OR REPLACE", "id=handed_nothing_then_1()")
            if rules:
                with pytest.raises(sqlite3.IntegrityError, match="never replaced"):
                    conn.execute(statement, _row(table, 9))
                conn.rollback()
                assert _stored(conn, table) == before
            else:
                conn.execute(statement, _row(table, 9))
                assert before[0] not in _stored(conn, table)
        finally:
            conn.close()


def test_every_key_of_each_table_is_one_the_rule_reads(tmp_path):
    """A replacement collides on a unique key, and the insert rule reads
    every key each table has -- its number and its primary key -- so a
    table that gains another key fails here until its rule reads it too."""
    conn = _world(tmp_path / "world.db")
    try:
        for table in TABLES:
            keys = []
            for index in conn.execute(f"PRAGMA index_list({table})"):
                if index[2]:
                    keys.append(tuple(r[2] for r in conn.execute(
                        f"PRAGMA index_info({index[1]})")))
            primary = tuple(r[1] for r in sorted(
                conn.execute(f"PRAGMA table_info({table})"), key=lambda r: r[5]) if r[5])
            expected = {"factor_scores": [], "llm_calls": []}.get(
                table, [primary])
            assert keys == expected, (table, keys)
            rule = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?",
                (f"{table}_never_replaced",)).fetchone()[0]
            for key in keys:
                for column in key:
                    assert f".{column} = NEW.{column}" in rule, (table, column)
            assert f"= NEW.{NUMBER[table]}" in rule
    finally:
        conn.close()


# --- the lawful writes -------------------------------------------------------

def test_the_writers_still_write(tmp_path, monkeypatch):
    """Each table's own writer, as the shipped code writes it, and a capture
    repeated in the same second, which writes nothing and raises nothing."""
    conn = _world(tmp_path / "world.db")
    season = config.SPORT_CURRENT_SEASON.get("nfl", config.CURRENT_SEASON)
    conn.execute(
        "INSERT INTO injuries (season, week, team, player_id, player_name,"
        " position, report_status, practice_status) VALUES"
        " (?, 1, 'KC', 'p1', 'Player 1', 'WR', 'Questionable', 'LP')", (season,))
    conn.execute(
        "INSERT INTO mlb_lineups (game_id, side, slot, player_id, player_name,"
        " recorded_utc, source) VALUES ('g1', 'home', 1, 101, 'Batter 1',"
        " '2026-09-29T11:00:00Z', 'live')")
    conn.commit()
    monkeypatch.setattr(capture, "utcnow", lambda: "2026-09-29T12:00:00Z")
    before = {t: len(_stored(conn, t)) for t in TABLES}
    try:
        store.record_factor_score(conn, "nfl", "planted_factor", "season:2026",
                                  40, 0.21, 0.61)
        llm.record_call(conn, purpose="reasoning", model="a-model",
                        input_tokens=5, output_tokens=5, usd=0.001, game_id="g1")
        assert capture.capture_injuries(conn, "nfl") == 1
        assert capture.capture_injuries(conn, "nfl") == 0
        assert capture.capture_lineups(conn) == 1
        assert capture.capture_lineups(conn) == 0
        conn.execute("INSERT INTO weather_observed (game_id, observed_utc,"
                     " source) VALUES ('g1', '2026-09-29T12:00:00Z', 'a source')")
        conn.commit()
        assert {t: len(_stored(conn, t)) for t in TABLES} == {
            t: before[t] + 1 for t in TABLES}
    finally:
        conn.close()


#: The two capture statements as they stood on 3c36861, kept here to be run
#: side by side with the writers that replaced them.
OLD_INJURY_CAPTURE = (
    "INSERT OR IGNORE INTO injury_reports (sport, season, week, team,"
    " player_name, player_id, position, report_status,"
    " practice_status, captured_utc) VALUES (?,?,?,?,?,?,?,?,?,?)")
OLD_LINEUP_CAPTURE = (
    "INSERT OR IGNORE INTO lineup_captures (game_id, side, slot,"
    " player_id, player_name, captured_utc, source)"
    " VALUES (?,?,?,?,?,?,'live')")


def _old_capture(conn, stamp):
    """The two captures as 3c36861 wrote them, for one stamp."""
    season = config.SPORT_CURRENT_SEASON.get("nfl", config.CURRENT_SEASON)
    written = 0
    for row in conn.execute(
            "SELECT season, week, team, player_id, player_name, position,"
            " report_status, practice_status FROM injuries WHERE season = ?",
            (season,)).fetchall():
        if not row["player_name"]:
            continue
        cur = conn.execute(OLD_INJURY_CAPTURE, (
            "nfl", row["season"], row["week"], row["team"], row["player_name"],
            row["player_id"], row["position"], row["report_status"],
            row["practice_status"], stamp))
        written += max(cur.rowcount, 0)
    for row in conn.execute(
            "SELECT l.game_id, l.side, l.slot, l.player_id, l.player_name"
            "  FROM mlb_lineups l JOIN games g ON g.id = l.game_id"
            " WHERE g.kickoff_utc IS NOT NULL AND g.kickoff_utc > ?"
            "   AND g.status = 'scheduled'", (stamp,)).fetchall():
        cur = conn.execute(OLD_LINEUP_CAPTURE, (
            row["game_id"], row["side"], row["slot"], row["player_id"],
            row["player_name"], stamp))
        written += max(cur.rowcount, 0)
    conn.commit()
    return written


def _capture_world(path: Path, rules: bool) -> sqlite3.Connection:
    conn = _world(path)
    if not rules:
        for name in RULES:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
    season = config.SPORT_CURRENT_SEASON.get("nfl", config.CURRENT_SEASON)
    for i, name in enumerate(("A. One", "B. Two", "", None, "C. Three")):
        conn.execute(
            "INSERT INTO injuries (season, week, team, player_id, player_name,"
            " position, report_status, practice_status) VALUES"
            " (?, 2, ?, ?, ?, 'WR', 'Out', 'DNP')",
            (season, "KC" if i % 2 else "BUF", f"i{i}", name))
    for slot in range(1, 10):
        conn.execute(
            "INSERT INTO mlb_lineups (game_id, side, slot, player_id,"
            " player_name, recorded_utc, source) VALUES ('g1', 'away', ?, ?,"
            " ?, '2026-09-29T11:00:00Z', 'live')", (slot, 200 + slot, f"B{slot}"))
    conn.commit()
    return conn


def test_the_capture_writers_write_what_or_ignore_wrote_side_by_side(
        tmp_path, monkeypatch):
    """THE SAME ROWS UNDER THE SAME ROWIDS (2026-09-29): the released OR
    IGNORE statements on a world without the rules, and the writers that
    replaced them on a world with the rules, each run for three passes --
    two in one second, a third a second later -- write the same rows, under
    the same rowids, and count the same."""
    old = _capture_world(tmp_path / "old.db", rules=False)
    new = _capture_world(tmp_path / "new.db", rules=True)
    try:
        counts_old, counts_new = [], []
        for stamp in ("2026-09-29T12:00:00Z", "2026-09-29T12:00:00Z",
                      "2026-09-29T12:00:01Z"):
            counts_old.append(_old_capture(old, stamp))
            monkeypatch.setattr(capture, "utcnow", lambda stamp=stamp: stamp)
            counts_new.append(capture.capture_injuries(new, "nfl")
                              + capture.capture_lineups(new))
        assert counts_old == counts_new == [12, 0, 12]
        for table in ("injury_reports", "lineup_captures"):
            assert _stored(old, table) == _stored(new, table)
    finally:
        old.close()
        new.close()


def test_or_ignore_of_a_stored_capture_is_refused_by_the_rules(tmp_path):
    """Why the writers changed: a rule's refusal is not a conflict OR IGNORE
    resolves, so the released statement's repeat in the same second, which
    skipped the row, is refused under the rules."""
    conn = _capture_world(tmp_path / "world.db", rules=True)
    try:
        assert _old_capture(conn, "2026-09-29T12:00:00Z") == 12
        with pytest.raises(sqlite3.IntegrityError, match="never replaced"):
            _old_capture(conn, "2026-09-29T12:00:00Z")
    finally:
        conn.close()


# --- the record gets them through db.init ------------------------------------

def test_an_older_record_gains_the_rules_through_init_and_no_row_moves(tmp_path):
    """A record without the rules -- every release until this one -- gains
    exactly them, with a fresh build's text; every row and every mark stays;
    a second open adds nothing; and a delete is refused from the first open."""
    conn = _world(tmp_path / "record.db")
    for name in RULES:
        conn.execute(f"DROP TRIGGER {name}")
    conn.commit()

    def objects(c):
        return {(r[0], r[1]): r[2] for r in c.execute(
            "SELECT type, name, sql FROM sqlite_master")}

    def sums(c):
        return {t: rebuild.column_checksums(c, t) for t in TABLES}

    marks = [tuple(r) for r in conn.execute("SELECT * FROM sqlite_sequence ORDER BY name")]
    before, rows = objects(conn), sums(conn)
    db.init(conn)
    after = objects(conn)
    assert set(after) - set(before) == {("trigger", n) for n in RULES}
    assert all(after[k] == before[k] for k in before)
    fresh = db.open_db(tmp_path / "fresh.db")
    try:
        for name in RULES:
            assert after[("trigger", name)] == objects(fresh)[("trigger", name)]
        assert schema_diff.compare(conn, fresh).differences == []
    finally:
        fresh.close()
    assert sums(conn) == rows
    assert [tuple(r) for r in conn.execute(
        "SELECT * FROM sqlite_sequence ORDER BY name")] == marks
    db.init(conn)
    assert objects(conn) == after and sums(conn) == rows
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM llm_calls WHERE id = 1")
    conn.rollback()
    conn.close()


def test_a_widened_factor_scores_keeps_its_rules(tmp_path, monkeypatch):
    """`factor_scores` is rebuilt through the rebuild door when a newly
    declared sport widens it; the door recreates its rules from the schema's
    text after the copy, so the widened table refuses a delete and a
    replacement, its rows and mark as they were."""
    conn = _world(tmp_path / "record.db")
    text = db.SCHEMA_PATH.read_text(encoding="utf-8")
    sixth = tmp_path / "schema_with_a_sixth_sport.sql"
    sixth.write_text(text.replace("'ufc')", "'ufc','xfl')"), encoding="utf-8")
    monkeypatch.setattr(config, "SPORTS", tuple(config.SPORTS) + ("xfl",))
    monkeypatch.setattr(db, "SCHEMA_PATH", sixth)
    rows = _stored(conn, "factor_scores")
    mark = conn.execute("SELECT seq FROM sqlite_sequence"
                        " WHERE name = 'factor_scores'").fetchone()[0]
    try:
        widened = db.widen_sport_checks(conn)
        assert any(w.startswith("factor_scores") for w in widened)
        assert "'xfl'" in conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'factor_scores'").fetchone()[0]
        assert {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            " AND tbl_name = 'factor_scores'")} == {
            f"factor_scores_{k}" for k in KINDS}
        assert _stored(conn, "factor_scores") == rows
        assert conn.execute("SELECT seq FROM sqlite_sequence"
                            " WHERE name = 'factor_scores'").fetchone()[0] == mark
        with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
            conn.execute("DELETE FROM factor_scores")
        conn.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="never replaced"):
            conn.execute(_insert("factor_scores", "INSERT OR REPLACE", "id=1"),
                         _row("factor_scores", 9))
        conn.rollback()
    finally:
        conn.close()


def test_the_recovery_of_a_half_finished_widening_passes_the_rules(tmp_path):
    """`db._finish_widening_table` copies `factor_scores_narrow` back into a
    table the schema script made, rules and all, when an old widening died
    half way: a plain insert of every row whose number is not stored, in
    order, each above the rebuilt table's mark -- none refused."""
    conn = _world(tmp_path / "record.db")
    for name in (f"factor_scores_{k}" for k in KINDS):
        conn.execute(f"DROP TRIGGER {name}")
    conn.execute("ALTER TABLE factor_scores RENAME TO factor_scores_narrow")
    conn.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
    kept = [tuple(r) for r in conn.execute(
        "SELECT * FROM factor_scores_narrow ORDER BY id")]
    try:
        said = db._finish_widening_table(conn, "factor_scores")
        assert said == "factor_scores (3 rows)"
        assert [tuple(r) for r in conn.execute(
            "SELECT * FROM factor_scores ORDER BY id")] == kept
        with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
            conn.execute("DELETE FROM factor_scores")
        conn.rollback()
    finally:
        conn.close()


# --- mlb_people: words that say what the code does ---------------------------

def test_mlb_people_is_described_as_the_cache_it_is_and_stays_registered():
    """Question 26: "mlb_people's description changes and it joins the upsert
    register." It joined on 2026-09-27, and the register only shrinks; its
    words said a row is written once, and load_people upserts it."""
    schema = db.SCHEMA_PATH.read_text(encoding="utf-8")
    comment = schema[:schema.index("CREATE TABLE IF NOT EXISTS mlb_people")]
    comment = " ".join(comment[comment.rindex("-- Handedness"):]
                       .replace("--", " ").split())
    assert "so a row is written once" not in comment
    assert "UPSERTED AT EACH LOAD, NOT APPEND-ONLY" in comment
    doc = " ".join(mlb_loader.load_people.__doc__.split())
    assert "so a player is fetched once and never again" not in doc
    assert "UPSERTED AT EACH LOAD, NOT APPEND-ONLY" in doc
    entry = ("gridiron/data/mlb_loader.py", "load_people", "mlb_people")
    assert entry in audit.UPSERTS_REGISTERED
    assert entry in audit.UPSERTS_REGISTERED_ON_2026_09_27


def test_load_people_upserts_as_its_words_say(tmp_path, monkeypatch):
    """What the words say, run: a player with both hands unknown is asked
    again and overwritten (name, sides, position; `fetched_utc` as first
    written); one with either known is not asked; a new one is inserted."""
    import json

    conn = db.open_db(tmp_path / "people.db")
    for pid in (1, 2, 3):
        conn.execute(
            "INSERT INTO mlb_batter_games (player_id, game_pk, game_date,"
            " team, season) VALUES (?, 1, '2026-09-01', 'AAA', 2026)", (pid,))
    conn.execute("INSERT INTO mlb_people (player_id, full_name, bat_side,"
                 " pitch_hand, primary_position, fetched_utc) VALUES"
                 " (1, 'Old Name', NULL, NULL, NULL, '2026-08-30T00:00:00Z'),"
                 " (2, 'Known', 'L', NULL, 'CF', '2026-08-30T00:00:00Z')")
    conn.commit()
    asked: list[list[int]] = []

    def fetch(_conn, url, immutable=False):
        ids = [int(x) for x in url.split("personIds=")[1].split("&")[0].split(",")]
        asked.append(ids)
        return json.dumps({"people": [
            {"id": i, "fullName": f"Player {i}", "batSide": {"code": "R"},
             "pitchHand": {"code": "R"}, "primaryPosition": {"abbreviation": "P"}}
            for i in ids]}).encode()

    monkeypatch.setattr(mlb_loader.sources, "fetch", fetch)
    try:
        assert mlb_loader.load_people(conn) == 2
        assert asked == [[1, 3]]
        rows = {r[0]: tuple(r) for r in conn.execute(
            "SELECT player_id, full_name, bat_side, pitch_hand,"
            " primary_position, fetched_utc FROM mlb_people")}
        assert rows[1][:5] == (1, "Player 1", "R", "R", "P")
        assert rows[1][5] == "2026-08-30T00:00:00Z"
        assert rows[2] == (2, "Known", "L", None, "CF", "2026-08-30T00:00:00Z")
        assert rows[3][:5] == (3, "Player 3", "R", "R", "P")
    finally:
        conn.close()
