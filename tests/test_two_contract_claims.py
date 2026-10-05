"""A CLAIM PRICED ACROSS TWO CONTRACTS IS IN NO PRICE COMPARISON (operator
ruling A.2 of 2026-10-05, docs/briefs/2026-10-05-rulings.md).

    "Void the 54 recommendations by append-only rows (reason: 'priced across
    two contracts, Q36'). The 269 claims stay in the blind record (model
    against outcome at its own line) and are excluded by a dated rule from
    every price comparison: at-the-line record, closing line, edge figures,
    combos. List every released number that moves."

The claims are the stored claims whose line is not the line their contract
sells (`at_the_line.priced_across_two_contracts`): an away contract read at
-s before Q36.1 (275 on the record, MLB 139, NFL 96, NCAAF 40). The READ
RULE: the at-the-line door leaves each out (`at_the_line.on_one_contract`),
taking back the claim and not the bet; the measurement door leaves out every
recommendation priced from one (`recommend.priced_on_one_contract`, in
`counted_once`), never one of a pair, and names it beside the closing line;
the combo engine proposes no leg on one; the writer writes no
recommendation from one; each builder's guard asks the stored claims its rows
name; the recounts work the rule out again in Python; and the gate's step 2
asks every builder and each slate's combos. THE VOIDS: `tools/
void_two_contract_recommendations.py` writes the 54 named, by rule, once, and
lists recs 114 and 115 for the operator's word.
"""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

from gridiron import audit, calibration, db, language, recount, shortlist, views
from gridiron.market import at_the_line, combos, recommend
from gridiron.priced import coverage

REPO = Path(__file__).resolve().parents[1]
DIST = json.dumps({"coverage": 1.0, "margin_distribution": {
    "quantity": "home_margin", "family": "normal", "mean": -2.0, "sd": 13.5,
    "declared": "2026-08-31T00:00:00Z", "written_blind": True}})

#: name -> (game, home, away, subject, asked, side, number; the contract its
#: look was priced off -- ticker, stored line, side, bid, ask; the claim's
#: stored line, its number and price; the score; the recommendation's side;
#: the later read that closed it; the open of the home contract at the
#: claim's line). "across" is rec 114's shape as the released writer wrote
#: it: a claim at -2.5 off "Pittsburgh wins by over 2.5", which sells +2.5.
QUESTIONS = {
    "across": ("g_pit_cle", "CLE", "PIT", "CLE", 0.5, "not_cover", 0.561059,
               ("tPIT3", 2.5, "away", 0.515, 0.535), -2.5, 0.3834, 0.475,
               (20, 24), "no", (0.55, 0.57), ("tCLE3", -2.5, 0.30, 0.32)),
    "one": ("g_sea_was", "WAS", "SEA", "WAS", -3.5, "cover", 0.6,
            ("tWAS4", -3.5, "home", 0.49, 0.51), -3.5, 0.6, 0.5, (27, 20), "yes",
            (0.53, 0.55), ("tWAS4", -3.5, 0.40, 0.42)),
    "across2": ("g_kc_lv", "LV", "KC", "LV", 1.5, "not_cover", 0.58,
                ("tKC4", 3.5, "away", 0.52, 0.54), -3.5, 0.33, 0.47, (17, 24),
                "no", (0.55, 0.57), ("tLV4", -3.5, 0.25, 0.27)),
}


def _read(conn, game, ticker, line, side, bid, ask, at, kind):
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, volume, fetched_utc,"
        " read_kind) VALUES ('kalshi', ?, 'e', 'nfl', ?, 'spread', 'home_margin',"
        " ?, ?, ?, ?, 900, ?, ?)", (ticker, game, line, side, bid, ask, at, kind))
    return conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]


