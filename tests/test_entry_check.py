"""Check an entry, step 1: the arithmetic, no model (GRIDIRON_ENTRY_CHECK; the
brief of 2026-09-30, docs/briefs/2026-09-30-entry-check.md, with the
operator's amendments of 2026-10-05, ruling D; built 2026-10-07).

The brief, step 1: "'Check an entry' on the Props page: app, entry type, legs
(player, stat, line, over/under, original line if discounted), payout (power
multiplier or flex table), optional boost (boosted multiplier, or profit-boost
percent and cap, converted and shown). Output: break-even per leg (power
M^(-1/N); flex solved from the typed table); EV per unit at coin-flip legs;
the boost's value (EV with minus without); a same-game flag on legs from one
game ('these legs move together; the math assumes they don't'), no
correlation estimate (LAW 2). Colour law: green outline clears, red outline
costs." Ruling D: "Legs are standard, goblin or demon; the operator types the
line and the payout the app shows for the entry; break-even comes from that
payout only." LAW 5's forbidden half: "Gridiron never logs in to, reads,
scrapes or calls any pick'em app, holds no credential for one, never places or
edits an entry. No payout table hard-coded as fact: the operator types the
multiplier or flex table shown in the app; the last one typed per app and
entry size is offered as a default and must be confirmed."

EVERY NUMBER BELOW IS WORKED BY HAND in its test (2026-10-07), never read back
off the code: a power entry breaks even per leg at M ** (-1/N) and returns
M / 2**N - 1 per unit at coin flips; a flex table returns the sum over k of
C(N, k) / 2**N times what k right pays, less one, and breaks even where that
sum taken at p, the legs independent, is one. Each test fails on 535c253,
which has no entry check (the module, the route and the panel are new), and
the browser tests fail there on the form they drive.
"""
from __future__ import annotations

import ast
import json
import re
import sqlite3
from pathlib import Path

import pytest

from gridiron import api, audit, auth, db, entry_check, entry_math, language, rebuild, schema_diff

ROOT = Path(__file__).resolve().parents[1]

#: The clock the worked examples are asked at: before the world's games.
NOW = "2099-10-01T00:00:00Z"


# ---------------------------------------------------------------------------
# the world: four clubs, their next games, a game played, and the players
# ---------------------------------------------------------------------------

def _world(conn):
    """Green Bay at Detroit and Kansas City at Buffalo on 11 October 2099,
    Detroit's next game after it a week later, a game Detroit already played
    and one under way; the players the tests name, Davante Adams with a game
    for Green Bay and a later one for Kansas City, and two players called
    Mike Williams on Kansas City."""
    for code, name in (("DET", "Detroit Lions"), ("GB", "Green Bay Packers"),
                       ("BUF", "Buffalo Bills"), ("KC", "Kansas City Chiefs"),
                       ("NYJ", "New York Jets"), ("MIA", "Miami Dolphins")):
        conn.execute(
            "INSERT INTO teams (sport, tricode, display_name, short_name, location,"
            " source_url, fetched_utc) VALUES ('nfl', ?, ?, ?, ?, 'test',"
            " '2099-09-01T00:00:00Z')", (code, name, name.split()[-1], name))
    for gid, home, away, start, status, score in (
            ("w_played", "DET", "KC", "2099-09-27T17:00:00Z", "final", 24),
            ("w_gb_det", "DET", "GB", "2099-10-11T17:00:00Z", "scheduled", None),
            ("w_kc_buf", "BUF", "KC", "2099-10-11T20:25:00Z", "scheduled", None),
            ("w_det_next", "DET", "BUF", "2099-10-18T17:00:00Z", "scheduled", None),
            # The Jets' and Dolphins' one game is under way: no game to come.
            ("w_under_way", "NYJ", "MIA", "2099-09-30T23:00:00Z", "in", 7)):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
            " league_date, home, away, status, home_score, away_score) VALUES (?, 'nfl',"
            " 2099, 5, 'REG', ?, ?, ?, ?, ?, ?, ?)",
            (gid, start, start[:10], home, away, status, score,
             None if score is None else score - 4))
    for week, pid, name, club in (
            (1, "p-goff", "Jared Goff", "DET"), (1, "p-stb", "Amon-Ra St. Brown", "DET"),
            (1, "p-love", "Jordan Love", "GB"), (1, "p-allen", "Josh Allen", "BUF"),
            (1, "p-pm", "Patrick Mahomes", "KC"), (1, "p-mw1", "Mike Williams", "KC"),
            (1, "p-mw2", "Mike Williams", "KC"), (1, "p-da", "Davante Adams", "GB"),
            (2, "p-da", "Davante Adams", "KC"), (1, "p-jet", "Garrett Wilson", "NYJ")):
        conn.execute(
            "INSERT INTO player_week_stats (season, week, player_id, player_name,"
            " position, team, opponent) VALUES (2099, ?, ?, ?, 'WR', ?, 'BUF')",
            (week, pid, name, club))
    conn.commit()
    return conn


@pytest.fixture
def world(conn):
    return _world(conn)


def _leg(player, club, *, line=250.5, side="over", kind="standard", original="",
         stat="passing yards"):
    return {"player": player, "club": club, "stat": stat, "line": str(line),
            "side": side, "kind": kind, "original_line": original}


def _form(legs, payout, *, entry_type="power", app="prizepicks", confirmed=True, promo=None):
    return {"app": app, "entry_type": entry_type, "legs": legs, "payout": payout,
            "payout_confirmed": confirmed, "promo": promo or {"kind": "none"}}


TWO = [_leg("Jared Goff", "DET"), _leg("Josh Allen", "BUF")]
THREE = TWO + [_leg("Jordan Love", "GB")]
FIVE = THREE + [_leg("Patrick Mahomes", "KC"),
                _leg("Amon-Ra St. Brown", "DET", stat="receiving yards", line=70.5)]


def _check(conn, form, *, remember=False):
    """The shipped check on a form, as the page sends it (through JSON)."""
    return entry_check.check(conn, json.loads(json.dumps(form)), now=NOW,
                             remember_it=remember)


def _said(out) -> str:
    return json.dumps(out, ensure_ascii=False)


def _flex_return(table, n, p):
    """What a flex table returns per unit, less the unit, the legs
    independent at p: worked here apart from the code, term by term."""
    from math import comb
    return sum(comb(n, k) * p ** k * (1 - p) ** (n - k) * table.get(k, 0.0)
               for k in range(n + 1)) - 1.0


# ---------------------------------------------------------------------------
# the brief's worked examples
# ---------------------------------------------------------------------------

def test_a_two_leg_power_entry_at_3x_breaks_even_at_57_74_and_costs(world):
    """3 ** (-1/2) = 0.57735; 3 / 4 - 1 = -0.25 per unit at coin flips; an
    even chance is 7.74 points under the break-even, and the entry costs (the
    red outline)."""
    out = _check(world, _form(TWO, {"multiplier": "3"}))
    assert out["computed"] and out["refused_words"] is None
    assert out["numbers"]["breakeven"] == pytest.approx(0.577350, abs=1e-6)
    assert out["numbers"]["expected"] == pytest.approx(-0.25, abs=1e-12)
    assert out["signal"] == "costs"
    said = _said(out)
    for words in ("57.74%", "-0.25 per unit", "7.74 points under its break-even",
                  "Costs at coin flips"):
        assert words in said, words


def test_a_two_leg_power_entry_at_4_5x_is_a_number_with_no_outline(world):
    """4.5 ** (-1/2) = 0.471405; 4.5 / 4 - 1 = +0.125 per unit: it returns
    more than it costs at coin flips, but an even chance is only 2.86 points
    over each leg's break-even -- under B.2's three -- so reading (h) gives
    the numbers and no outline."""
    out = _check(world, _form(TWO, {"multiplier": "4.5"}))
    assert out["numbers"]["breakeven"] == pytest.approx(0.471405, abs=1e-6)
    assert out["numbers"]["expected"] == pytest.approx(0.125, abs=1e-12)
    assert out["signal"] == "none"
    assert out["verdict_words"].startswith("No outline")
    said = _said(out)
    for words in ("47.14%", "+0.125 per unit", "2.86 points over its break-even",
                  "under the 3 the bar needs"):
        assert words in said, words


def test_a_goblin_and_a_demon_leg_move_no_number(world):
    """RULING D: "break-even comes from that payout only." A goblin leg (its
    line lowered from 265.5) and a demon leg in one 2-leg power entry at 3x
    break even at 57.74% a leg and return -0.25 at coin flips -- exactly the
    standard legs' numbers -- and each leg is drawn with its kind and its
    discount. Neither the line typed nor the side moves a number either."""
    plain = _check(world, _form(TWO, {"multiplier": "3"}))
    kinds = _check(world, _form([_leg("Jared Goff", "DET", kind="goblin", original="265.5",
                                      line=240.5, side="under"),
                                 _leg("Josh Allen", "BUF", kind="demon", line=310.5)],
                                {"multiplier": "3"}))
    for key in ("breakeven", "expected", "offered_breakeven", "offered_expected",
                "edge_points"):
        assert kinds["numbers"][key] == plain["numbers"][key], key
    assert kinds["signal"] == plain["signal"] == "costs"
    assert [leg["detail_words"] for leg in kinds["legs"]] == [
        "goblin · discounted from 265.5", "demon"]
    assert kinds["legs"][0]["words"] == "Jared Goff under 240.5 passing yards"
    assert "57.74%" in _said(kinds)


