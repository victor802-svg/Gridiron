"""The scorecard. This is the product; the predictions are just its inputs.

LAW 4 is mechanical here, not editorial. Every figure this module produces is a
dict carrying its own `n`, and `assert_every_figure_has_n()` walks the finished
payload and raises if any number that could be read as a claim is standing
without its sample size. The API calls that validator before serialising, so a
figure cannot reach the browser naked.

Two other things this module refuses to do:

* It never merges categories. Spreads and props are different questions with
  different difficulty, and the statistical and LLM predictors are different
  forecasters. Averaging them produces a curve describing nobody.
* It reports the LARGEST gap, not the best-looking bucket. The sentence at the
  top of the track record is always the worst thing the record says.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field

from . import config, horizon, language
from .factors import compute as factor_compute, registry
from .model import logistic

#: Stated-confidence buckets. Confidence is always >= 0.5 by construction: the
#: model states a side and its confidence in that side.
BUCKETS: tuple[tuple[float, float, str], ...] = (
    (0.50, 0.60, "50-60%"),
    (0.60, 0.70, "60-70%"),
    (0.70, 0.80, "70-80%"),
    (0.80, 1.01, "80%+"),
)

#: Confidence tiers, mapped from the claimed-probability bucket. This is a
#: LABEL over the existing buckets, not a second grouping: a tier's earned
#: figure comes from `bucket_record` — the same function the record page uses —
#: so the number on a pick card and the number on the chart cannot drift apart.
#:
#: STRONG covers two buckets, and each keeps its OWN number. Pooling 70-80% with
#: 80%+ to make one "STRONG hit rate" would be exactly the merge LAW 4 forbids,
#: and it would flatter: the easier bucket would lift the harder one.
TIERS: dict[str, str] = {
    "50-60%": "LEAN",
    "60-70%": "SOLID",
    "70-80%": "STRONG",
    "80%+": "STRONG",
}

#: A tier states its earned accuracy only once its own bucket holds this many
#: settled picks. Deliberately the same constant the calibration chart uses to
#: decide whether a point is provisional — one threshold, one meaning.
TIER_MIN_SETTLED = config.MIN_SAMPLE_FOR_BUCKET_POINT

ALWAYS_HALF_BRIER = 0.25
ALWAYS_HALF_LOG_LOSS = math.log(2.0)

#: Keys that assert a result. Any dict holding one of these must hold `n` too.
CLAIM_KEYS = frozenset(
    {
        "brier",
        "log_loss",
        "actual",
        "hit_rate",
        "resolved_in_model_favour",
        "delta_brier",
        "claimed",
    }
)


class MissingSampleSize(RuntimeError):
    """LAW 4: a figure was about to render without its N."""


#: RE-EXPORTED, not redefined. Both moved to `config`, beside `SPORTS`,
#: because this module names market columns and so cannot be imported by
#: anything on the prediction path -- which left LAW 6's own tripwire out of
#: reach of the modules most likely to need it. See `config.require_sport`.
CrossSportAggregation = config.CrossSportAggregation
require_sport = config.require_sport


def assert_every_figure_has_n(payload, path: str = "$") -> None:
    """Walk a payload and refuse any claim standing without its sample size."""
    if isinstance(payload, dict):
        asserted = CLAIM_KEYS & payload.keys()
        if asserted and "n" not in payload:
            raise MissingSampleSize(
                f"LAW 4: {path} reports {sorted(asserted)} without an 'n'. "
                "No calibration curve, edge estimate or factor verdict renders "
                "without its sample size beside it."
            )
        for key, value in payload.items():
            assert_every_figure_has_n(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            assert_every_figure_has_n(value, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# reading resolved history
# ---------------------------------------------------------------------------

@dataclass
class Resolved:
    id: int
    created_utc: str
    game_id: str
    season: int
    week: int
    market_type: str
    prop_type: str | None
    predictor: str
    factor_set_version: str
    subject: str
    line_asked: float
    model_prob: float
    model_side: str
    outcome: int
    implied_prob: float | None
    factors_json: str = "{}"


def resolved(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
    with_factors: bool = False,
) -> list[Resolved]:
    require_sport(sport, "calibration.resolved")
    where = ["p.resolved_utc IS NOT NULL", "p.sport = ?"]
    params: list = [sport]
    if market_type:
        where.append("p.market_type = ?")
        params.append(market_type)
    if prop_type:
        where.append("p.prop_type = ?")
        params.append(prop_type)
    if predictor:
        where.append("p.predictor = ?")
        params.append(predictor)
    if factor_set_version:
        where.append("p.factor_set_version = ?")
        params.append(factor_set_version)

    rows = conn.execute(
        "SELECT p.id, p.created_utc, p.game_id, g.season, g.week, p.market_type,"
        " p.prop_type, p.predictor, p.factor_set_version, p.subject, p.line_asked,"
        " p.model_prob, p.model_side, p.outcome, p.factors_json,"
        " (SELECT s.implied_prob FROM market_snapshots s WHERE s.prediction_id = p.id"
        "  ORDER BY s.id LIMIT 1) AS implied_prob"
        f" FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE {' AND '.join(where)} ORDER BY p.id",
        params,
    ).fetchall()

    return [
        Resolved(
            id=r["id"],
            created_utc=r["created_utc"],
            game_id=r["game_id"],
            season=r["season"],
            week=r["week"],
            market_type=r["market_type"],
            prop_type=r["prop_type"],
            predictor=r["predictor"],
            factor_set_version=r["factor_set_version"],
            subject=r["subject"],
            line_asked=r["line_asked"],
            model_prob=r["model_prob"],
            model_side=r["model_side"],
            outcome=r["outcome"],
            implied_prob=r["implied_prob"],
            factors_json=r["factors_json"] if with_factors else "{}",
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# the curve
# ---------------------------------------------------------------------------

def calibration_buckets(items: list[Resolved]) -> list[dict]:
    out = []
    for lo, hi, label in BUCKETS:
        chosen = [r for r in items if lo <= r.model_prob < hi]
        n = len(chosen)
        entry: dict = {
            "label": label,
            "lo": lo,
            "hi": min(hi, 1.0),
            "n": n,                       # LAW 4: present even when zero
            "provisional": n < config.MIN_SAMPLE_FOR_BUCKET_POINT,
        }
        if n:
            claimed = sum(r.model_prob for r in chosen) / n
            actual = sum(r.outcome for r in chosen) / n
            entry.update(
                claimed=round(claimed, 4),
                actual=round(actual, 4),
                gap=round(actual - claimed, 4),
            )
        else:
            entry.update(claimed=None, actual=None, gap=None)
        out.append(entry)
    return out


def largest_gap_sentence(buckets: list[dict], minimum_n: int | None = None) -> str:
    """The worst thing the record says, in one sentence. Never the best."""
    minimum_n = config.MIN_SAMPLE_FOR_BUCKET_POINT if minimum_n is None else minimum_n
    usable = [b for b in buckets if b["n"] >= minimum_n and b["gap"] is not None]
    if not usable:
        total = sum(b["n"] for b in buckets)
        if total == 0:
            return "Nothing has resolved yet, so there is no calibration to report."
        return (
            f"{total} predictions have resolved, but no confidence bucket yet holds "
            f"the {minimum_n} needed to say anything about calibration."
        )
    worst = max(usable, key=lambda b: abs(b["gap"]))
    direction = "overconfident" if worst["gap"] < 0 else "underconfident"
    return (
        f"Largest gap: in the {worst['label']} bucket the model claimed "
        f"{worst['claimed'] * 100:.1f}% and was right {worst['actual'] * 100:.1f}% "
        f"of the time across {worst['n']} resolved predictions — "
        f"{direction} by {abs(worst['gap']) * 100:.1f} points."
    )


def score(items: list[Resolved]) -> dict:
    n = len(items)
    if not n:
        return {"n": 0, "brier": None, "log_loss": None, "hit_rate": None}
    probs = [r.model_prob for r in items]
    outcomes = [r.outcome for r in items]
    return {
        "n": n,
        "brier": round(logistic.brier(probs, outcomes), 4),
        "log_loss": round(logistic.log_loss(probs, outcomes), 4),
        "hit_rate": round(sum(outcomes) / n, 4),
    }


def baselines(items: list[Resolved]) -> dict:
    """What the model has to beat: a coin, and the market."""
    out = {
        "always_50": {
            "n": len(items),
            "brier": round(ALWAYS_HALF_BRIER, 4),
            "log_loss": round(ALWAYS_HALF_LOG_LOSS, 4),
            "note": "a forecaster who says 50% to everything",
        }
    }
    with_market = [r for r in items if r.implied_prob is not None]
    if with_market:
        probs = [r.implied_prob for r in with_market]
        outcomes = [r.outcome for r in with_market]
        out["market"] = {
            "n": len(with_market),
            "brier": round(logistic.brier(probs, outcomes), 4),
            "log_loss": round(logistic.log_loss(probs, outcomes), 4),
            "note": (
                "the closing line converted to a probability, scored on the same "
                "questions. This is the number that is hard to beat."
            ),
        }
        # The model's own score restricted to the same subset, so the comparison
        # is like for like rather than across different question sets.
        out["model_on_market_subset"] = score(with_market)
    else:
        out["market"] = {
            "n": 0,
            "brier": None,
            "log_loss": None,
            "note": "no market comparison available for these questions",
        }
    return out


def void_count(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
) -> int:
    require_sport(sport, "calibration.void_count")
    where = ["p.sport = ?"]
    params: list = [sport]
    for column, value in (
        ("market_type", market_type),
        ("prop_type", prop_type),
        ("predictor", predictor),
        ("factor_set_version", factor_set_version),
    ):
        if value:
            where.append(f"p.{column} = ?")
            params.append(value)
    return conn.execute(
        "SELECT COUNT(*) FROM prediction_voids v JOIN predictions p"
        f" ON p.id = v.prediction_id WHERE {' AND '.join(where)}",
        params,
    ).fetchone()[0]


def curve(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
) -> dict:
    require_sport(sport, "calibration.curve")
    items = resolved(
        conn,
        sport=sport,
        market_type=market_type,
        prop_type=prop_type,
        predictor=predictor,
        factor_set_version=factor_set_version,
    )
    buckets = calibration_buckets(items)
    voids = void_count(
        conn, sport=sport, market_type=market_type, prop_type=prop_type,
        predictor=predictor, factor_set_version=factor_set_version,
    )
    return {
        "sport": sport,
        "filters": {
            "sport": sport,
            "market_type": market_type or "all",
            "prop_type": prop_type or "all",
            "predictor": predictor or "all",
            "factor_set_version": factor_set_version or "all",
        },
        "n": len(items),
        "buckets": buckets,
        "largest_gap": largest_gap_sentence(buckets),
        "score": score(items),
        "baselines": baselines(items),
        # Reported beside the curve, never folded into it. A rising void rate is
        # a finding about which questions we are choosing, not a rounding error.
        "voided": voids,
        "void_rate": round(voids / (len(items) + voids), 4) if (len(items) + voids) else None,
    }


# ---------------------------------------------------------------------------
# the edge question — computed, and heavily caveated
# ---------------------------------------------------------------------------

EDGE_STANDING_NOTE = (
    "Beating the market on a small sample is the expected behaviour of luck, not "
    "evidence of an edge. A run of correct disagreements is what chance looks "
    "like at this scale. Nothing here should be read as a claim until the sample "
    f"is well past {config.MIN_SAMPLE_FOR_EDGE_CLAIM} and has survived a season "
    "it was not fitted on."
)


def edge(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str = "spread",
    prop_type: str | None = None,
    predictor: str | None = None,
    threshold: float | None = None,
) -> dict:
    """Where the model disagreed with the market, who was right?

    "Disagreement" means the model was more confident in the side it stated than
    the market's implied probability for that same side, by more than the
    threshold. The reverse subset — where the market was more confident than the
    model — is reported alongside it, because showing only the flattering half
    of a comparison is how a record lies while being technically accurate.
    """
    threshold = config.EDGE_DISAGREEMENT_THRESHOLD if threshold is None else threshold
    require_sport(sport, "calibration.edge")
    items = [
        r
        for r in resolved(
            conn, sport=sport, market_type=market_type, prop_type=prop_type,
            predictor=predictor,
        )
        if r.implied_prob is not None
    ]

    model_bolder = [r for r in items if r.model_prob - r.implied_prob > threshold]
    market_bolder = [r for r in items if r.implied_prob - r.model_prob > threshold]

    def side(subset: list[Resolved], label: str) -> dict:
        n = len(subset)
        entry: dict = {"label": label, "n": n}
        if n:
            entry["resolved_in_model_favour"] = round(
                sum(r.outcome for r in subset) / n, 4
            )
            entry["mean_model_prob"] = round(sum(r.model_prob for r in subset) / n, 4)
            entry["mean_market_prob"] = round(sum(r.implied_prob for r in subset) / n, 4)
        else:
            entry["resolved_in_model_favour"] = None
            entry["mean_model_prob"] = None
            entry["mean_market_prob"] = None
        return entry

    minimum = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    n_eligible = len(model_bolder)
    payload = {
        "sport": sport,
        "market_type": market_type,
        "prop_type": prop_type or "all",
        "predictor": predictor or "all",
        "threshold": threshold,
        "n": len(items),
        "n_disagreements": n_eligible,
        "minimum_for_a_claim": minimum,
        "standing_note": EDGE_STANDING_NOTE,
    }

    if n_eligible < minimum:
        payload["renderable"] = False
        payload["shortfall"] = minimum - n_eligible
        payload["message"] = (
            f"{n_eligible} resolved disagreements of the {minimum} required. "
            f"{minimum - n_eligible} more before this figure will be shown at all."
        )
        return payload

    payload["renderable"] = True
    payload["model_more_confident"] = side(model_bolder, "model more confident")
    payload["market_more_confident"] = side(market_bolder, "market more confident")
    return payload


# ---------------------------------------------------------------------------
# per-factor scoring (LAW 2: is this factor actually doing anything?)
# ---------------------------------------------------------------------------

FACTOR_METHOD_NOTE = (
    "Each factor is scored by removing its contribution from the log-odds of the "
    "predictions it actually took part in, and comparing the Brier score with and "
    "without it. A positive delta means the record was better with the factor in. "
    "This is an attribution within the fitted model, not an independent test of "
    "the idea, and it only counts predictions made from the factor's activation "
    "date forward — never backfitted onto older ones."
)


def factor_report(
    conn: sqlite3.Connection, *, sport: str, factor_set_version: str | None = None
) -> dict:
    require_sport(sport, "calibration.factor_report")
    items = resolved(
        conn,
        sport=sport,
        predictor="statistical",
        factor_set_version=factor_set_version,
        with_factors=True,
    )

    stats: dict[str, dict] = {}
    for r in items:
        payload = json.loads(r.factors_json or "{}")
        contributions = payload.get("contributions") or []
        log_odds = payload.get("log_odds")
        question = payload.get("question") or {}
        yes_label = question.get("yes_label")
        absent = set(factor_compute.absent_factors(payload))
        if log_odds is None or not contributions or not yes_label:
            continue
        outcome_yes = r.outcome if r.model_side == yes_label else 1 - r.outcome

        for c in contributions:
            name = c["factor"]
            declared = registry.REGISTRY.get(name)
            if declared and r.created_utc < declared.added_utc:
                continue  # never scored before it existed
            bucket = stats.setdefault(
                name,
                {
                    "n": 0,
                    "with": 0.0,
                    "without": 0.0,
                    "abs_contribution": 0.0,
                    "nonzero": 0,
                    "defaulted": 0,
                },
            )
            p_with = logistic.sigmoid(log_odds)
            p_without = logistic.sigmoid(log_odds - c["contribution"])
            bucket["n"] += 1
            bucket["with"] += (p_with - outcome_yes) ** 2
            bucket["without"] += (p_without - outcome_yes) ** 2
            bucket["abs_contribution"] += abs(c["contribution"])
            # Whether the INPUT varied at all, kept apart from whether the
            # factor mattered. A factor the schedule never lets move is an
            # untested hypothesis, not a disproved one.
            if abs(c.get("value") or 0.0) > 1e-9:
                bucket["nonzero"] += 1
            if name in absent:
                bucket["defaulted"] += 1

    factors = []
    for f in registry.all_factors(sport=sport):
        entry: dict = {
            "factor": f.name,
            "added_utc": f.added_utc,
            "active": f.active,
            "applies_to": list(f.applies_to),
            "rationale": f.rationale,
            "note": f.note,
            "n": 0,
            "brier": None,
            "delta_brier": None,
            "mean_abs_contribution": None,
            "verdict": "no resolved predictions yet",
        }
        s = stats.get(f.name)
        if s and s["n"]:
            n = s["n"]
            with_brier = s["with"] / n
            without_brier = s["without"] / n
            mean_abs = s["abs_contribution"] / n
            nonzero_share = s["nonzero"] / n
            defaulted_share = s["defaulted"] / n
            entry.update(
                n=n,
                brier=round(with_brier, 4),
                brier_without=round(without_brier, 4),
                delta_brier=round(without_brier - with_brier, 5),
                mean_abs_contribution=round(mean_abs, 4),
                nonzero_share=round(nonzero_share, 4),
                defaulted_share=round(defaulted_share, 4),
                verdict=_factor_verdict(
                    without_brier - with_brier, mean_abs, n, nonzero_share, defaulted_share
                ),
            )
        elif not f.active:
            entry["verdict"] = "inactive; never used in a prediction"
        factors.append(entry)

    # What the current fit could actually do with each factor. A factor absent
    # from every training row, or present but never varying, has no coefficient
    # to score and would otherwise show as "no resolved predictions yet", which
    # reads like patience when it is really a measurement problem.
    fit_status = _fit_status(conn, sport, factor_set_version or config.FACTOR_SET_VERSION)
    for entry in factors:
        status = fit_status.get(entry["factor"])
        if not status:
            continue
        entry["training_rows_measured"] = status.get("presence")
        entry["excluded_from_fit"] = status.get("excluded")
        if status.get("excluded") and not entry["n"]:
            entry["verdict"] = status["reason"]

    factors.sort(key=lambda e: (-(e["delta_brier"] or -9), e["factor"]))
    return {
        "n": len(items),
        "sport": sport,
        "method": FACTOR_METHOD_NOTE,
        "factor_set_version": factor_set_version or config.FACTOR_SET_VERSION,
        "factors": factors,
    }


def _fit_status(conn: sqlite3.Connection, sport: str, version: str) -> dict[str, dict]:
    """Per-factor presence in the most recent fit of each of the sport's markets."""
    out: dict[str, dict] = {}
    for market in config.SPORT_MARKETS.get(sport, ()):
        market_type = market if market in ("spread", "moneyline") else f"prop:{market}"
        row = conn.execute(
            "SELECT coefficients_json FROM model_fits"
            " WHERE sport = ? AND market_type = ? AND factor_set_version = ?"
            " ORDER BY id DESC LIMIT 1",
            (sport, market_type, version),
        ).fetchone()
        if row is None:
            continue
        blob = json.loads(row["coefficients_json"])
        total = blob.get("n") or 0
        for name, count in (blob.get("presence") or {}).items():
            out.setdefault(name, {"presence": count, "excluded": False})
        for name, count in (blob.get("constant") or {}).items():
            out[name] = {
                "presence": count,
                "excluded": True,
                "reason": (
                    f"never varied where it could be measured - one value across all "
                    f"{count:,} of {total:,} training rows that carried it, so there "
                    "is nothing to fit and nothing to score"
                ),
            }
        for name, count in (blob.get("dropped") or {}).items():
            out[name] = {
                "presence": count,
                "excluded": True,
                "reason": (
                    f"measurable in only {count:,} of {total:,} training rows, below "
                    "the floor for estimating a coefficient at all"
                ),
            }
    return out


