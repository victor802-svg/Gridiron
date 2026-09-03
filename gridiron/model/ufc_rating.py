"""A fighter rating, computed walk-forward from results only.

WHY A RATING AT ALL. Team sports in this record have a points differential to
adjust — SRS for football, net rating for basketball. A fight has no score: it
has a winner. Elo is the plainest instrument that turns a sequence of winners
into a number, and it is used here for that reason rather than because it is
clever.

WALK-FORWARD, AND THE LEAK THIS AVOIDS. A rating is stored per bout as the
rating each fighter carried INTO it, computed from bouts strictly before it.
A rating recomputed at read time would have seen the result it is being used to
predict, which is the same leak the rolling windows in every other sport are
shaped to avoid — and which cost this project a real defect when a game was let
into its own window for 76.8% of NBA rows.

K IS FITTED, NOT CHOSEN, and this module says so where a reader will see it.
`fit_k` sweeps a declared list of candidates, scores each by Brier on HELD-OUT
bouts, and reports the winner with its margin. That makes K a fitted constant
rather than a judgement, and it is recorded as one: `K_DECLARED` carries the
date and the sample it was fitted on. Nothing here searches over anything else.
"""

from __future__ import annotations

import sqlite3

from ..db import utcnow

#: Where every fighter starts. The value is arbitrary and cancels: only
#: differences between ratings are ever read, so 1500 is convention rather
#: than a claim about anybody.
START = 1500.0

#: How much a rating difference is worth, in the logistic Elo sense. 400 is
#: the standard scale and is NOT fitted -- changing it is the same act as
#: rescaling K, so fitting both would be fitting one thing twice.
SCALE = 400.0

#: The candidates `fit_k` sweeps. Declared in advance (LAW 2's habit applied
#: to a constant rather than a factor): a sweep with an open range is a search,
#: and a search over outcomes is how a model becomes confidently wrong.
#:
#: THE RANGE REACHES PAST ITS OWN OPTIMUM, DELIBERATELY. The first version
#: stopped at 48 and 48 won -- which is not a fitted constant, it is a clamped
#: one, and a value sitting at the edge of its own candidate list has told you
#: only that the list was too short. Extending it found the turn at 80, with
#: 96 and 120 worse on both sides. A sweep whose winner is its last entry is
#: not a measurement.
K_CANDIDATES: tuple[float, ...] = (
    8.0, 16.0, 24.0, 32.0, 40.0, 48.0, 56.0, 64.0, 80.0, 96.0, 120.0, 160.0,
    200.0,
)

#: THE FITTED K, and what it is worth.
#:
#: Fitted 2026-09-03 over 2,445 decided bouts from the 2022-2026 cards, graded
#: on the 1,091 where both fighters had at least two prior bouts. K=80 has the
#: lowest held-out Brier, 0.2364, and the curve turns over on both sides.
#:
#: WHAT IT IS WORTH, STATED PLAINLY, because a fitted number invites more faith
#: than it has earned. Always saying 0.5 scores 0.2500. The best K scores
#: 0.2364 -- an edge of 0.0136 -- and the ENTIRE sweep from K=8 to K=200 spans
#: 0.0119. So the choice of K is worth about as much as having a rating at all
#: is worth, and neither is worth much: the rating calls about 60% of decided
#: bouts. That is a real signal and a small one, and the market will beat it.
K_FITTED = 80.0
K_DECLARED = "2026-09-03T00:00:00Z"


def expected(rating_a: float, rating_b: float) -> float:
    """The probability A beats B, on the Elo curve. No home advantage.

    THERE IS NO HOME SIDE IN A FIGHT. Every other sport in this record carries
    a home-field term; adding one here would be inventing an effect to match
    the shape of the other sports' code.
    """
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / SCALE))


def _decided(bout: sqlite3.Row) -> bool:
    """Whether this bout moves a rating at all.

    A DRAW OR NO CONTEST MOVES NOTHING. The moneyline is void for those bouts
    (docs/UFC_FEASIBILITY.md section 6), and a rating that treated a no contest
    as half a win would be reading a result out of a bout that had none.
    """
    return bool(bout["winner"])


