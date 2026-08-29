"""D3: five prop markets, a capped slate, and VOID as a terminal state."""

from __future__ import annotations

import json
import sqlite3

import pytest

from gridiron import calibration, config, db, resolve, run
from gridiron.data import repo
from gridiron.factors import registry, store
from gridiron.model import baseline, questions


# --- the five markets -------------------------------------------------------

def test_five_markets_are_declared_in_liquidity_order():
    assert config.PROP_MARKETS == (
        "passing_yards", "receiving_yards", "rushing_yards", "receptions", "passing_tds"
    )
    for market in config.PROP_MARKETS:
        assert market in config.PROP_LINE_STEP
        assert market in questions.STAT_POSITIONS
        assert market in questions.STAT_VOLUME_COLUMN
        assert market in questions.STAT_MEAN_COLUMN
        assert market in questions.STAT_VOLUME_STAT


def test_the_stat_maps_have_exactly_one_source_of_truth():
    """They were duplicated in context.py once, the copy fell behind when two
    markets were added, and both raised KeyError and were silently skipped."""
    from gridiron.factors import context

    source = (config.PACKAGE_ROOT / "factors" / "context.py").read_text(encoding="utf-8")
    assert "STAT_VOLUME = {" not in source
    assert "STAT_POSITION = {" not in source
    volume_map, position_map = context._stat_maps()
    assert set(volume_map) == set(config.PROP_MARKETS)
    assert set(position_map) == set(config.PROP_MARKETS)


@pytest.mark.parametrize("market", config.PROP_MARKETS)
def test_no_prop_line_can_push(market):
    for mean in (0.4, 1.0, 3.7, 8.0, 62.5, 255.0):
        for key in ("a", "b", "c", "d"):
            line = questions.prop_line_asked(mean, key, market)
            assert line % 1 == 0.5, f"{market} at mean {mean} produced {line}"
            assert line > 0


def test_counting_markets_get_counting_lines():
    """Receptions and touchdowns are not rounded to the nearest five."""
    assert questions.prop_line_asked(5.0, "k", "receptions") in (3.5, 4.5, 5.5, 6.5)
    assert questions.prop_line_asked(1.8, "k", "passing_tds") in (0.5, 1.5, 2.5)
    assert questions.prop_line_asked(255.0, "k", "passing_yards") % 5 == 0.5


def test_a_tiny_average_still_yields_a_sane_line():
    assert questions.prop_line_asked(0.2, "k", "passing_tds") == 0.5
    assert questions.prop_line_asked(0.0, "k", "receptions") == 0.5


# --- the weekly slate -------------------------------------------------------

@pytest.fixture
def week_games(league):
    return repo.games_for_week(league, 2025, 10)


def test_the_slate_respects_the_weekly_cap(league, week_games):
    picks = questions.select_week_props(league, week_games, cap=7)
    assert len(picks) == 7


def test_the_slate_respects_the_per_game_ceiling(league, week_games):
    import collections

    picks = questions.select_week_props(league, week_games, cap=100, per_game=2)
    counts = collections.Counter(p["game_id"] for p in picks)
    assert max(counts.values()) <= 2


def test_the_slate_is_balanced_across_markets(league, week_games):
    """Round-robin, so a slate is never all quarterbacks."""
    import collections

    picks = questions.select_week_props(league, week_games, cap=8, per_game=8)
    kinds = collections.Counter(p["stat"] for p in picks)
    assert len(kinds) >= 3, f"the slate collapsed onto {dict(kinds)}"
    assert max(kinds.values()) - min(kinds.values()) <= 1


def test_the_slate_is_deterministic(league, week_games):
    first = questions.select_week_props(league, week_games)
    second = questions.select_week_props(league, week_games)
    assert [(p["player_id"], p["stat"], p["line_asked"]) for p in first] == [
        (p["player_id"], p["stat"], p["line_asked"]) for p in second
    ]


def test_a_player_is_asked_each_question_once_per_week(league, week_games):
    import collections

    picks = questions.select_week_props(league, week_games, cap=100, per_game=100)
    counts = collections.Counter((p["player_id"], p["stat"]) for p in picks)
    assert not [k for k, v in counts.items() if v > 1]


def test_a_player_ruled_out_is_not_asked_about(league, week_games):
    game = week_games[0]
    victim = questions.prop_candidates(league, game)[0]
    league.execute(
        "INSERT INTO injuries (season, week, team, player_name, position,"
        " report_status) VALUES (2025, 10, ?, ?, ?, 'Out')",
        (victim["team"], victim["player_name"], victim["position"]),
    )
    league.commit()

    assert victim["player_name"] in questions.players_ruled_out(
        league, 2025, 10, victim["team"]
    )
    remaining = [
        c for c in questions.prop_candidates(league, game)
        if c["player_name"] == victim["player_name"] and c["stat"] == victim["stat"]
    ]
    assert remaining == []


