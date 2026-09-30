"""At-the-line claims (AT_THE_LINE E4, 2026-09-06): the frozen distribution
read at the venue's own line, after the quote exists, on one fixed proposition;
settled like a prediction and never edited afterwards."""
from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import db, tasks
from gridiron.market import at_the_line

DIST = {"quantity": "home_margin", "family": "normal", "mean": 3.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}


def _finish(conn, home_score, away_score, game="2026_01_NE_SEA"):
    """The game ends, AFTER the claim was written.

    THE ORDER IS THE REAL ONE from 2026-09-07: `evaluate` refuses a game
    already under way, because a pre-game probability against an in-play price
    is not a disagreement. A fixture that starts a game final writes no claim
    at all, so these tests build the claim first and then let the game finish.
    """
    conn.execute(
        "UPDATE games SET status = 'final', home_score = ?, away_score = ?"
        " WHERE id = ?", (home_score, away_score, game))
    conn.commit()


# THE FIXTURE'S CLOCK IS RELATIVE, NOT A DATE (2026-09-10).
#
# These fixtures hard-coded `2026-09-10T00:20:00Z` as the kickoff. The claim
# writer refuses a game already under way, so the moment the wall clock passed
# that instant every claim was refused and the tests failed on code nobody had
# touched. A test that passes only before a certain date is a test with an
# expiry.
#
# TWO DAYS OUT, which is comfortably clear of any window the pipeline cares
# about: the near-start pass looks two hours ahead, and nothing here is about
# what happens close to a start.
def _soon(hours: int = 48) -> str:
    """A kickoff far enough ahead that the fixture is never mid-game."""
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")



def _world(tmp_path, *, status="scheduled", home_score=None, away_score=None,
           dist=DIST, market="spread"):
    conn = db.open_db(tmp_path / "atl.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('2026_01_NE_SEA', 'nfl', 2026, 1, 'REG', 'SEA', 'NE',"
        " ?, ?, '2026-09-09', ?, ?)",
        (_soon(), status, home_score, away_score))
    factors = json.dumps({"margin_distribution": dist} if dist else {})
    # A WINNER QUESTION HAS NO LINE AND IS NOT ABOUT COVERING. The fixture
    # used to give every market a spread's line and a spread's side, which
    # nothing checked until the four shapes existed -- a moneyline question
    # carrying -3.5 is now refused as a pair that is not about the same
    # proposition, and rightly.
    line, side = (None, "win") if market == "moneyline" else (-3.5, "cover")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-06T00:00:00Z', 'nfl', '2026_01_NE_SEA', ?, 'SEA', ?,"
        " 0.58, ?, 'statistical', 'final', 'fs5', ?, 'test')",
        (market, line, side, factors))
    conn.commit()
    return conn


def _quote(conn, **kw):
    row = {"venue": "kalshi", "ticker": "KXNFLSPREAD-26SEP09NESEA-SEA5",
           "event_ticker": "KXNFLSPREAD-26SEP09NESEA", "sport": "nfl",
           "game_id": "2026_01_NE_SEA", "market": "spread",
           "quantity": "home_margin", "line": -4.5, "yes_side": "home",
           "yes_bid": 0.45, "yes_ask": 0.47, "last_price": 0.46,
           "fetched_utc": "2026-09-07T00:00:00Z"}
    row.update(kw)
    cols = ", ".join(row)
    conn.execute(f"INSERT INTO venue_quotes ({cols}) VALUES"
                 f" ({', '.join('?' for _ in row)})", tuple(row.values()))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM at_the_line_claims").fetchone()[0]


def test_the_distribution_answers_the_venues_question():
    p = at_the_line.model_probability("home_margin", 3.0, 13.0, -3.5)
    assert p == pytest.approx(at_the_line.normal_cdf((3.0 - 3.5) / 13.0))
    assert 0.48 < p < 0.5
    # the same mean, a friendlier number: more likely, and by the normal's shape
    assert at_the_line.model_probability("home_margin", 3.0, 13.0, 6.5) > p
    assert at_the_line.model_probability("total", 44.0, 10.0, 47.5) == pytest.approx(
        at_the_line.normal_cdf((44.0 - 47.5) / 10.0))
    assert at_the_line.model_probability("home_win", 3.0, 13.0, None) == pytest.approx(
        at_the_line.normal_cdf(3.0 / 13.0))
    # absent, never guessed
    assert at_the_line.model_probability("home_margin", 3.0, 13.0, None) is None
    assert at_the_line.model_probability("home_margin", None, 13.0, -3.5) is None
    assert at_the_line.model_probability("home_margin", 3.0, 0.0, -3.5) is None
    assert at_the_line.model_probability("passing_yards", 3.0, 13.0, -3.5) is None