def test_a_three_leg_power_entry_at_5x_breaks_even_at_58_48(world):
    """5 ** (-1/3) = 0.584804; 5 / 8 - 1 = -0.375 per unit."""
    out = _check(world, _form(THREE, {"multiplier": "5"}))
    assert out["numbers"]["breakeven"] == pytest.approx(0.584804, abs=1e-6)
    assert out["numbers"]["expected"] == pytest.approx(-0.375, abs=1e-12)
    assert out["signal"] == "costs"
    assert "58.48%" in _said(out) and "-0.375 per unit" in _said(out)


def test_a_five_leg_flex_table_is_solved_from_the_table_typed(world):
    """THE FLEX TABLE STATED: 5 of 5 right pays 10x, 4 of 5 pays 2x, 3 of 5
    pays 0.4x, fewer nothing (Underdog's shape; typed, never declared). At
    coin flips it returns (1 x 10 + 5 x 2 + 10 x 0.4) / 32 - 1 = 24/32 - 1 =
    -0.25 per unit. Its break-even per leg is the p at which
    10p^5 + 10p^4(1-p) + 4p^3(1-p)^2 = 1: 0.542525, solved by bisection to
    far under the hundredth of a point drawn (54.25%), and checked here by
    the sign of the return a millionth either side of it."""
    table = {5: 10.0, 4: 2.0, 3: 0.4}
    out = _check(world, _form(FIVE, {"table": {"5": "10", "4": "2", "3": "0.4"}},
                              entry_type="flex", app="underdog"))
    assert out["numbers"]["expected"] == pytest.approx(-0.25, abs=1e-12)
    be = out["numbers"]["breakeven"]
    assert be == pytest.approx(0.542525, abs=1e-6)
    assert _flex_return(table, 5, be - 1e-6) < 0 < _flex_return(table, 5, be + 1e-6)
    said = _said(out)
    assert "54.25%" in said and "-0.25 per unit" in said and "solved step by step" in said
    # A 3-leg flex table: 3 right pays 2.25x, 2 right 1.25x -- (2.25 + 3 x
    # 1.25) / 8 - 1 = -0.25; break-even 0.590942.
    three = _check(world, _form(THREE, {"table": {"3": "2.25", "2": "1.25"}},
                                entry_type="flex", app="chalkboard"))
    assert three["numbers"]["expected"] == pytest.approx(-0.25, abs=1e-12)
    assert three["numbers"]["breakeven"] == pytest.approx(0.590942, abs=1e-6)


def test_a_promo_raising_3x_to_3_5x_is_shown_and_adds_what_it_adds(world):
    """The app raises a 2-leg power entry from 3x to 3.5x: with the promo it
    breaks even at 3.5 ** (-1/2) = 53.45% a leg and returns 3.5 / 4 - 1 =
    -0.125; without it 57.74% and -0.25; the promo adds -0.125 - (-0.25) =
    +0.125 per unit (the brief's "EV with minus without")."""
    out = _check(world, _form(TWO, {"multiplier": "3"},
                              promo={"kind": "raised", "payout": {"multiplier": "3.5"}}))
    n = out["numbers"]
    assert n["breakeven"] == pytest.approx(0.577350, abs=1e-6)
    assert n["offered_breakeven"] == pytest.approx(0.534522, abs=1e-6)
    assert n["offered_expected"] == pytest.approx(-0.125, abs=1e-12)
    assert n["promo_adds"] == pytest.approx(0.125, abs=1e-12)
    assert n["offered"] == {"multiplier": "3.5"} and n["payout"] == {"multiplier": "3"}
    said = _said(out)
    for words in ("With the promo the app pays 3.5x, from 3x.", "53.45%",
                  "-0.125 per unit", "+0.125 per unit"):
        assert words in said, words


def test_a_20_percent_profit_promo_with_a_cap_is_converted_and_shown(world):
    """A 3-leg power entry at 5x with 20% of the winnings added, at most 5
    units on a 10-unit entry. Uncapped it adds 20% of the 4 units of profit
    a unit, 0.8, to make 5.8x; the cap allows 5 / 10 = 0.5 a unit, so 5.5x:
    break-even 5.5 ** (-1/3) = 56.65%, 5.5 / 8 - 1 = -0.3125 at coin flips,
    and the promo adds -0.3125 - (-0.375) = +0.0625. With no cap: 5.8x, -0.275,
    adds +0.1. Units only, never dollars; the entry in units is asked only
    because the cap needs it."""
    capped = _check(world, _form(THREE, {"multiplier": "5"},
                                 promo={"kind": "profit", "percent": "20",
                                        "cap_units": "5", "entry_units": "10"}))
    n = capped["numbers"]
    assert n["offered"] == {"multiplier": "5.5"}
    assert n["offered_breakeven"] == pytest.approx(0.566516, abs=1e-6)
    assert n["offered_expected"] == pytest.approx(-0.3125, abs=1e-12)
    assert n["promo_adds"] == pytest.approx(0.0625, abs=1e-12)
    said = _said(capped)
    for words in ("A 20% share of the winnings added, at most 5 units on a 10-unit entry,",
                  "makes the entry pay 5.5x, from 5x",
                  "The cap holds it there: without the cap it would pay 5.8x",
                  "56.65%", "+0.0625 per unit"):
        assert words in said, words
    # UNITS ONLY: no sum of money anywhere; the one "dollars" is the note's
    # "never dollars".
    assert "$" not in said and said.lower().count("dollar") == said.count("never dollars")
    open_ended = _check(world, _form(THREE, {"multiplier": "5"},
                                     promo={"kind": "profit", "percent": "20"}))
    assert open_ended["numbers"]["offered"] == {"multiplier": "5.8"}
    assert open_ended["numbers"]["offered_expected"] == pytest.approx(-0.275, abs=1e-12)
    assert open_ended["numbers"]["promo_adds"] == pytest.approx(0.1, abs=1e-12)


def test_a_capped_promo_asks_the_entry_in_units_and_nothing_else_does(world):
    """READING (c): the entry in units is asked only where the cap needs it.
    With a cap and no entry typed, nothing is worked out and the check asks;
    with no cap, whatever sits in the field is not read at all."""
    asked = _check(world, _form(TWO, {"multiplier": "3"},
                                promo={"kind": "profit", "percent": "20", "cap_units": "5"}))
    assert not asked["computed"] and asked["numbers"] is None and asked["signal"] == "none"
    assert asked["ask_words"].startswith("Type the entry in units")
    ignored = _check(world, _form(TWO, {"multiplier": "3"},
                                  promo={"kind": "profit", "percent": "20",
                                         "entry_units": "not a number"}))
    assert ignored["computed"] and ignored["refused_words"] is None


def test_a_promo_is_applied_once_to_the_payout_typed(world):
    """THE BRIEF'S PLANTING, "a boost applied twice": the promo is applied to
    the payout typed, once. The 20% share applied again to the 5.5x it made
    would be 6x (5.5 + min(0.2 x 4.5, 0.5)); the app's raised 3.5x taken as a
    rise of 0.5 on the raised payout would be 4x. Neither is what the check
    offers."""
    twice = entry_math.with_a_profit_promo(
        entry_math.with_a_profit_promo({"multiplier": 5.0}, percent=20, cap_units=5,
                                       entry_units=10),
        percent=20, cap_units=5, entry_units=10)
    assert twice == {"multiplier": 6.0}
    once = _check(world, _form(THREE, {"multiplier": "5"},
                               promo={"kind": "profit", "percent": "20", "cap_units": "5",
                                      "entry_units": "10"}))
    assert once["numbers"]["offered"] == {"multiplier": "5.5"}
    raised = _check(world, _form(TWO, {"multiplier": "3"},
                                 promo={"kind": "raised", "payout": {"multiplier": "3.5"}}))
    assert raised["numbers"]["offered"] == {"multiplier": "3.5"}


# ---------------------------------------------------------------------------
# the colour, reading (h)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("multiple,signal,gap", [
    ("5", "clears", "5.28 points over its break-even"),       # 44.72%
    ("4.526935264825713", "clears", "3.00 points over its break-even"),  # 47.00%: at the bar
    ("4.52", "none", "2.96 points over its break-even"),       # 47.04%
    ("4.5", "none", "2.86 points over its break-even"),
    ("4", "none", "exactly at its break-even"),                # returns its cost
    ("3", "costs", "7.74 points under its break-even"),
])
def test_the_outline_is_reading_h(world, multiple, signal, gap):
    """READING (h), 2026-10-07: at coin flips an entry CLEARS -- the green
    outline -- only where each leg's break-even is three points or more under
    an even chance (B.2, through its one door `picks.clears_the_pick_bar`),
    COSTS -- the red one -- where it returns less than it costs, and between
    them it is drawn as numbers with no outline."""
    out = _check(world, _form(TWO, {"multiplier": multiple}))
    assert out["signal"] == signal, out["verdict_words"]
    assert gap in _said(out)
    assert "-0.00" not in _said(out)


