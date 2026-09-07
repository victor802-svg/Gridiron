"""The rank and the shortlist (THE_SHORTLIST S1-S2, 2026-09-07): three declared
inputs, an edge that moves nothing until its market has earned a verdict, a
selection that hides nothing, and a rank row that cannot be rewritten."""
from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import audit, config, db, shortlist

WHOLE = json.dumps({"coverage": 1.0})
PARTIAL = json.dumps({"coverage": 0.5})


def _world(tmp_path, games=1):
    conn = db.open_db(tmp_path / "rank.db")
    for i in range(games):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " 'AAA', 'BBB', '2026-09-08T00:00:00Z', 'scheduled', '2026-09-07')",
            (f"g{i}",))
    conn.commit()
    return conn


def _write(conn, *, prob=0.62, factors=WHOLE, market="moneyline", prop=None,
           game="g0", line=None, implied=None, subject="AAA",
           created="2026-09-07T00:00:00Z"):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, prop_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?, 'mlb', ?, ?, ?, ?, ?, ?, 'win', 'statistical', 'final',"
        " 'fs2', ?, 'test')",
        (created, game, market, prop, subject, line, prob, factors))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    if implied is not None:
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line,"
            " implied_prob, kind) VALUES (?, '2026-09-07T01:00:00Z', 'test', ?, ?,"
            " 'open_at_predict')", (pid, line, implied))
    conn.commit()
    return pid


def test_the_three_inputs_are_what_they_say_they_are():
    # confidence is distance from a coin flip, symmetric: a 22% claim about the
    # yes side is a 78% claim about the no side
    assert shortlist.confidence_score(0.78) == shortlist.confidence_score(0.22)
    assert shortlist.confidence_score(0.5) == 0.0
    assert shortlist.confidence_score(1.0) == 1.0
    assert shortlist.confidence_score(None) == 0.0
    # completeness is the frozen payload's own coverage, not a second count
    assert shortlist.completeness_score(WHOLE) == 1.0
    assert shortlist.completeness_score(PARTIAL) == 0.5
    assert shortlist.completeness_score("not json") == 0.0
    assert shortlist.completeness_score(None) == 0.0
    # edge saturates at the declared scale and is ABSENT where there is no line
    assert shortlist.edge_score(0.62, 0.52) == pytest.approx(0.5)
    assert shortlist.edge_score(0.90, 0.50) == 1.0
    assert shortlist.edge_score(0.62, None) is None


def test_an_input_out_of_play_is_not_scored_as_a_zero():
    # the same question, ranked with the edge gated off and gated on
    off = shortlist.combine(0.6, 1.0, 0.0, edge_counted=False)
    on_zero = shortlist.combine(0.6, 1.0, 0.0, edge_counted=True)
    # agreeing with the market COSTS rank once the market's gate is open;
    # before it opens, agreement is not a mark against a question at all
    assert off > on_zero
    assert off == pytest.approx((0.5 * 0.6 + 0.3 * 1.0) / 0.8)
    assert on_zero == pytest.approx(0.5 * 0.6 + 0.3 * 1.0)
    # and a counted edge with nothing to count is refused rather than zeroed
    with pytest.raises(shortlist.RankIsNotAClaim, match="zero disagreement"):
        shortlist.combine(0.6, 1.0, None, edge_counted=True)


