"""EVERY NUMBER ON A PICK NAMES THE LINE IT BELONGS TO (pick-number step A,
2026-09-30).

The queue rule as the operator amended it on 30 September: "anything that
could show the operator a wrong number on a pick (side, price, probability,
size) joins the queue first, display or not". The reading recorded in
docs/REPAIR_STATE.md (the conservative default): a number on a pick is
always shown under the words of the exact contract it belongs to -- its line
and its side. Findings 2 and 5 of the wrong-side fix's builder and prover,
the live pregame figure, and operator question 36's default for a claim
priced across two contracts:

  * rec 111 asked "North Texas -6.5" and was priced off "Tulsa by more than
    1.5": its 76% and 51.5c are North Texas +1.5's, and the page said "North
    Texas -6.5" beside them. It says "North Texas +1.5" now, everywhere.
  * the opening read took the venue's main rung ("Under 60.5 total" at 57.5's
    52c); it reads the question's own contract, or names the one it is.
  * a claim stored at -s off an away contract before Q36.1 carries a number
    about one line and a price about another; the page draws none of them
    and says why (recs 114 and 115, written at 18:05Z on 30 September).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from gridiron import audit, board, db, language, recount, shortlist, views  # noqa: F401
from gridiron.market import at_the_line, recommend
from gridiron.priced import coverage

ROOT = Path(__file__).resolve().parents[1]
DIST = {"quantity": "home_margin", "family": "normal", "mean": -9.0, "sd": 14.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})
#: THE DEFAULT'S SENTENCE (docs/REPAIR_STATE.md, 2026-09-30 ~15:30Z), as the
#: page must say it; `language.across_two_contracts_words` is held to it below.
SENTENCE = ("Priced across two contracts before 30 September; no single contract "
            "carries these numbers.")


@pytest.fixture(autouse=True)
def covered(monkeypatch):
    """The coverage list is not what these test: every market is priceable."""
    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market, **_: {
        "priceable": True, "market": market, "why": "covered, in this test"})


NAMES = {"TLSA": ("Tulsa Golden Hurricane", "Golden Hurricane", "Tulsa"),
         "UNT": ("North Texas Mean Green", "Mean Green", "North Texas"),
         "CLE": ("Cleveland Browns", "Browns", "Cleveland"),
         "PIT": ("Pittsburgh Steelers", "Steelers", "Pittsburgh"),
         "NO": ("New Orleans Saints", "Saints", "New Orleans"),
         "ATL": ("Atlanta Falcons", "Falcons", "Atlanta")}

#: kind -> (sport, week, home, away, subject, asked, blind, side,
#:          (ticker, contract line, contract side, bid, ask),
#:          (claim line, model number, implied))
SHAPES = {
    # rec 111: "TLSA covers +6.5", fail to cover (North Texas), priced off
    # the home contract "Tulsa wins by over 1.5"
    "rec111": ("cfb", 20261001, "TLSA", "UNT", "TLSA", 6.5, 0.626036, "fail to cover",
               ("tTLSA2", -1.5, "home", 0.475, 0.495), (-1.5, 0.2398, 0.485)),
    # rec 114: "CLE covers +0.5", not_cover (Pittsburgh), its claim stored
    # at -2.5 off "Pittsburgh wins by over 2.5" (which sells +2.5)
    "rec114": ("nfl", 4, "CLE", "PIT", "CLE", 0.5, 0.561059, "not_cover",
               ("tPIT3", 2.5, "away", 0.515, 0.535), (-2.5, 0.3834, 0.475)),
    # rec 117: "NO covers -9.5", not_cover (Atlanta), priced off the home
    # contract "New Orleans wins by over 2.5"; the recommendation buys New
    # Orleans -2.5, the other side of the words
    "rec117": ("nfl", 4, "NO", "ATL", "NO", -9.5, 0.577186, "not_cover",
               ("tNO3", -2.5, "home", 0.505, 0.525), (-2.5, 0.6848, 0.515)),
}


def _world(path, kind, *, live=False, final=None):
    """`final` (step A's prover): the game finished at (home score, away
    score), the forecast and its claim settled on it."""
    sport, week, home, away, subject, asked, blind, side, quote, claim = SHAPES[kind]
    conn = db.open_db(path)
    status, kickoff, score = (("in", "2026-09-30T00:00:00Z", (7, 10)) if live
                              else ("final", "2026-09-29T01:00:00Z", final) if final
                              else ("scheduled", "2099-10-02T01:00:00Z", (None, None)))
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('g1', ?, 2026, ?, 'REG', ?, ?, ?, ?, '2026-10-01', ?, ?)",
        (sport, week, home, away, kickoff, status, *score))
    for code in (home, away):
        full, short, city = NAMES[code]
        conn.execute(
            "INSERT INTO teams (sport, tricode, display_name, short_name, location,"
            " source_url, fetched_utc) VALUES (?, ?, ?, ?, ?, 'test',"
            " '2026-09-01T00:00:00Z')", (sport, code, full, short, city))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-28T15:00:00Z', ?, 'g1', 'spread', ?, ?, ?, ?, 'statistical',"
        " 'final', 'fs2', ?, 'test')", (sport, subject, asked, blind, side, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    ticker, line, yes_side, bid, ask = quote
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
        " VALUES ('kalshi', ?, 'e', ?, 'g1', 'spread', 'home_margin', ?, ?, ?, ?,"
        " '2026-09-28T15:00:44Z')", (ticker, sport, line, yes_side, bid, ask))
    quote_id = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    claim_line, model, implied = claim
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', ?, 'g1', 'spread', 'home_margin', ?, 'home',"
        " 'rung_differs_margin', -9.0, 14.0, ?, ?, ?, 'mid',"
        " '2026-09-28T15:00:45Z')",
        (pid, quote_id, sport, claim_line, model, round((bid + ask) / 2, 4), implied))
    if final:
        # SETTLED AS THE RESOLVERS SETTLE THEM: the forecast's side on the
        # question's line, the claim's proposition (the home side) at its own
        from gridiron.model import questions

        home_score, away_score = final
        covers = questions.spread_outcome(home_score, away_score, asked)
        took_yes = side == "cover"
        conn.execute("UPDATE predictions SET resolved_utc = '2026-09-29T05:00:00Z',"
                     " outcome = ? WHERE id = ?", (int(covers == took_yes), pid))
        conn.execute("UPDATE at_the_line_claims SET resolved_utc = '2026-09-29T05:00:00Z',"
                     " outcome = ? WHERE prediction_id = ?",
                     (questions.spread_outcome(home_score, away_score, claim_line), pid))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    return conn, pid, sport, week


def _open_world(path, *, listed=True):
    """"under 60.5 total points" on UNT at TLSA, no claim, and an opening
    ladder whose rung nearest an even chance is over 57.5 (48.5c), the
    question's own over 60.5 at 41.5c listed or not."""
    conn = db.open_db(path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g1', 'cfb', 2026, 20261001,"
        " 'REG', 'TLSA', 'UNT', '2099-10-02T01:00:00Z', 'scheduled', '2026-10-01')")
    for code in ("TLSA", "UNT"):
        full, short, city = NAMES[code]
        conn.execute(
            "INSERT INTO teams (sport, tricode, display_name, short_name, location,"
            " source_url, fetched_utc) VALUES ('cfb', ?, ?, ?, ?, 'test',"
            " '2026-09-01T00:00:00Z')", (code, full, short, city))
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('2026-09-28T15:00:00Z', 'cfb', 'g1', 'total', 'UNT @ TLSA', 60.5, 0.66,"
        " 'under', 'statistical', 'final', 'fs2', '{\"coverage\": 1.0}', 'test')")
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    rungs = [(57.5, 0.475, 0.495), (63.5, 0.34, 0.36)] + (
        [(60.5, 0.405, 0.425)] if listed else [])
    for line, bid, ask in rungs:
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
            " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc,"
            " read_kind) VALUES ('kalshi', ?, 'e', 'cfb', 'g1', 'total', 'total', ?,"
            " 'over', ?, ?, '2026-09-29T12:00:00Z', 'open')",
            (f"tOVER{line:g}", line, bid, ask))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    return conn, pid