def _plus(stamp: str, seconds: int) -> str:
    from datetime import timedelta

    return (db.instant(stamp) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _question(conn, name, *, game=None, rec=True, claim_at="2026-09-28T15:00:45Z",
              written="2026-09-28T15:00:00Z", kickoff="2026-09-29T17:00:00Z"):
    """One finished question of `QUESTIONS`, priced, settled, and -- when
    `rec` -- recommended in the closing line's window and closed on a later
    read of its own contract, measured. Returns its ids. The open is read ten
    seconds after the forecast (LAW 1: no quote before a prediction), the
    look a second before its claim."""
    (gid, home, away, subject, asked, side, prob, quote, claim_line, claim_prob,
     implied, score, rec_side, close, opening) = QUESTIONS[name]
    gid = game or gid
    if conn.execute("SELECT 1 FROM games WHERE id = ?", (gid,)).fetchone() is None:
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES (?, 'nfl', 2026, 3, 'REG', ?, ?, ?, 'final', '2026-09-29',"
            " ?, ?)", (gid, home, away, kickoff, *score))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES (?, 'nfl', ?,"
        " 'spread', ?, ?, ?, ?, 'statistical', 'final', 'fs2', ?, 'test')",
        (written, gid, subject, asked, prob, side, DIST))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    o_ticker, o_line, o_bid, o_ask = opening
    _read(conn, gid, o_ticker, o_line, "home", o_bid, o_ask, _plus(written, 10),
          "open")
    ticker, line, yes, bid, ask = quote
    priced_by = _read(conn, gid, ticker, line, yes, bid, ask, _plus(claim_at, -1),
                      "near_start")
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'nfl', ?, 'spread', 'home_margin', ?, 'home',"
        " 'rung_differs_margin', -2.0, 13.5, ?, ?, ?, 'mid', ?)",
        (pid, priced_by, gid, claim_line, claim_prob, round((bid + ask) / 2, 4),
         implied, claim_at))
    claim = conn.execute("SELECT MAX(id) FROM at_the_line_claims").fetchone()[0]
    out = {"pid": pid, "claim": claim, "game": gid, "quote": priced_by}
    if rec:
        closed_by = _read(conn, gid, ticker, line, yes, *close,
                          "2026-09-29T16:30:00Z", "near_start")
        mid = (close[0] + close[1]) / 2
        close_implied = round(mid if yes == "home" else 1 - mid, 4)
        clv = round(((close_implied - implied) if rec_side == "yes"
                     else (implied - close_implied)) * 100, 2)
        conn.execute(
            "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
            " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
            " created_utc, close_price, clv_cents, closed_utc) VALUES"
            " (?, 'nfl', ?, 'spread', ?, ?, ?, 5.0, 'flat', 1.0, 0,"
            " '2026-09-28T15:01:00Z', ?, ?, '2026-09-29T17:05:00Z')",
            (pid, gid, rec_side, claim_prob, implied, close_implied, clv))
        out["rec"] = conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
        conn.execute(
            "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
            " pricing_quote_id, close_quote_id, close_price, clv_cents,"
            " minutes_before_start, restated, reason) VALUES (?,"
            " '2026-09-29T17:05:00Z', ?, ?, ?, ?, 30.0, 0, 'the last near-start"
            " read of its own contract before the start')",
            (out["rec"], priced_by, closed_by, close_implied, clv))
    return out


@pytest.fixture
def world(tmp_path):
    conn = db.open_db(tmp_path / "q36ii.db")
    made = {name: _question(conn, name) for name in QUESTIONS}
    conn.commit()
    at_the_line.resolve_claims(conn)
    conn.commit()
    yield conn, made
    conn.close()


def _cell(rows, market="spread", predictor="statistical"):
    return next(r for r in rows if r["market"] == market and r["predictor"] == predictor)


# --- the rule, in its two spellings -------------------------------------------------

def test_the_rule_is_the_one_place_in_sql_and_in_python(world):
    conn, made = world
    every = [r[0] for r in conn.execute("SELECT id FROM at_the_line_claims")]
    by_python = set(at_the_line.across_two_contracts_among(conn, every))
    by_sql = {r[0] for r in conn.execute(
        "SELECT c.id FROM at_the_line_claims c WHERE 1"
        + at_the_line.on_one_contract("c"))}
    assert by_python == {made["across"]["claim"], made["across2"]["claim"]}
    assert by_sql == set(every) - by_python
    # A WINNER MARKET'S CLAIM AND CONTRACT BOTH HAVE NO LINE: one contract.
    assert not at_the_line.priced_across_two_contracts(
        None, {"line": None, "yes_side": "home"})
    assert at_the_line.priced_across_two_contracts(
        None, {"line": 2.5, "yes_side": "away"})
    # A CONTRACT THAT CANNOT BE FOUND IS NOT ACROSS, in either spelling.
    assert at_the_line.across_two_contracts_among(conn, [999999]) == []
    with pytest.raises(ValueError):
        at_the_line.on_one_contract("c; DROP")


def test_the_rule_is_dated_and_names_its_release():
    assert at_the_line.ON_ONE_CONTRACT_RULED == "2026-10-05"
    assert db.instant(at_the_line.ONE_CONTRACT_FROM)
    assert at_the_line.ONE_CONTRACT_FROM == "2026-09-30T18:44:00Z"


