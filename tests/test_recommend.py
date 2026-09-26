"""The recommendation (THE_RECOMMENDATION R2-R4, 2026-09-07): an edge that
survives the fee, a size that refuses to vary on an unproven market, a parlay
that is refused, nothing sized in-game, and the closing line recorded once."""
from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import audit, calibration, config, db, language, shortlist
from gridiron.market import recommend

DIST = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
WHOLE = json.dumps({"coverage": 1.0, "margin_distribution": DIST})


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

    monkeypatch.setattr(coverage, "priceable",
                        lambda conn, sport, market: {
                            "priceable": True, "market": market,
                            "why": "covered, in this test"})


def _pick(conn, *, prob=0.62, implied=0.46, subject="AAA", market="moneyline"):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-07T00:00:00Z', 'mlb', 'g0', ?, ?, NULL, ?, 'win',"
        " 'statistical', 'final', 'fs2', ?, 'test')",
        (market, subject, prob, WHOLE))
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


def test_a_recommendation_is_recorded_with_the_price_it_was_made_at(tmp_path):
    conn = _world(tmp_path)
    pid = _pick(conn)
    counts = recommend.record_for(conn, [pid])
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
    counts = recommend.record_for(conn, [pid])
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
               predictor="statistical"):
    """The away side at 57%, so a claim of 43% on the home side, line-less,
    against a 48.5c price: the no side, raw, at +3.5c."""
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES (?, 'mlb', ?,"
        " 'moneyline', 'BBB', NULL, ?, 'win', ?, 'final', 'fs2',"
        " ?, 'test')", (created, game, confidence, predictor, WHOLE))
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
    from gridiron import correction

    return correction.record_fit(
        conn, sport="mlb", market_type="moneyline", forecaster="statistical",
        model=correction.Platt(**(model or _SKEWED)), status="test",
        active_from=active_from, fitted_utc="2026-09-01T00:00:00Z")


def test_an_active_correction_that_would_flip_the_side_flips_the_pick(tmp_path):
    conn = _world(tmp_path)
    pid = _away_pick(conn)
    raw = recommend.for_predictions(conn, [pid])[0]
    assert (raw["side"], raw["edge_cents"]) == ("no", pytest.approx(3.5))
    assert raw["correction_version"] is None
    assert raw["fair_value"] == raw["raw_fair_value"] == pytest.approx(0.43)
    version = _correct(conn)
    got = recommend.for_predictions(conn, [pid])[0]
    assert got["side"] == "yes" and got["edge_side"] == "yes"
    assert got["edge_cents"] == pytest.approx(3.08, abs=0.01)
    assert got["fair_value"] == pytest.approx(0.5358, abs=1e-4)
    assert got["raw_fair_value"] == pytest.approx(0.43)
    assert got["correction_version"] == version


def test_a_fitted_correction_that_was_never_activated_decides_nothing(tmp_path):
    conn = _world(tmp_path)
    pid = _away_pick(conn)
    _correct(conn, active_from=None)
    got = recommend.for_predictions(conn, [pid])[0]
    assert got["side"] == "no" and got["correction_version"] is None
    # and one whose activation is still ahead is not in force yet
    _correct(conn, active_from="2099-01-01T00:00:00Z")
    assert recommend.for_predictions(conn, [pid])[0]["side"] == "no"


