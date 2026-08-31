"""Adjusting the model's claims by what claims like them have been worth.

A forecaster that says 70% and is right 62% of the time is not broken. It is
MISCALIBRATED, which is a measurable and correctable fact — and correcting it
is the difference between a number that sounds confident and a number that has
earned its confidence.

PLATT SCALING, and why not isotonic
===================================
Two parameters, fitted on the claim's log-odds:

    corrected = sigmoid(slope * logit(claim) + intercept)

Isotonic regression is the obvious alternative and is more flexible: it fits an
arbitrary monotone step function rather than a straight line in log-odds. That
flexibility is exactly the problem here. A category becomes eligible at fifty
settled predictions, and at fifty rows isotonic fits the noise — it will
happily produce a step saying every claim between 68% and 71% is worth 100%,
because the four rows in that bin happened to win. Two parameters cannot do
that. They can only stretch and shift the whole curve, which is the shape
miscalibration actually takes: a forecaster is systematically overconfident or
systematically shy, across the range, not in one bin.

`slope < 1` is the common case and means overconfident claims pulled toward the
middle. `slope > 1` means the model is shy and its claims are worth more than
it says.

WHAT THIS MODULE MAY TOUCH
==========================
`predictions` — its claims, its outcomes, its resolution timestamps — and
`prediction_voids`, to exclude the terminal ones. NOTHING ELSE. Not `games`,
not `market_snapshots`, not a line, not a score. `audit.check_correction_is_
isolated` reads the SQL in this file and fails by name on any other table,
because a correction fitted against anything but the record's own claims and
outcomes is no longer a correction — it is a second model, fitted on the
outcome, wearing a calibration label.

The same scan requires every training query to bound itself in time. A
correction fitted on rows that resolved after it was fitted has seen its own
future, and every figure downstream of it would be a claim about data it was
built from.

APPLIED AT WRITE TIME, NEVER RETROACTIVELY
==========================================
A prediction records what was claimed when it was made. Recomputing an old
row's number under a new correction would rewrite the record to make it look
better, which is what LAW 3 exists to prevent, so corrections reach only
predictions written after they activate. The version is stored on the row,
which is what makes a correction gradeable: "did v1 help" is answerable with an
N, over the forward predictions written under v1.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

from . import config
from .db import utcnow

#: A claim is squeezed inside this before its log-odds is taken. A stored
#: probability of exactly 0 or 1 has infinite log-odds and would take the fit
#: with it; the model does not produce them today, and this is here so that a
#: model that someday does fails visibly rather than silently.
EPS = 1e-6

#: Below this many settled predictions a category has no correction (C2's gate
#: lives here so the engine and the interface read one number).
MIN_TRAIN = 50


@dataclass
class Platt:
    """Two numbers and what they were fitted on."""

    slope: float
    intercept: float
    n_train: int
    brier_raw: float | None = None
    brier_corrected: float | None = None

    def apply(self, claim: float) -> float:
        return _sigmoid(self.slope * _logit(claim) + self.intercept)


def _logit(p: float) -> float:
    p = min(max(float(p), EPS), 1.0 - EPS)
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def category_of(sport: str, market_type: str, forecaster: str) -> tuple[str, str, str]:
    """The unit a correction is fitted for. Never merged (LAW 6).

    A slope fitted across two sports describes neither, and one fitted across
    two forecasters lets the better flatter the worse -- the same reasoning as
    the scorecard's categories, applied to the correction.
    """
    config.require_sport(sport, "correction.category_of")
    if not market_type or not forecaster:
        raise ValueError(
            "a correction category is (sport, market_type, forecaster); "
            f"got market_type={market_type!r} forecaster={forecaster!r}"
        )
    return (sport, market_type, forecaster)


def training_rows(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str,
    forecaster: str,
    before_utc: str,
) -> list[tuple[float, int, str]]:
    """(claim, outcome, resolved_utc) for one category, resolved before a time.

    THE TIME BOUND IS THE POINT. `before_utc` is the moment the fit is being
    made for, and only rows already settled by then may train it. Without that
    the correction sees results that had not happened when it was fitted, and
    the holdout check in C2 -- which fits on the earliest 80% and tests on the
    latest 20% -- would be testing on rows it had trained on.

    Voids are excluded because a void is terminal: it has no outcome, and
    counting one as a loss would train the correction on a roster decision.
    """
    return [
        (row["model_prob"], int(row["outcome"]), row["resolved_utc"])
        for row in conn.execute(
            "SELECT p.model_prob, p.outcome, p.resolved_utc FROM predictions p"
            " WHERE p.sport = ? AND p.market_type = ? AND p.predictor = ?"
            "   AND p.resolved_utc IS NOT NULL"
            "   AND p.outcome IS NOT NULL"
            "   AND p.resolved_utc < ?"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)"
            " ORDER BY p.resolved_utc, p.id",
            (sport, market_type, forecaster, before_utc),
        )
    ]


def fit_platt(rows: list[tuple[float, int, str]], *, l2: float = 1.0,
              max_iterations: int = 60, tol: float = 1e-9) -> Platt | None:
    """Newton–Raphson on two parameters. Returns None when there is nothing to fit.

    Written out rather than delegated to `model.logistic` because that fitter
    carries missingness bookkeeping, per-factor presence and dropping rules
    that mean nothing here: there is exactly one feature, it is present on
    every row by construction, and the ridge exists only to keep a separable
    category from running the slope to infinity.

    A category where every outcome is the same is SEPARABLE -- any large slope
    fits it perfectly -- and it returns None rather than a huge coefficient
    that would look like a strong correction and is really an absence of
    counter-examples.
    """
    if not rows:
        return None
    labels = {int(y) for _p, y, _t in rows}
    if len(labels) < 2:
        return None

    xs = [_logit(p) for p, _y, _t in rows]
    ys = [float(y) for _p, y, _t in rows]

    slope, intercept = 1.0, 0.0
    for _ in range(max_iterations):
        # Gradient and Hessian of the penalised log-likelihood, by hand: two
        # parameters make this six sums and a 2x2 solve, which is inspectable
        # in a way a matrix library is not.
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, ys):
            p = _sigmoid(slope * x + intercept)
            r = y - p
            w = p * (1.0 - p)
            g0 += r * x
            g1 += r
            h00 += w * x * x
            h01 += w * x
            h11 += w
        g0 -= l2 * slope
        h00 += l2

        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            break
        d_slope = (h11 * g0 - h01 * g1) / det
        d_intercept = (h00 * g1 - h01 * g0) / det
        slope += d_slope
        intercept += d_intercept
        if abs(d_slope) < tol and abs(d_intercept) < tol:
            break

    model = Platt(slope=slope, intercept=intercept, n_train=len(rows))
    model.brier_raw = brier([p for p, _y, _t in rows], [y for _p, y, _t in rows])
    model.brier_corrected = brier(
        [model.apply(p) for p, _y, _t in rows], [y for _p, y, _t in rows]
    )
    return model


def brier(probs: list[float], outcomes: list[float]) -> float | None:
    if not probs:
        return None
    return round(
        sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs), 6
    )


def active_correction(
    conn: sqlite3.Connection, *, sport: str, market_type: str, forecaster: str,
    at_utc: str | None = None,
) -> sqlite3.Row | None:
    """The correction in force for a category, or None while it is still raw.

    `active_from` NULL means fitted but inert: a fit can be recorded and read
    without touching a single claim, which is what makes C2's gate a decision
    rather than a side effect of fitting.
    """
    now = at_utc or utcnow()
    return conn.execute(
        "SELECT * FROM calibration_corrections"
        " WHERE sport = ? AND market_type = ? AND forecaster = ?"
        "   AND active_from IS NOT NULL AND active_from <= ?"
        " ORDER BY version DESC LIMIT 1",
        (sport, market_type, forecaster, now),
    ).fetchone()


def next_version(conn: sqlite3.Connection, *, sport: str, market_type: str,
                 forecaster: str) -> int:
    row = conn.execute(
        "SELECT MAX(version) AS v FROM calibration_corrections"
        " WHERE sport = ? AND market_type = ? AND forecaster = ?",
        (sport, market_type, forecaster),
    ).fetchone()
    return int((row["v"] or 0)) + 1


def record_fit(
    conn: sqlite3.Connection, *, sport: str, market_type: str, forecaster: str,
    model: Platt | None, status: str, active_from: str | None = None,
    holdout: dict | None = None, fitted_utc: str | None = None,
) -> int:
    """Write one version. Never edits: a refit is a new row (LAW 3).

    A category with nothing to fit is still RECORDED, with the reason in
    `status` and no slope to apply -- so the interface can say "corrections
    begin at 50 settled, 31 so far" from the record rather than by recomputing
    a count that could drift from what the engine actually saw.
    """
    version = next_version(conn, sport=sport, market_type=market_type,
                           forecaster=forecaster)
    hold = holdout or {}
    conn.execute(
        "INSERT INTO calibration_corrections (sport, market_type, forecaster,"
        " version, fitted_utc, n_train, slope, intercept, train_brier_raw,"
        " train_brier_corrected, holdout_n, holdout_brier_raw,"
        " holdout_brier_corrected, active_from, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sport, market_type, forecaster, version, fitted_utc or utcnow(),
         model.n_train if model else 0,
         model.slope if model else 1.0,
         model.intercept if model else 0.0,
         model.brier_raw if model else None,
         model.brier_corrected if model else None,
         hold.get("n"), hold.get("brier_raw"), hold.get("brier_corrected"),
         active_from, status),
    )
    conn.commit()
    return version


def categories_in_the_record(conn: sqlite3.Connection, *,
                            before_utc: str) -> list[tuple[str, str, str]]:
    """Every (sport, market_type, forecaster) with settled rows before a time.

    Read from the record rather than from a declared list, so a category that
    starts settling is fitted without anyone remembering to add it -- and a
    category with nothing in it never gets a row saying it is unfit, which
    would read as a failure rather than an absence.

    IT CARRIES THE SAME BOUNDS AS THE TRAINING QUERY, and the isolation scan
    insisted on it before I had thought it through. It is right: a category
    whose only rows are VOIDS has no settled record, and enumerating it here
    would write a correction row for a category the fit will then find empty.
    The same goes for the time bound -- the enumeration must see the same
    record the fit does, or the two disagree about what exists.
    """
    return [
        (r["sport"], r["market_type"], r["predictor"])
        for r in conn.execute(
            "SELECT DISTINCT p.sport, p.market_type, p.predictor FROM predictions p"
            " WHERE p.resolved_utc IS NOT NULL AND p.outcome IS NOT NULL"
            "   AND p.resolved_utc < ?"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)"
            " ORDER BY p.sport, p.market_type, p.predictor",
            (before_utc,),
        )
    ]


def refit_all(conn: sqlite3.Connection, *, now: str | None = None) -> dict:
    """Fit one version per category. Records what it found, activates nothing.

    ACTIVATION IS C2'S DECISION AND IS DELIBERATELY NOT MADE HERE. A fit that
    activated itself would mean the only way to inspect a correction was to
    have it already applied to live claims. Every row this writes has
    `active_from` NULL and a `status` saying why.
    """
    at = now or utcnow()
    written = []
    for sport, market_type, forecaster in categories_in_the_record(conn, before_utc=at):
        rows = training_rows(conn, sport=sport, market_type=market_type,
                             forecaster=forecaster, before_utc=at)
        if len(rows) < MIN_TRAIN:
            status = (f"corrections begin at {MIN_TRAIN} settled - "
                      f"{len(rows)} so far")
            model = None
        else:
            model = fit_platt(rows)
            status = ("fitted; awaiting the holdout check"
                      if model else
                      "every outcome in this category is the same, so there is "
                      "nothing to calibrate against")
        version = record_fit(conn, sport=sport, market_type=market_type,
                             forecaster=forecaster, model=model, status=status,
                             fitted_utc=at)
        written.append({
            "sport": sport, "market_type": market_type,
            "forecaster": forecaster, "version": version,
            "n_train": len(rows), "status": status,
        })
    return {"fitted_utc": at, "categories": written,
            "n": len(written),
            "eligible": sum(1 for w in written if w["n_train"] >= MIN_TRAIN)}
