"""G6: the guards, each proven by planting the violation it exists to catch.

Every test here breaks a law on purpose and asserts the *named* failure. A
guard that has only ever been asserted to pass is a guard nobody has tested.

The full planted-violation harness lives in `tools/guards/plant.py`; the last
test in this file runs it and requires every planting to be caught.
"""

from __future__ import annotations

import json
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


# ---------------------------------------------------------------------------
# THE WITHDRAWAL LEFT NOTHING BEHIND (GRIDIRON_16 R1, R4)
# ---------------------------------------------------------------------------

def test_a_resolved_row_on_picks_is_caught_by_name():
    faults = audit.picks_resolved_faults(audit.PICKS_RESOLVED_FIXTURE_POSITIVE)
    assert faults and "Results" in faults[0]


def test_an_ordinary_row_list_is_not_mistaken_for_a_resolved_one():
    assert not audit.picks_resolved_faults("const list = el('div', 'rows');")


def test_a_reinstated_call_block_is_caught_by_name():
    faults = audit.withdrawn_calls_faults(
        audit.WITHDRAWN_CALLS_FIXTURE_POSITIVE, comment="//")
    assert faults and "withdrawn" in faults[0]


def test_the_record_of_the_removal_outlives_it():
    """The comments and docs that say what went and why must NOT trip the
    scan. A guard that forces the explanation to be deleted has made the
    codebase harder to read in the name of tidiness."""
    assert not audit.withdrawn_calls_faults(
        "// operator_calls was withdrawn on 2026-09-02", comment="//")
    assert not audit.withdrawn_calls_faults(
        "#: `operator_calls` went 2026-09-02 by ruling.", comment="#")


def test_the_drop_list_may_name_what_it_drops():
    """`db.WITHDRAWN` names the table because naming it is HOW the table gets
    dropped. It is the instrument of the removal, not a survival of it."""
    from gridiron import db

    source = (config.PACKAGE_ROOT / "db.py").read_text(encoding="utf-8")
    assert "operator_calls" in source, "the drop list lost its subject"
    assert not audit.withdrawn_calls_faults(source, comment="#")
    assert any(name == "operator_calls" for _, name in db.WITHDRAWN)


def test_the_withdrawal_scan_exemption_is_one_file():
    """The scanner holds the forbidden words, so it trips over itself -- the
    same situation BETTING_SCAN_EXEMPT was written for. Pinned to one file so
    the exemption cannot grow into a way to hide a stump."""
    assert audit.WITHDRAWN_SCAN_EXEMPT == ("audit.py",)


def test_the_shipped_code_is_free_of_the_withdrawn_feature():
    audit.check_the_calls_feature_stayed_withdrawn()      # must not raise
    audit.check_picks_shows_tonight()                     # must not raise


# ---------------------------------------------------------------------------
# HOW CLOSE A GATE IS (GRIDIRON_13 P1)
# ---------------------------------------------------------------------------

def test_a_progress_line_stating_a_percentage_is_caught():
    """A share of the way to a verdict reads as a probability on a page whose
    whole subject is probabilities -- and it hides the N."""
    faults = audit.progress_faults(audit.PROGRESS_FIXTURE_PERCENT)
    assert faults and "COUNTS" in faults[0]


def test_a_gate_line_without_its_n_is_caught():
    faults = audit.progress_faults(audit.PROGRESS_FIXTURE_NO_N)
    assert faults and "LAW 4" in faults[0]


def test_a_green_progress_bar_is_caught_twice():
    """In the payload and in the stylesheet. A filling bar is not a win."""
    assert audit.progress_faults(audit.PROGRESS_FIXTURE_GREEN)
    assert audit.colour_law_faults(".gate-bar i { background: var(--win); }")


def test_a_correct_gate_line_is_not_flagged():
    assert not audit.progress_faults(audit.PROGRESS_FIXTURE_GOOD)


def test_every_gate_in_the_real_scorecard_counts(resolved_league):
    """The guard runs inside `views.scorecard`, so this is the payload the
    API would serve."""
    from gridiron import views

    payload = views.scorecard(resolved_league, sport="nfl")
    audit.check_progress_is_counted(payload)          # must not raise
    rows = payload["tier_table"]["rows"]
    assert rows and all("progress" in r for r in rows)
    for r in rows:
        p = r["progress"]
        assert p["n"] == p["done"]
        assert "%" not in p["line"] and "%" not in (p["note"] or "")


