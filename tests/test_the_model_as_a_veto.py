"""Check an entry, step 2: the model as a veto (GRIDIRON_ENTRY_CHECK; the brief
of 2026-09-30, docs/briefs/2026-09-30-entry-check.md, with ruling D of
2026-10-05, docs/briefs/2026-10-05-rulings.md; built 2026-10-07).

The brief, step 2: "the model as a veto: each leg's model probability at the
typed line if the model forecasts that player and stat; at a discounted line
only if the model can state a probability at any line, otherwise 'can't
price this discount'. Show model EV beside coin-flip EV and flag legs below
their break-even, with the model's record for that stat in plain words. The
model only flags; it never raises a verdict." Ruling D: "Step 2 needs the
model's chance at any line: a first version of M4, P(stat over x) from the
model's projection and a per-stat spread fitted on settled history. Written
inactive; shown as 'not yet proven' until its record clears 100 graded legs."

EVERY NUMBER BELOW IS WORKED BY HAND in its test (2026-10-07), never read back
off the code: a Poisson tail in closed form (mean 1.5: over 1.5 is
1 - 2.5e^-1.5; over 0.5 is 1 - e^-1.5; mean 2: over 1.5 is 1 - 3e^-2), a
negative binomial of mean 6 and spread 1.5 by its terms (r = 12, p = 2/3: 4 or
fewer is the sum over k of C(k+11, k) (2/3)^12 (1/3)^k), the spread as the
mean of (actual - projection)^2 / projection, a power entry's return at the
model's chances as M times their product less one, and a flex table's as the
chance of each count right, by every way of it, times its row. Each test fails
on 6395fb4, which has no M4 (the module, its table and its words are new),
and the browser test fails there on the words it reads.
"""
from __future__ import annotations

import json
import math
import shutil
import sqlite3
from pathlib import Path

import pytest

from gridiron import audit, board, db, entry_check, language, m4, rebuild, schema_diff

ROOT = Path(__file__).resolve().parents[1]

#: The clock the examples are asked at, and the fit's instant.
NOW = "2099-10-01T00:00:00Z"
FITTED = "2099-09-30T00:00:00Z"
UNPROVEN = "not yet proven · 0 of 100 graded legs"

E15 = math.exp(-1.5)
E2 = math.exp(-2.0)
#: A negative binomial of mean 6 and spread 1.5: r = 12, p = 2/3, by its terms.
NB6_LE4 = sum(math.comb(k + 11, k) * (2 / 3) ** 12 * (1 / 3) ** k for k in range(5))


# ---------------------------------------------------------------------------
# the world: a played game's settled forecasts, and the forecasts to come
# ---------------------------------------------------------------------------

def _forecast(conn, gid, pid, name, stat, line, side, projection, *, created,
              pass_kind="final", settled=None):
    payload = {"coverage": 1.0, "question": {"player_id": pid, "stat": stat}}
    if projection is not None:
        payload["expected_count"] = projection
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, prop_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES (?, 'nfl', ?, 'prop', ?, ?,"
        " ?, 0.6, ?, 'statistical', ?, 'fs2', ?, 'test')",
        (created, gid, stat, f"{name} {stat}", line, side, pass_kind, json.dumps(payload)))
    fid = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    if settled is not None:
        conn.execute("UPDATE predictions SET resolved_utc = '2099-09-28T00:00:00Z',"
                     " outcome = ? WHERE id = ?", (settled, fid))
    return fid


def _world(conn, *, fit=True):
    """Detroit played Kansas City on 27 September 2099 (week 4); Green Bay at
    Detroit and Kansas City at Buffalo are to come on 11 October (week 5).
    Settled: Amon-Ra St. Brown's receptions projected 4.0, he caught 6;
    Davante Adams's projected 2.0, he caught 4; Patrick Mahomes's passing
    touchdowns projected 2.0, he threw 3; Jared Goff's projected 2.0, he
    threw 1. To come: St. Brown's receptions (an early pass projecting 9.9
    and a final pass projecting 6.0), Goff's passing yards (no projection),
    Jordan Love's passing touchdowns (2.0) and Mahomes's (1.5)."""
    for code, name in (("DET", "Detroit Lions"), ("GB", "Green Bay Packers"),
                       ("BUF", "Buffalo Bills"), ("KC", "Kansas City Chiefs")):
        conn.execute(
            "INSERT INTO teams (sport, tricode, display_name, short_name, location,"
            " source_url, fetched_utc) VALUES ('nfl', ?, ?, ?, ?, 'test',"
            " '2099-09-01T00:00:00Z')", (code, name, name.split()[-1], name))
    for gid, home, away, start, week, status, hs, as_ in (
            ("w_played", "DET", "KC", "2099-09-27T17:00:00Z", 4, "final", 24, 20),
            ("w_gb_det", "DET", "GB", "2099-10-11T17:00:00Z", 5, "scheduled", None, None),
            ("w_kc_buf", "BUF", "KC", "2099-10-11T20:25:00Z", 5, "scheduled", None, None)):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc, league_date,"
            " home, away, status, home_score, away_score) VALUES (?, 'nfl', 2099, ?, 'REG',"
            " ?, ?, ?, ?, ?, ?, ?)", (gid, week, start, start[:10], home, away, status, hs, as_))
    for pid, name, club, rec, tds in (
            ("p-stb", "Amon-Ra St. Brown", "DET", 6, None), ("p-da", "Davante Adams", "KC", 4, None),
            ("p-pm", "Patrick Mahomes", "KC", None, 3), ("p-goff", "Jared Goff", "DET", None, 1),
            ("p-love", "Jordan Love", "GB", None, None), ("p-allen", "Josh Allen", "BUF", None, None)):
        conn.execute(
            "INSERT INTO player_week_stats (season, week, player_id, player_name, position,"
            " team, opponent, receptions, passing_tds) VALUES (2099, 4, ?, ?, 'WR', ?, 'BUF',"
            " ?, ?)", (pid, name, club, rec, tds))
    settled = "2099-09-26T12:00:00Z"
    ids = {
        "stb_settled": _forecast(conn, "w_played", "p-stb", "Amon-Ra St. Brown", "receptions",
                                 5.5, "over", 4.0, created=settled, settled=1),
        "da_settled": _forecast(conn, "w_played", "p-da", "Davante Adams", "receptions",
                                2.5, "over", 2.0, created=settled, settled=1),
        "pm_settled": _forecast(conn, "w_played", "p-pm", "Patrick Mahomes", "passing_tds",
                                1.5, "over", 2.0, created=settled, settled=1),
        "goff_settled": _forecast(conn, "w_played", "p-goff", "Jared Goff", "passing_tds",
                                  1.5, "over", 2.0, created=settled, settled=0),
        "stb_early": _forecast(conn, "w_gb_det", "p-stb", "Amon-Ra St. Brown", "receptions",
                               5.5, "over", 9.9, created="2099-09-30T12:00:00Z",
                               pass_kind="early"),
        "stb_final": _forecast(conn, "w_gb_det", "p-stb", "Amon-Ra St. Brown", "receptions",
                               5.5, "over", 6.0, created="2099-09-30T18:00:00Z"),
        "goff_yards": _forecast(conn, "w_gb_det", "p-goff", "Jared Goff", "passing_yards",
                                250.5, "over", None, created="2099-09-30T18:00:00Z"),
        "love": _forecast(conn, "w_gb_det", "p-love", "Jordan Love", "passing_tds", 1.5,
                          "over", 2.0, created="2099-09-30T18:00:00Z"),
        "pm": _forecast(conn, "w_kc_buf", "p-pm", "Patrick Mahomes", "passing_tds", 1.5,
                        "over", 1.5, created="2099-09-30T18:00:00Z"),
    }
    conn.commit()
    if fit:
        m4.refit(conn, write=True, now=FITTED)
    return ids


