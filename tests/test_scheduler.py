"""P2: the appliance, and whether it tells the truth about itself.

The tests that matter here are not "does the task run". They are:

  * a slate that started without being forecast is recorded MISSED and is
    NEVER forecast late — the voided-rows lesson made structural;
  * resolve is idempotent, because a four-hourly schedule runs it six times a
    day and the second run of an hour must change nothing;
  * a task that fails is RECORDED as failed rather than raising into the
    scheduler, where the only trace would be an exit code nobody reads;
  * the panel says a task is silent when it is, because a status board that
    looks calm while the appliance is dead is worse than no board at all.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from gridiron import audit, config, db, language, tasks


@pytest.fixture
def mlb_season(monkeypatch):
    """Point the tasks at the fixture's season.

    Without this the task reads SPORT_CURRENT_SEASON (2026), looks at a season
    the fixture has no games in, finds nothing, and the test passes while
    exercising none of the logic it claims to. Two of these did exactly that.
    """
    seasons = dict(config.SPORT_CURRENT_SEASON)
    seasons["mlb"] = 2025
    monkeypatch.setattr(config, "SPORT_CURRENT_SEASON", seasons)
    return 2025


# --- the ledger -------------------------------------------------------------

def test_a_run_is_recorded_whatever_happens(league):
    tasks.run_task(league, "resolve", use_llm=False)
    row = league.execute(
        "SELECT * FROM task_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["task"] == "resolve"
    assert row["result"] in ("ok", "noop")
    assert row["finished_utc"] >= row["started_utc"]


def test_the_ledger_is_append_only(league):
    tasks.run_task(league, "resolve", use_llm=False)
    with pytest.raises(sqlite3.IntegrityError):
        league.execute("DELETE FROM task_runs")


def test_a_failing_task_is_recorded_not_raised(league, monkeypatch):
    """The scheduler's only channel is an exit code. A task that raises leaves
    no explanation anywhere a person will look, so the failure is caught,
    written down with its traceback, and reported in the panel."""
    def boom(conn):
        raise RuntimeError("the source went away")

    monkeypatch.setattr(tasks, "_run_resolve", boom)
    result = tasks.run_task(league, "resolve", use_llm=False)
    assert result["result"] == "failed"
    assert "the source went away" in result["detail"]

    row = league.execute(
        "SELECT * FROM task_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["result"] == "failed"
    assert "Traceback" in json.loads(row["payload_json"])["traceback"]


def test_an_unknown_task_is_refused_by_name(league):
    with pytest.raises(ValueError, match="unknown task"):
        tasks.run_task(league, "predict:cricket")


# --- idempotence, which is what makes a four-hourly schedule safe -----------

def test_resolve_run_twice_settles_nothing_the_second_time(league, monkeypatch):
    from gridiron import run
    from gridiron.factors import store
    from gridiron.model import activation, baseline
    from tests.conftest import asks_only

    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    asks_only(monkeypatch, "nfl", "spread")     # a spread world (item 2)
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    first = tasks.run_task(league, "resolve", use_llm=False)
    second = tasks.run_task(league, "resolve", use_llm=False)
    assert first["settled"] > 0, "the fixture should have something to settle"
    assert second["settled"] == 0
    assert second["result"] == "noop"


# --- the missed slate, which is the whole point ----------------------------

def test_a_slate_that_started_unforecast_is_recorded_missed(mlb_league, mlb_season):
    """Simulated directly: predict one slate so the appliance has a start date,
    then let a LATER slate begin without being forecast."""
    # The appliance starts running: its first forecast is two days ago.
    db.set_meta(mlb_league, "kind", "live")
    mlb_league.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) SELECT ?, 'mlb', id, 'moneyline', home, 0.55,"
        " 'win', 'statistical', 'fs2', '{}', 'x' FROM games"
        " WHERE sport='mlb' AND week = 1 LIMIT 1",
        (_hours_ago(48),),
    )
    # ...and then a slate began YESTERDAY without being forecast. Dating it
    # before the first prediction would be excluded on purpose: the appliance
    # cannot miss what it was not yet running for.
    mlb_league.execute(
        "UPDATE games SET kickoff_utc = ? WHERE sport='mlb' AND week = 5",
        (_hours_ago(24),),
    )
    mlb_league.commit()

    tasks._record_missed_slates(mlb_league, "mlb")
    missed = mlb_league.execute(
        "SELECT * FROM task_runs WHERE result = 'missed'"
    ).fetchall()
    assert missed, "a slate that started unforecast was not recorded"
    assert "was not forecast" in missed[0]["detail"]
    assert "NOT being forecast now" in missed[0]["detail"]


def test_a_missed_slate_is_never_forecast_late(mlb_league, mlb_season):
    """The rule that cost 47 NBA rows and 6 MLB ones, made structural. A
    question once answered is never re-asked, so a late answer permanently
    occupies the slot the real forecast should have had."""
    db.set_meta(mlb_league, "kind", "live")
    mlb_league.execute(
        "UPDATE games SET kickoff_utc = ? WHERE sport='mlb' AND week = 5",
        (_hours_ago(24),),
    )
    mlb_league.commit()

    tasks.run_task(mlb_league, "predict:mlb", use_llm=False)

    after = mlb_league.execute(
        "SELECT COUNT(*) FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport='mlb' AND g.week = 5"
    ).fetchone()[0]
    assert after == 0, "a slate that had already started was forecast anyway"


def test_the_same_missed_slate_is_not_mourned_twice(mlb_league, mlb_season):
    db.set_meta(mlb_league, "kind", "live")
    mlb_league.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) SELECT ?, 'mlb', id, 'moneyline', home, 0.55,"
        " 'win', 'statistical', 'fs2', '{}', 'x' FROM games"
        " WHERE sport='mlb' AND week = 1 LIMIT 1",
        (_hours_ago(48),),
    )
    mlb_league.execute(
        "UPDATE games SET kickoff_utc = ? WHERE sport='mlb' AND week = 5",
        (_hours_ago(24),),
    )
    mlb_league.commit()

    tasks._record_missed_slates(mlb_league, "mlb")
    first = mlb_league.execute(
        "SELECT COUNT(*) FROM task_runs WHERE result='missed'"
    ).fetchone()[0]
    tasks._record_missed_slates(mlb_league, "mlb")
    second = mlb_league.execute(
        "SELECT COUNT(*) FROM task_runs WHERE result='missed'"
    ).fetchone()[0]
    assert first == second, "the same missed slate was recorded twice"


def test_nothing_before_the_first_prediction_counts_as_missed(mlb_league, mlb_season):
    """The appliance was not running before its first forecast, and calling
    every game in history 'missed' would be noise pretending to be a finding."""
    mlb_league.execute("DELETE FROM prediction_voids")
    mlb_league.commit()
    assert tasks._record_missed_slates(mlb_league, "mlb") == []


# --- catch-up ---------------------------------------------------------------

def test_catch_up_refreshes_then_resolves_and_records_every_sport(league):
    """REFRESH FIRST, then resolve. The order is not cosmetic: the resolver
    settles against `games.status`, so resolving before re-reading the results
    settles nothing and reports `noop` truthfully. In its earlier form -- no
    refresh task at all -- that stalled the record for two days while every
    task reported success."""
    results = tasks.catch_up(league, use_llm=False)
    assert results[0]["task"] == "refresh"
    assert results[1]["task"] == "resolve"
    # Derived from the declared sports. The fourth literal list in this suite
    # to go stale when a sport was added.
    assert {r["task"] for r in results} == {"refresh", "resolve"} | {
        f"predict:{s}" for s in config.SPORTS
    }
    assert all(r["result"] in ("ok", "noop", "missed", "failed") for r in results)


# --- the panel --------------------------------------------------------------

def test_a_task_that_has_never_run_says_so_rather_than_showing_blank(conn):
    status = tasks.status(conn)
    for task in status["tasks"]:
        assert task["last_run_utc"] is None
        assert task["silent"] is True
        assert "never run" in task["warning"]


def test_a_silent_task_is_reported_as_silent(league):
    league.execute(
        "INSERT INTO task_runs (task, started_utc, finished_utc, result, detail)"
        " VALUES ('resolve', '2020-01-01T00:00:00Z', '2020-01-01T00:00:01Z',"
        " 'ok', 'long ago')"
    )
    league.commit()
    entry = next(t for t in tasks.status(league)["tasks"] if t["task"] == "resolve")
    assert entry["silent"] is True
    assert "has not run for" in entry["warning"]
    assert entry["next_due_utc"] < db.utcnow(), "an overdue task must read overdue"


def test_the_panel_carries_the_staleness_line(league):
    status = tasks.status(league)
    assert "schedule_staleness" in status
    # Derived from the declared sports, not listed. The literal went stale the
    # moment college football was added, which is the third test in this suite
    # to do that.
    assert ({s["sport"] for s in status["schedule_staleness"]["sports"]}
            == set(config.SPORTS))


def test_every_declared_task_appears_in_the_panel(league):
    reported = {t["task"] for t in tasks.status(league)["tasks"]}
    assert reported == set(tasks.TASKS)


def _hours_ago(n: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(hours=n)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )



# --- one list of tasks (audit 2026-09-05) -----------------------------------

def test_every_task_is_installable_and_worded():
    """tasks.TASKS, scheduler.OS_TASK_NAMES, language.TASK_WORDS and the
    installer disagreed four ways: the UFC passes existed only in the first
    and third, `live` was named on the scheduler and registered nowhere, and
    CatchUp was registered and named nowhere. Three lists that describe one
    appliance are held together here."""
    from pathlib import Path

    from gridiron import language, scheduler

    script = (Path(config.REPO_ROOT) / "tools" / "schedule_install.ps1").read_text(
        encoding="utf-8")
    names_block = script.split("$TaskNames = @(")[1].split(chr(10) + ")")[0]
    for task in tasks.TASKS:
        assert task in language.TASK_WORDS, f"{task} would reach the panel as a key"
        assert task in scheduler.OS_TASK_NAMES, f"{task} has no name on the scheduler"
        if task in scheduler.NOT_INSTALLED:
            continue
        suffix = scheduler.OS_TASK_NAMES[task]
        assert f'"$($Prefix){suffix}"' in script, f"the installer never registers {suffix}"
        assert f'TaskArg "{task}"' in script, f"the installer registers {suffix} for the wrong task"
        assert suffix in names_block, f"an uninstall would orphan {suffix}"
    for task, why in scheduler.NOT_INSTALLED.items():
        assert task in tasks.TASKS and why, task
    # And the other way: nothing on the scheduler that the app does not know.
    for task, suffix in scheduler.OS_TASK_NAMES.items():
        assert task in tasks.TASKS, (
            f"{suffix} is named on the scheduler and is not a task")



# --- the record precedes the run (audit 2026-09-05) ---------------------------

def test_a_killed_run_leaves_a_row_with_no_ending(league, monkeypatch):
    """Gridiron-Refresh died at 03:00Z on 2026-09-05 and the ledger had no
    row. A KeyboardInterrupt is what a control-C exit looks like from here."""
    def killed(conn):
        raise KeyboardInterrupt
    monkeypatch.setattr(tasks, "_run_refresh", killed)
    with pytest.raises(KeyboardInterrupt):
        tasks.run_task(league, "refresh", use_llm=False)
    row = league.execute(
        "SELECT * FROM task_runs WHERE task = 'refresh' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["result"] == "running"
    assert row["finished_utc"] is None


def test_a_run_with_no_ending_is_said_so_on_the_panel(league, monkeypatch):
    from datetime import datetime, timedelta, timezone

    def killed(conn):
        raise KeyboardInterrupt
    monkeypatch.setattr(tasks, "_run_refresh", killed)
    with pytest.raises(KeyboardInterrupt):
        tasks.run_task(league, "refresh", use_llm=False)
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    league.execute("UPDATE task_runs SET started_utc = ? WHERE result = 'running'", (stale,))
    league.commit()
    entry = next(t for t in tasks.status(league)["tasks"] if t["task"] == "refresh")
    assert entry["unfinished"] is True
    assert "never recorded an ending" in entry["warning"]


def test_a_finished_run_finishes_its_own_row(league):
    out = tasks.run_task(league, "resolve", use_llm=False)
    rows = league.execute(
        "SELECT result, finished_utc FROM task_runs WHERE task = 'resolve'"
    ).fetchall()
    assert len(rows) == 1, "a run must be one row, started then finished"
    assert rows[0]["result"] == out["result"] and rows[0]["finished_utc"]


def test_an_older_ledger_is_widened_to_admit_running(tmp_path):
    conn = db.open_db(tmp_path / "old.db")
    try:
        conn.executescript(
            "DROP TABLE task_runs;"
            "CREATE TABLE task_runs ("
            " id INTEGER PRIMARY KEY, task TEXT NOT NULL, started_utc TEXT NOT NULL,"
            " finished_utc TEXT, result TEXT NOT NULL"
            " CHECK (result IN ('ok', 'noop', 'missed', 'failed')),"
            " detail TEXT, payload_json TEXT);")
        conn.execute(
            "INSERT INTO task_runs (task, started_utc, finished_utc, result)"
            " VALUES ('refresh','2026-01-01T00:00:00Z','2026-01-01T00:01:00Z','ok')")
        conn.commit()
        assert db.widen_task_run_results(conn) is True
        ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='task_runs'").fetchone()[0]
        assert "'running'" in ddl
        assert conn.execute("SELECT COUNT(*) FROM task_runs").fetchone()[0] == 1
        assert db.widen_task_run_results(conn) is False
    finally:
        conn.close()


def test_the_guard_sees_a_run_recorded_only_when_it_ends():
    from pathlib import Path

    from gridiron import audit

    source = (Path(config.PACKAGE_ROOT) / "tasks.py").read_text(encoding="utf-8")
    assert audit.task_run_order_faults(source) == []
    late = source.replace("INSERT INTO task_runs (task, started_utc, result, detail)",
                          "INSERT INTO task_runs_later (task, started_utc, result, detail)", 1)
    assert late != source
    faults = audit.task_run_order_faults(late)
    assert faults and "before the task runs" in faults[0]


# --- catch-up on the panel (ruling 5 on the audit, 2026-09-05) ---------------

def test_catch_up_is_a_task_with_a_row_of_its_own(league):
    out = tasks.run_task(league, "catch-up", use_llm=False)
    assert out["task"] == "catch-up" and out["result"] in ("ok", "noop")
    own = league.execute(
        "SELECT result, detail FROM task_runs WHERE task = 'catch-up'").fetchall()
    assert len(own) == 1 and own[0]["result"] == out["result"]
    assert "Fetch results" in own[0]["detail"] and "Settle picks" in own[0]["detail"]
    inner = league.execute(
        "SELECT COUNT(*) FROM task_runs WHERE task IN ('refresh', 'resolve')").fetchone()[0]
    assert inner == 2, "the catch-up's own row does not replace the rows of what it ran"
    entry = next(t for t in tasks.status(league)["tasks"] if t["task"] == "catch-up")
    assert entry["last_result"] == out["result"]
    assert ":" not in entry["task_label"] and "catch" not in entry["task_label"].lower() or entry["task_label"]


# --- THE JOBS (GRIDIRON_REPAIR item 7, the operator's ruling of 2026-09-23) ----
#
# "SlateAlreadyAnswered is a noop, not a failure; the run_task closing UPDATE
# moves inside the try and a hung 'running' row older than its task's
# silent_after_hours is marked abandoned; every Gridiron-* task gains
# WakeToRun." Built 2026-09-26. Every test that can take the failure path
# keeps the notice off the desktop.

#: A fixed instant for the sweep, so no test here reads the clock.
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def _at(hours_before: float) -> str:
    return (NOW - timedelta(hours=hours_before)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(conn, task, started, result="running", finished=None,
         detail="started; no ending recorded yet"):
    return conn.execute(
        "INSERT INTO task_runs (task, started_utc, finished_utc, result, detail)"
        " VALUES (?, ?, ?, ?, ?)", (task, started, finished, result, detail)).lastrowid


def _a_slate_two_days_out(conn, sport="nfl", week=3):
    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    kickoff = datetime.now(timezone.utc) + timedelta(hours=48)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away,"
        " kickoff_utc, status, league_date) VALUES (?, ?, ?, ?, 'REG', 'HOM',"
        " 'AWY', ?, 'scheduled', ?)",
        (f"{sport}_item7_{week}", sport, season, week,
         kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"), kickoff.strftime("%Y-%m-%d")))
    conn.commit()
    return season


def test_a_refused_rerun_is_a_noop_and_every_other_fault_still_fails(conn, monkeypatch):
    import re

    from gridiron import run

    monkeypatch.setenv("GRIDIRON_NOTIFY_FAILURES", "0")
    season = _a_slate_two_days_out(conn)

    def refuses(*_args, **_kwargs):
        raise run.SlateAlreadyAnswered(
            f"nfl {season} slate 3 already has 35 forecasts in every market it "
            f"asks (moneyline, prop, spread, total). A slate is answered once.")

    monkeypatch.setattr(run, "run_slate", refuses)
    out = tasks.run_task(conn, "predict:nfl", use_llm=False)
    stored = conn.execute("SELECT * FROM task_runs WHERE task = 'predict:nfl'"
                          " ORDER BY id DESC LIMIT 1").fetchone()
    assert out["result"] == stored["result"] == "noop"
    assert stored["finished_utc"]
    detail = stored["detail"]
    assert detail.startswith("the NFL slate of Week 3, ") and "refused" in detail
    assert re.search(r"\bslate \d", detail) is None, detail
    assert audit_plain(detail) == [], detail
    payload = json.loads(stored["payload_json"])
    assert payload == {"refused_slate": 3, "already_written": 0}
    assert '"week"' not in stored["payload_json"], "the slate card reads that key"
    # EXACTLY THE ONE CLASS: what it subclasses, and its sibling, still fail.
    for fault in (RuntimeError("the source went away"),
                  run.MarketNotTrained("no model", markets=[], result={})):
        def raises(*_args, _fault=fault, **_kwargs):
            raise _fault
        monkeypatch.setattr(run, "run_slate", raises)
        assert tasks.run_task(conn, "predict:nfl", use_llm=False)["result"] == "failed"


def audit_plain(text):
    return audit.plain_words_violations(language.task_detail_words(text))


def test_a_catch_up_is_not_failed_by_a_member_that_correctly_refuses(conn, monkeypatch):
    """ALL 18 CATCH-UPS THAT EVER FINISHED WERE 'failed' for this alone
    (measured read-only on 2026-09-26)."""
    from gridiron import run

    monkeypatch.setenv("GRIDIRON_NOTIFY_FAILURES", "0")
    for sport in config.SPORTS:
        _a_slate_two_days_out(conn, sport, week=3)
    monkeypatch.setattr(tasks, "_run_refresh", lambda c: ("noop", "stubbed", {}))
    monkeypatch.setattr(tasks, "_run_resolve", lambda c: ("noop", "stubbed", {}))

    def refuses(conn_, sport, *_args, **_kwargs):
        raise run.SlateAlreadyAnswered(f"{sport} slate answered once")

    monkeypatch.setattr(run, "run_slate", refuses)
    out = tasks.run_task(conn, "catch-up", use_llm=False)
    members = {r["task"]: r["result"] for r in out["runs"]}
    assert "failed" not in members.values(), members
    assert out["result"] == "noop"
    assert conn.execute("SELECT COUNT(*) FROM task_runs WHERE result = 'failed'"
                        ).fetchone()[0] == 0


def test_a_hung_run_past_its_own_silence_is_marked_abandoned_once(conn):
    ids = {
        "refresh_hung": _row(conn, "refresh", _at(13)),       # past refresh's 12
        "refresh_young": _row(conn, "refresh", _at(3)),       # past two hours only
        "nfl_hung": _row(conn, "predict:nfl", _at(217)),      # past the NFL's 216
        "nfl_young": _row(conn, "predict:nfl", _at(215)),
        "catch_up": _row(conn, "catch-up", _at(87)),          # a year's silence
        "unknown": _row(conn, "a task nobody declares", _at(1000)),
        "ended": _row(conn, "resolve", _at(20), "ok", _at(20), "settled 2 predictions"),
    }
    conn.commit()
    before = {k: tuple(conn.execute("SELECT * FROM task_runs WHERE id = ?", (i,)).fetchone())
              for k, i in ids.items()}
    marked = tasks.abandon_hung_runs(conn, by_task="live", by_run=99, now=NOW)
    assert sorted(marked) == sorted([ids["refresh_hung"], ids["nfl_hung"]])
    rows = {k: conn.execute("SELECT * FROM task_runs WHERE id = ?", (i,)).fetchone()
            for k, i in ids.items()}
    for key in ("refresh_hung", "nfl_hung"):
        row = rows[key]
        assert row["result"] == "abandoned" and row["finished_utc"] is None
        assert row["started_utc"] == before[key][2], "the start is never rewritten"
        payload = json.loads(row["payload_json"])
        assert payload["abandoned_utc"] == "2026-09-26T12:00:00Z"
        assert payload["marked_by_task"] == "live" and payload["marked_by_run"] == 99
        words = language.task_detail_words(row["detail"])
        assert words.startswith("never recorded an ending: it started ")
        assert "26 September 2026 at 12:00 UTC" in words
        assert audit_plain(row["detail"]) == [], words
    assert json.loads(rows["refresh_hung"]["payload_json"])["silent_after_hours"] == 12.0
    assert json.loads(rows["nfl_hung"]["payload_json"])["silent_after_hours"] == 216.0
    for key in ("refresh_young", "nfl_young", "catch_up", "unknown", "ended"):
        assert tuple(rows[key]) == before[key], f"{key} was touched"
    # TERMINAL: a second sweep, later still, marks nothing and changes nothing.
    marked_once = {k: tuple(rows[k]) for k in ("refresh_hung", "nfl_hung")}
    later = NOW.replace(day=27)
    assert tasks.abandon_hung_runs(conn, now=later) == [ids["refresh_young"],
                                                        ids["nfl_young"]]
    for key, row in marked_once.items():
        assert tuple(conn.execute("SELECT * FROM task_runs WHERE id = ?",
                                  (ids[key],)).fetchone()) == row


def test_an_abandoned_run_says_so_on_the_panel_in_words(conn):
    _row(conn, "predict:nfl", "2026-01-01T00:00:00Z")
    conn.commit()
    tasks.abandon_hung_runs(conn, now=NOW)
    status = tasks.status(conn)
    entry = next(t for t in status["tasks"] if t["task"] == "predict:nfl")
    assert entry["last_result"] == "abandoned"
    assert entry["unfinished"] is True
    assert "never recorded an ending" in entry["warning"]
    assert "1 January 2026 at 00:00 UTC" in entry["last_detail"]
    assert audit.health_detail_faults(status) == []


def test_every_run_sweeps_and_a_failing_sweep_never_stops_it(league, monkeypatch):
    hung = _row(league, "refresh", _hours_ago(13))
    league.commit()
    out = tasks.run_task(league, "resolve", use_llm=False)
    assert league.execute("SELECT result FROM task_runs WHERE id = ?",
                          (hung,)).fetchone()[0] == "abandoned"
    marker = json.loads(league.execute("SELECT payload_json FROM task_runs WHERE id = ?",
                                       (hung,)).fetchone()[0])
    own = league.execute("SELECT id FROM task_runs WHERE task = 'resolve'"
                         " ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert marker["marked_by_task"] == "resolve" and marker["marked_by_run"] == own
    assert out["result"] in ("ok", "noop")

    def broken(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(tasks, "abandon_hung_runs", broken)
    again = tasks.run_task(league, "resolve", use_llm=False)
    assert again["result"] in ("ok", "noop")
    last = league.execute("SELECT result, finished_utc FROM task_runs"
                          " ORDER BY id DESC LIMIT 1").fetchone()
    assert last["result"] == again["result"] and last["finished_utc"]


class _Handle:
    """A scratch handle whose closing writes on the ledger are refused as
    locked, `times` of them -- what a second writer holding the record past
    the 30-second wait does. A plain object: the one-way-in scan refuses a
    subclass of the driver's connection."""

    def __init__(self, real, times):
        self._real, self.times, self.refused = real, times, 0

    def execute(self, sql, parameters=()):
        if self.refused < self.times and str(sql).lstrip().upper().startswith(
                "UPDATE TASK_RUNS SET FINISHED_UTC"):
            self.refused += 1
            raise sqlite3.OperationalError("database is locked")
        return self._real.execute(sql, parameters)

    def commit(self):
        return self._real.commit()

    def rollback(self):
        return self._real.rollback()

    @property
    def in_transaction(self):
        return self._real.in_transaction


