"""The side is placed in one place, and a side it cannot place is refused
(the operator's ruling of 2026-09-30, docs/briefs/2026-09-30-rulings.md).

"Rec 111 / NCAAF wrong side: fix it ... Read 'fail to cover' as the no side in
the one place the side is worked out; the page and the check refuse any side
they can't place instead of passing it."

Recommendation 111 -- UNT at TLSA, a sized flat unit, stored correctly as the
no side of "TLSA covers +6.5" at a fair value of 0.2398 for the yes side and a
price of 0.485 -- was drawn "North Texas -6.5 · 24% · 48¢": the other side's
chance and price under North Texas, whose own are about 76% and 51.5¢.
College football stores the no side of a spread as "fail to cover", the
numbers' mapping (`priced.shape.blind_probability`) had no rule for it, and
every builder and the gate's check turned the numbers only on `is False`.
"""

from __future__ import annotations

import json

import pytest

from gridiron import audit, board, db, language, resolve, subjects, views
from gridiron.market import recommend
from gridiron.priced import shape
from gridiron.sports import cfb

DIST = {"quantity": "home_margin", "family": "normal", "mean": -9.0, "sd": 14.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})
GAME = "401862786"
SLATE = 20261001


@pytest.fixture(autouse=True)
def _covered(monkeypatch):
    """The coverage list is not what these tests are about (test_priced.py)."""
    from gridiron.priced import coverage

    monkeypatch.setattr(coverage, "priceable",
                        lambda conn, sport, market, **_: {
                            "priceable": True, "market": market,
                            "why": "covered, in this test"})


def _rec_111(path, *, side="fail to cover"):
    """Recommendation 111's shape, as the record holds it: the final pass on
    UNT at TLSA, "TLSA covers +6.5" answered on the no side at 62.6%, and a
    claim of 0.2398 for the home side covering against a 48.5c yes price."""
    conn = db.open_db(path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES (?, 'cfb', 2026, ?, 'REG',"
        " 'TLSA', 'UNT', '2099-10-02T01:00:00Z', 'scheduled', '2026-10-01')",
        (GAME, SLATE))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-28T15:00:00Z', 'cfb', ?, 'spread', 'TLSA', 6.5, 0.626036,"
        " ?, 'statistical', 'final', 'fs2', ?, 'test')", (GAME, side, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
        " VALUES ('kalshi', 't111', 'e', 'cfb', ?, 'spread', 'home_margin', 6.5,"
        " 'home', 0.475, 0.495, '2026-09-28T15:00:44Z')", (GAME,))
    quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'cfb', ?, 'spread', 'home_margin', 6.5,"
        " 'home', 'rung_differs_margin', -9.0, 14.0, 0.2398, 0.485, 0.485,"
        " 'mid', '2026-09-28T15:00:45Z')", (pid, quote, GAME))
    conn.commit()
    from gridiron import shortlist

    shortlist.rank_rows(conn, [pid])
    return conn, pid


def _block_and_card(payload, pid):
    card = next(c for group in ("clears", "below_floor", "watching")
                for c in payload["today"][group] if c["prediction_id"] == pid)
    block = next(q for g in payload["board"]["games"] for q in g["questions"]
                 if q["prediction_id"] == pid)
    return block, card


# --- 1. rec 111's shape, on the page -----------------------------------------

def test_rec_111s_shape_shows_north_texas_own_numbers(tmp_path):
    """About 76% and about 51.5c for North Texas -6.5 -- not the 24% and 48c
    of Tulsa covering that the released page drew under North Texas."""
    conn, pid = _rec_111(tmp_path / "rec111.db")
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["side"] == "no"
    assert entry["question_takes_the_proposition"] is False
    assert entry["fair_value"] == pytest.approx(0.2398)
    assert entry["price"] == pytest.approx(0.485)
    payload = views.week(conn, "cfb", 2026, SLATE)
    block, card = _block_and_card(payload, pid)
    assert "UNT" in block["question"] and "-6.5" in block["question"], block["question"]
    assert block["prob"] == pytest.approx(0.7602), block["prob"]
    assert block["prob_words"] == "76%"
    assert block["price"] == pytest.approx(0.515)
    assert block["pays"] == recommend.payout_multiple(0.515) == pytest.approx(1.942)
    assert card["model_words"] == "76¢"
    assert card["question_takes_the_proposition"] is False
    # the row's pick is this question, on the same numbers
    pick = next(g["pick"] for g in payload["board"]["games"] if g["pick"])
    assert pick["prediction_id"] == pid and pick["prob"] == pytest.approx(0.7602)
    assert audit.board_price_side_faults(payload) == []


