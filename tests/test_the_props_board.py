"""The Props board (operator ruling C, 2026-10-05; built 2026-10-06).

"1. Never present a venue ladder rung as a pick'em pick. Per player and stat:
the model's projection and its chance at the market's main line (the rung
nearest 50c), labelled 'about the app's line, check the app'. The full ladder
moves to its own 'Kalshi ladder' view. 2. Browse plus picks: every listed
player shows projection, chance at the main line, and the break-evens; only
legs clearing B.2 get a pick badge. 3. Default break-even when no entry is
typed: 2-pick power and 3-pick power, both shown on each leg. The operator
types each multiplier once (no payout hard-coded as fact); until typed, the
page asks for it and shows no break-even." And B.2: "A leg is called a pick
only if its edge after fees is 3 percentage points or more."

Each test builds a world of one game in 2099 and the prop questions it needs,
and hands the venue's ladder in where it needs one -- no prop ladder is read
on the record (measured 2026-10-06), so `board._venue_prop_ladders` answers
none, and these worlds stand in for the day one is.
"""
from __future__ import annotations

import json

import pytest

from gridiron import audit, board, config, settings, views
from gridiron.model import counts

GAME = "gProps"


def _world(conn, rows, *, typed=None):
    """One NFL game in 2099 and its prop questions: rows of (subject, prop
    type, line asked, model prob, side, extra factors). `typed` is the
    payouts typed through the settings door, by legs."""
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES (?, 'nfl', 2026, 5, 'REG',"
        " 'DET', 'GB', '2099-10-12T17:00:00Z', 'scheduled', '2026-10-12')", (GAME,))
    for code, full, short, city in (("DET", "Detroit Lions", "Lions", "Detroit"),
                                    ("GB", "Green Bay Packers", "Packers", "Green Bay")):
        conn.execute(
            "INSERT INTO teams (sport, tricode, display_name, short_name, location,"
            " source_url, fetched_utc) VALUES ('nfl', ?, ?, ?, ?, 'test',"
            " '2026-09-01T00:00:00Z')", (code, full, short, city))
    ids = []
    for subject, prop, line, prob, side, extra in rows:
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type, prop_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning) VALUES"
            " ('2026-10-07T15:00:00Z', 'nfl', ?, 'prop', ?, ?, ?, ?, ?, 'statistical',"
            " 'early', 'fs2', ?, 'test')",
            (GAME, prop, subject, line, prob, side,
             json.dumps(dict({"coverage": 1.0}, **(extra or {})))))
        ids.append(conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0])
    conn.commit()
    names = dict(config.PICKEM_POWER_ENTRIES)
    for legs, value in (typed or {}).items():
        settings.set_value(conn, names[legs], value)
    return ids


def _ladder(monkeypatch, by_subject):
    """Hand the venue's ladder in: {subject: [(line, price), ...]}."""
    def handed_in(conn, sport, cards):
        out = {}
        for c in cards:
            if c["subject"] in by_subject:
                out[board.ladder_key(c)] = [{"line": float(l), "price": p, "ticker": f"t{l}"}
                                            for l, p in by_subject[c["subject"]]]
        return out, None
    monkeypatch.setattr(board, "_venue_prop_ladders", handed_in)


def _props(conn):
    payload = views.week(conn, "nfl", 2026, 5)
    return payload, payload["board"]["props"]


def _tile(props, pid):
    return next(t for t in props["tiles"] if t["prediction_id"] == pid)


def _check(conn, payload):
    audit.check_the_props_board_calls_no_rung_a_pick(conn, payload)


# --- C.3: the payouts the operator types --------------------------------------

def test_a_payout_is_typed_through_the_settings_door_and_kept_with_its_day(conn):
    assert settings.typed(conn, "pickem_two_pick_power") is None
    for bad in ("1", "0.5", "abc", "101", ""):
        with pytest.raises(settings.SettingRefused):
            settings.set_value(conn, "pickem_two_pick_power", bad)
    settings.set_value(conn, "pickem_two_pick_power", "3x")
    got = settings.typed(conn, "pickem_two_pick_power")
    assert got["value"] == "3" and got["typed_utc"].endswith("Z")
    settings.set_value(conn, "pickem_two_pick_power", "3.2")
    assert settings.typed(conn, "pickem_two_pick_power")["value"] == "3.2"
    # APPEND-ONLY: the earlier value is kept, the change dated.
    rows = conn.execute("SELECT value, previous FROM settings WHERE name ="
                        " 'pickem_two_pick_power' ORDER BY id").fetchall()
    assert [(r["value"], r["previous"]) for r in rows] == [("3", ""), ("3.2", "3")]


