"""The activation gate: which fit a market forecasts from, and how it got there.

OPERATOR RULINGS OF 2026-09-24 (ruling 2 of the morning; ruling 3 of the three
decisions). "Training a fit must not make it live. Fits are written inactive.
A fit becomes the active model for a market only by an explicit, dated
activation that records its holdout scores against the incumbent. The predict
path reads only activated fits." And: "ties go to the incumbent. A new fit is
activated only if it beats the incumbent on the holdout with the bootstrap
interval of the difference in log loss excluding zero."

THE CASE THIS EXISTS FOR. Until this module, the model a market forecast from
was simply the newest fit of its declared factor set. Fits 91-94 were trained
on the live record at 05:16Z on 24 September and were live the instant they
were written; the logon catch-up published from them at 05:32Z. Nobody had
activated anything. Nothing could have: there was no such act.

ONE DOOR. Every row in `fit_activations` is written here, and the only reader
the predict path has is `active_fit`, through `baseline.load_fit`. The RULES
live in the schema's triggers, not here -- a rule the database enforces
cannot be forgotten by the next caller -- and this module translates a
refusal into `ActivationRefused` carrying the trigger's own words.

Nothing here names a market table, and nothing here may: `baseline` imports
it, so it sits inside the LAW 1 prediction closure.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .. import config, db
from ..db import utcnow


class ActivationRefused(RuntimeError):
    """The schema refused an activation. The message is the trigger's own."""


class ScratchWorldRefused(RuntimeError):
    """A scratch activation was asked of a database that is a record."""


#: The reason every bootstrapped activation carries, in words a reader of
#: the record can follow without this file.
BOOTSTRAP_REASON = (
    "the activation gate's birthday bootstrap (operator rulings of "
    "2026-09-24): the newest fit of the market's declared factor set, fitted "
    "before the rule existed and forecasting when it landed, recorded as the "
    "market's incumbent")

#: What a scratch activation says, and what a scratch world says about itself.
SCRATCH_REASON = (
    "a scratch world trains its own fits and activates them without a "
    "holdout, which only a database that is not the live record may do")
SCRATCH_KIND_NOTE = (
    "A scratch world: its fits were activated without a holdout, which the "
    "live record never allows. Nothing here is a record of anything.")


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,)).fetchone() is not None


def active_fit(conn: sqlite3.Connection, sport: str,
               market_type: str) -> sqlite3.Row | None:
    """The fit a market forecasts from: the one its LATEST activation names.

    None when the market has never been activated -- and on a record whose
    schema predates the gate, which has no activation table to hold one. That
    is not a default standing in for an answer: a record with no activation
    has no activated model, which is exactly what the caller is told.

    Latest by row id, which is append order. `activated_utc` can tie within a
    second; the id cannot.
    """
    if not _has_table(conn, "fit_activations"):
        return None
    return conn.execute(
        "SELECT a.id AS activation_id, a.kind, a.activated_utc, a.reason,"
        "       a.factor_set_version, f.id AS fit_id, f.fitted_utc,"
        "       f.train_through, f.coefficients_json"
        "  FROM fit_activations a JOIN model_fits f ON f.id = a.fit_id"
        " WHERE a.sport = ? AND a.market_type = ?"
        " ORDER BY a.id DESC LIMIT 1",
        (sport, market_type)).fetchone()