def test_a_gap_under_the_bar_is_never_drawn_at_it(world):
    """B.2's rule (`picks.drawn_edge`, at this page's hundredths): a break-even
    2.996 points under an even chance is drawn 2.99, never 3.00, and wears no
    outline."""
    multiple = (0.5 - 0.02996) ** -2
    out = _check(world, _form(TWO, {"multiplier": repr(multiple)}))
    assert out["signal"] == "none"
    assert "2.99 points over its break-even" in _said(out)
    assert "3.00" not in _said(out)


def test_an_entry_returning_exactly_its_cost_says_so_and_never_minus_zero(world):
    """8x on three legs returns 8 / 8 - 1 = 0 at coin flips, and 8 ** (-1/3)
    is a hair over one half in floating point: the words say it returns
    exactly what it costs, with no "-0.00"."""
    out = _check(world, _form(THREE, {"multiplier": "8"}))
    assert out["signal"] == "none"
    said = _said(out)
    assert "exactly at its break-even" in said and "returns exactly what it costs" in said
    assert "-0.00" not in said and "+0.00 per unit" in said


def test_exactly_is_said_only_of_an_entry_exactly_at_its_break_even(world):
    """THE PROVER (2026-10-07): a gap under a hundredth of a point rounds to
    0.00, and as handed the words then said "exactly". 3.9999x on two legs
    breaks even at 3.9999 ** (-1/2) = 0.5000063 a leg and returns 3.9999 / 4
    - 1 = -0.000025 at coin flips -- red, rightly -- and its gap read "exactly
    at its break-even"; 4.0001x, 0.4999938 and +0.000025, no outline, was
    said to return "exactly what it costs". Each is less than a hundredth of
    a point from its break-even, on its own side; 4x is exactly at it. And a
    cap of one unit is "1 unit"."""
    under = _check(world, _form(TWO, {"multiplier": "3.9999"}))
    assert under["signal"] == "costs"
    gap = under["lines"][-1]["value_words"]
    assert gap == "less than a hundredth of a point under its break-even", gap
    over = _check(world, _form(TWO, {"multiplier": "4.0001"}))
    assert over["signal"] == "none"
    assert over["lines"][-1]["value_words"] == (
        "less than a hundredth of a point over its break-even")
    assert "exactly" not in _said(over) and "exactly" not in _said(under)
    assert "less than a hundredth of a point over each leg's break-even" in over["verdict_words"]
    exact = _check(world, _form(TWO, {"multiplier": "4"}))
    assert exact["lines"][-1]["value_words"] == "exactly at its break-even"
    assert "returns exactly what it costs" in exact["verdict_words"]
    one = _check(world, _form(THREE, {"multiplier": "5"}, promo={
        "kind": "profit", "percent": "20", "cap_units": "1", "entry_units": "10"}))
    assert "at most 1 unit on a 10-unit entry," in one["promo_words"], one["promo_words"]


def test_a_promo_can_make_an_entry_clear(world):
    """THE OUTLINE IS THE ENTRY AS OFFERED, its promo in: the brief's reason
    for the check -- "Pick'em promos are the one place an edge can come from
    arithmetic alone". 3x on two legs costs; the app raising it to 5x makes
    it clear (each leg's break-even 44.72%, 5.28 points under an even
    chance), and the lines say both."""
    out = _check(world, _form(TWO, {"multiplier": "3"},
                              promo={"kind": "raised", "payout": {"multiplier": "5"}}))
    assert out["signal"] == "clears"
    said = _said(out)
    assert "57.74%" in said and "44.72%" in said and "5.28 points over" in said


# ---------------------------------------------------------------------------
# nothing from a payout not confirmed (reading (e))
# ---------------------------------------------------------------------------

def test_nothing_is_worked_out_from_a_payout_not_confirmed(world):
    """"Offered as a default and must be confirmed": with the box unticked,
    no number, no outline and no line is worked out, nothing is kept, and the
    check says why -- while the legs are still placed in their games, which
    no payout moves."""
    out = _check(world, _form(TWO, {"multiplier": "3"}, confirmed=False), remember=True)
    assert not out["computed"] and out["numbers"] is None
    assert out["signal"] == "none" and out["lines"] == [] and out["verdict_words"] is None
    assert out["ask_words"].startswith("Confirm what the app pays for this entry")
    assert [leg["game_words"] is not None for leg in out["legs"]] == [True, True]
    assert world.execute("SELECT COUNT(*) FROM pickem_payouts_typed").fetchone()[0] == 0
    # A "true" that is not the value true is not a confirmation.
    loose = _form(TWO, {"multiplier": "3"})
    loose["payout_confirmed"] = "true"
    assert not _check(world, loose)["computed"]


# ---------------------------------------------------------------------------
# legs in one game (reading (d))
# ---------------------------------------------------------------------------

def test_legs_in_one_game_are_flagged_in_the_briefs_words_and_nothing_is_estimated(world):
    """Two Detroit legs and a Buffalo one: legs 1 and 2 are in Green Bay at
    Detroit, flagged in the brief's own words. LAW 2: no number is put on how
    they move together -- the arithmetic is the arithmetic of the same
    payout with the legs in three games, and nothing in the answer speaks of
    a correlation."""
    pair = _check(world, _form([_leg("Jared Goff", "DET"), _leg("Amon-Ra St. Brown", "DET"),
                                _leg("Josh Allen", "BUF")], {"multiplier": "6"}))
    apart = _check(world, _form([_leg("Jared Goff", "DET"), _leg("Patrick Mahomes", "KC"),
                                 _leg("Josh Allen", "BUF")], {"multiplier": "6"}))
    assert pair["numbers"]["groups"] == [[0, 1]] and pair["numbers"]["unchecked"] == []
    assert pair["one_game_words"][0].startswith(
        "Legs 1 and 2 are in one game, Green Bay Packers at Detroit Lions, ")
    assert pair["one_game_words"][0].endswith(
        ": these legs move together; the math assumes they don't.")
    for key in ("breakeven", "expected", "edge_points"):
        assert pair["numbers"][key] == apart["numbers"][key], key
    assert pair["signal"] == apart["signal"]
    assert "correlat" not in _said(pair).lower()
    # KANSAS CITY AT BUFFALO is one game too, and Detroit's next game is the
    # earliest still to come (11 October), never the one after it.
    assert apart["numbers"]["groups"] == [[1, 2]]
    assert pair["legs"][0]["game_words"].startswith("Green Bay Packers at Detroit Lions, ")
    assert "October" in pair["legs"][0]["game_words"]
    clubs = _check(world, _form([_leg("Jordan Love", "GB"), _leg("Jared Goff", "DET")],
                                {"multiplier": "3"}))
    assert clubs["numbers"]["groups"] == [[0, 1]]
    alone = _check(world, _form(TWO, {"multiplier": "3"}))
    assert alone["numbers"]["groups"] == [] and alone["one_game_words"] == [
        "No two legs are in one game."]


def test_a_traded_player_is_placed_with_the_club_of_his_latest_game(world):
    """Davante Adams played week 1 for Green Bay and week 2 for Kansas City:
    typed with Kansas City he is in Kansas City at Buffalo beside Patrick
    Mahomes; typed with Green Bay he is not placed, and the words say where
    the record has him."""
    with_kc = _check(world, _form([_leg("Davante Adams", "KC"), _leg("Patrick Mahomes", "KC")],
                                  {"multiplier": "3"}))
    assert with_kc["numbers"]["groups"] == [[0, 1]]
    with_gb = _check(world, _form([_leg("Davante Adams", "GB"), _leg("Jordan Love", "GB")],
                                  {"multiplier": "3"}))
    assert with_gb["numbers"]["groups"] == [] and with_gb["numbers"]["unchecked"] == [0]
    assert ("The record has Davante Adams playing for Kansas City Chiefs by his latest game "
            "this season, not Green Bay Packers") in with_gb["legs"][0]["unplaced_words"]


