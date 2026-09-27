"""No stored prediction is replaced by any statement (operator question 15).

Ruled 2026-09-27, third set: "Q15: first in the order. Fix predictions the
same way as Q13, own commit, planting that gets through on the unfixed
code." Found by question 13's build: `predictions_no_delete` refuses a
delete, and SQLite runs no delete rule for a replacement unless recursive
triggers are on, so OR REPLACE went round LAW 3's own table exactly as it
went round `recommendations` (`test_recommend.py`, question 13, is the
precedent: its forms, its words, its order, its older record and its
number read twice, applied here to the three keys of `predictions`).

Scratch worlds only.
"""
from __future__ import annotations

import re
import sqlite3

import pytest

from gridiron import db, resolve, run
from gridiron.factors import store
from gridiron.model import activation, baseline, predict, prompt_record
from tests.conftest import asks_only
from tests.test_predict import StubClient

RULES = ("predictions_never_replaced",
         "predictions_never_replaced_by_update",
         "predictions_never_replaced_by_the_number_written")
COLS = ("created_utc, sport, game_id, market_type, subject, line_asked,"
        " model_prob, model_side, predictor, pass_kind, factor_set_version,"
        " factors_json, reasoning")
STAMP = "2026-09-06T20:50:15Z"
LATER = "2026-09-08T00:00:00Z"
#: The cite of the world's reasoning forecast, written before the prompt
#: record binds (the world's instant is when `db.init` ran), so the prompt
#: record's own rule does not look at it -- the one-forecast key does.
CITE = '{{"reasoning_prompt_id": 7}}'


def _world(tmp_path):
    """Two forecasts on games of their own, a reasoning forecast citing a
    sent prompt, the final pass of the first forecast's question, and a
    voided forecast, the newest. Nothing points at the first four."""
    conn = db.open_db(tmp_path / "world.db")
    for n in range(1, 7):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " 'AAA', 'BBB', '2026-09-09T22:45:00Z', 'scheduled', '2026-09-09')",
            (f"g{n}",))
    ids = {}
    for key, game, predictor, pass_kind, factors in (
            ("p1", "g1", "statistical", "early", "{}"),
            ("p2", "g2", "statistical", "early", "{}"),
            ("llm", "g4", "llm", "early", '{"reasoning_prompt_id": 7}'),
            ("final", "g1", "statistical", "final", "{}"),
            ("void", "g3", "statistical", "early", "{}")):
        ids[key] = conn.execute(
            f"INSERT INTO predictions ({COLS}) VALUES (?, 'mlb', ?, 'moneyline',"
            " 'BBB', NULL, 0.61, 'win', ?, ?, 'fs2', ?, 'as stored')",
            (STAMP, game, predictor, pass_kind, factors)).lastrowid
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, '2026-09-08T00:00:00Z', 'voided in this test world')",
                 (ids["void"],))
    conn.commit()
    return conn, ids


def _stored(conn):
    return ([tuple(r) for r in conn.execute("SELECT * FROM predictions ORDER BY id")],
            [tuple(r) for r in conn.execute(
                "SELECT * FROM prediction_voids ORDER BY prediction_id")])


def _newcomer(number, game="g5", *, verb="INSERT OR REPLACE", column="id",
              predictor="statistical", pass_sql="'early'", factors="{{}}",
              created=LATER):
    head = "" if number is None else f"{column}, "
    lead = "" if number is None else f"{number}, "
    return (f"{verb} INTO predictions ({head}{COLS}) VALUES ({lead}'{created}',"
            f" 'mlb', '{game}', 'moneyline', 'BBB', NULL, 0.99, 'win',"
            f" '{predictor}', {pass_sql}, 'fs2', '{factors}', 'newcomer')")


