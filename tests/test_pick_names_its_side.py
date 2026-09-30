"""Every pick names its own side: the payout, the recommendation line, My day.

Pick-number step C (2026-09-30), under the queue rule as amended that day:
"anything that could show the operator a wrong number on a pick (side, price,
probability, size) joins the queue first, display or not" -- and the reading
recorded in docs/REPAIR_STATE.md: a number on a pick is always stated under
the words of the exact contract it belongs to, its line and its side.

Three places stated a pick's side, or a number of it, under another side's
words (the wrong-side fix's builder and prover, 2026-09-30):

  3. the Today card's `payout` and `payout_words` were what the claim's fixed
     proposition pays -- the home side, the over -- while the chips beside
     them were turned to the side the question names;
  4. `recommendations.lines[].words` put the proposition's number and price
     after the question's words and called the side bought "the yes side" or
     "the other side";
  6. My day's chip wore the club of the question's SUBJECT -- the home club
     -- so a taken "not_cover" on PHI -3.5 read "PHI · DAL +3.5".

And from the sweep: the payout floor read the proposition's payout whatever
side a pick buys, and a moneyline "lose" with no opponent recorded was said
"PHI to win".
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from gridiron import audit, db, language, settings, shortlist, subjects, views
from gridiron.market import recommend

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def covered(monkeypatch):
    """The coverage list is not what these tests are about (test_recommend's
    reason): every market is priceable here."""
    from gridiron.priced import coverage

    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market, **_: {
        "priceable": True, "market": market, "why": "covered, in this test"})


def _priced_world(tmp_path, *, price=0.485, confidence=0.57):
    """test_recommend's world: the away side (BBB) at `confidence`, so a claim
    of one minus it on the home side (AAA), against a home price of
    `price`."""
    from tests import test_recommend as rec

    conn = rec._world(tmp_path, kickoff="2099-01-01T00:00:00Z")
    pid = rec._away_pick(conn, price=price, confidence=confidence)
    return conn, pid


def _today_card(payload, pid):
    return next(c for group in ("clears", "below_floor", "watching")
                for c in payload["today"][group] if c["prediction_id"] == pid)


def _line(payload, pid):
    return next(line for line in payload["recommendations"]["lines"]
                if line["prediction_id"] == pid)


# --- 3: the Today card's payout ------------------------------------------------

def test_the_today_cards_payout_is_what_its_questions_side_pays(tmp_path, covered):
    """The question names the away side (BBB to win); the claim's fixed
    proposition is the home side at 48.5c. The card's chip and venue words
    were turned -- "52¢ · pays 1.94x" -- and its payout and payout words said
    2.062 and "2.06x", the home side's (pick-number finding 3)."""
    conn, pid = _priced_world(tmp_path)
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["question_takes_the_proposition"] is False
    assert entry["payout"] == recommend.payout_multiple(0.485) == 2.062
    payload = views.week(conn, "mlb", 2026, 1)
    card = _today_card(payload, pid)
    assert card["venue_words"] == "52¢ · pays 1.94x", card["venue_words"]
    assert card["payout"] == recommend.payout_multiple(1.0 - 0.485) == 1.942
    assert card["payout_words"] == "1.94x"
    assert audit.pick_side_faults(payload) == []
    # AS RELEASED: the proposition's payout on the turned card.
    card.update({"payout": 2.062, "payout_words": "2.06x"})
    faults = audit.pick_side_faults(payload)
    assert any("finding 3" in f and "2.062" in f for f in faults), faults
    with pytest.raises(audit.LawViolation, match="ANOTHER SIDE'S NUMBER"):
        audit.check_every_pick_names_its_side(payload)