def test_the_row_carries_the_correction_that_was_current_and_keeps_it(tmp_path):
    conn = _world(tmp_path)
    before = _away_pick(conn, game="g0")
    recommend.record_for(conn, [before])
    version = _correct(conn)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES ('g9', 'mlb', 2026, 1, 'R',"
        " 'AAA', 'BBB', '2026-09-09T00:00:00Z', 'scheduled', '2026-09-08')")
    after = _away_pick(conn, game="g9")
    recommend.record_for(conn, [after])
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
    # its version, nor a number that is not a probability
    for version_, number in ((2, None), (None, 0.5), (2, 1.0)):
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute(
                "INSERT INTO recommendations (prediction_id, sport, game_id,"
                " market, side, fair_value, price, edge_cents, size_kind,"
                " size_units, gate_n, created_utc, correction_version,"
                " calibrated_fair_value) VALUES (?, 'mlb', 'g9', 'moneyline',"
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
    card = views._today_card(entry, {"prediction_id": pid, "phrase": "x"},
                             taken=False, group_tier=None, unit_dollars=None)
    # the question names the away side, so the chip is the other half of 54%
    assert card["model_words"] == "46¢"
    line = views._recommendations_block(
        conn, [{"prediction_id": pid, "on_shortlist": True, "phrase": "x"}])
    assert "54¢" in line["lines"][0]["words"]
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
    what was in force when its claim was written, as the sentence is."""
    from gridiron import views

    conn = _world(tmp_path, status="final", kickoff="2026-09-09T00:00:00Z")
    pid = _away_pick(conn)                    # its claim: 2026-09-07T01:30Z
    recommend.record_for(conn, [pid])
    _correct(conn, active_from="2026-09-20T00:00:00Z")
    got = recommend.for_predictions(conn, [pid])[0]
    assert (got["side"], got["correction_version"]) == ("no", None)
    assert got["fair_value"] == pytest.approx(0.43)
    beside = views._at_the_line(conn, "mlb", [pid], {})[pid]
    assert beside["model_prob"] == pytest.approx(got["fair_value"])
    row = conn.execute("SELECT side, correction_version FROM recommendations").fetchone()
    assert (row["side"], row["correction_version"]) == ("no", None)
    # A CORRECTION IN FORCE WHEN THE CLAIM WAS WRITTEN is the one that was
    # current for it, and the finished card keeps it -- pick and sentence.
    earlier = _world(tmp_path / "earlier", status="final",
                     kickoff="2026-09-09T00:00:00Z")
    epid = _away_pick(earlier)
    version = _correct(earlier, active_from="2026-09-01T00:00:00Z")
    kept = recommend.for_predictions(earlier, [epid])[0]
    assert (kept["side"], kept["correction_version"]) == ("yes", version)
    beside = views._at_the_line(earlier, "mlb", [epid], {})[epid]
    assert beside["model_prob"] == pytest.approx(kept["fair_value"], abs=1e-4)


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
    got = recommend.for_predictions(conn, [pid])[0]
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
           for e in recommend.for_predictions(conn, [ours, theirs])}
    assert (got[ours]["side"], got[ours]["correction_version"]) == ("yes", version)
    assert (got[theirs]["side"], got[theirs]["correction_version"]) == ("no", None)
    assert got[theirs]["fair_value"] == pytest.approx(0.43)


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
    given later reads. Returns (conn, rec row after closing, counts)."""
    conn = _world(tmp_path, kickoff="2026-09-07T02:00:00Z")
    pid = _pick(conn)
    recommend.record_for(conn, [pid])
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
    recommend.record_for(conn, [pid])
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
    recommend.record_for(conn, [pid])
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
    # a second recommendation, still open, on the same prediction
    conn.execute(
        "INSERT INTO recommendations (prediction_id, sport, game_id, market,"
        " side, fair_value, price, edge_cents, size_kind, size_units, gate_n,"
        " created_utc) SELECT prediction_id, sport, game_id, market, side,"
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
        question="Seattle covering -4.5", fair_value=0.58, price=0.46,
        edge_cents=8.6, side="yes", units=1.0, flat=True,
        size_why="no measured edge yet: 3 of 100 settled in this market")
    assert "flat unit" in line and "8.6" in line
    for words in (line, language.nothing_priced_line(18, 4, 14),
                  language.nothing_priced_line(0, 0, 0),
                  language.clv_line(10, None, None, 50),
                  language.clv_line(0, None, None, 50, unmeasured=16,
                                    restated=33)):
        assert audit.advice_word_faults(words) == [], words
        assert audit.plain_words_violations(words) == [], words