def test_until_typed_no_breakeven_is_shown_and_the_page_asks(conn):
    pid, = _world(conn, [("Jayden Reed receiving_yards", "receiving_yards", 50.5, 0.71,
                          "over", {})])
    payload, props = _props(conn)
    tile = _tile(props, pid)
    assert [e["breakeven"] for e in tile["entries"]] == [None, None]
    assert all(e["breakeven_words"].endswith("payout not typed") for e in tile["entries"])
    assert tile["multiple_source"] == "untyped" and tile["pick"] is False
    assert props["payouts"]["typed"] is False
    assert props["payouts"]["ask_words"].startswith(
        "Type what a 2-pick power entry and a 3-pick power entry pay in your app.")
    _check(conn, payload)
    # ONE TYPED: its break-even shows with the day it was typed, and the page
    # still asks for the other.
    settings.set_value(conn, "pickem_two_pick_power", "3")
    payload, props = _props(conn)
    two, three = _tile(props, pid)["entries"]
    assert two["breakeven_words"] == "2-pick power 57.7%" and abs(two["breakeven"] - 3 ** -0.5) < 1e-6
    assert three["breakeven"] is None
    assert props["payouts"]["entries"][0]["typed_words"].startswith("typed ")
    assert props["payouts"]["ask_words"].startswith("Type what a 3-pick power entry pays")
    _check(conn, payload)


# --- C.1: the main line, and the chance the model states at it ----------------

def test_the_main_line_is_the_rung_nearest_an_even_chance(conn, monkeypatch):
    pid, = _world(conn, [("Jared Goff passing_yards", "passing_yards", 250.5, 0.64, "over", {})],
                  typed={2: "3", 3: "6"})
    _ladder(monkeypatch, {"Jared Goff passing_yards": [(230.5, 0.91), (250.5, 0.47),
                                                       (270.5, 0.27)]})
    payload, props = _props(conn)
    tile = _tile(props, pid)
    assert tile["main_line"] == 250.5 and tile["main_price"] == 0.47
    assert tile["main_note_words"] == "about the app's line, check the app"
    assert tile["main_words"] == "Jared Goff over 250.5 passing yards"
    assert tile["main_chance"] == pytest.approx(0.64) and tile["main_chance_words"] == "64%"
    _check(conn, payload)
    # A TIE GOES TO THE LOWER LINE
    assert board._main_rung([{"line": 3.5, "price": 0.45}, {"line": 2.5, "price": 0.55}])["line"] == 2.5


def test_a_counting_stat_reads_its_stored_rate_at_the_main_line(conn, monkeypatch):
    pid, = _world(conn, [("Amon-Ra St. Brown receptions", "receptions", 6.5, 0.62, "under",
                          {"expected_count": 5.3, "model_form": "negative_binomial"})],
                  typed={2: "3", 3: "6"})
    _ladder(monkeypatch, {"Amon-Ra St. Brown receptions": [(3.5, 0.8), (4.5, 0.55),
                                                           (5.5, 0.38)]})
    payload, props = _props(conn)
    tile = _tile(props, pid)
    assert tile["projection"] == 5.3 and tile["projection_words"] == "about 5.3 receptions"
    form, dispersion = counts.form_for("receptions")
    over = counts.p_over(5.3, 4.5, form=form, dispersion=dispersion)
    assert tile["main_line"] == 4.5
    assert tile["main_side"] == ("over" if over >= 0.5 else "under")
    assert tile["main_chance"] == pytest.approx(max(over, 1 - over), abs=1e-6)
    assert "read at this line as a count" in tile["tips"]["leg_chance"]
    _check(conn, payload)


