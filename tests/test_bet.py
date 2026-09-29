"""One function defines a distinct bet (operator question 17, ruled
2026-09-27; question 21, ruled 2026-09-28; built 2026-09-28).

"One function defines a distinct bet: forecaster + the venue's question
(game, market, line). Morning and final pass of one question count once;
which pass counts stays each record's standing rule; alt lines are separate
questions." And: "the line the forecaster was asked (the rung). Two rungs on
one game are two questions."

`gridiron.bet` is the function, in Python and in SQL from one tuple;
`gridiron.recount` counts each record again without its door, by it; each
record's guard refuses a count the two disagree on; and the source scan
refuses a key spelled anywhere else.
"""
from __future__ import annotations

import pytest

from gridiron import audit, bet, calibration, db, recount


def _forecast(conn, *, game="g1", market="spread", prop=None, subject="SEA",
              rung=-3.5, who="statistical", pass_kind="final",
              written="2026-09-07T21:00:00Z", fsv="fs2") -> int:
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " pass_kind, factor_set_version, factors_json, reasoning)"
        " VALUES (?, 'nfl', ?, ?, ?, ?, ?, 0.6, 'cover', ?, ?, ?, '{}', 'test')",
        (written, game, market, prop, subject, rung, who, pass_kind, fsv))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]


def _world(tmp_path):
    conn = db.open_db(tmp_path / "bet.db")
    for game in ("g1", "g2"):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'nfl', 2026, 1,"
            " 'REG', 'SEA', 'NE', '2026-09-08T00:20:00Z', 'scheduled',"
            " '2026-09-07')", (game,))
    conn.commit()
    return conn


def test_the_key_is_the_forecaster_and_the_question_with_its_rung():
    """The ruling's key, in the order the tuple holds it: no prop type from
    2026-09-29 -- a prop's question is named by its subject."""
    assert bet.KEY == ("predictor", "game_id", "market_type", "subject",
                       "line_asked")
    row = {"predictor": "statistical", "game_id": "g1", "market_type": "spread",
           "prop_type": None, "subject": "SEA", "line_asked": -3.5,
           "model_prob": 0.6}
    assert bet.of(row) == ("statistical", "g1", "spread", "SEA", -3.5)
    # TWO RUNGS ON ONE GAME ARE TWO QUESTIONS (question 21)
    assert bet.count([row, dict(row, line_asked=-14.5)]) == 2
    # THE FORECASTER IS IN THE KEY: two forecasters, two bets
    assert bet.count([row, dict(row, predictor="llm")]) == 2
    # ONE QUESTION'S PASSES ARE ONE BET
    assert bet.count([row, dict(row, model_prob=0.7)]) == 1
    # A MONEYLINE'S ABSENT RUNG IS ONE RUNG
    ml = dict(row, market_type="moneyline", line_asked=None)
    assert bet.count([ml, dict(ml)]) == 1


def test_a_row_without_the_key_is_refused_by_name():
    """A door whose SELECT dropped a key column would count every rung, or
    every forecaster, as one -- so it is refused, not guessed."""
    with pytest.raises(bet.NotABet, match="line_asked"):
        bet.of({"predictor": "statistical", "game_id": "g1",
                "market_type": "spread", "prop_type": None, "subject": "SEA"})
    with pytest.raises(bet.NotABet, match="bet.columns"):
        bet.count([object()])


def test_the_sql_and_the_python_forms_are_one_key(tmp_path):
    """`columns` and `same` are made from the tuple `of` reads: a window
    partitioned by `columns`, a self-join on `same` and `of` in Python group
    the same rows the same way -- NULL one value in each, and a prop written
    with no prop type one question with the same subject and rung written
    with one (2026-09-29; until then the two were two)."""
    conn = _world(tmp_path)
    _forecast(conn, rung=-3.5, pass_kind="early", written="2026-09-06T00:00:00Z")
    _forecast(conn, rung=-3.5)                                  # a second pass
    _forecast(conn, rung=-14.5, pass_kind="early",
              written="2026-09-05T00:00:00Z", subject="SEA2")   # another subject
    _forecast(conn, who="llm", rung=-3.5)                       # the other forecaster
    _forecast(conn, market="moneyline", rung=None, subject="SEA")
    _forecast(conn, market="moneyline", rung=None, subject="SEA",
              pass_kind="early", written="2026-09-06T00:00:00Z")
    _forecast(conn, market="prop", prop=None, subject="A passing_yards",
              rung=240.5)
    _forecast(conn, market="prop", prop="passing_yards",
              subject="A passing_yards", rung=240.5, pass_kind="early",
              written="2026-09-06T00:00:00Z")
    rows = [dict(r) for r in conn.execute(
        f"SELECT p.id, {bet.columns('p')} FROM predictions p ORDER BY p.id")]
    by_python: dict = {}
    for r in rows:
        by_python.setdefault(bet.of(r), set()).add(r["id"])
    by_window: dict = {}
    for r in conn.execute(
            f"SELECT p.id, DENSE_RANK() OVER (ORDER BY {bet.columns('p')}) AS g"
            " FROM predictions p"):
        by_window.setdefault(r["g"], set()).add(r["id"])
    by_join = {frozenset(r[0] for r in conn.execute(
        f"SELECT p2.id FROM predictions p JOIN predictions p2 ON {bet.same('p2', 'p')}"
        " WHERE p.id = ?", (rid,))) for rid in (row["id"] for row in rows)}
    groups = {frozenset(ids) for ids in by_python.values()}
    assert groups == {frozenset(ids) for ids in by_window.values()} == by_join
    # the two passes of the -3.5 spread, of the moneyline and of the prop
    # (one written with no prop type) are one bet each
    assert sorted(len(g) for g in groups) == [1, 1, 2, 2, 2]
    assert "IS" in bet.same("a", "b") and " = " not in bet.same("a", "b")


