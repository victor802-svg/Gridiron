"""PICKS ARE RANKED BY EDGE, NEVER BY CHANCE (operator ruling B, 2026-10-05;
built 2026-10-07).

The ruling, whole (docs/briefs/2026-10-05-rulings.md):

  "B. Picks are ranked by edge, never by chance of hitting (every page).
  1. Edge = model's chance minus the price (Kalshi) or minus the break-even of
  the payout (pick'em), after fees. Chance of hitting alone never ranks
  anything.
  2. A leg is called a pick only if its edge after fees is 3 percentage points
  or more. Below that it is shown as a number, never as a pick.
  3. Every pick and every browse row shows its payout as a multiplier beside
  its chance and edge, e.g. "62% · 2-pick break-even 57.7% · edge +4.3".
  4. No filling. When nothing clears on a slate: "Nothing worth taking today".
  5. Kalshi game markets (spreads, moneylines, totals) stay on the board with
  their numbers, but none carries a pick badge, and none feeds a combo
  proposal, until its market passes its gate."

The readings (docs/REPAIR_STATE.md, "Rulings taken in your absence"): a pick
needs the writer's own bar, three points after fees and, in a Kalshi game
market, B.5's gate -- its at-the-line record's hundred settled comparisons,
this forecaster's; a pick is ranked by its edge and nothing else; everything
else is ordered by its start and the declared market order; the writer is
not changed, and the page draws a recommendation that is not a pick with its
numbers only and says why. Every test here fails on 4274f1d, the release
before the ruling, but the one that holds what was right and says so.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from gridiron import audit, board, config, db, language, settings, shortlist, views
from gridiron.market import at_the_line, recommend
from gridiron.priced import coverage
from tests.gate_world import pass_the_gate

ROOT = Path(__file__).resolve().parents[1]
DIST = {"quantity": "home_margin", "family": "normal", "mean": -3.0, "sd": 13.5,
        "declared": "2026-08-31T00:00:00Z", "written_blind": True}
CLUBS = {"NO": ("New Orleans Saints", "Saints", "New Orleans"),
         "ATL": ("Atlanta Falcons", "Falcons", "Atlanta"),
         "DET": ("Detroit Lions", "Lions", "Detroit"),
         "GB": ("Green Bay Packers", "Packers", "Green Bay")}
NOTHING = "Nothing worth taking today"


@pytest.fixture(autouse=True)
def covered(monkeypatch):
    """The coverage list is not what these test: every market is priceable."""
    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market, **_: {
        "priceable": True, "market": market, "why": "covered, in this test"})


def _world(path, games, *, gated=()):
    """NFL week 5 of 2026, its games in 2099: (game id, home, away, hours after
    17:00, questions), a question (market, line asked, the model's number,
    side, priced) with priced None or (claim line, claim number, price) off
    the home contract selling that line. `gated`: (market, forecaster) pairs
    past B.5's gate. Returns (conn, {(game, market): id})."""
    conn = db.open_db(path)
    for code in sorted({c for _g, h, a, _x, _q in games for c in (h, a)}):
        full, short, city = CLUBS[code]
        conn.execute(
            "INSERT INTO teams (sport, tricode, display_name, short_name, location,"
            " source_url, fetched_utc) VALUES ('nfl', ?, ?, ?, ?, 'test',"
            " '2026-09-01T00:00:00Z')", (code, full, short, city))
    ids = {}
    for gid, home, away, hours, questions in games:
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES (?, 'nfl', 2026, 5, 'REG', ?, ?,"
            " ?, 'scheduled', '2026-10-12')",
            (gid, home, away, f"2099-10-12T{17 + hours:02d}:00:00Z"))
        for market, line, prob, side, priced in questions:
            subject = f"{away} @ {home}" if market == "total" else home
            conn.execute(
                "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
                " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
                " factor_set_version, factors_json, reasoning) VALUES"
                " ('2026-10-07T15:00:00Z', 'nfl', ?, ?, ?, ?, ?, ?, 'statistical',"
                " 'final', 'fs2', ?, 'test')",
                (gid, market, subject, line, prob, side,
                 json.dumps({"coverage": 1.0, "margin_distribution": DIST})))
            pid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
            ids[(gid, market)] = pid
            if priced is None:
                continue
            claim_line, model, price = priced
            quantity = {"spread": "home_margin", "moneyline": "home_win"}[market]
            conn.execute(
                "INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id,"
                " market, quantity, line, yes_side, yes_bid, yes_ask, fetched_utc)"
                " VALUES ('kalshi', ?, 'e', 'nfl', ?, ?, ?, ?, 'home', ?, ?,"
                " '2026-10-07T15:00:44Z')",
                (f"t{pid}", gid, market, quantity, claim_line, price - 0.01, price + 0.01))
            quote = conn.execute("SELECT MAX(id) FROM venue_quotes").fetchone()[0]
            shape, mean, sd = (("rung_differs_margin", -3.0, 13.5) if market == "spread"
                               else ("line_less", None, None))
            conn.execute(
                "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue, sport,"
                " game_id, market, quantity, line, side, shape, dist_mean, dist_sd,"
                " model_prob, venue_price, venue_implied, price_basis, created_utc)"
                " VALUES (?, ?, 'kalshi', 'nfl', ?, ?, ?, ?, 'home', ?, ?, ?, ?, ?, ?,"
                " 'mid', '2026-10-07T15:00:45Z')",
                (pid, quote, gid, market, quantity, claim_line, shape, mean, sd, model,
                 price, price))
    conn.commit()
    for market, predictor in gated:
        pass_the_gate(conn, sport="nfl", market=market, predictor=predictor)
    shortlist.rank_rows(conn, list(ids.values()))
    return conn, ids