@pytest.fixture
def world(conn):
    _world(conn)
    return conn


def _leg(player, club, stat, line, *, side="over", original=""):
    return {"player": player, "club": club, "stat": stat, "line": str(line), "side": side,
            "kind": "standard", "original_line": original}


def _form(legs, payout, *, entry_type="power", promo=None):
    return {"app": "prizepicks", "entry_type": entry_type, "legs": legs, "payout": payout,
            "payout_confirmed": True, "promo": promo or {"kind": "none"}}


STB = _leg("Amon-Ra St. Brown", "DET", "receptions", 4.5)
PM = _leg("Patrick Mahomes", "KC", "passing touchdowns", 1.5)
PM_UNDER = _leg("Patrick Mahomes", "KC", "passing touchdowns", 1.5, side="under")
LOVE = _leg("Jordan Love", "GB", "passing touchdowns", 1.5)


def _check(conn, form):
    return entry_check.check(conn, json.loads(json.dumps(form)), now=NOW, remember_it=False)


def _chances(out):
    return [leg["chance"] for leg in out["model"]["numbers"]["legs"]]


# ---------------------------------------------------------------------------
# M4: the chance at a line, from the projection and a spread
# ---------------------------------------------------------------------------

def test_the_chance_at_a_line_is_a_count_about_the_projection_worked_by_hand():
    """A spread of one or less is a Poisson about the projection; above one a
    negative binomial whose variance is the spread times the projection. Over
    a line is strictly over it, under strictly under, and a whole-number line
    can be landed on exactly, which is neither."""
    assert m4.chance_over(1.5, 1.5, 0.5) == pytest.approx(1 - 2.5 * E15, abs=1e-12)
    assert m4.chance_over(1.5, 0.5, 1.0) == pytest.approx(1 - E15, abs=1e-12)
    assert m4.chance_under(1.5, 1.5, 0.5) == pytest.approx(2.5 * E15, abs=1e-12)
    assert m4.chance_over(2.0, 1.5, 0.9) == pytest.approx(1 - 3 * E2, abs=1e-12)
    # A WHOLE LINE: over 2 is 3 or more, under 2 is 1 or fewer, and 2 itself
    # (1.125e^-1.5) is neither.
    over, under = m4.chance_over(1.5, 2, 0.5), m4.chance_under(1.5, 2, 0.5)
    assert over == pytest.approx(1 - 3.625 * E15, abs=1e-12)
    assert under == pytest.approx(2.5 * E15, abs=1e-12)
    assert 1 - over - under == pytest.approx(1.125 * E15, abs=1e-12)
    # THE NEGATIVE BINOMIAL OF MEAN 6 AND SPREAD 1.5.
    assert NB6_LE4 == pytest.approx(0.339123, abs=1e-6)
    assert m4.chance_over(6.0, 4.5, 1.5) == pytest.approx(1 - NB6_LE4, abs=1e-12)
    assert m4.chance_under(6.0, 5, 1.5) == pytest.approx(NB6_LE4, abs=1e-12)
    assert m4.chance_on_side(6.0, 4.5, "under", 1.5) == pytest.approx(NB6_LE4, abs=1e-12)
    with pytest.raises(ValueError):
        m4.chance_on_side(6.0, 4.5, "sideways", 1.5)
    # THE DECLARED FORM, ONCE, DATED.
    assert m4.FORM == "count_about_the_projection"
    assert m4.FORM_DECLARED == "2026-10-07T00:00:00Z"


