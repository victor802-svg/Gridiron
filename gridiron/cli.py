"""Command line entry point. `python -m gridiron.cli <command>`."""

from __future__ import annotations

import argparse
import json
import sys

from . import config, db
from .data import loader, repo


def cmd_init(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    print(f"schema ready at {args.database or config.DB_PATH}")
    conn.close()
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    seasons = tuple(range(args.since, args.until + 1))
    totals = loader.load_all(conn, seasons, progress=lambda m: print(f"  .. {m}", flush=True))
    print()
    for table, n in totals.items():
        print(f"{table:22s} {n:>8,} rows touched")
    conn.close()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    conn = db.open_db(args.database)
    print(json.dumps(repo.counts(conn), indent=2))
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

    s = sub.add_parser("status", help="row counts")
    s.set_defaults(func=cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