def test_the_rung_is_the_one_priced_nearest_a_coin_flip(tmp_path):
    conn = _world(tmp_path)
    _quote(conn, ticker="a", line=-10.5, yes_bid=0.20, yes_ask=0.22, last_price=None)
    _quote(conn, ticker="b", line=-2.5, yes_bid=0.51, yes_ask=0.53, last_price=None)
    _quote(conn, ticker="c", line=6.5, yes_side="away", yes_bid=0.30, yes_ask=0.32,
           last_price=None)
    rows = conn.execute("SELECT * FROM venue_quotes ORDER BY id").fetchall()
    best = at_the_line.rung_for(rows)
    assert best["quote"]["ticker"] == "b" and best["implied"] == pytest.approx(0.52)
    assert best["basis"] == at_the_line.PRICE_BASIS_MID
    # an away-side strike answers the other question, so its price is complemented
    away = at_the_line.rung_for([rows[2]])
    assert away["price"] == pytest.approx(0.31) and away["implied"] == pytest.approx(0.69)
    # ...and its line is the one it sells: the home side's +6.5 (operator
    # question 36 (i), 2026-09-30), where the released reading said -6.5
    assert away["line"] == 6.5 and best["line"] == -2.5
    # no two-sided quote: the last trade, named as such
    _quote(conn, ticker="d", line=-3.5, yes_bid=None, yes_ask=None, last_price=0.49,
           fetched_utc="2026-09-07T06:00:00Z")
    last_look = conn.execute("SELECT * FROM venue_quotes WHERE ticker = 'd'").fetchall()
    assert at_the_line.rung_for(last_look)["basis"] == at_the_line.PRICE_BASIS_LAST
    # nothing priced at all is None, never a filled-in number
    assert at_the_line.rung_for([]) is None


def test_a_claim_needs_the_frozen_distribution_and_comes_after_it(tmp_path):
    conn = _world(tmp_path, dist=None)
    _quote(conn)
    quote_id = conn.execute("SELECT id FROM venue_quotes").fetchone()[0]
    # A MARGIN-SHAPE CLAIM, which is the one shape that still needs the
    # frozen distribution. The other three do not, which is the whole of
    # AT_THE_PRICE: this trigger refused all four until 2026-09-07 and that is
    # why the record held no claim at all.
    values = ("kalshi", "nfl", "2026_01_NE_SEA", "spread", "home_margin", -4.5,
              "home", "rung_differs_margin", 3.0, 13.0, 0.48, 0.46, 0.46, "mid",
              "2026-09-07T01:00:00Z")
    pid = conn.execute("SELECT id FROM predictions").fetchone()[0]
    sql = ("INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
           " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
           " model_prob, venue_price, venue_implied, price_basis, created_utc)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    with pytest.raises(sqlite3.IntegrityError, match="frozen distribution"):
        conn.execute(sql, (pid, quote_id) + values)


def test_a_claim_stamped_before_its_prediction_or_its_quote_is_refused(tmp_path):
    conn = _world(tmp_path)
    _quote(conn)
    quote_id = conn.execute("SELECT id FROM venue_quotes").fetchone()[0]
    pid = conn.execute("SELECT id FROM predictions").fetchone()[0]
    sql = ("INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
           " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
           " model_prob, venue_price, venue_implied, price_basis, created_utc)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    head = (pid, quote_id, "kalshi", "nfl", "2026_01_NE_SEA", "spread",
            "home_margin", -4.5, "home", "rung_differs_margin", 3.0, 13.0,
            0.48, 0.46, 0.46, "mid")
    # before the prediction: it would read as a blind row, and is not one.
    # Read against a quote of the prediction's own moment, so this is the only
    # rule the row breaks.
    _quote(conn, ticker="same-moment", fetched_utc="2026-09-06T00:00:00Z")
    early_quote = conn.execute(
        "SELECT id FROM venue_quotes WHERE ticker = 'same-moment'").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="blind row"):
        conn.execute(sql, (pid, early_quote) + head[2:] + ("2026-09-06T00:00:00Z",))
    # after the prediction but before the quote it was computed from
    with pytest.raises(sqlite3.IntegrityError, match="before the quote"):
        conn.execute(sql, head + ("2026-09-06T12:00:00Z",))
    conn.execute(sql, head + ("2026-09-07T01:00:00Z",))
    conn.commit()
    # and it is never edited afterwards
    claim_id = conn.execute("SELECT id FROM at_the_line_claims").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE at_the_line_claims SET model_prob = 0.9 WHERE id = ?",
                     (claim_id,))
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM at_the_line_claims WHERE id = ?", (claim_id,))