def test_the_spread_is_fitted_on_settled_history_by_the_arithmetic_declared(conn):
    """Receptions: (6-4)^2/4 = 1 and (4-2)^2/2 = 2, mean 1.5. Passing
    touchdowns: (3-2)^2/2 = 0.5 and (1-2)^2/2 = 0.5, mean 0.5. A forecast
    still to come is not in it, a yardage stat stores no projection and is
    never fitted, a second rung of one player's game is that game once, and a
    withdrawn forecast is never in it."""
    ids = _world(conn, fit=False)
    # A SECOND RUNG OF ST. BROWN'S SETTLED GAME (an early pass asked at 3.5,
    # another question on the distinct-bet key, standing beside the final
    # pass at 5.5), and a WITHDRAWN settled forecast of another player:
    # neither moves the fit.
    _forecast(conn, "w_played", "p-stb", "Amon-Ra St. Brown", "receptions", 3.5, "over", 4.0,
              created="2099-09-26T11:00:00Z", pass_kind="early", settled=1)
    conn.execute("INSERT INTO player_week_stats (season, week, player_id, player_name,"
                 " position, team, opponent, receptions) VALUES (2099, 4, 'p-x', 'X Wing',"
                 " 'WR', 'KC', 'DET', 20)")
    voided = _forecast(conn, "w_played", "p-x", "X Wing", "receptions", 2.5, "over", 1.0,
                       created="2099-09-26T12:00:00Z", settled=1)
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason) VALUES"
                 " (?, '2099-09-29T00:00:00Z', 'a test of a withdrawn forecast left out')",
                 (voided,))
    conn.commit()
    report = {r["stat"]: r for r in m4.refit(conn, now=FITTED)}
    assert list(report) == ["receptions", "passing_tds"]
    assert report["receptions"]["spread"] == pytest.approx(1.5, abs=1e-12)
    assert report["receptions"]["n"] == 2
    assert report["passing_tds"]["spread"] == pytest.approx(0.5, abs=1e-12)
    assert report["passing_tds"]["forecasts"] == [ids["pm_settled"], ids["goff_settled"]]
    assert ids["da_settled"] in report["receptions"]["forecasts"]
    assert m4.stats_it_can_fit("nfl") == ("receptions", "passing_tds")
    assert m4.stats_it_can_fit("mlb") == ()
    # DRY: nothing written.
    assert conn.execute("SELECT COUNT(*) FROM prop_spread_fits").fetchone()[0] == 0


def test_a_fit_is_written_inactive_once_and_is_append_only(conn):
    """Each stat's fit is one dated row; the same rows and spread are not
    written again; a row is never edited, deleted or written over; and no
    table holds an activation of one (ruling D: "Written inactive")."""
    _world(conn, fit=False)
    first = m4.refit(conn, write=True, now=FITTED)
    assert [bool(r["written"]) for r in first] == [True, True]
    again = m4.refit(conn, write=True, now=NOW)
    assert [r["written"] for r in again] == [None, None]
    rows = conn.execute("SELECT stat, spread, n, form, form_declared, fitted_utc, method"
                        " FROM prop_spread_fits ORDER BY id").fetchall()
    assert [(r["stat"], round(r["spread"], 12), r["n"]) for r in rows] == [
        ("receptions", 1.5, 2), ("passing_tds", 0.5, 2)]
    assert all(r["fitted_utc"] == FITTED and r["form_declared"] == m4.FORM_DECLARED
               for r in rows)
    for statement in ("UPDATE prop_spread_fits SET spread = 2.0",
                      "DELETE FROM prop_spread_fits",
                      "INSERT INTO prop_spread_fits (id, fitted_utc, sport, stat, form,"
                      " form_declared, spread, n, forecasts, method) VALUES (1,"
                      " '2099-10-01T00:00:00Z', 'nfl', 'receptions',"
                      " 'count_about_the_projection', '2026-10-07T00:00:00Z', 2.0, 1, '[1]',"
                      " 'written over the first fit, which is refused')"):
        with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
            conn.execute(statement)
        conn.rollback()
    for bad in ("('2099-10-01', 'nfl', 'receptions', 'count_about_the_projection',"
                " '2026-10-07', 1.2, 1, '[1]', 'a day with no time is refused here')",
                "('2099-10-01T00:00:00Z', 'nfl', 'receptions', 'another_form',"
                " '2026-10-07', 1.2, 1, '[1]', 'a form never declared is refused here')",
                "('2099-10-01T00:00:00Z', 'nfl', 'receptions', 'count_about_the_projection',"
                " '2026-10-07', 0.0, 1, '[1]', 'no spread at all is refused here')",
                "('2099-10-01T00:00:00Z', 'nfl', 'receptions', 'count_about_the_projection',"
                " '2026-10-07', 1.2, 2, '[1]', 'a count that is not its forecasts')"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO prop_spread_fits (fitted_utc, sport, stat, form,"
                         f" form_declared, spread, n, forecasts, method) VALUES {bad}")
        conn.rollback()
    assert [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND sql LIKE '%prop_spread_fits%'"
    )] == ["prop_spread_fits"]


def test_an_older_record_gains_the_fit_table_through_init_and_no_row_moves(conn, tmp_path):
    """THE RELEASE REACHES THE RECORD THROUGH `db.init` ALONE: a record without
    the fit table -- every release until this one -- gains exactly it, its
    index and its three rules, as a fresh build has them; no stored row
    moves; a second open adds nothing; and the copy then matches a fresh
    build with no difference. Rehearsed on one verified copy of the record
    too (REPAIR_STATE, "THE ENTRY CHECK, STEP 2 BUILT")."""
    _world(conn, fit=False)
    # THE WORLD'S FORECASTS ARE WRITTEN BY HAND, so `db.init` first gives each
    # its fingerprint, as every forecast on the record has one; then the
    # record as every release until this one left it.
    db.init(conn)
    conn.execute("DROP TABLE prop_spread_fits")
    conn.commit()

    def objects(c):
        return {(r[0], r[1]): r[2] for r in c.execute("SELECT type, name, sql FROM sqlite_master")}

    def sums(c):
        return {name: rebuild.column_checksums(c, name) for (kind, name) in objects(c)
                if kind == "table" and not name.startswith("sqlite_")}

    before, rows = objects(conn), sums(conn)
    db.init(conn)
    after = objects(conn)
    assert set(after) - set(before) == {
        ("table", "prop_spread_fits"), ("index", "prop_spread_fits_stat"),
        ("trigger", "prop_spread_fits_never_replaced"),
        ("trigger", "prop_spread_fits_no_update"), ("trigger", "prop_spread_fits_no_delete")}
    assert all(after[k] == before[k] for k in before)
    assert {k: v for k, v in sums(conn).items() if k in rows} == rows
    db.init(conn)
    assert objects(conn) == after
    fresh = db.open_db(tmp_path / "fresh.db")
    try:
        assert schema_diff.compare(conn, fresh).differences == []
    finally:
        fresh.close()


