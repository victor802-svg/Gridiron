"""Prove the guards by breaking the laws on purpose.

A guard that has never fired is a guard nobody has tested. This harness plants
each violation for real, runs the guard against it, and prints the failure it
produced — by name. If a planted violation is NOT caught, the harness exits
non-zero and says which law is unenforced.

Nothing here touches the real database or the real source tree. Source
violations are planted in a throwaway copy of the package; database violations
run against a temporary SQLite file.

    python tools/guards/plant.py
    python tools/guards/plant.py --verbose
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import audit, blind, calibration, config, db, resolve, run  # noqa: E402
from gridiron.factors import compute  # noqa: E402
from gridiron.market import sources as line_sources  # noqa: E402
from gridiron.factors import registry, store  # noqa: E402
from gridiron.model import baseline  # noqa: E402


@dataclass
class Result:
    law: str
    violation: str
    guard: str
    caught: bool
    failure: str


# ---------------------------------------------------------------------------
# a small synthetic league, so the harness needs no network and no real data
# ---------------------------------------------------------------------------

TEAMS = ["KC", "BUF", "SF", "PHI", "DAL", "MIA", "SEA", "GB"]


def seeded_database(path: Path) -> sqlite3.Connection:
    import random
    from datetime import datetime, timedelta, timezone

    conn = db.open_db(path)
    rng = random.Random(20260828)
    strength = dict(zip(TEAMS, [7, 5, 4, 2, 0, -2, -4, -6]))
    start = datetime(2025, 9, 7, 17, 0, tzinfo=timezone.utc)

    with conn:
        for week in range(1, 19):
            order = list(TEAMS)
            rng.shuffle(order)
            kickoff = (start + timedelta(days=7 * (week - 1))).strftime("%Y-%m-%dT%H:%M:%SZ")
            for i in range(0, len(order), 2):
                away, home = order[i], order[i + 1]
                gid = f"2025_{week:02d}_{away}_{home}"
                played = week <= 16
                margin = strength[home] - strength[away] + 2.0 + rng.gauss(0, 9)
                hs = max(0, int(round(21 + margin / 2))) if played else None
                as_ = max(0, int(round(21 - margin / 2))) if played else None
                conn.execute(
                    "INSERT INTO games (id, season, week, game_type, kickoff_utc, home,"
                    " away, status, home_score, away_score)"
                    " VALUES (?,2025,?,'REG',?,?,?,?,?,?)",
                    (gid, week, kickoff, home, away, "final" if played else "scheduled", hs, as_),
                )
                conn.execute(
                    "INSERT INTO game_conditions (game_id, home_rest, away_rest, roof,"
                    " surface, neutral_site, div_game, stadium)"
                    " VALUES (?,7,7,'outdoors','grass',0,0,?)",
                    (gid, f"{home} Field"),
                )
                conn.execute(
                    "INSERT INTO market_lines_raw (game_id, fetched_utc, source,"
                    " spread_line, total_line) VALUES (?,?,'harness',?,44.5)",
                    (gid, kickoff, round((strength[home] - strength[away] + 2.0) * 2) / 2),
                )
                if played:
                    for team, opp, pf, pa in ((home, away, hs, as_), (away, home, as_, hs)):
                        conn.execute(
                            "INSERT INTO team_week_stats (season, week, team, game_id,"
                            " opponent, points_for, points_against, plays)"
                            " VALUES (2025,?,?,?,?,?,?,?)",
                            (week, team, gid, opp, pf, pa, rng.randint(55, 72)),
                        )
    store.sync_registry(conn)
    baseline.train(conn, "spread", (2025,), sport="nfl", l2=1.0, note="guard harness")
    return conn


# ---------------------------------------------------------------------------
# the plantings
# ---------------------------------------------------------------------------

def plant_market_import_in_prediction_path() -> Result:
    """LAW 1: add a market import to a module the prediction path depends on."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root)
        victim = root / "factors" / "context.py"
        victim.write_text(
            victim.read_text(encoding="utf-8")
            + "\n\n# PLANTED VIOLATION\nfrom ..market import lines  # noqa\n",
            encoding="utf-8",
        )
        try:
            audit.check_prediction_closure(root=root)
        except audit.LawViolation as exc:
            return Result("LAW 1", "import gridiron.market from factors/context.py",
                          "audit.check_prediction_closure", True, str(exc))
    return Result("LAW 1", "import gridiron.market from factors/context.py",
                  "audit.check_prediction_closure", False,
                  "NOT CAUGHT — the prediction path can reach the market package")