def test_the_standing_clause_is_the_one_function(tmp_path):
    """`calibration.standing_row_clause` matches the question by `bet.same`,
    both times it asks, and keeps one row per distinct bet: the latest before
    the start, per forecaster and per rung."""
    conn = _world(tmp_path)
    for same_set in (False, True):
        clause = calibration.standing_row_clause(same_set)
        assert bet.same("p2", "p") in clause and bet.same("p3", "p2") in clause
    early = _forecast(conn, rung=-3.5, pass_kind="early",
                      written="2026-09-06T00:00:00Z")
    final = _forecast(conn, rung=-3.5)
    other_rung = _forecast(conn, rung=-14.5, pass_kind="early",
                           written="2026-09-05T00:00:00Z", fsv="fs3")
    llm = _forecast(conn, who="llm", rung=-3.5)
    standing = [r[0] for r in conn.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE 1 = 1" + calibration.standing_row_clause(False) + " ORDER BY p.id")]
    assert standing == [final, other_rung, llm]
    assert early not in standing


def test_a_prop_asked_without_its_type_and_again_with_it_is_one_question(
        tmp_path):
    """THE EIGHT PAIRS OF 29 AUGUST (2026-09-29). `predict:nfl` wrote week
    one's props at 05:55Z under fs1 with no prop type (the subject names it)
    and asked the same player, prop and rung again at 07:34Z under fs2 with
    the prop type set; three of the questions were asked a third time by the
    final pass. From 2026-09-28 the key named the prop type as well, `IS`
    telling NULL from 'receiving_yards', so each such question stood twice
    and "morning and final pass of one question count once" broke: 14 NFL
    figures moved (the factor table's N, "scored over 154" read 162). A
    prop's question is named by its subject: one distinct bet, one standing
    row -- the latest before the start -- for the clause, the recount and a
    reader of every market together; a count of one prop type, which
    filters by it, is as it was; and another stat of the same player is
    another question."""
    conn = _world(tmp_path)
    london = "Drake London receiving_yards"
    untyped = _forecast(conn, market="prop", prop=None, subject=london,
                        rung=100.5, pass_kind="early",
                        written="2026-08-29T05:55:46Z", fsv="fs1")
    typed = _forecast(conn, market="prop", prop="receiving_yards",
                      subject=london, rung=100.5, pass_kind="early",
                      written="2026-08-29T07:34:56Z", fsv="fs2")
    other_stat = _forecast(conn, market="prop", prop="receptions",
                           subject="Drake London receptions", rung=5.5,
                           pass_kind="early", written="2026-08-29T07:34:56Z",
                           fsv="fs2")
    irving = "Bucky Irving rushing_yards"
    untyped_2 = _forecast(conn, market="prop", prop=None, subject=irving,
                          rung=60.5, pass_kind="early",
                          written="2026-08-29T05:55:46Z", fsv="fs1")
    typed_2 = _forecast(conn, market="prop", prop="rushing_yards",
                        subject=irving, rung=60.5, pass_kind="early",
                        written="2026-08-29T07:34:56Z", fsv="fs2")
    final_2 = _forecast(conn, market="prop", prop="rushing_yards",
                        subject=irving, rung=60.5, pass_kind="final",
                        written="2026-09-04T18:40:24Z", fsv="fs2")
    rows = {r["id"]: dict(r) for r in conn.execute(
        f"SELECT p.id, {bet.columns('p')} FROM predictions p")}
    # ONE DISTINCT BET: the pass without the prop type and the passes with it
    assert bet.of(rows[untyped]) == bet.of(rows[typed])
    assert bet.of(rows[untyped_2]) == bet.of(rows[typed_2]) == bet.of(rows[final_2])
    assert bet.count(rows.values()) == 3
    # ONE STANDING ROW, the latest before the start, by the clause and the
    # recount alike
    standing = [r[0] for r in conn.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE 1 = 1" + calibration.standing_row_clause(False) + " ORDER BY p.id")]
    assert standing == [typed, other_stat, final_2]
    again = recount.standing_of(recount.forecasts(
        conn, sport="nfl", predictor="statistical", market_type=None,
        prop_type=None, event_tier=None))
    assert sorted(r["id"] for r in again.values()) == standing
    # A READER OF EVERY MARKET TOGETHER counts each question once
    conn.execute("UPDATE predictions SET resolved_utc = '2026-09-08T03:00:00Z',"
                 " outcome = 1 WHERE resolved_utc IS NULL")
    conn.commit()
    assert [r.id for r in calibration.resolved(
        conn, sport="nfl", predictor="statistical")] == standing
    # A COUNT OF ONE PROP TYPE filters by it, as it always did: the row
    # without a type was never in it
    assert [r.id for r in calibration.resolved(
        conn, sport="nfl", market_type="prop", prop_type="receiving_yards")] == [typed]
    assert [r.id for r in calibration.resolved(
        conn, sport="nfl", market_type="prop", prop_type="rushing_yards")] == [final_2]
    # AND THE SOURCE SCAN HOLDS THE KEY TO IT
    assert "prop_type" not in bet.KEY
    assert "prop_type" not in audit.RULED_DISTINCT_BET


def test_the_recount_is_each_standing_rule_again_by_the_key(tmp_path):
    """`recount.standing_of` is the blind record's rule in Python; on the
    same rows it keeps what the clause keeps -- withdrawn rows skipped, a
    question whose only pre-start row was withdrawn standing on nothing, a
    backtest's rows standing on the latest."""
    conn = _world(tmp_path)
    conn.execute("UPDATE games SET kickoff_utc = '2026-09-07T23:00:00Z'"
                 " WHERE id = 'g2'")
    ids = [
        _forecast(conn, rung=-3.5, pass_kind="early", written="2026-09-06T00:00:00Z"),
        _forecast(conn, rung=-3.5),
        # another rung (written under another factor set: the schema keys a
        # pass by game, market, subject, forecaster, set and pass, no rung)
        _forecast(conn, rung=-14.5, pass_kind="early",
                  written="2026-09-05T00:00:00Z", fsv="fs3"),
        _forecast(conn, who="llm", rung=-3.5),
        # a question on g2 whose pre-start row is withdrawn and whose other
        # row came after the start: it stands on nothing
        _forecast(conn, game="g2", rung=-1.5, pass_kind="early",
                  written="2026-09-07T20:00:00Z"),
        _forecast(conn, game="g2", rung=-1.5, written="2026-09-08T01:00:00Z"),
        # a backtest's question: every row after the start, the latest stands
        _forecast(conn, game="g2", rung=-7.5, pass_kind="early",
                  written="2026-09-08T02:00:00Z", fsv="fs3"),
        _forecast(conn, game="g2", rung=-7.5, written="2026-09-08T03:00:00Z",
                  fsv="fs3"),
    ]
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, '2026-09-08T04:00:00Z', 'withdrawn in this test')",
                 (ids[4],))
    conn.commit()
    clause = {r[0] for r in conn.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = 'nfl'" + calibration.standing_row_clause(False))}
    again = set()
    for who in ("statistical", "llm"):
        again |= {r["id"] for r in recount.standing_of(recount.forecasts(
            conn, sport="nfl", predictor=who, market_type=None, prop_type=None,
            event_tier=None)).values()}
    assert again == clause == {ids[1], ids[2], ids[3], ids[7]}


def test_one_instant_holds_one_read(tmp_path):
    """A count and its recount are read inside one transaction, so a write
    landing between them cannot make an honest count look pooled."""
    path = tmp_path / "instant.db"
    writer = db.open_db(path)
    reader = db.connect(path)
    with db.one_instant(reader):
        before = reader.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        writer.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES ('g9', 'nfl', 2026, 1,"
            " 'REG', 'A', 'B', '2026-09-08T00:20:00Z', 'scheduled', '2026-09-07')")
        writer.commit()
        assert reader.execute("SELECT COUNT(*) FROM games").fetchone()[0] == before
    assert not reader.in_transaction
    assert reader.execute("SELECT COUNT(*) FROM games").fetchone()[0] == before + 1
    # a connection already inside a transaction is left as it is
    writer.execute("UPDATE games SET status = 'scheduled' WHERE id = 'g9'")
    assert writer.in_transaction
    with db.one_instant(writer):
        pass
    assert writer.in_transaction
    writer.rollback()


def test_a_write_between_the_door_and_the_recount_is_no_pooled_count(
        tmp_path, monkeypatch):
    """THE PROVER OF 2026-09-28: on the live record a scheduled task writes
    while the page is read. A question and its claim written between the
    door's read and the recount's made an honest curve read "counts 2 where
    the recount ... finds 3" -- a 500 for nothing -- until both were read in
    one instant (`db.one_instant`). The curve counts the instant it read."""
    from gridiron.market import at_the_line

    path = tmp_path / "race.db"
    conn = db.open_db(path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('g1', 'nfl', 2026, 1, 'REG', 'SEA', 'NE',"
        " '2026-09-07T23:05:00Z', 'final', '2026-09-07', 30, 3)")
    at_the_line.ensure_read_kind(conn)
    # THREE QUESTIONS, three rungs of one game (a pass each keyed apart by
    # its factor set, as the schema keys a pass without the rung)
    for rung, fsv in ((-14.5, "fs2"), (-24.5, "fs3"), (-30.5, "fs4")):
        _forecast(conn, rung=rung, fsv=fsv, written="2026-09-07T21:00:00Z")
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, last_price,"
        " fetched_utc, read_kind) VALUES (?, 'T', 'E', 'nfl', 'g1', 'spread',"
        " 'home_margin', -20.5, 'home', 0.44, 0.46, 0.45,"
        " '2026-09-07T21:35:00Z', 'near_start')", (at_the_line.VENUE,))

    def claim(on, pid, second):
        on.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
            " sport, game_id, market, quantity, line, side, shape, model_prob,"
            " venue_price, venue_implied, price_basis, created_utc,"
            " resolved_utc, outcome) VALUES (?, 1, ?, 'nfl', 'g1', 'spread',"
            " 'home_margin', -20.5, 'home', 'rung_matched', 0.7, 0.45, 0.45,"
            " 'mid', ?, '2026-09-08T03:00:00Z', 1)",
            (pid, at_the_line.VENUE, f"2026-09-07T21:45:0{second}Z"))

    claim(conn, 1, 0)
    claim(conn, 2, 1)
    conn.commit()
    shipped = at_the_line.standing_claims

    def door_then_a_write(conn, **kw):
        rows = shipped(conn, **kw)
        other = db.connect(path)
        claim(other, 3, 2)
        other.commit()
        other.close()
        return rows

    monkeypatch.setattr(at_the_line, "standing_claims", door_then_a_write)
    curve = calibration.at_the_line_curve(conn, sport="nfl", market="spread",
                                          predictor="statistical")
    calibration.assert_no_pooled_claims(
        {"sport": "nfl", "record": "at_the_line", "categories": [curve]})
    assert curve["n"] == curve["recounted"] == 2
    # and the next read sees the third, door and recount alike
    monkeypatch.setattr(at_the_line, "standing_claims", shipped)
    again = calibration.at_the_line_curve(conn, sport="nfl", market="spread",
                                          predictor="statistical")
    assert again["n"] == again["recounted"] == 3


