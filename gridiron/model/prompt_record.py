"""The prompt record: what the reasoning pass was sent, kept with every
forecast it writes. THE ONE DOOR to the `reasoning_prompts` table.

THE RULINGS. Two additions, 2026-09-24, item 1: "The reasoning pass stores
the exact prompt it sent, or its hash plus the full inputs, with every row it
writes, append-only. No reasoning row may exist without it; planting." And
the ruling on question 4, 2026-09-25: "the prompt-record rule binds from the
release that ships it, and the gap before it is labelled, not exempted."

WHY. Until this module the prompt was a local variable in `llm.reason`: built,
sent, and gone. 467 reasoning forecasts reached the live record between 2
and 25 September with nothing saying what the model had been told, so a
forecast that read oddly could not be checked against its own input, and a
change to the prompt code could not be told apart from a change in the model.

TWO KINDS, and each is refused where it does not belong (`schema.sql`):

  * SENT -- the exact request, every message, the system prompt, the model and
    its parameters, as canonical JSON with its SHA-256, serialized BEFORE it
    is sent and sent as the parse of those bytes, so what is stored is what
    left by construction. Written by `keep_sent`, on the forecast's own
    transaction and before it; the forecast cites it in its frozen,
    fingerprinted factors (`reasoning_prompt_id`), so the `predictions` table,
    its protected fields and the record's baseline hash are unchanged.
  * RECONSTRUCTED -- for a forecast written before the release instant: the
    request rebuilt from what the forecast stored, through the prompt code of
    the commit the scheduler was running when it was written
    (`tools/reconstruct_prompts.py`), with that commit, the day it was
    rebuilt, and words saying what the commit can and cannot vouch for. It is
    never presented as the prompt sent: the page labels it "reconstructed" in
    that word (`language.prompt_label`).

THE RELEASE INSTANT is data, not a literal: `write_the_release_instant`, run
by `db.init`, writes it once into `meta`, and the trigger and the gate read it
from there.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from .. import config
from ..db import just_after, utcnow

KIND_SENT = "sent"
KIND_RECONSTRUCTED = "reconstructed"
KINDS = (KIND_SENT, KIND_RECONSTRUCTED)

#: The `meta` key the release instant is written under, once.
BINDS_FROM = "prompt_record_binds_from"

#: The key in a reasoning forecast's frozen factors that names its sent record.
CITE = "reasoning_prompt_id"

#: What a request to the model carries, and nothing else: the four keyword
#: arguments `messages.create` is called with.
REQUEST_KEYS = ("max_tokens", "messages", "model", "system")

#: UNTIL ABOUT THIS MINUTE THE SCHEDULER RAN THE MAIN CHECKOUT'S WORKING TREE,
#: uncommitted edits and all (FOLLOWUPS, "the scheduler runs the working
#: tree"; the worktree rule of the evening of 23 September). A reconstruction
#: of a forecast written before it names the commit as the committed code
#: nearest the run, not as proof of the code that ran.
WORKING_TREE_UNTIL = "2026-09-23T22:47:00Z"


class PromptNotKept(RuntimeError):
    """A reasoning forecast, or its prompt record, could not be written as
    the rule requires. Raised by name, before anything is committed."""


def canonical(request: dict) -> str:
    """THE ONE SERIALIZATION: keys sorted, no spaces, UTF-8 as itself. Two
    equal requests give the same bytes, so one hash names one request."""
    return json.dumps(request, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(text: str) -> str:
    """The SHA-256 of a stored text's UTF-8 bytes, as lower-case hex."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def binds_from(conn: sqlite3.Connection) -> str | None:
    """The release instant, or None on a database that has not been opened
    under the schema that ships the rule."""
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?",
                           (BINDS_FROM,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return None if row is None else row[0]


def write_the_release_instant(conn: sqlite3.Connection) -> str | None:
    """Write the release instant, once. Idempotent; returns what is stored.

    ONE STATEMENT, so two tasks opening the record in the same minute cannot
    both write it: the second finds the row and inserts nothing, and the
    schema refuses any other way in.

    NEVER BEFORE A FORECAST ALREADY WRITTEN. The instant is now, or one second
    after the newest reasoning forecast on the record if that is later: a row
    that old code wrote in the same second as this open is before the
    instant, and is reconstructed like the rest, rather than being after it
    with no sent record that code could never have written.
    """
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not {"meta", "predictions", "reasoning_prompts"} <= tables:
        return None
    latest = conn.execute(
        "SELECT MAX(created_utc) FROM predictions WHERE predictor = 'llm'"
    ).fetchone()[0]
    instant = just_after(latest)
    conn.execute(
        "INSERT INTO meta (key, value) SELECT ?, ?"
        " WHERE NOT EXISTS (SELECT 1 FROM meta WHERE key = ?)",
        (BINDS_FROM, instant, BINDS_FROM))
    conn.commit()
    return binds_from(conn)


@dataclass(frozen=True)
class SentPrompt:
    """What the reasoning pass sent, as the bytes it was sent from."""
    request_json: str
    sent_utc: str
    repair_json: str | None = None
    llm_call_id: int | None = None

    @property
    def request(self) -> dict:
        return json.loads(self.request_json)


def sent(request: dict, *, sent_utc: str | None = None,
         repair: dict | None = None, llm_call_id: int | None = None) -> SentPrompt:
    """A `SentPrompt` from the request dicts, serialized the one way."""
    return SentPrompt(canonical(request), sent_utc or utcnow(),
                      None if repair is None else canonical(repair), llm_call_id)


def _secrets() -> list[str]:
    """Values that may never travel in a prompt: the model's key and the
    page's access token. None can by construction -- the request is built
    from the system text, the model's name, a number and the prompt's own
    text -- and this is the backstop that says so if that ever changes."""
    values = [config.ANTHROPIC_API_KEY, config.setting("GRIDIRON_ACCESS_TOKEN")]
    return [v for v in values if v and len(v) >= 8]


def _checked(text: str | None, what: str, *, required: bool = True) -> None:
    """Refuse a request that is not one canonical request, by name."""
    if text is None:
        if required:
            raise PromptNotKept(f"THE PROMPT RECORD NEEDS THE {what.upper()}: "
                                f"none was given")
        return
    try:
        request = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise PromptNotKept(f"the {what} is not JSON: {exc}") from exc
    if not isinstance(request, dict) or tuple(sorted(request)) != REQUEST_KEYS:
        raise PromptNotKept(
            f"the {what} must carry exactly {', '.join(REQUEST_KEYS)}, which "
            f"is what the model is sent; this one carries "
            f"{sorted(request) if isinstance(request, dict) else type(request).__name__}")
    messages = request["messages"]
    if (not isinstance(messages, list) or not messages
            or not all(isinstance(m, dict) and set(m) == {"role", "content"}
                       and isinstance(m["content"], str) for m in messages)):
        raise PromptNotKept(f"the {what}'s messages are not a list of role and "
                            f"content")
    if canonical(request) != text:
        raise PromptNotKept(
            f"the {what} is not in its canonical form (keys sorted, no spaces), "
            f"so its hash would not name it")
    for secret in _secrets():
        if secret in text:
            raise PromptNotKept(
                f"the {what} carries a secret value -- the model's key or the "
                f"page's access token -- and a prompt record is read on the "
                f"page. Nothing was written.")


def keep_sent(conn: sqlite3.Connection, prompt: SentPrompt, *,
              game_id: str, claim: str) -> int:
    """Write the sent record of one reasoning forecast, and return its id.

    NOT COMMITTED HERE: the caller is `predict.write_prediction`, which writes
    the forecast citing this id on the same transaction and commits both, or
    neither. A forecast from the release instant on is refused by the schema
    unless the record it cites was written first.
    """
    if not isinstance(prompt, SentPrompt):
        raise PromptNotKept(
            "A REASONING FORECAST IS WRITTEN WITH THE PROMPT IT WAS SENT (the "
            "ruling of 2026-09-24, two additions, item 1); none was given")
    _checked(prompt.request_json, "request")
    _checked(prompt.repair_json, "reformatting request", required=False)
    cur = conn.execute(
        "INSERT INTO reasoning_prompts (kind, game_id, claim, request_json,"
        " request_sha256, repair_json, repair_sha256, sent_utc, llm_call_id)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (KIND_SENT, game_id, claim, prompt.request_json,
         digest(prompt.request_json), prompt.repair_json,
         None if prompt.repair_json is None else digest(prompt.repair_json),
         prompt.sent_utc, prompt.llm_call_id))
    return int(cur.lastrowid)


