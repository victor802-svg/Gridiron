"""Scheduled work, and an honest record of whether it happened.

Two rules shape everything here.

**A missed slate is recorded, never caught up.** If the machine was asleep when
an MLB morning came round, the games have started and the moment to forecast
them has gone. Predicting them late would be the same failure that voided 47 NBA
rows and 6 MLB ones earlier: a question once answered is never re-asked, so a
late answer permanently occupies the slot the real forecast should have had.
The task records MISSED with its reason and moves on.

**Failure is reported, not smoothed.** `task_runs` is append-only with a trigger
to enforce it. A panel that forgets its failures is worse than no panel, because
it converts "I don't know" into "everything is fine".

This module is NOT in any sport's prediction closure — it imports the runner,
which reaches the market package after the blind window has closed.
"""

from __future__ import annotations

import json
import sqlite3
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import config, db

#: The tasks the scheduler knows how to run, and how often each is expected.
#: `silent_after_hours` is when the panel starts complaining; it is deliberately
#: longer than the interval, so one skipped run is not an alarm and a dead
#: scheduler is.
@dataclass(frozen=True)
class TaskSpec:
    name: str
    what: str
    every_hours: float
    silent_after_hours: float


TASKS: dict[str, TaskSpec] = {
    "refresh": TaskSpec(
        "refresh",
        "re-read the current season's results so finished games are marked finished",
        every_hours=4.0,
        silent_after_hours=12.0,
    ),
    "resolve": TaskSpec(
        "resolve",
        "settle every prediction whose game has finished",
        every_hours=4,
        silent_after_hours=12,
    ),
    "predict:mlb": TaskSpec(
        "predict:mlb",
        "forecast today's baseball slate, blind",
        every_hours=24,
        silent_after_hours=36,
    ),
    "predict:nfl": TaskSpec(
        "predict:nfl",
        "forecast this week's football slate, blind",
        every_hours=24 * 7,
        silent_after_hours=24 * 9,
    ),
    "predict:nba": TaskSpec(
        "predict:nba",
        "forecast today's basketball slate, blind",
        every_hours=24,
        silent_after_hours=36,
    ),
}


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------

def run_task(conn: sqlite3.Connection, task: str, *, use_llm: bool = True) -> dict:
    """Run one scheduled task and record the attempt, whatever happens."""
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}; known: {', '.join(sorted(TASKS))}")

    started = db.utcnow()
    # A missed slate is recorded BEFORE today's work, and independently of it.
    # Checking only when there is no upcoming slate was a real gap: a slate
    # missed yesterday would go unrecorded on every day that had one pending,
    # which is every day. The panel would have shown an unbroken run of
    # successes with a hole in the record behind it.
    if task.startswith("predict:"):
        _record_missed_slates(conn, task.split(":", 1)[1])

    try:
        if task == "refresh":
            result, detail, payload = _run_refresh(conn)
        elif task == "resolve":
            result, detail, payload = _run_resolve(conn)
        else:
            result, detail, payload = _run_predict(
                conn, task.split(":", 1)[1], use_llm=use_llm
            )
    except Exception as exc:  # noqa: BLE001 - a failed task must be recorded, not raised away
        result, detail = "failed", f"{type(exc).__name__}: {exc}"
        payload = {"traceback": traceback.format_exc()[-2000:]}

    conn.execute(
        "INSERT INTO task_runs (task, started_utc, finished_utc, result, detail,"
        " payload_json) VALUES (?,?,?,?,?,?)",
        (task, started, db.utcnow(), result, detail, json.dumps(payload)),
    )
    conn.commit()
    return {"task": task, "result": result, "detail": detail, **payload}


