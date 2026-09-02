"""Operational settings, and the fence around everything that is not one.

THE FENCE IS THE POINT OF THIS MODULE. Two kinds of number live in this
project and they look identical in a config file:

  OPERATIONAL: when the prediction task runs, when quiet hours start, whether
  failure notifications are on. These are preferences. The operator should be
  able to change them from the app at 23:00 without opening an editor, and
  getting one wrong costs a late slate, not a corrupted record.

  MODEL AND LAW: the props floor, the prop ladders, the sample gates, the
  factor sets, the margin standard deviations. Changing one of these changes
  what the record MEANS. Every figure already written was produced under the
  old value, and a curve computed across a change nobody recorded is a curve
  describing two different models at once.

So the second kind is SHOWN, never edited here, each with the date it was
declared and a line saying that changing it is a ruling. `EDITABLE` is a
closed list; anything not in it is refused BY NAME, and a planting adds a
model constant to a settings form to prove the refusal fires.

APPEND-ONLY. A change writes a new row (`schema.sql` has the triggers). A
settings row is the record of a decision -- "at 21:40 the operator moved the
baseball slate to 11:05" -- and updating in place would destroy the only
evidence of when a schedule changed and what from. That is exactly the
evidence somebody wants when a slate is missed and nobody can remember
whether the time moved.

SECRETS ARE NOT SETTINGS. The access token and the ntfy topic stay in `.env`,
outside the database and outside any backup of it. They appear here only as a
masked display and a "rotate" action that runs `tools/make_token.py`.
"""

from __future__ import annotations

import re
import sqlite3

from . import config, language
from .db import utcnow


class SettingRefused(RuntimeError):
    """A settings write that may not happen, and why, in words."""


# ---------------------------------------------------------------------------
# what may be changed
# ---------------------------------------------------------------------------

_TIME = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")


def _a_time(value: str) -> str:
    if not _TIME.match(value.strip()):
        raise SettingRefused(
            f"{value!r} is not a time of day. Write it as 24-hour local time, "
            f"like 11:00 or 23:30.")
    return value.strip()


def _an_hour(value: str) -> str:
    try:
        hour = int(str(value).strip())
    except (TypeError, ValueError):
        raise SettingRefused(
            f"{value!r} is not an hour. Write a whole number from 0 to 23.") from None
    if not 0 <= hour <= 23:
        raise SettingRefused(
            f"{hour} is not an hour of the day. Quiet hours run on a 24-hour "
            f"clock, so 0 to 23.")
    return str(hour)


def _a_switch(value: str) -> str:
    text = str(value).strip().lower()
    if text in ("1", "true", "on", "yes"):
        return "1"
    if text in ("0", "false", "off", "no"):
        return "0"
    raise SettingRefused(f"{value!r} is not on or off.")


#: THE CLOSED LIST. A name not here cannot be written, whatever the form says.
#:
#: Each entry says what it is in the words the page shows, so the interface
#: composes no labels of its own -- the plain-words law applies to a settings
#: page exactly as it applies to a pick card.
EDITABLE: dict[str, dict] = {
    "predict_mlb_at": {
        "label": "Predict MLB",
        "why": "daily, after most probable starters post",
        "section": "when it runs",
        "kind": "time",
        "check": _a_time,
        "default": "11:00",
        "task": "predict:mlb",
    },
    "predict_nfl_at": {
        "label": "Predict NFL",
        "why": "weekly, on Wednesday morning",
        "section": "when it runs",
        "kind": "time",
        "check": _a_time,
        "default": "09:00",
        "task": "predict:nfl",
    },
    "predict_cfb_at": {
        "label": "Predict college football",
        "why": "daily -- a college week is three different slates",
        "section": "when it runs",
        "kind": "time",
        "check": _a_time,
        "default": "10:00",
        "task": "predict:cfb",
    },
    "quiet_from": {
        "label": "Quiet hours start",
        "why": "results queue overnight and arrive in one message",
        "section": "quiet hours",
        "kind": "hour",
        "check": _an_hour,
        "default": "23",
    },
    "quiet_until": {
        "label": "Quiet hours end",
        "why": "the queued message is sent at this hour",
        "section": "quiet hours",
        "kind": "hour",
        "check": _an_hour,
        "default": "7",
    },
    "notify_results": {
        "label": "Tell me when results land",
        "why": "sent only when something actually settled",
        "section": "notifications",
        "kind": "switch",
        "check": _a_switch,
        "default": "1",
    },
    "notify_failures": {
        "label": "Tell me when something stops",
        "why": ("a missed slate, a task silent over 36 hours, a red gate. On "
                "by default: the appliance once sat stalled for two days with "
                "every screen green"),
        "section": "notifications",
        "kind": "switch",
        "check": _a_switch,
        "default": "1",
    },
}


#: SHOWN, NEVER EDITED HERE. Each carries the date it was declared, because a
#: constant without one cannot be told from a value somebody typed.
#:
#: The `note` is the same sentence on every row on purpose. It is not a
#: warning about this page; it is what the project already believes about
#: these numbers, said where somebody might otherwise go looking for a text
#: box.
FENCED_NOTE = ("Changing this is a ruling. Edit config.py with a dated note "
               "and say why in the commit.")


