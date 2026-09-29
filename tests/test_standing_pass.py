"""Operator question 27, ruled 2026-09-28 (the brief's reading confirmed by the
operator on 2026-09-29; built 2026-09-29): "the standing pass is chosen by
pass, not by write time: the final pass stands whenever one exists before the
start; otherwise the latest early pass. A read rule -- no row changes. ...
Separately, a catch-up may not run an early pass for a question whose final
pass exists; it is a SlateAlreadyAnswered noop."

THE RULE is `calibration.standing_row_clause`, ordered by the one door
`calibration.standing_pass_order`; the at-the-line window orders its claims by
the same door; the guard's second spelling is `gridiron.recount`; the
correction's measurement reads it by pass alone; the slate's card reads the
clause; and `audit.standing_pass_faults` asks every one of them on a world
made to tell the pass from the write time (gate step 2). THE NOOP is
`predict.final_pass_written`, asked before every early pass's write, and
`run.run_slate`'s refusal of a run left with nothing else to write.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from gridiron import (audit, bet, calibration, config, correction, db, language,
                      recount, run, tasks, views)
from gridiron.factors import store
from gridiron.model import activation, baseline, predict
from tests.conftest import asks_only

FACTORS = '{"values": {}, "present": [], "absent": []}'
SUBJECT = "QTWENTYSEVEN"
SET_A, SET_B = "fs-q27-a", "fs-q27-b"


def _shift(stamp: str, seconds: int) -> str:
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return (moment + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _played_game(conn, n=0):
    return conn.execute(
        "SELECT id, season, week, kickoff_utc FROM games WHERE sport = 'nfl'"
        "   AND status = 'final' AND kickoff_utc IS NOT NULL"
        " ORDER BY kickoff_utc, id LIMIT 1 OFFSET ?", (n,)).fetchone()


def _forecast(conn, game_id, kickoff, pass_kind, seconds, *, fs=None,
              prob=0.6, rung=-3.5, subject=SUBJECT, written=None):
    """One statistical spread forecast of the planted question, written
    `seconds` from the kickoff (negative: before it)."""
    cur = conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (written or _shift(kickoff, seconds), "nfl", game_id, "spread",
         subject, rung, prob, "cover", "statistical", pass_kind,
         fs or config.FACTOR_SET_VERSION, FACTORS, "planted by question 27"))
    conn.commit()
    return cur.lastrowid


def _standing(conn, same_set=None, subject=SUBJECT) -> set[int]:
    """The ids the one clause keeps for the planted question."""
    where, params = "p.subject = ?", [subject]
    if same_set:
        where += " AND p.factor_set_version = ?"
        params.append(same_set)
    return {r[0] for r in conn.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE {where}" + calibration.standing_row_clause(bool(same_set)),
        params)}


def _recounted(conn, subject=SUBJECT) -> set[int]:
    """The ids the guard's own spelling keeps for the planted question."""
    rows = [r for r in recount.forecasts(conn, sport="nfl", predictor="statistical",
                                         market_type="spread", prop_type=None,
                                         event_tier=None)
            if r["subject"] == subject]
    return {r["id"] for r in recount.standing_of(rows).values()}


def _void(conn, prediction_id):
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, ?, ?)",
                 (prediction_id, "2026-09-28T12:00:00Z",
                  "withdrawn in this test, by hand"))
    conn.commit()


# ---------------------------------------------------------------------------
# THE RULE
# ---------------------------------------------------------------------------

