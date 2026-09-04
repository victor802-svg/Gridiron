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
import re
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
    """Every prop market's availability claim must be BACKED, either way.

    This check used to assert that every prop market reports no source, which
    was true when it was written and became false on 2026-08-30, when ESPN was
    found to publish MLB player props in quantity. The guard was encoding a
    measurement as a law -- and the measurement was a generalisation from one
    look at one sport.

    So it now checks the thing that actually matters and stays true as sources
    come and go: a market that CLAIMS a line must have a fetch path that could
    produce one, and a market that claims none must say why. Both halves are
    faked-line failures. A market claiming availability with nothing behind it
    would draw a dumbbell against an invented number; a market claiming absence
    with no reason hides whether anybody ever looked.
    """
    from gridiron.market import props as prop_lines

    wired = set(prop_lines.TOTAL_MARKETS.values()) | set(
        prop_lines.MILESTONE_MARKETS.values()
    )
    offenders = []
    for sport in config.SPORTS:
        for market in config.SPORT_PROP_MARKETS.get(sport, ()):
            entry = line_sources.for_market(sport, market)
            if entry.get("available") and market not in wired:
                offenders.append(
                    f"{sport}:{market} (claims a line with no fetch path)"
                )
            elif not entry.get("available") and not entry.get("reason"):
                offenders.append(f"{sport}:{market} (absent with no reason given)")
    if offenders:
        return Result("NO FAKED LINES",
                      "check every prop market's availability claim is backed",
                      "market.sources.for_market", False,
                      "NOT CAUGHT - " + ", ".join(offenders))
    return Result("NO FAKED LINES",
                  "check every prop market's availability claim is backed",
                  "market.sources.for_market", True,
                  "every prop market either has a wired fetch path or states "
                  "why it has none")


def plant_a_reversed_side_pair() -> Result:
    """Swap the two halves of a prop pair and check the anchor refuses to be
    fooled by the swap.

    THE FAILURE THIS GUARDS IS THE ESPN SPREAD SIGN, IN A NEW MARKET. A prop
    row carries a line and a price and no over/under label. Getting the side
    backwards produces a plausible number for every subject and a
    sign-reversed comparison for half of them, and nothing in the data looks
    wrong.

    The derivation is anchored on a one-sided milestone -- "2+ total bases" is
    the same event as "over 1.5 total bases", so the milestone's price states
    P(over) directly. Reversing the pair therefore CANNOT flip the answer: the
    anchor picks the same member whichever order the pair arrives in. That is
    the property being proved here, and it is why the derivation is not "the
    shorter price is the over", which reversal would silently flip.
    """
    from gridiron.market import props as prop_lines

    # Each row keeps its OWN price and its own implied probability; reversing
    # swaps the order they arrive in, which is the only thing a caller could
    # ever get wrong about an unlabelled pair.
    rows = [
        {"line": 1.5, "price": -150, "prob": 0.600},
        {"line": 1.5, "price": 120, "prob": 0.455},
    ]
    anchor = [{"line": 2.0, "price": 118, "prob": 0.459}]

    forward = prop_lines.derive_sides(
        "batter_total_bases", {"totals": list(rows), "milestones": anchor}
    )
    reversed_ = prop_lines.derive_sides(
        "batter_total_bases", {"totals": list(reversed(rows)), "milestones": anchor}
    )

    def over_price(quotes):
        return next((q["price"] for q in quotes if q["side"] == "over"), None)

    same = (
        over_price(forward) is not None
        and over_price(forward) == over_price(reversed_)
    )
    return Result(
        "NO REVERSED SIDES", "reverse the two halves of an unlabelled prop pair",
        "market.props.derive_sides", same,
        f"the anchor names the same quote as the over either way "
        f"({over_price(forward)}), so document order cannot flip a comparison"
        if same else
        f"NOT CAUGHT - reversing the pair changed the over from "
        f"{over_price(forward)} to {over_price(reversed_)}",
    )


def plant_an_ambiguous_side_accepted() -> Result:
    """Two sides priced alike: the anchor must refuse, not pick the closer one."""
    from gridiron.market import props as prop_lines

    quotes = prop_lines.derive_sides("pitcher_strikeouts", {
        "totals": [
            {"line": 5.5, "price": -105, "prob": 0.512},
            {"line": 5.5, "price": -102, "prob": 0.505},
        ],
        "milestones": [{"line": 6.0, "price": -104, "prob": 0.510}],
    })
    caught = bool(quotes) and all(q["side"] == "unknown" for q in quotes)
    return Result(
        "NO GUESSED SIDES", "accept a side the anchor cannot separate",
        "market.props.derive_sides", caught,
        f"refused: {quotes[0]['method']}" if caught else
        f"NOT CAUGHT - a coin-flip pair was labelled {quotes}",
    )


def plant_an_ambiguous_crosswalk_match() -> Result:
    """Two players normalising to one name must REFUSE, never pick one.

    An ambiguous name accepted attaches a published price to the wrong player,
    and nothing downstream can tell: the line looks reasonable, the comparison
    computes, and the record is quietly about somebody else.
    """
    from gridiron.market import crosswalk

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        conn = db.open_db(Path(tmp) / "crosswalk.db")
        for pid, name in ((1, "Jose Ramirez"), (2, "José Ramírez")):
            conn.execute(
                "INSERT INTO mlb_batter_games (player_id, season, game_date,"
                " game_pk, player_name, hits) VALUES (?,?,?,?,?,0)",
                (pid, 2026, "2026-05-01", 900000 + pid, name),
            )
        conn.commit()
        index = crosswalk.our_players(conn, "mlb")
        candidates = index.get(crosswalk.normalise("Jose Ramirez")) or []
        caught = len(candidates) > 1
        conn.close()
    return Result(
        "NO GUESSED IDENTITY", "let two players share one normalised name",
        "market.crosswalk.our_players", caught,
        f"{len(candidates)} players normalise to 'jose ramirez', so the match "
        "is refused rather than decided by a coin flip"
        if caught else
        "NOT CAUGHT - an ambiguous name resolved to a single player",
    )


def plant_a_constant_prop_factor() -> Result:
    """A factor that never varies is a broken instrument, and the fit says so.

    Checklist item 2. `short_week_diff` varied in 1 NFL game of 544;
    `mlb_home_away` was constant across all 4,859 rows; `nba_back_to_back`
    never fired at all. Each looked like a weak factor and was a dead one.
    """
    from gridiron.model import logistic

    rows = [{"real": float(i % 7), "always_one": 1.0} for i in range(200)]
    labels = [i % 2 for i in range(200)]
    fit = logistic.fit(rows, labels, ["real", "always_one"], l2=2.0)
    caught = "always_one" in fit.constant and "real" not in fit.constant
    return Result(
        "VARIANCE BOOKKEEPING", "fit a factor that is constant across training",
        "logistic.fit constant detection", caught,
        f"reported constant: {fit.constant}" if caught else
        f"NOT CAUGHT - a constant factor was fitted a coefficient: {fit.as_dict()}",
    )


def plant_a_rung_off_the_declared_ladder() -> Result:
    """Ask an MLB prop at a line the declared ladder does not contain.

    An off-ladder rung is incomparable twice over: no book quotes it, so there
    is no market comparison, and no other prediction in the category shares it,
    so there is no internal comparison either. Both losses are silent.
    """
    from gridiron.model import questions as q

    try:
        q.assert_on_ladder(2.5, "batter_hits")
    except q.RungOffLadder as exc:
        return Result("DECLARED LADDER", "ask a prop at a rung off the ladder",
                      "questions.assert_on_ladder", True, str(exc))
    return Result("DECLARED LADDER", "ask a prop at a rung off the ladder",
                  "questions.assert_on_ladder", False,
                  "NOT CAUGHT - a question was formed at an undeclared rung")


#: A rung function that asks at the book's number. Written as a literal block
#: rather than with escapes, because an escaped newline has been mangled on the
#: way into this repository five times and a guard's fixture is the last place
#: that can be allowed to happen quietly.
_RUNG_FROM_THE_MARKET = """
def cfb_spread_rung(game_id, expected_margin=None):
    return quote.spread_line
"""


def _scan_planted_module(source: str) -> list[str]:
    """Run the real closure scanners over a planted module.

    Written to a FILE and scanned from there, because that is what the guard
    does in earnest -- `market_identifiers_in` parses a path, and a planting
    that exercised some other entry point would be proving a different thing
    than the one that runs.
    """
    import tempfile
    from pathlib import Path

    faults = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "planted.py"
        path.write_text(source, encoding="utf-8")
        for word, line in audit.market_identifiers_in(path):
            faults.append(f"planted.py:{line} names {word!r}")
        tree = __import__("ast").parse(source)
        for node in __import__("ast").walk(tree):
            names = []
            if isinstance(node, __import__("ast").Import):
                names = [a.name for a in node.names]
            elif isinstance(node, __import__("ast").ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                for banned in audit.FORBIDDEN_MODULES:
                    if name == banned or name.startswith(banned + "."):
                        faults.append(f"planted.py imports {name!r}")
    return faults


def plant_a_notification_carrying_a_probability() -> Result:
    """Put a percentage in a push notification.

    A push lands on a lock screen, and the ntfy topic is readable by anyone
    holding it -- there are no accounts on the free tier, the topic IS the
    secret. A probability there is a tip, whatever the field is called.
    """
    from gridiron import notify as _notify

    faults = _notify.message_faults("MLB: 7 settled - model 62% right")
    return _desk_plant(faults, "put a probability in a notification",
                       "notify.message_faults")


def plant_a_notification_carrying_a_line() -> Result:
    """Put a spread in a push notification.

    THE ONE THE FIRST VERSION OF THE GUARD MISSED. `\b[-+]` cannot match after
    a space -- a word boundary needs a word character on one side and both
    ' ' and '-' are non-word -- so "Alabama -24.5" walked straight through the
    check whose entire purpose is that no line leaves the building.
    """
    from gridiron import notify as _notify

    faults = _notify.message_faults("CFB: Alabama -24.5 settled")
    return _desk_plant(faults, "put a line in a notification",
                       "notify.message_faults")


def plant_a_results_message_on_an_empty_run() -> Result:
    """Send a results notification when nothing settled.

    Every four hours, forever. A notification that says nothing happened is a
    notification that teaches its reader to stop opening them, which disarms
    the channel that matters -- the failure one -- by habit rather than by
    code.
    """
    from gridiron import notify as _notify

    said = _notify.results_message({"mlb": {"settled": 0, "right": 0}})
    if said is None:
        return Result("NOTIFICATIONS", "message the operator about nothing",
                      "notify.results_message", True,
                      "a run that settled nothing produces no message")
    return Result("NOTIFICATIONS", "message the operator about nothing",
                  "notify.results_message", False,
                  f"NOT CAUGHT - it would have sent {said!r}")


def plant_a_merged_forecaster_view() -> Result:
    """Offer an "all forecasters" option on the record.

    The tempting version, because it looks like a convenience. It would be the
    one number on the page that describes nothing: the model answers every
    question on a slate, the operator answers the ones they chose, and the LLM
    answers whichever it was asked. One figure over all three is the merge
    LAW 4 forbids, wearing a selector.
    """
    faults = audit.merged_forecaster_faults(
        audit.MERGED_FORECASTER_FIXTURE_POSITIVE)
    return _desk_plant(faults, "offer one combined forecaster on the record",
                       "audit.merged_forecaster_faults")


def plant_two_forecasters_in_one_picks_list() -> Result:
    """Rank the statistical and the LLM picks together, unlabelled.

    NOT HYPOTHETICAL. This is what the MLB slate did until GRIDIRON_14: both
    forecasters in one ranking, each sorted on its own disagreement with the
    market, nothing on either card saying who said it. Toronto at Cleveland
    appeared twice -- "Cleveland to win 53%" and, seven rows down, "Toronto to
    win 53%". Two contradictory picks, both presented as the pick.

    The merge LAW 4 forbids in a curve, committed in a LIST instead, where it
    is harder to see: nothing is averaged, so nothing looks pooled.
    """
    faults = audit.one_forecaster_faults({
        "forecaster": "statistical",
        "cards": [
            {"game_id": "mlb_824441", "market_type": "moneyline",
             "predictor": "statistical", "model_side": "win"},
            {"game_id": "mlb_824441", "market_type": "moneyline",
             "predictor": "llm", "model_side": "lose"},
        ],
    })
    return _desk_plant(faults, "rank two forecasters in one picks list",
                       "audit.one_forecaster_faults")


def plant_a_picks_list_labelled_for_the_wrong_forecaster() -> Result:
    """Say the list is the LLM's while showing the statistical model's rows.

    The quieter half of the same guard. Nothing on screen contradicts itself,
    so a reader has no way to notice -- they simply attribute one forecaster's
    picks to the other, and any judgement they form about either is wrong.
    """
    faults = audit.one_forecaster_faults({
        "forecaster": "llm",
        "cards": [{"game_id": "mlb_824441", "market_type": "moneyline",
                   "predictor": "statistical"}],
    })
    return _desk_plant(faults, "label a picks list for the wrong forecaster",
                       "audit.one_forecaster_faults")


def plant_a_day_key_in_visible_text() -> Result:
    """Put "Day 159, 2026" at the top of the slate.

    The slate key's second disguise, and the first version of the rule missed
    it. Catching the eight-digit form -- "week 20260905" -- left the ORDINAL
    standing above every baseball slate: not eight digits, just as much an
    internal number, and read by nobody. No baseball fan calls a date
    "Day 159".
    """
    faults = audit.plain_words_violations("Day 159, 2026")
    return _desk_plant(faults, "print a day key where a date belongs",
                       "audit.plain_words_violations")


def plant_a_slate_answered_twice() -> Result:
    """Forecast a slate this factor set has already answered.

    `predict:nfl` ran twice on 2026-08-29. Nothing stopped it, nothing said
    so, and it surfaced days later as every game appearing twice on Picks. A
    changed factor set is the exception and stays one -- a different model
    asking the same question is a different forecast.
    """
    from gridiron import db as _db, run as _run

    conn = _db.connect(":memory:")
    _db.init(conn)
    conn.execute(
        "INSERT INTO games (id, season, week, game_type, kickoff_utc, home,"
        " away, status, sport) VALUES ('nfl_x', 2026, 1, 'REG',"
        " '2026-09-13T17:00:00Z', 'AAA', 'BBB', 'scheduled', 'nfl')")
    # EVERY MARKET THE SPORT ASKS, because the refusal is per market now: a
    # slate missing one is a slate a new market can still be added to, which
    # is how the run line reached a day the moneyline had already covered.
    from gridiron import config as _config, sports as _sports

    for market in _sports.get("nfl").markets():
        kind = ("prop" if market in _config.SPORT_PROP_MARKETS.get("nfl", ())
                else market)
        conn.execute(
            "INSERT INTO predictions (created_utc, game_id, sport, market_type,"
            " prop_type, subject, line_asked, model_prob, model_side, predictor,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES ('2026-08-29T05:55:46Z', 'nfl_x', 'nfl', ?, ?, ?,"
            " -3.5, 0.53, 'cover', 'statistical', ?, '{}', 'x')",
            # PER MARKET (2026-09-03). Seeding every row with the global
            # default leaves the spread rows on fs2 while the guard looks for
            # fs3, so the slate reads as unanswered and the guard cannot fire.
            (kind, market if kind == "prop" else None, f"AAA {market}",
             _run.config.factor_set_version("nfl", kind)))
    conn.commit()
    try:
        _run.run_slate(conn, "nfl", 2026, 1, snapshot=False, use_llm=False)
    except _run.SlateAlreadyAnswered as exc:
        return Result("LAW 3", "answer a slate twice with the same factor set",
                      "run.already_answered", True, str(exc).splitlines()[0])
    return Result("LAW 3", "answer a slate twice with the same factor set",
                  "run.already_answered", False,
                  "a second full set of forecasts was written")


LAW_TIMING = "TWO PASSES, ONE STANDING ROW"

_PLANT_FACTORS = '{"values": {}, "present": [], "absent": []}'


def _iso_shift(stamp: str, seconds: int) -> str:
    """An ISO timestamp moved by `seconds`, in the project's Z format."""
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return (moment + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timing_world(tmp):
    """A throwaway league, and one finished NFL game to forecast twice.

    ITS OWN DATABASE, and the reason is a guard firing on me. The first
    version of these plantings wrote into the shared harness database and
    deleted the rows afterwards; LAW 3 refused the delete by name, which is
    exactly right -- a prediction cannot be removed. Rows that cannot be
    cleaned up must not be written where anything else will read them.
    """
    conn = seeded_database(Path(tmp) / "timing.db")
    game = conn.execute(
        "SELECT id, kickoff_utc FROM games WHERE sport='nfl'"
        "   AND kickoff_utc IS NOT NULL LIMIT 1").fetchone()
    if game is None:
        return conn, None, None
    conn.execute(
        "UPDATE games SET status='final', home_score=30, away_score=20"
        " WHERE id = ?", (game["id"],))
    conn.commit()
    return conn, game["id"], game["kickoff_utc"]


def _plant_pair(conn, game_id: str, subject: str, rows) -> None:
    """Write one early and one final forecast of the same question."""
    for pass_kind, created, prob in rows:
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor,"
            " pass_kind, factor_set_version, factors_json, reasoning,"
            " resolved_utc, outcome)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
            (created, "nfl", game_id, "spread", subject, -3.5, prob,
             "cover", "statistical", pass_kind, config.FACTOR_SET_VERSION,
             _PLANT_FACTORS, "planted", db.utcnow()))
    conn.commit()


def _graded_claims(conn, subject: str) -> list:
    """The claims the record actually grades for one planted question."""
    return sorted(round(r.model_prob, 4)
                  for r in calibration.resolved(conn, sport="nfl")
                  if r.subject == subject)


def plant_two_standing_rows_for_one_question() -> Result:
    """Write an early and a final forecast, and demand exactly one is graded.

    THE WHOLE MECHANISM RESTS ON THIS. Two passes are the point; two STANDING
    rows would be the 2026-08-29 duplicate bug wearing a new name -- every
    game twice on the Picks page, and a calibration curve counting each
    question twice.
    """
    what = "two standing rows for one question"
    with tempfile.TemporaryDirectory() as tmp:
        conn, game_id, kickoff = _timing_world(tmp)
        if game_id is None:
            conn.close()
            return Result(LAW_TIMING, what, "calibration.resolved", False,
                          "no dated game to plant against")
        _plant_pair(conn, game_id, "PLANTPAIR", [
            ("early", _iso_shift(kickoff, -86400), 0.58),
            ("final", _iso_shift(kickoff, -3600), 0.71),
        ])
        claims = _graded_claims(conn, "PLANTPAIR")
        conn.close()

    if len(claims) != 1:
        return Result(
            LAW_TIMING, what, "calibration.resolved", False,
            f"{len(claims)} rows were graded for one question (claims "
            f"{claims}); exactly one forecast stands per question")
    if claims != [0.71]:
        return Result(
            LAW_TIMING, what, "calibration.resolved", False,
            f"the EARLY row was graded ({claims}); the standing forecast is "
            f"the latest one written before start")
    return Result(LAW_TIMING, what, "calibration.resolved", True,
                  "exactly one row was graded, and it was the later one")


def plant_a_final_pass_writing_after_start() -> Result:
    """A forecast written after kickoff must not become the standing one.

    MISSED IS RECORDED, NEVER CAUGHT UP LATE (MENTOR 4). The task refuses to
    write at all; this is the second lock, on the READING side -- a row that
    somehow exists still cannot be the one the record is graded on. A 0.99
    claim written an hour into the game would otherwise grade as a triumph.
    """
    what = "a final pass writing after start"
    with tempfile.TemporaryDirectory() as tmp:
        conn, game_id, kickoff = _timing_world(tmp)
        if game_id is None:
            conn.close()
            return Result(LAW_TIMING, what, "calibration.resolved", False,
                          "no dated game to plant against")
        _plant_pair(conn, game_id, "PLANTLATE", [
            ("early", _iso_shift(kickoff, -3600), 0.58),
            ("final", _iso_shift(kickoff, +3600), 0.99),
        ])
        claims = _graded_claims(conn, "PLANTLATE")
        conn.close()

    if 0.99 in claims:
        return Result(
            LAW_TIMING, what, "calibration.resolved", False,
            "a forecast written AFTER kickoff became the standing row; a "
            "question answered once the game has started is not a forecast")
    if claims != [0.58]:
        return Result(
            LAW_TIMING, what, "calibration.resolved", False,
            f"expected the pre-kickoff row alone to stand; graded {claims}")
    return Result(LAW_TIMING, what, "calibration.resolved", True,
                  "the post-kickoff row was refused and the earlier one stands")


def plant_an_early_row_entering_calibration() -> Result:
    """A superseded early row must not reach the record.

    Distinct from the pair planting above: that one asks how MANY rows are
    graded, this one asks WHICH. A record that graded early rows would be
    measuring a forecast the app no longer shows anyone.
    """
    what = "an early row entering calibration"
    with tempfile.TemporaryDirectory() as tmp:
        conn, game_id, kickoff = _timing_world(tmp)
        if game_id is None:
            conn.close()
            return Result(LAW_TIMING, what, "calibration.resolved", False,
                          "no dated game to plant against")
        _plant_pair(conn, game_id, "PLANTEARLY", [
            ("early", _iso_shift(kickoff, -86400), 0.55),
            ("final", _iso_shift(kickoff, -3600), 0.80),
        ])
        claims = _graded_claims(conn, "PLANTEARLY")
        conn.close()

    if 0.55 in claims:
        return Result(
            LAW_TIMING, what, "calibration.resolved", False,
            "a superseded early forecast was graded; the record would be "
            "measuring a forecast the app no longer shows")
    if claims != [0.8]:
        return Result(LAW_TIMING, what, "calibration.resolved", False,
                      f"expected the final row alone to stand; graded {claims}")
    return Result(LAW_TIMING, what, "calibration.resolved", True,
                  "only the final row reached the record")


LAW_ASKED = "THE ASKED LINE IS A DISTANCE"


def plant_an_asked_line_that_is_not_a_distance() -> Result:
    """Compute the asked-line factor from the rung alone, as it used to be.

    THIS IS THE BUG THE RULING REPAIRED, replanted. Under nearest-expected-
    margin rungs the rung IS the rating, coarsened: it is chosen as the ladder
    point nearest minus the expected margin, so handing it to the model as a
    factor tells the model the rating a second time. Measured before the
    repair: |corr| 0.9816 between `cfb_asked_line` and `cfb_srs_diff`.

    A guard cannot read a coefficient's meaning, so this measures the thing
    that made it meaningless -- correlation with the rating on real rows.
    Anything above 0.5 is not an independent instrument.
    """
    from gridiron import config as _config
    from gridiron import sports as _sports
    from gridiron.model import questions as _q

    def corr(a, b):
        n = len(a)
        if n < 3:
            return None
        ma, mb = sum(a) / n, sum(b) / n
        va = sum((x - ma) ** 2 for x in a)
        vb = sum((x - mb) ** 2 for x in b)
        if va <= 0 or vb <= 0:
            return None
        return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / ((va * vb) ** 0.5)

    conn = db.connect()
    seasons = _config.SPORT_LOAD_SEASONS.get("cfb", _config.DEFAULT_LOAD_SEASONS)
    rows, _labels, _names = _sports.get("cfb").training_set(conn, seasons, "spread")
    conn.close()

    pres = [r for r in rows
            if "cfb_srs_diff" in r and "cfb_asked_distance" in r]
    if len(pres) < 100:
        return Result(LAW_ASKED, "an asked line computed from the rung alone",
                      "correlation with the rating", False,
                      f"only {len(pres)} rows to measure on")

    rating = [r["cfb_srs_diff"] for r in pres]
    good = [r["cfb_asked_distance"] for r in pres]
    # THE PLANTED VERSION: the rung itself, reconstructed exactly. The shipped
    # factor is `-rung - expected`, and the expected margin is recoverable
    # from the rating, so `rung = -(distance + expected)` is the old factor
    # to the last decimal rather than a lookalike.
    bad = []
    for r in pres:
        expected = _q.cfb_expected_margin(r["cfb_srs_diff"], 0.0)
        bad.append(-(r["cfb_asked_distance"] + expected))

    c_bad = abs(corr(bad, rating) or 0.0)
    c_good = abs(corr(good, rating) or 0.0)

    if c_bad < 0.5:
        return Result(
            LAW_ASKED, "an asked line computed from the rung alone",
            "correlation with the rating", False,
            f"the planted copy correlates only {c_bad:.4f} with the rating, so "
            f"this planting no longer reproduces the defect it was written for")
    if c_good >= 0.5:
        return Result(
            LAW_ASKED, "an asked line computed from the rung alone",
            "correlation with the rating", False,
            f"the SHIPPED factor correlates {c_good:.4f} with the rating -- it "
            f"is a coarsened copy of it, and its coefficient cannot be read as "
            f"an independent effect")
    return Result(
        LAW_ASKED, "an asked line computed from the rung alone",
        "correlation with the rating", True,
        f"the rung alone correlates {c_bad:.4f} with the rating; the shipped "
        f"distance correlates {c_good:.4f}")


def plant_a_market_value_in_the_asked_line_path() -> Result:
    """Reach for a market line inside the factor that sets the asked line.

    LAW 1. The rung is chosen BEFORE the model runs and is one of its inputs,
    so a market value reaching this path would make the market an input to
    the question itself -- not merely to the probability. The closure scan is
    what stops it, and this proves the scan covers the new code.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.db"))
        victim = root / "model" / "questions.py"
        victim.write_text(
            victim.read_text(encoding="utf-8")
            + chr(10) + chr(10)
            + "def _peek_at_the_line(conn, game_id):" + chr(10)
            + "    row = conn.execute(" + chr(10)
            + "        'SELECT spread_line FROM market_lines_raw WHERE game_id = ?'," + chr(10)
            + "        (game_id,)).fetchone()" + chr(10)
            + "    return row['spread_line'] if row else None" + chr(10),
            encoding="utf-8")
        try:
            audit.check_prediction_closure(root=root)
        except audit.LawViolation as exc:
            return Result("LAW 1", "a market value in the asked-line path",
                          "audit.check_prediction_closure", True, str(exc))
    return Result("LAW 1", "a market value in the asked-line path",
                  "audit.check_prediction_closure", False,
                  "NOT CAUGHT - the rung could be chosen from the market's "
                  "own number, which would make the market an input to the "
                  "question and not merely to the answer")


def plant_a_training_set_spanning_two_sports() -> Result:
    """Hand a training loader games from four sports and watch it refuse.

    THIS SHIPPED FOR DAYS. `spread_training_set` lost its `sport` filter in a
    commit about something else, so the NFL spread model trained on 18,715
    games of which 2,639 were football. Nothing failed; the fit converged and
    a bigger training set reads as a better one.
    """
    from gridiron.model import baseline as _baseline

    conn = db.connect()
    games = conn.execute(
        "SELECT id, sport FROM games"
        " WHERE sport IN ('nfl','mlb','nba','cfb') AND status = 'final'"
        " GROUP BY sport").fetchall()
    conn.close()
    sports_seen = {g["sport"] for g in games}
    if len(sports_seen) < 2:
        return Result("LAW 6", "a training set spanning two sports",
                      "baseline.assert_one_sport", False,
                      f"only {sports_seen} in the record to plant with")

    try:
        _baseline.assert_one_sport(games, "nfl", "a planted loader")
    except _baseline.TrainingSetSpansSports as exc:
        # AND THE HONEST CASE MUST PASS: a genuine single-sport selection is
        # not flagged, or the guard would refuse every real fit.
        clean = [g for g in games if g["sport"] == "nfl"]
        try:
            _baseline.assert_one_sport(clean, "nfl", "a planted loader")
        except _baseline.TrainingSetSpansSports as wrong:
            return Result("LAW 6", "a training set spanning two sports",
                          "baseline.assert_one_sport", False,
                          f"the guard fires on a clean NFL selection: {wrong}")
        return Result("LAW 6", "a training set spanning two sports",
                      "baseline.assert_one_sport", True, str(exc))
    return Result("LAW 6", "a training set spanning two sports",
                  "baseline.assert_one_sport", False,
                  "NOT CAUGHT - a loader may hand four sports to one model "
                  "and the fit will converge on them")


def plant_a_sport_adapter_missing_markets() -> Result:
    """An adapter without `markets()` must fail when loaded, not when called.

    IT FAILED AT FIRST USE FOR A DAY. `run.already_answered` calls
    `markets()`, and neither the NBA nor the college football adapter defined
    it, so ruling R4's duplicate-slate guard raised AttributeError before it
    could refuse anything -- for two sports out of four. First use of that
    path is a scheduled predict run, where the failure is a task-runs row
    nobody reads until they go looking.
    """
    import types

    from gridiron import sports as _sports

    victim = types.ModuleType("gridiron.sports.planted")
    victim.SPORT = "planted"
    victim.slate_questions = lambda *a, **k: []
    victim.next_slate = lambda *a, **k: None
    victim.resolve_outcome = lambda *a, **k: 0
    victim.training_set = lambda *a, **k: ([], [], [])
    # markets() deliberately absent -- the exact gap that shipped.

    try:
        _sports._check_adapter("planted", victim)
    except _sports.AdapterIncomplete as exc:
        if "markets" not in str(exc):
            return Result("A SPORT ADAPTER IS COMPLETE OR IT IS NOT LOADED",
                          "an adapter with no markets()",
                          "sports._check_adapter", False,
                          f"caught, but did not name `markets`: {exc}")
        # AND EVERY REAL ADAPTER STILL LOADS.
        for sport in config.SPORTS:
            try:
                _sports.get(sport)
            except Exception as wrong:  # noqa: BLE001
                return Result("A SPORT ADAPTER IS COMPLETE OR IT IS NOT LOADED",
                              "an adapter with no markets()",
                              "sports._check_adapter", False,
                              f"the check rejects the real {sport} adapter: "
                              f"{type(wrong).__name__}: {wrong}")
        return Result("A SPORT ADAPTER IS COMPLETE OR IT IS NOT LOADED",
                      "an adapter with no markets()",
                      "sports._check_adapter", True, str(exc))
    return Result("A SPORT ADAPTER IS COMPLETE OR IT IS NOT LOADED",
                  "an adapter with no markets()",
                  "sports._check_adapter", False,
                  "NOT CAUGHT - the gap surfaces at first use, inside a "
                  "scheduled run, as an AttributeError nobody reads")


def plant_a_docstring_promising_a_guard_that_does_not_exist() -> Result:
    """Write a reference to a guard that does not exist into a real docstring.

    A COMMENT MAY NOT PROMISE A MECHANISM THAT IS NOT THERE. One did:
    `attach_decision` claimed a scan checked it, no such function existed, and
    the carve-out the sentence was describing went on to open the app on a
    five-day-old build.

    THIS DOCSTRING NAMES NO GUARD, deliberately. The first version spelled the
    phantom out in full and tripped the very scan it plants -- the same shape
    as `audit.py` being unable to scan itself for betting identifiers. The
    project already answers that with a narrow exemption; here it costs
    nothing to simply not write the name, so the scan keeps zero exemptions
    and this planting builds the name at runtime instead.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.db"))
        victim = root / "correction.py"
        text = victim.read_text(encoding="utf-8")
        marker = '"""'
        head, sep, tail = text.partition(marker)
        if not sep:
            return Result("A COMMENT IS NOT A MECHANISM",
                          "a docstring naming a guard that does not exist",
                          "audit.docstring_reference_faults", False,
                          "no module docstring to plant in")
        planted = (head + sep
                   + "Checked by " + "audit." + "check_nothing_at_all"
                   + ", which is a sentence and not a guard."
                   + chr(10) + chr(10)
                   + tail)
        victim.write_text(planted, encoding="utf-8")
        faults = audit.docstring_reference_faults(root)

    if not faults:
        return Result("A COMMENT IS NOT A MECHANISM",
                      "a docstring naming a guard that does not exist",
                      "audit.docstring_reference_faults", False,
                      "NOT CAUGHT - a docstring may promise a guard nobody "
                      "wrote, which is how one went unwritten for a week")
    if audit.docstring_reference_faults():
        return Result("A COMMENT IS NOT A MECHANISM",
                      "a docstring naming a guard that does not exist",
                      "audit.docstring_reference_faults", False,
                      "the scan fires on the shipped tree too")
    return Result("A COMMENT IS NOT A MECHANISM",
                  "a docstring naming a guard that does not exist",
                  "audit.docstring_reference_faults", True, faults[0])


LAW_KNOWABLE = "WHAT WAS KNOWABLE, WHEN"


def plant_an_injury_row_without_a_capture_time() -> Result:
    """Store an injury observation with no stamp on it.

    THIS IS THE STATE THE PROJECT WAS IN. `injuries` holds 55,554 rows and not
    one of them carries a timestamp, which is why the timing probe could not
    measure NFL report timing at all -- not thinly, not approximately, not at
    all. An undated observation answers every question except the one about
    time, and looks complete while doing it.
    """
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.open_db(Path(tmp) / "capture.db")
        try:
            conn.execute(
                "INSERT INTO injury_reports (sport, season, week, team,"
                " player_name, captured_utc)"
                " VALUES ('nfl', 2026, 1, 'KC', 'A. Player', NULL)")
        except sqlite3.IntegrityError as exc:
            return Result(LAW_KNOWABLE, "an injury row with no capture time",
                          "schema: injury_reports.captured_utc NOT NULL",
                          True, str(exc))
        finally:
            conn.close()
    return Result(LAW_KNOWABLE, "an injury row with no capture time",
                  "schema: injury_reports.captured_utc NOT NULL", False,
                  "NOT CAUGHT - an undated observation was stored, which is "
                  "the state that made three sports unmeasurable")


def plant_a_backfilled_lineup_posing_as_live() -> Result:
    """Store a lineup capture whose source is neither live nor backfill.

    THE DISTINCTION IS THE MEASUREMENT. 6,902 of the 6,958 lineups this
    project holds came from one historical load, and averaging them with the
    39 real captures produced "lineups post 10,592 hours before first pitch"
    -- which is 441 days AFTER the game. A capture that will not say which it
    is puts that back.
    """
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.open_db(Path(tmp) / "capture.db")
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " status) VALUES ('g1','mlb',2026,1,'REG','AAA','BBB','scheduled')")
        try:
            conn.execute(
                "INSERT INTO lineup_captures (game_id, side, slot, player_id,"
                " captured_utc, source) VALUES ('g1','home',1,1,?,'live-ish')",
                (db.utcnow(),))
        except sqlite3.IntegrityError as exc:
            # AND THE HONEST VALUES MUST STILL BE ACCEPTED.
            for good in ("live", "backfill"):
                try:
                    conn.execute(
                        "INSERT INTO lineup_captures (game_id, side, slot,"
                        " player_id, captured_utc, source)"
                        " VALUES ('g1','home',?,1,?,?)",
                        (2 if good == "live" else 3, db.utcnow(), good))
                except sqlite3.IntegrityError as wrong:
                    conn.close()
                    return Result(
                        LAW_KNOWABLE, "a lineup that will not say what it is",
                        "schema: lineup_captures.source CHECK", False,
                        f"the check rejects the honest value {good!r}: {wrong}")
            conn.close()
            return Result(LAW_KNOWABLE, "a lineup that will not say what it is",
                          "schema: lineup_captures.source CHECK", True, str(exc))
        conn.close()
    return Result(LAW_KNOWABLE, "a lineup that will not say what it is",
                  "schema: lineup_captures.source CHECK", False,
                  "NOT CAUGHT - a capture stored a source nobody can read as "
                  "either live or backfill, and the two must never merge")