def test_a_yardage_stat_off_its_own_line_has_no_chance_and_no_pick(conn, monkeypatch):
    pid, = _world(conn, [("Jared Goff passing_yards", "passing_yards", 240.5, 0.80, "over", {})],
                  typed={2: "3", 3: "6"})
    _ladder(monkeypatch, {"Jared Goff passing_yards": [(250.5, 0.5), (270.5, 0.3)]})
    payload, props = _props(conn)
    tile = _tile(props, pid)
    assert tile["main_line"] == 250.5 and tile["main_chance"] is None
    assert tile["main_chance_words"] == "the model has no chance at this line yet"
    assert tile["projection"] is None and tile["projection_words"] == "none for passing yards"
    assert all(e["edge"] is None and not e["clears"] for e in tile["entries"])
    assert tile["pick"] is False and tile["signal"] == "none"
    assert props["nothing_words"] == "Nothing worth taking today"
    _check(conn, payload)


# --- C.2 and B.2: a pick only at three points ----------------------------------

def test_a_leg_is_a_pick_only_at_three_points_of_edge(conn, monkeypatch):
    rows = [("A Two passing_yards", "passing_yards", 200.5, 0.60, "over", {}),   # +2.3 / +5.0
            ("B Three passing_yards", "passing_yards", 210.5, 0.61, "over", {}),  # +3.3 / +6.0
            ("C Under rushing_yards", "rushing_yards", 60.5, 0.52, "under", {})]  # -5.7 / -3.0
    a, b, c = _world(conn, rows, typed={2: "3", 3: "6"})
    _ladder(monkeypatch, {s: [(line, 0.5)] for s, _p, line, *_ in rows})
    payload, props = _props(conn)
    ta, tb, tc = (_tile(props, x) for x in (a, b, c))
    assert ta["pick"] is True and ta["pick_words"] == "Pick · 3-pick power"
    assert [e["clears"] for e in ta["entries"]] == [False, True]
    assert tb["pick"] is True and tb["pick_words"] == "Pick · 2-pick and 3-pick power"
    assert tb["signal"] == "clears" and tb["multiple_source"] == "typed"
    assert [e["edge_words"] for e in tb["entries"]] == ["edge +3.3", "edge +6.0"]
    assert tc["pick"] is False and tc["signal"] == "none"
    assert props["nothing_words"] is None
    # RANKED BY EDGE, NEVER BY CHANCE: B's best edge beats A's.
    order = [t["prediction_id"] for t in props["tiles"]]
    assert order.index(b) < order.index(a) < order.index(c)
    _check(conn, payload)
    assert audit.board_signal_faults(payload) == []


def test_exactly_three_points_is_a_pick_and_a_hair_under_is_not():
    assert board.clears_the_pick_bar(0.03)
    assert board.clears_the_pick_bar(0.0300004)
    assert not board.clears_the_pick_bar(0.029999)
    assert not board.clears_the_pick_bar(None)


def test_the_bar_reads_the_edge_as_worked_out_not_its_six_places(conn, monkeypatch):
    """THE PROVER OF RULING C (2026-10-06). B.2: "3 percentage points or
    more". As built the edge was rounded to six places before the bar was
    read, so a leg at 2.99996 points was called a pick, and the gate, reading
    the page's rounded chance, named a leg at 2.99994 that the builder had
    rightly left a number. Float noise is all the bar forgives."""
    be = 3 ** -0.5
    rows = [("A Hair passing_yards", "passing_yards", 200.5, be + 0.0299996, "over", {}),
            ("B Under rushing_yards", "rushing_yards", 60.5, be + 0.0299994, "over", {}),
            ("C Three receiving_yards", "receiving_yards", 50.5, be + 0.03, "over", {})]
    a, b, c = _world(conn, rows, typed={2: "3", 3: "4"})
    _ladder(monkeypatch, {s: [(line, 0.5)] for s, _p, line, *_ in rows})
    payload, props = _props(conn)
    ta, tb, tc = (_tile(props, x) for x in (a, b, c))
    assert ta["pick"] is False and ta["entries"][0]["clears"] is False, ta["entries"][0]
    assert tb["pick"] is False and tb["entries"][0]["clears"] is False
    assert tc["pick"] is True and tc["pick_words"] == "Pick · 2-pick power"
    assert not board.clears_the_pick_bar(0.0299996)
    assert board.clears_the_pick_bar(0.03 - 1e-12)
    _check(conn, payload)
    # THE 2.99996-POINT LEG CALLED A PICK IS NAMED, on the forecast's chance.
    planted = json.loads(json.dumps(payload))
    tile = _tile(planted["board"]["props"], a)
    tile.update(pick=True, pick_words="Pick · 2-pick power", signal="clears")
    tile["entries"][0]["clears"] = True
    assert any("clears the bar of 3 points" in f for f in _faults(conn, planted))


