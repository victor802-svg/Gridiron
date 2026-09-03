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

from . import config, db, language
from . import language

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
    "recalibrate": TaskSpec(
        "recalibrate",
        "re-fit each category's claim correction against its settled record",
        # WEEKLY, and not more often. A correction refitted daily would move
        # under the interface for reasons nobody could point at, and its
        # training set grows by a handful of rows a day -- there is nothing a
        # daily refit could see that a weekly one misses.
        every_hours=24 * 7,
        silent_after_hours=24 * 9,
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
    "live": TaskSpec(
        "live",
        "follow the games that are on right now",
        # NOT AN INTERVAL LIKE THE OTHERS. This one runs every 90 seconds while
        # a window is open and not at all otherwise, so "every_hours" is a
        # fiction for the panel's benefit. What matters for the silence check
        # is that a whole day with no poll is unremarkable -- most days have
        # no games in most sports -- so it never reports as silent. The rate
        # figures beside it are what say whether it is alive.
        every_hours=24.0,
        silent_after_hours=24.0 * 365,
    ),
    "predict:cfb": TaskSpec(
        "predict:cfb",
        "forecast the college football slate, blind",
        # WEEKLY, and the slate it writes is Saturday's. College football's
        # week is really three slates -- Saturday's 60 games, Sunday's 16,
        # Friday's 8 -- so this runs daily and writes whichever slate is next,
        # rather than assuming the week has one card.
        every_hours=24,
        silent_after_hours=36,
    ),
}


# THE FINAL PASS, ONE PER SPORT (2026-09-03). Derived from config.SPORTS
# rather than typed out four times: a sport added later gets its late pass
# automatically, and cannot be the one that was forgotten. The lesson is
# recorded in MENTOR 3 and this is it applied -- two tests fetched a whole
# season for weeks because a list of sports was written by hand and one arm
# was missed.
for _sport in config.SPORTS:
    _spec = config.FINAL_PASS[_sport]
    TASKS[f"final:{_sport}"] = TaskSpec(
        f"final:{_sport}",
        f"re-forecast the {_sport} slate close to start, on what is known then",
        # Same cadence as the sport's own early pass: a weekly sport gets a
        # weekly late pass, a daily one a daily late pass.
        every_hours=TASKS[f"predict:{_sport}"].every_hours,
        silent_after_hours=TASKS[f"predict:{_sport}"].silent_after_hours,
    )
del _sport, _spec


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
    if task.startswith("predict:") or task.startswith("final:"):
        _record_missed_slates(conn, task.split(":", 1)[1])

    try:
        if task == "refresh":
            result, detail, payload = _run_refresh(conn)
        elif task == "recalibrate":
            result, detail, payload = _run_recalibrate(conn)
        elif task == "resolve":
            result, detail, payload = _run_resolve(conn)
        elif task == "live":
            result, detail, payload = _run_live(conn)
        elif task.startswith("final:"):
            result, detail, payload = _run_final_pass(
                conn, task.split(":", 1)[1], use_llm=use_llm
            )
        else:
            result, detail, payload = _run_predict(
                conn, task.split(":", 1)[1], use_llm=use_llm
            )
    except Exception as exc:  # noqa: BLE001 - a failed task must be recorded, not raised away
        result, detail = "failed", f"{type(exc).__name__}: {exc}"
        payload = {"traceback": traceback.format_exc()[-2000:]}
        # A FAILED TASK IS EXACTLY WHEN THE SECOND CHANNEL EXISTS (ruling R4).
        # Checked here rather than on a schedule of its own, which could go
        # silent in the same way the thing it watches did.
        try:
            notify_failures(conn)
        except Exception:  # noqa: BLE001 - the notifier must never mask the fault
            pass

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
            elif sport == "cfb":
                # ITS OWN LOADER, and the `else` branch below is why this
                # matters: without this arm, college football fell through to
                # the NFL loader and refreshed football's schedule under
                # college football's name.
                from .data import cfb_loader

                loaded = cfb_loader.load_season(conn, season)
                result = {"rows": {"games": loaded["games"],
                                   "finals": loaded["finals"]},
                          "warnings": []}
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

            if sport == "cfb":
                # `cfb_loader.load_season` already wrote the names, from group
                # 80's teams. The generic ESPN team path has no college entry
                # and would report a skip every four hours forever.
                raise StopIteration
            named = _teams.load_teams(conn, sport, season)
            if named.get("skipped"):
                warnings.append(f"{sport} team names: {named['skipped']}")
        except StopIteration:
            pass                    # this sport's loader named its own teams
        except Exception as exc:  # noqa: BLE001 - names are cosmetic, results are not
            warnings.append(f"{sport} team names: {type(exc).__name__}: {exc}")

    became_final = conn.execute(
        "SELECT COUNT(*) FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.resolved_utc IS NULL AND g.status = 'final'"
        " AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                 WHERE v.prediction_id = p.id)"
    ).fetchone()[0]

    # THE SECOND LOOK AT THE LINE (C3), taken here because this task already
    # runs every four hours and already knows which games are close. It reads
    # the market for games about to start; it touches no prediction and can
    # change no claim.
    drift_counts = _near_start_snapshots(conn)

    payload = {"sports": list(counts), "resolvable_now": became_final,
               "warnings": warnings[:8], **drift_counts}
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


