"""The blind prediction core — steps 1 to 4 of the loop, for any sport.

  1. select the questions for the slate (the sport's adapter decides how)
  2. compute the factor vector from stored data only
  3. produce probabilities: the statistical baseline, and the LLM pass
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

from .. import config, sports
from ..db import utcnow
from ..factors import compute, context
from . import baseline, llm
from .question import Question

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
) -> WrittenPrediction | None:
    """Insert one prediction row. Returns None if this exact question has
    already been answered by this predictor under this factor set — a rerun of
    the slate is a no-op, never a second opinion."""
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
        " AND subject = ? AND predictor = ? AND factor_set_version = ?",
        (q.game_id, q.market_type, q.subject, predictor, config.FACTOR_SET_VERSION),
    ).fetchone()
    if already:
        return None

    cur = conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " prop_type, subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning, degraded)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            utcnow(),
            q.sport,
            q.game_id,
            q.market_type,
            q.stat if q.market_type == "prop" else None,
            q.subject,
            q.line_asked,
            round(min(max(confidence, 0.001), 0.999), 6),
            side,
            predictor,
            config.FACTOR_SET_VERSION,
            json.dumps(payload),
            reasoning,
            degraded,
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
) -> BlindRun:
    """Steps 1-4, for one slate of one sport. No line is fetched or reachable."""
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
        written = write_prediction(
            conn,
            q,
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
    return run


def predict_week(
    conn: sqlite3.Connection, season: int, week: int, **kwargs
) -> BlindRun:
    """NFL-shaped call kept for the existing callers and tests."""
    return predict_slate(conn, "nfl", season, week, **kwargs)
