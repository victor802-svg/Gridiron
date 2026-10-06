"""The recommendation (THE_RECOMMENDATION R2-R4, 2026-09-07): an edge that
survives the fee, a size that refuses to vary on an unproven market, a parlay
that is refused, nothing sized in-game, and the closing line recorded once."""
from __future__ import annotations

import json
import re
import sqlite3

import pytest

from gridiron import audit, calibration, config, db, language, shortlist
from gridiron.market import recommend

DIST = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})

#: THE CLOCK A PASS ASKS AT in this world (operator question 38, ruling 2,
#: 2026-10-06; 2026-10-07): `recommend.for_predictions` gives no entry for a
#: game that is not still upcoming, so a pass over this world's games
#: (listed for 2026-09-09) asks at a moment before them, after their claims.
#: Until that ruling these tests priced the games at the real clock, a month
#: past their start -- which is the finished game's pick the ruling refuses.
ASKED = "2026-09-08T00:00:00Z"
#: ...and over `_closed`'s game, listed for 02:00 on the 7th, before it.
ASKED_BEFORE_THE_CLOSE = "2026-09-07T01:45:00Z"


def _world(tmp_path, *, status="scheduled", kickoff="2026-09-09T00:00:00Z"):
    conn = db.open_db(tmp_path / "rec.db")
    # A STARTED GAME CARRIES A SCORE, and the schema insists on it: the pair
    # (status, scores) is checked, so a live game with no score is refused.
    scores = (None, None) if status == "scheduled" else (2, 1)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date, home_score, away_score)"
        " VALUES ('g0', 'mlb', 2026, 1, 'R', 'AAA', 'BBB', ?, ?, '2026-09-08',"
        " ?, ?)", (kickoff, status) + scores)
    conn.commit()
    return conn


@pytest.fixture(autouse=True)
def _covered(monkeypatch):
    """These tests are about the price, not about the coverage list.

    THE_PRICED (2026-09-07) put a measured coverage list in front of the
    recommendation engine, so a market nobody has measured is priced by nobody
    -- correct, and not what these tests are checking. Coverage has its own
    tests in `test_priced.py`.
    """
    from gridiron.priced import coverage

    # THE FORECASTER IS PASSED (operator question 22, 2026-09-28: the kill
    # criterion reads each forecaster's line), and a stand-in takes it.
    monkeypatch.setattr(coverage, "priceable",
                        lambda conn, sport, market, **_: {
                            "priceable": True, "market": market,
                            "why": "covered, in this test"})


def _pick(conn, *, prob=0.62, implied=0.46, subject="AAA", market="moneyline",
          predictor="statistical"):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'mlb', 'g0', ?, ?, NULL, ?, 'win',"
        " ?, 'final', 'fs2', ?, 'test')",
        (market, subject, prob, predictor, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    if implied is not None:
        # THE VENUE'S OWN PRICE, through the at-the-line claim the engine reads.
        # A market snapshot is a bookmaker's line republished by a media API;
        # the recommendation is priced, fed and closed at one venue, so the
        # fixture provides that venue's row.
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " implied_prob, kind) VALUES (?, '2026-09-07T01:00:00Z', 'test', ?,"
            " 'open_at_predict')", (pid, implied))
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport,"
            " game_id, market, quantity, line, yes_side, yes_bid, yes_ask,"
            " fetched_utc) VALUES ('kalshi', ?, 'e', 'mlb', 'g0', ?,"
            " 'home_margin', -1.5, 'home', ?, ?, '2026-09-07T01:00:00Z')",
            (f"t{pid}", market, implied - 0.01, implied + 0.01))
        quote_id = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
            " sport, game_id, market, quantity, line, side, shape,"
            " dist_mean, dist_sd, model_prob, venue_price, venue_implied,"
            " price_basis, created_utc)"
            " VALUES (?, ?, 'kalshi', 'mlb', 'g0', ?, 'home_margin', -1.5,"
            " 'home', 'rung_differs_margin', 2.0, 13.0, ?, ?, ?, 'mid',"
            " '2026-09-07T01:30:00Z')",
            (pid, quote_id, market, prob, implied, implied))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    return pid


def test_an_edge_that_does_not_clear_the_fee_is_no_edge():
    # the fee is largest at a coin flip, which is where the raw disagreement
    # looks most tempting
    assert recommend.fee(0.5) > recommend.fee(0.9)
    got = recommend.side_for(0.51, 0.50)
    assert got["side"] is None
    assert "clears the fee" in got["why"]
    # a real gap survives it, and the number is what is left afterwards
    got = recommend.side_for(0.62, 0.46)
    assert got["side"] == "yes"
    assert got["edge_cents"] == pytest.approx(
        (0.62 - 0.46 - recommend.fee(0.46)) * 100, abs=1e-6)
    # the other side is the one that clears when the model is under the price
    assert recommend.side_for(0.30, 0.46)["side"] == "no"
    # no price, no opinion
    assert recommend.side_for(0.62, None)["side"] is None


def test_below_the_gate_the_size_does_not_move_with_confidence():
    lean = recommend.size_for(model_prob=0.62, price=0.50, settled=3)
    strong = recommend.size_for(model_prob=0.92, price=0.50, settled=3)
    assert lean["kind"] == strong["kind"] == "flat"
    assert lean["units"] == strong["units"] == config.FLAT_UNIT
    assert "no measured edge" in lean["why"]


def test_a_measured_sample_is_not_a_measured_edge():
    """286 settled questions on a market the model is BEHIND on is not a
    licence to size up. Both conditions or the flat unit."""
    behind = recommend.size_for(model_prob=0.62, price=0.50, settled=400,
                                measured_edge=False)
    assert behind["kind"] == "flat" and behind["units"] == config.FLAT_UNIT
    assert "NOT ahead" in behind["why"]
    unknown = recommend.size_for(model_prob=0.62, price=0.50, settled=400,
                                 measured_edge=None)
    assert unknown["kind"] == "flat"
    ahead = recommend.size_for(model_prob=0.62, price=0.50, settled=400,
                               measured_edge=True)
    assert ahead["kind"] == "fraction" and ahead["units"] > 0


def test_the_fraction_is_a_quarter_of_kelly_and_capped():
    full = recommend.kelly_fraction(0.62, 0.50)
    sized = recommend.size_for(model_prob=0.62, price=0.50, settled=400,
                               measured_edge=True)
    assert sized["fraction"] == pytest.approx(
        min(config.KELLY_FRACTION * full, config.MAX_FRACTION))
    assert sized["fraction"] < full          # never full Kelly
    # a wild claim is capped rather than trusted
    wild = recommend.size_for(model_prob=0.97, price=0.30, settled=400,
                              measured_edge=True)
    assert wild["fraction"] == config.MAX_FRACTION


def test_the_blanket_refusal_is_retired_by_name_and_says_what_replaced_it():
    """RETIRED 2026-09-08, not quietly deleted.

    `price_parlay` refused every multi-leg price. LAW 5 as amended permits
    pricing a package the venue published, so the blanket refusal is gone --
    and this test fails if it comes back, or if the note saying where it went
    is removed.
    """
    from pathlib import Path

    assert not hasattr(recommend, "price_parlay")
    assert not hasattr(recommend, "SinglesOnly")
    source = Path(recommend.__file__).read_text(encoding="utf-8")
    assert "RETIRED 2026-09-08" in source
    assert "market.combos.classify" in source, "the note must say what replaced it"


def test_the_four_shapes_that_replaced_it_are_each_refused():
    """One refusal per shape, and none of them counts legs alone."""
    from gridiron.market import combos

    games = {"Kansas City": "g1", "Buffalo": "g1", "Miami": "g2"}
    same_game = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Buffalo over 44"]}, games)
    assert same_game == {"priceable": False, "why": "same_game",
                         "legs": ["Kansas City -3", "Buffalo over 44"],
                         "games": ["g1", "g1"]}
    four = combos.classify(
        {"sport": "nfl", "legs": ["a", "b", "c", "d"]}, games)
    assert four["why"] == "leg_count"
    unforecast_leg = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Sunderland to win"]}, games)
    assert unforecast_leg["why"] == "unforecast_leg"
    unforecast_sport = combos.classify(
        {"sport": "cbb", "legs": ["Michigan -7.5", "UConn -2"]}, games)
    assert unforecast_sport["why"] == "unforecast_sport"
    # and the shape the law permits still passes
    good = combos.classify(
        {"sport": "nfl", "legs": ["Kansas City -3", "Miami moneyline"]}, games)
    assert good["priceable"] and good["games"] == ["g1", "g2"]


def test_nothing_is_sized_once_a_game_is_under_way(tmp_path):
    recommend.refuse_in_game("scheduled")       # must not raise
    with pytest.raises(recommend.NotSizedInGame, match="ninety seconds"):
        recommend.refuse_in_game("in")          # this record's own word
    with pytest.raises(recommend.NotSizedInGame):
        recommend.refuse_in_game("in_progress")  # and the ones it is not
    conn = _world(tmp_path, status="in")
    pid = _pick(conn)
    assert recommend.for_predictions(conn, [pid]) == []
    assert recommend.for_predictions(conn, [pid], now=ASKED) == []


def test_a_recommendation_is_recorded_with_the_price_it_was_made_at(tmp_path):
    conn = _world(tmp_path)
    pid = _pick(conn)
    counts = recommend.record_for(conn, [pid], now=ASKED)
    assert counts["recommended"] == 1
    row = conn.execute("SELECT * FROM recommendations").fetchone()
    assert row["side"] == "yes" and row["price"] == pytest.approx(0.46)
    assert row["size_kind"] == "flat" and row["size_units"] == config.FLAT_UNIT
    assert row["close_price"] is None
    # append-only, and stamped after the prediction it is about
    assert row["created_utc"] > "2026-09-07T00:00:00Z"
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE recommendations SET price = 0.1 WHERE id = ?",
                     (row["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM recommendations WHERE id = ?", (row["id"],))


def test_a_question_with_no_side_is_not_recorded(tmp_path):
    conn = _world(tmp_path)
    pid = _pick(conn, prob=0.51, implied=0.50)
    counts = recommend.record_for(conn, [pid], now=ASKED)
    assert counts["recommended"] == 0 and counts["no_side"] == 1
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 0


# --- corrections reach recommendations (GRIDIRON_REPAIR item 3) --------------
#
# The operator's ruling of 2026-09-23, built 2026-09-26: "recommend.py:324
# reads the corrected probability, never the raw claim. Re-derive nothing
# retroactively (LAW 3); from the fix forward, every recommendation carries
# the correction that was current."

#: The live record's baseball total fit for the reasoning pass, version 2
#: (measured 2026-09-26), put on this world's category.
_SKEWED = dict(slope=0.449, intercept=-0.270, n_train=106)


def _away_pick(conn, *, game="g0", created="2026-09-07T00:00:00Z",
               claimed="2026-09-07T01:30:00Z", confidence=0.57, price=0.485,
               predictor="statistical", pass_kind="final"):
    """The away side at 57%, so a claim of 43% on the home side, line-less,
    against a 48.5c price: the no side, raw, at +3.5c."""
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES (?, 'mlb', ?,"
        " 'moneyline', 'BBB', NULL, ?, 'win', ?, ?, 'fs2',"
        " ?, 'test')", (created, game, confidence, predictor, pass_kind, WHOLE))
    pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
        " implied_prob, kind) VALUES (?, ?, 'test', ?, 'open_at_predict')",
        (pid, claimed, price))
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
        " VALUES ('kalshi', ?, 'e', 'mlb', ?, 'moneyline', 'home_win', NULL,"
        " 'home', ?, ?, ?)",
        (f"t{pid}", game, price - 0.01, price + 0.01, claimed))
    quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', ?, 'moneyline', 'home_win', NULL,"
        " 'home', 'line_less', NULL, NULL, ?, ?, ?, 'mid', ?)",
        (pid, quote, game, round(1.0 - confidence, 6), price, price, claimed))
    conn.commit()
    shortlist.rank_rows(conn, [pid])
    return pid


def _correct(conn, *, active_from="2026-09-01T00:00:00Z", **model):
    """A correction written inactive and, unless `active_from` is None, put
    in force by its own row at that instant: a scratch activation, the one
    lawful way a test world has (operator question 32, 2026-09-29)."""
    from gridiron import correction

    version = correction.record_fit(
        conn, sport="mlb", market_type="moneyline", forecaster="statistical",
        model=correction.Platt(**(model or _SKEWED)), status="test",
        fitted_utc="2026-09-01T00:00:00Z")
    if active_from is not None:
        fid = conn.execute(
            "SELECT id FROM calibration_corrections WHERE sport = 'mlb'"
            " AND market_type = 'moneyline' AND forecaster = 'statistical'"
            " AND version = ?", (version,)).fetchone()[0]
        correction.activate_in_a_scratch_world(conn, fid, now=active_from)
    return version


def test_an_active_correction_that_would_flip_the_side_flips_the_pick(tmp_path):
    conn = _world(tmp_path)
    pid = _away_pick(conn)
    raw = recommend.for_predictions(conn, [pid], now=ASKED)[0]
    assert (raw["side"], raw["edge_cents"]) == ("no", pytest.approx(3.5))
    assert raw["correction_version"] is None
    assert raw["fair_value"] == raw["raw_fair_value"] == pytest.approx(0.43)
    version = _correct(conn)
    got = recommend.for_predictions(conn, [pid], now=ASKED)[0]
    assert got["side"] == "yes" and got["edge_side"] == "yes"
    assert got["edge_cents"] == pytest.approx(3.08, abs=0.01)
    assert got["fair_value"] == pytest.approx(0.5358, abs=1e-4)
    assert got["raw_fair_value"] == pytest.approx(0.43)
    assert got["correction_version"] == version