def walk_forward(conn: sqlite3.Connection, k: float,
                 *, store: bool = False) -> list[dict]:
    """Every decided bout in time order, with the ratings carried into it.

    Returns one dict per bout: the two ratings BEFORE it, how many bouts each
    fighter had already had, and what happened. `store=True` writes the
    ratings to `ufc_ratings`; the fitting path leaves it False so a sweep
    never touches the record.
    """
    bouts = conn.execute(
        "SELECT id, bout_utc, fighter_a, fighter_b, winner FROM ufc_bouts"
        " WHERE status = 'final' AND bout_utc IS NOT NULL"
        " ORDER BY bout_utc, id").fetchall()

    rating: dict[str, float] = {}
    fought: dict[str, int] = {}
    out: list[dict] = []
    rows: list[tuple] = []
    stamp = utcnow()

    for bout in bouts:
        a, b = bout["fighter_a"], bout["fighter_b"]
        ra = rating.get(a, START)
        rb = rating.get(b, START)
        na = fought.get(a, 0)
        nb = fought.get(b, 0)

        if _decided(bout):
            out.append({
                "bout_id": bout["id"],
                "when": bout["bout_utc"],
                "rating_a": ra, "rating_b": rb,
                "bouts_a": na, "bouts_b": nb,
                "a_won": 1 if bout["winner"] == a else 0,
                "expected_a": expected(ra, rb),
            })

        if store:
            rows.append((bout["id"], a, ra, na, k, stamp))
            rows.append((bout["id"], b, rb, nb, k, stamp))

        if not _decided(bout):
            continue

        score_a = 1.0 if bout["winner"] == a else 0.0
        exp_a = expected(ra, rb)
        rating[a] = ra + k * (score_a - exp_a)
        rating[b] = rb + k * ((1.0 - score_a) - (1.0 - exp_a))
        fought[a] = na + 1
        fought[b] = nb + 1

    if store:
        conn.executemany(
            "INSERT INTO ufc_ratings (bout_id, fighter_id, rating_before,"
            " bouts_before, k_factor, computed_utc) VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(bout_id, fighter_id) DO UPDATE SET"
            "   rating_before = excluded.rating_before,"
            "   bouts_before = excluded.bouts_before,"
            "   k_factor = excluded.k_factor,"
            "   computed_utc = excluded.computed_utc", rows)
        conn.commit()
    return out


def fit_k(conn: sqlite3.Connection, *, warmup: int = 2) -> dict:
    """Which K predicts held-out bouts best. A FITTED CONSTANT, reported.

    `warmup` excludes a fighter's first bouts from scoring, because a rating
    that has seen two fights is a starting value with noise on it, not a
    measurement — including them scores the prior rather than the model.
    Those bouts still MOVE the ratings; they are simply not graded.

    Scored by Brier on the held-out set, which is the same measure the
    scorecard uses, so a K chosen here and a curve read later are not two
    different notions of "better".
    """
    results = []
    for k in K_CANDIDATES:
        rows = walk_forward(conn, k)
        graded = [r for r in rows
                  if r["bouts_a"] >= warmup and r["bouts_b"] >= warmup]
        if not graded:
            continue
        brier = sum((r["expected_a"] - r["a_won"]) ** 2 for r in graded) / len(graded)
        hit = sum(1 for r in graded
                  if (r["expected_a"] >= 0.5) == bool(r["a_won"])) / len(graded)
        results.append({"k": k, "brier": round(brier, 6),
                        "hit_rate": round(hit, 4), "n": len(graded)})

    if not results:
        return {"k": None, "n": 0, "candidates": [],
                "note": "no bout cleared the warm-up; nothing was fitted"}

    results.sort(key=lambda r: r["brier"])
    best, runner = results[0], (results[1] if len(results) > 1 else None)
    return {
        "k": best["k"],
        "n": best["n"],
        "brier": best["brier"],
        "hit_rate": best["hit_rate"],
        # THE MARGIN IS REPORTED because a sweep that wins by 0.0001 has
        # chosen nothing, and a reader is entitled to see that rather than a
        # single number wearing the authority of a measurement.
        "margin_over_runner_up": (round(runner["brier"] - best["brier"], 6)
                                  if runner else None),
        "runner_up_k": runner["k"] if runner else None,
        "candidates": results,
        "warmup": warmup,
    }
