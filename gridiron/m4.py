"""M4 v1: THE MODEL'S CHANCE AT ANY LINE, READ FROM ITS OWN PROJECTION
(GRIDIRON_ENTRY_CHECK step 2; the brief of 2026-09-30, docs/briefs/
2026-09-30-entry-check.md, with ruling D of 2026-10-05, docs/briefs/
2026-10-05-rulings.md; built 2026-10-07).

Ruling D, whole on this: "Step 2 needs the model's chance at any line: a first
version of M4, P(stat over x) from the model's projection and a per-stat
spread fitted on settled history. Written inactive; shown as 'not yet proven'
until its record clears 100 graded legs." The brief's step 2: "each leg's
model probability at the typed line if the model forecasts that player and
stat; at a discounted line only if the model can state a probability at any
line, otherwise 'can't price this discount' ... The model only flags; it never
raises a verdict."

OUTSIDE THE PREDICTION CLOSURE (LAW 1, above all). Nothing here is read by
anything that forecasts: `audit.check_prediction_closure` refuses
`gridiron.m4` and its fit table (`M4_MODULE`, `M4_IDENTIFIERS`) anywhere on
the prediction path, BY NAME. The precedent is the at-the-line claim writer:
the model's frozen numbers, read at a number it never saw. M4 reads a
forecast the model wrote before any line (its stored projection), the record's
settled stats, and its own fits; a line the operator types reaches this
module and goes no further.

THE READINGS (recorded in docs/REPAIR_STATE.md, "Rulings taken in your
absence", 2026-10-07, the entry check's step 2):

  (a) THE PROJECTION is a number the model STORED with its forecast before any
      line: `expected_count`, the counting stats' rate (NFL receptions and
      passing touchdowns). Where it stored none -- the three yardage stats,
      answered as yes-or-no questions at the model's own line -- M4 states
      nothing, and no projection is implied from the model's chance at its own
      question (operator question 43 asks whether one may be; default no).
  (b) THE DECLARED FORM (`FORM`, declared `FORM_DECLARED`): the stat is a
      count about the projection, its variance the fitted spread times the
      projection -- a negative binomial where the spread is above one, a
      Poisson where it is one or less. THE RECORD'S OWN FORM FOR A COUNT
      (`model.counts`, measured 2026-09-03: counts modelled as rates, a
      negative binomial with the measured variance over the mean where a
      Poisson would understate the spread), read through the record's own
      arithmetic (`counts.p_over`, whose rule a spread of one or less is a
      Poisson -- "UNDER-dispersed ... a Poisson is the honest form", the
      record's note on batter strikeouts). M4 changes one thing: the spread
      is FITTED on the stat's settled history against the model's own
      projections (`spread_of`), where the record's dispersion was measured
      on raw counts across every player. No factor is added or discovered
      (LAW 2): the spread is the one parameter of a declared form, dated.
      THE ARITHMETIC: the mean, over the stat's settled standing forecasts
      that carry a projection -- one per player and game, the actual read as
      the resolver reads it -- of (the stat he recorded less the projection)
      squared, over the projection (the Pearson estimate of a variance that is
      the spread times the mean).
  (c) WRITTEN INACTIVE: a fit is a dated, append-only row of
      `prop_spread_fits`, and nothing activates one (no activation row is
      written; no table holds one). M4 reads the latest fit of a stat to state
      a chance, and every chance is drawn "not yet proven" with its count of
      graded legs -- 0 of 100: the record of graded legs is step 3's (a
      checked entry kept and its legs graded), so it is 0 here.
  (d) IT NEVER MAKES A PICK: no chance it states is a pick, a badge, an
      outline or a verdict (B.5's spirit: no pick from a model whose record
      has not cleared its gate).

THE ONE WRITE is a fit (`record_fit`), made only by the fitting run
(`refit`, run by `tools/fit_prop_spreads.py`: on a test world or a scratch
copy, and on the operator's record only with `--live`, after the release
that carries the table).
"""

from __future__ import annotations