# --- the at-the-line record ---------------------------------------------------------

def test_the_at_the_line_record_leaves_every_claim_across_two_contracts_out(world):
    conn, made = world
    sc = calibration.at_the_line_scorecard(conn, sport="nfl")
    curve = _cell(sc["categories"])
    ledger = _cell(sc["paper"])
    cover = _cell(sc["coverage"])
    # THE CURVE, ITS OUTLOOK, THE LEDGER: "one" alone, recounted so
    assert (curve["n"], curve["recounted"], curve["outlook"]["resolved"]) == (1, 1, 1)
    assert (ledger["n"], ledger["recounted"]) == (1, 1)
    # THE EDGE FIGURE
    edge = calibration.at_the_line_edge(conn, sport="nfl", market="spread",
                                        predictor="statistical")
    assert (edge["n"], edge["recounted"]) == (1, 1)
    # THE COVERAGE LINE: read for one, two read only across two contracts
    assert (cover["n"], cover["with_a_claim"]) == (3, 1)
    assert cover["across_two_contracts"] == cover["across_recounted"] == 2
    assert cover["holes"][0] == {"reason": at_the_line.ACROSS_TWO_CONTRACTS_HOLE, "n": 2}
    assert sum(h["n"] for h in cover["holes"]) == 2
    assert cover["words"] == (
        "point spread, statistical: the venue's line could be read for 1 of 3 "
        "questions it answered (33%); 2 more were read only across two contracts "
        "before the fix of 30 September, and no comparison with a price counts "
        "them")
    assert audit.plain_words_violations(cover["words"]) == []
    # THE VENUE'S DRIFT PAIR: "one" alone
    venue = [m for m in views.drift_report(conn, "nfl")["venue_markets"]
             if m["market_type"] == "spread" and m["predictor"] == "statistical"]
    assert venue and venue[0]["n"] == 1 and venue[0]["claims_read"] == 1
    # THE SETTLED COUNT BESIDE A CARD, the curve's own
    beside = views._at_the_line(conn, "nfl", [made["across"]["pid"]], {})
    assert beside[made["across"]["pid"]]["n"] == 1


def _now(module):
    """THE MODULE AS IT IS NOW, never as this file imported it: a blind
    window earlier in the session drops the market package from
    `sys.modules`, and a patch on the stale copy is a patch on nothing
    (test_voids.py and test_near_start_reads.py say so; these two passed
    alone and failed in the suite the first time, 2026-10-05)."""
    return importlib.import_module(module.__name__)


def test_the_released_door_counts_them_and_the_guards_refuse_it_by_name(world, monkeypatch):
    conn, made = world
    door = _now(at_the_line)
    monkeypatch.setattr(door, "on_one_contract", lambda claim="c": "")
    assert len(door.standing_claims(conn, sport="nfl", market="spread",
                                    predictor="statistical")) == 3
    # THE RECOUNT, MADE WITHOUT THE DOOR, STILL LEAVES THEM OUT
    assert recount.at_the_line(conn, sport="nfl", market="spread",
                               predictor="statistical", event_tier=None)["claims"] == 1
    for build in (lambda: calibration.at_the_line_scorecard(conn, sport="nfl"),
                  lambda: calibration.at_the_line_edge(
                      conn, sport="nfl", market="spread", predictor="statistical"),
                  lambda: views.drift_report(conn, "nfl"),
                  lambda: views._at_the_line(conn, "nfl", [made["one"]["pid"]], {}),
                  lambda: door.coverage(conn, sport="nfl", predictor="statistical")):
        with pytest.raises(calibration.ComparedAcrossTwoContracts,
                           match=str(made["across"]["claim"])):
            build()
    faults = audit.two_contract_comparison_faults(conn)
    assert any("the at-the-line record" in f for f in faults)
    with pytest.raises(audit.LawViolation, match="ACROSS TWO CONTRACTS"):
        audit.check_no_price_comparison_holds_a_claim_across_two_contracts(conn)