def test_a_card_naming_the_proposition_keeps_its_own_payout(tmp_path, covered):
    """A question naming the proposition's own side (the home club, AAA, to
    win at 62% against 46c) is not turned, and its payout is the entry's,
    unchanged: nothing moves that was right."""
    from tests import test_recommend as rec

    conn = rec._world(tmp_path, kickoff="2099-01-01T00:00:00Z")
    pid = rec._pick(conn, prob=0.62, implied=0.46, subject="AAA", market="moneyline")
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["question_takes_the_proposition"] is True
    payload = views.week(conn, "mlb", 2026, 1)
    card = _today_card(payload, pid)
    assert card["payout"] == entry["payout"] == recommend.payout_multiple(0.46)
    assert card["payout_words"] == "2.17x"
    assert audit.pick_side_faults(payload) == []


# --- 4: the recommendation line ------------------------------------------------

def test_a_recommendation_line_states_the_side_it_buys_with_its_numbers(tmp_path, covered):
    """The recommendation buys the away side (the no side of the home
    proposition), the side the question's words name. The line read "BBB to
    win -- the model makes it 43¢, the venue is at 48¢, and the other side is
    worth +3.5¢": the home side's number and price after the away side's
    words, and a side called "the other side" (pick-number finding 4)."""
    conn, pid = _priced_world(tmp_path)
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["side"] == "no" and entry["question_takes_the_proposition"] is False
    payload = views.week(conn, "mlb", 2026, 1)
    line = _line(payload, pid)
    assert line["side_words"] == "BBB to win"
    assert line["fair_value"] == pytest.approx(0.57)
    assert line["price"] == pytest.approx(0.515)
    assert line["words"].startswith(
        "BBB to win — the model makes it 57¢, the venue is at 52¢, and it is "
        "worth +3.5¢ a contract after the fee."), line["words"]
    assert "the yes side" not in line["words"] and "the other side" not in line["words"]
    # THE LINE AND ITS CARD SAY ONE PRICE (a half-cent rounded one way).
    card = _today_card(payload, pid)
    assert card["price_words"].startswith("52¢")
    assert audit.pick_side_faults(payload) == []
    # AS RELEASED.
    line["words"] = ("BBB to win — the model makes it 43¢, the venue is at 48¢, "
                     "and the other side is worth +3.5¢ a contract after the fee.")
    faults = audit.pick_side_faults(payload)
    assert any("'the other side'" in f for f in faults), faults


def test_a_recommendation_that_buys_the_other_side_of_its_words_names_it(tmp_path, covered):
    """The price can make the side the model did not take the one worth
    buying: here the model's side is the away club at 57% and the home side
    costs 30c, worth 43% -- the recommendation buys the home side. Recs 47 and
    82 on the record did this (the model's "Washington covers +1.5", bought
    Detroit -1.5 at 37.5c). The line names the side it buys, AAA, with AAA's
    number and price."""
    conn, pid = _priced_world(tmp_path, price=0.30)
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["side"] == "yes" and entry["question_takes_the_proposition"] is False
    payload = views.week(conn, "mlb", 2026, 1)
    line = _line(payload, pid)
    assert line["side_words"] == "AAA to win"
    assert line["fair_value"] == pytest.approx(0.43)
    assert line["price"] == pytest.approx(0.30)
    assert line["words"].startswith(
        "AAA to win — the model makes it 43¢, the venue is at 30¢"), line["words"]
    assert audit.pick_side_faults(payload) == []
    # THE QUESTION'S WORDS BESIDE THE SIDE BOUGHT'S NUMBERS ARE NAMED.
    line["side_words"] = "BBB to win"
    line["words"] = line["words"].replace("AAA to win", "BBB to win", 1)
    faults = audit.pick_side_faults(payload)
    assert any("'AAA to win'" in f and "finding 4" in f for f in faults), faults


def test_the_line_takes_the_words_it_is_handed():
    line = language.recommendation_line(
        words="Detroit covers -1.5", fair_value=0.4156, price=0.375,
        edge_cents=2.06, units=1.0, flat=True, size_why="no measured edge yet")
    assert line.startswith("Detroit covers -1.5 — the model makes it 42¢, the "
                           "venue is at 38¢, and it is worth +2.1¢")
    assert audit.advice_word_faults(line) == []
    assert audit.plain_words_violations(line) == []


# --- 6: My day -----------------------------------------------------------------

