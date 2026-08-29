"""BACKTEST-AS-SANITY. Read the warning before reading the numbers.

    This runs the pipeline over seasons that have already been played. It
    proves that the machinery works end to end: questions get chosen, factors
    get computed from the right cutoff, probabilities get written, lines get
    snapshotted afterwards, outcomes get resolved, and the scorecard renders.

    IT IS NOT EVIDENCE OF AN EDGE.

    The fit for each test season is trained only on seasons before it, so the
    predictions are out-of-sample in the narrow technical sense. But the factor
    set, the question rules, the scaling constants and the model form were all
    chosen in 2026 by someone who already knew how these seasons went in
    aggregate. That is a form of hindsight no walk-forward split removes. Any
    real claim requires forward predictions made before kickoff, resolved
    afterwards, in numbers — which is what the live database is for and why it
    is kept separate from this one.

Writes to its own database, marked `kind=backtest`, so these rows can never be
read as part of the live forward record. The interface shows a banner when it
is pointed at one.

Usage:
    python tools/backtest.py --seasons 2023 2024 2025
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The report contains em-dashes; a Windows console defaults to cp1252 and would
# mangle them into replacement characters.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover - non-tty stream
        pass

from gridiron import calibration, config, db, resolve, run  # noqa: E402
from gridiron.factors import store  # noqa: E402
from gridiron.model import baseline  # noqa: E402

#: Tables carrying facts about the world. Copied from the live database so the
#: backtest does not refetch 25MB that is already on disk. Predictions are
#: pointedly not in this list.
# `games` FIRST: the sport tables carry foreign keys into it, and copying a
# child before its parent fails the constraint.
FACT_TABLES = (
    "games",
    "game_conditions",
    "team_week_stats",
    "player_week_stats",
    "injuries",
    "snap_counts",
    "market_lines_raw",
    "http_cache",
    "mlb_probables",
    "mlb_pitcher_starts",
    "mlb_team_games",
)


def build_database(source: Path, target: Path, note: str) -> sqlite3.Connection:
    if target.exists():
        target.unlink()
    for suffix in ("-wal", "-shm"):
        extra = Path(str(target) + suffix)
        if extra.exists():
            extra.unlink()

    conn = db.open_db(target)
    conn.execute("ATTACH DATABASE ? AS live", (str(source),))
    for table in FACT_TABLES:
        # By NAME, never `SELECT *`. A column added by migration lands at the
        # end of the live table but sits in its declared position in a fresh
        # schema, so a positional copy shifts every value one place along and
        # the only reason we noticed was a CHECK constraint catching a season
        # number where a sport name belonged. Silent corruption otherwise.
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        live_cols = {r[1] for r in conn.execute(f"PRAGMA live.table_info({table})")}
        shared = [c for c in cols if c in live_cols]
        joined = ", ".join(shared)
        conn.execute(f"INSERT INTO {table} ({joined}) SELECT {joined} FROM live.{table}")
    conn.commit()
    conn.execute("DETACH DATABASE live")

    db.set_meta(conn, "kind", "backtest")
    db.set_meta(conn, "kind_note", note)
    store.sync_registry(conn)
    return conn


def run_backtest(
    conn: sqlite3.Connection,
    seasons: list[int],
    train_from: int,
    *,
    sport: str = "nfl",
    include_props: bool = True,
    snapshot: bool = True,
    log=print,
) -> dict:
    totals = {"predicted": 0, "resolved": 0, "seasons": {}}

    for season in seasons:
        log(f"\n=== {season} " + "=" * 50)
        started = time.time()
        train_seasons = tuple(range(train_from, season))
        if not train_seasons:
            raise SystemExit(f"nothing to train on before {season}")

        fits = baseline.train_all(
            conn,
            train_seasons,
            sport=sport,
            include_props=include_props,
            note=f"backtest fit for {season}, trained on "
                 f"{min(train_seasons)}-{max(train_seasons)}",
        )
        for market_type, fit in fits.items():
            log(
                f"  fit {market_type:22s} n={fit.n:,} on seasons "
                f"{min(train_seasons)}-{max(train_seasons)} (strictly before {season})"
            )

        weeks = [
            r["week"]
            for r in conn.execute(
                "SELECT DISTINCT week FROM games WHERE sport = ? AND season = ?"
                " AND status = 'final' ORDER BY week",
                (sport, season),
            )
        ]
        written = 0
        for i, week in enumerate(weeks):
            if log and i % 25 == 0:
                log(f"    slate {i}/{len(weeks)}")
            result = run.run_slate(
                conn, sport, season, week, include_props=include_props,
                use_llm=False, snapshot=snapshot,
            )
            written += result["written"]
        settled = resolve.resolve_all(conn)
        log(
            f"  {len(weeks)} weeks: {written} predictions written, "
            f"{settled['settled']} resolved  [{time.time() - started:.0f}s]"
        )
        totals["predicted"] += written
        totals["resolved"] += settled["settled"]
        totals["seasons"][season] = {"written": written, "resolved": settled["settled"]}

    return totals


def report(conn: sqlite3.Connection, log=print, sport: str = "nfl") -> None:
    log("\n" + "=" * 66)
    log("BACKTEST RESULT — pipeline sanity, NOT evidence of an edge")
    log("=" * 66)

    markets = [
        (calibration.market_type_of(sport, m), calibration.prop_type_of(sport, m))
        for m in config.SPORT_MARKETS.get(sport, ())
    ]
    for market_type, prop_type in markets:
        c = calibration.curve(conn, sport=sport, market_type=market_type,
                              prop_type=prop_type, predictor="statistical")
        s = c["score"]
        if not s["n"]:
            continue
        name = prop_type or market_type
        log(f"\n{name.upper()}  (n={s['n']:,}, {c['voided']} void)")
        log(f"  Brier    {s['brier']:.4f}   vs always-50%: {calibration.ALWAYS_HALF_BRIER:.4f}")
        log(f"  log loss {s['log_loss']:.4f}   vs always-50%: {calibration.ALWAYS_HALF_LOG_LOSS:.4f}")
        log(f"  hit rate {s['hit_rate']:.4f}")
        market = c["baselines"].get("market") or {}
        if market.get("n"):
            same = c["baselines"]["model_on_market_subset"]
            log(
                f"  market   {market['brier']:.4f} Brier over the same {market['n']:,} "
                f"questions; the model scores {same['brier']:.4f} on that subset"
            )
        log("  calibration:")
        for b in c["buckets"]:
            if b["n"]:
                flag = "  (provisional)" if b["provisional"] else ""
                log(
                    f"    {b['label']:>7s}  n={b['n']:>5,}  claimed {b['claimed']:.3f}  "
                    f"actual {b['actual']:.3f}  gap {b['gap']:+.3f}{flag}"
                )
            else:
                log(f"    {b['label']:>7s}  n=0")
        log(f"  {c['largest_gap']}")

    # The game market of THIS sport, not football's. A hardcoded "spread" here
    # asked baseball a football question and got an empty answer that looked
    # like a finding; the required sport argument is what made it fail loudly
    # instead of quietly reporting nothing.
    game_market = next(
        m for m in config.SPORT_MARKETS[sport]
        if m not in config.SPORT_PROP_MARKETS.get(sport, ())
    )
    e = calibration.edge(
        conn, sport=sport, market_type=game_market, predictor="statistical"
    )
    log("")
    log(f"EDGE QUESTION ({game_market}, threshold {e['threshold']}):")
    if not e.get("renderable"):
        log(f"  {e['message']}")
    else:
        m = e["model_more_confident"]
        k = e["market_more_confident"]
        log(
            f"  model more confident: n={m['n']:,}  resolved in model's favour "
            f"{m['resolved_in_model_favour']:.3f}  (model said {m['mean_model_prob']:.3f}, "
            f"market said {m['mean_market_prob']:.3f})"
        )
        log(
            f"  market more confident: n={k['n']:,}  resolved in model's favour "
            f"{k['resolved_in_model_favour']:.3f}"
        )
    log(f"  {e['standing_note']}")

    fr = calibration.factor_report(conn, sport=sport)
    log(f"\nFACTORS (over {fr['n']:,} resolved statistical predictions):")
    for f in fr["factors"]:
        if not f["n"]:
            log(f"    {f['factor']:22s} n=0      {f['verdict']}")
            continue
        log(
            f"    {f['factor']:22s} n={f['n']:>5,}  delta Brier {f['delta_brier']:+.5f}  "
            f"mean |contribution| {f['mean_abs_contribution']:.4f}  {f['verdict']}"
        )

    log("\n" + "-" * 66)
    log("ON COMPARING THIS TO A PREVIOUS FACTOR SET")
    log("-" * 66)
    log("A Brier score from a refit is not a result. Any change in it, in")
    log("either direction, is what refitting a model on the same seasons")
    log("produces. It means nothing until the new factor set has a FORWARD")
    log("record of its own. The version comparison in the interface starts")
    log("v2 at N=0 for exactly this reason, and never adds it to v1.")
    log("")
    log("This run's numbers are stated above. They are not offered as an")
    log("improvement on anything. If they look like one, that is the")
    log("expected behaviour of a refit and not evidence about football.")

    log("\n" + "=" * 66)
    log("Reminder: every number above was produced over seasons already played,")
    log("by a factor set chosen with knowledge of how those seasons went. It")
    log("shows the pipeline runs. It does not show the model has an edge.")
    log("=" * 66)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--sport", default="nfl", choices=list(config.SPORTS))
    p.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024, 2025])
    p.add_argument("--no-snapshot", action="store_true",
                   help="skip the market fetch; the record still resolves")
    p.add_argument("--train-from", type=int, default=2016)
    p.add_argument("--source", default=str(config.DEFAULT_DB))
    p.add_argument("--target", default=str(config.REPO_ROOT / "var" / "backtest.db"))
    p.add_argument("--no-props", action="store_true")
    args = p.parse_args()

    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f"no source database at {source}; run `gridiron.cli load` first")

    note = (
        f"Walk-forward {args.sport.upper()} backtest over {args.seasons}, each season "
        f"predicted by a fit "
        f"trained only on seasons from {args.train_from} up to the year before. "
        "Predictions were made AFTER the games were played. This is a pipeline "
        "sanity check, not evidence of an edge."
    )
    conn = build_database(source, Path(args.target), note)
    print(f"backtest database: {args.target}")
    print(f"kind: {db.database_kind(conn)}")

    run_backtest(
        conn, args.seasons, args.train_from, sport=args.sport,
        include_props=not args.no_props, snapshot=not args.no_snapshot,
    )
    report(conn, sport=args.sport)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
