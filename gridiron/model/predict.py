"""The blind prediction core — steps 1 to 4 of the G3 loop.

  1. select the questions for the week
  2. compute the factor vector from stored data only
  3. produce probabilities: the statistical baseline, and the LLM pass
  4. WRITE THE PREDICTION ROWS

Step 5 — fetching the line — is deliberately not here and cannot be. This
module, and everything it imports, has no path to `gridiron.market`; the guard
test walks the import closure and fails by name if one appears. The runner in
`gridiron.run` calls this inside a `blind_window()`, which additionally refuses
to let the market package be imported at all while these rows are being formed.

Nothing in this file has ever seen a spread, and there is nowhere for one to
arrive.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from .. import config
from ..db import utcnow
from ..factors import compute, context, registry
from . import baseline, llm, questions


@dataclass
class Question:
    """One thing we are about to be wrong or right about."""

    game_id: str
    market_type: str
    subject: str
    line_asked: float
    claim: str                       # the sentence being assigned a probability
    yes_label: str
    no_label: str
    player_id: str | None = None
    stat: str | None = None


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
    season: int
    week: int
    written: list[WrittenPrediction] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    degradations: dict[str, int] = field(default_factory=dict)

    @property
    def prediction_ids(self) -> list[int]:
        return [w.prediction_id for w in self.written]


# ---------------------------------------------------------------------------
# step 1 — the questions
# ---------------------------------------------------------------------------

def week_questions(
    conn: sqlite3.Connection, season: int, week: int, *, include_props: bool = True
) -> list[Question]:
    from ..data import repo

    out: list[Question] = []
    for game in repo.games_for_week(conn, season, week):
        line = questions.spread_rung(game["id"])
        sign = "+" if line > 0 else ""
        out.append(
            Question(
                game_id=game["id"],
                market_type="spread",
                subject=game["home"],
                line_asked=line,
                claim=(
                    f"{game['home']} (home) covers {sign}{line:g} against "
                    f"{game['away']}"
                ),
                yes_label="cover",
                no_label="not_cover",
            )
        )
        if not include_props:
            continue
        for pick in questions.select_props(conn, game):
            out.append(
                Question(
                    game_id=game["id"],
                    market_type="prop",
                    subject=f"{pick['player_name']} {pick['stat']}",
                    line_asked=pick["line_asked"],
                    claim=(
                        f"{pick['player_name']} ({pick['position']}, {pick['team']}) "
                        f"records more than {pick['line_asked']:g} "
                        f"{pick['stat'].replace('_', ' ')}"
                    ),
                    yes_label="over",
                    no_label="under",
                    player_id=pick["player_id"],
                    stat=pick["stat"],
                )
            )
    return out


# ---------------------------------------------------------------------------
# step 2 — the factor vector
# ---------------------------------------------------------------------------

def question_features(
    conn: sqlite3.Connection, q: Question, cache: context.WeekCache | None = None
) -> tuple[compute.FeatureVector, context.GameContext]:
    if q.market_type == "spread":
        ctx = context.build_game_context(conn, q.game_id, cache, line_asked=q.line_asked)
    else:
        ctx = context.build_prop_context(
            conn, q.game_id, q.player_id, q.stat, q.line_asked, cache
        )
    return compute.feature_vector(ctx, q.market_type), ctx


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
    the week is a no-op, never a second opinion."""
    side, confidence = baseline.stated_side(prob_yes, q.yes_label, q.no_label)
    payload = fv.to_json_dict()
    payload["prob_yes"] = round(prob_yes, 6)
    # What was asked, in resolvable terms. The resolver needs the player id and
    # stat by name later; `subject` is for humans and must not be parsed back.
    payload["question"] = {
        "claim": q.claim,
        "player_id": q.player_id,
        "stat": q.stat,
        "yes_label": q.yes_label,
        "no_label": q.no_label,
    }
    if extra:
        payload.update(extra)

    cur = conn.execute(
        "INSERT OR IGNORE INTO predictions (created_utc, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning, degraded) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            utcnow(),
            q.game_id,
            q.market_type,
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
    if cur.lastrowid is None or cur.rowcount == 0:
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

def predict_week(
    conn: sqlite3.Connection,
    season: int,
    week: int,
    *,
    include_props: bool = True,
    use_llm: bool = True,
    llm_client=None,
    progress=None,
) -> BlindRun:
    """Steps 1-4, for one week. No line is fetched, read or reachable."""
    run = BlindRun(season=season, week=week)
    cache = context.WeekCache()

    fits = {}
    for market_type in ("spread", "prop") if include_props else ("spread",):
        try:
            fits[market_type] = baseline.load_fit(conn, market_type)
        except baseline.NotTrained as exc:
            run.skipped.append(str(exc))

    llm_off: str | None = None

    for q in week_questions(conn, season, week, include_props=include_props):
        if q.market_type not in fits:
            run.skipped.append(f"{q.game_id} {q.market_type}: no fitted model")
            continue
        try:
            fv, ctx = question_features(conn, q, cache)
        except KeyError as exc:
            run.skipped.append(f"{q.game_id} {q.subject}: {exc}")
            continue

        if progress:
            progress(f"{q.game_id} {q.market_type} {q.subject}")

        # --- the statistical path ------------------------------------------
        stat = baseline.predict(fits[q.market_type], fv)
        stat_degraded = llm_off if use_llm else None
        written = write_prediction(
            conn,
            q,
            predictor="statistical",
            prob_yes=stat["prob_yes"],
            fv=fv,
            reasoning=baseline.explain(stat["contributions"]),
            extra={"contributions": stat["contributions"], "log_odds": round(stat["log_odds"], 6)},
            degraded=stat_degraded,
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
            # slate rather than burning the budget failing 48 more times.
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
        # The statistical rows written before the LLM failed do not carry the
        # tag; record the run-level fact so the count is never misread as "the
        # LLM agreed with everything it skipped".
        run.skipped.append(
            f"LLM reasoning pass unavailable for this run ({llm_off}); "
            "statistical predictions stand alone"
        )
    return run