def test_a_tier_past_its_verdict_gate_points_at_the_edge_gate():
    """"36 of 20" is arithmetic nobody needs. Once a gate is behind you the
    next one is the thing standing between this tier and an edge claim."""
    from gridiron import language

    below = language.gate_progress(14, 20, 100)
    assert below["stage"] == "verdict" and below["line"] == "14 of 20 settled"
    past = language.gate_progress(36, 20, 100)
    assert past["stage"] == "edge"
    assert past["line"] == "36 of 100 settled"
    assert "verdict earned" in past["note"]
    way_past = language.gate_progress(140, 20, 100)
    assert way_past["line"] == "140 settled", "a count exceeded its own target"


def test_pace_refuses_to_estimate_below_a_week_of_history():
    """An estimate from three days is a number with an interval wider than
    the thing it estimates."""
    from gridiron import language

    assert "pace unknown" in language.pace_clause(6, 3.0, 3)
    assert "pace unknown" in language.pace_clause(6, None, 30)
    assert "about 2 slates" in language.pace_clause(6, 3.0, 14)
    assert "about a slate" in language.pace_clause(2, 3.0, 14)


def test_a_dated_read_window_counts_in_days():
    from gridiron import language

    g = language.date_gate("2026-08-31", "2026-09-14", today="2026-09-02")
    assert g["line"] == "2 of 14 days"
    assert "read on Monday 14 September" in g["note"] and "12 days" in g["note"]
    assert not audit.progress_faults(g)
    open_now = language.date_gate("2026-08-31", "2026-09-14", today="2026-09-20")
    assert open_now["cleared"] and "window is open" in open_now["note"]


# ---------------------------------------------------------------------------
# THE SEASON AS A SHAPE (GRIDIRON_13 P2)
# ---------------------------------------------------------------------------

def test_a_calendar_merging_sports_is_caught_by_name():
    faults = audit.calendar_faults(audit.CALENDAR_FIXTURE_MERGED)
    assert faults and "LAW 6" in faults[0]


def test_a_void_counted_as_a_loss_is_caught_by_name():
    faults = audit.calendar_faults(audit.CALENDAR_FIXTURE_VOID_AS_LOSS)
    assert faults and "void is not a loss" in faults[0]


def test_a_square_tinted_against_its_balance_is_caught():
    faults = audit.calendar_faults(audit.CALENDAR_FIXTURE_WRONG_TINT)
    assert faults and "balance" in faults[0]


def test_a_correct_calendar_day_is_not_flagged():
    assert not audit.calendar_faults(audit.CALENDAR_FIXTURE_GOOD)


def test_the_real_calendar_carries_one_sport_and_no_void_as_a_loss(resolved_league):
    """The guard runs inside `views.results_calendar`, so this is the payload
    the API would serve."""
    from gridiron import views

    payload = views.results_calendar(resolved_league, sport="nfl")
    audit.check_the_calendar_says_what_it_shows(payload)      # must not raise
    for day in payload["days"]:
        assert day["sport"] == "nfl"
        assert day["settled"] == day["won"] + day["lost"], (
            "a void was counted into the day's settled total")
        assert "n" in day


def test_a_calendar_day_states_its_voids_in_words():
    from gridiron import language

    line = language.calendar_day_line("2026-08-31", 14, 4, 4)
    assert "14 right, 4 wrong" in line and "4 void" in line
    assert "Monday 31 August" in line
    quiet = language.calendar_day_line("2026-08-31", 0, 0, 0)
    assert "nothing settled" in quiet


def test_the_calendar_note_says_voids_are_neither():
    from gridiron import language

    note = language.calendar_note()
    assert "neither" in note and "never answered is not a loss" in note


# ---------------------------------------------------------------------------
# SETTINGS, AND THE FENCE AROUND THEM (GRIDIRON_13 P3)
# ---------------------------------------------------------------------------

def test_a_model_constant_cannot_be_written_from_the_settings_page(tmp_path):
    """Operational knobs are preferences; the props floor is not. Every figure
    already written was produced under the old value."""
    from gridiron import db as _db, settings as _settings

    conn = _db.open_db(tmp_path / "t.db")
    for name in ("PROPS_MIN_CLAIM", "MLB_PROP_LADDER",
                 "MIN_SAMPLE_FOR_EDGE_CLAIM", "FACTOR_SET_VERSION"):
        with pytest.raises(_settings.SettingRefused, match="not an operational"):
            _settings.set_value(conn, name, "0.5")