def test_the_entry_rail_names_a_leg_by_its_main_lines_contract(conn, monkeypatch):
    """THE PROVER OF RULING C (2026-10-06). As built the entry rail drew a
    taken leg under the words of the question the record asked at its own
    line beside its chance at the venue's main line: "over 6.5 receptions"
    beside a chance at 4.5. A leg is named by its main line's contract, or,
    with no main line, by its player and stat and no line."""
    st_brown, goff = _world(conn, [
        ("Amon-Ra St. Brown receptions", "receptions", 6.5, 0.62, "under",
         {"expected_count": 5.3, "model_form": "negative_binomial"}),
        ("Jared Goff passing_yards", "passing_yards", 250.5, 0.64, "over", {})],
        typed={2: "3", 3: "6"})
    _ladder(monkeypatch, {"Amon-Ra St. Brown receptions": [(3.5, 0.8), (4.5, 0.55), (5.5, 0.38)]})
    payload, props = _props(conn)
    leg, unlisted = _tile(props, st_brown), _tile(props, goff)
    assert leg["main_line"] == 4.5 and leg["leg_words"] == leg["main_words"]
    assert "4.5" in leg["leg_words"] and "6.5" not in leg["leg_words"]
    assert leg["leg_words"] != leg["question"]
    assert unlisted["main_line"] is None and unlisted["leg_words"] == "Jared Goff · passing yards"
    _check(conn, payload)
    # THE QUESTION'S OWN WORDS PUT BACK OFF THE TILE: named.
    planted = json.loads(json.dumps(payload))
    _tile(planted["board"]["props"], st_brown)["leg_words"] = leg["question"]
    assert any("names its leg" in f for f in _faults(conn, planted))
    planted = json.loads(json.dumps(payload))
    _tile(planted["board"]["props"], goff)["leg_words"] = unlisted["question"]
    assert any("never by the line the record asked" in f for f in _faults(conn, planted))
    # AND THE RAIL'S ROW PUT BACK TO THE QUESTION'S WORDS: the gate names it.
    from pathlib import Path
    js = (Path(audit.__file__).parent / "web" / "app.js").read_text(encoding="utf-8")
    assert audit.entry_rail_leg_faults(js) == []
    put_back = js.replace("el('span', 'entry-leg-line', l.leg_words || '')",
                          "el('span', 'entry-leg-line', l.line_words || '')")
    assert put_back != js
    assert any("`line_words`" in f for f in audit.entry_rail_leg_faults(put_back))
    with pytest.raises(audit.LawViolation):
        audit.check_the_props_board_calls_no_rung_a_pick(conn, payload, app_js=put_back)


def test_a_payout_that_is_not_a_number_is_refused(conn):
    """THE PROVER OF RULING C (2026-10-06): "nan" is a float to Python and
    passed both bounds, so it was stored as the typed payout."""
    for bad in ("nan", "NaN", "inf", "-inf"):
        with pytest.raises(settings.SettingRefused):
            settings.set_value(conn, "pickem_two_pick_power", bad)
    assert settings.typed(conn, "pickem_two_pick_power") is None


def test_the_breakeven_tip_says_how_often_every_leg_hits():
    """Plain words (the prover of ruling C, 2026-10-06): the tip said "2 legs
    that likely all hit together one time in 3"."""
    from gridiron import language

    two = language.pickem_breakeven_tip(2, 3.0, 3 ** -0.5, "2026-10-06T12:00:00Z")
    three = language.pickem_breakeven_tip(3, 6.0, 6 ** (-1 / 3), "2026-10-06T12:00:00Z")
    assert "at that chance both legs hit together one time in 3" in two
    assert "at that chance all 3 legs hit together one time in 6" in three
    assert "likely" not in two + three
    assert audit.advice_word_faults(two + three) == []


