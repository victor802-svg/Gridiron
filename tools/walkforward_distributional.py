"""THE TEST THAT DECIDES WHETHER THE REDESIGN SHIPS.

`docs/DISTRIBUTIONAL.md` §7, and its clause:

    The change ships only if the distributional read-out is better calibrated
    than the current rung method, measured on identical games, walk-forward,
    and labelled sanity only.

    If it is not better, it does not ship, and this document is the record of
    a hypothesis the evidence refused.

PER SPORT (operator ruling, 2026-09-04). LAW 6 makes each sport its own
decision, and sports are never averaged to reach a verdict. A sport that
passes ships; a sport that fails stays on rungs with its verdict dated.

WHAT IS COMPARED, on identical games:

    method A (today)      "over OUR rung", fitted logistic
    method B (proposed)   "over THE MARKET'S line", Phi((mu - line) / sigma)

Both trained on seasons <= T and tested on T+1. They are NOT the same
question, which is why Brier is reported as context and CALIBRATION is the
decidable metric: a method that says 70% and is right 70% of the time is
calibrated whatever its Brier, and calibration is comparable across questions
in a way Brier is not.

    python tools/walkforward_distributional.py --sport nfl --market total

THIS WRITES NOTHING TO `predictions`. It reads the record, computes both
methods on completed games, and prints. That is the whole point of it being a
separate script run before the schema exists: building the schema first would
make the test a formality that nobody wants to fail.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import config, db  # noqa: E402
from gridiron.factors import compute  # noqa: E402
from gridiron.model import baseline, questions  # noqa: E402

#: The buckets calibration already uses, so the gap is measured the way the
#: record measures it rather than by a second definition.
BUCKETS = ((0.5, 0.6, "50-60%"), (0.6, 0.7, "60-70%"),
           (0.7, 0.8, "70-80%"), (0.8, 1.01, "80%+"))

#: §7's PIT gate: ten bins want ten times a bucket's minimum before the shape
#: means anything.
PIT_MIN = config.MIN_SAMPLE_FOR_BUCKET_POINT * 10
PIT_BINS = 10
#: §7's flatness rule: no decile more than 50% above or below uniform.
PIT_TOLERANCE = 0.50


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def brier(probs, labels) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def folded(p: float) -> float:
    """A probability read from the side the model would actually claim."""
    return p if p >= 0.5 else 1.0 - p


def calibration(probs, labels) -> dict:
    """Weighted mean |claimed - actual| across the declared buckets.

    ON THE CLAIMED SIDE, not on "over". A model that says 20% over is claiming
    80% under, and grading it as a 20% claim would call a confident correct
    call a miss. This is how the record already reads a sub-50 probability.
    """
    rows = []
    total = 0
    weighted = 0.0
    for lo, hi, label in BUCKETS:
        items = [(folded(p), y if p >= 0.5 else 1 - y)
                 for p, y in zip(probs, labels) if lo <= folded(p) < hi]
        if not items:
            rows.append({"bucket": label, "n": 0})
            continue
        n = len(items)
        claimed = sum(p for p, _ in items) / n
        actual = sum(y for _, y in items) / n
        rows.append({"bucket": label, "n": n,
                     "claimed": round(claimed, 4), "actual": round(actual, 4),
                     "gap_pts": round((actual - claimed) * 100, 2)})
        total += n
        weighted += n * abs(actual - claimed)
    return {
        "buckets": rows,
        "n": total,
        "weighted_gap_pts": round(100 * weighted / total, 4) if total else None,
    }


def pit(us: list[float]) -> dict:
    """Is the distribution honest about its own width?

    `u = Phi((y - mu) / sigma)` is uniform when the forecast is honest.
    U-shaped means too narrow, n-shaped too wide, sloped means biased.
    """
    n = len(us)
    if n == 0:
        return {"n": 0}
    counts = [0] * PIT_BINS
    for u in us:
        counts[min(int(u * PIT_BINS), PIT_BINS - 1)] += 1
    expected = n / PIT_BINS
    worst = max(abs(c - expected) / expected for c in counts)
    return {
        "n": n,
        "bins": counts,
        "expected_per_bin": round(expected, 1),
        "worst_deviation": round(worst, 4),
        "gate": PIT_MIN,
        "provisional": n < PIT_MIN,
        "flat": bool(n >= PIT_MIN and worst <= PIT_TOLERANCE),
    }


def _expectation(conn, sport, market, game_id, cache):
    """(expectation, actual) for one game, through the sport's own builder."""
    if sport == "nfl":
        from gridiron.factors import context
        ctx = context.build_game_context(conn, game_id, cache)
        if market == "total":
            return ctx, questions.nfl_expected_total(
                ctx.home_points_for, ctx.home_points_against,
                ctx.away_points_for, ctx.away_points_against)
        return ctx, questions.expected_margin("nfl", ctx.home_srs, ctx.away_srs)
    if sport == "nba":
        from gridiron.sports import nba as _nba
        ctx = _nba.build_context(conn, game_id)
        if market == "total":
            return ctx, ctx.expected_total
        return ctx, questions.expected_margin(
            "nba", getattr(ctx, "home_srs", None), getattr(ctx, "away_srs", None))
    raise ValueError(f"no expectation path for {sport}:{market}")