def _blocks(payload, pid):
    return [q for g in payload["board"]["games"]
            for q in ([g["pick"]] if g.get("pick") else []) + g["questions"]
            if q["prediction_id"] == pid]


def _card(payload, pid, groups=("clears", "below_floor", "watching", "live")):
    return next((c for group in groups for c in payload["today"].get(group) or []
                 if c["prediction_id"] == pid), None)


def _faults(conn, payload):
    return audit.number_line_faults(payload, audit.pick_contracts(conn, payload))


# --- rec 111: the venue's contract, its numbers, its words ---------------------

def test_rec_111_reads_north_texas_plus_1_5_with_its_own_numbers(tmp_path):
    """"North Texas +1.5 · 76% · 51.5c" on the row, the tile, the Today card
    and the recommendation line -- the contract the numbers belong to -- and
    beside the chance, what the model was asked: North Texas -6.5, 63%."""
    conn, pid, sport, week = _world(tmp_path / "rec111.db", "rec111")
    payload = views.week(conn, sport, 2026, week)
    blocks = _blocks(payload, pid)
    assert len(blocks) == 2       # the row's pick and its tile
    for block in blocks:
        assert block["line_words"] == "North Texas +1.5"
        assert block["question"] == "North Texas covers +1.5"
        assert block["prob_words"] == "76%"
        assert block["price"] == pytest.approx(0.515)
        assert block["pays"] == pytest.approx(1.942)
        assert "The model was asked about North Texas -6.5 and gives it 63%" \
            in block["tips"]["prob"]
    card = _card(payload, pid)
    assert card["question"] == "North Texas covers +1.5"
    assert card["line_words"] == "North Texas +1.5"
    assert card["words_line_asked"] == pytest.approx(-1.5)
    assert card["model_words"] == "76¢" and card["venue_words"] == "52¢ · pays 1.94x"
    assert card["asked_words"] == ("The model was asked about North Texas -6.5 and "
                                   "gives it 63%.")
    line = next(x for x in payload["recommendations"]["lines"] if x["prediction_id"] == pid)
    assert line["side_words"] == "North Texas covers +1.5"
    assert line["words"].startswith("North Texas covers +1.5 — the model makes it 76¢, "
                                    "the venue is at 52¢")
    assert _faults(conn, payload) == []
    assert audit.pick_side_faults(payload) == []
    assert audit.board_price_side_faults(payload) == []