def plant_a_capture_that_stores_nothing_and_reports_success() -> Result:
    """Run a capture pass with rows eligible and every writer returning zero.

    A SILENT ZERO IS THE FAILURE THIS PROJECT KEEPS FINDING. A resolver ran
    for two days against a table nobody refreshed, reporting `noop` truthfully
    every time, and nothing failed. A capture that stores nothing while there
    was something to store is the same shape.
    """
    from gridiron import capture as _capture

    with tempfile.TemporaryDirectory() as tmp:
        conn = db.open_db(Path(tmp) / "capture.db")
        season = config.SPORT_CURRENT_SEASON.get("nfl", config.CURRENT_SEASON)
        conn.execute(
            "INSERT INTO injuries (season, week, team, player_name,"
            " report_status) VALUES (?,1,'KC','A. Player','Out')", (season,))
        conn.commit()

        real_injuries = _capture.capture_injuries
        real_lineups = _capture.capture_lineups
        _capture.capture_injuries = lambda *a, **k: 0
        _capture.capture_lineups = lambda *a, **k: 0
        try:
            _capture.run(conn)
        except _capture.NothingCaptured as exc:
            return Result(LAW_KNOWABLE, "a capture that stores nothing quietly",
                          "capture.run", True, str(exc))
        finally:
            _capture.capture_injuries = real_injuries
            _capture.capture_lineups = real_lineups
            conn.close()
    return Result(LAW_KNOWABLE, "a capture that stores nothing quietly",
                  "capture.run", False,
                  "NOT CAUGHT - a capture pass wrote nothing with rows "
                  "eligible and reported success")


def plant_a_what_it_knew_line_that_disagrees_with_its_row() -> Result:
    """Say a forecast rested on more factors than the row records.

    THE LINE IS A CLAIM ABOUT THE ROW, and a claim about a row that the row
    does not support is the most quietly misleading thing an interface can
    say: it reads as provenance and is a decoration. A reader deciding whether
    to trust a pick made without the starter has only this sentence to go on.
    """
    from gridiron import language as _language

    absent = ["the starter had not been announced"]
    honest = _language.what_it_knew(7, absent)
    if "7 of 8" not in honest:
        return Result("WHAT IT KNEW", "a coverage line disagreeing with its row",
                      "language.what_it_knew", False,
                      f"the honest line does not name its own totals: {honest!r}")

    # THE PLANTED VERSION: the same row, described as complete.
    planted = _language.what_it_knew(8, [])
    if "8 of 8" not in planted:
        return Result("WHAT IT KNEW", "a coverage line disagreeing with its row",
                      "language.what_it_knew", False,
                      "the planted line did not come out as a complete claim")

    # A card carrying the planted line alongside a row with an absence is the
    # disagreement, and it is detectable by comparing the two -- which is what
    # `audit.coverage_line_faults` does.
    faults = audit.coverage_line_faults([
        {"what_it_knew": planted,
         "factors_json": '{"present": ["a","b","c","d","e","f","g"],'
                         ' "absent": ["h"]}'},
    ])
    if not faults:
        return Result("WHAT IT KNEW", "a coverage line disagreeing with its row",
                      "audit.coverage_line_faults", False,
                      "NOT CAUGHT - a card said it rested on everything while "
                      "its own row recorded an absence")

    clean = audit.coverage_line_faults([
        {"what_it_knew": honest,
         "factors_json": '{"present": ["a","b","c","d","e","f","g"],'
                         ' "absent": ["h"]}'},
    ])
    if clean:
        return Result("WHAT IT KNEW", "a coverage line disagreeing with its row",
                      "audit.coverage_line_faults", False,
                      f"the scan fires on an honest card too: {clean[0]}")
    return Result("WHAT IT KNEW", "a coverage line disagreeing with its row",
                  "audit.coverage_line_faults", True, faults[0])


LAW_UFC = "A FIGHT IS ITS OWN SPORT"


def plant_a_ufc_query_merged_with_another_sport() -> Result:
    """Ask for a UFC curve without naming the sport.

    LAW 6. A rounds curve pooled with anything else describes neither, and UFC
    is the easiest sport in this record to pool by accident: its moneyline has
    the same name as baseball's and its markets sit in the same tables.
    """
    conn = db.connect()
    try:
        try:
            calibration.resolved(conn)
        except TypeError as exc:
            return Result(LAW_UFC, "a UFC query with no sport",
                          "calibration.resolved(sport=...)", True, str(exc))
        except config.CrossSportAggregation as exc:
            return Result(LAW_UFC, "a UFC query with no sport",
                          "config.require_sport", True, str(exc))
    finally:
        conn.close()
    return Result(LAW_UFC, "a UFC query with no sport",
                  "calibration.resolved(sport=...)", False,
                  "NOT CAUGHT - a curve was built across every sport at once")


def plant_rounds_merged_with_the_moneyline_curve() -> Result:
    """Score the rounds market against the moneyline's category.

    A bout ending inside a round is right or wrong for entirely different
    reasons than who won it. Merging them produces a curve describing neither,
    and it flatters -- the easy market dilutes the hard one.
    """
    payload = {
        "sport": "ufc",
        "categories": [
            {"sport": "ufc", "category": "ufc:moneyline", "market": "moneyline",
             "n": 40, "filters": {"predictor": "statistical"}},
            # THE MERGE: one category claiming to hold two markets.
            {"sport": "ufc", "category": "ufc:all", "market": "all",
             "n": 80, "filters": {"predictor": "statistical"}},
        ],
    }
    try:
        calibration.assert_no_merged_categories(payload)
    except calibration.MergedCurve as exc:
        # EVERY CATEGORY CARRIES ITS TIER (R2, 2026-09-03). This fixture was
        # written before UFC's record divided three ways; without the tier it
        # now trips the tier rule rather than passing, which would make this
        # planting fail for a reason it is not about.
        honest = {"sport": "ufc", "categories": [
            {"sport": "ufc", "category": "ufc:moneyline", "market": "moneyline",
             "event_tier": "numbered", "n": 40,
             "filters": {"predictor": "statistical"}},
            {"sport": "ufc", "category": "ufc:rounds", "market": "rounds",
             "event_tier": "numbered", "n": 40,
             "filters": {"predictor": "statistical"}},
        ]}
        try:
            calibration.assert_no_merged_categories(honest)
        except calibration.MergedCurve as wrong:
            return Result(LAW_UFC, "rounds merged with the moneyline curve",
                          "calibration.assert_no_merged_categories", False,
                          f"the guard rejects two honest categories: {wrong}")
        return Result(LAW_UFC, "rounds merged with the moneyline curve",
                      "calibration.assert_no_merged_categories", True, str(exc))
    return Result(LAW_UFC, "rounds merged with the moneyline curve",
                  "calibration.assert_no_merged_categories", False,
                  "NOT CAUGHT - one curve claimed to describe two markets")


def plant_a_rating_with_a_hand_chosen_k() -> Result:
    """Trim the candidate list until the fitted K is its last entry.

    A CONSTANT AT THE EDGE OF ITS OWN SWEEP HAS NOT BEEN FITTED. The first
    real sweep stopped at 48 and 48 won, which says only that the list was too
    short -- extending it found the turn at 80, with 96 and 120 worse on both
    sides. This plants the trimmed list and checks the guard notices.
    """
    from gridiron.model import ufc_rating

    real = ufc_rating.K_CANDIDATES
    try:
        # THE PLANT: a list that stops exactly at the answer.
        trimmed = tuple(k for k in real if k <= ufc_rating.K_FITTED)
        ufc_rating.K_CANDIDATES = trimmed
        clamped = ufc_rating.K_FITTED == ufc_rating.K_CANDIDATES[-1]
    finally:
        ufc_rating.K_CANDIDATES = real

    if not clamped:
        return Result(LAW_UFC, "a rating whose K sits at the edge of its sweep",
                      "K_FITTED is interior to K_CANDIDATES", False,
                      "the planted trim did not put K at the end of the list")
    if ufc_rating.K_FITTED == ufc_rating.K_CANDIDATES[-1]:
        return Result(LAW_UFC, "a rating whose K sits at the edge of its sweep",
                      "K_FITTED is interior to K_CANDIDATES", False,
                      "the SHIPPED K is the last candidate, so it was clamped "
                      "rather than fitted")
    return Result(LAW_UFC, "a rating whose K sits at the edge of its sweep",
                  "K_FITTED is interior to K_CANDIDATES", True,
                  f"a list ending at K={ufc_rating.K_FITTED} makes the fit its "
                  f"own last entry; the shipped list runs to "
                  f"{ufc_rating.K_CANDIDATES[-1]} and the optimum sits inside it")


def plant_a_bout_predicted_after_its_start() -> Result:
    """Forecast a bout that has already begun.

    MISSED IS RECORDED, NEVER CAUGHT UP LATE. A question answered after the
    cage door shuts is not a forecast, and the standing-row rule refuses to
    grade one even if it exists.
    """
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.open_db(Path(tmp) / "ufc.db")
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
            " home, away, status, home_score, away_score)"
            " VALUES ('b1','ufc',2026,20260101,'REG','2020-01-01T00:00:00Z',"
            " 'A','B','final',1,0)")
        for created, prob in (("2019-12-31T00:00:00Z", 0.55),
                              ("2020-01-01T01:00:00Z", 0.99)):
            conn.execute(
                "INSERT INTO predictions (created_utc, sport, game_id,"
                " market_type, subject, model_prob, model_side, predictor,"
                " pass_kind, factor_set_version, factors_json, reasoning,"
                " resolved_utc, outcome) VALUES (?,'ufc','b1','moneyline','A',"
                " ?,'win','statistical',?, 'fs2','{}','planted',?,1)",
                (created, prob, "early" if prob == 0.55 else "final",
                 db.utcnow()))
        conn.commit()
        graded = [r.model_prob for r in calibration.resolved(conn, sport="ufc")]
        conn.close()

    if any(abs(p - 0.99) < 1e-9 for p in graded):
        return Result(LAW_UFC, "a bout predicted after it started",
                      "calibration.resolved standing rule", False,
                      "a forecast written an hour into the bout was graded, "
                      "and it would grade as a triumph")
    if not any(abs(p - 0.55) < 1e-9 for p in graded):
        return Result(LAW_UFC, "a bout predicted after it started",
                      "calibration.resolved standing rule", False,
                      f"the honest pre-bout row was not graded either: {graded}")
    return Result(LAW_UFC, "a bout predicted after it started",
                  "calibration.resolved standing rule", True,
                  "the post-start row was refused and the earlier one stands")


def plant_a_fighter_matched_by_guess() -> Result:
    """Build a bout whose competitor carries no id, and expect it refused.

    IDENTITY IS NEVER A NAME MATCH IN UFC. Every competitor arrives with a
    numeric athlete id, which is why the name-collision problem the brief
    worried about does not arise -- fighters share names far more than clubs
    do. A competitor with no id is refused rather than matched on a name.
    """
    from gridiron.data import ufc_loader

    guessed = {"athlete": {"displayName": "Jon Jones"}}
    got = ufc_loader._athlete_id(guessed)
    if got is not None:
        return Result(LAW_UFC, "a fighter identified by name",
                      "ufc_loader._athlete_id", False,
                      f"a competitor with no id resolved to {got!r} -- two "
                      f"fighters sharing a name would become one")

    real = {"athlete": {"$ref": "http://x/v2/sports/mma/athletes/4848646?lang=en"}}
    if ufc_loader._athlete_id(real) != "4848646":
        return Result(LAW_UFC, "a fighter identified by name",
                      "ufc_loader._athlete_id", False,
                      "a real athlete reference no longer resolves")
    return Result(LAW_UFC, "a fighter identified by name",
                  "ufc_loader._athlete_id", True,
                  "a competitor without an id is refused; identity comes from "
                  "the reference, never from a name")


def plant_a_launcher_attaching_to_an_older_build() -> Result:
    """Restore the carve-out that showed a photograph on 2026-09-03.

    THIS ONE HAPPENED, to the operator, in the middle of a session. The app
    opened on a server reporting no build at all: seven nav pages where the
    current app has four, no sport tabs, thirty-five commits behind, and every
    screen rendering perfectly. `attach_decision` read "no build" as missing
    information and attached in silence -- the exact failure its own docstring
    describes, reached through the one door left open.

    Planted by monkeypatching the real decision function back to the old rule
    and running the real scan against it, so this proves the SCAN fires rather
    than that a copied lookalike does.
    """
    from desktop import launcher as _launcher

    original = _launcher.attach_decision

    def old_rule(mine, theirs, *, confirmed=False):
        # THE CARVE-OUT AS IT WAS: either unknown means attach.
        if not mine or not theirs:
            return _launcher.ATTACH
        if mine == theirs:
            return _launcher.ATTACH
        return _launcher.RESTART if confirmed else _launcher.ASK

    _launcher.attach_decision = old_rule
    try:
        faults = audit.stale_attach_faults()
    finally:
        _launcher.attach_decision = original

    if not faults:
        return Result(
            "A STALE ATTACH IS A PHOTOGRAPH",
            "attach to a server that cannot report its build",
            "audit.stale_attach_faults", False,
            "NOT CAUGHT - the launcher would open on an older build in "
            "silence, which is how the operator spent an hour looking for "
            "sport tabs that had shipped five days earlier")
    if audit.stale_attach_faults():
        return Result(
            "A STALE ATTACH IS A PHOTOGRAPH",
            "attach to a server that cannot report its build",
            "audit.stale_attach_faults", False,
            "the scan fires on the SHIPPED launcher too")
    return Result("A STALE ATTACH IS A PHOTOGRAPH",
                  "attach to a server that cannot report its build",
                  "audit.stale_attach_faults", True, faults[0])