def _factor_verdict(
    delta: float, mean_abs: float, n: int, nonzero_share: float, defaulted_share: float
) -> str:
    """Three different kinds of "nothing", told apart.

    A factor can look inert because its data was never available, because the
    world almost never let it vary, or because it genuinely does not matter.
    Only the third is a verdict on the hypothesis; reporting all three as
    "inert" would quietly retire good ideas for bad reasons.
    """
    if defaulted_share > 0.9:
        return (
            f"no data — defaulted in {defaulted_share * 100:.0f}% of predictions, "
            "so this has never actually been tested"
        )
    if nonzero_share < 0.05:
        return (
            f"input almost never varies ({nonzero_share * 100:.1f}% non-zero); "
            "untested rather than disproved"
        )
    if mean_abs < 0.005:
        return "inert — it barely moves any forecast"
    if n < config.MIN_SAMPLE_FOR_BUCKET_POINT:
        return f"too few resolved predictions ({n}) to say"
    if delta > 0.002:
        return "carrying weight"
    if delta < -0.002:
        return "costing accuracy"
    return "no measurable effect either way"


# ---------------------------------------------------------------------------
# the whole thing
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TWO PRE-LAW-6 FUNCTIONS WERE DELETED HERE, and they were not dead weight.
# ---------------------------------------------------------------------------
#
# `scorecard(conn)` and `version_comparison(conn)` -- no `sport` argument --
# were the versions from before LAW 6. Each queried `predictions` with no
# sport filter, which is the merged-across-sports read LAW 6 exists to make
# impossible. They were REPLACED further down the file by the `*, sport:`
# versions, and the old bodies were left in place.
#
# Python discards a shadowed definition, so neither ran. That is exactly why
# nothing caught them: `require_sport` never fired because the code never
# executed, the orphan scan saw the NAME reached (by the live definition's
# callers) and passed, and every test called the live one. Four hundred lines
# of a forbidden query, invisible to every guard in the project.
#
# Found by editing one of them and watching the output not change.
# `audit.check_no_shadowed_definitions` now fails on a redefined name.