def test_the_released_words_beside_those_numbers_are_named(tmp_path):
    conn, pid, sport, week = _world(tmp_path / "rec111.db", "rec111")
    payload = views.week(conn, sport, 2026, week)
    for block in _blocks(payload, pid):
        block["line_words"] = "North Texas -6.5"
    _card(payload, pid)["question"] = "North Texas covers -6.5"
    for line in payload["recommendations"]["lines"]:
        line["side_words"] = "North Texas covers -6.5"
    faults = _faults(conn, payload)
    for where in ("board.games", "today.clears", "recommendations.lines"):
        assert any(f.startswith(where) and "another line" in f for f in faults), where
    with pytest.raises(audit.LawViolation, match="ANOTHER LINE"):
        audit.check_every_number_names_its_line(conn, payload)


def test_the_live_figure_names_its_claims_line(tmp_path):
    conn, pid, sport, week = _world(tmp_path / "live.db", "rec111", live=True)
    payload = views.week(conn, sport, 2026, week)
    card = _card(payload, pid, groups=("live",))
    assert card["question"] == "North Texas covers +1.5"
    assert card["pregame_words"] == "pregame 76%"
    assert [(b["line_words"], b["pregame_words"]) for b in _blocks(payload, pid)] \
        == [("North Texas +1.5", "pregame 76%")] * 2
    assert _faults(conn, payload) == []
    for block in _blocks(payload, pid):
        block["line_words"] = "North Texas -6.5"
    assert any("another line" in f for f in _faults(conn, payload))


# --- a claim priced across two contracts (operator question 36) ----------------