def plant_market_column_in_prediction_path() -> Result:
    """LAW 1: read a market column from a module on the prediction path."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root)
        victim = root / "data" / "repo.py"
        victim.write_text(
            victim.read_text(encoding="utf-8")
            + textwrap.dedent(
                '''

                # PLANTED VIOLATION
                def sneak(conn, game_id):
                    return conn.execute(
                        "SELECT spread_line FROM market_lines_raw WHERE game_id = ?",
                        (game_id,),
                    ).fetchone()
                '''
            ),
            encoding="utf-8",
        )
        try:
            audit.check_prediction_closure(root=root)
        except audit.LawViolation as exc:
            return Result("LAW 1", "SELECT spread_line FROM market_lines_raw in data/repo.py",
                          "audit.check_prediction_closure", True, str(exc))
    return Result("LAW 1", "SELECT spread_line FROM market_lines_raw in data/repo.py",
                  "audit.check_prediction_closure", False,
                  "NOT CAUGHT — a market column is readable from the prediction path")


def plant_market_import_inside_the_blind_window() -> Result:
    """LAW 1, at runtime: import the market package mid-prediction."""
    blind.forget_market_module()
    try:
        with blind.blind_window():
            import gridiron.market.lines  # noqa: F401
    except blind.MarketAccessDuringBlindWindow as exc:
        return Result("LAW 1", "import gridiron.market inside the blind window",
                      "blind.blind_window sentinel", True, str(exc))
    finally:
        blind.forget_market_module()
    return Result("LAW 1", "import gridiron.market inside the blind window",
                  "blind.blind_window sentinel", False,
                  "NOT CAUGHT — the market was importable while predicting")


def plant_snapshot_before_prediction(conn: sqlite3.Connection) -> Result:
    """LAW 1: reorder the loop so the line is snapshotted first."""
    game_id = conn.execute("SELECT id FROM games LIMIT 1").fetchone()["id"]
    pid = conn.execute(
        "INSERT INTO predictions (created_utc, game_id, market_type, subject, line_asked,"
        " model_prob, model_side, predictor, factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-06-01T00:00:00Z',?,'spread','KC',-3.5,0.6,'cover','statistical',"
        " 'fs1','{}','planted')",
        (game_id,),
    ).lastrowid
    conn.commit()
    try:
        # The line was fetched before the prediction was formed.
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line)"
            " VALUES (?, '2026-05-01T00:00:00Z', 'planted', -3.5)",
            (pid,),
        )
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return Result("LAW 1", "market_snapshot timestamped before its prediction",
                      "SQL trigger snapshot_not_before_prediction", True, str(exc))
    conn.rollback()
    return Result("LAW 1", "market_snapshot timestamped before its prediction",
                  "SQL trigger snapshot_not_before_prediction", False,
                  "NOT CAUGHT — a line was recorded as seen before the prediction existed")


def plant_snapshot_without_prediction(conn: sqlite3.Connection) -> Result:
    try:
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line)"
            " VALUES (424242, '2026-06-02T00:00:00Z', 'planted', -3.5)"
        )
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return Result("LAW 1", "market_snapshot for a prediction that does not exist",
                      "SQL trigger snapshot_requires_prediction", True, str(exc))
    conn.rollback()
    return Result("LAW 1", "market_snapshot for a prediction that does not exist",
                  "SQL trigger snapshot_requires_prediction", False, "NOT CAUGHT")


def plant_prediction_mutation(conn: sqlite3.Connection) -> Result:
    """LAW 3: edit a probability after the fact."""
    pid = conn.execute("SELECT id FROM predictions ORDER BY id LIMIT 1").fetchone()["id"]
    try:
        conn.execute("UPDATE predictions SET model_prob = 0.99 WHERE id = ?", (pid,))
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return Result("LAW 3", "UPDATE predictions SET model_prob after creation",
                      "SQL trigger predictions_no_update", True, str(exc))
    conn.rollback()
    return Result("LAW 3", "UPDATE predictions SET model_prob after creation",
                  "SQL trigger predictions_no_update", False,
                  "NOT CAUGHT — a probability was rewritten after the fact")


def plant_prediction_delete(conn: sqlite3.Connection) -> Result:
    pid = conn.execute("SELECT id FROM predictions ORDER BY id LIMIT 1").fetchone()["id"]
    try:
        conn.execute("DELETE FROM predictions WHERE id = ?", (pid,))
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return Result("LAW 3", "DELETE a prediction", "SQL trigger predictions_no_delete",
                      True, str(exc))
    conn.rollback()
    return Result("LAW 3", "DELETE a prediction", "SQL trigger predictions_no_delete",
                  False, "NOT CAUGHT — history is erasable")


def plant_double_resolution(conn: sqlite3.Connection) -> Result:
    """LAW 3: resolve everything twice and check the record did not move."""
    run.run_week(conn, 2025, 7, include_props=False, use_llm=False)
    first = resolve.resolve_all(conn)
    before = conn.execute(
        "SELECT id, resolved_utc, outcome FROM predictions WHERE resolved_utc IS NOT NULL"
        " ORDER BY id"
    ).fetchall()
    second = resolve.resolve_all(conn)
    after = conn.execute(
        "SELECT id, resolved_utc, outcome FROM predictions WHERE resolved_utc IS NOT NULL"
        " ORDER BY id"
    ).fetchall()

    unchanged = [tuple(r) for r in before] == [tuple(r) for r in after]
    settled_twice = second["settled"] > 0

    # And the hard backstop: force a re-resolution and watch the trigger.
    trigger_message = "the trigger did not fire"
    trigger_fired = False
    if before:
        try:
            conn.execute(
                "UPDATE predictions SET resolved_utc = '2030-01-01T00:00:00Z', outcome = 1"
                " WHERE id = ?",
                (before[0]["id"],),
            )
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            trigger_fired = True
            trigger_message = str(exc)

    caught = unchanged and not settled_twice and trigger_fired
    detail = (
        f"first pass settled {first['settled']}, second pass settled {second['settled']}; "
        f"{len(before)} outcomes unchanged: {unchanged}.\n"
        f"forced re-resolution: {trigger_message}"
    )
    return Result("LAW 3", "resolve the same predictions twice",
                  "resolve_all WHERE resolved_utc IS NULL + trigger predictions_resolve_once",
                  caught, detail)


def plant_figure_without_sample_size(conn: sqlite3.Connection) -> Result:
    """LAW 4: strip the N off a rendered figure."""
    payload = calibration.scorecard(conn, sport="nfl")
    payload["headline"]["score"].pop("n", None)
    try:
        calibration.assert_every_figure_has_n(payload)
    except calibration.MissingSampleSize as exc:
        return Result("LAW 4", "remove 'n' from the headline score before rendering",
                      "calibration.assert_every_figure_has_n", True, str(exc))
    return Result("LAW 4", "remove 'n' from the headline score before rendering",
                  "calibration.assert_every_figure_has_n", False,
                  "NOT CAUGHT — a Brier score would render with no sample size")


def plant_edge_claim_below_threshold(conn: sqlite3.Connection) -> Result:
    """LAW 4: try to read an edge figure that has not earned the right to exist."""
    edge = calibration.edge(conn, sport="nfl", market_type="spread", predictor="statistical")
    if edge["n_disagreements"] >= config.MIN_SAMPLE_FOR_EDGE_CLAIM:
        return Result("LAW 4", "read an edge figure below the sample threshold",
                      "calibration.edge", False,
                      "INCONCLUSIVE — the harness sample is above the threshold")
    caught = not edge.get("renderable") and "model_more_confident" not in edge
    return Result(
        "LAW 4", "read an edge figure below the sample threshold", "calibration.edge",
        caught,
        f"withheld: {edge['message']}" if caught
        else "NOT CAUGHT — an edge figure rendered below the minimum sample",
    )


def plant_factor_without_rationale(conn: sqlite3.Connection) -> Result:
    """LAW 2: register a factor with no stated reason."""
    try:
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES"
            " ('gut_feel', '2026-08-28T00:00:00Z', 'vibes')"
        )
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return Result("LAW 2", "add a factor whose rationale is 'vibes'",
                      "CHECK constraint on factors.rationale", True, str(exc))
    conn.rollback()
    return Result("LAW 2", "add a factor whose rationale is 'vibes'",
                  "CHECK constraint on factors.rationale", False,
                  "NOT CAUGHT — an unjustified factor entered the registry")


def plant_factor_without_a_date(conn: sqlite3.Connection) -> Result:
    try:
        conn.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES"
            " ('gut_feel', 'sometime last year',"
            " 'A perfectly reasonable sounding sentence about why this matters.')"
        )
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return Result("LAW 2", "add a factor with an unparseable activation date",
                      "CHECK constraint on factors.added_utc", True, str(exc))
    conn.rollback()
    return Result("LAW 2", "add a factor with an unparseable activation date",
                  "CHECK constraint on factors.added_utc", False, "NOT CAUGHT")


def plant_backdated_factor(conn: sqlite3.Connection) -> Result:
    """LAW 2: move a factor's activation date back so it scores older work."""
    original = registry.REGISTRY["home_field"]
    registry.REGISTRY["home_field"] = registry.Factor(
        name="home_field",
        added_utc="2015-01-01T00:00:00Z",
        rationale=original.rationale,
        applies_to=original.applies_to,
        fn=original.fn,
    )
    try:
        store.sync_registry(conn)
    except store.RegistryConflict as exc:
        return Result("LAW 2", "backdate home_field to 2015 so it scores old predictions",
                      "store.sync_registry activation-date check", True, str(exc))
    finally:
        registry.REGISTRY["home_field"] = original
    return Result("LAW 2", "backdate home_field to 2015 so it scores old predictions",
                  "store.sync_registry activation-date check", False,
                  "NOT CAUGHT — a factor moved its own start date")