def test_a_90_percent_leg_at_91_cents_is_not_a_pick(conn, monkeypatch):
    """The ruling's planting, as a test: the model's question sits at the rung
    the venue prices at 91c and says 90%; the main line is the rung nearest an
    even chance, where a yardage stat has no chance, so nothing is a pick --
    and the 91c rung, in the Kalshi ladder view, carries no pick either."""
    pid, = _world(conn, [("Jared Goff passing_yards", "passing_yards", 200.5, 0.90, "over", {})],
                  typed={2: "3", 3: "6"})
    _ladder(monkeypatch, {"Jared Goff passing_yards": [(200.5, 0.91), (250.5, 0.52),
                                                       (290.5, 0.2)]})
    payload, props = _props(conn)
    tile = _tile(props, pid)
    assert tile["main_line"] == 250.5 and tile["main_chance"] is None and tile["pick"] is False
    rung = next(r for r in props["ladder"]["rows"][0]["rungs"] if r["line"] == 200.5)
    assert set(rung) == {"line", "price", "contract_words", "price_words", "main"}
    assert rung["main"] is False and rung["price_words"] == "91¢"
    assert props["nothing_words"] == "Nothing worth taking today"
    _check(conn, payload)


def test_the_kalshi_ladder_view_names_every_rung_under_its_own_contract(conn, monkeypatch):
    pid, = _world(conn, [("Jared Goff passing_yards", "passing_yards", 250.5, 0.64, "over", {})])
    _ladder(monkeypatch, {"Jared Goff passing_yards": [(270.5, 0.27), (230.5, 0.74),
                                                       (250.5, 0.52)]})
    payload, props = _props(conn)
    row, = props["ladder"]["rows"]
    assert row["prediction_id"] == pid and row["player"] == "Jared Goff"
    assert [r["contract_words"] for r in row["rungs"]] == [
        "Jared Goff over 230.5 passing yards", "Jared Goff over 250.5 passing yards",
        "Jared Goff over 270.5 passing yards"]
    assert [r["main"] for r in row["rungs"]] == [False, True, False]
    for key in audit.LADDER_PICK_FIELDS:
        assert key not in row and all(key not in r for r in row["rungs"]), key
    assert props["ladder"]["empty_words"] is None
    chip = next(c for c in props["chips"] if c["key"] == "ladder")
    assert chip["label"] == "Kalshi ladder" and chip["n"] == 1
    _check(conn, payload)


def test_no_ladder_is_read_on_any_slate_and_the_page_says_so(conn):
    """The one place a venue ladder is read answers none: no prop ladder is
    read (the record's measurement, 2026-10-06), and the view says why."""
    _world(conn, [("Jared Goff passing_yards", "passing_yards", 250.5, 0.64, "over", {})])
    ladders, why = board._venue_prop_ladders(conn, "nfl", [{"prediction_id": 1}])
    assert ladders == {} and "not read" in why
    payload, props = _props(conn)
    assert props["ladder"]["rows"] == [] and "not read" in props["ladder"]["empty_words"]
    assert props["ladders_words"] == why


def test_a_live_or_settled_tile_carries_no_leg(conn, monkeypatch):
    pid, = _world(conn, [("Jared Goff passing_yards", "passing_yards", 250.5, 0.64, "over", {})],
                  typed={2: "3", 3: "6"})
    _ladder(monkeypatch, {"Jared Goff passing_yards": [(250.5, 0.5)]})
    conn.execute("UPDATE games SET status = 'in', home_score = 7, away_score = 3,"
                 " live_period = '2nd Quarter', live_clock = '3:10' WHERE id = ?", (GAME,))
    conn.commit()
    payload, props = _props(conn)
    tile = _tile(props, pid)
    for key in audit.LEG_FIELDS:
        assert tile.get(key) in (None, False, [], ""), key
    assert props["nothing_words"] is None
    _check(conn, payload)
    assert audit.live_card_faults(payload) == [] and audit.live_tab_faults(payload) == []