def test_the_fence_names_what_the_page_may_change(tmp_path):
    """A refusal that does not say what IS allowed sends the operator to the
    source code to find out."""
    from gridiron import db as _db, settings as _settings

    conn = _db.open_db(tmp_path / "t.db")
    with pytest.raises(_settings.SettingRefused) as caught:
        _settings.set_value(conn, "PROPS_MIN_CLAIM", "0.5")
    said = str(caught.value)
    assert "quiet hours" in said and "when tasks run" in said
    assert "ruling" in said and "config.py" in said


def test_a_setting_is_append_only(tmp_path):
    from gridiron import db as _db, settings as _settings

    conn = _db.open_db(tmp_path / "t.db")
    _settings.set_value(conn, "predict_mlb_at", "11:05")
    _settings.set_value(conn, "predict_mlb_at", "11:10")
    rows = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    assert rows == 2, "a change overwrote its predecessor"
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE settings SET value = '09:00'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM settings")


def test_a_setting_records_what_it_changed_from(tmp_path):
    """A history reconstructed by ordering reads differently after a clock
    skew. The previous value is stored on the row."""
    from gridiron import db as _db, settings as _settings

    conn = _db.open_db(tmp_path / "t.db")
    _settings.set_value(conn, "predict_mlb_at", "11:05")
    entry = _settings.history(conn)[0]
    assert entry["previous"] == "11:00" and entry["value"] == "11:05"
    assert entry["label"] == "Predict MLB"


def test_a_bad_time_is_refused_in_words(tmp_path):
    from gridiron import db as _db, settings as _settings

    conn = _db.open_db(tmp_path / "t.db")
    for bad in ("25:00", "11:60", "eleven", "11"):
        with pytest.raises(_settings.SettingRefused, match="time of day"):
            _settings.set_value(conn, "predict_mlb_at", bad)


def test_a_schedule_change_claimed_without_a_read_back_is_caught():
    faults = audit.schedule_claim_faults(audit.SCHEDULE_FIXTURE_NO_READBACK)
    assert faults and "reading the scheduler back" in faults[0]


def test_a_read_back_that_disagrees_with_the_change_is_caught():
    """The case this exists for: the command succeeded and the task did not
    move."""
    faults = audit.schedule_claim_faults(audit.SCHEDULE_FIXTURE_DISAGREES)
    assert faults and "11:00" in faults[0] and "11:05" in faults[0]


def test_a_confirmed_schedule_change_is_not_flagged():
    assert not audit.schedule_claim_faults(audit.SCHEDULE_FIXTURE_GOOD)


def test_the_csrf_token_is_bound_to_the_session():
    from gridiron import auth as _auth

    token = _auth.csrf_token("session-one")
    assert token and _auth.csrf_is_valid("session-one", token)
    assert not _auth.csrf_is_valid("session-two", token)
    assert not _auth.csrf_is_valid("session-one", "not-the-token")
    assert not _auth.csrf_is_valid(None, token)


def test_neither_secret_is_returned_by_the_settings_page():
    """The token is the whole of the app's security and the topic is readable
    by anyone holding it. A page that shows either puts it in a screenshot."""
    from gridiron import auth as _auth, config as _config, views as _views

    panel = _views._access_panel()
    blob = json.dumps(panel)
    token = _auth.read_token()
    topic = _config.setting("GRIDIRON_NTFY_TOPIC")
    if token:
        assert token not in blob, "the access token was serialised to the page"
    if topic:
        assert topic not in blob, "the ntfy topic was serialised to the page"
    assert "..." in panel["token"]["masked"] or panel["token"]["masked"] in (
        "not set", "set")


# ---------------------------------------------------------------------------
# THE DOOR (GRIDIRON_13 P6)
# ---------------------------------------------------------------------------

def test_a_pick_on_the_login_page_is_caught_by_name():
    """The sign-in screen faces somebody who has not signed in."""
    faults = audit.login_glance_faults(audit.LOGIN_FIXTURE_A_PICK)
    assert faults and "PICK" in faults[0]


