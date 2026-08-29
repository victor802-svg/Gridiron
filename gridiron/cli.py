"""Command line entry point. `python -m gridiron.cli <command>`."""

from __future__ import annotations

import argparse
import json
import sys

from . import config, db
from . import calibration, resolve as resolver
from .data import loader, repo, weather
from .factors import registry, store
from .model import baseline


def cmd_init(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    print(f"schema ready at {args.database or config.DB_PATH}")
    conn.close()
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    say = lambda m: print(f"  .. {m}", flush=True)

    if args.sport == "mlb":
        from .data import mlb_loader

        seasons = tuple(range(
            args.since or min(config.SPORT_LOAD_SEASONS["mlb"]),
            (args.until or max(config.SPORT_LOAD_SEASONS["mlb"])) + 1,
        ))
        result = mlb_loader.load_all(conn, seasons, progress=say)
    elif args.sport == "nba":
        from .data import nba_loader

        seasons = tuple(range(
            args.since or min(config.SPORT_LOAD_SEASONS["nba"]),
            (args.until or max(config.SPORT_LOAD_SEASONS["nba"])) + 1,
        ))
        result = nba_loader.load_all(conn, seasons, progress=say)
    else:
        seasons = tuple(range(args.since, args.until + 1))
        result = loader.load_all(conn, seasons, progress=say)
    print()
    for table, n in result["rows"].items():
        print(f"{table:22s} {n:>8,} rows touched")
    if result["warnings"]:
        print()
        print("!! DATA WARNINGS — a source returned nothing where data was expected:")
        for w in result["warnings"]:
            print(f"   - {w}")
        conn.close()
        return 1
    conn.close()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    print(json.dumps(repo.counts(conn), indent=2))
    conn.close()
    return 0


def cmd_factors(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    if args.sync:
        print(json.dumps(store.sync_registry(conn), indent=2))
    rows = store.stored_factors(conn)
    if not rows:
        print("no factors recorded yet; run `factors --sync`")
        conn.close()
        return 0
    width = max(len(r["name"]) for r in rows)
    for r in rows:
        flag = "active  " if r["active"] else "INACTIVE"
        applies = ",".join(r["applies_to"]) or "-"
        print(f"{flag} {r['name']:<{width}}  added {r['added_utc'][:10]}  [{applies}]")
        print(f"         {r['rationale']}")
        if r["note"]:
            print(f"         NOTE: {r['note']}")
        print()
    print(f"{len(rows)} factors declared, {sum(1 for r in rows if r['active'])} active")
    conn.close()
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    store.sync_registry(conn)
    seasons = tuple(range(args.since, args.until + 1))
    sport = args.sport
    markets = args.markets
    if markets == ["all"]:
        markets = [
            m if m not in config.SPORT_PROP_MARKETS.get(sport, ()) else f"prop:{m}"
            for m in config.SPORT_MARKETS.get(sport, ())
        ]
    for market_type in markets:
        fit = baseline.train(
            conn,
            market_type,
            seasons,
            sport=sport,
            note=args.note,
            progress=lambda m: print(f"  .. {market_type} {m}", flush=True),
        )
        print()
        print(f"{sport}:{market_type}: n={fit.n:,} converged={fit.converged} "
              f"iterations={fit.iterations} intercept={fit.intercept:+.4f}")
        for name, coef in sorted(zip(fit.names, fit.coefficients), key=lambda t: -abs(t[1])):
            print(f"    {name:22s} {coef:+.4f}")
        print()
    conn.close()
    return 0


def cmd_weather(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    print(json.dumps(weather.fetch_week(conn, args.season, args.week), indent=2))
    conn.close()
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
    """The blind loop: predict, then -- and only then -- the market."""
    from .run import run_slate

    conn = db.open_db(args.database)
    store.sync_registry(conn)
    sport = args.sport
    season = args.season or config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    week = args.week
    if week is None:
        week = repo.next_unplayed_week(conn, season, sport=sport)
        if week is None:
            print(f"no scheduled {sport} games left in {season}")
            conn.close()
            return 1
        word = config.SPORT_SLATE_WORD.get(sport, "week")
        print(f"next unplayed {word} in {season} is {word} {week}")

    if sport == "nfl" and not args.no_weather:
        counts = weather.fetch_week(conn, season, week)
        print(f"weather: {counts}")

    result = run_slate(
        conn,
        sport,
        season,
        week,
        include_props=not args.no_props,
        use_llm=not args.no_llm,
        progress=lambda m: print(f"  .. {m}", flush=True) if args.verbose else None,
    )
    print()
    print(json.dumps(result, indent=2))
    conn.close()
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    result = resolver.resolve_all(conn, progress=lambda m: print(f"  .. {m}", flush=True))
    print(json.dumps(result, indent=2))
    print(json.dumps(resolver.summary(conn), indent=2))
    conn.close()
    return 0


def cmd_scorecard(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    kind = db.database_kind(conn)
    if kind["kind"] != "live":
        print(f"!! {kind['kind'].upper()} DATABASE — {kind['note']}")
        print()
    if args.json:
        print(json.dumps(calibration.scorecard(conn, sport=args.sport), indent=2))
        conn.close()
        return 0

    for market in config.SPORT_MARKETS.get(args.sport, ()):
        for predictor in ("statistical", "llm"):
            c = calibration.curve(
                conn, sport=args.sport,
                market_type=calibration.market_type_of(args.sport, market),
                prop_type=calibration.prop_type_of(args.sport, market),
                predictor=predictor,
            )
            if not c["n"]:
                continue
            print(f"=== {args.sport} {market} / {predictor}  (n={c['n']:,})")
            s2 = c["score"]
            print(f"    Brier {s2['brier']}  log loss {s2['log_loss']}  hit rate {s2['hit_rate']}")
            for b in c["buckets"]:
                if b["n"]:
                    print(f"      {b['label']:>7s} n={b['n']:>5,} claimed {b['claimed']:.3f}"
                          f" actual {b['actual']:.3f} gap {b['gap']:+.3f}")
                else:
                    print(f"      {b['label']:>7s} n=0")
            print(f"    {c['largest_gap']}")
            print()

    e = calibration.edge(conn, sport=args.sport)
    print("=== edge question")
    print(f"    {e['message'] if not e.get('renderable') else e['model_more_confident']}")
    print(f"    {e['standing_note']}")
    conn.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from . import api

    from . import auth

    api.set_database(args.database or config.DB_PATH)
    print(f"Gridiron on http://{config.HOST}:{args.port}  (127.0.0.1 only)")
    if auth.read_token() is None:
        print("  no access token configured — run: python tools/make_token.py")
    elif getattr(args, "open_browser", False):
        print("  opening a signed-in browser (single-use handoff, 60s)")
    api.serve(port=args.port, open_browser=getattr(args, "open_browser", False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gridiron", description="NFL forecaster with a scorecard")
    p.add_argument("--database", help="path to the SQLite file (default: var/gridiron.db)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="create the schema")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("load", help="fetch and cache one sport's data")
    s.add_argument("--sport", default="nfl", choices=list(config.SPORTS))
    s.add_argument("--since", type=int, default=min(config.DEFAULT_LOAD_SEASONS))
    s.add_argument("--until", type=int, default=max(config.DEFAULT_LOAD_SEASONS))
    s.set_defaults(func=cmd_load)

    s = sub.add_parser("factors", help="the declared factor registry")
    s.add_argument("--sync", action="store_true", help="write the registry into the database")
    s.set_defaults(func=cmd_factors)

    s = sub.add_parser("train", help="fit the statistical baseline")
    s.add_argument("--sport", default="nfl", choices=list(config.SPORTS))
    s.add_argument("--since", type=int, default=min(config.DEFAULT_LOAD_SEASONS))
    s.add_argument("--until", type=int, default=config.CURRENT_SEASON - 1)
    s.add_argument("--markets", nargs="+", default=["all"],
                   help="'all', or e.g. spread prop:receptions")
    s.add_argument("--note")
    s.set_defaults(func=cmd_train)

    s = sub.add_parser("weather", help="fetch kickoff forecasts for a week")
    s.add_argument("--season", type=int, default=config.CURRENT_SEASON)
    s.add_argument("--week", type=int, required=True)
    s.set_defaults(func=cmd_weather)

    s = sub.add_parser("predict", help="blind prediction for a slate, then snapshot lines")
    s.add_argument("--sport", default="nfl", choices=list(config.SPORTS))
    s.add_argument("--season", type=int, default=None)
    s.add_argument("--week", type=int, default=None, help="default: next unplayed")
    s.add_argument("--no-props", action="store_true")
    s.add_argument("--no-llm", action="store_true")
    s.add_argument("--no-weather", action="store_true")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_predict)

    s = sub.add_parser("resolve", help="settle every open prediction whose game is final")
    s.set_defaults(func=cmd_resolve)

    s = sub.add_parser("scorecard", help="the calibration record for one sport")
    s.add_argument("--sport", default="nfl", choices=list(config.SPORTS))
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_scorecard)

    s = sub.add_parser("task", help="run one scheduled task and record the attempt")
    s.add_argument("name", choices=sorted(list(_task_names()) + ["catch-up"]))
    s.add_argument("--no-llm", action="store_true")
    s.set_defaults(func=cmd_task)

    s = sub.add_parser("schedule", help="what the scheduler has and has not done")
    s.set_defaults(func=cmd_schedule)

    s = sub.add_parser("serve", help="run the local web interface")
    s.add_argument("--open", dest="open_browser", action="store_true",
                   help="open an already-signed-in browser (the desktop launcher)")
    s.add_argument("--port", type=int, default=config.PORT)
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("status", help="row counts")
    s.set_defaults(func=cmd_status)

    return p


def _task_names():
    from .tasks import TASKS

    return TASKS.keys()


def cmd_task(args: argparse.Namespace) -> int:
    """Run one scheduled task. Always exits 0 unless the task itself failed:
    the scheduler should not retry a task that correctly did nothing."""
    from . import tasks

    conn = db.open_db(args.database)
    if args.name == "catch-up":
        results = tasks.catch_up(conn, use_llm=not args.no_llm)
    else:
        results = [tasks.run_task(conn, args.name, use_llm=not args.no_llm)]
    for r in results:
        print(f"[{r['result']:6s}] {r['task']}: {r['detail']}")
    return 1 if any(r["result"] == "failed" for r in results) else 0


def cmd_schedule(args: argparse.Namespace) -> int:
    from . import tasks

    conn = db.open_db(args.database)
    st = tasks.status(conn)
    print(f"{'task':14s} {'last run':22s} {'result':8s} {'age':>7s}  next due")
    for t in st["tasks"]:
        age = f"{t['age_hours']:.1f}h" if t["age_hours"] is not None else "never"
        print(f"{t['task']:14s} {str(t['last_run_utc']):22s} "
              f"{str(t['last_result']):8s} {age:>7s}  {t['next_due_utc'] or '-'}")
        if t.get("warning"):
            print(f"                 !! {t['warning']}")
        for m in t["missed"]:
            print(f"                 MISSED {m['started_utc']}: {m['detail'][:90]}")
    print()
    for s in st["schedule_staleness"]["sports"]:
        flag = "STALE" if s["stale"] else "ok   "
        print(f"  schedule {s['label']:4s} {flag}  {s['note']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