def test_a_fitted_correction_that_was_never_activated_decides_nothing(tmp_path):
    conn = _world(tmp_path)
    pid = _away_pick(conn)
    from gridiron import correction

    _correct(conn, active_from=None)
    got = recommend.for_predictions(conn, [pid], now=ASKED)[0]
    assert got["side"] == "no" and got["correction_version"] is None
    # AND AN ACTIVATION STAMPED AHEAD IS NO ACTIVATION (question 32,
    # 2026-09-29): a row is stamped when it is written, so one dated 2099 --
    # which this test once used to stand for "not in force yet" -- is refused,
    # and the fit stays out of force
    with pytest.raises(correction.ActivationRefused, match="stamped when it is written"):
        _correct(conn, active_from="2099-01-01T00:00:00Z")
    assert recommend.for_predictions(conn, [pid], now=ASKED)[0]["side"] == "no"


def test_the_row_carries_the_correction_that_was_current_and_keeps_it(tmp_path):
    conn = _world(tmp_path)
    before = _away_pick(conn, game="g0")
    recommend.record_for(conn, [before], now=ASKED)
    version = _correct(conn)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g9', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')")
    after = _away_pick(conn, game="g9")
    recommend.record_for(conn, [after], now=ASKED)
    rows = {r["prediction_id"]: r for r in conn.execute(
        "SELECT * FROM recommendations ORDER BY id")}
    # WRITTEN BEFORE THE ACTIVATION: the raw no side and no correction, and
    # nothing re-derived when one arrived (LAW 3).
    first = rows[before]
    assert first["side"] == "no" and first["fair_value"] == pytest.approx(0.43)
    assert first["correction_version"] is None
    assert first["calibrated_fair_value"] is None
    # WRITTEN UNDER IT: the raw claim's number where it always was, the number
    # the side was chosen from beside it, and the version
    row = rows[after]
    assert row["side"] == "yes" and row["fair_value"] == pytest.approx(0.43)
    assert row["calibrated_fair_value"] == pytest.approx(0.5358, abs=1e-4)
    assert row["correction_version"] == version
    assert row["edge_cents"] == pytest.approx(3.08, abs=0.01)
    # FROZEN WITH IT, even to "no correction" -- which the pairing would allow
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        conn.execute("UPDATE recommendations SET correction_version = NULL,"
                     " calibrated_fair_value = NULL WHERE id = ?", (row["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        conn.execute("UPDATE recommendations SET calibrated_fair_value = 0.6,"
                     " correction_version = 9 WHERE id = ?", (first["id"],))
    # and a version is never written without its number, nor a number without
    # its version, nor a number that is not a probability. On a market of the
    # game with nothing standing: g9's moneyline holds `after`, and a second
    # there is refused before any CHECK is read (item 5, 2026-09-26).
    for version_, number in ((2, None), (None, 0.5), (2, 1.0)):
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute(
                "INSERT INTO recommendations (prediction_id, sport, game_id,"
                " market, side, fair_value, price, edge_cents, size_kind,"
                " size_units, gate_n, created_utc, correction_version,"
                " calibrated_fair_value) VALUES (?, 'mlb', 'g9', 'spread',"
                " 'yes', 0.43, 0.485, 3.0, 'flat', 1.0, 0,"
                " '2099-01-01T00:00:00Z', ?, ?)", (after, version_, number))


def test_the_card_the_line_sentence_and_the_pregame_figure_read_one_number(tmp_path):
    """ONE DOOR ON THE PAGE TOO. With a correction in force, the price row's
    model chip, the at-the-line sentence beside it and the recommendation line
    all state the corrected number; a live card's pregame figure is the claim
    corrected by the version in force when the claim was written."""
    from gridiron import views

    conn = _world(tmp_path, kickoff="2099-01-01T00:00:00Z")
    pid = _away_pick(conn)
    _correct(conn)
    entry = recommend.for_predictions(conn, [pid])[0]
    beside = views._at_the_line(conn, "mlb", [pid], {})[pid]
    assert beside["model_prob"] == pytest.approx(entry["fair_value"], abs=1e-4)
    assert "is a 54% chance" in beside["words"]
    # THE PAGE READS AN ENTRY AS IT DRAWS IT (pick-number step A,
    # 2026-09-30): its numbers named by the line they belong to; a claim's
    # numbers handed straight to the card are refused by name.
    with pytest.raises(language.LineNotNamed):
        views._today_card(entry, {"prediction_id": pid, "phrase": "x"},
                          taken=False, group_tier=None, unit_dollars=None)
    # THE CARD HEADLINES THE CONTRACT ITS RECOMMENDATION BUYS (operator
    # question 37, ruled 2026-10-05). The corrected 54% makes the home side,
    # AAA, the one worth buying -- the other side of the model's "BBB to win"
    # -- so the card names AAA with AAA's 54%, and the model's own side and
    # number beside it. (Until the ruling the chip was "46¢", BBB's, beside
    # AAA's size; a card handed no market at all cannot word the side bought
    # and is refused by name.)
    asked = {"prediction_id": pid, "phrase": "BBB to win", "sport": "mlb",
             "market_type": "moneyline", "subject": "BBB", "opponent": "AAA",
             "model_side": "win", "line_asked": None}
    from gridiron import subjects

    with pytest.raises(subjects.UnplaceableSide):
        views._today_card(views._as_the_page_draws(entry),
                          {"prediction_id": pid, "phrase": "x"},
                          taken=False, group_tier=None, unit_dollars=None)
    card = views._today_card(views._as_the_page_draws(entry), asked,
                             taken=False, group_tier=None, unit_dollars=None)
    assert card["question"] == "AAA to win" and card["model_words"] == "54¢"
    assert card["own_side_words"] == "The model's own side: BBB to win, 46%"
    # THE LINE STATES THE SIDE IT BUYS (pick-number finding 4, 2026-09-30):
    # the corrected 54% makes the home side the one worth buying, so the line
    # names it, in its own words, with its own number -- where the card it
    # is handed names the away side the model took.
    line = views._recommendations_block(
        conn, [{"prediction_id": pid, "on_shortlist": True, "phrase": "BBB to win",
                "sport": "mlb", "market_type": "moneyline", "subject": "BBB",
                "opponent": "AAA", "model_side": "win", "line_asked": None}])
    assert entry["side"] == "yes"
    assert line["lines"][0]["words"].startswith("AAA to win — the model makes it 54¢")
    # A LIVE CARD: the claim's own instant. A correction activated after the
    # claim was written does not reach the pregame figure.
    assert views._pregame_probability(conn, entry, {}) == pytest.approx(0.5358, abs=1e-4)
    later = _world(tmp_path / "later", kickoff="2099-01-01T00:00:00Z")
    lpid = _away_pick(later)
    _correct(later, active_from="2026-09-08T00:00:00Z")
    assert views._pregame_probability(later, {"prediction_id": lpid}, {}) \
        == pytest.approx(0.43)


def test_a_finished_games_pick_is_never_re_derived_by_a_later_correction(tmp_path):
    """RE-DERIVE NOTHING RETROACTIVELY, ON THE PAGE TOO (the prover of item 3,
    2026-09-26). A finished game is still priced for the Today block and the
    recommendation lines, and the pick read the correction in force NOW: a
    correction that activated on the 20th turned a pick on a game played on
    the 9th to the yes side, while the at-the-line sentence on the same card
    kept the claim's 43%. Once a game has started, its pick is corrected by
    what was in force when its claim was written, as the sentence is.

    AND FROM 2026-10-07 A FINISHED GAME HAS NO PICK AT ALL (operator question
    38, ruling 2: "recommend.for_predictions refuses any game that is not
    still upcoming"): no price, side, edge or size at any clock after its
    start, so nothing about it can be re-derived; the recommendation written
    while it was to come stands as written, and the sentence beside the card
    keeps the claim's own instant."""
    from gridiron import views

    conn = _world(tmp_path, kickoff="2026-09-09T00:00:00Z")
    pid = _away_pick(conn)                    # its claim: 2026-09-07T01:30Z
    recommend.record_for(conn, [pid], now=ASKED)
    conn.execute("UPDATE games SET status = 'final', home_score = 2,"
                 " away_score = 1 WHERE id = 'g0'")
    conn.commit()
    _correct(conn, active_from="2026-09-20T00:00:00Z")
    assert recommend.for_predictions(conn, [pid]) == []
    assert recommend.for_predictions(conn, [pid], now=ASKED) == []
    beside = views._at_the_line(conn, "mlb", [pid], {})[pid]
    assert beside["model_prob"] == pytest.approx(0.43)
    row = conn.execute("SELECT side, correction_version FROM recommendations").fetchone()
    assert (row["side"], row["correction_version"]) == ("no", None)
    # A CORRECTION IN FORCE WHEN THE CLAIM WAS WRITTEN is the one that was
    # current for it, and the finished card's sentence keeps it.
    earlier = _world(tmp_path / "earlier", status="final",
                     kickoff="2026-09-09T00:00:00Z")
    epid = _away_pick(earlier)
    _correct(earlier, active_from="2026-09-01T00:00:00Z")
    assert recommend.for_predictions(earlier, [epid]) == []
    beside = views._at_the_line(earlier, "mlb", [epid], {})[epid]
    assert beside["model_prob"] == pytest.approx(0.5358, abs=1e-4)


def test_the_size_is_computed_from_the_corrected_claim(tmp_path, monkeypatch):
    """THE SIZE READS THE NUMBER THE SIDE READS (the prover of item 3,
    2026-09-26). Below a market's gate every size is one flat unit, so the
    flip test cannot tell which number the size was asked about; a copy of
    the fix that sized from the raw claim passed every item-3 test. Above
    the gate, a quarter of Kelly on the raw 43% against a 48.5c yes price is
    nothing, and on the corrected 54% it is a stake."""
    monkeypatch.setattr(config, "MIN_SAMPLE_FOR_EDGE_CLAIM", 0)
    monkeypatch.setattr(recommend, "measured_edge", lambda conn, **_: {
        "ahead": True, "n": 100, "model_brier": 0.2, "market_brier": 0.25,
        "why": "measured and ahead, in this test"})
    conn = _world(tmp_path)
    pid = _away_pick(conn)
    _correct(conn)
    got = recommend.for_predictions(conn, [pid], now=ASKED)[0]
    assert got["side"] == "yes" and got["size"]["kind"] == "fraction"
    corrected = recommend.size_for(model_prob=got["fair_value"], price=0.485,
                                   settled=got["gate_n"], measured_edge=True)
    raw = recommend.size_for(model_prob=0.43, price=0.485,
                             settled=got["gate_n"], measured_edge=True)
    assert raw["units"] == 0 < corrected["units"]
    assert got["size"]["units"] == pytest.approx(corrected["units"], abs=1e-3)


def test_a_correction_reaches_only_its_own_forecasters_picks(tmp_path):
    """A CORRECTION IS ITS OWN CATEGORY'S -- sport, market type AND forecaster
    (the prover of item 3, 2026-09-26). The statistical pass's fit in force
    leaves the reasoning pass's pick, on another game with the same numbers,
    exactly where its raw claim prices it."""
    conn = _world(tmp_path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g9', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')")
    ours = _away_pick(conn)
    theirs = _away_pick(conn, game="g9", predictor="llm")
    version = _correct(conn)
    got = {e["prediction_id"]: e
           for e in recommend.for_predictions(conn, [ours, theirs], now=ASKED)}
    assert (got[ours]["side"], got[ours]["correction_version"]) == ("yes", version)
    assert (got[theirs]["side"], got[theirs]["correction_version"]) == ("no", None)
    assert got[theirs]["fair_value"] == pytest.approx(0.43)


# --- the return on what the side costs (GRIDIRON_REPAIR item 4) --------------
#
# The operator's ruling of 2026-09-23, built 2026-09-26: "Return-on-stake
# denominator: a no-side edge divides by the no-side cost. Re-grade the three
# recommendations it let through as 'would not have cleared'. Planting."

def test_a_no_side_edge_is_a_share_of_what_the_no_side_costs():
    """REC 3'S NUMBERS: 2.09c on the no side of a 37.5c yes price. On the yes
    price it read 5.6% and cleared; the no side costs 62.5c, and on that it
    is 3.3%, under the 5% bar. The words name the cost to the tenth of a
    cent -- the old words rounded the yes price to 38c and called that what
    the pick cost."""
    got = recommend.clears_the_bar(2.09, 0.375, side="no")
    assert got["clears"] is False
    assert got["return_on_stake"] == pytest.approx(0.0334)
    assert "3.3%" in got["why"] and "62.5¢" in got["why"] and "5%" in got["why"]
    assert recommend.return_on_stake(2.09, 0.375, side="no") == pytest.approx(0.0334)
    # the yes side of the same price is divided by the price, as it always was
    assert recommend.return_on_stake(2.09, 0.375, side="yes") == pytest.approx(0.0557)


def test_above_fifty_cents_a_real_no_side_edge_now_clears():
    """THE MIRROR (prediction 1774 in THE READ of 2026-09-23): 2.5c on the no
    side of a 50.5c yes price was 4.95% of the yes price and refused; it is
    5.05% of the 49.5c the no side costs."""
    got = recommend.clears_the_bar(2.5, 0.505, side="no")
    assert got["clears"] is True
    assert got["return_on_stake"] == pytest.approx(0.0505)
    assert "49.5¢" in got["why"]


def test_the_bar_cannot_be_asked_without_naming_the_side():
    """A KEYWORD WITH NO DEFAULT: a caller that forgets the side is a
    TypeError, not a quiet division by the yes price. A side that is neither
    is refused by name, and an unknown side has no return rather than one."""
    with pytest.raises(TypeError):
        recommend.clears_the_bar(2.09, 0.375)
    with pytest.raises(TypeError):
        recommend.return_on_stake(2.09, 0.375)
    with pytest.raises(TypeError):
        recommend.clears_the_bar(2.09, 0.375, "no")       # not positionally either
    with pytest.raises(ValueError, match="'yes' or 'no'"):
        recommend.return_on_stake(2.09, 0.375, side="home")
    assert recommend.return_on_stake(2.09, 0.375, side=None) is None
    assert recommend.clears_the_bar(2.09, 0.375, side=None)["clears"] is False
    # a price that is not a price has no return, on either side
    assert recommend.return_on_stake(2.0, 1.0, side="no") is None
    assert recommend.return_on_stake(2.0, 0.0, side="yes") is None


def test_the_edge_did_not_move_when_it_shared_the_cost_with_the_return():
    """`edge_cents` asks `_cost_of` now instead of working the cost out for
    itself. Bit for bit what it was, on both sides, across the price range."""
    def before(model_prob, price, side):
        if side == "yes":
            raw, cost = model_prob - price, price
        else:
            raw, cost = (1.0 - model_prob) - (1.0 - price), 1.0 - price
        return round((raw - recommend.fee(cost)) * 100.0, 2)

    for p in (0.05, 0.3341, 0.43, 0.5, 0.54, 0.62, 0.91):
        for c in (0.02, 0.2, 0.375, 0.485, 0.505, 0.89, 0.98):
            for side in ("yes", "no"):
                assert recommend.edge_cents(p, c, side) == before(p, c, side)


def test_rec_3s_numbers_are_not_recommended_and_the_mirror_is(tmp_path):
    """THROUGH THE ONE CALL SITE. Rec 3's numbers leave the pick with no side
    -- the edge still on the no side, with its number on the card -- and
    nothing is written; the mirror's is recommended on the no side."""
    conn = _world(tmp_path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g1', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')")
    dear = _away_pick(conn, confidence=0.6659, price=0.375)
    mirror = _away_pick(conn, game="g1", confidence=0.54, price=0.505)
    got = {e["prediction_id"]: e
           for e in recommend.for_predictions(conn, [dear, mirror], now=ASKED)}
    a, b = got[dear], got[mirror]
    assert (a["edge_side"], a["edge_cents"]) == ("no", pytest.approx(2.09))
    assert a["side"] is None
    assert a["return_on_stake"] == pytest.approx(0.0334)
    assert "62.5¢" in a["side_why"]
    assert (b["side"], b["edge_cents"]) == ("no", pytest.approx(2.5))
    assert b["return_on_stake"] == pytest.approx(0.0505)
    counts = recommend.record_for(conn, [dear, mirror], now=ASKED)
    assert counts["recommended"] == 1 and counts["no_side"] == 1
    row = conn.execute("SELECT prediction_id, side FROM recommendations").fetchone()
    assert (row["prediction_id"], row["side"]) == (mirror, "no")


def test_a_pick_with_no_side_carries_no_return(tmp_path):
    """NO SIDE, NO RETURN: when neither side clears the fee there is no cost
    to divide by, and the entry says None rather than a share of the yes
    price (absent is not zero)."""
    conn = _world(tmp_path)
    pid = _pick(conn, prob=0.51, implied=0.50)
    entry = recommend.for_predictions(conn, [pid], now=ASKED)[0]
    assert entry["side"] is None and entry["edge_side"] is None
    assert entry["return_on_stake"] is None


def _recorded(conn, rid, *, side, price, edge, created, fair=0.40, pid=None):
    """A recommendation as the record holds one, written straight in.

    EACH ON A GAME OF ITS OWN (GRIDIRON_REPAIR item 5, 2026-09-26): one game
    and market hold one recommendation, so a row here is a game here -- as
    recs 3, 10 and 26 were on the record. What these tests read is the
    row's own side, price and edge.

    AND ON A FORECAST OF ITS OWN GAME (operator question 22, 2026-09-28): a
    count of recommendations reads whose each is and which distinct bet
    through the forecast it was made from, and every recommendation on the
    record is made from a forecast of its own game. So `pid`'s forecast is
    written again on this row's game -- the fields the counts read, and
    nothing else, as the record's own rows carry them -- and the row cites
    that copy: sharing one forecast, these rows were one question on both
    sides, which no record holds."""
    game = f"r{rid}"
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')",
        (game,))
    if pid is not None:
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " prop_type, subject, line_asked, model_prob, model_side,"
            " predictor, pass_kind, factor_set_version, factors_json,"
            " reasoning) SELECT created_utc, sport, ?, market_type, prop_type,"
            " subject, line_asked, model_prob, model_side, predictor,"
            " pass_kind, factor_set_version, factors_json, reasoning"
            "  FROM predictions WHERE id = ?", (game, pid))
        pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    conn.execute(
        "INSERT INTO recommendations (id, prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc) VALUES (?, ?, 'mlb', ?, 'spread', ?, ?, ?, ?, 'flat',"
        " 1.0, 53, ?)", (rid, pid, game, side, fair, price, edge, created))