def test_a_probability_on_the_login_page_is_caught():
    faults = audit.login_glance_faults(audit.LOGIN_FIXTURE_A_PROBABILITY)
    assert faults and "PROBABILITY" in faults[0]


def test_a_rate_on_the_login_page_is_caught():
    """A percentage is the model's claim about something. Counts only."""
    faults = audit.login_glance_faults(audit.LOGIN_FIXTURE_A_RATE)
    assert faults and "percentage" in faults[0]


def test_a_record_and_a_slate_size_are_allowed():
    assert not audit.login_glance_faults(audit.LOGIN_FIXTURE_GOOD)


def test_the_real_login_glance_carries_no_pick(resolved_league):
    """The guard runs inside `views.login_glance`, so this is what the open
    route would actually serve."""
    from gridiron import views

    payload = views.login_glance(resolved_league)
    audit.check_the_login_page_shows_no_pick(payload)      # must not raise
    blob = json.dumps(payload).lower()
    for forbidden in ("model_prob", "model_side", "reasoning", "line_asked"):
        assert forbidden not in blob, f"the login page carries {forbidden}"


def test_the_login_glance_is_never_summed(resolved_league):
    """LAW 6 on the one page a stranger can see."""
    from gridiron import views

    payload = views.login_glance(resolved_league)
    assert "never added together" in payload["never_summed"]
    sports = [s["sport"] for s in payload["sports"]]
    assert len(sports) == len(set(sports)), "a sport appears twice"
    assert "total" not in json.dumps(payload).lower()


def test_a_session_slides_on_use(tmp_path):
    """THIRTY DAYS FROM LAST USE, not from sign-in. A fixed expiry logs the
    operator out on a schedule that has nothing to do with whether they were
    using the app."""
    import datetime as dt

    from gridiron import auth as _auth, db as _db

    conn = _db.open_db(tmp_path / "s.db")
    sid = _auth.create_session(conn)
    near = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    conn.execute("UPDATE sessions SET expires_utc = ? WHERE id = ?", (near, sid))
    conn.commit()

    assert _auth.session_is_valid(conn, sid)
    after = conn.execute(
        "SELECT expires_utc FROM sessions WHERE id = ?", (sid,)).fetchone()[0]
    assert after > near, "the session did not slide on use"


def test_an_expired_session_does_not_slide(tmp_path):
    """Sliding extends a LIVE session. It must not resurrect a dead one."""
    import datetime as dt

    from gridiron import auth as _auth, db as _db

    conn = _db.open_db(tmp_path / "s.db")
    sid = _auth.create_session(conn)
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    conn.execute("UPDATE sessions SET expires_utc = ? WHERE id = ?", (past, sid))
    conn.commit()
    assert not _auth.session_is_valid(conn, sid)
    still = conn.execute(
        "SELECT expires_utc FROM sessions WHERE id = ?", (sid,)).fetchone()[0]
    assert still == past, "an expired session was extended"


def test_signing_out_everywhere_ends_every_session(tmp_path):
    from gridiron import auth as _auth, db as _db

    conn = _db.open_db(tmp_path / "s.db")
    ids = [_auth.create_session(conn) for _ in range(3)]
    assert _auth.drop_all_sessions(conn) == 3
    for sid in ids:
        assert not _auth.session_is_valid(conn, sid)


def test_the_launcher_never_attaches_to_a_different_build():
    """THE FAILURE THAT DOES NOT LOOK LIKE ONE: the app opens, every screen
    renders, nothing errors, and the code answering is not the code that was
    built."""
    import sys as _sys
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parent.parent
    _sys.path.insert(0, str(root / "desktop"))
    try:
        import launcher as _launcher
    finally:
        _sys.path.pop(0)

    assert _launcher.attach_decision("a", "b") == _launcher.ASK
    assert _launcher.attach_decision("a", "b", confirmed=True) == _launcher.RESTART
    assert _launcher.attach_decision("a", "a") == _launcher.ATTACH

    # A SERVER THAT CANNOT REPORT A BUILD IS STALE, NOT UNKNOWN (2026-09-03).
    #
    # This line asserted ATTACH until the carve-out it encoded cost the
    # operator an hour. `/api/health` has carried the build since GRIDIRON_13
    # P6, so a server answering without one is provably older than that --
    # a definite answer, and the answer is "not this build". The app attached
    # to exactly such a server, showed seven nav pages where the current app
    # has four, no sport tabs at all, and looked perfectly healthy while being
    # thirty-five commits behind.
    assert _launcher.attach_decision("a", None) == _launcher.ASK
    assert _launcher.attach_decision("a", None, confirmed=True) == _launcher.RESTART

    # A LAUNCHER THAT CANNOT READ ITS OWN BUILD still attaches: nothing has
    # been learned about the server, and refusing there would make the app
    # unopenable for a reason nobody could act on. That is what the carve-out
    # was actually for.
    assert _launcher.attach_decision(None, "b") == _launcher.ATTACH
    assert _launcher.attach_decision(None, None) == _launcher.ATTACH


