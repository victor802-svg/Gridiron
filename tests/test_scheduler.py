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

import pytest

from gridiron import config, db, tasks


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

def test_resolve_run_twice_settles_nothing_the_second_time(league):
    from gridiron import run
    from gridiron.factors import store
    from gridiron.model import baseline

    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
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
        assert task in tasks.TASKS or task == "catch-up", (
            f"{suffix} is named on the scheduler and is not a task")