def test_one_claim_per_look_and_one_standing_claim_per_prediction(tmp_path):
    conn = _world(tmp_path)
    _quote(conn, ticker="open-a", line=-4.5, yes_bid=0.45, yes_ask=0.47)
    _quote(conn, ticker="open-b", line=-9.5, yes_bid=0.25, yes_ask=0.27)
    _quote(conn, ticker="near-a", line=-6.5, yes_bid=0.49, yes_ask=0.51,
           fetched_utc="2026-09-09T23:00:00Z")
    counts = at_the_line.evaluate(conn)
    assert counts["claims"] == 2 and counts["predictions"] == 1
    assert counts["no_distribution"] == 0 and counts["no_quotes"] == 0
    rows = conn.execute("SELECT * FROM at_the_line_claims ORDER BY id").fetchall()
    assert [r["line"] for r in rows] == [-4.5, -6.5]
    assert rows[0]["side"] == "home" and rows[0]["venue"] == "kalshi"
    assert rows[0]["model_prob"] == pytest.approx(
        at_the_line.model_probability("home_margin", 3.0, 13.0, -4.5), abs=1e-6)
    assert rows[0]["venue_implied"] == pytest.approx(0.46)
    # running it again writes nothing twice
    again = at_the_line.evaluate(conn)
    assert again["claims"] == 0 and again["already"] == 2
    # the standing claim is the last look before the start, and there is one
    standing = at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                           predictor="statistical")
    assert len(standing) == 1 and standing[0]["line"] == -6.5


def test_the_holes_are_counted_by_name(tmp_path):
    conn = _world(tmp_path, dist=None)
    counts = at_the_line.evaluate(conn)
    # NO QUOTE IS NOT NO DISTRIBUTION. A shape is a property of the PAIR --
    # the question and the contract -- so with nothing quoted there is no
    # pair to classify, and the hole is the missing quote. The distribution
    # only becomes the hole once a differing rung has been quoted.
    assert counts["claims"] == 0 and counts["no_quotes"] == 1
    _quote(conn, line=-4.5)
    counts = at_the_line.evaluate(conn)
    assert counts["claims"] == 0 and counts["no_distribution"] == 1
    conn.execute("INSERT INTO games (id, sport, season, week, game_type, home, away,"
                 " kickoff_utc, status, league_date) VALUES ('2026_01_KC_DEN', 'nfl',"
                 " 2026, 1, 'REG', 'DEN', 'KC', '2026-09-14T00:20:00Z', 'scheduled',"
                 " '2026-09-13')")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-06T00:00:00Z', 'nfl', '2026_01_KC_DEN', 'spread', 'DEN',"
        " -3.5, 0.55, 'cover', 'statistical', 'final', 'fs5', ?, 'test')",
        (json.dumps({"margin_distribution": DIST}),))
    conn.commit()
    counts = at_the_line.evaluate(conn)
    assert counts["no_quotes"] == 1 and counts["no_distribution"] == 1
    cover = {c["market"]: c for c in at_the_line.coverage(
        conn, sport="nfl", predictor="statistical")}
    spread = cover["spread"]
    assert spread["n"] == 2 and spread["with_a_claim"] == 0 and spread["share"] == 0.0
    named = {h["reason"]: h["n"] for h in spread["holes"]}
    assert named["the prediction carries no frozen distribution"] == 1
    assert named["the venue quoted nothing for the game"] == 1


def test_a_claim_settles_with_its_game_and_a_level_game_is_left_open(tmp_path):
    conn = _world(tmp_path)
    _quote(conn, line=-4.5, yes_bid=0.45, yes_ask=0.47)
    assert at_the_line.evaluate(conn)["claims"] == 1
    _finish(conn, 27, 20)
    result = tasks.settle_everything(conn)
    assert result["at_the_line_settled"] == 1 and result["at_the_line_open"] == 0
    row = conn.execute("SELECT * FROM at_the_line_claims").fetchone()
    # 27-20 is a seven-point win, so the home side covered -4.5
    assert row["outcome"] == 1 and row["resolved_utc"]
    # resolution is idempotent, and never re-scores
    assert tasks.settle_everything(conn)["at_the_line_settled"] == 0
    with pytest.raises(sqlite3.IntegrityError, match="already resolved"):
        conn.execute("UPDATE at_the_line_claims SET resolved_utc = ?, outcome = 0"
                     " WHERE id = ?", ("2026-09-11T00:00:00Z", row["id"]))