# --- the check: every form the ruling names ----------------------------------

def _good(conn, monkeypatch):
    rows = [("Jared Goff passing_yards", "passing_yards", 250.5, 0.64, "over", {}),
            ("Jayden Reed receiving_yards", "receiving_yards", 50.5, 0.55, "over", {})]
    ids = _world(conn, rows, typed={2: "3", 3: "6"})
    _ladder(monkeypatch, {"Jared Goff passing_yards": [(230.5, 0.91), (250.5, 0.52),
                                                       (270.5, 0.27)],
                          "Jayden Reed receiving_yards": [(50.5, 0.5)]})
    payload, _props_ = _props(conn)
    return ids, payload


def _faults(conn, payload):
    from gridiron import audit as a
    tiles = payload["board"]["props"]["tiles"]
    forecasts = {r[0]: {"sport": r[1], "line_asked": r[2], "model_prob": r[3],
                        "model_side": r[4], "prop_type": r[5], "predictor": r[6],
                        "factors_json": r[7]}
                 for r in conn.execute(
                     "SELECT id, sport, line_asked, model_prob, model_side, prop_type,"
                     " predictor, factors_json FROM predictions")}
    assert tiles
    return a.props_board_faults(payload, typed=a._typed_pickem_payouts(conn),
                                forecasts=forecasts, conn=conn)


def test_the_check_names_a_ladder_rung_presented_as_a_pick(conn, monkeypatch):
    (goff, _reed), payload = _good(conn, monkeypatch)
    assert _faults(conn, payload) == []
    planted = json.loads(json.dumps(payload))
    rung = planted["board"]["props"]["ladder"]["rows"][0]["rungs"][0]
    rung.update(pick=True, pick_words="Pick · 2-pick power", edge=0.32)
    assert any("venue ladder rung presented as a pick'em pick" in f
               for f in _faults(conn, planted))
    planted = json.loads(json.dumps(payload))
    tile = _tile(planted["board"]["props"], goff)
    tile.update(main_line=230.5, main_chance=0.9, main_words="Jared Goff over 230.5 passing yards")
    assert any("where the main line" in f and "230.5" in f for f in _faults(conn, planted))
    planted = json.loads(json.dumps(payload))
    _tile(planted["board"]["props"], goff)["question"] = "Jared Goff over 230.5 passing yards"
    assert any("not the question the record asked" in f for f in _faults(conn, planted))


def test_the_check_names_a_breakeven_from_an_untyped_multiplier(conn, monkeypatch):
    (goff, _reed), payload = _good(conn, monkeypatch)
    planted = json.loads(json.dumps(payload))
    entry = _tile(planted["board"]["props"], goff)["entries"][0]
    entry.update(multiple=4.0, breakeven=0.5, breakeven_words="2-pick power 50.0%")
    assert any("typed 3x" in f for f in _faults(conn, planted))
    # THE DECLARED 3X ON A RECORD WHERE NOTHING IS TYPED
    typed = {2: None, 3: None}
    faults = audit.props_board_faults(payload, typed=typed)
    assert any("from a multiplier nobody typed" in f for f in faults)
    assert any("does not ask" in f for f in faults)


def test_the_check_names_a_slate_with_nothing_clearing_drawn_with_picks(conn, monkeypatch):
    (_goff, reed), payload = _good(conn, monkeypatch)
    planted = json.loads(json.dumps(payload))
    tile = _tile(planted["board"]["props"], reed)
    assert tile["pick"] is False
    tile.update(pick=True, pick_words="Pick · 2-pick power", signal="clears")
    assert any("with no edge of 3 points" in f for f in _faults(conn, planted))
    # AND THE PAGE SAYS NOTHING CLEARS WHEN NOTHING DOES
    planted = json.loads(json.dumps(payload))
    for t in planted["board"]["props"]["tiles"]:
        t["main_line"] = t["main_chance"] = None
        t["main_note_words"] = None
        for e in t["entries"]:
            e.update(edge=None, edge_words=None, clears=False)
        t.update(pick=False, pick_words=None, signal="none")
    planted["board"]["props"]["ladder"]["rows"] = []
    planted["board"]["props"]["nothing_words"] = None
    assert any("Nothing worth taking today" in f for f in _faults(conn, planted))


