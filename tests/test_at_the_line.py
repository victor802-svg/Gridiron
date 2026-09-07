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


def _world(tmp_path, *, status="scheduled", home_score=None, away_score=None,
           dist=DIST, market="spread"):
    conn = db.open_db(tmp_path / "atl.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('2026_01_NE_SEA', 'nfl', 2026, 1, 'REG', 'SEA', 'NE',"
        " '2026-09-10T00:20:00Z', ?, '2026-09-09', ?, ?)",
        (status, home_score, away_score))
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
    standing = at_the_line.standing_claims(conn, sport="nfl", market="spread")
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
    cover = {c["market"]: c for c in at_the_line.coverage(conn, sport="nfl")}
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
    spread = next(c for c in card["categories"] if c["market"] == "spread")
    assert spread["record"] == "at_the_line" and spread["n"] == 1
    assert "100" in spread["gate_line"] and spread["score"]["n"] == 1
    # the venue's own prices are the baseline the model is scored against
    assert spread["baselines"]["market"]["n"] == 1
    # coverage names what could be read and what could not
    assert any(row["market"] == "spread" and row["with_a_claim"] == 1
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


class _Prose:
    """The smallest thing the reasoning scan reads: rows with an id and words."""

    def __init__(self, text):
        self.text = text

    def execute(self, _sql):
        return [{"id": 1, "reasoning": self.text}]