#: Two recommendations on two games: a spread at +15 points after fees (rec
#: 117's numbers, read at the question's own side) and a moneyline at +10.
TWO = [("g1", "NO", "ATL", 0, [("spread", -2.5, 0.6848, "cover", (-2.5, 0.6848, 0.515))]),
       ("g2", "DET", "GB", 3, [("moneyline", None, 0.62, "win", (None, 0.62, 0.50))])]


def _card(payload, pid):
    return next((c for g in ("clears", "below_floor", "watching")
                 for c in payload["today"][g] if c["prediction_id"] == pid), {})


def _group(payload, pid):
    return next((g for g in ("clears", "below_floor", "watching")
                 for c in payload["today"][g] if c["prediction_id"] == pid), None)


def _row(payload, gid):
    return next(g for g in payload["board"]["games"] if g["game_id"] == gid)


def _line(payload, pid):
    return next(x for x in payload["recommendations"]["lines"] if x["prediction_id"] == pid)


def _week(conn):
    return views.week(conn, "nfl", 2026, 5)


# --- B.5 and reading (d): a recommendation short of its gate is a number -----

def test_a_recommendation_in_a_market_short_of_its_gate_is_a_number_and_says_why(tmp_path):
    """Rec 117's +15 points in an NFL spread with none of the hundred settled
    comparisons B.5 asks: watched, with its numbers, no size, no outline, no
    "Model's pick", and the words beside it saying how many of the hundred
    its market has. Fails on 4274f1d, which drew it in CLEARS, sized,
    outlined and "Model's pick"."""
    conn, ids = _world(tmp_path / "w.db", TWO)
    pid = ids[("g1", "spread")]
    payload = _week(conn)
    card = _card(payload, pid)
    assert _group(payload, pid) == "watching"
    assert card["pick"] is False and "size_words" not in card
    assert card["edge_words"] == "+15.0¢"
    # WHOSE COUNT IT IS, named as the Record page names its curve (the
    # prover, 2026-10-07): the market at the venue's line and the forecaster.
    assert card["not_a_pick_words"] == (
        "Not a pick: its market has 0 of the 100 settled comparisons with the "
        "venue's price it needs first (point spread at the venue's line, "
        "statistical).")
    row = _row(payload, "g1")
    assert row["pick_label_words"] == "Not a pick"
    assert row["pick"]["signal"] != "clears" and not row["pick"].get("size_words")
    assert row["pick"]["not_a_pick_words"] == card["not_a_pick_words"]
    line = _line(payload, pid)
    assert line["pick"] is False and line["units"] is None
    assert "flat unit" not in line["words"] and line["words"].endswith(
        "it is worth +15.0¢ a contract after the fee. Not a pick: its market has 0 "
        "of the 100 settled comparisons with the venue's price it needs first "
        "(point spread at the venue's line, statistical).")
    assert payload["today"]["combos"]["cards"] == []
    assert audit.pick_rank_faults(conn, payload) == []
    conn.close()


