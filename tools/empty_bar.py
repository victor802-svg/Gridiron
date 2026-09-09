"""How often nothing cleared the venue's fee — in two spans, before and after.

    .venv\\Scripts\\python.exe tools\\empty_bar.py

WHY TWO SPANS AND NOT ONE (operator ruling, 2026-09-09). The shortlist now
ranks priceable questions first, so a slate chosen before that date and a slate
chosen after it are not the same measurement: before, a day's thirty places
could be spent on questions the venue does not list, and nothing on that day
could clear a bar it was never priced against. Averaging the two spans would
report the ranker's old shape as if it were the market's behaviour.

WHAT A DAY IS, and the definition matters more than the number:

  * A DAY COUNTS when the record holds at least one at-the-line claim created
    that day for that sport. That is the day the bar could have been tested --
    the model's frozen number read at the venue's price. A day with no claim
    is a day nothing was measured, which is a different fact and is reported
    separately rather than folded in as an empty one.

  * A DAY IS EMPTY when it counted and no recommendation was written. The bar
    was testable and nothing cleared it.

Read on 21 September with `docs/READINESS.md`. The headline it answers: how
often does a real edge appear -- and whether ranking priceable questions first
changed that, which is the only way to tell whether the ruling helped or
merely rearranged the screen.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import config, db  # noqa: E402


def spans(conn, sport: str) -> dict:
    """Countable days and empty days, split at `config.PRICEABLE_FIRST_FROM`."""
    split = config.PRICEABLE_FIRST_FROM
    claim_days = {
        r[0] for r in conn.execute(
            "SELECT DISTINCT substr(created_utc, 1, 10) FROM at_the_line_claims"
            " WHERE sport = ?", (sport,))
    }
    rec_days = {
        r[0] for r in conn.execute(
            "SELECT DISTINCT substr(created_utc, 1, 10) FROM recommendations"
            " WHERE sport = ?", (sport,))
    }
    out = {"sport": sport, "split_on": split, "spans": []}
    for name, days in (("before " + split, {d for d in claim_days if d < split}),
                       ("from " + split, {d for d in claim_days if d >= split})):
        empty = sorted(d for d in days if d not in rec_days)
        out["spans"].append({
            "span": name,
            "days_the_bar_could_be_tested": len(days),
            "days_nothing_cleared": len(empty),
            "empty_days": empty,
        })
    return out


def main() -> int:
    conn = db.read_the_live_record(
        "the empty-bar count for the 21 September reading, in two spans "
        "either side of the priceable-first ruling")
    print("EMPTY TOP GROUP — how often nothing cleared the venue's fee")
    print(f"split on {config.PRICEABLE_FIRST_FROM}, the priceable-first ruling")
    print()
    for sport in config.SPORTS:
        report = spans(conn, sport)
        rows = [s for s in report["spans"] if s["days_the_bar_could_be_tested"]]
        if not rows:
            print(f"{sport:6} no day yet on which the bar could be tested")
            continue
        print(f"{sport}:")
        for s in report["spans"]:
            n = s["days_the_bar_could_be_tested"]
            if not n:
                print(f"  {s['span']:22} no day the bar could be tested")
                continue
            print(f"  {s['span']:22} {s['days_nothing_cleared']} of {n} days "
                  f"cleared nothing"
                  + (f"  ({', '.join(s['empty_days'])})" if s["empty_days"] else ""))
        print()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