def test_a_leg_is_read_from_the_standing_forecast_of_its_player_and_stat(conn):
    """The statistical model's standing forecast of the player and stat in the
    leg's game, through the one clause: St. Brown's final pass (6.0), never
    his early pass (9.9); with the final pass withdrawn, the early pass."""
    ids = _world(conn)
    got = m4.reading(conn, game_id="w_gb_det", player_id="p-stb", stat="receptions",
                     line=4.5, side="over")
    assert got["forecast_id"] == ids["stb_final"] and got["projection"] == 6.0
    assert got["state"] == "priced" and got["chance"] == pytest.approx(1 - NB6_LE4, abs=1e-12)
    conn.execute("INSERT INTO prediction_voids (prediction_id, voided_utc, reason) VALUES"
                 " (?, '2099-09-30T19:00:00Z', 'a test of a withdrawn final pass')",
                 (ids["stb_final"],))
    conn.commit()
    got = m4.reading(conn, game_id="w_gb_det", player_id="p-stb", stat="receptions",
                     line=4.5, side="over")
    assert got["forecast_id"] == ids["stb_early"] and got["projection"] == 9.9
    # NO FORECAST OF THE PLAYER IN THAT GAME, and no projection stored.
    assert m4.reading(conn, game_id="w_kc_buf", player_id="p-stb", stat="receptions",
                      line=4.5, side="over")["state"] == "no_forecast"
    assert m4.reading(conn, game_id="w_gb_det", player_id="p-goff", stat="passing_yards",
                      line=240.5, side="over")["state"] == "no_projection"


# ---------------------------------------------------------------------------
# the veto in the entry check
# ---------------------------------------------------------------------------

def test_each_leg_is_read_at_its_typed_line_and_flagged_under_its_breakeven(world):
    """6x on three legs breaks even at 6^(-1/3) = 55.03% a leg. St. Brown over
    4.5 receptions: 1 - 0.339123 = 66.09%, 11.06 points over. Mahomes over 1.5
    passing touchdowns: 1 - 2.5e^-1.5 = 44.22%, 10.81 under: FLAGGED. Love
    over 1.5: 1 - 3e^-2 = 59.40%, 4.37 over."""
    out = _check(world, _form([STB, PM, LOVE], {"multiplier": "6"}))
    be = 6 ** (-1 / 3)
    want = [1 - NB6_LE4, 1 - 2.5 * E15, 1 - 3 * E2]
    assert _chances(out) == pytest.approx(want, abs=1e-6)
    assert [leg["flag"] for leg in out["model"]["numbers"]["legs"]] == [False, True, False]
    assert out["model"]["numbers"]["flagged"] == [1]
    legs = out["model"]["legs"]
    assert legs[1]["lean_words"] == "The model leans against this leg."
    assert legs[0]["lean_words"] is None and legs[2]["lean_words"] is None
    assert legs[0]["model_words"] == (
        f"The model: 66.09% over 4.5, from its projection of 6.00 receptions ({UNPROVEN}).")
    assert legs[1]["model_gap_words"] == (
        f"By the model, this leg is 10.81 points under its break-even ({UNPROVEN}).")
    assert [round(want[i] - be, 4) for i in range(3)] == [
        round(leg["edge"], 4) for leg in out["model"]["numbers"]["legs"]]
    assert out["model"]["summary_words"].startswith(
        f"The model leans against leg 2 ({UNPROVEN}).")


def test_the_model_never_raises_a_verdict(conn):
    """4.5x on two legs is 2.86 points under the bar at coin flips -- no
    outline -- and the model gives the legs 66.09% and 55.78% (under 1.5:
    2.5e^-1.5), 18.95 and 8.64 points over 47.14%: still no outline. 6x on
    three legs costs at coin flips (-0.25) and returns +0.041 at the model's
    chances: still red. The verdict is the same with the model and without
    it (no fit), word for word."""
    _world(conn, fit=False)
    without = [_check(conn, _form([STB, PM_UNDER], {"multiplier": "4.5"})),
               _check(conn, _form([STB, PM, LOVE], {"multiplier": "6"}))]
    m4.refit(conn, write=True, now=FITTED)
    with_it = [_check(conn, _form([STB, PM_UNDER], {"multiplier": "4.5"})),
               _check(conn, _form([STB, PM, LOVE], {"multiplier": "6"}))]
    assert [o["signal"] for o in with_it] == ["none", "costs"]
    for a, b in zip(without, with_it):
        assert (a["signal"], a["verdict_words"]) == (b["signal"], b["verdict_words"])
        assert [line for line in b["lines"] if not line.get("model")] == a["lines"]
    nb = with_it[0]["model"]["numbers"]
    assert nb["flagged"] == [] and all(leg["edge"] > 0.03 for leg in nb["legs"])
    assert with_it[1]["model"]["numbers"]["expected"] == pytest.approx(
        6 * (1 - NB6_LE4) * (1 - 2.5 * E15) * (1 - 3 * E2) - 1, abs=1e-6)
    assert with_it[1]["model"]["numbers"]["expected"] > 0
    # NOTHING A PICK OR A VERDICT CARRIES, in the model's part.
    said = json.dumps([o["model"] for o in with_it])
    for key in ('"signal"', '"pick"', '"pick_words"', '"clears"', '"badge_words"'):
        assert key not in said
    assert "never changes it" in with_it[0]["model"]["summary_words"]