def test_the_writer_records_what_it_recorded_before(tmp_path):
    """HOLDS WHAT WAS RIGHT (reading (d)): the recommendation writer is not
    changed -- it records the ungated spread with its flat unit, as it did on
    4274f1d, and the closing line's measurement rests on such rows."""
    conn, ids = _world(tmp_path / "w.db", TWO)
    pid = ids[("g1", "spread")]
    got = recommend.record_for(conn, [pid])
    row = conn.execute("SELECT side, size_kind, size_units, edge_cents FROM recommendations"
                       " WHERE prediction_id = ?", (pid,)).fetchone()
    assert got["recommended"] == 1 and tuple(row) == ("yes", "flat", 1.0, 14.98)
    conn.close()


# --- B.1, B.2 and B.5: a pick, past its gate, ranked by edge -----------------

def test_past_its_gate_three_points_is_a_pick_and_the_picks_are_ranked_by_edge(tmp_path):
    """With both markets past the gate, both recommendations are picks: in
    CLEARS by their edge, best first (+15 before +10, whatever the order the
    record wrote them in), sized, outlined, "Model's pick", with the pick's
    badge; and the two make a combo. Fails on 4274f1d, which drew the
    moneyline first (the engine's order) and wore no badge."""
    games = [TWO[1], TWO[0]]          # the moneyline is written first
    conn, ids = _world(tmp_path / "w.db", games,
                       gated=[("spread", "statistical"), ("moneyline", "statistical")])
    spread, money = ids[("g1", "spread")], ids[("g2", "moneyline")]
    assert money < spread
    payload = _week(conn)
    assert [c["prediction_id"] for c in payload["today"]["clears"]] == [spread, money]
    card = _card(payload, spread)
    assert card["pick"] is True and card["size_words"] and "not_a_pick_words" not in card
    assert card["pick_words"] == "Pick · +15.0 after fees"
    row = _row(payload, "g1")
    assert row["pick_label_words"] == "Model's pick" and row["pick"]["signal"] == "clears"
    assert row["pick"]["pick_words"] == "Pick · +15.0 after fees"
    combos = payload["today"]["combos"]["cards"]
    assert [sorted(leg["prediction_id"] for leg in c["legs"]) for c in combos] == [
        sorted([spread, money])]
    assert payload["today"]["nothing_words"] is None
    assert payload["board"]["nothing_clears_words"] is None
    assert audit.pick_rank_faults(conn, payload) == []
    conn.close()


def test_a_pick_under_three_points_is_a_number_never_drawn_at_three(tmp_path):
    """2.97 points after fees, in a market past its gate, cleared the writer's
    bar (5.7% of the 52c it costs): it is watched, unsized, its edge drawn
    "+2.9c" -- never "+3.0c" -- and the words say it is under the three a pick
    needs. Fails on 4274f1d (a pick, "+3.0c")."""
    model = 0.52 + 0.02 + 0.0297
    conn, ids = _world(tmp_path / "w.db",
                       [("g1", "NO", "ATL", 0, [("spread", -2.5, model, "cover",
                                                 (-2.5, model, 0.52))])],
                       gated=[("spread", "statistical")])
    pid = ids[("g1", "spread")]
    payload = _week(conn)
    card = _card(payload, pid)
    assert _group(payload, pid) == "watching" and card["pick"] is False
    assert card["edge_points"] == pytest.approx(2.97)
    assert card["edge_words"] == "+2.9¢" and card["edge_line_words"] == "+2.9¢"
    assert card["not_a_pick_words"] == (
        "Not a pick: its edge after fees is +2.9 points, under the 3 a pick needs.")
    assert _row(payload, "g1")["pick"]["edge_words"] == "+2.9¢"
    assert "+3.0" not in _line(payload, pid)["words"]
    assert audit.pick_rank_faults(conn, payload) == []
    conn.close()