def version_words(version: str) -> str:
    """A factor set named the way a person would name it: by when it started.

    "fs2" is an internal identifier -- it says neither what changed nor when,
    and the plain-words scan is right to reject it. The activation date is the
    thing that distinguishes one set from another to a reader, and it is
    already recorded. The code stays in the payload for matching against a
    stored row; it just does not reach the prose.
    """
    started = config.FACTOR_SET_ACTIVATED.get(version)
    return f"the set of {started[:10]}" if started else "an undated set"


def bucket_label(probability: float) -> str:
    """Which confidence bucket a stated probability falls in."""
    for lo, hi, label in BUCKETS:
        if lo <= probability < hi:
            return label
    return BUCKETS[-1][2]


def bucket_record(
    conn: sqlite3.Connection,
    probability: float,
    *,
    sport: str,
    market_type: str,
    prop_type: str | None = None,
    predictor: str = "statistical",
    factor_set_version: str | None = None,
) -> dict:
    """How this bucket has actually done, for the chip on a pick card.

    Always carries `n`, including when `n` is zero. A chip that showed an
    accuracy without its sample size would be the most persuasive lie on the
    page: it sits right next to a specific forecast and reads as a track record
    for THAT pick.
    """
    label = bucket_label(probability)
    lo, hi = next((lo, hi) for lo, hi, name in BUCKETS if name == label)
    require_sport(sport, "calibration.bucket_record")
    items = [
        r
        for r in resolved(
            conn, sport=sport, market_type=market_type, prop_type=prop_type,
            predictor=predictor, factor_set_version=factor_set_version,
        )
        if lo <= r.model_prob < hi
    ]
    n = len(items)
    entry = {
        "label": label,
        "n": n,
        "provisional": n < config.MIN_SAMPLE_FOR_BUCKET_POINT,
        "minimum": config.MIN_SAMPLE_FOR_BUCKET_POINT,
    }
    if n:
        entry["actual"] = round(sum(r.outcome for r in items) / n, 4)
        entry["claimed"] = round(sum(r.model_prob for r in items) / n, 4)
    else:
        entry["actual"] = None
        entry["claimed"] = None
        entry["message"] = f"no resolved predictions in the {label} bucket yet"
    return entry


