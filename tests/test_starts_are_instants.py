"""Operator question 35, ruled 2026-09-30 (docs/briefs/2026-09-30-rulings.md):
"Q35: a pass written at or after the start is not blind. Store and compare
starts as instants, never as text. The 18 are voided by append-only rows
under the existing void rule, and Q27's standing rule then falls back to their
early passes. Report why a final pass ran at the start time and move that
schedule so every final pass lands before its start." Built 2026-10-01.

THE SHAPE: UFC starts were stored to the minute ("2026-09-05T19:00Z") and every
pass to the second; compared as text a colon sorts below a Z, so eighteen
final passes written at 19:00:02-03Z stood as written before a 19:00Z start.

STORED: every loader writes a start through `db.stored_start` (to the second).
COMPARED: `db.instant` in Python, `julianday()` on both sides in SQL, and
`audit.check_every_start_is_compared_as_an_instant` (gate step 2) names any
other comparison. NEVER WRITTEN AT OR AFTER: `predict.write_prediction`
refuses the row at its own stamp. THE SCHEDULE: `final:ufc` fires by its lead
(`tasks.final_pass_window`). THE 18: `tools/void_passes_written_at_the_start.py`.

No test reads the clock: every instant here is a fixed stamp, and the code's
own clock is held by hand where it is asked.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sqlite3

import pytest

from gridiron import audit, calibration, config, db, recount, run, tasks
from gridiron.factors import store
from gridiron.market import at_the_line, recommend
from gridiron.model import activation, baseline, predict
from gridiron.sports import ufc
from tests.conftest import asks_only

REPO = config.PACKAGE_ROOT.parent
FACTORS = '{"values": {}, "present": [], "absent": []}'


def _hold(monkeypatch, stamp: str) -> None:
    """THE CODE'S CLOCK, HELD AT `stamp`, in every module that reads it by
    its own name. Nothing here reads the real clock."""
    for module in (db, predict, recommend, ufc):
        monkeypatch.setattr(module, "utcnow", lambda stamp=stamp: stamp)


# ---------------------------------------------------------------------------
# STORED AS INSTANTS
# ---------------------------------------------------------------------------

def test_a_start_is_stored_to_the_second_whatever_its_feed_sent():
    assert db.stored_instant("2026-09-05T19:00Z") == "2026-09-05T19:00:00Z"
    assert db.stored_instant("2026-09-05T19:00:00Z") == "2026-09-05T19:00:00Z"
    assert db.stored_instant("2026-09-05T21:00:00+02:00") == "2026-09-05T19:00:00Z"
    assert db.stored_instant(None) is None and db.stored_instant("") is None
    with pytest.raises(ValueError, match="names no zone"):
        db.stored_instant("2026-09-05T19:00:00")
    with pytest.raises(ValueError, match="cannot be read"):
        db.stored_instant("TBD")
    # A LOADER KEEPS WHAT IT CANNOT READ AS SENT, never a guess and never NULL
    assert db.stored_start("2026-09-05T19:00Z") == "2026-09-05T19:00:00Z"
    assert db.stored_start("TBD") == "TBD"
    assert db.stored_start(None) is None


def _ufc_world(conn, *, start="2026-09-05T19:00Z", prelims=None, status="scheduled"):
    """One card: `start` for its main card's two bouts, `prelims` (if given)
    for a third, each mirrored into `games` as the refresh mirrors them."""
    conn.execute(
        "INSERT INTO ufc_events (id, name, event_utc, season, event_tier,"
        " is_card, fetched_utc) VALUES ('e1', 'UFC Fight Night: A vs. B', ?,"
        " 2026, 'fight_night', 1, '2026-09-01T00:00:00Z')", (prelims or start,))
    for n, fighters in enumerate((("f1", "f2"), ("f3", "f4"))):
        conn.execute(
            "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
            " match_number, fighter_a, fighter_b, status, fetched_utc)"
            " VALUES (?, 'e1', ?, 3, ?, ?, ?, ?, '2026-09-01T00:00:00Z')",
            (f"b{n}", start, 10 + n, *fighters, status))
    if prelims:
        conn.execute(
            "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
            " match_number, fighter_a, fighter_b, status, fetched_utc)"
            " VALUES ('bp', 'e1', ?, 3, 1, 'f5', 'f6', ?, '2026-09-01T00:00:00Z')",
            (prelims, status))
    conn.commit()
    ufc.mirror_bouts(conn)


def test_the_ufc_mirror_rewrites_every_start_to_the_second(conn):
    """THE LOADER'S OWN DOOR BRINGS THE RECORD'S STARTS TO THE FORM: the
    mirror rewrites every bout's start on every refresh, so a start stored to
    the minute before 2026-10-01 is written to the second, the same instant,
    and no other column moves."""
    _ufc_world(conn)
    conn.execute("UPDATE games SET kickoff_utc = '2026-09-05T19:00Z' WHERE id = 'b0'")
    conn.commit()
    before = dict(conn.execute("SELECT * FROM games WHERE id = 'b0'").fetchone())
    ufc.mirror_bouts(conn)
    after = dict(conn.execute("SELECT * FROM games WHERE id = 'b0'").fetchone())
    assert after["kickoff_utc"] == "2026-09-05T19:00:00Z"
    assert db.instant(after["kickoff_utc"]) == db.instant(before["kickoff_utc"])
    assert {k: v for k, v in after.items() if k != "kickoff_utc"} == {
        k: v for k, v in before.items() if k != "kickoff_utc"}


def test_every_loader_writes_its_start_through_the_one_door():
    """Each writer of a stored start -- the four sports' loaders, the UFC
    loader's card and bout, and the UFC mirror -- hands it to
    `db.stored_start` in the call that writes it."""
    writers = {
        "gridiron/data/loader.py": "load_games",
        "gridiron/data/mlb_loader.py": "_write_game",
        "gridiron/data/nba_loader.py": "load_schedule",
        "gridiron/data/cfb_loader.py": "load_season",
        "gridiron/data/ufc_loader.py": "load_season",
        "gridiron/sports/ufc.py": "mirror_bouts",
    }
    missing = []
    for path, function in writers.items():
        tree = ast.parse((REPO / path).read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == function)
        if not any(isinstance(n, ast.Call)
                   and getattr(n.func, "id", getattr(n.func, "attr", None)) == "stored_start"
                   for n in ast.walk(fn)):
            missing.append(f"{path}:{function}")
    tree = ast.parse((REPO / "gridiron/data/ufc_loader.py").read_text(encoding="utf-8"))
    bout = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_load_bout")
    if "stored_start(bout.get(\"date\"))" not in ast.unparse(bout).replace("'", '"'):
        missing.append("gridiron/data/ufc_loader.py:_load_bout")
    assert missing == []


# ---------------------------------------------------------------------------
# COMPARED AS INSTANTS: THE STANDING RULE
# ---------------------------------------------------------------------------

def _settled_bout(conn, *, start: str, gid: str = "q35"):
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, home_score, away_score, league_date)"
        " VALUES (?, 'ufc', 2026, 20260905, 'REG', 'A', 'B', ?, 'final', 1, 0,"
        " '2026-09-05')", (gid, start))
    conn.commit()


def _pass(conn, *, gid="q35", kind: str, written: str, prob=0.6):
    cur = conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
        " VALUES (?, 'ufc', ?, 'moneyline', 'A', ?, 'win', 'statistical', ?,"
        " 'fs2', ?, 'planted by question 35', '2026-09-06T01:20:02Z', 1)",
        (written, gid, prob, kind, FACTORS))
    conn.commit()
    return cur.lastrowid


def _standing(conn) -> set[int]:
    return {r.id for r in calibration.resolved(conn, sport="ufc",
                                               market_type="moneyline",
                                               predictor="statistical")}


def _recounted(conn) -> set[int]:
    rows = recount.forecasts(conn, sport="ufc", predictor="statistical",
                             market_type="moneyline", prop_type=None,
                             event_tier=None)
    return {r["id"] for r in recount.standing_of(rows).values()}


def test_a_final_pass_seconds_after_a_start_to_the_minute_never_stands(conn):
    """THE EIGHTEEN'S SHAPE: the early pass the day before, the final pass at
    19:00:02Z on a bout listed "2026-09-05T19:00Z". As text the final pass
    stood; read as instants the early pass does, in the clause and in the
    recount alike."""
    _settled_bout(conn, start="2026-09-05T19:00Z")
    early = _pass(conn, kind="early", written="2026-09-04T02:05:10Z")
    final = _pass(conn, kind="final", written="2026-09-05T19:00:02Z")
    assert _standing(conn) == {early} == _recounted(conn), final


def test_a_pass_written_at_the_starts_own_second_never_stands(conn):
    """"AT OR AFTER THE START IS NOT BLIND": a final pass stamped with the
    start's own second is not before it (the clause admitted it with `<=`
    until 2026-10-01); one a second before the start stands."""
    _settled_bout(conn, start="2026-09-05T19:00:00Z")
    early = _pass(conn, kind="early", written="2026-09-04T02:05:10Z")
    _pass(conn, kind="final", written="2026-09-05T19:00:00Z")
    assert _standing(conn) == {early} == _recounted(conn)
    _settled_bout(conn, start="2026-09-05T19:00Z", gid="q35b")
    _pass(conn, gid="q35b", kind="early", written="2026-09-04T02:05:10Z")
    before = _pass(conn, gid="q35b", kind="final", written="2026-09-05T18:59:59Z")
    assert before in _standing(conn) and before in _recounted(conn)


def test_a_start_nobody_can_read_stands_its_latest_row_in_the_clause_and_the_recount(conn):
    """A START NOBODY CAN READ IS BEFORE NOTHING (Q35's prover, 2026-10-01).
    `julianday()` of it is NULL, so as first built the clause's order put a
    final pass on such a game below an early one (NULL sorts last in DESC)
    and stood the early pass, where the recount -- and the rule's own
    fallback, nothing shown to come before the start -- keep the latest row.
    A feed's text kept as sent and an empty start, each with an early pass
    and a later final pass: the clause and the recount both keep the final,
    and agree on every question."""
    finals = set()
    for gid, start in (("q35t", "TBD"), ("q35e", "")):
        _settled_bout(conn, start=start, gid=gid)
        _pass(conn, gid=gid, kind="early", written="2026-09-04T02:05:10Z")
        finals.add(_pass(conn, gid=gid, kind="final", written="2026-09-05T12:00:00Z"))
    assert _standing(conn) == finals == _recounted(conn)


def test_a_claim_in_the_first_minute_of_a_game_to_the_minute_never_stands(conn):
    """THE AT-THE-LINE WINDOW: a claim written thirty seconds into a game
    whose start is stored to the minute is not a claim before it, in the
    door and in its recount. (A baseball game here: the door asks a UFC
    count for one card, and the window is the same SQL for every sport.)"""
    at_the_line.ensure_read_kind(conn)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, home_score, away_score, league_date)"
        " VALUES ('m35', 'mlb', 2026, 1, 'R', 'AAA', 'BBB', '2026-09-05T19:00Z',"
        " 'final', 3, 2, '2026-09-05')")
    cur = conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
        " VALUES ('2026-09-04T02:05:10Z', 'mlb', 'm35', 'moneyline', 'AAA', 0.6,"
        " 'win', 'statistical', 'early', 'fs2', ?, 'q35', '2026-09-06T01:20:02Z',"
        " 1)", (FACTORS,))
    pid = cur.lastrowid
    claims = {}
    for stamp in ("2026-09-05T18:30:00Z", "2026-09-05T19:00:30Z"):
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " fetched_utc, read_kind) VALUES ('kalshi', 'T', 'E', 'mlb', 'm35',"
            " 'moneyline', 'home_win', NULL, 'home', 0.5, 0.52, ?, 'near_start')",
            (stamp,))
        qid = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
            " sport, game_id, market, quantity, line, side, shape, model_prob,"
            " venue_price, venue_implied, price_basis, created_utc,"
            " resolved_utc, outcome) VALUES (?, ?, 'kalshi', 'mlb', 'm35',"
            " 'moneyline', 'home_win', NULL, 'home', 'line_less', 0.6, 0.51,"
            " 0.51, 'mid', ?, '2026-09-06T01:20:02Z', 1)", (pid, qid, stamp))
        claims[stamp] = cur.lastrowid
    conn.commit()
    before = {claims["2026-09-05T18:30:00Z"]}
    door = at_the_line.standing_claims(conn, sport="mlb", market="moneyline",
                                       predictor="statistical")
    assert {c["id"] for c in door} == before
    mine = recount.standing_claims_of(recount.claims(
        conn, sport="mlb", market="moneyline", predictor="statistical",
        event_tier=None))
    assert {c["id"] for c in mine.values()} == before


def test_the_recommendations_claim_window_reads_instants(tmp_path, monkeypatch):
    """THE RECOMMENDATION'S CLAIM WINDOW: the latest claim written before the
    start. On a game listed to the minute, a claim thirty seconds into it at
    another price was, as text, "before" it and priced the pick."""
    from gridiron.priced import coverage
    from gridiron import shortlist

    monkeypatch.setattr(coverage, "priceable",
                        lambda conn, sport, market, **_: {
                            "priceable": True, "market": market,
                            "why": "covered, in this test"})
    conn = db.open_db(tmp_path / "window.db")
    at_the_line.ensure_read_kind(conn)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g0', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-09-09T00:00Z', 'scheduled', '2026-09-08')")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-07T00:00:00Z', 'mlb', 'g0', 'moneyline', 'AAA', NULL, 0.62,"
        " 'win', 'statistical', 'final', 'fs2', '{\"coverage\": 1.0}', 'test')")
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    for stamp, implied in (("2026-09-08T23:30:00Z", 0.46),
                           ("2026-09-09T00:00:30Z", 0.30)):
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " fetched_utc, read_kind) VALUES ('kalshi', 'TM', 'e', 'mlb', 'g0',"
            " 'moneyline', 'home_win', NULL, 'home', ?, ?, ?, 'near_start')",
            (implied - 0.01, implied + 0.01, stamp))
        qid = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
            " sport, game_id, market, quantity, line, side, shape, model_prob,"
            " venue_price, venue_implied, price_basis, created_utc) VALUES"
            " (?, ?, 'kalshi', 'mlb', 'g0', 'moneyline', 'home_win', NULL,"
            " 'home', 'line_less', 0.62, ?, ?, 'mid', ?)",
            (pid, qid, implied, implied, stamp))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    before = conn.execute(
        "SELECT id FROM at_the_line_claims WHERE created_utc = '2026-09-08T23:30:00Z'"
    ).fetchone()[0]
    _hold(monkeypatch, "2026-09-08T23:40:00Z")
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["claim_id"] == before, entry
    assert entry["price"] == pytest.approx(0.46)
    conn.close()


def test_correction_instant_reads_the_start_as_an_instant(monkeypatch):
    """"HAS STARTED" IS AN INSTANT: thirty seconds after a start stored to
    the minute the claim's own instant is the correction's, not now's; a
    second before it, now's. A start nobody can read is taken as begun."""
    _hold(monkeypatch, "2026-09-05T19:00:30Z")
    assert recommend.correction_instant(
        "2026-09-05T18:00:00Z", "scheduled", "2026-09-05T19:00Z") == "2026-09-05T18:00:00Z"
    _hold(monkeypatch, "2026-09-05T18:59:59Z")
    assert recommend.correction_instant(
        "2026-09-05T18:00:00Z", "scheduled", "2026-09-05T19:00Z") is None
    assert recommend.correction_instant(
        "2026-09-05T18:00:00Z", "scheduled", "2026-09-05 nobody") == "2026-09-05T18:00:00Z"


def test_the_ufc_slate_has_begun_a_second_after_a_start_to_the_minute(conn, monkeypatch):
    """`next_slate`, which `final:ufc` asks: as text a card listed at
    "19:00Z" was still to come at 19:00:01Z."""
    _ufc_world(conn)
    conn.execute("UPDATE games SET kickoff_utc = '2026-09-05T19:00Z'")
    conn.commit()
    _hold(monkeypatch, "2026-09-05T18:59:59Z")
    assert ufc.next_slate(conn, 2026) == conn.execute(
        "SELECT week FROM games WHERE id = 'b0'").fetchone()[0]
    _hold(monkeypatch, "2026-09-05T19:00:01Z")
    assert ufc.next_slate(conn, 2026) is None
    # AND A CARD THIRTY SECONDS PAST ITS DATE IS NOT "STILL BEING ANNOUNCED"
    assert ufc.is_sanctioned_card("UFC Fight Night: A vs. B", 1, "2026-09-05T19:00Z",
                                  "2026-09-05T19:00:30Z") is False
    assert ufc.is_sanctioned_card("UFC Fight Night: A vs. B", 1, "2026-09-05T19:00Z",
                                  "2026-09-05T18:59:30Z") is True


# ---------------------------------------------------------------------------
# NEVER WRITTEN AT OR AFTER ITS START
# ---------------------------------------------------------------------------

def _a_question(conn, rung=-3.5, nth=0):
    from gridiron.factors.compute import FeatureVector
    from gridiron.model.question import Question

    game_id = conn.execute(
        "SELECT id FROM games WHERE status = 'scheduled' ORDER BY id LIMIT 1"
        " OFFSET ?", (nth,)).fetchone()["id"]
    q = Question(sport="nfl", game_id=game_id, market_type="spread",
                 market="spread", subject="KC", line_asked=rung,
                 claim=f"KC cover {rung}", yes_label="cover", no_label="not cover")
    fv = FeatureVector(sport="nfl", market_type="spread")
    fv.values["home_field"] = 1.0
    fv.raw["home_field"] = 1.0
    return q, fv


def test_no_pass_is_written_at_or_after_its_start(league, monkeypatch):
    """The writer itself refuses, at the row's own stamp read as an instant:
    two seconds after a start stored to the minute, and at the start's own
    second; a second before it the row is written. A backtest is written
    after its games on purpose and is not asked."""
    db.set_meta(league, "kind", "live")         # the fixture is a backtest
    q, fv = _a_question(league)
    league.execute("UPDATE games SET kickoff_utc = '2026-09-05T19:00Z' WHERE id = ?",
                   (q.game_id,))
    league.commit()
    for stamp in ("2026-09-05T19:00:02Z", "2026-09-05T19:00:00Z"):
        _hold(monkeypatch, stamp)
        with pytest.raises(predict.PassAtOrAfterTheStart, match="already under way"):
            predict.write_prediction(league, q, predictor="statistical",
                                     prob_yes=0.7, fv=fv, reasoning="late",
                                     final=True)
    assert league.execute("SELECT COUNT(*) FROM predictions WHERE game_id = ?",
                          (q.game_id,)).fetchone()[0] == 0
    _hold(monkeypatch, "2026-09-05T18:59:59Z")
    wrote = predict.write_prediction(league, q, predictor="statistical",
                                     prob_yes=0.7, fv=fv, reasoning="in time",
                                     final=True)
    assert wrote is not None
    assert league.execute("SELECT created_utc FROM predictions WHERE id = ?",
                          (wrote.prediction_id,)).fetchone()[0] == "2026-09-05T18:59:59Z"
    # A START NOBODY CAN READ refuses the row: nothing shows it comes first
    other, _ = _a_question(league, nth=1)
    league.execute("UPDATE games SET kickoff_utc = 'soon' WHERE id = ?",
                   (other.game_id,))
    league.commit()
    with pytest.raises(predict.PassAtOrAfterTheStart, match="cannot be read"):
        predict.write_prediction(league, other, predictor="statistical",
                                 prob_yes=0.7, fv=fv, reasoning="x", final=True)
    # A BACKTEST IS NOT ASKED
    db.set_meta(league, "kind", "backtest")
    league.execute("UPDATE games SET kickoff_utc = '2026-09-05T19:00Z' WHERE id = ?",
                   (other.game_id,))
    league.commit()
    _hold(monkeypatch, "2026-09-06T00:00:00Z")
    assert predict.write_prediction(league, other, predictor="statistical",
                                    prob_yes=0.7, fv=fv, reasoning="late",
                                    final=True) is not None


def _two_market_world(league, monkeypatch):
    store.sync_registry(league)
    for market in ("spread", "moneyline"):
        baseline.train(league, market, (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    asks_only(monkeypatch, "nfl", "spread", "moneyline")


def _week(league):
    """The slate the passes are run on; and from here the world is a LIVE
    record, as the operator's is (the fixture is a backtest, and its fits
    were activated as a scratch world's before this)."""
    db.set_meta(league, "kind", "live")
    return league.execute("SELECT MIN(week) FROM games WHERE status = 'scheduled'"
                          ).fetchone()[0]


#: The slate's start, to the minute as UFC's were stored, and on a date
#: behind the machine's own clock, so every row the run writes beside a
#: forecast (a media look, stamped by its own clock) comes after it.
_LISTED = "2026-09-05T19:00Z"


def test_the_final_pass_writes_nothing_once_its_start_has_come(league, monkeypatch):
    """THE 5 SEPTEMBER SHAPE, through the final pass itself: the slate's games
    listed to the minute at 19:00Z and the pass run a second after. Nothing
    is written, and the run names every question it did not write; a second
    before the start it writes them."""
    _two_market_world(league, monkeypatch)
    week = _week(league)
    league.execute("UPDATE games SET kickoff_utc = ? WHERE status = 'scheduled'"
                   " AND week = ?", (_LISTED, week))
    league.commit()
    asked = league.execute("SELECT COUNT(*) FROM games WHERE week = ?",
                           (week,)).fetchone()[0] * 2
    _hold(monkeypatch, "2026-09-05T19:00:01Z")
    result = run.run_slate(league, "nfl", 2025, week, include_props=False,
                           use_llm=False, final=True)
    assert result["written"] == 0
    assert league.execute("SELECT COUNT(*) FROM predictions WHERE pass_kind = 'final'"
                          ).fetchone()[0] == 0
    assert sum("already under way" in s for s in result["skipped"]) == asked, \
        result["skipped"]
    _hold(monkeypatch, "2026-09-05T18:59:59Z")
    result = run.run_slate(league, "nfl", 2025, week, include_props=False,
                           use_llm=False, final=True)
    assert result["written"] == asked


def test_a_start_that_comes_while_the_pass_works_stops_the_write(league, monkeypatch):
    """A SLOW RUN CROSSES A START: the question is asked a second before the
    start and the row would be stamped a second after it. The writer refuses
    it at its own stamp; nothing is written and the run names it."""
    _two_market_world(league, monkeypatch)
    week = _week(league)
    league.execute("UPDATE games SET kickoff_utc = ? WHERE status = 'scheduled'"
                   " AND week = ?", (_LISTED, week))
    league.commit()
    asked = league.execute("SELECT COUNT(*) FROM games WHERE week = ?",
                           (week,)).fetchone()[0] * 2
    _hold(monkeypatch, "2026-09-05T18:59:59Z")
    monkeypatch.setattr(predict, "utcnow", lambda: "2026-09-05T19:00:01Z")
    result = run.run_slate(league, "nfl", 2025, week, include_props=False,
                           use_llm=False, final=True)
    assert result["written"] == 0
    assert league.execute("SELECT COUNT(*) FROM predictions WHERE pass_kind = 'final'"
                          ).fetchone()[0] == 0
    assert sum("NOT WRITTEN" in s and "already under way" in s
               for s in result["skipped"]) == asked, result["skipped"]


# ---------------------------------------------------------------------------
# THE SCHEDULE: THE UFC FINAL PASS FIRES BY ITS LEAD
# ---------------------------------------------------------------------------

def test_the_ufc_final_pass_writes_only_inside_its_window(conn, monkeypatch):
    """`config.FINAL_PASS["ufc"]` declares 180 minutes before the first bout;
    the window is that long before the slate's first start still ahead, read
    as an instant -- the main card's once the prelims have begun."""
    _ufc_world(conn, start="2026-10-03T23:00Z", prelims="2026-10-03T20:00Z")
    week = conn.execute("SELECT week FROM games WHERE id = 'b0'").fetchone()[0]
    shut = tasks.final_pass_window(conn, "ufc", 2026, week, "2026-10-03T16:59:59Z")
    assert shut == {"open": False, "first": "2026-10-03T20:00:00Z",
                    "opens": "2026-10-03T17:00:00Z", "minutes": 180}
    assert tasks.final_pass_window(conn, "ufc", 2026, week,
                                   "2026-10-03T17:00:00Z")["open"] is True
    after_prelims = tasks.final_pass_window(conn, "ufc", 2026, week,
                                            "2026-10-03T20:00:00Z")
    assert after_prelims["first"] == "2026-10-03T23:00:00Z" and after_prelims["open"]
    over = tasks.final_pass_window(conn, "ufc", 2026, week, "2026-10-03T23:00:00Z")
    assert over["open"] is False and over["first"] is None
    for sport in ("nfl", "mlb", "cfb", "nba"):
        assert tasks.final_pass_window(conn, sport, 2026, week,
                                       "2026-10-03T17:00:00Z") is None


def test_a_firing_before_the_window_writes_nothing_and_says_when(conn, monkeypatch):
    _ufc_world(conn, start="2026-10-03T23:00Z", prelims="2026-10-03T20:00Z")
    monkeypatch.setitem(config.SPORT_CURRENT_SEASON, "ufc", 2026)
    _hold(monkeypatch, "2026-10-03T12:00:00Z")
    result, detail, payload = tasks._run_final_pass(conn, "ufc", use_llm=False)
    assert result == "noop"
    assert "waits for its window" in detail and "2026-10-03T17:00:00Z" in detail
    assert payload["window_opens"] == "2026-10-03T17:00:00Z"
    assert payload["first_start_ahead"] == "2026-10-03T20:00:00Z"


def test_the_installer_fires_final_ufc_every_thirty_minutes():
    """THE MOVE, in `tools/schedule_install.ps1`: Final-UFC repeats every
    thirty minutes (the task decides by its window); the daily 12:00 trigger
    that fired it at a main card's listed start is gone, and the task still
    wakes the machine."""
    script = (REPO / "tools" / "schedule_install.ps1").read_text(encoding="utf-8")
    block = script[script.index('-Name "$($Prefix)Final-UFC"'):]
    block = block[:block.index("-Description")]
    assert "-RepetitionInterval (New-TimeSpan -Minutes 30)" in block
    assert "-Daily" not in block
    assert audit.installer_wake_faults(script) == []
    assert config.FINAL_PASS["ufc"].fires_by_lead is True
    assert config.FINAL_PASS["ufc"].minutes_before_first == 180
    assert not any(config.FINAL_PASS[s].fires_by_lead for s in config.SPORTS if s != "ufc")


# ---------------------------------------------------------------------------
# THE GATE: NO START COMPARED AS TEXT
# ---------------------------------------------------------------------------

def _copy(tmp_path):
    import shutil

    root = tmp_path / "gridiron"
    shutil.copytree(config.PACKAGE_ROOT, root,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return root


def test_the_shipped_code_compares_no_start_as_text():
    assert audit.start_text_comparison_faults() == []
    audit.check_every_start_is_compared_as_an_instant()


def test_the_scan_names_each_text_comparison_of_a_start(tmp_path):
    """The released shapes, planted in a copy of the package: the standing
    clause's `<=`, a `kickoff_utc > ?` bound, an ORDER BY, a MIN, a Python
    comparison and a sort key -- each named by file, line and function."""
    root = _copy(tmp_path)
    planted = (
        "\n\ndef planted_window(conn):\n"
        "    return conn.execute(\"SELECT p.id FROM predictions p JOIN games g\"\n"
        "                        \" ON g.id = p.game_id WHERE p.created_utc <= g.kickoff_utc\")\n"
        "\n\ndef planted_bound(conn, now):\n"
        "    return conn.execute(\"SELECT MIN(week) FROM games WHERE kickoff_utc > ?\", (now,))\n"
        "\n\ndef planted_order(conn):\n"
        "    return conn.execute(\"SELECT id FROM games ORDER BY kickoff_utc, id\")\n"
        "\n\ndef planted_first(conn):\n"
        "    return conn.execute(\"SELECT MIN(kickoff_utc) FROM games\")\n"
        "\n\ndef planted_python(row, now):\n"
        "    return row['kickoff_utc'] <= now\n"
        "\n\ndef planted_sort(games):\n"
        "    games.sort(key=lambda g: (g['kickoff_utc'] or '', g['id']))\n")
    with open(root / "views.py", "a", encoding="utf-8") as fh:
        fh.write(planted)
    faults = audit.start_text_comparison_faults(root)
    for name, how in (("planted_window", "compared as text"),
                      ("planted_bound", "compared as text"),
                      ("planted_order", "ordered as text"),
                      ("planted_first", "taken the least of as text"),
                      ("planted_python", "compared as text in Python"),
                      ("planted_sort", "ordered as text in Python")):
        assert any(f"({name})" in f and how in f for f in faults), (name, faults)
    assert len(faults) == 6, faults


def test_the_scan_names_a_start_compared_by_another_road(tmp_path):
    """Q35's PROVER (2026-10-01): each of these got past the scan as first
    built, which named a start only under its own name and only bare -- a
    start handed to a local of another name, or to a loop over a list of
    starts; `str()` or a string method of one; one cut short of its day; one
    inside a call that keeps it text (COALESCE, datetime, a substr short of
    the day), as the greatest of such a call, or ordered by one; one in
    brackets; and one that is a scalar subquery's only column. Each is named;
    a day cut off a start, a count of starts and a start handed on and then
    read as an instant are not."""
    root = _copy(tmp_path)
    planted = (
        "\n\ndef planted_alias(row, now):\n"
        "    listed = row['kickoff_utc']\n"
        "    return listed <= now\n"
        "\n\ndef planted_loop(rows, now):\n"
        "    starts = [r['kickoff_utc'] for r in rows]\n"
        "    for start in starts:\n"
        "        if start < now:\n"
        "            return start\n"
        "\n\ndef planted_str(row, now):\n"
        "    return str(row['kickoff_utc']).rstrip('Z') < now\n"
        "\n\ndef planted_cut(row, now):\n"
        "    cut = row['kickoff_utc'][:16]\n"
        "    return cut <= now[:16]\n"
        "\n\ndef planted_coalesce(conn, now):\n"
        "    return conn.execute(\"SELECT id FROM games WHERE COALESCE(kickoff_utc, '') > ?\", (now,))\n"
        "\n\ndef planted_datetime(conn):\n"
        "    return conn.execute(\"SELECT id FROM predictions p JOIN games g ON g.id = p.game_id\"\n"
        "                        \" WHERE datetime(g.kickoff_utc) <= p.created_utc\")\n"
        "\n\ndef planted_greatest(conn):\n"
        "    return conn.execute(\"SELECT MAX(IFNULL(kickoff_utc, '')) FROM games\")\n"
        "\n\ndef planted_ordered(conn):\n"
        "    return conn.execute(\"SELECT id FROM games ORDER BY substr(kickoff_utc, 1, 16), id\")\n"
        "\n\ndef planted_brackets(conn, now):\n"
        "    return conn.execute(\"SELECT id FROM games WHERE (kickoff_utc) > ?\", (now,))\n"
        "\n\ndef planted_subquery(conn):\n"
        "    return conn.execute(\"SELECT p.id FROM predictions p WHERE (SELECT g.kickoff_utc\"\n"
        "                        \" FROM games g WHERE g.id = p.game_id) >= p.created_utc\")\n"
        "\n\ndef planted_lawful(conn, row, today, now):\n"
        "    listed = row['kickoff_utc']\n"
        "    ok = row['kickoff_utc'][:10] < today and instant(listed) < instant(now)\n"
        "    return ok, conn.execute(\"SELECT COUNT(kickoff_utc) > 0,\"\n"
        "                            \" substr(kickoff_utc, 1, 10) < date('now'),\"\n"
        "                            \" julianday(COALESCE(kickoff_utc, ?)) < julianday(?)\"\n"
        "                            \" FROM games\", (now, now))\n")
    with open(root / "views.py", "a", encoding="utf-8") as fh:
        fh.write(planted)
    faults = audit.start_text_comparison_faults(root)
    for name, how in (("planted_alias", "compared as text in Python"),
                      ("planted_loop", "compared as text in Python"),
                      ("planted_str", "compared as text in Python"),
                      ("planted_cut", "compared as text in Python"),
                      ("planted_coalesce", "compared as text (inside COALESCE)"),
                      ("planted_datetime", "compared as text (inside DATETIME)"),
                      ("planted_greatest", "taken the greatest of as text"),
                      ("planted_ordered", "ordered as text (inside SUBSTR)"),
                      ("planted_brackets", "compared as text (inside brackets)"),
                      ("planted_subquery", "inside a subquery's one column")):
        assert any(f"({name})" in f and how in f for f in faults), (name, faults)
    assert not any("(planted_lawful)" in f for f in faults), faults
    assert len(faults) == 10, faults


def test_the_held_register_only_shrinks(tmp_path):
    root = _copy(tmp_path)
    held = dict(audit.START_TEXT_COMPARISONS_HELD)
    assert audit.start_text_comparison_faults(root, held=held) == []
    extra = dict(held)
    extra[("gridiron/views.py", "anything")] = "2026-10-02: added later"
    faults = audit.start_text_comparison_faults(root, held=extra)
    assert any("was not held on 2026-10-01" in f for f in faults), faults
    assert any("no text comparison of a start is found there" in f for f in faults)
    undated = {k: "because" for k in held}
    assert any("carries no date" in f for f in audit.start_text_comparison_faults(
        root, held=undated))
    faults = audit.start_text_comparison_faults(root, held={})
    assert any("recommendation_close_is_a_later_read_of_its_own_contract" in f
               for f in faults), faults


def test_the_gate_makes_the_call():
    tree = ast.parse((REPO / "tools" / "verify.py").read_text(encoding="utf-8"))
    step = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "step_2_guards")
    assert any(isinstance(n, ast.Attribute)
               and n.attr == "check_every_start_is_compared_as_an_instant"
               for n in ast.walk(step))


def _released_order(forecast, game, row=None):
    """`calibration.standing_pass_order` as released (a9c5193): the stored
    text, and `<=`."""
    row = row or forecast
    return (f"({forecast}.pass_kind = 'final' AND ({game}.kickoff_utc IS NULL"
            f" OR {forecast}.created_utc <= {game}.kickoff_utc)) DESC,"
            f" {row}.created_utc DESC, {row}.id DESC")


def _released_clause(same_set):
    """`calibration.standing_row_clause` as released (a9c5193)."""
    from gridiron import bet

    same = (" AND p2.factor_set_version = p.factor_set_version"
            if same_set else "")
    return (
        " AND NOT EXISTS (SELECT 1 FROM prediction_voids vs"
        "                 WHERE vs.prediction_id = p.id)"
        " AND p.id = (SELECT p2.id FROM predictions p2"
        "              JOIN games g2 ON g2.id = p2.game_id"
        f"              WHERE {bet.same('p2', 'p')}{same}"
        "                AND NOT EXISTS (SELECT 1 FROM prediction_voids v2"
        "                                WHERE v2.prediction_id = p2.id)"
        "                AND (g2.kickoff_utc IS NULL"
        "                     OR p2.created_utc <= g2.kickoff_utc"
        "                     OR NOT EXISTS (SELECT 1 FROM predictions p3"
        "                                    JOIN games g3 ON g3.id = p3.game_id"
        f"                                    WHERE {bet.same('p3', 'p2')}"
        "                                      AND p3.created_utc <= g3.kickoff_utc))"
        f"              ORDER BY {_released_order('p2', 'g2')} LIMIT 1)")


def _released_claims(rows):
    """`recount.standing_claims_of` as released (a9c5193): text, `<`."""
    from gridiron import bet

    def order(row):
        return (row["pass_kind"] == "final" and (
            row["kickoff_utc"] is None or row["forecast_utc"] <= row["kickoff_utc"]),
            row["created_utc"], row["id"])

    out = {}
    for row in rows:
        if row["voided"]:
            continue
        if row["kickoff_utc"] is not None and not row["created_utc"] < row["kickoff_utc"]:
            continue
        held = out.get(bet.of(row))
        if held is None or order(row) > order(held):
            out[bet.of(row)] = row
    return out


def test_the_gate_asks_every_door_on_a_start_to_the_minute(monkeypatch):
    """`audit.standing_pass_faults` asks every door on a world whose start is
    stored to the minute too: the clause put back as released keeps the
    final pass written two seconds after the start and the one written at
    its second, and the recount put back as released keeps a claim written
    thirty seconds into the game -- each named."""
    assert audit.standing_pass_faults() == []
    monkeypatch.setattr(calibration, "standing_pass_order", _released_order)
    monkeypatch.setattr(calibration, "standing_row_clause", _released_clause)
    faults = audit.standing_pass_faults()
    minute = [f for f in faults if f.startswith("with the start stored to the minute")]
    for door in ("calibration.standing_row_clause:", "horizon.standing_questions",
                 "views.week"):
        assert any(door in f and "EIGHTEEN" in f and "+2s" in f for f in minute), (door, faults)
        assert any(door in f and "ATSTART" in f and "+0s" in f for f in minute), (door, faults)
    assert not [f for f in faults if not f.startswith("with the start")], faults
    with pytest.raises(audit.LawViolation, match="question 27"):
        audit.check_the_final_pass_stands()
    monkeypatch.undo()
    monkeypatch.setattr(recount, "standing_claims_of", _released_claims)
    faults = audit.standing_pass_faults()
    assert any("recount.standing_claims_of" in f and "at or after its game's start" in f
               for f in faults), faults


# ---------------------------------------------------------------------------
# THE SCHEMA: A CLOSE READ AT OR AFTER THE START, AS INSTANTS
# ---------------------------------------------------------------------------

def test_the_schema_refuses_a_close_read_in_the_first_minute_of_a_game(conn):
    """The later-read rule compares as text and lets a read thirty seconds
    into a game stored to the minute be a close; the rule beside it refuses
    it, read as instants, and lets a read before the start through."""
    at_the_line.ensure_read_kind(conn)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g1', 'ufc', 2026, 1, 'REG',"
        " 'A', 'B', '2026-09-27T02:00Z', 'scheduled', '2026-09-26')")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-26T12:00:00Z', 'ufc', 'g1', 'moneyline', 'A', 0.6, 'win',"
        " 'statistical', 'final', 'fs2', '{}', 'x')")
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    quotes = {}
    for stamp in ("2026-09-26T12:30:00Z", "2026-09-27T01:59:00Z",
                  "2026-09-27T02:00:30Z"):
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " fetched_utc, read_kind) VALUES ('kalshi', 'TM', 'E', 'ufc', 'g1',"
            " 'moneyline', 'home_win', NULL, 'home', 0.45, 0.47, ?, 'near_start')",
            (stamp,))
        quotes[stamp] = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, model_prob, venue_price,"
        " venue_implied, price_basis, created_utc) VALUES (?, ?, 'kalshi', 'ufc',"
        " 'g1', 'moneyline', 'home_win', NULL, 'home', 'line_less', 0.6, 0.46,"
        " 0.46, 'mid', '2026-09-26T12:31:00Z')", (pid, quotes["2026-09-26T12:30:00Z"]))
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market, side,"
        " fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc, closed_utc, close_price, clv_cents) VALUES (?, 'ufc', 'g1',"
        " 'moneyline', 'yes', 0.6, 0.46, 10.0, 'flat', 1.0, 0,"
        " '2026-09-26T13:00:00Z', '2026-09-27T03:00:00Z', 0.46, 0.0)", (pid,))
    rec = conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
    conn.commit()

    def close(stamp):
        conn.execute(
            "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
            " pricing_quote_id, close_quote_id, close_price, clv_cents,"
            " minutes_before_start, restated, reason) VALUES (?,"
            " '2026-09-27T03:00:00Z', ?, ?, 0.46, 0.0, 0.5, 0, 'a close in a test')",
            (rec, quotes["2026-09-26T12:30:00Z"], quotes[stamp]))

    with pytest.raises(sqlite3.IntegrityError, match="read as an instant"):
        close("2026-09-27T02:00:30Z")
    conn.rollback()
    close("2026-09-27T01:59:00Z")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM recommendation_closes").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# THE 18: VOIDED BY RULE, ONCE, BY APPEND-ONLY ROWS