# --- 2. each stored spelling of each sport maps to one side ------------------

#: EVERY (sport, market, stored side) ON THE RECORD, measured read-only on
#: 2026-09-30 (`db.read_the_live_record`), and the side each one is.
STORED = [
    ("cfb", "moneyline", "win", "yes"), ("cfb", "moneyline", "lose", "no"),
    ("cfb", "spread", "cover", "yes"), ("cfb", "spread", "fail to cover", "no"),
    ("cfb", "total", "over", "yes"), ("cfb", "total", "under", "no"),
    ("mlb", "moneyline", "win", "yes"), ("mlb", "moneyline", "lose", "no"),
    ("mlb", "spread", "not_cover", "no"),
    ("mlb", "total", "over", "yes"), ("mlb", "total", "under", "no"),
    ("mlb", "prop", "over", "yes"), ("mlb", "prop", "under", "no"),
    ("nba", "moneyline", "win", "yes"), ("nba", "moneyline", "lose", "no"),
    ("nba", "spread", "cover", "yes"), ("nba", "spread", "not_cover", "no"),
    ("nba", "total", "over", "yes"), ("nba", "total", "under", "no"),
    ("nfl", "moneyline", "win", "yes"), ("nfl", "moneyline", "lose", "no"),
    ("nfl", "spread", "cover", "yes"), ("nfl", "spread", "not_cover", "no"),
    ("nfl", "total", "over", "yes"), ("nfl", "total", "under", "no"),
    ("nfl", "prop", "over", "yes"), ("nfl", "prop", "under", "no"),
    ("ufc", "moneyline", "win", "yes"), ("ufc", "moneyline", "lose", "no"),
    ("ufc", "rounds", "over", "yes"), ("ufc", "rounds", "under", "no"),
    ("ufc", "distance", "yes", "yes"), ("ufc", "distance", "no", "no"),
]

#: The claim's fixed proposition for each market the numbers are priced on.
QUANTITY = {"spread": "home_margin", "moneyline": "home_win", "total": "total",
            "prop": "count"}


@pytest.mark.parametrize("sport,market,side,which", STORED)
def test_each_stored_spelling_of_each_sport_maps_to_one_side(sport, market, side, which):
    """The one place, the words and the numbers agree on every spelling."""
    assert subjects.side_taken(market, side) == which
    item = {"market_type": market, "model_side": side, "subject": "HOM",
            "opponent": "AWY", "sport": sport}
    assert language.is_no_side(item) is (which == "no")
    assert resolve._yes_side({"market_type": market, "model_side": side}) is (which == "yes")
    if market in QUANTITY:
        got = shape.blind_probability(
            {"model_prob": 0.6, "model_side": side, "subject": "HOM"},
            {"home": "HOM", "away": "AWY"}, quantity=QUANTITY[market])
        assert got["prob"] == pytest.approx(0.6 if which == "yes" else 0.4)
        assert shape.question_takes_the_proposition(
            {"model_prob": 0.6, "model_side": side, "subject": "HOM"},
            {"home": "HOM", "away": "AWY"}, quantity=QUANTITY[market]) is (which == "yes")


def test_every_side_a_sport_declares_is_placed_on_its_declared_side():
    declared = audit.declared_sides()
    assert ("spread", "fail to cover", "no") in {(m, l, w) for m, l, w, _ in declared}
    assert audit.sides_not_placed(set(), declared) == []
    audit.check_every_side_is_placed()


def test_a_declared_no_side_read_as_the_yes_side_is_caught(monkeypatch):
    """The one place cannot come to read a sport's no side as its yes side:
    every number on it would be turned the wrong way, consistently."""
    monkeypatch.setitem(subjects.SIDES, "spread",
                        dict(subjects.SIDES["spread"], **{"fail to cover": "yes"}))
    faults = audit.sides_not_placed(set(), audit.declared_sides())
    assert any("'fail to cover'" in f and "reads it as the yes side" in f
               for f in faults), faults


