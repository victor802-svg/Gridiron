"""Schema ruling 5 of 2026-09-24: no gated test depends on elapsed real time.

"The auth backoff test takes an injectable clock instead of wall time. No test
in the gate may depend on elapsed real time." Built 2026-09-25. Auth reads one
clock, `auth.clock`, which test_auth replaces with one it moves by hand; the
scans hold both halves. The plantings are
`plant.py::plant_a_test_that_waits_on_the_clock` and
`::plant_a_wall_clock_read_in_the_backoff`.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gridiron import audit


@pytest.fixture
def no_registers(monkeypatch):
    """A synthetic tree holds none of the real tests, so the real registers
    would all read as stale against it."""
    monkeypatch.setattr(audit, "ELAPSED_TIME_HELD", {})
    monkeypatch.setattr(audit, "ELAPSED_TIME_EXEMPT", {})


def _tests(tmp_path: Path, text: str) -> Path:
    """A package root with one test file beside it."""
    (tmp_path / "gridiron").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(textwrap.dedent(text),
                                                  encoding="utf-8")
    return tmp_path / "gridiron"


def test_no_gated_test_waits_on_the_real_clock():
    audit.check_no_test_waits_on_the_clock()


def test_auth_reads_only_the_clock_a_test_can_move():
    audit.check_auth_reads_one_clock()


def test_each_way_of_waiting_on_the_clock_is_named(tmp_path, no_registers):
    root = _tests(tmp_path, """
        import asyncio
        import time as t
        from datetime import datetime, timedelta, timezone
        from time import perf_counter, sleep as nap

        def test_sleeps():
            nap(1)

        async def test_awaits():
            await asyncio.sleep(1)

        def test_times():
            begun = perf_counter()
            assert t.monotonic_ns() > 0 and begun

        def test_waits(page):
            page.wait_for_timeout(250)

        def test_compares():
            started = datetime.now(timezone.utc)
            assert datetime.now(timezone.utc) - started < timedelta(seconds=2)

        def test_reckons(kickoff):
            assert datetime.now(timezone.utc) + timedelta(hours=1) > kickoff
        """)
    faults = audit.elapsed_time_faults(root)
    for name in ("(test_sleeps)", "(test_awaits)", "(test_times)",
                 "(test_waits)", "(test_compares)", "(test_reckons)"):
        assert any(name in f for f in faults), (name, faults)
    # test_times reads two clocks; test_compares both reckons and subtracts
    assert len(faults) == 8, faults


def test_a_date_placed_from_now_is_not_a_wait(tmp_path, no_registers):
    """A fixture placed at "now plus two days" is a date: nothing in it waits,
    and its result does not turn on how long anything took."""
    root = _tests(tmp_path, """
        from datetime import datetime, timedelta, timezone
        from gridiron import db

        def _soon(hours):
            return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()

        def _ago(n):
            return datetime.now(timezone.utc) - timedelta(hours=n)

        def test_overdue(entry, page):
            assert entry["next_due_utc"] < db.utcnow()
            page.wait_for_selector("#x", timeout=15000)
        """)
    assert audit.elapsed_time_faults(root) == []


def test_the_held_register_holds_its_count_and_only_shrinks(tmp_path, monkeypatch):
    root = _tests(tmp_path, """
        def test_held(page):
            page.wait_for_timeout(300)
            page.wait_for_timeout(300)
        """)
    monkeypatch.setattr(audit, "ELAPSED_TIME_HELD",
                        {"tests/test_x.py:test_held": 2})
    monkeypatch.setattr(audit, "ELAPSED_TIME_EXEMPT", {})
    assert audit.elapsed_time_faults(root) == []

    audit.ELAPSED_TIME_HELD["tests/test_x.py:test_held"] = 1
    added = audit.elapsed_time_faults(root)
    assert len(added) == 2 and all("1 held" in f for f in added), added

    audit.ELAPSED_TIME_HELD["tests/test_x.py:test_held"] = 3
    stale = audit.elapsed_time_faults(root)
    assert len(stale) == 1 and "lower it to 2" in stale[0], stale


def test_an_exemption_that_no_longer_waits_must_go(tmp_path, monkeypatch):
    root = _tests(tmp_path, "def test_nothing():\n    pass\n")
    monkeypatch.setattr(audit, "ELAPSED_TIME_HELD", {})
    monkeypatch.setattr(audit, "ELAPSED_TIME_EXEMPT",
                        {"tests/test_x.py:test_nothing": "2026-09-25: a reason"})
    faults = audit.elapsed_time_faults(root)
    assert len(faults) == 1 and "Remove the entry" in faults[0], faults


def test_a_second_reading_of_the_real_clock_in_auth_is_named(tmp_path):
    from gridiron import config

    root = tmp_path / "gridiron"
    root.mkdir()
    source = (config.PACKAGE_ROOT / "auth.py").read_text(encoding="utf-8")
    assert audit.auth_clock_faults(config.PACKAGE_ROOT) == []
    (root / "auth.py").write_text(
        source + "\n\ndef planted_expiry():\n"
                 "    import time\n"
                 "    return time.time() + 60\n",
        encoding="utf-8")
    faults = audit.auth_clock_faults(root)
    assert len(faults) == 1 and "(planted_expiry)" in faults[0], faults


def test_every_spelling_of_a_clock_reading_in_auth_is_named(tmp_path):
    """AN ALIAS IS STILL THE MACHINE'S CLOCK (2026-09-25, found proving the
    ruling 5 build). The first version of the auth scan knew `time.<clock>()`
    and `datetime.now()` by those spellings only: `import time as t`,
    `from time import perf_counter` and `from datetime import datetime as D`
    each read the real clock past it, while the tests scan beside it already
    resolved the first two."""
    from gridiron import config

    source = (config.PACKAGE_ROOT / "auth.py").read_text(encoding="utf-8")
    shapes = {
        "planted_module_alias": "    import time as t\n    return t.monotonic()\n",
        "planted_imported_clock":
            "    from time import perf_counter as tick\n    return tick()\n",
        "planted_class_alias":
            "    from datetime import datetime as D\n    return D.now()\n",
        "planted_date_alias": "    from datetime import date as day\n    return day.today()\n",
    }
    for name, body in shapes.items():
        root = tmp_path / name / "gridiron"
        root.mkdir(parents=True)
        (root / "auth.py").write_text(source + f"\n\ndef {name}():\n{body}",
                                      encoding="utf-8")
        faults = audit.auth_clock_faults(root)
        assert len(faults) == 1 and f"({name})" in faults[0], (name, faults)


def test_an_aliased_datetime_in_a_test_is_still_the_real_clock(tmp_path, no_registers):
    """The same resolution in the tests scan (2026-09-25): a test that times
    itself through `from datetime import datetime as D` is named."""
    root = _tests(tmp_path, """
        from datetime import datetime as D, timedelta, timezone

        def test_aliased(client):
            started = D.now(timezone.utc)
            client.get("/")
            assert D.now(timezone.utc) - started < timedelta(seconds=2)
        """)
    faults = audit.elapsed_time_faults(root)
    assert len(faults) == 2 and all("(test_aliased)" in f for f in faults), faults