def _let_through_world(tmp_path, *, with_56=False):
    """Recs 3, 10 and 26 as the record holds them, and around them the rows
    the rule must leave alone."""
    conn = _world(tmp_path)
    pid = _pick(conn, implied=None)
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-06T00:00:00Z', 'mlb', 'g0', 'spread', 'AAA', -1.5,"
        " 0.62, 'cover', 'statistical', 'final', 'fs2', ?, 'test')", (WHOLE,))
    early = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    # WRITTEN BEFORE THE BAR WAS DECLARED: nothing let it through, because
    # nothing was asked. Written first, as its stamp says it was: from
    # 2026-09-27 (question 13's prover) no recommendation is written under a
    # number below one already given out, the rule that keeps a number read
    # one way by the rules and another by the key from writing over one.
    _recorded(conn, 2, side="no", price=0.375, edge=2.09,
              created="2026-09-06T23:59:59Z", pid=early)
    rows = [(3, "no", 0.375, 2.09, "2026-09-07T20:52:31Z"),
            (10, "no", 0.375, 2.30, "2026-09-08T21:33:31Z"),
            (26, "no", 0.395, 2.84, "2026-09-09T21:32:20Z"),
            # the no side above 50c: 5.05% of its 49.5c cost -- clears
            (30, "no", 0.505, 2.50, "2026-09-10T00:00:00Z"),
            # the no side with room to spare: 5.6% of 62.5c -- clears
            (31, "no", 0.375, 3.50, "2026-09-10T00:00:01Z"),
            # the yes side: its divisor was always its cost -- 10% of 20c
            (32, "yes", 0.20, 2.00, "2026-09-10T00:00:02Z"),
            # let through by the yes price, and withdrawn: shown as withdrawn
            (33, "no", 0.375, 2.09, "2026-09-10T00:00:03Z")]
    if with_56:
        rows.append((56, "no", 0.39, 3.03, "2026-09-24T05:21:25Z"))
    for rid, side, price, edge, created in rows:
        _recorded(conn, rid, side=side, price=price, edge=edge,
                  created=created, pid=pid)
    conn.execute("INSERT INTO recommendation_voids (recommendation_id,"
                 " voided_utc, reason) VALUES (33, '2026-09-11T00:00:00Z',"
                 " 'withdrawn in this test world')")
    conn.commit()
    return conn


def test_the_regrade_is_chosen_by_rule_from_the_frozen_row(tmp_path):
    conn = _let_through_world(tmp_path)
    got = recommend.let_through_by_the_yes_price(conn)
    assert [g["id"] for g in got] == [3, 10, 26]
    by = {g["id"]: g for g in got}
    assert (by[3]["side_cost"], by[3]["return_on_cost"],
            by[3]["return_on_yes_price"]) == (0.625, pytest.approx(0.0334),
                                              pytest.approx(0.0557))
    assert by[26]["side_cost"] == pytest.approx(0.605)
    assert by[26]["return_on_cost"] == pytest.approx(0.0469)
    assert not any(g["already"] for g in got)
    assert "62.5¢ the no side cost it is 3.34%" in by[3]["reason"]
    # AND NEVER BY OUTCOME: nothing about how the games went is read
    assert "outcome" not in by[3] and "clv_cents" not in by[3]


def test_a_regrade_is_written_once_for_ids_the_arithmetic_supports(tmp_path):
    conn = _let_through_world(tmp_path)
    with pytest.raises(ValueError, match=r"\[32\]"):
        recommend.write_regrades(conn, [3, 32])
    assert conn.execute("SELECT COUNT(*) FROM recommendation_regrades").fetchone()[0] == 0
    assert recommend.write_regrades(conn, [3, 10, 26]) == {"written": 3, "already": 0}
    assert recommend.write_regrades(conn, [3, 10, 26]) == {"written": 0, "already": 3}
    rows = conn.execute("SELECT * FROM recommendation_regrades ORDER BY 1").fetchall()
    assert [r["recommendation_id"] for r in rows] == [3, 10, 26]
    assert {r["verdict"] for r in rows} == {recommend.WOULD_NOT_HAVE_CLEARED}
    assert all(r["minimum_return"] == config.MIN_RETURN_ON_STAKE for r in rows)
    # THE RECOMMENDATIONS THEMSELVES ARE UNTOUCHED (LAW 3)
    rec = conn.execute("SELECT side, price, edge_cents FROM recommendations"
                       " WHERE id = 3").fetchone()
    assert tuple(rec) == ("no", 0.375, 2.09)


def test_a_regrade_is_true_and_permanent(tmp_path):
    conn = _let_through_world(tmp_path)
    recommend.write_regrades(conn, [3])

    def insert(rid, *, cost, got, on_yes, at="2026-09-26T00:00:00Z",
               reason="the bar divided by the yes price", verb="INSERT"):
        conn.execute(
            f"{verb} INTO recommendation_regrades (recommendation_id,"
            " regraded_utc, verdict, side_cost, return_on_cost,"
            " return_on_yes_price, minimum_return, reason)"
            " VALUES (?, ?, 'would_not_have_cleared', ?, ?, ?, 0.05, ?)",
            (rid, at, cost, got, on_yes, reason))

    # a pick that clears on its own cost, however it is stated
    with pytest.raises(sqlite3.IntegrityError, match="numbers are that"):
        insert(32, cost=0.20, got=0.10, on_yes=0.10)
    with pytest.raises(sqlite3.IntegrityError, match="numbers are that"):
        insert(32, cost=0.20, got=0.02, on_yes=0.10)
    with pytest.raises(sqlite3.IntegrityError, match="numbers are that"):
        insert(10, cost=0.375, got=0.0613, on_yes=0.0613)   # the yes price as cost
    with pytest.raises(sqlite3.IntegrityError, match="after the recommendation"):
        insert(10, cost=0.625, got=0.0368, on_yes=0.0613, at="2026-09-08T21:33:31Z")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert(10, cost=0.625, got=0.0368, on_yes=0.0613, reason="short")
    with pytest.raises(sqlite3.IntegrityError, match="never replaced"):
        insert(3, cost=0.625, got=0.0334, on_yes=0.0557, verb="INSERT OR REPLACE")
    with pytest.raises(sqlite3.IntegrityError, match="cannot be rewritten"):
        conn.execute("UPDATE recommendation_regrades SET reason = 'a different one'")
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM recommendation_regrades")
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM recommendation_regrades").fetchone()[0] == 1


def test_a_regrade_labels_only_what_the_yes_price_let_through(tmp_path):
    """THE PROVER OF ITEM 4 (2026-09-26). The table checked a label's figures
    against the row but took the bar from the label, trusted its figures
    within a tolerance, and took any row -- so each of these, on the row's
    own numbers, was taken as "would not have cleared". The one exception is
    rec 32 read as if on the no side, which the rule now needs the side to
    refuse, because it reads the no side's cost off the row."""
    conn = _let_through_world(tmp_path)
    # 4.996% of the 62.45c the no side costs: the bar rounds it to 5.0% and
    # clears it, so it was written, rightly
    _recorded(conn, 34, side="no", price=0.3755, edge=3.12,
              created="2026-09-10T00:00:05Z",
              pid=conn.execute("SELECT prediction_id FROM recommendations"
                               " WHERE id = 3").fetchone()[0])
    assert recommend.clears_the_bar(3.12, 0.3755, side="no")["clears"] is True

    def insert(rid, *, cost, got, on_yes, minimum=0.05):
        conn.execute(
            "INSERT INTO recommendation_regrades (recommendation_id,"
            " regraded_utc, verdict, side_cost, return_on_cost,"
            " return_on_yes_price, minimum_return, reason)"
            " VALUES (?, '2026-09-26T00:00:00Z', 'would_not_have_cleared',"
            " ?, ?, ?, ?, 'the bar divided by the yes price')",
            (rid, cost, got, on_yes, minimum))

    refused = "one the yes price let through"
    # rec 31 cleared 5.6% of its 62.5c: not under a bar it was never asked
    with pytest.raises(sqlite3.IntegrityError, match=refused):
        insert(31, cost=0.625, got=0.056, on_yes=0.0933, minimum=0.08)
    # rec 32 cleared 10% of its 20c on the yes side: not as if it were no
    with pytest.raises(sqlite3.IntegrityError, match=refused):
        insert(32, cost=0.80, got=0.025, on_yes=0.10)
    # rec 34, cleared at the bar's own four places, stated a hair under
    with pytest.raises(sqlite3.IntegrityError, match=refused):
        insert(34, cost=0.6245, got=0.04991, on_yes=0.0831)
    # rec 30, the no side above 50c: the yes price never passed it
    with pytest.raises(sqlite3.IntegrityError, match=refused):
        insert(30, cost=0.495, got=0.0505, on_yes=0.0495, minimum=0.06)
    # rec 2, rec 3's numbers written before the bar was declared
    with pytest.raises(sqlite3.IntegrityError, match=refused):
        insert(2, cost=0.625, got=0.0334, on_yes=0.0557)
    conn.rollback()
    # and the true ones, as `write_regrades` states them, are taken
    assert recommend.write_regrades(conn, [3, 10, 26]) == {"written": 3,
                                                          "already": 0}