def tier_from_bucket(bucket: dict) -> dict:
    """The tier chip for a pick, derived from the bucket record it already has.

    Takes the dict `bucket_record` returned rather than re-querying, so there is
    exactly one place that counts a bucket and exactly one number it can
    produce. `earned` is None below the threshold and the caller renders the
    shortfall instead — a tier that showed a hit rate on nine settled picks
    would be the most persuasive lie on the page, sitting beside a specific
    forecast and reading as a track record for it.
    """
    label = bucket.get("label")
    tier = TIERS.get(label)
    if tier is None:
        return {"tier": None, "earned": None, "n": 0, "proven": False,
                "message": "no tier for this probability"}

    n = bucket.get("n") or 0
    proven = n >= TIER_MIN_SETTLED
    entry = {
        "tier": tier,
        "bucket": label,
        "n": n,
        "needed": TIER_MIN_SETTLED,
        "proven": proven,
        "earned": bucket.get("actual") if proven else None,
    }
    entry["message"] = (
        f"this tier hits {round((entry['earned'] or 0) * 100)}% over {n} settled"
        if proven
        else f"tier unproven - {n} settled of {TIER_MIN_SETTLED} needed"
    )
    return entry


def over_time(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str = "statistical",
    factor_set_version: str | None = None,
) -> dict:
    """Weekly calibration points: how far claimed sat from actual, week by week.

    Each point carries its own n. Weeks are never smoothed into each other,
    because a rolling average across a thin week and a fat one is a line drawn
    through a sample size that never existed.
    """
    require_sport(sport, "calibration.over_time")
    items = resolved(
        conn, sport=sport, market_type=market_type, prop_type=prop_type,
        predictor=predictor, factor_set_version=factor_set_version,
    )
    weeks: dict[tuple[int, int], list[Resolved]] = {}
    for r in items:
        weeks.setdefault((r.season, r.week), []).append(r)

    points = []
    running = 0
    for (season, week) in sorted(weeks):
        chosen = weeks[(season, week)]
        n = len(chosen)
        running += n
        claimed = sum(r.model_prob for r in chosen) / n
        actual = sum(r.outcome for r in chosen) / n
        points.append({
            "season": season,
            "week": week,
            "label": f"{season} wk{week}",
            "n": n,
            "cumulative_n": running,
            "claimed": round(claimed, 4),
            "actual": round(actual, 4),
            "gap": round(actual - claimed, 4),
            "brier": round(logistic.brier(
                [r.model_prob for r in chosen], [r.outcome for r in chosen]), 4),
            "provisional": n < config.MIN_SAMPLE_FOR_BUCKET_POINT,
        })

    return {
        "n": len(items),
        "sport": sport,
        "filters": {
            "sport": sport,
            "market_type": market_type or "all",
            "prop_type": prop_type or "all",
            "predictor": predictor,
            "factor_set_version": factor_set_version or "all",
        },
        "points": points,
        "note": (
            "One point per week, each with its own N. Nothing is smoothed: a "
            "rolling average across a thin week and a fat one draws a line "
            "through a sample size that never existed."
        ),
    }