import json
import math
import sqlite3

from . import calibration, config, db
# THE RECORD'S OWN COUNTING ARITHMETIC, by its module's name (the entry
# check's reach scan allows `gridiron.model.counts` and never `gridiron.model`
# whole, whose `llm` calls another machine).
from .model.counts import is_count_market, p_over

#: SCOPE v1, the entry check's: NFL player props.
SPORT = "nfl"

#: WHOSE PROJECTION: the statistical model's -- the forecaster that writes a
#: counting stat's rate with its forecast. The reasoning pass writes none.
FORECASTER = "statistical"

#: THE DECLARED FORM, ONCE, DATED (reading (b), 2026-10-07): a count about the
#: projection whose variance is the spread times the projection -- a negative
#: binomial where the spread is above one, a Poisson where it is one or less
#: (`counts.p_over`'s own rule). Stored on every fit, so a later form is a
#: new family of rows, never a reading of these.
FORM = "count_about_the_projection"
FORM_DECLARED = "2026-10-07T00:00:00Z"

#: THE TABLE ITS FITS ARE KEPT IN (schema.sql), named in full in each
#: statement below.
TABLE = "prop_spread_fits"

#: "NOT YET PROVEN UNTIL ITS RECORD CLEARS 100 GRADED LEGS" (ruling D): LAW 4's
#: hundred, the gate every record here reads.
PROVEN_AT = config.MIN_SAMPLE_FOR_EDGE_CLAIM

#: HOW A FIT'S SPREAD IS WORKED OUT, IN WORDS, stored on every fit.
METHOD = ("the mean, over the stat's settled standing forecasts carrying a "
          "projection, one per player and game, of the stat he recorded less "
          "the projection, squared, over the projection")

#: A SPREAD THE TABLE HOLDS: above nothing and under a hundred (the schema's
#: own bounds); a fit outside them is not written, and the run says why.
SPREAD_FLOOR = 0.0
SPREAD_CEILING = 100.0


def stats_it_can_fit(sport: str = SPORT) -> tuple[str, ...]:
    """The sport's prop stats whose forecasts store a projection: its counting
    stats (`counts.COUNT_MARKETS`, declared, never sniffed). For the NFL,
    receptions and passing touchdowns; never a yardage stat (reading (a)).
    NFL ONLY (scope v1): the settled stats are read from the NFL's own game
    stats (`player_week_stats`), so another sport has none here."""
    if sport != SPORT:
        return ()
    return tuple(s for s in config.SPORT_PROP_MARKETS.get(sport, ())
                 if is_count_market(s))


def graded_legs(conn: sqlite3.Connection | None = None, *, sport: str = SPORT) -> int:
    """HOW MANY LEGS M4 HAS BEEN GRADED ON: none. A leg is graded once a
    checked entry is kept and the leg settles -- step 3 of the brief ("Step
    3, the record: a checked entry can be marked 'taken' and is stored
    append-only ... Legs graded from settled stats"), not built -- so no leg
    is stored or graded anywhere and the count is 0 (reading (c)). Step 3
    replaces this with its count; until it clears `PROVEN_AT`, every chance
    M4 states is drawn "not yet proven"."""
    return 0


# ---------------------------------------------------------------------------
# the chance at a line
# ---------------------------------------------------------------------------

def projection_of(forecast) -> float | None:
    """The projection the model stored with its forecast (`expected_count`),
    or None where it stored none -- a yardage stat, answered yes or no at its
    own line, or a row written before the rate model."""
    if not forecast:
        return None
    try:
        raw = forecast["factors_json"]
    except (KeyError, IndexError):
        return None
    try:
        rate = (json.loads(raw or "{}") or {}).get("expected_count")
    except ValueError:
        return None
    try:
        rate = None if rate is None else float(rate)
    except (TypeError, ValueError):
        return None
    return rate if rate is not None and rate > 0.0 and math.isfinite(rate) else None


