"""S1: the multi-sport core, and LAW 6's tripwire.

LAW 6 says no figure ever mixes two sports. The mechanism is not a convention
about writing careful queries: `sport` is a REQUIRED argument on every function
that reads the record, so the only way to write a cross-sport query is to delete
the parameter — and then the tripwire fires by name.
"""

from __future__ import annotations

import sqlite3

import pytest

from gridiron import audit, calibration, config, db, views
from gridiron.factors import compute, context, registry
from gridiron.market import lines, sources
from gridiron.model import baseline


# --- the sport column -------------------------------------------------------

@pytest.mark.parametrize(
    "table", ["games", "predictions", "factors", "factor_scores", "model_fits"]
)
def test_every_record_table_carries_its_sport(conn, table):
    assert "sport" in db.table_columns(conn, table)


def test_existing_rows_backfill_to_nfl(conn):
    """Rows written before there was a second sport keep the only value they
    could have had, rather than a NULL that later code has to guess about."""
    conn.execute(
        "INSERT INTO games (id, season, week, game_type, home, away, status)"
        " VALUES ('x', 2025, 1, 'REG', 'KC', 'BUF', 'scheduled')"
    )
    conn.commit()
    assert conn.execute("SELECT sport FROM games WHERE id='x'").fetchone()[0] == "nfl"


def test_a_sport_outside_the_declared_set_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away, status)"
            " VALUES ('y', 'cricket', 2025, 1, 'REG', 'A', 'B', 'scheduled')"
        )


# --- LAW 6: the tripwire ----------------------------------------------------

READERS = [
    ("resolved", lambda c, s: calibration.resolved(c, sport=s)),
    ("curve", lambda c, s: calibration.curve(c, sport=s)),
    ("edge", lambda c, s: calibration.edge(c, sport=s)),
    ("scorecard", lambda c, s: calibration.scorecard(c, sport=s)),
    ("factor_report", lambda c, s: calibration.factor_report(c, sport=s)),
    ("over_time", lambda c, s: calibration.over_time(c, sport=s)),
    ("void_count", lambda c, s: calibration.void_count(c, sport=s)),
    ("version_comparison", lambda c, s: calibration.version_comparison(c, sport=s)),
    ("views.week", lambda c, s: views.week(c, s)),
    ("views.history", lambda c, s: views.history(c, sport=s)),
    ("views.factors", lambda c, s: views.factors(c, s)),
]


@pytest.mark.parametrize("name,call", READERS, ids=[r[0] for r in READERS])
@pytest.mark.parametrize("bad", [None, "", "all"])
def test_every_reader_refuses_a_cross_sport_query(league, name, call, bad):
    with pytest.raises(calibration.CrossSportAggregation) as exc:
        call(league, bad)
    assert "LAW 6" in str(exc.value)
    assert "exactly one sport" in str(exc.value) or "unknown sport" in str(exc.value)


@pytest.mark.parametrize("name,call", READERS, ids=[r[0] for r in READERS])
def test_every_reader_refuses_an_undeclared_sport(league, name, call):
    with pytest.raises(calibration.CrossSportAggregation, match="unknown sport"):
        call(league, "cricket")


def test_a_reader_scoped_to_one_sport_sees_only_that_sport(league):
    """The other half: the scoping is real, not merely required."""
    league.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away, status,"
        " home_score, away_score) VALUES ('mlb_x','mlb',2026,1,'REG','NYY','BOS',"
        " 'final',5,3)"
    )
    league.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning, resolved_utc, outcome)"
        " VALUES (?, 'mlb', 'mlb_x', 'moneyline', 'NYY', NULL, 0.61, 'win',"
        " 'statistical', 'fs2', '{}', 'test', ?, 1)",
        (db.utcnow(), db.utcnow()),
    )
    league.commit()

    assert len(calibration.resolved(league, sport="mlb")) == 1
    nfl = calibration.resolved(league, sport="nfl")
    assert all(r.sport == "nfl" for r in nfl)
    assert not any(r.game_id == "mlb_x" for r in nfl)


def test_a_payload_stitched_from_two_sports_is_caught(league):
    payload = calibration.scorecard(league, sport="nfl")
    intruder = dict(payload["categories"][0])
    intruder["sport"] = "mlb"
    payload["categories"].append(intruder)
    with pytest.raises(calibration.CrossSportAggregation) as exc:
        calibration.assert_single_sport(payload, "nfl")
    assert "never stitched into one record" in str(exc.value)


def test_the_tab_summary_is_the_one_permitted_multi_sport_structure(league):
    """Listing sports side by side is display, not aggregation. It is marked
    explicitly rather than left for the validator to guess about."""
    summary = views.sports_summary(league)
    assert summary["side_by_side_sports"] is True
    assert [s["sport"] for s in summary["sports"]] == list(config.SPORTS)
    assert "n" not in summary, "a cross-sport total is the exact thing LAW 6 forbids"
    for entry in summary["sports"]:
        assert isinstance(entry["n"], int)      # LAW 4: every tab carries its N
    calibration.assert_single_sport({"x": summary}, "nfl")   # must not raise


# --- the registry namespaces by sport ---------------------------------------

def test_factor_names_are_globally_unique():
    names = [f.name for f in registry.REGISTRY.values()]
    assert len(names) == len(set(names))


def test_every_non_nfl_factor_is_prefixed_with_its_sport():
    for f in registry.REGISTRY.values():
        if f.sport != "nfl":
            assert f.name.startswith(f"{f.sport}_"), (
                f"{f.name} belongs to {f.sport} but is not prefixed"
            )