def test_a_level_game_leaves_the_winner_claim_open_and_says_so(tmp_path):
    conn = _world(tmp_path, market="moneyline")
    _quote(conn, market="moneyline", quantity="home_win", line=None,
           yes_bid=0.55, yes_ask=0.57)
    assert at_the_line.evaluate(conn)["claims"] == 1
    _finish(conn, 20, 20)
    result = tasks.settle_everything(conn)
    assert result["at_the_line_settled"] == 0
    assert result["at_the_line_unanswerable"] == 1 and result["at_the_line_open"] == 1


def _settled_claim(conn, *, outcome=1, prob=0.58, implied=0.52, line=-4.5,
                   ticker="k1", fetched="2026-09-07T00:00:00Z"):
    _quote(conn, ticker=ticker, line=line, fetched_utc=fetched)
    at_the_line.evaluate(conn)   # while the game is still ahead
    row = conn.execute("SELECT id FROM at_the_line_claims ORDER BY id DESC").fetchone()
    conn.execute("UPDATE at_the_line_claims SET resolved_utc = '2026-09-11T00:00:00Z',"
                 " outcome = ? WHERE id = ?", (outcome, row[0]))
    conn.commit()
    return row[0]


def test_the_at_the_line_record_is_its_own_record(tmp_path):
    from gridiron import calibration

    conn = _world(tmp_path)
    _settled_claim(conn)
    card = calibration.at_the_line_scorecard(conn, sport="nfl")
    assert card["record"] == "at_the_line" and card["venue"] == "kalshi"
    # WHOSE CURVE, BY NAME (item 6, 2026-09-26): two curves per market now,
    # so the test names the forecaster rather than taking the first row.
    spread = next(c for c in card["categories"]
                  if c["market"] == "spread" and c["predictor"] == "statistical")
    assert spread["record"] == "at_the_line" and spread["n"] == 1
    assert "100" in spread["gate_line"] and spread["score"]["n"] == 1
    # the venue's own prices are the baseline the model is scored against
    assert spread["baselines"]["market"]["n"] == 1
    # coverage names what could be read and what could not
    assert any(row["market"] == "spread" and row["with_a_claim"] == 1
               and row["predictor"] == "statistical"
               for row in card["coverage"])
    assert all("words" in row for row in card["coverage"])


def test_a_claim_curve_cannot_be_filed_with_the_blind_curves():
    from gridiron import calibration

    merged = {"record": "rung", "categories": [
        {"category": "spread / statistical", "record": "rung"},
        {"category": "spread / at the venue's line", "record": "at_the_line"}]}
    with pytest.raises(calibration.MergedRecord, match="never merged"):
        calibration.assert_the_records_stay_apart(merged)
    # and a scorecard that will not say which record it is
    with pytest.raises(calibration.MergedRecord, match="neither"):
        calibration.assert_the_records_stay_apart({"categories": []})


def test_the_record_page_carries_both_records_separately(tmp_path):
    from gridiron import calibration

    conn = _world(tmp_path)
    _settled_claim(conn)
    card = calibration.scorecard(conn, sport="nfl")
    assert card["record"] == "rung"
    assert all(c["record"] == "rung" for c in card["categories"])
    assert card["at_the_line"]["record"] == "at_the_line"
    assert not any(c.get("record") == "at_the_line" for c in card["categories"])


def test_the_words_beside_a_pick_are_a_forecast_and_carry_their_sample(tmp_path):
    from gridiron import audit, views

    conn = _world(tmp_path)
    _quote(conn, line=-4.5)
    at_the_line.evaluate(conn)
    pid = conn.execute("SELECT id FROM predictions").fetchone()[0]
    beside = views._at_the_line(conn, "nfl", [pid], {})
    words = beside[pid]["words"]
    # THE SENTENCE NAMES WHICH FORECAST IT IS. The card already shows the fitted
    # model's own percentage; an unlabelled second one inches away reads as a
    # contradiction rather than a second reading of the same game.
    assert "from the model's margin forecast" in words
    assert "the venue's price implies" in words
    assert beside[pid]["n"] == 0 and "0 of 100" in beside[pid]["gate_line"]
    assert audit.advice_word_faults(words) == []
    assert audit.plain_words_violations(words) == []
    assert audit.plain_words_violations(beside[pid]["gate_line"]) == []
    # a prediction with no claim gets nothing rather than an empty comparison
    assert views._at_the_line(conn, "nfl", [], {}) == {}


# ---------------------------------------------------------------------------
# ONE CLAIM PER DISTINCT BET (GRIDIRON_REPAIR item 6, 2026-09-26; operator
# question 17, ruled 2026-09-27, and question 21, ruled 2026-09-28)
# ---------------------------------------------------------------------------

