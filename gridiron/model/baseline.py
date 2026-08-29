"""The statistical baseline: fit the declared factors, predict, explain.

Training data is built the same way predictions are — same question rule, same
cutoff, same factor code — so what the model learned on and what it is asked at
runtime are the same shape of thing.

Nothing here imports the market package, and nothing here can. Training labels
come from final scores in `games` and stat lines in `player_week_stats`; the
line being asked about is our own (`questions.py`).
"""

from __future__ import annotations

import json
import sqlite3

from .. import config
from ..db import utcnow
from ..factors import compute, context, registry
from . import logistic, questions


class NotTrained(RuntimeError):
    """No fitted model exists for this market type and factor set."""


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------

def spread_training_set(
    conn: sqlite3.Connection,
    seasons: tuple[int, ...],
    *,
    through_season: int | None = None,
    through_week: int | None = None,
    progress=None,
) -> tuple[list[dict[str, float]], list[int], list[str]]:
    """One row per completed game: the factor vector, and whether home covered.

    `through_*` is the walk-forward cutoff. Passing it makes the fit strictly
    out-of-sample for anything after that point, which is what the backtest
    uses; leaving it off trains on everything available.
    """
    placeholders = ",".join("?" for _ in seasons)
    sql = (
        f"SELECT id, season, week, home_score, away_score FROM games"
        f" WHERE status = 'final' AND game_type = 'REG' AND season IN ({placeholders})"
    )
    params: list = list(seasons)
    if through_season is not None:
        sql += " AND (season < ? OR (season = ? AND week <= ?))"
        params += [through_season, through_season, through_week or 99]
    sql += " ORDER BY season, week, id"

    games = conn.execute(sql, params).fetchall()
    cache = context.WeekCache()
    rows: list[dict[str, float]] = []
    labels: list[int] = []

    for i, g in enumerate(games):
        if progress and i % 250 == 0:
            progress(f"features {i}/{len(games)}")
        line = questions.spread_line_asked(g["id"])
        ctx = context.build_game_context(conn, g["id"], cache, line_asked=line)
        # Weeks 1-2 have no in-season sample and a prior-season fallback that is
        # a different kind of estimate; they are still included, because
        # excluding them would train a model that never sees the situation it
        # will actually be asked about in September.
        fv = compute.feature_vector(ctx, "spread")
        rows.append(fv.values)
        labels.append(questions.spread_outcome(g["home_score"], g["away_score"], line))

    names = [f.name for f in registry.active_factors("spread")]
    return rows, labels, names


def prop_training_set(
    conn: sqlite3.Connection,
    seasons: tuple[int, ...],
    *,
    through_season: int | None = None,
    through_week: int | None = None,
    progress=None,
) -> tuple[list[dict[str, float]], list[int], list[str]]:
    """One row per (completed game, selected player, stat), labelled over/under
    the line the same rule would have asked."""
    placeholders = ",".join("?" for _ in seasons)
    sql = (
        f"SELECT id, season, week, home, away FROM games"
        f" WHERE status = 'final' AND game_type = 'REG' AND season IN ({placeholders})"
    )
    params: list = list(seasons)
    if through_season is not None:
        sql += " AND (season < ? OR (season = ? AND week <= ?))"
        params += [through_season, through_season, through_week or 99]
    sql += " ORDER BY season, week, id"

    games = conn.execute(sql, params).fetchall()
    cache = context.WeekCache()
    rows: list[dict[str, float]] = []
    labels: list[int] = []

    for i, g in enumerate(games):
        if progress and i % 250 == 0:
            progress(f"prop features {i}/{len(games)}")
        for pick in questions.select_props(conn, g):
            actual = conn.execute(
                f"SELECT {pick['stat']} AS v FROM player_week_stats"
                " WHERE season = ? AND week = ? AND player_id = ?",
                (g["season"], g["week"], pick["player_id"]),
            ).fetchone()
            # A player with no box-score row did not appear and therefore
            # recorded zero. Training counts that as an under, exactly as the
            # resolver will: the question asked whether he would exceed a
            # number, and he did not. Dropping these rows instead would train a
            # model that never sees the games its subject misses.
            value = 0.0 if actual is None or actual["v"] is None else float(actual["v"])
            try:
                ctx = context.build_prop_context(
                    conn, g["id"], pick["player_id"], pick["stat"], pick["line_asked"], cache
                )
            except KeyError:
                continue
            fv = compute.feature_vector(ctx, "prop")
            rows.append(fv.values)
            labels.append(questions.prop_outcome(value, pick["line_asked"]))

    names = [f.name for f in registry.active_factors("prop")]
    return rows, labels, names