def plant_a_silent_missing_data_default() -> Result:
    """v2: reintroduce the 0.0 fallback that made precipitation look measured."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root)
        victim = root / "factors" / "compute.py"
        text = victim.read_text(encoding="utf-8")
        anchor = (
            "        if value is None:" + chr(10)
            + "            fv.absent.append(f.name)"
        )
        text = text.replace(
            anchor,
            anchor + chr(10)
            + "            fv.values[f.name] = f.default   # PLANTED",
        )
        victim.write_text(text, encoding="utf-8")
        try:
            audit.check_no_silent_defaults(root=root)
        except audit.MissingDataDefaulted as exc:
            return Result("v2 MISSING", "put back the 0.0 fallback in the feature vector",
                          "audit.check_no_silent_defaults", True, str(exc))
    return Result("v2 MISSING", "put back the 0.0 fallback in the feature vector",
                  "audit.check_no_silent_defaults", False,
                  "NOT CAUGHT - an unmeasurable factor can be given a value again")


def plant_a_defaulted_factor_at_runtime() -> Result:
    """The same violation, at the moment it would produce its first silent zero."""
    from gridiron.factors.compute import FeatureVector

    fv = FeatureVector(sport="nfl", market_type="spread")
    fv.values["precipitation"] = 0.0
    fv.raw["precipitation"] = None
    fv.absent.append("precipitation")
    try:
        audit.assert_missing_is_explicit(fv)
    except audit.MissingDataDefaulted as exc:
        return Result("v2 MISSING", "a vector carrying a value for an ABSENT factor",
                      "audit.assert_missing_is_explicit", True, str(exc))
    return Result("v2 MISSING", "a vector carrying a value for an ABSENT factor",
                  "audit.assert_missing_is_explicit", False,
                  "NOT CAUGHT - absent and measured are indistinguishable again")


def plant_a_merged_calibration_curve(conn: sqlite3.Connection) -> Result:
    """LAW 4 / no-merged-curves: average every prop market into one number."""
    payload = calibration.scorecard(conn, sport="nfl")
    merged = dict(payload["categories"][0])
    merged["category"] = "props / statistical"
    merged["market"] = "prop"
    merged["filters"] = dict(merged["filters"])
    merged["filters"]["market_type"] = "prop"
    merged["filters"]["prop_type"] = "all"
    payload["categories"].append(merged)
    try:
        calibration.assert_no_merged_categories(payload)
    except calibration.MergedCurve as exc:
        return Result("NO MERGED CURVES", "average all five prop markets into one curve",
                      "calibration.assert_no_merged_categories", True, str(exc))
    return Result("NO MERGED CURVES", "average all five prop markets into one curve",
                  "calibration.assert_no_merged_categories", False,
                  "NOT CAUGHT - a merged curve reached the interface")


def plant_a_merged_forecaster_curve(conn: sqlite3.Connection) -> Result:
    payload = calibration.scorecard(conn, sport="nfl")
    merged = dict(payload["categories"][0])
    merged["filters"] = dict(merged["filters"])
    merged["filters"]["predictor"] = "all"
    payload["categories"].append(merged)
    try:
        calibration.assert_no_merged_categories(payload)
    except calibration.MergedCurve as exc:
        return Result("NO MERGED CURVES", "average the statistical and LLM forecasters",
                      "calibration.assert_no_merged_categories", True, str(exc))
    return Result("NO MERGED CURVES", "average the statistical and LLM forecasters",
                  "calibration.assert_no_merged_categories", False, "NOT CAUGHT")


def plant_a_registry_factor_without_a_rationale(conn: sqlite3.Connection) -> Result:
    """LAW 2 through the REALISTIC path: declared in code, then synced."""
    planted = registry.Factor(
        name="looks_good_to_me",
        added_utc="2026-08-29T00:00:00Z",
        rationale="trust me",
        applies_to=("spread",),
        fn=lambda ctx: 1.0,
    )
    registry.REGISTRY["looks_good_to_me"] = planted
    try:
        store.sync_registry(conn)
    except sqlite3.IntegrityError as exc:
        return Result("LAW 2", "declare a factor in the registry whose rationale is 'trust me'",
                      "CHECK constraint reached through store.sync_registry", True, str(exc))
    finally:
        registry.REGISTRY.pop("looks_good_to_me", None)
    return Result("LAW 2", "declare a factor in the registry whose rationale is 'trust me'",
                  "CHECK constraint reached through store.sync_registry", False,
                  "NOT CAUGHT - an unjustified factor entered the registry in code")


def plant_a_cross_sport_query(conn: sqlite3.Connection) -> Result:
    """LAW 6: ask the record a question that spans sports.

    The tripwire is that `sport` is a REQUIRED argument on every function that
    reads the record. The only way to write a cross-sport query is to delete
    the parameter, so that is exactly what this plants.
    """
    for attempt, label in (
        (lambda: calibration.resolved(conn, sport=None), "sport=None"),
        (lambda: calibration.resolved(conn, sport="all"), "sport='all'"),
        (lambda: calibration.curve(conn, sport="all"), "curve over every sport"),
    ):
        try:
            attempt()
        except calibration.CrossSportAggregation as exc:
            return Result("LAW 6", f"read the record with {label}",
                          "calibration.require_sport", True, str(exc))
        return Result("LAW 6", f"read the record with {label}",
                      "calibration.require_sport", False,
                      "NOT CAUGHT - a query spanning sports returned a number")
    return Result("LAW 6", "read the record across sports",
                  "calibration.require_sport", False, "no attempt was made")


def plant_a_cross_sport_payload(conn: sqlite3.Connection) -> Result:
    """LAW 6, one level up: two correct queries stitched into one payload."""
    payload = calibration.scorecard(conn, sport="nfl")
    intruder = dict(payload["categories"][0])
    intruder["sport"] = "mlb"
    intruder["category"] = "moneyline / statistical"
    payload["categories"].append(intruder)
    try:
        calibration.assert_single_sport(payload, "nfl")
    except calibration.CrossSportAggregation as exc:
        return Result("LAW 6", "stitch an MLB category into an NFL scorecard",
                      "calibration.assert_single_sport", True, str(exc))
    return Result("LAW 6", "stitch an MLB category into an NFL scorecard",
                  "calibration.assert_single_sport", False,
                  "NOT CAUGHT - one payload described two sports")


def plant_a_faked_line_where_none_exists() -> Result:
    """A market with no source must report absence, never a number.

    Planted at the source descriptor: if `for_market` ever claims availability
    for a market nothing prices, the interface would draw a dumbbell against an
    invented number and the edge figure would be computed from it.
    """
    offenders = []
    for sport in config.SPORTS:
        for market in config.SPORT_PROP_MARKETS.get(sport, ()):
            entry = line_sources.for_market(sport, market)
            if entry.get("available"):
                offenders.append(f"{sport}:{market}")
            elif not entry.get("reason"):
                offenders.append(f"{sport}:{market} (absent with no reason given)")
    if offenders:
        return Result("NO FAKED LINES", "check every prop market reports no source",
                      "market.sources.for_market", False,
                      "NOT CAUGHT - these claim a line that does not exist: "
                      + ", ".join(offenders))
    return Result("NO FAKED LINES", "check every prop market reports no source",
                  "market.sources.for_market", True,
                  "every prop market reports available=False with a stated reason")


def plant_a_line_claimed_for_an_unpriced_market() -> Result:
    """The same check, planted: claim a market that no source carries."""
    fake = "shots_on_goal"
    entry = line_sources.for_market("mlb", fake)
    caught = not entry.get("available") and bool(entry.get("reason"))
    return Result(
        "NO FAKED LINES", "ask for a line on a market nobody prices",
        "market.sources.for_market", caught,
        entry.get("reason", "") if caught
        else "NOT CAUGHT - an unpriced market reported a line",
    )


def plant_a_context_with_no_sport() -> Result:
    """LAW 6 at the factor loop: a context that does not say whose factors apply."""
    class Anonymous:
        notes: list = []

    try:
        compute.feature_vector(Anonymous(), "spread")
    except compute.SportNotOnContext as exc:
        return Result("LAW 6", "build a feature vector from a context with no sport",
                      "compute.feature_vector", True, str(exc))
    return Result("LAW 6", "build a feature vector from a context with no sport",
                  "compute.feature_vector", False,
                  "NOT CAUGHT - one sport's factors could reach another's model")


def plant_an_unprefixed_foreign_factor() -> Result:
    """LAW 6 in the registry: declare an MLB factor without its sport prefix."""
    try:
        @registry.factor(
            added="2026-08-29T00:00:00Z",
            sport="mlb",
            applies_to=("moneyline",),
            rationale=(
                "A planted factor that collides with another sport's namespace, "
                "which is exactly what the prefix rule exists to prevent."
            ),
        )
        def home_advantage(ctx):
            return 1.0
    except ValueError as exc:
        registry.REGISTRY.pop("home_advantage", None)
        return Result("LAW 6", "declare an MLB factor with no sport prefix",
                      "registry.factor prefix rule", True, str(exc))
    registry.REGISTRY.pop("home_advantage", None)
    return Result("LAW 6", "declare an MLB factor with no sport prefix",
                  "registry.factor prefix rule", False,
                  "NOT CAUGHT - two sports can now collide on one factor name")

def plant_betting_surface() -> Result:
    """LAW 5: has a staking surface grown anywhere in the package?

    The scan looks at identifiers, not prose. The disclaimer in views.py says
    the words "bankroll" and "stake" on purpose, and a guard that could not
    tell a refusal from a feature would punish the project for explaining
    itself.
    """
    try:
        audit.check_not_a_betting_tool()
    except audit.LawViolation as exc:
        return Result("LAW 5", "scan package identifiers for a staking surface",
                      "audit.check_not_a_betting_tool", False, str(exc))
    return Result("LAW 5", "scan package identifiers for a staking surface",
                  "audit.check_not_a_betting_tool", True,
                  "no stake, bankroll, Kelly or sportsbook identifier exists in the package")


def plant_betting_surface_violation() -> Result:
    """LAW 5, planted: add a Kelly stake-sizing function and watch it caught."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root)
        (root / "staking.py").write_text(
            textwrap.dedent(
                """
                # PLANTED VIOLATION
                def kelly_stake(probability, odds, bankroll):
                    edge = probability * odds - 1
                    return bankroll * edge / (odds - 1)
                """
            ),
            encoding="utf-8",
        )
        try:
            audit.check_not_a_betting_tool(root=root)
        except audit.LawViolation as exc:
            return Result("LAW 5", "add a kelly_stake() function to the package",
                          "audit.check_not_a_betting_tool", True, str(exc))
    return Result("LAW 5", "add a kelly_stake() function to the package",
                  "audit.check_not_a_betting_tool", False,
                  "NOT CAUGHT — stake sizing entered the package unremarked")


