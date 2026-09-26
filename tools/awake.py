"""How much of a window the machine was awake, from the Windows System log.

THE OPERATOR'S RULING of 2026-09-23 (GRIDIRON_REPAIR item 7, built
2026-09-26): "every Gridiron-* task gains WakeToRun. Report awake fraction
since the fix in each close-out." This is the measurement a close-out
quotes: between two UTC instants, the share of the time the machine was
awake, and every stretch it was not, with its cause in plain words --
asleep, switched off (and by what: the power button or the sign-in screen,
the Start menu, an update's restart), or stopped without shutting down,
where the log cannot say when.

READ-ONLY, AND IT WRITES NOTHING: it asks the System log through
`Get-WinEvent` in a PowerShell child, prints, and exits. No database is
opened, no file written, no setting read or changed. Everything past the
reading is one pure function over a list of events, `measure`, so a test
hands it events and never touches the log; `read_events` takes the child
as an argument for the same reason.

WHAT IT READS, and why each (measured on this machine, September 2026):

  Kernel-General 12      the machine started; its StartTime is the instant
  Kernel-General 13      it shut down cleanly; StopTime
  Power-Troubleshooter 1 a sleep and the wake that ended it: SleepTime and
                         WakeTime, the only trustworthy wake time -- Kernel-
                         Power 107 is stamped about a second after the sleep
                         began, not at the wake, and is ignored -- and the
                         wake's source, including the timer that woke it
                         (the only evidence a WakeToRun task ever did)
  Kernel-Power 42        a sleep began; one with no Power-Troubleshooter 1
                         beside it never recorded a wake, and counts as
                         asleep until the next start
  Kernel-Power 41,       the start after a stop that was not a shutdown: the
  EventLog 6008          log cannot say when it went off, so the time from
                         the last thing it recorded to that start is NOT
                         KNOWN, counted apart and never guessed
  User32 1074            who shut it down or restarted it, and why: from
                         winlogon for SYSTEM with "power off" (reason
                         0x500ff) is the power button or the sign-in screen;
                         TrustedInstaller or an "Operating System: Upgrade"
                         reason is an update's restart
  EventLog 6005, 6006,   and every other event read, only as evidence the
  Kernel-Power 109, 172, machine was on at that moment
  Kernel-General 1

    python tools/awake.py --since 2026-09-27T00:00:00Z
    python tools/awake.py --since 2026-09-27T00:00:00Z --until 2026-10-04T00:00:00Z --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

KERNEL_GENERAL = "Microsoft-Windows-Kernel-General"
KERNEL_POWER = "Microsoft-Windows-Kernel-Power"
TROUBLESHOOTER = "Microsoft-Windows-Power-Troubleshooter"
USER32 = "User32"
EVENTLOG = "EventLog"

#: The events asked for, by provider. An id alone is not enough: Hyper-V
#: logs a 42 and Wininit a 12 on every start of this machine.
WANTED: dict[str, tuple[int, ...]] = {
    KERNEL_GENERAL: (1, 12, 13),
    KERNEL_POWER: (41, 42, 107, 109, 172),
    TROUBLESHOOTER: (1,),
    USER32: (1074,),
    EVENTLOG: (6005, 6006, 6008),
}

#: How far before the window the log is read, so the state the window opens
#: in (on, asleep, off) is known rather than assumed.
LOOK_BACK_DAYS = 30

#: A shutdown's cause is the 1074 written at most this long before it.
CAUSE_WITHIN = timedelta(minutes=30)

#: A Kernel-Power 42 and a Power-Troubleshooter 1 are one sleep when their
#: sleep times are this close.
SAME_SLEEP = timedelta(minutes=2)

STATE_WORDS = {"on": "awake", "asleep": "asleep", "off": "switched off",
               "unknown": "not known"}

_STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?$")


class ReadRefused(RuntimeError):
    """The log could not be read, said in words."""


def parse_utc(text) -> datetime | None:
    """An event log instant ("2026-09-24T05:12:20.5000000Z", seven places of
    fraction, or an offset) as an aware UTC datetime; None if it is not one."""
    if not text:
        return None
    m = _STAMP.match(str(text).strip())
    if m is None:
        return None
    base = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
    fraction = (m.group(2) or ".0")[1:7].ljust(6, "0")
    when = base.replace(microsecond=int(fraction))
    zone = m.group(3) or "Z"
    if zone == "Z":
        return when.replace(tzinfo=timezone.utc)
    sign = 1 if zone[0] == "+" else -1
    offset = timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6]))
    return (when - sign * offset).replace(tzinfo=timezone.utc)


def iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# the pure part: events in, a measurement out
# ---------------------------------------------------------------------------

def _why_off(initiated: dict | None) -> str:
    """Why the machine went off, from the 1074 that asked for it."""
    if not initiated:
        return "shut down; the log names no cause"
    process = str(initiated.get("param1") or "")
    exe = process.split(" (")[0].rsplit("\\", 1)[-1].lower()
    reason = str(initiated.get("param3") or "")
    kind = str(initiated.get("param5") or "").lower()
    restart = "restart" in kind
    if (exe in ("trustedinstaller.exe", "monotificationux.exe",
                "musnotification.exe", "usoclient.exe")
            or reason.lower().startswith("operating system:")):
        return "restarted for a Windows update"
    if exe == "winlogon.exe":
        return ("restarted" if restart else "powered off") + \
            " from the power button or the sign-in screen"
    if exe == "startmenuexperiencehost.exe":
        return ("restarted" if restart else "shut down") + " from the Start menu"
    name = exe or "an unnamed program"
    return ("restarted" if restart else "shut down") + f" by {name}"


def _wake_words(info: dict) -> str:
    timer = info.get("timer")
    if timer:
        return f"woken by a timer ({timer})"
    source = info.get("source")
    if source:
        return f"woken by {source}"
    if info.get("no_wake"):
        return ("no wake was recorded, so it lost power or was started "
                "afresh while asleep")
    return "the log names no wake source"


def _marks(events: list[dict]) -> tuple[list[tuple], list[datetime], list[tuple]]:
    """Transitions and signs of life, in time order; the unexpected starts;
    and the shutdown requests (1074), each with its data."""
    marks: list[tuple] = []
    unexpected: list[datetime] = []
    initiated: list[tuple] = []
    sleeps_with_wakes: list[datetime] = []
    bare_sleeps: list[datetime] = []
    order = {"seen": 0, "shutdown": 1, "sleep": 1, "boot": 2, "wake": 2}
    for event in events:
        provider = str(event.get("provider") or "")
        number = int(event.get("id") or 0)
        data = event.get("data") or {}
        when = parse_utc(event.get("time"))
        if when is None:
            continue
        if event.get("bound"):
            marks.append((when, "seen", {}))
        elif provider == KERNEL_GENERAL and number == 12:
            marks.append((parse_utc(data.get("StartTime")) or when, "boot", {}))
        elif provider == KERNEL_GENERAL and number == 13:
            marks.append((parse_utc(data.get("StopTime")) or when, "shutdown", {}))
        elif provider == TROUBLESHOOTER and number == 1:
            slept, woke = parse_utc(data.get("SleepTime")), parse_utc(data.get("WakeTime"))
            if slept is None or woke is None:
                continue
            owner = " ".join(str(data.get(k) or "").strip()
                             for k in ("WakeTimerOwner", "WakeTimerContext")).strip()
            marks.append((slept, "sleep", {}))
            marks.append((woke, "wake", {"timer": owner,
                                         "source": str(data.get("WakeSourceText") or "").strip()}))
            sleeps_with_wakes.append(slept)
        elif provider == KERNEL_POWER and number == 42:
            bare_sleeps.append(when)
        elif provider == KERNEL_POWER and number == 107:
            continue            # stamped at the sleep's start, not its wake
        elif (provider, number) in ((KERNEL_POWER, 41), (EVENTLOG, 6008)):
            unexpected.append(when)
        elif provider == USER32 and number == 1074:
            initiated.append((when, data))
        else:
            marks.append((when, "seen", {}))
    for slept in bare_sleeps:
        if not any(abs(slept - s) <= SAME_SLEEP for s in sleeps_with_wakes):
            marks.append((slept, "sleep", {"no_wake": True}))
    marks.sort(key=lambda m: (m[0], order[m[1]]))
    return marks, sorted(unexpected), sorted(initiated, key=lambda i: i[0])


def _step(state: str, why: str, last_on, when: datetime, kind: str, info: dict,
          cause_of_shutdown) -> tuple[str, str, datetime | None]:
    """The state after one mark: (state, why it is in it, last sign of life)."""
    if kind == "seen":
        return ("on", "", when) if state in ("on", "unknown") else (state, why, last_on)
    if kind in ("boot", "wake"):
        return "on", "", when
    if kind == "shutdown":
        return (state, why, last_on) if state == "off" else \
            ("off", cause_of_shutdown(when), last_on)
    # a sleep; one that never recorded a wake says so on its stretch
    if state == "asleep":
        return state, why, last_on
    return "asleep", _wake_words(info) if info.get("no_wake") else "", last_on


def measure(events: list[dict], since: datetime, until: datetime) -> dict:
    """The window's hours awake, asleep, off and not known, and every
    stretch it was not awake with its cause. `events` are dicts of
    provider, id, time (UTC) and data, as `read_events` returns them."""
    if until <= since:
        raise ValueError("the window ends before it starts")
    marks, unexpected, initiated = _marks(events)

    def cause_of_shutdown(at: datetime) -> str:
        asked = [d for t, d in initiated if at - CAUSE_WITHIN <= t <= at]
        return _why_off(asked[-1] if asked else None)

    # THE STATE THE WINDOW OPENS IN, from what the log holds before it.
    state, why, last_on = "unknown", "the log holds nothing before this window", None
    for when, kind, info in marks:
        if when > since:
            break
        state, why, last_on = _step(state, why, last_on, when, kind, info,
                                    cause_of_shutdown)
    if state == "on":
        last_on = since
    stretches: list[dict] = []
    cursor = since

    def close(end: datetime, as_state: str, words: str) -> None:
        nonlocal cursor
        if end > cursor:
            stretches.append({"start": cursor, "end": end, "state": as_state,
                              "why": words})
            cursor = end

    for when, kind, info in marks:
        if when <= since:
            continue
        if when > until:
            break
        after = _step(state, why, last_on, when, kind, info, cause_of_shutdown)
        if kind == "boot" and state == "on":
            # IT STOPPED WITHOUT SHUTTING DOWN: awake until the last thing
            # the log recorded, then NOT KNOWN until this start -- never
            # guessed either way.
            seen = max(last_on or cursor, cursor)
            close(seen, "on", "")
            dirty = any(when - timedelta(minutes=5) <= u <= when + timedelta(minutes=10)
                        for u in unexpected)
            close(when, "unknown",
                  "stopped without shutting down"
                  + (" (the next start logged an unexpected shutdown)" if dirty else "")
                  + f"; last seen awake {_when_words(iso(seen))}")
        elif after[0] != state:
            # A TRANSITION: the stretch in the old state ends here, and an
            # asleep one is said by the wake that ended it.
            close(when, state, why or (_wake_words(info) if kind == "wake" else ""))
        state, why, last_on = after
    close(until, state,
          why or ("still asleep when the window ends" if state == "asleep" else ""))

    totals = {s: 0.0 for s in STATE_WORDS}
    for stretch in stretches:
        stretch["hours"] = (stretch["end"] - stretch["start"]).total_seconds() / 3600.0
        totals[stretch["state"]] += stretch["hours"]
    hours = (until - since).total_seconds() / 3600.0
    timer_wakes = [iso(when) for when, kind, info in marks
                   if kind == "wake" and since < when <= until and info.get("timer")]
    return {
        "since": iso(since), "until": iso(until), "hours": hours,
        "awake_hours": totals["on"], "asleep_hours": totals["asleep"],
        "off_hours": totals["off"], "unknown_hours": totals["unknown"],
        "awake_fraction": totals["on"] / hours,
        "gaps": [{"start": iso(s["start"]), "end": iso(s["end"]),
                  "hours": s["hours"], "state": STATE_WORDS[s["state"]],
                  "why": s["why"]}
                 for s in stretches if s["state"] != "on"],
        "timer_wakes": timer_wakes,
        "unexpected_stops": sum(1 for u in unexpected if since < u <= until),
    }


def _when_words(stamp: str) -> str:
    when = parse_utc(stamp)
    return f"{when.day} {when:%B %Y} {when:%H:%M} UTC" if when else stamp


def words(report: dict) -> list[str]:
    """The measurement as a close-out quotes it."""
    lines = [
        f"Awake {report['awake_hours']:.2f} of {report['hours']:.2f} hours, "
        f"{report['awake_fraction'] * 100:.1f}%, from {_when_words(report['since'])} "
        f"to {_when_words(report['until'])}.",
        f"Asleep {report['asleep_hours']:.2f} hours, switched off "
        f"{report['off_hours']:.2f} hours, not known {report['unknown_hours']:.2f} "
        f"hours" + (" (each such stretch below says why the log cannot tell)"
                    if report["unknown_hours"] else "") + ".",
        f"Woken by a timer {len(report['timer_wakes'])} "
        f"{'time' if len(report['timer_wakes']) == 1 else 'times'}: the only "
        f"evidence a task set to wake the machine ever did.",
    ]
    if report["gaps"]:
        lines.append("Every stretch it was not awake:")
        for gap in report["gaps"]:
            lines.append(f"  {_when_words(gap['start'])} to {_when_words(gap['end'])}, "
                         f"{gap['hours']:.2f} hours, {gap['state']}"
                         + (f": {gap['why']}" if gap["why"] else ""))
    else:
        lines.append("It was awake the whole window.")
    return lines


# ---------------------------------------------------------------------------
# the reading: the System log, through a PowerShell child, and nothing else
# ---------------------------------------------------------------------------

def _powershell(script: str) -> str:
    """Run a READ-ONLY script in a PowerShell child and return what it printed."""
    done = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-Command", script],
        capture_output=True, timeout=300)
    if done.returncode != 0:
        raise ReadRefused("the System log could not be read: "
                          + done.stderr.decode("utf-8", "replace").strip()[:400])
    return done.stdout.decode("utf-8", "replace").lstrip(chr(0xFEFF))


_READ = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$inv = [Globalization.CultureInfo]::InvariantCulture
$wanted = @{ WANTED }
$from = [DateTimeOffset]::Parse('FROM', $inv).LocalDateTime
$until = [DateTimeOffset]::Parse('UNTIL', $inv).LocalDateTime
try {
    $events = @(Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName=@($wanted.Keys); StartTime=$from; EndTime=$until})
} catch {
    if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { $events = @() } else { throw }
}
$out = @(foreach ($e in $events) {
    if (-not ($wanted[$e.ProviderName] -contains $e.Id)) { continue }
    $d = [ordered]@{}
    $i = 0
    foreach ($n in ([xml]$e.ToXml()).Event.EventData.Data) {
        if ($n -is [string]) { $d["param$i"] = $n }
        else { $k = $n.Name; if (-not $k) { $k = "param$i" }; $d[$k] = $n.'#text' }
        $i++
    }
    [pscustomobject]@{ provider = $e.ProviderName; id = $e.Id;
        time = $e.TimeCreated.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ', $inv);
        data = $d }
})
ConvertTo-Json -InputObject $out -Depth 4 -Compress
"""