def _nfl_world(path, taken):
    """Two NFL games -- PHI at home to DAL (g1), NYG at home to WAS (g2) --
    and the questions in `taken`, each (game, market, line, side), every one
    tapped. One question per game and market: the record keys a question by
    its game, market, subject, forecaster, factor set and pass."""
    conn = db.open_db(path)
    for gid, home, away in (("g1", "PHI", "DAL"), ("g2", "NYG", "WAS")):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'nfl', 2026, 5, 'REG',"
            " ?, ?, '2099-10-05T17:00:00Z', 'scheduled', '2026-10-05')",
            (gid, home, away))
    homes = {"g1": ("PHI", "DAL"), "g2": ("NYG", "WAS")}
    ids = []
    for i, (gid, market, line, side) in enumerate(taken):
        home, away = homes[gid]
        subject = f"{away} @ {home}" if market == "total" else home
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES (?, 'nfl', ?,"
            " ?, ?, ?, 0.61, ?, 'statistical', 'final', 'fs3', '{}', 'test')",
            (f"2026-09-28T15:00:0{i}Z", gid, market, subject, line, side))
        ids.append(conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0])
    conn.commit()
    shortlist.rank_rows(conn, ids)
    for pid in ids:
        conn.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                     (pid, db.utcnow()))
    conn.commit()
    return conn, ids


def test_my_day_wears_the_club_its_picks_words_name(tmp_path):
    """A taken "not_cover" on PHI -3.5 is Dallas +3.5, and a taken "lose"
    moneyline is Dallas to win: the chip wore PHI, the subject's club, beside
    both (pick-number finding 6). A "cover" (NYG -7.5) wears NYG, and a total
    -- which names no club -- wears the home club as the game's mark, as it
    did."""
    conn, (spread_no, money_no, spread_yes, total) = _nfl_world(
        tmp_path / "day.db", [("g1", "spread", -3.5, "not_cover"),
                              ("g1", "moneyline", None, "lose"),
                              ("g2", "spread", -7.5, "cover"),
                              ("g1", "total", 44.5, "under")])
    payload = views.week(conn, "nfl", 2026, 5)
    chips = {e["prediction_id"]: e for e in payload["board"]["my_day"]["entries"]}
    assert set(chips) == {spread_no, money_no, spread_yes, total}
    assert (chips[spread_no]["club"]["tricode"], chips[spread_no]["line_words"]) == ("DAL", "DAL +3.5")
    assert (chips[money_no]["club"]["tricode"], chips[money_no]["line_words"]) == ("DAL", "DAL to win")
    assert (chips[spread_yes]["club"]["tricode"], chips[spread_yes]["line_words"]) == ("NYG", "NYG -7.5")
    assert chips[total]["club"]["tricode"] == "PHI"
    game = next(g for g in payload["board"]["games"] if g["game_id"] == "g1")
    dal = game["away"]
    assert chips[spread_no]["club"]["colour"] == dal["colour"]
    assert audit.pick_side_faults(payload) == []
    # AS RELEASED: the subject's club on both no-side picks.
    for pid in (spread_no, money_no):
        chips[pid]["club"] = {"tricode": "PHI"}
    faults = audit.pick_side_faults(payload)
    assert sum("finding 6" in f for f in faults) == 2, faults


# --- the sweep ------------------------------------------------------------------

def test_the_payout_floor_reads_what_the_side_bought_pays(tmp_path, covered):
    """The floor ("picks that clear the bar but pay less than this fold into
    one line") read the proposition's payout whatever side a pick buys. The
    away side here costs 51.5c and pays 1.94x; the home side's 48.5c pays
    2.06x. Under a 2.0x floor the pick was left out of the fold on the home
    side's payout; it pays 1.94x, and the fold counts it."""
    conn, pid = _priced_world(tmp_path)
    settings.set_value(conn, "min_payout", "2.0")
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["side"] == "no" and entry["payout"] == 2.062
    payload = views.week(conn, "mlb", 2026, 1)
    today = payload["today"]
    assert today["below_floor_n"] == 1 and today["n"] == 0, today["count_words"]
    assert "below your 2x floor" in today["count_words"]
    assert audit.pick_side_faults(payload) == []
    # AS RELEASED: shown above the floor on the home side's 2.06x.
    today["clears"], today["below_floor"] = today["below_floor"], []
    faults = audit.pick_side_faults(payload)
    assert any("shown above" in f and "1.942" in f for f in faults), faults
    settings.set_value(conn, "min_payout", "1.9")
    again = views.week(conn, "mlb", 2026, 1)["today"]
    assert again["below_floor_n"] == 0 and again["n"] == 1