#: Every statement found that takes a stored prediction's place or rewrites
#: one through an insert, each with whether it changes the table on the
#: tree before the rules (98091d2, measured 2026-09-27); the three that do
#: not are held so a later rule cannot open them.
FORMS = {
    "insert or replace naming a stored number":
        (_newcomer("{p1}"), True),
    "replace naming a stored number as rowid":
        (_newcomer("{p1}", verb="REPLACE", column="rowid"), True),
    "insert or replace naming a stored number as text":
        (_newcomer("'{p1}'"), True),
    "insert or replace naming a stored number as a real":
        (_newcomer("{p1}.0"), True),
    "insert or replace on a stored question and pass":
        (_newcomer(None, "g1"), True),
    "insert or replace on a stored question and pass, stamped as it was":
        (_newcomer(None, "g1", created=STAMP), True),
    "insert or replace on a stored question, its pass given as null":
        (_newcomer(None, "g1", pass_sql="NULL"), True),
    "insert or replace colliding with two rows at once":
        (f"INSERT OR REPLACE INTO predictions (id, {COLS}) SELECT {{p2}},"
         f" '{LATER}', 'mlb', 'g1', 'moneyline', 'BBB', NULL, 0.99, 'win',"
         f" 'statistical', 'early', 'fs2', '{{{{}}}}', 'newcomer'", True),
    "insert or replace onto a voided one on its own question":
        (_newcomer("{void}", "g3"), True),
    "insert or replace citing a stored reasoning forecast's sent prompt":
        (_newcomer(None, predictor="llm", factors=CITE), True),
    "update or replace onto another's number by id":
        ("UPDATE OR REPLACE predictions SET id = {p1} WHERE id = {p2}", True),
    "update or replace onto another's number by rowid":
        ("UPDATE OR REPLACE predictions SET rowid = {p1} WHERE id = {p2}", True),
    "update or replace onto another's number by oid":
        ("UPDATE OR REPLACE predictions SET oid = {p1} WHERE id = {p2}", True),
    "update or replace onto another's number by _rowid_":
        ("UPDATE OR REPLACE predictions SET _rowid_ = {p1} WHERE id = {p2}", True),
    "update or replace onto another's question by its pass":
        ("UPDATE OR REPLACE predictions SET pass_kind = 'early' WHERE id = {final}",
         True),
    "update or replace onto another's question, its pass set to null":
        ("UPDATE OR REPLACE predictions SET pass_kind = NULL WHERE id = {final}",
         True),
    "an upsert rewriting a stored one's pass":
        (_newcomer("{p2}", verb="INSERT")
         + " ON CONFLICT(id) DO UPDATE SET pass_kind = 'final'", True),
    "an upsert writing a stored one's resolution":
        (_newcomer("{p2}", verb="INSERT")
         + " ON CONFLICT(id) DO UPDATE SET resolved_utc = '2026-09-10T00:00:00Z',"
           " outcome = 1", True),
    "an upsert on a stored question rewriting its pass":
        (_newcomer(None, "g2", verb="INSERT")
         + " ON CONFLICT(game_id, market_type, subject, predictor,"
           " factor_set_version, pass_kind) DO UPDATE SET pass_kind = 'final'",
         True),
    "update or replace onto another's question by its game":
        ("UPDATE OR REPLACE predictions SET game_id = 'g1' WHERE id = {p2}", False),
    "an upsert rewriting what a stored one said":
        (_newcomer("{p1}", verb="INSERT")
         + " ON CONFLICT(id) DO UPDATE SET model_prob = excluded.model_prob",
         False),
    "an upsert moving a stored one onto another's number":
        (_newcomer("{p2}", verb="INSERT") + " ON CONFLICT(id) DO UPDATE SET id = {p1}",
         False),
    "a plain second answer to a stored question":
        (_newcomer(None, "g1", verb="INSERT"), False),
}


@pytest.mark.parametrize("form", sorted(FORMS))
def test_no_stored_prediction_is_replaced_by_any_statement(tmp_path, form):
    """EACH FORM REFUSED UNDER LAW 3, in the replace rules' words -- they run
    first, so even those an older rule or the key already refused are
    refused by them -- and every forecast and void exactly as stored."""
    conn, ids = _world(tmp_path)
    before = _stored(conn)
    with pytest.raises(sqlite3.IntegrityError) as refused:
        conn.execute(FORMS[form][0].format(**ids))
    conn.rollback()
    assert "LAW 3" in str(refused.value)
    assert predict.NEVER_REPLACED in str(refused.value)
    assert "UNIQUE" not in str(refused.value)
    assert _stored(conn) == before