def test_a_claim_left_out_takes_back_the_claim_not_the_bet(tmp_path):
    """A bet read twice -- an earlier look priced off a home contract at the
    line it sells, a later look off an away contract read at -s -- stands on
    the earlier claim, as a voided forecast's bet stands on another's."""
    conn = db.open_db(tmp_path / "bet.db")
    first = _question(conn, "one", rec=False, claim_at="2026-09-28T15:30:00Z")
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
        " VALUES ('kalshi', 'tSEA4', 'e', 'nfl', 'g_sea_was', 'spread',"
        " 'home_margin', 3.5, 'away', 0.52, 0.54, '2026-09-28T16:00:00Z')")
    quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'nfl', 'g_sea_was', 'spread', 'home_margin',"
        " -3.5, 'home', 'rung_differs_margin', -2.0, 13.5, 0.6, 0.53, 0.47, 'mid',"
        " '2026-09-28T16:00:01Z')", (first["pid"], quote))
    later = conn.execute("SELECT MAX(id) FROM at_the_line_claims").fetchone()[0]
    conn.commit()
    at_the_line.resolve_claims(conn)
    conn.commit()
    standing = at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                           predictor="statistical")
    assert [c["id"] for c in standing] == [first["claim"]]
    chosen = recount.standing_claims_of(recount.claims(
        conn, sport="nfl", market="spread", predictor="statistical", event_tier=None))
    assert [c["id"] for c in chosen.values()] == [first["claim"]]
    assert at_the_line.across_two_contracts_among(conn, [later]) == [later]
    cover = _cell(calibration.at_the_line_scorecard(conn, sport="nfl")["coverage"])
    assert (cover["with_a_claim"], cover["across_two_contracts"]) == (1, 0)
    conn.close()


def test_a_coverage_line_misstating_its_across_count_is_refused(world):
    conn, _made = world
    sc = calibration.at_the_line_scorecard(conn, sport="nfl")
    calibration.assert_no_pooled_claims(sc)
    cover = _cell(sc["coverage"])
    for wrong in (None, 1, 3, "2"):
        cover["across_two_contracts"] = wrong
        with pytest.raises(calibration.ComparedAcrossTwoContracts):
            calibration.assert_no_pooled_claims(sc)


# --- the closing line ---------------------------------------------------------------

def test_the_closing_line_leaves_out_and_names_a_recommendation_priced_across(world):
    conn, made = world
    report = calibration.clv_report(conn, sport="nfl")
    block = next(b for b in report["forecasters"] if b["predictor"] == "statistical")
    assert block["n"] == 1 and block["window_line"]["n"] == 1
    assert block["across_two_contracts"] == {"n": 2, "measured": 2, "closed": 2,
                                             "awaiting_close": 0}
    assert block["across_line"] == {
        "label": "Priced across two contracts, statistical", "n": 2,
        "words": ("2 recommendations were priced across two contracts before the "
                  "fix of 30 September, because the venue's contract naming the "
                  "visiting side was read at the wrong sign, so the model's number "
                  "was about one contract and the price about another, and they "
                  "are never counted")}
    assert audit.plain_words_violations(block["across_line"]["words"]) == []
    assert [e["n"] for e in report["markets"] if e["predictor"] == "statistical"] == [1]
    assert audit.withdrawn_counted_faults(conn, report) == []
    assert audit.pair_counted_faults(conn, report) == []
    listed = recommend.priced_across_two_contracts(conn, sport="nfl",
                                                   predictor="statistical")
    assert [r["id"] for r in listed] == [made["across"]["rec"], made["across2"]["rec"]]
    assert recommend.priced_across_two_contracts(conn, sport="nfl", predictor="llm") == []
    # THE KILL CRITERION READS THE SAME LINE
    assert coverage.stopped(conn, "nfl") == {}


def test_the_measurement_door_and_its_guard(world, monkeypatch):
    conn, made = world
    counted = {r[0] for r in conn.execute(
        "SELECT r.id FROM recommendations r WHERE 1"
        + recommend.counted_once(conn, predictor="statistical"))}
    assert counted == {made["one"]["rec"]}
    assert recommend.pricing_claim_ids(conn, [made["across"]["rec"]]) == {
        made["across"]["rec"]: made["across"]["claim"]}
    with pytest.raises(calibration.ComparedAcrossTwoContracts,
                       match=str(made["across2"]["rec"])):
        calibration.refuse_recommendations_across_two_contracts(
            conn, [made["across2"]["rec"]], what="a test")
    # THE RULE PUT BACK: the builder's guard refuses the line by name...
    monkeypatch.setattr(_now(recommend), "_priced_on_one_contract", lambda alias: "")
    with pytest.raises(calibration.ComparedAcrossTwoContracts):
        calibration.clv_report(conn, sport="nfl")
    # ...and with the guard silenced, the recount names the rows
    monkeypatch.setattr(calibration, "refuse_recommendations_across_two_contracts",
                        lambda *a, **k: None)
    faults = audit.pair_counted_faults(conn, calibration.clv_report(conn, sport="nfl"))
    assert any(f"{made['across']['rec']}, {made['across2']['rec']}" in f for f in faults)


