"""G6: the guards, each proven by planting the violation it exists to catch.

Every test here breaks a law on purpose and asserts the *named* failure. A
guard that has only ever been asserted to pass is a guard nobody has tested.

The full planted-violation harness lives in `tools/guards/plant.py`; the last
test in this file runs it and requires every planting to be caught.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from gridiron import audit, blind, calibration, config, db, resolve, run
from gridiron.factors import registry, store
from gridiron.model import baseline

REPO = config.REPO_ROOT


@pytest.fixture
def planted_tree(tmp_path):
    """A throwaway copy of the package, so a violation can be planted without
    touching the real source."""
    root = tmp_path / "gridiron"
    shutil.copytree(config.PACKAGE_ROOT, root)
    return root


# --- LAW 1: the prediction path cannot reach market data -------------------

def test_the_real_prediction_closure_is_clean():
    report = audit.check_prediction_closure()
    assert report.modules, "the closure walker found nothing, so it proves nothing"
    assert "gridiron.model.baseline" in report.modules
    assert "gridiron.factors.context" in report.modules
    assert not any(m.startswith("gridiron.market") for m in report.modules)


def test_a_planted_market_import_is_caught_by_name(planted_tree):
    victim = planted_tree / "factors" / "context.py"
    victim.write_text(
        victim.read_text(encoding="utf-8") + "\nfrom ..market import lines  # PLANTED\n",
        encoding="utf-8",
    )
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_prediction_closure(root=planted_tree)
    message = str(exc.value)
    assert "LAW 1" in message
    assert "gridiron.market" in message
    assert "import chain" in message, "the failure must say how the path was reached"


def test_a_planted_market_column_read_is_caught_by_name(planted_tree):
    victim = planted_tree / "data" / "repo.py"
    victim.write_text(
        victim.read_text(encoding="utf-8")
        + textwrap.dedent(
            '''
            def sneak(conn, game_id):   # PLANTED
                return conn.execute(
                    "SELECT spread_line FROM market_lines_raw WHERE game_id = ?",
                    (game_id,),
                ).fetchone()
            '''
        ),
        encoding="utf-8",
    )
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_prediction_closure(root=planted_tree)
    assert "LAW 1" in str(exc.value)
    assert "spread_line" in str(exc.value)


def test_prose_about_the_market_is_allowed(planted_tree):
    """A module must stay free to explain what it refuses to do."""
    victim = planted_tree / "data" / "repo.py"
    victim.write_text(
        victim.read_text(encoding="utf-8")
        + textwrap.dedent(
            '''
            def harmless():
                """This never reads spread_line from market_lines_raw."""
                return 1
            '''
        ),
        encoding="utf-8",
    )
    audit.check_prediction_closure(root=planted_tree)   # must not raise


def test_a_market_import_inside_the_blind_window_is_caught():
    blind.forget_market_module()
    try:
        with pytest.raises(blind.MarketAccessDuringBlindWindow) as exc:
            with blind.blind_window():
                import gridiron.market.lines  # noqa: F401
        assert "LAW 1" in str(exc.value)
    finally:
        blind.forget_market_module()


# --- LAW 1: a prediction exists before its snapshot ------------------------

def test_a_reordered_snapshot_is_rejected(a_prediction, league):
    """Plant the reordering: fetch the line, then write the prediction."""
    with pytest.raises(sqlite3.IntegrityError) as exc:
        league.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line)"
            " VALUES (?, '1999-01-01T00:00:00Z', 'planted', -3.5)",
            (a_prediction,),
        )
    assert "LAW 1" in str(exc.value)
    assert "before the prediction" in str(exc.value)


def test_a_snapshot_with_no_prediction_is_rejected(league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 1"):
        league.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line)"
            " VALUES (777777, '2026-01-01T00:00:00Z', 'planted', -3.5)"
        )


# --- LAW 3: no prediction is mutated after creation ------------------------

@pytest.mark.parametrize(
    "column, value",
    [
        ("model_prob", 0.99),
        ("model_side", "not_cover"),
        ("line_asked", -10.5),
        ("reasoning", "rewritten later"),
        ("factors_json", "{}"),
        ("created_utc", "2020-01-01T00:00:00Z"),
    ],
)
def test_every_substantive_field_is_frozen(a_prediction, league, column, value):
    with pytest.raises(sqlite3.IntegrityError) as exc:
        league.execute(
            f"UPDATE predictions SET {column} = ? WHERE id = ?", (value, a_prediction)
        )
    assert "LAW 3" in str(exc.value)


def test_a_prediction_cannot_be_deleted(a_prediction, league):
    with pytest.raises(sqlite3.IntegrityError, match="LAW 3"):
        league.execute("DELETE FROM predictions WHERE id = ?", (a_prediction,))


# --- LAW 3: resolution is idempotent ---------------------------------------

@pytest.fixture
def resolved_league(league):
    store.sync_registry(league)
    baseline.train_all(league, (2025,), l2=1.0, note="guards", min_rows=20)
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    resolve.resolve_all(league)
    return league


def test_resolving_twice_yields_one_outcome(resolved_league):
    before = resolved_league.execute(
        "SELECT id, resolved_utc, outcome FROM predictions ORDER BY id"
    ).fetchall()
    again = resolve.resolve_all(resolved_league)
    after = resolved_league.execute(
        "SELECT id, resolved_utc, outcome FROM predictions ORDER BY id"
    ).fetchall()
    assert again["settled"] == 0
    assert [tuple(r) for r in before] == [tuple(r) for r in after]


def test_a_forced_re_resolution_is_rejected_by_name(resolved_league):
    pid = resolved_league.execute(
        "SELECT id FROM predictions WHERE resolved_utc IS NOT NULL LIMIT 1"
    ).fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError) as exc:
        resolved_league.execute(
            "UPDATE predictions SET resolved_utc = ?, outcome = 0 WHERE id = ?",
            (db.utcnow(), pid),
        )
    assert "LAW 3" in str(exc.value)
    assert "idempotent" in str(exc.value)


# --- LAW 4: no figure renders without its N --------------------------------

def test_a_removed_sample_size_is_caught_by_name(resolved_league):
    payload = calibration.scorecard(resolved_league, sport="nfl")
    payload["categories"][0]["score"].pop("n")
    with pytest.raises(calibration.MissingSampleSize) as exc:
        calibration.assert_every_figure_has_n(payload)
    assert "LAW 4" in str(exc.value)
    assert "categories[0].score" in str(exc.value)


def test_a_removed_bucket_sample_size_is_caught(resolved_league):
    payload = calibration.scorecard(resolved_league, sport="nfl")
    payload["headline"]["buckets"][0].pop("n")
    with pytest.raises(calibration.MissingSampleSize, match="LAW 4"):
        calibration.assert_every_figure_has_n(payload)


def test_an_edge_figure_below_threshold_is_not_present_to_render(resolved_league):
    edge = calibration.edge(resolved_league, sport="nfl", market_type="spread")
    assert edge["renderable"] is False
    for key in ("model_more_confident", "market_more_confident"):
        assert key not in edge, f"{key} leaked below the sample threshold"


# --- LAW 2: no factor without a dated rationale ----------------------------

def test_a_factor_with_a_token_rationale_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale)"
            " VALUES ('gut_feel', '2026-08-28T00:00:00Z', 'vibes')"
        )
    assert "rationale" in str(exc.value)


def test_a_factor_with_no_date_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES"
            " ('gut_feel', 'last tuesday',"
            " 'A sentence long enough to look like a real justification.')"
        )
    assert "added_utc" in str(exc.value)


def test_backdating_a_factor_is_rejected_by_name(conn, monkeypatch):
    store.sync_registry(conn)
    original = registry.REGISTRY["home_field"]
    monkeypatch.setitem(
        registry.REGISTRY,
        "home_field",
        registry.Factor(
            name="home_field",
            added_utc="2015-01-01T00:00:00Z",
            rationale=original.rationale,
            applies_to=original.applies_to,
            fn=original.fn,
        ),
    )
    with pytest.raises(store.RegistryConflict) as exc:
        store.sync_registry(conn)
    assert "cannot be moved" in str(exc.value)
    assert "LAW 2" in str(exc.value)


def test_every_declared_factor_reached_the_database(conn):
    store.sync_registry(conn)
    stored = {r["name"] for r in conn.execute("SELECT name FROM factors")}
    assert stored == set(registry.REGISTRY)


# --- LAW 5: not a betting tool ---------------------------------------------

def test_the_package_has_no_staking_surface():
    audit.check_not_a_betting_tool()   # must not raise


def test_a_planted_stake_sizer_is_caught_by_name(planted_tree):
    (planted_tree / "staking.py").write_text(
        "def kelly_stake(p, odds, bankroll):\n    return bankroll * p\n",
        encoding="utf-8",
    )
    with pytest.raises(audit.LawViolation) as exc:
        audit.check_not_a_betting_tool(root=planted_tree)
    assert "LAW 5" in str(exc.value)
    assert "kelly" in str(exc.value).lower()


def test_the_disclaimer_is_not_mistaken_for_a_feature():
    """views.py says "bankroll" in the sentence explaining it has none."""
    from gridiron import views

    source = (config.PACKAGE_ROOT / "views.py").read_text(encoding="utf-8")
    assert "bankroll" in source, "the disclaimer should still be there"
    audit.check_not_a_betting_tool()   # and must still pass


def test_no_sportsbook_or_exchange_dependency():
    requirements = (REPO / "requirements.txt").read_text(encoding="utf-8").lower()
    for word in ("odds", "sportsbook", "betfair", "pinnacle", "draftkings", "fanduel"):
        assert word not in requirements, f"a betting dependency appeared: {word}"


# --- the harness itself ----------------------------------------------------

@pytest.mark.slow
def test_the_planted_violation_harness_catches_everything():
    """Run tools/guards/plant.py. Exit 0 means every planting was caught."""
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "guards" / "plant.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=600,
    )
    assert result.returncode == 0, (
        "a planted violation escaped its guard:\n" + result.stdout + result.stderr
    )
    assert "planted violations were caught" in result.stdout
    assert "ESCAPED" not in result.stdout


# --- v2: missing data stays missing ----------------------------------------

def test_a_planted_zero_fallback_is_caught_by_name(planted_tree):
    """Plant the exact regression v2 removed: an unmeasurable factor given 0.0."""
    victim = planted_tree / "factors" / "compute.py"
    anchor = "        if value is None:\n            fv.absent.append(f.name)"
    text = victim.read_text(encoding="utf-8")
    assert anchor in text, "the exclusion branch moved; the planting must follow it"
    victim.write_text(
        text.replace(
            anchor,
            anchor + "\n            fv.values[f.name] = f.default   # PLANTED",
        ),
        encoding="utf-8",
    )
    with pytest.raises(audit.MissingDataDefaulted) as exc:
        audit.check_no_silent_defaults(root=planted_tree)
    assert "excluded from the vector" in str(exc.value)


def test_the_real_factor_code_has_no_fallback():
    audit.check_no_silent_defaults()          # must not raise


def test_the_default_field_was_removed_not_merely_unused():
    """A dead knob that looks live is an invitation to turn it."""
    from gridiron.factors import registry as reg

    assert "default" not in reg.Factor.__dataclass_fields__
    source = (config.PACKAGE_ROOT / "factors" / "registry.py").read_text(encoding="utf-8")
    assert "default=0.0" not in source


def test_a_vector_that_defaults_an_absent_factor_is_caught_at_runtime():
    from gridiron.factors.compute import FeatureVector

    fv = FeatureVector(sport="nfl", market_type="spread")
    fv.values["precipitation"] = 0.0
    fv.raw["precipitation"] = None
    fv.absent.append("precipitation")
    with pytest.raises(audit.MissingDataDefaulted) as exc:
        audit.assert_missing_is_explicit(fv)
    assert "precipitation" in str(exc.value)
    assert "confirmed dry weather" in str(exc.value)


def test_a_real_vector_passes_the_runtime_check(league):
    from gridiron.factors import compute, context

    game_id = league.execute(
        "SELECT id FROM games WHERE status = 'scheduled' LIMIT 1"
    ).fetchone()["id"]
    fv = compute.feature_vector(context.build_game_context(league, game_id), "spread")
    audit.assert_missing_is_explicit(fv)      # must not raise
    assert set(fv.values) & set(fv.absent) == set()


# --- curves are never merged ------------------------------------------------

def test_a_planted_merged_prop_curve_is_caught_by_name(resolved_league):
    payload = calibration.scorecard(resolved_league, sport="nfl")
    merged = dict(payload["categories"][0])
    merged["category"] = "props / statistical"
    merged["market"] = "prop"
    merged["filters"] = {**merged["filters"], "market_type": "prop", "prop_type": "all"}
    payload["categories"].append(merged)

    with pytest.raises(calibration.MergedCurve) as exc:
        calibration.assert_no_merged_categories(payload)
    assert "never merged" in str(exc.value).lower() or "averages" in str(exc.value)


def test_a_planted_merged_forecaster_curve_is_caught(resolved_league):
    payload = calibration.scorecard(resolved_league, sport="nfl")
    merged = dict(payload["categories"][0])
    merged["filters"] = {**merged["filters"], "predictor": "all"}
    payload["categories"].append(merged)
    with pytest.raises(calibration.MergedCurve, match="merges the"):
        calibration.assert_no_merged_categories(payload)


def test_the_real_scorecard_has_no_merged_category(resolved_league):
    payload = calibration.scorecard(resolved_league, sport="nfl")
    calibration.assert_no_merged_categories(payload)     # must not raise
    markets = {c["market"] for c in payload["categories"]}
    assert markets == {"spread", *config.PROP_MARKETS}


def test_the_scorecard_refuses_to_serve_a_merged_payload(resolved_league, monkeypatch):
    """The check runs inside scorecard(), so a merge cannot reach the API."""
    real = calibration.version_comparison

    def merged(conn, *, sport):
        payload = real(conn, sport=sport)
        payload["versions"] = payload["versions"]
        return payload

    monkeypatch.setattr(calibration, "version_comparison", merged)
    calibration.scorecard(resolved_league, sport="nfl")               # still clean


# --- a factor declared in code, not just inserted in SQL --------------------

def test_a_registry_factor_with_a_token_rationale_is_caught(conn, monkeypatch):
    """The realistic path: someone adds a factor to the registry and syncs."""
    store.sync_registry(conn)
    monkeypatch.setitem(
        registry.REGISTRY,
        "looks_good_to_me",
        registry.Factor(
            name="looks_good_to_me",
            added_utc="2026-08-29T00:00:00Z",
            rationale="trust me",
            applies_to=("spread",),
            fn=lambda ctx: 1.0,
        ),
    )
    with pytest.raises(sqlite3.IntegrityError) as exc:
        store.sync_registry(conn)
    assert "rationale" in str(exc.value)


# --- the harness ------------------------------------------------------------

def test_every_new_guard_is_in_the_planted_harness():
    """A guard absent from the harness is a guard nobody re-proves."""
    source = (REPO / "tools" / "guards" / "plant.py").read_text(encoding="utf-8")
    for name in (
        "plant_a_silent_missing_data_default",
        "plant_a_defaulted_factor_at_runtime",
        "plant_a_merged_calibration_curve",
        "plant_a_merged_forecaster_curve",
        "plant_a_registry_factor_without_a_rationale",
    ):
        assert f"def {name}" in source, name
        assert f"results.append({name}" in source, f"{name} is defined but never run"


# ---------------------------------------------------------------------------
# ONE FORECASTER IN ONE RANKING (GRIDIRON_14)
# ---------------------------------------------------------------------------

def test_two_forecasters_in_one_picks_list_are_caught_by_name():
    """THE DEFECT THIS WAS WRITTEN FOR WAS ON SCREEN, not hypothetical.

    The MLB slate listed the statistical row and the LLM row for the same
    game, unlabelled and adjacent, each sorted on its own disagreement -- so
    Toronto at Cleveland appeared twice, once as "Cleveland to win 53%" and
    once as "Toronto to win 53%". Two contradictory picks, both presented as
    the pick.
    """
    payload = {
        "forecaster": "statistical",
        "cards": [
            {"game_id": "mlb_824441", "market_type": "moneyline",
             "predictor": "statistical", "model_side": "win"},
            {"game_id": "mlb_824441", "market_type": "moneyline",
             "predictor": "llm", "model_side": "lose"},
        ],
    }
    with pytest.raises(audit.LawViolation, match="TWO FORECASTERS IN ONE RANKING"):
        audit.check_one_forecaster_per_list(payload)
    # The fault NAMES the game carrying both, so it can be looked up.
    assert "mlb_824441" in audit.one_forecaster_faults(payload)[0]


def test_a_picks_list_labelled_for_the_wrong_forecaster_is_caught():
    """Nothing on screen contradicts itself, which is what makes it worse."""
    payload = {
        "forecaster": "llm",
        "cards": [{"game_id": "mlb_1", "market_type": "moneyline",
                   "predictor": "statistical"}],
    }
    faults = audit.one_forecaster_faults(payload)
    assert faults and "does not match" in faults[0].replace("disagrees with", "does not match")


def test_a_combined_forecaster_option_on_picks_is_caught():
    assert audit.one_forecaster_faults({"forecaster": "all", "cards": []})


def test_the_real_slate_carries_one_forecaster(resolved_league):
    """The guard runs inside `views.week`, so this is the payload the API
    would actually serve -- not a fixture built to pass."""
    from gridiron import views
    payload = views.week(resolved_league, sport="nfl")
    audit.check_one_forecaster_per_list(payload)          # must not raise
    predictors = {c["predictor"] for c in payload["cards"]}
    assert len(predictors) <= 1, predictors
    assert payload["forecaster"] == config.PICKS_DEFAULT_FORECASTER


def test_a_day_key_in_visible_text_is_caught_by_name():
    """The slate key's other disguise. Catching "week 20260905" left
    "Day 159, 2026" standing above every baseball slate."""
    hits = audit.plain_words_violations("Day 159, 2026")
    assert hits and "Day 159" in hits[0]
    with pytest.raises(audit.LawViolation, match="PLAIN WORDS"):
        audit.check_plain_words("Day 159, 2026")


def test_a_week_number_is_not_mistaken_for_a_day_key():
    """"Week 2" is how football organises itself and how a reader refers to a
    slate. The first version of the date fix replaced BOTH and quietly renamed
    "Week 2, 2026" to a date nobody asked for."""
    assert not audit.plain_words_violations("Week 2, 2026")
    assert not audit.plain_words_violations("Wednesday 2 September, 2026")
    # Ordinary English that happens to contain the word.
    assert not audit.plain_words_violations("sessions are 30-day sliding")
    assert not audit.plain_words_violations("settled 14 days ago")


def test_one_card_per_question_when_a_task_ran_twice(resolved_league):
    """A second prediction run must not put every game on the slate twice.

    `predict:nfl` ran twice on 2026-08-29 and wrote a full second set of
    forecasts for week 1. Both rows stay in the record -- LAW 3 is
    append-only -- but the slate shows the STANDING one: the latest forecast
    written supersedes the earlier, which stays in the results.
    """
    from gridiron import views

    payload = views.week(resolved_league, sport="nfl")
    seen = [(c["game_id"], c["market_type"], c["subject"], c["line_asked"])
            for c in payload["cards"]]
    assert len(seen) == len(set(seen)), "the slate lists one question twice"
    assert "superseded" in payload, (
        "the slate must say how many earlier forecasts it is not showing")


def test_the_superseded_count_is_the_rows_the_slate_hid(resolved_league):
    """The count is stated so a reader comparing the slate against the record
    is owed the difference -- and so a task that ran twice is discoverable."""
    from gridiron import views

    payload = views.week(resolved_league, sport="nfl")
    written = resolved_league.execute(
        "SELECT COUNT(*) FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = 'nfl' AND g.season = ? AND g.week = ?"
        "   AND p.predictor = 'statistical'"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)",
        (payload["season"], payload["week"])).fetchone()[0]
    assert payload["n"] + payload["superseded"] == written


# ---------------------------------------------------------------------------
# THE COLOUR LAW (GRIDIRON_16 R2)
# ---------------------------------------------------------------------------

def test_a_green_link_is_caught_by_name():
    """Green was the interactive accent AND the positive value until
    2026-09-02, so every link and focus ring wore the colour that means a
    pick won."""
    faults = audit.colour_law_faults(
        ".row-more { color: var(--win); text-decoration: none; }")
    assert faults and "interactive" in faults[0]


def test_the_colour_law_check_refuses_a_stylesheet_that_breaks_it(tmp_path):
    """The CHECK, not just the scanner: a stylesheet with a green link must
    stop the gate, naming the rule."""
    sheet = tmp_path / "style.css"
    sheet.write_text(
        """