def test_a_leg_the_record_cannot_place_says_so_and_is_never_guessed(world):
    """READING (d): "never guessed; a leg that cannot be placed in a game says
    so, and the flag then says it could not check those legs". No club; a
    club whose one game is under way (none still to come); two Kansas City
    players called Mike Williams; a player the record does not have; a name
    folded only by accents, case and punctuation ("amon ra st brown" is
    Amon-Ra St. Brown) -- never a nickname or a near miss."""
    out = _check(world, _form([
        _leg("Jared Goff", "DET"), _leg("Josh Allen", ""), _leg("Garrett Wilson", "NYJ"),
        _leg("Mike Williams", "KC"), _leg("Nobody Atall", "KC"),
        _leg("amon ra st brown", "DET"), _leg("Jared Gof", "DET")], {"multiplier": "20"}))
    assert out["numbers"]["unchecked"] == [1, 2, 3, 4, 6]
    assert out["numbers"]["groups"] == [[0, 5]]
    why = [leg["unplaced_words"] for leg in out["legs"]]
    assert why[1] == "No club was chosen, so this leg was not placed in a game."
    assert why[2] == ("The record has no New York Jets game still to come, so this leg "
                      "was not placed in a game.")
    assert "more than one Kansas City Chiefs player called Mike Williams" in why[3]
    assert why[4].startswith("No player called Nobody Atall is in the record's game stats")
    assert why[6].startswith("No player called Jared Gof is in the record's game stats")
    assert out["one_game_words"][-1] == (
        "Legs 2, 3, 4, 5 and 7 could not be placed in a game, so they were not checked "
        "against the others for a game they share.")
    none = _check(world, _form([_leg("Nobody", ""), _leg("Somebody", "")], {"multiplier": "3"}))
    assert none["one_game_words"] == [
        "No leg could be placed in a game, so none was checked against the others for a "
        "game they share."]


def test_two_legs_of_a_game_past_its_start_and_not_over_are_never_put_in_next_weeks_games(world):
    """THE PROVER (2026-10-07): an NFL game stays 'scheduled' on the record
    from its listed start until a refresh writes its result (no poll follows
    an NFL game, question 38), and the check as built placed a leg in its
    club's next game still to come -- so during Chicago at Minnesota, a
    Minnesota leg and a Chicago leg, both in that game, were put in next
    week's two games, and "No two legs are in one game" was said of a pair in
    one game: the brief's planting, an unflagged same-game pair, and a game
    guessed (reading (d)). A club whose latest game past its listed start is
    not recorded as over cannot say which game a leg is in: such a leg is not
    placed, says why, and the flag says it was not checked. Before the start
    the two legs are one game; once the game is recorded as over, each is in
    its club's next game."""
    world.execute(
        "INSERT INTO teams (sport, tricode, display_name, short_name, location, source_url,"
        " fetched_utc) VALUES ('nfl', 'MIN', 'Minnesota Vikings', 'Vikings', 'Minnesota',"
        " 'test', '2099-09-01T00:00:00Z'), ('nfl', 'CHI', 'Chicago Bears', 'Bears',"
        " 'Chicago', 'test', '2099-09-01T00:00:00Z')")
    for gid, home, away, start in (("w_chi_min", "MIN", "CHI", "2099-09-30T23:00:00Z"),
                                   ("w_min_next", "GB", "MIN", "2099-10-18T20:25:00Z"),
                                   ("w_chi_next", "KC", "CHI", "2099-10-19T00:15:00Z")):
        world.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc, league_date,"
            " home, away, status) VALUES (?, 'nfl', 2099, 5, 'REG', ?, ?, ?, ?, 'scheduled')",
            (gid, start, start[:10], home, away))
    for pid, name, club in (("p-jj", "Justin Jefferson", "MIN"), ("p-djm", "DJ Moore", "CHI")):
        world.execute(
            "INSERT INTO player_week_stats (season, week, player_id, player_name, position,"
            " team, opponent) VALUES (2099, 1, ?, ?, 'WR', ?, 'BUF')", (pid, name, club))
    world.commit()
    form = _form([_leg("Justin Jefferson", "MIN"), _leg("DJ Moore", "CHI")], {"multiplier": "3"})
    before = entry_check.check(world, json.loads(json.dumps(form)), now="2099-09-30T22:00:00Z",
                               remember_it=False)
    assert before["numbers"]["groups"] == [[0, 1]], before["numbers"]
    assert before["legs"][0]["game_words"].startswith("Chicago Bears at Minnesota Vikings")
    under_way = _check(world, form)
    assert under_way["numbers"]["groups"] == [] and under_way["numbers"]["unchecked"] == [0, 1], (
        under_way["numbers"], [leg["game_words"] for leg in under_way["legs"]])
    why = [leg["unplaced_words"] for leg in under_way["legs"]]
    assert why[0] == (
        "The record does not yet have the Chicago Bears at Minnesota Vikings game of "
        + language.date_words_from_iso("2099-09-30") + " as over, though it is past its "
        "listed start, so it cannot tell whether this leg is in that game or the next one; "
        "this leg was not placed in a game."), why[0]
    assert under_way["one_game_words"] == [
        "No leg could be placed in a game, so none was checked against the others for a "
        "game they share."]
    assert "No two legs are in one game." not in under_way["one_game_words"]
    world.execute("UPDATE games SET status = 'final', home_score = 20, away_score = 17"
                  " WHERE id = 'w_chi_min'")
    world.commit()
    over = _check(world, form)
    assert over["numbers"]["unchecked"] == [] and over["numbers"]["groups"] == []
    assert over["legs"][0]["game_words"].startswith("Minnesota Vikings at Green Bay Packers")
    assert over["legs"][1]["game_words"].startswith("Chicago Bears at Kansas City Chiefs")


def test_a_game_with_no_start_time_yet_that_could_come_first_places_no_leg(world):
    """THE PROVER (2026-10-07): nflverse lists a game's time as not yet set
    for weeks (a late-season game the league has not slotted), and the loader
    stores no start for it rather than guess one (`reference.kickoff_to_utc`).
    The check as built read only dated games, so a leg on a club whose next
    game had no time yet was put in the dated game AFTER it, and two legs of
    that one game in two later games, unflagged. Such a game, not recorded as
    over and on or before the club's next dated game's day, leaves the leg
    unplaced and saying why; one after the next dated game, or one before a
    game the club has since played, changes nothing."""
    world.execute(
        "INSERT INTO teams (sport, tricode, display_name, short_name, location, source_url,"
        " fetched_utc) VALUES ('nfl', 'SEA', 'Seattle Seahawks', 'Seahawks', 'Seattle',"
        " 'test', '2099-09-01T00:00:00Z'), ('nfl', 'LAR', 'Los Angeles Rams', 'Rams',"
        " 'Los Angeles', 'test', '2099-09-01T00:00:00Z')")
    for gid, home, away, start, day in (
            ("w_lar_sea_tbd", "SEA", "LAR", None, "2099-10-10"),
            ("w_sea_next", "SEA", "GB", "2099-10-18T20:05:00Z", "2099-10-18"),
            ("w_lar_next", "LAR", "BUF", "2099-10-19T00:20:00Z", "2099-10-19")):
        world.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc, league_date,"
            " home, away, status) VALUES (?, 'nfl', 2099, 5, 'REG', ?, ?, ?, ?, 'scheduled')",
            (gid, start, day, home, away))
    for pid, name, club in (("p-dk", "DK Metcalf", "SEA"), ("p-pn", "Puka Nacua", "LAR")):
        world.execute(
            "INSERT INTO player_week_stats (season, week, player_id, player_name, position,"
            " team, opponent) VALUES (2099, 1, ?, ?, 'WR', ?, 'BUF')", (pid, name, club))
    world.commit()
    form = _form([_leg("DK Metcalf", "SEA"), _leg("Puka Nacua", "LAR"),
                  _leg("Jared Goff", "DET")], {"multiplier": "6"})
    out = _check(world, form)
    assert out["numbers"]["unchecked"] == [0, 1] and out["numbers"]["groups"] == [], (
        out["numbers"], [leg["game_words"] for leg in out["legs"]])
    assert out["legs"][0]["unplaced_words"] == (
        "The record has no start time yet for the Los Angeles Rams at Seattle Seahawks game "
        "of " + language.date_words_from_iso("2099-10-10") + ", so it cannot tell whether "
        "this leg is in that game or the next one; this leg was not placed in a game.")
    assert out["legs"][2]["game_words"].startswith("Green Bay Packers at Detroit Lions")
    # A GAME WITH NO TIME AFTER THE NEXT DATED ONE CHANGES NOTHING: Detroit's
    # next game is 11 October, and one on 25 October with no time yet is not
    # before it.
    world.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc, league_date,"
        " home, away, status) VALUES ('w_det_tbd', 'nfl', 2099, 7, 'REG', NULL, '2099-10-25',"
        " 'DET', 'SEA', 'scheduled')")
    # NOR ONE BEFORE A GAME THE CLUB HAS SINCE PLAYED: Kansas City played on
    # 27 September, after a game of 20 September the record never dated.
    world.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc, league_date,"
        " home, away, status) VALUES ('w_kc_old_tbd', 'nfl', 2099, 2, 'REG', NULL,"
        " '2099-09-20', 'KC', 'GB', 'scheduled')")
    world.commit()
    later = _check(world, _form([_leg("Jared Goff", "DET"), _leg("Patrick Mahomes", "KC")],
                                {"multiplier": "3"}))
    assert later["numbers"]["unchecked"] == [], [leg["unplaced_words"] for leg in later["legs"]]
    assert later["legs"][0]["game_words"].startswith("Green Bay Packers at Detroit Lions")
    assert later["legs"][1]["game_words"].startswith("Kansas City Chiefs at Buffalo Bills")


