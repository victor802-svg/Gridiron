"""The blind prediction core — steps 1 to 4 of the loop, for any sport.

  1. select the questions for the slate (the sport's adapter decides how)
  2. compute the factor vector from stored data only
  3. produce probabilities: the statistical baseline, and the LLM pass
  3b. drop prop questions below the declared confidence floor
  4. WRITE THE PREDICTION ROWS

Step 5 — fetching the line — is deliberately not here and cannot be. This
module, every sport adapter, and everything they import has no path to
`gridiron.market`; the guard test walks each sport's import closure separately
and fails by name if one appears. The runner in `gridiron.run` calls this
inside a `blind_window()`, which additionally refuses to let the market package
be imported at all while these rows are being formed.

Nothing in this file has ever seen a line, and there is nowhere for one to
arrive — in any sport.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from datetime import date

from .. import config, sports
from ..db import utcnow
from ..factors import compute, context
from . import baseline, llm
from .question import Question
from . import rungs
from .. import correction

__all__ = ["Question", "BlindRun", "WrittenPrediction", "predict_slate", "predict_week"]


@dataclass
class WrittenPrediction:
    prediction_id: int
    question: Question
    predictor: str
    model_prob: float
    model_side: str
    degraded: str | None = None


@dataclass
class BlindRun:
    sport: str
    season: int
    week: int
    written: list[WrittenPrediction] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    degradations: dict[str, int] = field(default_factory=dict)
    #: Prop questions the model formed an answer to and did not write, because
    #: the answer was not confident enough to be worth claiming. Counted rather
    #: than dropped: a slate that ran under its cap should say why.
    below_floor: int = 0
    #: Rows added to the rung log. A MEASUREMENT, never a prediction count --
    #: see `model/rungs.py` for why the two must not be added together.
    rungs_logged: int = 0

    @property
    def prediction_ids(self) -> list[int]:
        return [w.prediction_id for w in self.written]


# ---------------------------------------------------------------------------
# step 4 — the write
# ---------------------------------------------------------------------------

def write_prediction(
    conn: sqlite3.Connection,
    q: Question,
    *,
    predictor: str,
    prob_yes: float,
    fv: compute.FeatureVector,
    reasoning: str,
    extra: dict | None = None,
    degraded: str | None = None,
    final: bool = False,
) -> WrittenPrediction | None:
    """Insert one prediction row. Returns None if this exact question has
    already been answered by this predictor under this factor set — a rerun of
    the slate is a no-op, never a second opinion.

    `final=True` IS THE ONE SECOND OPINION THAT IS ALLOWED (2026-09-03): the
    late pass answers a question the early pass already answered, deliberately
    and close to start, and the newer row supersedes the older as the standing
    forecast. Both rows are kept (LAW 3) and the early one is labelled rather
    than hidden.
    """
    side, confidence = baseline.stated_side(prob_yes, q.yes_label, q.no_label)
    payload = fv.to_json_dict()
    payload["prob_yes"] = round(prob_yes, 6)
    payload["question"] = {
        "claim": q.claim,
        "sport": q.sport,
        "market": q.market,
        "player_id": q.player_id,
        "stat": q.stat,
        "yes_label": q.yes_label,
        "no_label": q.no_label,
    }
    if extra:
        payload.update(extra)

    # An existence check rather than INSERT OR IGNORE, and the difference is
    # not stylistic. OR IGNORE swallows EVERY constraint failure, so a row
    # rejected by a CHECK looked exactly like a rerun of a question already
    # answered — which is how an entire sport's first slate silently wrote zero
    # predictions and reported success. A duplicate is a no-op; a violated
    # constraint is a bug, and the two must not return the same thing.
    already = conn.execute(
        "SELECT 1 FROM predictions WHERE game_id = ? AND market_type = ?"
        " AND subject = ? AND predictor = ? AND factor_set_version = ?"
        "   AND pass_kind = ?",
        (q.game_id, q.market_type, q.subject, predictor,
         config.FACTOR_SET_VERSION, "final" if final else "early"),
    ).fetchone()
    # MIRRORS THE UNIQUE INDEX, `pass_kind` included (2026-09-03). A check that
    # does not match the constraint it stands in for is worse than none: it
    # lets a write through and turns a clean no-op into an IntegrityError,
    # which is exactly how the final pass failed the first time it ran.
    if already:
        return None

    # THE CORRECTION, APPLIED AT WRITE TIME AND ONLY HERE.
    #
    # `model_prob` is what the model claimed and is never touched. When the
    # category has an active correction, the number the interface will SHOW is
    # computed now and stored beside the raw claim, with the version that
    # produced it. Two consequences, both intended:
    #
    #   * nothing already written ever changes (LAW 3) -- a correction reaches
    #     only predictions made after it activates;
    #   * every version is gradeable, because the rows written under it carry
    #     its number and have their own forward record.
    #
    # A raw category leaves both NULL, which reads correctly as "no correction
    # was in force", because none was.
    claimed = round(min(max(confidence, 0.001), 0.999), 6)
    shown, correction_version = correction.shown_claim(
        conn, sport=q.sport, market_type=q.market_type, forecaster=predictor,
        claim=claimed)
    calibrated = shown if correction_version is not None else None

    cur = conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " pass_kind, factor_set_version, factors_json, reasoning, degraded,"
        " calibrated_prob, correction_version)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            utcnow(),
            q.sport,
            q.game_id,
            q.market_type,
            q.stat if q.market_type == "prop" else None,
            q.subject,
            q.line_asked,
            claimed,
            side,
            predictor,
            "final" if final else "early",
            config.FACTOR_SET_VERSION,
            json.dumps(payload),
            reasoning,
            degraded,
            calibrated,
            correction_version,
        ),
    )
    conn.commit()
    if cur.lastrowid is None:
        return None
    return WrittenPrediction(
        prediction_id=cur.lastrowid,
        question=q,
        predictor=predictor,
        model_prob=confidence,
        model_side=side,
        degraded=degraded,
    )


# ---------------------------------------------------------------------------
# the loop
# ---------------------------------------------------------------------------

def predict_slate(
    conn: sqlite3.Connection,
    sport: str,
    season: int,
    week: int,
    *,
    include_props: bool = True,
    use_llm: bool = True,
    llm_client=None,
    progress=None,
    final: bool = False,
) -> BlindRun:
    """Steps 1-4, for one slate of one sport. No line is fetched or reachable.

    `final=True` is the late pass: the same prediction path, the same blind
    window, run again close to start so the forecast is made on what is known
    then rather than on what was known days earlier.
    """
    adapter = sports.get(sport)
    run = BlindRun(sport=sport, season=season, week=week)
    cache = context.WeekCache()

    # BLIND FIRST implies BEFORE. A live record may only contain predictions
    # written before the event started; a game already under way is skipped with
    # a stated reason rather than forecast retrospectively. A backtest database
    # is exempt because retrospection is its entire purpose, and it is marked
    # and bannered so nobody reads it as a forward record.
    from ..db import database_kind, utcnow as _now

    live = database_kind(conn)["kind"] == "live"
    now = _now()

    # ...and BEFORE has a near edge as well as a far one. A slate two months out
    # is not the next slate, it is the season opener, and a forecast written for
    # it would be made with last season's rotations, last season's form and no
    # injury report — conditions that will never recur and cannot be compared
    # with anything else in the record. NBA's first run wrote 47 such rows at 52
    # days' notice before this guard existed.
    if live:
        horizon = conn.execute(
            "SELECT MIN(kickoff_utc) AS first FROM games WHERE sport = ?"
            " AND season = ? AND week = ? AND kickoff_utc IS NOT NULL",
            (sport, season, week),
        ).fetchone()
        if horizon and horizon["first"]:
            lead = _days_between(now, horizon["first"])
            if lead is not None and lead > config.MAX_FORECAST_LEAD_DAYS:
                run.skipped.append(
                    f"{sport} {season} slate {week} starts in {lead} days, beyond "
                    f"the {config.MAX_FORECAST_LEAD_DAYS}-day forecast horizon. "
                    "Nothing was written: a forecast made from a previous "
                    "season's form is not the forecast this slate will get, and "
                    "keeping both would put two incomparable things in one record."
                )
                return run

    fits: dict[str, object] = {}
    for market in config.SPORT_MARKETS.get(sport, ()):
        if not include_props and market in config.SPORT_PROP_MARKETS.get(sport, ()):
            continue
        key = baseline.market_key(sport, market)
        try:
            fits[key] = baseline.load_fit(conn, key)
        except baseline.NotTrained as exc:
            run.skipped.append(str(exc))

    llm_off: str | None = None

    for q in adapter.slate_questions(conn, season, week, include_props=include_props):
        if live:
            kickoff = conn.execute(
                "SELECT kickoff_utc, status FROM games WHERE id = ?", (q.game_id,)
            ).fetchone()
            started = kickoff and (
                kickoff["status"] == "final"
                or (kickoff["kickoff_utc"] and kickoff["kickoff_utc"] <= now)
            )
            if started:
                run.skipped.append(
                    f"{q.game_id}: already under way at {now}; a forecast written "
                    "after the first pitch is not a forecast"
                )
                continue
        if q.market_key not in fits:
            run.skipped.append(f"{q.game_id} {q.market_key}: no fitted model")
            continue
        try:
            fv, ctx = adapter.build_features(conn, q, cache)
        except KeyError as exc:
            run.skipped.append(f"{q.game_id} {q.subject}: {exc}")
            continue

        if progress:
            progress(f"{sport} {q.game_id} {q.market} {q.subject}")

        # --- the statistical path ------------------------------------------
        stat = baseline.predict(fits[q.market_key], fv)

        # THE PROPS CONFIDENCE FLOOR (config.PROPS_MIN_CLAIM, declared
        # 2026-08-30). A player-prop question whose answer the model is not at
        # least this sure of is not asked at all.
        #
        # It is blind-compatible by construction: the only input is the
        # probability the model has just produced from stored data, and there is
        # nothing else here to consult.
        #
        # The gate reads the STATISTICAL probability and skips the question for
        # every predictor, rather than letting each predictor filter its own.
        # Two predictors that answered different sets of questions could not be
        # compared with each other at all -- the LLM's record would be over the
        # questions the LLM found easy, which is the one thing a head-to-head
        # must not be.
        #
        # `stated_side` reports confidence in the side claimed, so this reads
        # the same on both halves of a market: a 28% chance of a home run is a
        # 72% claim that there will not be one, and it qualifies.
        # THE RUNG LOG (ruling, 2026-08-31). What the model would claim at
        # every rung the ladder OFFERS, recorded whether or not the question
        # gets asked -- because the thing that separates "the floor working"
        # from "the ladder mis-set" is the shape of the claims that failed, and
        # a count cannot show a shape. Computed before the floor is applied so
        # the below-floor cases are exactly the ones it keeps.
        rung_claims = []
        if q.market_type == "prop":
            rung_claims = rungs.claims_across_the_ladder(
                conn, adapter, fits, q, chosen_stat=stat, baseline=baseline)

        if q.market_type == "prop":
            _side, claimed = baseline.stated_side(
                stat["prob_yes"], q.yes_label, q.no_label
            )
            # THE FLOOR RUNS ON THE NUMBER THE READER WOULD SEE. Once a
            # category has an active correction, its raw claims are mostly
            # lower after adjustment, so questions that used to clear 70% stop
            # clearing it and the slate shrinks. That is the point: the floor
            # exists to refuse claims the model is not confident enough to
            # make, and "confident enough" has to mean the earned number or the
            # floor is being applied to a figure nobody is shown.
            claimed, _v = correction.shown_claim(
                conn, sport=q.sport, market_type=q.market_type,
                forecaster="statistical", claim=claimed)
            if claimed < config.PROPS_MIN_CLAIM:
                run.below_floor += 1
                run.rungs_logged += rungs.record(
                    conn, q, rung_claims, season=season, week=week,
                    rolling_mean=getattr(ctx, "rolling_mean", None),
                    written=False)
                continue

        written = write_prediction(
            conn,
            q,
            final=final,
            predictor="statistical",
            prob_yes=stat["prob_yes"],
            fv=fv,
            reasoning=baseline.explain(stat["contributions"], absent=stat["absent"]),
            extra={
                "contributions": stat["contributions"],
                "log_odds": round(stat["log_odds"], 6),
                "absent_detail": stat["absent_detail"],
            },
            degraded=llm_off if use_llm else None,
        )
        if written:
            run.written.append(written)
        run.rungs_logged += rungs.record(
            conn, q, rung_claims, season=season, week=week,
            rolling_mean=getattr(ctx, "rolling_mean", None),
            written=bool(written))

        # --- the LLM path ---------------------------------------------------
        if not use_llm or llm_off:
            continue
        try:
            result = llm.reason(
                conn,
                question=q.claim,
                factor_rows=compute.describe(fv),
                notes=fv.notes,
                game_id=q.game_id,
                client=llm_client,
            )
        except llm.LLMUnavailable as exc:
            # One failure of a kind that will not fix itself stops the whole
            # slate rather than burning the budget failing many more times.
            llm_off = f"llm_unavailable:{exc.reason}"
            run.degradations[llm_off] = run.degradations.get(llm_off, 0) + 1
            if progress:
                progress(f"  LLM pass off for this run: {exc}")
            continue

        llm_written = write_prediction(
            conn,
            q,
            final=final,
            predictor="llm",
            prob_yes=result.probability,
            fv=fv,
            reasoning=result.reasoning,
            extra={
                "llm_model": result.model,
                "llm_usd": round(result.usd, 6),
                "llm_repaired": result.repaired,
            },
        )
        if llm_written:
            run.written.append(llm_written)

    if llm_off:
        run.skipped.append(
            f"LLM reasoning pass unavailable for this run ({llm_off}); "
            "statistical predictions stand alone"
        )
    if run.below_floor:
        run.skipped.append(
            f"{run.below_floor} below confidence floor: the model formed an "
            f"answer and was less than {round(config.PROPS_MIN_CLAIM * 100)}% "
            "sure of it, so the question was not asked. A slate under its cap "
            "for this reason is the floor working, not a failure to find "
            "questions."
        )
    return run


def predict_week(
    conn: sqlite3.Connection, season: int, week: int, **kwargs
) -> BlindRun:
    """NFL-shaped call kept for the existing callers and tests."""
    return predict_slate(conn, "nfl", season, week, **kwargs)


def _days_between(now: str, later: str) -> int | None:
    try:
        return (date.fromisoformat(later[:10]) - date.fromisoformat(now[:10])).days
    except ValueError:
        return None