def test_a_discount_is_priced_only_where_the_model_states_a_chance(world):
    """Mahomes over 0.5 passing touchdowns, discounted from 1.5: 1 - e^-1.5 =
    77.69% at 0.5 and 44.22% before the discount. Goff over 240.5 passing
    yards, discounted from 250.5 -- the model's own question asked at 250.5,
    no projection stored: "Can't price this discount." and no chance."""
    out = _check(world, _form([_leg("Patrick Mahomes", "KC", "passing touchdowns", 0.5,
                                    original="1.5"),
                               _leg("Jared Goff", "DET", "passing yards", 240.5,
                                    original="250.5")], {"multiplier": "3"}))
    nums = out["model"]["numbers"]["legs"]
    assert nums[0]["chance"] == pytest.approx(1 - E15, abs=1e-6)
    assert nums[0]["chance_before"] == pytest.approx(1 - 2.5 * E15, abs=1e-6)
    assert out["model"]["legs"][0]["discount_words"] == (
        f"Before the discount, at over 1.5, the model gives it 44.22% ({UNPROVEN}).")
    assert nums[1]["state"] == "no_projection" and nums[1]["chance"] is None
    assert nums[1]["chance_before"] is None
    assert out["model"]["legs"][1]["discount_words"] == "Can't price this discount."
    assert out["model"]["legs"][1]["model_words"] == (
        "The model has no projection for passing yards yet, so it states no chance at "
        "your line.")
    assert out["model"]["numbers"]["expected"] is None
    assert out["model"]["return_missing_words"] == (
        "The return at the model's chances needs its chance on every leg: leg 2 has none.")
    # ONE LEG PRICED, said of one leg (the render of 2026-10-07).
    assert out["model"]["summary_words"] == (
        f"The model does not lean against the one leg it can price ({UNPROVEN}). Leg 2 has "
        f"no chance from it. It only flags: the verdict above is the arithmetic at coin "
        f"flips, and the model never changes it.")


def test_legs_the_model_says_nothing_of_say_why(conn):
    """No forecast of the player and stat in the game; a stat the model does
    not forecast (an app's abbreviation, never guessed); a leg not placed; a
    stat with a projection but nothing fitted yet."""
    _world(conn, fit=False)
    out = _check(conn, _form([_leg("Josh Allen", "BUF", "receptions", 1.5),
                              _leg("Jordan Love", "GB", "Pass TDs", 1.5),
                              _leg("Nobody Atall", "KC", "receptions", 3.5),
                              _leg("Amon-Ra St. Brown", "DET", "Receptions", 4.5)],
                             {"multiplier": "10"}))
    states = [leg["state"] for leg in out["model"]["numbers"]["legs"]]
    assert states == ["no_forecast", "not_a_stat", "unplaced", "no_fit"]
    words = [leg["model_words"] for leg in out["model"]["legs"]]
    assert words[0] == ("The model made no forecast of Josh Allen's receptions for this game, "
                        "so it says nothing of this leg.")
    assert words[1] == ("The model forecasts no stat it can match to “Pass TDs”: "
                        "choose one of the stats offered to ask it.")
    assert words[2] == "This leg was not placed in a game, so the model was not asked."
    assert words[3].startswith("Nothing has been fitted yet for how far receptions stray")
    assert out["model"]["summary_words"] == (
        "The model states a chance on none of these legs, so it flags nothing.")
    assert entry_check.stat_of("Passing Touchdowns") == "passing_tds"
    assert entry_check.stat_of("passing_tds") == "passing_tds"
    assert entry_check.stat_of("Pass Yds") is None


def test_the_return_at_the_models_chances_stands_beside_the_coin_flips(world):
    """POWER: 4.5 x 0.660877 x 0.557825 - 1 = +0.658942, beside +0.125 at coin
    flips. FLEX, 3 right pays 2.25x and 2 right 1.25x, the legs at a, b, c:
    2.25abc + 1.25(ab(1-c) + a(1-b)c + (1-a)bc) - 1 = +0.037227, beside -0.25.
    A RAISED PAYOUT, 3x to 3.5x: 3ab - 1 = -0.123331 and 3.5ab - 1 = +0.022780,
    each beside its coin flips, and each leg read against 53.45%, the
    break-even of the entry as offered."""
    a, b_under, c = 1 - NB6_LE4, 2.5 * E15, 1 - 3 * E2
    b_over = 1 - 2.5 * E15
    power = _check(world, _form([STB, PM_UNDER], {"multiplier": "4.5"}))
    assert power["model"]["numbers"]["expected"] == pytest.approx(4.5 * a * b_under - 1, abs=1e-6)
    labels = [line["label"] for line in power["lines"]]
    at = labels.index("At coin flips, per unit")
    assert labels[at + 1] == f"With the model's chances, per unit ({UNPROVEN})"
    assert power["lines"][at + 1]["value_words"] == "+0.65894 per unit"
    flex = _check(world, _form([STB, PM_UNDER, LOVE], {"table": {"3": "2.25", "2": "1.25"}},
                               entry_type="flex"))
    two = a * b_under * (1 - c) + a * (1 - b_under) * c + (1 - a) * b_under * c
    assert flex["model"]["numbers"]["expected"] == pytest.approx(
        2.25 * a * b_under * c + 1.25 * two - 1, abs=1e-6)
    raised = _check(world, _form([STB, PM], {"multiplier": "3"},
                                 promo={"kind": "raised", "payout": {"multiplier": "3.5"}}))
    nums = raised["model"]["numbers"]
    assert nums["expected"] == pytest.approx(3 * a * b_over - 1, abs=1e-6)
    assert nums["offered_expected"] == pytest.approx(3.5 * a * b_over - 1, abs=1e-6)
    assert [leg["edge"] for leg in nums["legs"]] == pytest.approx(
        [a - 3.5 ** -0.5, b_over - 3.5 ** -0.5], abs=1e-6)
    assert nums["flagged"] == [1]
    labels = [line["label"] for line in raised["lines"]]
    assert labels[labels.index("At coin flips with the promo") + 1] == (
        f"With the model's chances and the promo, per unit ({UNPROVEN})")
    assert raised["model"]["legs"][1]["model_gap_words"].endswith(
        f"under its break-even with the promo ({UNPROVEN}).")


def test_every_model_number_is_drawn_not_yet_proven_with_its_count(world):
    """Ruling D: "shown as 'not yet proven' until its record clears 100 graded
    legs" -- 0 of 100 here, because no leg is graded before step 3."""
    assert m4.graded_legs() == 0 and m4.PROVEN_AT == 100
    assert language.m4_unproven_words(0, 100) == UNPROVEN
    out = _check(world, _form([STB, _leg("Patrick Mahomes", "KC", "passing touchdowns", 0.5,
                                         original="1.5")], {"multiplier": "3"}))
    for leg in out["model"]["legs"]:
        assert UNPROVEN in leg["model_words"] and UNPROVEN in leg["model_gap_words"]
        if leg["discount_words"] is not None:
            assert "%" in leg["discount_words"] and UNPROVEN in leg["discount_words"]
    for line in out["lines"]:
        if line.get("model"):
            assert UNPROVEN in line["label"]
    assert UNPROVEN in out["model"]["summary_words"]
    assert out["model"]["numbers"]["graded"] == 0 and out["model"]["numbers"]["gate"] == 100