def test_the_college_resolver_grades_fail_to_cover_as_the_no_side(tmp_path):
    conn = db.open_db(tmp_path / "graded.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score) VALUES"
        " ('g1', 'cfb', 2026, 20260926, 'REG', 'TLSA', 'UNT',"
        " '2026-09-27T01:00:00Z', 'final', '2026-09-26', 20, 24)")
    conn.commit()

    def pred(side):
        return {"game_id": "g1", "market_type": "spread", "line_asked": 6.5,
                "model_side": side, "subject": "TLSA", "sport": "cfb", "id": 1}

    covered = cfb.resolve_outcome(conn, pred("cover"))
    assert cfb.resolve_outcome(conn, pred("fail to cover")) == 1 - covered
    with pytest.raises(subjects.UnplaceableSide, match="fails to cover"):
        cfb.resolve_outcome(conn, pred("fails to cover"))


# --- 3. an unknown spelling is refused by name -------------------------------

def test_an_unknown_spelling_is_refused_by_name(tmp_path):
    with pytest.raises(subjects.UnplaceableSide, match="'fails to cover'"):
        subjects.side_taken("spread", "fails to cover")
    with pytest.raises(subjects.UnplaceableSide, match="'coin toss'"):
        subjects.side_taken("coin toss", "heads")
    # the claim writer's refusal stays an ordinary, counted outcome
    got = shape.blind_probability(
        {"model_prob": 0.6, "model_side": "fails to cover", "subject": "TLSA"},
        {"home": "TLSA", "away": "UNT"}, quantity="home_margin")
    assert got["prob"] is None and "'fails to cover'" in got["why"]
    # the words refuse it rather than guess the no side
    with pytest.raises(subjects.UnplaceableSide, match="fails to cover"):
        language.is_no_side({"market_type": "spread", "model_side": "fails to cover"})
    # the page refuses it, by name
    conn, pid = _rec_111(tmp_path / "unknown.db", side="fails to cover")
    with pytest.raises(subjects.UnplaceableSide, match="fails to cover"):
        views.week(conn, "cfb", 2026, SLATE)
    # and the gate's check fails on the record that holds it
    with pytest.raises(audit.LawViolation, match="fails to cover"):
        audit.check_every_side_is_placed(conn)