def test_a_closing_write_that_raises_is_recorded_not_raised(conn, monkeypatch):
    """THE TASK FINISHED; only its ending failed to be written the first time.
    What it did is kept -- 'ok', not 'failed' -- with the write's error."""
    monkeypatch.setenv("GRIDIRON_NOTIFY_FAILURES", "0")
    monkeypatch.setattr(tasks, "_run_resolve",
                        lambda c: ("ok", "settled 1 prediction", {"settled": 1}))
    noticed = []
    monkeypatch.setattr(tasks, "notify_failures", lambda c: noticed.append(1))
    handle = _Handle(conn, times=1)
    out = tasks.run_task(handle, "resolve", use_llm=False)
    row = conn.execute("SELECT * FROM task_runs WHERE task = 'resolve'").fetchone()
    assert handle.refused == 1
    assert out["result"] == row["result"] == "ok" and row["finished_utc"]
    payload = json.loads(row["payload_json"])
    assert payload["settled"] == 1
    assert payload["closing_write"] == "OperationalError: database is locked"
    assert noticed == [], "nothing failed, so no failure notice"


def test_a_payload_json_cannot_write_is_recorded_not_raised(conn, monkeypatch):
    unwritable = {"settled": 1, "seen": {"a set is not JSON"}}
    monkeypatch.setattr(tasks, "_run_resolve",
                        lambda c: ("ok", "settled 1 prediction", unwritable))
    out = tasks.run_task(conn, "resolve", use_llm=False)
    row = conn.execute("SELECT * FROM task_runs WHERE task = 'resolve'").fetchone()
    assert out["result"] == row["result"] == "ok"
    payload = json.loads(row["payload_json"])
    assert payload["closing_write"].startswith("TypeError: ")
    assert payload["seen"] == str({"a set is not JSON"})


