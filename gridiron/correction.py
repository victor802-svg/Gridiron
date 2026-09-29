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

AND RECOMMENDATIONS, FROM 2026-09-26 (GRIDIRON_REPAIR item 3). A
recommendation is priced from the claim at the line through
`shown_proposition`, and the version in force when it is written is stored on
its row beside the corrected number, with the raw claim's number kept in
`fair_value` as it always was. The recommendations written before that date
carry neither, and that is true rather than missing: no correction had ever
been active (0 of 63 fits on the live record that day).

THE GATE COUNTS QUESTIONS, FROM QUESTION 16'S RELEASE (operator question 16,
ruled (B) 2026-09-27: "on its key. Each correction gate's count per
forecaster and distinct bet"; question 23, ruled (A) 2026-09-28: "The page's
count and the fit's own gate both move to the key, for fits from the release
forward. The 63 existing fits stay as written; any that falls short of its
gate on the corrected count is labelled 'fitted below its gate' and can
never be activated"; built 2026-09-29). `settled_rows` is the one door for
what a category's gate counts, and every count of it is `bet.count` of its
rows -- one per distinct bet, the forecaster in the category: the page's
"A correction for ..." line, the fit's own gate in `refit_all`, the forward
count in `version_report`, and the learning panel's correction row. Until
this release the gate was `len(training_rows(...))`, every settled forecast
of the category -- a question's morning and final pass each, two rungs of one
game -- and on 28 September MLB moneyline's 364 were 260 questions and UFC's
statistical 85 were 49. THE ROWS A FIT IS TRAINED ON ARE NOT MOVED: the
ruling names the gate and the page's count; what a correction is fitted on
(`training_rows`, every settled forecast, as always) would change every
slope and intercept fitted after it, a model change no ruling names. So the
gate and the training are two reads from this release, where they were one.

THE CATEGORY IS NOT SPLIT. A category is (sport, market type, forecaster),
so every prop type is one category under 'prop' and UFC's cards are one:
that is what a fit is fitted for, not a count, and splitting it would be a
model change the ruling does not name. `settled_rows` refuses a prop type's
own name as a market, so no count of one prop type can pass for the
category's; the page says "every prop type together" and "every card
together" instead.