def test_the_regrade_rule_pins_the_bar_as_declared():
    """The schema cannot read config, so the bar and the day it was declared
    are written into the rule -- as the activation gate's birthday is -- and
    must be the config's own."""
    from pathlib import Path

    schema = (Path(db.__file__).resolve().parent / "schema.sql").read_text(
        encoding="utf-8")
    at = schema.index(
        "CREATE TRIGGER IF NOT EXISTS recommendation_regrade_is_its_own_arithmetic")
    trigger = schema[at:schema.index("END;", at)]
    assert f"NEW.minimum_return = {config.MIN_RETURN_ON_STAKE}" in trigger
    assert f"'{config.MIN_RETURN_ON_STAKE_DECLARED}'" in trigger
    assert "r.side = 'no'" in trigger


def test_the_closing_line_names_a_regrade_and_counts_it_where_it_was(tmp_path):
    """A LABEL, NOT A WITHDRAWAL. Every count the closing line gives is the
    same before and after; beside it, "would not have cleared", with its N
    and the return on what each side cost."""
    conn = _let_through_world(tmp_path)

    def mine(report):
        # ONE FORECASTER'S LINE (operator question 22, 2026-09-28): the
        # world's recommendations are the statistical model's
        return next(b for b in report["forecasters"]
                    if b["predictor"] == "statistical")

    before = calibration.clv_report(conn, sport="mlb")
    assert mine(before)["regraded"] == 0 and mine(before)["regraded_line"] is None
    recommend.write_regrades(conn, [3, 10, 26])
    after = calibration.clv_report(conn, sport="mlb")
    for key in ("n", "unmeasured", "restated", "unaccounted", "awaiting_close",
                "withdrawn"):
        assert mine(after)[key] == mine(before)[key], key
    assert mine(after)["regraded"] == 3
    # the reasoning pass's line holds none of them
    theirs = next(b for b in after["forecasters"] if b["predictor"] == "llm")
    assert theirs["regraded"] == 0 and theirs["regraded_line"] is None
    line = mine(after)["regraded_line"]
    assert line["label"] == "Would not have cleared, statistical" and line["n"] == 3
    assert line["words"].startswith("3 recommendations would not have cleared")
    assert "3.34%, 3.68% and 4.69%" in line["words"] and "5%" in line["words"]
    assert "counted where they were" in line["words"]
    assert audit.plain_words_violations(line["words"]) == []
    assert audit.advice_word_faults(line["words"]) == []
    calibration.assert_every_figure_has_n(after)
    audit.check_no_withdrawn_recommendation_counted(conn, after)
    # rec 56's 4.97% is never printed as "5.0%, under the 5%"
    assert "4.97%" in language.regraded_recommendations_line([(0.0497, 0.05)])
    assert language.regraded_recommendations_line([(0.0334, 0.05)]).startswith(
        "1 recommendation would not have cleared the bar: its edge")


def test_a_record_without_the_table_has_regraded_nothing(tmp_path):
    """The gate and the dry runs read the live record without applying the
    schema; a reader must not stop at a table the record does not hold yet."""
    conn = _let_through_world(tmp_path)
    conn.execute("DROP TABLE recommendation_regrades")
    assert recommend.regraded(conn, sport="mlb", predictor="statistical") == []
    assert [g["id"] for g in recommend.let_through_by_the_yes_price(conn)] == [3, 10, 26]
    with pytest.raises(RuntimeError, match="db.init"):
        recommend.write_regrades(conn, [3])


def test_the_renderer_draws_the_regrade_beside_the_closing_line():
    from pathlib import Path

    js = (Path(recommend.__file__).resolve().parents[1] / "web" / "app.js").read_text(
        encoding="utf-8")
    # EACH FORECASTER'S LINE (operator question 22, 2026-09-28)
    assert "block.regraded_line" in js
    at = js.index("block.regraded_line")
    assert "requireN(regraded" in js[at:at + 400]


def _regrade_tool():
    import importlib.util

    path = config.PACKAGE_ROOT.parent / "tools" / "regrade_return_on_stake.py"
    spec = importlib.util.spec_from_file_location("regrade_tool_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_tool_writes_the_ruled_set_once_and_reads_only_until_told(tmp_path, capsys):
    """QUESTION 9, RULED 2026-09-27: "label all four: 3, 10, 26, 56". The
    world holds all four as the live record does."""
    tool = _regrade_tool()
    assert tool.RULED == (3, 10, 26, 56) and tool.LEFT_BY_RULING == ()
    path = tmp_path / "rec.db"
    _let_through_world(tmp_path, with_56=True).close()
    assert tool.main(["--database", str(path)]) == 0
    out = capsys.readouterr().out
    assert "4 recommendation(s) cleared 5% of the yes price" in out
    assert "nothing written" in out
    check = db.connect(path)
    assert check.execute("SELECT COUNT(*) FROM recommendation_regrades").fetchone()[0] == 0
    check.close()
    assert tool.main(["--database", str(path), "--write"]) == 0
    assert tool.main(["--database", str(path), "--write"]) == 0     # idempotent
    assert "4 already re-graded" in capsys.readouterr().out
    check = db.connect(path)
    assert [r[0] for r in check.execute(
        "SELECT recommendation_id FROM recommendation_regrades ORDER BY 1")] == [3, 10, 26, 56]


def test_the_tool_refuses_a_ruled_recommendation_the_rule_does_not_select(tmp_path, capsys):
    """THE OTHER DIRECTION: rec 56 is ruled, and a record where the rule does
    not select it (here, a world without it) is refused by name, nothing
    written -- a re-grade is permanent, and the ruling is checked against the
    arithmetic, never taken on trust."""
    tool = _regrade_tool()
    path = tmp_path / "rec.db"
    _let_through_world(tmp_path).close()
    with pytest.raises(SystemExit) as exc:
        tool.main(["--database", str(path), "--write"])
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "REFUSED, NOTHING WRITTEN" in out and "[56]" in out
    check = db.connect(path)
    assert check.execute("SELECT COUNT(*) FROM recommendation_regrades").fetchone()[0] == 0


def test_the_tool_refuses_a_selection_the_ruling_did_not_name(tmp_path, capsys):
    """REC 56, AS THE LIVE RECORD HOLDS IT ON 2026-09-26: let through by the
    yes price after the ruling was measured. Under the reading the operator
    did NOT take ("the three", set here in the test), the tool names the
    fourth and writes nothing -- the refusal the live record met until
    question 9 was ruled."""
    tool = _regrade_tool()
    tool.RULED = (3, 10, 26)
    path = tmp_path / "rec.db"
    _let_through_world(tmp_path, with_56=True).close()
    with pytest.raises(SystemExit) as exc:
        tool.main(["--database", str(path), "--write"])
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "REFUSED, NOTHING WRITTEN" in out and "rec 56" in out
    assert "4.97% of the 61.0c" in out
    check = db.connect(path)
    assert check.execute("SELECT COUNT(*) FROM recommendation_regrades").fetchone()[0] == 0


def test_the_tool_refuses_live_on_anything_but_the_record(tmp_path):
    tool = _regrade_tool()
    path = tmp_path / "rec.db"
    _let_through_world(tmp_path).close()
    with pytest.raises(SystemExit) as exc:
        tool.main(["--database", str(path), "--write", "--live"])
    assert exc.value.code == 2


def _read(conn, pid, *, at, bid, ask, ticker=None, kind="near_start",
          last=None):
    """A later look at the venue. The recommendation's own contract unless told
    otherwise: `_pick` prices from ticker t<pid>."""
    conn.execute(
        "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
        " market, quantity, line, yes_side, yes_bid, yes_ask, last_price,"
        " fetched_utc, read_kind) VALUES ('kalshi', ?, 'e', 'mlb', 'g0',"
        " 'moneyline', 'home_margin', -1.5, 'home', ?, ?, ?, ?, ?)",
        (ticker or f"t{pid}", bid, ask, last, at, kind))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]


def _closed(tmp_path, reads, *, price_claim_shift=None):
    """A recommendation priced at 46c on a game that has started, with the
    given later reads. Returns (conn, rec row after closing, counts). The
    pass recommends before the game (operator question 38, ruling 2); the
    closer runs at the clock, after it."""
    conn = _world(tmp_path, kickoff="2026-09-07T02:00:00Z")
    pid = _pick(conn)
    recommend.record_for(conn, [pid], now=ASKED_BEFORE_THE_CLOSE)
    for read in reads:
        _read(conn, pid, **read)
    counts = recommend.record_closing_prices(conn)
    rec = conn.execute("SELECT * FROM recommendations").fetchone()
    return conn, rec, counts


def test_the_closing_line_is_measured_once_and_can_report_bad_news(tmp_path):
    # THE NEAR-START LOOK AT THE SAME CONTRACT, taken before the game started.
    # The closing line is that venue's last word on the same proposition, not
    # another venue's and not another strike's.
    conn, row, counts = _closed(tmp_path, [
        dict(at="2026-09-07T01:50:00Z", bid=0.51, ask=0.53)])
    assert counts["closed"] == 1
    # bought at 46, closed at 52: six cents better than the market's own last word
    assert row["close_price"] == pytest.approx(0.52)
    assert row["clv_cents"] == pytest.approx(6.0)
    assert row["closed_utc"]
    # and how it was measured is written beside it, in the same transaction
    how = conn.execute("SELECT * FROM recommendation_closes").fetchone()
    assert how["restated"] == 0 and how["close_price"] == pytest.approx(0.52)
    assert how["minutes_before_start"] == pytest.approx(10.0)
    # measured once
    assert recommend.record_closing_prices(conn)["closed"] == 0
    with pytest.raises(sqlite3.IntegrityError, match="measured once"):
        conn.execute("UPDATE recommendations SET close_price = 0.9,"
                     " clv_cents = 1.0, closed_utc = '2026-09-08T00:00:00Z'"
                     " WHERE id = ?", (row["id"],))


def test_the_close_is_the_last_of_two_reads_of_its_own_contract(tmp_path):
    """THE 2026-09-23 DEFECT: 49 of 49 closes were the price compared with
    itself. With two reads AFTER the price and before the start, the later one
    is the close -- both after the 01:00 pricing read, so a closer that took
    the first later read would fail here, which the review proved it could."""
    _, row, _ = _closed(tmp_path, [
        dict(at="2026-09-07T01:20:00Z", bid=0.47, ask=0.49),
        dict(at="2026-09-07T01:40:00Z", bid=0.53, ask=0.55)])
    assert row["close_price"] == pytest.approx(0.54)
    assert row["clv_cents"] == pytest.approx(8.0)


def test_a_read_identical_to_the_pricing_read_is_not_a_close(tmp_path):
    """A cached body re-stamped as a new read looks exactly like this: the
    same bid, ask, last price and volume, later. It is no evidence of a later
    price, so it is skipped -- and with nothing before it, unmeasured."""
    _, alone, counts = _closed(tmp_path, [
        dict(at="2026-09-07T01:50:00Z", bid=0.45, ask=0.47)])
    assert alone["close_price"] is None and counts["unmeasured"] == 1
    _, row, _ = _closed(tmp_path / "two", [
        dict(at="2026-09-07T01:30:00Z", bid=0.51, ask=0.53),
        dict(at="2026-09-07T01:50:00Z", bid=0.45, ask=0.47)])
    assert row["close_price"] == pytest.approx(0.52)


def test_a_start_nobody_knows_yet_is_still_open(tmp_path):
    conn = _world(tmp_path, kickoff=None)
    pid = _pick(conn)
    recommend.record_for(conn, [pid])
    assert recommend.record_closing_prices(conn) == {
        "closed": 0, "unmeasured": 0, "still_open": 1}


@pytest.mark.parametrize("wrong", [
    dict(at="2026-09-07T01:50:00Z", bid=0.29, ask=0.31, ticker="another-strike"),
    dict(at="2026-09-07T01:50:00Z", bid=0.59, ask=0.61, kind="open"),
    dict(at="2026-09-07T02:00:00Z", bid=0.89, ask=0.91),     # at the start
    dict(at="2026-09-07T02:20:00Z", bid=0.89, ask=0.91),     # after it
])
def test_no_other_read_can_close_it(tmp_path, wrong):
    """Another strike, an opening read, a read at or after the start: none is
    the close. Beside the right read, the right read wins; alone, unmeasured."""
    _, row, _ = _closed(tmp_path, [
        dict(at="2026-09-07T01:30:00Z", bid=0.51, ask=0.53), wrong])
    assert row["close_price"] == pytest.approx(0.52)
    _, alone, counts = _closed(tmp_path / "alone", [wrong])
    assert alone["closed_utc"] and alone["close_price"] is None
    assert counts["unmeasured"] == 1


def test_an_unpriced_last_read_falls_back_to_the_one_before(tmp_path):
    _, row, _ = _closed(tmp_path, [
        dict(at="2026-09-07T01:30:00Z", bid=0.51, ask=0.53),
        dict(at="2026-09-07T01:55:00Z", bid=None, ask=None)])
    assert row["close_price"] == pytest.approx(0.52)


