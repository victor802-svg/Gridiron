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


def shown_claim(conn: sqlite3.Connection, *, sport: str, market_type: str,
                forecaster: str, claim: float) -> tuple[float, int | None]:
    """The number a reader will see, and the correction version behind it.

    ONE DOOR, for the same reason `side_named` is one door. Every consumer of a
    claim has to agree about which number it is using: the tier chip, the props
    confidence floor, the sort order, the sentence on the card. Three of those
    reading the raw claim and one reading the corrected one would put a STRONG
    chip on a card whose percentage says LEAN, and the disagreement would be
    invisible because both numbers are real.

    Returns the raw claim unchanged when the category has no active
    correction, which is every category today.
    """
    active = active_correction(conn, sport=sport, market_type=market_type,
                              forecaster=forecaster)
    if active is None:
        return claim, None
    model = Platt(slope=active["slope"], intercept=active["intercept"],
                  n_train=active["n_train"])
    return round(model.apply(claim), 6), int(active["version"])


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


#: The share of a category's settled rows used to FIT the holdout check. The
#: rest -- the most recent fifth -- is what the check is scored on.
HOLDOUT_TRAIN_SHARE = 0.8

#: THE HOLDOUT MUST BE BIG ENOUGH TO TELL THE TWO CASES APART, and this number
#: is measured rather than assumed. 40 trials per cell, synthetic categories at
#: two levels of miscalibration, counting how often each ACTIVATES:
#:
#:      settled   badly overconfident   already calibrated
#:           50            13 of 40             11 of 40
#:          100            19 of 40             13 of 40
#:          200            25 of 40              5 of 40
#:          300            25 of 40              1 of 40
#:          400            32 of 40              1 of 40
#:
#: At fifty settled the check CANNOT TELL THE TWO APART -- 13 against 11 is
#: noise -- so a ten-row holdout would activate a correction on a category that
#: needs none about a quarter of the time, while the interface said its numbers
#: were earned. Separation arrives around 200 and is clean by 300.
#:
#: So the holdout needs 40 rows of its own, which at the 80/20 split means a
#: category is not merely fitted but ACTIVATED from about 200 settled. That is
#: later than the brief's fifty, and it is what the measurement supports: fifty
#: is the bar for FITTING a correction and looking at it, not for applying one.
HOLDOUT_MIN = 40

#: HOW MUCH BETTER THE HOLDOUT MUST BE, and it is not zero. Measured
#: 2026-08-31, 60 synthetic categories of 200 rows each at three levels of
#: miscalibration, holdout of 40:
#:
#:   claims worth exactly what they say   -- bare `corrected < raw`: 23 of 60
#:   claims worth 55% of what they say    -- bare `corrected < raw`: 45 of 60
#:
#: A PERFECTLY CALIBRATED CATEGORY PASSED A BARE COMPARISON 38% OF THE TIME.
#: That is what a coin flip looks like: with no real effect the corrected Brier
#: lands either side of the raw one at random, and half those flips would
#: activate a correction that corrects nothing while the interface says the
#: numbers are earned.
#:
#: At this margin the same trials give 2 of 60 for the null and 35 of 60 for
#: the genuine miscalibration. The false activations fall from 38% to 3%; the
#: cost is that a mild miscalibration waits for more record before it
#: activates, which is the right way round for a gate.
HOLDOUT_MIN_GAIN = 0.005