# ---------------------------------------------------------------------------

def plant_a_transposed_column_copy() -> Result:
    """Copy a table POSITIONALLY, the way the original bug did, and check the
    verifier names it.

    This is the planting that was missing when it mattered. The positional copy
    corrupted both a backtest and the verifier itself, and the only reason it was
    ever noticed was a CHECK constraint that happened to reject a season number
    where a sport name belonged. Had `sport` carried no CHECK, both tools would
    have run happily on transposed data and every figure downstream would have
    been quietly wrong. Luck is not a guard.
    """
    import sqlite3 as _sqlite
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    import dbcopy

    with tempfile.TemporaryDirectory() as tmp:
        source = _Path(tmp) / "source.db"
        target = _Path(tmp) / "target.db"
        src = db.open_db(source)
        # Two columns whose values are obviously different, so a shift shows.
        src.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " status, league_date) VALUES ('g1', 'nfl', 2025, 3, 'REG', 'KC',"
            " 'BUF', 'scheduled', '2025-09-14')"
        )
        src.commit()
        src.close()

        conn = db.open_db(target)
        conn.execute("ATTACH DATABASE ? AS live", (str(source),))
        # THE PLANTED BUG: copy by position, deliberately shifting two columns.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(games)")]
        shifted = cols[:]
        i = shifted.index("home")
        shifted[i], shifted[i + 1] = shifted[i + 1], shifted[i]
        conn.execute(
            f"INSERT INTO games ({', '.join(cols)})"
            f" SELECT {', '.join(shifted)} FROM live.games"
        )
        conn.commit()

        try:
            dbcopy.verify_copy(conn, tables=("games",))
        except dbcopy.TransposedCopy as exc:
            conn.close()
            return Result(
                "DBCOPY", "copy a table positionally so two columns shift",
                "dbcopy.verify_copy", True, str(exc),
            )
        except _sqlite.Error as exc:
            conn.close()
            return Result(
                "DBCOPY", "copy a table positionally so two columns shift",
                "dbcopy.verify_copy", False,
                f"NOT CAUGHT BY NAME - only a database error, by luck: {exc}",
            )
        conn.close()
        return Result(
            "DBCOPY", "copy a table positionally so two columns shift",
            "dbcopy.verify_copy", False,
            "NOT CAUGHT - a transposed copy verified as correct",
        )


