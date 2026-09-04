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
from ..data import repo
from ..factors import compute, context, registry
from . import logistic, questions


class NotTrained(RuntimeError):
    """No fitted model exists for this market type and factor set."""


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------

class TrainingSetSpansSports(RuntimeError):
    """A training loader selected games from more than one sport (LAW 6)."""


def assert_one_sport(games, sport: str, where: str) -> None:
    """Every game a training loader selected belongs to `sport`. LAW 6.

    THIS IS PLANTED BECAUSE IT HAPPENED. `spread_training_set` had no `sport`
    filter from 9c0bc64 until 2026-09-03, so the NFL spread model trained on
    18,715 games of which 2,639 -- fourteen per cent -- were football. The rest
    were baseball, basketball and college games, each handed the NFL's factor
    vector and asked whether the home side covered an NFL rung.

    NOTHING FAILED, which is the point. The fit converged, the row count looked
    healthy, and a bigger training set reads as a better one. It surfaced only
    as a base rate 0.06 away from where a nearest-margin rung should sit, and
    only because a separate ruling put that number in front of somebody.

    A FILTER IS A CONVENTION; THIS IS A MECHANISM. The query can lose its
    `WHERE sport = ?` again -- the same way it lost it the first time, in a
    commit about something else entirely -- and this will refuse the fit rather
    than quietly train on four sports.

    Rows with no `sport` column are passed over rather than guessed at: a
    loader that does not select the column is not thereby proven wrong, and
    inventing a verdict about it would be its own failure.
    """
    seen = set()
    for game in games:
        try:
            value = game["sport"]
        except (KeyError, IndexError, TypeError):
            return
        if value is not None:
            seen.add(value)
    if not seen:
        return
    if seen != {sport}:
        others = ", ".join(sorted(s for s in seen if s != sport)) or "nothing"
        raise TrainingSetSpansSports(
            f"GRIDIRON LAW 6 VIOLATED: the {sport} training set in {where} "
            f"selected games from {len(seen)} sports -- {', '.join(sorted(seen))}. "
            f"A model trained on {others} and scored as {sport} describes "
            f"neither, and it flatters reliably, because the easy sport "
            f"dilutes the hard one. The loader has lost its sport filter."
        )


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
    # LAW 6, AND IT WAS BROKEN HERE SINCE 9c0bc64 ("s1: multi-sport").
    #
    # This query had no `sport` filter. `games` holds every sport, so the NFL
    # spread model was trained on 18,715 games of which 2,639 -- FOURTEEN PER
    # CENT -- were football. The other 16,076 were baseball, basketball and
    # college games, each handed the NFL's factor vector and asked whether the
    # home side covered an NFL rung.
    #
    # It was invisible because nothing failed: the fit converged, the row
    # count looked healthy, and a bigger training set reads as a better one.
    # What gave it away was the base rate -- 0.4265 where a nearest-margin
    # rung should sit near 0.500, against NBA's 0.4983 on the same rule.
    #
    # LAW 6 exists for exactly this: "a number that mixes NFL spreads with MLB
    # moneylines describes neither, and it flatters reliably, because the easy
    # sport dilutes the hard one."
    sql = (
        f"SELECT id, sport, season, week, home_score, away_score FROM games"
        f" WHERE sport = 'nfl' AND status = 'final' AND game_type = 'REG'"
        f"   AND season IN ({placeholders})"
    )
    params: list = list(seasons)
    if through_season is not None:
        sql += " AND (season < ? OR (season = ? AND week <= ?))"
        params += [through_season, through_season, through_week or 99]
    sql += " ORDER BY season, week, id"

    games = conn.execute(sql, params).fetchall()
    assert_one_sport(games, "nfl", "baseline.spread_training_set")
    cache = context.WeekCache()
    rows: list[dict[str, float]] = []
    labels: list[int] = []

    for i, g in enumerate(games):
        if progress and i % 250 == 0:
            progress(f"features {i}/{len(games)}")
        # THE SAME RULE THE FORWARD PATH USES (R4, 2026-09-03). A training set
        # asked at rotated rungs and a live slate asked at margin-chosen ones
        # would be two different questions sharing a coefficient. The context
        # is built first because the rung now depends on it.
        ctx = context.build_game_context(conn, g["id"], cache)
        expected = questions.expected_margin(ctx.sport, ctx.home_srs, ctx.away_srs)
        try:
            line = questions.spread_rung(g["id"], expected)
        except questions.RungOffTheLadder:
            # THE TRAINING SET SKIPS WHAT THE LIVE SLATE WOULD SKIP. A fit
            # trained on games the forward path refuses would be fitting a
            # population that never reaches the record.
            continue
        ctx.line_asked = line
        # Weeks 1-2 have no in-season sample and a prior-season fallback that is
        # a different kind of estimate; they are still included, because
        # excluding them would train a model that never sees the situation it
        # will actually be asked about in September.
        fv = compute.feature_vector(ctx, "spread")
        rows.append(fv.values)
        labels.append(questions.spread_outcome(g["home_score"], g["away_score"], line))

    names = [f.name for f in registry.active_factors("nfl", "spread")]
    return rows, labels, names