def plant_a_final_pass_inside_the_market_closure() -> Result:
    """Import the market module from the final pass's own code path.

    LAW 1 IS NOT RELAXED BY RUNNING LATER, and a late pass is exactly where
    anchoring would be most tempting: the line is up by then and it is right
    there. The final pass runs the same prediction path inside the same blind
    window, so the same closure scan governs it -- this proves that, rather
    than asserting it in a comment.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.db"))
        victim = root / "model" / "predict.py"
        victim.write_text(
            victim.read_text(encoding="utf-8")
            + chr(10) + chr(10)
            + "from gridiron.market import lines as _late_lines" + chr(10)
            + "def _late_peek():" + chr(10)
            + "    return _late_lines" + chr(10),
            encoding="utf-8")
        try:
            audit.check_prediction_closure(root=root)
        except audit.LawViolation as exc:
            return Result("LAW 1", "the final pass imports the market module",
                          "audit.check_prediction_closure", True, str(exc))
    return Result("LAW 1", "the final pass imports the market module",
                  "audit.check_prediction_closure", False,
                  "NOT CAUGHT - the late pass could read the line it is "
                  "meant to be blind to")


def plant_a_selector_for_a_class_nothing_builds() -> Result:
    """Rename the class the desk tile's corner is fetched by.

    This is the bug that actually shipped, replanted. `applyLive` fetched
    `.tile-mkt` after the element had been renamed `.tile-score`, so every
    live tick threw -- and the throw escaped the forEach, stopping the score
    update for every pick after that tile. `querySelector` answers null rather
    than raising, which is why nothing caught it: the suite was green and the
    scores simply stopped moving.

    Planted for real against the shipped files.
    """
    from gridiron import audit as _audit

    web = config.PACKAGE_ROOT / "web"
    js = (web / "app.js").read_text(encoding="utf-8")
    html = (web / "index.html").read_text(encoding="utf-8")
    css = (web / "style.css").read_text(encoding="utf-8")

    # RE-POINTED AT THE CARDS UI (2026-09-04). It anchored on
    # `tile.querySelector('.tile-score')`, and the tiles are deleted. The
    # failure it guards against is unchanged and the new layout can commit it
    # exactly as the old one did: `applyCardState` fetches parts of a card by
    # class on every live tick, and `querySelector` answers null rather than
    # raising, so a renamed class stops the scores moving in silence.
    #
    # THE BRIEF SAID RE-POINT, NOT DROP, and this is what that means: the
    # guard follows the mechanism it protects rather than retiring with the
    # markup it happened to be written against.
    live = "node.querySelector('.card-when')"
    if js.count(live) != 1:
        return _desk_plant([], "a selector for a class nothing builds",
                           "audit.dead_selector_faults")
    broken = js.replace(live, "node.querySelector('.card-clock')", 1)
    faults = _audit.dead_selector_faults(broken, html, css)

    if _audit.dead_selector_faults(js, html, css):
        return Result("THE DESK", "a selector for a class nothing builds",
                      "audit.dead_selector_faults", False,
                      "the scan fires on the shipped files too")

    return _desk_plant(faults, "a selector for a class nothing builds",
                       "audit.dead_selector_faults")


def plant_a_default_tier_that_hides_the_count() -> Result:
    """Compose a filtered count line with no denominator.

    Picks opens on STRONG (ruling R2, 2026-09-02) rather than on the whole
    slate, which makes the count line the sentence carrying the filter. A
    reader who never chose that filter has no other way to tell a narrow band
    from a thin night. This plants the failure for real: the composer's own
    output is used, and the payload it builds is run past the scan.
    """
    from gridiron import audit as _audit
    from gridiron import language as _language

    shown, total = 4, 46
    # THE HIDING: a count line built from the part alone. Not a hand-written
    # string -- the composer's own output for an UNFILTERED slate of 4, which
    # is exactly what a filtered line degrades into when the whole is dropped.
    whole = _language.tier_filter_line(None, total, total)
    hidden = _language.tier_filter_line(None, shown, shown)
    payload = {"default_tier": "STRONG",
               "glance": {"count_lines": {"|": whole, "|STRONG": hidden}}}
    faults = _audit.tier_count_faults(payload)

    honest = {"default_tier": "STRONG",
              "glance": {"count_lines": {
                  "|": whole,
                  "|STRONG": _language.tier_filter_line("STRONG", shown, total),
              }}}
    if _audit.tier_count_faults(honest):
        return Result("a default tier that hides the count", False,
                      "the scan fires on an honest count line too")

    return _desk_plant(faults, "a default tier that hides the count",
                       "audit.tier_count_faults")


def plant_payout_arithmetic_against_a_market_source() -> Result:
    """LAW 5 as amended: read the line, never price it.

    The amendment (2026-09-02) admits PrizePicks as MARKET DATA -- "only to
    record what the market said". The line between reading a line and pricing
    one is the whole of the law, and it is thinner here than with ESPN,
    because a projections feed is shaped like an invitation to compute a
    return from it.

    So the failure is planted in the form it would actually take: a helper
    in the market module that turns a stored line into a payout. It must be
    caught even though it sits where market code is ALLOWED to sit -- the
    quarantine says where a source may be read, not that anything goes there.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.db"))
        (root / "market" / "entries.py").write_text(
            "# PLANTED VIOLATION\n"
            "def prizepicks_payout(line_count, entry_amount):\n"
            "    return entry_amount * (2 ** line_count)\n",
            encoding="utf-8")
        try:
            audit.check_not_a_betting_tool(root=root)
        except audit.LawViolation as exc:
            return Result(
                "LAW 5", "price a market source's line into a payout",
                "audit.check_not_a_betting_tool", True, str(exc))
    return Result(
        "LAW 5", "price a market source's line into a payout",
        "audit.check_not_a_betting_tool", False,
        "a payout function was added to the market module and nothing "
        "objected. Reading a line and pricing one are different acts; the "
        "quarantine says WHERE a source may be read, not that anything goes "
        "there.")


def plant_a_market_source_outside_the_market_module() -> Result:
    """Name PrizePicks from a prediction-path module.

    LAW 5 as amended (2026-09-02) permits read-only PrizePicks lines as market
    data, "only inside the market module". That quarantine is not decoration:
    it is what keeps a fetcher out of a prediction path. LAW 1's closure scan
    can only see what the closure IMPORTS, so a module that merely NAMES a
    source is invisible to it -- this scan is what catches that.

    Planted for real: the identifier is written into a copy of a real
    prediction-path module and the scan is run against the tree holding it.
    """
    from gridiron import audit as _audit

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.db"))
        victim = root / "sports" / "mlb.py"
        # A NAME, not a string literal: `identifiers_in` reads the AST, and a
        # string is deliberately not a name -- prose may discuss a source, code
        # may not reach for one.
        leak = (
            chr(10) + chr(10)
            + "def _leak():" + chr(10)
            + "    prizepicks_line = 1" + chr(10)
            + "    return prizepicks_line" + chr(10)
        )
        victim.write_text(
            victim.read_text(encoding="utf-8") + leak, encoding="utf-8")
        faults = _audit.market_source_faults(root)

    return _desk_plant(faults, "name a market source in a prediction path",
                       "audit.market_source_faults")


def plant_a_clamped_rung_beyond_the_ladder() -> Result:
    """Ask a sixty-point mismatch at the ladder's end rung anyway.

    THE FAILURE THE EXTENSION WAS RULED ON. Under the old ladder the top rung
    was chosen for 27% of college games, and 45 of the 58 rated games on
    2026-09-05 -- every mismatch past it collapsed onto one number, so the
    record measured the schedule rather than the model.

    Extending the ladder moves the wall; it does not remove it. A game beyond
    the new top must be REFUSED and recorded absent, because clamping it would
    store a confident claim about a number nobody chose, on exactly the games
    where the model is least tested.
    """
    from gridiron.model import questions as _q

    try:
        rung = _q.cfb_spread_rung("plant", 60.0)
    except _q.RungOffTheLadder as exc:
        return Result("LAW 1", "clamp a rung beyond the declared ladder",
                      "questions.cfb_spread_rung", True, str(exc)[:150])
    return Result("LAW 1", "clamp a rung beyond the declared ladder",
                  "questions.cfb_spread_rung", False,
                  f"a 60-point mismatch was silently asked at {rung:+.1f}")


def plant_a_run_line_rung_off_the_market() -> Result:
    """Ask the run line at a rung the market does not offer.

    Every MLB run line ESPN carries is +/-1.5 -- 71 of 71 in the probe. A
    question asked at -2.5 is incomparable with the market AND with the rest
    of its own category, which is the same objection the prop ladder answers.
    """
    from gridiron.model import questions as _q

    asked = -_q.MLB_RUN_LINE
    caught = abs(asked) == 1.5
    return Result("NEW MARKET", "ask the run line at a rung the market never offers",
                  "questions.MLB_RUN_LINE", caught,
                  f"the rung is a declared constant, {asked:+.1f}, not a per-game fetch"
                  if caught else f"the rung is {asked}, which the market does not offer")


def plant_a_total_asked_from_a_market_value() -> Result:
    """Form the asked total from a published total instead of our own form.

    THE WHOLE OF LAW 1 IN ONE FUNCTION. `mlb_total_asked` takes runs per game
    and nothing else; it cannot reach a market module, and a total asked at
    the market's number would make every comparison a comparison with itself.
    """
    import inspect

    from gridiron.model import questions as _q

    # THE CODE, NOT THE DOCSTRING. The first version scanned the whole source
    # and tripped on the docstring, which explains the rule by naming what it
    # forbids -- the same trap that made LAW 5 flag its own guard.
    source = inspect.getsource(_q.mlb_total_asked)
    body = source.split('"""')[-1] if '"""' in source else source
    reaches_market = any(word in body for word in
                         ("market", "total_line", "overUnder", "espn"))
    params = list(inspect.signature(_q.mlb_total_asked).parameters)
    caught = not reaches_market and params == ["home_rpg", "away_rpg"]
    return Result("LAW 1", "ask a total at the market's own number",
                  "questions.mlb_total_asked", caught,
                  f"takes {params} and names no market" if caught
                  else "the asked total can reach a published one")


def plant_a_total_merged_with_the_moneyline_curve() -> Result:
    """Score the total inside the moneyline's category.

    Two markets in one curve is the merge LAW 4 forbids: a total and a
    moneyline are different questions with different base rates -- 45.1% and
    roughly 54% -- and one number over both describes neither.
    """
    faults = audit.merged_curve_faults({
        "categories": [{
            "sport": "mlb", "n": 10,
            "filters": {"market_type": "moneyline", "prop_type": "all",
                        "predictor": "statistical"},
        }],
    }) if hasattr(audit, "merged_curve_faults") else []
    if not faults:
        # The real guard is `calibration.assert_no_merged_categories`, which
        # runs inside `scorecard()`. Exercise it rather than a lookalike.
        from gridiron import calibration as _cal

        payload = {"sport": "mlb", "categories": [
            {"sport": "mlb", "n": 10,
             "filters": {"market_type": "all", "prop_type": "all",
                         "predictor": "statistical"}}]}
        try:
            _cal.assert_no_merged_categories(payload)
        except Exception as exc:  # noqa: BLE001 - the guard is the catcher
            return Result("LAW 4", "score the total in the moneyline's curve",
                          "calibration.assert_no_merged_categories", True,
                          str(exc)[:150])
        return Result("LAW 4", "score the total in the moneyline's curve",
                      "calibration.assert_no_merged_categories", False,
                      "a merged category was accepted")
    return _desk_plant(faults, "score the total in the moneyline's curve",
                       "calibration.assert_no_merged_categories")


def plant_an_undated_total_sd() -> Result:
    """Use a totals SD for a sport that never measured one.

    `total_sd` has no fallback and says so: a plausible-looking number nobody
    measured is how NBA's market comparison came to be wrong for a day.
    """
    from gridiron.market import lines as _lines

    try:
        _lines.total_sd("nba")
    except _lines.UnmeasuredMarginSD as exc:
        return Result("NEW MARKET", "compare a total against an unmeasured SD",
                      "lines.total_sd", True, str(exc)[:150])
    return Result("NEW MARKET", "compare a total against an unmeasured SD",
                  "lines.total_sd", False,
                  "an unmeasured SD was served without complaint")


def plant_a_run_line_contradicting_its_moneyline() -> Result:
    """Store a run line whose sign says the opposite of its own price.

    21 of 76 MLB rows did this. Nothing consumed it -- Gridiron asks no
    run-line question yet -- so no figure was ever wrong. A build inheriting
    it would have been, and silently: a market comparison drawn against a
    reversed line shows the model disagreeing with the market on exactly the
    games where it agrees.
    """
    faults = audit.run_line_sign_faults(audit.RUN_LINE_FIXTURE_CONTRADICTED)
    return _desk_plant(faults, "store a run line that contradicts its price",
                       "audit.run_line_sign_faults")


def plant_a_fifth_nav_item() -> Result:
    """Add a fifth page to the nav.

    A nav grows ONE LINK AT A TIME, each defensible on its own, which is how
    this one got to seven: Picks, Record, Results, Settings, Schedule,
    Factors, Versions, Digest. Every addition was reasonable and the total was
    a page a reader had to make a decision about before they could ask a
    question. Four is the ruling (GRIDIRON_13 R4).
    """
    good = ("const RENAMED = { history: 'results', factors: 'record',"
            " versions: 'record', schedule: 'settings', digest: 'week' };")
    faults = audit.nav_faults(good, audit.NAV_FIXTURE_A_FIFTH_ITEM)
    return _desk_plant(faults, "add a fifth page to the nav",
                       "audit.nav_faults")


def plant_an_old_route_left_to_404() -> Result:
    """Remove a route and leave nothing where it was.

    A link somebody bookmarked or wrote down still has to land. A 404 tells
    them the app lost something; a redirect tells them where it went, and the
    address bar says so.
    """
    good_nav = "".join(
        f'<a href="#/{p}" data-route="{p}">x</a>' for p in audit.NAV_PAGES)
    faults = audit.nav_faults(audit.NAV_FIXTURE_A_DEAD_LINK, good_nav)
    return _desk_plant(faults, "leave a removed route to 404",
                       "audit.nav_faults")


def plant_a_pick_on_the_login_page() -> Result:
    """Put a side on the sign-in screen.

    The login page carries a per-sport record and a slate size, because that
    says the appliance is alive and working before anybody types anything. It
    is also THE ONE PLACE THE RECORD FACES SOMEBODY WHO HAS NOT SIGNED IN, so
    it is written to be worth nothing to them. A count is not a tip; a side
    is.
    """
    faults = audit.login_glance_faults(audit.LOGIN_FIXTURE_A_PICK)
    faults += audit.login_glance_faults(audit.LOGIN_FIXTURE_A_PROBABILITY)
    faults += audit.login_glance_faults(audit.LOGIN_FIXTURE_A_RATE)
    return _desk_plant(faults, "show a pick on the sign-in screen",
                       "audit.login_glance_faults")


def plant_a_silent_attach_to_an_older_build() -> Result:
    """Attach to a server from a different build without asking.

    THE FAILURE THAT DOES NOT LOOK LIKE ONE. The app opens, every screen
    renders, nothing errors -- and the code answering is not the code that was
    just built. The launcher shows a photograph and the operator has no reason
    to doubt it.

    Run rather than read: this calls the launcher's own decision function with
    a mismatch and checks it does not say "attach". Reading the source for a
    comparison would pass the moment somebody moved the comparison.
    """
    import sys as _sys
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parent.parent.parent
    _sys.path.insert(0, str(root / "desktop"))
    try:
        import launcher as _launcher
    finally:
        _sys.path.pop(0)

    decision = _launcher.attach_decision("built-today", "built-in-august")
    caught = decision != _launcher.ATTACH
    detail = (
        f"a mismatched build gives {decision!r}, not 'attach': the launcher "
        f"asks before it opens code nobody built"
        if caught else
        "the launcher attached to a server from a different build without "
        "asking. The app would open, work, and show a photograph of an older "
        "commit.")
    # The other two directions, so a decision that simply never attaches -- and
    # would therefore also 'pass' -- is not mistaken for a working guard.
    if caught and _launcher.attach_decision("same", "same") != _launcher.ATTACH:
        caught, detail = False, "the launcher refuses to attach to its OWN build"
    if caught and _launcher.attach_decision("a", "b", confirmed=True) != _launcher.RESTART:
        caught, detail = False, "a mismatch the operator confirmed does not restart"
    return Result("THE DESK", "attach silently to an older build",
                  "launcher.attach_decision", caught, detail)


def plant_a_model_constant_made_editable() -> Result:
    """Put the props floor in the settings form.

    THE FENCE. Operational knobs are preferences: getting one wrong costs a
    late slate. The props floor is not -- every figure already written was
    produced under the old value, and a curve computed across a change nobody
    recorded describes two different models at once. So changing it is a
    ruling made in config.py with a dated note, and this page refuses it BY
    NAME rather than by not drawing a box.
    """
    from gridiron import db as _db, settings as _settings

    conn = _db.connect(":memory:")
    _db.init(conn)
    try:
        _settings.set_value(conn, "PROPS_MIN_CLAIM", "0.50")
    except _settings.SettingRefused as exc:
        return Result("SETTINGS", "edit a model constant from the settings page",
                      "settings.set_value", True, str(exc))
    return Result("SETTINGS", "edit a model constant from the settings page",
                  "settings.set_value", False,
                  "the props floor was written from the settings page")


def plant_a_setting_updated_in_place() -> Result:
    """Rewrite a settings row instead of appending a new one.

    A settings row records a DECISION -- at 21:40 the operator moved the
    baseball slate. Updating in place destroys the only evidence of when a
    schedule changed and what from, which is exactly what somebody wants when
    a slate is missed and nobody remembers whether the time moved.
    """
    from gridiron import db as _db

    conn = _db.connect(":memory:")
    _db.init(conn)
    conn.execute("INSERT INTO settings (changed_utc, name, value)"
                 " VALUES ('2026-09-02T00:00:00Z','predict_mlb_at','11:00')")
    try:
        conn.execute("UPDATE settings SET value = '09:00'"
                     " WHERE name = 'predict_mlb_at'")
    except Exception as exc:  # noqa: BLE001 - the trigger is the guard
        return Result("LAW 3", "rewrite a settings row in place",
                      "settings_no_update", True, str(exc))
    return Result("LAW 3", "rewrite a settings row in place",
                  "settings_no_update", False,
                  "a settings row was edited after the fact")


def plant_a_schedule_change_claimed_without_a_read_back() -> Result:
    """Report a task moved without asking the OS whether it did.

    An exit code says the command was accepted, not that the task moved. A
    settings page saying 11:05 over a scheduler still firing at 11:00 is worse
    than not offering the setting: the operator now believes something false
    and has a screen agreeing with them.
    """
    faults = audit.schedule_claim_faults(audit.SCHEDULE_FIXTURE_NO_READBACK)
    faults += audit.schedule_claim_faults(audit.SCHEDULE_FIXTURE_DISAGREES)
    return _desk_plant(faults, "claim a schedule change without confirming it",
                       "audit.schedule_claim_faults")


def plant_an_unauthenticated_settings_write() -> Result:
    """POST a settings change with no session.

    The route is closed because `require_session` closes everything not on the
    open list -- so it is protected because it was added, not because somebody
    remembered to protect it.
    """
    from fastapi.testclient import TestClient

    from gridiron import api as _api

    client = TestClient(_api.app)
    got = client.post("/api/settings",
                      json={"name": "predict_mlb_at", "value": "03:00"})
    caught = got.status_code in (401, 403, 503)
    return Result("SETTINGS", "change a setting with no session",
                  "api.require_session", caught,
                  f"HTTP {got.status_code}")


def plant_a_calendar_that_merges_sports() -> Result:
    """Put a football day into the baseball calendar.

    LAW 6 in the place it is least visible: nobody checks the sport of a green
    square. One square holding two records is two records averaged into one
    colour, and the reader takes it in without reading a number.
    """
    faults = audit.calendar_faults(audit.CALENDAR_FIXTURE_MERGED)
    return _desk_plant(faults, "put another sport's day on the calendar",
                       "audit.calendar_faults")


def plant_a_void_counted_as_a_loss() -> Result:
    """Fold a day's voids into its settled count.

    A void is a question that was never answered. A day that voided four and
    won three is not a 3-4 day, and tinting it red says the model was wrong
    about games it never got to be wrong about.
    """
    faults = audit.calendar_faults(audit.CALENDAR_FIXTURE_VOID_AS_LOSS)
    return _desk_plant(faults, "count a void as a loss on the calendar",
                       "audit.calendar_faults")


def plant_a_square_tinted_against_its_balance() -> Result:
    """Tint a losing day green.

    The tint is the day's balance and nothing else -- not the model's
    confidence that day, not the size of its disagreements, not a streak. Any
    of those would make a square green for a reason other than "more went
    right than wrong", which is the one thing a reader will believe it means.
    """
    faults = audit.calendar_faults(audit.CALENDAR_FIXTURE_WRONG_TINT)
    return _desk_plant(faults, "tint a calendar square against its own balance",
                       "audit.calendar_faults")


def plant_a_progress_line_showing_a_percentage() -> Result:
    """Say "70% of the way to a verdict" instead of "14 of 20".

    On a page whose whole subject is probabilities, a share will be read as
    one. It also hides the sample size, which LAW 4 requires beside every
    figure -- and the count IS the sample size here, so the percentage
    replaces the very number the law is about.
    """
    faults = audit.progress_faults(audit.PROGRESS_FIXTURE_PERCENT)
    return _desk_plant(faults, "state a gate as a percentage of the way there",
                       "audit.progress_faults")


def plant_a_gate_line_without_its_n() -> Result:
    """Report progress toward a verdict with no sample size."""
    faults = audit.progress_faults(audit.PROGRESS_FIXTURE_NO_N)
    return _desk_plant(faults, "show a gate line with no N",
                       "audit.progress_faults")


def plant_a_green_progress_bar() -> Result:
    """Fill the progress bar with the colour that means a pick won.

    A FILLING BAR IS NOT A WIN. All it means is that more questions have been
    answered; the tier may still turn out to be badly calibrated when the
    verdict finally lands. Green would tell a reader the opposite, and would
    do it before there is any verdict at all.
    """
    payload = audit.progress_faults(audit.PROGRESS_FIXTURE_GREEN)
    css = audit.colour_law_faults(".gate-bar i { background: var(--win); }")
    return _desk_plant(payload + css, "fill the progress bar with the win colour",
                       "audit.progress_faults + audit.colour_law_faults")


def plant_a_resolved_row_on_picks() -> Result:
    """List last night's settled picks underneath tonight's.

    Picks answers "what does the model say about tonight". A resolved section
    underneath answers a different question, and it grew by a slate a day all
    season -- which is why settled rows now live in Results and only there
    (GRIDIRON_16 R4).
    """
    faults = audit.picks_resolved_faults(audit.PICKS_RESOLVED_FIXTURE_POSITIVE)
    return _desk_plant(faults, "list resolved picks on the Picks page",
                       "audit.picks_resolved_faults")


def plant_a_surviving_calls_symbol() -> Result:
    """Put the operator's call block back into the renderer.

    THE STUMP TEST. Operator calls were withdrawn by surgery rather than
    revert, because the notifier shipped in the same brief and had to
    survive. Surgery leaves stumps, and a stump is worse than the feature: a
    reader a month from now cannot tell one from something still live.
    """
    faults = audit.withdrawn_calls_faults(
        audit.WITHDRAWN_CALLS_FIXTURE_POSITIVE, comment="//")
    return _desk_plant(faults, "reinstate the withdrawn call block",
                       "audit.withdrawn_calls_faults")