def plant_an_undated_margin_sd() -> Result:
    """Reach for a margin SD that carries no measurement.

    A margin SD decides how confident the MARKET is made to look, so an invented
    one silently rewrites the comparison this project exists to make. NBA's was
    written down as "~11.5 across recent seasons"; measured, it is 13.95.
    """
    from gridiron.market import lines as market_lines

    failures = []

    # 1. a sport with no entry at all must fail by name, never fall back
    try:
        market_lines.margin_sd("cricket")
        failures.append("an unknown sport returned a number instead of raising")
    except market_lines.UnmeasuredMarginSD:
        pass

    # 2. an entry with no measurement date is an assumption in disguise
    saved = market_lines.MARGIN_SD_BY_SPORT.get("nfl")
    market_lines.MARGIN_SD_BY_SPORT["nfl"] = market_lines.MarginSD(
        sd=13.2, n=0, measured_utc="", source="vibes",
    )
    try:
        market_lines.margin_sd("nfl")
        failures.append("an undated SD was accepted as a measurement")
    except market_lines.UnmeasuredMarginSD:
        pass
    finally:
        market_lines.MARGIN_SD_BY_SPORT["nfl"] = saved

    # 3. every shipped entry must actually carry its evidence
    for sport, entry in market_lines.MARGIN_SD_BY_SPORT.items():
        if not entry.measured_utc or not entry.n or not entry.source:
            failures.append(f"{sport} ships without its measurement")

    if failures:
        return Result("MEASURED NOT ASSUMED", "use a margin SD with no measurement",
                      "market.lines.margin_sd", False, "NOT CAUGHT - " + "; ".join(failures))
    return Result(
        "MEASURED NOT ASSUMED", "use a margin SD with no measurement",
        "market.lines.margin_sd", True,
        "an unknown sport and an undated entry both raise UnmeasuredMarginSD; "
        "every shipped SD carries its date, sample size and source",
    )


