"""The decayed rating (AT_THE_LINE E2, 2026-09-06): recency-decayed,
margin-capped, home-adjusted by a measured figure, opponent-adjusted;
declared with its choices, dated, replacing the plain rating -- which is
retired as REPLACED, not refuted, on its own factor set."""
from __future__ import annotations

import sys

from gridiron import config, db
from gridiron.data import cfb_repo, repo
from gridiron.factors import context, registry


def _row(team, opp, pf, pa, home, season=2025, week=1):
    return {"season": season, "week": week, "team": team, "opponent": opp,
            "points_for": pf, "points_against": pa, "was_home": 1 if home else 0}


def _two_way(team, opp, margin, home, season=2025, week=1):
    """Both sides of one game, as team_week_stats holds them."""
    return [_row(team, opp, 20 + margin, 20, home, season, week),
            _row(opp, team, 20, 20 + margin, not home, season, week)]


def test_the_successor_is_declared_dated_and_the_plain_rating_retired():
    new = registry.REGISTRY["nfl_rating_decayed_diff"]
    assert new.added_utc.startswith("2026-09-06") and new.active
    assert set(new.applies_to) == {"spread", "moneyline"}
    for word in ("half-life", "28 points", "MEASURED", "NOT tuned"):
        assert word in new.rationale, word
    old = registry.REGISTRY["srs_diff"]
    assert not old.active and old.deactivated_utc.startswith("2026-09-06")
    assert "REPLACED, not refuted" in old.note
    assert "nfl_rating_decayed_diff" in old.note
    assert config.RATING_DECAY["declared"].startswith("2026-09-06")
    for sport in ("nfl", "cfb"):
        m = config.HOME_MARGIN_MEASURED[sport]
        assert m["n"] > 1000 and m["measured_utc"].startswith("2026-09-06") and m["mean"] > 0


def test_home_adjustment_rates_the_team_not_the_venue():
    rows = _two_way("A", "B", 12, home=True) + _two_way("C", "D", 8, home=False)
    r = context.decayed_ratings(rows, half_life_games=6, margin_cap=28, home_adjust=2.0)
    # A won by 12 at home (10 after the adjustment); C won by 8 away (10 after it)
    assert abs(r["A"] - r["C"]) < 1e-9
    assert abs(r["B"] - r["D"]) < 1e-9


def test_a_blowout_counts_as_the_cap():
    big = context.decayed_ratings(_two_way("A", "B", 60, home=False), half_life_games=6, margin_cap=28, home_adjust=0)
    capped = context.decayed_ratings(_two_way("A", "B", 28, home=False), half_life_games=6, margin_cap=28, home_adjust=0)
    assert abs(big["A"] - capped["A"]) < 1e-9 and big["A"] > 0


def test_recent_games_weigh_more_and_a_long_half_life_is_the_plain_average():
    rows = []
    for week in range(1, 8):
        margin = -21 if week == 1 else 7      # one old loss, six recent wins
        rows += _two_way("A", "B", margin, home=False, week=week)
    decayed = context.decayed_ratings(rows, half_life_games=6, margin_cap=28, home_adjust=0)
    flat = context.decayed_ratings(rows, half_life_games=1e9, margin_cap=28, home_adjust=0)
    plain = context.srs_ratings(rows)
    assert abs(flat["A"] - plain["A"]) < 1e-6, "a huge half-life should reproduce the plain rating"
    assert decayed["A"] > plain["A"], "the old loss should weigh less than the recent wins"
    # the first game weighs one half at six games' distance
    assert abs(0.5 ** (6 / 6) - 0.5) < 1e-12


def test_beating_a_strong_side_rates_higher_than_beating_a_weak_one():
    # B is strong (beats C twice by 20); A beats B by 10; D beats C by 10.
    rows = (_two_way("B", "C", 20, home=False, week=1) + _two_way("B", "C", 20, home=True, week=2)
            + _two_way("A", "B", 10, home=False, week=3) + _two_way("D", "C", 10, home=False, week=3))
    r = context.decayed_ratings(rows, half_life_games=1e9, margin_cap=28, home_adjust=0)
    assert r["A"] > r["D"]