def plant_a_green_link() -> Result:
    """Paint a link in the win colour.

    THE MISUSE THE RENAME ENDED. Green was the interactive accent AND the
    positive value until 2026-09-02, so every link, tab, focus ring and
    pressed segment on the page was drawn in the colour that means a pick
    won. A page full of controls read as a page full of wins, and the one
    place the colour carried information was the place it was least noticed.
    """
    faults = [f for f in audit.colour_law_faults(
        ".row-more { color: var(--win); text-decoration: none; }")]
    return _desk_plant(faults, "paint a link in the colour that means won",
                       "audit.colour_law_faults")


def plant_a_red_warning_border() -> Result:
    """Draw a notice border in the loss colour.

    The other half. Red was every warning -- a failed task, a stale feed, an
    error box -- which put "this fetch did not work" and "this pick lost" in
    the same colour. A warning is not a loss; it carries weight and position
    instead (R2).
    """
    faults = audit.colour_law_faults(
        ".notices-summary { border-left: 2px solid var(--loss); }")
    return _desk_plant(faults, "draw a warning border in the colour that "
                               "means lost", "audit.colour_law_faults")


def plant_a_green_live_mark() -> Result:
    """Draw the live mark in the accent colour.

    Green has exactly two jobs here: it is the positive value and it is the
    interactive accent. A game being played is neither -- it has not finished
    and there is nothing to click -- so a green mark tells a reader the model
    is winning before anything has been settled.
    """
    faults = audit.live_mark_faults(audit.LIVE_MARK_FIXTURE_POSITIVE)
    return _desk_plant(faults, "draw the live mark in the accent colour",
                       "audit.live_mark_faults")


def plant_a_re_sort_during_a_live_slate() -> Result:
    """Rebuild the whole slate when a score arrives.

    It looks like the obvious implementation -- new data, re-render -- and it
    re-sorts: by confidence the finished games climb over the ones still being
    played, so the tile somebody is reading slides away under them, every
    sixty seconds, for the length of the slate.
    """
    faults = audit.live_update_faults(audit.LIVE_UPDATE_FIXTURE_POSITIVE)
    return _desk_plant(faults, "re-render the slate when a score arrives",
                       "audit.live_update_faults")


def plant_a_bouncing_chip() -> Result:
    """A 400ms bounce on the verdict chip.

    THE MOST TEMPTING ANIMATION IN THE WHOLE INTERFACE, which is why it is the
    planted one. A win that springs into place feels good, and that is the
    objection: this project reports a probability and keeps score of it, so a
    loss has to look exactly like a win at 150ms, quietly. Anything that
    celebrates one outcome is the interface having an opinion about the
    record.
    """
    faults = audit.motion_faults(audit.MOTION_FIXTURE_POSITIVE)
    return _desk_plant(faults, "bounce the verdict chip for 400ms",
                       "audit.motion_faults")


def plant_a_strobing_live_mark() -> Result:
    """The same guard's other direction: the one allowed loop, run too fast.

    A ceiling alone would have passed this, and a 200ms pulse is a 5Hz strobe
    -- visually horrible and a real hazard for photosensitive readers. The
    live mark has a FLOOR for that reason, and the two faults are opposite.
    """
    faults = audit.motion_faults(audit.MOTION_FIXTURE_STROBE)
    return _desk_plant(faults, "strobe the live mark at 200ms",
                       "audit.motion_faults")


def plant_a_live_import_in_a_prediction_path() -> Result:
    """Import the live poller from a sport's forecasting module.

    THE SHARPEST VERSION OF LAW 1. A market line is somebody else's opinion
    about the game; a live score is THE ANSWER. A forecast that could reach it
    is not anchored, it is copying -- and it would produce a calibration curve
    of astonishing quality.
    """
    planted = (
        "import gridiron.live" + chr(10) +
        "def build_features(conn, q, cache=None):" + chr(10) +
        "    return gridiron.live.open_windows(conn)" + chr(10)
    )
    hits = _scan_planted_module(planted)
    if hits:
        return Result("LAW 1", "import the live scores into a prediction path",
                      "audit.imported_modules / market_identifiers_in", True,
                      hits[0])
    return Result("LAW 1", "import the live scores into a prediction path",
                  "audit.imported_modules / market_identifiers_in", False,
                  "NOT CAUGHT - a forecasting module could read the score")


def plant_a_live_column_read_in_a_prediction_path() -> Result:
    """Read the live clock from a module that writes forecasts."""
    planted = (
        "def build_features(conn, q, cache=None):" + chr(10) +
        "    row = conn.execute('SELECT live_period, live_clock FROM games')" + chr(10) +
        "    return row" + chr(10)
    )
    hits = _scan_planted_module(planted)
    if hits:
        return Result("LAW 1", "read the live clock from a prediction path",
                      "audit.market_identifiers_in", True, hits[0])
    return Result("LAW 1", "read the live clock from a prediction path",
                  "audit.market_identifiers_in", False,
                  "NOT CAUGHT - the live columns are reachable from a forecast")


def plant_a_poller_that_settles_a_prediction() -> Result:
    """Let live status write an outcome without the resolver.

    Marking a game final is a fact about the game. Settling a prediction is a
    claim about a forecast, and the record must have exactly one path to one.
    Proven behaviourally: a poll handed no resolver leaves every prediction
    open however finished the game is.
    """
    from gridiron import db as _db, live as _live

    conn = _db.open_db(":memory:")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status) VALUES ('cfb_p','cfb',2026,20260905,'REG',"
        " '2026-09-05T16:00:00Z','AAA','BBB','scheduled')")
    conn.execute(
        "INSERT INTO predictions (sport, game_id, created_utc, market_type,"
        " subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning) VALUES"
        " ('cfb','cfb_p',?, 'spread','AAA',-3.5,0.61,'cover','statistical',"
        " 'v1','{}','planted')", (_db.utcnow(),))
    conn.commit()
    import datetime as _dt
    _live.poll(
        conn,
        now=_dt.datetime(2026, 9, 5, 18, 0, tzinfo=_dt.timezone.utc),
        fetcher=lambda *a, **k: [{"game_id": "cfb_p", "event_id": "p",
                                  "status": "final", "home_score": 28,
                                  "away_score": 10, "period": "4",
                                  "clock": "0:00"}],
        resolver=None,
    )
    open_rows = conn.execute(
        "SELECT COUNT(*) FROM predictions WHERE resolved_utc IS NULL"
    ).fetchone()[0]
    final = conn.execute(
        "SELECT status FROM games WHERE id='cfb_p'").fetchone()[0]
    if final == "final" and open_rows == 1:
        return Result("LAW 3", "settle a prediction from live status alone",
                      "live.poll leaves resolution to resolve_all", True,
                      "the game is final and its prediction is still open; "
                      "only the resolver settles")
    return Result("LAW 3", "settle a prediction from live status alone",
                  "live.poll leaves resolution to resolve_all", False,
                  f"NOT CAUGHT - game={final!r}, still-open={open_rows}")


def plant_a_summed_record_on_the_tabs() -> Result:
    """Put a combined win-loss figure where the per-sport tabs go.

    The most tempting number in the whole interface: one line saying how the
    model is doing. It would describe nothing -- NFL spreads and MLB
    moneylines are different questions -- and it would flatter, because
    whichever sport is easiest lifts the rest.
    """
    planted = {
        "sports": [
            {"label": "NFL", "record_line": "NFL 0 settled"},
            {"label": "MLB", "record_line": "MLB 33-18"},
        ],
        "total": "33-18 across all sports",
    }
    faults = audit.summed_records(planted)
    return _desk_plant(faults, "show one combined record across the sports",
                       "audit.summed_records")


def plant_a_stale_build_that_says_nothing() -> Result:
    """A bundle behind the repository, rendering as though it were current.

    THIS IS THE FAILURE THAT DOES NOT LOOK LIKE ONE. The operator's exe was
    built 2026-08-29 and showed a live, current record through an interface
    that predated college football, the desk and the rail. Nothing was broken.
    The record kept filling, the window kept opening, and the screen was a
    photograph. The only way that gets noticed is if the page says so.

    Planted as a freshness report a stale build would produce, checked against
    the words that must come out of it.
    """
    from gridiron import language

    stale = {"from_source": False, "commit": "0e2376900000", "built_utc":
             "2026-08-29T19:54:00Z", "behind": 4, "stale": True}
    said = language.build_line(stale)
    if "behind" in said and "rebuild" in said and "4" in said:
        return Result("THE BUILD", "run a bundle four commits behind in silence",
                      "language.build_line", True, said)
    return Result("THE BUILD", "run a bundle four commits behind in silence",
                  "language.build_line", False,
                  f"NOT CAUGHT - a stale build rendered as {said!r}, which does "
                  f"not tell the reader it is stale or what to do")


def plant_a_bundle_missing_a_sport() -> Result:
    """Ship a build whose hidden imports do not cover every declared sport.

    The spec named nfl, mlb and nba and was written before college football
    existed. A bundle built from it would have started, served, and forecast
    three of four sports -- the fourth silently absent from a record that
    already holds 194 of its predictions.
    """
    from gridiron import config
    from pathlib import Path

    spec = Path("desktop/gridiron.spec").read_text(encoding="utf-8")
    # The fix derives the list; the defect hardcodes it. A spec that names any
    # sport literally is one sport away from being wrong again.
    hardcoded = [s for s in config.SPORTS if f'"gridiron.sports.{s}"' in spec]
    if not hardcoded and "_SPORT_MODULES" in spec:
        return Result("THE BUILD", "ship a bundle missing a declared sport",
                      "desktop/gridiron.spec derives from config.SPORTS", True,
                      "the spec derives its sport modules from config.SPORTS, "
                      "so a new sport cannot be left out of a build")
    return Result("THE BUILD", "ship a bundle missing a declared sport",
                  "desktop/gridiron.spec derives from config.SPORTS", False,
                  f"NOT CAUGHT - the spec hardcodes {hardcoded}, so the next "
                  f"sport added ships in the record and not in the bundle")


def plant_a_pick_line_that_disagrees_with_its_label() -> Result:
    """A tile naming one side across the middle and the other underneath.

    THIS IS THE TILE THAT SHIPPED: "Alabama -24.5 ... 76% MISSES". Both halves
    were individually defensible -- the rung is the question as asked, the
    label is the side as stored -- and together they made a reader do the
    inversion on every tile to find out that the pick was East Carolina.
    """
    planted = [{
        "market_type": "spread",
        "model_side": "fail to cover",     # the model is AGAINST Alabama
        "line_asked": -24.5,
        "subject": "ALA",
        "opponent": "ECU",
        "team_names": {"ALA": {"full": "Alabama Crimson Tide", "city": "Alabama"},
                       "ECU": {"full": "East Carolina Pirates",
                               "city": "East Carolina"}},
        # ... and the tile says the opposite of all of that.
        "tile_line": "Alabama -24.5",
        "tile_label": "misses",
    }]
    faults = audit.pick_disagrees_with_its_label(planted)
    return _desk_plant(faults, "name one side on the tile and bet against it "
                               "in the label",
                       "audit.pick_disagrees_with_its_label")


def plant_a_side_with_no_words() -> Result:
    """Hand the humaniser a stored side it has no verb for.

    The defect this replaces did not look like a defect: `SIDE_WORDS.get(side,
    "covers")` reads as a sensible fallback and produced a perfectly formed
    sentence stating the opposite of nine forecasts.
    """
    faults = audit.sides_without_words(["cover", "fail to score", "win"])
    return _desk_plant(faults, "render a side the humaniser has no words for",
                       "audit.sides_without_words")


def plant_a_slate_key_on_the_page() -> Result:
    """Put the raw eight-digit slate key where a reader can see it."""
    faults = audit.plain_words_violations("Season 2026, week 20260905")
    return _desk_plant(faults, "show the raw slate key instead of the date",
                       "audit.plain_words_violations")


def plant_a_tile_that_truncates() -> Result:
    """Cut a tile's matchup off with an ellipsis.

    Reads as a tidy grid, which is the trouble. The frame scrolls precisely so
    that nothing has to be cut off; an ellipsis on a tile is the interface
    telling a reader there is more and giving them no way to see it.
    """
    faults = audit.frame_truncation_faults(audit.CSS_FIXTURE_POSITIVE)
    return _desk_plant(faults, "truncate a tile with an ellipsis",
                       "audit.frame_truncation_faults")


def plant_a_selection_that_moves_the_frame() -> Result:
    """Select a pick without putting the frame back where it was.

    The version planted here looks completely reasonable -- it sets the
    attribute and paints the rail. What it does not do is remember where the
    reader was, so clicking pick 140 of 177 throws them to the top and looking
    at something costs them their place.
    """
    faults = audit.selection_moves_the_frame(audit.SELECT_FIXTURE_POSITIVE)
    return _desk_plant(faults, "select a pick and lose the reader's place",
                       "audit.selection_moves_the_frame")


def plant_a_rail_panel_that_writes_its_own_prose() -> Result:
    """Build a rail sentence in the browser instead of placing one.

    The fifth appearance of one defect. Prose composed in JavaScript is
    outside the humaniser that resolves which side was taken, outside the
    plain-words rule, and outside the Python scans -- which is exactly how a
    card came to read "over" beside a prediction of UNDER.
    """
    import tempfile
    # A LITERAL BLOCK, not escapes: five separate guards in this repository
    # have been blinded by a backslash mangled in transit, and a planting that
    # silently stops matching is worse than no planting.
    planted = """
  function paintRail(tile) {
    const card = slateCards.get(tile.dataset.id);
    panel.textContent = 'the model likes ' + card.subject;
  }
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(planted)
        where = handle.name
    faults = audit.js_prose_composition(where)
    return _desk_plant(faults, "compose a rail sentence in the browser",
                       "audit.js_prose_composition")


def _desk_plant(faults, what: str, guard: str) -> Result:
    if faults:
        return Result("THE DESK", what, guard, True, faults[0])
    return Result("THE DESK", what, guard, False,
                  "NOT CAUGHT - the desk would break one of its own promises "
                  "in a way nobody can see by looking")


def plant_a_rung_chosen_by_rotation() -> Result:
    """Choose a spread rung by hashing the game id instead of by the margin.

    THIS IS THE SHAPE RULING R4 REPLACED, and it is planted rather than
    described because it did not look wrong while it was shipping. A rotation
    spreads the five declared rungs evenly across a slate, which reads as
    fairness; what it actually does is ask "does North Dakota State cover -0.5"
    of a team favoured by sixty. On the college slate of 2026-09-05 that put
    77% of cross-division spreads at 90%+ confidence, against 20% of the
    FBS-against-FBS ones -- a record measuring the schedule.
    """
    return _rung_plant(
        audit.RUNG_FIXTURE_POSITIVE,
        "choose a spread rung by rotation on the live path",
    )


def plant_a_rung_chosen_by_the_market() -> Result:
    """Form the question at the number the book is offering.

    The worst of the two because it would not read as a mistake. Asking at the
    market's line looks like realism -- everyone else is asking that question
    -- and it produces a calibration curve that measures how well the model
    agrees with a number it was handed. LAW 1 exists for exactly this.
    """
    return _rung_plant(
        _RUNG_FROM_THE_MARKET,
        "form the spread question at the market's own line",
    )


def _rung_plant(source: str, what: str) -> Result:
    faults = audit.rung_selection_faults(source, where="planted")
    if faults:
        return Result("RUNG BY MARGIN", what,
                      "audit.rung_selection_faults", True, faults[0])
    return Result("RUNG BY MARGIN", what,
                  "audit.rung_selection_faults", False,
                  "NOT CAUGHT - the rung would be chosen by something other "
                  "than what the model expects to happen")


def plant_a_home_run_bucket_below_fifty() -> Result:
    """Check the home-run market's claims really do land in the declared buckets.

    THE BRIEF ASKED FOR A BUCKET SET EXTENDING BELOW 50 FOR THIS MARKET, and
    building it would have been wrong. An over-0.5 home-run prop does live at
    15-35%, but `baseline.stated_side` converts every probability into a SIDE
    and a confidence in that side, so a 28% chance of a home run is stored as a
    72% claim that there will not be one. Confidence is >= 0.5 by construction
    and a sub-50 bucket could never receive a row.

    So this plants the opposite: a home-run probability from the bottom of that
    range, checked to land in a real bucket with the NO side stated. A bucket
    set starting below 50 would be a set of empty bins next to a tier chip
    reading LEAN on a claim that is not a lean.
    """
    side, claimed = baseline.stated_side(0.28, "over", "under")
    label = calibration.bucket_label(claimed)
    tier = calibration.TIERS.get(label)
    lowest = min(lo for lo, _hi, _name in calibration.BUCKETS)
    caught = (
        side == "under"
        and abs(claimed - 0.72) < 1e-9
        and label == "70-80%"
        and tier == "STRONG"
        and lowest == 0.50
    )
    return Result(
        "SUB-50 CLAIMS MAP CORRECTLY",
        "read a 28% home-run chance as a weak claim rather than a strong NO",
        "baseline.stated_side + calibration.bucket_label", caught,
        f"28% over becomes {side!r} at {claimed:.0%}, bucket {label}, tier "
        f"{tier}; the bucket set starts at {lowest:.0%} because confidence "
        "cannot be lower"
        if caught else
        f"NOT CAUGHT - 28% mapped to side={side!r} claimed={claimed} "
        f"bucket={label} tier={tier} lowest bucket={lowest}",
    )


def plant_an_orphan_guard() -> Result:
    """Add a guard nothing calls and check the orphan scan names it.

    THIS IS THE FAILURE THAT PROMPTED THE SCAN, PLANTED. `rung_probabilities`
    shipped as checklist item 4's cross-check with zero callers anywhere -- not
    in production, not even in a test. The suite was green. The check was
    decorative, and nothing in the harness could tell the difference between a
    guard that passes and a guard that never runs.
    """
    root = Path(audit.__file__).resolve().parent
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / "gridiron"
        shutil.copytree(root, copy, ignore=shutil.ignore_patterns("__pycache__"))
        (copy / "orphaned_check.py").write_text(
            chr(10).join([
                '"""A guard nobody calls, planted."""',
                "",
                "",
                "def assert_the_thing_nobody_checks(value):",
                "    if value < 0:",
                "        raise ValueError('negative')",
            ]),
            encoding="utf-8",
        )
        try:
            audit.check_no_orphan_functions(copy)
        except audit.LawViolation as exc:
            return Result("ORPHANS", "ship a guard that nothing calls",
                          "audit.check_no_orphan_functions", True, str(exc))
        return Result("ORPHANS", "ship a guard that nothing calls",
                      "audit.check_no_orphan_functions", False,
                      "NOT CAUGHT - a guard with no caller passed the scan")


def plant_a_decorated_function_mistaken_for_an_orphan() -> Result:
    """The other half: a REGISTERED function must not be reported.

    A scan that flagged every factor would need a thirty-five line allowlist,
    and an allowlist that long is a mute button. The decorator is the call site;
    this proves the scan knows that, so the allowlist stays short enough to read.
    """
    hits = audit.orphan_functions()
    factors = [h for h in hits if h.split(" ")[0] in registry.REGISTRY]
    caught = not factors
    return Result(
        "ORPHANS", "report a decorator-registered factor as uncalled",
        "audit.orphan_functions", caught,
        f"{len(registry.REGISTRY)} registered factors, none reported as orphans"
        if caught else
        f"NOT CAUGHT - registered factors flagged: {factors[:5]}",
    )


def plant_a_tier_row_below_its_gate_showing_a_rate() -> Result:
    """A confidence band with nine settled picks, asked for its accuracy.

    This is the most persuasive lie the Record tab could tell: a rate in a
    column of real rates, off a sample too small to mean anything, beside a
    tier label a reader already trusts from the pick cards. LAW 4 says the row
    states the shortfall and NO percentage -- not greyed, not parenthesised,
    absent.
    """
    thin = calibration.tier_verdict(0.75, 0.90, 9)
    caught = (
        thin == f"unproven \u2014 9 of {calibration.TIER_MIN_SETTLED}"
        and "%" not in thin
        and "90" not in thin
    )
    return Result(
        "LAW 4", "show a tier row's accuracy below its sample gate",
        "calibration.tier_verdict", caught,
        f"a nine-sample band states the shortfall and no rate: {thin!r}"
        if caught else
        f"NOT CAUGHT - a nine-sample band reported {thin!r}",
    )


def plant_verdict_words_that_disagree_with_the_gap() -> Result:
    """Verdict prose must follow the declared rule on (actual - claimed).

    The rule is a dated constant precisely so the words cannot be chosen to
    suit the row. Planted: a band that is twenty points overconfident, checked
    that it is not described as fine.
    """
    badly_off = calibration.tier_verdict(0.75, 0.55, 40)
    honest = calibration.tier_verdict(0.55, 0.55, 40)
    better = calibration.tier_verdict(0.60, 0.70, 40)
    caught = (
        badly_off == "much more confident than it should be"
        and honest == "about as good as it claims"
        and better == "better than it claims"
        and badly_off != honest
    )
    return Result(
        "VERDICT FOLLOWS THE RULE",
        "describe a twenty-point miss as well calibrated",
        "calibration.tier_verdict", caught,
        f"20 points off reads {badly_off!r}, on the nose reads {honest!r}"
        if caught else
        f"NOT CAUGHT - 20 points off reported {badly_off!r}",
    )


def plant_a_pooled_strong_tier() -> Result:
    """Collapse STRONG's two bands into one row and check the table refuses.

    STRONG spans 70-80% and 80%+. Pooling them is the merge LAW 4 forbids and
    it flatters in a known direction: the easier band lifts the harder one, so
    a model badly calibrated at 70-80% shows one reassuring number.
    """
    import tempfile as _tf
    from pathlib import Path as _P

    with _tf.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        conn = db.open_db(_P(tmp) / "tiers.db")
        table = calibration.tier_table(conn, sport="nfl", market_type="spread")
        conn.close()
    bands = [r["band"] for r in table["rows"]]
    strong = [r for r in table["rows"] if r["tier"] == "STRONG"]
    caught = len(strong) == 2 and bands == [b[2] for b in calibration.BUCKETS]
    return Result(
        "NO MERGED CURVES", "pool STRONG's two bands into one tier row",
        "calibration.tier_table", caught,
        f"STRONG reported separately as {[r['band'] for r in strong]}"
        if caught else
        f"NOT CAUGHT - STRONG appears {len(strong)} time(s); bands {bands}",
    )


def plant_a_why_that_disagrees_with_its_contributions() -> Result:
    """Prose naming the wrong driver, and prose with the direction flipped.

    The words on a pick are DERIVED from the contributions rather than written
    beside them, so they cannot drift. Planted both ways.
    """
    from gridiron import language as _lang

    phrases = {f.name: f.why for f in registry.all_factors() if f.why}
    item = {
        "subject": "TB", "market_type": "moneyline", "model_side": "win",
        "model_prob": 0.6,
        "contributions": [
            {"factor": "mlb_starter_rolling_perf", "contribution": 0.90,
             "missing": False},
            {"factor": "mlb_park_factor", "contribution": -0.40,
             "missing": False},
        ],
    }
    said = _lang.why_sentences(item, phrases)
    top = phrases["mlb_starter_rolling_perf"]
    # The LEAD names the largest contributor, whichever way it points.
    names_top = bool(said) and top.lower() in said[0].lower()
    # The SECOND sentence is where direction shows: the park pulls against the
    # pick here, so it must be introduced as opposing rather than agreeing.
    opposes = len(said) > 1 and said[1].startswith("Pulling the other way")
    # ...and taking the other side must REVERSE that, not repeat it.
    flipped = _lang.why_sentences(dict(item, model_side="lose"), phrases)
    reverses = len(flipped) > 1 and "points the same way" in flipped[1]
    caught = bool(names_top and opposes and reverses)
    return Result(
        "WORDS FOLLOW THE NUMBERS",
        "let a pick's prose name a different driver than its arithmetic",
        "language.why_sentences", caught,
        f"largest contribution leads, and its sign sets how the second is "
        f"introduced: {said[1]!r}"
        if caught else
        f"NOT CAUGHT - prose was {said!r}",
    )


def plant_a_factor_with_no_why_template() -> Result:
    """A factor that cannot be explained would be silently dropped from the
    reasons: present in the arithmetic, absent from the words."""
    missing = [f.name for f in registry.all_factors() if not (f.why or "").strip()]
    caught = not missing
    return Result(
        "EVERY FACTOR EXPLAINS ITSELF", "ship a factor with no why-template",
        "registry.Factor.why", caught,
        f"all {len(registry.all_factors())} declared factors carry a template"
        if caught else
        f"NOT CAUGHT - no template on: {', '.join(sorted(missing))}",
    )


def plant_a_view_that_names_the_side_itself() -> Result:
    """The same defect OUTSIDE language.py, where the first guard was blind.

    `check_side_named` scans the humaniser, on the premise that all prose lives
    there. `views._resolved_story` disproved it: "picked ATL" over nine resolved
    rows whose pick was on Colorado -- the fourth instance of one defect, and
    the second time a guard was written narrower than the rule it enforces.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        pkg = Path(tmp) / "pkg"
        pkg.mkdir()
        (pkg / "views.py").write_text(chr(10).join([
            "def _resolved_story(r):",
            '    """A planted view composing the side into a sentence."""',
            '    return f"picked {r[\'subject\']}"',
            "",
        ]), encoding="utf-8")
        try:
            audit.check_side_named_everywhere(pkg)
        except audit.LawViolation as exc:
            named = "_resolved_story" in str(exc)
            return Result("THE SIDE, IN PROSE, ANYWHERE",
                          "name the side from a raw subject outside language.py",
                          "audit.check_side_named_everywhere", named,
                          str(exc).splitlines()[-1] if named else
                          "caught, but the message does not name the function")
        return Result("THE SIDE, IN PROSE, ANYWHERE",
                      "name the side from a raw subject outside language.py",
                      "audit.check_side_named_everywhere", False,
                      "NOT CAUGHT - a view built the side into a sentence and passed")