def test_a_final_pass_before_the_start_stands_over_a_later_early_pass(league):
    """THE SIXTEEN NFL TOTALS' SHAPE: the final pass written first (23 Sep
    19:30Z), the early pass after it (24 Sep 05:32Z), both before the start.
    The write time kept the early pass; the ruling keeps the final."""
    game = _played_game(league)
    final = _forecast(league, game["id"], game["kickoff_utc"], "final", -2 * 86400,
                      prob=0.71)
    early = _forecast(league, game["id"], game["kickoff_utc"], "early", -86400,
                      prob=0.58)
    assert _standing(league) == {final}, "the later EARLY pass stood over the final"
    assert _standing(league, same_set=config.FACTOR_SET_VERSION) == {final}
    assert _recounted(league) == {final}, "the recount and the clause disagree"
    # AND THE CURVE GRADES IT, a read rule: no row changed but the outcome
    # the resolver writes.
    kept = ("SELECT id, created_utc, pass_kind, model_prob, factor_set_version"
            "  FROM predictions WHERE id IN (?, ?) ORDER BY id")
    before = [tuple(r) for r in league.execute(kept, (final, early))]
    league.execute("UPDATE predictions SET resolved_utc = ?, outcome = 1"
                   " WHERE id IN (?, ?)", ("2026-09-28T12:00:00Z", final, early))
    league.commit()
    graded = [r for r in calibration.resolved(league, sport="nfl")
              if r.subject == SUBJECT]
    assert [(r.id, r.model_prob) for r in graded] == [(final, 0.71)]
    assert [tuple(r) for r in league.execute(kept, (final, early))] == before


def test_an_early_pass_then_a_final_pass_still_leaves_the_final(league):
    """The ordinary order, unchanged: the final pass written close to the
    start after the early one."""
    game = _played_game(league)
    _forecast(league, game["id"], game["kickoff_utc"], "early", -86400)
    final = _forecast(league, game["id"], game["kickoff_utc"], "final", -3600)
    assert _standing(league) == _recounted(league) == {final}


def test_two_early_passes_and_no_final_the_latest_early_stands(league):
    """The ruling's "otherwise the latest early pass": two early passes of
    one question (two factor sets, as on 2026-08-29), no final pass."""
    game = _played_game(league)
    _forecast(league, game["id"], game["kickoff_utc"], "early", -2 * 86400, fs=SET_A)
    later = _forecast(league, game["id"], game["kickoff_utc"], "early", -86400, fs=SET_B)
    assert _standing(league) == _recounted(league) == {later}


def test_a_withdrawn_final_pass_leaves_the_latest_early_pass_standing(league):
    """A withdrawn row is never a candidate (ruling 1, 2026-09-24): with the
    final pass withdrawn the question stands on its LATEST early pass, not
    on none and not on the earlier early pass."""
    game = _played_game(league)
    final = _forecast(league, game["id"], game["kickoff_utc"], "final", -3 * 86400,
                      fs=SET_A)
    _forecast(league, game["id"], game["kickoff_utc"], "early", -2 * 86400, fs=SET_A)
    latest = _forecast(league, game["id"], game["kickoff_utc"], "early", -86400,
                       fs=SET_B)
    assert _standing(league) == _recounted(league) == {final}
    _void(league, final)
    assert _standing(league) == _recounted(league) == {latest}


def test_a_final_pass_written_after_the_start_never_stands(league):
    """A row written after the game began is not a forecast: with an early
    pass before the start, the final pass after it never stands -- over one
    early pass or two."""
    game = _played_game(league)
    early = _forecast(league, game["id"], game["kickoff_utc"], "early", -86400)
    _forecast(league, game["id"], game["kickoff_utc"], "final", +3600)
    assert _standing(league) == _recounted(league) == {early}
    later = _forecast(league, game["id"], game["kickoff_utc"], "early", -3600,
                      fs=SET_B)
    assert _standing(league) == _recounted(league) == {later}