def test_a_rank_is_written_after_the_prediction_and_never_rewritten(tmp_path):
    conn = _world(tmp_path)
    pid = _write(conn)
    counts = shortlist.rank_rows(conn, [pid])
    assert counts["ranked"] == 1 and counts["no_line"] == 1
    row = conn.execute("SELECT * FROM prediction_ranks").fetchone()
    assert row["ranker_version"] == config.RANKER_VERSION
    assert row["created_utc"] > "2026-09-07T00:00:00Z"
    assert row["edge"] is None and row["edge_counted"] == 0
    assert row["rank_score"] == pytest.approx(
        shortlist.combine(row["confidence"], row["completeness"], None,
                          edge_counted=False))
    # running again writes nothing twice
    assert shortlist.rank_rows(conn, [pid])["ranked"] == 0
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE prediction_ranks SET rank_score = 1.0 WHERE id = ?",
                     (row["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM prediction_ranks WHERE id = ?", (row["id"],))
    # and a rank stamped at its own prediction's moment is refused
    with pytest.raises(sqlite3.IntegrityError, match="LAW 1"):
        conn.execute(
            "INSERT INTO prediction_ranks (prediction_id, ranker_version, sport,"
            " market_type, rank_score, confidence, completeness, edge_counted,"
            " edge_gate_n, created_utc) VALUES (?, 'r0', 'mlb', 'moneyline', 0.5,"
            " 0.2, 1.0, 0, 0, '2026-09-07T00:00:00Z')", (pid,))


def test_the_edge_is_measured_and_stored_but_moves_nothing_below_the_gate(tmp_path):
    conn = _world(tmp_path)
    pid = _write(conn, prob=0.62, implied=0.42)
    shortlist.rank_rows(conn, [pid])
    row = conn.execute("SELECT * FROM prediction_ranks").fetchone()
    # the disagreement is real, recorded, and carries no weight
    assert row["edge"] == pytest.approx(1.0)
    assert row["edge_counted"] == 0 and row["edge_gate_n"] == 0
    assert row["rank_score"] == pytest.approx(
        shortlist.combine(row["confidence"], row["completeness"], None,
                          edge_counted=False))
    assert audit.edge_weight_faults(conn) == []


def test_the_gate_opening_is_what_turns_the_edge_on(tmp_path, monkeypatch):
    conn = _world(tmp_path)
    monkeypatch.setattr(config, "RANK_EDGE_GATE", 1)
    monkeypatch.setattr(shortlist, "settled_for_gate",
                        lambda *a, **k: 4)   # this market has a record now
    pid = _write(conn, prob=0.62, implied=0.42)
    shortlist.rank_rows(conn, [pid])
    row = conn.execute("SELECT * FROM prediction_ranks").fetchone()
    assert row["edge_counted"] == 1 and row["edge_gate_n"] == 4
    assert row["rank_score"] == pytest.approx(
        shortlist.combine(row["confidence"], row["completeness"], row["edge"],
                          edge_counted=True))
    assert audit.edge_weight_faults(conn) == []


def test_a_rank_that_does_not_follow_from_its_inputs_is_caught(tmp_path):
    conn = _world(tmp_path)
    pid = _write(conn, implied=0.42)
    conn.execute(
        "INSERT INTO prediction_ranks (prediction_id, ranker_version, sport,"
        " market_type, rank_score, confidence, completeness, edge, edge_counted,"
        " edge_gate_n, created_utc) VALUES (?, 'r1', 'mlb', 'moneyline', 0.91,"
        " 0.24, 1.0, 0.9, 1, 3, '2026-09-07T12:00:00Z')", (pid,))
    conn.commit()
    faults = audit.edge_weight_faults(conn)
    assert faults and "below the 100" in faults[0]
    with pytest.raises(audit.LawViolation, match="HAS NOT EARNED"):
        audit.check_the_edge_moves_no_ungated_ordering(conn)


def test_the_shortlist_caps_spreads_and_hides_nothing(tmp_path, monkeypatch):
    conn = _world(tmp_path, games=6)
    monkeypatch.setattr(config, "SHORTLIST_CAPS", dict(config.SHORTLIST_CAPS, mlb=6))
    ids = []
    # one game full of very confident props, five games with one question each
    for i in range(8):
        ids.append(_write(conn, prob=0.95, market="prop", prop="batter_hits",
                          game="g0", line=1.5, subject=f"player {i}"))
    for g in range(1, 6):
        ids.append(_write(conn, prob=0.70, market="moneyline", game=f"g{g}"))
    shortlist.rank_rows(conn, ids)
    picked = shortlist.choose(conn, "mlb", ids)
    assert len(picked["shortlist"]) == 6
    assert len(picked["shortlist"]) + len(picked["rest"]) == len(ids)
    ranks = shortlist.ranks_for(conn, picked["shortlist"])
    games = {r["id"]: r["game_id"] for r in conn.execute(
        "SELECT id, game_id FROM predictions")}
    # the marquee game cannot eat the list
    from collections import Counter
    per_game = Counter(games[pid] for pid in picked["shortlist"])
    assert per_game["g0"] <= config.SHORTLIST_PER_GAME
    # and the list is not all of one kind of question
    kinds = {ranks[pid]["prop_type"] or ranks[pid]["market_type"]
             for pid in picked["shortlist"]}
    assert len(kinds) > 1
    # nothing is dropped: every id is on one list or the other, exactly once
    assert sorted(picked["shortlist"] + picked["rest"]) == sorted(ids)


def test_a_small_slate_is_its_own_shortlist(tmp_path):
    conn = _world(tmp_path, games=2)
    ids = [_write(conn, game="g0"), _write(conn, game="g1")]
    shortlist.rank_rows(conn, ids)
    picked = shortlist.choose(conn, "mlb", ids)
    assert picked["rest"] == [] and sorted(picked["shortlist"]) == sorted(ids)
    # a sport with no cap declared keeps its whole card
    assert config.shortlist_cap("ufc") is None


def test_the_page_leads_with_the_shortlist_and_hides_nothing(tmp_path, monkeypatch):
    from gridiron import views

    conn = _world(tmp_path, games=6)
    monkeypatch.setattr(config, "SHORTLIST_CAPS", dict(config.SHORTLIST_CAPS, mlb=4))
    ids = [_write(conn, prob=0.60 + i * 0.03, game=f"g{i}") for i in range(6)]
    shortlist.rank_rows(conn, ids)
    payload = views.week(conn, "mlb", 2026, 1)
    block = payload["shortlist"]
    assert block["ranked"] is True and block["n"] == 4 and block["rest"] == 2
    assert block["rest_words"] == "the other 2"
    assert "clearest questions" in block["words"]
    # every card is still on the payload, each marked
    assert len(payload["cards"]) == 6
    assert sum(1 for c in payload["cards"] if c["on_shortlist"]) == 4
    # and the ones that lead are the ones the ranker put first
    leading = {c["prediction_id"] for c in payload["cards"] if c["on_shortlist"]}
    assert leading == set(shortlist.choose(conn, "mlb", ids)["shortlist"])
    # each card explains its own place in the reader's terms, without advice
    for card in payload["cards"]:
        assert "coin flip" in card["rank_line"]
    audit.check_the_shortlist_speaks_of_questions(payload)


def test_a_slate_written_before_the_ordering_says_so(tmp_path):
    from gridiron import views

    conn = _world(tmp_path, games=3)
    for i in range(3):
        _write(conn, game=f"g{i}")
    payload = views.week(conn, "mlb", 2026, 1)
    block = payload["shortlist"]
    # no ranks: everything shows, and the sentence does not claim an ordering
    assert block["ranked"] is False and block["rest"] == 0
    assert block["rest_words"] is None
    assert "written before the ordering" in block["words"]
    assert all(c["on_shortlist"] for c in payload["cards"])
    assert all(c["rank_line"] is None for c in payload["cards"])


def test_the_shortlist_never_speaks_like_a_tip_sheet():
    from gridiron import language

    for words in (language.shortlist_line(20, 68, "day"),
                  language.shortlist_line(9, 9, "card"),
                  language.shortlist_line(9, 9, "card", ranked=False),
                  language.shortlist_rest_line(48),
                  language.shortlist_rank_line(
                      {"confidence": 0.5, "completeness": 1.0, "edge": 0.4,
                       "edge_counted": 0, "edge_gate_n": 12, "gate": 100})):
        assert audit.advice_word_faults(words) == [], words
        assert audit.plain_words_violations(words) == [], words
    planted = {"shortlist": {"words": "today's best bets"}, "cards": []}
    assert audit.slate_advice_faults(planted)
    with pytest.raises(audit.LawViolation, match="recommending rather than"):
        audit.check_the_shortlist_speaks_of_questions(planted)