def test_a_closing_write_that_cannot_be_made_is_left_for_the_sweep(conn, monkeypatch):
    monkeypatch.setenv("GRIDIRON_NOTIFY_FAILURES", "0")
    monkeypatch.setattr(tasks, "_run_resolve", lambda c: ("noop", "nothing", {}))
    out = tasks.run_task(_Handle(conn, times=2), "resolve", use_llm=False)
    assert out["result"] == "noop", "the task's own result, returned, not raised"
    row = conn.execute("SELECT * FROM task_runs WHERE task = 'resolve'").fetchone()
    assert row["result"] == "running" and row["finished_utc"] is None
    later = tasks._parse(row["started_utc"]) + timedelta(hours=12, seconds=1)
    assert tasks.abandon_hung_runs(conn, now=later) == [row["id"]]


def test_a_failed_task_whose_ending_cannot_be_written_returns_failed(conn, monkeypatch):
    """The task raised, so the handler's write is the only one -- and it is
    refused too. Nothing is raised out of `run_task`: the failure is
    returned, and the row waits for the sweep."""
    monkeypatch.setenv("GRIDIRON_NOTIFY_FAILURES", "0")

    def boom(c):
        raise RuntimeError("the source went away")

    monkeypatch.setattr(tasks, "_run_resolve", boom)
    handle = _Handle(conn, times=1)
    out = tasks.run_task(handle, "resolve", use_llm=False)
    row = conn.execute("SELECT * FROM task_runs WHERE task = 'resolve'").fetchone()
    assert out["result"] == "failed" and "the source went away" in out["detail"]
    assert handle.refused == 1 and row["result"] == "running"
    # and with the write let through, it is recorded failed, as ever
    out = tasks.run_task(_Handle(conn, times=0), "resolve", use_llm=False)
    row = conn.execute("SELECT * FROM task_runs WHERE task = 'resolve'"
                       " ORDER BY id DESC LIMIT 1").fetchone()
    assert out["result"] == row["result"] == "failed"
    assert "Traceback" in json.loads(row["payload_json"])["traceback"]