def test_the_backtest_fallback_is_unchanged(league):
    """NOTHING WRITTEN BEFORE THE START (a backtest): the latest row stands,
    whatever its pass, exactly as before the ruling -- in either order."""
    one, two = _played_game(league, 0), _played_game(league, 1)
    # a final pass written after an early pass, both after the start
    _forecast(league, one["id"], one["kickoff_utc"], "early", +3600, subject="FALLBACKA")
    last_a = _forecast(league, one["id"], one["kickoff_utc"], "final", +7200,
                       subject="FALLBACKA")
    # an early pass written after a final pass, both after the start: the
    # early one is the latest and stands -- the pass is not read here
    _forecast(league, two["id"], two["kickoff_utc"], "final", +3600, subject="FALLBACKB")
    last_b = _forecast(league, two["id"], two["kickoff_utc"], "early", +7200,
                       subject="FALLBACKB")
    for subject, last in (("FALLBACKA", last_a), ("FALLBACKB", last_b)):
        assert _standing(league, subject=subject) == {last}
        assert _recounted(league, subject=subject) == {last}


def test_a_game_with_no_start_time_keeps_its_final_pass(league):
    """Every row of a game with no start time recorded is a candidate, as the
    clause has always kept it; among them the final pass stands."""
    league.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status) VALUES ('2025_99_KC_BUF', 'nfl', 2025, 19, 'REG',"
        " 'BUF', 'KC', NULL, 'scheduled')")
    league.commit()
    final = _forecast(league, "2025_99_KC_BUF", None, "final", 0,
                      written="2025-12-01T00:00:00Z")
    _forecast(league, "2025_99_KC_BUF", None, "early", 0,
              written="2025-12-02T00:00:00Z")
    assert _standing(league) == _recounted(league) == {final}


def test_the_slate_card_shows_the_pass_the_record_grades(league):
    """PICKS AND THE RECORD MUST NEVER DISAGREE (views.week, 2026-09-03). The
    card had a rule of its own, by write time; from the ruling it reads the
    one clause, so a final pass written before a later early pass is the
    card, and the early row is the early view."""
    game = league.execute(
        "SELECT id, season, week, kickoff_utc FROM games WHERE sport = 'nfl'"
        "   AND status = 'scheduled' ORDER BY kickoff_utc, id LIMIT 1").fetchone()
    final = _forecast(league, game["id"], game["kickoff_utc"], "final", -2 * 86400,
                      prob=0.71)
    early = _forecast(league, game["id"], game["kickoff_utc"], "early", -86400,
                      prob=0.58)
    payload = views.week(league, "nfl", game["season"], game["week"])
    mine = [c for c in payload["cards"] if c["subject"] == SUBJECT]
    assert len(mine) == 1, "one card per question"
    assert mine[0]["prediction_id"] == final, "the card showed the early pass"
    assert abs(mine[0]["model_prob"] - 0.71) < 1e-9
    assert mine[0]["is_early_view"] is False
    shown = views.week(league, "nfl", game["season"], game["week"], early_view=True)
    theirs = [c for c in shown["cards"] if c["subject"] == SUBJECT]
    assert [c["prediction_id"] for c in theirs] == [early]
    assert theirs[0]["is_early_view"] is True


def test_a_withdrawn_later_row_no_longer_takes_its_question_off_the_slate(league):
    """THE CARD'S OLD RULE did not skip a withdrawn row when choosing: a
    withdrawn final pass knocked out the early pass before it, and the fetch
    then dropped the withdrawn one, so the question left the slate. Read
    through the clause, the early pass is the card."""
    game = league.execute(
        "SELECT id, season, week, kickoff_utc FROM games WHERE sport = 'nfl'"
        "   AND status = 'scheduled' ORDER BY kickoff_utc, id LIMIT 1").fetchone()
    early = _forecast(league, game["id"], game["kickoff_utc"], "early", -86400)
    final = _forecast(league, game["id"], game["kickoff_utc"], "final", -3600)
    _void(league, final)
    payload = views.week(league, "nfl", game["season"], game["week"])
    assert [c["prediction_id"] for c in payload["cards"]
            if c["subject"] == SUBJECT] == [early]