# ---------------------------------------------------------------------------
# the payouts typed (reading (e))
# ---------------------------------------------------------------------------

def test_the_payout_confirmed_is_kept_once_as_typed_and_offered_unconfirmed(world):
    """The last payout typed per app, entry type and size is kept when the
    operator confirms it, once (the same again is not kept twice), as he
    typed it -- never a promo's raised payout -- and offered back filled in
    with words saying what and when, carrying no confirmation of its own."""
    def kept():
        return world.execute("SELECT COUNT(*) FROM pickem_payouts_typed").fetchone()[0]

    _check(world, _form(TWO, {"multiplier": "3"}), remember=True)
    first = _check(world, _form(TWO, {"multiplier": "3"}), remember=True)
    assert kept() == 1 and first["remembered_now_words"] is None
    raised = _check(world, _form(TWO, {"multiplier": "3"},
                                 promo={"kind": "raised", "payout": {"multiplier": "3.5"}}),
                    remember=True)
    assert kept() == 1 and raised["remembered_now_words"] is None
    later = _check(world, _form(TWO, {"multiplier": "3.25"}), remember=True)
    assert kept() == 2
    assert later["remembered_now_words"] == (
        "Remembered for PrizePicks 2-pick power: 3.25x. It is offered next time, to "
        "confirm again.")
    _check(world, _form(FIVE, {"table": {"5": "10", "4": "2", "3": "0.4"}},
                        entry_type="flex", app="underdog"), remember=True)
    offered = entry_check.remembered(world)
    assert [(r["app"], r["entry_type"], r["legs"], r["fields"]) for r in offered] == [
        ("prizepicks", "power", 2, {"multiplier": "3.25"}),
        ("underdog", "flex", 5, {"table": {"3": "0.4", "4": "2", "5": "10"}})]
    assert all("confirmed" not in r for r in offered)
    assert offered[1]["words"].startswith("Last typed for Underdog 5-pick flex, ")
    assert offered[1]["words"].endswith(
        ": 5 of 5 right pays 10x, 4 of 5 right pays 2x, 3 of 5 right pays 0.4x, fewer pays "
        "nothing. Confirm it is what the app shows for this entry, or type what it shows.")
    rows = world.execute("SELECT app, entry_type, legs, multiplier, flex_table"
                         " FROM pickem_payouts_typed ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [
        ("prizepicks", "power", 2, 3.0, None), ("prizepicks", "power", 2, 3.25, None),
        ("underdog", "flex", 5, None, '{"3": 0.4, "4": 2.0, "5": 10.0}')]
    # A form refused, or a payout not confirmed, keeps nothing.
    _check(world, _form(TWO[:1], {"multiplier": "9"}), remember=True)
    _check(world, _form(TWO, {"multiplier": "9"}, confirmed=False), remember=True)
    assert kept() == 3


def test_a_payout_is_offered_back_as_it_was_typed(world):
    """THE PROVER (2026-10-07): the payout offered is the last one TYPED
    (reading (e)). As handed the fields held six figures, so 123.4567x came
    back as 123.457 -- another payout -- and, confirmed as offered, was kept
    again as a second row; a flex row of 0.3333 came back whole only because
    it has four."""
    form = _form(TWO, {"multiplier": "123.4567"}, app="chalkboard")
    _check(world, form, remember=True)
    offered = [r for r in entry_check.remembered(world) if r["app"] == "chalkboard"]
    assert [r["fields"] for r in offered] == [{"multiplier": "123.4567"}], offered
    again = _form(TWO, offered[0]["fields"], app="chalkboard")
    _check(world, again, remember=True)
    assert world.execute("SELECT COUNT(*) FROM pickem_payouts_typed"
                         " WHERE app = 'chalkboard'").fetchone()[0] == 1
    flex = _form(FIVE, {"table": {"5": "20.123456", "4": "1.75", "3": "0.3333"}},
                 entry_type="flex", app="chalkboard")
    _check(world, flex, remember=True)
    got = [r["fields"] for r in entry_check.remembered(world)
           if (r["app"], r["entry_type"]) == ("chalkboard", "flex")]
    assert got == [{"table": {"3": "0.3333", "4": "1.75", "5": "20.123456"}}], got


def test_the_payouts_typed_are_append_only(world):
    """A later payout is a new row; a row written is never edited, deleted or
    written over, and the table refuses what is not a payout per unit."""
    _check(world, _form(TWO, {"multiplier": "3"}), remember=True)
    for statement in ("UPDATE pickem_payouts_typed SET multiplier = 4",
                      "DELETE FROM pickem_payouts_typed",
                      "INSERT INTO pickem_payouts_typed (id, typed_utc, app, entry_type, legs,"
                      " multiplier) VALUES (1, '2099-10-01T00:00:00Z', 'prizepicks', 'power',"
                      " 2, 4.0)"):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            world.execute(statement)
        world.rollback()
    for bad in ("('2099-10-01T00:00:00Z', 'sleeper', 'power', 2, 3.0, NULL)",
                "('2099-10-01T00:00:00Z', 'prizepicks', 'power', 9, 3.0, NULL)",
                "('2099-10-01T00:00:00Z', 'prizepicks', 'power', 2, 1.0, NULL)",
                "('2099-10-01T00:00:00Z', 'prizepicks', 'power', 2, NULL, '{}')",
                "('2099-10-01', 'prizepicks', 'power', 2, 3.0, NULL)"):
        with pytest.raises(sqlite3.IntegrityError):
            world.execute("INSERT INTO pickem_payouts_typed (typed_utc, app, entry_type,"
                          f" legs, multiplier, flex_table) VALUES {bad}")
        world.rollback()
    assert world.execute("SELECT COUNT(*) FROM pickem_payouts_typed").fetchone()[0] == 1


def test_an_older_record_gains_the_table_through_init_and_no_row_moves(world, tmp_path):
    """THE RELEASE REACHES THE RECORD THROUGH `db.init` ALONE: a record
    without the payouts-typed table -- every release until this one -- gains
    exactly it, its index and its three rules, as a fresh build has them;
    no stored row moves; a second open adds nothing; and the copy then
    matches a fresh build with no difference (the gate's comparison, its
    register empty). Rehearsed on one verified copy of the record too
    (REPAIR_STATE, "THE ENTRY CHECK, STEP 1 BUILT")."""
    world.execute("DROP TABLE pickem_payouts_typed")
    world.commit()

    def objects(c):
        return {(r[0], r[1]): r[2] for r in c.execute("SELECT type, name, sql FROM sqlite_master")}

    def sums(c):
        return {name: rebuild.column_checksums(c, name) for (kind, name) in objects(c)
                if kind == "table" and not name.startswith("sqlite_")}

    before, rows = objects(world), sums(world)
    db.init(world)
    after = objects(world)
    assert set(after) - set(before) == {
        ("table", "pickem_payouts_typed"), ("index", "pickem_payouts_typed_key"),
        ("trigger", "pickem_payouts_typed_never_replaced"),
        ("trigger", "pickem_payouts_typed_no_update"),
        ("trigger", "pickem_payouts_typed_no_delete")}
    assert all(after[k] == before[k] for k in before)
    moved = sums(world)
    assert {k: v for k, v in moved.items() if k in rows} == rows
    db.init(world)
    assert objects(world) == after
    fresh = db.open_db(tmp_path / "fresh.db")
    try:
        assert schema_diff.compare(world, fresh).differences == []
    finally:
        fresh.close()


