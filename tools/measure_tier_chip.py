"""Does the tier chip do the job the confidence floor would have done?

WHY THIS EXISTS. The ruling of 2026-09-04 removed no cards from game markets
and set no floor, on the argument that *"a reader is told what a claim is
worth instead of having weak claims hidden from them"*. The thing doing the
telling is the tier chip. That was asserted and never measured, and the
operator asked for it to be measured against a real slate.

THREE QUESTIONS, and the chip has to answer all three to be carrying that
argument:

  1. DOES IT APPEAR?  A card with no chip says nothing at all.
  2. DOES IT VARY?    A chip that reads the same on every card in a market
                      conveys no more than no chip would.
  3. IS IT EARNED?    `tier_from_bucket` states a hit rate only once the
                      bucket holds `TIER_MIN_SETTLED` settled picks. Below
                      that the chip names a band and nothing stands behind it,
                      which is honest and is NOT the same as telling a reader
                      what a claim is worth.

    python tools/measure_tier_chip.py

READS THE LIVE RECORD AND WRITES NOTHING. It asks each sport for the slate a
reader would actually see -- through `views.week`, the same call the page
makes -- so what it measures is what is on the page rather than a
reconstruction of it.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import calibration, config, db, views  # noqa: E402


def measure_sport(conn, sport: str) -> dict:
    payload = views.week(conn, sport)
    cards = payload.get("cards") or []
    if not cards:
        return {"sport": sport, "cards": 0,
                "message": payload.get("message") or "no slate"}

    by_market: dict[str, dict] = {}
    for card in cards:
        market = card.get("prop_type") or card.get("market_type") or "?"
        tier = card.get("tier") or {}
        entry = by_market.setdefault(market, {
            "cards": 0, "tiers": collections.Counter(), "proven": 0,
            "no_chip": 0, "settled_seen": [],
        })
        entry["cards"] += 1
        name = tier.get("tier")
        if not name:
            entry["no_chip"] += 1
            continue
        entry["tiers"][name] += 1
        if tier.get("proven"):
            entry["proven"] += 1
        entry["settled_seen"].append(tier.get("n") or 0)

    out_markets = {}
    for market, entry in sorted(by_market.items()):
        n = entry["cards"]
        settled = entry["settled_seen"]
        out_markets[market] = {
            "cards": n,
            "tiers": dict(entry["tiers"]),
            "distinct_tiers": len(entry["tiers"]),
            # (2) A chip that never varies is a chip that says nothing.
            "varies": len(entry["tiers"]) > 1,
            "no_chip": entry["no_chip"],
            # (3) The one that matters most.
            "proven": entry["proven"],
            "proven_pct": round(100 * entry["proven"] / n, 1),
            "median_settled_behind_a_chip": (
                sorted(settled)[len(settled) // 2] if settled else 0),
        }

    total = len(cards)
    proven = sum(m["proven"] for m in out_markets.values())
    return {
        "sport": sport,
        "slate": payload.get("week"),
        "cards": total,
        "proven": proven,
        "proven_pct": round(100 * proven / total, 1),
        "markets": out_markets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    conn = db.connect()
    result = {
        "gate": calibration.TIER_MIN_SETTLED,
        "bands": dict(calibration.TIERS),
        "sports": [measure_sport(conn, s) for s in config.SPORTS],
    }
    conn.close()

    live = [s for s in result["sports"] if s.get("cards")]
    result["totals"] = {
        "cards": sum(s["cards"] for s in live),
        "proven": sum(s["proven"] for s in live),
    }
    if result["totals"]["cards"]:
        result["totals"]["proven_pct"] = round(
            100 * result["totals"]["proven"] / result["totals"]["cards"], 1)

    print(json.dumps(result, indent=1))
    print("\nA chip is PROVEN when its own probability bucket holds "
          f"{calibration.TIER_MIN_SETTLED} settled picks. Below that it names "
          "a band and says so; it is not a track record.")
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