def market_key(sport: str, market: str) -> str:
    """The key one fitted model is stored and looked up under.

    `nfl:spread`, `nfl:prop:receptions`, `mlb:moneyline`, `nba:prop:points`.
    Every market of every sport is fitted separately: a receptions question and
    a passing-yards question are different questions, and a baseball moneyline
    is not either of them. Pooling would let the market with the most rows set
    the coefficients for the market with the fewest (LAW 6 and no-merged-curves
    applied to the model, not just the scorecard).
    """
    from .. import config

    if market in config.SPORT_PROP_MARKETS.get(sport, ()):
        return f"{sport}:prop:{market}"
    return f"{sport}:{market}"


def split_key(key: str) -> tuple[str, str]:
    """`nfl:prop:receptions` -> ('nfl', 'prop:receptions')."""
    sport, _, market_type = key.partition(":")
    return sport, market_type


def prop_market(stat: str) -> str:
    """Kept for NFL-era callers: the market_type a prop model is stored under."""
    return f"prop:{stat}"


def prop_stat(market_type: str) -> str | None:
    return market_type.split(":", 1)[1] if market_type.startswith("prop:") else None


def _weeks(conn: sqlite3.Connection, seasons: tuple[int, ...],
           through_season: int | None, through_week: int | None):
    placeholders = ",".join("?" for _ in seasons)
    sql = (
        f"SELECT DISTINCT season, week FROM games"
        f" WHERE status = 'final' AND game_type = 'REG' AND season IN ({placeholders})"
    )
    params: list = list(seasons)
    if through_season is not None:
        sql += " AND (season < ? OR (season = ? AND week <= ?))"
        params += [through_season, through_season, through_week or 99]
    sql += " ORDER BY season, week"
    return conn.execute(sql, params).fetchall()


def prop_training_set(
    conn: sqlite3.Connection,
    seasons: tuple[int, ...],
    stat: str,
    *,
    through_season: int | None = None,
    through_week: int | None = None,
    progress=None,
    with_counts: bool = False,
) -> tuple:
    """One row per selected prop question of this type, labelled over/under.

    `with_counts=True` returns a fourth list carrying the ACTUAL COUNT and the
    rung for each row. Session C needs both forms fitted on the identical
    selection, and the default shape is unchanged so nothing else notices.

    Selection runs a WEEK at a time using the same capped, liquidity-ordered
    rule the live slate uses, so the model is fitted on the questions it will
    actually be asked rather than on a different, larger set.

    A question whose stat cannot be read is skipped here for the same reason it
    resolves VOID in the live record: a guess would be training data invented
    to fill a gap.
    """
    weeks = _weeks(conn, seasons, through_season, through_week)
    cache = context.WeekCache()
    rows: list[dict[str, float]] = []
    labels: list[int] = []
    extras: list[dict] = []

    for i, w in enumerate(weeks):
        if progress and i % 25 == 0:
            progress(f"{stat} week {i}/{len(weeks)}")
        games = repo.games_for_week(conn, w["season"], w["week"])
        for pick in questions.select_week_props(conn, games):
            if pick["stat"] != stat:
                continue
            actual = conn.execute(
                f"SELECT {stat} AS v FROM player_week_stats"
                " WHERE season = ? AND week = ? AND player_id = ?",
                (w["season"], w["week"], pick["player_id"]),
            ).fetchone()
            if actual is None or actual["v"] is None:
                continue          # would be VOID live; not invented here either
            try:
                ctx = context.build_prop_context(
                    conn, pick["game_id"], pick["player_id"], stat,
                    pick["line_asked"], cache,
                )
            except KeyError:
                continue
            fv = compute.feature_vector(ctx, "prop")
            rows.append(fv.values)
            labels.append(questions.prop_outcome(float(actual["v"]), pick["line_asked"]))
            # THE COUNT AND THE RUNG, kept beside the over/under label so a
            # rate model can be fitted on the same selection the logistic
            # sees. Session C's whole comparison depends on the two forms
            # being asked about identical rows -- fitting them on different
            # selections would compare the selections.
            extras.append({"count": float(actual["v"]),
                           "rung": float(pick["line_asked"]),
                           "season": w["season"], "week": w["week"]})

    names = [f.name for f in registry.active_factors("nfl", "prop")]
    if with_counts:
        return rows, labels, names, extras
    return rows, labels, names