# ---------------------------------------------------------------------------
# the form, refused in words
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("change,words", [
    (lambda f: "not a form", "not an entry"),
    (lambda f: dict(f, app=""), "Choose the app: PrizePicks, Underdog or Chalkboard."),
    (lambda f: dict(f, app="sleeper"), "Choose the app"),
    (lambda f: dict(f, entry_type="parlay"), "Choose power or flex."),
    (lambda f: dict(f, legs=f["legs"][:1]), "2 to 8 legs; this one has 1."),
    (lambda f: dict(f, legs=f["legs"] * 5), "2 to 8 legs; this one has 10."),
    (lambda f: dict(f, legs=[dict(f["legs"][0], player=" "), f["legs"][1]]),
     "Leg 1: type the player."),
    (lambda f: dict(f, legs=[f["legs"][0], dict(f["legs"][1], line="two fifty")]),
     "Leg 2: the line 'two fifty' is not a number."),
    (lambda f: dict(f, legs=[f["legs"][0], dict(f["legs"][1], line="")]),
     "Leg 2: type the line"),
    (lambda f: dict(f, legs=[dict(f["legs"][0], side="sideways"), f["legs"][1]]),
     "Leg 1: choose over or under."),
    (lambda f: dict(f, legs=[dict(f["legs"][0], kind="imp"), f["legs"][1]]),
     "Leg 1: choose standard, goblin or demon."),
    (lambda f: dict(f, legs=[dict(f["legs"][0], original_line="250.5"), f["legs"][1]]),
     "the line before a discount is the line itself"),
    (lambda f: dict(f, payout={"multiplier": ""}), "Type what the app pays for this entry."),
    (lambda f: dict(f, payout={"multiplier": "1"}), "returns no more than the entry costs"),
    (lambda f: dict(f, payout={"multiplier": "nan"}), "is not a payout"),
    (lambda f: dict(f, payout={"multiplier": "inf"}), "is not a payout"),
    (lambda f: dict(f, payout={"multiplier": "5000"}), "more than this page reads"),
    (lambda f: dict(f, entry_type="flex", payout={"table": {"2": "1.5", "1": "2"}}),
     "pays less for more legs right"),
    (lambda f: dict(f, entry_type="flex", payout={"table": {"2": "1"}}),
     "with all 2 legs right it returns no more than the entry costs"),
    (lambda f: dict(f, promo={"kind": "raised", "payout": {"multiplier": "2.5"}}),
     "is not higher than the payout"),
    (lambda f: dict(f, promo={"kind": "raised", "payout": {}}),
     "Type what the app pays with the promo."),
    (lambda f: dict(f, promo={"kind": "profit", "percent": "0"}), "share of the winnings"),
    (lambda f: dict(f, promo={"kind": "profit", "percent": "20", "cap_units": "-1"}),
     "the most the promo adds"),
    (lambda f: dict(f, promo={"kind": "deposit match"}), "Choose a promo, or no promo."),
])
def test_a_form_the_check_cannot_read_is_refused_in_words(world, change, words):
    """Every field read and bounded, and a form it cannot read refused in
    words a reader reads -- never an error, never a number, never a write."""
    form = change(_form(TWO, {"multiplier": "3"}))
    out = entry_check.check(world, json.loads(json.dumps(form)), now=NOW, remember_it=True)
    assert out["refused_words"] and words in out["refused_words"], out["refused_words"]
    assert not out["computed"] and out["numbers"] is None and out["signal"] == "none"
    assert audit.entry_check_words_faults(out, "refused") == []
    assert world.execute("SELECT COUNT(*) FROM pickem_payouts_typed").fetchone()[0] == 0


def test_every_word_the_check_sends_is_plain(world):
    """PLAIN WORDS, with the banned list (2026-09-08: "parlay", "same game",
    "boost", "builder", "add leg" and "slip") and the advice list: every
    string the panel and every worked example's answer carries but a code."""
    texts = [entry_check.panel(world, sport="nfl", tiles=[], now=NOW),
             entry_check.panel(world, sport="mlb", tiles=[], now=NOW)]
    for ex in audit.ENTRY_CHECK_WORKED_EXAMPLES:
        texts.append(_check(world, ex["form"]))
    for out in texts:
        assert audit.entry_check_words_faults(out, "entry check") == []
        said = _said(out)
        assert not re.search(r"\bboost|\bsame[- ]game\b|\bparlay|\bslip\b|\bbuilder\b"
                             r"|\badd leg\b|\bbankroll\b", said, re.I), said[:400]


# ---------------------------------------------------------------------------
# the panel on the Props page
# ---------------------------------------------------------------------------

def test_the_panel_is_nfl_only_and_puts_a_marked_prop_in_with_no_line(world):
    """Scope v1, NFL player props only: another sport's page says so. The
    clubs offered are those with a game still to come, by name. A prop the
    operator marked is offered under its player and stat and put in with its
    player, club and stat -- never its line or the model's chance at one:
    the line is the app's, his to type (ruling D), and step 1 has no model."""
    tile = {"taken": True, "state": "upcoming", "player": "Jared Goff",
            "club": {"tricode": "DET"}, "family_words": "passing yards",
            "line_words": "Jared Goff over 250.5 passing yards", "main_chance": 0.64,
            "main_chance_words": "64%", "leg_words": "Jared Goff over 260.5 passing yards"}
    live = dict(tile, state="live", player="Josh Allen")
    unmarked = dict(tile, taken=False, player="Jordan Love")
    panel = entry_check.panel(world, sport="nfl", tiles=[tile, live, unmarked], now=NOW)
    assert panel["open"] and panel["heading"] == "Check an entry"
    assert panel["marked"] == [{"player": "Jared Goff", "club": "DET",
                                "stat": "passing yards",
                                "words": "Jared Goff · passing yards"}]
    assert "250.5" not in _said(panel) and "260.5" not in _said(panel)
    assert "64%" not in _said(panel)
    assert [c["key"] for c in panel["clubs"]] == ["BUF", "DET", "GB", "KC"]
    assert [c["label"] for c in panel["clubs"]] == [
        "Buffalo Bills", "Detroit Lions", "Green Bay Packers", "Kansas City Chiefs"]
    assert [a["label"] for a in panel["apps"]] == ["PrizePicks", "Underdog", "Chalkboard"]
    assert [k["key"] for k in panel["kinds"]] == ["standard", "goblin", "demon"]
    assert [t["key"] for t in panel["types"]] == ["power", "flex"]
    assert panel["flex_rows"]["5"][0] == {"right": 5, "label": "5 of 5 right pays"}
    assert panel["remembered"] == []
    closed = entry_check.panel(world, sport="mlb", tiles=[tile], now=NOW)
    assert closed == {"open": False, "heading": "Check an entry", "closed_words": (
        "Checking an entry is for NFL player props: this first version of the check "
        "reads no other sport.")}


def test_no_payout_table_is_hard_coded_as_fact():
    """LAW 5 (the brief): "No payout table hard-coded as fact: the operator
    types the multiplier or flex table shown in the app". The check's two
    modules hold no multiplier and no table: the numbers in their code are
    the form's bounds, the even chance and the float noise, named."""
    for name in ("entry_check.py", "entry_math.py"):
        tree = ast.parse((ROOT / "gridiron" / name).read_text(encoding="utf-8"))
        numbers = {node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Constant) and type(node.value) in (int, float)}
        # The form's bounds (2 to 8 legs, a payout to 1000x, a line to 10,000,
        # a percent to 1000, units to 100,000, 80 letters, a club's 4), the
        # even chance, the float noise and the bisection's width, a percent's
        # 100, six places kept, a date's first 10 letters, and 0, 1 and 2.
        assert numbers <= {0, 1, 2, 4, 6, 8, 10, 80, 0.0, 0.5, 1.0, 1e-9, 1e-12, 100.0,
                           1000.0, 10000.0, 100000.0}, (name, sorted(numbers))
    assert not hasattr(entry_check, "PAYOUTS") and not hasattr(entry_math, "PAYOUTS")


# ---------------------------------------------------------------------------
# LAW 5: it reaches no app and writes no entry
# ---------------------------------------------------------------------------

def test_the_check_reaches_no_app_and_writes_no_entry(world):
    """The brief's forbidden half: "Gridiron never logs in to, reads, scrapes
    or calls any pick'em app, holds no credential for one, never places or
    edits an entry." The shipped check passes the reach scan; each way out
    planted in a module of its own is named; and a confirmed check writes one
    row, to the payouts typed, and moves no other table."""
    assert audit.entry_check_reach_faults() == []
    faults = audit._entry_check_python_faults
    for code, want in (
            ("URL = 'https://api.prizepicks.com/projections'\n", "names an address"),
            ("HOST = 'stats.underdogfantasy.com'\n", "names an address"),
            ("import urllib.request\n", "imports urllib.request"),
            ("import socket\n", "imports socket"),
            ("import http.client\n", "imports http.client"),
            ("import requests\n", "imports requests"),
            ("from .market import kalshi\n", "imports gridiron.market"),
            ("from . import live\n", "imports gridiron.live"),
            ("def go(u):\n    return __import__('urllib').request.urlopen(u)\n", "calls"),
            ("def go(conn):\n    conn.execute('INSERT INTO picks_taken (prediction_id)"
             " VALUES (1)')\n", "hands SQLite a write"),
            ("def go(conn):\n    conn.execute('INSERT OR REPLACE INTO pickem_payouts_typed"
             " (app) VALUES (1)')\n", "hands SQLite a write")):
        found = faults(code, "planted.py", "gridiron.planted")
        assert any(want in f for f in found), (code, found)
    js = (ROOT / "gridiron" / "web" / "app.js").read_text(encoding="utf-8")
    anchor = "const res = await fetch('/api/entry-check', {"
    assert anchor in js
    for put_back, want in (
            (js.replace(anchor, "const res = await fetch('https://api.prizepicks.com/x', {"),
             "names an address"),
            (js.replace(anchor, "const res = await fetchJSON('/api/projections', {"),
             "sends a request"),
            (js.replace(anchor, "new XMLHttpRequest(); const res = await fetch('/api/entry-check', {"),
             "sends a request")):
        assert any(want in f for f in audit.entry_check_reach_faults(app_js=put_back)), want

    def counts():
        return {r[0]: world.execute(f'SELECT COUNT(*) FROM "{r[0]}"').fetchone()[0]
                for r in world.execute("SELECT name FROM sqlite_master WHERE type = 'table'"
                                       " AND name NOT LIKE 'sqlite_%'")}

    before = counts()
    _check(world, _form(FIVE, {"table": {"5": "10", "4": "2"}}, entry_type="flex",
                        promo={"kind": "raised", "payout": {"table": {"5": "12", "4": "2"}}}),
           remember=True)
    after = counts()
    assert {t for t in after if after[t] != before[t]} == {"pickem_payouts_typed"}
    assert after["pickem_payouts_typed"] - before["pickem_payouts_typed"] == 1