def chance_over(projection: float, line: float, spread: float) -> float:
    """P(the stat is over `line`): strictly over -- "over 4.5" is 5 or more,
    "over 5" is 6 or more -- in the declared form, through the record's own
    arithmetic (`counts.p_over`)."""
    if spread > 1.0:
        return p_over(float(projection), float(line), form="negative_binomial",
                      dispersion=float(spread))
    return p_over(float(projection), float(line), form="poisson")


def chance_under(projection: float, line: float, spread: float) -> float:
    """P(the stat is under `line`): strictly under -- "under 4.5" is 4 or
    fewer, "under 5" is 4 or fewer -- one less the chance of `ceil(line)` or
    more."""
    need = math.ceil(float(line))
    if need <= 0:
        return 0.0
    return 1.0 - chance_over(projection, need - 1, spread)


def chance_on_side(projection: float, line: float, side: str, spread: float) -> float:
    """The chance a leg wins on the side typed. A WHOLE-NUMBER LINE can be
    landed on exactly, which is neither side: it is counted here as not won,
    the stricter reading (an app's rule for it is the operator's to read)."""
    if side == "over":
        return chance_over(projection, line, spread)
    if side == "under":
        return chance_under(projection, line, spread)
    raise ValueError(f"a leg's side is over or under, not {side!r}")


# ---------------------------------------------------------------------------
# the forecast behind a leg, and the fit it is read with
# ---------------------------------------------------------------------------

def has_the_table(conn: sqlite3.Connection) -> bool:
    """A record no release carrying the table has opened yet, read through a
    read-only door, holds none: then nothing is fitted
    (`entry_check._has_the_table`'s precedent)."""
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'"
                        " AND name = ?", (TABLE,)).fetchone() is not None


def latest_fit(conn: sqlite3.Connection, stat: str, *, sport: str = SPORT) -> dict | None:
    """The latest fit of one stat in the declared form, or None where none has
    been written. INACTIVE, as every fit is (reading (c)): what M4 reads to
    state a chance drawn "not yet proven", never one in force."""
    if not has_the_table(conn):
        return None
    row = conn.execute(
        "SELECT * FROM prop_spread_fits WHERE sport = ? AND stat = ? AND form = ?"
        " ORDER BY id DESC LIMIT 1", (sport, stat, FORM)).fetchone()
    return None if row is None else dict(row)


def standing_forecast(conn: sqlite3.Connection, *, game_id: str, stat: str,
                      player_id: str, sport: str = SPORT) -> dict | None:
    """THE MODEL'S FORECAST FOR ONE PLAYER AND ONE STAT IN ONE GAME: the
    statistical model's standing row, through the one clause
    (`calibration.standing_row_clause`: a final pass written before the start
    first, else the latest written before it, a withdrawn row never), never a
    rule of M4's own. Two rungs of one player's game are two questions with
    one projection (one pass wrote both); the later-numbered stands here.

    THE PLAYER IS READ ONLY FROM A ROW THAT IS JSON (its prover, 2026-10-07):
    the schema holds no rule on the column's form, and a bare `json_extract`
    raises "malformed JSON" on any row of the game and stat that is not --
    which took the whole entry check, the coin flips' verdict with it, and
    the Props tile's "at your line" row with the slate. `json_valid` first,
    the prompt record's precedent (`model.prompt_record`); such a row is no
    forecast of anyone here."""
    row = conn.execute(
        "SELECT p.id, p.game_id, p.prop_type, p.subject, p.line_asked, p.model_prob,"
        "       p.model_side, p.pass_kind, p.created_utc, p.factors_json"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND p.game_id = ? AND p.market_type = 'prop'"
        "   AND p.prop_type = ? AND p.predictor = ?"
        "   AND (CASE WHEN json_valid(p.factors_json)"
        "             THEN json_extract(p.factors_json, '$.question.player_id') END) = ?"
        f"{calibration.standing_row_clause(False)}"
        " ORDER BY p.id DESC LIMIT 1",
        (sport, game_id, stat, FORECASTER, player_id)).fetchone()
    return None if row is None else dict(row)