def test_an_abandoned_row_is_never_given_a_second_ending(conn, monkeypatch):
    """'abandoned' IS TERMINAL. A run that outlives its task's silence -- by
    hand past the scheduler's limits -- finds its row marked by another run
    and does not overwrite the mark."""
    def outlives(c):
        c.execute("UPDATE task_runs SET result = 'abandoned', detail = 'marked'"
                  " WHERE result = 'running'")
        c.commit()
        return "ok", "settled 1 prediction", {}

    monkeypatch.setattr(tasks, "_run_resolve", outlives)
    out = tasks.run_task(conn, "resolve", use_llm=False)
    row = conn.execute("SELECT * FROM task_runs WHERE task = 'resolve'").fetchone()
    assert out["result"] == "ok"
    assert row["result"] == "abandoned" and row["detail"] == "marked"
    assert row["finished_utc"] is None


def test_the_gate_sees_a_closing_write_outside_the_try():
    from pathlib import Path

    source = (Path(config.PACKAGE_ROOT) / "tasks.py").read_text(encoding="utf-8")
    assert audit.task_run_order_faults(source) == []
    head_shape = "\n".join([
        "def run_task(conn, task):",
        "    cursor = conn.execute(\"INSERT INTO task_runs (task) VALUES (?)\", (task,))",
        "    conn.commit()",
        "    try:",
        "        result = _run_resolve(conn)",
        "    except Exception:",
        "        result = 'failed'",
        "    conn.execute(\"UPDATE task_runs SET result = ? WHERE id = ?\", (result, 1))",
        "    conn.commit()",
    ])
    faults = audit.task_run_order_faults(head_shape)
    assert any("line 8" in f and "outside any try" in f for f in faults), faults
    assert any("commit at line 9" in f for f in faults), faults