def test_the_edge_drawn_under_the_bar_never_reaches_it():
    """Reading (c): a figure under three points that would round to 3.0 is
    drawn at the tenth below it; every other figure as it was."""
    from gridiron import picks

    assert picks.drawn_edge(2.97, 2.97) == 2.9
    assert picks.drawn_edge(2.95001, 2.95) == 2.9
    assert picks.drawn_edge(2.996, 3.0) == 2.9
    assert picks.drawn_edge(3.0, 3.0) == 3.0
    assert picks.drawn_edge(14.98, 14.98) == 14.98
    assert picks.drawn_edge(2.5, 2.5) == 2.5
    assert picks.drawn_edge(None, 2.97) == 2.9
    assert language.prop_edge_words(picks.drawn_edge(2.97) / 100) == "edge +2.9"


def test_one_bar_for_both_venues_and_the_gate_as_ruled():
    from gridiron import picks

    assert picks.GAME_MARKETS == at_the_line.BET_MARKETS
    assert config.GAME_MARKET_PICK_GATE == 100 == audit.GAME_MARKET_GATE_AS_RULED
    assert board.clears_the_pick_bar(0.03) and picks.clears_the_pick_bar(0.03)
    assert not board.clears_the_pick_bar(0.0297) and not picks.clears_the_pick_bar(0.0297)


# --- reading (b): never by chance; the lead is the best pick or the first market

def test_a_rows_lead_is_its_best_pick_else_the_first_declared_market(tmp_path):
    """No pick on ATL at NO: its lead is the spread, the first of the NFL's
    declared markets, and its questions are in that order -- never the
    moneyline at 93%, the surest. Fails on 4274f1d, which led with the
    surest and labelled it "Model's pick"."""
    conn, ids = _world(tmp_path / "w.db", [
        ("g1", "NO", "ATL", 0, [("total", 44.5, 0.6, "over", None),
                                ("moneyline", None, 0.93, "win", None),
                                ("spread", -2.5, 0.55, "cover", None)])])
    payload = _week(conn)
    row = _row(payload, "g1")
    assert row["pick"]["prediction_id"] == ids[("g1", "spread")]
    assert row["pick_label_words"] == "Not a pick"
    assert [q["prediction_id"] for q in row["questions"]] == [
        ids[("g1", "spread")], ids[("g1", "moneyline")], ids[("g1", "total")]]
    assert audit.pick_rank_faults(conn, payload) == []
    conn.close()


def test_a_live_or_finished_row_is_never_labelled_a_pick():
    assert language.pick_label_words("final", "won") == "The model's number · won"
    assert language.pick_label_words("live", "none") == "The model's number · pregame"
    assert language.pick_label_words("upcoming", "none") == "Not a pick"
    assert language.pick_label_words("upcoming", "clears", pick=True) == "Model's pick"


def test_no_page_orders_or_leads_by_the_models_chance():
    """The Games page's "the model's chance" sort is gone and no renderer that
    orders rows or tiles reads a chance; the 'edge' sort is offered."""
    assert "sort_prob" not in language.board_labels()
    assert audit.games_order_faults() == []
    js = (ROOT / "gridiron" / "web" / "app.js").read_text(encoding="utf-8")
    assert "['edge', labels.sort_edge]" in js


# --- B.3: the multiplier beside the chance and the edge ----------------------