def test_a_moneyline_no_side_with_no_opponent_is_said_as_asked():
    """With an opponent the no side is restated as the other club's win; with
    none recorded it read "PHI to win" over a pick against PHI, where the
    chance clause beside it said "PHI loses"."""
    lose = {"market_type": "moneyline", "model_side": "lose", "subject": "PHI",
            "line_asked": None}
    assert language.phrase(lose) == "PHI to lose"
    assert language.tile_line(lose) == "PHI to lose"
    assert language.club_named(lose) == "PHI"
    against = dict(lose, opponent="DAL")
    assert language.phrase(against) == "DAL to win"
    assert language.tile_line(against) == "DAL to win"
    assert language.club_named(against) == "DAL"
    assert language.club_named(dict(against, model_side="win")) == "PHI"
    assert language.club_named({"market_type": "total", "model_side": "under",
                                "subject": "DAL @ PHI"}) is None


def test_the_other_side_is_placed_by_the_one_place():
    for market, spelling, other in (("spread", "cover", "not_cover"),
                                    ("spread", "not_cover", "cover"),
                                    ("spread", "fail to cover", "cover"),
                                    ("moneyline", "lose", "win"),
                                    ("total", "under", "over"),
                                    ("prop", "over", "under"),
                                    ("distance", "no", "yes")):
        assert subjects.other_side_spelling(market, spelling) == other
    with pytest.raises(subjects.UnplaceableSide):
        subjects.other_side_spelling("spread", "fails to cover")
    spread = {"market_type": "spread", "model_side": "not_cover", "subject": "DET",
              "opponent": "WSH", "line_asked": -1.5, "sport": "mlb"}
    assert language.phrase(spread) == "WSH covers +1.5"
    assert language.phrase_of_the_other_side(spread) == "DET covers -1.5"
    total = {"market_type": "total", "model_side": "under", "subject": "AZ @ KC",
             "line_asked": 8.5, "sport": "mlb"}
    assert language.phrase_of_the_other_side(total) == "over 8.5 total runs"


# --- the step's prover (2026-09-30) ---------------------------------------------

def _results_world(path):
    """One NFL game, PHI at home to DAL, and a question on each side of each
    game market -- every one a row of the Results table."""
    conn = db.open_db(path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g1', 'nfl', 2026, 5, 'REG',"
        " 'PHI', 'DAL', '2099-10-05T17:00:00Z', 'scheduled', '2026-10-05')")
    ids = {}
    for i, (market, subject, line, side) in enumerate((
            ("moneyline", "PHI", None, "lose"), ("moneyline", "PHI", None, "win"),
            ("spread", "PHI", -3.5, "not_cover"), ("spread", "PHI", -3.5, "cover"),
            ("total", "DAL @ PHI", 44.5, "under"), ("total", "DAL @ PHI", 44.5, "over"))):
        # one question per pass: a question and its other side are two
        # forecasters' here, as the record keys a question per forecaster
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES (?, 'nfl', 'g1',"
            " ?, ?, ?, 0.61, ?, ?, 'final', 'fs3', '{}', 'test')",
            (f"2026-09-28T15:00:0{i}Z", market, subject, line, side,
             "statistical" if i % 2 == 0 else "llm"))
        ids[(market, side)] = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    return conn, ids