def test_a_recommendation_priced_across_is_never_the_earlier_of_a_pair(tmp_path):
    """Two passes of ONE question on one side: the morning's priced across two
    contracts, the final pass's off one contract. The later counts, alone --
    as NFL 73 counts after the withdrawn 62."""
    conn = db.open_db(tmp_path / "pair.db")
    conn.execute("DROP TRIGGER recommendation_one_per_game_and_market")
    early = _question(conn, "across")
    conn.execute("UPDATE predictions SET pass_kind = 'early' WHERE id = ?",
                 (early["pid"],))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-28T16:00:00Z', 'nfl', 'g_pit_cle', 'spread', 'CLE', 0.5, 0.56,"
        " 'not_cover', 'statistical', 'final', 'fs2', ?, 'test')", (DIST,))
    late_pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    quote = _read(conn, "g_pit_cle", "tCLE3", -2.5, "home", 0.50, 0.52,
                  "2026-09-28T16:00:30Z", "near_start")
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'nfl', 'g_pit_cle', 'spread', 'home_margin',"
        " -2.5, 'home', 'rung_differs_margin', -2.0, 13.5, 0.38, 0.51, 0.51,"
        " 'mid', '2026-09-28T16:00:31Z')", (late_pid, quote))
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market, side,"
        " fair_value, price, edge_cents, size_kind, size_units, gate_n, created_utc)"
        " VALUES (?, 'nfl', 'g_pit_cle', 'spread', 'no', 0.38, 0.51, 5.0, 'flat',"
        " 1.0, 0, '2026-09-28T16:01:00Z')", (late_pid,))
    late = conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
    conn.commit()
    db.init(conn)
    conn.commit()
    counted = {r[0] for r in conn.execute(
        "SELECT r.id FROM recommendations r WHERE 1"
        + recommend.counted_once(conn, predictor="statistical"))}
    assert counted == {late}
    assert recommend.not_counted_once(conn, sport="nfl", predictor="statistical") == []
    report = calibration.clv_report(conn, sport="nfl")
    assert audit.pair_counted_faults(conn, report) == []
    assert audit.withdrawn_counted_faults(conn, report) == []
    conn.close()


def test_the_voids_move_which_line_names_them_and_no_count(world):
    conn, made = world
    before = calibration.clv_report(conn, sport="nfl")
    conn.execute("INSERT INTO recommendation_voids (recommendation_id, voided_utc,"
                 " reason) VALUES (?, '2026-10-05T16:00:00Z', ?)",
                 (made["across"]["rec"], recommend.TWO_CONTRACTS_VOID_REASON))
    conn.commit()
    after = calibration.clv_report(conn, sport="nfl")
    b, a = (next(x for x in r["forecasters"] if x["predictor"] == "statistical")
            for r in (before, after))
    assert (b["n"], a["n"]) == (1, 1)
    assert (b["across_two_contracts"]["n"], a["across_two_contracts"]["n"]) == (2, 1)
    assert (b["withdrawn"], a["withdrawn"]) == (0, 1)
    # THE RULED REASON, SAID IN PLAIN WORDS
    assert a["withdrawn_line"]["words"] == (
        "1 recommendation withdrawn and never counted: "
        + language.ACROSS_TWO_CONTRACTS_REASON_WORDS)
    assert "Q36" not in a["withdrawn_line"]["words"]
    assert audit.plain_words_violations(a["withdrawn_line"]["words"]) == []
    assert audit.withdrawn_counted_faults(conn, after) == []
    assert audit.pair_counted_faults(conn, after) == []


def test_the_empty_bar_counts_no_day_on_a_claim_across_two_contracts(tmp_path):
    spec = importlib.util.spec_from_file_location("empty_bar_q36ii",
                                                  REPO / "tools" / "empty_bar.py")
    empty_bar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(empty_bar)
    conn = db.open_db(tmp_path / "bar.db")
    _question(conn, "across")
    conn.commit()
    block = next(b for b in empty_bar.spans(conn, "nfl")["forecasters"]
                 if b["predictor"] == "statistical")
    assert sum(s["days_the_bar_could_be_tested"] for s in block["spans"]) == 0
    _question(conn, "one")
    conn.commit()
    block = next(b for b in empty_bar.spans(conn, "nfl")["forecasters"]
                 if b["predictor"] == "statistical")
    assert sum(s["days_the_bar_could_be_tested"] for s in block["spans"]) == 1
    assert sum(s["days_nothing_cleared"] for s in block["spans"]) == 0
    conn.close()