def test_no_later_read_is_unmeasured_never_zero(tmp_path):
    conn, row, counts = _closed(tmp_path, [])
    assert counts == {"closed": 0, "unmeasured": 1, "still_open": 0}
    assert row["closed_utc"] and row["close_price"] is None
    assert row["clv_cents"] is None
    how = conn.execute("SELECT * FROM recommendation_closes").fetchone()
    assert how["close_quote_id"] is None and "no near-start read" in how["reason"]
    entry = calibration.clv_report(conn, sport="mlb")["markets"][0]
    assert entry["n"] == 0 and entry["unmeasured"] == 1
    assert entry["mean_cents"] is None
    assert "not counted" in entry["words"]
    assert audit.advice_word_faults(entry["words"]) == []
    assert audit.plain_words_violations(entry["words"]) == []


def test_a_price_that_does_not_trace_to_its_quote_is_unmeasured(tmp_path):
    """The contract is found through the claim the price came from. A later
    claim at another price, written before the recommendation, breaks the
    trail -- and the answer is unmeasured, never a guessed contract."""
    conn = _world(tmp_path, kickoff="2026-09-07T02:00:00Z")
    pid = _pick(conn)
    recommend.record_for(conn, [pid], now=ASKED_BEFORE_THE_CLOSE)
    qid = _read(conn, pid, at="2026-09-07T01:40:00Z", bid=0.51, ask=0.53)
    conn.execute(
        "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
        " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc)"
        " VALUES (?, ?, 'kalshi', 'mlb', 'g0', 'moneyline', 'home_margin', -1.5,"
        " 'home', 'rung_differs_margin', 2.0, 13.0, 0.62, 0.52, 0.52, 'mid',"
        " '2026-09-07T01:41:00Z')", (pid, qid))
    conn.commit()
    assert recommend.record_closing_prices(conn)["unmeasured"] == 1
    how = conn.execute("SELECT reason FROM recommendation_closes").fetchone()
    assert "cannot be traced" in how["reason"]


def test_an_old_close_with_no_account_is_unmeasured_until_restated(tmp_path):
    """The shape the old closer left: a close equal to the price, and nothing
    beside it. It is not read as 0.00c; restated, it is shown beside the
    closing line and never counted inside it."""
    conn = _world(tmp_path, kickoff="2026-09-07T02:00:00Z")
    pid = _pick(conn)
    recommend.record_for(conn, [pid], now=ASKED_BEFORE_THE_CLOSE)
    conn.execute("UPDATE recommendations SET close_price = price, clv_cents = 0,"
                 " closed_utc = '2026-09-07T02:10:00Z'")
    _read(conn, pid, at="2026-09-07T01:40:00Z", bid=0.51, ask=0.53)
    conn.commit()
    entry = calibration.clv_report(conn, sport="mlb")["markets"][0]
    # NOT "no later read": it has one. It simply has not been worked out yet.
    assert entry["n"] == 0 and entry["unaccounted"] == 1
    assert entry["unmeasured"] == 0
    assert "have not been worked out again" in entry["words"] or \
        "has not been worked out again" in entry["words"]

    dry = recommend.restate_old_closes(conn, write=False)
    assert dry["rows"] == 1 and dry["written"] == 0
    assert dry["by"][("mlb", "moneyline")]["clv"] == [pytest.approx(6.0)]
    assert conn.execute("SELECT COUNT(*) FROM recommendation_closes").fetchone()[0] == 0

    wrote = recommend.restate_old_closes(conn, write=True)
    assert wrote["written"] == 1
    how = conn.execute("SELECT * FROM recommendation_closes").fetchone()
    assert how["restated"] == 1 and how["clv_cents"] == pytest.approx(6.0)
    assert "own price, not a later read" in how["reason"]
    entry = calibration.clv_report(conn, sport="mlb")["markets"][0]
    assert entry["n"] == 0 and entry["restated"] == 1 and entry["unmeasured"] == 0
    assert entry["unaccounted"] == 0
    assert "worked out again afterwards" in entry["words"]
    # the recorded close stands as it was
    row = conn.execute("SELECT close_price, clv_cents FROM recommendations").fetchone()
    assert row["clv_cents"] == 0 and row["close_price"] == pytest.approx(0.46)
    # idempotent
    assert recommend.restate_old_closes(conn, write=True)["rows"] == 0


def test_the_account_of_a_close_is_append_only_and_refuses_the_old_defect(tmp_path):
    conn, row, _ = _closed(tmp_path, [
        dict(at="2026-09-07T01:50:00Z", bid=0.51, ask=0.53)])
    with pytest.raises(sqlite3.IntegrityError, match="written once"):
        conn.execute("UPDATE recommendation_closes SET clv_cents = 9")
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM recommendation_closes")
    # a second recommendation, still open, on the same prediction -- under
    # another market of its game, because one game and market hold one
    # recommendation (GRIDIRON_REPAIR item 5, 2026-09-26); the close's rules
    # read the game and the contract, never the market
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc) SELECT prediction_id, sport, game_id, 'spread', side,"
        " fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " '2099-01-01T00:00:00Z' FROM recommendations")
    open_id = conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="never for one still open"):
        conn.execute(
            "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
            " restated, reason) VALUES (?, 'x', 0, 'no later read at all')",
            (open_id,))
    how = conn.execute("SELECT pricing_quote_id FROM recommendation_closes").fetchone()
    conn.execute("UPDATE recommendations SET closed_utc = '2026-09-07T03:00:00Z'"
                 " WHERE id = ?", (open_id,))
    with pytest.raises(sqlite3.IntegrityError, match="own contract"):
        conn.execute(
            "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
            " pricing_quote_id, close_quote_id, close_price, clv_cents,"
            " restated, reason) VALUES (?, 'x', ?, ?, 0.46, 0.0, 0,"
            " 'the price compared with itself')",
            (open_id, how["pricing_quote_id"], how["pricing_quote_id"]))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO recommendation_closes (recommendation_id, written_utc,"
            " restated, reason) VALUES (?, 'x', 0, 'short')", (open_id,))


def test_the_closing_line_claims_nothing_from_a_small_sample(tmp_path):
    conn, _, _ = _closed(tmp_path, [
        dict(at="2026-09-07T01:50:00Z", bid=0.51, ask=0.53)])
    report = calibration.clv_report(conn, sport="mlb")
    entry = report["markets"][0]
    assert entry["n"] == 1 and entry["renderable"] is False
    assert "nothing is claimed" in entry["words"]
    assert "finding" not in entry
    # and the sentence for bad news exists before it is needed
    bad = language.clv_finding_line(-2.4, 60)
    assert "BUYING RICH" in bad and audit.advice_word_faults(bad) == []


def test_the_words_are_plain_and_recommend_without_tipping():
    line = language.recommendation_line(
        words="Seattle covers -4.5", fair_value=0.58, price=0.46,
        edge_cents=8.6, units=1.0, flat=True,
        size_why="no measured edge yet: 3 of 100 settled in this market")
    assert "flat unit" in line and "8.6" in line
    for words in (line, language.nothing_priced_line(18, 4, 14),
                  language.nothing_priced_line(0, 0, 0),
                  language.clv_line(10, None, None, 50),
                  language.clv_line(0, None, None, 50, unmeasured=16,
                                    restated=33)):
        assert audit.advice_word_faults(words) == [], words
        assert audit.plain_words_violations(words) == [], words


# --- one recommendation per game and market (GRIDIRON_REPAIR item 5) --------
#
# The operator's ruling of 2026-09-23, built 2026-09-26: "One recommendation
# per game and market, and never both sides. Recs 45 and 46 are the
# planting." Recs 45 and 46's numbers, put on this world's moneyline: the
# statistical forecast's 54.9% claim and the reasoning forecast's 43%, both
# against 48.5c -- the yes side at +4.45c and the no side at +3.5c.

def _both_sides(conn, *, game="g0"):
    """Rec 45's forecast and rec 46's, on one game and market, one pass."""
    over = _away_pick(conn, game=game, confidence=0.450524,
                      created="2026-09-07T00:00:00Z")
    under = _away_pick(conn, game=game, predictor="llm",
                       created="2026-09-07T00:00:07Z")
    return over, under


def _rows(conn):
    return [tuple(r) for r in conn.execute(
        "SELECT prediction_id, game_id, market, side FROM recommendations"
        " ORDER BY id")]


def _insert(conn, pid, side, created, *, game="g0", market="moneyline"):
    """A recommendation written straight into the table, round the door."""
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc) VALUES (?, 'mlb', ?, ?, ?, 0.5, 0.485, 3.5, 'flat',"
        " 1.0, 0, ?)", (pid, game, market, side, created))
    return conn.execute("SELECT MAX(id) FROM recommendations").fetchone()[0]


def test_one_pass_taking_both_sides_of_a_game_and_market_recommends_neither(tmp_path):
    """THE PASS OF 22:13:03Z ON 21 SEPTEMBER, as it ran: both forecasts clear
    the bar, on opposite sides of one game and market. Neither is written,
    both are counted by name, and each says why in words."""
    conn = _world(tmp_path)
    over, under = _both_sides(conn)
    got = {e["prediction_id"]: e
           for e in recommend.for_predictions(conn, [over, under], now=ASKED)}
    assert (got[over]["side"], got[over]["edge_cents"]) == ("yes", pytest.approx(4.45))
    assert (got[under]["side"], got[under]["edge_cents"]) == ("no", pytest.approx(3.5))
    counts = recommend.record_for(conn, [over, under], now=ASKED)
    assert _rows(conn) == []
    assert counts["recommended"] == 0 and counts["both_sides"] == 2
    words = {r["prediction_id"]: r["why"] for r in counts["refused"]}
    assert set(words) == {over, under}
    assert "both sides" in words[over]
    assert "1 on the yes side and 1 on the no side" in words[over]
    assert audit.plain_words_violations(words[over]) == []
    assert audit.advice_word_faults(words[over]) == []


def test_a_game_and_market_with_a_standing_recommendation_gets_no_second(tmp_path):
    """THE MORNING AND FINAL PASSES, and recs 45 and 46 replayed in order:
    once a game and market hold a standing recommendation, a later pass adds
    none -- the same side at a new price, or the other side from another
    forecaster -- and says which one stands. A pass that would take both
    sides of it is counted as a second, not as both sides: the standing one
    decides first."""
    conn = _world(tmp_path)
    morning = _away_pick(conn, confidence=0.450524, pass_kind="early",
                         created="2026-09-06T00:00:00Z")
    assert recommend.record_for(conn, [morning], now=ASKED)["recommended"] == 1
    first = conn.execute("SELECT id FROM recommendations").fetchone()[0]
    over, under = _both_sides(conn)
    for ids in ([over], [under], [over, under]):
        counts = recommend.record_for(conn, ids, now=ASKED)
        assert counts["recommended"] == 0 and counts["both_sides"] == 0
        assert counts["second_on_game_market"] == len(ids)
        why = counts["refused"][0]["why"]
        assert f"recommendation {first} standing" in why
        assert "the yes side at 48.5¢" in why
        assert audit.plain_words_violations(why) == []
    # its own forecast, asked again, is the recommendation already there
    again = recommend.record_for(conn, [morning], now=ASKED)
    assert again["already"] == 1 and again["refused"] == []
    assert _rows(conn) == [(morning, "g0", "moneyline", "yes")]


def test_one_sides_picks_in_one_pass_are_recommended_once_from_the_first(tmp_path):
    """TWO FORECASTS CLEARING ONE SIDE IN ONE PASS: the forecast written
    first is the recommendation, whichever order they are handed in."""
    conn = _world(tmp_path)
    earlier = _away_pick(conn, created="2026-09-07T00:00:00Z")
    later = _away_pick(conn, predictor="llm", created="2026-09-07T00:00:07Z")
    counts = recommend.record_for(conn, [later, earlier], now=ASKED)
    assert counts["recommended"] == 1 and counts["second_on_game_market"] == 1
    assert _rows(conn) == [(earlier, "g0", "moneyline", "no")]
    assert counts["refused"][0]["prediction_id"] == later
    assert "from the forecast it wrote first" in counts["refused"][0]["why"]


def test_another_game_or_another_market_is_its_own(tmp_path):
    """ONE PER GAME AND MARKET, not one per game, and not one per pass."""
    conn = _world(tmp_path)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g1', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')")
    here = _away_pick(conn)
    there = _away_pick(conn, game="g1", predictor="llm")
    other_market = _pick(conn, prob=0.62, implied=0.46, market="spread")
    counts = recommend.record_for(conn, [here, there, other_market], now=ASKED)
    assert counts["recommended"] == 3 and counts["refused"] == []
    assert sorted((g, m) for _, g, m, _ in _rows(conn)) == [
        ("g0", "moneyline"), ("g0", "spread"), ("g1", "moneyline")]


def test_the_schema_refuses_a_second_standing_recommendation_on_either_side(tmp_path):
    """THE SECOND LOCK, however the row is written: straight into the table,
    a second recommendation on a game and market is refused in the ruling's
    words, on either side, and never in the words of a forecast written
    twice. A withdrawn one does not stand -- by its own void or by its
    forecast's -- so the game and market may be recommended again, as NFL
    spreads 73, 75, 76 and 78 were after 62, 63, 64 and 66."""
    conn = _world(tmp_path)
    over, under = _both_sides(conn)
    first = _insert(conn, over, "yes", "2026-09-07T02:00:00Z")
    for pid, side in ((under, "no"), (over, "yes")):
        with pytest.raises(sqlite3.IntegrityError) as refused:
            _insert(conn, pid, side, "2026-09-07T02:00:01Z")
        assert recommend.ONE_PER_GAME_AND_MARKET in str(refused.value)
        assert "UNIQUE" not in str(refused.value)
    conn.execute("INSERT INTO recommendation_voids (recommendation_id,"
                 " voided_utc, reason) VALUES (?, '2026-09-07T03:00:00Z',"
                 " 'withdrawn in this test world')", (first,))
    _insert(conn, under, "no", "2026-09-07T03:00:01Z")
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc,"
                 " reason) VALUES (?, '2026-09-07T04:00:00Z',"
                 " 'withdrawn in this test world')", (under,))
    _insert(conn, over, "yes", "2026-09-07T04:00:01Z")
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 3
    # and the door reads standing exactly as the rule does: one, the last
    assert [s["prediction_id"] for s in
            recommend.standing_recommendations(conn, "g0", "moneyline")] == [over]