def _two_passes_world(tmp_path, *, final_rung=-1.5):
    """One game forecast three ways at the spread, read at two looks.

    The statistical model's morning pass asked -3.5 and its final pass
    another rung, -1.5 -- two standing questions, as the live NCAAF record
    holds them -- and the reasoning pass asked -3.5. The venue is read twice
    before the start, so every forecast gets a claim at each look: six rows,
    THREE bets from operator question 17 ("Two rungs on one game are two
    questions"): the statistical model's two and the reasoning pass's one.
    It was two bets, one per forecaster, from item 6 to that date. An
    opening read a week out, at the venue's line then (-4.5) and at the
    strike the claims are read at near the start (-6.5), gives the venue's
    drift pair something to start from at the claim's own strike.
    `final_rung=-3.5` makes the final pass ask the morning pass's rung: one
    question answered twice, one bet.
    """
    conn = db.open_db(tmp_path / "bets.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date)"
        " VALUES ('2026_01_NE_SEA', 'nfl', 2026, 1, 'REG', 'SEA', 'NE',"
        " ?, 'scheduled', '2026-09-09')", (_soon(),))
    factors = json.dumps({"margin_distribution": DIST})
    ids = {}
    for who, pass_kind, rung, written in (
            ("statistical", "early", -3.5, "2026-09-06T00:00:00Z"),
            ("statistical", "final", final_rung, "2026-09-07T00:00:00Z"),
            ("llm", "final", -3.5, "2026-09-07T00:00:01Z")):
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES (?, 'nfl', '2026_01_NE_SEA', 'spread', 'SEA', ?, 0.58,"
            " 'cover', ?, ?, 'fs5', ?, 'test')",
            (written, rung, who, pass_kind, factors))
        ids[(who, pass_kind)] = conn.execute(
            "SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    at_the_line.ensure_read_kind(conn)
    _quote(conn, ticker="open", line=-4.5, yes_bid=0.29, yes_ask=0.31,
           fetched_utc="2026-09-07T12:00:00Z", read_kind="open")
    _quote(conn, ticker="open-alt", line=-6.5, yes_bid=0.24, yes_ask=0.26,
           fetched_utc="2026-09-07T12:00:00Z", read_kind="open")
    _quote(conn, ticker="look-1", line=-4.5, yes_bid=0.45, yes_ask=0.47,
           fetched_utc="2026-09-08T00:00:00Z")
    _quote(conn, ticker="look-2", line=-6.5, yes_bid=0.49, yes_ask=0.51,
           fetched_utc="2026-09-09T00:00:00Z")
    assert at_the_line.evaluate(conn)["claims"] == 6
    _finish(conn, 27, 20)
    tasks.settle_everything(conn)
    return conn, ids


def test_the_at_the_line_record_counts_one_claim_per_distinct_bet(tmp_path):
    """FLIPPED BY OPERATOR QUESTION 17 (ruled 2026-09-27; question 21, ruled
    2026-09-28: "Two rungs on one game are two questions"). Item 6 counted
    one claim per forecaster per GAME, so the statistical model's two rungs
    were one bet; a bet is now `bet.of` -- the forecaster and the question
    it was asked, the rung included -- so they are two, each on its own
    last claim before the start, and the reasoning pass's one is its own."""
    from gridiron import bet, calibration, drift, views

    conn, ids = _two_passes_world(tmp_path)
    settled = conn.execute("SELECT COUNT(*) FROM at_the_line_claims"
                           " WHERE resolved_utc IS NOT NULL").fetchone()[0]
    assert settled == 6, "the world is six settled claims on one game"
    # THE DOOR: one claim per distinct bet, the last before the start -- each
    # question's claim at the second look's number.
    mine = at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                       predictor="statistical")
    theirs = at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                         predictor="llm")
    assert len(mine) == 2 and len(theirs) == 1
    assert [c["prediction_id"] for c in mine] == [
        ids[("statistical", "early")], ids[("statistical", "final")]]
    assert {c["line_asked"] for c in mine} == {-3.5, -1.5}
    assert all(c["line"] == -6.5 and c["predictor"] == "statistical" for c in mine)
    assert theirs[0]["prediction_id"] == ids[("llm", "final")]
    assert bet.count(mine) == 2 and bet.count(list(mine) + list(theirs)) == 3
    # THE PAGE: one curve per forecaster, its own bets each, never a curve of
    # three or of six.
    card = calibration.at_the_line_scorecard(conn, sport="nfl")
    spread = {c["predictor"]: c for c in card["categories"] if c["market"] == "spread"}
    assert set(spread) == {"statistical", "llm"}
    for who, count in (("statistical", 2), ("llm", 1)):
        curve = spread[who]
        assert curve["n"] == curve["distinct_bets"] == curve["recounted"] == count, who
        assert curve["forecasters_counted"] == [who]
        assert curve["filters"]["predictor"] == who
        assert f"{count} of 100" in curve["gate_line"]
    assert "statistical" in spread["statistical"]["category_label"]
    assert "reasoning pass" in spread["llm"]["category_label"]
    assert "n" not in card, "a total across the forecasters is nobody's record"
    ledgers = {(p["market"], p["predictor"]): p for p in card["paper"]}
    mine_ledger = ledgers[("spread", "statistical")]
    assert mine_ledger["distinct_bets"] == mine_ledger["n"] == mine_ledger["recounted"] <= 2
    assert card["edge"]["predictor"] == "statistical"
    assert card["edge"]["n"] == card["edge"]["recounted"] == 2
    # THE CARD beside each pick counts its own forecaster's bets, and says
    # the same number as that forecaster's curve.
    beside = views._at_the_line(conn, "nfl", list(ids.values()), {})
    assert beside[ids[("statistical", "final")]]["n"] == 2
    assert beside[ids[("statistical", "early")]]["n"] == 2
    assert beside[ids[("llm", "final")]]["n"] == 1
    # THE COVERAGE, ONE PER DISTINCT BET: the statistical model's two
    # standing questions are two bets, both read -- the same two its curve
    # counts -- and the line says questions, not games.
    cover = {(c["market"], c["predictor"]): c for c in card["coverage"]}
    mine = cover[("spread", "statistical")]
    assert mine["forecasts"] == 2
    assert mine["n"] == mine["distinct_bets"] == mine["recounted"] == 2
    assert mine["with_a_claim"] == mine["read_recounted"] == 2
    assert mine["with_a_claim"] == spread["statistical"]["distinct_bets"]
    assert cover[("spread", "llm")]["n"] == cover[("spread", "llm")]["with_a_claim"] == 1
    assert "statistical" in mine["words"]
    assert "for 2 of 2 questions it answered" in mine["words"]
    assert "game" not in mine["words"]
    # THE VENUE'S DRIFT PAIR: one per distinct bet, each claim beside the
    # opening read AT ITS OWN STRIKE (-6.5, priced 25% at the open), never
    # the open's own line (-4.5), which is another question.
    for who, count in (("statistical", 2), ("llm", 1)):
        pairs = drift.venue_pairs(conn, sport="nfl", market_type="spread",
                                  predictor=who)
        assert len(pairs) == bet.count(pairs) == count, who
        assert all(p["line"] == -6.5 and p["opened"] == pytest.approx(0.25)
                   for p in pairs), who


