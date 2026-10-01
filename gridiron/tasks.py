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


#: The installer gives every task a two-hour execution limit; a 'running'
#: row older than that is a run that never recorded an ending.
RUN_CEILING_HOURS = 2.0

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
    "capture": TaskSpec(
        "capture",
        "stamp the injury report and tonight's lineups, so what was knowable "
        "when becomes data",
        # EVERY FOUR HOURS IN SEASON, per S1. The point is the SEQUENCE -- a
        # player appearing as questionable and later as out is the thing a
        # timing probe needs, and a daily capture would record the end of that
        # story and none of it.
        every_hours=4.0,
        silent_after_hours=12.0,
    ),
    # THE SECOND LOOK AT THE LINE, ON ITS OWN CLOCK (2026-09-07).
    #
    # It used to ride inside `refresh`, which fires every four hours, while
    # the window it acts on is two hours wide. Measured on today's baseball
    # slate: three of twelve games fell in no firing's window and would have
    # got no second look ever. Since this pass is the only writer of a
    # near-start ladder, an at-the-line claim and a closing price, that is
    # also why both of those tables were empty.
    #
    # Half an hour, against a two-hour window, means every kickoff is seen
    # by at least three firings. The cost is a no-op row in `task_runs` most
    # of the time, which is the cheapest thing in this record.
    "near-start": TaskSpec(
        "near-start",
        "take the second look at the line for games about to start",
        every_hours=0.5,
        # Six hours, not one. A machine asleep overnight is not a fault, and
        # this task's own no-op runs are what prove the clock is alive.
        silent_after_hours=6.0,
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
    # THE LOGON CATCH-UP, ON THE PANEL (ruling 5 on the audit, 2026-09-05).
    # It was a function the installer registered and the panel could not
    # show, so the one task that had never fired was the one nobody could see
    # had never fired. No cadence: it runs at logon or not at all, so a year
    # without one is unremarkable, as with the live poll.
    "catch-up": TaskSpec(
        "catch-up",
        "after a sleep: re-read results, settle, then forecast only slates that have not started",
        every_hours=24.0,
        silent_after_hours=24.0 * 365,
    ),
    "predict:ufc": TaskSpec(
        "predict:ufc",
        "forecast the next UFC card, blind",
        # DAILY, and the slate it writes is the next card. UFC runs about 4.3
        # cards a month with no season shape at all -- a weekly cadence would
        # miss a Wednesday card entirely, and a daily run on a night with no
        # card is a logged no-op that costs nothing.
        every_hours=24,
        silent_after_hours=36,
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

def _slate_words(conn: sqlite3.Connection, sport: str, season: int,
                 week: int | None) -> str:
    """The slate as the page names it: "Saturday 5 September", "Week 1, 2026".

    NEVER THE KEY. College football keys a slate as 20260905 and baseball as
    an ordinal, and both reached the Health panel as "slate 20260905" until
    2026-09-05. This is the door `views` already uses for the page title,
    fed the slate's own calendar date so a baseball ordinal reads as a date.
    """
    from . import language
    day = conn.execute(
        "SELECT MIN(league_date) FROM games WHERE sport = ? AND season = ?"
        " AND week = ?", (sport, season, week)).fetchone()[0]
    return language.slate_title(
        season, week, config.SPORT_SLATE_WORD.get(sport, "week"), day)


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

    # THE ROW EXISTS BEFORE THE WORK DOES (audit 2026-09-05). Gridiron-Refresh
    # was killed at 03:00Z on 2026-09-05 with a control-C exit and left no row
    # at all, so the Health panel showed the last run that finished and the
    # resolve that followed read a table nobody had refreshed. A run that
    # dies now dies as a 'running' row with no ending, which the panel can
    # see. The same ordering as `notify.send`: intent recorded, then the act.
    cursor = conn.execute(
        "INSERT INTO task_runs (task, started_utc, result, detail)"
        " VALUES (?,?,'running','started; no ending recorded yet')",
        (task, started),
    )
    row_id = cursor.lastrowid
    conn.commit()

    # A RUN THAT NEVER ENDED IS MARKED ONCE IT IS PAST ITS TASK'S SILENCE
    # (GRIDIRON_REPAIR item 7, the operator's ruling of 2026-09-23, built
    # 2026-09-26). Here, after this run's own row exists -- the record still
    # precedes the run -- and never at the cost of the run: a sweep that
    # fails leaves every row as it was, for the next run to try, and takes
    # nothing of this one with it (its row is already committed above).
    try:
        abandon_hung_runs(conn, by_task=task, by_run=row_id)
    except Exception:  # noqa: BLE001 - the sweep must never stop the run
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass

    # WHAT THE TASK DID, once it has done it (GRIDIRON_REPAIR item 7,
    # 2026-09-26). Set only when the dispatch returned, so the handler below
    # can tell a task that raised from a task whose closing write raised.
    done = None
    try:
        if task == "refresh":
            result, detail, payload = _run_refresh(conn)
        elif task == "recalibrate":
            result, detail, payload = _run_recalibrate(conn)
        elif task == "resolve":
            result, detail, payload = _run_resolve(conn)
        elif task == "live":
            result, detail, payload = _run_live(conn)
        elif task == "capture":
            result, detail, payload = _run_capture(conn)
        elif task == "near-start":
            result, detail, payload = _run_near_start(conn)
        elif task == "catch-up":
            result, detail, payload = _run_catch_up(conn, use_llm=use_llm)
        elif task.startswith("final:"):
            result, detail, payload = _run_final_pass(
                conn, task.split(":", 1)[1], use_llm=use_llm
            )
        else:
            result, detail, payload = _run_predict(
                conn, task.split(":", 1)[1], use_llm=use_llm
            )
        # THE CLOSING WRITE IS INSIDE THE TRY (GRIDIRON_REPAIR item 7, the
        # operator's ruling of 2026-09-23: "the run_task closing UPDATE moves
        # inside the try"). It sat after the handler until 2026-09-26, so a
        # write that raised -- a second writer holding the record past the
        # 30-second wait, or a payload `json` cannot write -- left
        # `run_task`, the process exited 1 and the row stayed 'running':
        # `final:cfb` on 9, 21, 23 and 25 September, each started inside a
        # burst of concurrent refreshes (the lock is the likeliest cause and
        # was never reproduced). Now the handler below records it.
        #
        # AN ENDING IS WRITTEN ONCE (`AND result = 'running'`): a row a later
        # run has marked abandoned keeps that mark -- 'abandoned' is terminal
        # -- and no closing write ever replaces another ending.
        done = (result, detail, payload)
        conn.execute(
            "UPDATE task_runs SET finished_utc = ?, result = ?, detail = ?,"
            " payload_json = ? WHERE id = ? AND result = 'running'",
            (db.utcnow(), result, detail, json.dumps(payload), row_id),
        )
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - a failed task must be recorded, not raised away
        if done is not None:
            # THE TASK FINISHED; ONLY ITS ENDING FAILED TO BE WRITTEN. What
            # it did is recorded as it did it -- `failed` means the task
            # raised (schema.sql), and final:cfb had written its forecasts --
            # with the write's own error beside it, and no failure notice.
            result, detail, payload = done
            payload = {**payload,
                       "closing_write": f"{type(exc).__name__}: {exc}"}
        else:
            result, detail = "failed", f"{type(exc).__name__}: {exc}"
            payload = {"traceback": traceback.format_exc()[-2000:]}
            # A RUN FAILED FOR WANT OF A MODEL HAS STILL RECOMMENDED (the
            # prover of GRIDIRON_REPAIR item 5, 2026-09-26).
            # `run.MarketNotTrained` is raised after the markets that have a
            # model are written, priced and recorded, and carries what the
            # run did; until this date the payload kept only the traceback,
            # so what such a run recommended, and what it kept off the
            # record as a second on its game and market or as both sides of
            # one, with why, went unsaid -- while a run that ended ok kept
            # it. Kept here the same way, and never at the cost of recording
            # the failure itself.
            try:
                from . import run as _run

                if isinstance(exc, _run.MarketNotTrained):
                    payload["recommended"] = (exc.result or {}).get("recommended")
                    # AND WHAT IT LEFT TO A FINAL PASS, by name (operator
                    # question 27, 2026-09-29), as a run that ended ok does.
                    payload["final_pass_answered"] = (
                        (exc.result or {}).get("final_pass_answered") or [])
            except Exception:  # noqa: BLE001 - keeping it must never mask the fault
                pass
            # A FAILED TASK IS EXACTLY WHEN THE SECOND CHANNEL EXISTS (ruling
            # R4). Checked here rather than on a schedule of its own, which
            # could go silent in the same way the thing it watches did.
            try:
                notify_failures(conn)
            except Exception:  # noqa: BLE001 - the notifier must never mask the fault
                pass
        # ONE MORE ATTEMPT, AND THEN THE SWEEP (2026-09-26). The same write,
        # with a payload `json` can always write; if it cannot be made
        # either, nothing is raised: the row stays 'running', the Health
        # panel says it never recorded an ending, and the first run after
        # its task's silence marks it abandoned (`abandon_hung_runs`).
        try:
            conn.execute(
                "UPDATE task_runs SET finished_utc = ?, result = ?, detail = ?,"
                " payload_json = ? WHERE id = ? AND result = 'running'",
                (db.utcnow(), result, detail, json.dumps(payload, default=str),
                 row_id),
            )
            conn.commit()
        except Exception:  # noqa: BLE001 - left for the sweep, never raised
            pass
    return {"task": task, "result": result, "detail": detail, **payload}


def abandon_hung_runs(conn: sqlite3.Connection, *, by_task: str | None = None,
                      by_run: int | None = None,
                      now: datetime | None = None) -> list[int]:
    """Mark abandoned every 'running' row older than its task's silence.

    THE OPERATOR'S RULING of 2026-09-23 (GRIDIRON_REPAIR item 7, built
    2026-09-26): "a hung 'running' row older than its task's
    silent_after_hours is marked abandoned". Until then nothing ended such a
    row: thirteen stood on the record on 26 September, the oldest a
    `final:cfb` run begun at 19:41Z on 9 September.

    LITERAL, PER TASK: the age is measured from the row's start against
    ITS OWN task's `silent_after_hours`, the figure the Health panel already
    calls that task silent past. So a hung `refresh` row goes after 12
    hours, `final:cfb` after 36, `predict:nfl` after 216 -- and `catch-up`
    and `live`, which declare a year because neither has a cadence, keep a
    hung row 'running' for a year. That follows from the ruling's words and
    those figures, which the ruling does not name; it is recorded, not
    changed (FOLLOWUPS).

    WRITTEN ONCE, ON A ROW WITH NO ENDING, never by deleting or rewriting
    one. `task_runs` refuses a delete; what it has always allowed is the one
    write that ends a row, which `run_task` makes itself. This is that write,
    made by a later run for a run that could not make it: `result` from
    'running' to 'abandoned', the detail in words, and a payload saying when
    and by which run. `finished_utc` stays NULL -- no ending was recorded,
    and the row does not pretend one was -- and `AND result = 'running'`
    keeps it from touching a row that has ended, including one ended while
    this ran. 'abandoned' is terminal: `run_task`'s own closing write
    carries the same clause.

    SAFE BY THE SCHEDULER'S LIMITS: every task's silence (six hours at the
    least, `near-start`) is longer than the longest execution the installer
    allows (two hours), so a row past it belongs to no process still
    running under the scheduler. `now` is for tests; it is the real clock
    otherwise. Returns the ids it marked.
    """
    now = now or datetime.now(timezone.utc)
    marked_at = _iso(now)
    marked = []
    for row in conn.execute(
            "SELECT id, task, started_utc FROM task_runs"
            " WHERE result = 'running' ORDER BY id").fetchall():
        spec = TASKS.get(row["task"])
        if spec is None:
            continue            # no declared task, so no silence to be past
        try:
            started = _parse(row["started_utc"])
        except (TypeError, ValueError):
            continue            # a stamp nobody can age is left as it is
        age = (now - started).total_seconds() / 3600.0
        if age <= spec.silent_after_hours:
            continue
        cursor = conn.execute(
            "UPDATE task_runs SET result = 'abandoned', detail = ?,"
            " payload_json = ? WHERE id = ? AND result = 'running'",
            (language.abandoned_run_line(row["started_utc"], marked_at,
                                         spec.silent_after_hours),
             json.dumps({"abandoned_utc": marked_at,
                         "silent_after_hours": spec.silent_after_hours,
                         "marked_by_task": by_task,
                         "marked_by_run": by_run}),
             row["id"]))
        if cursor.rowcount:
            marked.append(row["id"])
    if marked:
        conn.commit()
    return marked


def failed_for_want_of_a_model(conn: sqlite3.Connection, sport: str) -> bool:
    """Has a predict or final run of this sport been recorded failed because
    a market it asks has no model (`run.MarketNotTrained`)?

    Read from the words `run_task` above records a failure in -- the
    exception's class name, then its message -- so the writing and the
    reading sit in one module.

    WHY THE STRIP ASKS (GRIDIRON_REPAIR item 2, found by its prover on
    2026-09-26). The day strip listed a sport's untrained markets only once
    the record held a forecast of it, as it lists a hold. A sport whose
    first run meets no model writes nothing, so it never has one: the run
    failed by name on the Health panel while the first screen showed three
    ages, the daily run kept fresh by another sport -- the ruling's "fails by
    name, and the day strip shows it" kept by half.
    """
    from . import run

    return conn.execute(
        "SELECT 1 FROM task_runs WHERE task IN (?, ?) AND result = 'failed'"
        "   AND detail LIKE ? LIMIT 1",
        (f"predict:{sport}", f"final:{sport}",
         f"{run.MarketNotTrained.__name__}: %")).fetchone() is not None


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
            elif sport == "ufc":
                from .data import ufc_loader
                from .sports import ufc as ufc_adapter

                loaded = ufc_loader.load_season(conn, season)
                # THE BOUTS BECOME GAMES HERE, and only here. A prediction
                # references `games`, so a card that is loaded but not
                # mirrored is a card nothing can be asked about.
                loaded["mirrored"] = ufc_adapter.mirror_bouts(conn)
                loaded["undated_cards"] = getattr(ufc_adapter.mirror_bouts, "undated", 0)
                result = {"rows": loaded, "warnings": []}
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

    # THE OPENING READ (GRIDIRON_OPENING_READ, 2026-09-09), beside the second
    # look and deliberately after it: if a game is inside the near-start
    # window its ladder has just been read as the look that counts, and the
    # opening pass skips it by kickoff time rather than by luck of ordering.
    try:
        open_counts = _opening_read(conn)
    except Exception as exc:  # noqa: BLE001 - a venue outage is not a failed refresh
        warnings.append(f"opening read: {type(exc).__name__}: {exc}")
        open_counts = {"opening_read_due": 0, "opening_read_quotes": 0}

    payload = {"sports": list(counts), "resolvable_now": became_final,
               "warnings": warnings[:8], **drift_counts, **open_counts}
    if warnings:
        return ("ok" if counts else "failed",
                f"refreshed {language.counted(len(counts), 'sport')}; "
                f"{language.counted(became_final, 'prediction')} now "
                f"{'has' if became_final == 1 else 'have'} a finished game "
                f"waiting; {language.counted(len(warnings), 'warning')}",
                payload)
    if became_final == 0:
        return ("noop",
                "every sport re-read; no prediction's game has finished since "
                "the last refresh", payload)
    return ("ok",
            f"re-read {language.counted(len(counts), 'sport')}; "
            f"{language.counted(became_final, 'prediction')} now "
            f"{'has' if became_final == 1 else 'have'} a finished game waiting "
            "for the resolver", payload)


#: How close to the start a second look at the line is taken. Two hours is
#: late enough that most of the day's news is priced and early enough that the
#: fetch is not racing the first pitch.
NEAR_START_HOURS = 2.0

#: How stale an opening read may be before the slate is asked again
#: (GRIDIRON_OPENING_READ, 2026-09-09). Twelve hours, so a card carries a
#: price from this morning or last night rather than from whenever the game
#: was first seen -- and so the refresh, which fires every four hours, writes
#: about two ladders a day per game rather than six.
#:
#: THE OPEN IS NOT RE-DATED BY A RE-READ. Every row is kept and timestamped;
#: "the open" for drift is the EARLIEST one, and the card shows the latest.
#: Which read you mean is a query, not a state.
OPENING_READ_HOURS = 12.0


def _opening_read(conn: sqlite3.Connection) -> dict:
    """Ask the venue about the whole slate, not just the games about to start.

    WHY THIS EXISTS. Until today the venue was read in one place only -- the
    near-start pass, inside a two-hour window before kickoff. So an NFL card
    four days out said "no price yet" while the venue had the market open with
    twenty-five contracts on it, and the operator found that on his own
    screen. Measured 2026-09-09: the venue answers for NFL events sixteen days
    ahead. Nothing was asking.

    IT PRICES NOTHING. The rows go in as `read_kind='open'`, no claim is
    evaluated, and the at-the-line record cannot see them. The near-start read
    is untouched and stays the only look a claim may cite.
    """
    from .market import at_the_line

    # THE COLUMN BEFORE THE QUERY THAT READS IT. On the operator's own record
    # this is the first thing that touches `read_kind`, and the capture below
    # -- which also ensures it -- runs too late to help the SELECT.
    at_the_line.ensure_read_kind(conn)
    now = db.utcnow()
    horizon = _plus_hours(now, NEAR_START_HOURS)
    stale_before = _plus_hours(now, -OPENING_READ_HOURS)
    rows = conn.execute(
        "SELECT p.id FROM predictions p"
        " JOIN games g ON g.id = p.game_id"
        " WHERE g.status = 'scheduled'"
        # PAST THE NEAR-START WINDOW ONLY. Inside it the near-start pass is
        # already reading the same events, and its read is the one that
        # counts; two passes fetching the same ladder in the same minute
        # would double the rows and answer nothing extra. THE START AS AN
        # INSTANT (operator question 35, 2026-10-01): `julianday()` on both
        # sides and in the order, never the stored text.
        "   AND julianday(g.kickoff_utc) > julianday(?)"
        "   AND NOT EXISTS (SELECT 1 FROM venue_quotes v"
        "                   WHERE v.game_id = g.id AND v.read_kind = 'open'"
        "                     AND v.fetched_utc > ?)"
        " ORDER BY julianday(g.kickoff_utc)",
        (horizon, stale_before)).fetchall()
    if not rows:
        return {"opening_read_due": 0, "opening_read_quotes": 0}
    from .market import lines

    got = lines.read_the_venue_open(conn, [r["id"] for r in rows])
    return {"opening_read_due": len(rows),
            "opening_read_quotes": got["quotes"]}


def _run_near_start(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    """The second look at the line, as a task in its own right.

    `refresh` still calls the same pass, and that is deliberate: a second
    caller buys cadence and nothing else. The venue is re-read on every firing
    inside the window -- every open recommendation and every drift row -- and
    that is the point: the close is the LAST read before kickoff, so a pass
    that read once and stopped measured nothing (2026-09-23). The drift
    snapshot is still one per prediction; the schema holds that, not a filter.
    """
    counts = _near_start_snapshots(conn)
    due = counts.get("near_start_due", 0)
    if not due:
        # TWO DIFFERENT REASONS FOR DOING NOTHING, and they were reported as
        # one. At 19:00Z on the day this ran first, a game was kicking off at
        # 19:10 and the task said "no game starts within the next two hours":
        # the two predictions on it already had their second look, taken on an
        # earlier firing of the same clock. A task that misreports why it did
        # nothing is how a scheduler talks somebody out of trusting it.
        #
        # BY THE LISTED START, READ AS AN INSTANT, WHATEVER THE STATUS SAYS
        # (2026-09-30, GRIDIRON_REPAIR item 1, the close window). This counted
        # games still 'scheduled', by text; it counts the window the
        # selection reads now (`_near_start_selection`), so the words count
        # the games the firing would have read.
        soon = _games_starting_within(conn, db.utcnow())
        counts["near_start_games_in_window"] = soon
        # WHAT IT CLOSED, EVEN ON A NOOP (ruling 2026-09-08). The pass still
        # closes finished games on a firing with nothing near start, and a
        # detail line that said only "no game starts" would hide the one
        # thing this firing did.
        also = _closes_words(counts) + _unreadable_start_words(counts)
        if soon:
            return ("noop",
                    f"{language.counted(soon, 'game')} starts within the next "
                    f"{NEAR_START_HOURS:g} hours, and none of them carries a "
                    f"forecast with a line to read" + also, counts)
        return ("noop",
                f"no game starts within the next {NEAR_START_HOURS:g} hours"
                + also, counts)
    took = counts.get("near_start_taken", 0)
    asked = counts.get("near_start_asked", 0)
    quotes = counts.get("venue_near_start", 0)
    claims = counts.get("at_the_line_claims", 0)
    pairs = (f"; {language.counted(took, 'media line')} looked at a second "
             f"time" if took else "")
    # WHAT CAME BACK, not what was asked: a venue that does not answer writes
    # no quote now, and a line saying "read again" over nothing would hide it.
    return ("ok",
            f"{language.counted(asked, 'forecast')} asked at the line, "
            f"{language.counted(quotes, 'price')} came back; "
            f"{language.counted(claims, 'claim')} at the line"
            + pairs + _closes_words(counts) + _unreadable_start_words(counts),
            counts)


def _unreadable_start_words(counts: dict) -> str:
    """The forecasts a firing could not read because their game's listed
    start cannot be read as an instant, in words (2026-09-30, item 1's
    prover): named in the payload by `_near_start_selection`, and said in the
    detail line so a firing that left a game out never reads as one that left
    none out."""
    named = counts.get("near_start_unreadable_start") or []
    if not named:
        return ""
    games = len({row["game_id"] for row in named})
    return (f"; {language.counted(len(named), 'forecast')} not read: "
            f"the listed start of {language.counted(games, 'game')} cannot "
            f"be read as an instant")


def _closes_words(counts: dict) -> str:
    """What this firing closed, measured and not, in words."""
    shut = counts.get("closing_prices", 0)
    blind = counts.get("closing_unmeasured", 0)
    words = ""
    if shut:
        words += f"; {language.counted(shut, 'closing price')} recorded"
    if blind == 1:
        words += "; 1 closed with no later read of its own price, unmeasured"
    elif blind:
        words += (f"; {blind} closed with no later read of their own price, "
                  f"unmeasured")
    return words


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
    # RETIRED 2026-09-23 (GRIDIRON_REPAIR item 1): THE ONCE-THEN-EXCLUDE.
    #
    #     AND NOT EXISTS (SELECT 1 FROM market_snapshots n
    #                     WHERE n.prediction_id = p.id AND n.kind = 'near_start')
    #
    # stood in this query from the pass's first version and read each
    # prediction ONCE, then never again. With the `implied_prob IS NOT NULL`
    # join beside it, it did worse than that to the recommendations: every
    # recommended prediction had no media line (55 of 55), so none of them was
    # ever read inside the window at all, and the close -- "the last claim
    # before kickoff" -- was always the claim the price came from. 49 of 49
    # closes equalled the price paid; every closing-line value read 0.00c.
    #
    # REPLACED BY: every open recommendation inside the window, read at the
    # venue on EVERY firing until kickoff, whatever media line it had. A drift
    # row still gets its venue look once, with its media look: the drift pair
    # is one media snapshot each side (`market_snapshots_one_per_kind`, a
    # unique index, not a filter), and re-reading it every firing would only
    # multiply claims nothing reads.
    #
    # AND EVERY GAME UNTIL ITS LISTED START, WHATEVER ITS STATUS SAYS
    # (2026-09-30, the operator's ruling on the close window, GRIDIRON_REPAIR
    # item 1: "The near-start run keeps every game until its start, so the
    # close is the last read before the start"). The selection is
    # `_near_start_selection`, below, and it says why the status left.
    selected = _near_start_selection(conn, now)
    drift, recs = selected["drift"], selected["recs"]
    firsts = [pid for pid in drift if not conn.execute(
        "SELECT 1 FROM market_snapshots WHERE prediction_id = ?"
        "   AND kind = 'near_start'", (pid,)).fetchone()]

    # THE CLOSING LINE (R3, 2026-09-07), AND IT RUNS FIRST (ruling 2026-09-08).
    #
    # It sat below the early return until then, so a firing with no game
    # within two hours -- most firings, and every firing overnight -- left a
    # finished game's recommendation open until some unrelated game happened
    # to approach its own kickoff. Measured on a scratch copy at 02:40 PT on
    # 2026-09-08: two recommendations whose games were already final, zero
    # closed, because nothing else was near start.
    #
    # THE TWO SETS ARE DISJOINT, which is what makes this a move rather than a
    # rewrite: the rows above are games whose listed start is still ahead,
    # and the closer only touches recommendations whose start has passed --
    # both read as instants from 2026-09-30, and neither by the status (the
    # rows above were games still SCHEDULED, compared as text, until then).
    # Nothing is closed here that the second look would have priced.
    #
    # WHAT THE CLOSE IS, from 2026-09-23: the recommendation's own contract's
    # last near-start read before kickoff, or UNMEASURED where there is none
    # (`recommend.close_of`). Never the claim it was priced from.
    closed = lines.record_closing_prices(conn)
    closing = {"closing_prices": closed["closed"],
               "closing_unmeasured": closed["unmeasured"],
               "closing_still_open": closed["still_open"]}

    ids = sorted(set(drift) | set(recs))
    # A START NOBODY CAN READ, NAMED ON EVERY FIRING, read or not (2026-09-30,
    # item 1's prover): `_near_start_selection` says why.
    unreadable = {"near_start_unreadable_start": selected["unreadable_start"]}
    if not ids:
        return {"near_start_taken": 0, "near_start_failed": 0,
                "near_start_due": 0, "near_start_marked_under_way": [],
                **unreadable, **closing}

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
    #
    # THE MEDIA SNAPSHOT IS TAKEN ONCE: it is one half of a drift pair, and
    # the unique index would refuse a second. So only the rows without one are
    # refetched for it.
    refreshed = (lines.refresh_quotes(conn, firsts, ttl=espn.NEAR_START_TTL)
                 if firsts else 0)
    # THE VENUE'S LOOK (ruling D3, 2026-09-06): on EVERY firing for every open
    # recommendation, and with its media look for a drift row. Asked for by
    # shape, not by name -- the venue is named only inside the market module,
    # and the quarantine scan is what says so.
    looks = sorted(set(firsts) | set(recs))
    venue = (lines.refresh_venue_ladder(conn, looks) if looks
             else {"quotes": 0, "claims": 0})
    taken, failed = 0, 0
    for pid in firsts:
        try:
            lines.snapshot_prediction(conn, pid, kind="near_start")
            taken += 1
        except Exception:  # noqa: BLE001 - one bad quote must not stop the pass
            failed += 1
    return {"near_start_taken": taken, "near_start_failed": failed,
            "near_start_due": len(ids), "near_start_refetched": refreshed,
            "near_start_recommendations": len(recs),
            "near_start_asked": len(looks),
            "venue_near_start": venue["quotes"],
            "at_the_line_claims": venue["claims"],
            # WHAT THE STATUS SAID, KEPT (2026-09-30, item 1's close window):
            # the record holds only a game's current status, so the re-read
            # of 29 September could only INFER why fourteen baseball games
            # were left out five minutes before their start. Each forecast
            # this firing read while its game's status said it was under way
            # or over is named here, with that status and its listed start.
            "near_start_marked_under_way": selected["marked_under_way"],
            **unreadable, **closing}


def _near_start_selection(conn: sqlite3.Connection, now: str) -> dict:
    """Which forecasts the near-start pass reads at `now`: every drift row (a
    forecast whose media line was read at its first look) and every open,
    standing recommendation, whose game's LISTED START is after `now` and no
    more than `NEAR_START_HOURS` after it -- read as instants, WHATEVER THE
    GAME'S STATUS SAYS.

    THE OPERATOR'S RULING OF 2026-09-30 (GRIDIRON_REPAIR item 1, the close
    window): "The near-start run keeps every game until its start, so the
    close is the last read before the start." Until that date the pass kept
    a recommendation only while its game's status was 'scheduled' or 'pre'
    (the table has never held 'pre') and a drift row only while 'scheduled',
    each beside the listed start compared as text. Measured on one verified
    copy of the record (30 September, FOLLOWUPS "The close window"): 14 of
    the 19 measured baseball closes since item 1 were the read 35 minutes out
    (34.5 to 35.0), because the firing five minutes before each game's listed
    start left it out -- nine firings, fourteen recommendations, every one of
    them five minutes before its listed start and no other. The live poller
    maps statsapi's 'Live' to 'in' (`live.MLB_STATES`), its window opens ten
    minutes before a listed start (`live.WINDOW_LEAD`), and the league calls a
    game in its warm-up 'Live'; the record keeps no history of a game's
    status, so that is inferred. NFL (12 of 12) and NCAAF (7 of 8; the eighth
    a read whose venue answer lacked its contract) closed on the last firing
    before the start. So THE STATUS IS NOT CONSULTED AT ALL: warm-up, 'Live',
    'in', delayed, or 'final' before its time, a game is read until its
    listed start, and after it never. A start is read by `db.instant`, to the
    second or to the minute as stored, never compared as text (operator
    question 35, next in the order, stores and compares every start as an
    instant; this agrees with it).

    WHAT THE STATUS CHECK STOOD AGAINST, AND WHY IT GOES ANYWAY. Its comment
    named a game under way before its listed time (a doubleheader's second
    game), priced off the game rather than before it. The ruling reads every
    game until its listed start whatever its status says, so such a game is
    read, and its reads claimed, until then (FOLLOWUPS, "The close window":
    none is measurable on the record, which keeps no status history -- the
    payload below now does -- and the live poll only opens ten minutes before
    a listed start, so the check stood only in those minutes; the one
    doubleheader of the record's September whose two games are listed
    together, BAL at NYY on the 25th, lists them five minutes apart, 20:05Z
    and 20:10Z, so its second game's listed start was earlier than it was
    played, not later).

    A WITHDRAWN RECOMMENDATION IS NOT READ AGAIN (ruling 1, 2026-09-24): its
    close is never counted, so a look at its contract on every firing would
    spend a venue read and write a claim on a forecast nobody stands behind.

    A START NOBODY CAN READ STOPS NOTHING BUT ITSELF (2026-09-30, item 1's
    prover). As first built, one listed start `db.instant` refuses -- a feed
    that drops its zone ("2026-10-03T19:30:00"), a date with no time -- on ANY
    game a drift row or an open recommendation sits on, of any sport and any
    date, raised here, before the closer, and stopped the whole pass on every
    firing until the row was mended by hand: every other game, warm-up or
    not, left out until its start, and every finished game left unclosed --
    the left-out this ruling removes, made total. (No start on the record
    fails the parse on 30 September; no loader refuses one, and the games
    table has no rule on the column's form.) Such a forecast is not read --
    whether its start is ahead cannot be told, and it is never guessed -- and
    it is NAMED, with its listed start as stored, on every firing it would
    have been asked about (`unreadable_start`), so the record says which game
    was not read and why; every other game is read as the ruling says. The
    closer holds such a recommendation open (`recommend.
    record_closing_prices`: a start nobody can read is not one that has
    passed), and the claim writer writes no claim on such a game
    (`at_the_line.evaluate`'s `start_unreadable`).

    Returns the drift rows and the recommendations' forecasts (each sorted,
    each once), and every forecast among them whose game's status said it
    was under way or over, with that status and its listed start -- so the
    next firing that reads a game in its warm-up says so on the record -- and
    every candidate whose listed start cannot be read.
    """
    from .market import recommend

    at = db.instant(now)
    horizon = at + timedelta(hours=NEAR_START_HOURS)
    unreadable: dict[int, dict] = {}

    def ahead(row: sqlite3.Row) -> bool:
        try:
            when = db.instant(row["kickoff_utc"])
        except ValueError:
            unreadable[row["id"]] = {"prediction_id": row["id"],
                                     "game_id": row["game_id"],
                                     "listed_start": row["kickoff_utc"]}
            return False
        return when is not None and at < when <= horizon

    drift_rows = [r for r in conn.execute(
        "SELECT p.id, p.game_id, g.kickoff_utc, g.status FROM predictions p"
        " JOIN games g ON g.id = p.game_id"
        " JOIN market_snapshots o"
        "   ON o.prediction_id = p.id AND o.kind = 'open_at_predict'"
        " WHERE g.kickoff_utc IS NOT NULL"
        "   AND o.implied_prob IS NOT NULL").fetchall()
        if ahead(r)]
    rec_rows = [r for r in conn.execute(
        "SELECT DISTINCT r.prediction_id AS id, r.game_id, g.kickoff_utc,"
        "       g.status"
        "  FROM recommendations r"
        " JOIN games g ON g.id = r.game_id"
        " WHERE r.closed_utc IS NULL"
        "   AND g.kickoff_utc IS NOT NULL"
        + recommend.not_withdrawn(conn)).fetchall()
        if ahead(r)]
    marked: dict[int, dict] = {}
    for row in drift_rows + rec_rows:
        if row["status"] != "scheduled":
            marked[row["id"]] = {"prediction_id": row["id"],
                                 "game_id": row["game_id"],
                                 "status": row["status"],
                                 "listed_start": row["kickoff_utc"]}
    return {"drift": sorted({r["id"] for r in drift_rows}),
            "recs": sorted({r["id"] for r in rec_rows}),
            "marked_under_way": [marked[pid] for pid in sorted(marked)],
            "unreadable_start": [unreadable[pid]
                                 for pid in sorted(unreadable)]}


def _games_starting_within(conn: sqlite3.Connection, now: str) -> int:
    """How many games' listed starts fall after `now` and within
    `NEAR_START_HOURS` of it, read as instants, whatever their status says
    (2026-09-30, item 1's close window): the window `_near_start_selection`
    reads, counted for the words of a firing that read nothing. A start
    `db.instant` cannot read is not counted -- whether it is ahead cannot be
    told -- and never stops the count (2026-09-30, item 1's prover: as first
    built one such start among every game of the record raised here); the
    selection names any such game a forecast of its would have been read
    on."""
    at = db.instant(now)
    horizon = at + timedelta(hours=NEAR_START_HOURS)
    count = 0
    for row in conn.execute(
            "SELECT kickoff_utc FROM games WHERE kickoff_utc IS NOT NULL"):
        try:
            when = db.instant(row["kickoff_utc"])
        except ValueError:
            continue
        if when is not None and at < when <= horizon:
            count += 1
    return count


def _plus_hours(stamp: str, hours: float) -> str:
    when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc) + timedelta(hours=hours)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_recalibrate(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    """Re-fit every category's correction: one new version per category with
    settled forecasts (`correction.refit_all`), fitted from the fiftieth
    settled question and recorded as a placeholder below it, every one
    written INACTIVE. It measures nothing and puts nothing in force.

    WHAT IT DOES, SAID TRUE (operator question 32, ruled 2026-09-29: "The
    recalibration task never activates anything; fix its docstring to say
    what it does"). Until that release this docstring said "Writes versions;
    activates nothing" while the refit it calls set `active_from` on any fit
    whose point holdout check passed -- which is how fit 71 came into force
    from this task at 2026-09-28T13:00:01Z (task run 6173). A correction now
    comes into force only by its own dated row in `correction_activations`,
    written when its measurement clears the gate
    (`tools/correction_holdout.py`), never by this task.

    Reports in the same voice as the gates elsewhere: a category under the
    threshold says how far off it is, because "no correction" and "not enough
    record yet" are different states and the panel must not show them alike.
    """
    from . import correction

    report = correction.refit_all(conn)
    if not report["n"]:
        return "noop", "nothing has settled yet, so there is nothing to fit", report
    # QUESTIONS, FROM QUESTION 16'S RELEASE (2026-09-29): a category is
    # eligible at fifty settled questions, each counted once, where this
    # counted settled forecasts.
    detail = (f"fitted {report['n']} categor"
              f"{'y' if report['n'] == 1 else 'ies'}; "
              f"{report['eligible']} had at least {correction.MIN_TRAIN} "
              f"settled questions")
    return ("ok" if report["eligible"] else "noop"), detail, report


def settle_everything(conn: sqlite3.Connection, *, progress=None) -> dict:
    """Settle the predictions, then the at-the-line claims that came of them.

    ONE DOOR, AND IT IS THIS ONE. `resolve.resolve_all` cannot do the second
    half itself: a sport adapter imports that module, which puts it inside a
    prediction closure, and nothing inside a closure may name the market
    package -- the planted violation proved it by name the first time this was
    written the other way round. So the pair lives here, where the scheduler,
    the CLI and the live poll already are.

    The counts are returned together because a claim that settled on a
    different pass than its own prediction would let the two records disagree
    about which games have finished.
    """
    from . import resolve
    from .market import at_the_line

    result = resolve.resolve_all(conn, progress=progress)
    claims = at_the_line.resolve_claims(conn)
    # THE PRICED ROWS TAKE THE SAME OUTCOME, copied rather than judged again:
    # two forecasters answered one question about one game, and if they could
    # disagree about what happened every comparison between them would mean
    # nothing.
    from .priced import forecast as priced

    priced_settled = priced.resolve_forecasts(conn)
    result["at_the_line_settled"] = claims["settled"]
    result["at_the_line_open"] = claims["still_open"]
    result["at_the_line_unanswerable"] = claims["unanswerable_level_game"]
    result["priced_settled"] = priced_settled["settled"]
    return result


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

    settled = settle_everything(conn)
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
    return "ok", f"settled {language.counted(n, 'prediction')}", payload


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
    report = live.poll(conn, resolver=settle_everything)
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


def _run_capture(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    """Stamp what is knowable now, so it can be measured later (S1)."""
    from . import capture

    try:
        counts = capture.run(conn)
    except capture.NothingCaptured as exc:
        return "failed", str(exc), {}
    total = sum(counts.values())
    if not total:
        return ("noop",
                "nothing to capture: no injury report and no posted lineup",
                counts)
    return ("ok",
            f"stamped {counts['injuries']} injury row(s) and "
            f"{counts['lineups']} lineup slot(s)",
            counts)


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
                f"the {config.SPORT_LABELS.get(sport, sport.upper())} slate of "
                f"{_slate_words(conn, sport, season, missed['week'])} began at "
                f"{missed['first']} and was not forecast. It is NOT being "
                "forecast now: a question answered after its games have started "
                "is not a forecast, and answering it late would permanently "
                "occupy the slot the real one should have had.",
                missed,
            )
        return "noop", f"no upcoming {sport} slate is scheduled", {}

    try:
        result = run.run_slate(conn, sport, season, week, use_llm=use_llm)
    except run.SlateAlreadyAnswered as refused:
        # A REFUSED RERUN IS A NOOP, NOT A FAILURE (GRIDIRON_REPAIR item 7,
        # the operator's ruling of 2026-09-23: "SlateAlreadyAnswered is a
        # noop, not a failure"). The refusal is the record keeping a slate
        # answered once, and `noop` is the ledger's own word for it: "it ran
        # and there was correctly nothing to do". Until 2026-09-26 it was
        # recorded 'failed' -- 90 of the 114 failed rows on the record that
        # day, every one of the 18 catch-ups that ever finished called
        # failed for it alone, and each one raising the failure notice -- so
        # a real failure sat unseen among them.
        #
        # EXACTLY THIS CLASS, never `RuntimeError`, which it subclasses: a
        # run that fails for want of a model (`run.MarketNotTrained`) and any
        # other fault stay failures. Item 2 made the refusal honest first --
        # a market the run asks and cannot answer keeps the slate open, so a
        # refusal now means every market it asks is answered. The run's own
        # `run_slate` still raises it; only the scheduled task's record
        # changes.
        #
        # THE SLATE IN WORDS, never the refusal's text, which names it by
        # key ("slate 180"); and no "week" in the payload, which the slate
        # card reads to find the run that wrote it (`views._below_floor`).
        answered = run.already_answered(conn, sport, season, week)
        if refused.final_pass_answered:
            # AN EARLY PASS LEFT WITH NOTHING TO WRITE BUT QUESTIONS WHOSE
            # FINAL PASS IS WRITTEN (operator question 27, ruled 2026-09-28,
            # built 2026-09-29: "it is a SlateAlreadyAnswered noop"). The same
            # class, so the same record; its own words, because "every market
            # this run asks" is not what happened -- a market may have had no
            # row, which is what kept the slate open. The questions are named
            # in the payload, and their count is its length.
            return (
                "noop",
                f"the {config.SPORT_LABELS.get(sport, sport.upper())} slate "
                f"of {_slate_words(conn, sport, season, week)} had nothing "
                "left for an early forecast to answer: "
                f"{language.final_pass_answered_words(len(refused.final_pass_answered))}"
                ". Nothing was written.",
                {"refused_slate": week, "already_written": answered["written"],
                 "final_pass_answered": refused.final_pass_answered},
            )
        return (
            "noop",
            f"the {config.SPORT_LABELS.get(sport, sport.upper())} slate of "
            f"{_slate_words(conn, sport, season, week)} already has "
            f"{language.counted(answered['written'], 'forecast')} in every "
            "market this run asks. A slate is answered once, so this rerun "
            "was refused and nothing was written.",
            {"refused_slate": week, "already_written": answered["written"]},
        )
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
        # WHAT THE PASS RECOMMENDED AND WHAT IT KEPT OFF THE RECORD, with
        # why in words (GRIDIRON_REPAIR item 5, 2026-09-26): a pick refused
        # as a second on its game and market, or because the pass took both
        # sides of one, is said, and kept with the run that refused it.
        "recommended": result.get("recommended"),
        # EVERY QUESTION NOT ANSWERED BECAUSE ITS FINAL PASS IS WRITTEN, BY
        # NAME (operator question 27, 2026-09-29): the run wrote the others
        # and skipped these; the list's length is the count, and the detail
        # says it in words.
        "final_pass_answered": result.get("final_pass_answered") or [],
    }
    floor_note = (
        f"; {language.counted(result['below_floor'], 'prop question')} "
        f"{'was' if result['below_floor'] == 1 else 'were'} below the "
        f"{round(config.PROPS_MIN_CLAIM * 100)}% confidence floor and not asked"
        if result.get("below_floor") else ""
    )
    if result.get("final_pass_answered"):
        floor_note += ("; " + language.final_pass_answered_words(
            len(result["final_pass_answered"])))
    if written == 0:
        return (
            "noop",
            "every question on this slate was already answered" + floor_note,
            payload,
        )
    return ("ok",
            f"wrote {language.counted(written, 'prediction')} for "
            f"{_slate_words(conn, sport, season, week)}{floor_note}", payload)


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


def final_pass_window(conn: sqlite3.Connection, sport: str, season: int,
                      week: int, now: str) -> dict | None:
    """When a final pass that FIRES BY ITS LEAD may write for this slate
    (operator question 35, ruled 2026-09-30: "move that schedule so every
    final pass lands before its start"; built 2026-10-01); None for a sport
    whose installer's wall-clock triggers decide (`FinalPass.fires_by_lead`).

    THE WINDOW is `minutes_before_first` before the slate's FIRST START STILL
    AHEAD, each start read as an instant (`db.instant`) -- the first bout of
    a card whose prelims have not begun, its main card's once they have --
    until that start. `open` says whether `now` is inside it; `first` and
    `opens` are written in the one stored form. No start still ahead that
    can be read: `first` None, and the window is shut (a start nobody can
    read is never guessed into one).
    """
    spec = config.FINAL_PASS.get(sport)
    if (spec is None or not spec.fires_by_lead
            or spec.minutes_before_first is None):
        return None
    at = db.instant(now)
    ahead = []
    for (stamp,) in conn.execute(
            "SELECT kickoff_utc FROM games WHERE sport = ? AND season = ?"
            "   AND week = ? AND kickoff_utc IS NOT NULL",
            (sport, season, week)).fetchall():
        try:
            start = db.instant(stamp)
        except ValueError:
            continue
        if start is not None and start > at:
            ahead.append(start)
    if not ahead:
        return {"open": False, "first": None, "opens": None,
                "minutes": spec.minutes_before_first}
    first = min(ahead)
    opens = first - timedelta(minutes=spec.minutes_before_first)
    return {"open": at >= opens, "first": first.strftime(db.INSTANT_FORM),
            "opens": opens.strftime(db.INSTANT_FORM),
            "minutes": spec.minutes_before_first}


def _run_final_pass(conn: sqlite3.Connection, sport: str, *, use_llm: bool) -> tuple[str, str, dict]:
    """Forecast the next slate AGAIN, close to start (config.FINAL_PASS).

    The rows this writes supersede the early ones as the standing forecast.
    The early rows are kept and labelled; nothing is edited or deleted.

    A SPORT WHOSE FINAL PASS FIRES BY ITS LEAD (UFC, from 2026-10-01:
    operator question 35) is fired every thirty minutes by the installer and
    writes only inside its window (`final_pass_window`): a firing before the
    window is a noop that says when it opens. And whatever fires it, no pass
    is written at or after its game's start: `predict.write_prediction`
    refuses the row at its own stamp, read as an instant.
    """
    from . import run, sports

    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    adapter = sports.get(sport)
    week = adapter.next_slate(conn, season)
    window = (final_pass_window(conn, sport, season, week, db.utcnow())
              if week is not None else None)
    if window is not None and not window["open"]:
        slate = _slate_words(conn, sport, season, week)
        if window["first"] is None:
            return ("noop",
                    f"the {sport} final pass found no start still ahead on "
                    f"{slate} that can be read; nothing was written",
                    {"week": week, "window_opens": None,
                     "first_start_ahead": None})
        return ("noop",
                f"the {sport} final pass for {slate} waits for its window: it "
                f"writes from {window['opens']}, {window['minutes']} minutes "
                f"before its first start still ahead ({window['first']}); "
                f"nothing was written",
                {"week": week, "window_opens": window["opens"],
                 "first_start_ahead": window["first"]})
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
        # And here, for the same reason (item 5, 2026-09-26): the final pass
        # is where a second on a morning's game and market is refused.
        "recommended": result.get("recommended"),
    }
    if written == 0:
        return ("noop",
                f"the final pass found nothing new to write for "
                f"{_slate_words(conn, sport, season, week)}"
                + (f"; {fetch_note}" if fetch_note else ""),
                payload)
    return ("ok",
            f"re-forecast {language.counted(written, 'question')} for "
            f"{_slate_words(conn, sport, season, week)} close to start; these "
            f"supersede the early rows"
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
    # STARTS AS INSTANTS (operator question 35, ruled 2026-09-30, built
    # 2026-10-01): `julianday()` on both sides of each bound, and the slate's
    # first start the earliest instant, written back in the one stored form
    # -- never the stored text, where a UFC start to the minute ("...T19:00Z")
    # sorted after a clock to the second of the same minute.
    started = conn.execute(
        "SELECT g.week, strftime('%Y-%m-%dT%H:%M:%SZ',"
        "                        MIN(julianday(g.kickoff_utc))) AS first_game"
        "  FROM games g"
        " WHERE g.sport = ? AND g.season = ? AND g.kickoff_utc IS NOT NULL"
        "   AND julianday(g.kickoff_utc) <= julianday(?)"
        "   AND julianday(g.kickoff_utc) >= julianday(?)"
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
    """The most recent slate that started without being forecast.

    Starts read as instants (operator question 35, 2026-10-01), as
    `_record_missed_slates` reads them."""
    row = conn.execute(
        "SELECT g.week, strftime('%Y-%m-%dT%H:%M:%SZ',"
        "                        MIN(julianday(g.kickoff_utc))) AS first"
        "  FROM games g"
        " WHERE g.sport = ? AND g.season = ? AND g.kickoff_utc IS NOT NULL"
        "   AND julianday(g.kickoff_utc) <= julianday(?)"
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

def _run_catch_up(conn: sqlite3.Connection, *, use_llm: bool) -> tuple[str, str, dict]:
    """The catch-up as one row of its own, wrapping the rows of what it ran."""
    runs = catch_up(conn, use_llm=use_llm)
    results = [r["result"] for r in runs]
    if "failed" in results:
        result = "failed"
    elif "ok" in results:
        result = "ok"
    else:
        result = "noop"
    detail = (f"ran {language.counted(len(runs), 'task')}: "
              + ", ".join(f"{language.task_name(r['task'])} {r['result']}" for r in runs))
    return result, detail, {"runs": [{"task": r["task"], "result": r["result"],
                                       "detail": r["detail"]} for r in runs]}


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
            "last_detail": language.task_detail_words(last["detail"]) if last else None,
            "missed": [{**dict(m), "detail": language.task_detail_words(m["detail"])}
                       for m in missed],
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
            # A ROW WITH NO ENDING. Past the scheduler's own two-hour limit
            # on a task, a 'running' row is a run that died -- killed, or the
            # machine slept -- and the panel says so rather than showing the
            # last good ending as if nothing had happened since. An
            # 'abandoned' row is the same run, marked by a later one past its
            # task's silence (GRIDIRON_REPAIR item 7, 2026-09-26): it still
            # never recorded an ending, and the panel still says so.
            if last["result"] in ("running", "abandoned") and age > RUN_CEILING_HOURS:
                entry["unfinished"] = True
                entry["warning"] = language.unfinished_run_line(age)
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
