"""Measure the MODEL's own forecast: its bias, its spread, and its shape.

Run this, paste the output into `gridiron/model/questions.py`, and date it. A
tool rather than a runtime computation, for the reason `measure_margin_sd.py`
gives: a constant that recomputes itself from whatever data happens to be
loaded is a constant that changes silently, and every probability derived from
it changes with it.

    python tools/measure_forecast_spread.py            # every sport
    python tools/measure_forecast_spread.py --sport cfb --fit

THIS IS NOT `market.lines.MARGIN_SD_BY_SPORT` OR `TOTAL_SD_BY_SPORT`. Those
hold SD(actual - THE MARKET'S line) and exist for the market comparison. This
is SD(actual - THE MODEL'S expectation) -- a different and generally wider
quantity, and confusing the two is the mistake that produced a false
4.71-versus-4.534 discrepancy in the run-line probe.

`--fit` additionally regresses the actual on the expectation by least squares,
which is what CFB's total needed: `docs/DISTRIBUTIONAL.md` §1 measured a
-1.93 point bias whose size moves with the expectation, exactly the defect the
CFB MARGIN had before `EXPECTED_MARGIN_FIT` measured its slope on 2026-09-03.
Calibrating the instrument that chooses the question is not factor discovery
(LAW 2); it is the same act, carried one market further.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import config, db  # noqa: E402
from gridiron.model import questions  # noqa: E402

#: Normal reference points, so the coverage columns read against something.
NORMAL = {"1sd": 68.27, "90": 90.0, "95": 95.0, "99": 99.0, "beyond3": 0.27}


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def shape(resid: list[float]) -> dict:
    """Bias, spread and the two shape numbers that decide the family."""
    n = len(resid)
    if n < 30:
        return {"n": n, "error": "too few rows to measure"}
    mean = sum(resid) / n
    var = sum((x - mean) ** 2 for x in resid) / (n - 1)
    sd = math.sqrt(var)
    z = [(x - mean) / sd for x in resid]
    return {
        "n": n,
        "bias": round(mean, 4),
        "sd": round(sd, 4),
        "skew": round(sum(v ** 3 for v in z) / n, 4),
        "excess_kurtosis": round(sum(v ** 4 for v in z) / n - 3.0, 4),
        "cover_1sd": round(100 * sum(1 for v in z if abs(v) <= 1.0) / n, 2),
        "cover_95": round(100 * sum(1 for v in z if abs(v) <= 1.96) / n, 2),
        "cover_99": round(100 * sum(1 for v in z if abs(v) <= 2.5758) / n, 2),
        "beyond_3sd_pct": round(100 * sum(1 for v in z if abs(v) > 3.0) / n, 3),
    }


def least_squares(xs: list[float], ys: list[float]) -> dict:
    """`y = intercept + slope * x`, and the spread that remains after it.

    Two numbers, declared in advance and dated, with no search over variants --
    the same act as `EXPECTED_MARGIN_FIT`.
    """
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return {"n": n, "error": "the expectation never varies"}
    slope = sxy / sxx
    intercept = my - slope * mx
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    ss_res = sum(r ** 2 for r in resid)
    ss_tot = sum((y - my) ** 2 for y in ys)
    out = {
        "n": n,
        "intercept": round(intercept, 4),
        "slope": round(slope, 4),
        "r2": round(1 - ss_res / ss_tot, 4) if ss_tot else None,
        "resid_sd": round(math.sqrt(ss_res / (n - 2)), 4),
    }
    out["after_fit"] = shape(resid)
    return out


def pairs(conn, sport: str, quantity: str) -> tuple[list[float], list[float]]:
    """(expectation, actual) for every completed game the model can answer.

    Built through each sport's OWN context builder, so what is measured is the
    number the model would actually have produced rather than a re-derivation
    that might differ.
    """
    expects: list[float] = []
    actuals: list[float] = []

    if sport == "nfl":
        from gridiron.factors import context
        cache = context.WeekCache()
        games = conn.execute(
            "SELECT id, home_score, away_score FROM games"
            " WHERE sport='nfl' AND status='final' AND game_type='REG'"
            "   AND home_score IS NOT NULL ORDER BY season, week, id").fetchall()
        for g in games:
            ctx = context.build_game_context(conn, g["id"], cache)
            if quantity == "total":
                e = questions.nfl_expected_total(
                    ctx.home_points_for, ctx.home_points_against,
                    ctx.away_points_for, ctx.away_points_against)
                a = g["home_score"] + g["away_score"]
            else:
                e = questions.expected_margin("nfl", ctx.home_srs, ctx.away_srs)
                a = g["home_score"] - g["away_score"]
            if e is not None:
                expects.append(float(e))
                actuals.append(float(a))
        return expects, actuals

    if sport == "nba":
        from gridiron.sports import nba as _nba
        games = conn.execute(
            "SELECT id, home_score, away_score FROM games"
            " WHERE sport='nba' AND status='final' AND home_score IS NOT NULL"
            " ORDER BY season, week, id").fetchall()
        for g in games:
            try:
                ctx = _nba.build_context(conn, g["id"])
            except Exception:                                     # noqa: BLE001
                continue
            if quantity == "total":
                e, a = ctx.expected_total, g["home_score"] + g["away_score"]
            else:
                e = questions.expected_margin(
                    "nba", getattr(ctx, "home_srs", None),
                    getattr(ctx, "away_srs", None))
                a = g["home_score"] - g["away_score"]
            if e is not None:
                expects.append(float(e))
                actuals.append(float(a))
        return expects, actuals

    if sport == "cfb":
        from gridiron.sports import cfb as _cfb
        games = conn.execute(
            "SELECT id, home_score, away_score FROM games"
            " WHERE sport='cfb' AND status='final' AND home_score IS NOT NULL"
            " ORDER BY season, week, id").fetchall()
        for g in games:
            try:
                ctx = _cfb.build_context(conn, g["id"])
            except Exception:                                     # noqa: BLE001
                continue
            if quantity == "total":
                hf = (getattr(ctx, "home_form", None) or {}).get("for_pg")
                af = (getattr(ctx, "away_form", None) or {}).get("for_pg")
                e = None if hf is None or af is None else float(hf) + float(af)
                a = g["home_score"] + g["away_score"]
            else:
                e = questions.cfb_expected_margin(
                    getattr(ctx, "home_rating", None),
                    getattr(ctx, "away_rating", None))
                a = g["home_score"] - g["away_score"]
            if e is not None:
                expects.append(float(e))
                actuals.append(float(a))
        return expects, actuals

    raise ValueError(f"no expectation path measured for {sport!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sport", default="")
    parser.add_argument("--quantity", default="", choices=["", "total", "margin"])
    parser.add_argument("--fit", action="store_true",
                        help="also regress actual on expectation (least squares)")
    args = parser.parse_args()

    sports = [args.sport] if args.sport else ["nfl", "nba", "cfb"]
    quantities = [args.quantity] if args.quantity else ["total", "margin"]

    conn = db.connect()
    out: dict = {}
    for sport in sports:
        for quantity in quantities:
            try:
                expects, actuals = pairs(conn, sport, quantity)
            except Exception as exc:                              # noqa: BLE001
                out[f"{sport}:{quantity}"] = {"error": f"{type(exc).__name__}: {exc}"}
                continue
            entry = {"raw": shape([a - e for e, a in zip(expects, actuals)])}
            if args.fit and len(expects) >= 30:
                entry["least_squares"] = least_squares(expects, actuals)
            out[f"{sport}:{quantity}"] = entry
            print(f"{sport}:{quantity} {json.dumps(entry, indent=1)}", flush=True)
    conn.close()

    print("\nNormal reference: " + json.dumps(NORMAL))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