# ---------------------------------------------------------------------------

def _tool():
    path = REPO / "tools" / "void_passes_written_at_the_start.py"
    spec = importlib.util.spec_from_file_location("void_at_the_start_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _eighteen_world(path):
    """Three bouts listed to the minute, each with an early pass the day
    before and a final pass two seconds into it, all settled; and an MLB
    pass written after first pitch, already withdrawn for that reason."""
    conn = db.open_db(path)
    finals = []
    for n in range(3):
        _settled_bout(conn, start="2026-09-05T19:00Z", gid=f"b{n}")
        _pass(conn, gid=f"b{n}", kind="early", written="2026-09-04T02:05:10Z")
    for n in range(3):
        finals.append(_pass(conn, gid=f"b{n}", kind="final",
                            written="2026-09-05T19:00:02Z"))
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('m1', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-08-29T17:05:00Z', 'scheduled', '2026-08-29')")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-08-29T19:17:55Z', 'mlb', 'm1', 'moneyline', 'AAA', 0.6, 'win',"
        " 'statistical', 'early', 'fs2', '{}', 'late')")
    late = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, '2026-08-29T19:19:07Z', 'written after first pitch')",
                 (late,))
    conn.commit()
    conn.close()
    return finals, late


def test_the_void_tool_selects_by_rule_and_writes_each_void_once(tmp_path, monkeypatch, capsys):
    path = tmp_path / "eighteen.db"
    finals, late = _eighteen_world(path)
    tool = _tool()
    monkeypatch.setattr(tool, "RULED", tuple(finals))
    assert tool.main(["--database", str(path)]) == 0
    out = capsys.readouterr().out
    assert "--write would void 3" in out and f"{late}" in out
    conn = db.read_only(path, "the test's own world")
    assert conn.execute("SELECT COUNT(*) FROM prediction_voids").fetchone()[0] == 1
    conn.close()
    assert tool.main(["--database", str(path), "--write"]) == 0
    assert "wrote 3 void(s)" in capsys.readouterr().out
    assert tool.main(["--database", str(path), "--write"]) == 0
    assert "wrote 0 void(s)" in capsys.readouterr().out
    conn = db.read_only(path, "the test's own world")
    voids = {r["prediction_id"]: r["reason"] for r in conn.execute(
        "SELECT * FROM prediction_voids")}
    assert set(voids) == {late, *finals}
    assert all(voids[f] == tool.REASON for f in finals)
    assert len(tool.REASON.strip()) >= 10 and "question 35" in tool.REASON
    # Q27'S STANDING RULE THEN FALLS BACK TO THEIR EARLY PASSES
    standing = {r.id for r in calibration.resolved(conn, sport="ufc")}
    early = {r[0] for r in conn.execute(
        "SELECT id FROM predictions WHERE pass_kind = 'early' AND sport = 'ufc'")}
    assert standing == early
    conn.close()