def test_the_gate_sees_a_closing_write_under_a_handler_that_lets_it_out():
    """THE PROVER, 2026-09-26: the first order check passed a close inside
    ANY try with a handler, so `except ValueError:` -- or a handler that
    catches everything and raises it again -- let the locked write out of
    `run_task` with a clean gate."""
    def shape(*handler):
        return "\n".join([
            "def run_task(conn, task):",
            "    cursor = conn.execute(\"INSERT INTO task_runs (task) VALUES (?)\", (task,))",
            "    conn.commit()",
            "    try:",
            "        result = _run_resolve(conn)",
            "        conn.execute(\"UPDATE task_runs SET result = ? WHERE id = ?\", (result, 1))",
            "        conn.commit()",
            *handler,
        ])

    for handler in (["    except ValueError:", "        result = 'failed'"],
                    ["    except (KeyError, TypeError):", "        result = 'failed'"],
                    ["    except Exception:", "        result = 'failed'", "        raise"]):
        faults = audit.task_run_order_faults(shape(*handler))
        assert any("line 6" in f and "outside any try" in f for f in faults), (handler, faults)
        assert any("commit at line 7" in f for f in faults), (handler, faults)
    for handler in (["    except Exception:", "        result = 'failed'"],
                    ["    except:", "        result = 'failed'"],
                    ["    except (OSError, BaseException):", "        result = 'failed'"]):
        assert audit.task_run_order_faults(shape(*handler)) == [], handler