#: How close to the start a second look at the line is taken. Two hours is
#: late enough that most of the day's news is priced and early enough that the
#: fetch is not racing the first pitch.
NEAR_START_HOURS = 2.0


def _near_start_snapshots(conn: sqlite3.Connection) -> dict:
    """A second look at the line for games about to start.

    THE PREDICTION ALREADY EXISTS -- this only ever runs for rows that have one
    -- so the blind structure is untouched. LAW 1 is about what the model may
    see before it commits; this is about what the market did afterwards, which
    the model never sees.

    A game with no first snapshot gets no second one. The pair is the unit: a
    near-start line with nothing to compare it against says nothing about
    drift, and storing it would make the count of pairs disagree with the count
    of rows.
    """
    from .market import espn, lines

    now = db.utcnow()
    horizon = _plus_hours(now, NEAR_START_HOURS)
    rows = conn.execute(
        "SELECT p.id FROM predictions p"
        " JOIN games g ON g.id = p.game_id"
        " JOIN market_snapshots o"
        "   ON o.prediction_id = p.id AND o.kind = 'open_at_predict'"
        " WHERE g.status = 'scheduled'"
        "   AND g.kickoff_utc > ? AND g.kickoff_utc <= ?"
        "   AND o.implied_prob IS NOT NULL"
        "   AND NOT EXISTS (SELECT 1 FROM market_snapshots n"
        "                   WHERE n.prediction_id = p.id AND n.kind = 'near_start')",
        (now, horizon),
    ).fetchall()

    if not rows:
        return {"near_start_taken": 0, "near_start_failed": 0,
                "near_start_due": 0}

    # RE-READ THE MARKET FIRST, AND FORCE IT PAST THE CACHE.
    #
    # `snapshot_prediction` reads the quote already stored in
    # `market_lines_raw`; on its own it would copy the line captured when the
    # prediction was written and file it as a second look. And the fetch that
    # refills that table serves anything younger than six hours out of
    # `http_cache`, so even calling it would have replayed the same bytes.
    #
    # Both were true on the first live run: eight near-start rows, four usable
    # pairs, every one with `near` equal to `opened` to the last decimal. A
    # market does not do that. The drift measurement would have reported "the
    # line never moves" forever, from real-looking rows.
    ids = [r["id"] for r in rows]
    refreshed = lines.refresh_quotes(conn, ids, ttl=espn.NEAR_START_TTL)

    taken, failed = 0, 0
    for row in rows:
        try:
            lines.snapshot_prediction(conn, row["id"], kind="near_start")
            taken += 1
        except Exception:  # noqa: BLE001 - one bad quote must not stop the pass
            failed += 1
    return {"near_start_taken": taken, "near_start_failed": failed,
            "near_start_due": len(rows), "near_start_refetched": refreshed}