def holdout_check(rows: list[tuple[float, int, str]]) -> dict:
    """Fit on the earliest 80%, score on the latest 20%. TIME-ORDERED, always.

    WHAT THIS IS: a thin, forward-SHAPED check. The rows are already ordered by
    when they resolved, so the fit never sees a result that had not happened
    when the holdout rows were still open. That is the only property that makes
    the number worth anything.

    WHAT THIS IS NOT: proof the correction helps. Ten to thirty rows decide it
    at the sizes this gate opens at, and a category can pass by luck. It is a
    filter against the obvious failure -- a correction that makes things worse
    on rows it has not seen -- and it is reported as that, never as evidence.

    A random split would be worse than nothing here. It would let the fit train
    on a game from next week and be tested on one from last week, and the
    result would look like a forward check while being a backward one.
    """
    n = len(rows)
    cut = int(n * HOLDOUT_TRAIN_SHARE)
    train, test = rows[:cut], rows[cut:]
    if len(test) < HOLDOUT_MIN or not train:
        return {"n": len(test), "passed": False,
                "why": (f"the check would rest on {len(test)} rows, under the "
                        f"{HOLDOUT_MIN} needed to tell a correction that helps "
                        f"from one that does not")}

    model = fit_platt(train)
    if model is None:
        return {"n": len(test), "passed": False,
                "why": ("the earliest rows have only one kind of outcome, so "
                        "there is nothing to fit a correction from")}

    probs = [p for p, _y, _t in test]
    ys = [float(y) for _p, y, _t in test]
    raw = brier(probs, ys)
    corrected = brier([model.apply(p) for p in probs], ys)
    gain = None if (raw is None or corrected is None) else raw - corrected
    passed = gain is not None and gain > HOLDOUT_MIN_GAIN
    return {
        "n": len(test), "brier_raw": raw, "brier_corrected": corrected,
        "gain": None if gain is None else round(gain, 6),
        "passed": passed,
        "why": ("the correction scored better on the most recent rows, which "
                "it was not fitted on"
                if passed else
                "the correction did not clearly improve the rows it had not "
                "seen"),
    }


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
    """Fit one version per category, and activate only what clears both bars.

    TWO BARS, and they answer different questions. `MIN_TRAIN` asks whether
    there is enough record to fit anything. The holdout asks whether the fit is
    any good on rows it did not see -- which is the question the in-sample
    Brier cannot answer, because a fit always improves the rows it was fitted
    on.

    A category failing either stays RAW, and its status says which bar it
    missed, in words the interface shows unchanged.
    """
    at = now or utcnow()
    written = []
    for sport, market_type, forecaster in categories_in_the_record(conn, before_utc=at):
        rows = training_rows(conn, sport=sport, market_type=market_type,
                             forecaster=forecaster, before_utc=at)
        model, holdout, active_from = None, None, None
        if len(rows) < MIN_TRAIN:
            status = (f"corrections begin at {MIN_TRAIN} settled - "
                      f"{len(rows)} so far")
        else:
            model = fit_platt(rows)
            if model is None:
                status = ("every outcome in this category is the same, so "
                          "there is nothing to calibrate against")
            else:
                # BOTH BARS, and the holdout is the one that can say no to a
                # fit that already exists. A correction is activated because it
                # improved rows it had not seen, not because it improved the
                # rows it was fitted on -- which it always will.
                holdout = holdout_check(rows)
                if holdout["passed"]:
                    active_from = at
                    status = (f"active - {holdout['why']} "
                              f"({holdout['n']} rows held out)")
                else:
                    status = f"fitted but not applied - {holdout['why']}"
        version = record_fit(conn, sport=sport, market_type=market_type,
                             forecaster=forecaster, model=model, status=status,
                             holdout=holdout, active_from=active_from,
                             fitted_utc=at)
        written.append({
            "sport": sport, "market_type": market_type,
            "forecaster": forecaster, "version": version,
            "n_train": len(rows), "status": status,
            "active": active_from is not None,
        })
    return {"fitted_utc": at, "categories": written,
            "n": len(written),
            "eligible": sum(1 for w in written if w["n_train"] >= MIN_TRAIN),
            "activated": sum(1 for w in written if w["active"])}


def version_report(conn: sqlite3.Connection, *, sport: str, market_type: str,
                   forecaster: str) -> list[dict]:
    """Every version of one category's correction, and how it has actually done.

    THE IN-SAMPLE FIGURE AND THE FORWARD FIGURE ARE DIFFERENT ANIMALS and are
    kept apart here so nothing downstream can mistake one for the other.
    `train_brier_*` is measured on the rows the fit was made from and will
    almost always look good -- it says the fit converged, not that it helps.
    The forward figure is measured on predictions WRITTEN UNDER the version,
    which is the only number that answers "did v1 help".

    A version that was fitted but never activated has no forward record at all,
    correctly: it never touched a claim.
    """
    out = []
    for row in conn.execute(
        "SELECT * FROM calibration_corrections"
        " WHERE sport = ? AND market_type = ? AND forecaster = ?"
        " ORDER BY version",
        (sport, market_type, forecaster),
    ):
        forward = conn.execute(
            "SELECT COUNT(*) AS n,"
            " AVG((p.calibrated_prob - p.outcome) * (p.calibrated_prob - p.outcome))"
            "   AS brier_shown,"
            " AVG((p.model_prob - p.outcome) * (p.model_prob - p.outcome))"
            "   AS brier_raw"
            " FROM predictions p"
            " WHERE p.sport = ? AND p.market_type = ? AND p.predictor = ?"
            "   AND p.correction_version = ?"
            "   AND p.resolved_utc IS NOT NULL AND p.outcome IS NOT NULL"
            "   AND p.resolved_utc < ?"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)",
            (sport, market_type, forecaster, row["version"], utcnow()),
        ).fetchone()
        out.append({
            "version": row["version"],
            "fitted_utc": row["fitted_utc"],
            "n_train": row["n_train"],
            "slope": row["slope"],
            "intercept": row["intercept"],
            "status": row["status"],
            "active_from": row["active_from"],
            "in_sample": {
                "brier_raw": row["train_brier_raw"],
                "brier_corrected": row["train_brier_corrected"],
                # Said in the payload, not only in a comment, because this
                # figure is the one most likely to be quoted as if it meant
                # something it does not.
                "label": "in-sample: measured on the rows it was fitted from",
            },
            "holdout": {
                "n": row["holdout_n"],
                "brier_raw": row["holdout_brier_raw"],
                "brier_corrected": row["holdout_brier_corrected"],
                "label": ("a thin forward-shaped check on the most recent "
                          "rows, not proof"),
            },
            "forward": {
                "n": forward["n"] or 0,
                "brier_shown": (round(forward["brier_shown"], 6)
                                if forward["brier_shown"] is not None else None),
                "brier_raw": (round(forward["brier_raw"], 6)
                              if forward["brier_raw"] is not None else None),
                "label": "measured on predictions written under this version",
            },
        })
    return out