def test_a_results_row_says_the_side_its_number_is_for(tmp_path):
    """THE RESULTS TABLE (`views.history`, drawn: "Prediction | ... | Model |
    Market then | ... | Result"). A row carries no opponent, so a no side is
    said as asked -- and a moneyline "lose" read "PHI to win" beside the
    model's 61% for PHI LOSING: 403 rows on the record, every sport, found by
    the step's prover (2026-09-30) on a verified copy. Fails on 401d059."""
    conn, ids = _results_world(tmp_path / "results.db")
    payload = views.history(conn, sport="nfl", limit=50)
    said = {i["prediction_id"]: i["phrase"] for i in payload["items"]}
    assert said[ids[("moneyline", "lose")]] == "PHI to lose"
    assert said[ids[("moneyline", "win")]] == "PHI to win"
    assert said[ids[("spread", "not_cover")]] == "PHI does not cover -3.5"
    assert said[ids[("spread", "cover")]] == "PHI covers -3.5"
    assert said[ids[("total", "under")]] == "under 44.5 total points"
    assert said[ids[("total", "over")]] == "over 44.5 total points"
    assert audit.pick_side_faults(payload) == []
    # AS RELEASED: the lose row said "PHI to win".
    for item in payload["items"]:
        if item["prediction_id"] == ids[("moneyline", "lose")]:
            item["phrase"] = "PHI to win"
    faults = audit.pick_side_faults(payload)
    assert len(faults) == 1 and "Results table" in faults[0], faults
    with pytest.raises(audit.LawViolation, match="ANOTHER SIDE'S NUMBER"):
        audit.check_every_pick_names_its_side(payload)


def test_the_edge_figure_says_whose_it_is(tmp_path, covered):
    """The edge figure is the BETTER side's. "BBB to win" at 57% against 58c
    (AAA's yes price 42c): AAA is worth -1.0c after the fee, BBB -3.0c, and
    neither clears it -- so no side is chosen, `edge_side` is None, and the
    card labelled AAA's -1.0c as BBB's ("Edge after fees") while the board's
    tile drew it bare beside "BBB to win". NBA 3166 on the record, the step's
    prover (2026-09-30). The engine names the figure's side; the card and
    the tile say "on the other side". Fails on 401d059."""
    conn, pid = _priced_world(tmp_path, price=0.42)
    entry = recommend.for_predictions(conn, [pid])[0]
    # NO SIDE, NO RETURN, as before; the figure's side is named beside it.
    assert entry["side"] is None and entry["edge_side"] is None
    assert entry["return_on_stake"] is None
    assert entry["edge_cents"] == pytest.approx(-1.0)
    assert entry["edge_cents_side"] == "yes"
    assert entry["question_takes_the_proposition"] is False
    payload = views.week(conn, "mlb", 2026, 1)
    card = _today_card(payload, pid)
    assert card["edge_words"] == "-1.0¢"
    assert card["edge_label"] == "Edge after fees, on the other side"
    assert card["edge_on_the_other_side"] is True
    tile = next(q for g in payload["board"]["games"] for q in g["questions"]
                if q["prediction_id"] == pid)
    assert tile["line_words"] == "BBB to win"
    assert tile["edge_words"] == "-1.0¢ on the other side"
    assert audit.pick_side_faults(payload) == []
    # AS RELEASED: the card's label and the bare tile.
    card["edge_label"] = "Edge after fees"
    tile["edge_words"] = "-1.0¢"
    faults = audit.pick_side_faults(payload)
    assert any("labels its '-1.0¢'" in f for f in faults), faults
    assert any("draws the edge '-1.0¢'" in f for f in faults), faults


def test_an_edge_on_the_questions_own_side_says_nothing_more(tmp_path, covered):
    """BBB at 57% against 55c (AAA's 45c): BBB is worth +0.0c, AAA -4.0c --
    the figure is the question's own side's, and nothing is added."""
    conn, pid = _priced_world(tmp_path, price=0.45)
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["edge_cents_side"] == "no" and entry["side"] is None
    payload = views.week(conn, "mlb", 2026, 1)
    card = _today_card(payload, pid)
    assert card["edge_label"] == "Edge after fees"
    assert card["edge_on_the_other_side"] is False
    tile = next(q for g in payload["board"]["games"] for q in g["questions"]
                if q["prediction_id"] == pid)
    assert not tile["edge_words"].endswith("on the other side")
    assert audit.pick_side_faults(payload) == []


