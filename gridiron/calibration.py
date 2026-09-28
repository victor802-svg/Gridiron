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

from . import bet, config, horizon, language
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


#: HOW MANY EARLY/FINAL PAIRS BEFORE THE COMPARISON SAYS ANYTHING (A2).
#:
#: Fifty, and it is deliberately not the 100 of MIN_SAMPLE_FOR_EDGE_CLAIM,
#: because this is not an edge claim. It compares two forecasts of the SAME
#: game against the same outcome, so the pairing removes most of the variance
#: an edge estimate has to fight through -- the games are identical and only
#: the information differs. Below fifty the panel shows the COUNT and no
#: verdict, which is LAW 4's shape applied to a smaller question.
MIN_PAIRS_FOR_TIMING_VERDICT = 50


def early_vs_final(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Did forecasting later actually help? The number, not an opinion.

    THIS IS THE POINT OF THE WHOLE MECHANISM. Moving the graded forecast close
    to start is a bet that the market's edge on our confident disagreements
    (55.6% on n=207, docs/DIAGNOSIS.md) is partly an information gap we are
    inflicting on ourselves by asking early. That bet might be wrong. A later
    forecast could be a worse one -- more news is not automatically more
    signal, and a lineup can push a model around for no gain.

    So nothing here assumes it. On every resolved question that has BOTH a
    row from the early pass and one from the final pass, this reports how
    often the side changed, how far the claim moved, and which pass scored
    better by Brier. The number decides, on its date.

    LAW 6: one sport, required.
    """
    require_sport(sport, "early_vs_final")
    rows = conn.execute(
        "SELECT e.game_id, e.market_type, e.subject, e.predictor,"
        "       e.model_prob AS early_prob, e.model_side AS early_side,"
        "       f.model_prob AS final_prob, f.model_side AS final_side,"
        "       e.outcome"
        "  FROM predictions e"
        "  JOIN predictions f"
        "    ON f.game_id = e.game_id AND f.market_type = e.market_type"
        "   AND f.subject = e.subject AND f.predictor = e.predictor"
        "   AND f.factor_set_version = e.factor_set_version"
        "   AND IFNULL(f.line_asked, -1e9) = IFNULL(e.line_asked, -1e9)"
        "   AND f.pass_kind = 'final'"
        " WHERE e.sport = ? AND e.pass_kind = 'early'"
        # BOTH ROWS RESOLVED, and to the same outcome. They are two forecasts
        # of one question, so a disagreement about what happened would be a
        # resolution bug rather than a timing finding.
        "   AND e.resolved_utc IS NOT NULL AND f.resolved_utc IS NOT NULL"
        "   AND e.outcome = f.outcome"
        # NEITHER ROW VOIDED (ruling 1, 2026-09-24), even after it settled.
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id IN (e.id, f.id))",
        (sport,)).fetchall()

    pairs = len(rows)
    changed = sum(1 for r in rows if r["early_side"] != r["final_side"])
    moved = [abs(r["final_prob"] - r["early_prob"]) for r in rows]
    early_better = final_better = 0
    early_brier = final_brier = 0.0
    for r in rows:
        # Brier against the row's OWN stated side: each pass is scored on the
        # claim it actually made, which is the only fair comparison when the
        # two passes may have named opposite sides.
        e = (r["early_prob"] - float(r["outcome"])) ** 2
        f = (r["final_prob"] - float(r["outcome"])) ** 2
        early_brier += e
        final_brier += f
        if f < e:
            final_better += 1
        elif e < f:
            early_better += 1

    out = {
        "n": pairs,
        "sport": sport,
        "gate": MIN_PAIRS_FOR_TIMING_VERDICT,
        "proven": pairs >= MIN_PAIRS_FOR_TIMING_VERDICT,
        "changed_side": changed,
        "final_better": final_better,
        "early_better": early_better,
        "mean_move": round(sum(moved) / pairs, 4) if pairs else None,
        "early_brier": round(early_brier / pairs, 4) if pairs else None,
        "final_brier": round(final_brier / pairs, 4) if pairs else None,
    }
    out["says"] = language.early_vs_final_line(out)
    return out


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


def standing_row_clause(same_set: bool) -> str:
    """The SQL that keeps ONE standing row per question: the latest written
    before start. Appended to a query over `predictions p JOIN games g`.

    ONE DOOR (audit 2026-09-05). `resolved()` had this rule inline and every
    scorecard went through it, but the version table's N and the pace line
    counted rows straight off the table -- so the MLB record showed 233
    settled under fs2 while its categories summed to 197, the other 36 being
    early rows a final pass had superseded. Two counts of one record cannot
    disagree if they share the clause.

    ONE STANDING ROW PER DISTINCT BET (operator question 17, 2026-09-28).
    "The question" is `bet.same` -- the one function's SQL form: the
    forecaster, the game, the market and prop type, the subject and the rung
    asked, NULL one value. It was written out here twice until this date,
    without the prop type, which the subject carries (measured on a copy of
    the record that day: naming it moves no count). `gridiron.recount`
    works this rule out again in Python, and each builder that counts
    through it refuses a count the two disagree on.
    """
    same = (" AND p2.factor_set_version = p.factor_set_version"
            if same_set else "")
    # A VOIDED ROW IS NEVER THE STANDING ONE (operator ruling 1, 2026-09-24).
    #
    # Until this date a void stayed out of the arithmetic only because a
    # trigger refuses to resolve a voided row, so it never reached a count
    # that asks for an outcome. That holds for a void written BEFORE the game
    # settles, and it is the only case the resolver produces. The ruling's
    # voids are written by hand, and a game can settle first -- after which
    # the row carries an outcome and nothing here would have left it out.
    #
    # TWO PLACES, for two reasons. The row itself is excluded, so a voided
    # forecast is never graded. And it is skipped when choosing the standing
    # row, so a voided later row does not displace an earlier forecast of the
    # same question that still stands -- a withdrawal takes one row back, not
    # the question. The fallback below (every row written after the start)
    # still sees voided rows: a question whose pre-start forecasts were all
    # withdrawn had a forecast before the start, and a row written afterwards
    # must not become its standing one.
    voided = (" AND NOT EXISTS (SELECT 1 FROM prediction_voids vs"
              "                 WHERE vs.prediction_id = p.id)")
    skip_voided = ("                AND NOT EXISTS (SELECT 1 FROM prediction_voids v2"
                   "                                WHERE v2.prediction_id = p2.id)")
    # THE LATEST ROW **BEFORE START**, not simply the latest (2026-09-03).
    #
    # The final pass (config.FINAL_PASS) writes a second forecast close to
    # kickoff, so "which row is the standing one" stopped being a duplicate
    # question and became the ordinary case. A row written AFTER the game
    # began is not a forecast -- the MISSED rule already refuses to write one,
    # and this is the second lock: even if one existed, it could not become
    # the row the record is graded on. A backtest is the case that proves it
    # matters, because every backtest row is written after its game.
    #
    # `g2.kickoff_utc IS NULL` keeps a game with no scheduled time eligible
    # rather than silently dropping every question about it.
    return (
        f"{voided}"
        " AND p.id = (SELECT p2.id FROM predictions p2"
        "              JOIN games g2 ON g2.id = p2.game_id"
        f"              WHERE {bet.same('p2', 'p')}"
        f"{same}"
        f"{skip_voided}"
        "                AND (g2.kickoff_utc IS NULL"
        "                     OR p2.created_utc <= g2.kickoff_utc"
        # A SLATE OF ROWS ALL WRITTEN AFTER START is a backtest, and a
        # backtest still has to produce a curve. When nothing was written
        # before kickoff the latest row stands, because refusing them all
        # would report an empty record rather than a retrospective one.
        "                     OR NOT EXISTS (SELECT 1 FROM predictions p3"
        "                                    JOIN games g3 ON g3.id = p3.game_id"
        f"                                    WHERE {bet.same('p3', 'p2')}"
        "                                      AND p3.created_utc <= g3.kickoff_utc))"
        "              ORDER BY p2.created_utc DESC, p2.id DESC LIMIT 1)"
    )


def resolved(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
    event_tier: str | None = None,
    with_factors: bool = False,
) -> list[Resolved]:
    require_sport(sport, "calibration.resolved")
    where = ["p.resolved_utc IS NOT NULL", "p.sport = ?"]
    params: list = [sport]
    if event_tier:
        # LAW 6 ONE LEVEL DOWN (R2, 2026-09-03). A Contender Series bout goes
        # the distance 43.6% of the time and a numbered-card bout 58.0%; one
        # UFC curve would average those and describe neither, which is exactly
        # the failure the law forbids across sports. The tier lives on the
        # EVENT, so this reaches through the bout to the card it was on.
        where.append(
            "EXISTS (SELECT 1 FROM ufc_bouts b JOIN ufc_events e"
            "          ON e.id = b.event_id"
            "         WHERE b.id = p.game_id AND e.event_tier = ?)")
        params.append(event_tier)
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

    # SUPERSEDED FORECASTS ARE NOT IN THE RECORD'S ARITHMETIC (ruling R4,
    # 2026-09-02), and they are never deleted.
    #
    # `predict:nfl` ran twice on 2026-08-29 -- 05:55Z and again at 07:34Z --
    # and wrote a full second set of week 1 forecasts. Both rows are the
    # record: LAW 3 is append-only and a prediction is never removed. But a
    # curve that counts 26 questions twice is describing a slate that was
    # never asked, and it counts them with correlated errors, which is worse
    # than counting them once.
    #
    # THE STANDING FORECAST IS THE LATEST ONE WRITTEN, per question per
    # forecaster -- the same rule `views.week` already applies to Picks and
    # the same rule a revised call once followed. The earlier rows stay
    # readable in Results and in `prediction_detail`; they are simply not
    # arithmetic.
    #
    # WHAT MAKES TWO ROWS THE SAME QUESTION: the game, the market, the
    # subject, the rung and the forecaster. `line_asked` is part of it -- the
    # same subject asked at two different rungs is two questions, not a
    # revision of one.
    #
    # `prop_type` IS DELIBERATELY NOT PART OF IT, and the reason is a data
    # artefact worth naming. The subject already carries the stat ("Trey
    # McBride receiving_yards"), and ten NFL rows from the earlier of the two
    # 2026-08-29 runs left `prop_type` NULL where the later run set it. Keying
    # on it split ten questions that are plainly the same one and counted each
    # twice -- 88 standing instead of 78, disagreeing with the Picks page
    # about the very same slate. One definition of "the same question", and
    # this is it.
    #
    # THE SUBQUERY MIRRORS THE FILTER, and it has to. `factor_set_version` is
    # a legitimate reason for two forecasts on one question -- a different
    # model asking it is a different forecast, and the record keeps both with
    # their versions attached. That is exactly what happened on 2026-08-29:
    # fs1 at 05:55 and fs2 at 07:34.
    #
    # So an UNFILTERED curve takes the latest across sets, because a curve
    # spanning two factor sets describes two models. A curve asked for ONE set
    # takes the latest within it -- without this, asking for fs1 would match
    # the fs2 row's id, fail the outer filter, and return nothing at all.
    standing = standing_row_clause(bool(factor_set_version))
    rows = conn.execute(
        "SELECT p.id, p.created_utc, p.game_id, g.season, g.week, p.market_type,"
        " p.prop_type, p.predictor, p.factor_set_version, p.subject, p.line_asked,"
        " p.model_prob, p.model_side, p.outcome, p.factors_json,"
        " (SELECT s.implied_prob FROM market_snapshots s WHERE s.prediction_id = p.id"
        "  ORDER BY s.id LIMIT 1) AS implied_prob"
        f" FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE {' AND '.join(where)}{standing} ORDER BY p.id",
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
    event_tier: str | None = None,
) -> dict:
    require_sport(sport, "calibration.curve")
    items = resolved(
        conn,
        sport=sport,
        market_type=market_type,
        prop_type=prop_type,
        predictor=predictor,
        factor_set_version=factor_set_version,
        event_tier=event_tier,
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
            "event_tier": event_tier or "all",
        },
        "event_tier": event_tier,
        "tier_label": language.tier_label(event_tier),
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
    #
    # EACH MARKET'S ACTIVE FIT, one entry per market that fit carries the
    # factor in (operator ruling 4, 2026-09-24: "the fit reports each factor's
    # rows used"). Until that day this read the NEWEST fit of the default
    # factor set under a market key that was wrong for every total, so the
    # page could describe a fit no market was forecasting from. The version
    # filter above scopes the RESOLVED predictions; the fits are the ones in
    # force, whatever it is.
    fit_status = _fit_status(conn, sport)
    for entry in factors:
        status = fit_status.get(entry["factor"])
        if not status:
            continue
        entry["fit_rows"] = status
        entry["fit_rows_words"] = language.fit_rows_words(sport, status)
        entry["excluded_from_fit"] = all(s["excluded"] for s in status)
        if entry["excluded_from_fit"] and not entry["n"]:
            entry["verdict"] = status[0]["reason"]

    factors.sort(key=lambda e: (-(e["delta_brier"] or -9), e["factor"]))
    return {
        "n": len(items),
        "sport": sport,
        "method": FACTOR_METHOD_NOTE,
        "factor_set_version": factor_set_version or config.FACTOR_SET_VERSION,
        "factors": factors,
    }


def _fit_status(conn: sqlite3.Connection, sport: str) -> dict[str, list[dict]]:
    """Per factor, the rows that carried it in each market's ACTIVE fit.

    ONE ENTRY PER MARKET, from the fit that market forecasts from
    (`activation.active_fit`), keyed by the market's own key
    (`baseline.market_key`) -- REPAIRED 2026-09-24 (operator ruling 4). It
    read the newest fit of one factor set for every market, looked a total
    up as 'prop:total', and kept the first market's count for a factor
    several markets share, so the wind on the page was one market's wind.

    `rows` is what the fit stored: the training rows that carried a value.
    `indoor_filled` marks a weather count taken before an indoor game carried
    no value (`registry.FILLED_INDOORS_UNTIL_2026_09_24`): those rows include
    domes given 0.0, which added nothing to the fit and are not readings.
    """
    from .model import activation, baseline

    out: dict[str, list[dict]] = {}
    for market in config.active_markets(sport):
        _, market_type = baseline.split_key(baseline.market_key(sport, market))
        active = activation.active_fit(conn, sport, market_type)
        if active is None:
            continue
        blob = json.loads(active["coefficients_json"])
        total = blob.get("n") or 0
        base = {"market": market, "fit_id": active["fit_id"],
                "factor_set_version": active["factor_set_version"], "n": total}
        presence = blob.get("presence") or {}
        filled = blob.get("indoor_weather") != factor_compute.INDOOR_WEATHER

        def add(name: str, rows, excluded: bool, reason: str | None = None):
            # Only a count that HAS rows can have domes among them: "0 of 64,
            # indoor games among them" rendered once and said nothing true.
            out.setdefault(name, []).append({
                **base, "rows": rows, "excluded": excluded, "reason": reason,
                "indoor_filled": bool(
                    filled and rows
                    and name in registry.FILLED_INDOORS_UNTIL_2026_09_24),
            })

        for name in (blob.get("coefficients") or {}):
            add(name, presence.get(name), False)
        for name, count in (blob.get("constant") or {}).items():
            add(name, count, True, (
                f"never varied where it could be measured - one value across all "
                f"{count:,} of {total:,} training rows that carried it, so there "
                "is nothing to fit and nothing to score"))
        for name, count in (blob.get("dropped") or {}).items():
            add(name, count, True, (
                f"measurable in only {count:,} of {total:,} training rows, below "
                "the floor for estimating a coefficient at all"))
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
    # THE LABEL TELLS ITS OWN RECORD (S3, 2026-09-03), and says the tier's
    # NAME while doing it. "tier unproven - 19 settled of 20 needed" made a
    # reader carry the band in their head from the chip beside it; "STRONG --
    # 19 settled, not yet proven" is the same fact and needs nothing carried.
    entry["message"] = language.tier_record_line(
        tier, n, TIER_MIN_SETTLED, entry["earned"])
    # WHAT THE CHIP ITSELF READS (2026-09-04). Composed here rather than in the
    # browser, so a renderer cannot invent it -- and composed at all because
    # `message` above reached a grid card only as a hover tooltip, which is no
    # caveat on a phone. Measured across four live slates: 17 of 379 chips had
    # a settled record behind them.
    entry["chip_label"] = language.tier_chip_label(tier, proven)
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
        # LAW 6 ONE LEVEL DOWN (R2, 2026-09-03). A sport that splits below the
        # market may not report a category that spans its tiers: a UFC distance
        # curve mixing 43.6% Contender Series bouts with 58.0% numbered-card
        # ones describes neither, and flatters, for the same reason the law
        # forbids mixing sports.
        declared_tiers = config.event_tiers(sport)
        if declared_tiers:
            tier = category.get("event_tier")
            if tier in (None, "all"):
                raise MergedCurve(
                    f"LAW 6: category {category.get('category')!r} names no "
                    f"event tier, so it averages {sport}'s "
                    f"{len(declared_tiers)} tiers into one curve. Tiers are "
                    f"reported side by side, never summed."
                )
            if tier not in declared_tiers:
                raise MergedCurve(
                    f"LAW 6: category {category.get('category')!r} reports "
                    f"event tier {tier!r}, which is not one of {sport}'s "
                    f"declared tiers {list(declared_tiers)}."
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
        # STANDING ROWS ONLY, the same clause every category beneath uses.
        # Counted off the raw table this said 280 written / 233 settled for
        # MLB's fs2 while the categories summed to 197 (audit 2026-09-05).
        counts = conn.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN p.resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved"
            " FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND p.factor_set_version = ?"
            + standing_row_clause(True),
            (sport, version),
        ).fetchone()
        total = counts["total"] or 0
        n_resolved = counts["resolved"] or 0
        is_current = version == config.FACTOR_SET_VERSION

        categories = []
        # A SPORT THAT SPLITS BELOW THE MARKET GETS ONE CATEGORY PER TIER
        # (R2, 2026-09-03). `(None,)` for every other sport, so the loop below
        # is unchanged for four of the five and no category gains an empty
        # tier key it would have to be filtered out by later.
        tiers = config.event_tiers(sport) or (None,)
        for market in config.SPORT_MARKETS.get(sport, ()):
            for tier in tiers:
                for predictor in ("statistical", "llm"):
                    items = resolved(
                        conn,
                        sport=sport,
                        market_type=market_type_of(sport, market),
                        prop_type=prop_type_of(sport, market),
                        predictor=predictor,
                        factor_set_version=version,
                        event_tier=tier,
                    )
                    if not items and not is_current:
                        continue
                    entry_c = {
                        "category": (f"{market} / {tier} / {predictor}"
                                     if tier else f"{market} / {predictor}"),
                        "category_label": language.category_label(
                            market, tier, predictor,
                            config.retired_market(sport, market)),
                        "retired": config.retired_market(sport, market),
                        "market": market,
                        "predictor": predictor,
                        **score(items),
                    }
                    if tier:
                        entry_c["event_tier"] = tier
                        entry_c["tier_label"] = language.tier_label(tier)
                    categories.append(entry_c)

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


def blind_categories(conn: sqlite3.Connection, *, sport: str) -> list[dict]:
    """Every blind curve for ONE sport -- one per market, card and forecaster
    -- each with the outlook beside it, checked before anything is served.

    THE PAYLOAD BUILDER OF THE RECORD PAGE'S "RECORD BY CATEGORY" TABLE, taken
    out of `scorecard` on 2026-09-27 (operator question 14, 3 of 3) so the
    gate can build every sport's without the rest of the page, and the guard
    runs here, inside it: the API answers 500 rather than serve an outlook
    counting another record than the curve it sits under.
    """
    require_sport(sport, "calibration.blind_categories")
    markets = config.SPORT_MARKETS.get(sport, ())
    categories = []
    # ONE CATEGORY PER TIER for a sport that splits below the market (R2),
    # and `(None,)` for the four that do not, so nothing changes for them.
    tiers = config.event_tiers(sport) or (None,)
    for market in markets:
        for tier in tiers:
            for predictor in ("statistical", "llm"):
                c = curve(conn, sport=sport,
                          market_type=market_type_of(sport, market),
                          prop_type=prop_type_of(sport, market),
                          predictor=predictor, event_tier=tier)
                c["category"] = (f"{market} / {tier} / {predictor}"
                                 if tier else f"{market} / {predictor}")
                c["category_label"] = language.category_label(
                    market, tier, predictor, config.retired_market(sport, market))
                c["retired"] = config.retired_market(sport, market)
                c["market"] = market
                # WHICH RECORD THIS ROW BELONGS TO (E4). Checked, not assumed:
                # an at-the-line curve filed here would be averaging a forecast
                # against a price with a forecast against its own rung.
                c["record"] = "rung"
                # RULING R3: a gate that will not be reached is not a gate that
                # has not been reached YET, and rendering them alike reads as
                # progress.
                #
                # THE CURVE'S OWN FORECASTER AND CARD (operator question 14,
                # 2026-09-27). The outlook is the statistical model's, beside
                # its own curve on each card, counted through the door the
                # curve's rows come from (`horizon.standing_questions`). Until
                # this date one outlook per market, of every row on every card,
                # sat beside each card's curve -- on the reasoning that the two
                # forecasters answer the same questions, which the counts do
                # not bear out (MLB moneyline 246 and 134 standing on 27
                # September). The reasoning pass's curve in a market it is
                # still asked carries its N and no projection, as it always
                # has: the ruling rebuilds the counts the page states and adds
                # none (FOLLOWUPS).
                if predictor == "statistical":
                    c["outlook"] = horizon.market_outlook(
                        conn, sport, market, predictor=predictor, event_tier=tier)
                elif not config.llm_routed(sport, market):
                    # THE CURVE STOPS GROWING WITHOUT IMPLYING AN ERROR (ruling
                    # E1, 2026-09-06): the reasoning pass no longer asks this
                    # market, and the line says the count is final.
                    c["outlook"] = horizon.llm_routed_off_outlook(
                        conn, sport, market, event_tier=tier)
                categories.append(c)
    assert_no_pooled_outlooks({"sport": sport, "record": "rung",
                               "categories": categories})
    return categories


def assert_no_pooled_outlooks(payload: dict) -> None:
    """Every outlook beside a blind curve counts THAT CURVE'S standing
    questions: one forecaster's, one card's for UFC, each question once.

    The operator's ruling on question 14 (2026-09-27, 3 of 3): "Every count
    on the Record page that states a gate distance is rebuilt per forecaster
    (per tier for UFC) and per distinct bet, through its record's standing
    rule." Checked on the payload, as `assert_no_pooled_claims` checks the
    at-the-line record's -- and it runs `assert_no_merged_categories` first,
    so the sport, the market, the forecaster and the tier are one rule for
    every record.

    Then, for each category's outlook, by name: one filed from another
    record; one naming another forecaster than the curve's, or none, or
    counting another's rows (`forecasters_counted`); one naming another card
    than the curve's, or counting another card's bouts (`tiers_counted`, read
    off each row's own bout); a settled count or a pace counting more rows
    than distinct questions (a question's morning and final pass); a
    settled count or a pace other than the one `gridiron.recount` makes
    without the door, one per distinct bet by the one key (operator
    question 17, 2026-09-28: a door or a standing rule keyed without the
    rung, or across forecasters); a settled
    count that is not the curve's n -- two counts of one record (MLB
    moneyline said "330 of 100" beside a curve of 233 on 26 September); an
    expectation that is not its own counts' arithmetic; and a line stating
    another count than its own. Raised inside `blind_categories`, so the API
    answers 500 rather than serving the pool.
    """
    law = "LAW 4 / LAW 6 IN THE BLIND RECORD'S OUTLOOK"
    assert_no_merged_categories(payload)
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    for category in payload.get("categories") or []:
        outlook = category.get("outlook")
        if outlook is None:
            continue
        what = f"the outlook beside {category.get('category')!r}"
        if outlook.get("record") != "rung":
            raise MergedCurve(
                f"{law}: {what} belongs to the {outlook.get('record')!r} "
                f"record and is filed beside a blind curve.")
        named = (category.get("filters") or {}).get("predictor")
        if (outlook.get("predictor") != named
                or named not in horizon.FORECASTERS):
            raise MergedCurve(
                f"{law}: {what} names forecaster {outlook.get('predictor')!r} "
                f"beside the {named!r} forecaster's curve. The statistical "
                f"model's questions and the reasoning pass's are counted apart "
                f"and never pooled.")
        counted = outlook.get("forecasters_counted")
        if counted not in ([], [named]):
            raise MergedCurve(
                f"{law}: {what} is the {named!r} forecaster's and counts the "
                f"forecasts of {counted!r}: two forecasters pooled into one "
                f"count.")
        tier, cards = category.get("event_tier"), outlook.get("tiers_counted")
        if outlook.get("event_tier") != tier:
            raise MergedCurve(
                f"{law}: {what} names event tier {outlook.get('event_tier')!r} "
                f"beside the {tier!r} curve; {sport}'s cards are reported side "
                f"by side, never summed.")
        if tiers:
            if tier not in tiers or cards not in ([], [tier]):
                raise MergedCurve(
                    f"{law}: {what} names event tier {tier!r} and counts bouts "
                    f"on {cards!r}; {sport}'s tiers {list(tiers)} are reported "
                    f"side by side, never summed.")
        elif tier is not None or cards not in ([], None):
            raise MergedCurve(
                f"{law}: {what} names event tier {tier!r} in {sport}, which "
                f"declares none.")
        n, bets = outlook.get("resolved"), outlook.get("distinct_bets")
        if bets is None or n != bets or outlook.get("n") != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled forecasts for {bets} "
                f"distinct question{'' if bets == 1 else 's'}. A question is "
                f"counted once, on its standing forecast, however many passes "
                f"answered it.")
        written, asked = outlook.get("written"), outlook.get("distinct_bets_written")
        if asked is None or written != asked:
            raise MergedCurve(
                f"{law}: {what} paces {written} forecasts written this season "
                f"for {asked} distinct question{'' if asked == 1 else 's'}: a "
                f"rate from every pass projects questions nobody asked.")
        if n != category.get("n"):
            raise MergedCurve(
                f"{law}: {what} counts {n} settled beside a curve of "
                f"{category.get('n')!r}: two counts of one record.")
        if outlook.get("expected") != horizon.expected_from(outlook):
            raise MergedCurve(
                f"{law}: {what} expects {outlook.get('expected')!r} where its "
                f"own counts project {horizon.expected_from(outlook)!r}.")
        said = horizon.outlook_words(outlook)
        if outlook.get("message") != said:
            raise MergedCurve(
                f"{law}: {what} says {outlook.get('message')!r}, which is not "
                f"its own count of {n}: {said!r}.")
        # AND THE RECOUNT MADE WITHOUT THE DOOR (operator question 17,
        # 2026-09-28). The curve and the outlook both read the standing
        # clause, so a clause keyed without the rung, or across forecasters,
        # moves both alike and they still agree; only a count made without
        # it sees that they count other bets than the record holds.
        again, again_written = (outlook.get("recounted"),
                                outlook.get("recounted_written"))
        if again != n or again_written != written:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled and {written} written this "
                f"season where the recount made without its door finds "
                f"{again!r} and {again_written!r}, one per distinct bet by "
                f"the one key (`bet.of`: the forecaster, the game, the market, "
                f"the subject and the rung asked). A door or a standing rule "
                f"keyed any other way -- without the rung, or across "
                f"forecasters -- counts other bets than the record holds "
                f"(operator question 17, 2026-09-28).")


def scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Every curve for ONE sport, kept separate. Never a merged headline."""
    require_sport(sport, "calibration.scorecard")
    markets = config.SPORT_MARKETS.get(sport, ())
    categories = blind_categories(conn, sport=sport)

    headline_market = markets[0] if markets else "spread"
    headline = curve(conn, sport=sport,
                     market_type=market_type_of(sport, headline_market),
                     prop_type=prop_type_of(sport, headline_market),
                     predictor="statistical")
    headline["market"] = headline_market

    payload = {
        "sport": sport,
        "record": "rung",
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
    # THE OTHER RECORD, BESIDE THIS ONE AND NEVER INSIDE IT (E4, 2026-09-06).
    # Its own curves, its own gate, its own guard; the Record page draws it as
    # a separate section for the same reason.
    payload["at_the_line"] = at_the_line_scorecard(conn, sport=sport)
    # AND THE ORDERING'S OWN RECORD (S3, 2026-09-07): did the questions that
    # led each slate score better than the ones they outranked? Beside the
    # curves, never inside them -- this is a fact about the ranker, not about
    # the model.
    payload["ranker"] = ranker_scorecard(conn, sport=sport)
    # THE CLOSING LINE (R3, 2026-09-07): the first verdict available on whether
    # the app is buying cheap. Its own section, its own minimum, and capable of
    # returning bad news in words written before it was needed.
    #
    # ONE INSTANT FOR BOTH READS OF IT (2026-09-27): the closing line and the
    # kill criterion below ask the same window, and two readings of the clock
    # either side of midnight UTC on 15 October could have given the page a
    # verdict in one panel and none in the other.
    from .db import utcnow

    read_at = utcnow()
    payload["closing_line"] = clv_report(conn, sport=sport, now=read_at)
    # AND WHETHER PACKAGES ARE WORTH TAKING AT ALL (GRIDIRON_COMBOS C4,
    # 2026-09-08). The kill criterion was declared before the first package
    # existed and is printed from the first day, so its wording cannot be
    # chosen later to suit the numbers.
    # The packages he marked, on their own line and never inside a leg's.
    payload["taken_packages"] = taken_packages(conn, sport=sport)
    # WHAT THE ENGINE IS ALLOWED TO PRICE AT ALL (P2, 2026-09-07), with the
    # measurement behind every entry and the reason for every exclusion.
    from .priced import coverage as _coverage

    covered = _coverage.coverage(conn, sport)
    covered["words"] = language.priced_coverage_line(
        config.SPORT_LABELS.get(sport, sport.upper()), covered["covered"],
        len(covered["entries"]))
    covered["stopped"] = list(_coverage.stopped(conn, sport, now=read_at).values())
    payload["coverage"] = covered
    payload["priced"] = priced_scorecard(conn, sport=sport)

    assert_every_figure_has_n(payload)
    assert_no_merged_categories(payload)
    assert_the_records_stay_apart(payload)
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
            # HOW CLOSE THIS ROW IS (GRIDIRON_13 P1). The verdict gate at 20,
            # and once that is behind it the edge gate at 100. Counts only --
            # `audit.progress_faults` refuses a share of the way to a verdict,
            # because a percentage on this page reads as a probability.
            "progress": language.gate_progress(
                n, TIER_MIN_SETTLED, config.MIN_SAMPLE_FOR_EDGE_CLAIM),
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
        # WHICH NUMBERS THIS TABLE IS GRADING. A tier table over corrected
        # claims and one over raw claims are different tables, and a reader
        # comparing today's against last month's has to be told which they are
        # looking at.
        "corrections_note": _corrections_note(
            conn, sport=sport, market_type=market_type, predictor=predictor),
        # WHICH GATE IS NEAREST, named once at the top rather than left for a
        # reader to work out by comparing four rows.
        "closest": _closest_verdict(conn, rows, sport=sport),
    }


def recent_settled(conn: sqlite3.Connection, *, sport: str, since: str) -> tuple[int, int]:
    """(standing rows settled since `since`, distinct days that settled any).

    Standing rows, through the one clause: a superseded early row settles on
    the same day as its final and would count the question twice.
    """
    require_sport(sport, "calibration.recent_settled")
    row = conn.execute(
        "SELECT COUNT(*) AS n, COUNT(DISTINCT substr(p.resolved_utc, 1, 10)) AS days"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL"
        "   AND p.resolved_utc >= ?" + standing_row_clause(False),
        (sport, since)).fetchone()
    return int(row["n"] or 0), int(row["days"] or 0)


def _closest_verdict(conn: sqlite3.Connection, rows: list, *, sport: str) -> dict:
    """The tier nearest a verdict, and roughly how many slates that is.

    PACE IS AN ESTIMATE AND SAYS SO. It divides what settled in the last
    fourteen days by the number of days that actually carried a settlement,
    which is the closest thing to "a slate" this record holds. Below a week of
    history it refuses to estimate at all rather than dividing by two days and
    calling the answer a forecast.
    """
    from . import language

    waiting = [r for r in rows if not r["proven"]]
    if not waiting:
        return {"n": sum(r["n"] for r in rows), "tier": None,
                "line": language.closest_verdict_line(None, 0, ""),
                "pace_known": False}
    nearest = min(waiting, key=lambda r: r["needed"] - r["n"])
    remaining = nearest["needed"] - nearest["n"]

    cutoff = _days_ago_iso(language.PACE_WINDOW_DAYS)
    n_recent, days = recent_settled(conn, sport=sport, since=cutoff)
    per_slate = (n_recent / days) if days else None
    return {
        "n": nearest["n"],
        "tier": nearest["tier"],
        "remaining": remaining,
        "settled_recently": n_recent,
        "days_of_history": days,
        "pace_known": days >= language.PACE_MIN_DAYS and bool(per_slate),
        "line": language.closest_verdict_line(
            nearest["tier"], remaining,
            language.pace_clause(remaining, per_slate, days)),
        "note": (
            f"pace from the last {language.PACE_WINDOW_DAYS} days - an "
            f"estimate, not a promise - {sport.upper()} only, because sports "
            f"are never added together"),
    }


def _days_ago_iso(days: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _corrections_note(conn: sqlite3.Connection, *, sport: str,
                      market_type: str, predictor: str) -> str:
    from . import correction, language

    active = correction.active_correction(
        conn, sport=sport, market_type=market_type, forecaster=predictor)
    return language.corrections_note(
        active is not None, correction.MIN_TRAIN,
        version=active["version"] if active else None,
        fitted=active["fitted_utc"] if active else None,
        settled=active["n_train"] if active else None,
    )


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


# ---------------------------------------------------------------------------
# THE AT-THE-LINE RECORD (E4, 2026-09-06)
# ---------------------------------------------------------------------------
#
# A SECOND RECORD, NOT A SECOND OPINION. Every row here is the frozen
# distribution read at a number the venue published after the prediction was
# written. It resolves like a prediction and calibrates like one, and it is
# kept apart from the blind rung record at every level:
#
#   * its own curves, one per market, never mixed with a rung curve;
#   * its own gate, the same 100 as every other edge figure, counted from its
#     own settled comparisons -- which are always fewer, because a claim needs
#     a ladder and a price as well as a forecast;
#   * its own guard. `assert_the_records_stay_apart` refuses a payload whose
#     categories do not all belong to the record they are filed under, and
#     `plant.py` puts an at-the-line curve in the blind record to prove it
#     fires. Merging the two would describe neither: one is what the model
#     said about its own question, the other what it says about the venue's.


class MergedRecord(RuntimeError):
    """The blind record and the at-the-line record were filed as one."""


AT_THE_LINE_NOTE = (
    "The model's own distribution, read at the venue's published line after the "
    "forecast was written and frozen. Two probabilities for the same question, "
    "and nothing else: this is a forecast beside a price, not a recommendation."
)


@dataclass(frozen=True)
class AtTheLineResolved:
    """One settled claim, in the shape the bucket and score functions read.

    It carries its BET -- its forecast's key, `bet.KEY`: the forecaster, the
    game, the market and prop type, the subject and the rung asked (operator
    question 17, 2026-09-28; item 6 carried the game, market and side) -- so
    a payload can say how many distinct bets its count is (`bet.count`), and
    a guard can refuse one that counts a bet twice or two forecasters as one.
    The venue's own number is `line`; the rung the forecaster was asked is
    `line_asked`.
    """
    model_prob: float
    implied_prob: float
    outcome: int
    market: str
    line: float | None
    game_id: str
    side: str
    predictor: str
    market_type: str
    prop_type: str | None
    subject: str
    line_asked: float | None


def _at_the_line_items_of(claims) -> list[AtTheLineResolved]:
    """The settled claims among the door's rows, as items."""
    from .market import at_the_line

    return [
        AtTheLineResolved(model_prob=c["model_prob"], implied_prob=c["venue_implied"],
                          outcome=c["outcome"], market=c["market"], line=c["line"],
                          game_id=c["game_id"], side=c["side"],
                          predictor=c["predictor"], market_type=c["market_type"],
                          prop_type=c["prop_type"], subject=c["subject"],
                          line_asked=c["line_asked"])
        for c in at_the_line.settled(claims)
    ]


def forecasters_counted(items) -> list[str]:
    """Whose claims a set of items holds, read off the items themselves."""
    return sorted({i.predictor for i in items})


def at_the_line_items(conn: sqlite3.Connection, *, sport: str, market: str,
                      predictor: str,
                      event_tier: str | None = None) -> list[AtTheLineResolved]:
    """The settled standing claims for one sport, market and forecaster --
    and, for a sport that splits below the market, one tier.

    ONE PER DISTINCT BET (the market module's door,
    `at_the_line.standing_claims`, keyed by `bet`): a question's morning and
    final pass and its every look are one claim, two rungs of one game are
    two, and the two forecasters are never counted together (item 6;
    operator question 17, 2026-09-28).
    """
    from .market import at_the_line

    require_sport(sport, "calibration.at_the_line_items")
    return _at_the_line_items_of(at_the_line.standing_claims(
        conn, sport=sport, market=market, predictor=predictor,
        event_tier=event_tier))


def at_the_line_curve(conn: sqlite3.Connection, *, sport: str, market: str,
                      predictor: str, event_tier: str | None = None) -> dict:
    """One forecaster's at-the-line curve in one market, with the venue's own
    prices as the baseline it has to beat.

    ONE LIST, THREE COUNTS (GRIDIRON_REPAIR item 6, 2026-09-26). The door is
    asked once; the curve's n, the gate line and the outlook beside it are all
    read off that list. Until this date the outlook asked a query of its own,
    and MLB spread said "80 of 100" beside "128 of 100" -- two counts of one
    record, the ONE CLAUSE failure again (FOLLOWUPS, 2026-09-23).

    AND RECOUNTED WITHOUT THE DOOR (operator question 17, 2026-09-28): the
    same read asks `gridiron.recount` for the cell's settled bets by the one
    key, and the payload carries it as `recounted` for
    `assert_no_pooled_claims` to hold the curve's n to.
    """
    from . import db, recount
    from .market import at_the_line

    require_sport(sport, "calibration.at_the_line_curve")
    with db.one_instant(conn):
        bets = at_the_line.standing_claims(conn, sport=sport, market=market,
                                           predictor=predictor,
                                           event_tier=event_tier)
        again = recount.at_the_line(conn, sport=sport, market=market,
                                    predictor=predictor, event_tier=event_tier)
        outlook = horizon.at_the_line_outlook(
            conn, sport, market, predictor=predictor, bets=bets,
            event_tier=event_tier)
    items = _at_the_line_items_of(bets)
    buckets = calibration_buckets(items)
    filters = {"sport": sport, "market": market, "predictor": predictor,
               "record": "at_the_line"}
    if event_tier is not None:
        filters["event_tier"] = event_tier
    return {
        "sport": sport,
        "record": "at_the_line",
        "venue": at_the_line_venue(),
        "market": market,
        "predictor": predictor,
        "event_tier": event_tier,
        "category": " / ".join(
            [market] + ([event_tier] if event_tier else [])
            + [predictor, "at the venue's line"]),
        "category_label": language.at_the_line_category_label(
            market, predictor, event_tier),
        "filters": filters,
        "n": len(items),
        "distinct_bets": bet.count(items),
        "recounted": again["settled"],
        "forecasters_counted": forecasters_counted(items),
        "buckets": buckets,
        "largest_gap": largest_gap_sentence(buckets),
        "score": score(items),
        "baselines": baselines(items),
        "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
        "gate_line": language.at_the_line_gate_line(
            len(items), config.MIN_SAMPLE_FOR_EDGE_CLAIM),
        "outlook": outlook,
        "note": AT_THE_LINE_NOTE,
    }


def at_the_line_venue() -> str:
    """The venue these claims are read against, named on every figure."""
    from .market import at_the_line

    return at_the_line.VENUE


def at_the_line_edge(conn: sqlite3.Connection, *, sport: str, market: str,
                     predictor: str, event_tier: str | None = None,
                     threshold: float | None = None) -> dict:
    """Where the model and the venue's price disagree, who was right?

    Both directions, always. Showing only the half where the model led is how
    a record lies while staying technically accurate, and this figure is the
    most decision-relevant one the project can produce, so it carries the same
    gate and the same standing caveat as the blind edge figure.

    ONE FORECASTER'S (item 6, 2026-09-26), as the blind edge figure has
    always been: the scorecard asks for the statistical model's, and the
    payload says whose it is. Its settled claims are recounted without the
    door in the same read (`recounted`, operator question 17, 2026-09-28).
    """
    from . import db, recount

    threshold = config.EDGE_DISAGREEMENT_THRESHOLD if threshold is None else threshold
    with db.one_instant(conn):
        items = at_the_line_items(conn, sport=sport, market=market,
                                  predictor=predictor, event_tier=event_tier)
        again = recount.at_the_line(conn, sport=sport, market=market,
                                    predictor=predictor, event_tier=event_tier)
    model_bolder = [r for r in items if r.model_prob - r.implied_prob > threshold]
    venue_bolder = [r for r in items if r.implied_prob - r.model_prob > threshold]

    def side(subset, label):
        n = len(subset)
        entry = {"label": label, "n": n}
        if n:
            entry["resolved_in_model_favour"] = round(
                sum(r.outcome for r in subset) / n, 4)
            entry["mean_model_prob"] = round(sum(r.model_prob for r in subset) / n, 4)
            entry["mean_venue_prob"] = round(sum(r.implied_prob for r in subset) / n, 4)
        else:
            entry["resolved_in_model_favour"] = None
            entry["mean_model_prob"] = None
            entry["mean_venue_prob"] = None
        return entry

    minimum = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    payload = {
        "sport": sport,
        "record": "at_the_line",
        "venue": at_the_line_venue(),
        "market": market,
        "predictor": predictor,
        "event_tier": event_tier,
        "threshold": threshold,
        "n": len(items),
        "distinct_bets": bet.count(items),
        "recounted": again["settled"],
        "forecasters_counted": forecasters_counted(items),
        "n_disagreements": len(model_bolder),
        "minimum_for_a_claim": minimum,
        "standing_note": EDGE_STANDING_NOTE,
        "note": AT_THE_LINE_NOTE,
    }
    if len(model_bolder) < minimum:
        payload["renderable"] = False
        payload["shortfall"] = minimum - len(model_bolder)
        payload["message"] = language.at_the_line_gate_line(len(model_bolder), minimum)
        return payload
    payload["renderable"] = True
    payload["model_more_confident"] = side(model_bolder, "model more confident")
    payload["venue_more_confident"] = side(venue_bolder, "the venue's price more confident")
    return payload


def at_the_line_scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Every at-the-line curve for ONE sport, and the coverage behind them."""
    from .market import at_the_line

    require_sport(sport, "calibration.at_the_line_scorecard")
    markets = [m for m in at_the_line.BET_MARKETS
               if m in config.SPORT_MARKETS.get(sport, ())]
    # ONE CATEGORY PER MARKET, TIER AND FORECASTER (GRIDIRON_REPAIR item 6,
    # 2026-09-26): "The at-the-line scorecard never pools forecasters or
    # duplicates; per-forecaster, per-distinct-bet counts only, LAW 4 and
    # LAW 6." The tiers are `(None,)` for the four sports that do not split,
    # as in `scorecard`; the statistical model comes first in each market.
    tiers = config.event_tiers(sport) or (None,)
    cells = [(m, t, p) for m in markets for t in tiers
             for p in at_the_line.FORECASTERS]
    categories = [at_the_line_curve(conn, sport=sport, market=m, predictor=p,
                                    event_tier=t) for m, t, p in cells]
    # THE HYPOTHETICAL LEDGER, one per category (ruling D1, 2026-09-06; one
    # per forecaster from item 6). Beside the curves and never inside them: a
    # curve says whether 58% means 58%, and this says what the same rows
    # would have come to at the venue's prices, which is a fact about those
    # prices as much as about the forecast.
    from .market import paper

    ledgers = []
    for m, t, p in cells:
        entry = paper.ledger(conn, sport=sport, market=m, predictor=p,
                             event_tier=t)
        entry["words"] = language.paper_ledger_line(entry)
        entry["fee_words"] = language.paper_fee_line(entry)
        ledgers.append(entry)

    coverage = [row for t in tiers for p in at_the_line.FORECASTERS
                for row in at_the_line.coverage(conn, sport=sport, predictor=p,
                                                event_tier=t)]
    order = {m: i for i, m in enumerate(markets)}
    coverage.sort(key=lambda row: (order.get(row["market"], 99),
                                   tiers.index(row["event_tier"]),
                                   at_the_line.FORECASTERS.index(row["predictor"])))
    for row in coverage:
        row["words"] = language.at_the_line_coverage_line(
            row["market"], row["with_a_claim"], row["n"],
            predictor=row["predictor"], event_tier=row["event_tier"])
    headline_market = markets[0] if markets else None
    payload = {
        "sport": sport,
        "record": "at_the_line",
        "venue": at_the_line_venue(),
        "categories": categories,
        "markets": markets,
        "coverage": coverage,
        "paper": ledgers,
        # NO TOTAL. The `n` that stood here summed every category -- both
        # forecasters -- and described nobody's record (item 6, 2026-09-26).
        "note": AT_THE_LINE_NOTE,
        # THE STATISTICAL MODEL'S EDGE in the headline market, as the blind
        # record's edge figure is (`scorecard`); for a sport that splits, the
        # first declared tier's, which is the numbered card.
        "edge": (at_the_line_edge(conn, sport=sport, market=headline_market,
                                  predictor="statistical", event_tier=tiers[0])
                 if headline_market else None),
    }
    assert_the_records_stay_apart(payload)
    assert_no_pooled_claims(payload)
    assert_every_figure_has_n(payload)
    assert_single_sport(payload, sport)
    return payload


def assert_no_pooled_claims(payload: dict) -> None:
    """Every count at the venue's line is ONE forecaster's DISTINCT BETS.

    The operator's ruling of 2026-09-23 (GRIDIRON_REPAIR item 6): "The
    at-the-line scorecard never pools forecasters or duplicates;
    per-forecaster, per-distinct-bet counts only, LAW 4 and LAW 6." Checked on
    the payload, as `assert_no_merged_categories` checks the blind record's
    -- and it runs that check first, so the forecaster, the sport, the market
    and the tier are one rule for both records.

    Then, by name: a curve, a ledger or the edge that counts more claims than
    it has distinct bets (a question's morning and final pass, two looks, or
    two forecasters' claims on one question); one whose claims are another
    forecaster's than the one it names; a gate line or an outlook that
    states another count than the curve's own (the live record said "80 of
    100" beside "128 of 100" for one MLB category, 2026-09-23); a coverage
    line that names no forecaster, or counts one bet more than once (the
    prover, 2026-09-26); and a total across categories.

    AND A COUNT THE RECOUNT DOES NOT MAKE (operator question 17, ruled
    2026-09-27, built 2026-09-28). A distinct bet is `bet.of`, and a door
    keyed any other way -- without the rung, so two rungs of one game are
    one claim, or across forecasters, so one's later claim stands in for the
    other's question -- counts other bets than the record holds while its
    own `distinct_bets` agrees with it. Each curve, ledger, edge and coverage
    line carries `gridiron.recount`'s count, made without the door in the
    same read, and one that differs is refused by name.
    Raised inside `at_the_line_scorecard`, so the API answers 500 rather
    than serving a pool, the same as LAW 4 everywhere else.
    """
    from .market import at_the_line

    assert_no_merged_categories(payload)
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    law = "LAW 4 / LAW 6 AT THE VENUE'S LINE"

    def whose(entry: dict, what: str) -> None:
        named = entry.get("predictor")
        filtered = (entry.get("filters") or {}).get("predictor", named)
        if named not in at_the_line.FORECASTERS or filtered != named:
            raise MergedCurve(
                f"{law}: {what} names forecaster {named!r} (filtered by "
                f"{filtered!r}). The statistical model and the reasoning pass "
                f"are counted apart and never pooled.")
        counted = entry.get("forecasters_counted")
        if counted is not None and counted not in ([], [named]):
            raise MergedCurve(
                f"{law}: {what} is the {named!r} forecaster's and counts the "
                f"claims of {counted}: two forecasters pooled into one count.")
        if tiers and entry.get("event_tier") not in tiers:
            raise MergedCurve(
                f"{law}: {what} names event tier {entry.get('event_tier')!r}, "
                f"not one of {sport}'s {list(tiers)}; tiers are reported side "
                f"by side, never summed.")

    def once(entry: dict, what: str) -> None:
        n, bets = entry.get("n"), entry.get("distinct_bets")
        if bets is None or n != bets:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled claims for {bets} distinct "
                f"bet{'' if bets == 1 else 's'}. A distinct bet is counted once, "
                f"however many passes or looks repeated it.")

    def recounted(entry: dict, what: str) -> None:
        n, again = entry.get("n"), entry.get("recounted")
        if again != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} where the recount made without its "
                f"door finds {again!r}, one per distinct bet by the one "
                f"key (`bet.of`: the forecaster, the game, the market, the "
                f"subject and the rung asked). A door keyed any other way -- "
                f"without the rung, or across forecasters -- counts other bets "
                f"than the record holds (operator question 17, 2026-09-28).")

    if "n" in payload:
        raise MergedCurve(
            f"{law}: the at-the-line payload carries a total n of "
            f"{payload['n']}, a sum across its categories and so across both "
            f"forecasters, which is nobody's record.")
    for category in payload.get("categories") or []:
        what = f"category {category.get('category')!r}"
        whose(category, what)
        once(category, what)
        n = category.get("n")
        outlook = category.get("outlook") or {}
        if outlook.get("resolved") != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled beside an outlook of "
                f"{outlook.get('resolved')!r}: two counts of one record.")
        said = language.at_the_line_gate_line(n, category.get("gate"))
        if category.get("gate_line") != said:
            raise MergedCurve(
                f"{law}: {what}'s gate line says {category.get('gate_line')!r}, "
                f"which is not its own count of {n}.")
        recounted(category, what)
    for entry in payload.get("paper") or []:
        what = (f"the hypothetical ledger for {entry.get('market')!r}, "
                f"{entry.get('predictor')!r}")
        whose(entry, what)
        once(entry, what)
        recounted(entry, what)
    edge = payload.get("edge")
    if edge:
        whose(edge, "the at-the-line edge figure")
        once(edge, "the at-the-line edge figure")
        recounted(edge, "the at-the-line edge figure")
    for row in payload.get("coverage") or []:
        what = (f"the coverage line for {row.get('market')!r}, "
                f"{row.get('predictor')!r}")
        whose(row, what)
        # AND ONCE PER BET (the prover of item 6, 2026-09-26): the coverage
        # line counted a question's passes as more forecasts than it had
        # bets, and read one bet twice. From operator question 17
        # (2026-09-28) a bet is `bet.of`, so two rungs of one game are two
        # questions here as on the curve beside it.
        n, bets, read = row.get("n"), row.get("distinct_bets"), row.get("with_a_claim")
        if (bets is None or n != bets or not isinstance(read, int)
                or not 0 <= read <= n):
            raise MergedCurve(
                f"{law}: {what} counts {n} questions, "
                f"{read!r} of them read, for {bets} distinct "
                f"bet{'' if bets == 1 else 's'}. A question is one bet however "
                f"many passes answered it.")
        if row.get("recounted") != n or row.get("read_recounted") != read:
            raise MergedCurve(
                f"{law}: {what} counts {n} questions, {read} of them read, "
                f"where the recount made without either door finds "
                f"{row.get('recounted')!r} and {row.get('read_recounted')!r}, "
                f"one per distinct bet by the one key (`bet.of`). A rule keyed "
                f"any other way counts other bets than the record holds "
                f"(operator question 17, 2026-09-28).")


def assert_the_records_stay_apart(payload: dict) -> None:
    """Every category belongs to the record it is filed under.

    The blind record answers the question the model chose; the at-the-line
    record answers the venue's. A payload holding both would average a
    forecast against its own rung with a forecast against a price, and the
    result would describe neither -- the same failure LAW 6 names one level up.
    """
    record = payload.get("record")
    if record not in ("rung", "at_the_line"):
        raise MergedRecord(
            f"a scorecard must say which record it is: {record!r} is neither "
            f"'rung' nor 'at_the_line'.")
    for category in payload.get("categories") or []:
        theirs = category.get("record")
        if theirs != record:
            raise MergedRecord(
                f"category {category.get('category')!r} belongs to the "
                f"{theirs!r} record and is filed under the {record!r} one. The "
                f"blind record and the at-the-line record are never merged: "
                f"one is what the model said about its own question, the other "
                f"what it says about the venue's.")


# ---------------------------------------------------------------------------
# SCORING THE RANKER ITSELF (THE_SHORTLIST S3, 2026-09-07)
# ---------------------------------------------------------------------------
#
# The reason the rank is written to the database rather than computed when the
# page loads. A shortlist is a claim of a kind -- that these twenty questions
# are the better ones -- and this project does not ship claims it cannot check.
#
# TWO CURVES, NEVER ONE. The questions that led their slate, and the questions
# they outranked, scored separately with their own N and the same hundred-
# resolution gate as every other figure here. Below the gate there is no
# verdict at all, only the count and what is missing.
#
# BACKFILLED RANKS ARE EXCLUDED, and the exclusion matters more than it looks.
# A rank computed after the games were played, by a formula written today, is
# not the same object as one computed before kickoff: it cannot have been
# influenced by the outcome, but it was written by somebody who already knew
# it. Mixing the two would flatter the ranker with rows it never really
# ordered.


def ranker_comparison(conn: sqlite3.Connection, *, sport: str,
                      market_type: str, prop_type: str | None = None,
                      predictor: str = "statistical") -> dict:
    """Did the shortlist calibrate better than what it outranked?"""
    from . import shortlist as ranker

    require_sport(sport, "calibration.ranker_comparison")
    items = resolved(conn, sport=sport, market_type=market_type,
                     prop_type=prop_type, predictor=predictor)
    ranks = ranker.ranks_for(conn, [r.id for r in items])
    led, rest = [], []
    for row in items:
        rank = ranks.get(row.id)
        if rank is None or rank["backfilled"]:
            continue
        (led if rank["on_shortlist"] else rest).append(row)

    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    led_score, rest_score = score(led), score(rest)
    payload = {
        "sport": sport,
        "record": "ranker",
        "market": prop_type or market_type,
        "ranker_version": config.RANKER_VERSION,
        "n": len(led) + len(rest),
        "gate": gate,
        "shortlisted": {
            "label": "led the slate", "n": len(led), "score": led_score,
            "buckets": calibration_buckets(led),
        },
        "not_shortlisted": {
            "label": "outranked", "n": len(rest), "score": rest_score,
            "buckets": calibration_buckets(rest),
        },
        "gate_line": language.ranker_gate_line(len(led), len(rest), gate),
        "excludes_backfilled": True,
    }
    payload["renderable"] = len(led) >= gate and len(rest) >= gate
    if payload["renderable"]:
        payload["verdict"] = language.ranker_verdict_line(
            led_score["brier"], rest_score["brier"], len(led), len(rest))
    else:
        payload["verdict"] = None
        payload["shortfall"] = max(gate - len(led), 0) + max(gate - len(rest), 0)
    return payload


def ranker_scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """One comparison per market of one sport, kept apart like every curve."""
    require_sport(sport, "calibration.ranker_scorecard")
    markets = config.SPORT_MARKETS.get(sport, ())
    comparisons = [
        ranker_comparison(conn, sport=sport,
                          market_type=market_type_of(sport, market),
                          prop_type=prop_type_of(sport, market))
        for market in markets
    ]
    return {
        "sport": sport,
        "record": "ranker",
        "ranker_version": config.RANKER_VERSION,
        "n": sum(c["n"] for c in comparisons),
        "comparisons": comparisons,
        "note": (
            "The shortlist is an ordering, and an ordering can be wrong. These "
            "compare what led each slate against what it outranked, separately "
            "per market, with the same gate as every other figure. Ranks "
            "computed after the fact are left out: a formula written today "
            "cannot be scored on games it already knows the answer to."
        ),
    }


# ---------------------------------------------------------------------------
# CLOSING-LINE VALUE (THE_RECOMMENDATION R3, 2026-09-07)
# ---------------------------------------------------------------------------
#
# THE VERDICT THAT ARRIVES FIRST. Every other figure on this page waits for
# games to finish and for a hundred of them to accumulate. This one compares
# the price the app recommended against the market's own final estimate of the
# same question, which is a far less noisy comparison than one outcome -- it
# says something at around fifty observations rather than several hundred.
#
# IT IS STILL A CLAIM, so it renders with its N and claims nothing below the
# declared minimum. And it is capable of returning bad news: a negative mean
# means the app is buying prices the market is about to move away from, and the
# sentence for that case is written in `language.clv_finding_line` rather than
# improvised on the day.

#: HOW MANY RECOMMENDATIONS BEFORE THE CLOSING LINE SAYS ANYTHING. Fifty,
#: declared 2026-09-07 and deliberately not the hundred of MIN_SAMPLE_FOR_EDGE_CLAIM:
#: this compares two prices for the same question rather than a forecast
#: against an outcome, so most of the variance an edge estimate fights through
#: is not in it. The number is a judgement and is dated as one.
MIN_RECOMMENDATIONS_FOR_CLV = 50
#: WHERE THE FIRST WINDOW STARTED, kept in the payload beside the second
#: (2026-09-27). The count started again on `config.CLOSING_LINE_WINDOW_START`
#: by the operator's ruling 8 of 2026-09-23, because nothing counted from this
#: date had been measured: every close before the repair was the price paid.
CLV_DECLARED = "2026-09-07T00:00:00Z"

#: AND A HUNDRED FOR A PACKAGE (GRIDIRON_COMBOS C4, 2026-09-08). A package's
#: close is the product of two or three moving quotes, so the same confidence
#: costs more observations than a single's does -- twice as many, which is the
#: coarsest defensible answer and is declared as a judgement, not fitted.
#: `MIN_PACKAGES_FOR_CLV = 100` stood here from 2026-09-08 until C4 was
#: WITHDRAWN on 2026-09-09. A package needed twice a single's observations
#: before its closing-line number meant anything -- a sound threshold for a
#: product with a closing line. A combo has none: the app never sees the price
#: the operator was quoted, so there is nothing to close against.
COMBO_CLV_WITHDRAWN = "2026-09-09"


def clv_minimum(market: str) -> int:
    """How many closes this market needs before its number means anything.

    ONE ANSWER NOW. The combo branch went with C4: no combo settles, so no
    combo market ever reaches this function.
    """
    return MIN_RECOMMENDATIONS_FOR_CLV


def closing_line_window(now: str | None = None) -> dict:
    """When the closing line counts from, and whether it may be read yet.

    THE ONE DOOR FOR THE OPERATOR'S RULING 8 OF 2026-09-23 (GRIDIRON_REPAIR
    item 8, built 2026-09-27): "the observation window restarts on the date
    item 1 ships; the first clean CLV read is 21 days after that, not before."
    The dates are `config.CLOSING_LINE_WINDOW_START` and
    `config.CLOSING_LINE_FIRST_CLEAN_READ`; whether today is on or after the
    second is asked here and nowhere else, counted in days by the same
    `language.date_gate` every dated window on the Record page uses.

    `now` is an instant (the record's format); only its UTC date is read. It
    defaults to the clock, and a test or a planting passes it so that what it
    proves does not change on 15 October.
    """
    from .db import utcnow

    today = (now or utcnow())[:10]
    days = language.date_gate(config.CLOSING_LINE_WINDOW_START,
                              config.CLOSING_LINE_FIRST_CLEAN_READ, today=today)
    return {
        "from": config.CLOSING_LINE_WINDOW_START,
        "from_utc": config.CLOSING_LINE_WINDOW_START + "T00:00:00Z",
        "first_clean_read": config.CLOSING_LINE_FIRST_CLEAN_READ,
        "open": bool(days["cleared"]),
        "days": days,
    }


def _both_sides_groups(sport: str, rows: list[dict]) -> list[dict]:
    """One entry per game and market recommended on both sides: its market in
    words, the day its first row was written, and how many rows it holds --
    what `language.both_sides_recommendations_line` says (question 12)."""
    groups: dict[tuple[str, str], dict] = {}
    for row in rows:                       # first first, as the door lists them
        group = groups.setdefault((row["game_id"], row["market"]), {
            "market": language.market_words(sport, row["market"]),
            "day": row["created_utc"][:10], "n": 0})
        group["n"] += 1
    return list(groups.values())


def clv_report(conn: sqlite3.Connection, *, sport: str,
               now: str | None = None) -> dict:
    """What the closing line says about this sport's recommendations.

    COUNTED FROM `recommendation_closes`, NOT FROM THE COLUMNS (2026-09-23).
    Until then every close was the recommendation's own price and this read
    49 rows at 0.00c as a measurement. Now:

      * MEASURED -- a close by the one rule, at the time: counted, in N.
      * UNMEASURED -- closed with no later read of its own contract, or closed
        by the old closer and not yet restated: counted BESIDE, never at zero.
      * RESTATED -- an old close recomputed after the fact from quotes the
        record held before the start: counted beside too. It was computed by
        somebody who knew how the games went, so it is shown and never counted.
      * UNACCOUNTED -- an old close not yet restated. Its recorded value is
        its own price; counted beside, with its own words, until it is.
      * WITHDRAWN (ruling 1, 2026-09-24) -- a recommendation voided, or made
        on a voided forecast. Not in N, not in any bucket above, not awaiting
        a close: named once beside the closing line, in that word, and never
        counted anywhere. Every read below goes through
        `recommend.not_withdrawn`, the one door (from 2026-09-27 inside
        `recommend.counted_once`, which is that door and question 12's rule).
      * WOULD NOT HAVE CLEARED (GRIDIRON_REPAIR item 4, 2026-09-26) -- a
        recommendation the bar let through by dividing a no-side edge by the
        yes price, re-graded after the fact. A LABEL, NOT A WITHDRAWAL: it
        stays in whichever count above it was in -- the ruling says re-grade,
        where it says void when it means out of the counts -- and it is
        named once beside the closing line, with its N and its return on
        what its side cost.
      * BEFORE THE WINDOW (the operator's ruling 8 of 2026-09-23, built
        2026-09-27) -- a measured close on a recommendation written before
        `config.CLOSING_LINE_WINDOW_START`, the day the closing line was
        repaired. Counted beside, never in N: the count started again that
        day. (None exists on the record: every close before the repair was
        the old closer's, and is restated or unaccounted above.)
      * A PAIR, COUNTED ONCE; BOTH SIDES, NOT AT ALL (operator question 12,
        ruled 2026-09-27) -- every read above goes through
        `recommend.counted_once`: of a game and market's standing rows all on
        one side only the first is in any figure above, and each later one
        is a REPEAT, named beside its market ("counted once, as the earlier
        one");
        a game and market recommended on both sides is in no figure above,
        and its rows are named once beside the closing line under the
        ruling's label, "both sides, no position", with their N. The rows
        stay as written; the tallies of what was set aside (`set_aside`)
        are in the payload so the withdrawn recount can still add up every
        standing row.

    AND NO FIGURE BEFORE THE FIRST CLEAN READ (the same ruling: "the first
    clean CLV read is 21 days after that, not before"). Until
    `config.CLOSING_LINE_FIRST_CLEAN_READ`, asked through
    `closing_line_window`, no entry is renderable, its mean and the share
    that beat the close are None rather than figures nobody may read, no
    finding is written, and the words say the date. The count, with its N, is
    shown throughout: how many there are is not a verdict on them.
    """
    from .market import recommend

    require_sport(sport, "calibration.clv_report")
    window = closing_line_window(now)
    # COUNTED ONCE (operator question 12, 2026-09-27): a same-side pair is
    # its earlier row here, and both sides of one game and market are
    # neither. `counted_once` is `not_withdrawn` and that rule, in one door.
    rows = conn.execute(
        "SELECT r.market, r.side, r.price, c.clv_cents, c.restated,"
        "       c.recommendation_id IS NOT NULL AS accounted,"
        "       r.created_utc >= ? AS in_window"
        "  FROM recommendations r"
        "  LEFT JOIN recommendation_closes c ON c.recommendation_id = r.id"
        " WHERE r.sport = ? AND r.closed_utc IS NOT NULL"
        + recommend.counted_once(conn),
        (window["from_utc"], sport)).fetchall()
    by_market: dict[str, list] = {}
    for row in rows:
        by_market.setdefault(row["market"], []).append(row)
    # WHAT THE DOOR LEFT OUT, NAMED RATHER THAN VANISHED: the repeats beside
    # their market's count, both sides beside the closing line.
    aside = recommend.not_counted_once(conn, sport=sport)
    repeats: dict[str, int] = {}
    for row in aside:
        if row["why"] == recommend.REPEAT:
            repeats[row["market"]] = repeats.get(row["market"], 0) + 1
    both = [row for row in aside if row["why"] == recommend.BOTH_SIDES]

    entries = []
    for market in sorted(set(by_market) | set(repeats)):
        closed = by_market.get(market, [])
        measured = [r for r in closed if r["accounted"] and not r["restated"]
                    and r["clv_cents"] is not None]
        # THE COUNT STARTED AGAIN ON THE DAY OF THE REPAIR (ruling 8): a
        # measured close on a recommendation written before it is named
        # beside, never counted.
        got = [r for r in measured if r["in_window"]]
        before_window = len(measured) - len(got)
        restated = sum(1 for r in closed if r["accounted"] and r["restated"]
                       and r["clv_cents"] is not None)
        # CLOSED BY THE OLD CLOSER AND NOT YET RESTATED: its recorded close is
        # its own price, and nothing is known either way until it is.
        unaccounted = sum(1 for r in closed if not r["accounted"])
        unmeasured = len(closed) - len(measured) - restated - unaccounted
        n = len(got)
        # NO FIGURE BEFORE THE FIRST CLEAN READ (ruling 8). Not computed,
        # rather than computed and held back, so nothing downstream -- the
        # kill criterion, a payload read by hand -- can read one early.
        figures = bool(n) and window["open"]
        mean = round(sum(r["clv_cents"] for r in got) / n, 2) if figures else None
        beat = (round(sum(1 for r in got if r["clv_cents"] > 0) / n, 4)
                if figures else None)
        # ITS OWN N AND ITS OWN GATE. `combo_2` and `combo_3` are markets
        # here exactly like `moneyline` is, which is what keeps a package out
        # of a leg's count: this loop groups by the market a row was written
        # under, and a package is never written under a leg's.
        floor = clv_minimum(market)
        entry = {
            "sport": sport,
            "market": market,
            "n": n,
            "unmeasured": unmeasured,
            "restated": restated,
            "unaccounted": unaccounted,
            "before_window": before_window,
            # QUESTION 12: the later rows of this market's same-side pairs,
            # in no figure here, named beside it.
            "repeats": repeats.get(market, 0),
            "minimum_for_a_claim": floor,
            # THE DATE AND THE SAMPLE, both: a verdict needs fifty closes
            # counted from the repair AND the first clean read to have come.
            "renderable": window["open"] and n >= floor,
            "mean_cents": mean,
            "beat_the_close": beat,
            "words": language.clv_line(
                n, mean, beat, floor, unmeasured=unmeasured,
                restated=restated, unaccounted=unaccounted,
                before_window=before_window, repeats=repeats.get(market, 0),
                since=window["from"],
                first_read=(None if window["open"]
                            else window["first_clean_read"])),
        }
        if entry["renderable"] and mean is not None and mean < 0:
            entry["finding"] = language.clv_finding_line(mean, n)
        entries.append(entry)

    open_rows = conn.execute(
        "SELECT COUNT(*) FROM recommendations r"
        " WHERE r.sport = ? AND r.closed_utc IS NULL" + recommend.counted_once(conn),
        (sport,)).fetchone()[0]
    # WHAT WAS SET ASIDE, TALLIED AS THE COUNTS ABOVE ARE (question 12), so
    # `audit.withdrawn_counted_faults` can still add every standing row up:
    # a measured close is one with its account written at the time.
    aside_ids = [row["id"] for row in aside]
    aside_measured = (conn.execute(
        "SELECT COUNT(*) FROM recommendation_closes c"
        f" WHERE c.recommendation_id IN ({','.join('?' * len(aside_ids))})"
        "   AND c.restated = 0 AND c.clv_cents IS NOT NULL",
        aside_ids).fetchone()[0] if aside_ids else 0)
    # SHOWN, NEVER COUNTED. A withdrawn recommendation that simply vanished
    # from this report would be a deletion by omission; it is named here, with
    # its reason, and in no figure above.
    withdrawn = recommend.withdrawn(conn, sport=sport)
    # NAMED, AND COUNTED WHERE THEY WERE (GRIDIRON_REPAIR item 4, 2026-09-26):
    # the recommendations the corrected bar would have refused, beside the
    # closing line and never taken out of it.
    regraded = recommend.regraded(conn, sport=sport)
    counted = sum(e["n"] for e in entries)
    return {
        "sport": sport,
        "record": "closing_line",
        "declared": CLV_DECLARED,
        # THE SECOND WINDOW (ruling 8, 2026-09-27): from when the count runs,
        # the first clean read, whether it has come, and the days between.
        "window": {"from": window["from"],
                   "first_clean_read": window["first_clean_read"],
                   "open": window["open"], "days": window["days"]},
        "window_line": {
            "label": "Since the repair",
            "n": counted,
            "words": language.closing_line_window_line(
                window["from"], window["first_clean_read"], counted,
                verdict_open=window["open"]),
        },
        "n": counted,
        "unmeasured": sum(e["unmeasured"] for e in entries),
        "restated": sum(e["restated"] for e in entries),
        "unaccounted": sum(e["unaccounted"] for e in entries),
        "before_window": sum(e["before_window"] for e in entries),
        "awaiting_close": open_rows,
        "withdrawn": len(withdrawn),
        "withdrawn_line": ({
            "label": "Withdrawn",
            "n": len(withdrawn),
            "words": language.withdrawn_recommendations_line(
                len(withdrawn), [w["reason"] for w in withdrawn]),
        } if withdrawn else None),
        "regraded": len(regraded),
        "regraded_line": ({
            "label": "Would not have cleared",
            "n": len(regraded),
            "words": language.regraded_recommendations_line(
                [(g["return_on_cost"], g["minimum_return"]) for g in regraded]),
        } if regraded else None),
        # OPERATOR QUESTION 12 (ruled 2026-09-27). The later rows of
        # same-side pairs, each counted once as its earlier row (named per
        # market above), and the rows of a game and market recommended on
        # both sides, counted nowhere and named here under the ruling's own
        # label with their N -- derived on every read, never stored.
        "repeats": sum(repeats.values()),
        "both_sides": len(both),
        "both_sides_line": ({
            "label": recommend.BOTH_SIDES_LABEL,
            "n": len(both),
            "words": language.both_sides_recommendations_line(
                _both_sides_groups(sport, both)),
        } if both else None),
        "set_aside": {
            "n": len(aside),
            "measured": aside_measured,
            "closed": sum(1 for row in aside if row["closed"]),
            "awaiting_close": sum(1 for row in aside if not row["closed"]),
        },
        "markets": entries,
        "note": (
            "The price the app recommended against the market's own final "
            "estimate of the same question. It needs about fifty observations "
            "to say anything, where a win rate needs several hundred, which is "
            "why it is the first verdict this project can reach. A positive "
            "number means it is buying cheaper than the close."
        ),
    }


# ---------------------------------------------------------------------------
# THE PRICED FORECASTER'S OWN RECORD (THE_PRICED P1/P4, 2026-09-07)
# ---------------------------------------------------------------------------
#
# NEVER MERGED WITH THE BLIND ONE, and the reason is the whole point of having
# two. A forecaster that reads the price will beat a blind one at predicting
# outcomes while teaching nobody anything about the model's own skill, because
# most of what it knows it read off the market. Reported side by side, they
# answer two different questions: "are we any good?" and "are we making money?"
#
# ITS OBJECTIVE IS NOT A BRIER SCORE. A priced forecaster with a worse Brier
# score and a better closing line is succeeding, and this payload is built so
# the page can say that without a reader thinking something has gone wrong.


def priced_scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """What the priced forecaster's rows say, beside the blind ones.

    Both scores are reported for the same questions -- the priced rows carry
    the id of the blind row they came from -- so the comparison is like for
    like rather than across two different question sets.

    ONE CATEGORY PER MARKET, TIER AND BLIND FORECASTER, ONE ROW PER STANDING
    QUESTION (operator question 14, ruled 2026-09-27, 1 of 3: "Every count on
    the Record page that states a gate distance is rebuilt per forecaster
    (per tier for UFC) and per distinct bet, through its record's standing
    rule."). A priced row blends one blind forecast, so it is counted as that
    forecast's forecaster's, through the one door
    (`priced.forecast.standing_forecasts`, the blind record's standing rule).
    Until this date every settled priced row of a market was one count --
    both forecasters, a question's morning and final pass -- and MLB
    moneyline's gate line said "261 settled comparisons, past the 100 this
    record needs" for 96 and 84 standing questions.

    ONE PER DISTINCT BET, RECOUNTED (operator question 17, 2026-09-28): the
    door keys by `bet` through the standing clause, and the same read asks
    `gridiron.recount` for each forecaster's settled priced bets per market
    without it. A market the recount holds is a category even where the
    door found none, so a door that lost a market is seen, not skipped; each
    category carries `recounted` for `assert_no_pooled_priced_counts`.
    """
    from . import db, recount
    from .priced import forecast as priced

    require_sport(sport, "calibration.priced_scorecard")
    tiers = config.event_tiers(sport) or (None,)
    cells: dict[tuple, list] = {}
    recounted: dict[tuple, int] = {}
    with db.one_instant(conn):
        for tier in tiers:
            for predictor in priced.BLIND_FORECASTERS:
                rows = priced.standing_forecasts(conn, sport=sport,
                                                 predictor=predictor,
                                                 event_tier=tier)
                for row in priced.settled(rows):
                    cells.setdefault((row["market"], tier, predictor),
                                     []).append(row)
                again = recount.priced(conn, sport=sport, predictor=predictor,
                                       event_tier=tier,
                                       blend_version=config.PRICED_VERSION)
                for market, n in again.items():
                    recounted[(market, tier, predictor)] = n
                    cells.setdefault((market, tier, predictor), [])

    categories = []
    # A CATEGORY WHERE SOMETHING HAS SETTLED, as before this date (a market
    # with none showed no row); the markets in name order, then the tiers in
    # their declared order, then the statistical model before the reasoning
    # pass, as every other list on the Record page.
    for market, tier, predictor in sorted(
            cells, key=lambda k: (k[0], tiers.index(k[1]),
                                  priced.BLIND_FORECASTERS.index(k[2]))):
        got = cells[(market, tier, predictor)]
        priced_items = [_PricedResolved(r["priced_prob"], r["outcome"]) for r in got]
        blind_items = [_PricedResolved(r["blind_prob"], r["outcome"]) for r in got]
        market_items = [_PricedResolved(r["price_at_write"], r["outcome"]) for r in got]
        filters = {"sport": sport, "market": market, "predictor": predictor,
                   "record": "priced"}
        if prop_type_of(sport, market):
            filters["prop_type"] = market
        if tier is not None:
            filters["event_tier"] = tier
        categories.append({
            "sport": sport,
            "record": "priced",
            "forecaster": "priced",
            # WHOSE FORECASTS WERE PRICED, and on which card (2026-09-27).
            "predictor": predictor,
            "event_tier": tier,
            "market": market,
            "category": " / ".join([market] + ([tier] if tier else [])
                                   + [predictor, "priced"]),
            "category_label": language.priced_category_label(
                sport, market, predictor, tier),
            "filters": filters,
            "blend_version": config.PRICED_VERSION,
            "n": len(got),
            # COUNTED BESIDE THE DOOR, NOT BY IT: read off the rows' own
            # questions, forecasters and cards, so a door that let a bet in
            # twice, or two forecasters or two cards in, is seen.
            "distinct_bets": bet.count(got),
            "recounted": recounted.get((market, tier, predictor), 0),
            "forecasters_counted": sorted({r["predictor"] for r in got}),
            "tiers_counted": sorted({r["event_tier"] for r in got
                                     if r["event_tier"] is not None}),
            "priced": score(priced_items),
            "blind_on_the_same_questions": score(blind_items),
            "market_on_the_same_questions": score(market_items),
            "buckets": calibration_buckets(priced_items),
            "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
            "gate_line": language.at_the_line_gate_line(
                len(got), config.MIN_SAMPLE_FOR_EDGE_CLAIM),
        })

    payload = {
        "sport": sport,
        "record": "priced",
        "blend_version": config.PRICED_VERSION,
        "model_weight": config.PRICED_MODEL_WEIGHT,
        "declared": config.PRICED_WEIGHT_DECLARED,
        # NO TOTAL, AND NO POOLED "AWAITING" COUNT (2026-09-27). The `n` that
        # stood here summed every category -- both forecasters -- and
        # `awaiting_outcome` counted every unsettled priced row of the sport,
        # both passes of a question included. Neither was painted; both
        # described nobody's record, as item 6's at-the-line total did.
        "categories": categories,
        "note": (
            "A second forecaster that reads the price the blind one is forbidden "
            "to see. Its scores are shown beside the blind forecaster's on the "
            "same questions and are never added to them. A better Brier score "
            "here would mostly be the market's skill, not this project's, which "
            "is why the number that matters for this record is the closing line "
            "rather than the curve."
        ),
    }
    # INSIDE THE BUILDER (question 14, 2026-09-27), so the API answers 500
    # rather than serve a pooled count, and the gate's build of every sport
    # on the record's copy runs it (`audit.check_the_priced_record_is_never_pooled`).
    assert_no_pooled_priced_counts(payload)
    assert_every_figure_has_n(payload)
    assert_single_sport(payload, sport)
    return payload


#: The three scores a priced category reports on ONE set of questions.
PRICED_SCORES = ("priced", "blind_on_the_same_questions",
                 "market_on_the_same_questions")


def assert_no_pooled_priced_counts(payload: dict) -> None:
    """Every count in the priced record is ONE blind forecaster's STANDING
    QUESTIONS, once each -- and for UFC one card's.

    The operator's ruling on question 14 (2026-09-27): "Every count on the
    Record page that states a gate distance is rebuilt per forecaster (per
    tier for UFC) and per distinct bet, through its record's standing rule."
    Checked on the payload, as `assert_no_pooled_claims` checks the
    at-the-line record's -- and it runs `assert_no_merged_categories` first,
    so the sport, the market, the forecaster and the tier are one rule for
    every record.

    Then, by name: a category that counts more rows than it has distinct
    bets (a question's morning and final pass); one whose rows are another
    forecaster's, or another card's, than the one it names; one naming no
    blind forecaster; a count other than the one `gridiron.recount` makes
    without the door, one per distinct bet by the one key (operator question
    17, 2026-09-28: a door keyed without the rung, or across forecasters);
    a score on other questions than the count; a gate line stating another
    count than its own (the page said "261 settled comparisons, past the
    100" for 96 and 84 standing questions on 26 September); and a total or a
    pooled "awaiting" count across categories. Raised inside
    `priced_scorecard`, so the API answers 500 rather than serving a pool.
    """
    from .priced import forecast as priced

    law = "LAW 4 / LAW 6 IN THE PRICED RECORD"
    assert_no_merged_categories(payload)
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    for key in ("n", "awaiting_outcome"):
        if key in payload:
            raise MergedCurve(
                f"{law}: the priced payload carries a total {key!r} of "
                f"{payload[key]!r}, a sum across its categories and so across "
                f"both forecasters and every pass of a question, which is "
                f"nobody's record.")
    for category in payload.get("categories") or []:
        what = f"priced category {category.get('category')!r}"
        if category.get("record") != "priced":
            raise MergedRecord(
                f"{what} belongs to the {category.get('record')!r} record and "
                f"is filed under the priced one.")
        named = category.get("predictor")
        filtered = (category.get("filters") or {}).get("predictor")
        if named not in priced.BLIND_FORECASTERS or filtered != named:
            raise MergedCurve(
                f"{law}: {what} names forecaster {named!r} (filtered by "
                f"{filtered!r}). A priced row blends one blind forecast, and "
                f"the statistical model's and the reasoning pass's are counted "
                f"apart and never pooled.")
        counted = category.get("forecasters_counted")
        if counted not in ([], [named]):
            raise MergedCurve(
                f"{law}: {what} is the {named!r} forecaster's and counts rows "
                f"on the forecasts of {counted!r}: two forecasters pooled into "
                f"one count.")
        tier, cards = category.get("event_tier"), category.get("tiers_counted")
        if tiers:
            if tier not in tiers or cards not in ([], [tier]):
                raise MergedCurve(
                    f"{law}: {what} names event tier {tier!r} and counts bouts "
                    f"on {cards!r}; {sport}'s tiers {list(tiers)} are reported "
                    f"side by side, never summed.")
        elif tier is not None or cards not in ([], None):
            raise MergedCurve(
                f"{law}: {what} names event tier {tier!r} in {sport}, which "
                f"declares none.")
        n, bets = category.get("n"), category.get("distinct_bets")
        if bets is None or n != bets:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled priced rows for {bets} "
                f"distinct bet{'' if bets == 1 else 's'}. A question is counted "
                f"once, on its standing forecast, however many passes priced it.")
        for key in PRICED_SCORES:
            scored = (category.get(key) or {}).get("n")
            if scored != n:
                raise MergedCurve(
                    f"{law}: {what} counts {n} and scores {key!r} on {scored!r}: "
                    f"two counts of one record.")
        said = language.at_the_line_gate_line(n, category.get("gate"))
        if category.get("gate_line") != said:
            raise MergedCurve(
                f"{law}: {what}'s gate line says {category.get('gate_line')!r}, "
                f"which is not its own count of {n}.")
        # AND THE RECOUNT MADE WITHOUT THE DOOR (operator question 17,
        # 2026-09-28): a door keyed without the rung, or across forecasters,
        # counts other questions than the record holds while its own
        # distinct bets, scores and gate line all agree with it.
        if category.get("recounted") != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled priced rows where the "
                f"recount made without its door finds "
                f"{category.get('recounted')!r}, one per distinct bet by the "
                f"one key (`bet.of`: the forecaster, the game, the market, the "
                f"subject and the rung asked). A door keyed any other way -- "
                f"without the rung, or across forecasters -- counts other bets "
                f"than the record holds (operator question 17, 2026-09-28).")


@dataclass(frozen=True)
class _PricedResolved:
    """The two fields the bucket and score functions actually read."""
    model_prob: float
    outcome: int


def taken_comparison(conn: sqlite3.Connection, *, sport: str,
                     market_type: str, prop_type: str | None = None,
                     predictor: str = "statistical") -> dict:
    """Do the picks the operator took score better than the ones he passed over?

    THREE CURVES, NEVER MERGED: taken, not taken, and all of them. The third is
    not the sum of the first two in any useful sense -- it is the population
    both were drawn from, and it is reported so that a reader can see whether
    either group differs from the model's ordinary behaviour at all.

    NOTHING HERE FEEDS THE MODEL. This is a report about a human being's
    choices, read after the fact; `audit.check_taken_not_in_training` refuses
    the table's name in anything that trains or corrects, and a planting proves
    it fires.
    """
    require_sport(sport, "calibration.taken_comparison")
    items = resolved(conn, sport=sport, market_type=market_type,
                     prop_type=prop_type, predictor=predictor)
    # SINGLE TAPS ONLY IN THIS COMPARISON. A package tap is a row in the same
    # table carrying a package id instead of a prediction id, and it belongs to
    # `combo_2`/`combo_3` rather than to this market -- counting it here would
    # put a package in a leg's curve, which is LAW 6 one level down.
    taken_set = {
        r["prediction_id"] for r in conn.execute(
            "SELECT prediction_id FROM picks_taken"
            " WHERE prediction_id IS NOT NULL"
            "   AND id NOT IN (SELECT taken_id FROM picks_retracted)")
    }
    took = [r for r in items if r.id in taken_set]
    passed = [r for r in items if r.id not in taken_set]
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    payload = {
        "sport": sport,
        "record": "taken",
        "market": prop_type or market_type,
        "n": len(items),
        "gate": gate,
        "taken": {"label": "taken", "n": len(took), "score": score(took),
                  "buckets": calibration_buckets(took)},
        "not_taken": {"label": "passed over", "n": len(passed),
                      "score": score(passed), "buckets": calibration_buckets(passed)},
        "all": {"label": "every forecast", "n": len(items), "score": score(items),
                "buckets": calibration_buckets(items)},
        "renderable": len(took) >= gate and len(passed) >= gate,
        "note": (
            "What the operator chose against what he passed over, on the same "
            "questions and the same scale. It reads his selections, never the "
            "model's inputs: nothing that trains or corrects the model may see "
            "this table."
        ),
    }
    payload["words"] = language.taken_comparison_line(
        len(took), len(passed), gate,
        payload["taken"]["score"]["brier"] if payload["renderable"] else None,
        payload["not_taken"]["score"]["brier"] if payload["renderable"] else None)
    return payload


# `combo_kill_verdict` STOOD HERE from 2026-09-08 until C4 was WITHDRAWN on
# 2026-09-09. It asked whether a sport's packages were losing to the close
# while its singles beat it, and retired the combo markets when they were.
#
# IT COULD NEVER HAVE FIRED. It counted SETTLED packages, and a combo cannot
# settle: the app never sees the price the operator was quoted, so there is no
# closing line to compare against and no verdict to reach. A criterion that
# cannot fire is worse than no criterion -- it reads as a safety net while
# being a sign saying one is there.
#
# What replaced it is a sentence on the card and a line in READINESS saying
# the product is unmeasurable by construction, which is the true thing.


def taken_packages(conn: sqlite3.Connection, *, sport: str) -> dict:
    """The combo line on the taken record: what he took, of what was offered.

    ITS OWN LINE AND NEVER MERGED into the single-leg comparison. A package and
    a leg are different products at different prices with different fees, and
    one curve holding both would report a rate for a thing nobody buys.

    IT IS A COUNT, NOT A CURVE, until there are packages to score. Below the
    gate that is all it can honestly be, and the sentence says so.
    """
    require_sport(sport, "calibration.taken_packages")
    # PLACED IN GAMES THIS RECORD HOLDS, or it was never priceable here. A
    # package naming games the project has never seen has no legs to multiply,
    # so it is not one of the packages this app was "able to price at all" and
    # does not belong in the denominator. Added 2026-09-08 after a verification
    # run against the live database wrote exactly such a row.
    offered = conn.execute(
        "SELECT COUNT(*) FROM venue_packages v WHERE v.sport = ? AND v.priceable = 1"
        "   AND EXISTS (SELECT 1 FROM games g WHERE instr(v.game_ids, g.id) > 0)",
        (sport,)).fetchone()[0]
    took = conn.execute(
        "SELECT COUNT(*) FROM picks_taken t"
        "  JOIN venue_packages p ON p.id = t.package_id"
        " WHERE p.sport = ?"
        "   AND t.id NOT IN (SELECT taken_id FROM picks_retracted)"
        "   AND EXISTS (SELECT 1 FROM games g WHERE instr(p.game_ids, g.id) > 0)",
        (sport,)).fetchone()[0]
    return {
        "sport": sport,
        "record": "taken_packages",
        "market": "packages",
        "offered": offered,
        "n": took,
        "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
        "renderable": False if took < config.MIN_SAMPLE_FOR_EDGE_CLAIM else True,
        "words": language.taken_packages_line(
            took, offered, config.MIN_SAMPLE_FOR_EDGE_CLAIM),
        "note": (
            "Packages the operator marked, against the packages this app was "
            "able to price at all. It is its own line: a package and a single "
            "leg are different products, and one curve holding both would "
            "describe neither."
        ),
    }