def plant_a_game_inside_its_own_rolling_window() -> Result:
    """The leak that made a model look clairvoyant.

    A game tipping after midnight UTC is the previous evening where it is
    played, so its own game-log row is dated the day before its kickoff_utc.
    Cutting a rolling window on the UTC date admitted the game being predicted
    into its own rolling form: 76.8% of NBA games and 25.1% of MLB ones.
    """
    from pathlib import Path as _Path

    from gridiron.data import nba_repo

    with tempfile.TemporaryDirectory() as tmp:
        conn = db.open_db(_Path(tmp) / "leak.db")
        # A 7pm Pacific tip-off: 02:00 the NEXT day in UTC.
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES ('nba_x', 'nba', 2025, 1,"
            " 'REG', 'LAL', 'GSW', '2025-10-22T02:00:00Z', 'scheduled',"
            " '2025-10-21')"
        )
        conn.commit()
        utc_date = conn.execute(
            "SELECT substr(kickoff_utc, 1, 10) FROM games WHERE id = 'nba_x'"
        ).fetchone()[0]
        cutoff = nba_repo.game_date(conn, "nba_x")
        conn.close()

    caught = cutoff == "2025-10-21" and utc_date == "2025-10-22"
    return Result(
        "NO FUTURE DATA", "cut a rolling window on the UTC date, not the league date",
        "data.nba_repo.game_date", caught,
        f"the cutoff is the league date {cutoff}, not the UTC date {utc_date}, so "
        "the game cannot enter its own window" if caught
        else f"NOT CAUGHT - cutoff {cutoff} equals the UTC date {utc_date}, so this "
             "game is inside its own rolling window",
    )


#: A service worker that caches API responses. Written as a list of lines so no
#: escape sequence has to survive being pasted through three layers of tooling.
_CACHING_WORKER = chr(10).join([
    "self.addEventListener('fetch', (event) => {",
    "  const url = new URL(event.request.url);",
    "  if (url.pathname.startsWith('/api/')) {",
    "    event.respondWith(caches.open('data').then((cache) =>",
    "      cache.match(event.request).then((hit) => hit ||",
    "        fetch(event.request).then((r) => {",
    "          cache.put(event.request, r.clone());",
    "          return r;",
    "        }))));",
    "  }",
    "});",
])


