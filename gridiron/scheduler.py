"""What the OS scheduler actually holds, asked rather than assumed.

THE WHOLE POINT IS THE RE-READ. Changing a task's time from the app is two
acts: ask the OS to change it, and then ASK THE OS WHAT IT NOW HAS. Reporting
success on the strength of an exit code is how an appliance ends up with a
settings page that says 11:05 and a scheduler that still fires at 11:00 --
which is worse than not offering the setting at all, because the operator now
believes something false and has a screen agreeing with them.

This project has already lived the general version of that failure: the
appliance sat stalled for two days with every screen green, because every
screen was reporting what it had been told rather than what was true.

So `apply_time` returns what the scheduler holds AFTER the change, read back
from the OS, and `audit.schedule_claim_faults` refuses a payload that claims a
change without one. A planting proves it fires.

WINDOWS ONLY, and it says so rather than pretending. On anything else the
read returns `available: False` with a sentence, and the settings page shows
that sentence instead of an empty box.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time

#: The installer's naming, which is the only reason these are predictable.
#: `tools/schedule_install.ps1` registers "Gridiron-Predict-MLB" and friends.
PREFIX = "Gridiron-"

OS_TASK_NAMES = {
    "refresh": "Refresh",
    "resolve": "Resolve",
    "recalibrate": "Recalibrate",
    "predict:mlb": "Predict-MLB",
    "predict:nfl": "Predict-NFL",
    "predict:nba": "Predict-NBA",
    "predict:cfb": "Predict-CFB",
    "live": "Live",
}

#: A change that hangs is worse than one that fails: the page would sit there.
TIMEOUT = 20.0


class ScheduleRefused(RuntimeError):
    """A schedule change that could not be made, in words."""


def os_task_name(task: str) -> str:
    suffix = OS_TASK_NAMES.get(task)
    if suffix is None:
        raise ScheduleRefused(
            f"{task!r} is not a scheduled task this app installs. The tasks "
            f"are {', '.join(sorted(OS_TASK_NAMES))}.")
    return PREFIX + suffix


def available() -> bool:
    return sys.platform == "win32"


_START_TIME = re.compile(r"^\s*Start Time:\s*(.+?)\s*$", re.M | re.I)
_STATUS = re.compile(r"^\s*(?:Scheduled Task State|Status):\s*(.+?)\s*$", re.M | re.I)
_NEXT_RUN = re.compile(r"^\s*Next Run Time:\s*(.+?)\s*$", re.M | re.I)


#: A SHORT CACHE, because the settings page reads every scheduled task and
#: each read is a subprocess. Three of them made the page slow enough that a
#: browser test read it before the health panel had rendered -- which is a
#: real reader waiting, not just a flaky test.
#:
#: THIRTY SECONDS, and a write clears it. The scheduler changes when this app
#: changes it or when a person opens Task Scheduler; the first invalidates the
#: entry, and the second is worth up to half a minute of staleness against
#: three subprocess spawns on every page load.
CACHE_SECONDS = 30.0
_cache: dict[str, tuple[float, dict]] = {}


def forget(task: str | None = None) -> None:
    """Drop what was cached. Called after a change, so the read-back is real."""
    if task is None:
        _cache.clear()
    else:
        _cache.pop(task, None)


def read_os(task: str, *, fresh: bool = False) -> dict:
    """What the scheduler holds for this task, right now.

    HONEST WHEN IT CANNOT LOOK. A missing task, a non-Windows machine and a
    scheduler that refused the query are three different answers, and each
    gets its own sentence rather than all three collapsing into "unknown".
    """
    if not available():
        return {"available": False, "found": False, "task": task,
                "line": ("This machine has no Windows Task Scheduler, so the "
                         "app cannot say what is registered.")}
    if not fresh:
        cached = _cache.get(task)
        if cached and (time.monotonic() - cached[0]) < CACHE_SECONDS:
            return cached[1]
    name = os_task_name(task)
    try:
        done = subprocess.run(
            ["schtasks", "/Query", "/TN", name, "/V", "/FO", "LIST"],
            capture_output=True, text=True, timeout=TIMEOUT,
            stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": True, "found": False, "task": task, "os_name": name,
                "line": f"The scheduler could not be read: {type(exc).__name__}."}
    if done.returncode != 0:
        return {"available": True, "found": False, "task": task, "os_name": name,
                "line": (f"The scheduler has no task called {name}. It has not "
                         f"been installed on this machine, or it was removed.")}
    text = done.stdout or ""
    start = _START_TIME.search(text)
    status = _STATUS.search(text)
    nxt = _NEXT_RUN.search(text)
    at = _to_24h(start.group(1)) if start else None
    answer = {
        "available": True,
        "found": True,
        "task": task,
        "os_name": name,
        "at": at,
        "state": status.group(1) if status else None,
        "next_run": nxt.group(1) if nxt else None,
        "line": (f"The scheduler holds {name} at {at}."
                 if at else f"The scheduler holds {name}."),
    }
    _cache[task] = (time.monotonic(), answer)
    return answer


def _to_24h(text: str) -> str | None:
    """"11:05:00" or "11:05:00 AM" -> "11:05". None when it is neither."""
    match = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp][Mm])?", text.strip())
    if not match:
        return None
    hour, minute, meridiem = int(match.group(1)), match.group(2), match.group(3)
    if meridiem:
        upper = meridiem.upper()
        if upper == "PM" and hour != 12:
            hour += 12
        if upper == "AM" and hour == 12:
            hour = 0
    return f"{hour:02d}:{minute}"


def apply_time(task: str, at: str) -> dict:
    """Change a task's start time, then READ BACK what the scheduler holds.

    The return value always carries `read_back`. A caller cannot report a
    change without it, because there is nothing else in here to report -- and
    `audit.schedule_claim_faults` refuses a payload that tries.
    """
    name = os_task_name(task)
    if not available():
        return {
            "task": task, "asked": at, "changed": False,
            "read_back": read_os(task),
            "line": ("This machine has no Windows Task Scheduler. The setting "
                     "is recorded, and it will apply wherever the tasks are "
                     "installed."),
        }
    # POWERSHELL, NOT `schtasks /Change`, and the difference is not style.
    #
    # `schtasks /Change` PROMPTS for the run-as password on stdin -- it hung
    # for the full timeout the first time this was tried -- and when answered
    # with EOF it warns that it may have emptied the stored password, which
    # would leave the task registered and unable to run. Editing the existing
    # trigger's start boundary instead preserves the principal, the logon type
    # and any repetition pattern: the only thing that changes is the time.
    hour, minute = at.split(":")
    script = (
        f"$ErrorActionPreference='Stop';"
        f"$t = Get-ScheduledTask -TaskName '{name}';"
        f"$b = [datetime]$t.Triggers[0].StartBoundary;"
        f"$n = Get-Date -Year $b.Year -Month $b.Month -Day $b.Day "
        f"-Hour {int(hour)} -Minute {int(minute)} -Second 0;"
        f"$t.Triggers[0].StartBoundary = $n.ToString('yyyy-MM-ddTHH:mm:ss');"
        f"Set-ScheduledTask -TaskName '{name}' -Trigger $t.Triggers | Out-Null;"
        f"'changed'"
    )
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=TIMEOUT,
            stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"task": task, "asked": at, "changed": False,
                "read_back": read_os(task),
                "line": (f"The scheduler refused the change: "
                         f"{type(exc).__name__}. The setting is recorded but "
                         f"the task still runs at its old time.")}

    # FRESH, ALWAYS. A read-back served from a cache written before the change
    # would confirm the old value and call it success -- which is precisely
    # the lie this function exists to prevent.
    forget(task)
    read_back = read_os(task, fresh=True)
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        why = detail[-1][:160] if detail else "no reason given"
        return {"task": task, "asked": at, "changed": False,
                "read_back": read_back,
                "line": (f"The scheduler refused the change: {why}. The "
                         f"setting is recorded but the task still runs at its "
                         f"old time.")}

    # WHAT IT ACTUALLY HOLDS, not what was asked for. These disagree when the
    # task exists but the change did not take, which is precisely the case
    # this function exists to make visible.
    if read_back.get("found") and read_back.get("at") != at:
        return {"task": task, "asked": at, "changed": False,
                "read_back": read_back,
                "line": (f"The scheduler accepted the change but still holds "
                         f"{read_back.get('at')}. The setting is recorded; the "
                         f"task has not moved.")}
    return {"task": task, "asked": at, "changed": True, "read_back": read_back,
            "line": f"{name} now runs at {at}, and the scheduler confirms it."}