def test_the_context_carries_the_rating_and_stays_blind(league):
    game = league.execute("SELECT id FROM games WHERE season = 2025 AND week = 8 LIMIT 1").fetchone()
    ctx = context.build_game_context(league, game["id"])
    assert ctx.home_rating_decayed is not None and ctx.away_rating_decayed is not None
    assert registry.REGISTRY["nfl_rating_decayed_diff"].fn(ctx) is not None
    rows = repo.team_games_for_rating(league, 2025, 8)
    assert rows and all(r["week"] < 8 for r in rows if r["season"] == 2025)
    assert all(r["was_home"] in (0, 1) for r in rows)
    # week 1 with no season before it: absent, not zero
    first = league.execute("SELECT id FROM games WHERE season = 2025 AND week = 1 LIMIT 1").fetchone()
    ctx1 = context.build_game_context(league, first["id"])
    assert ctx1.home_rating_decayed is None
    assert registry.REGISTRY["nfl_rating_decayed_diff"].fn(ctx1) is None
    # LAW 1: the rating's modules are inside the prediction closure, and the
    # closure scan is the proof that none of them reaches market data.
    from gridiron import audit
    audit.check_prediction_closure()


def test_the_version_bumped_for_the_game_markets_and_nothing_else():
    assert config.factor_set_version("nfl", "spread") == "fs5"
    assert config.factor_set_version("nfl", "moneyline") == "fs5"
    assert config.factor_set_version("mlb", "moneyline") == "fs2"
    assert config.FACTOR_SET_ACTIVATED["fs5"].startswith("2026-09-06")
    for v in ("fs3", "fs3-rate", "fs4"):
        assert config.FACTOR_SET_ACTIVATED[v].startswith("2026-09-03")


def test_college_football_decays_by_days_caps_and_adjusts(tmp_path):
    conn = db.open_db(tmp_path / "cfb.db")
    def game(gid, home, away, hs, as_, kick):
        conn.execute("INSERT INTO games (id, sport, season, week, game_type, home, away, kickoff_utc,"
                     " status, home_score, away_score, league_date) VALUES (?, 'cfb', 2026, 1, 'REG', ?, ?, ?, 'final', ?, ?, ?)",
                     (gid, home, away, kick, hs, as_, kick[:10]))
    adj = config.HOME_MARGIN_MEASURED["cfb"]["mean"]
    # A beats B at home by adj+10 in the last week; C beats D away by 10 a year earlier
    game("g1", "A", "B", 40 + adj, 30, "2026-09-01T00:00:00Z")
    game("g2", "D", "C", 20, 30, "2025-09-15T00:00:00Z")
    conn.commit()
    r = cfb_repo.decayed_ratings(conn, 2026, before_utc="2026-09-06T00:00:00Z")
    assert r["A"] > 0 and r["C"] > 0
    assert r["A"] > r["C"], "a year-old win should weigh far less than last week's"
    plain = cfb_repo.ratings(conn, 2026, before_utc="2026-09-06T00:00:00Z")
    assert set(plain) == set(r)
    # the cap
    game("g3", "E", "F", 90, 0, "2026-09-01T00:00:00Z"); conn.commit()
    r2 = cfb_repo.decayed_ratings(conn, 2026, before_utc="2026-09-06T00:00:00Z")
    capped = config.RATING_DECAY["cfb"]["margin_cap"]
    assert r2["E"] - r2["F"] <= 2 * capped + 1e-6
    new = registry.REGISTRY["cfb_rating_decayed_diff"]
    old = registry.REGISTRY["cfb_srs_diff"]
    assert new.active and new.added_utc.startswith("2026-09-06") and new.sport == "cfb"
    assert not old.active and "REPLACED, not refuted" in old.note
    assert config.factor_set_version("cfb", "spread") == "fs5"
    assert config.factor_set_version("cfb", "moneyline") == "fs5"