def test_the_venues_pair_is_one_question_at_one_strike(tmp_path):
    """ALT LINES ARE SEPARATE QUESTIONS (operator question 17, 2026-09-28).
    Until this date the pair set the opening ladder's own line beside the
    claim's: "home covers -4.5" at the open beside "home covers -6.5" near
    the start, two questions, their difference called movement. A claim
    whose strike the opening read did not quote has no pair."""
    from gridiron import drift, views

    conn, ids = _two_passes_world(tmp_path)
    # THE OPEN QUOTED THE CLAIMS' STRIKE: a pair per bet
    assert len(drift.venue_pairs(conn, sport="nfl", market_type="spread",
                                 predictor="statistical")) == 2
    # A WORLD WHOSE OPENING READ QUOTED ONLY ANOTHER STRIKE HAS NONE: the
    # claim is read at -6.5, the open quoted -4.5 alone.
    conn2 = db.open_db(tmp_path / "alt.db")
    conn2.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date)"
        " VALUES ('2026_01_NE_SEA', 'nfl', 2026, 1, 'REG', 'SEA', 'NE',"
        " ?, 'scheduled', '2026-09-09')", (_soon(),))
    conn2.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-06T00:00:00Z', 'nfl', '2026_01_NE_SEA', 'spread',"
        " 'SEA', -3.5, 0.58, 'cover', 'statistical', 'final', 'fs5', ?, 'test')",
        (json.dumps({"margin_distribution": DIST}),))
    conn2.commit()
    at_the_line.ensure_read_kind(conn2)
    _quote(conn2, ticker="open", line=-4.5, yes_bid=0.29, yes_ask=0.31,
           fetched_utc="2026-09-07T12:00:00Z", read_kind="open")
    _quote(conn2, ticker="look", line=-6.5, yes_bid=0.49, yes_ask=0.51,
           fetched_utc="2026-09-08T00:00:00Z")
    assert at_the_line.evaluate(conn2)["claims"] == 1
    assert drift.venue_pairs(conn2, sport="nfl", market_type="spread",
                             predictor="statistical") == []
    (venue,) = [v for v in views.drift_report(conn2, "nfl")["venue_markets"]
                if v["market_type"] == "spread" and v["predictor"] == "statistical"]
    assert venue["n"] == 0 and venue["claims_read"] == venue["recounted"] == 1