def test_the_rule_reads_no_row_already_written(tmp_path):
    """NEW ROWS ONLY (LAW 3). A record that holds a pair written before the
    rule -- the shape of recs 45 and 46, and of the seventeen early and final
    pairs -- is opened under the schema that carries it: the rule is made
    over the pair without refusing or touching it, both rows stand exactly
    as written, and only a third is refused."""
    conn = _world(tmp_path)
    # a third forecast of the question, ranked while it led the slate (the
    # ranker shortlists one question once, so it is written first)
    third = _away_pick(conn, confidence=0.450524, pass_kind="early",
                       created="2026-09-06T00:00:00Z")
    over, under = _both_sides(conn)
    conn.execute("DROP TRIGGER recommendation_one_per_game_and_market")
    _insert(conn, over, "yes", "2026-09-07T02:00:00Z")
    _insert(conn, under, "no", "2026-09-07T02:00:00Z")
    conn.commit()
    before = [tuple(r) for r in conn.execute(
        "SELECT * FROM recommendations ORDER BY id")]
    db.init(conn)
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'trigger'"
        "   AND name = 'recommendation_one_per_game_and_market'").fetchone()
    assert [tuple(r) for r in conn.execute(
        "SELECT * FROM recommendations ORDER BY id")] == before
    # the pair reads as it stands, first first -- 45 before 46, by its id
    # where the stamp ties -- and each forecast finds its own there
    assert [s["prediction_id"] for s in recommend.standing_recommendations(
        conn, "g0", "moneyline")] == [over, under]
    counts = recommend.record_for(conn, [over, under], now=ASKED)
    assert counts["recommended"] == 0 and counts["already"] == 2
    assert recommend.for_predictions(conn, [third], now=ASKED)[0]["side"] == "yes"
    assert recommend.record_for(conn, [third], now=ASKED)["second_on_game_market"] == 1
    with pytest.raises(sqlite3.IntegrityError,
                       match=recommend.ONE_PER_GAME_AND_MARKET):
        _insert(conn, third, "yes", "2026-09-08T02:00:00Z")


def test_a_refusal_by_the_record_is_counted_by_its_own_name(tmp_path, monkeypatch):
    """TWO WRITERS AT ONCE: the door looked and found nothing standing, and
    another pass wrote first. The schema's refusal is counted as a second on
    the game and market, and said -- never as "already", which is a forecast
    written twice, and which is what a refusal carrying "UNIQUE" would have
    been filed under."""
    conn = _world(tmp_path)
    over, under = _both_sides(conn)
    recommend.record_for(conn, [over], now=ASKED)
    monkeypatch.setattr(recommend, "standing_recommendations",
                        lambda conn, game_id, market: [])
    counts = recommend.record_for(conn, [under], now=ASKED)
    assert counts["recommended"] == 0 and counts["already"] == 0
    assert counts["second_on_game_market"] == 1
    assert "the record refused it" in counts["refused"][0]["why"]
    assert len(_rows(conn)) == 1


def test_the_run_keeps_what_it_refused_and_why(tmp_path):
    """SAID IN PLAIN WORDS, AND KEPT: the counts and the words travel on the
    run's result, which the predict and final tasks store with the run."""
    import inspect

    from gridiron import tasks

    source = inspect.getsource(tasks)
    assert source.count('"recommended": result.get("recommended")') == 2
    conn = _world(tmp_path)
    over, under = _both_sides(conn)
    counts = recommend.record_for(conn, [over, under], now=ASKED)
    json.dumps(counts)          # it is stored as JSON with the run
    assert [r["side"] for r in counts["refused"]] == ["yes", "no"]


def test_a_run_failed_for_want_of_a_model_keeps_what_it_recommended(
        league, monkeypatch):
    """AND A RUN THAT FAILS BY NAME KEEPS IT TOO (the prover of item 5,
    2026-09-26). `run.MarketNotTrained` is raised after the markets that have
    a model are written and recorded, so such a run has recommended -- and
    until the prover its stored payload held the traceback alone, while a
    run that ended ok kept the account. The same world as
    `test_untrained.py`'s: NFL moneyline has no model, spread and total do."""
    from gridiron import run, tasks
    from gridiron.factors import store
    from gridiron.model import activation, baseline

    seasons = dict(config.SPORT_CURRENT_SEASON)
    seasons["nfl"] = 2025
    monkeypatch.setattr(config, "SPORT_CURRENT_SEASON", seasons)
    store.sync_registry(league)
    for market in ("spread", "total"):
        baseline.train(league, market, (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    raised = {}
    real = run.run_slate

    def watched(*args, **kwargs):
        try:
            return real(*args, **kwargs)
        except run.MarketNotTrained as exc:
            raised["result"] = exc.result
            raise

    monkeypatch.setattr(run, "run_slate", watched)
    got = tasks.run_task(league, "predict:nfl", use_llm=False)
    assert got["result"] == "failed" and got["detail"].startswith("MarketNotTrained")
    recorded = raised["result"]["recommended"]
    assert {"recommended", "second_on_game_market", "both_sides",
            "refused"} <= set(recorded)
    stored = json.loads(league.execute(
        "SELECT payload_json FROM task_runs WHERE task = 'predict:nfl'"
        " ORDER BY id DESC LIMIT 1").fetchone()[0])
    assert "Traceback" in stored["traceback"]
    assert stored["recommended"] == json.loads(json.dumps(recorded))


# --- no stored recommendation is replaced (operator question 13) -------------
#
# Ruled 2026-09-27: "No stored recommendation may be replaced by any
# statement." Found by item 5's prover (2026-09-26): SQLite runs no delete
# rule for a replacement unless recursive triggers are on, so OR REPLACE
# went round `recommendations_no_delete` -- the hole `market_snapshots` had
# until its two replace rules of 2026-09-25.

_Q13_COLS = ("prediction_id, sport, game_id, market, side, fair_value, price,"
             " edge_cents, size_kind, size_units, gate_n, created_utc")
_Q13_STAMP = "2026-09-07T02:00:00Z"
_Q13_LATER = "2026-09-08T00:00:00Z"
_Q13_RULES = ("recommendations_never_replaced",
              "recommendations_never_replaced_by_update",
              # the prover, 2026-09-27: the number a one-row insert writes
              # is read again after it lands (the rule reads it first)
              "recommendations_never_replaced_by_the_number_written")


def _replace_world(tmp_path):
    """Recs 1 and 2 standing on games of their own, rec 3 withdrawn, and a
    forecast on each of two more games with nothing recommended."""
    conn = _world(tmp_path)
    ids = {}
    for n in range(1, 6):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')",
            (f"q{n}",))
        ids[f"p{n}"] = _away_pick(conn, game=f"q{n}")
    for n in (1, 2, 3):
        ids[f"rec{n}"] = _insert(conn, ids[f"p{n}"], "yes", _Q13_STAMP,
                                 game=f"q{n}")
    conn.execute("INSERT INTO recommendation_voids (recommendation_id,"
                 " voided_utc, reason) VALUES (?, '2026-09-07T03:00:00Z',"
                 " 'withdrawn in this test world')", (ids["rec3"],))
    conn.commit()
    return conn, ids


def _stored(conn):
    return ([tuple(r) for r in conn.execute(
                "SELECT * FROM recommendations ORDER BY id")],
            [tuple(r) for r in conn.execute(
                "SELECT * FROM recommendation_voids ORDER BY recommendation_id")])


def _newcomer(number, pid, game, created, *, verb="INSERT OR REPLACE",
              column="id"):
    head = "" if number is None else f"{column}, "
    lead = "" if number is None else f"{number}, "
    return (f"{verb} INTO recommendations ({head}{_Q13_COLS}) VALUES ({lead}"
            f"{pid}, 'mlb', '{game}', 'moneyline', 'no', 0.4, 0.9, 1.0, 'flat',"
            f" 1.0, 0, '{created}')")


#: Every statement found that takes a stored recommendation's place, and
#: two no release lets through, held so a later rule cannot open them.
_Q13_FORMS = {
    "insert or replace naming a stored number":
        _newcomer("{rec1}", "{p4}", "q4", _Q13_LATER),
    "replace naming a stored number as rowid":
        _newcomer("{rec1}", "{p4}", "q4", _Q13_LATER, verb="REPLACE",
                  column="rowid"),
    "insert or replace naming a stored number as text":
        _newcomer("'{rec1}'", "{p4}", "q4", _Q13_LATER),
    "insert or replace naming a stored number as a real":
        _newcomer("{rec1}.0", "{p4}", "q4", _Q13_LATER),
    "insert or replace on a stored forecast and stamp":
        _newcomer(None, "{p1}", "q4", _Q13_STAMP),
    "insert or replace on a stored forecast given as text":
        _newcomer(None, "'{p1}'", "q4", _Q13_STAMP),
    "insert or replace colliding with two rows at once":
        f"INSERT OR REPLACE INTO recommendations (id, {_Q13_COLS}) SELECT"
        f" {{rec2}}, {{p1}}, 'mlb', 'q4', 'moneyline', 'no', 0.4, 0.9, 1.0,"
        f" 'flat', 1.0, 0, '{_Q13_STAMP}'",
    "insert or replace onto a withdrawn one on its own game":
        _newcomer("{rec3}", "{p3}", "q3", _Q13_LATER),
    "update or replace onto another's number by id":
        "UPDATE OR REPLACE recommendations SET id = {rec1} WHERE id = {rec2}",
    "update or replace onto another's number by rowid":
        "UPDATE OR REPLACE recommendations SET rowid = {rec1} WHERE id = {rec2}",
    "update or replace onto another's number by oid":
        "UPDATE OR REPLACE recommendations SET oid = {rec1} WHERE id = {rec2}",
    "update or replace onto another's number by _rowid_":
        "UPDATE OR REPLACE recommendations SET _rowid_ = {rec1} WHERE id = {rec2}",
    "update or replace onto another's forecast and stamp":
        "UPDATE OR REPLACE recommendations SET prediction_id = {p1},"
        " created_utc = '" + _Q13_STAMP + "' WHERE id = {rec2}",
    "an upsert rewriting what a stored one recommended":
        _newcomer("{rec1}", "{p4}", "q4", _Q13_LATER, verb="INSERT")
        + " ON CONFLICT(id) DO UPDATE SET side = excluded.side,"
          " price = excluded.price",
    "an upsert moving a stored one onto another's number":
        _newcomer("{rec2}", "{p4}", "q4", _Q13_LATER, verb="INSERT")
        + " ON CONFLICT(id) DO UPDATE SET id = {rec1}",
}


@pytest.mark.parametrize("form", sorted(_Q13_FORMS))
def test_no_stored_recommendation_is_replaced_by_any_statement(tmp_path, form):
    """EACH FORM REFUSED UNDER LAW 3, in the replace rules' words -- they
    run first, so even the two an older rule already refused (an update
    onto a forecast and stamp, an upsert rewriting what was recommended)
    are refused by them -- and the table and its withdrawals exactly as
    stored afterwards: none may take a stored recommendation's place,
    whatever it names and however it spells it."""
    conn, ids = _replace_world(tmp_path)
    before = _stored(conn)
    with pytest.raises(sqlite3.IntegrityError) as refused:
        conn.execute(_Q13_FORMS[form].format(**ids))
    conn.rollback()
    assert "LAW 3" in str(refused.value)
    assert recommend.NEVER_REPLACED in str(refused.value)
    assert _stored(conn) == before


def test_the_forms_replace_without_the_rules(tmp_path):
    """THE REPLACEMENT IS REAL: with the replace rules dropped, the forms that
    replace do -- the stored row is gone or overwritten, and the withdrawn
    one's withdrawal is left beside a recommendation nobody withdrew."""
    conn, ids = _replace_world(tmp_path)
    for name in _Q13_RULES:
        conn.execute(f"DROP TRIGGER {name}")
    before = _stored(conn)
    for form, statement in _Q13_FORMS.items():
        if "upsert" in form or form.endswith("forecast and stamp") \
                and form.startswith("update"):
            continue
        conn.execute(statement.format(**ids))
        assert _stored(conn) != before, form
        conn.rollback()
    conn.execute(_Q13_FORMS["insert or replace onto a withdrawn one on its "
                            "own game"].format(**ids))
    row = conn.execute("SELECT r.side, r.price FROM recommendations r"
                       " JOIN recommendation_voids w ON w.recommendation_id"
                       " = r.id").fetchone()
    assert tuple(row) == ("no", 0.9)
    conn.rollback()


def test_the_lawful_writes_are_untouched(tmp_path):
    """THE WRITERS DO NOT CHANGE: `record_for` still writes a pick on a game
    of its own, a plain insert on another still lands, and the closer still
    writes the close of an open recommendation -- the update rule runs on
    every update and refuses only one that takes another's place."""
    conn, ids = _replace_world(tmp_path)
    assert recommend.record_for(conn, [ids["p5"]], now=ASKED)["recommended"] == 1
    _insert(conn, ids["p4"], "no", _Q13_LATER, game="q4")
    conn.commit()
    got = recommend.record_closing_prices(conn)
    assert got["unmeasured"] == 4 and got["closed"] == 0
    closed = {r[0] for r in conn.execute(
        "SELECT id FROM recommendations WHERE closed_utc IS NOT NULL")}
    assert ids["rec1"] in closed and ids["rec2"] in closed
    assert ids["rec3"] not in closed        # withdrawn: never followed


def test_a_forecast_written_twice_is_still_counted_as_already(tmp_path):
    """RECORD_FOR COUNTS AS IT DID. A withdrawn recommendation does not
    stand, so its own forecast asked again passes the door, and its insert
    collides with the stored row's forecast and stamp: refused until
    2026-09-27 by the key ("UNIQUE"), now first by the replace rule, and
    counted `already` either way -- never raised, never written."""
    conn = _world(tmp_path)
    pid = _away_pick(conn)
    assert recommend.record_for(conn, [pid], now=ASKED)["recommended"] == 1
    rid = conn.execute("SELECT id FROM recommendations").fetchone()[0]
    conn.execute("INSERT INTO recommendation_voids (recommendation_id,"
                 " voided_utc, reason) VALUES (?, '2026-09-07T03:00:00Z',"
                 " 'withdrawn in this test world')", (rid,))
    conn.commit()
    before = _stored(conn)
    counts = recommend.record_for(conn, [pid], now=ASKED)
    assert counts["recommended"] == 0 and counts["already"] == 1
    assert counts["refused"] == []
    assert _stored(conn) == before


def test_the_replace_rules_carry_the_words_and_run_first(tmp_path):
    """ONE SET OF WORDS: every replace rule says `recommend.NEVER_REPLACED`, never
    "UNIQUE" and never the one-per-game words. DECLARED AFTER the one-per-
    game rule, as a record gains them, so a fresh build runs them in the
    record's order (SQLite runs a table's rules newest first) and a plain
    duplicate of a standing row is refused in these words on both."""
    conn = db.open_db(tmp_path / "fresh.db")
    rules = dict(conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'trigger'"
        " AND tbl_name = 'recommendations'").fetchall())
    for name in _Q13_RULES:
        assert recommend.NEVER_REPLACED in rules[name]
        assert "UNIQUE" not in rules[name]
        assert recommend.ONE_PER_GAME_AND_MARKET not in rules[name]
    order = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        " AND tbl_name = 'recommendations' ORDER BY rowid")]
    # Question 24's rule (2026-09-28) is declared after these three, as the
    # record gains it after them; they stay together, after one-per-game.
    assert order[-1] == _Q24_RULE
    assert order[-len(_Q13_RULES) - 1:-1] == list(_Q13_RULES)
    assert order[-len(_Q13_RULES) - 2] == "recommendation_one_per_game_and_market"
    conn.close()