def test_the_void_tool_refuses_a_selection_the_ruling_did_not_name(tmp_path, monkeypatch, capsys):
    path = tmp_path / "eighteen.db"
    finals, _late = _eighteen_world(path)
    tool = _tool()
    monkeypatch.setattr(tool, "RULED", tuple(finals[:2]))
    with pytest.raises(SystemExit) as refused:
        tool.main(["--database", str(path), "--write"])
    assert refused.value.code == 2
    assert f"Selected and not ruled: [{finals[2]}]" in capsys.readouterr().out
    conn = db.read_only(path, "the test's own world")
    assert conn.execute("SELECT COUNT(*) FROM prediction_voids").fetchone()[0] == 1
    conn.close()
    # THE RECORD ONLY WITH --live, AND --live ONLY ON THE RECORD
    monkeypatch.setattr(tool, "RULED", tuple(finals))
    monkeypatch.setattr(db, "is_the_live_record_file", lambda p: True)
    with pytest.raises(SystemExit) as refused:
        tool.main(["--database", str(path), "--write"])
    assert refused.value.code == 2 and "--live" in capsys.readouterr().out
    monkeypatch.setattr(db, "is_the_live_record_file", lambda p: False)
    with pytest.raises(SystemExit):
        tool.main(["--database", str(path), "--write", "--live"])
    # A BACKTEST IS NOT THE RECORD THE RULING IS ABOUT
    conn = db.connect(path)
    db.set_meta(conn, "kind", "backtest")
    conn.close()
    with pytest.raises(SystemExit) as refused:
        tool.main(["--database", str(path), "--write"])
    assert "backtest" in capsys.readouterr().out


def test_the_reason_is_plain_words():
    tool = _tool()
    assert audit.plain_words_violations(tool.REASON) == []
    assert tool.RULED == tuple(range(1014, 1032))