def test_the_api_answers_500_naming_a_side_it_cannot_place(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    path = tmp_path / "api.db"
    conn, _pid = _rec_111(path, side="fails to cover")
    conn.close()
    monkeypatch.setenv(auth.TOKEN_VAR, "test-token-for-the-side-is-placed")
    api.set_database(path)
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": "test-token-for-the-side-is-placed"})
            got = client.get(f"/api/week?sport=cfb&season=2026&week={SLATE}")
            assert got.status_code == 500
            assert "fails to cover" in got.json()["detail"]
            assert "CANNOT BE PLACED" in got.json()["detail"]
    finally:
        api.set_database(None)


def test_each_builder_refuses_a_priced_side_it_cannot_place(tmp_path):
    """None is not False: a priced entry whose side is None is refused by the
    Today card, the board's block, a combo's leg and a recommendation line."""
    conn, pid = _rec_111(tmp_path / "builders.db")
    entry = dict(recommend.for_predictions(conn, [pid])[0],
                 question_takes_the_proposition=None)
    card = next(c for c in views.week(conn, "cfb", 2026, SLATE)["cards"]
                if c["prediction_id"] == pid)
    with pytest.raises(subjects.UnplaceableSide):
        views._today_card(entry, card, taken=False, group_tier=None,
                          unit_dollars=15.0, conn=conn)
    with pytest.raises(subjects.UnplaceableSide):
        board._question_block(card, entry, state="upcoming", taken=False,
                              forecaster="statistical", n_settled=0, hours=3.0,
                              unit_dollars=15.0)
    with pytest.raises(subjects.UnplaceableSide):
        views._combo_block(conn, [card], [entry], "cfb")
    with pytest.raises(subjects.UnplaceableSide):
        views._on_the_question(0.2398, None, what="a number", entry=entry, card=card)
    with pytest.raises(subjects.UnplaceableSide):
        views._edge_side_words("no", None)
    # an unpriced question has nothing to place, and is not refused
    bare = {"prediction_id": pid, "gate_n": 0, "gate": 100, "sport": "cfb",
            "question_takes_the_proposition": None}
    views._today_card(bare, card, taken=False, group_tier=None,
                      unit_dollars=15.0, conn=conn)
    board._question_block(card, None, state="upcoming", taken=False,
                          forecaster="statistical", n_settled=0, hours=3.0,
                          unit_dollars=15.0)


# --- the check ----------------------------------------------------------------

def test_the_check_refuses_a_priced_card_whose_side_cannot_be_placed():
    faults = audit.board_price_side_faults(audit.BOARD_PRICED_FIXTURE_UNPLACED)
    assert faults and "cannot be placed" in faults[0], faults
    with pytest.raises(audit.LawViolation):
        audit.check_the_board_prices_the_side_it_names(
            audit.BOARD_PRICED_FIXTURE_UNPLACED)


def test_the_page_painting_the_other_sides_numbers_is_caught(tmp_path):
    """Rec 111's row painted on Tulsa's numbers -- 24%, 48c, 2.06x -- under
    North Texas, as the released page drew it: named by the check."""
    conn, pid = _rec_111(tmp_path / "painted.db")
    payload = views.week(conn, "cfb", 2026, SLATE)
    block, _card = _block_and_card(payload, pid)
    block.update({"prob": 0.2398, "prob_words": "24%", "price": 0.485,
                  "pays": recommend.payout_multiple(0.485)})
    faults = audit.board_price_side_faults(payload)
    assert any("chance" in f for f in faults) and any("wrong-side" in f for f in faults), faults


# --- a live card's pregame figure --------------------------------------------

def test_a_live_cards_pregame_figure_is_on_the_side_its_question_names(tmp_path):
    """A live card is built from an entry that carried no side, so its pregame
    figure was the claim's proposition's whatever the question named: "BBB to
    win" beside the home side's 43%. Placed from the card's own forecast now."""
    from gridiron import shortlist

    conn = db.open_db(tmp_path / "live.db")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('g0', 'mlb', 2026, 1, 'R', 'AAA', 'BBB',"
        " '2026-09-09T00:00:00Z', 'in', '2026-09-08', 2, 1)")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-07T00:00:00Z', 'mlb', 'g0', 'moneyline', 'AAA', NULL, 0.57,"
        " 'lose', 'statistical', 'final', 'fs2', ?, 'test')", (WHOLE,))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
        " VALUES ('kalshi', 't0', 'e', 'mlb', 'g0', 'moneyline', 'home_win', NULL,"
        " 'home', 0.475, 0.495, '2026-09-07T01:30:00Z')")
    quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', 'g0', 'moneyline', 'home_win', NULL,"
        " 'home', 'line_less', NULL, NULL, 0.43, 0.485, 0.485, 'mid',"
        " '2026-09-07T01:30:00Z')", (pid, quote))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    payload = views.week(conn, "mlb", 2026, 1)
    live = next(c for c in payload["today"]["live"] if c["prediction_id"] == pid)
    assert "BBB" in live["question"], live["question"]
    assert live["pregame_words"] == language.pregame_words(0.57), live["pregame_words"]
    assert live["question_takes_the_proposition"] is False
    row = next(q for g in payload["board"]["games"] for q in g["questions"]
               if q["prediction_id"] == pid)
    assert row["state"] == "live"
    assert row["pregame_words"] == language.pregame_words(0.57)
    # AND THE GATE'S CHECK PASSES THE PLACED LIVE ROW (the prover, 2026-09-30)
    assert audit.board_price_side_faults(payload) == []


# --- the prover's (2026-09-30): three paths the build left open ---------------