A FIT FITTED BELOW ITS GATE is labelled, never edited (`correction_gate_labels`,
the re-grade label's shape): `below_their_gates` selects by rule from each
fit's own record, `write_labels` writes the ruled ones, and the schema's rules
refuse a label the fit's record does not support. `active_correction`, the
activation door (C2's gate), never returns a labelled fit.

WHICH ARE RULED (operator question 31, ruled (B) and (B) 2026-09-29): "Label
every fitted row written before Q16's release that falls short on the key:
33, 59, 61, 63, 81, 85, 86, 87, 89", and "No labels on placeholders; they were
never fitted." A fit written from the release on is gated on the key at its
own instant, so the rule's selection over every fit on the record IS that
population, read with no instant; `tools/label_corrections_below_the_gate.py`
writes only when it is exactly the nine, and refuses any other selection by
name. (From the build to that ruling, 2026-09-29 ~01:50Z, the default: the
63 read by the instant question 23 was ruled, and the four among them.)

WRITTEN INACTIVE; IN FORCE ONLY BY ITS OWN DATED ROW (operator question 32,
ruled 2026-09-29, second set; built the same day): "corrections activate
through the same gate as model fits. Every correction row is written
inactive. Activation is its own dated append-only row, written only when the
holdout bootstrap interval of the Brier improvement excludes zero, measured on
distinct bets by the key, per forecaster; a tie goes to the uncorrected
probability. The recalibration task never activates anything." Until this
release `refit_all` set `active_from` on the row it wrote whenever
`holdout_check` -- a point comparison on the latest fifth of the category's
settled FORECASTS, a gain over 0.005 and no interval -- passed, and the door
read that column: fit 71 came into force that way, by the weekly task, at
2026-09-28T13:00:01Z. From this release:

  * `record_fit` writes every row inactive and the schema refuses
    `active_from` on a new row (`calibration_corrections_written_inactive`);
    `refit_all` fits and records, and never measures or activates.
  * the correction in force for a category is read from
    `correction_activations` alone, through `latest_activation` (the one
    door; `active_correction` is it, less a withdrawal): the category's latest
    row -- measured or scratch, that correction; withdrawn, none.
    `active_from` on a stored row is history, never read as in force.
  * `measure` is the gate's measurement, the model fits' shape
    (`tools/holdout.py`): the category's settled questions before the
    correction was fitted, ONE forecast per distinct bet on `gridiron.bet`'s
    key, in the order they settled; a correction refit on the earliest four
    fifths and scored on the latest fifth (the old split and its forty, now
    counted in questions); the paired bootstrap 95% interval of the Brier
    improvement (raw minus corrected), seeded and recorded as the model gate
    seeds it. It passes only when the lower bound is above zero: an interval
    touching zero is a tie, and a tie goes to the uncorrected probability.
  * `activate_measured` measures and writes the dated row in one
    transaction, only when it passes; `withdraw` writes a withdrawal with its
    reason; `activate_in_a_scratch_world` is a test world's lawful path. The
    schema's rules hold every part of it, the key's count among them.

WHICH ROW OF A BET STANDS in the measurement, and why: its FINAL PASS if
one settled, otherwise its LATEST WRITTEN settled forecast, withdrawn by no
void either way (operator question 27, ruled 2026-09-28, built 2026-09-29:
"the standing pass is chosen by pass, not by write time: the final pass
stands whenever one exists before the start; otherwise the latest early
pass"; until then the latest written, whatever its pass). The blind
record's standing rule reads the start as well (`calibration.
standing_row_clause`, `recount.standing_of`), and this module may not read
`games`, where the start is (`audit.check_correction_is_isolated`, which
allows `predictions` and `prediction_voids` and so allows the pass: it is a
column of `predictions`). So the pass is read here BY PASS ALONE, and the
two are one choice whenever no forecast withdrawn by no void was written
after its game began -- a pass never writes one (the missed rule) and one
found is voided (ruling 1, 2026-09-24) -- and the tool that writes an
activation on the record checks that they are, question by question,
against `recount.correction_standing`, and refuses by name where they are
not (`tools/correction_holdout.py`).
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

from . import bet, config
from .db import table_columns, transaction, utcnow

#: A claim is squeezed inside this before its log-odds is taken. A stored
#: probability of exactly 0 or 1 has infinite log-odds and would take the fit
#: with it; the model does not produce them today, and this is here so that a
#: model that someday does fails visibly rather than silently.
EPS = 1e-6

#: Below this many settled predictions a category has no correction (C2's gate
#: lives here so the engine and the interface read one number). FROM QUESTION
#: 16'S RELEASE (2026-09-29) it counts settled QUESTIONS -- distinct bets on
#: `gridiron.bet`'s key -- where it counted settled forecasts; the number is
#: unchanged, and the label's rule in the schema pins it (tested equal).
MIN_TRAIN = 50

#: The two forecasters a correction category may name (LAW 6's reasoning:
#: one fitted across both lets the better flatter the worse).
FORECASTERS = ("statistical", "llm")

#: THE LABEL (operator question 23, ruled 2026-09-28): the table, and the
#: verdict as stored; the page says it in words ("fitted below its gate").
LABELS = "correction_gate_labels"
FITTED_BELOW_ITS_GATE = "fitted_below_its_gate"


class PooledCount(ValueError):
    """A correction count asked for nobody in particular, for both
    forecasters, or for one prop type's share of the category."""


class Refused(ValueError):
    """A label the rule does not select, or one on a fit in force."""


class ActivationRefused(RuntimeError):
    """An activation or a withdrawal of a correction was refused -- by the
    schema, whose own words it carries, or by the measurement, which did not
    pass the gate (operator question 32, 2026-09-29)."""


class ScratchWorldRefused(RuntimeError):
    """A scratch activation of a correction was asked of a record."""


#: THE ACTIVATIONS (operator question 32, 2026-09-29): the table, and its
#: three kinds as stored.
ACTIVATIONS = "correction_activations"
MEASURED, WITHDRAWN, SCRATCH = "measured", "withdrawn", "scratch"

#: THE BOOTSTRAP, AS THE MODEL FITS' GATE DRAWS IT (question 32: "the same
#: gate as model fits"): `tools/holdout.py`'s resamples and seed, and its
#: percentile rule, so one measurement of one set of differences gives one
#: interval under either gate (tested equal). Recorded on every measured row.
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 20260923

#: FIT 71'S WITHDRAWAL, IN THE OPERATOR'S WORDS (question 32, ruled
#: 2026-09-29: "Fit 71: withdrawn now by a dated append-only row, reason
#: ..."). Stored as ruled; the page says it in plain words
#: (`language.withdrawal_reason_words`).
FIT_71_WITHDRAWAL_REASON = (
    "activated under the pre-Q32 rule: single holdout comparison, pooled rows")

#: What a scratch activation says, in words.
SCRATCH_REASON = (
    "a scratch world puts its own correction in force without a measurement, "
    "which only a database that is not the live record may do")


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


def settled_rows(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str,
    forecaster: str,
    before_utc: str | None = None,
    version: int | None = None,
    as_it_stood: bool = False,
) -> list[sqlite3.Row]:
    """THE ONE DOOR for what a correction category's gate counts: its settled
    forecasts before an instant, each carrying the distinct-bet key, so every
    count of it is `bet.count(rows)` -- one per question, the forecaster in
    the category (operator questions 16 and 23, built 2026-09-29).

    Read by the page's "A correction for ..." line, the fit's own gate in
    `refit_all` (`before_utc` the fit's instant), the forward count in
    `version_report` (`version`: only forecasts written under it), the
    learning panel's correction row and the label's selection
    (`below_their_gates`, at each fit's own instant, `as_it_stood`).

    SETTLED BEFORE THE INSTANT, AND NEVER A WITHDRAWN FORECAST: a forecast
    counts if it had an outcome before `before_utc` (now, when left out) and
    no void -- every void on the record, whatever its stamp, as
    `training_rows` reads them, for the page and the fit being made now. A
    void never counts toward a gate (ruling 1, 2026-09-24). ONLY A FIT'S OWN
    COUNT, READ AS ITS GATE READ IT (`as_it_stood`, the label's selection):
    no void stamped at or before its instant, so a void written after the fit
    does not take back a row it counted. THE PROVER (2026-09-29): this read
    voids stamped at or before the instant everywhere, so a void stamped after
    now -- by hand, or a clock -- left its forecast counted on the page, in
    the recount beside it and in the fit's gate, while the fit's training left
    it out; the guard saw nothing, because the recount read it the same way.

    WHICH PASS COUNTS is the blind record's standing rule, and the count
    does not turn on it: a question is counted once whichever of its passes
    settled. The standing rule reads the game's start, and this module may
    not name `games` (`audit.check_correction_is_isolated`); measured on the
    live record on 2026-09-28, the distinct keys and the standing rule give
    the same count for all 89 fits.

    THE CATEGORY WHOLE: `market_type` is the category's ('prop' for every
    prop type together), and a prop type's own name is refused by name -- a
    count of one prop type is not the count that gates the fit. The
    forecaster is required and one of the two.
    """
    config.require_sport(sport, "correction.settled_rows")
    if forecaster not in FORECASTERS:
        raise PooledCount(
            f"a correction's count is one forecaster's, {FORECASTERS}; asked "
            f"for {forecaster!r} (operator question 16, 2026-09-27: each "
            f"correction gate's count per forecaster and distinct bet)")
    if market_type in config.SPORT_PROP_MARKETS.get(sport, ()):
        raise PooledCount(
            f"{market_type!r} is one prop type; a correction is fitted for "
            f"every prop type together ('prop'), and its count is the "
            f"category's -- splitting the category is a model change no "
            f"ruling names")
    at = before_utc or utcnow()
    # NULL: every void on the record; an instant: those stamped by it.
    voided_by = at if as_it_stood else None
    # WHEN EACH WAS WRITTEN, beside the key (2026-09-29, question 32): the
    # measurement keeps one forecast per question, the latest written
    # (`holdout_questions`). A column more, no clause changed. AND ITS PASS
    # (operator question 27, 2026-09-29): a final pass is kept first.
    return conn.execute(
        f"SELECT p.id, {bet.columns('p')}, p.model_prob, p.calibrated_prob,"
        "       p.outcome, p.resolved_utc, p.created_utc, p.pass_kind"
        "  FROM predictions p"
        " WHERE p.sport = ? AND p.market_type = ? AND p.predictor = ?"
        "   AND p.resolved_utc IS NOT NULL AND p.outcome IS NOT NULL"
        "   AND p.resolved_utc < ?"
        "   AND (? IS NULL OR p.correction_version = ?)"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id"
        "                     AND (? IS NULL OR v.voided_utc <= ?))"
        " ORDER BY p.id",
        (sport, market_type, forecaster, at, version, version, voided_by,
         voided_by),
    ).fetchall()


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


def latest_activation(
    conn: sqlite3.Connection, *, sport: str, market_type: str, forecaster: str,
    at_utc: str | None = None,
) -> sqlite3.Row | None:
    """THE ONE DOOR for whether a correction is in force (operator question
    32, ruled 2026-09-29: "Activation is its own dated append-only row"):
    the category's latest row in `correction_activations` stamped at or
    before `at_utc` (now, when left out) -- the correction it names, every
    column of it, with the row's own beside it (`activation_kind`,
    `activated_utc`, `activation_reason`, and a measured row's measurement:
    `measured_bets`, `measured_holdout_n`, `measured_brier_raw`,
    `measured_brier_corrected`, `measured_improvement`, `diff_low`,
    `diff_high`, `bootstrap_seed`, `bootstrap_draws`, `measured_on`) -- or
    None when the category has no row by then.

    A withdrawal is returned as what it is: `active_correction` reads it as
    nothing in force; the page says since when, and why.

    `active_from` IS NEVER READ HERE. It was how a correction came into force
    until this release -- set by the weekly refit on the row it wrote -- and
    it stays on the stored rows as history. A record the schema of this
    release has not reached holds no activation row, so nothing is in force
    on it: the ruling's "every correction row is written inactive", read back.

    NEVER A FIT FITTED BELOW ITS GATE (operator question 23, 2026-09-28: a
    labelled fit "can never be activated"). The schema refuses an activation
    naming one, and this door passes over one on a record made otherwise by
    hand, as though it had never been activated: the category's latest row
    naming no labelled fit decides.
    """
    if not table_columns(conn, ACTIVATIONS):
        return None
    now = at_utc or utcnow()
    unlabelled = (" AND NOT EXISTS (SELECT 1 FROM correction_gate_labels l"
                  "                 WHERE l.correction_id = a.correction_id)"
                  if _labels_held(conn) else "")
    # Latest by the row's place in its category: the schema holds the place
    # and the stamp to one order (each row the next, never stamped before the
    # last), so the place decides and the stamp says when.
    return conn.execute(
        "SELECT c.*, a.seq AS activation_seq, a.kind AS activation_kind,"
        "       a.activated_utc, a.reason AS activation_reason,"
        "       a.holdout AS measured_on, a.bets AS measured_bets,"
        "       a.holdout_n AS measured_holdout_n,"
        "       a.brier_raw AS measured_brier_raw,"
        "       a.brier_corrected AS measured_brier_corrected,"
        "       a.improvement AS measured_improvement, a.diff_low, a.diff_high,"
        "       a.bootstrap_seed, a.bootstrap_draws"
        "  FROM correction_activations a"
        "  JOIN calibration_corrections c ON c.id = a.correction_id"
        " WHERE a.sport = ? AND a.market_type = ? AND a.forecaster = ?"
        "   AND a.activated_utc <= ?" + unlabelled +
        " ORDER BY a.seq DESC LIMIT 1",
        (sport, market_type, forecaster, now),
    ).fetchone()


def active_correction(
    conn: sqlite3.Connection, *, sport: str, market_type: str, forecaster: str,
    at_utc: str | None = None,
) -> sqlite3.Row | None:
    """The correction in force for a category, or None while it is still raw.

    FROM QUESTION 32 (2026-09-29) this is `latest_activation` less a
    withdrawal: the correction the category's latest activation row names
    when that row puts it in force (measured, or scratch in a test world),
    and None when the latest row withdraws it or there is none. A fit is
    written inert and stays inert until its own dated row -- which is what
    makes C2's gate a decision rather than a side effect of fitting, as it
    was meant to be and, until this release, was not: the weekly refit put
    fit 71 in force by setting `active_from` on the row it wrote.
    """
    latest = latest_activation(conn, sport=sport, market_type=market_type,
                               forecaster=forecaster, at_utc=at_utc)
    if latest is None or latest["activation_kind"] == WITHDRAWN:
        return None
    return latest


def activations(conn: sqlite3.Connection, *, sport: str, market_type: str,
                forecaster: str) -> list[dict]:
    """Every activation and withdrawal of one category, in its order: the
    history `version_report` sets beside each version."""
    if not table_columns(conn, ACTIVATIONS):
        return []
    return [dict(r) for r in conn.execute(
        "SELECT * FROM correction_activations"
        " WHERE sport = ? AND market_type = ? AND forecaster = ?"
        " ORDER BY seq", (sport, market_type, forecaster))]


def _labels_held(conn: sqlite3.Connection) -> bool:
    """Does this record hold the label table? One that the schema of
    question 16's release has not reached holds no label, exactly."""
    return bool(table_columns(conn, LABELS))


def shown_claim(conn: sqlite3.Connection, *, sport: str, market_type: str,
                forecaster: str, claim: float,
                at_utc: str | None = None) -> tuple[float, int | None]:
    """The number a reader will see, and the correction version behind it.

    ONE DOOR, for the same reason `side_named` is one door. Every consumer of a
    claim has to agree about which number it is using: the tier chip, the props
    confidence floor, the sort order, the sentence on the card. Three of those
    reading the raw claim and one reading the corrected one would put a STRONG
    chip on a card whose percentage says LEAN, and the disagreement would be
    invisible because both numbers are real.

    Returns the raw claim unchanged when the category has no active
    correction -- none has an activation row of its own when question 32's
    release lands (2026-09-29).

    `claim` is a CONFIDENCE -- the probability of the side the model took,
    at least 0.5 -- because that is what every fit is fitted on. A number
    stated from a fixed proposition goes through `shown_proposition`.

    `at_utc` (2026-09-26, GRIDIRON_REPAIR item 3): the correction in force AT
    that instant rather than now, so a figure describing a claim written
    earlier is corrected by the version that was current when it was written
    and never by a later one. Left out, it is now, as it always was.
    """
    active = active_correction(conn, sport=sport, market_type=market_type,
                              forecaster=forecaster, at_utc=at_utc)
    if active is None:
        return claim, None
    model = Platt(slope=active["slope"], intercept=active["intercept"],
                  n_train=active["n_train"])
    return round(model.apply(claim), 6), int(active["version"])


def shown_proposition(conn: sqlite3.Connection, *, sport: str,
                      market_type: str, forecaster: str, proposition: float,
                      at_utc: str | None = None) -> tuple[float, int | None]:
    """A number stated from a fixed proposition, corrected, and its version.

    GRIDIRON_REPAIR item 3 (the operator's ruling of 2026-09-23, built
    2026-09-26): "Corrections reach recommendations. recommend.py:324 reads the
    corrected probability, never the raw claim." A claim at the line is stated
    from ONE FIXED PROPOSITION -- the home side of a spread or a winner
    market, the over of a total -- so it can sit either side of a half, where
    every fit was fitted on confidences: 0 of the 2,581 forecasts on the live
    record was below 0.5 on 2026-09-26, and 628 of its 1,264 claims were.

    SO THE NUMBER IS TURNED TO THE SIDE IT FAVOURS, CORRECTED THERE, AND
    TURNED BACK. The same order `model.predict` uses to write a forecast
    (`baseline.stated_side`, then `shown_claim`), with the same tie rule: a
    number of exactly one half favours the proposition. Applying the fit to
    the proposition's number directly is not the same thing -- with a nonzero
    intercept the correction of `1 - p` is not one minus the correction of
    `p`. Under the live record's baseball total fit for the reasoning pass
    (version 2: slope 0.449, intercept -0.270), a home claim of 43% is 40%
    applied directly and 54% turned first: against a price of 48.5 cents,
    the no side one way and the yes side the other, on the same claim
    (measured 2026-09-26; the planting's own numbers).

    Returns the number unchanged, with no version, when the category has no
    correction in force at `at_utc` (now, when left out) -- which is every
    category on 2026-09-26. A fitted version whose holdout did not activate
    it is never applied: that is C2's gate, and this is the same door.
    """
    favoured = float(proposition) >= 0.5
    confidence = float(proposition) if favoured else 1.0 - float(proposition)
    shown, version = shown_claim(conn, sport=sport, market_type=market_type,
                                 forecaster=forecaster, claim=confidence,
                                 at_utc=at_utc)
    if version is None:
        return proposition, None
    return (shown if favoured else round(1.0 - shown, 6)), version


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
    model: Platt | None, status: str, fitted_utc: str | None = None,
) -> int:
    """Write one version. Never edits: a refit is a new row (LAW 3).

    A category with nothing to fit is still RECORDED, with the reason in
    `status` and no slope to apply -- so the interface can say "corrections
    begin at 50 settled, 31 so far" from the record rather than by recomputing
    a count that could drift from what the engine actually saw.

    ALWAYS INACTIVE (operator question 32, 2026-09-29: "Every correction row
    is written inactive"). There is no `active_from` to pass -- it was how a
    row put itself in force until this release -- and the schema refuses one
    on a new row. A correction comes into force only by its own dated row
    (`activate_measured`). Nor does a row carry a holdout of its own any more:
    the measurement that can put it in force is the activation's.
    """
    version = next_version(conn, sport=sport, market_type=market_type,
                           forecaster=forecaster)
    conn.execute(
        "INSERT INTO calibration_corrections (sport, market_type, forecaster,"
        " version, fitted_utc, n_train, slope, intercept, train_brier_raw,"
        " train_brier_corrected, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (sport, market_type, forecaster, version, fitted_utc or utcnow(),
         model.n_train if model else 0,
         model.slope if model else 1.0,
         model.intercept if model else 0.0,
         model.brier_raw if model else None,
         model.brier_corrected if model else None,
         status),
    )
    conn.commit()
    return version


#: The share of a category's settled QUESTIONS the measurement refits a
#: correction on, in the order they settled. The rest -- the most recent
#: fifth -- is what it is scored on. (Rows until question 32's release,
#: 2026-09-29: every settled forecast, a question's passes each.)
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

#: THE POINT MARGIN IS GONE (operator question 32, ruled 2026-09-29). Until
#: this release a holdout passed when the corrected Brier beat the raw one by
#: more than 0.005 (`HOLDOUT_MIN_GAIN`), one comparison with no interval, on
#: every settled forecast of the category -- measured 2026-08-31 on synthetic
#: categories to pass a calibrated one 2 times in 60, and fit 71 cleared it by
#: 0.0002. The gate is now the model fits': the bootstrap interval of the
#: improvement, which must lie wholly above zero (`measure`).


def paired_bootstrap(diffs: list[float], draws: int = BOOTSTRAP_DRAWS,
                     seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    """The 95% percentile interval of the mean of per-question differences,
    resampling QUESTIONS, so each draw keeps one question's raw and corrected
    scores together -- `tools/holdout.py`'s own rule for the model fits (the
    same draws, the same seed, the same two percentiles; tested equal)."""
    import random

    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(draws))
    return means[int(0.025 * draws)], means[int(0.975 * draws) - 1]


def holdout_questions(conn: sqlite3.Connection, fit) -> list[sqlite3.Row]:
    """The questions a correction is measured on: its category's settled
    questions before it was fitted -- ONE forecast per distinct bet on
    `gridiron.bet`'s key, the forecaster in the category -- in the order they
    settled (operator question 32, 2026-09-29: "measured on distinct bets by
    the key, per forecaster").

    Read through the gate's one door (`settled_rows`, at the correction's own
    fitted instant: the record the fit saw, so a measurement made a week
    later measures what was there to fit), so the questions measured are the
    questions the gate counts and the schema recounts. Each question stands on
    its FINAL PASS if one settled, otherwise its LATEST WRITTEN forecast
    (operator question 27, from 2026-09-29; the module's text says why it is
    read by pass alone, and what checks it); settled in time order, the
    forecast's number breaking a tie.
    """
    def order(row) -> tuple:
        # `calibration.standing_pass_order` without the start, which this
        # module may not read: the pass, then the write time, then the number.
        return (row["pass_kind"] == "final", row["created_utc"], row["id"])

    standing: dict[tuple, sqlite3.Row] = {}
    for row in settled_rows(conn, sport=fit["sport"],
                            market_type=fit["market_type"],
                            forecaster=fit["forecaster"],
                            before_utc=fit["fitted_utc"]):
        key = bet.of(row)
        held = standing.get(key)
        if held is None or order(row) > order(held):
            standing[key] = row
    return sorted(standing.values(), key=lambda r: (r["resolved_utc"], r["id"]))


def measure(conn: sqlite3.Connection, correction_id: int, *,
            draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED) -> dict:
    """THE GATE'S MEASUREMENT of one stored correction (operator question 32,
    ruled 2026-09-29, the model fits' shape): READS ONLY.

    Its category's settled questions before it was fitted
    (`holdout_questions`); a correction refit on the earliest four fifths
    (`HOLDOUT_TRAIN_SHARE`) and scored on the latest fifth, at least
    `HOLDOUT_MIN` of them; per held-out question, its raw claim's squared
    error less the refit's; the improvement is their mean -- the raw Brier
    less the corrected one on the same questions -- and its paired bootstrap
    95% interval (`paired_bootstrap`, seeded). PASSES ONLY WHEN THE LOWER
    BOUND IS ABOVE ZERO. An interval touching zero is a tie, and a tie goes to
    the uncorrected probability.

    WHAT IS SCORED is the correction's method on the category as it stood --
    a Platt fit made on the earliest four fifths, scored on the rest -- as the
    model gate scores a factor set refit through the season before
    (`tools/holdout.py`). The stored correction was fitted on all of them, so
    scoring it on the latest fifth would score it on rows it was fitted on.
    What goes in force, if this passes, is the stored correction.

    Never a placeholder (nothing was fitted) and never a fit labelled
    fitted below its gate (it can never be activated): each is returned
    unmeasured, `passed` False, with the reason in words.
    """
    fit = conn.execute("SELECT * FROM calibration_corrections WHERE id = ?",
                       (correction_id,)).fetchone()
    if fit is None:
        raise ActivationRefused(f"there is no correction {correction_id} to measure")
    out = {"correction_id": fit["id"], "sport": fit["sport"],
           "market_type": fit["market_type"], "forecaster": fit["forecaster"],
           "version": fit["version"], "fitted_utc": fit["fitted_utc"],
           "n_train": fit["n_train"], "seed": seed, "draws": draws,
           "passed": False}
    if fit["n_train"] < MIN_TRAIN:
        return dict(out, why=(
            f"a placeholder: nothing was fitted (its {fit['n_train']} settled "
            f"forecasts were under the {MIN_TRAIN} a fit needs), so there is "
            f"nothing to put in force"))
    if _labels_held(conn) and conn.execute(
            "SELECT 1 FROM correction_gate_labels WHERE correction_id = ?",
            (correction_id,)).fetchone():
        return dict(out, why=(
            "fitted below its gate, so it can never be in force (operator "
            "question 23, 2026-09-28)"))
    questions = holdout_questions(conn, fit)
    n = len(questions)
    cut = int(n * HOLDOUT_TRAIN_SHARE)
    train, test = questions[:cut], questions[cut:]
    out.update(bets=n, fitted_on=cut, holdout_n=len(test),
               standing={bet.of(r): r["id"] for r in questions})
    if len(test) < HOLDOUT_MIN or not train:
        return dict(out, why=(
            f"the measurement would rest on {len(test)} questions of its "
            f"{n}, under the {HOLDOUT_MIN} needed to tell a correction that "
            f"helps from one that does not"))
    model = fit_platt([(r["model_prob"], int(r["outcome"]), r["resolved_utc"])
                       for r in train])
    if model is None:
        return dict(out, why=("the earliest questions have only one kind of "
                              "outcome, so there is nothing to fit a "
                              "correction from"))
    raw_sq = [(float(r["model_prob"]) - float(r["outcome"])) ** 2 for r in test]
    fixed_sq = [(model.apply(r["model_prob"]) - float(r["outcome"])) ** 2
                for r in test]
    diffs = [a - b for a, b in zip(raw_sq, fixed_sq)]
    low, high = paired_bootstrap(diffs, draws=draws, seed=seed)
    passed = low > 0
    out.update(
        brier_raw=round(sum(raw_sq) / len(test), 6),
        brier_corrected=round(sum(fixed_sq) / len(test), 6),
        improvement=round(sum(diffs) / len(test), 6),
        interval=(low, high), passed=passed,
        holdout=(
            f"the latest {len(test)} of the category's {n} settled questions "
            f"before the fit ({fit['fitted_utc']}), one forecast each (its "
            f"final pass if one settled, otherwise its latest written) in the "
            f"order they settled; a correction refit "
            f"on the earliest {cut} and scored on them"),
        why=("the bootstrap interval of the Brier improvement lies wholly "
             "above zero" if passed else
             "the bootstrap interval of the Brier improvement touches zero: a "
             "tie, so the uncorrected probability stands"))
    return out


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
    """Fit one version per category, and record it -- INACTIVE, every one.

    ONE BAR HERE, `MIN_TRAIN`: is there enough record to fit anything? A
    category under it is recorded with its shortfall in words, and a fit is
    recorded with words saying it is not in force.

    AND NOTHING IS ACTIVATED HERE, OR MEASURED (operator question 32, ruled
    2026-09-29: "Every correction row is written inactive ... The
    recalibration task never activates anything"). Until this release this
    function also ran `holdout_check` -- a point comparison on the latest
    fifth of the category's settled forecasts -- and wrote `active_from` when
    it passed, which put fit 71 in force from the weekly task at
    2026-09-28T13:00:01Z. The question the holdout asked -- is the fit any
    good on questions it did not see? -- is the gate's now, asked by
    `measure` and answered by a dated row of its own (`activate_measured`,
    through `tools/correction_holdout.py`).

    THE BAR COUNTS QUESTIONS from question 16's release (operator
    question 23, ruled (A) 2026-09-28: "the fit's own gate ... move[s] to the
    key, for fits from the release forward"): `MIN_TRAIN` distinct bets
    among the category's settled forecasts (`settled_rows`, at this instant),
    where it counted the forecasts -- a question's morning and final pass
    each. The fit is still made from every settled forecast
    (`training_rows`, unchanged): the ruling moves the gate, not what a
    correction is fitted on. `n_train` stays the rows it was fitted on, and
    the report carries the gate's own count beside it (`questions`).
    """
    at = now or utcnow()
    written = []
    for sport, market_type, forecaster in categories_in_the_record(conn, before_utc=at):
        rows = training_rows(conn, sport=sport, market_type=market_type,
                             forecaster=forecaster, before_utc=at)
        questions = bet.count(settled_rows(
            conn, sport=sport, market_type=market_type, forecaster=forecaster,
            before_utc=at))
        model = None
        if questions < MIN_TRAIN:
            status = (f"corrections begin at {MIN_TRAIN} settled questions - "
                      f"{questions} so far")
        else:
            model = fit_platt(rows)
            if model is None:
                status = ("every outcome in this category is the same, so "
                          "there is nothing to calibrate against")
            else:
                # FITTED, NOT IN FORCE (question 32, 2026-09-29): what the
                # row is, in the words the interface shows as written.
                status = FITTED_NOT_IN_FORCE
        version = record_fit(conn, sport=sport, market_type=market_type,
                             forecaster=forecaster, model=model, status=status,
                             fitted_utc=at)
        written.append({
            "sport": sport, "market_type": market_type,
            "forecaster": forecaster, "version": version,
            "n_train": len(rows), "questions": questions, "status": status,
        })
    return {"fitted_utc": at, "categories": written,
            "n": len(written),
            "eligible": sum(1 for w in written if w["questions"] >= MIN_TRAIN)}


#: WHAT A FITTED ROW SAYS OF ITSELF from question 32's release (2026-09-29):
#: fitted, and not in force until it is measured and activated by its own row.
FITTED_NOT_IN_FORCE = (
    "fitted, and not in force - a correction is put in force only by a dated "
    "row of its own, once one fitted on the earliest four fifths of its "
    "settled questions improves the latest fifth, with a 95% interval clear "
    "of zero")


def version_report(conn: sqlite3.Connection, *, sport: str, market_type: str,
                   forecaster: str, at_utc: str | None = None) -> list[dict]:
    """Every version of one category's correction, and how it has actually done.

    THE IN-SAMPLE FIGURE AND THE FORWARD FIGURE ARE DIFFERENT ANIMALS and are
    kept apart here so nothing downstream can mistake one for the other.
    `train_brier_*` is measured on the rows the fit was made from and will
    almost always look good -- it says the fit converged, not that it helps.
    The forward figure is measured on predictions WRITTEN UNDER the version,
    which is the only number that answers "did v1 help".

    A version that was fitted but never activated has no forward record at all,
    correctly: it never touched a claim.

    THE FORWARD COUNT IS QUESTIONS (operator question 16, 2026-09-27; built
    2026-09-29): `n` is the distinct bets among the settled forecasts written
    under the version, through the one door (`settled_rows`), where it counted
    the forecasts -- a question's morning and final pass each. The two Brier
    figures are still averaged over those forecasts, and `forecasts` says how
    many, beside `n`, so neither is read over the other's sample.

    AND ITS LABEL (question 23, 2026-09-28): `below_its_gate` is the version's
    "fitted below its gate" label as written, or None.

    AND WHETHER IT IS IN FORCE, FROM ITS OWN ROWS (question 32, 2026-09-29):
    `in_force` is whether the door puts this version in force at `at_utc`,
    and `activations` every activation or withdrawal naming it, as written.
    `written_in_force_before_the_gate` is the row's `active_from` -- how a
    correction was put in force until this release, kept as the history it
    is and read as nothing else (fit 71's, 2026-09-28T13:00:01Z).
    """
    at = at_utc or utcnow()
    labelled = labels(conn, sport=sport, market_type=market_type,
                      forecaster=forecaster)
    in_force = active_correction(conn, sport=sport, market_type=market_type,
                                 forecaster=forecaster, at_utc=at)
    history = activations(conn, sport=sport, market_type=market_type,
                          forecaster=forecaster)
    out = []
    for row in conn.execute(
        "SELECT * FROM calibration_corrections"
        " WHERE sport = ? AND market_type = ? AND forecaster = ?"
        " ORDER BY version",
        (sport, market_type, forecaster),
    ).fetchall():
        under = settled_rows(conn, sport=sport, market_type=market_type,
                             forecaster=forecaster, before_utc=at,
                             version=row["version"])
        forward = {
            "n": bet.count(under),
            "forecasts": len(under),
            "brier_shown": brier(
                [r["calibrated_prob"] for r in under
                 if r["calibrated_prob"] is not None],
                [r["outcome"] for r in under
                 if r["calibrated_prob"] is not None]),
            "brier_raw": brier([r["model_prob"] for r in under],
                               [r["outcome"] for r in under]),
        }
        out.append({
            "id": row["id"],
            "version": row["version"],
            "fitted_utc": row["fitted_utc"],
            "n_train": row["n_train"],
            "slope": row["slope"],
            "intercept": row["intercept"],
            "status": row["status"],
            "in_force": in_force is not None and in_force["id"] == row["id"],
            "activations": [a for a in history
                            if a["correction_id"] == row["id"]],
            "written_in_force_before_the_gate": row["active_from"],
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
                # AS WRITTEN (question 32, 2026-09-29): the refit's own point
                # check until this release, on every settled forecast; a row
                # written from it carries none, and the gate's measurement is
                # its activation's.
                "label": ("the refit's own check before 29 September 2026: a "
                          "single comparison on the most recent rows, not "
                          "the gate"),
            },
            "forward": {
                "n": forward["n"],
                "forecasts": forward["forecasts"],
                "distinct_bets": bet.count(under),
                "forecasters_counted": sorted({r["predictor"] for r in under}),
                "brier_shown": forward["brier_shown"],
                "brier_raw": forward["brier_raw"],
                "label": ("measured on predictions written under this "
                          "version: n counts each question once, and the "
                          "two scores average its forecasts"),
            },
            "below_its_gate": labelled.get(row["id"]),
        })
    return out


def labels(conn: sqlite3.Connection, *, sport: str, market_type: str,
           forecaster: str) -> dict[int, dict]:
    """One category's "fitted below its gate" labels, by the fit's number,
    each as written with the fit's version and instant beside it."""
    if not _labels_held(conn):
        return {}
    return {r["correction_id"]: dict(r) for r in conn.execute(
        "SELECT l.*, c.version, c.fitted_utc FROM correction_gate_labels l"
        "  JOIN calibration_corrections c ON c.id = l.correction_id"
        " WHERE c.sport = ? AND c.market_type = ? AND c.forecaster = ?"
        " ORDER BY c.version",
        (sport, market_type, forecaster))}


def below_their_gates(conn: sqlite3.Connection) -> list[dict]:
    """Every fit on the record whose corrected count is below its gate, BY
    RULE FROM EACH FIT'S OWN RECORD (operator question 23, ruled (A)
    2026-09-28: "any that falls short of its gate on the corrected count is
    labelled 'fitted below its gate'"; the brief: "decided by rule from the
    fit's own record, never by a list").

    A FIT, NOT A PLACEHOLDER: a row whose `n_train` is under the gate
    recorded that there was nothing to fit (slope 1, intercept 0, "corrections
    begin at 50 ..."), so "fitted below its gate" would be false of it; it is
    never selected, and the schema refuses a label on it. ITS GATE: the fifty
    it passed on the count it used, its own `n_train`. THE ROWS ITS GATE
    COUNTED: its category's settled forecasts before its own fitted instant,
    withdrawn by no void stamped by then (`settled_rows` at that instant, as it
    stood; `counted` is how many, which the record must give back as
    `n_train`). ITS CORRECTED COUNT: the distinct bets among
    them (`bet.count`). Selected when that is below the gate. A fit written
    from question 16's release on was gated on that count and cannot be
    selected; the fits written before it were gated on the forecasts. SO THE
    SELECTION OVER EVERY FIT IS QUESTION 31'S POPULATION (ruled (B)
    2026-09-29): "every fitted row written before Q16's release" that falls
    short on the key, with no instant read -- on the record 33, 59, 61 and 63
    of the 63 existing when question 23 was ruled, and 81, 85, 86, 87 and 89
    of the weekly refit after it. A fit from the release on whose record was
    made otherwise (a void stamped back before it, a row written by hand) is
    selected all the same, and the tool refuses the selection by name.

    `active` says whether the fit carries an activation (the schema refuses a
    label on one: that is the operator's question) -- written in force under
    the rule before question 32 (`active_from`, as the schema's older rule
    reads it) or put in force by a row of its own since (2026-09-29) -- and
    `already` whether it is labelled. Which of these the ruling labels is the
    tool's constants' (`tools/label_corrections_below_the_gate.py`), never
    this rule's.
    """
    held = set()
    if _labels_held(conn):
        held = {r[0] for r in conn.execute(
            "SELECT correction_id FROM correction_gate_labels")}
    activated = set()
    if table_columns(conn, ACTIVATIONS):
        activated = {r[0] for r in conn.execute(
            "SELECT correction_id FROM correction_activations"
            " WHERE kind IN ('measured', 'scratch')")}
    out = []
    for fit in conn.execute(
            "SELECT * FROM calibration_corrections ORDER BY id").fetchall():
        if fit["n_train"] < MIN_TRAIN:
            continue
        counted = settled_rows(conn, sport=fit["sport"],
                               market_type=fit["market_type"],
                               forecaster=fit["forecaster"],
                               before_utc=fit["fitted_utc"], as_it_stood=True)
        questions = bet.count(counted)
        if questions >= MIN_TRAIN:
            continue
        out.append({
            "id": fit["id"], "sport": fit["sport"],
            "market_type": fit["market_type"],
            "forecaster": fit["forecaster"], "version": fit["version"],
            "fitted_utc": fit["fitted_utc"], "gate": MIN_TRAIN,
            "count_used": fit["n_train"], "counted": len(counted),
            "corrected_count": questions,
            "active": (fit["active_from"] is not None
                       or fit["id"] in activated),
            "already": fit["id"] in held,
            "reason": BELOW_ITS_GATE_WHY.format(
                used=fit["n_train"], gate=MIN_TRAIN, questions=questions),
        })
    return out


#: The reason a label carries, in words (question 23, 2026-09-28).
BELOW_ITS_GATE_WHY = (
    "fitted on {used} settled forecasts, past its gate of {gate} as that gate "
    "counted them; counted once per question, as a correction's gate counts "
    "from the release of operator question 16, they are {questions}, under "
    "the {gate} (operator questions 16 and 23, ruled 27 and 28 September "
    "2026)")


def write_labels(conn: sqlite3.Connection, ids: list[int], *,
                 now: str | None = None) -> dict:
    """One "fitted below its gate" label for each of `ids`, in one
    transaction, or none at all.

    EVERY ID IS CHECKED AGAINST THE RULE FIRST (`below_their_gates`, read in
    the same call): an id the rule does not select, or a fit carrying an
    activation (the operator's question: the ruling says a labelled fit can
    never be activated, not that one in force is taken out of force), is
    refused by name and nothing is written. The schema checks each label
    against the fit's record again as it is written. IDEMPOTENT: a fit
    already labelled is counted and skipped -- the table would refuse a
    second label anyway, and the first stands.
    """
    if not _labels_held(conn):
        raise RuntimeError(
            "the record has no correction_gate_labels table: it has not been "
            "opened under the schema that carries it (db.init does that, on "
            "any scheduled pass or the server's start after the release)")
    chosen = {g["id"]: g for g in below_their_gates(conn)}
    stray = sorted(set(ids) - set(chosen))
    if stray:
        raise Refused(
            f"fit(s) {stray} are not fitted below their gate by their own "
            f"record (a placeholder, a fit clear of its gate on the key, or "
            f"no fit at all): nothing written")
    in_force = sorted(i for i in set(ids) if chosen[i]["active"])
    if in_force:
        raise Refused(
            f"fit(s) {in_force} carry an activation: whether a fit in force "
            f"is labelled is the operator's question; nothing written")
    stamp = now or utcnow()
    counts = {"written": 0, "already": 0}
    try:
        with transaction(conn):
            for fid in sorted(set(ids)):
                got = chosen[fid]
                if got["already"]:
                    counts["already"] += 1
                    continue
                conn.execute(
                    "INSERT INTO correction_gate_labels (correction_id,"
                    " labelled_utc, verdict, gate, count_used, corrected_count,"
                    " reason) VALUES (?,?,?,?,?,?,?)",
                    (fid, stamp, FITTED_BELOW_ITS_GATE, got["gate"],
                     got["count_used"], got["corrected_count"], got["reason"]))
                counts["written"] += 1
    except sqlite3.IntegrityError as exc:
        # THE SCHEMA SAID NO, and the transaction took every label back.
        raise Refused(f"the record refused a label, so none was written: "
                      f"{exc}") from exc
    return counts


# ---------------------------------------------------------------------------
# THE ACTIVATION ROWS (operator question 32, ruled 2026-09-29)
# ---------------------------------------------------------------------------
#
# "Activation is its own dated append-only row." Every row of
# `correction_activations` is written by `_write_activation`, one statement
# that takes the category's next place itself; the RULES are the schema's,
# and a refusal comes back as `ActivationRefused` carrying the rule's words.


def _write_activation(conn: sqlite3.Connection, fit, kind: str, reason: str, *,
                      now: str | None = None,
                      measurement: dict | None = None) -> dict:
    """Insert one row -- the category's next -- and say what it was. The
    schema decides; this translates. A refused write leaves the connection
    as it found it when this call opened the transaction (the model gate's
    `_write`, for the same reason: a write lock held against the server)."""
    m = measurement or {}
    low, high = m.get("interval") or (None, None)
    stamp = now or utcnow()
    values = (fit["sport"], fit["market_type"], fit["forecaster"], fit["id"],
              stamp, kind, reason, m.get("holdout"), m.get("bets"),
              m.get("holdout_n"), m.get("brier_raw"), m.get("brier_corrected"),
              m.get("improvement"), low, high,
              m.get("seed") if measurement else None,
              m.get("draws") if measurement else None)
    opened_here = not conn.in_transaction
    try:
        # THE PLACE IS TAKEN IN THE SAME STATEMENT, under the write lock, so
        # two writers cannot both take it; an aggregate gives one row even
        # for a category with none yet.
        conn.execute(
            "INSERT INTO correction_activations (sport, market_type,"
            " forecaster, seq, correction_id, activated_utc, kind, reason,"
            " holdout, bets, holdout_n, brier_raw, brier_corrected,"
            " improvement, diff_low, diff_high, bootstrap_seed,"
            " bootstrap_draws)"
            " SELECT ?, ?, ?, COALESCE(MAX(a.seq), 0) + 1, ?, ?, ?, ?, ?, ?,"
            "        ?, ?, ?, ?, ?, ?, ?, ?"
            # the category again, for the aggregate's WHERE
            "   FROM correction_activations a"
            "  WHERE a.sport = ? AND a.market_type = ? AND a.forecaster = ?",
            values + values[:3])
    except sqlite3.IntegrityError as exc:
        if opened_here and conn.in_transaction:
            conn.rollback()
        raise ActivationRefused(str(exc)) from exc
    conn.commit()
    return {"correction_id": fit["id"], "kind": kind, "activated_utc": stamp,
            "sport": fit["sport"], "market_type": fit["market_type"],
            "forecaster": fit["forecaster"]}


def _fit(conn: sqlite3.Connection, correction_id: int):
    fit = conn.execute("SELECT * FROM calibration_corrections WHERE id = ?",
                       (correction_id,)).fetchone()
    if fit is None:
        raise ActivationRefused(f"there is no correction {correction_id}")
    return fit


def activate_measured(conn: sqlite3.Connection, correction_id: int, *,
                      reason: str, now: str | None = None) -> dict:
    """Measure one correction and, ONLY IF IT PASSES THE GATE, write its
    dated measured activation -- in one transaction, so nothing can land on
    the record between the measurement and the row that carries it.

    THE NUMBERS ARE THE MEASUREMENT'S OWN (`measure`, read on this
    connection inside the transaction): a caller cannot hand this a result,
    only a correction. Refused with `ActivationRefused` -- nothing written --
    when the measurement does not pass (a tie goes to the uncorrected
    probability), and when the schema refuses the row. Returns the
    measurement with the row it wrote.

    `now` is for a scratch world: ON A RECORD the schema refuses a row
    stamped more than a minute before it is written (question 32's prover,
    2026-09-29: the door reads the correction in force at an instant, so a
    row dated back put its correction over claims already written), and it
    refuses a measurement drawn any way but the gate's -- 1000 resamples
    from seed 20260923 -- so `measure`'s own `draws` and `seed` are for
    reading, never for a row.
    """
    if not table_columns(conn, ACTIVATIONS):
        raise ActivationRefused(
            "the record has no correction_activations table: it has not been "
            "opened under the schema that carries it (db.init does that, on "
            "any scheduled pass or the server's start after the release)")
    opened_here = not conn.in_transaction
    if opened_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        got = measure(conn, correction_id)
        if not got["passed"]:
            raise ActivationRefused(
                f"correction {correction_id} is not put in force: "
                f"{got['why']}"
                + (f" (improvement {got['improvement']:+.6f}, 95% interval "
                   f"[{got['interval'][0]:+.6f}, {got['interval'][1]:+.6f}], "
                   f"{got['holdout_n']} of {got['bets']} questions held out)"
                   if got.get("interval") else ""))
        row = _write_activation(conn, _fit(conn, correction_id), MEASURED,
                                reason, now=now, measurement=got)
    except BaseException:
        if opened_here and conn.in_transaction:
            conn.rollback()
        raise
    return dict(got, written=row)


def withdraw(conn: sqlite3.Connection, correction_id: int, *, reason: str,
             now: str | None = None) -> dict:
    """Take the correction in force for its category out of force: a dated
    withdrawal row with its reason (ten characters or more). The schema
    refuses one naming any correction but the one in force -- the one the
    category's latest row puts in force, or, where the category has no row
    yet, the one written in force under the rule before question 32 (fit 71,
    by the ruling of 2026-09-29)."""
    return _write_activation(conn, _fit(conn, correction_id), WITHDRAWN,
                             reason, now=now)


def activate_in_a_scratch_world(conn: sqlite3.Connection, correction_id: int,
                                *, now: str | None = None) -> dict:
    """Put a correction in force WITHOUT A MEASUREMENT, in a world that is
    not the live record: the lawful path for a test world, a planting and
    the gate's own pipeline, which have no record to measure on
    (`model.activation.activate_in_a_scratch_world`'s shape and its three
    locks):

      * the file: a connection whose main database IS the live record is
        refused by name, whatever the process is;
      * the record: a database holding a measured or withdrawn activation,
        or a correction written in force under the rule before question 32,
        is a record and not a scratch world, and is refused;
      * the schema: the rule refuses a scratch row on any database whose meta
        kind is 'live'. A fresh file says 'live' until it says otherwise, so
        this DECLARES the world scratch first, and a world that already calls
        itself a backtest keeps that name. AND ON ANY DATABASE HOLDING A
        RECORD'S OWN ROWS, whatever its kind says (question 32's prover,
        2026-09-29: the kind is a meta value no rule holds, so one statement
        setting it to scratch let a raw scratch row land on a record); the
        second lock above, in the schema too.
    """
    from pathlib import Path

    from . import db as _db

    main = next((row[2] for row in conn.execute("PRAGMA database_list")
                 if row[1] == "main"), "")
    if main and _db._is_the_live_record(Path(main)):
        raise ScratchWorldRefused(
            f"{main} is the live record. A correction there comes into force "
            f"by measurement (`correction.activate_measured`), never as a "
            f"scratch world.")
    records = 0
    if table_columns(conn, ACTIVATIONS):
        records = conn.execute(
            "SELECT COUNT(*) FROM correction_activations"
            " WHERE kind IN ('measured', 'withdrawn')").fetchone()[0]
    records += conn.execute(
        "SELECT COUNT(*) FROM calibration_corrections"
        " WHERE active_from IS NOT NULL").fetchone()[0]
    if records:
        raise ScratchWorldRefused(
            f"this database holds {records} correction(s) put in force or "
            f"withdrawn as a record's are, so it is a record and not a scratch "
            f"world. Put a correction in force in a world of your own.")
    if (_db.get_meta(conn, "kind", "live") or "live") == "live":
        _db.set_meta(conn, "kind", "scratch")
        _db.set_meta(conn, "kind_note", (
            "A scratch world: its corrections were put in force without a "
            "measurement, which the live record never allows. Nothing here "
            "is a record of anything."))
    return _write_activation(conn, _fit(conn, correction_id), SCRATCH,
                             SCRATCH_REASON, now=now)