def test_the_forms_replace_without_the_rules(tmp_path):
    """THE REPLACEMENT IS REAL: with the three rules dropped, every form that
    changed the table on the unfixed tree changes it here -- a stored
    forecast gone or written over -- and the voided one's void is left
    withdrawing a forecast nobody voided."""
    conn, ids = _world(tmp_path)
    for name in RULES:
        conn.execute(f"DROP TRIGGER {name}")
    before = _stored(conn)
    for form, (statement, changes) in FORMS.items():
        if not changes:
            continue
        conn.execute(statement.format(**ids))
        assert _stored(conn) != before, form
        conn.rollback()
    conn.execute(FORMS["insert or replace onto a voided one on its own question"][0]
                 .format(**ids))
    row = conn.execute("SELECT p.model_prob, p.reasoning FROM predictions p"
                       " JOIN prediction_voids v ON v.prediction_id = p.id").fetchone()
    assert tuple(row) == (0.99, "newcomer")
    conn.rollback()


def test_a_pass_given_as_null_is_read_as_any_pass(tmp_path):
    """THE KEY'S ONE DEFAULT. Under OR REPLACE SQLite writes a NULL pass as
    'early' only after the rules have seen NULL, so a rule comparing the pass
    as given lets both NULL forms remove the stored early pass; the rules as
    built read a NULL pass as either pass and refuse them."""
    clause = "(NEW.pass_kind IS NULL OR p.pass_kind = NEW.pass_kind)"
    nulls = ("insert or replace on a stored question, its pass given as null",
             "update or replace onto another's question, its pass set to null")
    conn, ids = _world(tmp_path)
    for name in RULES[:2]:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?",
                           (name,)).fetchone()[0]
        assert clause in sql, name
        conn.execute(f"DROP TRIGGER {name}")
        conn.execute(sql.replace(clause, "p.pass_kind = NEW.pass_kind"))
    conn.commit()
    before = _stored(conn)
    for form in nulls:
        conn.execute(FORMS[form][0].format(**ids))
        after = {r[0]: r for r in _stored(conn)[0]}
        assert ids["p1"] not in after, form            # the early pass is gone
        conn.rollback()
    assert _stored(conn) == before


def test_every_key_of_the_table_is_one_the_rules_read(tmp_path):
    """THE RULES READ EVERY KEY THE TABLE HAS: its number and the two unique
    indexes. A key added later is a new way to replace a stored forecast, so
    this fails until the rules read it too."""
    conn = db.open_db(tmp_path / "fresh.db")
    unique = {r[1] for r in conn.execute("PRAGMA index_list(predictions)") if r[2]}
    assert unique == {"pred_one_answer_per_question_per_pass",
                      "pred_cites_one_sent_prompt"}, unique
    info = {r[1]: r[5] for r in conn.execute("PRAGMA table_info(predictions)")}
    assert [c for c, pk in info.items() if pk] == ["id"]
    rules = dict(conn.execute("SELECT name, sql FROM sqlite_master"
                              " WHERE name IN (?, ?)", RULES[:2]).fetchall())
    assert set(rules) == set(RULES[:2])
    for sql in rules.values():
        for column in ("game_id", "market_type", "subject", "predictor",
                       "factor_set_version", "pass_kind"):
            assert f"p.{column} = NEW.{column}" in sql, column
        assert f"'$.{prompt_record.CITE}'" in sql
        assert "p.id = NEW.id" in sql
    conn.close()


def test_the_lawful_writes_are_untouched(league, monkeypatch):
    """THE WRITERS DO NOT CHANGE: the pipeline writes a slate, the reasoning
    pass writes its forecasts with the prompts it sent (its savepoint, its
    record first), the final pass writes its second opinion beside each, the
    resolver settles them once, and a void lands -- every rule in place."""
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    asks_only(monkeypatch, "nfl", "spread")
    answer = '{"probability": 0.66, "reasoning": "The home rating is better."}'
    run.run_week(league, 2025, 7, include_props=False, use_llm=True,
                 llm_client=StubClient([answer] * 40))
    early = league.execute("SELECT predictor, COUNT(*) FROM predictions"
                           " GROUP BY predictor").fetchall()
    assert dict((r[0], r[1]) for r in early) == {"statistical": 4, "llm": 4}
    run.run_slate(league, "nfl", 2025, 7, include_props=False, use_llm=True,
                  llm_client=StubClient([answer] * 40), final=True)
    passes = dict(league.execute("SELECT pass_kind, COUNT(*) FROM predictions"
                                 " GROUP BY pass_kind").fetchall())
    assert passes == {"early": 8, "final": 8}
    assert league.execute("SELECT COUNT(*) FROM reasoning_prompts").fetchone()[0] == 8
    got = resolve.resolve_all(league)
    assert got["settled"] > 0
    open_one = league.execute("SELECT id FROM predictions WHERE resolved_utc IS NULL"
                              " ORDER BY id LIMIT 1").fetchone()
    target = open_one[0] if open_one else league.execute(
        "SELECT MAX(id) FROM predictions").fetchone()[0]
    assert resolve.void_prediction(league, target, "voided in this test world")
    ids = [r[0] for r in league.execute("SELECT id FROM predictions ORDER BY id")]
    assert ids == list(range(1, len(ids) + 1))