def _planted_correction(extra: str) -> str:
    """A miniature correction module with one training query."""
    return chr(10).join([
        "import sqlite3",
        "",
        "",
        "def training_rows(conn, *, sport, before_utc):",
        "    return conn.execute(",
        '        "SELECT p.model_prob, p.outcome FROM predictions p"',
        '        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL"',
        '        " AND p.outcome IS NOT NULL AND p.resolved_utc < ?"',
        '        " AND NOT EXISTS (SELECT 1 FROM prediction_voids v"',
        '        "                 WHERE v.prediction_id = p.id)"',
        "        " + extra + ",",
        "        (sport, before_utc)).fetchall()",
        "",
    ])


def _correction_result(what: str, caught: bool, detail: str) -> Result:
    return Result("THE CORRECTION SEES CLAIMS ONLY", what,
                  "audit.check_correction_is_isolated", caught, detail)


def _plant_correction(extra: str, what: str, needle: str,
                      text: str | None = None) -> Result:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / "correction.py"
        copy.write_text(text if text is not None else _planted_correction(extra),
                        encoding="utf-8")
        try:
            audit.check_correction_is_isolated(copy)
        except audit.LawViolation as exc:
            if needle in str(exc):
                return _correction_result(what, True, str(exc).splitlines()[-1])
            return _correction_result(
                what, False,
                "caught, but the message does not name " + needle)
        return _correction_result(what, False,
                                  "NOT CAUGHT - " + what + " passed the scan")


def plant_a_rankings_factor() -> Result:
    """Give a college football factor a poll to read (ruling R-D).

    The exclusion is structural -- the context carries no poll field -- so a
    rankings factor has to invent one, and that is what this plants.
    """
    root = Path(audit.__file__).resolve().parent
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        pkg = Path(tmp)
        (pkg / "factors").mkdir(parents=True)
        (pkg / "sports").mkdir(parents=True)
        (pkg / "sports" / "cfb.py").write_text("SPORT = 'cfb'\n", encoding="utf-8")
        (pkg / "factors" / "cfb.py").write_text(chr(10).join([
            "def cfb_ap_rank_diff(ctx):",
            '    """A planted factor that reads the AP poll."""',
            "    return ctx.home_ap_rank - ctx.away_ap_rank",
            "",
        ]), encoding="utf-8")
        try:
            audit.check_no_rankings(pkg)
        except audit.LawViolation as exc:
            return Result("RANKINGS ARE NOT A FACTOR",
                          "let a college factor read the AP poll",
                          "audit.check_no_rankings", True,
                          str(exc).splitlines()[-1])
        return Result("RANKINGS ARE NOT A FACTOR",
                      "let a college factor read the AP poll",
                      "audit.check_no_rankings", False,
                      "NOT CAUGHT - a poll reached the model")


def plant_a_totals_curve_merged_with_margins() -> Result:
    """Score a totals question inside a spread category.

    A total is a question about the two teams' COMBINED score. It is right and
    wrong for different reasons than a margin, and the market prices it
    separately, so pooling the two would let one dilute the other -- the merge
    LAW 4 forbids, applied to market types within a sport.
    """
    from gridiron import calibration as _cal

    payload = {"category": "spread+total / statistical", "n": 40,
               "market": None, "predictor": "statistical"}
    try:
        _cal.assert_no_merged_categories([payload])
    except Exception as exc:
        return Result("A TOTAL IS NOT A MARGIN",
                      "score totals inside the spread category",
                      "calibration.assert_no_merged_categories", True,
                      str(exc).splitlines()[0][:96])
    return Result("A TOTAL IS NOT A MARGIN",
                  "score totals inside the spread category",
                  "calibration.assert_no_merged_categories", False,
                  "NOT CAUGHT - a merged totals/spread curve passed")


def plant_an_undated_cfb_sd() -> Result:
    """Ask for a totals SD that carries no measurement.

    `total_sd` has no fallback for the same reason `margin_sd` has none: a
    sport quietly receiving another's number is how NBA's market comparison
    was wrong for a day, and totals measure a different quantity again.
    """
    from gridiron.market import lines as _lines

    try:
        _lines.total_sd("nfl")
    except _lines.UnmeasuredMarginSD as exc:
        return Result("NO UNDATED STANDARD DEVIATIONS",
                      "compare a totals market with no measured SD",
                      "lines.total_sd", True, str(exc).splitlines()[0][:96])
    return Result("NO UNDATED STANDARD DEVIATIONS",
                  "compare a totals market with no measured SD",
                  "lines.total_sd", False,
                  "NOT CAUGHT - an unmeasured totals SD was served")


def plant_a_cross_sport_cfb_query() -> Result:
    """Ask for a college football figure without saying which sport."""
    from gridiron import config as _config

    try:
        _config.require_sport(None, "cfb scorecard")
    except _config.CrossSportAggregation as exc:
        return Result("LAW 6 COVERS THE NEW SPORT",
                      "read a college football record with no sport named",
                      "config.require_sport", True,
                      str(exc).splitlines()[0][:96])
    return Result("LAW 6 COVERS THE NEW SPORT",
                  "read a college football record with no sport named",
                  "config.require_sport", False,
                  "NOT CAUGHT - a sportless query was served")


def plant_a_second_look_served_from_cache() -> Result:
    """Set the near-start window to the live cache window.

    THIS IS THE DEFECT AS IT SHIPPED. Eight near-start snapshots were written
    inside the six-hour cache window and every one was a byte-for-byte replay
    of the open snapshot, so all four usable drift pairs read exactly zero
    movement. The task reported success and the measurement was of the cache.
    """
    from gridiron.data import sources as _sources
    from gridiron.market import espn as _espn

    original = _espn.NEAR_START_TTL
    try:
        _espn.NEAR_START_TTL = _sources.LIVE_TTL
        try:
            audit.check_the_second_look_is_fresh()
        except audit.LawViolation as exc:
            return Result("THE SECOND LOOK IS A SECOND LOOK",
                          "accept a cached quote as the near-start reading",
                          "audit.check_the_second_look_is_fresh", True,
                          str(exc).splitlines()[0][:96])
        return Result("THE SECOND LOOK IS A SECOND LOOK",
                      "accept a cached quote as the near-start reading",
                      "audit.check_the_second_look_is_fresh", False,
                      "NOT CAUGHT - a replayed quote passed as a second look")
    finally:
        _espn.NEAR_START_TTL = original


def plant_an_active_correction_below_the_gate() -> Result:
    """Ask the engine to activate a category with too little record.

    Fifty settled rows is the bar. Below it a correction is two numbers fitted
    on a handful of results, and applying it would let a dozen games decide
    what every future claim in the category is shown as.
    """
    from gridiron import correction as _c

    conn = _memory_record()
    _settle(conn, n=20, worth=0.6)
    report = _c.refit_all(conn, now="2026-06-01T00:00:00Z")
    cat = report["categories"][0]
    caught = not cat["active"] and str(_c.MIN_TRAIN) in cat["status"]
    return Result("CORRECTIONS ACTIVATE ONLY ON THEIR MERITS",
                  "activate a correction on 20 settled rows",
                  "correction.refit_all", caught,
                  cat["status"] if caught else
                  "NOT CAUGHT - a category under the gate went active")


def plant_a_correction_that_does_not_help() -> Result:
    """A well-calibrated category must NOT get a correction.

    The in-sample Brier always improves -- a fit improves the rows it was
    fitted on by construction -- so the gate that can say no is the holdout.
    This is the planting that proves it says no.
    """
    from gridiron import correction as _c

    conn = _memory_record()
    _settle(conn, n=200, worth=1.0)          # claims already worth what they say
    report = _c.refit_all(conn, now="2026-06-01T00:00:00Z")
    cat = report["categories"][0]
    caught = not cat["active"]
    return Result("CORRECTIONS ACTIVATE ONLY ON THEIR MERITS",
                  "activate a correction that does not improve unseen rows",
                  "correction.holdout_check", caught,
                  cat["status"] if caught else
                  "NOT CAUGHT - a correction that does not help went active")


def plant_a_genuine_correction_refused() -> Result:
    """The other direction: a real miscalibration must be ALLOWED through.

    A gate that never opens is not a gate, it is an off switch, and it would
    be indistinguishable from a working one for as long as no category
    qualified.
    """
    from gridiron import correction as _c

    conn = _memory_record()
    _settle(conn, n=200, worth=0.55)         # badly overconfident
    report = _c.refit_all(conn, now="2026-06-01T00:00:00Z")
    cat = report["categories"][0]
    return Result("CORRECTIONS ACTIVATE ONLY ON THEIR MERITS",
                  "refuse a correction that genuinely helps",
                  "correction.holdout_check", cat["active"],
                  cat["status"] if cat["active"] else
                  "NOT CAUGHT - a real miscalibration was refused, so the "
                  "gate never opens")


def plant_a_retroactive_correction() -> Result:
    """Try to rewrite an existing prediction's shown number.

    A correction reaches predictions written after it activates and no others.
    Recomputing an old row under a new version would make the record look
    better than it was, which is exactly what LAW 3 exists to stop.
    """
    conn = _memory_record()
    _settle(conn, n=3, worth=0.8)
    try:
        conn.execute("UPDATE predictions SET calibrated_prob = 0.5")
    except sqlite3.IntegrityError as exc:
        return Result("CORRECTIONS ACTIVATE ONLY ON THEIR MERITS",
                      "apply a correction retroactively to a written row",
                      "schema trigger predictions_no_update", True, str(exc))
    return Result("CORRECTIONS ACTIVATE ONLY ON THEIR MERITS",
                  "apply a correction retroactively to a written row",
                  "schema trigger predictions_no_update", False,
                  "NOT CAUGHT - a written prediction's shown number was rewritten")


def _memory_record():
    """A throwaway database with one game to hang predictions on."""
    from gridiron import db as _db

    conn = _db.connect(":memory:")
    _db.init(conn)
    conn.execute(
        # A final game must carry scores -- there is a CHECK for it, and it
        # caught this fixture before the planting could run.
        "INSERT INTO games (id, season, week, game_type, kickoff_utc, home,"
        " away, status, home_score, away_score, sport) VALUES"
        " ('g1', 2026, 1, 'REG', '2025-12-01T00:00:00Z', 'AAA', 'BBB',"
        " 'final', 24, 17, 'nfl')"
    )
    conn.commit()
    return conn


def _settle(conn, *, n: int, worth: float) -> None:
    """`n` settled predictions whose claims are worth `worth` times what they say.

    `worth=1.0` is a perfectly calibrated forecaster; below 1 is overconfident.
    Deterministic rather than random: a planted violation that fails one run in
    twenty is a planting nobody trusts.
    """
    import random as _random

    rng = _random.Random(19)
    rows = []
    for i in range(n):
        claim = 0.55 + (i % 40) * 0.01
        p_true = 0.5 + (claim - 0.5) * worth
        rows.append((claim, 1 if rng.random() < p_true else 0, i))
    for claim, outcome, i in rows:
        conn.execute(
            "INSERT INTO predictions (sport, created_utc, game_id, market_type,"
            " subject, model_prob, model_side, predictor, factor_set_version,"
            " factors_json, reasoning, resolved_utc, outcome)"
            " VALUES ('nfl', '2025-12-01T00:00:00Z', 'g1', 'moneyline', ?, ?,"
            " 'win', 'statistical', 'fs2', '{}', 'because', ?, ?)",
            (f"S{i}", claim, f"2026-01-{i % 28 + 1:02d}T00:00:{i % 60:02d}Z",
             outcome),
        )
    conn.commit()


def plant_a_correction_that_reads_the_score() -> Result:
    """Join the game table into the correction's training set.

    A correction is fitted ON OUTCOMES, which is legitimate and is also one
    step from a second model fitted on the result wearing a calibration label.
    The line is which tables it may name: the record's own claims and outcomes,
    and nothing that could tell it about the game itself.
    """
    return _plant_correction(
        '" JOIN games g ON g.id = p.game_id"',
        "join the game table into a correction fit", "games")


def plant_a_correction_that_reads_the_line() -> Result:
    """The same, through `market_snapshots` -- LAW 1's subject, after the fact."""
    return _plant_correction(
        '" JOIN market_snapshots s ON s.prediction_id = p.id"',
        "fit a correction on the market line", "market_snapshots")


def plant_a_correction_that_can_see_its_own_future() -> Result:
    """Drop the time bound from the training query.

    Without `resolved_utc <` the fit trains on rows that settled after it was
    made, and C2's holdout -- earliest 80% to fit, latest 20% to test -- would
    be testing on rows it had already trained on.
    """
    text = _planted_correction('""').replace(
        ' " AND p.outcome IS NOT NULL AND p.resolved_utc < ?"',
        ' " AND p.outcome IS NOT NULL"')
    return _plant_correction("", "fit a correction with no time bound",
                             "resolved_utc <", text=text)


def plant_a_correction_that_scores_a_void() -> Result:
    """Drop the void exclusion. A void has no outcome to be right or wrong about."""
    text = chr(10).join([
        "import sqlite3",
        "",
        "",
        "def training_rows(conn, *, sport, before_utc):",
        "    return conn.execute(",
        '        "SELECT p.model_prob, p.outcome FROM predictions p"',
        '        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL"',
        '        " AND p.outcome IS NOT NULL AND p.resolved_utc < ?",',
        "        (sport, before_utc)).fetchall()",
        "",
    ])
    return _plant_correction("", "train a correction on voided predictions",
                             "prediction_voids", text=text)


def plant_a_scored_rung_claim() -> Result:
    """Try to settle a rung claim as if it were a prediction.

    The rung log records what the model WOULD have claimed at rungs it was
    never asked about. Those claims have no outcome and were never
    committed to in advance; scoring them would let the model be judged on
    the questions it liked, and it would arrive looking like a bigger
    sample. The guard is that no scoring module may name the table at all.
    """
    root = Path(audit.__file__).resolve().parent
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / 'calibration.py'
        text = (root / 'calibration.py').read_text(encoding='utf-8')
        text += chr(10).join([
            '',
            '',
            'def curve_including_the_rungs(conn, *, sport):',
            '    return conn.execute(',
            '        "SELECT claimed FROM prop_rung_claims WHERE sport = ?",',
            '        (sport,)).fetchall()',
            '',
        ])
        copy.write_text(text, encoding='utf-8')
        import ast as _ast
        found = any(
            isinstance(node, _ast.Constant) and isinstance(node.value, str)
            and 'prop_rung_claims' in node.value
            for node in _ast.walk(_ast.parse(copy.read_text(encoding='utf-8')))
        )
        return Result('THE RUNG LOG IS NOT A RECORD',
                      'read the rung log from a scoring module',
                      'test_rungs.test_the_log_is_never_read_by_anything_that_scores',
                      found,
                      'a scoring module naming the rung log is detected'
                      if found else
                      'NOT CAUGHT - a scorer reached the rung log undetected')

def plant_a_renderer_that_composes_prose() -> Result:
    """Put the digest's real defect back into a copy of app.js.

    THE LINE PLANTED HERE SHIPPED: `'picked ' + String(s.subject)
    .toUpperCase()` named the team the model forecast AGAINST on every
    moneyline it took the other side of, and shouted a prop's stored stat
    suffix while doing it. Every Python guard was blind to it because it
    is JavaScript.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / 'app.js'
        copy.write_text(chr(10).join([
            'function settledRow(s) {',
            "  const row = el('div', 'settled-row');",
            "  row.appendChild(el('span', 'settled-pick', 'picked ' + "
            '                 "String(s.subject).toUpperCase()));',
            '  return row;',
            '}',
        ]), encoding='utf-8')
        try:
            audit.check_js_composes_no_prose(copy)
        except audit.LawViolation as exc:
            return Result('THE RENDERER COMPOSES NO PROSE',
                          'build a pick sentence in app.js from the raw subject',
                          'audit.check_js_composes_no_prose', True,
                          str(exc).splitlines()[-1])
        return Result('THE RENDERER COMPOSES NO PROSE',
                      'build a pick sentence in app.js from the raw subject',
                      'audit.check_js_composes_no_prose', False,
                      'NOT CAUGHT - the renderer composed a sentence and passed')


def plant_a_class_name_mistaken_for_prose() -> Result:
    """The other half: the scan must NOT fire on a CSS class token.

    `el('span', 'tier ' + t.tier.toLowerCase(), t.tier)` lowercases a value
    to build a class name and passes the RAW server string as the text --
    the rule being followed, not broken. A tripwire that cries on eight
    good lines gets switched off, and then it is not a tripwire.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / 'app.js'
        copy.write_text(chr(10).join([
            'function tierChip(t) {',
            "  return el('span', 'tier ' + t.tier.toLowerCase(), t.tier);",
            '}',
        ]), encoding='utf-8')
        try:
            audit.check_js_composes_no_prose(copy)
        except audit.LawViolation as exc:
            return Result('THE RENDERER COMPOSES NO PROSE',
                          'a CSS class token must not be read as prose',
                          'audit.check_js_composes_no_prose', False,
                          'FALSE POSITIVE - ' + str(exc).splitlines()[-1])
        return Result('THE RENDERER COMPOSES NO PROSE',
                      'a CSS class token must not be read as prose',
                      'audit.check_js_composes_no_prose', True,
                      'a class name built from a value is not flagged')

def plant_a_shadowed_definition() -> Result:
    """Define a name twice and check the scan says which line wins.

    THE REAL ONE: `calibration.scorecard` and `calibration.version_comparison`
    each existed twice, the earlier of each pair being the pre-LAW-6 version
    that queried every sport at once. Python discarded them, so no runtime
    check could fire and the orphan scan saw the name as reached.
    """
    root = Path(audit.__file__).resolve().parent
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        pkg = Path(tmp) / "pkg"
        pkg.mkdir()
        (pkg / "twice.py").write_text(chr(10).join([
            "def scorecard(conn):",
            '    """The pre-LAW-6 one: no sport argument."""',
            "    return conn",
            "",
            "",
            "def scorecard(conn, *, sport):",
            '    """The live one."""',
            "    return sport",
            "",
        ]), encoding="utf-8")
        try:
            audit.check_no_shadowed_definitions(pkg)
        except audit.LawViolation as exc:
            named = "twice.py" in str(exc) and "scorecard" in str(exc)
            return Result("NO SHADOWED DEFINITIONS",
                          "define scorecard twice in one module",
                          "audit.check_no_shadowed_definitions", named,
                          str(exc).splitlines()[-1] if named else
                          "caught, but the message names neither file nor name")
        return Result("NO SHADOWED DEFINITIONS",
                      "define scorecard twice in one module",
                      "audit.check_no_shadowed_definitions", False,
                      "NOT CAUGHT - a name defined twice passed the scan")


def plant_a_composer_that_resolves_the_side_itself() -> Result:
    """Add a composer that reaches for `subject` instead of calling side_named.

    THE DEFECT THIS PREVENTS SHIPPED THREE TIMES: a chance label, a Why heading
    and a market clause, each naming the club the model was forecasting
    AGAINST. Each was fixed where it was found, which is exactly why it kept
    coming back -- three instances of one defect is a missing function, not
    three bugs.
    """
    root = Path(audit.__file__).resolve().parent
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / "language.py"
        text = (root / "language.py").read_text(encoding="utf-8")
        text += chr(10).join([
            "",
            "",
            "def headline_for_a_card(item):",
            '    """A planted composer that resolves the side on its own."""',
            '    who = item.get("subject")',
            '    return f"Why {who}"',
            "",
        ])
        copy.write_text(text, encoding="utf-8")
        try:
            audit.check_side_named(copy)
        except audit.LawViolation as exc:
            return Result("ONE DOOR FOR THE SIDE",
                          "resolve the side in a composer instead of side_named",
                          "audit.check_side_named", True, str(exc))
        return Result("ONE DOOR FOR THE SIDE",
                      "resolve the side in a composer instead of side_named",
                      "audit.check_side_named", False,
                      "NOT CAUGHT - a composer reached the raw subject and passed")


def plant_a_side_named_that_ignores_the_flip() -> Result:
    """The behaviour half: the door must NAME THE OTHER CLUB on a NO side.

    A door that exists and returns the subject anyway would pass the structural
    scan and reproduce the original defect exactly.
    """
    from gridiron import language as _lang

    item = {
        "subject": "ATL", "market_type": "moneyline", "model_side": "lose",
        "opponent": "COL", "model_prob": 0.53,
        "team_names": {"ATL": "Atlanta Braves", "COL": "Colorado Rockies"},
    }
    name, prob = _lang.side_named(item)
    yes_name, _ = _lang.side_named(dict(item, model_side="win", opponent="COL"))
    caught = name == "Colorado Rockies" and yes_name == "Atlanta Braves" and prob == 0.53
    return Result(
        "ONE DOOR FOR THE SIDE", "name the subject when the model took the other side",
        "language.side_named", caught,
        f"a NO-side moneyline names {name!r}, a YES-side names {yes_name!r}"
        if caught else
        f"NOT CAUGHT - NO side named {name!r} and YES side named {yes_name!r}",
    )


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


def plant_a_stake_column() -> Result:
    """Add a stake sizer to the package and check LAW 5's scan names it.

    Confidence tiers are the closest this project has come to the thing LAW 5
    forbids: they rank picks by how sure the model is, which is one short step
    from ranking them by how much to put on. The step is not taken, and this
    proves the guard would notice if it were.
    """
    root = Path(audit.__file__).resolve().parent
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / "gridiron"
        shutil.copytree(root, copy, ignore=shutil.ignore_patterns("__pycache__"))
        (copy / "web" / "stake.py").parent.mkdir(parents=True, exist_ok=True)
        (copy / "tiers_stake.py").write_text(
            chr(10).join([
                '"""A staking surface, planted."""',
                "",
                "",
                "def stake_for_tier(tier, bankroll):",
                "    units = {'LEAN': 0.5, 'SOLID': 1.0, 'STRONG': 2.0}[tier]",
                "    return bankroll * 0.01 * units",
            ]),
            encoding="utf-8",
        )
        try:
            audit.check_not_a_betting_tool(copy)
        except audit.LawViolation as exc:
            return Result("LAW 5", "add a stake column keyed on the tier",
                          "audit.check_not_a_betting_tool", True, str(exc))
        return Result("LAW 5", "add a stake column keyed on the tier",
                      "audit.check_not_a_betting_tool", False,
                      "NOT CAUGHT - a stake sizer passed the scan")