def plant_an_offline_data_cache() -> Result:
    """Write a service worker that caches API responses, and check the audit
    names it.

    This is the PWA version of the failure the whole project is built against.
    An app shell served from cache is a convenience; a calibration curve served
    from cache is a forecast whose age nobody can see, and it arrives looking
    exactly like a fresh one.
    """
    with tempfile.TemporaryDirectory() as tmp:
        worker = Path(tmp) / "sw.js"
        worker.write_text(_CACHING_WORKER, encoding="utf-8")
        try:
            audit.check_no_offline_data_caching(worker)
        except audit.LawViolation as exc:
            return Result("OFFLINE HONESTY", "cache API responses in the service worker",
                          "audit.check_no_offline_data_caching", True, str(exc))
        return Result("OFFLINE HONESTY", "cache API responses in the service worker",
                      "audit.check_no_offline_data_caching", False,
                      "NOT CAUGHT - a worker that caches forecasts passed the audit")


def plant_a_shipped_worker_that_caches_data() -> Result:
    """The shipped worker, checked as it stands."""
    hits = audit.offline_data_caching()
    return Result(
        "OFFLINE HONESTY", "check the shipped service worker caches no data",
        "audit.offline_data_caching", not hits,
        "the shipped worker caches the app shell only; every /api/ and /auth/ "
        "request goes to the network" if not hits
        else "NOT CAUGHT - " + "; ".join(hits[:4]),
    )


def plant_an_unauthenticated_route() -> Result:
    """Ask every route for data without a session and see what answers.

    Enumerated from the app rather than from a list, because a hand-kept list of
    protected paths goes stale the first time somebody adds an endpoint — and it
    goes stale silently, while the suite stays green and the new route serves
    the record to anyone who asks.
    """
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        target = Path(tmp) / "gate.db"
        db.open_db(target).close()
        previous = os.environ.get(auth.TOKEN_VAR)
        os.environ[auth.TOKEN_VAR] = "planted-token-for-the-guard-run"
        api.set_database(target)
        leaked: list[str] = []
        try:
            with TestClient(api.app) as client:
                for route in api.app.routes:
                    path = getattr(route, "path", None)
                    methods = getattr(route, "methods", set()) or set()
                    if not path or "{" in path or "GET" not in methods:
                        continue
                    if auth.path_is_open(path):
                        continue
                    code = client.get(path, headers={"accept": "application/json"}).status_code
                    if code not in (401, 403):
                        leaked.append(f"{path} -> {code}")
        finally:
            api.set_database(None)
            if previous is None:
                os.environ.pop(auth.TOKEN_VAR, None)
            else:
                os.environ[auth.TOKEN_VAR] = previous

    if leaked:
        return Result("AUTH", "reach every route without a session",
                      "api.require_session", False,
                      "NOT CAUGHT - these answered unauthenticated: " + ", ".join(leaked))
    return Result("AUTH", "reach every route without a session",
                  "api.require_session", True,
                  "every route enumerated from the app answered 401 without a "
                  "session; only the open list is reachable")


def plant_a_late_predict() -> Result:
    """Try to forecast a slate whose games have already started.

    This is the rule that cost 47 NBA rows and 6 MLB ones. A question once
    answered is never re-asked, so a late answer permanently occupies the slot
    the real forecast should have had. The task must record MISSED and write
    nothing.
    """
    from gridiron import tasks

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        conn = db.open_db(Path(tmp) / "late.db")
        db.set_meta(conn, "kind", "live")
        started = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        season = config.SPORT_CURRENT_SEASON["mlb"]
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES ('late_1', 'mlb', ?, 900,"
            " 'REG', 'NYY', 'BOS', ?, 'scheduled', ?)",
            (season, started, started[:10]),
        )
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, model_prob, model_side, predictor, factor_set_version,"
            " factors_json, reasoning) VALUES (?, 'mlb', 'late_1', 'moneyline',"
            " 'NYY', 0.55, 'win', 'statistical', ?, '{}', 'seed')",
            ((datetime.now(timezone.utc) - timedelta(days=2)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"), config.FACTOR_SET_VERSION),
        )
        # A SECOND slate, also begun, which nothing has forecast.
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date) VALUES ('late_2', 'mlb', ?, 901,"
            " 'REG', 'LAD', 'SFG', ?, 'scheduled', ?)",
            (season, started, started[:10]),
        )
        conn.commit()

        before = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE game_id = 'late_2'"
        ).fetchone()[0]
        tasks._record_missed_slates(conn, "mlb")
        after = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE game_id = 'late_2'"
        ).fetchone()[0]
        missed = conn.execute(
            "SELECT detail FROM task_runs WHERE result = 'missed'"
        ).fetchall()
        conn.close()

    if after != before:
        return Result("NEVER PREDICT LATE", "forecast a slate whose games have started",
                      "tasks._record_missed_slates", False,
                      f"NOT CAUGHT - {after - before} prediction(s) were written late")
    if not missed:
        return Result("NEVER PREDICT LATE", "forecast a slate whose games have started",
                      "tasks._record_missed_slates", False,
                      "NOT CAUGHT - nothing was written, but no MISSED row was "
                      "recorded either, so the gap is invisible")
    return Result("NEVER PREDICT LATE", "forecast a slate whose games have started",
                  "tasks._record_missed_slates", True,
                  "recorded MISSED and wrote nothing: " + missed[0]["detail"][:120])