def _rung(sport, market, expectation, game_id):
    """Method A's question: the ladder point nearest our own expectation."""
    if expectation is None:
        return None
    try:
        if market == "total":
            return (questions.nfl_total_asked(expectation) if sport == "nfl"
                    else questions.nba_total_asked(expectation))
        # EACH SPORT ON ITS OWN LADDER, read from the sport module that
        # declares it rather than from a copy here. Routing the NBA through
        # football's ladder would undo a deliberate choice and would flatter
        # method A on the very games the comparison is about.
        ladder = None
        if sport == "nba":
            from gridiron.sports import nba as _nba_mod
            ladder = _nba_mod.SPREAD_LADDER
        return questions.spread_rung(game_id, expectation, ladder)
    except Exception:                                             # noqa: BLE001
        return None


def run(conn: sqlite3.Connection, sport: str, market: str,
        splits: list[int]) -> dict:
    sd = questions.forecast_spread(sport, market)
    seasons = config.SPORT_LOAD_SEASONS[sport]
    a_probs, a_labels, b_probs, b_labels, pits = [], [], [], [], []
    ours_err, theirs_err = [], []
    per_split = []

    for through in splits:
        test_season = through + 1
        fit = baseline.train(conn, market, seasons, sport=sport,
                             through_season=through, l2=2.0)
        games = conn.execute(
            "SELECT g.id, g.home_score, g.away_score, m.total_line, m.spread_line"
            "  FROM games g JOIN ("
            "       SELECT game_id, MIN(fetched_utc) AS f FROM market_lines_raw"
            "        GROUP BY game_id) first ON first.game_id = g.id"
            "  JOIN market_lines_raw m ON m.game_id = g.id AND m.fetched_utc = first.f"
            " WHERE g.sport = ? AND g.season = ? AND g.status = 'final'"
            "   AND g.home_score IS NOT NULL"
            + (" AND g.game_type = 'REG'" if sport == "nfl" else "")
            + " ORDER BY g.id", (sport, test_season)).fetchall()

        from gridiron.factors import context as _context
        cache = _context.WeekCache()
        used = 0
        for g in games:
            line = g["total_line"] if market == "total" else g["spread_line"]
            if line is None:
                continue
            try:
                ctx, expectation = _expectation(conn, sport, market, g["id"], cache)
            except Exception:                                     # noqa: BLE001
                continue
            if expectation is None:
                continue
            rung = _rung(sport, market, expectation, g["id"])
            if rung is None:
                continue

            # --- method A: our rung, fitted logistic -----------------------
            ctx.line_asked = rung
            if market == "total":
                setattr(ctx, "expected_total", expectation)
            try:
                features = compute.feature_vector(ctx, market).values
            except Exception:                                     # noqa: BLE001
                continue
            pa = fit.predict(features)
            if market == "total":
                la = questions.total_outcome(g["home_score"], g["away_score"], rung)
            else:
                la = questions.spread_outcome(g["home_score"], g["away_score"], rung)

            # --- method B: the market's line, read off the distribution ----
            if market == "total":
                actual = g["home_score"] + g["away_score"]
                pb = phi((expectation - float(line)) / sd)
                lb = questions.total_outcome(g["home_score"], g["away_score"],
                                             float(line))
            else:
                actual = g["home_score"] - g["away_score"]
                # `spread_line` is the expected HOME MARGIN, so the handicap
                # the home side is given is its negative.
                pb = phi((expectation - float(line)) / sd)
                lb = questions.spread_outcome(g["home_score"], g["away_score"],
                                              -float(line))

            a_probs.append(pa); a_labels.append(la)
            b_probs.append(pb); b_labels.append(lb)
            pits.append(phi((actual - expectation) / sd))
            # DIAGNOSTIC ONLY, and it decides nothing. Whose number lands
            # nearer the result -- ours or theirs. It is here because it is
            # the first thing anybody will ask if method B loses, and the
            # answer should not require a second script.
            ours_err.append(abs(actual - expectation))
            theirs_err.append(abs(actual - float(line)))
            used += 1

        per_split.append({"trained_through": through, "tested": test_season,
                          "games": len(games), "used": used,
                          "fit_n": fit.n, "converged": fit.converged})

    if not a_probs:
        return {"sport": sport, "market": market, "verdict": "NOT RUN",
                "why": "no test game carried both a stored line and an "
                       "expectation the model could form",
                "splits": per_split}

    n = len(a_probs)
    base_a = sum(a_labels) / n
    base_b = sum(b_labels) / n
    cal_a = calibration(a_probs, a_labels)
    cal_b = calibration(b_probs, b_labels)
    pit_b = pit(pits)

    better = (cal_b["weighted_gap_pts"] is not None
              and cal_a["weighted_gap_pts"] is not None
              and cal_b["weighted_gap_pts"] <= cal_a["weighted_gap_pts"])
    verdict = "SHIP" if (better and pit_b["flat"]) else "DO NOT SHIP"

    return {
        "sport": sport,
        "market": market,
        "forecast_sd": sd,
        "n": n,
        "splits": per_split,
        "method_a": {
            "question": "over our rung",
            "base_rate": round(base_a, 4),
            "brier": round(brier(a_probs, a_labels), 4),
            "edge_over_base": round(base_a * (1 - base_a)
                                    - brier(a_probs, a_labels), 4),
            "reach_70_pct": round(
                100 * sum(1 for p in a_probs if p >= 0.7 or p <= 0.3) / n, 2),
            "calibration": cal_a,
        },
        "method_b": {
            "question": "over the market's line",
            "base_rate": round(base_b, 4),
            "brier": round(brier(b_probs, b_labels), 4),
            "edge_over_base": round(base_b * (1 - base_b)
                                    - brier(b_probs, b_labels), 4),
            "reach_70_pct": round(
                100 * sum(1 for p in b_probs if p >= 0.7 or p <= 0.3) / n, 2),
            "calibration": cal_b,
            "pit": pit_b,
        },
        # NOT PART OF THE DECISION RULE. §7 fixed the rule before the
        # numbers arrived and no condition is added after them.
        "diagnostic_whose_number_is_closer": {
            "our_mean_abs_error": round(sum(ours_err) / n, 3),
            "market_mean_abs_error": round(sum(theirs_err) / n, 3),
            "market_closer_share_pct": round(
                100 * sum(1 for o, t in zip(ours_err, theirs_err) if t < o) / n, 2),
        },
        "better_calibrated": better,
        "pit_flat": pit_b["flat"],
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sport", required=True)
    parser.add_argument("--market", required=True, choices=["total", "spread"])
    parser.add_argument("--splits", default="",
                        help="comma-separated 'trained through' seasons")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    if args.splits:
        splits = [int(s) for s in args.splits.split(",") if s.strip()]
    else:
        seasons = sorted(config.SPORT_LOAD_SEASONS[args.sport])
        # Every season that has a season after it in the loaded range, minus
        # the first two, which are needed to have anything to fit on.
        splits = [s for s in seasons[2:-1]][-2:]

    conn = db.connect()
    result = run(conn, args.sport, args.market, splits)
    conn.close()

    print(json.dumps(result, indent=1))
    print("\nLABELLED SANITY ONLY. This is a retrospective comparison on "
          "completed games, not evidence of an edge.")
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