def test_the_outlook_and_the_gate_line_count_the_same_bets(tmp_path):
    from gridiron import calibration, config, language

    conn, _ids = _two_passes_world(tmp_path)
    card = calibration.at_the_line_scorecard(conn, sport="nfl")
    for curve in card["categories"]:
        outlook = curve["outlook"]
        # ONE LIST, THREE COUNTS: the gate line, the curve and the outlook.
        assert outlook["resolved"] == curve["n"], curve["category"]
        assert curve["gate_line"] == language.at_the_line_gate_line(
            curve["n"], config.MIN_SAMPLE_FOR_EDGE_CLAIM)
        assert outlook["predictor"] == curve["predictor"]
    spread = next(c for c in card["categories"]
                  if c["market"] == "spread" and c["predictor"] == "statistical")
    # written this season: two bets (two rungs, operator question 17) on one
    # slate, however many rows held them
    assert spread["outlook"]["written"] == 2
    assert spread["outlook"]["slates_used"] == 1
    assert spread["outlook"]["message"].startswith("2 of 100")


def test_the_pace_line_never_denies_the_claims_it_counts(tmp_path, monkeypatch):
    """THE PROVER OF ITEM 6 (2026-09-26): the curve counts every season's
    bets and the pace only this season's, so once a season turns over the
    line read "1 of 100 · no claim from this forecaster has been written in
    this market yet" -- a count and its denial in one sentence. It was on the
    browser world's Record page, whose games are last season's."""
    from gridiron import calibration, config

    conn, _ids = _two_passes_world(tmp_path)
    monkeypatch.setitem(config.SPORT_CURRENT_SEASON, "nfl", 2027)
    card = calibration.at_the_line_scorecard(conn, sport="nfl")
    curves = {(c["market"], c["predictor"]): c for c in card["categories"]}
    written = curves[("spread", "statistical")]
    assert written["n"] == 2 and written["outlook"]["written"] == 0
    assert written["outlook"]["message"].startswith("2 of 100")
    assert "written in this market this season" in written["outlook"]["message"]
    assert "yet" not in written["outlook"]["message"]
    # a forecaster with no claim in any season still says "yet"
    never = curves[("total", "statistical")]
    assert never["n"] == 0
    assert "written in this market yet" in never["outlook"]["message"]


def test_a_withdrawn_forecast_takes_back_its_claim_not_the_bet(tmp_path):
    # ONE QUESTION ASKED BY BOTH PASSES (operator question 17, 2026-09-28):
    # at two rungs they are two bets, and a withdrawal of one would take its
    # own bet back -- the shape this test is about needs the final pass to
    # have asked the morning pass's rung.
    conn, ids = _two_passes_world(tmp_path, final_rung=-3.5)

    def statistical():
        return at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                           predictor="statistical")

    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, '2026-09-10T00:00:00Z', ?)",
                 (ids[("statistical", "final")], "withdrawn in this test, by hand"))
    conn.commit()
    # the morning pass still stands behind the bet, with its own last claim
    assert [c["prediction_id"] for c in statistical()] == [ids[("statistical", "early")]]
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason)"
                 " VALUES (?, '2026-09-10T00:00:01Z', ?)",
                 (ids[("statistical", "early")], "withdrawn in this test, by hand"))
    conn.commit()
    assert statistical() == []
    # and the other forecaster's bet was never the statistical model's to lose
    assert len(at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                           predictor="llm")) == 1