def plant_a_double_resolve() -> Result:
    """Run resolve twice and check the second run changes nothing.

    The scheduler runs this every four hours, six times a day. If a second pass
    could re-settle anything, the record would drift on its own with nobody
    touching it.
    """
    from gridiron import tasks

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        conn = seeded_database(Path(tmp) / "twice.db")
        # Give the first pass something to settle. Without this the planting
        # proves only that zero equals zero, which is true of any code at all.
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, home_score, away_score, league_date)"
            " VALUES ('twice_1', 'mlb', 2026, 800, 'REG', 'NYY', 'BOS',"
            " '2026-01-01T18:00:00Z', 'final', 5, 3, '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, model_prob, model_side, predictor, factor_set_version,"
            " factors_json, reasoning) VALUES ('2026-01-01T12:00:00Z', 'mlb',"
            " 'twice_1', 'moneyline', 'NYY', 0.61, 'win', 'statistical', ?,"
            " '{}', 'planted so the first pass has work to do')",
            (config.FACTOR_SET_VERSION,),
        )
        conn.commit()
        first = tasks.run_task(conn, "resolve", use_llm=False)
        fingerprint = conn.execute(
            "SELECT COUNT(*) AS n, SUM(outcome) AS wins, MAX(resolved_utc) AS last"
            " FROM predictions WHERE resolved_utc IS NOT NULL"
        ).fetchone()
        second = tasks.run_task(conn, "resolve", use_llm=False)
        again = conn.execute(
            "SELECT COUNT(*) AS n, SUM(outcome) AS wins, MAX(resolved_utc) AS last"
            " FROM predictions WHERE resolved_utc IS NOT NULL"
        ).fetchone()
        conn.close()

    changed = tuple(fingerprint) != tuple(again)
    if not first.get("settled"):
        return Result("IDEMPOTENT RESOLVE", "run resolve twice back to back",
                      "resolve.resolve_all", False,
                      "NOT A TEST - the first pass settled nothing, so the second "
                      "settling nothing proves only that zero equals zero")
    if second["result"] != "noop" or changed:
        return Result("IDEMPOTENT RESOLVE", "run resolve twice back to back",
                      "resolve.resolve_all", False,
                      f"NOT CAUGHT - second run reported {second['result']} and the "
                      f"record {'changed' if changed else 'held'}")
    return Result(
        "IDEMPOTENT RESOLVE", "run resolve twice back to back",
        "resolve.resolve_all", True,
        f"first pass settled {first.get('settled', 0)}; second settled 0 and every "
        "resolved outcome and timestamp is byte-identical",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove the guards by breaking the laws")
    parser.add_argument("--verbose", action="store_true", help="print full failure text")
    args = parser.parse_args()

    results: list[Result] = []
    results.append(plant_market_import_in_prediction_path())
    results.append(plant_market_column_in_prediction_path())
    results.append(plant_market_import_inside_the_blind_window())
    results.append(plant_betting_surface())
    results.append(plant_betting_surface_violation())
    results.append(plant_a_silent_missing_data_default())
    results.append(plant_a_defaulted_factor_at_runtime())
    results.append(plant_a_faked_line_where_none_exists())
    results.append(plant_a_line_claimed_for_an_unpriced_market())
    results.append(plant_a_context_with_no_sport())
    results.append(plant_an_unprefixed_foreign_factor())
    results.append(plant_a_transposed_column_copy())
    results.append(plant_an_undated_margin_sd())
    results.append(plant_a_game_inside_its_own_rolling_window())
    results.append(plant_an_offline_data_cache())
    results.append(plant_a_shipped_worker_that_caches_data())
    results.append(plant_an_unauthenticated_route())
    results.append(plant_a_late_predict())
    results.append(plant_a_double_resolve())

    with tempfile.TemporaryDirectory() as tmp:
        conn = seeded_database(Path(tmp) / "guards.db")
        results.append(plant_snapshot_without_prediction(conn))
        results.append(plant_snapshot_before_prediction(conn))
        results.append(plant_prediction_mutation(conn))
        results.append(plant_prediction_delete(conn))
        results.append(plant_double_resolution(conn))
        results.append(plant_figure_without_sample_size(conn))
        results.append(plant_edge_claim_below_threshold(conn))
        results.append(plant_factor_without_rationale(conn))
        results.append(plant_factor_without_a_date(conn))
        results.append(plant_backdated_factor(conn))
        results.append(plant_a_registry_factor_without_a_rationale(conn))
        results.append(plant_a_merged_calibration_curve(conn))
        results.append(plant_a_merged_forecaster_curve(conn))
        results.append(plant_a_cross_sport_query(conn))
        results.append(plant_a_cross_sport_payload(conn))
        conn.close()

    print("=" * 74)
    print("PLANTED VIOLATIONS — each law broken on purpose, each failure named")
    print("=" * 74)
    for r in results:
        mark = "CAUGHT " if r.caught else "ESCAPED"
        print(f"\n[{mark}] {r.law}: {r.violation}")
        print(f"          guard: {r.guard}")
        first_line = r.failure.strip().splitlines()[0] if r.failure.strip() else ""
        if args.verbose:
            print(textwrap.indent(r.failure.strip(), "          | "))
        else:
            print(f"          -> {first_line[:150]}")

    escaped = [r for r in results if not r.caught]
    print("\n" + "=" * 74)
    print(f"{len(results) - len(escaped)}/{len(results)} planted violations were caught.")
    if escaped:
        print("\nUNENFORCED LAWS:")
        for r in escaped:
            print(f"  - {r.law}: {r.violation}\n      {r.failure}")
        print("=" * 74)
        return 1
    print("Every law has a guard, and every guard has now fired at least once.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
