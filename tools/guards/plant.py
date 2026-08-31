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
        and "9 settled of 20 needed" in thin["message"]
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
    results.append(plant_a_home_run_bucket_below_fifty())
    results.append(plant_a_tier_row_below_its_gate_showing_a_rate())
    results.append(plant_verdict_words_that_disagree_with_the_gap())
    results.append(plant_a_pooled_strong_tier())
    results.append(plant_a_why_that_disagrees_with_its_contributions())
    results.append(plant_a_factor_with_no_why_template())
    results.append(plant_a_view_that_names_the_side_itself())
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