def reading(conn: sqlite3.Connection, *, game_id: str, player_id: str, stat: str,
            line: float, side: str, original_line: float | None = None,
            sport: str = SPORT) -> dict:
    """WHAT M4 SAYS OF ONE LEG: its chance at the line typed, on the side
    typed, and -- a discounted leg -- at the line before the discount; or why
    it says nothing (`state`):

      "priced"         a forecast with a projection, and a fit of the stat
      "no_forecast"    the model forecast no such player and stat in the game
      "no_projection"  its forecast stores no projection (reading (a))
      "no_fit"         no spread has been fitted for the stat yet

    A discounted leg is priced at its line before the discount ONLY where M4
    can state a chance at any line -- here, wherever it states one at all --
    and never otherwise (the brief: "otherwise 'can't price this discount'")."""
    out = {"state": None, "chance": None, "chance_before": None, "projection": None,
           "spread": None, "fit_id": None, "fit_n": None, "forecast_id": None}
    forecast = standing_forecast(conn, game_id=game_id, stat=stat, player_id=player_id,
                                 sport=sport)
    if forecast is None:
        out["state"] = "no_forecast"
        return out
    out["forecast_id"] = forecast["id"]
    projection = projection_of(forecast)
    if projection is None:
        out["state"] = "no_projection"
        return out
    out["projection"] = projection
    fit = latest_fit(conn, stat, sport=sport)
    if fit is None:
        out["state"] = "no_fit"
        return out
    spread = float(fit["spread"])
    out.update(state="priced", spread=spread, fit_id=fit["id"], fit_n=fit["n"],
               chance=chance_on_side(projection, line, side, spread))
    if original_line is not None:
        out["chance_before"] = chance_on_side(projection, original_line, side, spread)
    return out