class MergedCurve(RuntimeError):
    """Two categories were averaged into one, which describes neither."""


def assert_no_merged_categories(payload: dict) -> None:
    """Every scoring category names exactly one concrete market of one sport.

    A "props" curve averaging rebounds with threes, a curve with
    `market_type: all`, or anything spanning two sports flatters reliably: the
    easy category dilutes the hard one and the result describes nobody. Checked
    on the payload rather than trusted to the code that built it.
    """
    sport = payload.get("sport")
    declared = set(config.SPORT_MARKETS.get(sport, ()))
    for category in payload.get("categories") or []:
        if category.get("sport") != sport:
            raise CrossSportAggregation(
                f"LAW 6: category {category.get('category')!r} reports sport "
                f"{category.get('sport')!r} inside a {sport!r} scorecard."
            )
        market = category.get("market")
        if market not in declared:
            raise MergedCurve(
                f"LAW: category {category.get('category')!r} reports market "
                f"{market!r}, which is not one of {sport}'s declared markets "
                f"{sorted(declared)}. Curves are never merged."
            )
        filters = category.get("filters") or {}
        if filters.get("predictor") in (None, "all"):
            raise MergedCurve(
                f"LAW: category {category.get('category')!r} merges the "
                "statistical and LLM forecasters into one curve."
            )
        is_prop = market in config.SPORT_PROP_MARKETS.get(sport, ())
        if is_prop and filters.get("prop_type") in (None, "all"):
            raise MergedCurve(
                f"LAW: category {category.get('category')!r} is a prop category "
                "with no prop_type filter, so it averages every prop market "
                "into a single number."
            )