def test_a_claim_priced_across_two_contracts_draws_none_of_its_numbers(tmp_path):
    """Rec 114's shape: no chance of the claim, no price, payout, edge or
    size, no outline -- the model's own 56% for Pittsburgh -0.5 -- and the
    sentence saying why; no recommendation line, counted by that reason; the
    at-the-line sentence states the model's number at its own line alone."""
    assert language.across_two_contracts_words() == SENTENCE
    conn, pid, sport, week = _world(tmp_path / "rec114.db", "rec114")
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["priced_across_two_contracts"] is True
    assert entry["side"] is not None, "the writer's entry is as it was"
    payload = views.week(conn, sport, 2026, week)
    for block in _blocks(payload, pid):
        assert block["line_words"] == "Pittsburgh -0.5"
        assert block["prob_words"] == "56%"
        assert block["price"] is None and block["pays"] is None
        assert not block.get("size_words") and not block.get("edge_words")
        assert block["signal"] == "none"
        assert block["across_words"] == SENTENCE
        assert block["price_words"] == "no single contract"
        assert "wrong sign" in block["tips"]["price"]
    card = _card(payload, pid)
    assert card in payload["today"]["watching"]
    assert card["across_words"] == SENTENCE and card.get("fair_value") is None
    recs = payload["recommendations"]
    assert recs["lines"] == [] and recs["across"] == 1
    assert "priced across two contracts before 30 September" in recs["empty_words"]
    beside = next(c["at_the_line"] for c in payload["cards"] if c["prediction_id"] == pid)
    assert beside["venue_implied"] is None and "implies" not in beside["words"]
    # the home side at the claim's own stored line, as the sentence names it
    assert "Browns covering -2.5" in beside["words"]
    assert _faults(conn, payload) == []


def test_a_claim_across_two_contracts_drawn_priced_or_silent_is_named(tmp_path):
    conn, pid, sport, week = _world(tmp_path / "rec114.db", "rec114")
    priced = views.week(conn, sport, 2026, week)
    for block in _blocks(priced, pid):
        block["priced"] = True
    assert any("priced across two contracts" in f for f in _faults(conn, priced))
    silent = views.week(conn, sport, 2026, week)
    for block in _blocks(silent, pid):      # the pick is one of the row's tiles
        block.pop("across_words", None)
    assert any("without the sentence" in f for f in _faults(conn, silent))


def test_a_live_figure_off_a_claim_across_two_contracts_is_the_questions_own(tmp_path):
    conn, pid, sport, week = _world(tmp_path / "live114.db", "rec114", live=True)
    payload = views.week(conn, sport, 2026, week)
    card = _card(payload, pid, groups=("live",))
    assert card["question"] == "Pittsburgh covers -0.5"
    assert card["pregame_words"] == "pregame 56%"
    assert card["across_words"] == SENTENCE
    assert _faults(conn, payload) == []


# --- the opening read (finding 5) ------------------------------------------------

def test_the_opening_read_is_the_questions_own_rung(tmp_path):
    conn, pid = _open_world(tmp_path / "open.db")
    payload = views.week(conn, "cfb", 2026, 20261001)
    card = _card(payload, pid)
    assert card["venue_words"] == "58¢ · pays 1.71x"
    assert card["open_read_line"] == pytest.approx(60.5)
    assert card["open_read_price"] == pytest.approx(0.585)
    assert "open_read_line_words" not in card
    assert all("1.71 times" in b["tips"]["pays"] for b in _blocks(payload, pid))
    assert _faults(conn, payload) == []
    # the released read, the main rung under the question's words, is named
    card.update({"payout": 1.942, "venue_words": "52¢ · pays 1.94x"})
    card.pop("open_read_line")
    card.pop("open_read_price")
    assert any("another rung under the question's words" in f
               for f in _faults(conn, payload))