def record_of(conn: sqlite3.Connection, stat: str, *, sport: str = SPORT) -> dict:
    """THE MODEL'S RECORD FOR THE STAT, the blind record's own (the brief:
    "with the model's record for that stat in plain words"; LAW 4): the
    statistical model's settled standing questions of this prop type at its
    own lines (`calibration.resolved`, the curve's own rows), how many, and
    how many it got right. Its record, never M4's (which is 0 graded legs)."""
    items = calibration.resolved(conn, sport=sport, market_type="prop", prop_type=stat,
                                 predictor=FORECASTER)
    return {"n": len(items), "right": sum(int(r.outcome) for r in items),
            "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM}


# ---------------------------------------------------------------------------
# the fit (the one write; reading (b))
# ---------------------------------------------------------------------------

def _actual(conn: sqlite3.Connection, stat: str, season, week, player_id: str) -> float | None:
    """The stat the player recorded in the game, read as the resolver reads it
    (`resolve._prop_actual`: the stat's column of `player_week_stats` for the
    forecast's own player, season and week), or None where it is not there.
    The column is one of the stats a fit is made for, never a word typed."""
    if stat not in stats_it_can_fit(SPORT):
        return None
    row = conn.execute(
        f"SELECT {stat} AS v FROM player_week_stats"
        " WHERE season = ? AND week = ? AND player_id = ?",
        (season, week, player_id)).fetchone()
    if row is None or row["v"] is None:
        return None
    return float(row["v"])


def settled_rows(conn: sqlite3.Connection, stat: str, *, sport: str = SPORT) -> list[dict]:
    """WHAT A FIT IS WORKED FROM: the stat's settled standing forecasts of the
    statistical model (`calibration.resolved`, the blind record's own rows --
    one per question, a withdrawn one never) that carry a projection, ONE PER
    PLAYER AND GAME (two rungs of one player's game share one projection and
    one actual; the later-numbered is kept), each with the stat he recorded.
    Ordered by the forecast's number."""
    kept: dict[tuple, dict] = {}
    items = calibration.resolved(conn, sport=sport, market_type="prop", prop_type=stat,
                                 predictor=FORECASTER, with_factors=True)
    for item in sorted(items, key=lambda r: r.id):
        try:
            payload = json.loads(item.factors_json or "{}") or {}
        except ValueError:
            continue
        projection = projection_of({"factors_json": item.factors_json})
        question = payload.get("question") or {}
        player_id = question.get("player_id")
        if projection is None or not player_id or question.get("stat") != stat:
            continue
        actual = _actual(conn, stat, item.season, item.week, player_id)
        if actual is None:
            continue
        kept[(item.game_id, player_id)] = {"forecast_id": item.id,
                                           "projection": projection, "actual": actual}
    return sorted(kept.values(), key=lambda r: r["forecast_id"])


def spread_of(rows: list[dict]) -> float | None:
    """THE SPREAD, BY THE ARITHMETIC DECLARED (reading (b)): the mean of
    (actual - projection)^2 / projection over the rows -- the Pearson estimate
    of a variance that is the spread times the mean. None with no rows."""
    if not rows:
        return None
    return sum((r["actual"] - r["projection"]) ** 2 / r["projection"]
               for r in rows) / len(rows)


def fit(conn: sqlite3.Connection, stat: str, *, sport: str = SPORT) -> dict:
    """One stat's fit as it would be written, or why none would be."""
    rows = settled_rows(conn, stat, sport=sport)
    spread = spread_of(rows)
    out = {"sport": sport, "stat": stat, "form": FORM, "form_declared": FORM_DECLARED,
           "n": len(rows), "spread": spread, "forecasts": [r["forecast_id"] for r in rows],
           "method": METHOD, "why_not": None}
    if not rows:
        out["why_not"] = ("no settled forecast of this stat carries a projection the "
                          "record can set beside the stat he recorded")
    elif not SPREAD_FLOOR < spread < SPREAD_CEILING:
        out["why_not"] = (f"the spread worked out, {spread!r}, is outside what the "
                          f"table holds (above {SPREAD_FLOOR:g}, under {SPREAD_CEILING:g})")
    return out


def record_fit(conn: sqlite3.Connection, fitted: dict, *, now: str | None = None) -> int | None:
    """WRITE ONE FIT, INACTIVE -- a plain insert (the frozen register: no
    upsert), and only where it differs from the stat's latest (the same
    forecasts and the same spread are not written twice). The one write M4
    makes. Returns the row's number, or None where nothing was written."""
    if fitted.get("why_not") or fitted.get("spread") is None:
        return None
    last = latest_fit(conn, fitted["stat"], sport=fitted["sport"])
    if last is not None and json.loads(last["forecasts"]) == fitted["forecasts"] \
            and abs(float(last["spread"]) - float(fitted["spread"])) < 1e-12:
        return None
    cur = conn.execute(
        "INSERT INTO prop_spread_fits (fitted_utc, sport, stat, form, form_declared,"
        " spread, n, forecasts, method) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now or db.utcnow(), fitted["sport"], fitted["stat"], fitted["form"],
         fitted["form_declared"], float(fitted["spread"]), int(fitted["n"]),
         json.dumps(fitted["forecasts"]), fitted["method"]))
    return int(cur.lastrowid)


def refit(conn: sqlite3.Connection, *, sport: str = SPORT, write: bool = False,
          now: str | None = None) -> list[dict]:
    """THE FITTING RUN: each stat that stores a projection fitted on its settled
    history, and -- with `write` -- each fit that differs from its stat's
    latest written, in one transaction. Never activates anything (reading
    (c)). Returns each stat's fit -- with `write`, the row written
    (`written`) or None where nothing was."""
    report = [fit(conn, stat, sport=sport) for stat in stats_it_can_fit(sport)]
    if not write:
        # DRY: no `written` at all, so nothing reads as "not written again"
        # (the run on the verified copy, 2026-10-07).
        return report
    if not has_the_table(conn):
        raise RuntimeError(
            f"this database holds no {TABLE} table: it has not been opened under the "
            f"schema that carries it (db.init brings it)")
    with conn:
        for got in report:
            got["written"] = record_fit(conn, got, now=now)
    return report