def _plus_hours(stamp: str, hours: float) -> str:
    when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc) + timedelta(hours=hours)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_recalibrate(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    """Re-fit every category's correction. Writes versions; activates nothing.

    Reports in the same voice as the gates elsewhere: a category under the
    threshold says how far off it is, because "no correction" and "not enough
    record yet" are different states and the panel must not show them alike.
    """
    from . import correction

    report = correction.refit_all(conn)
    if not report["n"]:
        return "noop", "nothing has settled yet, so there is nothing to fit", report
    detail = (f"fitted {report['n']} categor"
              f"{'y' if report['n'] == 1 else 'ies'}; "
              f"{report['eligible']} had at least {correction.MIN_TRAIN} settled")
    return ("ok" if report["eligible"] else "noop"), detail, report


def _run_resolve(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    """Idempotent by construction: `resolve_all` only touches rows whose
    `resolved_utc` is NULL, and a trigger is the backstop. Running it twice in a
    row settles nothing the second time, which is what makes a four-hourly
    schedule safe."""
    from . import resolve

    from . import notify

    # ANYTHING THAT QUEUED OVERNIGHT GOES OUT FIRST. The resolve task runs
    # every four hours, so it is the natural thing to carry the morning's
    # message -- no separate scheduled job that could itself go silent.
    held = notify.flush_queue(conn)

    settled = resolve.resolve_all(conn)
    n = settled["settled"]
    if held:
        settled["queued_sent"] = held
    payload = {k: v for k, v in settled.items() if not isinstance(v, list)}
    if n == 0:
        # NO MESSAGE ON A QUIET RUN. A notification saying "0 settled" is a
        # notification that teaches its reader to stop reading them, and this
        # task runs every four hours whether or not anything finished.
        return "noop", "no prediction had a finished game waiting", payload

    payload["notified"] = _notify_results(conn)
    return "ok", f"settled {n} prediction(s)", payload


def _notify_results(conn: sqlite3.Connection) -> dict:
    """Tell the operator what landed, per sport, never summed (LAW 6).

    Counted from the record AFTER the resolver has written, rather than from
    its return value: the message then describes what is actually settled
    rather than what one pass happened to touch, which is the difference that
    matters if a pass is interrupted and resumed.
    """
    from . import notify

    by_sport = {}
    for sport in config.SPORTS:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(outcome), 0) AS right_"
            " FROM predictions WHERE sport = ? AND resolved_utc >= ?",
            (sport, _since_last_notification(conn))).fetchone()
        by_sport[sport] = {
            "settled": row["n"] or 0, "right": row["right_"] or 0,
        }
    body = notify.results_message(by_sport)
    if not body:
        return {"sent": False, "reason": "nothing settled since the last message"}
    try:
        return notify.send(conn, "results", body)
    except notify.Blocked as exc:
        # REFUSED RATHER THAN SENT. A message carrying a number somebody could
        # act on is not softened, it is stopped, and the reason is recorded.
        return {"sent": False, "reason": str(exc)}


def _since_last_notification(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT MAX(queued_utc) AS last FROM notifications WHERE kind='results'"
    ).fetchone()
    return (row["last"] if row and row["last"] else "0000-01-01T00:00:00Z")