def test_an_opening_read_at_another_rung_names_the_contract(tmp_path):
    conn, pid = _open_world(tmp_path / "open.db", listed=False)
    payload = views.week(conn, "cfb", 2026, 20261001)
    card = _card(payload, pid)
    assert card["open_read_line_words"] == "Under 57.5 total"
    assert card["venue_words"] == "Under 57.5 total opened at 52¢ · pays 1.94x"
    assert card["payout_words"] == "1.94x on Under 57.5 total"
    assert card["question"] == "under 60.5 total points"
    for block in _blocks(payload, pid):
        assert "At Under 57.5 total a dollar returns 1.94 times" in block["tips"]["pays"]
    assert _faults(conn, payload) == []
    card.pop("open_read_line_words")
    card["venue_words"] = "52¢ · pays 1.94x"
    assert any("must name the contract" in f for f in _faults(conn, payload))


# --- the edge's side at the claim's line (step C's hold on spreads) ----------------

def test_a_spread_tile_names_the_other_side_of_its_claims_contract(tmp_path):
    """Rec 117's shape at the claim's line (-2.5). Until operator question 37
    was ruled (2026-10-05) the words named Atlanta at that line (Atlanta
    +2.5) and the edge -- New Orleans -2.5's, the side bought -- said it was
    the other side's, beside New Orleans -2.5's size and outline. The ruling
    ("headline the contract the recommendation buys; the model's own side
    named beside it"): the row and the tile name New Orleans -2.5, at the
    claim's line, with its own edge drawn bare, and Atlanta +2.5 beside it;
    the recommendation line names New Orleans -2.5 as before."""
    conn, pid, sport, week = _world(tmp_path / "rec117.db", "rec117")
    payload = views.week(conn, sport, 2026, week)
    for block in _blocks(payload, pid):
        assert block["line_words"] == "New Orleans -2.5"
        assert not block["edge_words"].endswith("on the other side")
        assert block["own_side_words"] == "The model's own side: Atlanta +2.5, 32%"
    line = next(x for x in payload["recommendations"]["lines"] if x["prediction_id"] == pid)
    assert line["words"].startswith("New Orleans covers -2.5 — the model makes it 68¢")
    assert _faults(conn, payload) == []
    assert audit.pick_side_faults(payload) == []
    assert audit.combo_side_faults(payload) == []
    assert audit.headline_faults(payload) == []


# --- the taken rail ---------------------------------------------------------------

def test_the_taken_rail_names_its_recommendations_contract(tmp_path):
    conn, pid, sport, week = _world(tmp_path / "rec111.db", "rec111")
    assert recommend.record_for(conn, [pid])["recommended"] == 1
    conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                 (pid, db.utcnow()))
    conn.commit()
    payload = views.week(conn, sport, 2026, week)
    words = payload["today"]["taken_today"]["entries"][0]["words"]
    assert words.startswith("North Texas covers +1.5 · +")
    assert _faults(conn, payload) == []
    across, pid2, sport2, week2 = _world(tmp_path / "rec114.db", "rec114")
    # THE WRITER WRITES NONE FROM A CLAIM PRICED ACROSS TWO CONTRACTS (operator
    # ruling A.2, 2026-10-05: such a claim is excluded from every price
    # comparison, and a recommendation is one), and counts it by that name --
    # so rec 114 is written here as the released writer wrote it on 30
    # September, from the same entry, which is what the rail reads.
    got = recommend.record_for(across, [pid2])
    assert got["recommended"] == 0 and got["across_two_contracts"] == 1
    entry = recommend.for_predictions(across, [pid2])[0]
    across.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market, side,"
        " fair_value, price, edge_cents, size_kind, size_units, gate_n, created_utc)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (pid2, entry["sport"], entry["game_id"], entry["market"], entry["side"],
         entry["raw_fair_value"], entry["price"], entry["edge_cents"],
         entry["size"]["kind"], entry["size"]["units"], entry["gate_n"],
         db.utcnow()))
    across.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                   (pid2, db.utcnow()))
    across.commit()
    payload = views.week(across, sport2, 2026, week2)
    words = payload["today"]["taken_today"]["entries"][0]["words"]
    assert words == "Pittsburgh covers -0.5 · no single contract carries its edge"
    assert _faults(across, payload) == []


# --- the one door, and what it refuses --------------------------------------------