def test_an_older_record_gains_the_rules_through_init_and_no_row_moves(tmp_path):
    """THE RELEASE REACHES THE RECORD THROUGH `db.init` ALONE: a record
    without the replace rules -- every release until this one -- gains exactly
    them, with a fresh build's text, after the one-per-game rule; every
    stored recommendation and withdrawal stays as it was; a second open
    adds nothing; and a replacement is refused from the first open."""
    conn, ids = _replace_world(tmp_path)
    for name in _Q13_RULES:
        conn.execute(f"DROP TRIGGER {name}")
    conn.commit()

    def objects(c):
        return {(r[0], r[1]): r[2] for r in c.execute(
            "SELECT type, name, sql FROM sqlite_master")}

    before, rows = objects(conn), _stored(conn)
    db.init(conn)
    after = objects(conn)
    assert set(after) - set(before) == {("trigger", n) for n in _Q13_RULES}
    assert set(before) <= set(after)
    assert all(after[k] == before[k] for k in before)
    fresh = db.open_db(tmp_path / "fresh.db")
    try:
        for name in _Q13_RULES:
            assert after[("trigger", name)] == objects(fresh)[("trigger", name)]
    finally:
        fresh.close()
    assert _stored(conn) == rows
    order = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        " AND tbl_name = 'recommendations' ORDER BY rowid")]
    assert order.index("recommendation_one_per_game_and_market") < min(
        order.index(n) for n in _Q13_RULES)
    db.init(conn)
    assert objects(conn) == after and _stored(conn) == rows
    with pytest.raises(sqlite3.IntegrityError, match=recommend.NEVER_REPLACED):
        conn.execute(_Q13_FORMS["insert or replace naming a stored number"]
                     .format(**ids))
    conn.rollback()
    assert _stored(conn) == rows


# --- the number the rule is shown is not the number written (the prover of
# question 13, 2026-09-27) ----------------------------------------------------
#
# For an insert of one row of values SQLite works the number out twice: once
# for the rules that run before the row, once for the row itself (measured on
# 3.49.1). A number that answers differently the second time -- random(), or
# a function the connection defines -- showed `recommendations_never_replaced`
# -1 or a free number and then wrote over a stored recommendation under OR
# REPLACE. `recommendations_never_replaced_by_the_number_written` reads the
# number after it lands.


class _Handed:
    """An application function answering the first reading with `first` and
    every later one with `then`: the rule reads first, the key after."""

    def __init__(self, first, then):
        self.first, self.then, self.calls = first, then, 0

    def __call__(self):
        self.calls += 1
        return self.first if self.calls == 1 else self.then


#: (the number the rules are shown, the stored recommendation the key gets)
_Q13_HANDED = {
    "nothing to the rules, rec 1 to the key": (None, "rec1"),
    "a free number to the rules, rec 2 to the key": (99, "rec2"),
    "a free number to the rules, the withdrawn newest to the key": (99, "rec3"),
}


@pytest.mark.parametrize("form", sorted(_Q13_HANDED))
@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_a_number_read_one_way_by_the_rules_and_another_by_the_key_is_refused(
        tmp_path, form, verb):
    """REFUSED, in the replace rules' words, the table and its withdrawals
    exactly as stored; and with ONLY the rule reading the written number
    dropped -- the two rules before it in place, as built first -- the same
    statement writes over the stored recommendation: that rule is what stops
    it."""
    conn, ids = _replace_world(tmp_path)
    first, key = _Q13_HANDED[form]
    before = _stored(conn)
    statement = _newcomer("handed()", "{p4}", "q4", _Q13_LATER,
                          verb=verb).format(**ids)
    handed = _Handed(first, ids[key])
    conn.create_function("handed", 0, handed)
    with pytest.raises(sqlite3.IntegrityError) as refused:
        conn.execute(statement)
    conn.rollback()
    assert handed.calls == 2                # read twice, as measured
    assert "LAW 3" in str(refused.value)
    assert recommend.NEVER_REPLACED in str(refused.value)
    assert _stored(conn) == before
    conn.execute(f"DROP TRIGGER {_Q13_RULES[-1]}")
    conn.create_function("handed", 0, _Handed(first, ids[key]))
    conn.execute(statement)
    after = {r[0]: r for r in _stored(conn)[0]}
    assert after[ids[key]] != {r[0]: r for r in before[0]}[ids[key]]
    assert after[ids[key]][3] == "q4"       # another game's, under its number
    conn.rollback()


def test_a_number_worked_out_at_random_never_writes_over_a_stored_one(tmp_path):
    """RANDOM(), THE PLAIN FORM: sixty-four tries each of a number drawn from
    one to six (three stored) and of one that is NULL or rec 1's by a coin.
    Each is refused or writes a new recommendation under a new number; no
    stored recommendation or withdrawal ever changes."""
    conn, ids = _replace_world(tmp_path)
    before = _stored(conn)
    stored = {r[0]: r for r in before[0]}
    for number in ("abs(random()) % 6 + 1",
                   "CASE WHEN random() % 2 = 0 THEN NULL ELSE {rec1} END"):
        for _ in range(64):
            try:
                conn.execute(_newcomer(number, "{p4}", "q4", _Q13_LATER)
                             .format(**ids))
            except sqlite3.IntegrityError as exc:
                assert recommend.NEVER_REPLACED in str(exc)
            rows, voids = _stored(conn)
            assert {r[0]: r for r in rows if r[0] in stored} == stored
            assert voids == before[1]
            conn.rollback()


def test_a_number_below_one_already_given_out_is_refused_and_one_above_lands(
        tmp_path):
    """THE CONSERVATIVE DEFAULT, recorded: after the insert a rule cannot
    tell a number that was stored from one that is free, so a free number
    at or below one already given out -- here 4, vacated by an update, and 0
    and -1, never used -- is refused too (no writer names a number, and the
    record's run 1 to 107); a number above every one lands.

    The update vacating 4 moves the recommendation DOWN, to -5 (2026-09-28,
    question 24): a move above every number given out is refused from that
    date (`test_a_recommendation_is_never_moved_out_of_reach_of_the_number_
    written`), and this world moved it up, to 10. Question 15's precedent
    (its own test world moved the same way); the numbers asked about are
    the same."""
    conn, ids = _replace_world(tmp_path)
    _insert(conn, ids["p4"], "no", _Q13_LATER, game="q4")    # number 4
    conn.execute("UPDATE recommendations SET id = -5 WHERE id = 4")
    conn.commit()
    before = _stored(conn)
    for unused in (4, 0, -1):
        with pytest.raises(sqlite3.IntegrityError,
                           match=recommend.NEVER_REPLACED):
            conn.execute(_newcomer(str(unused), "{p5}", "q5", _Q13_LATER,
                                   verb="INSERT").format(**ids))
        conn.rollback()
    assert _stored(conn) == before
    conn.execute(_newcomer("11", "{p5}", "q5", _Q13_LATER,
                           verb="INSERT").format(**ids))
    assert conn.execute("SELECT game_id FROM recommendations WHERE id = 11"
                        ).fetchone()[0] == "q5"
    conn.rollback()


def test_a_recommendation_given_a_number_below_one_does_not_stop_the_next(
        tmp_path):
    """THE -1 THE INSERT RULE IS SHOWN. An insert leaving the number to
    SQLite shows the rule -1, and an update may give a row -1 (it replaces
    nothing). Were the rule to look -1 up, every later pick would be refused
    in its words and `record_for` would count each `already`: nothing new
    recorded, and nothing said. It does not, so the next pick is written;
    and an insert naming -1 is still refused once it lands."""
    conn = _world(tmp_path)
    first = _away_pick(conn)
    assert recommend.record_for(conn, [first], now=ASKED)["recommended"] == 1
    rid = conn.execute("SELECT id FROM recommendations").fetchone()[0]
    conn.execute("UPDATE recommendations SET id = -1 WHERE id = ?", (rid,))
    conn.commit()
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g1', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')")
    second = _away_pick(conn, game="g1")
    got = recommend.record_for(conn, [second], now=ASKED)
    assert got["recommended"] == 1 and got["already"] == 0
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 2
    before = _stored(conn)
    with pytest.raises(sqlite3.IntegrityError, match=recommend.NEVER_REPLACED):
        conn.execute(
            "INSERT OR REPLACE INTO recommendations (id, prediction_id, sport,"
            " game_id, market, side, fair_value, price, edge_cents, size_kind,"
            " size_units, gate_n, created_utc) VALUES (-1, ?, 'mlb', 'g1',"
            " 'total', 'yes', 0.5, 0.5, 1.0, 'flat', 1.0, 0, ?)",
            (second, _Q13_LATER))
    conn.rollback()
    assert _stored(conn) == before


# --- no recommendation moved above every number given out (operator
# question 24) ------------------------------------------------------------------
#
# Ruled 2026-09-28: "Q24: fix after Q20, same basis as Q15, own commit and
# planting." Found by question 15's prover (2026-09-27): the rule on the
# number written holds a recommendation only at or below `sqlite_sequence`'s
# mark, and an update of a number does not move that mark, so a plain UPDATE
# moving rec 2 to 10 over a mark of 3 -- which takes no other row's place --
# left it out of that rule's reach, and a one-row insert whose number read
# as a free 99 to the rules and as 10 to the row wrote another game's
# recommendation over it. `recommendations_never_moved_above_the_mark`, a
# rule of its own (question 13's update rule is on the record and its text
# is never replaced), refuses the move. Question 15's
# `test_a_forecast_is_never_moved_out_of_reach_of_the_number_written` and
# `test_with_the_sequence_set_back_every_forecast_but_the_newest_is_held`
# are the precedent.

_Q24_RULE = "recommendations_never_moved_above_the_mark"
#: What the rule adds to `recommend.NEVER_REPLACED` in its refusal.
_Q24_WORDS = "above every number already given out"
#: The world's mark is 3; the question's own example moves rec 2 to 10.
_Q24_ABOVE = 10


def _mark(conn):
    return conn.execute("SELECT seq FROM sqlite_sequence"
                        " WHERE name = 'recommendations'").fetchone()[0]


def _moved_over(conn, ids, key):
    """Whether what recommendation `key` said is gone from the table."""
    return (ids[f"_said_{key}"] not in
            {tuple(r)[1:] for r in conn.execute("SELECT * FROM recommendations")})


def _q24_world(tmp_path):
    """Question 13's world, and what each of its recommendations said."""
    conn, ids = _replace_world(tmp_path)
    for key in ("rec1", "rec2", "rec3"):
        ids[f"_said_{key}"] = tuple(conn.execute(
            "SELECT * FROM recommendations WHERE id = ?", (ids[key],)).fetchone())[1:]
    return conn, ids


def _onto(function, verb="INSERT OR REPLACE"):
    """The newcomer on game q4 whose number the connection's `function`
    works out: once for the rules, once for the row."""
    return _newcomer(f"{function}()", "{p4}", "q4", _Q13_LATER, verb=verb)