def test_a_player_who_has_stopped_appearing_is_not_asked_about(league, week_games):
    """The recency rule. A player who quietly stopped playing would resolve VOID
    and teach the scorecard nothing while occupying a slot on a capped slate."""
    game = week_games[0]
    team = game["home"]
    before = {c["player_id"] for c in questions.prop_candidates(league, game)}
    assert before

    league.execute(
        "DELETE FROM player_week_stats WHERE team = ? AND season = 2025 AND week >= ?",
        (team, 10 - questions.MAX_WEEKS_SINCE_PLAYED),
    )
    league.commit()
    after = {
        c["player_id"] for c in questions.prop_candidates(league, game)
        if c["team"] == team
    }
    assert after == set(), "a stale player survived the recency rule"


def test_a_traded_player_leaves_his_old_club(league):
    """`team_players` keeps prior-season rows for early-season coverage, which
    once put the same quarterback on two teams' slates in one week."""
    rows = repo.team_players(league, 2025, league.execute(
        "SELECT home FROM games WHERE week = 10 LIMIT 1").fetchone()["home"], 10)
    assert rows
    for r in rows:
        assert "games_this_season" in r.keys()
        assert "last_week_played" in r.keys()


# --- VOID -------------------------------------------------------------------

@pytest.fixture
def settled_props(league):
    store.sync_registry(league)
    baseline.train_all(league, (2025,), l2=1.0, note="d3", min_rows=20)
    run.run_week(league, 2025, 7, include_props=True, use_llm=False)
    resolve.resolve_all(league)
    return league


def _ghost_prop(conn, stat: str = "passing_yards") -> int:
    game_id = conn.execute("SELECT id FROM games WHERE week = 7 LIMIT 1").fetchone()["id"]
    pid = conn.execute(
        "INSERT INTO predictions (created_utc, game_id, market_type, prop_type, subject,"
        " line_asked, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) VALUES (?,?,'prop',?,?,180.5,0.72,'over',"
        " 'statistical','fs2',?,'test')",
        (
            db.utcnow(), game_id, stat, f"Ghost Player {stat}",
            json.dumps({"question": {"player_id": "NOBODY", "stat": stat,
                                     "yes_label": "over", "no_label": "under"}}),
        ),
    ).lastrowid
    conn.commit()
    return pid


def test_an_unavailable_stat_voids_with_a_reason(settled_props):
    pid = _ghost_prop(settled_props)
    result = resolve.resolve_all(settled_props)
    assert result["voided"] >= 1

    row = settled_props.execute(
        "SELECT outcome, resolved_utc FROM predictions WHERE id = ?", (pid,)
    ).fetchone()
    assert row["outcome"] is None, "a void must never be recorded as a loss"
    assert row["resolved_utc"] is None

    void = settled_props.execute(
        "SELECT reason FROM prediction_voids WHERE prediction_id = ?", (pid,)
    ).fetchone()
    assert "did not appear" in void["reason"]
    assert "not being given one" in void["reason"]


def test_voiding_is_idempotent(settled_props):
    pid = _ghost_prop(settled_props)
    assert resolve.void_prediction(settled_props, pid, "first reason, long enough")
    assert not resolve.void_prediction(settled_props, pid, "a different reason entirely")
    row = settled_props.execute(
        "SELECT reason FROM prediction_voids WHERE prediction_id = ?", (pid,)
    ).fetchone()
    assert row["reason"] == "first reason, long enough", "the first reason must stand"


def test_a_void_is_terminal(settled_props):
    pid = _ghost_prop(settled_props)
    resolve.resolve_all(settled_props)
    with pytest.raises(sqlite3.IntegrityError) as exc:
        settled_props.execute(
            "UPDATE predictions SET resolved_utc = ?, outcome = 1 WHERE id = ?",
            (db.utcnow(), pid),
        )
    assert "LAW 3" in str(exc.value)
    assert "voided" in str(exc.value)


def test_a_void_reason_cannot_be_rewritten(settled_props):
    pid = _ghost_prop(settled_props)
    resolve.void_prediction(settled_props, pid, "the original stated reason")
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        settled_props.execute(
            "UPDATE prediction_voids SET reason = 'something nicer' "
            "WHERE prediction_id = ?", (pid,)
        )