def test_the_door_refuses_a_claims_numbers_without_a_line(tmp_path):
    card = {"prediction_id": 1, "market_type": "spread", "subject": "TLSA",
            "opponent": "UNT", "line_asked": 6.5, "model_side": "fail to cover",
            "phrase": "North Texas covers -6.5"}
    with pytest.raises(language.LineNotNamed):
        views._the_contract({"prediction_id": 1, "claim_id": 7}, card)
    with pytest.raises(language.LineNotNamed):
        board._question_block(
            card, {"price": 0.485, "fair_value": 0.2398,
                   "question_takes_the_proposition": False},
            state="upcoming", taken=False, forecaster="statistical", n_settled=0,
            hours=3.0, unit_dollars=None)
    # the question's own numbers need no line: nothing moves
    got = views._the_contract(None, card)
    assert got["moved"] is False and got["words"] == "North Texas covers -6.5"


def test_the_words_move_to_the_numbers_never_the_numbers_to_the_words():
    home = {"market_type": "spread", "subject": "TLSA", "opponent": "UNT",
            "line_asked": 6.5, "model_side": "fail to cover", "sport": "cfb",
            "team_names": {"UNT": {"city": "North Texas"}, "TLSA": {"city": "Tulsa"}}}
    moved = language.at_the_contract(home, -1.5, home="TLSA")
    assert moved["line_asked"] == -1.5 and language.tile_line(moved) == "North Texas +1.5"
    away = dict(home, subject="UNT", opponent="TLSA", line_asked=-6.5, model_side="cover")
    moved = language.at_the_contract(away, -1.5, home="TLSA")
    assert moved["line_asked"] == 1.5 and language.tile_line(moved) == "North Texas +1.5"
    total = {"market_type": "total", "line_asked": 60.5, "model_side": "under",
             "subject": "UNT @ TLSA", "sport": "cfb"}
    assert language.tile_line(language.at_the_contract(total, 57.5, home="TLSA")) \
        == "Under 57.5 total"
    winner = {"market_type": "moneyline", "subject": "TLSA", "opponent": "UNT"}
    assert language.at_the_contract(winner, None, home="TLSA") is winner
    assert language.at_the_contract(home, 6.5, home="TLSA") is home
    with pytest.raises(language.LineNotNamed):
        language.at_the_contract(home, -1.5, home="ELSE")


def test_a_claim_is_across_two_contracts_only_where_its_line_is_not_the_line_sold():
    home = {"line": -1.5, "yes_side": "home"}
    away = {"line": 2.5, "yes_side": "away"}
    assert at_the_line.priced_across_two_contracts(-1.5, home) is False
    assert at_the_line.priced_across_two_contracts(2.5, away) is False
    assert at_the_line.priced_across_two_contracts(-2.5, away) is True
    assert at_the_line.priced_across_two_contracts(None, {"line": None,
                                                          "yes_side": "home"}) is False
    assert at_the_line.priced_across_two_contracts(-1.5, None) is False


def test_rung_at_reads_the_contract_selling_the_line():
    def q(line, side, bid, ask):
        return {"line": line, "yes_side": side, "yes_bid": bid, "yes_ask": ask,
                "last_price": None}
    ladder = [q(-1.5, "home", 0.475, 0.495), q(6.5, "away", 0.28, 0.30),
              q(-6.5, "home", 0.30, 0.32)]
    got = at_the_line.rung_at(ladder, 6.5)
    assert got["line"] == 6.5 and got["implied"] == pytest.approx(0.71)
    assert at_the_line.rung_at(ladder, 3.5) is None
    assert at_the_line.rung_at([q(6.5, "away", None, None)], 6.5) is None
    assert at_the_line.rung_for(ladder)["line"] == -1.5


# --- the gate ------------------------------------------------------------------------