def train(
    conn: sqlite3.Connection,
    market_type: str,
    seasons: tuple[int, ...] = config.DEFAULT_LOAD_SEASONS,
    *,
    sport: str = "nfl",
    through_season: int | None = None,
    through_week: int | None = None,
    l2: float = 2.0,
    note: str | None = None,
    min_rows: int = 50,
    progress=None,
) -> logistic.Fit:
    """Fit one market of one sport.

    `market_type` is the storage form: 'spread', 'moneyline' or 'prop:<stat>'.

    `min_rows` is the floor below which we refuse to fit at all. It is 50 in
    production and is a parameter only so a synthetic test league, which has
    eight clubs rather than thirty-two, can exercise the same code path without
    the real floor being quietly lowered for everyone.
    """
    from .. import sports as sport_registry

    adapter = sport_registry.get(sport)
    stat = prop_stat(market_type)
    market = stat or market_type
    if market not in config.SPORT_MARKETS.get(sport, ()):
        raise ValueError(f"{market!r} is not a declared {sport} market")

    rows, labels, names = adapter.training_set(
        conn, seasons, market,
        through_season=through_season, through_week=through_week,
        progress=progress,
    )

    if len(rows) < min_rows:
        raise NotTrained(
            f"only {len(rows)} training rows for {sport}:{market_type}; refusing "
            f"to fit a model on fewer than {min_rows}"
        )
    fitted = logistic.fit(rows, labels, names, l2=l2)

    through = (
        f"season:{through_season} week:{through_week}"
        if through_season is not None
        else f"seasons:{min(seasons)}-{max(seasons)}"
    )
    conn.execute(
        "INSERT INTO model_fits (sport, fitted_utc, factor_set_version, market_type,"
        " train_through, n_train, coefficients_json, note) VALUES (?,?,?,?,?,?,?,?)",
        (
            sport,
            utcnow(),
            config.factor_set_version(sport, market_type),
            market_type,
            through,
            fitted.n,
            json.dumps(fitted.to_json()),
            note,
        ),
    )
    conn.commit()
    return fitted


def train_all(
    conn: sqlite3.Connection,
    seasons: tuple[int, ...] = config.DEFAULT_LOAD_SEASONS,
    *,
    sport: str = "nfl",
    include_props: bool = True,
    progress=None,
    **kwargs,
) -> dict[str, logistic.Fit]:
    """Fit every declared market of one sport, skipping those with too little."""
    out: dict[str, logistic.Fit] = {}
    for market in config.SPORT_MARKETS.get(sport, ()):
        is_prop = market in config.SPORT_PROP_MARKETS.get(sport, ())
        if is_prop and not include_props:
            continue
        market_type = f"prop:{market}" if is_prop else market
        try:
            out[market_key(sport, market)] = train(
                conn, market_type, seasons, sport=sport, progress=progress, **kwargs
            )
        except (NotTrained, ValueError) as exc:
            if progress:
                progress(f"{sport}:{market_type}: {exc}")
    return out


def load_fit(
    conn: sqlite3.Connection,
    key: str,
    factor_set_version: str | None = None,
) -> logistic.Fit:
    """`key` is a full market key: 'nfl:spread', 'mlb:moneyline', ..."""
    sport, market_type = split_key(key)
    row = conn.execute(
        "SELECT coefficients_json FROM model_fits"
        " WHERE sport = ? AND market_type = ? AND factor_set_version = ?"
        " ORDER BY id DESC LIMIT 1",
        (sport, market_type,
         factor_set_version or config.factor_set_version(sport, market_type)),
    ).fetchone()
    if row is None:
        raise NotTrained(
            f"no fitted {key} model for factor set "
            f"{factor_set_version or config.factor_set_version(sport, market_type)}"
            f"; run `train` first"
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
    coefficients = dict(zip(fit.names, fit.coefficients))
    return {
        "prob_yes": prob,
        "log_odds": fit.log_odds(fv.values),
        "intercept": fit.intercept,
        "contributions": [
            {
                "factor": name,
                "value": round(value, 4),
                "coefficient": round(coefficients[name], 4),
                "contribution": round(contribution, 4),
                "present": True,
            }
            for name, value, contribution in contributions
        ],
        # Named, not silently omitted. A reader is entitled to know what the
        # model could not see; a factor merely absent from the contributions
        # list would be indistinguishable from one that contributed zero.
        "absent": list(fv.absent),
        "absent_detail": {
            name: fv.failed.get(name, "not measurable for this game")
            for name in fv.absent
        },
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


def explain(
    contributions: list[dict], limit: int = 4, absent: list[str] | None = None
) -> str:
    """A plain-language reading of the largest contributions, used when the LLM
    pass is unavailable so a statistical-only prediction still has a reasoning
    field rather than an empty string."""
    parts = []
    for c in contributions[:limit]:
        if abs(c["contribution"]) < 0.01:
            continue
        direction = "toward" if c["contribution"] > 0 else "against"
        parts.append(
            f"{c['factor']} = {c['value']:g} pushes {direction} the yes side by "
            f"{abs(c['contribution']):.2f} in log-odds"
        )
    text = (
        "No factor moved this materially; the estimate sits near the base rate."
        if not parts
        else "Statistical decomposition: " + "; ".join(parts) + "."
    )
    if absent:
        text += (
            " Not measurable for this game, and excluded rather than assumed: "
            + ", ".join(sorted(absent)) + "."
        )
    return text