def test_the_shipped_package_keys_every_bet_by_the_one_function():
    """The source scan passes the package: no key function of its own, no
    `distinct_bets` counted another way, no window keyed by hand, and the
    standing clause is `bet.same`."""
    assert audit.distinct_bet_key_faults() == []
    audit.check_every_count_keys_one_bet()


def test_a_key_spelled_by_hand_is_named(tmp_path, monkeypatch):
    import shutil

    from gridiron import config

    root = tmp_path / "gridiron"
    shutil.copytree(config.PACKAGE_ROOT, root,
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / "planted.py").write_text(
        "def count_of_bets(rows):\n"
        "    return len({r['game_id'] for r in rows})\n"
        "\n"
        "PAYLOAD = {'distinct_bets': len([])}\n"
        "SQL = 'ROW_NUMBER() OVER (PARTITION BY game_id ORDER BY id)'\n",
        encoding="utf-8")
    faults = audit.distinct_bet_key_faults(root)
    assert any("`count_of_bets` keys a distinct bet" in f for f in faults)
    assert any("`distinct_bets` is counted by something other" in f for f in faults)
    assert any("written out in a plain string" in f for f in faults)
    with pytest.raises(audit.LawViolation, match="A COUNT KEYS A DISTINCT BET"):
        audit.check_every_count_keys_one_bet(root)
    # AND A STANDING CLAUSE MATCHING THE QUESTION BY HAND, in the running code
    monkeypatch.setattr(calibration, "standing_row_clause",
                        lambda same_set: " AND p.id = p.id")
    assert any("standing_row_clause" in f for f in audit.distinct_bet_key_faults())