def test_the_record_for_the_stat_is_said_in_plain_words_with_its_n(world):
    """The model's own receptions questions settled: 2, both right; its
    passing touchdowns: 2, one right -- each with how many more are needed
    (LAW 4)."""
    out = _check(world, _form([STB, PM], {"multiplier": "3"}))
    assert [leg["record_words"] for leg in out["model"]["legs"]] == [
        "Its record on its own receptions questions: right 2 of 2 settled; 98 more are "
        "needed before that record says anything.",
        "Its record on its own passing touchdowns questions: right 1 of 2 settled; 98 more "
        "are needed before that record says anything."]
    assert m4.record_of(world, "receptions") == {"n": 2, "right": 2, "gate": 100}


def test_nothing_is_worked_out_by_the_model_from_a_payout_not_confirmed(world):
    form = dict(_form([STB, PM], {"multiplier": "3"}), payout_confirmed=False)
    out = entry_check.check(world, form, now=NOW, remember_it=False)
    assert out["computed"] is False and out["model"] is None


# ---------------------------------------------------------------------------
# the Props tile, the tool, LAW 1 and the gate
# ---------------------------------------------------------------------------

def test_a_props_tile_says_whether_the_model_can_price_your_line_and_never_a_chance(world):
    """St. Brown's receptions: "type it in Check an entry · not yet proven · 0
    of 100 graded legs"; Goff's passing yards: "none: no projection for passing
    yards". Never a chance, an edge or a pick on the tile; a tile's pick is
    ruling C's, untouched."""
    from gridiron import views

    payload = views.week(world, "nfl", 2099, 5)
    tiles = {t["prediction_id"]: t for t in payload["board"]["props"]["tiles"]}
    ids = {r["subject"]: r["id"] for r in world.execute(
        "SELECT id, subject FROM predictions WHERE game_id = 'w_gb_det'"
        " AND pass_kind = 'final'")}
    stb = tiles[ids["Amon-Ra St. Brown receptions"]]
    goff = tiles[ids["Jared Goff passing_yards"]]
    assert stb["m4_words"] == f"type it in Check an entry · {UNPROVEN}"
    assert goff["m4_words"] == "none: no projection for passing yards"
    assert "projection of 6.00 receptions" in stb["tips"]["leg_m4"]
    assert not stb["pick"] and stb["signal"] == "none"
    assert payload["board"]["labels"]["at_your_line"] == "at your line"
    audit.check_the_props_board_calls_no_rung_a_pick(world, payload)


def test_the_tool_fits_a_scratch_copy_and_refuses_the_live_record(conn, db_path, capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "fit_prop_spreads_under_test", ROOT / "tools" / "fit_prop_spreads.py")
    fit_prop_spreads = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fit_prop_spreads)
    _world(conn, fit=False)
    conn.close()
    assert fit_prop_spreads.main(["--database", str(db_path)]) == 0
    said = capsys.readouterr().out
    assert "receptions: spread 1.500000 on 2 settled player-games" in said
    assert "dry, nothing written" in said
    check = db.read_only(db_path, "the test of the fitting tool")
    assert check.execute("SELECT COUNT(*) FROM prop_spread_fits").fetchone()[0] == 0
    check.close()
    assert fit_prop_spreads.main(["--database", str(db_path), "--write"]) == 0
    assert "[written as fit 1]" in capsys.readouterr().out
    assert fit_prop_spreads.main(["--database", str(db_path), "--write"]) == 0
    assert "not written again" in capsys.readouterr().out
    with pytest.raises(SystemExit) as refused:
        fit_prop_spreads.main(["--database", str(db_path), "--live"])
    assert refused.value.code == 2


def test_m4_is_outside_the_prediction_closure_and_named_if_planted(tmp_path):
    """LAW 1: the closure scan passes the shipped package, and names M4 by name
    when a module on the prediction path imports it or reads its fits."""
    audit.check_all_prediction_closures()
    root = tmp_path / "gridiron"
    shutil.copytree(ROOT / "gridiron", root,
                    ignore=shutil.ignore_patterns("__pycache__", "*.db", "fonts", "web"))
    victim = root / "factors" / "context.py"
    shipped = victim.read_text(encoding="utf-8")
    victim.write_text(shipped + "\nfrom .. import m4  # noqa\n", encoding="utf-8")
    with pytest.raises(audit.LawViolation, match="can reach 'gridiron.m4', M4"):
        audit.check_prediction_closure(root=root)
    victim.write_text(shipped + "\n\ndef sneak(conn):\n    return conn.execute("
                      "'SELECT spread FROM prop_spread_fits').fetchall()\n", encoding="utf-8")
    with pytest.raises(audit.LawViolation, match="names M4's fits"):
        audit.check_prediction_closure(root=root)