#: Every update found that moves a stored recommendation above every number
#: given out -- each taken on 8b569dc (measured 2026-09-28), with foreign
#: keys off where a withdrawal's key holds the row -- as (statements, the
#: functions they call, as (the rules' reading, the row's)). Each is refused
#: here before the number can be read twice onto the moved row.
_Q24_MOVES = {
    **{f"{verb.lower()} by {column}":
       ((f"{verb} recommendations SET {column} = {_Q24_ABOVE}"
         " WHERE id = {rec2}",), {})
       for verb in ("UPDATE", "UPDATE OR REPLACE", "UPDATE OR IGNORE",
                    "UPDATE OR FAIL", "UPDATE OR ABORT", "UPDATE OR ROLLBACK")
       for column in ("id", "rowid", "oid", "_rowid_")},
    **{f"the number spelled {spelled}":
       ((f"UPDATE recommendations SET id = {spelled} WHERE id = {{rec2}}",), {})
       for spelled in ("'10'", "10.0", "1e1", "' 10'", "(SELECT 10)", "id + 8",
                       "CAST('10' AS INTEGER)")},
    "to one above the mark":
        (("UPDATE recommendations SET id = 4 WHERE id = {rec2}",), {}),
    "the oldest":
        (("UPDATE recommendations SET id = 10 WHERE id = {rec1}",), {}),
    "the withdrawn newest, foreign keys off":
        (("PRAGMA foreign_keys = OFF",
          "UPDATE recommendations SET id = 10 WHERE id = {rec3}"), {}),
    "every row at once, foreign keys off":
        (("PRAGMA foreign_keys = OFF",
          "UPDATE recommendations SET id = id + 10"), {}),
    "an upsert whose number reads twice, moving the row it lands on":
        ((_onto("handed", verb="INSERT")
          + " ON CONFLICT(id) DO UPDATE SET id = 10",),
         {"handed": (99, "rec2")}),
    "a temporary rule moving one inside an update of a close":
        (("CREATE TEMP TRIGGER q24_move AFTER UPDATE OF close_price ON"
          " recommendations WHEN NEW.id = {rec1} BEGIN UPDATE recommendations"
          " SET id = 10 WHERE id = {rec2}; END",
          "UPDATE recommendations SET close_price = 0.52, clv_cents = 2.0,"
          " closed_utc = '2026-09-09T22:00:00Z' WHERE id = {rec1}"), {}),
}


def _functions(conn, ids, spec):
    for name, (first, then) in spec.items():
        conn.create_function(name, 0, _Handed(
            ids.get(first, first) if isinstance(first, str) else first,
            ids.get(then, then) if isinstance(then, str) else then))


@pytest.mark.parametrize("form", sorted(_Q24_MOVES))
def test_no_recommendation_is_moved_above_every_number_given_out(tmp_path, form):
    """EACH MOVE REFUSED UNDER LAW 3, in the replace rules' words and this
    rule's own, before a number read twice could be written onto the moved
    row: every recommendation and withdrawal as stored, and the mark where it
    was. However the number is spelled, whatever the conflict clause, by
    whichever of the table's names for its number, and from inside another
    statement."""
    conn, ids = _q24_world(tmp_path)
    statements, functions = _Q24_MOVES[form]
    _functions(conn, ids, functions)
    before, mark = _stored(conn), _mark(conn)
    with pytest.raises(sqlite3.IntegrityError) as refused:
        for statement in statements:
            conn.execute(statement.format(**ids))
    conn.rollback()
    conn.execute("PRAGMA foreign_keys = ON")
    assert "LAW 3" in str(refused.value)
    assert recommend.NEVER_REPLACED in str(refused.value)
    assert _Q24_WORDS in str(refused.value)
    assert "UNIQUE" not in str(refused.value)
    assert _stored(conn) == before and _mark(conn) == mark


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_a_recommendation_is_never_moved_out_of_reach_of_the_number_written(
        tmp_path, verb):
    """THE HOLE, AND WHAT CLOSES IT. The move above the mark is refused; a
    move to a free number within the numbers given out still lands (this is
    no freeze of the number, which stays the operator's) and nothing can be
    written over the moved row there -- the rule on the number written holds
    it; and with this rule dropped, the two statements of question 24 write
    another game's recommendation over rec 2: it is what stops them."""
    conn, ids = _q24_world(tmp_path)
    assert _mark(conn) == 3
    before = _stored(conn)
    with pytest.raises(sqlite3.IntegrityError, match=_Q24_WORDS):
        conn.execute("UPDATE recommendations SET id = 10 WHERE id = ?",
                     (ids["rec2"],))
    conn.rollback()
    assert _stored(conn) == before
    # within the numbers given out: lands, and stays in reach
    conn.execute("UPDATE recommendations SET id = 0 WHERE id = ?", (ids["rec2"],))
    conn.create_function("handed", 0, _Handed(99, 0))
    with pytest.raises(sqlite3.IntegrityError, match=recommend.NEVER_REPLACED):
        conn.execute(_onto("handed", verb=verb).format(**ids))
    assert not _moved_over(conn, ids, "rec2")
    assert conn.execute("SELECT game_id FROM recommendations WHERE id = 0"
                        ).fetchone()[0] == "q2"
    conn.rollback()
    assert _stored(conn) == before
    # the rule dropped: question 24's two statements, as measured on 8b569dc
    conn.execute(f"DROP TRIGGER {_Q24_RULE}")
    conn.execute("UPDATE recommendations SET id = 10 WHERE id = ?", (ids["rec2"],))
    assert _mark(conn) == 3                  # an update does not move the mark
    conn.create_function("handed", 0, _Handed(99, 10))
    conn.execute(_onto("handed", verb=verb).format(**ids))
    assert _moved_over(conn, ids, "rec2")
    assert tuple(conn.execute("SELECT game_id, side, price FROM recommendations"
                              " WHERE id = 10").fetchone()) == ("q4", "no", 0.9)
    conn.rollback()


def test_a_move_onto_the_mark_lands_in_reach_and_one_past_it_is_refused(tmp_path):
    """THE BOUNDARY IS THE MARK ITSELF. With the number at the mark vacated
    (rec 4 moved down), rec 2 moved onto the mark lands and a number read
    twice onto it is refused by the rule on the number written; moved one
    past the mark, it is refused by this rule."""
    conn, ids = _q24_world(tmp_path)
    _insert(conn, ids["p4"], "no", _Q13_LATER, game="q4")    # number 4
    conn.execute("UPDATE recommendations SET id = -5 WHERE id = 4")
    conn.commit()
    assert _mark(conn) == 4
    before = _stored(conn)
    with pytest.raises(sqlite3.IntegrityError, match=_Q24_WORDS):
        conn.execute("UPDATE recommendations SET id = 5 WHERE id = ?", (ids["rec2"],))
    conn.rollback()
    assert _stored(conn) == before
    conn.execute("UPDATE recommendations SET id = 4 WHERE id = ?", (ids["rec2"],))
    conn.create_function("handed", 0, _Handed(99, 4))
    with pytest.raises(sqlite3.IntegrityError, match=recommend.NEVER_REPLACED):
        conn.execute(_newcomer("handed()", "{p5}", "q5", _Q13_LATER).format(**ids))
    assert conn.execute("SELECT game_id FROM recommendations WHERE id = 4"
                        ).fetchone()[0] == "q2"
    conn.rollback()


#: The rule on the number written's clause refusing a number below any
#: stored one, as the schema writes it, whitespace aside.
_BELOW_ANY_STORED = re.compile(
    r"\s+OR EXISTS \(SELECT 1 FROM recommendations r WHERE r\.id > NEW\.id\)")


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_with_the_sequence_set_back_every_recommendation_but_the_newest_is_held(
        tmp_path, verb):
    """QUESTION 15'S SECOND FORM, applied here. SQLite's own sequence is NOT
    SEEN by any rule (FOLLOWUPS), and set back below every recommendation it
    leaves the newest where nothing stored tells it from a newcomer. Every
    recommendation below the newest is still held, by the rule on the number
    written's "below any stored one" -- while nothing newer is moved down
    beneath the mark set back, which would leave an older one the newest
    (this rule's prover, 2026-09-28: NOT SEEN, FOLLOWUPS); with that clause
    taken out, the same insert writes over rec 1. And with the sequence set
    back, a move of any number above it is refused by this rule, and an
    update that moves no number -- the closer's -- still lands."""
    conn, ids = _q24_world(tmp_path)
    before = _stored(conn)
    for key in ("rec1", "rec2"):
        conn.execute("UPDATE sqlite_sequence SET seq = 0"
                     " WHERE name = 'recommendations'")
        conn.create_function("handed", 0, _Handed(99, ids[key]))
        with pytest.raises(sqlite3.IntegrityError, match=recommend.NEVER_REPLACED):
            conn.execute(_onto("handed", verb=verb).format(**ids))
        conn.rollback()
        assert _stored(conn) == before, key
    conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'recommendations'")
    with pytest.raises(sqlite3.IntegrityError, match=_Q24_WORDS):
        conn.execute("UPDATE recommendations SET id = 7 WHERE id = ?",
                     (ids["rec2"],))
    conn.execute("UPDATE recommendations SET close_price = 0.52, clv_cents = 2.0,"
                 " closed_utc = '2026-09-09T22:00:00Z' WHERE id = ?", (ids["rec2"],))
    conn.rollback()
    assert _stored(conn) == before
    name = _Q13_RULES[-1]
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?",
                       (name,)).fetchone()[0]
    weakened, found = _BELOW_ANY_STORED.subn("", sql)
    assert found == 1, "the rule on the number written no longer carries the clause"
    conn.execute(f"DROP TRIGGER {name}")
    conn.execute(weakened)
    conn.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'recommendations'")
    conn.create_function("handed", 0, _Handed(99, ids["rec1"]))
    conn.execute(_onto("handed", verb=verb).format(**ids))
    assert _moved_over(conn, ids, "rec1")
    conn.rollback()


def test_the_move_rule_carries_the_words_and_runs_first(tmp_path):
    """ONE SET OF WORDS: `recommend.NEVER_REPLACED` under LAW 3, never
    "UNIQUE" and never the one-per-game words. NO COLUMN LIST (a rule
    listing id is not run for rowid, oid or _rowid_). DECLARED LAST of the
    table's rules, after the rule on the number written, as the record gains
    it -- so a fresh build runs the table's rules in the record's order
    (SQLite runs a table's rules newest first)."""
    conn = db.open_db(tmp_path / "fresh.db")
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'trigger'"
                       " AND name = ?", (_Q24_RULE,)).fetchone()[0]
    assert recommend.NEVER_REPLACED in sql and "LAW 3" in sql
    assert _Q24_WORDS in sql
    assert "UNIQUE" not in sql
    assert recommend.ONE_PER_GAME_AND_MARKET not in sql
    assert re.search(r"BEFORE\s+UPDATE\s+ON\s+recommendations\b", sql)
    order = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        " AND tbl_name = 'recommendations' ORDER BY rowid")]
    assert order[-2:] == [_Q13_RULES[-1], _Q24_RULE]
    conn.close()


def test_an_older_record_gains_the_move_rule_through_init_and_no_row_moves(
        tmp_path):
    """THE RELEASE REACHES THE RECORD THROUGH `db.init` ALONE: a record as
    released until this one -- question 13's three rules, not this one --
    gains exactly this rule, with a fresh build's text, after the rule on
    the number written; every recommendation and withdrawal, and the mark,
    stay as they were; a second open adds nothing; and the move is refused
    from the first open."""
    conn, ids = _q24_world(tmp_path)
    conn.execute(f"DROP TRIGGER {_Q24_RULE}")
    conn.commit()

    def objects(c):
        return {(r[0], r[1]): r[2] for r in c.execute(
            "SELECT type, name, sql FROM sqlite_master")}

    before, rows, mark = objects(conn), _stored(conn), _mark(conn)
    db.init(conn)
    after = objects(conn)
    assert set(after) - set(before) == {("trigger", _Q24_RULE)}
    assert all(after[k] == before[k] for k in before)
    fresh = db.open_db(tmp_path / "fresh.db")
    try:
        assert after[("trigger", _Q24_RULE)] == objects(fresh)[("trigger", _Q24_RULE)]
    finally:
        fresh.close()
    assert _stored(conn) == rows and _mark(conn) == mark
    order = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        " AND tbl_name = 'recommendations' ORDER BY rowid")]
    assert order[-2:] == [_Q13_RULES[-1], _Q24_RULE]
    db.init(conn)
    assert objects(conn) == after and _stored(conn) == rows
    with pytest.raises(sqlite3.IntegrityError, match=_Q24_WORDS):
        conn.execute("UPDATE recommendations SET id = 10 WHERE id = ?",
                     (ids["rec2"],))
    conn.rollback()
    assert _stored(conn) == rows


# --- the kill criterion is asked for the pick's own forecaster ---------------

def test_the_kill_criterion_is_asked_for_each_picks_own_forecaster(tmp_path,
                                                                    monkeypatch):
    """OPERATOR QUESTION 22 (2026-09-28): the kill criterion reads each
    forecaster's closing line, so the engine asks it for the forecaster whose
    pick it prices -- a reasoning-pass pick is never stopped by the
    statistical model's closes, nor waved through by them."""
    from gridiron.priced import coverage

    conn = _world(tmp_path)
    mine = _pick(conn)
    theirs = _pick(conn, predictor="llm")
    asked = []

    def recorded(conn, sport, market, *, predictor, now=None):
        asked.append((market, predictor))
        return {"priceable": predictor == "llm", "market": market,
                "why": "stopped for the statistical model, in this test"}

    monkeypatch.setattr(coverage, "priceable", recorded)
    entries = {e["prediction_id"]: e for e in recommend.for_predictions(
        conn, [mine, theirs], now=ASKED)}
    assert sorted(asked) == [("moneyline", "llm"), ("moneyline", "statistical")]
    assert entries[mine]["side"] is None
    assert entries[theirs]["side"] is not None