def test_an_older_ledger_is_widened_to_admit_abandoned(tmp_path):
    """The live record's ledger as released until 2026-09-26: its CHECK
    admits 'running' and not 'abandoned'. Widened through the rebuild door:
    every row kept with its id, the index and the no-delete trigger
    recreated, and the table exactly the one a fresh build has."""
    from gridiron import rebuild

    conn = db.open_db(tmp_path / "released.db")
    try:
        conn.executescript(
            "DROP TABLE task_runs;"
            "CREATE TABLE task_runs ("
            " id INTEGER PRIMARY KEY, task TEXT NOT NULL, started_utc TEXT NOT NULL,"
            " finished_utc TEXT, result TEXT NOT NULL"
            " CHECK (result IN ('running', 'ok', 'noop', 'missed', 'failed')),"
            " detail TEXT, payload_json TEXT);"
            "CREATE INDEX IF NOT EXISTS task_runs_lookup ON task_runs (task, started_utc DESC);"
            "CREATE TRIGGER IF NOT EXISTS task_runs_no_delete BEFORE DELETE ON task_runs"
            " BEGIN SELECT RAISE(ABORT, 'task_runs is append-only: a run that failed is a fact'); END;")
        for n, result in enumerate(("ok", "running", "failed", "noop", "missed"), start=1):
            conn.execute(
                "INSERT INTO task_runs (id, task, started_utc, finished_utc, result,"
                " detail, payload_json) VALUES (?, 'refresh', ?, NULL, ?, ?, '{}')",
                (n * 7, f"2026-09-0{n}T00:00:00Z", result, f"row {n}"))
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE task_runs SET result = 'abandoned' WHERE id = 14")
        conn.rollback()
        before = [tuple(r) for r in conn.execute("SELECT * FROM task_runs ORDER BY id")]

        assert db.widen_task_run_results(conn) is True
        assert [tuple(r) for r in conn.execute("SELECT * FROM task_runs ORDER BY id")] == before
        definition = rebuild.released_definitions(["task_runs"])["task_runs"]
        assert rebuild.differences_from(conn, definition) == []
        conn.execute("UPDATE task_runs SET result = 'abandoned' WHERE id = 14")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM task_runs WHERE id = 14")
        conn.rollback()
        assert db.widen_task_run_results(conn) is False
        db.init(conn)
        assert rebuild.differences_from(conn, definition) == []
    finally:
        conn.close()


