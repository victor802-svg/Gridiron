"""Today (GRIDIRON_TODAY, 2026-09-07): two groups that never blend, a row that
prints its own negative edge, a tap that records which pick and when and
nothing else, and a learning panel that says what has actually been fitted."""
from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import audit, config, db, language, shortlist, views

DIST = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})


def _world(tmp_path, games=2):
    conn = db.open_db(tmp_path / "today.db")
    for i in range(games):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')",
            (f"g{i}",))
    conn.commit()
    return conn


def _pick(conn, *, game="g0", prob=0.62, subject="AAA"):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'mlb', ?, 'moneyline', ?, NULL, ?,"
        " 'win', 'statistical', 'final', 'fs2', ?, 'test')",
        (game, subject, prob, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    return pid


def test_a_taken_pick_records_which_and_when_and_nothing_else(tmp_path):
    conn = _world(tmp_path)
    pid = _pick(conn)
    got = views.take_pick(conn, pid)
    assert got["taken"] is True and got["already"] is False
    row = conn.execute("SELECT * FROM picks_taken").fetchone()
    # AND `package_id` FROM 2026-09-08 (GRIDIRON_COMBOS C4): the same table
    # records the other thing the operator can take, and its CHECK admits
    # exactly one of the two per row. Still no stake, no price paid, no payout
    # and no result in money, which is what this assertion actually defends.
    assert set(row.keys()) == {"id", "prediction_id", "package_id", "taken_utc"}
    assert row["prediction_id"] == pid and row["taken_utc"] > "2026-09-07"
    # a second tap is the same fact, not a second wager
    assert views.take_pick(conn, pid)["already"] is True
    assert conn.execute("SELECT COUNT(*) FROM picks_taken").fetchone()[0] == 1
    # and it is append-only
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE picks_taken SET taken_utc = '2026-09-08T00:00:00Z'"
                     " WHERE id = ?", (row["id"],))
    # a pick that does not exist is refused rather than invented
    assert views.take_pick(conn, 9999)["taken"] is False


def test_the_taken_table_is_not_a_ledger_and_the_model_cannot_see_it(tmp_path):
    conn = _world(tmp_path)
    audit.check_taken_is_not_a_ledger(conn)      # must not raise
    audit.check_taken_not_in_training()          # nor this
    conn.execute("ALTER TABLE picks_taken ADD COLUMN payout REAL")
    with pytest.raises(audit.LawViolation, match="LEDGER"):
        audit.check_taken_is_not_a_ledger(conn)


def test_today_has_two_groups_and_the_watched_rows_show_their_own_edge(tmp_path):
    conn = _world(tmp_path, games=3)
    ids = [_pick(conn, game=f"g{i}", subject=f"AAA{i}") for i in range(3)]
    payload = views.week(conn, "mlb", 2026, 1)
    today = payload["today"]
    # nothing clears the fee on a slate with no venue price, and the screen
    # says so rather than reaching into the other group
    assert today["n"] == 0 and today["clears"] == []
    assert "Nothing clears" in today["clears_heading"]
    # the list is never empty: every shortlisted question is watched
    assert today["watching_n"] == len(ids)
    for row in today["watching"]:
        assert row["prediction_id"] in ids
        assert row["taken"] is False
    # and the fee line is present every day, even with nothing to price
    assert "fee" in today["fee_line"] or "no fee" in today["fee_line"]
    assert today["taken_line"] == "None marked as taken today."


def test_a_watched_row_prints_a_negative_edge_rather_than_hiding_it():
    """THE PROPERTY OUTLIVED THE FUNCTION. `language.watching_line` wrote a
    sentence per row until CARD_FACE replaced the rows with cards; a watched
    card still prints what the question is actually worth after the fee,
    including when that number is negative, which is the point of showing it.
    """
    assert language.edge_chip_words(-3.4) == "-3.4¢"
    assert language.edge_state(-3.4) == "down"
    label = language.price_row_labels()["edge"]
    assert "after fees" in label
    assert audit.advice_word_faults(label) == []
    assert audit.plain_words_violations(label) == []
    # and the heading says plainly that these do not clear the bar
    heading = language.watching_heading(18)
    assert "none of which clears" in heading
    assert audit.advice_word_faults(heading) == []


def test_no_watched_row_may_be_called_worth_backing():
    for word in ("value", "play", "lock", "best bet", "free money", "worth it"):
        planted = f"Seattle covering -4.5 — a {word} at this price"
        assert audit.advice_word_faults(planted), word
    payload = {"shortlist": {"words": "today's best bets"}, "cards": []}
    with pytest.raises(audit.LawViolation):
        audit.check_the_shortlist_speaks_of_questions(payload)


def test_the_learning_panel_says_what_has_actually_been_fitted(tmp_path):
    conn = _world(tmp_path)
    _pick(conn)
    got = views.learning(conn, "mlb")
    assert got["categories"], "every declared market gets a row"
    for entry in got["categories"]:
        assert "not yet fitted" in entry["status_words"] or \
               "eligible" in entry["status_words"] or \
               "in force" in entry["status_words"]
        assert audit.plain_words_violations(entry["status_words"]) == []
    assert "never" in got["never_rewrites"]


def test_a_placeholder_fit_is_not_reported_as_a_fit():
    """A correction row with `n_train = 0` records that there was nothing to
    fit. Reporting it as fitted would tell a reader the model has learned
    something it has not."""
    placeholder = language.correction_status_line(
        True, 52, 50, "2026-09-01T00:42:11Z", False,
        last_refit="2026-09-01T00:42:11Z", n_train=0)
    assert "eligible and not yet fitted" in placeholder
    assert "refit last ran" in placeholder
    real = language.correction_status_line(
        True, 110, 50, "2026-09-01T00:42:11Z", True,
        last_refit="2026-09-01T00:42:11Z", n_train=110)
    assert "in force since" in real
    below = language.correction_status_line(False, 19, 50, None, False, n_train=0)
    assert "31 more" in below


def test_the_correction_explains_itself_in_one_worked_number():
    lower = language.correction_meaning_line(0.70, 0.62)
    assert "70%" in lower and "62%" in lower and "lower" in lower
    same = language.correction_meaning_line(0.70, 0.70)
    assert "unchanged" in same
    assert audit.plain_words_violations(lower) == []
