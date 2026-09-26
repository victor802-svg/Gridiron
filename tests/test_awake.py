"""The awake fraction a close-out quotes (GRIDIRON_REPAIR item 7, the
operator's ruling of 2026-09-23: "Report awake fraction since the fix in
each close-out"), built 2026-09-26.

`tools/awake.py` reads the Windows System log and writes nothing. Every test
here hands it events, or a stand-in for the PowerShell child, so none reads
the log, starts a process or looks at the clock.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone

import pytest

from gridiron import config


def _tool():
    path = config.REPO_ROOT / "tools" / "awake.py"
    spec = importlib.util.spec_from_file_location("awake_tool_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


awake = _tool()

SINCE = datetime(2026, 9, 27, 6, 0, tzinfo=timezone.utc)
UNTIL = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)


def _event(provider, number, time, **data):
    return {"provider": provider, "id": number, "time": time, "data": data}


def _day() -> list[dict]:
    """One day of this machine's own event shapes (measured September 2026)."""
    kg, kp, pt = awake.KERNEL_GENERAL, awake.KERNEL_POWER, awake.TROUBLESHOOTER
    return [
        # on since the night before
        _event(kg, 12, "2026-09-26T22:00:01.000Z", StartTime="2026-09-26T22:00:00.5000000Z"),
        # asleep 08:00 to 10:00, woken by a task's timer; 107 is stamped at
        # the sleep's start and must not be read as the wake
        _event(kp, 42, "2026-09-27T08:00:00.200Z", TargetState="4", EffectiveState="5"),
        _event(kp, 107, "2026-09-27T08:00:02.000Z"),
        _event(pt, 1, "2026-09-27T10:00:01.000Z",
               SleepTime="2026-09-27T08:00:00.0000000Z", WakeTime="2026-09-27T10:00:00.0000000Z",
               WakeTimerOwner=r"\Device\HarddiskVolume2\Windows\System32\svchost.exe",
               WakeTimerContext="Gridiron-Refresh", WakeSourceText=None),
        # powered off from the sign-in screen at 12:00, on again at 13:00
        _event(awake.USER32, 1074, "2026-09-27T11:59:50.000Z",
               param1=r"C:\WINDOWS\system32\winlogon.exe (VICS_PC)",
               param3="No title for this reason could be found", param4="0x500ff",
               param5="power off", param7=r"NT AUTHORITY\SYSTEM"),
        _event(awake.EVENTLOG, 6006, "2026-09-27T11:59:55.000Z"),
        _event(kg, 13, "2026-09-27T12:00:00.100Z", StopTime="2026-09-27T12:00:00.0000000Z"),
        _event(kg, 12, "2026-09-27T13:00:01.000Z", StartTime="2026-09-27T13:00:00.0000000Z"),
        # an update's restart at 15:00, two minutes off
        _event(awake.USER32, 1074, "2026-09-27T14:59:00.000Z",
               param1=r"C:\WINDOWS\servicing\TrustedInstaller.exe (VICS_PC)",
               param3="Operating System: Upgrade (Planned)", param5="restart"),
        _event(kg, 13, "2026-09-27T15:00:00.100Z", StopTime="2026-09-27T15:00:00.0000000Z"),
        _event(kg, 12, "2026-09-27T15:02:01.000Z", StartTime="2026-09-27T15:02:00.0000000Z"),
        # last seen at 16:00, then a start with no shutdown before it
        _event(kg, 1, "2026-09-27T16:00:00.000Z"),
        _event(kg, 12, "2026-09-27T17:00:01.000Z", StartTime="2026-09-27T17:00:00.0000000Z"),
        _event(kp, 41, "2026-09-27T17:00:03.000Z"),
        # after the window: ignored
        _event(kg, 13, "2026-09-27T19:00:00.000Z", StopTime="2026-09-27T19:00:00.0000000Z"),
    ]


def test_the_window_is_measured_from_the_log_and_every_gap_has_its_cause():
    report = awake.measure(_day(), SINCE, UNTIL)
    assert report["hours"] == 12.0
    # awake 06-08, 10-12, 13-15, 15:02-16:00, 17-18
    assert report["awake_hours"] == pytest.approx(2 + 2 + 2 + 58 / 60 + 1)
    assert report["asleep_hours"] == pytest.approx(2.0)
    assert report["off_hours"] == pytest.approx(1 + 2 / 60)
    assert report["unknown_hours"] == pytest.approx(1.0)
    assert report["awake_fraction"] == pytest.approx(report["awake_hours"] / 12)
    gaps = [(g["start"], g["end"], g["state"], g["why"]) for g in report["gaps"]]
    assert gaps[0][:3] == ("2026-09-27T08:00:00Z", "2026-09-27T10:00:00Z", "asleep")
    assert gaps[0][3].startswith("woken by a timer") and "Gridiron-Refresh" in gaps[0][3]
    assert gaps[1] == ("2026-09-27T12:00:00Z", "2026-09-27T13:00:00Z", "switched off",
                       "powered off from the power button or the sign-in screen")
    assert gaps[2] == ("2026-09-27T15:00:00Z", "2026-09-27T15:02:00Z", "switched off",
                       "restarted for a Windows update")
    assert gaps[3][:3] == ("2026-09-27T16:00:00Z", "2026-09-27T17:00:00Z", "not known")
    assert gaps[3][3].startswith("stopped without shutting down (the next start "
                                 "logged an unexpected shutdown)")
    assert report["timer_wakes"] == ["2026-09-27T10:00:00Z"]
    assert report["unexpected_stops"] == 1