def test_every_task_the_installer_defines_wakes_the_machine():
    """ALL 18 READ BACK WakeToRun=False ON 23 SEPTEMBER, and the ruling says
    every one gains it -- Live and Serve included. Read from the installer's
    code, keyed on its own list of names, not on `scheduler.NOT_INSTALLED`
    (which would skip Live)."""
    script = audit.INSTALLER.read_text(encoding="utf-8")
    assert audit.installer_wake_faults(script) == []
    listed = script.split("$TaskNames = @(")[1].split(chr(10) + ")")[0]
    assert listed.count('"$($Prefix)') == 18
    serve = script.index('Register-ScheduledTask -TaskName "$($Prefix)Serve"')
    without = script[:serve] + script[serve:].replace(
        "New-ScheduledTaskSettingsSet -WakeToRun ", "New-ScheduledTaskSettingsSet ", 1)
    faults = audit.installer_wake_faults(without)
    assert [f.split(":", 1)[0] for f in faults] == ["Gridiron-Serve"], faults
    helper = script.replace("        -WakeToRun `" + chr(10), "", 1)
    named = sorted(f.split(":", 1)[0] for f in audit.installer_wake_faults(helper))
    assert len(named) == 17 and "Gridiron-Live" in named and "Gridiron-Serve" not in named
    audit.check_every_task_wakes_to_run()