def train(
    conn: sqlite3.Connection,
    market_type: str,
    seasons: tuple[int, ...] = config.DEFAULT_LOAD_SEASONS,
    *,
    through_season: int | None = None,
    through_week: int | None = None,
    l2: float = 2.0,
    note: str | None = None,
    progress=None,
) -> logistic.Fit:
    builder = spread_training_set if market_type == "spread" else prop_training_set
    rows, labels, names = builder(
        conn,
        seasons,
        through_season=through_season,
        through_week=through_week,
        progress=progress,
    )
    if len(rows) < 50:
        raise NotTrained(
            f"only {len(rows)} training rows for {market_type}; refusing to fit a "
            "model on a sample that small"
        )
    fitted = logistic.fit(rows, labels, names, l2=l2)

    through = (
        f"season:{through_season} week:{through_week}"
        if through_season is not None
        else f"seasons:{min(seasons)}-{max(seasons)}"
    )
    conn.execute(
        "INSERT INTO model_fits (fitted_utc, factor_set_version, market_type,"
        " train_through, n_train, coefficients_json, note) VALUES (?,?,?,?,?,?,?)",
        (
            utcnow(),
            config.FACTOR_SET_VERSION,
            market_type,
            through,
            fitted.n,
            json.dumps(fitted.to_json()),
            note,
        ),
    )
    conn.commit()
    return fitted


def load_fit(
    conn: sqlite3.Connection,
    market_type: str,
    factor_set_version: str | None = None,
) -> logistic.Fit:
    row = conn.execute(
        "SELECT coefficients_json FROM model_fits"
        " WHERE market_type = ? AND factor_set_version = ?"
        " ORDER BY id DESC LIMIT 1",
        (market_type, factor_set_version or config.FACTOR_SET_VERSION),
    ).fetchone()
    if row is None:
        raise NotTrained(
            f"no fitted {market_type} model for factor set "
            f"{factor_set_version or config.FACTOR_SET_VERSION}; run `train` first"
        )
    return logistic.Fit.from_json(json.loads(row["coefficients_json"]))


# ---------------------------------------------------------------------------
# prediction
# ---------------------------------------------------------------------------

def predict(fit: logistic.Fit, fv: compute.FeatureVector) -> dict:
    """Probability plus the decomposition that explains it.

    `prob_yes` is P(home covers) for a spread, P(over) for a prop. The caller
    turns that into a stated side and a stated confidence.
    """
    prob = fit.predict(fv.values)
    contributions = fit.contributions(fv.values)
    return {
        "prob_yes": prob,
        "log_odds": fit.log_odds(fv.values),
        "intercept": fit.intercept,
        "contributions": [
            {
                "factor": name,
                "value": round(value, 4),
                "coefficient": round(dict(zip(fit.names, fit.coefficients))[name], 4),
                "contribution": round(contribution, 4),
                "missing": name in fv.missing,
            }
            for name, value, contribution in contributions
        ],
    }


def stated_side(prob_yes: float, yes_label: str, no_label: str) -> tuple[str, float]:
    """Turn P(yes) into the side the model would state and its confidence in it.

    Confidence is always at least 0.5 by construction, which is what makes the
    50-60 / 60-70 / 70-80 / 80+ calibration buckets meaningful: they are buckets
    of *stated confidence in a claim*, not of P(home).
    """
    if prob_yes >= 0.5:
        return yes_label, prob_yes
    return no_label, 1.0 - prob_yes


def explain(contributions: list[dict], limit: int = 4) -> str:
    """A plain-language reading of the largest contributions, used when the LLM
    pass is unavailable so a statistical-only prediction still has a reasoning
    field rather than an empty string."""
    parts = []
    for c in contributions[:limit]:
        if abs(c["contribution"]) < 0.01:
            continue
        direction = "toward" if c["contribution"] > 0 else "against"
        tag = " (value unavailable, defaulted)" if c["missing"] else ""
        parts.append(
            f"{c['factor']} = {c['value']:g} pushes {direction} the yes side by "
            f"{abs(c['contribution']):.2f} in log-odds{tag}"
        )
    if not parts:
        return "No factor moved this materially; the estimate sits near the base rate."
    return "Statistical decomposition: " + "; ".join(parts) + "."