def _run_live(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    """Follow whatever is on. Makes no request when nothing is.

    Reports "noop" on a quiet day rather than "ok", so the panel can tell the
    difference between a poll that ran and found nothing on and a poll that
    ran and updated nothing -- those look identical in a request count and
    mean opposite things about whether the scheduler is alive.

    THE RESOLVER IS PASSED IN, not called from inside the poller. `live` does
    not import `resolve`, so there is no path by which live status could
    settle anything; what there is, is this line handing the poll the ONE
    idempotent resolver to call when a game ends, so a result lands in a
    minute rather than waiting up to four hours for the schedule.
    """
    from . import live, resolve

    live.ensure_live_columns(conn)
    report = live.poll(conn, resolver=resolve.resolve_all)
    if not report["windows"]:
        return "noop", "nothing is on; no request made", report
    settled = (report.get("resolved") or {}).get("settled")
    detail = (f"{report['requests']} request(s), {report['seen']} game(s) seen, "
              f"{report['changed']} updated")
    if report["finals"]:
        detail += f", {report['finals']} final"
    if settled:
        detail += f", {settled} settled"
    return "ok", detail, report


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


def _refresh_one_sport(conn: sqlite3.Connection, sport: str) -> str:
    """Re-read ONE sport's current season, immediately before forecasting it.

    THE FINAL PASS IS POINTLESS WITHOUT THIS, and the probe is what showed it
    (docs/TIMING_FEASIBILITY.md section 8). `_run_predict` reads stored rows;
    it does not fetch. So a pass scheduled ninety minutes before first pitch
    reads whatever the last `refresh` happened to leave behind, and if that
    ran six hours ago the lineup is not there -- however long ago the league
    posted it.

    The 39 lineups we hold from before their games are the illustration: they
    appeared in our database at 17:00 and 21:00 UTC because that is when we
    looked, not because that is when they posted. Moving the prediction
    without moving the fetch buys nothing at all.

    One sport, not all four, because this runs on a clock tied to one sport's
    slate and the other three have their own.
    """
    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    try:
        if sport == "mlb":
            from .data import mlb_loader
            mlb_loader.load_all(conn, (season,))
        elif sport == "nba":
            from .data import nba_loader
            nba_loader.load_all(conn, (season,))
        elif sport == "cfb":
            from .data import cfb_loader
            cfb_loader.load_season(conn, season)
        else:
            from .data import loader
            loader.load_all(conn, (season,))
    except Exception as exc:  # noqa: BLE001
        # A FETCH THAT FAILED IS NOT A REASON NOT TO FORECAST. The slate still
        # starts, and a forecast on slightly older inputs beats none at all --
        # but the run says so, so a pattern of failures is visible rather than
        # showing up as a final pass that mysteriously never improves on the
        # early one.
        return f"the pre-pass fetch failed ({type(exc).__name__}: {exc})"
    return ""


def _run_final_pass(conn: sqlite3.Connection, sport: str, *, use_llm: bool) -> tuple[str, str, dict]:
    """Forecast the next slate AGAIN, close to start (config.FINAL_PASS).

    The rows this writes supersede the early ones as the standing forecast.
    The early rows are kept and labelled; nothing is edited or deleted.
    """
    from . import run, sports

    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    adapter = sports.get(sport)
    week = adapter.next_slate(conn, season)
    if week is None:
        # MISSED, UNCHANGED (MENTOR 4): a pass whose slate has already begun
        # writes nothing. The early row remains the standing forecast for
        # those games and is labelled as the only one there was.
        missed = _missed_slate(conn, sport, season)
        if missed:
            return ("missed",
                    f"the {sport} slate {missed['week']} began at "
                    f"{missed['first']} and the final pass did not run before "
                    f"it. Nothing was written: a forecast made after the game "
                    f"started is not a forecast. The early forecast stands as "
                    f"the only one this slate got.",
                    missed)
        return "noop", f"no upcoming {sport} slate to re-forecast", {}

    early = conn.execute(
        "SELECT COUNT(*) AS n FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ?",
        (sport, season, week)).fetchone()["n"]
    if not early:
        return ("noop",
                f"the {sport} slate {week} has no early forecast to improve "
                f"on; the early pass writes first and this one revises it",
                {"week": week})

    fetch_note = _refresh_one_sport(conn, sport)
    result = run.run_slate(conn, sport, season, week, use_llm=use_llm, final=True)
    written = result.get("written", 0)
    payload = {
        "week": week,
        "written": written,
        "early_rows": early,
        "snapshots": result.get("snapshots"),
        "absent_starters": _absent_starters(conn, sport, season, week),
        "fetch_note": fetch_note or None,
    }
    if written == 0:
        return ("noop",
                f"the final pass found nothing new to write for slate {week}"
                + (f"; {fetch_note}" if fetch_note else ""),
                payload)
    return ("ok",
            f"re-forecast {written} question(s) for slate {week} close to "
            f"start; these supersede the early rows"
            + (f"; {fetch_note}" if fetch_note else ""),
            payload)


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
            # The panel says whether the machine is alive; a reader should not
            # need to know a colon-joined key to read it. The id stays in the
            # payload for anything matching against task_runs.
            "task_label": language.task_name(spec.name),
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
        # RATE HONESTY (L1). The live poll runs on a 90-second cadence inside a
        # window and not at all outside one, so "last ran" alone says nothing
        # about whether it is behaving: a poll that ran once and a poll that
        # ran four hundred times look identical by that measure. The request
        # count is the figure that can be held to a rate.
        "live_poll": _live_rate(conn),
        # WHAT WAS SENT, AND WHETHER IT ARRIVED. A push that silently failed
        # is worse than having no push channel: the operator believes they are
        # covered, which is the precise state this whole feature exists to
        # end.
        "last_notification": _last_notification(conn),
    }