def test_a_voided_prediction_is_not_reoffered_for_resolution(settled_props):
    pid = _ghost_prop(settled_props)
    resolve.resolve_all(settled_props)
    assert pid not in {r["id"] for r in resolve.open_predictions(settled_props)}
    again = resolve.resolve_all(settled_props)
    assert again["voided"] == 0, "a settled void must not be voided twice"


def test_the_summary_counts_voids_apart_from_losses(settled_props):
    _ghost_prop(settled_props)
    resolve.resolve_all(settled_props)
    summary = resolve.summary(settled_props)
    assert summary["voided"] >= 1
    assert summary["open"] >= 0
    assert summary["resolved"] + summary["voided"] + summary["open"] == summary["predictions"]


# --- per-market scoring -----------------------------------------------------

def test_each_market_is_its_own_category(settled_props):
    payload = calibration.scorecard(settled_props)
    labels = {c["category"] for c in payload["categories"]}
    for market in config.PROP_MARKETS:
        assert f"{market} / statistical" in labels
    assert "prop / statistical" not in labels, "a merged props curve reappeared"


def test_each_market_carries_its_own_void_count(settled_props):
    _ghost_prop(settled_props, "passing_yards")
    resolve.resolve_all(settled_props)
    curve = calibration.curve(
        settled_props, market_type="prop", prop_type="passing_yards",
        predictor="statistical",
    )
    assert curve["voided"] >= 1
    assert curve["void_rate"] is not None
    assert "n" in curve


def test_a_void_is_excluded_from_the_curve_but_reported_beside_it(settled_props):
    before = calibration.curve(
        settled_props, market_type="prop", prop_type="passing_yards",
        predictor="statistical",
    )
    _ghost_prop(settled_props, "passing_yards")
    resolve.resolve_all(settled_props)
    after = calibration.curve(
        settled_props, market_type="prop", prop_type="passing_yards",
        predictor="statistical",
    )
    assert after["n"] == before["n"], "a void must not enter the calibration sample"
    assert after["voided"] == before["voided"] + 1


def test_each_market_has_its_own_gate(settled_props):
    for market in config.PROP_MARKETS:
        e = calibration.edge(
            settled_props, market_type="prop", prop_type=market, predictor="statistical"
        )
        assert e["prop_type"] == market
        assert e["minimum_for_a_claim"] == config.MIN_SAMPLE_FOR_EDGE_CLAIM
        assert e["renderable"] is False


def test_every_market_is_fitted_separately(settled_props):
    fitted = {
        r["market_type"]
        for r in settled_props.execute("SELECT DISTINCT market_type FROM model_fits")
    }
    assert "spread" in fitted
    assert len(fitted & {baseline.prop_market(m) for m in config.PROP_MARKETS}) >= 3


def test_a_prediction_records_which_market_it_is(settled_props):
    rows = settled_props.execute(
        "SELECT market_type, prop_type FROM predictions WHERE market_type = 'prop'"
    ).fetchall()
    assert rows
    for r in rows:
        assert r["prop_type"] in config.PROP_MARKETS


# --- the new prop factors ---------------------------------------------------

@pytest.mark.parametrize(
    "name", ["prop_volume_share", "prop_snap_share", "prop_game_script"]
)
def test_the_new_prop_factors_are_declared_properly(name):
    f = registry.REGISTRY[name]
    assert f.active
    assert f.added_utc.startswith("2026-08-29")
    assert f.applies_to == ("prop",)
    assert len(f.rationale) > 80
    assert f.rationale.rstrip().endswith(".")


def test_the_new_prop_factors_return_none_when_unmeasurable():
    class Empty:
        volume_share = None
        snap_share = None
        game_script = None

    for name in ("prop_volume_share", "prop_snap_share", "prop_game_script"):
        assert registry.REGISTRY[name].fn(Empty()) is None


def test_game_script_is_signed_for_the_players_own_team():
    class Ctx:
        game_script = 7.0
    assert registry.REGISTRY["prop_game_script"].fn(Ctx()) == pytest.approx(0.7)
    Ctx.game_script = -7.0
    assert registry.REGISTRY["prop_game_script"].fn(Ctx()) == pytest.approx(-0.7)


def test_an_unmatched_snap_name_is_absent_not_zero(league):
    value, n = repo.snap_share(league, 2025, "KC", "Nobody At All", 10)
    assert value is None and n == 0


def test_snap_share_is_reported_with_its_sample(league):
    league.execute(
        "INSERT INTO snap_counts (season, week, team, player_name, position,"
        " offense_snaps, offense_pct) VALUES (2025, 9, 'KC', 'Someone Real', 'WR', 50, 0.8)"
    )
    league.commit()
    value, n = repo.snap_share(league, 2025, "KC", "Someone Real", 10)
    assert value == pytest.approx(0.8)
    assert n == 1