def _run_refresh(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    """Re-read the CURRENT season from each sport's source, so a game that has
    finished in the world is marked finished in the record.

    THIS TASK EXISTS BECAUSE ITS ABSENCE STALLED THE WHOLE APPLIANCE. Everything
    else was running correctly and nothing settled: `predict` wrote forecasts,
    `resolve` ran every four hours and reported `noop` truthfully every time,
    because it settles against `games.status` and NOTHING EVER UPDATED
    `games.status`. On 2026-08-31 the record held 27 open MLB predictions whose
    games were all still marked `scheduled` -- five of them from two days
    earlier. The six that ever settled did so only because a loader happened to
    be run by hand during development.

    A resolver reading a table nobody refreshes is a clock with no winder. The
    tasks were each individually correct, which is what made it invisible: no
    task failed, no error was logged, and the panel showed an unbroken run of
    successes with a record that never moved.

    Cheap by construction. Every loader fetches through `http_cache`, and a
    range wholly in the past is cached immutably, so a refresh re-reads only the
    chunks that touch today. The rest is re-parsed from cache and UPSERTed,
    which is local work.
    """
    from . import config as _config

    counts: dict[str, object] = {}
    warnings: list[str] = []
    for sport in _config.SPORTS:
        season = _config.SPORT_CURRENT_SEASON.get(sport, _config.CURRENT_SEASON)
        try:
            if sport == "mlb":
                from .data import mlb_loader

                result = mlb_loader.load_all(conn, (season,))
            elif sport == "nba":
                from .data import nba_loader

                result = nba_loader.load_all(conn, (season,))
            else:
                from .data import loader

                result = loader.load_all(conn, (season,))
        except Exception as exc:  # noqa: BLE001 - one sport's outage is not all three
            warnings.append(f"{sport}: {type(exc).__name__}: {exc}")
            continue
        counts[sport] = result.get("rows", result) if isinstance(result, dict) else {}
        warnings.extend(result.get("warnings", []) if isinstance(result, dict) else [])

        # Club display names, from the feed, alongside the results. Cheap --
        # cached permanently per club -- and it keeps the interface saying
        # "Tampa Bay Rays" rather than "TB" without anyone typing a name.
        try:
            from .data import teams as _teams

            named = _teams.load_teams(conn, sport, season)
            if named.get("skipped"):
                warnings.append(f"{sport} team names: {named['skipped']}")
        except Exception as exc:  # noqa: BLE001 - names are cosmetic, results are not
            warnings.append(f"{sport} team names: {type(exc).__name__}: {exc}")

    became_final = conn.execute(
        "SELECT COUNT(*) FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.resolved_utc IS NULL AND g.status = 'final'"
        " AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                 WHERE v.prediction_id = p.id)"
    ).fetchone()[0]

    payload = {"sports": list(counts), "resolvable_now": became_final,
               "warnings": warnings[:8]}
    if warnings:
        return ("ok" if counts else "failed",
                f"refreshed {len(counts)} sport(s); {became_final} prediction(s) "
                f"now have a finished game waiting; {len(warnings)} warning(s)",
                payload)
    if became_final == 0:
        return ("noop",
                "every sport re-read; no prediction's game has finished since "
                "the last refresh", payload)
    return ("ok",
            f"re-read {len(counts)} sport(s); {became_final} prediction(s) now "
            "have a finished game waiting for the resolver", payload)


def _run_resolve(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    """Idempotent by construction: `resolve_all` only touches rows whose
    `resolved_utc` is NULL, and a trigger is the backstop. Running it twice in a
    row settles nothing the second time, which is what makes a four-hourly
    schedule safe."""
    from . import resolve

    settled = resolve.resolve_all(conn)
    n = settled["settled"]
    payload = {k: v for k, v in settled.items() if not isinstance(v, list)}
    if n == 0:
        return "noop", "no prediction had a finished game waiting", payload
    return "ok", f"settled {n} prediction(s)", payload


def _run_predict(conn: sqlite3.Connection, sport: str, *, use_llm: bool) -> tuple[str, str, dict]:
    """Forecast the sport's next slate, or record why not.

    The MISSED branch is the important one. It fires when the next slate on the
    calendar has already begun, which means the machine was not awake when it
    should have been. Nothing is written.
    """
    from . import run, sports

    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    adapter = sports.get(sport)

    note = getattr(adapter, "first_slate_note", None)
    if note is not None:
        detail = note(conn, season)
        if detail and detail.get("state") == "preseason":
            return "noop", detail["message"], {"days_away": detail.get("days_away")}

    week = adapter.next_slate(conn, season)
    if week is None:
        missed = _missed_slate(conn, sport, season)
        if missed:
            return (
                "missed",
                f"{sport} {season} slate {missed['week']} began at "
                f"{missed['first']} and was not forecast. It is NOT being "
                "forecast now: a question answered after its games have started "
                "is not a forecast, and answering it late would permanently "
                "occupy the slot the real one should have had.",
                missed,
            )
        return "noop", f"no upcoming {sport} slate is scheduled", {}

    result = run.run_slate(conn, sport, season, week, use_llm=use_llm)
    written = result.get("written", 0)
    payload = {
        "week": week,
        "written": written,
        "snapshots": result.get("snapshots"),
        "degradations": result.get("degradations"),
        "below_floor": result.get("below_floor"),
        # Recorded per slate so the timing of this task can be revisited with
        # data rather than opinion: if most slates are forecast without a
        # starter, the task is running too early in the day.
        "absent_starters": _absent_starters(conn, sport, season, week),
    }
    floor_note = (
        f"; {result['below_floor']} prop question(s) were below the "
        f"{round(config.PROPS_MIN_CLAIM * 100)}% confidence floor and not asked"
        if result.get("below_floor") else ""
    )
    if written == 0:
        return (
            "noop",
            "every question on this slate was already answered" + floor_note,
            payload,
        )
    return "ok", f"wrote {written} prediction(s) for slate {week}{floor_note}", payload


def _record_missed_slates(conn: sqlite3.Connection, sport: str) -> list[dict]:
    """Write a MISSED row for every slate that started without being forecast.

    Bounded to slates after this sport's FIRST prediction. Before that the
    appliance was not running, and calling every game in history "missed" would
    be noise pretending to be a finding — the panel is for what went wrong while
    we were supposed to be watching.

    Recorded once per slate: a run that has already been mourned is not mourned
    again on every subsequent run.
    """
    first = conn.execute(
        "SELECT MIN(created_utc) AS first FROM predictions WHERE sport = ?", (sport,)
    ).fetchone()["first"]
    if not first:
        return []

    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    started = conn.execute(
        "SELECT g.week, MIN(g.kickoff_utc) AS first_game FROM games g"
        " WHERE g.sport = ? AND g.season = ? AND g.kickoff_utc IS NOT NULL"
        "   AND g.kickoff_utc <= ? AND g.kickoff_utc >= ?"
        "   AND NOT EXISTS (SELECT 1 FROM predictions p WHERE p.game_id = g.id)"
        " GROUP BY g.week ORDER BY g.week",
        (sport, season, db.utcnow(), first),
    ).fetchall()

    task = f"predict:{sport}"
    written = []
    for row in started:
        already = conn.execute(
            "SELECT 1 FROM task_runs WHERE task = ? AND result = 'missed'"
            " AND payload_json LIKE ?",
            (task, f'%"week": {row["week"]},%'),
        ).fetchone()
        if already:
            continue
        detail = (
            f"{sport} {season} slate {row['week']} began at {row['first_game']} "
            "and was not forecast. It is NOT being forecast now: a question "
            "answered after its games have started is not a forecast, and "
            "answering it late would permanently occupy the slot the real one "
            "should have had."
        )
        payload = {"week": row["week"], "first_game": row["first_game"], "sport": sport}
        conn.execute(
            "INSERT INTO task_runs (task, started_utc, finished_utc, result,"
            " detail, payload_json) VALUES (?,?,?,'missed',?,?)",
            (task, db.utcnow(), db.utcnow(), detail, json.dumps(payload)),
        )
        written.append(payload)
    if written:
        conn.commit()
    return written


def _missed_slate(conn: sqlite3.Connection, sport: str, season: int) -> dict | None:
    """The most recent slate that started without being forecast."""
    row = conn.execute(
        "SELECT g.week, MIN(g.kickoff_utc) AS first FROM games g"
        " WHERE g.sport = ? AND g.season = ? AND g.kickoff_utc IS NOT NULL"
        "   AND g.kickoff_utc <= ?"
        "   AND NOT EXISTS (SELECT 1 FROM predictions p WHERE p.game_id = g.id)"
        " GROUP BY g.week ORDER BY g.week DESC LIMIT 1",
        (sport, season, db.utcnow()),
    ).fetchone()
    if row is None or not row["first"]:
        return None
    return {"week": row["week"], "first": row["first"]}


def _absent_starters(conn: sqlite3.Connection, sport: str, season: int, week: int) -> dict:
    """How many of this slate's forecasts were made without knowing a key input.

    Baseball's unannounced starter is the case this exists for, and it is
    recorded per slate so the schedule time can be argued from evidence.
    """
    rows = conn.execute(
        "SELECT p.factors_json FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ?"
        "   AND p.predictor = 'statistical'",
        (sport, season, week),
    ).fetchall()
    if not rows:
        return {"n": 0}
    absent = 0
    for r in rows:
        try:
            payload = json.loads(r["factors_json"] or "{}")
        except ValueError:
            continue
        if any("starter" in name for name in payload.get("absent", [])):
            absent += 1
    return {"n": len(rows), "without_a_named_starter": absent}


# ---------------------------------------------------------------------------
# catch-up
# ---------------------------------------------------------------------------

def catch_up(conn: sqlite3.Connection, *, use_llm: bool = True) -> list[dict]:
    """What runs when the machine wakes up.

    `refresh` runs FIRST and `resolve` second, and the order is the whole point:
    the resolver settles against `games.status`, so resolving before re-reading
    the results settles nothing and reports `noop` truthfully. That ordering
    error, in its earlier form of having no refresh at all, is what stalled the
    record for two days while every task reported success.

    Both are cheap and idempotent, and the record is always behind after a
    sleep. Every `predict` runs only if its slate has not started — and if one
    has, the MISSED branch records it rather than forecasting into the past.
    """
    out = [run_task(conn, "refresh", use_llm=False),
           run_task(conn, "resolve", use_llm=False)]
    for sport in config.SPORTS:
        out.append(run_task(conn, f"predict:{sport}", use_llm=use_llm))
    return out


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def status(conn: sqlite3.Connection) -> dict:
    """Per task: when it last ran, what happened, when it is next due, and every
    MISSED entry. Honest about failure, never reassuring."""
    now = datetime.now(timezone.utc)
    out = []
    for spec in TASKS.values():
        last = conn.execute(
            "SELECT * FROM task_runs WHERE task = ? ORDER BY started_utc DESC LIMIT 1",
            (spec.name,),
        ).fetchone()
        missed = conn.execute(
            "SELECT started_utc, detail FROM task_runs WHERE task = ?"
            " AND result = 'missed' ORDER BY started_utc DESC LIMIT 5",
            (spec.name,),
        ).fetchall()
        failures = conn.execute(
            "SELECT COUNT(*) AS n FROM task_runs WHERE task = ? AND result = 'failed'",
            (spec.name,),
        ).fetchone()["n"]

        entry = {
            "task": spec.name,
            "what": spec.what,
            "every_hours": spec.every_hours,
            "last_run_utc": last["started_utc"] if last else None,
            "last_result": last["result"] if last else None,
            "last_detail": last["detail"] if last else None,
            "missed": [dict(m) for m in missed],
            "failures_all_time": failures,
            # A scheduled predict that ran statistical-only because the LLM
            # budget was spent is not a failure, but it IS a different run and
            # the panel says so. Silently producing half the forecasters and
            # reporting "ok" is the kind of quiet degradation this project
            # exists to refuse.
            "degraded": _degradations(last),
        }
        if last is None:
            entry.update({
                "age_hours": None, "silent": True, "next_due_utc": None,
                "warning": "has never run. If the scheduler is installed, it has "
                           "not fired yet; if it is not, nothing is running.",
            })
        else:
            age = (now - _parse(last["started_utc"])).total_seconds() / 3600.0
            entry["age_hours"] = round(age, 2)
            entry["next_due_utc"] = _iso(
                _parse(last["started_utc"]) + timedelta(hours=spec.every_hours)
            )
            entry["silent"] = age > spec.silent_after_hours
            if entry["silent"]:
                entry["warning"] = (
                    f"has not run for {age:.0f}h, past the {spec.silent_after_hours:.0f}h "
                    "mark. The record is not being kept up to date."
                )
        out.append(entry)

    from . import views

    return {
        "tasks": out,
        "any_silent": any(t["silent"] for t in out),
        "any_missed": any(t["missed"] for t in out),
        "schedule_staleness": views.schedule_staleness(conn),
    }


def _degradations(last: sqlite3.Row | None) -> list[str]:
    if last is None or not last["payload_json"]:
        return []
    try:
        payload = json.loads(last["payload_json"])
    except ValueError:
        return []
    degraded = payload.get("degradations") or {}
    return [f"{reason} ({count})" for reason, count in sorted(degraded.items())]


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")