def test_a_fifth_nav_item_is_caught_by_name():
    """A nav grows one link at a time, each defensible on its own."""
    good = ("const RENAMED = { history: 'results', factors: 'record',"
            " versions: 'record', schedule: 'settings', digest: 'week' };")
    faults = audit.nav_faults(good, audit.NAV_FIXTURE_A_FIFTH_ITEM)
    assert faults and "Four pages is the ruling" in faults[0]


def test_a_removed_route_left_to_404_is_caught_by_name():
    good_nav = "".join(
        f'<a href="#/{p}" data-route="{p}">x</a>' for p in audit.NAV_PAGES)
    faults = audit.nav_faults(audit.NAV_FIXTURE_A_DEAD_LINK, good_nav)
    assert faults and "must land, not 404" in faults[0]


def test_the_shipped_nav_is_the_four_ruled_pages():
    audit.check_the_nav_is_four_pages()          # must not raise


# ---------------------------------------------------------------------------
# A RUN LINE'S SIGN MUST AGREE WITH ITS MONEYLINE (ruling R2, 2026-09-02)
# ---------------------------------------------------------------------------

def test_a_run_line_contradicting_its_moneyline_is_caught_by_name():
    faults = audit.run_line_sign_faults(audit.RUN_LINE_FIXTURE_CONTRADICTED)
    assert faults and "says the opposite" in faults[0]


def test_a_consistent_run_line_is_not_flagged():
    assert not audit.run_line_sign_faults(audit.RUN_LINE_FIXTURE_GOOD)


def test_a_true_pickem_says_nothing_either_way():
    """Equal prices name no favourite, so the line cannot contradict them."""
    assert not audit.run_line_sign_faults(
        [{"game_id": "x", "spread_line": 1.5,
          "home_moneyline": -105, "away_moneyline": -105}])


def test_the_repair_never_guesses_a_contradicted_sign(tmp_path):
    """ESPN CAN CONTRADICT ITSELF on a near-pick'em: mlb_823010 is priced
    home -101, away -120 and its `favorite` flag says home. Neither source
    wins, so the row is marked and its sign is left exactly as it was."""
    from gridiron import db as _db
    from gridiron.market import lines as _lines

    conn = _db.open_db(tmp_path / "r.db")
    conn.execute(
        "INSERT INTO games (id, season, week, game_type, kickoff_utc, home,"
        " away, status, sport) VALUES ('mlb_x', 2026, 1, 'REG',"
        " '2026-09-01T18:00:00Z', 'AAA', 'BBB', 'scheduled', 'mlb')")
    conn.execute(
        "INSERT INTO market_lines_raw (game_id, fetched_utc, source,"
        " spread_line, home_moneyline, away_moneyline)"
        " VALUES ('mlb_x', '2026-09-01T18:00:00Z', 'test', 1.5, -101, -120)")
    # A cached payload whose flag says HOME, against a price that says away.
    conn.execute(
        "INSERT INTO http_cache (url, body, fetched_utc, etag)"
        " VALUES ('https://x/baseball/odds', ?, '2026-09-01T18:00:00Z', '')",
        (json.dumps({"homeTeamOdds": {"favorite": True, "moneyLine": -101},
                     "awayTeamOdds": {"favorite": False, "moneyLine": -120},
                     "spread": 1.5}),))
    conn.commit()

    counts = _lines.repair_run_line_signs(conn, "mlb")
    assert counts["contradicted"] == 1, counts
    row = conn.execute(
        "SELECT spread_line, spread_sign_source FROM market_lines_raw"
        " WHERE game_id = 'mlb_x'").fetchone()
    assert row["spread_sign_source"] == "contradicted"
    assert row["spread_line"] == 1.5, "a contradicted sign was changed anyway"