def fenced() -> list[dict]:
    """The model and law constants, with their dates. Read-only, always."""
    return [
        {
            "name": "PROPS_MIN_CLAIM",
            "label": "The props floor",
            "value": f"{config.PROPS_MIN_CLAIM:.0%}",
            "declared": config.PROPS_MIN_CLAIM_DECLARED[:10],
            "what": ("A prop question is only asked when the model claims at "
                     "least this much. Below it the model is guessing with "
                     "extra steps."),
            "note": FENCED_NOTE,
        },
        {
            "name": "MLB_PROP_LADDER",
            "label": "The baseball prop ladders",
            # HUMANISED, like everything else a reader sees. This printed the
            # stored keys -- "batter_hits: 0.5/1.5/2.5" -- and the plain-words
            # scan caught all three the first time the page was scanned.
            "value": ", ".join(
                f"{language.humanise(stat)}: {'/'.join(str(r) for r in rungs)}"
                for stat, rungs in list(config.MLB_PROP_LADDER.items())[:3]),
            "declared": config.MLB_PROP_LADDER_DECLARED[:10],
            "what": ("The rungs a question may be asked at. A question formed "
                     "off the ladder is refused by name."),
            "note": FENCED_NOTE,
        },
        {
            "name": "MIN_SAMPLE_FOR_BUCKET_POINT",
            "label": "Settled predictions before a tier gets a verdict",
            "value": str(config.MIN_SAMPLE_FOR_BUCKET_POINT),
            "declared": "2026-08-24",
            "what": "LAW 4: no claim below sample.",
            "note": FENCED_NOTE,
        },
        {
            "name": "MIN_SAMPLE_FOR_EDGE_CLAIM",
            "label": "Settled predictions before an edge may be claimed",
            "value": str(config.MIN_SAMPLE_FOR_EDGE_CLAIM),
            "declared": "2026-08-24",
            "what": ("LAW 4 again, and the higher bar: beating the market on "
                     "a small sample is the expected behaviour of luck."),
            "note": FENCED_NOTE,
        },
        {
            "name": "FACTOR_SET_VERSION",
            "label": "The factor set in force",
            # THE CODE IS THE VALUE HERE. A factor set has no plain name -- it
            # is an identifier stamped onto every prediction so a curve can
            # say which model produced it, and a reader matching a row against
            # `predictions.factor_set_version` needs the literal. Marked as
            # sanctioned code so it renders as one.
            "value": config.FACTOR_SET_VERSION,
            "literal": True,
            "declared": config.FACTOR_SET_ACTIVATED.get(
                config.FACTOR_SET_VERSION, "")[:10],
            "what": ("LAW 2: factors are declared in advance with a rationale "
                     "and scored from the date they were added."),
            "note": FENCED_NOTE,
        },
        {
            "name": "EDGE_DISAGREEMENT_THRESHOLD",
            "label": "What counts as disagreeing with the market",
            "value": f"{config.EDGE_DISAGREEMENT_THRESHOLD:.0%}",
            "declared": "2026-08-24",
            "what": "The gap at which a pick joins the drift question.",
            "note": FENCED_NOTE,
        },
    ]


# ---------------------------------------------------------------------------
# reading and writing
# ---------------------------------------------------------------------------

def current(conn: sqlite3.Connection) -> dict:
    """Every operational setting and its value now, defaults included.

    A NAME WITH NO ROW IS AT ITS DEFAULT, and the default is declared beside
    the setting rather than left implicit in whatever the code happened to do
    before anybody changed it.
    """
    rows = {
        r["name"]: r["value"] for r in conn.execute(
            "SELECT name, value FROM settings WHERE id IN ("
            "  SELECT MAX(id) FROM settings GROUP BY name)")
    }
    return {name: rows.get(name, spec["default"])
            for name, spec in EDITABLE.items()}


def value(conn: sqlite3.Connection, name: str) -> str:
    return current(conn).get(name, EDITABLE[name]["default"])


def set_value(conn: sqlite3.Connection, name: str, raw: str,
              *, note: str | None = None) -> dict:
    """Record a change. Refuses anything outside the fence, BY NAME.

    The refusal names the setting and says what the page may change, because
    "invalid setting" tells an operator nothing about whether they mistyped a
    name or asked for something this page will never do.
    """
    spec = EDITABLE.get(name)
    if spec is None:
        raise SettingRefused(
            f"{name!r} is not an operational setting, so it cannot be changed "
            f"here. This page changes when tasks run, quiet hours and which "
            f"notifications are on. Model and law constants -- the props "
            f"floor, the ladders, the sample gates, the factor sets -- are "
            f"shown read-only: changing one of those is a ruling, made in "
            f"config.py with a dated note, because every figure already "
            f"written was produced under the old value."
        )
    checked = spec["check"](raw)
    was = value(conn, name)
    if checked == was:
        return {"name": name, "value": checked, "changed": False,
                "was": was, "line": f"{spec['label']} is already {checked}."}
    conn.execute(
        "INSERT INTO settings (changed_utc, name, value, previous, note)"
        " VALUES (?,?,?,?,?)",
        (utcnow(), name, checked, was, note))
    conn.commit()
    return {"name": name, "value": checked, "changed": True, "was": was,
            "line": f"{spec['label']} changed from {was} to {checked}."}


def history(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Recent changes, newest first. Never edited, so this is the whole truth."""
    return [
        {
            "when": r["changed_utc"],
            "name": r["name"],
            "label": EDITABLE.get(r["name"], {}).get("label", r["name"]),
            "value": r["value"],
            "previous": r["previous"],
            "note": r["note"],
        }
        for r in conn.execute(
            "SELECT * FROM settings ORDER BY id DESC LIMIT ?", (limit,))
    ]