def _last_notification(conn: sqlite3.Connection) -> dict | None:
    from . import notify

    last = notify.last_sent(conn)
    if last is None:
        return None
    return {
        "kind": last["kind"],
        "state": last["state"],
        "sent_utc": last["sent_utc"],
        "queued_utc": last["queued_utc"],
        # The body is shown: it carries counts and team names by construction,
        # and a panel that hides what it sent cannot be checked.
        "body": last["body"],
        "channels": last["channels"],
    }


def notify_failures(conn: sqlite3.Connection) -> dict:
    """The second channel (ruling R4), on by default.

    THE CASE THIS EXISTS FOR ALREADY HAPPENED. The appliance sat stalled for
    two days with every screen green -- `resolve` ran every four hours and
    truthfully reported nothing to settle, because nothing was updating
    `games.status`. No task failed. No error was logged. A push is the only
    surface that reaches somebody who is not looking at a screen.
    """
    from . import notify

    if config.setting("GRIDIRON_NOTIFY_FAILURES", "1") != "1":
        return {"sent": False, "reason": "failure notices are switched off"}

    state = status(conn)
    problems = []
    for task in state["tasks"]:
        if task.get("silent"):
            problems.append(f"{language.task_name(task['task'])} has not run "
                            f"in {int(task.get('hours_since') or 0)} hours")
        if task.get("missed"):
            problems.append(f"{language.task_name(task['task'])} missed a slate")
    body = notify.failure_message(problems)
    if not body:
        return {"sent": False, "reason": "nothing is wrong"}
    try:
        return notify.send(conn, "failure", body, title="Gridiron needs a look")
    except notify.Blocked as exc:
        return {"sent": False, "reason": str(exc)}


def _live_rate(conn: sqlite3.Connection) -> dict:
    from . import language, live

    figures = live.rate(conn, hours=24)
    figures["line"] = language.live_rate_line(
        figures["requests"], figures["polls"], figures["hours"])
    figures["sports"] = list(live.LIVE_SPORTS)
    figures["not_followed"] = language.live_not_followed_line(
        [s for s in config.SPORTS if s not in live.LIVE_SPORTS])
    return figures


def _degradations(last: sqlite3.Row | None) -> list[str]:
    if last is None or not last["payload_json"]:
        return []
    try:
        payload = json.loads(last["payload_json"])
    except ValueError:
        return []
    degraded = payload.get("degradations") or {}
    # IN WORDS, HERE. The stored key is a code and the page said "ran degraded:
    # llm_unavailable:api_error (1)" inside an otherwise plain sentence.
    return [
        f"{language.degraded_words(reason)} ({count})"
        for reason, count in sorted(degraded.items())
    ]


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")