# --- the writer and the combo engine ------------------------------------------------

def _entry(pid, game, side, edge, *, across):
    return {"prediction_id": pid, "game_id": game, "sport": "nfl", "side": side,
            "fair_value": 0.6, "price": 0.5, "edge_cents": edge, "market": "spread",
            "priced_across_two_contracts": across}


def test_the_engine_proposes_no_leg_priced_across_two_contracts():
    entries = [_entry(1, "a", "no", 9.0, across=True),
               _entry(2, "b", "yes", 4.0, across=False),
               _entry(3, "c", "yes", 3.0, across=False)]
    legs = [leg for p in combos.propose(entries, sport="nfl") for leg in p["leg_ids"]]
    assert sorted(legs) == [2, 3]
    assert combos.propose(entries[:2], sport="nfl") == []


def test_the_writer_writes_no_recommendation_from_a_claim_across(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market, **_: {
        "priceable": True, "market": market, "why": "covered, in this test"})
    conn = db.open_db(tmp_path / "writer.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g114', 'nfl', 2026, 4, 'REG',"
        " 'CLE', 'PIT', '2099-10-02T00:15:00Z', 'scheduled', '2026-10-01')")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-30T18:00:00Z', 'nfl', 'g114', 'spread', 'CLE', 0.5, 0.561059,"
        " 'not_cover', 'statistical', 'final', 'fs2', ?, 'test')", (DIST,))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    quote = _read(conn, "g114", "tPIT3", 2.5, "away", 0.515, 0.535,
                  "2026-09-30T18:04:59Z", "near_start")
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'nfl', 'g114', 'spread', 'home_margin', -2.5,"
        " 'home', 'rung_differs_margin', -2.0, 13.5, 0.3834, 0.525, 0.475, 'mid',"
        " '2026-09-30T18:05:00Z')", (pid, quote))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    conn.commit()
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["side"] == "no" and entry["priced_across_two_contracts"] is True
    got = recommend.record_for(conn, [pid])
    assert (got["recommended"], got["across_two_contracts"]) == (0, 1)
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 0
    conn.close()


# --- the gate -----------------------------------------------------------------------

def test_the_gate_makes_the_call():
    tree = ast.parse((REPO / "tools" / "verify.py").read_text(encoding="utf-8"))
    step = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "step_2_guards")
    assert any(isinstance(n, ast.Attribute) and n.attr ==
               "check_no_price_comparison_holds_a_claim_across_two_contracts"
               for n in ast.walk(step))


def test_the_gate_passes_the_record_shape_and_names_a_late_claim(world):
    conn, made = world
    assert audit.two_contract_comparison_faults(conn) == []
    _question(conn, "across", game="g_late", rec=False,
              written="2026-10-01T15:00:00Z", claim_at="2026-10-01T15:00:45Z",
              kickoff="2026-10-02T17:00:00Z")
    conn.commit()
    late = conn.execute("SELECT MAX(id) FROM at_the_line_claims").fetchone()[0]
    faults = audit.two_contract_comparison_faults(conn)
    assert any(f"[{late}]" in f and "written at or after Q36.1's release" in f
               for f in faults)


def test_the_gate_names_a_combo_leg_priced_across(world):
    conn, made = world
    payload = {"sport": "nfl", "today": {"combos": {"cards": [
        {"legs": [{"prediction_id": made["one"]["pid"]}]}]}}}
    assert audit.two_contract_comparison_faults(conn, [payload]) == []
    payload["today"]["combos"]["cards"][0]["legs"].append(
        {"prediction_id": made["across"]["pid"]})
    faults = audit.two_contract_comparison_faults(conn, [payload])
    assert any(f"question {made['across']['pid']}" in f for f in faults)


# --- the words: every sentence of the rule says when, and the record bears it out ----

#: THE RULE'S SENTENCES AS FIRST BUILT (2026-10-05), each saying "before 30
#: September" of claims of which the record holds six written that day.
FIRST_BUILT_REASON = ("priced across two contracts before 30 September: the venue's "
                      "contract naming the visiting side was read at the wrong sign, "
                      "so the model's number was about one contract and the price "
                      "about another")