def test_the_at_the_line_record_keeps_the_final_pass_claim(tmp_path):
    """The at-the-line record's rows are claims; the near-start reader writes
    one for every forecast at each look in the order of their numbers, so an
    early pass written after its final pass gets the later claim at each
    look. That claim stood; the final pass's stands from the ruling, in the
    door and in the recount alike, and the count is one bet either way."""
    from gridiron.market import at_the_line
    from tests.test_at_the_line import DIST, _finish, _quote, _soon

    conn = db.open_db(tmp_path / "q27_claims.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date)"
        " VALUES ('2026_01_NE_SEA', 'nfl', 2026, 1, 'REG', 'SEA', 'NE',"
        " ?, 'scheduled', '2026-09-09')", (_soon(),))
    factors = json.dumps({"margin_distribution": DIST})
    ids = {}
    for pass_kind, written, prob in (("final", "2026-09-06T00:00:00Z", 0.62),
                                     ("early", "2026-09-07T00:00:00Z", 0.55)):
        cur = conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES (?, 'nfl', '2026_01_NE_SEA', 'spread', 'SEA', -3.5, ?,"
            " 'cover', 'statistical', ?, 'fs5', ?, 'test')",
            (written, prob, pass_kind, factors))
        ids[pass_kind] = cur.lastrowid
    conn.commit()
    at_the_line.ensure_read_kind(conn)
    _quote(conn, ticker="look-1", line=-4.5, yes_bid=0.45, yes_ask=0.47,
           fetched_utc="2026-09-08T00:00:00Z")
    _quote(conn, ticker="look-2", line=-6.5, yes_bid=0.49, yes_ask=0.51,
           fetched_utc="2026-09-09T00:00:00Z")
    assert at_the_line.evaluate(conn)["claims"] == 4
    _finish(conn, 27, 20)
    tasks.settle_everything(conn)
    newest = conn.execute("SELECT prediction_id FROM at_the_line_claims"
                          " ORDER BY created_utc DESC, id DESC LIMIT 1").fetchone()[0]
    assert newest == ids["early"], "the world must give the early pass the newest claim"
    chosen = at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                         predictor="statistical")
    assert [c["prediction_id"] for c in chosen] == [ids["final"]], (
        "the at-the-line record kept the early pass's claim over the final's")
    assert chosen[0]["line"] == -6.5, "and within the pass, its last look"
    again = recount.standing_claims_of(recount.claims(
        conn, sport="nfl", market="spread", predictor="statistical", event_tier=None))
    assert [c["prediction_id"] for c in again.values()] == [ids["final"]]
    card = calibration.at_the_line_scorecard(conn, sport="nfl")
    spread = next(c for c in card["categories"]
                  if c["market"] == "spread" and c["predictor"] == "statistical")
    assert spread["n"] == spread["recounted"] == spread["distinct_bets"] == 1
    conn.close()