def test_declaring_an_unprefixed_foreign_factor_is_refused():
    with pytest.raises(ValueError, match="LAW 6"):
        @registry.factor(
            added="2026-08-29T00:00:00Z",
            sport="nba",
            applies_to=("spread",),
            rationale=(
                "A planted collision with another sport's namespace, which is "
                "exactly what the prefix rule exists to prevent."
            ),
        )
        def home_court(ctx):
            return 1.0


def test_active_factors_requires_a_sport():
    with pytest.raises(TypeError):
        registry.active_factors("spread")


def test_active_factors_never_leaks_across_sports():
    for sport in config.SPORTS:
        for market in config.SPORT_MARKETS.get(sport, ()):
            market_type = calibration.market_type_of(sport, market)
            for f in registry.active_factors(sport, market_type):
                assert f.sport == sport


# --- a context must say whose factors apply ---------------------------------

def test_a_context_with_no_sport_cannot_produce_a_vector():
    class Anonymous:
        notes: list = []

    with pytest.raises(compute.SportNotOnContext, match="LAW 6"):
        compute.feature_vector(Anonymous(), "spread")


def test_a_real_context_carries_its_sport(league):
    game_id = league.execute("SELECT id FROM games LIMIT 1").fetchone()["id"]
    ctx = context.build_game_context(league, game_id)
    assert ctx.sport == "nfl"
    fv = compute.feature_vector(ctx, "spread")
    assert fv.sport == "nfl"
    assert fv.to_json_dict()["sport"] == "nfl"


# --- one fitted model per market per sport ----------------------------------

def test_market_keys_name_their_sport():
    assert baseline.market_key("nfl", "spread") == "nfl:spread"
    assert baseline.market_key("mlb", "moneyline") == "mlb:moneyline"
    assert baseline.market_key("nba", "points") == "nba:prop:points"
    assert baseline.split_key("nba:prop:points") == ("nba", "prop:points")


def test_a_fit_is_looked_up_within_its_sport(league):
    from gridiron.factors import store

    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), sport="nfl", l2=1.0, min_rows=20)
    assert baseline.load_fit(league, "nfl:spread")
    with pytest.raises(baseline.NotTrained):
        baseline.load_fit(league, "nba:spread")


# --- the per-sport import-closure audit -------------------------------------

def test_every_sport_has_its_own_prediction_closure():
    entrypoints = audit.prediction_entrypoints()
    assert set(entrypoints) == {"shared", *config.SPORTS}
    reports = audit.check_all_prediction_closures()
    for name, report in reports.items():
        assert not any(m.startswith("gridiron.market") for m in report.modules), name


def test_a_market_import_planted_in_one_sport_is_caught_in_that_sport(tmp_path):
    """Per-sport, not aggregate: baseball's violation is named as baseball's."""
    import shutil

    root = tmp_path / "gridiron"
    shutil.copytree(config.PACKAGE_ROOT, root)
    victim = root / "sports" / "nfl.py"
    victim.write_text(
        victim.read_text(encoding="utf-8") + "\nfrom ..market import lines  # PLANTED\n",
        encoding="utf-8",
    )
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_prediction_closure("gridiron.sports.nfl", root=root)
    assert "gridiron.market" in str(exc.value)


def test_moneyline_is_a_market_name_not_a_forbidden_price():
    """Our vocabulary and the market's collided; the more precise name won.

    `moneyline` names MLB's question. `home_moneyline` names the price, and
    that is what the prediction path may not touch.
    """
    assert "home_moneyline" in audit.FORBIDDEN_IDENTIFIERS
    assert "away_moneyline" in audit.FORBIDDEN_IDENTIFIERS
    assert "moneyline" not in audit.FORBIDDEN_IDENTIFIERS


# --- line sourcing, stated honestly -----------------------------------------

@pytest.mark.parametrize("sport", config.SPORTS)
def test_every_sport_declares_its_line_source_or_its_absence(sport):
    entry = sources.for_sport(sport)
    assert "available" in entry
    if entry["available"]:
        assert entry["name"] and entry["url"]
        assert entry["licence"], "a source with no stated licence must say so"
        assert entry["rate_limit"]
        assert entry["markets"]
    else:
        assert entry["reason"]


@pytest.mark.parametrize("sport", config.SPORTS)
def test_no_prop_market_claims_a_line_that_does_not_exist(sport):
    for market in config.SPORT_PROP_MARKETS.get(sport, ()):
        entry = sources.for_market(sport, market)
        assert entry["available"] is False
        assert len(entry["reason"]) > 40, "an absence must be explained, not asserted"


def test_an_unpriced_market_reports_absence_rather_than_a_number():
    entry = sources.for_market("mlb", "spread")
    assert entry["available"] is False
    assert "not" in entry["reason"]


def test_the_espn_licence_is_recorded_as_unstated():
    """It is an undocumented endpoint. Saying so is the point."""
    for sport in ("mlb", "nba"):
        assert "NONE STATED" in sources.for_sport(sport)["licence"]


def test_a_card_carries_why_its_market_has_no_line():
    availability = lines.market_availability("nfl", "receptions")
    assert availability["available"] is False
    assert availability["reason"]


# --- moneyline arithmetic ---------------------------------------------------

def test_american_odds_convert_to_probabilities():
    assert lines.american_to_probability(-200) == pytest.approx(2 / 3)
    assert lines.american_to_probability(100) == pytest.approx(0.5)
    assert lines.american_to_probability(200) == pytest.approx(1 / 3)


def test_the_raw_pair_carries_the_vig_and_the_devigged_pair_does_not():
    raw = (lines.american_to_probability(-193) + lines.american_to_probability(179))
    assert raw > 1.0, "a posted pair sums to more than one; that is the margin"
    home, away = lines.devig_pair(-193, 179)
    assert home + away == pytest.approx(1.0)
    assert home < lines.american_to_probability(-193)