def test_a_forecast_written_by_another_writer_first_still_raises(league):
    """NO WRITER COUNTS THE REFUSAL, AND NONE NEEDS TO. `write_prediction`
    asks `already_written` first; if another writer answers the question
    between that ask and the insert, the insert is refused -- on the key
    before 2026-09-27, by the insert rule now, in its words -- and raises
    the same `IntegrityError`, the savepoint taking the row back."""
    from gridiron.factors.compute import FeatureVector
    from gridiron.model.question import Question

    game_id = league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1").fetchone()["id"]
    q = Question(sport="nfl", game_id=game_id, market_type="spread",
                 market="spread", subject="KC", line_asked=-3.5,
                 claim="KC cover -3.5", yes_label="cover", no_label="not cover")
    fv = FeatureVector(sport="nfl", market_type="spread")
    fv.values["home_field"] = 1.0
    fv.raw["home_field"] = 1.0
    assert predict.write_prediction(league, q, predictor="statistical",
                                    prob_yes=0.58, fv=fv, reasoning="first")
    before = _stored(league)
    real = predict.already_written
    try:
        predict.already_written = lambda *a, **k: False     # the race
        with pytest.raises(sqlite3.IntegrityError, match=predict.NEVER_REPLACED):
            predict.write_prediction(league, q, predictor="statistical",
                                     prob_yes=0.71, fv=fv, reasoning="second")
    finally:
        predict.already_written = real
    assert not league.in_transaction
    assert _stored(league) == before


def test_the_replace_rules_carry_the_words_and_run_first(tmp_path):
    """ONE SET OF WORDS: every rule says `predict.NEVER_REPLACED` under LAW 3,
    never "UNIQUE". DECLARED AFTER `reasoning_row_carries_its_prompt`, the
    table's newest rule on the record, so a fresh build runs them in the
    order the record will (SQLite runs a table's rules newest first)."""
    conn = db.open_db(tmp_path / "fresh.db")
    rules = dict(conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'trigger'"
        " AND tbl_name = 'predictions'").fetchall())
    for name in RULES:
        assert predict.NEVER_REPLACED in rules[name]
        assert "LAW 3" in rules[name]
        assert "UNIQUE" not in rules[name]
    order = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        " AND tbl_name = 'predictions' ORDER BY rowid")]
    assert order[-len(RULES):] == list(RULES)
    assert order[-len(RULES) - 1] == "reasoning_row_carries_its_prompt"
    assert set(RULES) <= set(db.PREDICTION_TRIGGERS)
    conn.close()


def test_an_older_record_gains_the_rules_through_init_and_no_row_moves(tmp_path):
    """THE RELEASE REACHES THE RECORD THROUGH `db.init` ALONE: a record
    without the rules -- every release until this one -- gains exactly them,
    with a fresh build's text, after `reasoning_row_carries_its_prompt`;
    every forecast and void stays as it was; a second open adds nothing; and
    a replacement is refused from the first open."""
    conn, ids = _world(tmp_path)
    for name in RULES:
        conn.execute(f"DROP TRIGGER {name}")
    conn.commit()

    def objects(c):
        return {(r[0], r[1]): r[2] for r in c.execute(
            "SELECT type, name, sql FROM sqlite_master")}

    before, rows = objects(conn), _stored(conn)
    db.init(conn)
    after = objects(conn)
    assert set(after) - set(before) == {("trigger", n) for n in RULES}
    assert all(after[k] == before[k] for k in before)
    fresh = db.open_db(tmp_path / "fresh.db")
    try:
        for name in RULES:
            assert after[("trigger", name)] == objects(fresh)[("trigger", name)]
    finally:
        fresh.close()
    assert _stored(conn) == rows
    order = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        " AND tbl_name = 'predictions' ORDER BY rowid")]
    assert order[-len(RULES):] == list(RULES)
    db.init(conn)
    assert objects(conn) == after and _stored(conn) == rows
    with pytest.raises(sqlite3.IntegrityError, match=predict.NEVER_REPLACED):
        conn.execute(FORMS["insert or replace naming a stored number"][0]
                     .format(**ids))
    conn.rollback()
    assert _stored(conn) == rows