def test_the_correction_measures_each_question_on_its_final_pass(tmp_path):
    """THE MEASUREMENT READS THE PASS, NOT THE START (question 32's gate, from
    question 27): the correction may not read `games`, so of a question's
    settled forecasts it keeps a final pass first and the latest written
    otherwise -- the blind record's rule wherever no forecast was written
    after its start, which `tools/correction_holdout.py` checks question by
    question against `recount.correction_standing`."""
    conn = db.open_db(tmp_path / "q27_correction.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('g1', 'nfl', 2025, 1, 'REG', 'AAA', 'BBB',"
        " '2025-12-01T18:00:00Z', 'final', '2025-12-01', 24, 17)")
    ids = {}
    for subject, rows in (("SIXTEEN", (("final", "fsA", "2025-12-01T06:00:00Z"),
                                       ("early", "fsA", "2025-12-01T12:00:00Z"))),
                          ("TWOEARLY", (("early", "fsA", "2025-12-01T06:00:00Z"),
                                        ("early", "fsB", "2025-12-01T12:00:00Z")))):
        for pass_kind, fs, written in rows:
            cur = conn.execute(
                "INSERT INTO predictions (sport, created_utc, game_id, market_type,"
                " subject, line_asked, model_prob, model_side, predictor,"
                " pass_kind, factor_set_version, factors_json, reasoning,"
                " resolved_utc, outcome) VALUES ('nfl', ?, 'g1', 'total', ?,"
                " 44.5, 0.6, 'over', 'statistical', ?, ?, '{}', 'q27',"
                " '2025-12-02T00:00:00Z', 1)", (written, subject, pass_kind, fs))
            ids[(subject, pass_kind, fs)] = cur.lastrowid
    conn.commit()
    fit = {"sport": "nfl", "market_type": "total", "forecaster": "statistical",
           "fitted_utc": "2025-12-03T00:00:00Z"}
    kept = {r["subject"]: r["id"] for r in correction.holdout_questions(conn, fit)}
    assert kept == {"SIXTEEN": ids[("SIXTEEN", "final", "fsA")],
                    "TWOEARLY": ids[("TWOEARLY", "early", "fsB")]}
    standing = recount.correction_standing(
        conn, sport="nfl", market_type="total", predictor="statistical",
        before_utc=fit["fitted_utc"])
    assert sorted(standing.values()) == sorted(kept.values())
    conn.close()


def test_the_gate_asks_every_door_on_a_world_that_tells_them_apart(monkeypatch):
    """`audit.standing_pass_faults` (gate step 2): every door keeps the ruled
    row on its world, and each door put back to the write time is named --
    the one order (which the clause, the outlook's door, the at-the-line
    window and the card all read), the recount's two spellings and the
    correction's measurement."""
    assert audit.standing_pass_faults() == []
    audit.check_the_final_pass_stands()                  # must not raise

    monkeypatch.setattr(
        calibration, "standing_pass_order",
        lambda f, g, row=None: f"{row or f}.created_utc DESC, {row or f}.id DESC")
    faults = audit.standing_pass_faults()
    for door in ("calibration.standing_row_clause:",
                 "calibration.standing_row_clause within one factor set",
                 "horizon.standing_questions", "market.at_the_line.standing_claims",
                 "views.week"):
        assert any(f.startswith(door) and "SIXTEEN" in f for f in faults), (door, faults)
    with pytest.raises(audit.LawViolation, match="question 27"):
        audit.check_the_final_pass_stands()
    monkeypatch.undo()

    by_write_time = lambda rows: {  # noqa: E731
        bet.of(r): max((x for x in rows if bet.of(x) == bet.of(r)),
                       key=lambda x: (x["created_utc"], x["id"]))
        for r in rows}
    monkeypatch.setattr(recount, "standing_of", by_write_time)
    faults = audit.standing_pass_faults()
    assert any(f.startswith("recount.standing_of") for f in faults), faults
    monkeypatch.undo()

    def latest_claim(rows):
        out = {}
        for row in rows:
            if row["voided"] or not row["created_utc"] < row["kickoff_utc"]:
                continue
            held = out.get(bet.of(row))
            if held is None or (row["created_utc"], row["id"]) > (held["created_utc"], held["id"]):
                out[bet.of(row)] = row
        return out

    monkeypatch.setattr(recount, "standing_claims_of", latest_claim)
    faults = audit.standing_pass_faults()
    assert any(f.startswith("recount.standing_claims_of") for f in faults), faults
    monkeypatch.undo()

    def latest_written(conn, fit):
        standing = {}
        for row in correction.settled_rows(
                conn, sport=fit["sport"], market_type=fit["market_type"],
                forecaster=fit["forecaster"], before_utc=fit["fitted_utc"]):
            held = standing.get(bet.of(row))
            if held is None or (row["created_utc"], row["id"]) > (held["created_utc"], held["id"]):
                standing[bet.of(row)] = row
        return list(standing.values())

    monkeypatch.setattr(correction, "holdout_questions", latest_written)
    faults = audit.standing_pass_faults()
    assert any(f.startswith("correction.holdout_questions") and "SIXTEEN" in f
               for f in faults), faults


