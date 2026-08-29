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
import shutil
import sqlite3
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import audit, blind, calibration, config, db, resolve, run  # noqa: E402
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
    baseline.train(conn, "spread", (2025,), l2=1.0, note="guard harness")
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
    payload = calibration.scorecard(conn)
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
    edge = calibration.edge(conn, market_type="spread", predictor="statistical")
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