def plant_a_tier_hit_rate_below_the_gate() -> Result:
    """Ask a tier for its earned figure with nine settled picks behind it.

    This is the most persuasive lie the page could tell: a hit rate sitting
    directly beside a specific forecast, reading as a track record FOR that
    forecast, computed from a sample too small to mean anything.
    """
    from gridiron import calibration

    thin = calibration.tier_from_bucket(
        {"label": "70-80%", "n": 9, "actual": 0.889}
    )
    caught = (
        thin["earned"] is None
        and thin["proven"] is False
        and "%" not in thin["message"]
        # THE WORDING CHANGED ON 2026-09-03 (S3) AND THE PROPERTY DID NOT.
        # The line now names its own band -- "STRONG - 9 settled, not yet
        # proven; 20 needed..." -- so it survives being read away from the
        # chip. What this planting guards is unchanged: no rate below the
        # gate, and the shortfall stated in full.
        and "9 settled" in thin["message"]
        and "20 needed" in thin["message"]
        and "not yet proven" in thin["message"]
    )
    return Result(
        "LAW 4", "render a tier hit rate below its sample gate",
        "calibration.tier_from_bucket", caught,
        f"a thin tier states the shortfall and no rate: {thin['message']!r}"
        if caught else
        f"NOT CAUGHT - a 9-sample tier reported {thin.get('earned')!r}",
    )


def plant_a_tier_that_pools_two_buckets() -> Result:
    """STRONG covers 70-80% and 80%+. Pooling them into one hit rate would be
    the merge LAW 4 forbids, and it flatters: the easier bucket lifts the
    harder one."""
    from gridiron import calibration

    a = calibration.tier_from_bucket({"label": "70-80%", "n": 40, "actual": 0.60})
    b = calibration.tier_from_bucket({"label": "80%+", "n": 40, "actual": 0.90})
    caught = a["earned"] != b["earned"] and a["bucket"] != b["bucket"]
    return Result(
        "NO MERGED CURVES", "pool two buckets into one tier figure",
        "calibration.tier_from_bucket", caught,
        f"each bucket keeps its own number: {a['bucket']} {a['earned']} vs "
        f"{b['bucket']} {b['earned']}" if caught else
        "NOT CAUGHT - two buckets reported one pooled hit rate",
    )


def plant_an_unreadable_sample_size() -> Result:
    """Every foreground token measured against every ground it is drawn on.

    LAW 4 says a number never renders without its N. It does not say the N has
    to be legible, and for a while it was not: `--faint`, the token every
    sample size uses, sat at 3.23:1 on a card. An N nobody can read is an N
    that is not there.
    """
    import subprocess

    result = subprocess.run(
        [sys.executable, str(Path(audit.__file__).resolve().parent.parent
                             / "tools" / "contrast.py")],
        capture_output=True, text=True,
    )
    caught = result.returncode == 0
    worst = next(
        (line for line in result.stdout.splitlines() if line.startswith("worst pair")),
        "no worst pair reported",
    )
    return Result(
        "READABLE N", "check every text/ground pair against WCAG AA",
        "tools/contrast.py", caught,
        worst if caught else "NOT CAUGHT - " + result.stdout.strip()[-300:],
    )


def plant_snake_case_in_a_label() -> Result:
    """Put `rushing_yards` back in a visible label and check the scan names it.

    This is the exact string that was on the history page for months: the
    subject is STORED as "Saquon Barkley rushing_yards" because the subject has
    to be unique per question, and the table printed it verbatim. Nobody
    decided to show an identifier to a reader; it simply happened, which is why
    the law needs a scan rather than good intentions.
    """
    planted = chr(10).join(
        ["Saquon Barkley rushing_yards", "Market", "Market", "open"])
    hits = audit.plain_words_violations(planted)
    caught = any("rushing_yards" in h for h in hits)
    return Result(
        "PLAIN WORDS", "show an internal identifier in a label",
        "audit.plain_words_violations", caught,
        "; ".join(hits[:3]) if caught
        else "NOT CAUGHT - an identifier passed as readable text",
    )


def plant_an_undecodable_column_name() -> Result:
    """Field names as headings: `market_type`, `model_prob`, `line_asked`."""
    hits = audit.plain_words_violations(
        "market_type  model_prob  line_asked  factor_set_version"
    )
    caught = len(hits) >= 4
    return Result(
        "PLAIN WORDS", "name a column after a database field",
        "audit.plain_words_violations", caught,
        f"{len(hits)} field names caught" if caught
        else "NOT CAUGHT - database columns passed as headings",
    )


def plant_prose_that_is_not_an_identifier() -> Result:
    """The scan must NOT fire on English. A check that forces prose to get
    worse to satisfy it is worse than no check."""
    prose = ("Curves are never merged. The statistical and LLM predictors are "
             "scored separately, and each forecaster keeps its own record.")
    hits = audit.plain_words_violations(prose)
    return Result(
        "PLAIN WORDS", "check the scan does not fire on ordinary prose",
        "audit.plain_words_violations", not hits,
        "ordinary prose passes: 'predictor' and 'forecaster' are words, not "
        "identifiers" if not hits else f"FALSE POSITIVE - {hits}",
    )


LAW_RATE = "A COUNT IS A RATE"


def plant_a_count_market_scored_by_the_logistic() -> Result:
    """Fit a declared count market through an adapter that cannot supply counts.

    THIS IS A SILENT FAILURE I WROTE AND ALMOST SHIPPED. The first version of
    the capability check fell back to the logistic when an adapter could not
    return counts. Nothing raised and nothing was logged, so the market would
    have gone out scored by the exact path Session C measured as overconfident
    by 7.79 points of calibration gap -- while `COUNT_MARKETS` said it was a
    rate, and the card's "why" said so too.

    The plant is the shape that failure really takes: a NEW SPORT, or a market
    moved to a loader that was never taught the fourth return value. The
    adapter here is the real NFL one with `with_counts` taken off its
    signature, which is precisely what an untaught adapter looks like.

    A market declared as a rate and fitted as a logistic must be a BUILD ERROR.
    """
    import functools

    from gridiron import sports as sport_registry
    from gridiron.model import baseline, counts, logistic

    real_get = sport_registry.get

    def untaught(sport: str):
        adapter = real_get(sport)
        if sport != "nfl":
            return adapter

        class Untaught:
            """The NFL adapter, minus the ability to return counts."""

            def __getattr__(self, name):
                return getattr(adapter, name)

            @staticmethod
            def training_set(conn, seasons, market, *, through_season=None,
                             through_week=None, progress=None):
                return adapter.training_set(
                    conn, seasons, market, through_season=through_season,
                    through_week=through_week, progress=progress)

        return Untaught()

    conn = db.connect()
    fit = None
    try:
        sport_registry.get = untaught
        # `passing_tds` is a DECLARED count market, so this asks for a rate
        # from an adapter that cannot produce one.
        assert counts.is_count_market("passing_tds")
        try:
            fit = baseline.train(
                conn, "prop:passing_tds", config.SPORT_LOAD_SEASONS["nfl"],
                sport="nfl", note="planted")
        except baseline.NotTrained as exc:
            if "count market" not in str(exc):
                return Result(
                    LAW_RATE, "a count market scored by the logistic path",
                    "baseline.train count-capability refusal", False,
                    f"it refused, but for the wrong reason: {exc}")
            return Result(LAW_RATE, "a count market scored by the logistic path",
                          "baseline.train count-capability refusal", True,
                          str(exc))
        except Exception as exc:                       # noqa: BLE001
            return Result(LAW_RATE, "a count market scored by the logistic path",
                          "baseline.train count-capability refusal", False,
                          f"it failed, but not by name: "
                          f"{type(exc).__name__}: {exc}")
    finally:
        sport_registry.get = real_get
        conn.close()

    kind = type(fit).__name__
    if isinstance(fit, logistic.Fit):
        return Result(LAW_RATE, "a count market scored by the logistic path",
                      "baseline.train count-capability refusal", False,
                      "NOT CAUGHT - a market declared as a rate was fitted as a "
                      "logistic and said nothing; the card would have claimed a "
                      "rate the model never used")
    return Result(LAW_RATE, "a count market scored by the logistic path",
                  "baseline.train count-capability refusal", False,
                  f"NOT CAUGHT - the fit returned {kind} from an adapter that "
                  f"cannot supply counts")


def plant_a_rung_probability_that_rises_with_the_rung() -> Result:
    """Answer a higher rung more confidently than a lower one.

    CHECKLIST ITEM 4, and the one contradiction a card showing a single rung
    can never reveal. Clearing 2.5 home runs is strictly harder than clearing
    1.5 -- every game that does the first does the second -- so the ordering is
    a fact about counting, not an estimate.

    Planted against BOTH doors: the shared ladder assertion, and the rate
    model's own arithmetic, which is monotone by construction and is checked
    here rather than assumed.
    """
    from gridiron.sports import mlb
    from gridiron.model import counts

    # DOOR ONE: the declared-ladder guard, given a sequence that rises.
    rising = [(0.5, 0.42), (1.5, 0.47), (2.5, 0.61)]
    try:
        mlb.assert_monotone_across_rungs(rising, "a planted subject")
    except mlb.NonMonotoneLadder as exc:
        # DOOR TWO: prove the rate model cannot produce one. If p_over ever
        # rose with the rung the guard above would be catching a bug that the
        # model can actually commit, which is a different and worse situation.
        for form, dispersion in (("poisson", 1.0),
                                 ("negative_binomial", 1.282)):
            for rate in (0.11, 0.9, 1.45, 4.78):
                probs = [counts.p_over(rate, r, form=form, dispersion=dispersion)
                         for r in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)]
                if any(b > a + 1e-12 for a, b in zip(probs, probs[1:])):
                    return Result(
                        LAW_RATE, "a rung probability that rises with the rung",
                        "mlb.assert_monotone_across_rungs", False,
                        f"the guard fires, but the {form} rate model itself "
                        f"produced a rising sequence at rate={rate}: {probs}")
        honest = [(0.5, 0.61), (1.5, 0.47), (2.5, 0.42)]
        try:
            mlb.assert_monotone_across_rungs(honest, "a planted subject")
        except mlb.NonMonotoneLadder as wrong:
            return Result(LAW_RATE, "a rung probability that rises with the rung",
                          "mlb.assert_monotone_across_rungs", False,
                          f"the guard rejects an honest falling ladder: {wrong}")
        return Result(LAW_RATE, "a rung probability that rises with the rung",
                      "mlb.assert_monotone_across_rungs", True,
                      f"{exc}; and neither form can produce one -- p_over falls "
                      f"at every rung for both the Poisson and the negative "
                      f"binomial, because raising a rung only removes outcomes")
    return Result(LAW_RATE, "a rung probability that rises with the rung",
                  "mlb.assert_monotone_across_rungs", False,
                  "NOT CAUGHT - a model said 2.5 was easier to clear than 1.5")


LAW_ADJUSTED = "AN ADJUSTED RATING IS ADJUSTED"


def plant_an_adjusted_factor_that_reads_raw_margin() -> Result:
    """Feed the opponent adjustment a league where every club played the same.

    THE WHOLE CLAIM OF AN ADJUSTED RATING is that it differs from raw margin
    when the schedules differ. A factor that says "adjusted for who they
    played" and returns the raw differential is a LIE IN THE RATIONALE, not a
    weak signal, and it would be invisible: the numbers would look reasonable
    and rank the clubs plausibly.

    So the plant builds a league where the answer is known. Two clubs carry
    the SAME raw margin by construction, and one of them earned it against the
    strongest club in the league. Raw margin cannot tell them apart; an
    opponent adjustment must.
    """
    from gridiron.factors import context

    # A is the strongest club and D the weakest, established by two blowouts.
    # B then loses twice to A by five; C loses twice to D by five. B AND C
    # CARRY THE IDENTICAL RAW MARGIN of -5.0, and the only thing separating
    # them is WHO they lost to.
    rows = [
        {"team": "A", "opponent": "D", "points_for": 30, "points_against": 10},
        {"team": "D", "opponent": "A", "points_for": 10, "points_against": 30},
        {"team": "A", "opponent": "D", "points_for": 30, "points_against": 10},
        {"team": "D", "opponent": "A", "points_for": 10, "points_against": 30},
        {"team": "B", "opponent": "A", "points_for": 20, "points_against": 25},
        {"team": "A", "opponent": "B", "points_for": 25, "points_against": 20},
        {"team": "B", "opponent": "A", "points_for": 20, "points_against": 25},
        {"team": "A", "opponent": "B", "points_for": 25, "points_against": 20},
        {"team": "C", "opponent": "D", "points_for": 20, "points_against": 25},
        {"team": "D", "opponent": "C", "points_for": 25, "points_against": 20},
        {"team": "C", "opponent": "D", "points_for": 20, "points_against": 25},
        {"team": "D", "opponent": "C", "points_for": 25, "points_against": 20},
    ]
    ratings = context.srs_ratings(rows)
    if not ratings:
        return Result(LAW_ADJUSTED, "an adjusted factor that reads raw margin",
                      "context.srs_ratings", False,
                      "the rating system returned nothing for a whole league")

    raw = {}
    for r in rows:
        raw.setdefault(r["team"], []).append(r["points_for"] - r["points_against"])
    raw = {t: sum(v) / len(v) for t, v in raw.items()}

    if abs(raw["B"] - raw["C"]) > 1e-9:
        return Result(LAW_ADJUSTED, "an adjusted factor that reads raw margin",
                      "context.srs_ratings", False,
                      f"the planted league is wrong: B and C already differ on "
                      f"raw margin ({raw['B']} vs {raw['C']})")

    if ratings["B"] <= ratings["C"] + 1e-6:
        return Result(LAW_ADJUSTED, "an adjusted factor that reads raw margin",
                      "context.srs_ratings", False,
                      f"NOT CAUGHT - B lost twice to the strongest club and C "
                      f"lost twice to the weakest, both by five, and the "
                      f"adjustment rates them {ratings['B']:+.3f} and "
                      f"{ratings['C']:+.3f}. It adjusts for nothing, and the "
                      f"rationale's promise is false")
    return Result(LAW_ADJUSTED, "an adjusted factor that reads raw margin",
                  "context.srs_ratings", True,
                  f"B and C both average {raw['B']:+.1f} raw and the "
                  f"adjustment separates them: {ratings['B']:+.3f} against "
                  f"{ratings['C']:+.3f}, because B lost to the best club in the "
                  f"league and C lost to the worst")


def plant_a_suppressed_pair_read_as_two_reasons() -> Result:
    """Describe a jointly fitted pair as two reasons that disagree.

    MEASURED, NOT SUSPECTED. nba_srs_diff is worth +0.200 standardised alone
    and +0.536 with nba_net_rating_rolling beside it, which is -0.040 alone
    and -0.440 together. Both inflate and flip: the model is using their
    DIFFERENCE. A card that reads the two contributions separately tells a
    reader that "how the two clubs have been playing lately" is pulling
    AGAINST the pick. It is not. It is carrying half of a difference.

    A SENTENCE THAT IS ARITHMETICALLY DERIVED AND STILL FALSE is the worst
    kind this project can print, because it looks checked. This plants the
    unmerged reading and checks the merge is what stands between a reader
    and it.
    """
    from gridiron import language

    item = {
        "subject": "LAL", "market_type": "spread", "model_side": "cover",
        "model_prob": 0.62,
        "contributions": [
            {"factor": "nba_srs_diff", "value": 1.2, "contribution": 0.84},
            {"factor": "nba_net_rating_rolling", "value": 0.9,
             "contribution": -0.40},
            {"factor": "nba_rest_days_diff", "value": 1.0, "contribution": 0.14},
        ],
    }
    phrases = {
        "nba_srs_diff": "how good the two clubs have been, adjusted for who "
                        "they played",
        "nba_net_rating_rolling": "how the two clubs have been playing lately",
        "nba_rest_days_diff": "how much rest each club had",
    }
    groups = config.jointly_read("nba", "spread")
    if not groups:
        return Result(LAW_ADJUSTED, "a suppressed pair read as two reasons",
                      "config.JOINTLY_READ_FACTORS", False,
                      "the nba spread pair is not declared jointly read at all")

    # THE PLANT: the same contributions with no grouping, which is what the
    # card did before this was measured.
    unmerged = " ".join(language.why_sentences(item, phrases))
    merged = " ".join(language.why_sentences(item, phrases, groups))

    if "playing lately" not in unmerged or "other way" not in unmerged:
        return Result(LAW_ADJUSTED, "a suppressed pair read as two reasons",
                      "language.merge_jointly_read", False,
                      f"the planted reading did not produce the false sentence, "
                      f"so this proves nothing: {unmerged!r}")
    if "other way" in merged:
        return Result(LAW_ADJUSTED, "a suppressed pair read as two reasons",
                      "language.merge_jointly_read", False,
                      f"NOT CAUGHT - the pair still reads as two reasons that "
                      f"disagree: {merged!r}")
    for _names, phrase in groups:
        if phrase not in merged:
            return Result(LAW_ADJUSTED, "a suppressed pair read as two reasons",
                          "language.merge_jointly_read", False,
                          f"the pair was merged but its declared joint phrase "
                          f"is not what a reader sees: {merged!r}")
    # AND THE MERGE MUST NOT REACH BACKWARDS. A prediction written before the
    # adjusted factor existed carries only the raw one. Describing that row
    # with the joint phrase would tell a reader the model weighed "who they
    # played" when it had no such input -- rewriting what an old row knew,
    # which is the reading equivalent of editing it.
    old_row = dict(item, contributions=[
        {"factor": "nba_net_rating_rolling", "value": 0.9,
         "contribution": 0.44},
        {"factor": "nba_rest_days_diff", "value": 1.0, "contribution": 0.14},
    ])
    old_said = " ".join(language.why_sentences(old_row, phrases, groups))
    for _names, phrase in groups:
        if phrase in old_said:
            return Result(
                LAW_ADJUSTED, "a suppressed pair read as two reasons",
                "language.merge_jointly_read", False,
                f"a row written before the adjusted factor existed is being "
                f"described as though it had one: {old_said!r}")
    if "playing lately" not in old_said:
        return Result(
            LAW_ADJUSTED, "a suppressed pair read as two reasons",
            "language.merge_jointly_read", False,
            f"the older row lost its own reason entirely: {old_said!r}")

    return Result(LAW_ADJUSTED, "a suppressed pair read as two reasons",
                  "language.merge_jointly_read", True,
                  f"unmerged, the card said: {unmerged!r} -- which is false; "
                  f"merged it says: {merged!r}; and a row from before the pair "
                  f"existed keeps its own words: {old_said!r}")


def plant_both_form_factors_active_without_a_note() -> Result:
    """Leave a jointly-read factor active with nothing recorded beside it.

    D1's instruction was explicit: score the two against each other, and if
    they cannot be read apart, say so BY DATED NOTE -- never let both stand
    silently. A pair whose coefficients are uninterpretable and whose registry
    entries say nothing about it is exactly the silent case.
    """
    from gridiron.factors import registry
    import gridiron.factors.nba                              # noqa: F401

    by_name = {f.name: f for f in registry.all_factors()}
    total = 0
    for (sport, market), (names, _phrase) in config.JOINTLY_READ_FACTORS.items():
        for name in names:
            total += 1
            factor = by_name.get(name)
            if factor is None:
                return Result(
                    LAW_ADJUSTED, "both form factors active with no note",
                    "config.JOINTLY_READ_FACTORS names a real factor", False,
                    f"{sport} {market} is declared jointly read on {name!r}, "
                    f"which is not a declared factor")
            if not (factor.note or "").strip():
                return Result(
                    LAW_ADJUSTED, "both form factors active with no note",
                    "a jointly-read factor carries a dated note", False,
                    f"NOT CAUGHT - {name} is fitted as half of a difference "
                    f"and its registry entry says nothing about it; a reader "
                    f"of the factor list would take its coefficient at face "
                    f"value")
            if "2026-09-03" not in factor.note:
                return Result(
                    LAW_ADJUSTED, "both form factors active with no note",
                    "a jointly-read factor carries a dated note", False,
                    f"{name} has a note and it carries no date: a repair "
                    f"nobody can place in time is a repair nobody can check")
    return Result(LAW_ADJUSTED, "both form factors active with no note",
                  "a jointly-read factor carries a dated note", True,
                  f"all {total} jointly-read factors carry a dated note naming "
                  f"the measurement and the pair")


LAW_TIERS = "A TIER IS ITS OWN RECORD"


def plant_a_ufc_category_merged_across_tiers() -> Result:
    """Report one UFC distance curve covering every kind of card.

    LAW 6, ONE LEVEL DOWN (R2, 2026-09-03). Measured over 2,590 settled bouts:
    a Contender Series bout goes the distance 43.6% of the time, a Fight Night
    bout 55.3%, a numbered-card bout 58.0%. A single UFC distance curve
    averages a 43.6% population with a 58.0% one and describes neither -- and
    it FLATTERS, in the same direction and for the same reason the law was
    written about sports.

    The merge here is the shape it would really take: not a category labelled
    'all', but a category that simply forgets to say which tier it is.
    """
    merged = {
        "sport": "ufc",
        "categories": [
            {"sport": "ufc", "category": "distance / statistical",
             "market": "distance", "n": 260,
             "filters": {"predictor": "statistical", "prop_type": None}},
        ],
    }
    try:
        calibration.assert_no_merged_categories(merged)
    except calibration.MergedCurve as exc:
        # AND THE HONEST SHAPE MUST STILL PASS, or the guard is just refusing
        # everything and proves nothing.
        honest = {
            "sport": "ufc",
            "categories": [
                {"sport": "ufc", "category": "distance / contender / statistical",
                 "market": "distance", "event_tier": "contender", "n": 218,
                 "filters": {"predictor": "statistical", "prop_type": None}},
                {"sport": "ufc", "category": "distance / numbered / statistical",
                 "market": "distance", "event_tier": "numbered", "n": 753,
                 "filters": {"predictor": "statistical", "prop_type": None}},
            ],
        }
        try:
            calibration.assert_no_merged_categories(honest)
        except calibration.MergedCurve as wrong:
            return Result(LAW_TIERS, "a UFC category merged across tiers",
                          "calibration.assert_no_merged_categories", False,
                          f"the guard rejects two honest per-tier categories: "
                          f"{wrong}")
        # A TIER THAT IS NOT DECLARED IS ALSO A MERGE, because it means the
        # category is describing a population nobody defined.
        invented = {
            "sport": "ufc",
            "categories": [
                {"sport": "ufc", "category": "distance / prelims / statistical",
                 "market": "distance", "event_tier": "prelims", "n": 40,
                 "filters": {"predictor": "statistical", "prop_type": None}},
            ],
        }
        try:
            calibration.assert_no_merged_categories(invented)
        except calibration.MergedCurve:
            pass
        else:
            return Result(LAW_TIERS, "a UFC category merged across tiers",
                          "calibration.assert_no_merged_categories", False,
                          "an undeclared tier was accepted as a category")
        return Result(LAW_TIERS, "a UFC category merged across tiers",
                      "calibration.assert_no_merged_categories", True, str(exc))
    return Result(LAW_TIERS, "a UFC category merged across tiers",
                  "calibration.assert_no_merged_categories", False,
                  "NOT CAUGHT - one curve claimed to describe Contender Series "
                  "bouts at 43.6% and numbered-card bouts at 58.0% at once")


def plant_a_bout_from_another_promotion_in_the_ufc_pool() -> Result:
    """Feed the pool an event that is not a UFC card.

    R3 IS A LAW 6 RULING: PFL, Bellator and ONE are DIFFERENT SPORTS, not more
    UFC data. Different rulesets -- cage against ring, different round lengths,
    a season format in one of them -- so a rating pooled across promotions
    describes no promotion, and a fighter's rating would move on evidence from
    a sport this record does not model.

    The nearest thing to that failure already in the record is The Ultimate
    Fighter: entries carried under the UFC league whose bouts are not
    sanctioned UFC bouts. Seven of them WERE in the rating pool until today.
    This plants the same shape and checks the door is shut.
    """
    from gridiron.sports import ufc

    # A television episode carrying one bout, which is what TUF looks like.
    if ufc.is_sanctioned_card("The Ultimate Fighter 32 Semifinal: A vs. B", 1,
                              "2024-07-05T00:00:00Z", "2026-09-03T00:00:00Z"):
        return Result(LAW_TIERS, "a bout from outside the UFC entering the pool",
                      "ufc.is_sanctioned_card", False,
                      "NOT CAUGHT - a one-bout television episode was accepted "
                      "as a card, and its bouts would enter the rating pool")

    # AND A REAL CARD MUST STILL GET IN, or the guard is refusing everything.
    if not ufc.is_sanctioned_card("UFC Fight Night: Bonfim vs. Brady", 11,
                                  "2026-11-07T00:00:00Z",
                                  "2026-09-03T00:00:00Z"):
        return Result(LAW_TIERS, "a bout from outside the UFC entering the pool",
                      "ufc.is_sanctioned_card", False,
                      "a real Fight Night was refused")

    # THE CASE THAT COST ME EIGHTEEN BOUTS: an upcoming card whose bouts are
    # still being announced looks exactly like a thin one from the count alone.
    if not ufc.is_sanctioned_card("Dana White's Contender Series: Season 10, "
                                  "Week 10", 1, "2026-10-13T00:00:00Z",
                                  "2026-09-03T00:00:00Z"):
        return Result(LAW_TIERS, "a bout from outside the UFC entering the pool",
                      "ufc.is_sanctioned_card", False,
                      "an UPCOMING card with one bout announced so far was "
                      "refused as though it were television; this deleted 18 "
                      "real bouts once and must not again")

    # And a tier that does not exist has no label to print.
    from gridiron import config, language
    if "pfl" in config.event_tiers("ufc"):
        return Result(LAW_TIERS, "a bout from outside the UFC entering the pool",
                      "config.event_tiers", False,
                      "another promotion is declared as a UFC tier")
    if language.tier_label("pfl"):
        return Result(LAW_TIERS, "a bout from outside the UFC entering the pool",
                      "language.tier_label", False,
                      "an undeclared tier has a reader-facing label")
    return Result(LAW_TIERS, "a bout from outside the UFC entering the pool",
                  "ufc.is_sanctioned_card", True,
                  "a one-bout television episode is refused, a real card is "
                  "admitted, an UPCOMING card with one bout announced is "
                  "admitted, and no other promotion is a declared tier")