def test_every_priced_row_draws_its_multiplier_beside_its_chance_and_edge(tmp_path):
    """The row's face draws the chance, the multiplier and the edge (the
    renderer draws `pick.edge_words` now), each the side drawn's. Fails on
    4274f1d, whose row face drew no edge."""
    conn, ids = _world(tmp_path / "w.db", [
        ("g1", "NO", "ATL", 0, [("spread", -2.5, 0.55, "cover", (-2.5, 0.55, 0.52))])])
    payload = _week(conn)
    lead = _row(payload, "g1")["pick"]
    assert (lead["prob_words"], lead["pays_words"], lead["edge_words"]) == (
        "55%", "1.92x", "+1.0¢")
    assert audit.row_face_faults() == []
    conn.close()


# --- B.4: no filling ----------------------------------------------------------

def test_nothing_worth_taking_today_on_games_and_today(tmp_path):
    """A slate with questions to come and no pick says "Nothing worth taking
    today" in the Today groups and above the Games rows, priced or not; with
    a pick it says nothing of the kind. Fails on 4274f1d, which said "Nothing
    clears the bar today. Every pick below is priced..." on a priced slate
    only, and nothing in the Today groups."""
    conn, _ids = _world(tmp_path / "unpriced.db",
                        [("g1", "NO", "ATL", 0, [("spread", -2.5, 0.55, "cover", None)])])
    payload = _week(conn)
    assert payload["today"]["nothing_words"] == NOTHING
    assert payload["board"]["nothing_clears_words"] == NOTHING
    conn.close()
    conn, _ids = _world(tmp_path / "ungated.db", TWO)
    payload = _week(conn)
    assert payload["today"]["nothing_words"] == NOTHING
    assert payload["board"]["nothing_clears_words"] == NOTHING
    assert "picks" not in payload["today"]["count_words"]
    assert payload["today"]["count_words"].startswith("the model has no pick")
    conn.close()


def test_the_day_strip_and_the_taken_rail_call_nothing_a_pick():
    words = language.day_strip_words(day_words=None, slate_words="NFL", clears=0,
                                     watching=3, below_floor=0, floor=1.0,
                                     forecaster="statistical")
    assert words["counts"] == "the model has no pick · 3 questions watched"
    two = language.day_strip_words(day_words=None, slate_words="NFL", clears=2,
                                   watching=1, below_floor=0, floor=1.0,
                                   forecaster="statistical")
    assert two["counts"].startswith("the model has 2 picks")
    assert language.taken_today_heading(2) == "Taken today · 2 marked"


# --- the gate's check ---------------------------------------------------------

def test_the_check_names_each_way_a_pick_can_be_drawn_wrong(tmp_path):
    """On the ungated pair: called a pick, sized, outlined; headed "Model's
    pick"; fed to a combo; "Nothing worth taking today" left off; a row's
    multiplier taken away; the watched cards ordered by their edge -- each
    named by `audit.pick_rank_faults`."""
    conn, ids = _world(tmp_path / "w.db", TWO)
    spread, money = ids[("g1", "spread")], ids[("g2", "moneyline")]
    good = _week(conn)
    assert audit.pick_rank_faults(conn, good) == []

    def planted(change):
        p = json.loads(json.dumps(good, default=str))
        change(p)
        return audit.pick_rank_faults(conn, p)

    def called(p):
        card = _card(p, spread)
        p["today"]["watching"].remove(card)
        p["today"]["clears"].append(dict(card, pick=True, size_words="$15"))

    assert any("short of its gate" in f for f in planted(called))
    assert any("where it is not a pick" in f for f in planted(
        lambda p: _row(p, "g1").update(pick_label_words="Model's pick")))
    assert any("a combo is proposed only from picks" in f for f in planted(
        lambda p: p["today"]["combos"].update(cards=[{"legs": [
            {"prediction_id": spread}, {"prediction_id": money}]}])))
    assert any("(B.4)" in f for f in planted(
        lambda p: p["today"].update(nothing_words=None)))
    assert any("(B.3)" in f for f in planted(
        lambda p: _row(p, "g1")["pick"].update(pays_words="")))
    assert any("out of B's order" in f for f in planted(
        lambda p: p["today"]["watching"].reverse()))
    assert any("carries 'size_words'" in f for f in planted(
        lambda p: _row(p, "g1")["pick"].update(size_words="$15")))
    conn.close()