def _step_2_calls(name: str) -> bool:
    import ast

    gate = ROOT / "tools" / "verify.py"
    step = next(node for node in ast.parse(gate.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    return any(isinstance(node, ast.Attribute) and node.attr == name
               and isinstance(node.value, ast.Name) and node.value.id == "audit"
               for node in ast.walk(step))


def test_the_gate_makes_the_call_and_the_shipped_check_passes():
    assert _step_2_calls("check_the_model_only_flags")
    assert _step_2_calls("check_all_prediction_closures")
    audit.check_the_model_only_flags()
    assert "m4.py" in audit.ENTRY_CHECK_MODULES
    assert audit.entry_check_reach_faults() == []


def _green_by_the_model(real):
    def planted(conn, body, **kw):
        out = real(conn, body, **kw)
        legs = ((out.get("model") or {}).get("numbers") or {}).get("legs") or []
        if legs and all(leg.get("edge") is not None and leg["edge"] >= 0.03 for leg in legs):
            out["signal"] = "clears"
        return out
    return planted


def _lowered_by_the_model(real):
    """THE PROVER (2026-10-07): a green outline taken off where the model leans
    against a leg -- a verdict the model changed, which the gate's worked
    examples, none of them green at coin flips, let through as first built."""
    def planted(conn, body, **kw):
        out = real(conn, body, **kw)
        if out.get("signal") == "clears" and (
                (out.get("model") or {}).get("numbers") or {}).get("flagged"):
            out["signal"] = "none"
        return out
    return planted


def _red_by_the_model(real):
    """THE PROVER (2026-10-07): an entry turned red where the return at the
    model's chances is under its cost, whatever the coin flips say."""
    def planted(conn, body, **kw):
        out = real(conn, body, **kw)
        back = ((out.get("model") or {}).get("numbers") or {}).get("expected")
        if back is not None and back < 0.0:
            out["signal"] = "costs"
        return out
    return planted


def _standing_forecast_without_its_json_check(conn, *, game_id, stat, player_id,
                                              sport=m4.SPORT):
    """`m4.standing_forecast` as first built: its player read by a bare
    `json_extract`, which raises on a row that is not JSON."""
    from gridiron import calibration

    row = conn.execute(
        "SELECT p.id, p.game_id, p.prop_type, p.subject, p.line_asked, p.model_prob,"
        "       p.model_side, p.pass_kind, p.created_utc, p.factors_json"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND p.game_id = ? AND p.market_type = 'prop'"
        "   AND p.prop_type = ? AND p.predictor = ?"
        "   AND json_extract(p.factors_json, '$.question.player_id') = ?"
        f"{calibration.standing_row_clause(False)}"
        " ORDER BY p.id DESC LIMIT 1",
        (sport, game_id, stat, m4.FORECASTER, player_id)).fetchone()
    return None if row is None else dict(row)


@pytest.mark.parametrize("what,target,name,value,want", [
    ("an entry turned green by the model", "entry_check", "check", "green",
     "the model raised a verdict"),
    # THE PROVER'S (2026-10-07), each passing the gate's check as first built:
    # a verdict LOWERED by the model -- a green outline taken off where it
    # leans against a leg, an entry turned red where the return at its
    # chances is under its cost -- and the model's read of a forecast put back
    # to a bare `json_extract`, which raised on a row that is not JSON and took
    # the coin flips' verdict with it.
    ("a green outline taken off by the model's flag", "entry_check", "check", "lowered",
     "the model raised a verdict"),
    ("a green entry turned red by the model's return", "entry_check", "check", "red",
     "the model raised a verdict"),
    ("the model's read of a forecast without its JSON check", "m4", "standing_forecast",
     _standing_forecast_without_its_json_check, "raised OperationalError"),
    ("every model number drawn without its words", "language", "m4_unproven_words",
     lambda graded, gate: "", "M4 is said to be"),
    ("the Props tile without its words", "language", "prop_m4_words",
     lambda state, **kw: "in Check an entry", "can price the operator's line without"),
    ("a discount priced where the model states no chance", "language",
     "entry_check_m4_discount_words",
     lambda before, line, side, unproven="": "Before the discount, the model gives it 60.00%.",
     "a discounted line priced where the model states no chance"),
])
def test_the_gate_names_each_planted_defect(monkeypatch, what, target, name, value, want):
    """The gate's check, on its own worked examples, names each defect the
    plantings plant (tools/guards/plant.py holds them, each escaping on
    6395fb4); a few of them here, quickly."""
    module = {"entry_check": entry_check, "language": language, "m4": m4}[target]
    if value == "green":
        value = _green_by_the_model(module.check)
    elif value == "lowered":
        value = _lowered_by_the_model(module.check)
    elif value == "red":
        value = _red_by_the_model(module.check)
    monkeypatch.setattr(module, name, value)
    faults = audit.model_flag_faults()
    assert any(want in f for f in faults), (what, faults[:3])


def test_a_forecast_row_that_is_not_json_takes_neither_the_verdict_nor_the_tile(world):
    """THE PROVER (2026-10-07): a statistical prop row in the leg's game whose
    stored factors are not JSON made `m4.standing_forecast`'s bare
    `json_extract` raise "malformed JSON" -- the whole check raised, the
    coin flips' verdict with it, and the Props tile's "at your line" row with
    the slate. The forecast's player is read only from a row that is JSON
    (`json_valid`, the prompt record's precedent), and nothing else moves."""
    world.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, prop_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning) VALUES ('2099-09-30T18:30:00Z',"
        " 'nfl', 'w_gb_det', 'prop', 'receptions', 'Somebody Else receptions', 3.5, 0.6,"
        " 'over', 'statistical', 'final', 'fs2', 'not JSON at all', 'test')")
    world.commit()
    out = _check(world, _form([STB, PM, LOVE], {"multiplier": "6"}))
    assert out["signal"] == "costs"
    assert _chances(out) == pytest.approx([1 - NB6_LE4, 1 - 2.5 * E15, 1 - 3 * E2], abs=1e-6)
    row = world.execute("SELECT * FROM predictions WHERE subject = 'Amon-Ra St. Brown"
                        " receptions' AND game_id = 'w_gb_det' AND pass_kind = 'final'"
                        ).fetchone()
    got = board._at_your_line(world, {"game_id": "w_gb_det"}, dict(row), "receptions",
                              "receptions", sport="nfl")
    assert got["state"] == "priced"


def test_the_page_draws_no_number_of_the_models_bare():
    """THE PROVER (2026-10-07): every number the model states reaches the page
    inside the server's words, each carrying "not yet proven" and its count;
    a page drawing a leg's chance from the answer's numbers would draw it
    bare, and the gate's check names it."""
    js = (ROOT / "gridiron" / "web" / "app.js").read_text(encoding="utf-8")
    anchor = ("row.appendChild(tip(el('span', 'entry-read-model', said.model_words || ''), "
              "said.model_tip));")
    assert anchor in js
    put_back = js.replace(anchor, "row.appendChild(el('span', 'entry-read-model', "
                                  "(model.numbers.legs[i].chance * 100).toFixed(2) + '%'));")
    assert audit.model_flag_faults() == []
    assert any("reads the answer's numbers" in f for f in audit.model_flag_faults(js=put_back))


def test_the_page_draws_the_outline_from_the_servers_verdict_alone():
    js = (ROOT / "gridiron" / "web" / "app.js").read_text(encoding="utf-8")
    anchor = "const verdict = el('div', 'verdict ' + signalClass(r.signal));"
    assert anchor in js
    put_back = js.replace(anchor, "const verdict = el('div', 'verdict ' + signalClass("
                                  "model && model.signal ? model.signal : r.signal));")
    assert any("draws an outline" in f for f in audit.model_flag_faults(js=put_back))


# ---------------------------------------------------------------------------
# the page, in a real Chromium
# ---------------------------------------------------------------------------
#
# ON A COPY OF THE BROWSER WORLD, served on its own port: two forecasts with a
# projection are written on its first game to come, for a player of each club,
# and a fit of each stat, so the model can read both legs. No clock is read and
# nothing waits a fixed time: every wait is for what the page draws.

@pytest.fixture(scope="module")
def _veto_world(_shared_world, tmp_path_factory):
    from tests import conftest

    target = tmp_path_factory.mktemp("entry-veto") / "world.db"
    source = db.read_only(_shared_world["db"],
                          "copying the browser world for the model beside the entry check")
    copy = db.connect(target)
    source.backup(copy)
    source.close()
    copy.close()
    conn = db.open_db(target)
    game = conn.execute("SELECT id, home, away, season, kickoff_utc FROM games WHERE sport ="
                        " 'nfl' AND status = 'scheduled' ORDER BY kickoff_utc, id LIMIT 1"
                        ).fetchone()
    legs = []
    for club, projection in ((game["home"], 6.0), (game["away"], 1.5)):
        row = conn.execute("SELECT player_id, player_name FROM player_week_stats WHERE season ="
                           " ? AND team = ? ORDER BY week DESC, player_name LIMIT 1",
                           (game["season"], club)).fetchone()
        stat = "receptions" if projection == 6.0 else "passing_tds"
        fid = _forecast(conn, game["id"], row["player_id"], row["player_name"], stat, 3.5,
                        "over", projection, created=db.utcnow())
        legs.append((row["player_name"], club, stat, fid))
    for stat, spread in (("receptions", 1.5), ("passing_tds", 0.5)):
        m4.record_fit(conn, {"sport": "nfl", "stat": stat, "form": m4.FORM,
                             "form_declared": m4.FORM_DECLARED, "spread": spread, "n": 1,
                             "forecasts": [legs[0][3]], "method": m4.METHOD})
    conn.commit()
    base, server, thread = conftest._serve(target)
    yield {"base": base, "db": target, "conn": conn, "legs": legs}
    server.should_exit = True
    thread.join(timeout=10)
    conn.close()
    from gridiron import api

    api.set_database(_shared_world["db"])


@pytest.mark.parametrize("width", ["1300", "390"])
def test_the_page_draws_the_model_beside_the_verdict_and_never_on_it(_veto_world, _browser, width):
    """THE PAGE, END TO END: two legs the model can read, typed off the app at
    3x on two legs (57.74% a leg, -0.25 at coin flips: red); the page draws
    the server's verdict and outline -- red, the coin flips' -- and beside it
    the model's words for each leg and its summary, every number "not yet
    proven"; and at 390, three device pixels to one, every tap target 44px or
    more in whole pixels at rest, and nothing wider than the phone."""
    from tests.test_entry_check import _sign_in
    from tests.test_smoke import _AT_REST, _MEASURE_THE_TARGETS, SLATE_TAP_TARGETS

    context, page = _sign_in(_veto_world, _browser, phone=width == "390")
    try:
        page.select_option("#entry-form .entry-head-row select >> nth=0", "prizepicks")
        words = {"receptions": "receptions", "passing_tds": "passing touchdowns"}
        typed = []
        for i, (player, club, stat, _fid) in enumerate(_veto_world["legs"]):
            leg = f"#entry-legs .entry-leg >> nth={i}"
            page.fill(f"{leg} >> input >> nth=0", player)
            page.select_option(f"{leg} >> select >> nth=0", club)
            page.fill(f"{leg} >> input >> nth=1", words[stat])
            page.fill(f"{leg} >> input >> nth=2", "3.5" if stat == "receptions" else "0.5")
            typed.append(_leg(player, club, words[stat], 3.5 if stat == "receptions" else 0.5))
        page.fill("#entry-payout .entry-pays-rows input", "3")
        page.check("#entry-payout .entry-confirm input")
        page.click("#entry-check")
        page.wait_for_selector("#entry-lines .entry-model", timeout=10000)
        server = entry_check.check(_veto_world["conn"], _form(typed, {"multiplier": "3"}),
                                   remember_it=False)
        drawn = page.evaluate("""() => ({
            cls: document.querySelector('#entry-lines .verdict').className,
            summary: document.querySelector('#entry-lines .entry-model').textContent,
            model: [...document.querySelectorAll('#entry-lines .entry-read-model')]
                     .map(e => e.textContent),
            lines: [...document.querySelectorAll('#entry-lines .entry-line')]
                     .map(r => [r.querySelector('.entry-label').textContent,
                                r.querySelector('.entry-value').textContent]) })""")
        assert server["signal"] == "costs" and "sig-costs" in drawn["cls"]
        assert drawn["summary"] == server["model"]["summary_words"]
        assert drawn["lines"] == [[l["label"], l["value_words"]] for l in server["lines"]]
        assert any(UNPROVEN in label for label, _v in drawn["lines"])
        priced = [leg["model_words"] for leg in server["model"]["legs"]]
        assert all(w in drawn["model"] for w in priced) and all(UNPROVEN in w for w in priced)
        if width == "390":
            page.wait_for_function(_AT_REST, timeout=15000)
            got = page.evaluate(_MEASURE_THE_TARGETS, SLATE_TAP_TARGETS)
            assert got["measured"] > 20 and not got["small"], got["small"][:20]
            assert page.evaluate("document.documentElement.scrollWidth") <= 390
        assert not page.page_errors, page.page_errors
    finally:
        context.close()