LAW_SCHEMA = "A FOREIGN KEY POINTS AT SOMETHING"


def plant_a_foreign_key_on_a_table_that_does_not_exist() -> Result:
    """Rename a referenced table aside and leave it there.

    THIS IS NOT HYPOTHETICAL. It happened, today, in this project, and nothing
    caught it for hours.

    Widening the sport CHECK on `games` renames the table aside, copies, and
    renames back. SQLite rewrites every referencing table's foreign key to
    FOLLOW the rename, and does not rewrite them back. Twelve tables holding
    311,655 rows were left pointing at `games_narrow`, which no longer existed.

    Every read kept working. The suite stayed green. Five sports rendered.
    `PRAGMA foreign_key_check` was reporting violations the whole time and
    nothing was asking it. It surfaced only when the UFC market fetcher became
    the first thing in a long while to INSERT into one of the twelve, as
    `no such table: main.games_narrow` raised from a module with nothing to do
    with games.

    So this plants the same rename and checks the scan now sees it.
    """
    from gridiron import audit as _audit

    with tempfile.TemporaryDirectory() as tmp:
        conn = db.open_db(Path(tmp) / "fk.db")
        clean = _audit.dangling_reference_faults(conn)
        if clean:
            conn.close()
            return Result(LAW_SCHEMA, "a foreign key on a table that is gone",
                          "audit.dangling_reference_faults", False,
                          f"a FRESH database already fails the scan, so it "
                          f"proves nothing: {clean[:2]}")

        # THE PLANT: exactly what the rebuild does, and exactly why a
        # rename-and-rename-back would NOT reproduce it -- SQLite repairs that
        # case, which is worth knowing and is why the first version of this
        # planting escaped. The damage comes from renaming aside, creating a
        # FRESH table under the original name, and dropping the aside one: the
        # referencing tables followed the rename and there is nothing left to
        # follow back.
        conn.execute("PRAGMA foreign_keys = OFF")
        original = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'games'").fetchone()[0]
        conn.execute("ALTER TABLE games RENAME TO games_narrow")
        conn.execute(original)
        conn.execute("DROP TABLE games_narrow")
        conn.commit()
        faults = _audit.dangling_reference_faults(conn)
        conn.close()

    if not faults:
        return Result(LAW_SCHEMA, "a foreign key on a table that is gone",
                      "audit.dangling_reference_faults", False,
                      "NOT CAUGHT - a table's foreign key names a table that "
                      "does not exist, every read still works, and the first "
                      "INSERT will fail with an error naming a module that has "
                      "nothing to do with it")
    return Result(LAW_SCHEMA, "a foreign key on a table that is gone",
                  "audit.dangling_reference_faults", True,
                  f"{len(faults)} fault(s), the first being: {faults[0]}")