_LAST_BEFORE = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$inv = [Globalization.CultureInfo]::InvariantCulture
$out = @(foreach ($s in @(INSTANTS)) {
    $end = [DateTimeOffset]::Parse($s, $inv).LocalDateTime.AddSeconds(-1)
    try { $e = Get-WinEvent -FilterHashtable @{LogName='System'; EndTime=$end} -MaxEvents 1 }
    catch { if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { $e = $null } else { throw } }
    if ($e) {
        [pscustomobject]@{ provider = $e.ProviderName; id = $e.Id;
            time = $e.TimeCreated.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ', $inv);
            data = @{}; bound = $true; before = $s }
    }
})
ConvertTo-Json -InputObject $out -Depth 3 -Compress
"""


def _rows(text: str) -> list[dict]:
    """The events a child printed: a JSON list (or, from PowerShell, one
    object alone), empty entries dropped."""
    text = (text or "").strip()
    if not text:
        return []
    rows = json.loads(text)
    return [row for row in (rows if isinstance(rows, list) else [rows])
            if isinstance(row, dict)]


def read_events(since: datetime, until: datetime, *, run=None,
                look_back_days: int = LOOK_BACK_DAYS) -> list[dict]:
    """Every event `measure` reads between `look_back_days` before `since`
    and `until`, plus, for each start that followed no shutdown and no
    sleep, the last event the log holds before it (the last sign the
    machine was on). `run` runs a PowerShell script and returns its output;
    the real one is a child process, and a test passes its own."""
    run = run or _powershell
    wanted = "; ".join(f"'{provider}' = @({', '.join(str(i) for i in ids)})"
                       for provider, ids in WANTED.items())
    script = (_READ.replace("WANTED", wanted)
              .replace("FROM", iso(since - timedelta(days=look_back_days)))
              .replace("UNTIL", iso(until)))
    events = _rows(run(script))
    marks, _unexpected, _initiated = _marks(events)
    unclean, state = [], None
    for when, kind, _info in marks:
        if kind == "boot" and state == "on":
            unclean.append(iso(when))
        if kind in ("boot", "wake"):
            state = "on"
        elif kind in ("shutdown", "sleep"):
            state = "down"
    if unclean:
        listed = ", ".join(f"'{stamp}'" for stamp in unclean)
        events += _rows(run(_LAST_BEFORE.replace("INSTANTS", listed)))
    return events


def main(argv=None, *, events=None) -> int:
    parser = argparse.ArgumentParser(
        description="How much of a window the machine was awake, read from "
                    "the Windows System log. Reads only; writes nothing.")
    parser.add_argument("--since", required=True,
                        help="the window's start, UTC, e.g. 2026-09-27T00:00:00Z")
    parser.add_argument("--until", default=None,
                        help="the window's end, UTC (default: now)")
    parser.add_argument("--json", action="store_true",
                        help="print the measurement as JSON")
    args = parser.parse_args(argv)
    since = parse_utc(args.since)
    until = parse_utc(args.until) if args.until else datetime.now(timezone.utc)
    if since is None or until is None:
        parser.error("--since and --until are UTC instants such as "
                     "2026-09-27T00:00:00Z")
    try:
        found = events if events is not None else read_events(since, until)
        report = measure(found, since, until)
    except (ReadRefused, ValueError) as exc:
        print(f"awake: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n".join(words(report)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