def _nfl_world(path, *, market, subject, line, side, predictor, status="final",
               prop_type=None):
    """One NFL game with a well-spelled question of the page's forecaster on it
    (so the row exists) and the question under test, `side` as stored."""
    finished = status == "final"
    conn = db.open_db(path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score) VALUES"
        " ('g1', 'nfl', 2026, 5, 'REG', 'HOM', 'AWY', ?, ?, '2026-09-28', ?, ?)",
        ("2026-09-28T17:00:00Z" if status != "scheduled" else "2099-10-05T17:00:00Z",
         status, 27 if status != "scheduled" else None,
         20 if status != "scheduled" else None))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-28T15:00:00Z', 'nfl', 'g1', 'total', 'AWY @ HOM', 41.5, 0.6,"
        " 'over', 'statistical', 'early', 'fs2', '{}', 'test')")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning, prop_type, outcome,"
        " resolved_utc) VALUES ('2026-09-28T15:00:01Z', 'nfl', 'g1', ?, ?, ?, 0.62,"
        " ?, ?, 'final', 'fs3', '{}', 'test', ?, ?, ?)",
        (market, subject, line, side, predictor, prop_type,
         1 if finished else None, "2026-09-28T21:00:00Z" if finished else None))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    from gridiron import shortlist

    shortlist.rank_rows(conn, [pid - 1, pid])
    return conn, pid


def test_an_empty_stored_side_is_refused_not_said_as_asked(tmp_path):
    """`is_no_side` read `not side`, so a forecast stored with the side '' was
    said as asked and an unpriced card drew the model's number under the yes
    side's words: "over 44.5 total points · 62%" on a side nobody can place.
    Only a question with no side at all (None) is said as asked."""
    with pytest.raises(subjects.UnplaceableSide, match="''"):
        language.is_no_side({"market_type": "total", "model_side": ""})
    assert language.is_no_side({"market_type": "total", "model_side": None}) is False
    for market, subject, line in (("total", "AWY @ HOM", 44.5),
                                  ("spread", "HOM", -3.5), ("moneyline", "HOM", None)):
        conn, _pid = _nfl_world(tmp_path / f"empty-{market}.db", market=market,
                                subject=subject, line=line, side="",
                                predictor="statistical", status="scheduled")
        with pytest.raises(subjects.UnplaceableSide, match="''"):
            views.week(conn, "nfl", 2026, 5)
        conn.close()


def test_the_other_forecasters_prop_on_a_side_it_cannot_place_is_refused(tmp_path):
    """The other forecaster's question on an open row is built from `phrase`
    alone, and its prop branch never asked the one place: "Some Player Over
    55.5 receiving yards · 62%" was drawn, live and finished. Refused now, and
    the declared spellings are drawn as they were."""
    for status in ("in", "final"):
        conn, _pid = _nfl_world(tmp_path / f"prop-{status}.db", market="prop",
                                subject="Some Player receiving_yards", line=55.5,
                                side="Over", predictor="llm", status=status,
                                prop_type="receiving_yards")
        with pytest.raises(subjects.UnplaceableSide, match="'Over'"):
            views.week(conn, "nfl", 2026, 5, forecaster="statistical")
        conn.close()
    conn, pid = _nfl_world(tmp_path / "prop-under.db", market="prop",
                           subject="Some Player receiving_yards", line=55.5,
                           side="under", predictor="llm", status="final",
                           prop_type="receiving_yards")
    payload = views.week(conn, "nfl", 2026, 5, forecaster="statistical")
    row = next(q for g in payload["board"]["games"] for q in g["questions"]
               if q["prediction_id"] == pid)
    assert row["question"] == "Some Player under 55.5 receiving yards"
    assert row["prob_words"] == "62%"


def test_the_check_refuses_a_live_pregame_figure_whose_side_cannot_be_placed():
    """The check walked the priced upcoming blocks only, so a live card
    carrying the claim's pregame chance on an unplaced side passed -- rec 88's
    live row, "Army covers +0.5 · pregame 43%", where Army's own was 57%."""
    faults = audit.board_price_side_faults(audit.BOARD_LIVE_FIXTURE_UNPLACED)
    assert faults and "cannot be placed" in faults[0] and "pregame 43%" in faults[0], faults
    with pytest.raises(audit.LawViolation):
        audit.check_the_board_prices_the_side_it_names(audit.BOARD_LIVE_FIXTURE_UNPLACED)