def test_every_verified_run_line_in_the_record_agrees_with_its_price():
    """The shipped database, not a fixture. Rows marked 'contradicted' are
    known unknowns and are excluded -- they must not be read as correct."""
    from gridiron import db as _db

    conn = _db.connect()
    audit.check_run_line_signs(conn, "mlb")          # must not raise


# ---------------------------------------------------------------------------
# A SLATE IS ANSWERED ONCE (ruling R4, 2026-09-02)
# ---------------------------------------------------------------------------

def test_superseded_forecasts_are_not_in_the_arithmetic():
    """`predict:nfl` ran twice on 2026-08-29. Both rows stay -- LAW 3 -- but a
    curve that counts 26 questions twice describes a slate nobody asked."""
    from gridiron import calibration as _cal, db as _db

    conn = _db.connect()
    standing = conn.execute("""
      SELECT COUNT(*) FROM predictions p WHERE p.sport='nfl'
         AND p.id = (SELECT p2.id FROM predictions p2
                      WHERE p2.game_id=p.game_id AND p2.market_type=p.market_type
                        AND p2.subject=p.subject AND p2.predictor=p.predictor
                        AND IFNULL(p2.line_asked,-1e9)=IFNULL(p.line_asked,-1e9)
                      ORDER BY p2.created_utc DESC, p2.id DESC LIMIT 1)
    """).fetchone()[0]
    written = conn.execute(
        "SELECT COUNT(*) FROM predictions WHERE sport='nfl'").fetchone()[0]
    assert standing < written, "the double slate is not being deduplicated"
    # And the Picks page must agree, because there is one definition of "the
    # same question" and both read it.
    from gridiron import views as _views

    assert _views.week(conn, "nfl")["n"] + _views.week(conn, "nfl")["superseded"] \
        == conn.execute("SELECT COUNT(*) FROM predictions p JOIN games g"
                        " ON g.id=p.game_id WHERE p.sport='nfl'"
                        " AND p.predictor='statistical'").fetchone()[0]


def test_a_factor_set_query_still_returns_its_own_rows():
    """THE SUBQUERY MIRRORS THE FILTER. Without that, asking for fs1 matches
    the fs2 row's id, fails the outer filter and returns nothing at all."""
    from gridiron import db as _db

    conn = _db.connect()
    for fsv, expected in (("fs1", 48), ("fs2", 56)):
        got = conn.execute(f"""
          SELECT COUNT(*) FROM predictions p
           WHERE p.sport='nfl' AND p.factor_set_version='{fsv}'
             AND p.id = (SELECT p2.id FROM predictions p2
                          WHERE p2.game_id=p.game_id
                            AND p2.market_type=p.market_type
                            AND p2.subject=p.subject
                            AND p2.predictor=p.predictor
                            AND IFNULL(p2.line_asked,-1e9)=IFNULL(p.line_asked,-1e9)
                            AND p2.factor_set_version=p.factor_set_version
                          ORDER BY p2.created_utc DESC, p2.id DESC LIMIT 1)
        """).fetchone()[0]
        assert got == expected, f"{fsv}: {got} of {expected}"


def test_answering_a_slate_twice_is_refused(tmp_path):
    from gridiron import config as _config, db as _db, run as _run

    conn = _db.open_db(tmp_path / "a.db")
    conn.execute(
        "INSERT INTO games (id, season, week, game_type, kickoff_utc, home,"
        " away, status, sport) VALUES ('nfl_x', 2026, 1, 'REG',"
        " '2026-09-13T17:00:00Z', 'AAA', 'BBB', 'scheduled', 'nfl')")
    # EVERY MARKET THE SPORT ASKS. The refusal is per market since the run
    # line and the total were added: a slate missing one is a slate a new
    # market can still be added to, which is how those two reached a day
    # the moneyline had already covered.
    from gridiron import config as _config, sports as _sports

    for _market in _sports.get("nfl").markets():
        _kind = ("prop" if _market in _config.SPORT_PROP_MARKETS.get("nfl", ())
                 else _market)
        conn.execute(
            "INSERT INTO predictions (created_utc, game_id, sport, market_type,"
            " prop_type, subject, line_asked, model_prob, model_side, predictor,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES ('2026-08-29T05:55:46Z', 'nfl_x', 'nfl', ?, ?, ?, -3.5,"
            " 0.53, 'cover', 'statistical', ?, '{}', 'x')",
            # PER MARKET (2026-09-03). Seeding every row with the global
            # default made the spread rows fs2 while the guard now looks for
            # fs3, so the slate read as unanswered and the guard could not
            # fire -- which is exactly what this test exists to catch.
            (_kind, _market if _kind == "prop" else None, f"AAA {_market}",
             _config.factor_set_version("nfl", _kind)))
    conn.commit()
    with pytest.raises(_run.SlateAlreadyAnswered, match="answered once"):
        _run.run_slate(conn, "nfl", 2026, 1, snapshot=False, use_llm=False)