def test_the_world_would_have_caught_the_rule_as_released():
    """THE WORLD TELLS THEM APART: under the order as released (the write
    time alone) its sixteen-shaped question stands on the early pass, and
    under the ruling on the final -- so the gate's check is not asking a
    world where both rules agree."""
    shape = next(q for q in audit.STANDING_PASS_WORLD if q[0] == "SIXTEEN")
    rows = shape[1]
    by_pass = max(range(len(rows)), key=lambda i: (rows[i][0] == "final", rows[i][2]))
    by_time = max(range(len(rows)), key=lambda i: rows[i][2])
    assert by_pass == shape[2] != by_time


# ---------------------------------------------------------------------------
# THE NOOP
# ---------------------------------------------------------------------------

def _a_question(conn, rung=-3.5):
    from gridiron.factors.compute import FeatureVector
    from gridiron.model.question import Question

    game_id = conn.execute(
        "SELECT id FROM games WHERE status = 'scheduled' ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    q = Question(sport="nfl", game_id=game_id, market_type="spread",
                 market="spread", subject="KC", line_asked=rung,
                 claim=f"KC cover {rung}", yes_label="cover", no_label="not cover")
    fv = FeatureVector(sport="nfl", market_type="spread")
    fv.values["home_field"] = 1.0
    fv.raw["home_field"] = 1.0
    return q, fv


def test_no_early_pass_is_written_over_a_final_pass(league):
    """The one door, asked by the writer itself: a caller that forgot to ask
    still writes nothing."""
    q, fv = _a_question(league)
    assert predict.final_pass_written(league, q, "statistical") is False
    final = predict.write_prediction(league, q, predictor="statistical",
                                     prob_yes=0.7, fv=fv, reasoning="late",
                                     final=True)
    assert final is not None
    assert predict.final_pass_written(league, q, "statistical") is True
    assert predict.final_pass_written(league, q, "llm") is False, "one forecaster's"
    assert predict.write_prediction(league, q, predictor="statistical",
                                    prob_yes=0.55, fv=fv, reasoning="early") is None
    assert league.execute("SELECT COUNT(*) FROM predictions WHERE game_id = ?"
                          " AND pass_kind = 'early'", (q.game_id,)).fetchone()[0] == 0
    # ANOTHER RUNG IS ANOTHER QUESTION (question 21): written
    other, _ = _a_question(league, rung=-6.5)
    assert predict.write_prediction(league, other, predictor="statistical",
                                    prob_yes=0.55, fv=fv, reasoning="early") is not None
    # "EXISTS" AS WRITTEN: a withdrawn final pass still exists
    _void(league, final.prediction_id)
    assert predict.final_pass_written(league, q, "statistical") is True
    assert predict.write_prediction(league, q, predictor="statistical",
                                    prob_yes=0.55, fv=fv, reasoning="early") is None