def test_the_gate_makes_the_call_and_its_scanner_can_see():
    gate = ROOT / "tools" / "verify.py"
    step = next(node for node in ast.parse(gate.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert any(isinstance(node, ast.Attribute)
               and node.attr == "check_every_number_names_its_line"
               for node in ast.walk(step))
    assert audit.number_line_faults(audit.NUMBER_LINE_FIXTURE_GOOD,
                                    audit.NUMBER_LINE_CONTRACTS) == []
    for name, change in audit.NUMBER_LINE_FIXTURES_AS_RELEASED.items():
        assert audit.number_line_faults(audit._number_line_fixture(**change),
                                        audit.NUMBER_LINE_CONTRACTS), name


# --- STEP A'S PROVER (2026-09-30) -----------------------------------------------------
#
# Found on one verified copy of the record, each on the build as first written:
# a finished game's card, still priced, stated the QUESTION's figure and verdict
# under the claim's contract's words ("New York covers +6.5 · 30c · the model had
# this at 67% and it happened", where New York did not cover +6.5); a card whose
# words moved still carried the forecast's own numbers line and why block bare;
# and the check demanded the sentence of a live tile drawing the question's own
# figure with no Today card (196 on the record's finished slates read as live).

def test_a_finished_cards_figure_and_verdict_are_its_contracts(tmp_path):
    """Rec 111's shape, finished TLSA 20 UNT 23: North Texas +1.5 happened
    (the claim, Tulsa -1.5, settled no) and North Texas -6.5 did not. The
    card names North Texas +1.5 at 76%, so its verdict is that contract's;
    the board's finished row is the question's own, as it was."""
    conn, pid, sport, week = _world(tmp_path / "final.db", "rec111", final=(20, 23))
    payload = views.week(conn, sport, 2026, week)
    card = _card(payload, pid, groups=("clears", "below_floor", "watching"))
    assert card["state"] == "final"
    assert card["question"] == "North Texas covers +1.5" and card["model_words"] == "76¢"
    assert card["settled_words"] == "the model had this at 76% and it happened"
    assert _faults(conn, payload) == []
    for block in _blocks(payload, pid):
        assert block["line_words"] == "North Texas -6.5"
        assert block["settled_words"] == "the model had this at 63% and it did not"
    # as first built: the question's figure and verdict under the contract's words
    card["settled_words"] = "the model had this at 63% and it did not"
    faults = _faults(conn, payload)
    assert any("is finished and says" in f for f in faults), faults
    with pytest.raises(audit.LawViolation, match="ANOTHER LINE"):
        audit.check_every_number_names_its_line(conn, payload)


def test_the_forecasts_own_sentences_name_its_question_beside_moved_words(tmp_path):
    """The numbers line and the why block are the forecast's, about North
    Texas -6.5; beside "North Texas covers +1.5" each names that question."""
    conn, pid, sport, week = _world(tmp_path / "rec111.db", "rec111")
    payload = views.week(conn, sport, 2026, week)
    card = _card(payload, pid)
    assert card["rail_line"].startswith(
        "For North Texas -6.5, as the model was asked: The model says 63%.")
    assert card["why"]["heading"] == "Why North Texas -6.5, as the model was asked"
    slate = next(c for c in payload["cards"] if c["prediction_id"] == pid)
    assert slate["rail_line"].startswith("The model says 63%.")
    assert slate["why"]["heading"] == "Why North Texas", "the slate's own card is as it was"
    assert _faults(conn, payload) == []
    for field, bare in (("rail_line", slate["rail_line"]), ("why", slate["why"])):
        planted = json.loads(json.dumps(payload))
        _card(planted, pid)[field] = bare
        assert any(f"carries its {'why heading' if field == 'why' else field}" in f
                   for f in _faults(conn, planted)), field
    # a card whose words are the question's own keeps both as they were
    unmoved, pid2, sport2, week2 = _world(tmp_path / "rec114.db", "rec114")
    card2 = _card(views.week(unmoved, sport2, 2026, week2), pid2)
    assert card2["why"]["heading"] == "Why Pittsburgh"


def test_an_across_rows_payout_slot_says_it_is_not_shown(tmp_path):
    """Rec 114's tile drew "56% · no single contract | not recorded": its
    payout slot was left empty, and a tile draws an empty payout as "not
    recorded" -- false, the venue's price was recorded. The slot says the
    payout is not shown; the sentence and the tooltip say why."""
    conn, pid, sport, week = _world(tmp_path / "rec114.db", "rec114")
    payload = views.week(conn, sport, 2026, week)
    blocks = _blocks(payload, pid)
    assert blocks
    for block in blocks:
        assert block["price_words"] == "no single contract"
        assert block["pays_words"] == "not shown"
        assert "wrong sign" in block["tips"]["pays"]
    assert _faults(conn, payload) == []
    for block in blocks:
        block["pays_words"] = ""
    assert any("an empty slot is drawn 'not recorded'" in f for f in _faults(conn, payload))


def test_a_live_rows_reasons_name_the_question_first(tmp_path):
    """Rec 111's shape under way: the row names North Texas +1.5 with its
    claim's pregame 76%, and its reasons -- the forecast's, of North Texas
    -6.5 -- say which question they are about first, as an upcoming row's
    do (as first built a live row's did not)."""
    conn, pid, sport, week = _world(tmp_path / "live.db", "rec111", live=True)
    payload = views.week(conn, sport, 2026, week)
    blocks = _blocks(payload, pid)
    assert blocks and all(b["line_words"] == "North Texas +1.5" for b in blocks)
    for block in blocks:
        assert block["tips"]["line"].startswith(
            "The model was asked about North Texas -6.5 and gives it 63%.")
    assert _faults(conn, payload) == []
    asked = "The model was asked about North Texas -6.5 and gives it 63%."
    for block in blocks:            # the row's pick is one of its tiles
        block["tips"]["line"] = block["tips"]["line"].replace(asked, "").strip()
    assert any("the reasons" in f and "without naming it" in f
               for f in _faults(conn, payload))


def test_a_live_tile_with_no_today_card_needs_no_sentence(tmp_path, monkeypatch):
    """Rec 114's shape, live and off the shortlist: no Today card, so the
    tile draws the question's own pregame 56% under its own words -- what the
    default asks of a figure off a claim priced across two contracts -- and
    the check names nothing (as first built it demanded the sentence). The
    other forecaster's question on an open row is the same shape."""
    conn, pid, sport, week = _world(tmp_path / "live.db", "rec114", live=True)
    monkeypatch.setattr(shortlist, "choose", lambda conn_, sport_, ids: {
        "shortlist": [], "rest": list(ids), "cap": 20, "ranked": True})
    payload = views.week(conn, sport, 2026, week)
    assert _card(payload, pid, groups=("live",)) is None
    blocks = _blocks(payload, pid)
    assert blocks and all((b["line_words"], b["pregame_words"])
                          == ("Pittsburgh -0.5", "pregame 56%") for b in blocks)
    assert all(not b.get("across_words") for b in blocks)
    assert _faults(conn, payload) == []
    # the question's figure under the claim's words is still named
    for block in blocks:
        block["line_words"] = "Pittsburgh -2.5"
    assert any("another line" in f for f in _faults(conn, payload))


def test_an_opening_read_of_a_contract_read_twice_in_one_look_is_either_read(tmp_path):
    """A look holds some tickers written twice at two prices (DET7 at 54.5c
    and 53.5c in one NFL week-1 look). The page reads the first it meets;
    the check holds the read to the contract, never to the order of an
    unordered read."""
    conn, pid = _open_world(tmp_path / "open.db")
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc, read_kind)"
        " VALUES ('kalshi', 'tOVER60.5', 'e', 'cfb', 'g1', 'total', 'total', 60.5,"
        " 'over', 0.395, 0.405, '2026-09-29T12:00:00Z', 'open')")
    conn.commit()
    payload = views.week(conn, "cfb", 2026, 20261001)
    card = _card(payload, pid)
    assert card["open_read_line"] == pytest.approx(60.5)
    assert _faults(conn, payload) == []
    for price in (0.585, 0.6):                  # either read of Under 60.5
        card["open_read_price"] = price
        assert _faults(conn, payload) == [], price
    card["open_read_price"] = 0.515             # the 57.5 rung's, as released
    assert any("another rung under the question's words" in f
               for f in _faults(conn, payload))
