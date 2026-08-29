"""Measure SD(actual margin - market line) per sport, from the record.

Run this, paste the output into `gridiron/market/lines.py`, and date it. It is a
tool rather than a runtime computation on purpose: a constant that recomputes
itself from whatever data happens to be loaded is a constant that changes
silently, and every probability derived from it would change with it.

    python tools/measure_margin_sd.py
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import config, db  # noqa: E402


def measure(conn, sport: str) -> dict:
    """SD of (actual home margin - market spread) over completed games.

    This is the quantity the normal approximation needs: how far a final margin
    lands from the number the market put on it. It is NOT the SD of the margin
    itself, which is much larger and would make every derived probability far
    too timid.
    """
    rows = conn.execute(
        "SELECT g.home_score - g.away_score AS margin, m.spread_line"
        " FROM games g JOIN market_lines_raw m ON m.game_id = g.id"
        " WHERE g.sport = ? AND g.status = 'final'"
        "   AND g.home_score IS NOT NULL AND m.spread_line IS NOT NULL",
        (sport,),
    ).fetchall()
    residuals = [r["margin"] - r["spread_line"] for r in rows]
    if len(residuals) < 30:
        return {"sport": sport, "n": len(residuals), "sd": None,
                "reason": "fewer than 30 games carry both a final score and a line"}
    mean = sum(residuals) / len(residuals)
    var = sum((x - mean) ** 2 for x in residuals) / (len(residuals) - 1)
    return {
        "sport": sport,
        "n": len(residuals),
        "mean": round(mean, 3),
        "sd": round(math.sqrt(var), 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database", default=str(config.DEFAULT_DB))
    ap.add_argument("--extra", nargs="*", default=[],
                    help="further databases to pool in (e.g. the backtest DBs)")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    print(f"measured {db.utcnow()}")
    print("pooled across databases, DEDUPLICATED BY GAME ID: a backtest database")
    print("is a copy of the live one, so counting both would report a sample")
    print("twice the size of the games it actually describes.")
    print("")

    for sport in config.SPORTS:
        # game_id -> residual, so the same game seen in two databases counts once
        seen: dict[str, float] = {}
        sources_used: list[str] = []
        for path in [args.database, *args.extra]:
            if not Path(path).exists():
                continue
            conn = db.open_db(path)
            rows = conn.execute(
                "SELECT g.id, g.home_score - g.away_score AS margin, m.spread_line"
                " FROM games g JOIN market_lines_raw m ON m.game_id = g.id"
                " WHERE g.sport = ? AND g.status = 'final'"
                "   AND g.home_score IS NOT NULL AND m.spread_line IS NOT NULL",
                (sport,),
            ).fetchall()
            if rows:
                sources_used.append(f"{Path(path).name}(+{len(rows)})")
            for r in rows:
                seen.setdefault(r["id"], r["margin"] - r["spread_line"])

        residuals = list(seen.values())
        if len(residuals) < 30:
            print(f"  {sport:4s} n={len(residuals):<6,} NOT MEASURABLE - too few games "
                  "carry both a final score and a market line")
            continue
        mean = sum(residuals) / len(residuals)
        sd = math.sqrt(sum((x - mean) ** 2 for x in residuals) / (len(residuals) - 1))
        print(f"  {sport:4s} n={len(residuals):<6,} mean residual {mean:+.3f}   "
              f"SD {sd:.2f}")
        print(f"        from {', '.join(sources_used)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