def test_a_sleep_with_no_wake_is_asleep_until_the_next_start():
    kg, kp = awake.KERNEL_GENERAL, awake.KERNEL_POWER
    events = [
        _event(kg, 12, "2026-09-27T05:00:00.000Z", StartTime="2026-09-27T05:00:00.0000000Z"),
        _event(kp, 42, "2026-09-27T07:00:00.000Z"),
        _event(kg, 12, "2026-09-27T09:00:00.000Z", StartTime="2026-09-27T09:00:00.0000000Z"),
    ]
    report = awake.measure(events, SINCE, UNTIL)
    assert report["asleep_hours"] == pytest.approx(2.0)
    assert report["awake_hours"] == pytest.approx(10.0)
    assert "no wake was recorded" in report["gaps"][0]["why"]


def test_what_the_window_opens_in_is_read_from_before_it():
    kg = awake.KERNEL_GENERAL
    off = [_event(kg, 13, "2026-09-26T23:00:00.000Z", StopTime="2026-09-26T23:00:00.0000000Z"),
           _event(kg, 12, "2026-09-27T09:00:00.000Z", StartTime="2026-09-27T09:00:00.0000000Z")]
    report = awake.measure(off, SINCE, UNTIL)
    assert report["off_hours"] == pytest.approx(3.0)
    assert report["awake_hours"] == pytest.approx(9.0)
    # NOTHING BEFORE IT: not known, never assumed awake
    report = awake.measure(off[1:], SINCE, UNTIL)
    assert report["unknown_hours"] == pytest.approx(3.0)
    assert report["gaps"][0]["why"] == "the log holds nothing before this window"


def test_the_words_are_plain_and_say_every_gap():
    from gridiron import audit

    lines = awake.words(awake.measure(_day(), SINCE, UNTIL))
    assert lines[0].startswith("Awake 7.97 of 12.00 hours, 66.4%, from 27 September "
                               "2026 06:00 UTC to 27 September 2026 18:00 UTC")
    assert "Woken by a timer 1 time" in lines[2]
    assert sum(1 for line in lines if line.startswith("  ")) == 4
    for line in lines:
        assert audit.plain_words_violations(line) == [], line


def test_the_reader_asks_the_log_only_and_bounds_an_unclean_start():
    """THE CHILD IS A STAND-IN: the scripts it is handed are read, not run.
    They only read the System log, and the second is asked only when a
    start followed no shutdown and no sleep."""
    asked: list[str] = []
    day = _day()
    bound = {"provider": "Microsoft-Windows-Kernel-General", "id": 16,
             "time": "2026-09-27T16:40:00.000Z", "data": {}, "bound": True,
             "before": "2026-09-27T17:00:00Z"}

    def child(script: str) -> str:
        asked.append(script)
        return json.dumps(day if len(asked) == 1 else [bound])

    events = awake.read_events(SINCE, UNTIL, run=child)
    assert len(asked) == 2
    for script in asked:
        assert "Get-WinEvent" in script and "LogName='System'" in script
        for verb in ("Clear-EventLog", "Remove-", "Set-", "New-Item", "Out-File",
                     "wevtutil", "Limit-EventLog", "Write-EventLog"):
            assert verb not in script, verb
    assert "'2026-08-28T06:00:00Z'" in asked[0], "thirty days read before the window"
    assert "'2026-09-27T17:00:00Z'" in asked[1] and "-MaxEvents 1" in asked[1]
    report = awake.measure(events, SINCE, UNTIL)
    # the last sign of life, from the whole log, bounds what is not known
    assert report["unknown_hours"] == pytest.approx(20 / 60)
    assert report["gaps"][-1]["why"].endswith("last seen awake 27 September 2026 16:40 UTC")


def test_the_reader_needs_no_second_look_after_a_clean_day():
    asked = []
    kg = awake.KERNEL_GENERAL
    clean = [_event(kg, 12, "2026-09-27T05:00:00.000Z", StartTime="2026-09-27T05:00:00.0000000Z")]

    def child(script):
        asked.append(script)
        return json.dumps(clean)

    assert awake.read_events(SINCE, UNTIL, run=child) == clean
    assert len(asked) == 1
    # one event comes back from PowerShell as an object, not a list
    assert awake._rows(json.dumps(clean[0])) == clean
    assert awake._rows("") == []


def test_the_command_prints_the_measurement_and_writes_nothing(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = awake.main(["--since", "2026-09-27T06:00:00Z", "--until",
                       "2026-09-27T18:00:00Z"], events=_day())
    out = capsys.readouterr().out
    assert code == 0 and out.startswith("Awake 7.97 of 12.00 hours")
    assert list(tmp_path.iterdir()) == [], "the tool wrote a file"
    code = awake.main(["--since", "2026-09-27T06:00:00Z", "--until",
                       "2026-09-27T18:00:00Z", "--json"], events=_day())
    parsed = json.loads(capsys.readouterr().out)
    assert code == 0 and parsed["unexpected_stops"] == 1
    assert awake.main(["--since", "2026-09-27T18:00:00Z", "--until",
                       "2026-09-27T06:00:00Z"], events=_day()) == 1


def test_an_event_log_instant_is_read_exactly():
    assert awake.parse_utc("2026-09-24T05:12:20.5000000Z") == datetime(
        2026, 9, 24, 5, 12, 20, 500000, tzinfo=timezone.utc)
    assert awake.parse_utc("2026-09-24T05:12:20+02:00") == datetime(
        2026, 9, 24, 3, 12, 20, tzinfo=timezone.utc)
    assert awake.parse_utc("not a time") is None
    assert awake.parse_utc(None) is None
