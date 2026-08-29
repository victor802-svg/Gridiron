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

from . import config
from .factors import registry
from .model import logistic

#: Stated-confidence buckets. Confidence is always >= 0.5 by construction: the
#: model states a side and its confidence in that side.
BUCKETS: tuple[tuple[float, float, str], ...] = (
    (0.50, 0.60, "50-60%"),
    (0.60, 0.70, "60-70%"),
    (0.70, 0.80, "70-80%"),
    (0.80, 1.01, "80%+"),
)

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
    market_type: str
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
    market_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
    with_factors: bool = False,
) -> list[Resolved]:
    where = ["p.resolved_utc IS NOT NULL"]
    params: list = []
    if market_type:
        where.append("p.market_type = ?")
        params.append(market_type)
    if predictor:
        where.append("p.predictor = ?")
        params.append(predictor)
    if factor_set_version:
        where.append("p.factor_set_version = ?")
        params.append(factor_set_version)

    rows = conn.execute(
        "SELECT p.id, p.created_utc, p.game_id, p.market_type, p.predictor,"
        " p.factor_set_version, p.subject, p.line_asked, p.model_prob, p.model_side,"
        " p.outcome, p.factors_json,"
        " (SELECT s.implied_prob FROM market_snapshots s WHERE s.prediction_id = p.id"
        "  ORDER BY s.id LIMIT 1) AS implied_prob"
        f" FROM predictions p WHERE {' AND '.join(where)} ORDER BY p.id",
        params,
    ).fetchall()

    return [
        Resolved(
            id=r["id"],
            created_utc=r["created_utc"],
            game_id=r["game_id"],
            market_type=r["market_type"],
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


def curve(
    conn: sqlite3.Connection,
    *,
    market_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
) -> dict:
    items = resolved(
        conn,
        market_type=market_type,
        predictor=predictor,
        factor_set_version=factor_set_version,
    )
    buckets = calibration_buckets(items)
    return {
        "filters": {
            "market_type": market_type or "all",
            "predictor": predictor or "all",
            "factor_set_version": factor_set_version or "all",
        },
        "n": len(items),
        "buckets": buckets,
        "largest_gap": largest_gap_sentence(buckets),
        "score": score(items),
        "baselines": baselines(items),
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
    market_type: str = "spread",
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
    items = [
        r
        for r in resolved(conn, market_type=market_type, predictor=predictor)
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
        "market_type": market_type,
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
    conn: sqlite3.Connection, *, factor_set_version: str | None = None
) -> dict:
    items = resolved(
        conn,
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
        missing = set(payload.get("missing") or [])
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
            if name in missing:
                bucket["defaulted"] += 1

    factors = []
    for f in registry.REGISTRY.values():
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

    factors.sort(key=lambda e: (-(e["delta_brier"] or -9), e["factor"]))
    return {
        "n": len(items),
        "method": FACTOR_METHOD_NOTE,
        "factor_set_version": factor_set_version or config.FACTOR_SET_VERSION,
        "factors": factors,
    }


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

def scorecard(conn: sqlite3.Connection) -> dict:
    """Every curve, kept separate. Never a merged headline number."""
    versions = [
        r["v"]
        for r in conn.execute(
            "SELECT DISTINCT factor_set_version AS v FROM predictions"
            " WHERE resolved_utc IS NOT NULL ORDER BY v"
        )
    ]
    categories = []
    for market_type in ("spread", "prop"):
        for predictor in ("statistical", "llm"):
            c = curve(conn, market_type=market_type, predictor=predictor)
            c["category"] = f"{market_type} / {predictor}"
            categories.append(c)

    headline = curve(conn, market_type="spread", predictor="statistical")
    payload = {
        "generated_for_factor_set": config.FACTOR_SET_VERSION,
        "factor_set_versions_in_record": versions,
        "headline": headline,
        "categories": categories,
        "edge": edge(conn, market_type="spread", predictor="statistical"),
        "separation_note": (
            "Curves are never merged. Spreads and props are different questions, "
            "and the statistical and LLM predictors are different forecasters; an "
            "average across them describes nobody."
        ),
    }
    assert_every_figure_has_n(payload)
    return payload