def assert_single_sport(payload, sport: str, path: str = "$") -> None:
    """LAW 6, on the finished payload: no nested figure names another sport.

    `require_sport` stops a cross-sport QUERY. This stops a cross-sport
    PAYLOAD — two individually correct queries stitched into one object that a
    reader would take for a single record.
    """
    if isinstance(payload, dict):
        if payload.get("side_by_side_sports"):
            # The one permitted multi-sport structure: the tab summary, which
            # lists every sport with its OWN counts and computes no total. LAW 6
            # forbids aggregating across sports, not displaying them beside each
            # other; this flag marks the difference explicitly rather than
            # leaving the validator to guess.
            return
        found = payload.get("sport")
        if found is not None and found != sport:
            raise CrossSportAggregation(
                f"LAW 6: {path} carries sport={found!r} inside a {sport!r} "
                "payload. Sports are reported side by side, never stitched "
                "into one record."
            )
        for key, value in payload.items():
            assert_single_sport(value, sport, f"{path}.{key}")
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            assert_single_sport(value, sport, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# factor-set versions: closed records and accumulating ones, never summed
# ---------------------------------------------------------------------------

VERSION_NOTE = (
    "A factor set is a different forecaster. Its record begins at N=0 on the day "
    "it was activated and nothing earlier is backfitted onto it (LAW 2). The "
    "versions below are reported side by side and are NEVER added together: a "
    "closed record and an accumulating one describe different models, and their "
    "sum describes neither."
)


def market_type_of(sport: str, market: str) -> str:
    """The `market_type` column value a named market is stored under."""
    if market in config.SPORT_PROP_MARKETS.get(sport, ()):
        return "prop"
    return market      # 'spread' or 'moneyline'


def prop_type_of(sport: str, market: str) -> str | None:
    return market if market in config.SPORT_PROP_MARKETS.get(sport, ()) else None


#: A factor's effect may order a sentence only when it rests on at least this
#: many settled predictions -- the same gate the tier table uses for a bucket.
#: Reused rather than invented: a second small-sample threshold with a
#: different number would be two answers to one question.
RANK_MIN_SETTLED = TIER_MIN_SETTLED


def _rank_changes(changes: dict, effects: dict) -> tuple[dict, str]:
    """Order a set's joined factors by measured effect, IF the record allows.

    "The two most consequential changes" needs consequence to be measured, and
    the only measurement here is a factor's effect on the record. Today every
    sport is at 2 to 25 settled predictions per factor; ordering by an effect
    computed on two is not a ranking, it is noise with a sort applied, and the
    sentence that came out of it would claim the two named mattered most.

    So the gate is explicit and the caller is TOLD which happened: with enough
    behind every candidate the list is sorted by |effect| and the line may say
    "the two that moved the answer most"; without it the declaration order
    stands and the line claims nothing about size.
    """
    joined = changes.get("joined") or []
    if not joined:
        return changes, "declaration"

    scored = []
    for item in joined:
        row = effects.get(item.get("name")) or {}
        n = row.get("n") or 0
        size = row.get("mean_abs_contribution")
        if n < RANK_MIN_SETTLED or size is None:
            return changes, "declaration"
        scored.append((abs(float(size)), item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    ranked = dict(changes)
    ranked["joined"] = [item for _size, item in scored]
    return ranked, "effect"


def version_comparison(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Every factor set that has produced predictions FOR THIS SPORT."""
    require_sport(sport, "calibration.version_comparison")
    seen = [
        r["v"]
        for r in conn.execute(
            "SELECT DISTINCT factor_set_version AS v FROM predictions"
            " WHERE sport = ? ORDER BY v",
            (sport,),
        )
    ]
    known = list(config.FACTOR_SET_HISTORY)
    versions = known + [v for v in seen if v not in known]

    # Each set's window runs from its own activation to the NEXT one's, so
    # "what changed" is read straight out of the registry rather than kept as a
    # hand-written changelog beside the version constant.
    # What each factor has actually been worth, for ordering the change lines.
    # Read once for the sport rather than per version: it is the same report.
    effects = {
        f["factor"]: f
        for f in (factor_report(conn, sport=sport).get("factors") or [])
    }
    starts = {v: (config.FACTOR_SET_ACTIVATED.get(v) or "")[:10] for v in versions}
    ordered = sorted([v for v in versions if starts.get(v)], key=lambda v: starts[v])

    entries = []
    for version in versions:
        counts = conn.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved"
            " FROM predictions WHERE sport = ? AND factor_set_version = ?",
            (sport, version),
        ).fetchone()
        total = counts["total"] or 0
        n_resolved = counts["resolved"] or 0
        is_current = version == config.FACTOR_SET_VERSION

        categories = []
        for market in config.SPORT_MARKETS.get(sport, ()):
            for predictor in ("statistical", "llm"):
                items = resolved(
                    conn,
                    sport=sport,
                    market_type=market_type_of(sport, market),
                    prop_type=prop_type_of(sport, market),
                    predictor=predictor,
                    factor_set_version=version,
                )
                if not items and not is_current:
                    continue
                categories.append({
                    "category": f"{market} / {predictor}",
                    "market": market,
                    "predictor": predictor,
                    **score(items),
                })

        start = starts.get(version) or None
        pos = ordered.index(version) if version in ordered else None
        nxt = ordered[pos + 1] if pos is not None and pos + 1 < len(ordered) else None
        changes = registry.set_changes(sport, start, starts.get(nxt)) if start else {}
        changes, ranked_by = _rank_changes(changes, effects)

        entry = {
            "version": version,
            "activated_utc": config.FACTOR_SET_ACTIVATED.get(version),
            # WHAT changed, not only when: derived from the registry's own
            # dates, so the line cannot drift from the factors it describes.
            "changed": (language.set_change_line(
                changes, first=(pos == 0), ranked_by=ranked_by,
                sport_label=config.SPORT_LABELS.get(sport, sport))
                if start else None),
            # THE FULL LIST, under the summary line. The line names two; the
            # ruling says the rest stays on the page rather than being lost to
            # a count, so it is carried here rather than left to the reader to
            # go and find on another page.
            "changed_detail": {
                "ranked_by": ranked_by,
                "joined": changes.get("joined") or [],
                "left": changes.get("left") or [],
                "tried_and_dropped": changes.get("tried_and_dropped") or [],
            } if start else None,
            "status": "current" if is_current else "closed",
            "n": n_resolved,
            "predictions_written": total,
            "open": total - n_resolved,
            "categories": categories,
        }
        if n_resolved == 0:
            label = config.SPORT_LABELS.get(sport, sport)
            entry["message"] = (
                f"{version_words(version).capitalize()} has {total} "
                f"prediction(s) written for {label} and 0 "
                "resolved. Its record begins at N=0 on activation"
                + ". Nothing is carried over from an earlier version, so there "
                "is nothing to show yet and nothing wrong."
            )
        entries.append(entry)

    return {
        "n": sum(e["n"] for e in entries),
        "sport": sport,
        "current": config.FACTOR_SET_VERSION,
        "note": VERSION_NOTE,
        "never_summed": True,
        "versions": entries,
    }


def scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Every curve for ONE sport, kept separate. Never a merged headline."""
    require_sport(sport, "calibration.scorecard")
    markets = config.SPORT_MARKETS.get(sport, ())

    categories = []
    for market in markets:
        for predictor in ("statistical", "llm"):
            c = curve(conn, sport=sport,
                      market_type=market_type_of(sport, market),
                      prop_type=prop_type_of(sport, market),
                      predictor=predictor)
            c["category"] = f"{market} / {predictor}"
            c["market"] = market
            # RULING R3: a gate that will not be reached is not a gate that has
            # not been reached YET, and rendering them alike reads as progress.
            # Attached per category, statistical only -- the LLM predictor
            # answers the same questions, so one projection covers both and two
            # would invite a reader to add them.
            if predictor == "statistical":
                c["outlook"] = horizon.market_outlook(conn, sport, market)
            categories.append(c)

    headline_market = markets[0] if markets else "spread"
    headline = curve(conn, sport=sport,
                     market_type=market_type_of(sport, headline_market),
                     prop_type=prop_type_of(sport, headline_market),
                     predictor="statistical")
    headline["market"] = headline_market

    payload = {
        "sport": sport,
        "sport_label": config.SPORT_LABELS.get(sport, sport.upper()),
        "generated_for_factor_set": config.FACTOR_SET_VERSION,
        "headline": headline,
        "headline_market": headline_market,
        # THE TIER TABLE leads the Record tab. Same bucket math as the chips on
        # every pick card -- one implementation, so the two cannot drift.
        "tier_table": tier_table(
            conn, sport=sport,
            market_type=market_type_of(sport, headline_market),
            prop_type=prop_type_of(sport, headline_market),
            predictor="statistical",
        ),
        "categories": categories,
        "markets": list(markets),
        "edge": edge(conn, sport=sport,
                     market_type=market_type_of(sport, headline_market),
                     prop_type=prop_type_of(sport, headline_market),
                     predictor="statistical"),
        "versions": version_comparison(conn, sport=sport),
        "separation_note": (
            "Curves are never merged, and never across sports (LAW 6). Each "
            "market is its own category with its own gate, and the statistical "
            "and LLM predictors are different forecasters. An average across "
            "any of these describes nobody."
        ),
    }
    assert_every_figure_has_n(payload)
    assert_no_merged_categories(payload)
    assert_single_sport(payload, sport)
    return payload

# ---------------------------------------------------------------------------
# THE TIER TABLE — the record as the operator already reads it
# ---------------------------------------------------------------------------
#
# The Record tab led with a calibration chart. A chart is the right shape for
# somebody auditing the model and the wrong shape for the question a reader
# actually has, which is "when it says STRONG, is it?". This is that question as
# a table, in the same vocabulary the tier chips on every pick already use.
#
# ONE ROW PER BUCKET, NOT PER TIER, AND THAT IS NOT A DETAIL. The brief that
# asked for this said the buckets and the tiers are "the same partition (LEAN
# 50-60, SOLID 60-70, STRONG 70%+)". They are not: there are four buckets and
# three tiers, because STRONG spans 70-80% AND 80%+. Collapsing them into one
# STRONG row is precisely the merge LAW 4 forbids, and it flatters in a
# predictable direction -- the easier bucket lifts the harder one, so a model
# that is well calibrated at 80%+ and badly calibrated at 70-80% would show a
# single reassuring number.
#
# So STRONG appears twice, labelled with its band. The table answers the same
# question and cannot tell that particular lie.

#: How far actual may sit from claimed before the verdict stops saying so, in
#: PERCENTAGE POINTS. Dated because it is a judgement about what "about right"
#: means, not a measurement.
VERDICT_BANDS_DECLARED = "2026-08-31T00:00:00Z"
VERDICT_CLOSE_ENOUGH = 3.0      # within this, the claim is honest
VERDICT_BADLY_OFF = 8.0         # beyond this, the claim is not close


def tier_verdict(claimed: float | None, actual: float | None, n: int) -> str:
    """The verdict words for one row, from a fixed rule on (actual - claimed).

    Below the gate there is no verdict, only the shortfall: a row with nine
    settled picks has nothing to say about calibration and must not imply it
    does (LAW 4). No italics, no hedge, no number.
    """
    if n < TIER_MIN_SETTLED:
        return f"unproven — {n} of {TIER_MIN_SETTLED}"
    if claimed is None or actual is None:
        return f"unproven — {n} of {TIER_MIN_SETTLED}"

    # Rounded to one decimal BEFORE the comparison. 0.53 - 0.50 is
    # 3.0000000000000027 in binary floating point, so a gap the rule calls
    # "close enough" fell out of its own band and read "overconfident by 3.0
    # points" -- a boundary decided by representation error rather than by the
    # declared threshold.
    gap = round((actual - claimed) * 100.0, 1)
    if abs(gap) <= VERDICT_CLOSE_ENOUGH:
        return "about as good as it claims"
    if gap > VERDICT_CLOSE_ENOUGH:
        return "better than it claims"
    if gap >= -VERDICT_BADLY_OFF:
        # ONE DECIMAL, not zero. A gap of 3.4 rounded to "3 points" sits
        # directly beside a rule that calls anything within 3 points honest,
        # and a reader is entitled to conclude one of them is wrong. The
        # decimal costs a character and removes the contradiction.
        return f"overconfident by {abs(gap):.1f} points"
    return "much more confident than it should be"


def tier_table(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str,
    prop_type: str | None = None,
    predictor: str = "statistical",
) -> dict:
    """One row per confidence band, with its verdict.

    EVERY NUMBER COMES FROM `bucket_record`, the same function the tier chip on
    a pick card calls. Not a reimplementation that happens to agree today: the
    chip and this table cannot drift, because there is one place that counts a
    bucket and one number it can produce.
    """
    require_sport(sport, "calibration.tier_table")

    rows = []
    for lo, hi, label in BUCKETS:
        midpoint = (lo + min(hi, 1.0)) / 2.0
        bucket = bucket_record(
            conn, midpoint, sport=sport, market_type=market_type,
            prop_type=prop_type, predictor=predictor,
        )
        n = bucket.get("n") or 0
        proven = n >= TIER_MIN_SETTLED
        claimed = bucket.get("claimed") if proven else None
        actual = bucket.get("actual") if proven else None
        rows.append({
            "tier": TIERS.get(label),
            "band": label,
            "n": n,
            "settled": n,
            "right": round((actual or 0) * n) if proven else None,
            "claimed": claimed,
            "actual": actual,
            "proven": proven,
            "needed": TIER_MIN_SETTLED,
            "verdict": tier_verdict(claimed, actual, n),
        })

    return {
        "sport": sport,
        "market_type": market_type,
        "prop_type": prop_type,
        "predictor": predictor,
        "rows": rows,
        "n": sum(r["n"] for r in rows),
        "minimum": TIER_MIN_SETTLED,
        "headline": _tier_headline(rows),
        "bands_note": (
            "One row per confidence band. STRONG spans two bands and they are "
            "shown separately: pooling them would let the easier one lift the "
            "harder one, which is the merge LAW 4 forbids."
        ),
    }


def _tier_headline(rows: list[dict]) -> str:
    """One sentence above the table: the LARGEST GAP, never the flattering row.

    A headline that picked the best-looking band would be the model marking its
    own homework. Where nothing is proven, it says that instead.
    """
    proven = [r for r in rows if r["proven"]]
    if not proven:
        best = max(rows, key=lambda r: r["n"]) if rows else None
        if best is None or not best["n"]:
            return "Nothing has resolved yet, so there is nothing to grade."
        return (
            f"No band has the {TIER_MIN_SETTLED} settled picks needed to grade "
            f"calibration — the fullest has {best['n']}."
        )

    worst = max(proven, key=lambda r: abs((r["actual"] or 0) - (r["claimed"] or 0)))
    actual = (worst["actual"] or 0) * 100
    return (
        f"{worst['tier']} picks in the {worst['band']} band have been right "
        f"{actual:.0f}% of the time over {worst['n']} — {worst['verdict']}."
    )
