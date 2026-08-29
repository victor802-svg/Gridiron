"""Command line entry point. `python -m gridiron.cli <command>`."""

from __future__ import annotations

import argparse
import json
import sys

from . import config, db
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
    seasons = tuple(range(args.since, args.until + 1))
    result = loader.load_all(conn, seasons, progress=lambda m: print(f"  .. {m}", flush=True))
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
    for market_type in args.markets:
        fit = baseline.train(
            conn,
            market_type,
            seasons,
            note=args.note,
            progress=lambda m: print(f"  .. {market_type} {m}", flush=True),
        )
        print()
        print(f"{market_type}: n={fit.n:,} converged={fit.converged} "
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
    """The G3 loop: blind prediction, then -- and only then -- the market."""
    from .run import run_week

    conn = db.open_db(args.database)
    store.sync_registry(conn)
    week = args.week
    if week is None:
        week = repo.next_unplayed_week(conn, args.season)
        if week is None:
            print(f"no scheduled games left in {args.season}")
            conn.close()
            return 1
        print(f"next unplayed week in {args.season} is week {week}")

    if not args.no_weather:
        counts = weather.fetch_week(conn, args.season, week)
        print(f"weather: {counts}")

    result = run_week(
        conn,
        args.season,
        week,
        include_props=not args.no_props,
        use_llm=not args.no_llm,
        progress=lambda m: print(f"  .. {m}", flush=True) if args.verbose else None,
    )
    print()
    print(json.dumps(result, indent=2))
    conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gridiron", description="NFL forecaster with a scorecard")
    p.add_argument("--database", help="path to the SQLite file (default: var/gridiron.db)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="create the schema")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("load", help="fetch and cache nflverse data")
    s.add_argument("--since", type=int, default=min(config.DEFAULT_LOAD_SEASONS))
    s.add_argument("--until", type=int, default=max(config.DEFAULT_LOAD_SEASONS))
    s.set_defaults(func=cmd_load)

    s = sub.add_parser("factors", help="the declared factor registry")
    s.add_argument("--sync", action="store_true", help="write the registry into the database")
    s.set_defaults(func=cmd_factors)

    s = sub.add_parser("train", help="fit the statistical baseline")
    s.add_argument("--since", type=int, default=min(config.DEFAULT_LOAD_SEASONS))
    s.add_argument("--until", type=int, default=config.CURRENT_SEASON - 1)
    s.add_argument("--markets", nargs="+", default=["spread", "prop"])
    s.add_argument("--note")
    s.set_defaults(func=cmd_train)

    s = sub.add_parser("weather", help="fetch kickoff forecasts for a week")
    s.add_argument("--season", type=int, default=config.CURRENT_SEASON)
    s.add_argument("--week", type=int, required=True)
    s.set_defaults(func=cmd_weather)

    s = sub.add_parser("predict", help="blind prediction for a week, then snapshot lines")
    s.add_argument("--season", type=int, default=config.CURRENT_SEASON)
    s.add_argument("--week", type=int, default=None, help="default: next unplayed")
    s.add_argument("--no-props", action="store_true")
    s.add_argument("--no-llm", action="store_true")
    s.add_argument("--no-weather", action="store_true")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_predict)

    s = sub.add_parser("status", help="row counts")
    s.set_defaults(func=cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