FIRST_BUILT_HOLE = ("its only claims were priced across two contracts before 30 "
                    "September, and are left out of every comparison with a price")


def test_every_sentence_of_the_rule_is_true_of_recs_114_and_115(world, monkeypatch):
    """THE PROVER'S (2026-10-05). Run 8464 wrote six claims across two
    contracts at 18:00-18:05Z ON 30 September, and recs 114 and 115 were
    priced from two of them -- the two the closing line's own row names once
    the 54 are voided. Each sentence of the rule says "before the fix of 30
    September" (Q36.1, 18:44Z that day), which the record bears out; as first
    built each said "before 30 September", which it does not, and the gate's
    check names each."""
    conn, _made = world
    _question(conn, "across", game="g_week4", rec=False,
              written="2026-09-30T18:00:00Z", claim_at="2026-09-30T18:05:00Z",
              kickoff="2026-10-02T00:15:00Z")
    conn.commit()
    assert audit.two_contract_words_faults(conn) == []
    assert audit.two_contract_comparison_faults(conn) == []
    sentences = audit.two_contract_sentences()
    assert len(sentences) == 5
    for what, words in sentences:
        assert language.ACROSS_TWO_CONTRACTS_WHEN in words, what
        assert "before 30 September" not in words, what
        if what != "the builders' refusal":      # an API's 500, never drawn
            assert audit.plain_words_violations(words) == [], what
    # AS FIRST BUILT: every drawn sentence named, with the claim that makes
    # it false
    monkeypatch.setattr(_now(language), "ACROSS_TWO_CONTRACTS_REASON_WORDS",
                        FIRST_BUILT_REASON)
    monkeypatch.setattr(_now(language), "ACROSS_TWO_CONTRACTS_WHEN",
                        "before 30 September")
    monkeypatch.setattr(_now(at_the_line), "ACROSS_TWO_CONTRACTS_HOLE",
                        FIRST_BUILT_HOLE)
    faults = audit.two_contract_words_faults(conn)
    assert {f.split(" says ")[0] for f in faults} == {
        "the coverage line's hole", "the coverage line", "a withdrawal's reason",
        "the closing line's row"}
    assert all("2026-09-30T18:05:00Z" in f for f in faults)
    with pytest.raises(audit.LawViolation, match="before 30 September"):
        audit.check_no_price_comparison_holds_a_claim_across_two_contracts(conn)
    # A SENTENCE SAYING NO DATE, OR NAMING THE FIX ON ANOTHER DAY, IS NAMED TOO
    monkeypatch.setattr(_now(at_the_line), "ACROSS_TWO_CONTRACTS_HOLE",
                        "its only claims were priced across two contracts")
    monkeypatch.setattr(_now(language), "ACROSS_TWO_CONTRACTS_WHEN",
                        "before the fix of 1 October")
    faults = audit.two_contract_words_faults(conn)
    assert any(f.startswith("the coverage line's hole does not say when") for f in faults)
    assert any(f.startswith("the coverage line names the fix of 1 October")
               for f in faults)


# --- the void tool ------------------------------------------------------------------