def test_the_check_holds_the_bar_as_ruled(conn, monkeypatch):
    (_goff, _reed), payload = _good(conn, monkeypatch)
    monkeypatch.setattr(config, "PICK_MIN_EDGE", 0.0)
    assert any("not the three points ruled" in f for f in _faults(conn, payload))


def test_the_gate_makes_the_call():
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "tools" / "verify.py").read_text(
        encoding="utf-8")
    called = {n.func.attr for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "check_the_props_board_calls_no_rung_a_pick" in called


# --- the page ------------------------------------------------------------------

def test_the_props_page_asks_for_each_payout_and_draws_its_breakeven_once_typed(page, monkeypatch):
    """C.3 in a real Chromium: the page asks; a payout typed into its field is
    posted through the settings door, and the slate is asked again and draws
    the break-even. In the test server's process only: the door records the
    call and the reader answers it, so the shared world is not written."""
    from gridiron import views as _views

    typed: dict = {}
    real = board.typed_payouts

    def reader(conn):
        out = real(conn)
        for p in out:
            if p["name"] in typed:
                p["multiple"], p["typed_utc"] = float(typed[p["name"]]), "2026-10-06T12:00:00Z"
        return out

    def door(conn, *, name, raw):
        typed[name] = raw
        return {"name": name, "value": raw, "changed": True, "was": "", "line": "", "recent": []}

    monkeypatch.setattr(board, "typed_payouts", reader)
    monkeypatch.setattr(_views, "change_setting", door)
    from tests.conftest import wait_for_the_redraw_it_starts

    page.set_viewport_size({"width": 1440, "height": 900})
    with wait_for_the_redraw_it_starts(page, "props-tiles"):
        page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#props-payouts:not([hidden]) #payout-2", timeout=15000)
    assert "Type what a 2-pick power entry and a 3-pick power entry pay" in \
        page.text_content("#props-payouts")
    assert page.text_content("#props-nothing") == "Nothing worth taking today"
    drawn = page.evaluate("[...document.querySelectorAll('#props-tiles .leg-be')]"
                          ".map(e => e.textContent)")
    assert drawn and all(d.endswith("payout not typed") for d in drawn), drawn
    page.fill("#payout-2", "3")
    with wait_for_the_redraw_it_starts(page, "props-tiles"):
        page.click("#props-payouts .payout-save >> nth=0")
    assert typed == {"pickem_two_pick_power": "3"}
    drawn = page.evaluate("[...document.querySelectorAll('#props-tiles .leg-be')]"
                          ".map(e => e.textContent)")
    assert "2-pick power 57.7%" in drawn and "3-pick power: payout not typed" in drawn, drawn
    assert page.input_value("#payout-2") == "3"
    assert "typed Tuesday 6 October" in page.text_content("#props-payouts")
    assert not page.page_errors, page.page_errors


def test_the_entry_rail_draws_a_taken_leg_under_its_main_lines_words(page, monkeypatch):
    """THE PROVER OF RULING C (2026-10-06), in a real Chromium: a taken leg
    whose main line is not the line its question was asked at is drawn in the
    entry rail under the main line's words -- the ones its tile draws beside
    the chance -- and never under the question's own. In the test server's
    process only: the venue's ladder is handed in with its main rung ten
    above each question's own line, and the first leg still to start is read
    as taken, so the shared world is not written."""
    def off_the_own_line(conn, sport, cards):
        out = {}
        for c in cards:
            if c.get("line_asked") is None:
                continue
            line = float(c["line_asked"])
            out[board.ladder_key(c)] = [{"line": line, "price": 0.71, "ticker": "own"},
                                        {"line": line + 10.0, "price": 0.5, "ticker": "main"},
                                        {"line": line + 20.0, "price": 0.3, "ticker": "hi"}]
        return out, None

    real_build = board.build

    def one_taken(*args, **kwargs):
        out = real_build(*args, **kwargs)
        for tile in out["props"]["tiles"]:
            if tile["state"] == "upcoming":
                tile["taken"] = True
                break
        return out

    monkeypatch.setattr(board, "_venue_prop_ladders", off_the_own_line)
    monkeypatch.setattr(board, "build", one_taken)
    from tests.conftest import wait_for_the_redraw_it_starts

    page.set_viewport_size({"width": 1440, "height": 900})
    with wait_for_the_redraw_it_starts(page, "props-tiles"):
        page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#entry-legs .entry-leg", timeout=15000)
    got = page.evaluate("""() => {
        const tile = document.querySelector('#props-tiles .prop.q-taken');
        const rows = tile ? [...tile.querySelectorAll('.leg-row')] : [];
        return { rail: [...document.querySelectorAll('#entry-legs .entry-leg-line')]
                         .map(e => e.textContent),
                 main: rows.length > 1 ? rows[1].querySelector('.leg-words').textContent : null,
                 own: tile ? tile.querySelector('.prop-own').textContent : null }; }""")
    assert got["main"] and got["own"], got
    assert got["rail"] == [got["main"]], got
    assert not got["own"].endswith(got["rail"][0]) and got["rail"][0] not in got["own"], got
    assert not page.page_errors, page.page_errors


def test_the_entry_rails_filled_payout_follows_the_legs_taken(page, monkeypatch):
    """THE PROVER OF RULING C (2026-10-06), in a real Chromium: the payout the
    page fills into the entry rail is the one typed for the number of legs
    taken, and follows it. As built it was filled only into an empty field,
    so the 2-pick's 3x stayed when a third leg was taken and the verdict read
    a 3-leg entry at it. One the operator types in the field stays his. In
    the test server's process only: the payouts are read as typed (3x and
    6x) and the first legs still to start as taken, so the shared world is
    not written."""
    taken = {"n": 2}
    real_reader, real_build = board.typed_payouts, board.build

    def reader(conn):
        out = real_reader(conn)
        for p in out:
            p["multiple"] = 3.0 if p["legs"] == 2 else 6.0
            p["typed_utc"] = "2026-10-06T12:00:00Z"
        return out

    def some_taken(*args, **kwargs):
        out = real_build(*args, **kwargs)
        left = taken["n"]
        for tile in out["props"]["tiles"]:
            if tile["state"] == "upcoming":
                tile["taken"] = left > 0
                left -= 1
        return out

    def at_each_own_line(conn, sport, cards):
        return ({board.ladder_key(c): [{"line": float(c["line_asked"]), "price": 0.5,
                                        "ticker": "main"}]
                 for c in cards if c.get("line_asked") is not None}, None)

    monkeypatch.setattr(board, "typed_payouts", reader)
    monkeypatch.setattr(board, "build", some_taken)
    monkeypatch.setattr(board, "_venue_prop_ladders", at_each_own_line)
    from tests.conftest import wait_for_the_redraw_it_starts

    def redraw(n):
        taken["n"] = n
        with wait_for_the_redraw_it_starts(page, "props-tiles"):
            page.click("#props-chips .chip-btn[data-key=''] >> nth=0")
        page.wait_for_function(
            "(n) => document.querySelectorAll('#entry-legs .entry-leg').length === n",
            arg=n, timeout=15000)
        return page.input_value("#entry-pays")

    page.set_viewport_size({"width": 1440, "height": 900})
    with wait_for_the_redraw_it_starts(page, "props-tiles"):
        page.evaluate("location.hash = '#/props'")
    assert page.evaluate("document.querySelectorAll('#props-tiles .prop').length") >= 3
    assert redraw(2) == "3"
    # A TAKEN PICK KEEPS ITS OUTLINE (the prover, 2026-10-06): `.q-taken`
    # took it off a prop tile as built.
    outlines = page.evaluate(
        "[...document.querySelectorAll('#props-tiles .prop.q-taken.sig-clears')]"
        ".map(t => getComputedStyle(t).boxShadow)")
    assert outlines and all("1.5px" in s for s in outlines), outlines
    assert redraw(3) == "6", "the 2-pick's payout stayed in the field for a 3-leg entry"
    assert redraw(1) == ""
    page.fill("#entry-pays", "5")
    assert redraw(2) == "5", "a payout the operator typed in the field was replaced"
    assert not page.page_errors, page.page_errors
