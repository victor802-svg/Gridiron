"""The refresh task, and the stall its absence caused.

On 2026-08-31 the appliance had been running correctly for two days and the
record had not moved. `predict` wrote forecasts. `resolve` ran every four hours
and reported "no prediction had a finished game waiting" — truthfully, every
time, because it settles against `games.status` and NOTHING EVER UPDATED
`games.status`. Twenty-seven MLB predictions waited on games that had finished
in the world and were still marked `scheduled` here.

No task failed. No error was logged. The schedule panel showed an unbroken run
of successes. That is what makes this worth a test rather than a fix: the
failure mode is every component working and the system not.
"""

from __future__ import annotations

import pytest

from gridiron import config, db, tasks


@pytest.fixture()
def conn(tmp_path):
    connection = db.open_db(tmp_path / "refresh.db")
    yield connection
    connection.close()


def test_refresh_is_a_declared_task():
    assert "refresh" in tasks.TASKS
    spec = tasks.TASKS["refresh"]
    assert spec.every_hours == 4.0
    assert "finished" in spec.what


def test_catch_up_refreshes_before_it_resolves():
    """The order is the fix. Resolving before re-reading settles nothing and
    says so truthfully, which is exactly how this hid for two days."""
    import inspect

    src = inspect.getsource(tasks.catch_up)
    assert '"refresh"' in src and '"resolve"' in src
    assert src.index('"refresh"') < src.index('"resolve"')


def test_the_scheduler_registers_refresh_before_resolve():
    """A task that exists in code and not in the scheduler is not a task."""
    from pathlib import Path

    script = (Path(config.REPO_ROOT) / "tools" / "schedule_install.ps1").read_text(
        encoding="utf-8"
    )
    assert "$($Prefix)Refresh" in script
    assert 'TaskArg "refresh"' in script
    # ...and it must be torn down by an uninstall too, or a reinstall orphans it.
    # Cut at the closing paren that sits alone on its line: "$($Prefix)"
    # contains a bare ")" of its own, so splitting on ")" cuts far too early.
    names_block = script.split("$TaskNames = @(")[1].split(chr(10) + ")")[0]
    assert "Refresh" in names_block, names_block


def _game(conn, gid, status, day, scored):
    scores = (5, 3) if scored else (None, None)
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, home_score, away_score, league_date)"
        " VALUES (?, 'mlb', 2026, 1, 'REG', ?, 'PHI', 'NYM', ?, ?, ?, ?)",
        (gid, f"{day}T23:00:00Z", status, scores[0], scores[1], day),
    )


def _prediction(conn, gid):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning)"
        " VALUES ('2026-04-01T00:00:00Z','mlb',?,'moneyline','PHI',0.6,'win',"
        "'statistical','fs2','{}','because')",
        (gid,),
    )


def test_a_resolver_reading_a_stale_table_settles_nothing(conn):
    """The stall, reproduced. The game has finished; our row says otherwise;
    the resolver is correct and the record does not move."""
    from gridiron import resolve

    _game(conn, "mlb_1", "scheduled", "2026-04-01", scored=False)
    _prediction(conn, "mlb_1")
    conn.commit()

    settled = resolve.resolve_all(conn)
    assert settled["settled"] == 0, "nothing to settle, and that is correct"
    assert settled["still_open"] == 1


def test_once_the_game_is_marked_final_the_same_resolver_settles_it(conn):
    """The other half: the resolver was never the problem."""
    from gridiron import resolve

    _game(conn, "mlb_1", "scheduled", "2026-04-01", scored=False)
    _prediction(conn, "mlb_1")
    conn.commit()
    assert resolve.resolve_all(conn)["settled"] == 0

    # what a refresh does, in one line
    conn.execute(
        "UPDATE games SET status='final', home_score=5, away_score=3"
        " WHERE id='mlb_1'"
    )
    conn.commit()
    assert resolve.resolve_all(conn)["settled"] == 1


def test_refresh_reports_how_many_predictions_it_unblocked(conn, monkeypatch):
    """`ok` vs `noop` has to mean something. A refresh that unblocks nothing
    says so; one that unblocks work says how much, because "ran successfully"
    was the exact signal that hid the stall."""
    _game(conn, "mlb_1", "final", "2026-04-01", scored=True)
    _prediction(conn, "mlb_1")
    conn.commit()

    # No network in a test: the loaders are stubbed, so what is measured is the
    # REPORTING, which is the part that failed to communicate.
    # EVERY sport's loader, not a list of three. When college football was
    # added, its loader was the only one left unpatched, so the "nothing
    # happened" test went to the network and came back with something.
    import gridiron.data.cfb_loader as cfb_loader
    import gridiron.data.loader as nfl_loader
    import gridiron.data.mlb_loader as mlb_loader
    import gridiron.data.nba_loader as nba_loader

    for mod in (mlb_loader, nba_loader, nfl_loader):
        monkeypatch.setattr(mod, "load_all",
                            lambda *a, **k: {"rows": {}, "warnings": []})
    monkeypatch.setattr(cfb_loader, "load_season",
                        lambda *a, **k: {"games": 0, "finals": 0,
                                         "skipped": 0, "events": 0})

    result, detail, payload = tasks._run_refresh(conn)
    assert result == "ok"
    assert payload["resolvable_now"] == 1
    assert "1 prediction" in detail


def test_refresh_says_noop_when_nothing_became_resolvable(conn, monkeypatch):
    import gridiron.data.mlb_loader as mlb_loader
    import gridiron.data.nba_loader as nba_loader
    import gridiron.data.loader as nfl_loader

    for mod in (mlb_loader, nba_loader, nfl_loader):
        monkeypatch.setattr(mod, "load_all",
                            lambda *a, **k: {"rows": {}, "warnings": []})

    result, detail, payload = tasks._run_refresh(conn)
    assert result == "noop"
    assert payload["resolvable_now"] == 0


def test_one_sport_failing_does_not_stop_the_others(conn, monkeypatch):
    """An outage at one source is not an outage of the appliance."""
    import gridiron.data.mlb_loader as mlb_loader
    import gridiron.data.nba_loader as nba_loader
    import gridiron.data.loader as nfl_loader

    def boom(*a, **k):
        raise RuntimeError("source is down")

    monkeypatch.setattr(nfl_loader, "load_all", boom)
    for mod in (mlb_loader, nba_loader):
        monkeypatch.setattr(mod, "load_all",
                            lambda *a, **k: {"rows": {}, "warnings": []})

    result, detail, payload = tasks._run_refresh(conn)
    assert "mlb" in payload["sports"] and "nba" in payload["sports"]
    assert "nfl" not in payload["sports"]
    assert any("source is down" in w for w in payload["warnings"])
