"""A proposed combo is worth the product of its picked sides, each leg named
on its picked side.

Pick-number step B (2026-09-30), under the queue rule as amended that day:
"anything that could show the operator a wrong number on a pick (side,
price, probability, size) joins the queue first, display or not" -- and the
reading recorded in docs/REPAIR_STATE.md: a number on a pick is always
stated under the words of the exact contract it belongs to.

Finding 1 of the wrong-side fix's builder and prover: `combos.propose`
multiplied each leg's `fair_value` -- the claim's FIXED proposition's
number, the home side or the over -- whichever side the leg's
recommendation buys, worked its ceiling out from that and priced its
singles line off the yes price; and `views._proposal_card` named each leg in
its question's words. On the record's priced slates 34 of 35 proposals were
drawn at a worth that was not their picked sides' product ("Rutgers covers
-24.5 + Navy covers -6.5" at 2% where the sides bought give 71.1%) and 8
named a leg on the side it did not buy.

LAW 5's combo clause is unchanged: proposed, never priced at the venue, and
a same-game combo refused.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from gridiron import audit, db, language, shortlist, views
from gridiron.market import combos, recommend

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def covered(monkeypatch):
    """The coverage list is not what these tests are about (test_recommend's
    reason): every market is priceable here."""
    from gridiron.priced import coverage

    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market, **_: {
        "priceable": True, "market": market, "why": "covered, in this test"})


def _world(tmp_path, legs):
    """Baseball moneylines on one slate, one question per game: the away side
    at 57%, a claim of 43% on the home side against the home price given,
    all on the shortlist, every game in 2099. At 48.5c the pick buys the
    away side (the claim's no side, the side its words name: 57% at 51.5c);
    at 30c it buys the home side (the claim's yes side, the other side of
    its words: 43% at 30c)."""
    dist = {"quantity": "home_margin", "family": "normal", "mean": 2.0, "sd": 13.0,
            "declared": "2026-08-31T00:00:00Z", "written_blind": True}
    conn = db.open_db(tmp_path / "combos.db")
    ids = []
    claimed = "2026-09-07T01:30:00Z"
    for game, home, away, price in legs:
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " ?, ?, '2099-01-01T00:00:00Z', 'scheduled', '2026-09-08')",
            (game, home, away))
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES"
            " ('2026-09-07T00:00:00Z', 'mlb', ?, 'moneyline', ?, NULL, 0.57,"
            " 'win', 'statistical', 'final', 'fs2', ?, 'test')",
            (game, away, json.dumps({"coverage": 1.0, "margin_distribution": dist})))
        pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " implied_prob, kind) VALUES (?, ?, 'test', ?, 'open_at_predict')",
            (pid, claimed, price))
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
            " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
            " VALUES ('kalshi', ?, 'e', 'mlb', ?, 'moneyline', 'home_win', NULL,"
            " 'home', ?, ?, ?)", (f"t{game}", game, price - 0.01, price + 0.01, claimed))
        quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
            " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
            " model_prob, venue_price, venue_implied, price_basis, created_utc)"
            " VALUES (?, ?, 'kalshi', 'mlb', ?, 'moneyline', 'home_win', NULL,"
            " 'home', 'line_less', NULL, NULL, 0.43, ?, ?, 'mid', ?)",
            (pid, quote, game, price, price, claimed))
        ids.append(pid)
    conn.commit()
    # A COMBO IS MADE OF PICKS (operator ruling B, 2026-10-05: no Kalshi game
    # market "feeds a combo proposal, until its market passes its gate"; built
    # 2026-10-07): this world's baseball moneylines are given their hundred
    # settled comparisons at the venue's price, as the record's own has.
    from tests.gate_world import pass_the_gate

    pass_the_gate(conn, sport="mlb", market="moneyline")
    shortlist.rank_rows(conn, ids)
    return conn, ids


def _totals_world(tmp_path, games):
    """Baseball totals on one slate, the shape the reasoning pass's combos
    had on the record (MLB 165 and 166), written here as the statistical
    model's: each question "under 8.5 total runs" at 62%, a claim
    of 38% on the over against a 51.5c over, so each pick buys the under --
    the claim's no side, the side its words name -- at 48.5c. `games` is
    [(game, home, away)], all in 2099, all on the shortlist."""
    conn = db.open_db(tmp_path / "totals.db")
    ids = []
    claimed = "2026-09-07T01:30:00Z"
    for game, home, away in games:
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'mlb', 2026, 1, 'R',"
            " ?, ?, '2099-01-01T00:00:00Z', 'scheduled', '2026-09-08')",
            (game, home, away))
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES"
            " ('2026-09-07T00:00:00Z', 'mlb', ?, 'total', ?, 8.5, 0.62, 'under',"
            " 'statistical', 'final', 'fs2', ?, 'test')",
            (game, f"{away} at {home}", json.dumps({"coverage": 1.0})))
        pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
        conn.execute(
            "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
            " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
            " VALUES ('kalshi', ?, 'e', 'mlb', ?, 'total', 'total', 8.5, 'over',"
            " 0.505, 0.525, ?)", (f"t{game}", game, claimed))
        quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
        conn.execute(
            "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
            " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
            " model_prob, venue_price, venue_implied, price_basis, created_utc)"
            " VALUES (?, ?, 'kalshi', 'mlb', ?, 'total', 'total', 8.5, 'over',"
            " 'rung_matched', NULL, NULL, 0.38, 0.515, 0.515, 'mid', ?)",
            (pid, quote, game, claimed))
        ids.append(pid)
    conn.commit()
    # A COMBO IS MADE OF PICKS (operator ruling B, 2026-10-05: no Kalshi game
    # market "feeds a combo proposal, until its market passes its gate"; built
    # 2026-10-07): this world's baseball totals are given their hundred
    # settled comparisons at the venue's price, as the record's own has.
    from tests.gate_world import pass_the_gate

    pass_the_gate(conn, sport="mlb", market="total")
    shortlist.rank_rows(conn, ids)
    return conn, ids


def _proposals(payload):
    return ((payload.get("today") or {}).get("combos") or {}).get("cards") or []


def _entry(pid, *, game, side, fair, price, edge, sport="mlb", market="moneyline"):
    return {"prediction_id": pid, "sport": sport, "game_id": game, "market": market,
            "fair_value": fair, "price": price, "edge_cents": edge, "side": side}


# --- the arithmetic ------------------------------------------------------------

def test_a_leg_is_its_picked_sides_number_and_cost():
    """The yes side is the proposition's number at the yes price; the no side
    is one minus it, at the rest of the dollar -- `recommend._cost_of`'s
    orientation, so the leg's worth less its cost and the fee is its own
    edge."""
    yes = combos.leg_on_its_side({"side": "yes", "fair_value": 0.43, "price": 0.30})
    assert yes == {"side": "yes", "worth": 0.43, "cost": 0.30}
    no = combos.leg_on_its_side({"side": "no", "fair_value": 0.43, "price": 0.485})
    assert no["side"] == "no"
    assert no["worth"] == pytest.approx(0.57) and no["cost"] == pytest.approx(0.515)
    for got, side, price in ((yes, "yes", 0.30), (no, "no", 0.485)):
        edge = recommend.edge_cents(0.43, price, side)
        mine = round((got["worth"] - got["cost"] - recommend.fee(got["cost"])) * 100, 2)
        assert mine == edge


def test_a_side_that_is_neither_is_refused_by_name():
    """A side is 'yes' or 'no' of the claim's proposition; anything else is
    refused by name, never read as one of the two."""
    with pytest.raises(ValueError, match="'yes' or the 'no' side"):
        combos.leg_on_its_side({"side": "home", "fair_value": 0.43, "price": 0.3,
                                "prediction_id": 7})
    with pytest.raises(ValueError, match="'yes' or the 'no' side"):
        combos.propose([_entry(1, game="g1", side="home", fair=0.43, price=0.3, edge=5.0),
                        _entry(2, game="g2", side="no", fair=0.43, price=0.485, edge=3.5)],
                       sport="mlb")


def test_a_combo_is_worth_the_product_of_its_picked_sides():
    """Two legs bought on the no side (an under at 38% for the over, and an
    away club at 43% for the home side): the combo is worth 0.62 x 0.57, not
    0.38 x 0.43, and the ceiling and the singles line are those sides' --
    at 51.5c and 56c, never the yes prices."""
    legs = [_entry(1, game="g1", side="no", fair=0.38, price=0.44, edge=4.0,
                   market="total"),
            _entry(2, game="g2", side="no", fair=0.43, price=0.485, edge=3.5)]
    out = combos.propose(legs, sport="mlb")
    assert len(out) == 1
    proposal = out[0]
    assert proposal["fair"] == combos.fair_value([0.62, 0.57]) == 0.3534
    assert proposal["fair"] != combos.fair_value([0.38, 0.43])
    assert proposal["ceiling_cents"] == combos.price_ceiling(0.3534)["ceiling_cents"]
    assert proposal["singles"] == combos.singles_alternative([0.56, 0.515], [0.62, 0.57])
    assert [leg["side"] for leg in proposal["legs"]] == ["no", "no"]
    assert [round(leg["worth"], 4) for leg in proposal["legs"]] == [0.62, 0.57]
    assert [round(leg["cost"], 4) for leg in proposal["legs"]] == [0.56, 0.515]
    # THE SINGLES LINE IS THE LEGS' OWN EDGES: each leg's worth less its cost
    # and the fee is the edge its recommendation was chosen on.
    mean_edge = (recommend.edge_cents(0.38, 0.44, "no")
                 + recommend.edge_cents(0.43, 0.485, "no")) / 2
    assert proposal["singles"]["singles_edge_cents"] == round(mean_edge, 2)


def test_a_yes_side_leg_keeps_its_own_numbers():
    """Nothing that was right moves: a leg bought on the yes side is the
    proposition's number at the yes price, as before."""
    legs = [_entry(1, game="g1", side="yes", fair=0.62, price=0.46, edge=12.0),
            _entry(2, game="g2", side="yes", fair=0.43, price=0.30, edge=11.0)]
    proposal = combos.propose(legs, sport="mlb")[0]
    assert proposal["fair"] == combos.fair_value([0.62, 0.43])
    assert proposal["singles"] == combos.singles_alternative([0.46, 0.30], [0.62, 0.43])


def test_the_combo_clause_is_unchanged():
    """LAW 5: proposed, never priced at the venue -- no venue price, edge or
    payout on the proposal -- and a same-game pair refused whichever sides
    its legs are bought on."""
    same_game = [_entry(1, game="g1", side="no", fair=0.43, price=0.485, edge=3.5),
                 _entry(2, game="g1", side="yes", fair=0.43, price=0.30, edge=11.0)]
    assert combos.propose(same_game, sport="mlb") == []
    out = combos.propose(
        [_entry(1, game="g1", side="no", fair=0.43, price=0.485, edge=3.5),
         _entry(2, game="g2", side="yes", fair=0.43, price=0.30, edge=11.0)],
        sport="mlb")
    assert [k for k in ("price", "edge_cents", "payout", "venue_price")
            if out[0].get(k) is not None] == []


# --- the page ------------------------------------------------------------------

def test_the_page_multiplies_the_sides_bought(tmp_path, covered):
    """"BBB to win" and "DDD to win", each bought on the claim's no side --
    the away club, the side its words name, 57% at 51.5c. As released the
    combo was worth 0.43 x 0.43 = 18%, "worth taking only below 16¢"; the
    sides bought are worth 0.57 x 0.57."""
    conn, ids = _world(tmp_path, [("g0", "AAA", "BBB", 0.485),
                                  ("g1", "CCC", "DDD", 0.485)])
    payload = views.week(conn, "mlb", 2026, 1)
    [proposal] = _proposals(payload)
    assert proposal["fair"] == 0.3249
    assert proposal["fair_words"] == language.price_chip_words(32.49)
    ceiling = combos.price_ceiling(0.3249)["ceiling_cents"]
    assert proposal["ceiling_cents"] == ceiling
    assert proposal["ceiling_words"] == language.combo_ceiling_words(ceiling)
    singles = combos.singles_alternative([0.515, 0.515], [0.57, 0.57])
    assert proposal["singles_words"] == language.combo_singles_words(singles)
    assert sorted(leg["side_words"] for leg in proposal["legs"]) == ["BBB to win",
                                                                     "DDD to win"]
    assert sorted(leg["words"] for leg in proposal["legs"]) == [
        "BBB to win · BBB at AAA", "DDD to win · DDD at CCC"]
    assert [leg["fair_cents"] for leg in proposal["legs"]] == [57, 57]
    assert audit.combo_side_faults(payload) == []
    conn.close()


def test_the_page_names_each_leg_on_the_side_it_buys(tmp_path, covered):
    """"DDD to win" at 57% against a 30c home price is bought as CCC to win
    (43% at 30c, +11.0c), as recs 47 and 82 were bought on the other side of
    their words. As released the leg was drawn "DDD to win"; it is named on
    the side it buys, in the words its recommendation line uses."""
    conn, ids = _world(tmp_path, [("g0", "AAA", "BBB", 0.485),
                                  ("g1", "CCC", "DDD", 0.30)])
    payload = views.week(conn, "mlb", 2026, 1)
    [proposal] = _proposals(payload)
    legs = {leg["prediction_id"]: leg for leg in proposal["legs"]}
    assert legs[ids[0]]["side_words"] == "BBB to win" and legs[ids[0]]["side"] == "no"
    assert legs[ids[1]]["side_words"] == "CCC to win" and legs[ids[1]]["side"] == "yes"
    # AND THE GAME EACH IS IN (the prover, 2026-09-30).
    assert legs[ids[0]]["words"] == "BBB to win · BBB at AAA"
    assert legs[ids[1]]["words"] == "CCC to win · DDD at CCC"
    lines = {x["prediction_id"]: x for x in payload["recommendations"]["lines"]}
    for pid, leg in legs.items():
        assert leg["side_words"] == lines[pid]["side_words"]
        assert leg["worth"] == pytest.approx(lines[pid]["fair_value"])
        assert leg["cost"] == pytest.approx(lines[pid]["price"])
    assert proposal["fair"] == combos.fair_value([0.43, 0.57]) == 0.2451
    assert audit.combo_side_faults(payload) == []
    # AS RELEASED: the leg in its question's words.
    legs[ids[1]]["words"] = "DDD to win"
    faults = audit.combo_side_faults(payload)
    assert any("side it does not buy" in f and "'CCC to win · DDD at CCC'" in f
               for f in faults), faults
    with pytest.raises(audit.LawViolation, match="ANOTHER SIDE'S NUMBER OR NAMES A LEG"):
        audit.check_every_combo_is_its_picked_sides(payload)
    conn.close()


def test_each_leg_names_the_game_it_is_in(tmp_path, covered):
    """THE PROVER OF STEP B (2026-09-30). The card draws its legs and nothing
    around them, so two totals read "under 8.5 total runs + under 8.5 total
    runs" -- three of the reasoning pass's baseball combos on the record --
    and the worth named no contract. Each leg is its side's words and the
    game it is in, as the board heads that game."""
    conn, ids = _totals_world(tmp_path, [("g0", "AAA", "BBB"), ("g1", "CCC", "DDD")])
    payload = views.week(conn, "mlb", 2026, 1)
    [proposal] = _proposals(payload)
    legs = {leg["prediction_id"]: leg for leg in proposal["legs"]}
    assert [legs[pid]["side_words"] for pid in ids] == ["under 8.5 total runs"] * 2
    assert [legs[pid]["words"] for pid in ids] == [
        "under 8.5 total runs · BBB at AAA", "under 8.5 total runs · DDD at CCC"]
    rows = {g["game_id"]: g for g in payload["board"]["games"]}
    for leg in proposal["legs"]:
        # THE GAME AS THE BOARD HEADS IT, so the leg can be found on the page.
        card = next(c for c in payload["cards"] if c["prediction_id"] == leg["prediction_id"])
        assert leg["words"].endswith(" · " + card["row_title"])
        assert leg["game_id"] in rows
    assert proposal["fair"] == combos.fair_value([0.62, 0.62])
    assert audit.combo_side_faults(payload) == []
    # AS THE BUILD FIRST DREW IT: the side's words alone, twice alike.
    for leg in proposal["legs"]:
        leg["words"] = leg["side_words"]
    faults = audit.combo_side_faults(payload)
    assert sum("without the game it is in" in f for f in faults) == 2, faults
    with pytest.raises(audit.LawViolation, match="ANOTHER SIDE'S NUMBER OR NAMES A LEG"):
        audit.check_every_combo_is_its_picked_sides(payload)
    conn.close()


def test_a_leg_names_its_game_by_the_rows_title_or_a_props_matchup():
    """The game words: the row title the board heads the game with ("Rays at
    Braves"; a fight's "Hooker vs Parnasse", which has no home side), and a
    prop's matchup, since a prop's row title is its player."""
    assert language.combo_leg_words(
        "under 8.5 total runs", {"market_type": "total", "row_title": "Rays at Braves",
                                 "matchup": "Rays at Braves"}) == \
        "under 8.5 total runs · Rays at Braves"
    assert language.combo_leg_words(
        "Goes the distance", {"market_type": "distance", "row_title": "Hooker vs Parnasse",
                              "matchup": "Parnasse at Hooker"}) == \
        "Goes the distance · Hooker vs Parnasse"
    assert language.combo_leg_words(
        "Josh Allen over 245.5 passing yards",
        {"market_type": "prop", "row_title": "Allen · passing yards",
         "matchup": "Packers at Bills"}) == \
        "Josh Allen over 245.5 passing yards · Packers at Bills"
    assert language.combo_leg_words("BBB to win", {}) == "BBB to win"


def test_the_check_names_each_released_shape_of_the_page(tmp_path, covered):
    """The page's own payload, put back one place at a time as the released
    code drew it: the worth, the ceiling and the singles line of the yes
    sides, and a leg's number the proposition's. Each is named."""
    conn, ids = _world(tmp_path, [("g0", "AAA", "BBB", 0.485),
                                  ("g1", "CCC", "DDD", 0.485)])
    yes_fair = combos.fair_value([0.43, 0.43])
    yes_ceiling = combos.price_ceiling(yes_fair)["ceiling_cents"]
    yes_singles = combos.singles_alternative([0.485, 0.485], [0.43, 0.43])
    for change, legs, want in (
            ({"fair": yes_fair}, None, "multiply to 0.3249"),
            ({"ceiling_cents": yes_ceiling,
              "ceiling_words": language.combo_ceiling_words(yes_ceiling)}, None,
             "worth taking below"),
            ({"singles_words": language.combo_singles_words(yes_singles),
              "fee_ratio": yes_singles["ratio"]}, None, "singles line on another side"),
            ({}, {"fair_cents": 43}, "whose model number is 0.57")):
        payload = views.week(conn, "mlb", 2026, 1)
        [proposal] = _proposals(payload)
        proposal.update(change)
        if legs:
            proposal["legs"][0].update(legs)
        faults = audit.combo_side_faults(payload)
        assert any(want in f for f in faults), (want, faults)
    conn.close()


def test_the_scanners_fixtures_hold_every_released_shape():
    """The fixture the check holds itself to at import: the slate as this
    step leaves it passes, and every released shape is named."""
    assert audit.combo_side_faults(audit.COMBO_SIDE_FIXTURE_GOOD) == []
    for name, change in audit.COMBO_SIDE_FIXTURES_AS_RELEASED.items():
        assert audit.combo_side_faults(audit._combo_side_fixture(**change)), name


def test_a_leg_with_no_recommendation_line_is_named():
    """Every leg clears the bar alone (LAW 5), so every leg has a
    recommendation line saying which side it is bought on; a leg without one
    is a leg the app does not recommend on its own."""
    payload = json.loads(json.dumps(audit.COMBO_SIDE_FIXTURE_GOOD))
    payload["recommendations"]["lines"] = payload["recommendations"]["lines"][:1]
    faults = audit.combo_side_faults(payload)
    assert any("no recommendation line" in f for f in faults), faults


def test_the_gates_step_2_makes_the_call_on_every_sport():
    """Gate step 2 hands every sport's slate on the record's copy to the
    check, read from its syntax tree."""
    tree = ast.parse((ROOT / "tools" / "verify.py").read_text(encoding="utf-8"))
    step = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert any(isinstance(node, ast.Attribute)
               and node.attr == "check_every_combo_is_its_picked_sides"
               for node in ast.walk(step))