def test_the_gate_makes_the_call():
    """Step 2 of `tools/verify.py` calls `audit.check_picks_are_ranked_by_edge`
    on every sport's slate, both forecasters."""
    tree = ast.parse((ROOT / "tools" / "verify.py").read_text(encoding="utf-8"))
    step = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "step_2_guards")
    assert any(isinstance(n, ast.Attribute) and n.attr == "check_picks_are_ranked_by_edge"
               for n in ast.walk(step))


# --- Props: ruling C's board held to B's order -------------------------------

def test_the_props_tiles_that_are_no_pick_are_ordered_by_start_then_market(conn):
    """Two players on one game, neither a pick: the passing stat before the
    receiving one (the NFL's declared order), whatever their names. Fails on
    4274f1d, which ordered them by player after the start."""
    from tests import test_the_props_board as c_tests

    zach, aaron = c_tests._world(conn, [
        ("Zach Wilson passing_yards", "passing_yards", 200.5, 0.6, "over", {}),
        ("Aaron Jones receiving_yards", "receiving_yards", 30.5, 0.6, "over", {})])
    tiles = _week(conn)["board"]["props"]["tiles"]
    assert [t["prediction_id"] for t in tiles] == [zach, aaron]


def test_the_entry_rail_says_clears_only_of_an_entry_whose_every_leg_is_a_pick(conn):
    """The rail's verdict keeps its arithmetic (the brief: "leave its
    arithmetic, but it may not say 'pick' below B.2"): "Clears the bar" and
    its outline only where every leg is three points or more over the
    entry's break-even, and other words otherwise. Fails on 4274f1d, which
    said it of any entry returning more than a dollar per dollar.

    FROM THE ENTRY CHECK'S STEP 1 (2026-10-07; reading (h)) THE RAIL IS THE
    ENTRY CHECK, at an even chance on every leg (step 1 has no model): "Clears
    the bar" and the green outline only where each leg's break-even is three
    points or more under an even chance -- B.2's bar, through its one door,
    `picks.clears_the_pick_bar` -- and an entry that returns more than it
    costs short of that says "No outline" and wears none. The outline is the
    server's verdict, which the page draws by `signalClass` alone. Until that
    date this test read the rail's verdict at the model's chance on each
    leg's main line, in the page's own arithmetic (`entryLines`, gone)."""
    from gridiron import entry_check

    def check(multiple):
        leg = {"player": "A Player", "club": "", "stat": "passing yards", "line": "250.5",
               "side": "over", "kind": "standard", "original_line": ""}
        return entry_check.check(conn, {"app": "prizepicks", "entry_type": "power",
                                        "legs": [leg, dict(leg)],
                                        "payout": {"multiplier": str(multiple)},
                                        "payout_confirmed": True, "promo": {"kind": "none"}},
                                 now="2099-10-01T00:00:00Z", remember_it=False)

    short = check(4.5)
    assert short["numbers"]["expected"] > 0, "4.5x on two legs returns more than it costs"
    assert short["signal"] == "none" and short["verdict_words"].startswith("No outline")
    assert "Clears" not in short["verdict_words"] and "pick" not in short["verdict_words"]
    clears = check(5)
    assert clears["signal"] == "clears" and clears["verdict_words"].startswith("Clears the bar")
    js = (ROOT / "gridiron" / "web" / "app.js").read_text(encoding="utf-8")
    body = js[js.index("function paintEntryResult("):js.index("function renderEntryRail(")]
    assert "el('div', 'verdict ' + signalClass(r.signal))" in body
    assert "sig-clears" not in body and "sig-costs" not in body


