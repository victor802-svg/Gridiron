"""Results that find you, and failures that do not wait to be found.

TWO MESSAGE TYPES, and they exist for opposite reasons.

RESULTS are the good case: the games finished, the record moved, and a person
who is not watching a screen should be told. Sent only when something actually
settled -- a notification saying "0 settled" is a notification that teaches
the reader to ignore notifications.

FAILURES are the case this project has already lived through. The appliance
sat stalled for two days with every screen green: `resolve` ran every four
hours and truthfully reported "nothing to settle" each time, because nothing
was updating `games.status`. No task failed. No error was logged. That is
exactly the moment a push exists for, and it is why the failure channel is on
by default (ruling R4).

WHAT A NOTIFICATION MAY CONTAIN: counts, team names, task names, and plain
words. WHAT IT MAY NOT: a probability, a line, a price, or any reasoning. Two
reasons, and the second is the one that binds. A push notification is the
least private surface this project has -- it lands on a lock screen, and the
ntfy topic is readable by anyone holding it. And LAW 5: a message carrying a
number somebody could act on is a tip sheet, whatever the field is called.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from . import config
from .db import utcnow

#: Where a push goes. The topic is a random 32-character string in `.env`;
#: anyone holding it can read the messages, which is why they carry counts and
#: names and nothing else.
NTFY_URL = "https://ntfy.sh/{topic}"

#: How long to wait on the push before giving up. A notifier that blocks the
#: resolve task is worse than a notification that does not arrive.
POST_TIMEOUT = 10.0

#: Quiet hours, local. Results QUEUE and arrive in one message at the end;
#: failures do not queue -- a stalled appliance at 02:00 is still stalled at
#: 07:00, and the whole point of the failure channel is that it does not wait
#: to be noticed.
QUIET_FROM = 23
QUIET_UNTIL = 7


class Blocked(RuntimeError):
    """A message that must not be sent, and why."""


#: Anything that looks like a probability, a price or a line. Crude on
#: purpose: a false positive is fixed by writing the sentence in counts, which
#: is the desired outcome anyway.
_A_PROBABILITY = re.compile(r"\b\d{1,3}(?:\.\d+)?\s*%")
#: NO WORD BOUNDARY BEFORE THE SIGN. A boundary needs a word character on
#: one side, and a space followed by '-' has none -- so the first version
#: of this let "Alabama -24.5" straight through, a LINE, in the message
#: type whose entire rule is that it carries no line. Caught by testing the
#: guard against the thing it exists to stop rather than by reading it.
#:
#: The first alternative is American odds, the second a spread or total.
_A_PRICE = re.compile(r"[-+]\d{3,}|[-+]\d+\.\d")
_A_DECIMAL_ODDS = re.compile(r"\b\d\.\d{2}\b")


def message_faults(text: str) -> list[str]:
    """Every number in a message that a reader could act on."""
    faults = []
    if _A_PROBABILITY.search(text):
        faults.append(
            f"the message contains a percentage: {text!r}. A notification "
            f"carries counts and names -- a probability on a lock screen is a "
            f"tip, and the ntfy topic is readable by anyone holding it.")
    if _A_PRICE.search(text) or _A_DECIMAL_ODDS.search(text):
        faults.append(
            f"the message contains something shaped like a price or a line: "
            f"{text!r}. LAW 5: this project states probabilities and keeps "
            f"score of them; it does not send numbers to act on.")
    return faults


def check_message(text: str) -> str:
    """Refuse a message rather than send one that breaks the rule."""
    faults = message_faults(text)
    if faults:
        raise Blocked(" ".join(faults))
    return text


def in_quiet_hours(now: datetime | None = None) -> bool:
    """Is it the middle of the night where the operator is?

    Local time on purpose: the operator's night is a fact about them, not
    about UTC.
    """
    hour = (now or datetime.now()).hour
    if QUIET_FROM <= QUIET_UNTIL:
        return QUIET_FROM <= hour < QUIET_UNTIL
    return hour >= QUIET_FROM or hour < QUIET_UNTIL


def results_message(settled_by_sport: dict) -> str | None:
    """"MLB: 7 settled - model 4 right, you 2 of 3. CFB: 60 settled..."

    NEVER SUMMED ACROSS SPORTS (LAW 6), and the sentence is built so that it
    could not be: each sport is its own clause with its own counts, and there
    is no total anywhere to be tempted by.

    None when nothing settled -- a message saying so is a message that teaches
    the reader to stop reading them.
    """
    parts = []
    for sport in config.SPORTS:
        row = settled_by_sport.get(sport)
        if not row or not row.get("settled"):
            continue
        label = config.SPORT_LABELS.get(sport, sport.upper())
        clause = f"{label}: {row['settled']} settled - model {row['right']} right"
        calls_settled = row.get("calls_settled") or 0
        if calls_settled:
            clause += f", you {row.get('calls_right', 0)} of {calls_settled}"
        parts.append(clause)
    if not parts:
        return None
    return ". ".join(parts) + "."


def failure_message(problems: list[str]) -> str | None:
    """One line naming what stopped, in the task's own words.

    The task NAME, not a code: "predict:mlb never ran" is a line somebody can
    act on at a glance, and `language.task_name` already turns the stored key
    into words for the schedule panel.
    """
    if not problems:
        return None
    if len(problems) == 1:
        return problems[0]
    return f"{problems[0]} (and {len(problems) - 1} more)"


def send_toast(title: str, body: str) -> dict:
    """A Windows toast, through PowerShell and the notification COM path.

    No third-party module: the appliance already depends on enough, and a
    notification library that stops working after an OS update is a silent
    failure in the one channel meant to report silent failures.
    """
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, "
        "Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
        "$t = [Windows.UI.Notifications.ToastNotificationManager]::"
        "GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "$n = $t.GetElementsByTagName('text'); "
        f"$n.Item(0).AppendChild($t.CreateTextNode({_ps_quote(title)})) | Out-Null; "
        f"$n.Item(1).AppendChild($t.CreateTextNode({_ps_quote(body)})) | Out-Null; "
        "$x = [Windows.UI.Notifications.ToastNotification]::new($t); "
        "[Windows.UI.Notifications.ToastNotificationManager]::"
        "CreateToastNotifier('Gridiron').Show($x);"
    )
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=POST_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"channel": "toast", "ok": False,
                "detail": f"{type(exc).__name__}: {exc}"}
    if done.returncode != 0:
        return {"channel": "toast", "ok": False,
                "detail": (done.stderr or "").strip()[:200]}
    return {"channel": "toast", "ok": True, "detail": "shown"}


def _ps_quote(text: str) -> str:
    """A PowerShell single-quoted string. Doubling is the escape."""
    return "'" + str(text).replace("'", "''") + "'"


def send_push(body: str, title: str = "Gridiron") -> dict:
    """An ntfy push to the operator's topic.

    THE TOPIC IS NEVER LOGGED, here or anywhere: it is the whole of the
    secret, and a topic in a log file is a topic in a backup.
    """
    topic = config.setting("GRIDIRON_NTFY_TOPIC")
    if not topic:
        return {"channel": "push", "ok": False,
                "detail": "no topic configured; run tools/make_token.py --ntfy"}
    request = urllib.request.Request(
        NTFY_URL.format(topic=topic),
        data=body.encode("utf-8"),
        headers={"Title": title, "Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=POST_TIMEOUT) as response:
            ok = 200 <= response.status < 300
            return {"channel": "push", "ok": ok, "detail": f"HTTP {response.status}"}
    except urllib.error.HTTPError as exc:
        return {"channel": "push", "ok": False, "detail": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001 - any failure is the same to us
        # HONEST ABOUT A FAILED POST. The schedule panel shows this verbatim:
        # a push that silently did not arrive is worse than no push channel,
        # because the operator believes they are covered.
        return {"channel": "push", "ok": False,
                "detail": f"{type(exc).__name__}: {exc}"}


def send(conn: sqlite3.Connection, kind: str, body: str,
         title: str = "Gridiron", now: datetime | None = None) -> dict:
    """Send one message on both channels and record what happened.

    Results respect quiet hours and queue; failures do not. A stalled
    appliance at 02:00 is still stalled at 07:00, and a channel that waits
    until morning to say so is not the channel this project needed.
    """
    check_message(body)
    if kind == "results" and in_quiet_hours(now):
        conn.execute(
            "INSERT INTO notifications (queued_utc, kind, title, body, state)"
            " VALUES (?,?,?,?, 'queued')", (utcnow(), kind, title, body))
        conn.commit()
        return {"queued": True, "channels": []}

    channels = [send_toast(title, body), send_push(body, title)]
    conn.execute(
        "INSERT INTO notifications (queued_utc, sent_utc, kind, title, body,"
        " state, channels_json) VALUES (?,?,?,?,?,?,?)",
        (utcnow(), utcnow(), kind, title, body,
         "sent" if any(c["ok"] for c in channels) else "failed",
         json.dumps(channels)))
    conn.commit()
    return {"queued": False, "channels": channels}


def flush_queue(conn: sqlite3.Connection, now: datetime | None = None) -> int:
    """Send what queued overnight, as ONE message. Returns how many it held."""
    if in_quiet_hours(now):
        return 0
    rows = conn.execute(
        "SELECT id, body FROM notifications WHERE state = 'queued'"
        " ORDER BY id").fetchall()
    if not rows:
        return 0
    body = " ".join(r["body"] for r in rows)
    channels = [send_toast("Gridiron", body), send_push(body)]
    for row in rows:
        conn.execute(
            "UPDATE notifications SET sent_utc = ?, state = ?, channels_json = ?"
            " WHERE id = ?",
            (utcnow(), "sent" if any(c["ok"] for c in channels) else "failed",
             json.dumps(channels), row["id"]))
    conn.commit()
    return len(rows)


def last_sent(conn: sqlite3.Connection) -> dict | None:
    """What the schedule panel shows: the last message and how each channel did."""
    row = conn.execute(
        "SELECT * FROM notifications ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    out = dict(row)
    out["channels"] = json.loads(out.pop("channels_json") or "[]")
    return out