def _two_market_world(league, monkeypatch):
    """Spread and moneyline trained and asked, and nothing else."""
    store.sync_registry(league)
    for market in ("spread", "moneyline"):
        baseline.train(league, market, (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    asks_only(monkeypatch, "nfl", "spread", "moneyline")


def _hold(monkeypatch, *markets):
    """Hold the named NFL markets -- the test world's way to leave a market
    with no row, which keeps the slate open, as the untrained spread and
    moneyline kept week 3 open on 24 September."""
    monkeypatch.setattr(config, "HELD_MARKETS", {
        ("nfl", m): {"held": "2026-09-24", "reason": config.HELD_REASON}
        for m in markets})


def _early_rows(conn, week, market):
    return conn.execute(
        "SELECT COUNT(*) FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE g.season = 2025 AND g.week = ? AND p.market_type = ?"
        "   AND p.pass_kind = 'early'", (week, market)).fetchone()[0]


def test_an_early_run_writes_the_open_questions_and_names_the_answered(league, monkeypatch):
    """24 SEPTEMBER'S SHAPE: the final pass answered one market, another had
    no row, so the slate was open and the catch-up's early pass wrote over
    the answered one. Now it writes the open market and names the rest."""
    _two_market_world(league, monkeypatch)
    _hold(monkeypatch, "moneyline")
    finals = run.run_week(league, 2025, 7, include_props=False, use_llm=False,
                          final=True)
    assert finals["written"] == 4 and finals["final_pass_answered"] == []
    _hold(monkeypatch)
    result = run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert _early_rows(league, 7, "spread") == 0, "an early pass over a final one"
    assert _early_rows(league, 7, "moneyline") == 4
    assert result["written"] == 4
    named = result["final_pass_answered"]
    assert len(named) == 4 and all("spread" in n and n.endswith(", statistical")
                                   for n in named)
    assert any("final pass is written" in s for s in result["skipped"])


def test_an_early_run_left_with_nothing_to_write_is_refused_as_answered(league, monkeypatch):
    _two_market_world(league, monkeypatch)
    _hold(monkeypatch, "moneyline")
    run.run_week(league, 2025, 7, include_props=False, use_llm=False, final=True)
    before = league.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    with pytest.raises(run.SlateAlreadyAnswered) as refused:
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert type(refused.value) is run.SlateAlreadyAnswered
    assert len(refused.value.final_pass_answered) == 4
    assert "No forecast was written" in str(refused.value)
    assert league.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == before
    # THE R4 REFUSAL NAMES NONE: a slate every market of which has a row
    _hold(monkeypatch)
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    with pytest.raises(run.SlateAlreadyAnswered) as again:
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert again.value.final_pass_answered == []


def test_the_scheduled_task_records_it_noop_and_names_it(league, monkeypatch):
    """ITEM 7'S RECORD, THE RULING'S WORDS: "it is a SlateAlreadyAnswered
    noop". The scheduled predict (and so the catch-up, which runs it) records
    'noop', says so in plain words naming the slate, and keeps the questions
    in the payload; a run with an open market writes it and says how many it
    left to their final pass."""
    monkeypatch.setenv("GRIDIRON_NOTIFY_FAILURES", "0")
    monkeypatch.setitem(config.SPORT_CURRENT_SEASON, "nfl", 2025)
    _two_market_world(league, monkeypatch)
    week = league.execute("SELECT MIN(week) FROM games WHERE status = 'scheduled'"
                          ).fetchone()[0]
    _hold(monkeypatch, "moneyline")
    run.run_slate(league, "nfl", 2025, week, include_props=False, use_llm=False,
                  final=True)
    out = tasks.run_task(league, "predict:nfl", use_llm=False)
    stored = league.execute("SELECT * FROM task_runs WHERE task = 'predict:nfl'"
                            " ORDER BY id DESC LIMIT 1").fetchone()
    assert out["result"] == stored["result"] == "noop"
    detail = stored["detail"]
    assert f"Week {week}" in detail and "final forecast" in detail, detail
    assert "Nothing was written" in detail
    assert audit.plain_words_violations(language.task_detail_words(detail)) == [], detail
    payload = json.loads(stored["payload_json"])
    assert len(payload["final_pass_answered"]) == 4
    assert payload["refused_slate"] == week and "week" not in payload
    # THE OPEN MARKET: written, and the answered ones counted beside it
    _hold(monkeypatch)
    out = tasks.run_task(league, "predict:nfl", use_llm=False)
    stored = league.execute("SELECT * FROM task_runs WHERE task = 'predict:nfl'"
                            " ORDER BY id DESC LIMIT 1").fetchone()
    assert out["result"] == stored["result"] == "ok"
    payload = json.loads(stored["payload_json"])
    assert payload["written"] == 4 and len(payload["final_pass_answered"]) == 4
    assert "4 questions already have their final forecast" in stored["detail"]
    assert audit.plain_words_violations(
        language.task_detail_words(stored["detail"])) == [], stored["detail"]


def test_a_run_that_could_not_answer_is_not_called_answered(league, monkeypatch):
    """A MARKET WITH NO MODEL FAILS THE RUN BY NAME (item 2), even when the
    only other questions were left to their final pass: a question left to
    answer is not a slate already answered."""
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    asks_only(monkeypatch, "nfl", "spread", "moneyline")
    with pytest.raises(run.MarketNotTrained):
        run.run_week(league, 2025, 7, include_props=False, use_llm=False, final=True)
    with pytest.raises(run.MarketNotTrained) as failed:
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert len(failed.value.result["final_pass_answered"]) == 4
    assert _early_rows(league, 7, "spread") == 0


def test_a_failed_run_keeps_what_it_left_to_the_final_pass(league, monkeypatch):
    """A run failed for want of a model keeps what it recommended (item 5's
    prover), and from question 27 what it left to a final pass, by name."""
    monkeypatch.setenv("GRIDIRON_NOTIFY_FAILURES", "0")
    monkeypatch.setitem(config.SPORT_CURRENT_SEASON, "nfl", 2025)
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    asks_only(monkeypatch, "nfl", "spread", "moneyline")
    week = league.execute("SELECT MIN(week) FROM games WHERE status = 'scheduled'"
                          ).fetchone()[0]
    with pytest.raises(run.MarketNotTrained):
        run.run_slate(league, "nfl", 2025, week, include_props=False,
                      use_llm=False, final=True)
    out = tasks.run_task(league, "predict:nfl", use_llm=False)
    stored = league.execute("SELECT * FROM task_runs WHERE task = 'predict:nfl'"
                            " ORDER BY id DESC LIMIT 1").fetchone()
    assert out["result"] == stored["result"] == "failed"
    assert len(json.loads(stored["payload_json"])["final_pass_answered"]) == 4


def test_the_reasoning_pass_is_not_paid_for_over_its_final_pass(league, monkeypatch):
    """The sixteen of 24 September were reasoning-pass totals: each was a
    paid call for a row that, under the ruling, can never stand."""
    from tests.test_predict import StubClient

    _two_market_world(league, monkeypatch)
    client = StubClient(['{"probability": 0.63, "reasoning": "The home rating is better."}'] * 40)
    _hold(monkeypatch, "moneyline")
    run.run_week(league, 2025, 7, include_props=False, use_llm=True,
                 llm_client=client, final=True)
    asked_for_the_final = len(client.prompts)
    assert asked_for_the_final == 4
    _hold(monkeypatch)
    result = run.run_week(league, 2025, 7, include_props=False, use_llm=True,
                          llm_client=client)
    assert len(client.prompts) - asked_for_the_final == 4, (
        "the reasoning pass was asked a question its final pass had answered")
    names = result["final_pass_answered"]
    assert sum(n.endswith(", llm") for n in names) == 4
    assert sum(n.endswith(", statistical") for n in names) == 4
    assert _early_rows(league, 7, "spread") == 0


def test_the_skip_words_are_plain():
    for n in (1, 16):
        words = language.final_pass_answered_words(n)
        assert audit.plain_words_violations(words) == [], words
        assert "pass" not in words, "the panel calls it the final forecast"
    assert "1 question already has its final forecast" in language.final_pass_answered_words(1)
    refusal = language.final_pass_answered_refusal("nfl", 2025, 7, 16)
    assert "16 questions already have their final forecast" in refusal
    assert "No forecast was written" in refusal


def test_the_question_asked_is_the_one_functions():
    """`bet.given` is made from `bet.KEY` and nothing else."""
    assert bet.given("p").count(" IS ?") == len(bet.KEY)
    for column in bet.KEY:
        assert f"p.{column} IS ?" in bet.given("p")