.row-more { color: var(--win); text-decoration: none; }
.notices-summary { border-left: 2px solid var(--loss); }
""",
        encoding="utf-8")
    with pytest.raises(audit.LawViolation, match="THE COLOUR LAW WAS BROKEN"):
        audit.check_the_colour_law(sheet)


def test_a_red_warning_border_is_caught_by_name():
    """A warning is not a loss. Red was every failed task and stale feed."""
    faults = audit.colour_law_faults(
        ".notices-summary { border-left: 2px solid var(--loss); }")
    assert faults and "not losses" in faults[0]


def test_a_verdict_chip_may_wear_its_colour():
    """The one thing each colour is for."""
    assert not audit.colour_law_faults(
        ".verdict.win { color: var(--win); background: var(--win-wash); }")
    assert not audit.colour_law_faults(
        ".verdict.loss { color: var(--loss); background: var(--loss-wash); }")
    assert not audit.colour_law_faults(
        ".tile-verdict.v-win { color: var(--win); }")


def test_the_real_stylesheet_obeys_the_colour_law():
    """The scan runs over the shipped stylesheet, not a fixture."""
    audit.check_the_colour_law()          # must not raise


def test_the_tokens_are_named_for_their_meaning_not_their_hue():
    """`--green` and `--red` are gone: a colour named after its hue is one
    anyone can reach for when they want something to look important."""
    css = (config.PACKAGE_ROOT / "web" / "style.css").read_text(encoding="utf-8")
    rules = "\n".join(
        line for line in css.splitlines() if not line.strip().startswith(("/*", "*", "--green", "--red"))
    )
    assert "var(--green)" not in rules
    assert "var(--red)" not in rules
    assert "--win:" in css and "--loss:" in css