def _write(conn: sqlite3.Connection, fit_id: int, kind: str, reason: str, *,
           holdout: str | None = None, holdout_n: int | None = None,
           log_loss: float | None = None, brier: float | None = None,
           incumbent_fit_id: int | None = None,
           incumbent_log_loss: float | None = None,
           incumbent_brier: float | None = None,
           diff_low: float | None = None, diff_high: float | None = None,
           only_if_the_market_has_none: bool = False) -> int | None:
    """Insert one activation. The triggers decide; this says what they said.

    `only_if_the_market_has_none` makes the write and its condition ONE
    statement, so two processes opening the record at once -- the server and
    a scheduled task -- cannot both bootstrap the same market.
    """
    fit = conn.execute(
        "SELECT sport, market_type, factor_set_version FROM model_fits"
        " WHERE id = ?", (fit_id,)).fetchone()
    if fit is None:
        raise ActivationRefused(
            f"GRIDIRON ACTIVATION GATE: there is no fit {fit_id} to activate")
    values = (fit_id, fit["sport"], fit["market_type"],
              fit["factor_set_version"], utcnow(), kind, reason, holdout,
              holdout_n, log_loss, brier, incumbent_fit_id,
              incumbent_log_loss, incumbent_brier, diff_low, diff_high)
    columns = (
        "fit_id, sport, market_type, factor_set_version, activated_utc, kind,"
        " reason, holdout, holdout_n, log_loss, brier, incumbent_fit_id,"
        " incumbent_log_loss, incumbent_brier, diff_low, diff_high")
    marks = ",".join("?" for _ in values)
    # A REFUSED WRITE LEAVES THE CONNECTION AS IT FOUND IT. The INSERT opens
    # a transaction and takes the write lock before the trigger aborts it;
    # left open, a refused activation on the record would hold that lock
    # against the server and the scheduler until the handle closed. Rolled
    # back only when this call opened it, so a caller's own work is never
    # discarded here.
    opened_here = not conn.in_transaction
    try:
        if only_if_the_market_has_none:
            cur = conn.execute(
                f"INSERT INTO fit_activations ({columns}) SELECT {marks}"
                " WHERE NOT EXISTS (SELECT 1 FROM fit_activations"
                "                    WHERE sport = ? AND market_type = ?)",
                values + (fit["sport"], fit["market_type"]))
        else:
            cur = conn.execute(
                f"INSERT INTO fit_activations ({columns}) VALUES ({marks})",
                values)
    except sqlite3.IntegrityError as exc:
        if opened_here and conn.in_transaction:
            conn.rollback()
        raise ActivationRefused(str(exc)) from exc
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


def activate_measured(conn: sqlite3.Connection, candidate_fit_id: int, *,
                      incumbent_fit_id: int, holdout: str, holdout_n: int,
                      log_loss: float, brier: float,
                      incumbent_log_loss: float, incumbent_brier: float,
                      interval: tuple[float, float], reason: str) -> int:
    """Activate a candidate that BEAT the market's active fit on a holdout.

    THE ONLY WAY A FIT FITTED ON OR AFTER THE GATE'S BIRTHDAY REACHES THE
    LIVE RECORD. `interval` is the paired bootstrap 95% interval of
    (candidate - incumbent) log loss on the holdout's rows. The schema refuses
    the row unless every score is present, the incumbent is the fit active
    for the market now, and the interval lies wholly below zero: ties go to
    the incumbent. `tools/holdout.py` makes the measurement.
    """
    low, high = interval
    written = _write(
        conn, candidate_fit_id, "measured", reason, holdout=holdout,
        holdout_n=holdout_n, log_loss=log_loss, brier=brier,
        incumbent_fit_id=incumbent_fit_id,
        incumbent_log_loss=incumbent_log_loss,
        incumbent_brier=incumbent_brier, diff_low=low, diff_high=high)
    assert written is not None
    return written


def activate_incumbent(conn: sqlite3.Connection, fit_id: int, *, reason: str,
                       holdout: str | None = None,
                       holdout_n: int | None = None,
                       log_loss: float | None = None,
                       brier: float | None = None,
                       only_if_the_market_has_none: bool = False) -> int | None:
    """Record a fit fitted BEFORE the gate's birthday as the market's model.

    For the bootstrap of every market in use when the rule landed, and for a
    revert to one of them. Holdout scores where they exist, whole or not at
    all. The schema refuses a fit fitted on or after the birthday: the rule
    binds from then, and an incumbent that post-dates it would be a way
    round the measurement.
    """
    return _write(conn, fit_id, "incumbent", reason, holdout=holdout,
                  holdout_n=holdout_n, log_loss=log_loss, brier=brier,
                  only_if_the_market_has_none=only_if_the_market_has_none)


