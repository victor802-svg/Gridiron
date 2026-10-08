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


def test_the_held_register_is_pinned_empty(tmp_path, monkeypatch):
    """THE REGISTER IS EMPTY AND PINNED (operator question 5, ruled (A) on
    2026-09-27; built 2026-10-08). Until then a function might hold its count
    of fixed waits and the register only shrank (this test held it to that).
    Every wait was rebuilt, so an entry is refused by name -- whatever its
    count -- and holds nothing back: the waits under it are named too."""
    root = _tests(tmp_path, """
        def test_held(page):
            page.wait_for_timeout(300)
            page.wait_for_timeout(300)
        """)
    monkeypatch.setattr(audit, "ELAPSED_TIME_EXEMPT", {})
    for count in (1, 2, 3):
        monkeypatch.setattr(audit, "ELAPSED_TIME_HELD",
                            {"tests/test_x.py:test_held": count})
        faults = audit.elapsed_time_faults(root)
        pinned = [f for f in faults if "pinned empty" in f]
        waits = [f for f in faults if "(test_held) waits a fixed time" in f]
        assert len(pinned) == 1 and f"holds {count}" in pinned[0], faults
        assert len(waits) == 2 and len(faults) == 3, faults


def test_the_register_is_empty_and_what_it_held_is_kept_as_history():
    """EMPTIED BY QUESTION 5 (2026-10-08): the 27 fixed waits in 19 functions
    it held on 56d65a4 were each rebuilt, and their list is kept beside it as
    history that nothing reads as a register."""
    assert audit.ELAPSED_TIME_HELD == {}
    history = audit.ELAPSED_TIME_HELD_UNTIL_QUESTION_5
    assert len(history) == 19 and sum(history.values()) == 27, history
    assert audit.elapsed_time_faults() == []


#: A TIMER'S NAME, built so that this file's own strings hold none: the scan
#: reads every string a test hands anything (operator question 5, 2026-10-08).
_TIMER = "set" + "Timeout"


def test_a_timer_in_the_page_and_a_quiet_network_are_fixed_waits(tmp_path, no_registers):
    """WHAT THE SCAN DID NOT READ UNTIL QUESTION 5 (2026-10-08): a timer in
    the script a test hands the page -- `test_cards.py` read an opened row
    250ms after the tap that way, `test_rapid.py` pressed its second chip
    60ms after the first -- and Playwright's `networkidle`, half a second
    with no request, on eleven page loads. Each is named; a docstring that names a
    timer is words, and is not."""
    interval = "set" + "Interval"
    root = _tests(tmp_path, f'''
        def test_in_page(page):
            page.evaluate("async () => {{ await new Promise(r => {_TIMER}(r, 250)); }}")

        def test_in_an_f_string(page, second):
            page.evaluate(f"() => {_TIMER}(() => document.querySelector('{{second}}').click(), 60)")

        def test_polls_in_the_page(page):
            page.evaluate("() => {interval}(() => 0, 100)")

        def test_quiet(page, served):
            page.goto(served + "/login", wait_until="networkidle")

        def test_quiet_again(page):
            page.wait_for_load_state("networkidle")

        def test_words_only(page):
            """A docstring may say the page once used {_TIMER}(r, 250)."""
            page.goto("/login")
            page.wait_for_load_state("load")
        ''')
    faults = audit.elapsed_time_faults(root)
    for name in ("(test_in_page) waits a fixed time inside the page",
                 "(test_in_an_f_string) waits a fixed time inside the page",
                 "(test_polls_in_the_page) waits a fixed time inside the page",
                 "(test_quiet) waits for the network to fall quiet",
                 "(test_quiet_again) waits for the network to fall quiet"):
        assert sum(name in f for f in faults) == 1, (name, faults)
    assert len(faults) == 5, faults
    assert not [f for f in faults if "(test_words_only)" in f], faults


#: A FRAME'S CALL, built so that this file's own strings hold none (question
#: 5's prover, 2026-10-08).
_FRAME = "requestAnimation" + "Frame"
REPO = Path(__file__).resolve().parents[1]


def test_a_page_read_frame_by_frame_is_named_and_held_only_by_its_name(tmp_path, monkeypatch):
    """A READING OF THE PAGE FRAME BY FRAME (question 5's prover, 2026-10-08;
    schema ruling 5): `test_motion.py` read the Props grid's opacity on every
    frame and asked that one sit strictly between zero and one, which rode on
    frames coming faster than a 200ms fade -- with the document's timeline run
    fast it read [0, 1] and went red on a page that fades. A
    `requestAnimationFrame` in any string a test hands anything is named,
    a docstring that names one is words and is not, and a script kept at the
    module's top level is keyed by its own name -- so a hold
    (`ELAPSED_TIME_EXEMPT`, as question 20's per-frame check is held) names
    that script and nothing else of the module."""
    root = _tests(tmp_path, f'''
        SAMPLER = "() => {{ const tick = () => {_FRAME}(tick); {_FRAME}(tick); }}"
        ANOTHER = "() => {{ {_FRAME}(() => 0); }}"

        def test_fade(page):
            page.evaluate("() => {{ {_FRAME}(() => {{ window.__seen = 1; }}); }}")

        def test_words_only(page):
            """A docstring may say the sampler once read by {_FRAME}(tick)."""
            page.evaluate(SAMPLER)
        ''')
    monkeypatch.setattr(audit, "ELAPSED_TIME_HELD", {})
    monkeypatch.setattr(audit, "ELAPSED_TIME_EXEMPT", {})
    faults = audit.elapsed_time_faults(root)
    for name in ("(SAMPLER) reads the page frame by frame",
                 "(ANOTHER) reads the page frame by frame",
                 "(test_fade) reads the page frame by frame"):
        assert sum(name in f for f in faults) == 1, (name, faults)
    assert len(faults) == 3 and not [f for f in faults if "test_words_only" in f], faults
    monkeypatch.setattr(audit, "ELAPSED_TIME_EXEMPT",
                        {"tests/test_x.py:SAMPLER": "2026-10-08: a reason"})
    held = audit.elapsed_time_faults(root)
    assert len(held) == 2 and not [f for f in held if "(SAMPLER)" in f], held


def test_the_per_frame_check_is_held_by_name_and_reads_no_fade_by_its_frames():
    """THE ONE SAMPLER HELD (question 5's prover, 2026-10-08): question 20's
    per-frame whole-pixel check, by its script's name, with a dated reason;
    the scan finds it there (an exemption holding nothing is named stale), and
    no test reads a fade by the frames that land any more."""
    reason = audit.ELAPSED_TIME_EXEMPT["tests/test_smoke.py:WATCH_ONE_ARRIVAL"]
    assert reason.startswith("2026-10-08") and "question 20" in reason, reason
    assert audit.elapsed_time_faults() == []
    motion = (REPO / "tests" / "test_motion.py").read_text(encoding="utf-8")
    assert _FRAME not in motion and "__opacity" not in motion


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
