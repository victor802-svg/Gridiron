"""G2: the registry is the only door, and it is a locked one."""

from __future__ import annotations

import re

import pytest

from gridiron import config
from gridiron.factors import compute, context, registry, store

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


# --- LAW 2: every factor is declared, dated, and justified -----------------

def _all_declared_markets() -> set[str]:
    """What a factor may say it applies to.

    Two vocabularies meet here and both are legitimate. A game factor names a
    concrete market — `spread`, `moneyline` — while a prop factor applies to
    the whole `prop` class rather than being redeclared once per stat. Listing
    football's two by hand stopped being right the moment baseball declared a
    moneyline, and the failure was the assertion, not the factor."""
    from gridiron import config

    concrete = {m for markets in config.SPORT_MARKETS.values() for m in markets}
    return concrete | {"prop"}


def test_every_factor_has_a_dated_causal_rationale():
    assert registry.REGISTRY, "the registry is empty"
    for f in registry.REGISTRY.values():
        assert ISO.match(f.added_utc), f"{f.name} has no usable activation date"
        assert len(f.rationale) >= 20, f"{f.name} has a token rationale"
        # A rationale should say why, not merely restate the name.
        assert f.rationale.rstrip().endswith("."), f"{f.name} rationale is not a sentence"
        assert f.applies_to, f"{f.name} applies to no market type"
        for market in f.applies_to:
            assert market in _all_declared_markets(), f"{f.name} -> {market}"


def test_the_spec_factor_set_is_all_present():
    """Every factor the specification asked for is declared."""
    required = {
        "rest_diff",
        "short_week_either",
        "travel_kmiles",
        "timezone_shift",
        "home_field",
        "srs_diff",
        "recent_form_diff",
        "pace_sum",
        "injury_out_diff",
        "wind",
        "cold",
        "precipitation",
        "prop_volume",
        "prop_efficiency",
        "opponent_allowance",
        "public_bet_pct",
    }
    missing = required - set(registry.REGISTRY)
    assert not missing, f"declared factor set is missing {sorted(missing)}"


def test_public_betting_is_declared_but_inactive_with_a_reason():
    """LAW 2 said record the absence rather than invent a proxy."""
    f = registry.REGISTRY["public_bet_pct"]
    assert not f.active
    assert f.deactivated_utc
    assert f.note and "no free source" in f.note.lower()
    assert f.fn(object()) is None, "an inactive factor must not synthesise a value"
    assert f.name not in {g.name for g in registry.active_factors("nfl", "spread")}


def test_inactive_factors_are_excluded_from_the_vector(league):
    game_id = league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1"
    ).fetchone()["id"]
    fv = compute.feature_vector(context.build_game_context(league, game_id), "spread")
    assert "public_bet_pct" not in fv.values


# --- the registry / database contract --------------------------------------

def test_sync_is_idempotent(conn):
    first = store.sync_registry(conn)
    assert first["added"] == len(registry.REGISTRY)
    second = store.sync_registry(conn)
    assert second == {"added": 0, "updated": 0, "unchanged": len(registry.REGISTRY)}


def test_a_factor_cannot_move_its_own_activation_date(conn, monkeypatch):
    store.sync_registry(conn)
    original = registry.REGISTRY["home_field"]
    monkeypatch.setitem(
        registry.REGISTRY,
        "home_field",
        registry.Factor(
            name="home_field",
            added_utc="2020-01-01T00:00:00Z",   # backdated, to score it on old predictions
            rationale=original.rationale,
            applies_to=original.applies_to,
            fn=original.fn,
        ),
    )
    with pytest.raises(store.RegistryConflict, match="cannot be moved"):
        store.sync_registry(conn)


def test_recording_a_factor_score_requires_a_sample_size(conn):
    store.sync_registry(conn)
    with pytest.raises(ValueError, match="LAW 4"):
        store.record_factor_score(conn, "nfl", "home_field", "since_activation", None, 0.24, 0.6)


# --- feature vectors -------------------------------------------------------

def test_an_unmeasurable_factor_leaves_the_vector_entirely(league):
    """v2: absent is an explicit state, not a default that looks like data."""
    game_id = league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1"
    ).fetchone()["id"]
    ctx = context.build_game_context(league, game_id)
    ctx.home_rest = None                       # simulate an unavailable input
    fv = compute.feature_vector(ctx, "spread")

    assert fv.raw["rest_diff"] is None
    assert "rest_diff" not in fv.values, "an unmeasurable factor must not carry a value"
    assert "rest_diff" in fv.absent
    payload = fv.to_json_dict()
    assert "rest_diff" in payload["absent"]
    assert "rest_diff" not in payload["present"]
    assert payload["coverage"] < 1.0