def keep_reconstructed(conn: sqlite3.Connection, *, prediction_id: int,
                       game_id: str, claim: str, request_json: str,
                       code_version: str, provenance: str,
                       reconstructed_utc: str | None = None,
                       llm_call_id: int | None = None) -> int:
    """Write the reconstructed record of one forecast written before the
    release instant, and return its id. Not committed here: the one caller,
    `tools/reconstruct_prompts.py`, commits each forecast's record."""
    _checked(request_json, "reconstructed request")
    cur = conn.execute(
        "INSERT INTO reasoning_prompts (kind, prediction_id, game_id, claim,"
        " request_json, request_sha256, llm_call_id, code_version,"
        " reconstructed_utc, provenance) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (KIND_RECONSTRUCTED, prediction_id, game_id, claim, request_json,
         digest(request_json), llm_call_id, code_version,
         reconstructed_utc or utcnow(), provenance))
    return int(cur.lastrowid)


def _table_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        " AND name = 'reasoning_prompts'").fetchone() is not None


def records_for(conn: sqlite3.Connection, ids) -> dict[int, dict]:
    """THE ONE READER: forecast id -> its prompt record, for the ids given.

    A sent record is found through the cite in the forecast's frozen factors,
    a reconstructed one through its own forecast id; either way the KIND IS
    THE RECORD'S, never inferred from which way it was found. A forecast
    with no record is absent from the answer.

    THE CITE IS THE RECORD'S NUMBER (the prover of item 4, 2026-09-25): a
    cite spelled as text matched its record here by the id column's
    affinity, so the page showed a sent prompt under a forecast the gate's
    audit names as carrying none. Read the way the audit and the schema read
    it, a number or nothing.
    """
    ids = sorted({int(i) for i in ids if i is not None})
    if not ids or not _table_exists(conn):
        return {}
    out: dict[int, dict] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        marks = ",".join("?" * len(chunk))
        for row in conn.execute(
                f"SELECT p.id AS forecast_id, r.* FROM predictions p"
                f"  JOIN reasoning_prompts r"
                f"    ON r.id = (CASE WHEN NOT json_valid(p.factors_json) THEN NULL"
                f"                    WHEN json_type(p.factors_json, '$.{CITE}')"
                f"                         = 'integer'"
                f"                    THEN json_extract(p.factors_json, '$.{CITE}')"
                f"               END)"
                f"   AND r.kind = '{KIND_SENT}'"
                f" WHERE p.id IN ({marks}) AND p.predictor = 'llm'", chunk):
            out[row["forecast_id"]] = dict(row)
        for row in conn.execute(
                f"SELECT r.prediction_id AS forecast_id, r.* FROM reasoning_prompts r"
                f" WHERE r.kind = '{KIND_RECONSTRUCTED}'"
                f"   AND r.prediction_id IN ({marks})", chunk):
            out.setdefault(row["forecast_id"], dict(row))
    return out


def record_for(conn: sqlite3.Connection, prediction_id: int) -> dict | None:
    """One forecast's prompt record, or None."""
    return records_for(conn, [prediction_id]).get(int(prediction_id))
