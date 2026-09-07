"""Rank the predictions that were written before the ranker existed.

    python tools/backfill_ranks.py            # what it would do
    python tools/backfill_ranks.py --write    # do it

WHY THE ROWS ARE MARKED. A rank computed today from a frozen row is not the
same object as one computed before kickoff. It cannot have been influenced by
the outcome -- the inputs are the prediction's own probability, its coverage
figure and the snapshot taken at the time -- but it was written by somebody who
already knows how the games went, and the formula it uses was chosen with that
knowledge available. So every row this writes carries `backfilled = 1`, and
`calibration.ranker_comparison` leaves those rows out of the comparison that
scores the ranker.

It exists so the Picks page is not empty of ordering on its first day, not to
pad the evidence. Those are different jobs and the column is what keeps them
apart.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import config, db, shortlist  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="write the ranks; without it, only count them")
    parser.add_argument("--database", default=None)
    args = parser.parse_args(argv)

    conn = db.open_db(args.database)
    pending = conn.execute(
        "SELECT COUNT(*) FROM predictions p WHERE NOT EXISTS"
        " (SELECT 1 FROM prediction_ranks r WHERE r.prediction_id = p.id"
        "  AND r.ranker_version = ?)", (config.RANKER_VERSION,)).fetchone()[0]
    print(f"{pending} predictions carry no {config.RANKER_VERSION} rank")
    if not args.write:
        print("nothing written. Pass --write to record them, marked as a backfill.")
        return 0

    counts = shortlist.rank_rows(conn, None, backfilled=True)
    print(f"ranked {counts['ranked']} rows "
          f"({counts['shortlisted']} would have led their slate, "
          f"{counts['no_line']} had no line to disagree with, "
          f"{counts['edge_counted']} had an edge that counted)")
    by_sport = conn.execute(
        "SELECT sport, COUNT(*) AS n, SUM(on_shortlist) AS led"
        " FROM prediction_ranks WHERE ranker_version = ? AND backfilled = 1"
        " GROUP BY sport ORDER BY n DESC", (config.RANKER_VERSION,)).fetchall()
    for row in by_sport:
        print(f"  {row['sport']}: {row['n']} ranked, {row['led']} led a slate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