# --- THE PROVER OF RULING B (2026-10-07) -------------------------------------
#
# Each found on the change as handed to its prover, fixed, and failing on
# 4274f1d and on the change as handed: a taken tile's multiplier, the
# recommendation lines' multiplier and order, the gate's words saying whose
# count it is, and a count of open questions or a contract with no edge
# called a pick.

def test_a_taken_tile_keeps_its_multiplier_in_the_renderer():
    """B.3: "Every pick and every browse row shows its payout as a multiplier
    beside its chance and edge." The open row's tile drew "taken" in its
    multiplier's place once the operator marked the question, so a taken
    question off the row's face showed its chance and edge and no
    multiplier. The renderer draws the multiplier whatever was taken, and the
    scan names the released form."""
    assert audit.row_face_faults() == []
    js = (ROOT / "gridiron" / "web" / "app.js").read_text(encoding="utf-8")
    now = "el('span', 'pay', q.pays_words || ABSENT)"
    assert now in js
    released = js.replace(
        now, "el('span', 'pay', q.taken ? (labels.taken || '') : (q.pays_words || ABSENT))")
    assert any("only where the question was not taken" in f
               for f in audit.row_face_faults(released))


def test_a_taken_priced_tile_draws_its_multiplier_in_chromium(page, monkeypatch):
    """The same in a real Chromium: every question still to come on the
    slate read as priced and taken (in the test server's process only, so
    the shared world is not written), the first row still to come opened by
    its head -- each taken tile's payout slot says its multiplier, never
    "taken"."""
    real_build = board.build

    def taken_and_priced(*args, **kwargs):
        out = real_build(*args, **kwargs)
        for g in out["games"]:
            for q in g["questions"]:
                if q.get("state") == "upcoming":
                    q.update(taken=True, priced=True, pays_words="1.94x",
                             edge_words="+1.0¢", prob_words="55%")
        return out

    monkeypatch.setattr(board, "build", taken_and_priced)
    from tests.conftest import wait_for_the_redraw_it_starts

    page.set_viewport_size({"width": 1440, "height": 900})
    with wait_for_the_redraw_it_starts(page):
        page.evaluate("location.hash = '#/games'")
    row = page.locator("#games-rows .game[data-state='upcoming']").first
    game = row.get_attribute("data-game")
    row.locator(".game-head").click()
    page.wait_for_function(
        "(g) => document.querySelector(`#games-rows .game[data-game=\"${g}\"]`)"
        ".classList.contains('open')", arg=game, timeout=10000)
    pays = page.evaluate(
        "(g) => [...document.querySelectorAll(`#games-rows .game[data-game=\"${g}\"] "
        ".q.q-taken[data-state='upcoming'] .pay`)].map(e => e.textContent)", game)
    assert pays and all(p == "1.94x" for p in pays), pays
    assert not page.page_errors, page.page_errors


def test_every_recommendation_line_says_what_its_side_pays(tmp_path):
    """B.3 with reading (a)'s "the Today payload's ... recommendation lines":
    each line says what the side it buys pays, beside its price -- "the
    venue is at 52¢ (pays 1.94x)" -- and the check names a line without it.
    The line stated the chance, the price and the edge, and no multiplier."""
    conn, ids = _world(tmp_path / "w.db", TWO)
    payload = _week(conn)
    words = {x["prediction_id"]: x["words"] for x in payload["recommendations"]["lines"]}
    assert "the venue is at 52¢ (pays 1.94x), and it is worth" in words[ids[("g1", "spread")]]
    assert "the venue is at 50¢ (pays 2.00x), and it is worth" in words[
        ids[("g2", "moneyline")]]
    assert audit.pick_rank_faults(conn, payload) == []
    for x in payload["recommendations"]["lines"]:
        x["words"] = re.sub(r" \(pays [0-9.]+x\)", "", x["words"])
    assert any("without what the side it buys pays" in f
               for f in audit.pick_rank_faults(conn, payload))
    conn.close()