def bootstrap_incumbents(conn: sqlite3.Connection) -> list[dict]:
    """Activate, once, what every market was forecasting when the gate landed.

    Run by `db.init`, so every existing database -- the live record first --
    comes into the gate on its next open without anybody having to remember
    to. IDEMPOTENT: a market with ANY activation row is left alone, forever.

    For each declared market still asked: its newest fit of the declared
    factor set -- exactly the fit the old rule read -- is recorded as the
    incumbent IF it was fitted before the birthday. A newer one is not: on
    the live record that leaves the four fs5 markets (NFL and college
    football spread and moneyline, fits 91-94) with no activation, and so
    unforecast, which is the ruling rather than a gap in it.
    """
    if not (_has_table(conn, "fit_activations")
            and _has_table(conn, "model_fits")):
        return []
    written: list[dict] = []
    for sport in config.SPORTS:
        for market in config.active_markets(sport):
            market_type = (f"prop:{market}"
                           if market in config.SPORT_PROP_MARKETS.get(sport, ())
                           else market)
            if active_fit(conn, sport, market_type) is not None:
                continue
            newest = conn.execute(
                "SELECT id, fitted_utc FROM model_fits"
                " WHERE sport = ? AND market_type = ? AND factor_set_version = ?"
                " ORDER BY id DESC LIMIT 1",
                (sport, market_type,
                 config.factor_set_version(sport, market_type))).fetchone()
            if newest is None or newest["fitted_utc"] >= config.ACTIVATION_GATE_BIRTHDAY:
                continue
            if activate_incumbent(conn, newest["id"], reason=BOOTSTRAP_REASON,
                                  only_if_the_market_has_none=True):
                written.append({"sport": sport, "market_type": market_type,
                                "fit_id": newest["id"]})
    return written


def activate_in_a_scratch_world(conn: sqlite3.Connection,
                                sport: str | None = None) -> list[int]:
    """Activate the newest fit of every trained market, in a world that is
    not the live record.

    THE LAWFUL PATH FOR A TEST WORLD, A PLANTING AND THE GATE'S OWN PIPELINE.
    Each trains its own fits and predicts from them, and none has an
    incumbent to beat. Three locks keep it off the operator's record:

      * the file: a connection whose main database IS the live record is
        refused by name, whatever the process is;
      * the record: a database holding a measured or incumbent activation is
        a record, not a scratch world, and is refused;
      * the schema: the trigger refuses a scratch row on any database whose
        meta kind is 'live'. A fresh file says 'live' until it says
        otherwise, so this DECLARES the world scratch first -- and a world
        that already calls itself a backtest keeps that name.

    Returns the ids of the activations written. A market whose newest fit is
    already active is left alone, so calling this after every training step
    is safe.
    """
    main = next((row[2] for row in conn.execute("PRAGMA database_list")
                 if row[1] == "main"), "")
    if main and db._is_the_live_record(Path(main)):
        raise ScratchWorldRefused(
            f"GRIDIRON ACTIVATION GATE: {main} is the live record. A fit "
            f"there is activated by measurement against its incumbent "
            f"(`activation.activate_measured`), never as a scratch world.")
    records = conn.execute(
        "SELECT COUNT(*) FROM fit_activations WHERE kind <> 'scratch'"
    ).fetchone()[0]
    if records:
        raise ScratchWorldRefused(
            f"GRIDIRON ACTIVATION GATE: this database holds {records} "
            f"activations made under the gate, so it is a record and not a "
            f"scratch world. Train and activate in a world of your own.")
    if (db.get_meta(conn, "kind", "live") or "live") == "live":
        db.set_meta(conn, "kind", "scratch")
        db.set_meta(conn, "kind_note", SCRATCH_KIND_NOTE)

    markets = conn.execute(
        "SELECT DISTINCT sport, market_type FROM model_fits"
        + (" WHERE sport = ?" if sport else "")
        + " ORDER BY sport, market_type", (sport,) if sport else ()).fetchall()
    written: list[int] = []
    for row in markets:
        newest = conn.execute(
            "SELECT id FROM model_fits"
            " WHERE sport = ? AND market_type = ? AND factor_set_version = ?"
            " ORDER BY id DESC LIMIT 1",
            (row["sport"], row["market_type"],
             config.factor_set_version(row["sport"], row["market_type"]))
        ).fetchone()
        if newest is None:
            continue
        active = active_fit(conn, row["sport"], row["market_type"])
        if active is not None and active["fit_id"] == newest["id"]:
            continue
        written.append(_write(conn, newest["id"], "scratch", SCRATCH_REASON))
    return written