def test_a_widened_table_keeps_the_rules(tmp_path):
    """THE WIDENING CARRIES THEM (`db.PREDICTION_TRIGGERS`). A record whose
    stored table is narrower than the schema's -- here, one whose sport
    CHECK lacks a declared sport -- is rebuilt by `db.init`, row for row;
    the rules end on the widened table, the rows and the sequence as they
    were, and a replacement is refused. Measured 2026-09-27: without their
    names in that list the rename carried them away and none came back."""
    conn, ids = _world(tmp_path)
    rows = _stored(conn)
    sequence = conn.execute("SELECT seq FROM sqlite_sequence"
                            " WHERE name = 'predictions'").fetchone()[0]
    conn.execute("PRAGMA writable_schema = ON")
    conn.execute("UPDATE sqlite_master SET sql = replace(sql, ',''ufc''', '')"
                 " WHERE type = 'table' AND name = 'predictions'")
    conn.execute("PRAGMA writable_schema = OFF")
    conn.commit()
    conn.close()
    conn = db.connect(tmp_path / "world.db")
    assert db._needs_market_type_widening(conn)
    db.init(conn)
    assert not db._needs_market_type_widening(conn)
    on = {r[0]: r[1] for r in conn.execute(
        "SELECT name, tbl_name FROM sqlite_master WHERE type = 'trigger'")}
    assert all(on.get(name) == "predictions" for name in RULES)
    assert _stored(conn) == rows
    assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'predictions'"
                        ).fetchone()[0] == sequence
    with pytest.raises(sqlite3.IntegrityError, match=predict.NEVER_REPLACED):
        conn.execute(FORMS["insert or replace naming a stored number"][0]
                     .format(**ids))
    conn.rollback()
    conn.close()


# --- the number the rule is shown is not the number written (question 13's
# prover, applied here) ----------------------------------------------------


class _Handed:
    """An application function answering the first reading with `first` and
    every later one with `then`: the rules read first, the key after."""

    def __init__(self, first, then):
        self.first, self.then, self.calls = first, then, 0

    def __call__(self):
        self.calls += 1
        return self.first if self.calls == 1 else self.then


#: (the number the rules are shown, the stored forecast the key gets)
HANDED = {
    "nothing to the rules, the first to the key": (None, "p1"),
    "a free number to the rules, the second to the key": (99, "p2"),
    "a free number to the rules, the voided newest to the key": (99, "void"),
}


@pytest.mark.parametrize("form", sorted(HANDED))
@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_a_number_read_one_way_by_the_rules_and_another_by_the_key_is_refused(
        tmp_path, form, verb):
    """REFUSED, in the rules' words, every forecast and void exactly as
    stored; and with ONLY the rule reading the written number dropped, the
    same statement writes over the stored forecast: that rule stops it."""
    conn, ids = _world(tmp_path)
    first, key = HANDED[form]
    before = _stored(conn)
    statement = _newcomer("handed()", verb=verb).format(**ids)
    handed = _Handed(first, ids[key])
    conn.create_function("handed", 0, handed)
    with pytest.raises(sqlite3.IntegrityError) as refused:
        conn.execute(statement)
    conn.rollback()
    assert handed.calls == 2                # read twice, as measured
    assert "LAW 3" in str(refused.value)
    assert predict.NEVER_REPLACED in str(refused.value)
    assert _stored(conn) == before
    conn.execute(f"DROP TRIGGER {RULES[-1]}")
    conn.create_function("handed", 0, _Handed(first, ids[key]))
    conn.execute(statement)
    after = {r[0]: r for r in _stored(conn)[0]}
    assert after[ids[key]][3] == "g5"       # another game's, under its number
    conn.rollback()