def test_a_spread_tile_names_the_other_side_from_step_a(tmp_path, covered):
    """A spread claim is read at the venue's line, often not the question's
    (pick-number finding 2), so while the words named the question's line
    "the other side" of them could name another contract again, and the
    spread tile kept its bare figure (step C). From pick-number step A
    (2026-09-30) the words name the claim's contract, so the other side of
    them IS the other side of the figure's own contract: the tile says so as
    a moneyline or total tile does, and the check holds it to that. (Held
    here at the question's own line, where both readings are one contract;
    `test_every_number_names_its_line.py` holds a claim at another.)"""
    from tests import test_recommend as rec

    conn = rec._world(tmp_path, kickoff="2099-01-01T00:00:00Z")
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'mlb', 'g0', 'spread', 'AAA', -1.5,"
        " 0.57, 'not_cover', 'statistical', 'final', 'fs2', ?, 'test')", (rec.WHOLE,))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
        " VALUES ('kalshi', 't1', 'e', 'mlb', 'g0', 'spread', 'home_margin', -1.5,"
        " 'home', 0.41, 0.43, '2026-09-07T01:00:00Z')")
    quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', 'g0', 'spread', 'home_margin', -1.5,"
        " 'home', 'rung_differs_margin', 2.0, 13.0, 0.43, 0.42, 0.42, 'mid',"
        " '2026-09-07T01:30:00Z')", (pid, quote))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["question_takes_the_proposition"] is False
    assert (entry["side"], entry["edge_cents_side"]) == (None, "yes")
    payload = views.week(conn, "mlb", 2026, 1)
    card = _today_card(payload, pid)
    assert card["question"] == "BBB covers +1.5"
    assert card["edge_label"] == "Edge after fees, on the other side"
    tile = next(q for g in payload["board"]["games"] for q in g["questions"]
                if q["prediction_id"] == pid)
    assert tile["edge_words"] == "-1.0¢ on the other side"
    assert audit.pick_side_faults(payload) == []
    # AND THE BARE FIGURE, AS STEP C LEFT A SPREAD TILE, IS NAMED NOW
    bare = json.loads(json.dumps(payload, default=str))
    for g in bare["board"]["games"]:
        for q in g["questions"]:
            if q["prediction_id"] == pid:
                q["edge_words"] = "-1.0¢"
    assert any("the OTHER side's" in f for f in audit.pick_side_faults(bare))


def test_the_better_side_is_named_with_or_without_a_side_chosen():
    assert recommend.side_for(0.43, 0.42)["better_side"] == "yes"
    assert recommend.side_for(0.43, 0.42)["side"] is None
    assert recommend.side_for(0.30, 0.46)["better_side"] == "no"
    assert recommend.side_for(0.30, 0.46)["side"] == "no"
    assert recommend.side_for(0.62, None)["better_side"] is None


# --- the gate --------------------------------------------------------------------

def test_the_gate_makes_the_call_and_its_scanner_can_see():
    gate = ROOT / "tools" / "verify.py"
    step = next(node for node in ast.parse(gate.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert any(isinstance(node, ast.Attribute)
               and node.attr == "check_every_pick_names_its_side"
               for node in ast.walk(step))
    assert audit.pick_side_faults(audit.PICK_SIDE_FIXTURE_GOOD) == []
    for name, change in audit.PICK_SIDE_FIXTURES_AS_RELEASED.items():
        assert audit.pick_side_faults(audit._pick_side_fixture(**change)), name
    # THE FIXTURE ROUND-TRIPS AS THE PAYLOAD DOES (json), so a change made to
    # a copy never reaches the constant the self-check reads.
    assert json.loads(json.dumps(audit.PICK_SIDE_FIXTURE_GOOD)) == audit.PICK_SIDE_FIXTURE_GOOD
