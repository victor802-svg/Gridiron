"""The Today screen as cards (GRIDIRON_CARD_FACE, 2026-09-07).

The grammar of a sportsbook -- an event header, the market under it, three
prices reading across, a running list of what was taken -- without any of its
pressure. Every test here is about one of those two halves.

WHAT THE PAGE LOOKED LIKE BEFORE, measured rather than remembered: thirty
rows, each ending "-- no venue price to compare against yet", under a heading
promising "the number beside each is what it is actually worth after that
fee", with no number on any row; 13-pixel type beneath cards showing a
probability at 40 and a hero showing one at 72.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from gridiron import audit, config, db, language, settings, shortlist, views
from gridiron.market import recommend

DIST = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})

WEB = Path(views.__file__).resolve().parent / "web"


def _world(tmp_path, games=2):
    conn = db.open_db(tmp_path / "face.db")
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


def _claim(conn, pid, *, model_prob, venue_implied, game="g0"):
    """A quote and the frozen claim read against it.

    THE CLAIM NEEDS ITS QUOTE. A claim with no quote row would be a price with
    no provenance, which is the thing the schema refuses by making the
    reference NOT NULL.
    """
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, last_price,"
        " volume, fetched_utc) VALUES ('test venue', 'T', 'E', 'mlb', ?,"
        " 'moneyline', 'home_win', NULL, 'home', ?, ?, ?, 500,"
        " '2026-09-07T01:00:00Z')",
        (game, venue_implied - 0.01, venue_implied + 0.01, venue_implied))
    quote_id = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        # A WINNER CONTRACT, so the claim is line-less and carries no
        # distribution: AT_THE_PRICE gave the row a shape, and the two direct
        # shapes may not carry margin parameters they never read.
        "INSERT INTO at_the_line_claims (created_utc, prediction_id, quote_id,"
        " venue, sport, game_id, market, quantity, line, side, shape,"
        " model_prob, venue_price, venue_implied, price_basis)"
        " VALUES ('2026-09-07T01:00:00Z', ?, ?, 'test venue', 'mlb', ?,"
        " 'moneyline', 'home_win', NULL, 'home', 'line_less', ?, ?, ?,"
        " 'the midpoint of the venue book')",
        (pid, quote_id, game, model_prob, venue_implied, venue_implied))
    conn.commit()


@pytest.fixture()
def covered(monkeypatch):
    """Let this market be priceable, so the CARD can be tested.

    COVERAGE IS MEASURED FROM THE VENUE'S OWN LADDERS and needs roughly twenty
    games of them before it says yes to anything -- which is a fact about the
    venue, tested in `test_priced.py`, and nothing to do with what a card
    shows. Forcing it here keeps these tests about the thing they are about.
    """
    from gridiron.priced import coverage as _coverage

    monkeypatch.setattr(
        _coverage, "priceable",
        lambda conn, sport, market: {
            "priceable": True, "market": market,
            "why": "covered, for this test"})


# --- F2b: the bar has two conditions ----------------------------------------

def test_a_thin_edge_on_an_expensive_contract_does_not_clear_the_bar():
    """TWO CENTS IS TWO CENTS AND IS NOT THE SAME BET TWICE.

    On an 89-cent contract it is 2.2% of the money; on a 20-cent contract the
    same two cents is 10%. The cents test passes both and the operator's
    question -- is being right worth the click -- is only answered by the
    second number.
    """
    dear = recommend.clears_the_bar(2.0, 0.89)
    assert dear["clears"] is False
    assert "2.2%" in dear["why"] and "5%" in dear["why"]
    cheap = recommend.clears_the_bar(2.0, 0.20)
    assert cheap["clears"] is True
    assert recommend.return_on_stake(2.0, 0.20) == 0.1
    # absent stays absent rather than becoming a zero
    assert recommend.return_on_stake(None, 0.5) is None
    assert recommend.return_on_stake(2.0, None) is None
    assert recommend.payout_multiple(0.80) == 1.25
    assert recommend.payout_multiple(None) is None


def test_the_minimum_return_is_declared_and_dated():
    """A threshold with no date cannot be told from a number somebody typed."""
    assert config.MIN_RETURN_ON_STAKE == 0.05
    assert config.MIN_RETURN_ON_STAKE_DECLARED.startswith("2026-09-07")
    source = Path(config.__file__).read_text(encoding="utf-8")
    where = source.index("MIN_RETURN_ON_STAKE = ")
    rationale = source[max(0, where - 1400):where]
    assert "89-cent" in rationale, "the rationale must say what it is for"
    assert "DECLARED, NOT FITTED" in rationale


def test_a_pick_that_fails_the_return_test_keeps_its_edge_on_its_face(tmp_path, covered):
    """IT IS NOT HIDDEN. "The price is wrong but not wrong enough to be worth
    it" is a thing a reader should be able to see, so the pick stays in the
    watched group with its number."""
    conn = _world(tmp_path)
    pid = _pick(conn, prob=0.91)
    _claim(conn, pid, model_prob=0.91, venue_implied=0.89)
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["side"] is None, "it must not clear the bar"
    assert entry["edge_cents"] is not None and entry["edge_cents"] > 0
    assert entry["return_on_stake"] is not None
    assert "worth the click" in entry["side_why"]


# --- F2: the card ------------------------------------------------------------

def test_the_payout_leads_the_card_and_the_edge_is_a_quiet_line():
    """THE HIERARCHY MOVED BY OPERATOR RULING ON 2026-09-08, and the property
    this test protects did not: ONE number leads the card and it is a price,
    not the probability.

    It was the edge, from CARD_FACE on the 7th. It is the payout now -- what a
    reader of a sportsbook reads first, and the one number that says what the
    bet is FOR rather than what it is worth -- with the edge moved to its own
    line beneath, still signed and still the only green and red on the card.
    """
    css = (WEB / "style.css").read_text(encoding="utf-8")
    root = css[css.index(":root {"):css.index("* { box-sizing")]
    tokens = dict(re.findall(r"--([a-z0-9-]+):\s*([0-9.]+)px;", root))

    def size(selector):
        block = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
        assert block, selector
        found = re.search(r"font-size:\s*(?:var\(--([a-z0-9-]+)\)|([0-9.]+)px)",
                          block.group(1))
        assert found, selector
        return float(tokens[found.group(1)] if found.group(1) else found.group(2))

    assert size(".box-payout .box-value") > size(".box-value")
    assert size(".box-payout .box-value") > size(".face-q")
    # and the edge is set at the quietest size on the card
    assert size(".face-edge") <= size(".box-value")


def test_the_card_says_nothing_the_server_did_not_write():
    """Labels included. Three words typed into the renderer is how every
    composition this project has had to remove began."""
    labels = language.price_row_labels()
    assert set(labels) == {"model", "venue", "edge", "why", "took", "taken",
                           "tab_upcoming", "tab_live"}
    assert labels["edge"] == "Edge after fees"
    # THE VENUE BOX IS THE PAYOUT NOW, so its label says what the number is
    # rather than whose it is.
    assert labels["venue"] == "Pays"
    app = (WEB / "app.js").read_text(encoding="utf-8")
    card = app[app.index("function todayCard"):app.index("function renderToday")]
    for word in ("'Model'", "'Venue'", "'Edge", "'I took this'"):
        assert word not in card, f"the renderer types {word} for itself"
    assert audit.js_prose_composition() == []


def test_the_three_chips_read_across_and_an_absence_is_not_a_zero():
    assert language.venue_chip_words(0.84, 1.19) == "84¢ · pays 1.19x"
    assert language.venue_chip_words(None, None) == "no price yet"
    assert language.edge_chip_words(-3.4) == "-3.4¢"
    assert language.edge_chip_words(2.0) == "+2.0¢"
    assert language.edge_chip_words(None) == "—"
    # THE MODEL CHIP IS NOT THE VENUE CHIP. The model always has a
    # probability; what it lacks without a claim is a price for the venue's
    # question. "no price yet" in that box said the model had no opinion.
    assert language.price_chip_words(None) == "—"
    assert language.price_chip_words(88.0) == "88¢"
    assert language.edge_state(1.0) == "up"
    assert language.edge_state(-1.0) == "down"
    assert language.edge_state(None) == "none"


def test_the_sentence_is_said_once_for_the_slate_not_once_per_row(tmp_path):
    """IT WAS SAID THIRTY TIMES. Measured on the football slate of
    2026-09-07: "no venue price to compare against yet" appeared on all thirty
    rows, as though each had discovered it independently."""
    conn = _world(tmp_path, games=3)
    for i in range(3):
        _pick(conn, game=f"g{i}", subject=f"AAA{i}")
    today = views.week(conn, "mlb", 2026, 1)["today"]
    assert today["no_price_words"], "the slate says it once"
    assert "hours before each game starts" in today["no_price_words"]
    for card in today["watching"]:
        assert "no venue price to compare against yet" not in json.dumps(card)
        assert card["venue_words"] == "no price yet"


def test_a_chip_every_card_would_wear_belongs_to_the_heading(tmp_path):
    """TWELVE CHIPS READING "STRONG · unproven" down one page is a group
    heading wearing a badge twelve times. Measured on the same slate: the
    first twelve chips on the page were identical."""
    conn = _world(tmp_path, games=3)
    for i in range(3):
        _pick(conn, game=f"g{i}", prob=0.62, subject=f"AAA{i}")
    today = views.week(conn, "mlb", 2026, 1)["today"]
    if today["watching_chip"]:
        assert all(c["tier_chip"] is None for c in today["watching"]), \
            "the heading carries it, so the cards do not"


def test_every_card_carries_its_own_sample_size(tmp_path):
    """LAW 4 travels with a card the same as with a figure."""
    conn = _world(tmp_path)
    _pick(conn)
    today = views.week(conn, "mlb", 2026, 1)["today"]
    for card in today["clears"] + today["watching"] + today["below_floor"]:
        assert card["n"] is not None
        assert "settled" in card["gate_words"]


# --- F2b: the floor is a display preference ---------------------------------

def test_the_floor_folds_cards_and_hides_nothing_from_the_record(tmp_path, covered):
    """A FLOOR THAT HID PICKS FROM THE MEASUREMENT would be the operator's
    taste rewriting his own evidence. It is applied on the way to the screen;
    `record_for` writes every pick that clears the bar whatever it says."""
    conn = _world(tmp_path)
    pid = _pick(conn, prob=0.92)
    _claim(conn, pid, model_prob=0.92, venue_implied=0.80)   # pays 1.25x
    settings.set_value(conn, "min_payout", "1.5")

    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["side"] is not None, "it clears the bar"
    assert entry["payout"] == 1.25

    today = views.week(conn, "mlb", 2026, 1)["today"]
    assert today["below_floor_n"] == 1 and today["n"] == 0
    assert "1.5x floor" in today["below_floor_words"]

    # THE RECORD DOES NOT KNOW ABOUT THE FLOOR.
    recommend.record_for(conn, [pid])
    stored = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
    assert stored == 1, "the floor must not keep a pick off the record"

    settings.set_value(conn, "min_payout", "1.2")
    again = views.week(conn, "mlb", 2026, 1)["today"]
    assert again["n"] == 1 and again["below_floor_n"] == 0


def test_a_payout_floor_that_cannot_mean_anything_is_refused():
    for bad in ("0.9", "40", "nonsense"):
        with pytest.raises(settings.SettingRefused):
            settings._a_multiple(bad)
    assert settings._a_multiple("1.5x") == "1.5"


# --- F2: the size is money only when the operator has said what a unit is ----

def test_the_size_is_in_units_until_the_operator_declares_his_unit(tmp_path):
    """NOTHING HERE IS A BALANCE. `config.BANKROLL_UNITS` says in as many
    words that a unit maps to money outside this codebase, so the amount is
    asked for rather than invented, and until it is given the card says what
    it always said."""
    conn = _world(tmp_path)
    assert settings.value(conn, "unit_dollars") == ""
    in_units = language.size_words(units=1.0, flat=True, why="no measured edge",
                                  unit_dollars=None)
    assert "flat unit" in in_units and "$" not in in_units

    settings.set_value(conn, "unit_dollars", "5")
    in_money = language.size_words(units=1.0, flat=True, why="no measured edge",
                                   unit_dollars=5.0)
    assert in_money.startswith("$5 · one flat unit")
    quarter = language.size_words(units=1.37, flat=False, why=None,
                                  unit_dollars=5.0)
    assert "$6.85" in quarter and "quarter of Kelly" in quarter


def test_a_watched_card_carries_no_size(tmp_path):
    """A size on a pick that does not clear the bar is a recommendation the
    app is not making."""
    conn = _world(tmp_path)
    _pick(conn)
    today = views.week(conn, "mlb", 2026, 1)["today"]
    assert today["watching"], "there is something to check"
    for card in today["watching"]:
        assert "size_words" not in card


# --- F3: taken today ---------------------------------------------------------

def test_the_running_list_is_a_selection_record_and_not_a_slip(tmp_path):
    conn = _world(tmp_path)
    pid = _pick(conn)
    views.take_pick(conn, pid)
    today = views.week(conn, "mlb", 2026, 1)["today"]
    panel = today["taken_today"]
    assert panel["n"] == 1
    entry = panel["entries"][0]
    assert entry["prediction_id"] == pid and entry["taken_utc"]
    assert "when marked" in entry["words"] or "no price recorded" in entry["words"]
    # no stake, no payout, no total, and not the word a book uses
    blob = json.dumps(panel).lower()
    for forbidden in ("slip", "stake", "payout", "total"):
        assert forbidden not in blob, forbidden
    assert language.taken_today_heading(0) == "Taken today · nothing marked yet"


def test_the_edge_in_the_list_is_the_one_that_stood_when_it_was_marked(tmp_path, covered):
    """A NUMBER THAT MOVED AFTERWARDS WOULD MAKE THIS A SCOREBOARD.
    `picks_taken` holds three columns by law, so the edge comes from the
    recommendation already on the record at that moment."""
    conn = _world(tmp_path)
    pid = _pick(conn, prob=0.92)
    _claim(conn, pid, model_prob=0.92, venue_implied=0.60)
    recommend.record_for(conn, [pid])
    views.take_pick(conn, pid)
    entry = views.week(conn, "mlb", 2026, 1)["today"]["taken_today"]["entries"][0]
    assert "when marked" in entry["words"]
    stored = conn.execute("SELECT edge_cents FROM recommendations").fetchone()[0]
    assert f"{stored:+.1f}" in entry["words"]


# --- the pressure, banned by name --------------------------------------------

def test_no_pressure_word_may_reach_a_card():
    """SCANNED WHERE THE PROJECT'S OWN WORDS ARE, not where the model's are.

    The list started inside `plain_words_violations` and the suite caught it
    within the hour: that scan also reads the second forecaster's prose, where
    two stored rows say "boost" -- a boost from playing at home, which is
    ordinary English about a baseball game. `ADVICE_WORDS` and `TIPSTER_WORDS`
    already draw this line and the pressure words belong on the composed side
    of it.
    """
    for word in ("boost", "hot", "trending", "popular", "streak", "parlay",
                 "combo", "same game"):
        planted = f"Miami to win — a {word} pick at this price"
        assert audit.pressure_word_faults(planted), word
        payload = {"today": {"watching": [{"question": planted}]}}
        assert audit.day_pressure_faults(payload), word
        with pytest.raises(audit.LawViolation):
            audit.check_the_day_applies_no_pressure(payload)
    # and the model's own prose is left alone
    assert audit.plain_words_violations(
        "The home side get a boost from the short trip.") == []


def test_the_pressure_scan_does_not_fire_on_ordinary_english():
    """A SCAN THAT CRIES WOLF GETS SWITCHED OFF. "hot" inside "shot" is the
    false positive that would end this rule."""
    assert audit.pressure_word_faults(
        "He took a shot from the hotel roof and the photo was popularised.") == []
    assert audit.pressure_word_faults("Combos of factors") == []


def test_no_price_may_move_when_it_changes():
    assert audit.price_chip_animation_faults(
        ".edge .box-value { transition: color 200ms; }")
    assert audit.price_chip_animation_faults(
        ".box { animation: pulse 1s infinite; }")
    audit.check_no_price_animation()          # the shipped stylesheet


def test_kickoff_is_a_time_and_never_a_timer():
    audit.check_no_countdown()
    app = (WEB / "app.js").read_text(encoding="utf-8")
    assert "clockTimer" not in app, "the repainting timer is gone with it"
    assert "localDayTime" in app, "the instant is still shown, in the reader's clock"


def test_one_definition_per_function_in_the_renderer(tmp_path):
    """`renderToday` was defined twice, byte-identical, one directly after the
    other; `localTime` twice, 571 lines apart, and the two DISAGREED about
    what to show when a date will not parse. The second of each won at load."""
    audit.check_no_duplicate_js_definitions()
    planted = tmp_path / "app.js"
    planted.write_text(
        "  function a(x) {\n    return 1;\n  }\n\n  function a(x) {\n"
        "    return 2;\n  }\n", encoding="utf-8")
    faults = audit.duplicate_js_definitions(planted)
    assert faults and "dead code" in faults[0]


# --- F1 and F4 ---------------------------------------------------------------

def test_the_day_is_stated_once_at_the_top(tmp_path):
    conn = _world(tmp_path, games=2)
    _pick(conn, game="g0", subject="AAA0")
    _pick(conn, game="g1", subject="AAA1")
    today = views.week(conn, "mlb", 2026, 1)["today"]
    assert today["where_words"] and today["count_words"]
    assert "watched" in today["count_words"]
    assert audit.plain_words_violations(today["count_words"]) == []
    assert audit.advice_word_faults(today["count_words"]) == []
    markup = (WEB / "index.html").read_text(encoding="utf-8")
    strip = markup.index('class="day-strip"')
    assert strip < markup.index('id="today-clears"'), "the strip leads the panel"


def test_the_price_row_stays_on_one_line_on_a_phone():
    """The requirement survived the redesign; the number of boxes did not.

    CARD_FACE put three boxes on the row -- model, venue, edge. THREE_STATES
    took the edge off it and on to its own line, so the row is the model's
    price and the payout, and the phone layout still has to hold both on one
    line at 390px.
    """
    css = (WEB / "style.css").read_text(encoding="utf-8")
    phone = css[css.index("@media (max-width: 860px)"):]
    block = re.search(r"\.face-prices\s*\{([^}]*)\}", phone)
    assert block, "the phone layout says nothing about the price row"
    columns = re.search(r"grid-template-columns:([^;]*);", block.group(1))
    assert columns and len(columns.group(1).split()) == 2


def test_every_tap_target_keeps_its_floor():
    css = (WEB / "style.css").read_text(encoding="utf-8")
    for selector in (".expand", ".fold"):
        block = re.search(re.escape(selector) + r"[^{]*\{([^}]*)\}", css)
        assert block, selector
        assert "min-height: 44px" in block.group(1), selector


def test_the_price_row_is_about_the_side_the_question_names(tmp_path, covered):
    """FOUND ON THE FIRST SLATE THAT EVER CLEARED THE BAR. The card read
    "Toronto covers +1.5" over three numbers about the Athletics, and labelled
    the edge as being on the other side of the side it had already flipped.

    A claim is stored from one fixed proposition -- the home side, or the over
    -- so that a curve compares like with like. A card names the side the
    model took. When those are opposites the card must turn the prices round,
    or it names one team and prices the other.
    """
    conn = _world(tmp_path)
    # THE MODEL TAKES THE AWAY SIDE: the home side does not cover. Written
    # this way rather than edited afterwards, because LAW 3 refuses the edit --
    # which it did, on the first draft of this test.
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'mlb', 'g0', 'spread', 'AAA', -1.5,"
        " 0.70, 'not_cover', 'statistical', 'final', 'fs2', ?, 'test')",
        (WHOLE,))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, last_price,"
        " volume, fetched_utc) VALUES ('test venue', 'T2', 'E2', 'mlb', 'g0',"
        " 'spread', 'home_margin', -1.5, 'home', 0.49, 0.51, 0.5, 500,"
        " '2026-09-07T01:00:00Z')")
    quote_id = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (created_utc, prediction_id, quote_id,"
        " venue, sport, game_id, market, quantity, line, side, shape,"
        " model_prob, venue_price, venue_implied, price_basis)"
        " VALUES ('2026-09-07T01:00:00Z', ?, ?, 'test venue', 'mlb', 'g0',"
        " 'spread', 'home_margin', -1.5, 'home', 'rung_matched', 0.30, 0.50,"
        " 0.50, 'the midpoint of the venue book')", (pid, quote_id))
    conn.commit()

    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["question_takes_the_proposition"] is False, (
        "the question is about the away side and the claim about the home one")

    today = views.week(conn, "mlb", 2026, 1)["today"]
    card = (today["clears"] + today["below_floor"] + today["watching"])[0]
    # 30c on the home side is 70c on the side the question names
    assert card["model_words"] == "70¢"
    assert card["venue_words"].startswith("50¢")
    # and the edge is on that same side, so the label carries no qualifier
    assert card["edge_label"] == "Edge after fees"


def test_an_edge_on_the_other_side_still_says_so():
    """The qualifier is not deleted, only pointed correctly: it fires when the
    better side is NOT the one the question names."""
    same = views._edge_side_words("yes", True)
    assert same == "yes" and language.edge_label_words("Edge", same) == "Edge"
    other = views._edge_side_words("no", True)
    assert language.edge_label_words("Edge", other) == "Edge, on the other side"
    # and a question stated from the complement flips both answers
    assert views._edge_side_words("no", False) == "yes"
    assert views._edge_side_words("yes", False) == "no"
    assert views._edge_side_words(None, True) is None


def test_the_strip_says_whose_questions_it_is_counting():
    """FOUND WHEN THE RECORD HELD SIX RECOMMENDATIONS AND THE SCREEN SAID FOUR.

    Both were true. Picks shows one forecaster at a time -- two forecasters
    answering one question are two claims and not two picks -- and the
    recommendations table holds every forecaster's. "4 picks clear the bar" in
    twenty-point type reads as a fact about the day rather than about a
    filter, and a reader had no way to tell which it was.
    """
    model = language.day_strip_words(
        day_words="Tuesday 8 September", slate_words="MLB", clears=4,
        watching=11, below_floor=0, floor=1.5, forecaster="statistical")
    assert model["counts"].startswith("the model has 4 picks that clear the bar")

    pass_ = language.day_strip_words(
        day_words="Tuesday 8 September", slate_words="MLB", clears=2,
        watching=3, below_floor=0, floor=1.5, forecaster="llm")
    assert pass_["counts"].startswith("the reasoning pass has 2 picks")

    # every branch names it, including the empty one and the singular
    empty = language.day_strip_words(
        day_words="x", slate_words="MLB", clears=0, watching=15,
        below_floor=0, floor=1.5, forecaster="statistical")
    assert empty["counts"].startswith("the model has nothing that clears")
    one = language.day_strip_words(
        day_words="x", slate_words="MLB", clears=1, watching=9,
        below_floor=0, floor=1.5, forecaster="statistical")
    assert "1 pick that clears the bar" in one["counts"]
    # and the floor clause survives the rewording
    floored = language.day_strip_words(
        day_words="x", slate_words="MLB", clears=2, watching=9,
        below_floor=1, floor=1.5, forecaster="llm")
    assert "1 of them below your 1.5x floor" in floored["counts"]

    for words in (model["counts"], pass_["counts"], empty["counts"],
                  one["counts"], floored["counts"]):
        assert audit.plain_words_violations(words) == [], words
        assert audit.advice_word_faults(words) == [], words


def test_the_strip_counts_the_forecaster_the_page_is_showing(tmp_path):
    conn = _world(tmp_path, games=2)
    _pick(conn, game="g0", subject="AAA0")
    # the second forecaster answers a question of its own
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'mlb', 'g1', 'moneyline', 'AAA1',"
        " NULL, 0.66, 'win', 'llm', 'final', 'fs2', ?, 'test')", (WHOLE,))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.commit()
    shortlist.rank_rows(conn, [pid])

    statistical = views.week(conn, "mlb", 2026, 1, forecaster="statistical")["today"]
    reasoning = views.week(conn, "mlb", 2026, 1, forecaster="llm")["today"]
    assert "the model has" in statistical["count_words"]
    assert "the reasoning pass has" in reasoning["count_words"]
    # and the two counts are of different question sets
    assert statistical["watching_n"] != reasoning["watching_n"] or         statistical["watching"][0]["prediction_id"] !=         reasoning["watching"][0]["prediction_id"]