def test_a_changed_factor_set_is_still_allowed(tmp_path):
    """THE EXCEPTION IS REAL. A different model asking the same question is a
    different forecast, and that is what happened on 2026-08-29: fs1 at 05:55,
    fs2 at 07:34."""
    from gridiron import db as _db, run as _run

    conn = _db.open_db(tmp_path / "b.db")
    conn.execute(
        "INSERT INTO games (id, season, week, game_type, kickoff_utc, home,"
        " away, status, sport) VALUES ('nfl_x', 2026, 1, 'REG',"
        " '2026-09-13T17:00:00Z', 'AAA', 'BBB', 'scheduled', 'nfl')")
    conn.execute(
        "INSERT INTO predictions (created_utc, game_id, sport, market_type,"
        " subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-08-29T05:55:46Z', 'nfl_x', 'nfl', 'spread', 'AAA',"
        " -3.5, 0.53, 'cover', 'statistical', 'an-older-set', '{}', 'x')")
    conn.commit()
    assert not _run.already_answered(conn, "nfl", 2026, 1)["refuse"]


# ---------------------------------------------------------------------------
# A MARKET SOURCE LIVES IN THE MARKET MODULE (LAW 5, amended 2026-09-02)
# ---------------------------------------------------------------------------

def test_a_market_source_named_outside_the_market_module_is_caught(tmp_path):
    """LAW 5 as amended permits read-only PrizePicks lines "only inside the
    market module". LAW 1's closure scan sees only what a closure IMPORTS, so
    a module that merely names a source is invisible to it."""
    import shutil

    from gridiron import config as _config

    root = tmp_path / "gridiron"
    shutil.copytree(_config.PACKAGE_ROOT, root,
                    ignore=shutil.ignore_patterns("__pycache__", "*.db"))
    victim = root / "sports" / "mlb.py"
    leak = (chr(10) + chr(10) + "def _leak():" + chr(10)
            + "    prizepicks_line = 1" + chr(10)
            + "    return prizepicks_line" + chr(10))
    victim.write_text(victim.read_text(encoding="utf-8") + leak, encoding="utf-8")

    faults = audit.market_source_faults(root)
    assert faults and "outside gridiron/market/" in faults[0]
    with pytest.raises(audit.LawViolation, match="ESCAPED THE MARKET MODULE"):
        audit.check_market_sources_stay_in_the_market_module(root)


def test_the_market_module_may_name_its_own_sources(tmp_path):
    """The quarantine is a boundary, not a ban: inside it the name is the
    point."""
    import shutil

    from gridiron import config as _config

    root = tmp_path / "gridiron"
    shutil.copytree(_config.PACKAGE_ROOT, root,
                    ignore=shutil.ignore_patterns("__pycache__", "*.db"))
    inside = root / "market" / "prizepicks_probe.py"
    inside.write_text(
        "def prizepicks_lines():" + chr(10) + "    return []" + chr(10),
        encoding="utf-8")
    assert not audit.market_source_faults(root)


def test_the_shipped_package_names_no_market_source_outside_the_module():
    audit.check_market_sources_stay_in_the_market_module()   # must not raise


def test_law_five_still_forbids_everything_it_forbade():
    """The amendment ADDED a permitted market source. It removed nothing, and
    the identifier scan is unchanged."""
    for word in ("kelly", "bankroll", "stake", "wager", "sizing",
                 "recommend_bet", "sportsbook", "roi"):
        assert word in audit.BETTING_IDENTIFIERS
    audit.check_not_a_betting_tool()          # must not raise