def test_the_recommendation_lines_are_ranked_by_edge(tmp_path):
    """B.1: the picks among the recommendation lines by their edge after
    fees, best first -- the +15 before the +10, though the +10 was written
    first -- and the check names the engine's order. The lines followed the
    engine's rows, the record's ids."""
    conn, ids = _world(tmp_path / "w.db", [TWO[1], TWO[0]],
                       gated=[("spread", "statistical"), ("moneyline", "statistical")])
    spread, money = ids[("g1", "spread")], ids[("g2", "moneyline")]
    assert money < spread
    payload = _week(conn)
    assert [x["prediction_id"] for x in payload["recommendations"]["lines"]] == [spread, money]
    assert audit.pick_rank_faults(conn, payload) == []
    payload["recommendations"]["lines"].reverse()
    assert any("recommendations.lines are in the order" in f
               for f in audit.pick_rank_faults(conn, payload))
    conn.close()


def test_the_gates_words_say_whose_count_it_is(tmp_path, monkeypatch):
    """B.5's gate is one forecaster's count and, for UFC, one card's: the
    words beside a recommendation short of it name the Record page's curve
    whose n it is -- "(point spread at the venue's line, statistical)"; a UFC
    bout's, its card. "its market has 0 of the 100" said a card's count as
    the market's and never said whose."""
    from gridiron import picks

    conn, ids = _world(tmp_path / "w.db", TWO)
    payload = _week(conn)
    spread = ids[("g1", "spread")]
    said = _card(payload, spread)["not_a_pick_words"]
    assert said.endswith("it needs first (point spread at the venue's line, statistical).")
    assert audit.pick_rank_faults(conn, payload) == []
    bare = said.replace(" (point spread at the venue's line, statistical)", "")
    _card(payload, spread)["not_a_pick_words"] = bare
    assert any("without naming whose it is" in f for f in audit.pick_rank_faults(conn, payload))
    conn.close()
    # A UFC BOUT: the card's count, named by its card.
    monkeypatch.setattr(picks, "market_gate", lambda conn, **kw: {
        "game_market": True, "market": "moneyline", "predictor": "llm",
        "event_tier": "fight_night", "n": 0, "gate": 100, "passes": False})
    got = picks.judge(None, {"side": "yes", "edge_points": 6.0, "market": "moneyline",
                             "game_id": "bout"}, sport="ufc", predictor="llm")
    assert got["pick"] is False and got["words"] == (
        "Not a pick: its market has 0 of the 100 settled comparisons with the venue's "
        "price it needs first (moneyline at the venue's line, Fight Night, reasoning "
        "pass).")


def test_no_drawn_sentence_counts_a_question_or_a_contract_as_a_pick():
    """B.2: "Below that it is shown as a number, never as a pick." The sign-in
    screen counted every open question as a pick ("46 picks tonight") and
    the fee line beneath the day strip said "A pick with no edge costs that
    much" -- a thing B says cannot be. Each says what it counts now, and the
    checks name the released words."""
    assert language.login_glance_line("MLB", 45, 25, 46, "day") == "MLB 45-25 · 46 questions tonight"
    assert language.login_glance_line("NFL", 0, 0, 1, "week") == "NFL 1 question this week"
    assert audit.login_glance_faults(audit.LOGIN_FIXTURE_PICKS_COUNTED)
    assert not audit.login_glance_faults(audit.LOGIN_FIXTURE_GOOD)
    fee = language.fee_arithmetic_line(0.52, 2.0)
    assert "pick" not in fee and fee.endswith(
        "A contract with no edge costs that much before anything is right or wrong.")


def test_the_check_names_a_fee_line_calling_a_contract_a_pick(tmp_path):
    conn, _ids = _world(tmp_path / "w.db", TWO)
    payload = _week(conn)
    assert audit.pick_rank_faults(conn, payload) == []
    payload["today"]["fee_line"] = payload["today"]["fee_line"].replace(
        "A contract with no edge", "A pick with no edge")
    assert any("today.fee_line" in f for f in audit.pick_rank_faults(conn, payload))
    conn.close()