def test_a_broken_factor_does_not_kill_the_slate(league, monkeypatch):
    def explode(ctx):
        raise ZeroDivisionError("boom")

    original = registry.REGISTRY["home_field"]
    monkeypatch.setitem(
        registry.REGISTRY,
        "home_field",
        registry.Factor(
            name="home_field",
            added_utc=original.added_utc,
            rationale=original.rationale,
            applies_to=original.applies_to,
            fn=explode,
        ),
    )
    game_id = league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1"
    ).fetchone()["id"]
    fv = compute.feature_vector(context.build_game_context(league, game_id), "spread")
    assert "ZeroDivisionError" in fv.failed["home_field"]
    assert "home_field" in fv.absent
    assert "home_field" not in fv.values
    assert len(fv.values) + len(fv.absent) == len(registry.active_factors("nfl", "spread"))


# --- the ratings -----------------------------------------------------------

def test_srs_ranks_the_strong_team_first(league):
    ratings = context.srs_ratings(
        league.execute("SELECT * FROM team_week_stats WHERE season = 2025").fetchall()
    )
    assert ratings
    assert abs(sum(ratings.values())) < 1e-6, "ratings should be centred on zero"
    # The fixture builds KC as the strongest club and GB as the weakest.
    assert ratings["KC"] > ratings["GB"]


def test_srs_on_no_games_is_empty_not_zero():
    assert context.srs_ratings([]) == {}


# --- no future data --------------------------------------------------------

def test_context_cannot_see_the_game_it_is_predicting(league):
    """The week-7 context must be built from weeks 1-6 only."""
    game_id = league.execute(
        "SELECT id FROM games WHERE week = 7 LIMIT 1"
    ).fetchone()["id"]
    ctx = context.build_game_context(league, game_id)
    assert ctx.week == 7
    assert ctx.home_games_played == 6, "should see exactly the six completed weeks"
    assert ctx.away_games_played == 6


def test_context_at_week_two_sees_only_week_one(league):
    game_id = league.execute("SELECT id FROM games WHERE week = 2 LIMIT 1").fetchone()["id"]
    ctx = context.build_game_context(league, game_id)
    assert ctx.home_games_played == 1
    assert ctx.srs_basis != "season", "one game is too few to rate a team"


def test_early_season_falls_back_to_the_prior_year(league):
    """With a previous season on record, week 1 rates teams off last year's
    margin and labels the basis, rather than pretending it knows nothing."""
    league.execute(
        "INSERT INTO team_week_stats (season, week, team, opponent, points_for,"
        " points_against) VALUES (2024, 1, 'KC', 'BUF', 31, 10)"
    )
    league.execute(
        "INSERT INTO team_week_stats (season, week, team, opponent, points_for,"
        " points_against) VALUES (2024, 1, 'BUF', 'KC', 10, 31)"
    )
    league.commit()
    game_id = league.execute(
        "SELECT id FROM games WHERE week = 1 AND (home = 'KC' OR away = 'KC')"
    ).fetchone()["id"]
    ctx = context.build_game_context(league, game_id)
    kc_side = "home" if ctx.home == "KC" else "away"
    assert getattr(ctx, f"{kc_side}_srs") == 21.0
    assert ctx.srs_basis in ("prior_season", "none")


def test_week_one_falls_back_to_last_season_and_says_so(league):
    game_id = league.execute("SELECT id FROM games WHERE week = 1 LIMIT 1").fetchone()["id"]
    ctx = context.build_game_context(league, game_id)
    assert ctx.home_games_played == 0
    assert ctx.srs_basis in ("prior_season", "none")
    assert any("fall back" in n or "no rating" in n for n in ctx.notes)


def test_player_history_stops_at_the_cutoff(league):
    game_id = league.execute("SELECT id FROM games WHERE week = 5 LIMIT 1").fetchone()["id"]
    game = league.execute("SELECT home FROM games WHERE id = ?", (game_id,)).fetchone()
    ctx = context.build_prop_context(
        league, game_id, f"QB-{game['home']}", "passing_yards", 240.0
    )
    assert ctx.rolling_n == 4, "weeks 1-4 only"


# --- the context carries no line -------------------------------------------

def test_no_context_field_can_hold_a_line():
    fields = set(context.GameContext.__dataclass_fields__) | set(
        context.PropContext.__dataclass_fields__
    )
    forbidden = [
        f for f in fields
        if any(w in f for w in ("spread", "moneyline", "odds", "implied", "market"))
    ]
    assert forbidden == [], f"LAW 1: a market value could be carried in {forbidden}"
    # `line_asked` is ours, not the market's, and is the only "line" allowed.
    assert "line_asked" in context.PropContext.__dataclass_fields__


def test_factor_set_version_is_declared():
    assert config.FACTOR_SET_VERSION