def test_a_pooled_at_the_line_category_is_refused_by_name(tmp_path):
    import copy

    from gridiron import calibration, language

    conn, _ids = _two_passes_world(tmp_path)
    honest = calibration.at_the_line_scorecard(conn, sport="nfl")
    calibration.assert_no_pooled_claims(honest)

    def refused(change, match):
        payload = copy.deepcopy(honest)
        change(payload)
        with pytest.raises(calibration.MergedCurve, match=match):
            calibration.assert_no_pooled_claims(payload)

    def first(payload):
        return payload["categories"][0]

    def pooled(p):
        first(p)["filters"]["predictor"] = None

    def twice(p):
        # the statistical spread holds two bets (two rungs, operator
        # question 17); a third claim on them is one counted twice
        first(p).update(n=3)
        first(p)["outlook"]["resolved"] = 3

    refused(pooled, "merges the statistical and LLM forecasters")
    refused(lambda p: first(p).update(forecasters_counted=["llm", "statistical"]),
            "two forecasters pooled")
    refused(twice, "counts 3 settled claims for 2 distinct bets")
    refused(lambda p: first(p)["outlook"].update(resolved=6),
            "two counts of one record")
    refused(lambda p: first(p).update(gate_line="6 of 100 settled comparisons"),
            "not its own count")
    refused(lambda p: p["paper"][0].update(predictor=None), "names forecaster None")
    refused(lambda p: p["edge"].update(distinct_bets=0), "distinct bets")
    refused(lambda p: p["coverage"][0].update(predictor="all"), "names forecaster 'all'")
    # a coverage line counting a question's passes as more, or reading one
    # twice (the prover, 2026-09-26)
    refused(lambda p: p["coverage"][0].update(n=p["coverage"][0]["n"] + 1),
            "A question is one bet")
    refused(lambda p: p["coverage"][0].update(
        with_a_claim=p["coverage"][0]["n"] + 1), "A question is one bet")
    # A COUNT THE RECOUNT DOES NOT MAKE (operator question 17, 2026-09-28):
    # a curve, a ledger, the edge or a coverage line whose count is not the
    # one made without its door, one per distinct bet by the one key -- or
    # that carries no recount at all.
    def one_rung(p):
        # THE DOOR OF 2026-09-26: the two rungs as one claim, every figure
        # the door's own count agreeing with it
        first(p).update(n=1, distinct_bets=1, gate_line=language.at_the_line_gate_line(
            1, first(p)["gate"]))
        first(p)["outlook"]["resolved"] = 1

    refused(one_rung, "counts 1 where the recount made without its door finds 2")
    refused(lambda p: first(p).pop("recounted"), "finds None")
    refused(lambda p: p["paper"][0].update(recounted=p["paper"][0]["n"] + 1),
            "where the recount made without its door")
    refused(lambda p: p["edge"].update(recounted=p["edge"]["n"] + 1),
            "where the recount made without its door")
    refused(lambda p: p["coverage"][0].update(recounted=p["coverage"][0]["n"] + 1),
            "where the recount made without either door")
    refused(lambda p: p["coverage"][0].update(read_recounted=None),
            "where the recount made without either door")
    refused(lambda p: p.update(n=2), "a total n")
    # THE DOOR ITSELF will not count for nobody in particular, or across tiers
    for who in (None, "all", "priced"):
        with pytest.raises(at_the_line.PooledCount, match="never pooled"):
            at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                        predictor=who)
    with pytest.raises(at_the_line.PooledCount, match="LAW 6"):
        at_the_line.standing_claims(conn, sport="ufc", market="moneyline",
                                    predictor="statistical")
    with pytest.raises(at_the_line.PooledCount, match="LAW 6"):
        at_the_line.standing_claims(conn, sport="nfl", market="spread",
                                    predictor="statistical", event_tier="numbered")
    # AND UFC IS SPLIT BY CARD, as the rest of its record is: one curve per
    # tier and forecaster, each naming its tier in words.
    ufc = calibration.at_the_line_scorecard(conn, sport="ufc")
    tiers = {(c["event_tier"], c["predictor"]) for c in ufc["categories"]}
    assert len(tiers) == len(ufc["categories"]) == 6
    assert all(c["event_tier"] in ("numbered", "fight_night", "contender")
               for c in ufc["categories"])
    assert any("Fight Night" in c["category_label"] for c in ufc["categories"])


def test_advice_words_are_caught_wherever_the_record_composes_them():
    from gridiron import audit

    planted = {"record": "at_the_line", "categories": [
        {"category": "spread", "gate_line": "the value play is the home side"}]}
    assert audit.at_the_line_advice_faults(planted)
    with pytest.raises(audit.LawViolation, match="forecast"):
        audit.check_the_at_the_line_words_are_a_forecast(planted)
    # the model's own quoted prose is scanned for the shorter list: a tip is
    # caught wherever it was written, and "value" in an ordinary sentence about
    # a running game is not a tip
    assert audit.advice_word_faults("this is a lock")
    assert audit.tipster_faults_in_quoted_prose(_Prose("this is a lock"))
    assert audit.tipster_faults_in_quoted_prose(
        _Prose("the value of the run game showed")) == []
    # EVERY WORD IS BOUND ON BOTH SIDES (2026-09-24): "lock" inside
    # "body-clock" is not a tip, and "a lock" still is
    assert audit.tipster_faults_in_quoted_prose(
        _Prose("a 1pm body-clock start after three time zones")) == []
    assert audit.tipster_faults_in_quoted_prose(_Prose("it is a lock, trust it"))


class _Prose:
    """The smallest thing the reasoning scan reads: rows with an id and words."""

    def __init__(self, text):
        self.text = text

    def execute(self, _sql):
        return [{"id": 1, "reasoning": self.text}]