def test_a_number_worked_out_at_random_never_writes_over_a_stored_one(tmp_path):
    """RANDOM(), THE PLAIN FORM: sixty-four tries each of a number drawn from
    one to six (five stored) and of one that is NULL or the first's by a
    coin. Each is refused or writes a new forecast under a new number; no
    stored forecast or void ever changes."""
    conn, ids = _world(tmp_path)
    before = _stored(conn)
    stored = {r[0]: r for r in before[0]}
    for number in ("abs(random()) % 6 + 1",
                   "CASE WHEN random() % 2 = 0 THEN NULL ELSE {p1} END"):
        for _ in range(64):
            try:
                conn.execute(_newcomer(number).format(**ids))
            except sqlite3.IntegrityError as exc:
                assert predict.NEVER_REPLACED in str(exc)
            rows, voids = _stored(conn)
            assert {r[0]: r for r in rows if r[0] in stored} == stored
            assert voids == before[1]
            conn.rollback()


def test_a_number_below_one_already_given_out_is_refused_and_one_above_lands(
        tmp_path):
    """THE CONSERVATIVE DEFAULT, recorded: after the insert a rule cannot
    tell a number that was stored from one that is free, so a free number
    at or below one already given out -- here 2, vacated by an update, and 0
    and -1, never used -- is refused too (no writer names a number); a
    number above every one lands.

    The update vacating 2 moves the forecast DOWN, to -5 (2026-09-27, the
    prover): a move above every number given out is refused from that date
    (`test_a_forecast_is_never_moved_out_of_reach_of_the_number_written`),
    and this world moved it to 10. The numbers asked about are the same."""
    conn, ids = _world(tmp_path)
    conn.execute("UPDATE predictions SET id = -5 WHERE id = ?", (ids["p2"],))
    conn.commit()
    before = _stored(conn)
    for unused in (ids["p2"], 0, -1):
        with pytest.raises(sqlite3.IntegrityError, match=predict.NEVER_REPLACED):
            conn.execute(_newcomer(str(unused), "g6", verb="INSERT").format(**ids))
        conn.rollback()
    assert _stored(conn) == before
    conn.execute(_newcomer("11", "g6", verb="INSERT").format(**ids))
    assert conn.execute("SELECT game_id FROM predictions WHERE id = 11"
                        ).fetchone()[0] == "g6"
    conn.rollback()


def test_a_prediction_given_a_number_below_one_does_not_stop_the_next(tmp_path):
    """THE -1 THE INSERT RULE IS SHOWN. An insert leaving the number to
    SQLite shows the rule -1, and an update may give a forecast nothing
    points at -1 (it replaces nothing). Were the rule to look -1 up, every
    later forecast would be refused. It does not, so the next is written;
    and an insert naming -1 is still refused once it lands."""
    conn, ids = _world(tmp_path)
    conn.execute("UPDATE predictions SET id = -1 WHERE id = ?", (ids["p2"],))
    conn.commit()
    conn.execute(_newcomer(None, "g6", verb="INSERT").format(**ids))
    assert conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 6
    conn.commit()
    before = _stored(conn)
    # on a question of its own, so only the number can refuse it: the rule
    # before the row lets -1 pass, and the rule after it lands refuses it
    with pytest.raises(sqlite3.IntegrityError, match=predict.NEVER_REPLACED):
        conn.execute(_newcomer("-1", "g5").format(**ids))
    conn.rollback()
    assert _stored(conn) == before


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_with_the_sequence_set_back_every_forecast_but_the_newest_is_held(
        tmp_path, verb):
    """SQLite's own sequence is NOT SEEN by any rule (FOLLOWUPS), and set
    back below every forecast it leaves the newest where nothing stored tells
    it from a newcomer. Every forecast below the newest is still held: the
    number-written rule refuses a number below any stored one (the prover,
    2026-09-27, found no other form that needs that clause). With the clause
    taken out, the same insert writes over the first forecast."""
    conn, ids = _world(tmp_path)
    before = _stored(conn)
    for key in ("p1", "p2", "llm", "final"):
        conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'predictions'")
        conn.create_function("handed", 0, _Handed(99, ids[key]))
        with pytest.raises(sqlite3.IntegrityError, match=predict.NEVER_REPLACED):
            conn.execute(_newcomer("handed()", verb=verb).format(**ids))
        conn.rollback()
        assert _stored(conn) == before, key
    name = RULES[-1]
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?",
                       (name,)).fetchone()[0]
    weakened, found = BELOW_ANY_STORED.subn("", sql)
    assert found == 1, "the number-written rule no longer carries the clause"
    conn.execute(f"DROP TRIGGER {name}")
    conn.execute(weakened)
    conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'predictions'")
    conn.create_function("handed", 0, _Handed(99, ids["p1"]))
    conn.execute(_newcomer("handed()", verb=verb).format(**ids))
    assert conn.execute("SELECT game_id FROM predictions WHERE id = ?",
                        (ids["p1"],)).fetchone()[0] == "g5"
    conn.rollback()