def test_a_wake_taken_away_another_way_is_named():
    """THE PROVER, 2026-09-26: the first scan refused only `-WakeToRun:$false`
    and read the last assignment of the settings made by the settings
    cmdlet, so each of these passed while the seventeen tasks registered
    through the helper would not wake the machine. Every one now names all
    seventeen; `-WakeToRun:$true` still passes."""
    script = audit.INSTALLER.read_text(encoding="utf-8")
    switch = "        -WakeToRun `" + chr(10)
    limit = "-StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)" + chr(10)
    register = "    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger `"
    assert script.count(switch) == script.count(limit) == script.count(register) == 1

    def before_register(line):
        return script.replace(register, line + chr(10) + register, 1)

    variants = {
        "a comment on the statement": script.replace(switch, "", 1).replace(
            limit, limit[:-1] + "  # -WakeToRun" + chr(10), 1),
        **{f"bound to {value}": script.replace(
            switch, f"        -WakeToRun:{value} `" + chr(10), 1)
           for value in ("0", "$null", "$off", "(1 -eq 2)", "$False")},
        "taken off by property": before_register("    $settings.WakeToRun = $false"),
        "taken off through PSObject": before_register(
            "    $settings.PSObject.Properties['WakeToRun'].Value = $false"),
        "made again in brackets": before_register(
            "    $settings = (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries)"),
        "made again from another variable": before_register(
            "    $plain = New-ScheduledTaskSettingsSet" + chr(10) + "    $settings = $plain"),
        "made again by Set-Variable": before_register(
            "    Set-Variable -Name settings -Value (New-ScheduledTaskSettingsSet)"),
        "made again in another scope": before_register(
            "    $script:settings = New-ScheduledTaskSettingsSet"),
        "handed to a command that may change it": before_register(
            "    Update-Settings $settings"),
    }
    for label, planted in variants.items():
        named = sorted(f.split(":", 1)[0] for f in audit.installer_wake_faults(planted))
        assert len(named) == 17 and "Gridiron-Serve" not in named, (label, named)
    lawful = script.replace(switch, "        -WakeToRun:$true `" + chr(10), 1)
    assert audit.installer_wake_faults(lawful) == []
