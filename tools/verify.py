"""The G6 verification run, in one command.

    python tools/verify.py

Four steps, reported honestly:

  1. The full test suite.
  2. The planted-violation harness: every law broken on purpose, every guard
     required to fire.
  3. One complete week end to end — questions chosen, factors computed,
     probabilities written blind, lines snapshotted afterwards, outcomes
     resolved, calibration rendered with its (tiny) N. Run on the most recent
     COMPLETED week, because a week that has not been played cannot be
     resolved, and this step is about proving resolution works.
  4. The status of the live forward week: written before kickoff, lines
     snapshotted after, waiting for the games. Its N is zero until they are
     played, and this says so rather than borrowing step 3's numbers.

Steps 3 and 4 are reported separately and never added together. Step 3 is a
retrospective run and proves the pipeline works. Step 4 is the only thing that
could ever become evidence, and it has not happened yet.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
# `tools/` itself, so the shared copy helper imports by name.
sys.path.insert(0, str(Path(__file__).resolve().parent))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from gridiron import calibration, config, db, resolve, run  # noqa: E402
from gridiron.factors import store  # noqa: E402
from gridiron.model import baseline  # noqa: E402

from dbcopy import FACT_TABLES, copy_facts  # noqa: E402,F401


def rule(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def step_1_tests(quick: bool) -> bool:
    rule("STEP 1 — the full test suite")
    args = [sys.executable, "-m", "pytest", "-q"]
    if quick:
        args += ["-m", "not browser and not slow"]
    result = subprocess.run(args, cwd=str(REPO), capture_output=True, text=True)
    tail = [ln for ln in result.stdout.strip().splitlines() if ln.strip()][-3:]
    print("\n".join(tail))
    return result.returncode == 0


def step_2_guards() -> bool:
    rule("STEP 2 — planted violations")
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "guards" / "plant.py")],
        cwd=str(REPO), capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("[") or "planted violations were caught" in line:
            print(line)
    ok = result.returncode == 0

    # The standing scans, run against the REAL package rather than a planted
    # copy. A planting proves a scan fires; this proves the package passes it.
    # They were reachable only from tests until 2026-08-31, which the orphan
    # scan is what noticed.
    from gridiron import audit

    print()
    for name, fn in (
        ("prediction closures (LAW 1)", audit.check_all_prediction_closures),
        ("no orphan functions", audit.check_no_orphan_functions),
        ("one door for the side", audit.check_side_named),
        ("no shadowed definitions", audit.check_no_shadowed_definitions),
        ("the side, in prose, anywhere", audit.check_side_named_everywhere),
        ("the renderer composes no prose", audit.check_js_composes_no_prose),
        ("the correction sees claims only", audit.check_correction_is_isolated),
        ("the second look is a second look", audit.check_the_second_look_is_fresh),
        ("no rankings in college football", audit.check_no_rankings),
        ("the rung is chosen against the margin",
         audit.check_the_rung_is_chosen_by_margin),
        ("no tile truncates", audit.check_no_truncation_in_the_frame),
        ("selecting leaves the frame alone",
         audit.check_selection_leaves_the_frame_alone),
        ("every side has words", audit.check_every_side_has_words),
        ("no silent defaults (v2)", audit.check_no_silent_defaults),
        ("not a betting tool (LAW 5)", audit.check_not_a_betting_tool),
        ("no offline data caching", audit.check_no_offline_data_caching),
    ):
        try:
            fn()
            print(f"  PASS  {name}")
        except audit.LawViolation as exc:
            ok = False
            print(f"  FAIL  {name}: {str(exc).splitlines()[0]}")
    return ok


def step_3_one_week_end_to_end(source: Path) -> bool:
    rule("STEP 3 — one complete week, end to end (retrospective; resolution works)")

    sport = "nfl"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        target = Path(tmp) / "one-week.db"
        conn = db.open_db(target)
        copy_facts(conn, source)
        db.set_meta(conn, "kind", "backtest")
        db.set_meta(conn, "kind_note", "single-week end-to-end verification run")
        store.sync_registry(conn)

        # SPORT-SCOPED. This step verifies one NFL week, and without the filter
        # it took MAX(week) across every sport - which is a BASEBALL DAY NUMBER,
        # 155 and climbing. It selected a week no football game has ever been
        # played in, wrote zero predictions, and reported that as a failure of
        # the pipeline rather than of the query. LAW 6 is about reading the
        # record, but the same confusion reaches anything that mixes the sports'
        # week keys.
        last = conn.execute(
            "SELECT season, MAX(week) AS week FROM games"
            " WHERE sport = ? AND status = 'final' AND game_type = 'REG'"
            " AND season = (SELECT MAX(season) FROM games"
            "               WHERE sport = ? AND status = 'final')",
            (sport, sport),
        ).fetchone()
        season, week = last["season"], last["week"]
        print(f"target: {season} week {week} (the most recent completed regular-season week)")

        started = time.time()
        fits = baseline.train_all(
            conn, tuple(range(2016, season)),
            note=f"verification fit, strictly before {season}",
        )
        for market_type, fit in sorted(fits.items()):
            print(f"  fit {market_type:22s} n={fit.n:>6,}, trained on "
                  f"2016-{season - 1} only")

        result = run.run_week(conn, season, week, include_props=True, use_llm=False)
        print(f"  predictions written blind: {result['written']}  {result['by_predictor']}")
        print(f"  market snapshots attached AFTER: {result['snapshots']}")

        ordering_violations = conn.execute(
            "SELECT COUNT(*) FROM predictions p JOIN market_snapshots s"
            " ON s.prediction_id = p.id WHERE s.fetched_utc < p.created_utc"
        ).fetchone()[0]
        print(f"  snapshots timestamped before their prediction: {ordering_violations}")

        settled = resolve.resolve_all(conn)
        print(f"  resolved: {settled['settled']}  voided: {settled['voided']}"
              f"  still open: {settled['still_open']}")
        again = resolve.resolve_all(conn)
        print(f"  second resolution pass settled: {again['settled']} (must be 0)")

        print(f"  [{time.time() - started:.0f}s]")
        print()
        ok = True
        # LAW 6: every read of the record names its sport. This step verifies
        # one NFL week, so it asks NFL. It was written before LAW 6 existed and
        # sat broken behind an earlier failure, which is its own small lesson
        # about what an unrun verifier is worth.
        markets = [("spread", None)] + [("prop", m) for m in config.PROP_MARKETS]
        for market_type, prop_type in markets:
            curve = calibration.curve(conn, sport=sport, market_type=market_type,
                                      prop_type=prop_type, predictor="statistical")
            name = prop_type or market_type
            print(f"  {name} / statistical  n={curve['n']}, {curve['voided']} void")
            for bucket in curve["buckets"]:
                if bucket["n"]:
                    print(f"     {bucket['label']:>7s} n={bucket['n']:>3}  "
                          f"claimed {bucket['claimed']:.3f}  actual {bucket['actual']:.3f}"
                          f"  {'(provisional)' if bucket['provisional'] else ''}")
                else:
                    print(f"     {bucket['label']:>7s} n=0")
            print(f"     {curve['largest_gap']}")

        payload = calibration.scorecard(conn, sport=sport)
        calibration.assert_every_figure_has_n(payload)
        print("\n  scorecard passed the LAW 4 validator: every figure carries its N")
        edge = payload["edge"]
        print(f"  edge question: {edge.get('message', 'rendered')}")

        ok = ok and ordering_violations == 0 and settled["settled"] > 0 and again["settled"] == 0
        # Close before the TemporaryDirectory unwinds: Windows will not delete a
        # file that still has an open handle, and the cleanup error would mask
        # the result of the step.
        conn.close()
        return ok


def step_4_live_forward_week() -> bool:
    rule("STEP 4 — the live forward week (the only thing that could be evidence)")
    if not config.DB_PATH.exists():
        print(f"no live database at {config.DB_PATH}")
        return False

    conn = db.open_db(config.DB_PATH)
    kind = db.database_kind(conn)
    print(f"database: {config.DB_PATH}  (kind={kind['kind']})")

    # GROUPED BY SPORT, and VOIDED ROWS EXCLUDED. Both matter and both were
    # wrong. Without the sport, NFL week 1 and NBA week 1 were added together
    # and reported as one slate of 151 predictions - the same cross-sport week
    # confusion that made step 3 target a baseball day number. And a voided
    # prediction is not part of the record: the six MLB rows written after first
    # pitch were voided FOR that reason, and counting them made the blind-first
    # check fail on predictions that had already been removed for failing it.
    rows = conn.execute(
        "SELECT g.sport, g.season, g.week, COUNT(*) AS n,"
        " MIN(p.created_utc) AS written, MIN(g.kickoff_utc) AS first_kickoff,"
        " SUM(CASE WHEN p.resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved,"
        " SUM(CASE WHEN g.status = 'final' THEN 1 ELSE 0 END) AS played"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)"
        " GROUP BY g.sport, g.season, g.week"
        " ORDER BY g.sport, g.season DESC, g.week DESC"
    ).fetchall()
    if not rows:
        print("no forward predictions on record")
        conn.close()
        return False

    ok = True
    for r in rows:
        snapshots = conn.execute(
            "SELECT COUNT(*) FROM market_snapshots s JOIN predictions p"
            " ON p.id = s.prediction_id JOIN games g ON g.id = p.game_id"
            " WHERE g.sport = ? AND g.season = ? AND g.week = ?",
            (r["sport"], r["season"], r["week"]),
        ).fetchone()[0]
        blind_ok = r["written"] < r["first_kickoff"] if r["first_kickoff"] else None
        print(f"\n  {r['season']} week {r['week']}: {r['n']} predictions")
        print(f"    written        {r['written']}")
        print(f"    first kickoff  {r['first_kickoff']}")
        print(f"    written before kickoff: {blind_ok}")
        print(f"    market snapshots attached: {snapshots}")
        print(f"    games played: {r['played']} of {r['n']}   resolved: {r['resolved']}")
        if blind_ok is False:
            ok = False

    print(
        "\n  Predictions on unplayed games cannot be resolved, so this week's"
        "\n  calibration N is zero and stays zero until the games happen. That is"
        "\n  the honest state of the record, not a gap to be filled with step 3's"
        "\n  numbers. Run `python -m gridiron.cli resolve` after the games."
    )
    conn.close()
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the G6 verification")
    parser.add_argument("--quick", action="store_true",
                        help="skip browser and slow tests in step 1")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--source", default=str(config.DEFAULT_DB))
    args = parser.parse_args()

    outcomes: dict[str, bool] = {}
    if not args.skip_tests:
        outcomes["1. test suite"] = step_1_tests(args.quick)
    outcomes["2. planted violations"] = step_2_guards()

    source = Path(args.source)
    if source.exists():
        outcomes["3. one week end to end"] = step_3_one_week_end_to_end(source)
    else:
        print(f"\nno database at {source}; skipping steps 3 and 4")

    outcomes["4. live forward week"] = step_4_live_forward_week()

    rule("VERIFICATION SUMMARY")
    for name, ok in outcomes.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(
        "\nStep 3 is retrospective and proves the pipeline works. Step 4 is the"
        "\nonly step that could ever become evidence of an edge, and it will not"
        "\nbe evidence of anything until it has a season behind it."
    )
    return 0 if all(outcomes.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