#: The number-written rule's clause refusing a number below any stored one.
BELOW_ANY_STORED = re.compile(
    r"\s+OR EXISTS \(SELECT 1 FROM predictions p WHERE p\.id > NEW\.id\)")

#: The update rule's clause refusing a move above every number given out
#: (the prover, 2026-09-27), as the schema writes it, whitespace aside.
ABOVE_THE_MARK = re.compile(
    r"\s+OR \(NEW\.id IS NOT OLD\.id\s+AND NEW\.id > \(SELECT seq FROM"
    r" sqlite_sequence WHERE name = 'predictions'\)\)")


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_a_forecast_is_never_moved_out_of_reach_of_the_number_written(
        tmp_path, verb):
    """FOUND BY THE PROVER (2026-09-27). The rule after the insert holds a
    forecast at or below `sqlite_sequence`'s mark, and an UPDATE of a number
    does not move the mark (measured). So a plain update moving a forecast
    above every number given out -- which replaces nothing, and which the
    three rules as first built let through -- left it where a one-row insert
    whose number reads free to the rules and as the moved forecast's to the
    row wrote another game's forecast over it (measured on 98091d2 and on the
    first build, by both verbs). The update rule now refuses the move, by
    every spelling of the number, in the rules' words; a move to a free
    number at or below the mark still lands (not a freeze of the number,
    which stays the operator's) and nothing can be written over it there;
    and with the clause taken out, the two statements write over the moved
    forecast -- it is what stops them."""
    conn, ids = _world(tmp_path)
    mark = conn.execute("SELECT seq FROM sqlite_sequence"
                        " WHERE name = 'predictions'").fetchone()[0]
    above = mark + 5
    before = _stored(conn)
    for update in ("UPDATE", "UPDATE OR REPLACE"):
        for column in ("id", "rowid", "oid", "_rowid_"):
            with pytest.raises(sqlite3.IntegrityError) as refused:
                conn.execute(f"{update} predictions SET {column} = ?"
                             " WHERE id = ?", (above, ids["p2"]))
            conn.rollback()
            assert "LAW 3" in str(refused.value)
            assert predict.NEVER_REPLACED in str(refused.value)
            assert _stored(conn) == before
    # within the mark: lands, and stays in reach of the rule after the insert
    conn.execute("UPDATE predictions SET id = 0 WHERE id = ?", (ids["p2"],))
    conn.create_function("handed", 0, _Handed(99, 0))
    with pytest.raises(sqlite3.IntegrityError, match=predict.NEVER_REPLACED):
        conn.execute(_newcomer("handed()", verb=verb).format(**ids))
    assert conn.execute("SELECT game_id FROM predictions WHERE id = 0"
                        ).fetchone()[0] == "g2"
    conn.rollback()
    assert _stored(conn) == before
    # the clause taken out: the move lands and the forecast is written over
    name = RULES[1]
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?",
                       (name,)).fetchone()[0]
    weakened, found = ABOVE_THE_MARK.subn("", sql)
    assert found == 1, "the update rule no longer carries the clause"
    conn.execute(f"DROP TRIGGER {name}")
    conn.execute(weakened)
    conn.execute("UPDATE predictions SET id = ? WHERE id = ?", (above, ids["p2"]))
    conn.create_function("handed", 0, _Handed(99, above))
    conn.execute(_newcomer("handed()", verb=verb).format(**ids))
    moved = conn.execute("SELECT game_id, reasoning FROM predictions WHERE id = ?",
                         (above,)).fetchone()
    assert tuple(moved) == ("g5", "newcomer")      # the stored g2 forecast is gone
    conn.rollback()