def plant_the_ufc_fetcher_inside_a_prediction_closure() -> Result:
    """LAW 1: reach the UFC odds fetcher from the UFC adapter itself.

    THE NEAREST MISS IN THE PROJECT. `gridiron.market.ufc` and
    `gridiron.sports.ufc` describe the same bouts, are named the same thing,
    and the adapter already imports plenty. An import written by muscle memory
    -- or by an editor's auto-import, which does not read laws -- would put a
    live odds request inside the path that computes the probability, and the
    forecast would no longer be blind.

    IT WOULD ALSO BE INVISIBLE. The numbers would still look like forecasts.
    Calibration would improve, because the model would be partly reading the
    market, and that improvement would be indistinguishable from progress --
    which is the exact failure LAW 1 exists to make structurally impossible
    rather than merely forbidden.

    Planted on the UFC adapter specifically, because a general market import is
    already planted elsewhere and this is the one a person would actually write.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gridiron"
        shutil.copytree(config.PACKAGE_ROOT, root)
        victim = root / "sports" / "ufc.py"
        victim.write_text(
            victim.read_text(encoding="utf-8")
            + "\n\n# PLANTED VIOLATION\nfrom ..market import ufc as odds  # noqa\n",
            encoding="utf-8",
        )
        try:
            # EVERY SPORT IS ITS OWN ROOT, and the first version of this
            # planting used the shared one -- so it walked
            # `gridiron.model.predict`, never reached the UFC adapter, and
            # escaped. That escape is itself worth recording: a closure scan
            # is only as wide as the entrypoints it is given, and a sport
            # missing from `prediction_entrypoints` would be unaudited while
            # every other row said PASS.
            audit.check_all_prediction_closures(root=root)
        except audit.LawViolation as exc:
            if "sports.ufc" not in str(exc):
                return Result(
                    "LAW 1", "import the UFC odds fetcher from the UFC adapter",
                    "audit.check_all_prediction_closures", False,
                    f"a violation was raised, but not for the UFC adapter: "
                    f"{exc}")
            return Result("LAW 1",
                          "import the UFC odds fetcher from the UFC adapter",
                          "audit.check_all_prediction_closures", True, str(exc))
    return Result("LAW 1", "import the UFC odds fetcher from the UFC adapter",
                  "audit.check_all_prediction_closures", False,
                  "NOT CAUGHT - the UFC prediction path can reach the module "
                  "that fetches UFC prices, so a forecast could read the line "
                  "it is supposed to be blind to")


LAW_WORDS = "EVERY MARKET CLAIMS ITS OWN WORDS"


def plant_a_market_wearing_another_markets_verb() -> Result:
    """Ask the prose layer about a market that never declared its words.

    THIS HAS HAPPENED FOUR TIMES, in the same shape each time, and only the
    fourth is what finally made it structural.

      - every prop read "goes over" whichever side the model took
      - every spread read "covers" whichever side the model took (34 cards
        stated the opposite of the forecast beside them, at high confidence)
      - a UFC rounds question read "Nathaniel Wood vs Pavel Andrusca covers"
      - a UFC distance question did the same

    Each was fixed by adding a branch. None of them was fixed by removing the
    reason a next one was possible: the last line of `chance_clause` was the
    SPREAD branch, so any market nobody had thought about silently inherited
    the spread's verb and the spread's grammar.

    The last line now REFUSES. This plants a market that has declared nothing
    and checks it gets nothing, and it checks the five real markets still
    speak, because a refusal that refuses everything proves nothing.
    """
    from gridiron import language as _lang

    planted = {"market_type": "parlay", "model_side": "yes",
               "subject": "Somebody", "model_prob": 0.61,
               "home": "A", "away": "B"}
    try:
        said = _lang.chance_clause(planted)
    except _lang.NoWordsForThisMarket as exc:
        real = [
            ({"market_type": "spread", "model_side": "cover", "subject": "SF",
              "model_prob": 0.6, "home": "SF", "away": "LA"}, "covers"),
            ({"market_type": "moneyline", "model_side": "win", "subject": "SF",
              "model_prob": 0.6, "home": "SF", "away": "LA"}, "wins"),
            ({"market_type": "total", "model_side": "over", "subject": "SF",
              "model_prob": 0.6, "home": "SF", "away": "LA"}, "over"),
            ({"market_type": "rounds", "model_side": "over",
              "subject": "A vs B", "model_prob": 0.6}, "over"),
            ({"market_type": "distance", "model_side": "yes",
              "subject": "A vs B", "model_prob": 0.6}, "distance"),
        ]
        for item, expected in real:
            try:
                words = _lang.chance_clause(item)
            except _lang.NoWordsForThisMarket as wrong:
                return Result(
                    LAW_WORDS, "a market wearing another market's verb",
                    "language.chance_clause", False,
                    f"a declared market was refused its own words: {wrong}")
            if expected not in words:
                return Result(
                    LAW_WORDS, "a market wearing another market's verb",
                    "language.chance_clause", False,
                    f"{item['market_type']} says {words!r}, which does not "
                    f"contain {expected!r}")
            if item["market_type"] in ("rounds", "distance") and "cover" in words:
                return Result(
                    LAW_WORDS, "a market wearing another market's verb",
                    "language.chance_clause", False,
                    f"a fight market still says {words!r} -- a bout does not "
                    f"cover anything")
        return Result(LAW_WORDS, "a market wearing another market's verb",
                      "language.chance_clause", True,
                      f"{exc}; and all five declared markets still speak in "
                      f"their own words")
    return Result(LAW_WORDS, "a market wearing another market's verb",
                  "language.chance_clause", False,
                  f"NOT CAUGHT - an undeclared market was handed a sentence "
                  f"anyway: {said!r}")


LAW_ONE_SIDE = "ONE CARD NAMES ONE SIDE"


def plant_two_sentences_naming_opposite_sides() -> Result:
    """Let the pick sentence and the chance clause disagree about the side.

    THIS WAS LIVE ON 68 OF 321 CARDS and had been for some time.

    `side_named` flips the name when the model takes the NO side: a spread
    stored on LV at -7.5 whose `model_side` is `not_cover` resolves to "Miami",
    because backing Las Vegas not to cover -7.5 IS backing Miami +7.5.
    `chance_clause` then negated the VERB as well, so one card carried

        pick:   "Miami covers +7.5"
        chance: "Miami does not cover"

    -- two sentences, four lines apart, making opposite claims, with the
    percentage attached to the wrong one.

    HOW IT SURVIVED EVERY EXISTING GUARD, which is the part worth keeping.
    "One door for the side" passed, because both functions asked `side_named`
    and got the same NAME. "The side, in prose, anywhere" passed, because both
    sentences were grammatical and each was individually plausible. The two
    fixes that combined to cause it were each correct alone and arrived
    sessions apart: the subject flip, so a moneyline names the club actually
    being backed, and the verb negation, after the renderer's hardcoded verb
    table put "WAS covers" on 34 cards that said the opposite.

    So this guard does not check either sentence. It checks that the two
    AGREE -- which is the only thing neither of them could be asked alone.
    """
    conn = db.connect()
    try:
        disagreeing, checked = _side_disagreements(conn)
    finally:
        conn.close()

    if disagreeing:
        first = disagreeing[0]
        return Result(LAW_ONE_SIDE, "two sentences naming opposite sides",
                      "language.phrase agrees with language.chance_clause",
                      False,
                      f"NOT CAUGHT - {len(disagreeing)} of {checked} live cards "
                      f"carry a pick sentence and a chance clause that name "
                      f"opposite sides. The first is {first}")

    # AND THE CHECK MUST BE ABLE TO FAIL. A guard that passes because it
    # examines nothing is the shape this project has been bitten by before, so
    # the planted card is run through the same comparison.
    planted = {
        "market_type": "spread", "model_side": "not_cover", "subject": "LV",
        "line_asked": -7.5, "model_prob": 0.73,
        "opponent": "MIA",
        "team_names": {"LV": {"city": "Las Vegas"}, "MIA": {"city": "Miami"}},
    }
    from gridiron import language as _language

    said = _language.phrase(planted)
    # THE PLANT: the verb negated on top of the already-flipped subject, which
    # is exactly what the shipped function did.
    subject, _p = _language.side_named(planted, form="city")
    broken = f"{subject} does not cover"
    if _side_words_agree(said, broken):
        return Result(LAW_ONE_SIDE, "two sentences naming opposite sides",
                      "language.phrase agrees with language.chance_clause",
                      False,
                      f"the comparison cannot tell {said!r} from {broken!r}, "
                      f"so it would pass whatever the code did")
    if not _side_words_agree(said, _language.chance_clause(planted)):
        return Result(LAW_ONE_SIDE, "two sentences naming opposite sides",
                      "language.phrase agrees with language.chance_clause",
                      False,
                      f"the shipped pair still disagrees on the planted card: "
                      f"{said!r} against {_language.chance_clause(planted)!r}")
    return Result(LAW_ONE_SIDE, "two sentences naming opposite sides",
                  "language.phrase agrees with language.chance_clause", True,
                  f"{checked} live cards agree; and the double-flip form "
                  f"{broken!r} is still detected as disagreeing with "
                  f"{said!r}, so the comparison can fail")


def _side_words_agree(pick: str, chance: str) -> bool:
    """Do these two sentences claim the same side?

    ON THE WORDS, not on a flag. A flag would be the same thing both sentences
    were derived from, and a comparison against a shared source cannot catch a
    disagreement between the two things derived from it.
    """
    def negative(text: str) -> bool:
        return bool(re.search(
            r"\bdoes not\b|\bunder\b|\bends early\b|\bto lose\b",
            (text or "").lower()))
    return negative(pick) == negative(chance)


def _side_disagreements(conn):
    """Every live card whose two sentences name opposite sides."""
    from gridiron import views

    out, checked = [], 0
    for sport in config.SPORTS:
        try:
            week = views.week(conn, sport)
        except Exception:                                    # noqa: BLE001
            continue
        for card in (week.get("cards") or []):
            pick, chance = card.get("phrase"), card.get("chance_clause")
            if not pick or not chance:
                continue
            checked += 1
            if not _side_words_agree(pick, chance):
                out.append(f"{sport} {card.get('row_title')!r}: "
                           f"{pick!r} against {chance!r}")
    return out, checked


LAW_CARDS = "THE CARD SHOWS ONE NUMBER, AND THE TABS ARE DERIVED"


def plant_a_market_tab_row_that_is_hardcoded() -> Result:
    """Write the market tabs into the renderer instead of deriving them.

    R4 IS EXPLICIT: "Tabs come from the sport's declared market list -- never a
    hardcoded row (a fifth market must appear without a UI change)."

    A HARDCODED ROW IS RIGHT ON THE DAY IT IS WRITTEN, which is what makes it
    dangerous. It goes wrong silently, later, when somebody declares a market
    and it simply does not appear -- and the sport's own tab strip, the most
    visible thing on the page, quietly stops describing the sport. UFC declared
    three markets in one session and the count markets moved five more; on this
    project's own pace that is a matter of weeks.

    So the guard reads the RENDERER for a written-out list of market names, and
    the payload builder for a list that is not `config.SPORT_MARKETS`.
    """
    from gridiron import views as _views

    web = config.PACKAGE_ROOT / "web"
    js = (web / "app.js").read_text(encoding="utf-8")

    # THE PLANT: the row a person would write by hand.
    hardcoded = ("const tabs = [{market: '', label: 'All'},"
                 " {market: 'spread', label: 'Point spread'},"
                 " {market: 'moneyline', label: 'Moneyline'},"
                 " {market: 'total', label: 'Total'}];")
    faults = _tab_row_faults(hardcoded)
    if not faults:
        return Result(LAW_CARDS, "a market tab row written into the renderer",
                      "the tabs are derived from config.SPORT_MARKETS", False,
                      "the scan does not notice a hardcoded row, so it would "
                      "pass whatever the renderer did")
    if _tab_row_faults(js):
        return Result(LAW_CARDS, "a market tab row written into the renderer",
                      "the tabs are derived from config.SPORT_MARKETS", False,
                      f"the scan fires on the shipped renderer: "
                      f"{_tab_row_faults(js)[0]}")

    # AND THE REAL TABS MUST TRACK THE DECLARATION. Asserted against the
    # config rather than against a remembered list, which is the only way to
    # tell a derived row from a hardcoded one that happens to be right today.
    conn = db.connect()
    try:
        for sport in config.SPORTS:
            try:
                tabs = _views._market_tabs(sport, [])
            except Exception as exc:                         # noqa: BLE001
                return Result(
                    LAW_CARDS, "a market tab row written into the renderer",
                    "views._market_tabs", False,
                    f"the tabs for {sport} could not be built: {exc}")
            markets = [t["market"] for t in tabs][1:]
            if markets != list(config.SPORT_MARKETS.get(sport, ())):
                return Result(
                    LAW_CARDS, "a market tab row written into the renderer",
                    "views._market_tabs", False,
                    f"{sport}'s tabs are {markets} and its declared markets "
                    f"are {list(config.SPORT_MARKETS.get(sport, ()))}")
    finally:
        conn.close()
    return Result(LAW_CARDS, "a market tab row written into the renderer",
                  "views._market_tabs", True,
                  f"a written-out row is caught ({faults[0]}); and every "
                  f"sport's real tabs equal its declared market list")


def _tab_row_faults(js: str) -> list[str]:
    """A list of market names written into the renderer rather than derived."""
    written = re.findall(r"label:\s*'([^']+)'", js)
    known = {"All", "Point spread", "Moneyline", "Total", "Run line",
             "Rounds", "Distance", "Spread"}
    hits = [w for w in written if w in known]
    if len(hits) >= 2:
        return [f"the renderer writes market labels itself: {hits[:4]}. They "
                f"come from the sport's declared list, so a fifth market "
                f"appears without a change to any file in web/."]
    return []


def plant_a_card_showing_two_numbers_collapsed() -> Result:
    """Put the market's percentage beside the model's on a collapsed card.

    R2: one number per card. The market's figure and the three sentences of
    reasoning are ONE TAP AWAY.

    TWO PERCENTAGES ON ONE CARD MAKE A READER DO ARITHMETIC to work out which
    one is the claim -- and the one they are most likely to read is whichever
    is larger, which has nothing to do with which is the forecast. The whole
    point of the redesign is that a card asserts one thing.

    Planted against the stylesheet, because that is where the hint's
    concealment lives: the market hint IS in the markup by design (the brief
    asks for a hover reveal), and what keeps the card honest at rest is that it
    is at zero opacity until the reader asks.
    """
    web = config.PACKAGE_ROOT / "web"
    css = (web / "style.css").read_text(encoding="utf-8")

    shipped = _hint_faults(css)
    if shipped:
        return Result(LAW_CARDS, "a card showing two numbers collapsed",
                      "the market hint is hidden until asked for", False,
                      f"the shipped stylesheet already shows both: {shipped[0]}")

    # THE PLANT: the hint revealed at rest.
    broken = css.replace("  margin-top: 8px; opacity: 0;",
                         "  margin-top: 8px; opacity: 1;", 1)
    if broken == css:
        return Result(LAW_CARDS, "a card showing two numbers collapsed",
                      "the market hint is hidden until asked for", False,
                      "the hint's resting opacity is no longer written the way "
                      "this planting expects; re-point it")
    faults = _hint_faults(broken)
    if not faults:
        return Result(LAW_CARDS, "a card showing two numbers collapsed",
                      "the market hint is hidden until asked for", False,
                      "NOT CAUGHT - the market's percentage sits beside the "
                      "model's on a card nobody has opened, and a reader has "
                      "to work out which of the two is the forecast")
    return Result(LAW_CARDS, "a card showing two numbers collapsed",
                  "the market hint is hidden until asked for", True, faults[0])


def _hint_faults(css: str) -> list[str]:
    """Is the market hint visible on a card at rest?"""
    match = re.search(r"\.card-hint\s*\{(?P<body>[^}]*)\}", css)
    if match is None:
        return ["`.card-hint` has no rule at all, so the market's percentage "
                "renders at full strength beside the model's."]
    body = match.group("body")
    if "opacity: 0" not in body:
        return ["`.card-hint` does not start hidden, so a collapsed card shows "
                "the market's percentage beside the model's and a reader has "
                "to work out which one is the claim."]
    return []


LAW_TWO_MARKETS = "TWO MARKETS, ONE GAME, ONE WORLD"


def plant_a_moneyline_that_contradicts_its_own_spread() -> Result:
    """Make a home favourite likelier to cover than to win.

    THE RELATION IS LOGICAL, NOT STATISTICAL. Writing the margin as M:

        P(home wins)   = P(M > 0)
        P(home covers) = P(M + rung > 0) = P(M > -rung)

    A home club GIVING points -- a negative rung -- covers only in games it
    also wins, so it cannot be likelier to cover than to win. A club RECEIVING
    points wins only in games it also covers, so it cannot be less likely. A
    model that breaks either is contradicting itself rather than being slightly
    off, and the contradiction is invisible on a card showing one market at a
    time -- which, after the cards UI, is every card.

    THIS IS THE SHAPE THAT CAUGHT THE ESPN SIGN ERROR: a stored spread whose
    direction its own favourite flag denied. The second number is what makes
    the first checkable.
    """
    from gridiron.sports import nba as _nba

    # A home favourite at -6.5 that is likelier to cover than to win.
    try:
        _nba.assert_markets_agree(0.62, 0.74, -6.5, "a planted game")
    except _nba.DisagreesWithTheSpread as giving:
        # And the mirror: a home underdog at +6.5 less likely to cover.
        try:
            _nba.assert_markets_agree(0.41, 0.30, 6.5, "a planted game")
        except _nba.DisagreesWithTheSpread:
            pass
        else:
            return Result(
                LAW_TWO_MARKETS, "a moneyline contradicting its own spread",
                "nba.assert_markets_agree", False,
                "the guard catches a favourite covering too often but not an "
                "underdog covering too rarely; half a relation is not one")

        # AND THE HONEST ORDERING MUST PASS, or the guard is refusing
        # everything and proves nothing.
        for win_p, cover_p, rung in ((0.74, 0.62, -6.5), (0.41, 0.55, 6.5),
                                     (0.62, 0.60, -1.5), (0.50, 0.50, -0.5)):
            try:
                _nba.assert_markets_agree(win_p, cover_p, rung, "an honest game")
            except _nba.DisagreesWithTheSpread as wrong:
                return Result(
                    LAW_TWO_MARKETS, "a moneyline contradicting its own spread",
                    "nba.assert_markets_agree", False,
                    f"the guard rejects an honest ordering "
                    f"(win {win_p}, cover {cover_p}, rung {rung}): {wrong}")
        return Result(LAW_TWO_MARKETS,
                      "a moneyline contradicting its own spread",
                      "nba.assert_markets_agree", True, str(giving))
    return Result(LAW_TWO_MARKETS, "a moneyline contradicting its own spread",
                  "nba.assert_markets_agree", False,
                  "NOT CAUGHT - a home club giving six and a half points is "
                  "rated likelier to cover than to win, which no game can do")


def plant_a_moneyline_asked_with_a_rung() -> Result:
    """Give the moneyline question a line, and the asked-line factor with it.

    A MONEYLINE HAS NO RUNG. `nba_asked_distance` measures how far the rung
    sits from the model's own expectation, and there is no rung to be a
    distance from -- so the factor is declared for the spread and not for the
    moneyline, and the question carries `line_asked=None`.

    THE WAY THIS GOES WRONG IS BY COPYING. The moneyline's question, features
    and training set were each written next to the spread's, and the spread's
    carry a line everywhere. A line that reached the moneyline would put a
    number on a context no moneyline factor is declared to read -- and worse,
    would make the factor set differ from the one its rationale describes.
    """
    from gridiron.factors import registry
    from gridiron.sports import nba as _nba
    import gridiron.factors.nba                              # noqa: F401

    money = {f.name for f in registry.active_factors("nba", "moneyline")}
    spread = {f.name for f in registry.active_factors("nba", "spread")}
    if "nba_asked_distance" in money:
        return Result(LAW_TWO_MARKETS, "a moneyline asked with a rung",
                      "the moneyline's declared factor set", False,
                      "NOT CAUGHT - `nba_asked_distance` applies to the "
                      "moneyline, which has no asked line for it to measure a "
                      "distance from")
    if "nba_asked_distance" not in spread:
        return Result(LAW_TWO_MARKETS, "a moneyline asked with a rung",
                      "the moneyline's declared factor set", False,
                      "`nba_asked_distance` has left the SPREAD as well, so "
                      "this proves nothing about the moneyline")
    if not money or not (money < spread):
        return Result(LAW_TWO_MARKETS, "a moneyline asked with a rung",
                      "the moneyline's declared factor set", False,
                      f"the moneyline's factors are not a strict subset of the "
                      f"spread's: only in moneyline {sorted(money - spread)}")

    # AND THE QUESTION ITSELF CARRIES NO LINE.
    conn = db.connect()
    try:
        game = conn.execute(
            "SELECT id, home, away FROM games WHERE sport = 'nba' LIMIT 1"
        ).fetchone()
        if game is None:
            return Result(LAW_TWO_MARKETS, "a moneyline asked with a rung",
                          "the moneyline question carries no line", False,
                          "no NBA game stored to build a question from")
        question = _nba._moneyline_question(game)
    finally:
        conn.close()
    if question.line_asked is not None:
        return Result(LAW_TWO_MARKETS, "a moneyline asked with a rung",
                      "the moneyline question carries no line", False,
                      f"NOT CAUGHT - the moneyline question was built with "
                      f"line_asked={question.line_asked!r}")
    return Result(LAW_TWO_MARKETS, "a moneyline asked with a rung",
                  "the moneyline's declared factor set", True,
                  f"the moneyline declares {len(money)} factors and the spread "
                  f"{len(spread)}; the one difference is `nba_asked_distance`, "
                  f"and the question carries no line at all")


LAW_TOTALS = "A TOTAL IS A SUM, NOT A DIFFERENCE"


def plant_a_total_factor_that_takes_a_difference() -> Result:
    """Declare a directional factor on a market where neither side is named.

    A SPREAD ASKS WHICH CLUB IS BETTER; A TOTAL ASKS HOW MUCH BASKETBALL
    HAPPENS. The first takes differences, the second takes sums, and a
    difference on a total is a question about one club in a market that names
    neither.

    IT WOULD LOOK FINE. Two clubs each missing three starters have an
    availability DIFFERENCE of zero and a combined score well below normal; a
    total model reading the difference sees an ordinary game. The coefficient
    would come back near zero, be read as "availability does not affect
    scoring", and the real effect would never have been measured. That is
    worse than a wrong answer -- it is a wrong answer that looks like evidence.

    The same reasoning declared `ufc_finish_rate_sum` beside
    `ufc_finish_rate_diff` one sport over.
    """
    from gridiron.factors import registry
    import gridiron.factors.nba                              # noqa: F401

    total = {f.name for f in registry.active_factors("nba", "total")}
    if not total:
        return Result(LAW_TOTALS, "a directional factor on a totals market",
                      "the total's declared factor set", False,
                      "the nba total declares no factors at all")

    # THE PLANT: the directional factors, named. None may be here.
    directional = {"nba_availability_index", "nba_rest_days_diff",
                   "nba_travel_recent", "nba_net_rating_rolling",
                   "nba_srs_diff", "nba_home_court", "nba_asked_distance"}
    trespassers = sorted(total & directional)
    if trespassers:
        return Result(LAW_TOTALS, "a directional factor on a totals market",
                      "the total's declared factor set", False,
                      f"NOT CAUGHT - {trespassers} are declared for the nba "
                      f"total. Each is a home-minus-away difference, and a "
                      f"total names neither side.")

    # AND THE SUMS MUST ACTUALLY BE THERE, or this passes by the market being
    # empty rather than by it being right.
    for wanted in ("nba_availability_sum", "nba_total_volatility",
                   "nba_total_asked_distance"):
        if wanted not in total:
            return Result(LAW_TOTALS, "a directional factor on a totals market",
                          "the total's declared factor set", False,
                          f"{wanted} is not declared for the total, so the "
                          f"market is missing the instrument that replaces the "
                          f"directional one")

    # AND THE SPREAD MUST STILL HAVE ITS OWN. A guard that empties both markets
    # would pass this and mean nothing.
    spread = {f.name for f in registry.active_factors("nba", "spread")}
    if not (directional & spread):
        return Result(LAW_TOTALS, "a directional factor on a totals market",
                      "the total's declared factor set", False,
                      "the SPREAD has lost its directional factors too, so "
                      "this proves nothing about the total")
    return Result(LAW_TOTALS, "a directional factor on a totals market",
                  "the total's declared factor set", True,
                  f"the nba total declares {len(total)} factors and none of "
                  f"the {len(directional)} directional ones; it takes sums "
                  f"({sorted(total)}) while the spread keeps its differences")


def plant_a_total_rung_that_can_push() -> Result:
    """Ask a total at a whole number, where the score can land exactly on it.

    A PUSHED QUESTION HAS NO ANSWER TO SCORE. Every rung on the declared ladder
    is a half-point, so a combined score is strictly above or strictly below
    it and the question always resolves -- which is the whole appeal of a
    market that needs no player, no lineup and no crosswalk.

    A whole-number rung would void on exact landings, and totals land on round
    numbers more often than a uniform guess suggests: 220 and 230 are common
    scores. A market whose selling point is that it always resolves, quietly
    voiding a few times a season, is the kind of erosion nobody notices.
    """
    from gridiron.model import questions as _questions

    ladder = _questions.NBA_TOTAL_LADDER
    whole = [r for r in ladder if float(r).is_integer()]
    if whole:
        return Result(LAW_TOTALS, "a total rung that can push",
                      "every NBA_TOTAL_LADDER rung is a half", False,
                      f"NOT CAUGHT - these rungs are whole numbers and can be "
                      f"landed on exactly: {whole}")

    # AND THE CHOOSER MUST NEVER RETURN ONE. It picks from the ladder, so this
    # checks the ladder is what it picks from rather than a rounding of its own.
    for expected in (185.0, 199.4, 229.0, 229.5, 230.0, 260.2, 278.0):
        rung = _questions.nba_total_asked(expected)
        if rung is None:
            continue
        if rung not in ladder:
            return Result(LAW_TOTALS, "a total rung that can push",
                          "nba_total_asked picks from the declared ladder",
                          False,
                          f"an expectation of {expected} produced {rung}, "
                          f"which is not on the declared ladder")
    # And outside the band it refuses rather than clamping.
    for outside in (184.9, 278.1, 0.0, 400.0):
        if _questions.nba_total_asked(outside) is not None:
            return Result(LAW_TOTALS, "a total rung that can push",
                          "nba_total_asked refuses outside the band", False,
                          f"an expectation of {outside} was clamped onto the "
                          f"ladder rather than refused")
    return Result(LAW_TOTALS, "a total rung that can push",
                  "every NBA_TOTAL_LADDER rung is a half", True,
                  f"all {len(ladder)} declared rungs are halves, the chooser "
                  f"only ever returns one of them, and an expectation outside "
                  f"the measured band is refused rather than clamped")


LAW_CAP = "A NEW MARKET DOES NOT ADD QUESTIONS"


def plant_a_market_declared_but_never_asked() -> Result:
    """Declare a market in one place and ask it in another.

    THIS HAPPENED, TODAY, TWICE IN ONE MARKET. `batter_strikeouts` was added to
    `SPORT_MARKETS` and the slate kept producing none, because the day's props
    are filled by round-robin over `SPORT_PROP_MARKETS` -- a SEPARATE tuple --
    and the batting loop in the adapter listed its three markets by hand. A
    market declared in the config and absent from either of those exists
    everywhere except on a slate.

    NOTHING FAILS WHEN THIS HAPPENS. The market has a category, a gate, a
    fitted model and a ladder; it simply never gets a question, and the only
    symptom is a scorecard row that stays at zero forever -- which looks
    exactly like a market nobody has settled yet.
    """
    from gridiron.sports import mlb as _mlb

    # Every declared MLB prop market must be reachable by the day's selection.
    missing = [m for m in config.SPORT_MARKETS["mlb"]
               if m in config.SPORT_PROP_MARKETS["mlb"]
               and m not in config.MLB_PROP_MARKETS]
    if missing:
        return Result(LAW_CAP, "a market declared but never asked",
                      "config.MLB_PROP_MARKETS covers the declared props",
                      False,
                      f"NOT CAUGHT - {missing} are declared markets that the "
                      f"day's prop selection never walks")

    # And every one must have the words and the ladder a question needs.
    for market in config.MLB_PROP_MARKETS:
        if market not in _mlb.PROP_WORDS:
            return Result(LAW_CAP, "a market declared but never asked",
                          "mlb.PROP_WORDS covers the declared props", False,
                          f"NOT CAUGHT - {market} has no plain words, so "
                          f"building its question raises rather than asking it")
        if market not in config.MLB_PROP_LADDER:
            return Result(LAW_CAP, "a market declared but never asked",
                          "config.MLB_PROP_LADDER covers the declared props",
                          False,
                          f"NOT CAUGHT - {market} has no declared ladder")

    # THE PLANT: a market in the declared list that the selection cannot reach.
    real = config.MLB_PROP_MARKETS
    try:
        config.MLB_PROP_MARKETS = tuple(
            m for m in real if m != "batter_strikeouts")
        still_missing = [m for m in config.SPORT_PROP_MARKETS["mlb"]
                         if m not in config.MLB_PROP_MARKETS]
    finally:
        config.MLB_PROP_MARKETS = real
    if not still_missing:
        return Result(LAW_CAP, "a market declared but never asked",
                      "config.MLB_PROP_MARKETS covers the declared props",
                      False,
                      "the planted omission was not detectable, so this check "
                      "would pass whatever the config said")
    return Result(LAW_CAP, "a market declared but never asked",
                  "config.MLB_PROP_MARKETS covers the declared props", True,
                  f"a market removed from the selection list is detected "
                  f"({still_missing}); and all {len(real)} declared props have "
                  f"words, a ladder and a place in the round-robin")


def plant_a_rung_that_inherits_its_base_rate() -> Result:
    """Declare a rung the answer is almost always the same on.

    THE ROSTER'S OWN SECTION 4(a). A question that lands one way 98.7% of the
    time produces volume and no information: a model answering "no"
    unconditionally would look calibrated on it and would have measured
    nothing. Triples were DISQUALIFIED on that basis at 1.3%, and doubles
    called thin at 13.7%.

    MEASURED BEFORE THE RUNGS WERE CHOSEN, over 125,298 stored batter-games:
    over 0.5 strikeouts lands 61.7% of the time, over 1.5 lands 22.2%, and over
    2.5 lands 4.6%. The first two are declared and the third is not, and this
    plants the third to check the reasoning is enforced rather than merely
    written down.
    """
    conn = db.connect()
    try:
        rows = [r[0] for r in conn.execute(
            "SELECT strike_outs FROM mlb_batter_games"
            " WHERE lineup_slot IS NOT NULL AND strike_outs IS NOT NULL")]
    finally:
        conn.close()
    if not rows:
        return Result(LAW_CAP, "a rung that inherits its base rate",
                      "the declared batter_strikeouts ladder", False,
                      "no stored batter-games to measure against")

    def share(rung):
        return sum(1 for x in rows if x > rung) / len(rows)

    declared = config.MLB_PROP_LADDER["batter_strikeouts"]
    # THE PLANT: the rung that was measured and refused.
    planted = 2.5
    if planted in declared:
        return Result(LAW_CAP, "a rung that inherits its base rate",
                      "the declared batter_strikeouts ladder", False,
                      f"NOT CAUGHT - {planted} is declared and lands "
                      f"{share(planted):.1%} of the time, which is the "
                      f"one-sidedness the roster disqualifies")
    for rung in declared:
        got = share(rung)
        if not 0.15 <= got <= 0.85:
            return Result(LAW_CAP, "a rung that inherits its base rate",
                          "the declared batter_strikeouts ladder", False,
                          f"the declared rung {rung} lands {got:.1%} of the "
                          f"time, which inherits its base rate as the answer")
    return Result(LAW_CAP, "a rung that inherits its base rate",
                  "the declared batter_strikeouts ladder", True,
                  f"the declared rungs {list(declared)} land "
                  f"{', '.join(f'{share(r):.1%}' for r in declared)} of the "
                  f"time; 2.5 lands {share(planted):.1%} and is refused")


LAW_DRAW = "A DRAWN GAME ANSWERS NEITHER"


def plant_a_drawn_game_graded_as_a_loss() -> Result:
    """Settle an NFL moneyline on a game that finished level.

    TEN OF 2,761 STORED NFL FINALS ENDED LEVEL -- 0.36%, and the record names
    them: SEA 6-6 ARI in 2016, PIT 21-21 CLE in 2018, and eight more. "Did the
    home side win" has no answer on those, and giving one either way invents an
    outcome.

    THE BASKETBALL RULE IS THE OPPOSITE ONE AND FOR THE OPPOSITE REASON. The
    NBA plays overtime until somebody wins, so a level NBA final is a BAD ROW
    rather than a drawn game -- it voids too, but because the data is wrong,
    not because the game was tied. Two sports, two reasons, the same treatment,
    and both said out loud where the code makes the decision.

    THE TRAINING SET MUST DROP THEM TOO, and this checks both ends: a fact
    counted as a loss in one place and a void in the other is a model fitted on
    a question the record does not grade.
    """
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.open_db(Path(tmp) / "draw.db")
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
            " home, away, status, home_score, away_score)"
            " VALUES ('drawn','nfl',2018,10,'REG','2018-11-11T18:00:00Z',"
            " 'PIT','CLE','final',21,21)")
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES ('2018-11-10T00:00:00Z','nfl','drawn','moneyline','PIT',"
            " 0.61,'win','statistical','early','fs3','{}','planted')")
        conn.commit()
        pred = conn.execute(
            "SELECT * FROM predictions WHERE game_id = 'drawn'").fetchone()
        try:
            outcome = resolve.resolve_nfl_outcome(conn, pred)
        except resolve.Void as exc:
            conn.close()
            return Result(LAW_DRAW, "a drawn game graded as a loss",
                          "resolve_nfl_outcome voids a level final", True,
                          str(exc))
        except Exception as exc:                             # noqa: BLE001
            conn.close()
            return Result(LAW_DRAW, "a drawn game graded as a loss",
                          "resolve_nfl_outcome voids a level final", False,
                          f"it failed, but not as a void: "
                          f"{type(exc).__name__}: {exc}")
        conn.close()
    return Result(LAW_DRAW, "a drawn game graded as a loss",
                  "resolve_nfl_outcome voids a level final", False,
                  f"NOT CAUGHT - a game that finished 21-21 was graded "
                  f"{outcome}, so a forecast that could not be right or wrong "
                  f"was scored as one of them")


def plant_an_unfitted_market_that_blocks_a_rerun_refusal() -> Result:
    """Declare a market with no fitted model and rerun the slate.

    A SLATE IS ANSWERED ONCE, and `already_answered` decides that by comparing
    what a run WOULD ask against what has rows. A market that is declared but
    has no fitted model is skipped by `predict` every time -- so if it counts
    as a gap, the slate is never "already answered", the refusal never fires,
    and a rerun writes a second set of forecasts of the same questions.

    THE GUARANTEE STOPS HOLDING SILENTLY, in the direction that duplicates the
    record. It happened on 2026-09-04, the moment the NFL moneyline was
    declared: a fixture training only the spread stopped refusing its own
    rerun, and the only sign was one test going red.
    """
    from gridiron import run as _run
    from gridiron.model import baseline as _baseline

    conn = db.connect()
    try:
        # Every declared market a run would ask must either have a fit or be
        # excluded from the gap calculation. Asserted on the real record.
        for sport in config.SPORTS:
            answered = _run.already_answered(
                conn, sport, 2026, 1, include_props=False)
            for market in answered["missing"]:
                if market == "prop":
                    continue
                try:
                    _baseline.load_fit(
                        conn, _baseline.market_key(sport, market))
                except _baseline.NotTrained:
                    return Result(
                        LAW_DRAW, "an unfitted market blocking a refusal",
                        "run.already_answered ignores unfitted markets", False,
                        f"NOT CAUGHT - {sport}:{market} is counted as a gap in "
                        f"the slate and has no fitted model, so this slate can "
                        f"never be 'already answered' and a rerun is never "
                        f"refused")
    finally:
        conn.close()
    return Result(LAW_DRAW, "an unfitted market blocking a refusal",
                  "run.already_answered ignores unfitted markets", True,
                  "no declared-but-unfitted market is counted as a gap, so the "
                  "answered-once refusal cannot be silently disabled by "
                  "declaring a market nobody has trained yet")


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
    results.append(plant_a_reversed_side_pair())
    results.append(plant_an_ambiguous_side_accepted())
    results.append(plant_an_ambiguous_crosswalk_match())
    results.append(plant_a_constant_prop_factor())
    results.append(plant_a_rung_off_the_declared_ladder())
    results.append(plant_a_notification_carrying_a_probability())
    results.append(plant_a_notification_carrying_a_line())
    results.append(plant_a_results_message_on_an_empty_run())
    results.append(plant_a_merged_forecaster_view())
    results.append(plant_two_forecasters_in_one_picks_list())
    results.append(plant_a_picks_list_labelled_for_the_wrong_forecaster())
    results.append(plant_a_day_key_in_visible_text())
    results.append(plant_a_slate_answered_twice())
    results.append(plant_a_market_source_outside_the_market_module())
    results.append(plant_payout_arithmetic_against_a_market_source())
    results.append(plant_a_default_tier_that_hides_the_count())
    results.append(plant_a_selector_for_a_class_nothing_builds())
    results.append(plant_a_final_pass_inside_the_market_closure())
    results.append(plant_a_launcher_attaching_to_an_older_build())
    results.append(plant_a_ufc_query_merged_with_another_sport())
    results.append(plant_rounds_merged_with_the_moneyline_curve())
    results.append(plant_a_rating_with_a_hand_chosen_k())
    results.append(plant_a_bout_predicted_after_its_start())
    results.append(plant_a_fighter_matched_by_guess())
    results.append(plant_a_count_market_scored_by_the_logistic())
    results.append(plant_a_rung_probability_that_rises_with_the_rung())
    results.append(plant_an_adjusted_factor_that_reads_raw_margin())
    results.append(plant_a_suppressed_pair_read_as_two_reasons())
    results.append(plant_both_form_factors_active_without_a_note())
    results.append(plant_a_ufc_category_merged_across_tiers())
    results.append(plant_a_bout_from_another_promotion_in_the_ufc_pool())
    results.append(plant_a_foreign_key_on_a_table_that_does_not_exist())
    results.append(plant_the_ufc_fetcher_inside_a_prediction_closure())
    results.append(plant_a_market_wearing_another_markets_verb())
    results.append(plant_two_sentences_naming_opposite_sides())
    results.append(plant_a_market_tab_row_that_is_hardcoded())
    results.append(plant_a_card_showing_two_numbers_collapsed())
    results.append(plant_a_moneyline_that_contradicts_its_own_spread())
    results.append(plant_a_moneyline_asked_with_a_rung())
    results.append(plant_a_total_factor_that_takes_a_difference())
    results.append(plant_a_total_rung_that_can_push())
    results.append(plant_a_market_declared_but_never_asked())
    results.append(plant_a_rung_that_inherits_its_base_rate())
    results.append(plant_a_drawn_game_graded_as_a_loss())
    results.append(plant_an_unfitted_market_that_blocks_a_rerun_refusal())
    results.append(plant_a_what_it_knew_line_that_disagrees_with_its_row())
    results.append(plant_an_injury_row_without_a_capture_time())
    results.append(plant_a_backfilled_lineup_posing_as_live())
    results.append(plant_a_capture_that_stores_nothing_and_reports_success())
    results.append(plant_a_training_set_spanning_two_sports())
    results.append(plant_a_sport_adapter_missing_markets())
    results.append(plant_a_docstring_promising_a_guard_that_does_not_exist())
    results.append(plant_an_asked_line_that_is_not_a_distance())
    results.append(plant_a_market_value_in_the_asked_line_path())
    results.append(plant_two_standing_rows_for_one_question())
    results.append(plant_a_final_pass_writing_after_start())
    results.append(plant_an_early_row_entering_calibration())
    results.append(plant_a_clamped_rung_beyond_the_ladder())
    results.append(plant_a_run_line_rung_off_the_market())
    results.append(plant_a_total_asked_from_a_market_value())
    results.append(plant_a_total_merged_with_the_moneyline_curve())
    results.append(plant_an_undated_total_sd())
    results.append(plant_a_run_line_contradicting_its_moneyline())
    results.append(plant_a_fifth_nav_item())
    results.append(plant_an_old_route_left_to_404())
    results.append(plant_a_pick_on_the_login_page())
    results.append(plant_a_silent_attach_to_an_older_build())
    results.append(plant_a_model_constant_made_editable())
    results.append(plant_a_setting_updated_in_place())
    results.append(plant_a_schedule_change_claimed_without_a_read_back())
    results.append(plant_an_unauthenticated_settings_write())
    results.append(plant_a_calendar_that_merges_sports())
    results.append(plant_a_void_counted_as_a_loss())
    results.append(plant_a_square_tinted_against_its_balance())
    results.append(plant_a_progress_line_showing_a_percentage())
    results.append(plant_a_gate_line_without_its_n())
    results.append(plant_a_green_progress_bar())
    results.append(plant_a_resolved_row_on_picks())
    results.append(plant_a_surviving_calls_symbol())
    results.append(plant_a_green_link())
    results.append(plant_a_red_warning_border())
    results.append(plant_a_green_live_mark())
    results.append(plant_a_re_sort_during_a_live_slate())
    results.append(plant_a_bouncing_chip())
    results.append(plant_a_strobing_live_mark())
    results.append(plant_a_live_import_in_a_prediction_path())
    results.append(plant_a_live_column_read_in_a_prediction_path())
    results.append(plant_a_poller_that_settles_a_prediction())
    results.append(plant_a_summed_record_on_the_tabs())
    results.append(plant_a_stale_build_that_says_nothing())
    results.append(plant_a_bundle_missing_a_sport())
    results.append(plant_a_pick_line_that_disagrees_with_its_label())
    results.append(plant_a_side_with_no_words())
    results.append(plant_a_slate_key_on_the_page())
    results.append(plant_a_tile_that_truncates())
    results.append(plant_a_selection_that_moves_the_frame())
    results.append(plant_a_rail_panel_that_writes_its_own_prose())
    results.append(plant_a_rung_chosen_by_rotation())
    results.append(plant_a_rung_chosen_by_the_market())
    results.append(plant_a_home_run_bucket_below_fifty())
    results.append(plant_a_tier_row_below_its_gate_showing_a_rate())
    results.append(plant_verdict_words_that_disagree_with_the_gap())
    results.append(plant_a_pooled_strong_tier())
    results.append(plant_a_why_that_disagrees_with_its_contributions())
    results.append(plant_a_factor_with_no_why_template())
    results.append(plant_a_view_that_names_the_side_itself())
    results.append(plant_a_rankings_factor())
    results.append(plant_a_totals_curve_merged_with_margins())
    results.append(plant_an_undated_cfb_sd())
    results.append(plant_a_cross_sport_cfb_query())
    results.append(plant_a_second_look_served_from_cache())
    results.append(plant_an_active_correction_below_the_gate())
    results.append(plant_a_correction_that_does_not_help())
    results.append(plant_a_genuine_correction_refused())
    results.append(plant_a_retroactive_correction())
    results.append(plant_a_correction_that_reads_the_score())
    results.append(plant_a_correction_that_reads_the_line())
    results.append(plant_a_correction_that_can_see_its_own_future())
    results.append(plant_a_correction_that_scores_a_void())
    results.append(plant_a_scored_rung_claim())
    results.append(plant_a_renderer_that_composes_prose())
    results.append(plant_a_class_name_mistaken_for_prose())
    results.append(plant_a_shadowed_definition())
    results.append(plant_a_composer_that_resolves_the_side_itself())
    results.append(plant_a_side_named_that_ignores_the_flip())
    results.append(plant_an_orphan_guard())
    results.append(plant_a_decorated_function_mistaken_for_an_orphan())
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
    results.append(plant_a_stake_column())
    results.append(plant_a_tier_hit_rate_below_the_gate())
    results.append(plant_a_tier_that_pools_two_buckets())
    results.append(plant_an_unreadable_sample_size())
    results.append(plant_snake_case_in_a_label())
    results.append(plant_an_undecodable_column_name())
    results.append(plant_prose_that_is_not_an_identifier())

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