def test_the_law_5_scans_know_the_three_apps_and_an_entrys_verbs(tmp_path):
    """`audit.check_no_venue_credentials` and `check_no_order_path` read the
    entry check's modules as they read every other, and now know Underdog
    and Chalkboard as PrizePicks was known, and an entry's verbs as an
    order's: the shipped tree passes both. (The package only: the settings
    file is handed as one that does not exist -- this test reads no `.env`.)"""
    for app in ("prizepicks", "underdog", "chalkboard"):
        assert app in audit.VENUE_WORDS
        assert app.upper() in audit.VENUE_ENV_PREFIXES
    for verb in ("place_entry", "submit_entry", "edit_entry", "cancel_entry"):
        assert verb in audit.ORDER_PATH_IDENTIFIERS
    audit.check_no_order_path()
    audit.check_no_venue_credentials(env_file=tmp_path / "no.env")


def test_the_record_handle_stays_read_only_and_the_route_has_its_two_locks(world, tmp_path, monkeypatch):
    """The route answers the form; without the form token it refuses; the
    check is handed its own handle, never the interface's read-only one; and
    a body that is not JSON is refused in words."""
    from fastapi.testclient import TestClient

    token = "test-token-for-the-entry-check"
    path = Path(world.execute("PRAGMA database_list").fetchone()[2])
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(path)
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            form = _form(TWO, {"multiplier": "3"})
            refused = client.post("/api/entry-check", json=form)
            assert refused.status_code == 403
            assert "Reload it and try again" in refused.json()["detail"]
            csrf = auth.csrf_token(client.cookies.get(auth.COOKIE_NAME))
            headers = {auth.CSRF_HEADER: csrf}
            got = client.post("/api/entry-check", json=form, headers=headers)
            assert got.status_code == 200, got.text
            answer = got.json()
            assert answer["computed"] and answer["signal"] == "costs"
            assert answer["numbers"]["breakeven"] == pytest.approx(0.577350, abs=1e-6)
            garbled = client.post("/api/entry-check", content=b"not json",
                                  headers=dict(headers, **{"Content-Type": "application/json"}))
            assert garbled.status_code == 200
            assert "not an entry" in garbled.json()["refused_words"]
            assert client.get("/api/entry-check").status_code == 405
    finally:
        api.set_database(None)
    assert world.execute("SELECT COUNT(*) FROM pickem_payouts_typed").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def _step_2_calls(name: str) -> bool:
    gate = ROOT / "tools" / "verify.py"
    step = next(node for node in ast.parse(gate.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    return any(isinstance(node, ast.Attribute) and node.attr == name
               and isinstance(node.value, ast.Name) and node.value.id == "audit"
               for node in ast.walk(step))


def test_the_gate_makes_both_calls_and_the_shipped_check_passes_them():
    assert _step_2_calls("check_the_entry_check_is_its_own_arithmetic")
    assert _step_2_calls("check_the_entry_check_reaches_no_app")
    audit.check_the_entry_check_is_its_own_arithmetic()
    audit.check_the_entry_check_reaches_no_app()


@pytest.mark.parametrize("what,module,name,value,want", [
    ("the power break-even read as one over the payout", "math", "power_breakeven",
     lambda m, n: 1.0 / float(m), "break-even per leg"),
    ("the profit promo applied twice", "math", "with_a_profit_promo", "twice",
     "with the promo"),
    ("the one-game flag never raised", "math", "one_game_groups", lambda games: [],
     "in one game"),
    ("an entry returning exactly its cost outlined red", "math", "costs",
     lambda ev: float(ev) <= 0.0, "the outline is"),
    ("a payout not confirmed worked out anyway", "check", "read_form", "confirmed",
     "did not confirm"),
])
def test_the_gate_names_each_planted_defect(monkeypatch, what, module, name, value, want):
    """The gate's check of the arithmetic, on its own worked examples, names
    each defect the brief's plantings plant (tools/guards/plant.py holds
    them, each escaping on 535c253); a few of them here, quickly."""
    target = entry_math if module == "math" else entry_check
    real = getattr(target, name)
    if value == "twice":
        value = lambda payout, **kw: real(real(payout, **kw), **kw)  # noqa: E731
    elif value == "confirmed":
        value = lambda body: dict(real(body), confirmed=True)  # noqa: E731
    monkeypatch.setattr(target, name, value)
    faults = audit.entry_check_arithmetic_faults()
    assert any(want in f for f in faults), (what, faults[:3])


# ---------------------------------------------------------------------------
# the page, in a real Chromium
# ---------------------------------------------------------------------------
#
# ON A COPY OF THE BROWSER WORLD, served on its own port: a payout confirmed
# here is kept (reading (e)) and a prop is marked, and the shared world is
# left as every other browser test finds it. No clock is read and nothing
# waits a fixed time: every wait is for what the page draws.

@pytest.fixture(scope="module")
def _entry_world(_shared_world, tmp_path_factory):
    from tests import conftest

    target = tmp_path_factory.mktemp("entry-check") / "world.db"
    source = db.read_only(_shared_world["db"],
                          "copying the browser world for the entry check, which keeps a payout")
    copy = db.connect(target)
    source.backup(copy)
    source.close()
    copy.close()
    conn = db.open_db(target)
    base, server, thread = conftest._serve(target)
    yield {"base": base, "db": target, "conn": conn}
    server.should_exit = True
    thread.join(timeout=10)
    conn.close()
    api.set_database(_shared_world["db"])


def _sign_in(world, browser, *, phone: bool):
    """A context signed in to the copy, at 390 (three device pixels to one)
    or 1300 wide."""
    from tests.conftest import SMOKE_TOKEN
    import os

    api.set_database(world["db"])
    os.environ[auth.TOKEN_VAR] = SMOKE_TOKEN
    if phone:
        context = browser.new_context(viewport={"width": 390, "height": 844},
                                      device_scale_factor=3, is_mobile=True, has_touch=True)
    else:
        context = browser.new_context(viewport={"width": 1300, "height": 900})
    page = context.new_page()
    page.page_errors = []
    page.on("pageerror", lambda e: page.page_errors.append(str(e)))
    page.goto(world["base"] + "/login", wait_until="networkidle")
    page.fill("#token", SMOKE_TOKEN)
    page.click("#submit")
    page.wait_for_url(world["base"] + "/", timeout=15000)
    page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
    page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#entry-form .entry-head-row select", timeout=15000)
    return context, page


def _one_game(world):
    """The world's first game still to come, and a player of each club by his
    latest game this season."""
    conn = world["conn"]
    game = conn.execute("SELECT home, away, season FROM games WHERE sport = 'nfl'"
                        " AND status = 'scheduled' ORDER BY kickoff_utc, id LIMIT 1").fetchone()
    def player(club):
        return conn.execute("SELECT player_name FROM player_week_stats WHERE season = ?"
                            " AND team = ? ORDER BY week DESC, player_name LIMIT 1",
                            (game["season"], club)).fetchone()[0]
    return game["home"], player(game["home"]), game["away"], player(game["away"])


def _type_leg(page, i, player, club, line):
    leg = f"#entry-legs .entry-leg >> nth={i}"
    page.fill(f"{leg} >> input >> nth=0", player)
    page.select_option(f"{leg} >> select >> nth=0", club)
    page.fill(f"{leg} >> input >> nth=1", "passing yards")
    page.fill(f"{leg} >> input >> nth=2", str(line))


def _ask(page, multiple, breakeven):
    page.fill("#entry-payout .entry-pays-rows input", str(multiple))
    assert not page.is_checked("#entry-payout .entry-confirm input"), \
        "typing a payout left the box ticked"
    page.check("#entry-payout .entry-confirm input")
    page.click("#entry-check")
    page.wait_for_function(
        "(b) => document.getElementById('entry-lines').textContent.includes(b)",
        arg=breakeven, timeout=10000)
    return page.evaluate("""() => {
        const v = document.querySelector('#entry-lines .verdict');
        return { cls: v ? v.className : null, verdict: v ? v.textContent : null,
                 lines: [...document.querySelectorAll('#entry-lines .entry-line')]
                          .map(r => [r.querySelector('.entry-label').textContent,
                                     r.querySelector('.entry-value').textContent]),
                 said: [...document.querySelectorAll('#entry-lines .entry-said')]
                          .map(p => p.textContent),
                 legs: [...document.querySelectorAll('#entry-lines .entry-read-leg')]
                          .map(r => r.textContent) }; }""")


@pytest.mark.parametrize("width", ["1300", "390"])
def test_the_form_checks_an_entry_and_draws_the_servers_answer(_entry_world, _browser, width):
    """THE PAGE, END TO END: the operator chooses the app, types two legs of
    one game off the app with their clubs, the payout and ticks the box; the
    page asks `/api/entry-check` and draws its answer -- the server's words,
    numbers and outline, nothing composed or worked out in the page -- and
    the three outlines reading (h) gives: 4.5x none, 5x green, 3x red. A
    change to the entry puts the last answer aside; typing a payout unticks
    the box."""
    home, home_player, away, away_player = _one_game(_entry_world)
    context, page = _sign_in(_entry_world, _browser, phone=width == "390")
    try:
        page.select_option("#entry-form .entry-head-row select >> nth=0", "prizepicks")
        _type_leg(page, 0, home_player, home, 250.5)
        _type_leg(page, 1, away_player, away, 60.5)
        legs = [_leg(home_player, home), _leg(away_player, away, line=60.5)]
        for multiple, breakeven, signal, opening in (
                ("4.5", "47.14%", "none", "No outline"),
                ("5", "44.72%", "clears", "Clears the bar at coin flips"),
                ("3", "57.74%", "costs", "Costs at coin flips")):
            drawn = _ask(page, multiple, breakeven)
            server = entry_check.check(_entry_world["conn"],
                                       _form(legs, {"multiplier": multiple}),
                                       remember_it=False)
            assert server["signal"] == signal
            assert drawn["verdict"] == server["verdict_words"] and drawn["verdict"].startswith(opening)
            has = {"clears": "sig-clears", "costs": "sig-costs"}.get(signal)
            assert (has in drawn["cls"]) if has else ("sig-" not in drawn["cls"]), drawn["cls"]
            assert drawn["lines"] == [[l["label"], l["value_words"]] for l in server["lines"]]
            assert drawn["said"] == server["one_game_words"]
            assert drawn["said"][0].startswith("Legs 1 and 2 are in one game")
            assert len(drawn["legs"]) == 2 and all(" at " in leg for leg in drawn["legs"])
        # A CHANGE PUTS THE ANSWER ASIDE.
        page.fill("#entry-legs .entry-leg >> nth=0 >> input >> nth=2", "251.5")
        page.wait_for_function(
            "() => document.getElementById('entry-lines').textContent.startsWith('Changed since')",
            timeout=10000)
        assert not page.query_selector("#entry-lines .verdict")
        assert not page.page_errors, page.page_errors
    finally:
        context.close()


def test_the_last_payout_confirmed_is_offered_filled_in_and_unticked(_entry_world, _browser):
    """READING (e): "the last one typed per app and entry size is offered as
    a default and must be confirmed". A 2-leg PrizePicks power entry checked
    at 3.5x with the box ticked keeps 3.5x; on the next visit, once the app,
    entry type and size are his, the field holds 3.5 with the box unticked
    and the words saying when it was typed; checked without the tick, the
    page asks him to confirm and works nothing out; another size offers
    nothing."""
    home, home_player, away, away_player = _one_game(_entry_world)
    context, page = _sign_in(_entry_world, _browser, phone=False)
    try:
        page.select_option("#entry-form .entry-head-row select >> nth=0", "prizepicks")
        _type_leg(page, 0, home_player, home, 250.5)
        _type_leg(page, 1, away_player, away, 60.5)
        _ask(page, "3.5", "53.45%")
        page.wait_for_function(
            "() => document.getElementById('entry-lines').textContent"
            ".includes('Remembered for PrizePicks 2-pick power: 3.5x')", timeout=10000)
    finally:
        context.close()
    kept = [r for r in entry_check.remembered(_entry_world["conn"])
            if (r["app"], r["entry_type"], r["legs"]) == ("prizepicks", "power", 2)]
    assert [r["fields"] for r in kept] == [{"multiplier": "3.5"}]
    context, page = _sign_in(_entry_world, _browser, phone=False)
    try:
        payout, box = "#entry-payout .entry-pays-rows input", "#entry-payout .entry-confirm input"
        assert page.input_value(payout) == "", "a payout filled in before an app was chosen"
        page.select_option("#entry-form .entry-head-row select >> nth=0", "prizepicks")
        page.wait_for_function(f"() => document.querySelector('{payout}').value === '3.5'",
                               timeout=10000)
        assert not page.is_checked(box)
        offered = page.text_content("#entry-offered")
        assert offered.startswith("Last typed for PrizePicks 2-pick power, ") and "3.5x" in offered
        _type_leg(page, 0, home_player, home, 250.5)
        _type_leg(page, 1, away_player, away, 60.5)
        page.click("#entry-check")
        page.wait_for_function(
            "() => document.getElementById('entry-lines').textContent"
            ".includes('Confirm what the app pays for this entry')", timeout=10000)
        assert not page.query_selector("#entry-lines .verdict")
        assert not page.query_selector("#entry-lines .entry-line")
        page.select_option("#entry-form .entry-head-row select >> nth=1", "flex")
        page.wait_for_function(
            f"() => [...document.querySelectorAll('{payout}')].every(i => i.value === '')",
            timeout=10000)
        assert page.is_hidden("#entry-offered")
        assert not page.page_errors, page.page_errors
    finally:
        context.close()


def test_a_marked_prop_is_put_in_with_no_line_and_every_tap_target_is_44px_at_390(_entry_world, _browser):
    """A prop the operator marks on its tile is offered in the entry under its
    player and stat, and put in with its player, club and stat -- the line is
    left for him to type. And at 390, three device pixels to one, at rest,
    with every field the check can draw on screen -- a marked prop's button,
    a flex table of three rows, a raised table, a promo's three fields -- and
    its whole answer: every tap target 44px or more tall in whole pixels and
    44px or more wide (the board merge's floor; nothing rounded or widened)."""
    from tests.test_smoke import _AT_REST, _MEASURE_THE_TARGETS, SLATE_TAP_TARGETS

    context, page = _sign_in(_entry_world, _browser, phone=True)
    try:
        page.wait_for_selector("#props-tiles .prop[data-state='upcoming'] .chk", timeout=15000)
        with page.expect_response(lambda r: "/api/taken/" in r.url, timeout=20000):
            page.click("#props-tiles .prop[data-state='upcoming'] .chk >> nth=0")
        page.wait_for_selector("#entry-marked .entry-put", timeout=15000)
        words = page.text_content("#entry-marked .entry-put")
        player, stat = words.split(" · ")
        page.click("#entry-marked .entry-put")
        page.wait_for_function(
            "(p) => document.querySelector('#entry-legs .entry-leg input').value === p",
            arg=player, timeout=10000)
        first = "#entry-legs .entry-leg >> nth=0"
        assert page.input_value(f"{first} >> input >> nth=1") == stat
        assert page.input_value(f"{first} >> select >> nth=0") != ""
        assert page.input_value(f"{first} >> input >> nth=2") == ""
        heads = "#entry-form .entry-head-row select"
        page.select_option(f"{heads} >> nth=0", "underdog")
        page.select_option(f"{heads} >> nth=1", "flex")
        page.click("#entry-more")
        page.wait_for_function(
            "() => document.querySelectorAll('#entry-legs .entry-leg').length === 3",
            timeout=10000)
        for i in range(3):
            leg = f"#entry-legs .entry-leg >> nth={i} >> input"
            if i:
                page.fill(f"{leg} >> nth=0", f"A Player {i}")
                page.fill(f"{leg} >> nth=1", stat)
            page.fill(f"{leg} >> nth=2", "4.5")
        rows = "#entry-payout .entry-pays-rows input"
        for i, value in enumerate(("6", "1.5", "")):
            page.fill(f"{rows} >> nth={i}", value)
        page.select_option("#entry-promo select", "raised")
        page.wait_for_function(
            "() => document.querySelectorAll('#entry-promo input').length === 3", timeout=10000)
        for i, value in enumerate(("7", "1.5", "")):
            page.fill(f"#entry-promo input >> nth={i}", value)
        page.check("#entry-payout .entry-confirm input")
        page.click("#entry-check")
        page.wait_for_selector("#entry-lines .verdict", timeout=10000)
        said = page.text_content("#entry-lines")
        assert "With the promo: 3 of 3 right pays 7x, 2 of 3 right pays 1.5x" in said
        page.wait_for_function(_AT_REST, timeout=15000)
        got = page.evaluate(_MEASURE_THE_TARGETS, SLATE_TAP_TARGETS)
        assert got["measured"] > 20 and not got["small"], got["small"][:20]
        page.select_option("#entry-promo select", "profit")
        page.wait_for_function(
            "() => document.querySelectorAll('#entry-promo input').length === 3"
            " && document.getElementById('entry-lines').textContent.startsWith('Changed since')",
            timeout=10000)
        page.wait_for_function(_AT_REST, timeout=15000)
        got = page.evaluate(_MEASURE_THE_TARGETS, SLATE_TAP_TARGETS)
        assert got["measured"] > 20 and not got["small"], got["small"][:20]
        # NOTHING IN THE RAIL IS WIDER THAN THE PHONE.
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        assert not page.page_errors, page.page_errors
    finally:
        context.close()