def _tool():
    path = REPO / "tools" / "void_two_contract_recommendations.py"
    spec = importlib.util.spec_from_file_location("void_two_contracts_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: THE 54 question 36 names, in its own words' order.
QUESTION_36 = ([6, 8, 11, 14, 16, 20, 25, 30, 32, 34] + list(range(38, 43))
               + [44, 48, 50, 51, 53, 54, 55, 57, 59, 60, 79, 84, 85, 86, 87]
               + list(range(93, 99)) + [100, 106, 107, 108, 109]
               + [62, 63, 66, 68, 69, 70, 73, 75, 77, 78] + [88, 90, 91])


def test_the_tools_ruled_set_is_question_36s_54_and_its_reason_the_operators():
    tool = _tool()
    assert len(QUESTION_36) == 54 == len(set(QUESTION_36))
    assert sorted(tool.RULED) == sorted(QUESTION_36)
    assert tool.ON_THE_OPERATORS_WORD == ()
    assert tool.REASON == recommend.TWO_CONTRACTS_VOID_REASON == (
        "priced across two contracts, Q36")
    assert len(tool.REASON.strip()) >= 10


def _record_shape(path):
    """Recommendations numbered 1-117 as the record numbers them: the 54 and
    114, 115 priced from a claim across two contracts, 62, 63 and 66 already
    withdrawn under ruling 1, the rest priced off one contract."""
    conn = db.open_db(path)
    across = set(QUESTION_36) | {114, 115}
    for n in range(1, 118):
        name = "across" if n in across else "one"
        made = _question(conn, name, game=f"g{n}")
        assert made["rec"] == n
    for n in (62, 63, 66):
        conn.execute("INSERT INTO recommendation_voids (recommendation_id,"
                     " voided_utc, reason) VALUES (?, '2026-09-24T06:00:00Z',"
                     " 'published from an unvalidated fit before the hold; fit"
                     " subsequently failed holdout')", (n,))
    conn.commit()
    conn.close()


def test_the_tool_writes_the_54_once_lists_114_and_115_and_leaves_the_withdrawn(
        tmp_path, capsys):
    path = tmp_path / "record.db"
    _record_shape(path)
    tool = _tool()
    assert tool.main(["--database", str(path)]) == 0
    out = capsys.readouterr().out
    assert "56 recommendation(s) were priced from a claim across two contracts" in out
    assert "--write would void 51" in out
    assert "waiting for the operator's word, NOT written: [114, 115]" in out
    assert "left as they are: [62, 63, 66]" in out
    conn = db.read_only(path, "the test's own world")
    assert conn.execute("SELECT COUNT(*) FROM recommendation_voids").fetchone()[0] == 3
    conn.close()
    assert tool.main(["--database", str(path), "--write"]) == 0
    assert "wrote 51 void(s)" in capsys.readouterr().out
    assert tool.main(["--database", str(path), "--write"]) == 0
    again = capsys.readouterr().out
    assert "wrote 0 void(s)" in again and "51 already voided by this ruling" in again
    conn = db.read_only(path, "the test's own world")
    voids = {r[0]: r[1] for r in conn.execute(
        "SELECT recommendation_id, reason FROM recommendation_voids")}
    assert set(voids) == set(QUESTION_36)
    assert {voids[n] for n in set(QUESTION_36) - {62, 63, 66}} == {tool.REASON}
    assert 114 not in voids and 115 not in voids
    # NOTHING COUNTED MOVED: the read rule had already left them out
    report = calibration.clv_report(conn, sport="nfl")
    block = next(b for b in report["forecasters"] if b["predictor"] == "statistical")
    assert block["n"] == 117 - 56
    assert block["across_two_contracts"]["n"] == 2
    assert block["withdrawn"] == 54
    assert audit.withdrawn_counted_faults(conn, report) == []
    assert audit.pair_counted_faults(conn, report) == []
    conn.close()


def test_the_tool_refuses_a_ruled_set_the_rule_does_not_select(tmp_path, capsys,
                                                               monkeypatch):
    conn = db.open_db(tmp_path / "small.db")
    across = _question(conn, "across")["rec"]
    one = _question(conn, "one")["rec"]
    conn.commit()
    conn.close()
    path = tmp_path / "small.db"
    tool = _tool()
    with pytest.raises(SystemExit) as refused:
        tool.main(["--database", str(path), "--write"])
    assert refused.value.code == 2
    assert "which the rule does not select" in capsys.readouterr().out
    monkeypatch.setattr(tool, "RULED", (across, one))
    with pytest.raises(SystemExit):
        tool.main(["--database", str(path), "--write"])
    assert f"[{one}]" in capsys.readouterr().out
    # AND ITS WRITE ASKS AGAIN, ROW BY ROW
    monkeypatch.setattr(tool, "RULED", (across,))
    conn = db.connect(path)
    with pytest.raises(tool.OutsideTheRuledSet, match=str(one)):
        tool.write_voids(conn, [across, one])
    assert conn.execute("SELECT COUNT(*) FROM recommendation_voids").fetchone()[0] == 0
    conn.close()
    # THE RECORD ONLY WITH --live, --live ONLY ON THE RECORD, NEVER A BACKTEST
    monkeypatch.setattr(db, "is_the_live_record_file", lambda p: True)
    with pytest.raises(SystemExit) as refused:
        tool.main(["--database", str(path), "--write"])
    assert refused.value.code == 2 and "--live" in capsys.readouterr().out
    monkeypatch.setattr(db, "is_the_live_record_file", lambda p: False)
    with pytest.raises(SystemExit):
        tool.main(["--database", str(path), "--write", "--live"])
    conn = db.connect(path)
    db.set_meta(conn, "kind", "backtest")
    conn.close()
    with pytest.raises(SystemExit):
        tool.main(["--database", str(path), "--write"])
    assert "backtest" in capsys.readouterr().out
