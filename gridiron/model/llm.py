"""The LLM reasoning pass, and the ledger that keeps it honest and cheap.

The model is handed the factor values and nothing else. It writes a narrative
and states its own probability, which is recorded as a *separate prediction*
from the statistical one so the two can be scored against each other.

It never sees a market line, for the same reason nothing else here does, and it
is structurally incapable of doing so: this module sits inside the prediction
import closure, which cannot reach `gridiron.market`.

Three rules on spend:
  * A daily USD cap, read from the environment.
  * Every call is priced and written to `llm_calls` before its result is used.
  * Model routing: the reasoning call goes to the stronger model, and the
    cheap model is used only to repair malformed JSON, which is a formatting
    job and does not need to think about football.

When the key is missing, the SDK is absent, the budget is gone or the API
errors, this raises `LLMUnavailable` with a reason. The caller records a
statistical-only prediction carrying that reason as a `degraded` tag. Nothing
invents a probability. A fabricated forecast in a calibration record is worse
than no forecast, because it is indistinguishable from a real one later.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .. import config
from ..db import utcnow

SYSTEM_PROMPT = """You are a football forecaster. You are given a fixed set of \
measured factors about one upcoming question and nothing else.

Hard constraints:
- You have NOT been shown any betting line, market price, implied probability or \
public betting percentage, and none is available to you. Do not guess at one, \
do not reason about what "the market" thinks, and do not anchor on a number you \
imagine a sportsbook would post. Reason only from the factors given.
- Factors listed as NOT MEASURABLE have no value for this game at all. \
Treat them as unknown: do not assume a value, do not treat them as zero, and \
say so in your reasoning if one of them would have mattered.
- You are estimating a probability, not giving advice. Do not mention betting, \
staking, value, or whether something is worth backing.

Answer with a single JSON object and nothing else:
{"probability": <float between 0.02 and 0.98>, "reasoning": "<2-4 sentences>"}

`probability` is your probability that the stated claim is TRUE. The reasoning \
should name the two or three factors that actually moved your estimate and say \
which way, and should say plainly when the factors are thin."""


class LLMUnavailable(RuntimeError):
    """The reasoning pass could not run. `.reason` is the tag for the record."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}{': ' + detail if detail else ''}")
        self.reason = reason
        self.detail = detail


@dataclass
class LLMResult:
    probability: float
    reasoning: str
    model: str
    usd: float
    input_tokens: int
    output_tokens: int
    repaired: bool = False


# ---------------------------------------------------------------------------
# the ledger
# ---------------------------------------------------------------------------

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def price(model: str, input_tokens: int, output_tokens: int) -> float:
    per_in, per_out = config.LLM_PRICES.get(model, config.LLM_PRICE_FALLBACK)
    return (input_tokens * per_in + output_tokens * per_out) / 1_000_000.0


def spent_today(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(usd), 0.0) AS total FROM llm_calls WHERE day_utc = ?",
        (_today(),),
    ).fetchone()
    return float(row["total"])


def budget_remaining(conn: sqlite3.Connection) -> float:
    return max(0.0, config.LLM_DAILY_USD_CAP - spent_today(conn))


def record_call(
    conn: sqlite3.Connection,
    *,
    purpose: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    usd: float,
    game_id: str | None,
    ok: bool = True,
    error: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO llm_calls (called_utc, day_utc, purpose, model, input_tokens,"
        " output_tokens, usd, game_id, ok, error) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            utcnow(),
            _today(),
            purpose,
            model,
            input_tokens,
            output_tokens,
            usd,
            game_id,
            1 if ok else 0,
            error,
        ),
    )
    conn.commit()


def ledger_summary(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(usd),0) AS usd,"
        " COALESCE(SUM(input_tokens),0) AS tin, COALESCE(SUM(output_tokens),0) AS tout,"
        " SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) AS failures"
        " FROM llm_calls WHERE day_utc = ?",
        (_today(),),
    ).fetchone()
    return {
        "day": _today(),
        "calls": row["calls"],
        "usd_spent": round(float(row["usd"]), 4),
        "usd_cap": config.LLM_DAILY_USD_CAP,
        "usd_remaining": round(budget_remaining(conn), 4),
        "input_tokens": row["tin"],
        "output_tokens": row["tout"],
        "failures": row["failures"] or 0,
    }


# ---------------------------------------------------------------------------
# the call
# ---------------------------------------------------------------------------

#: HTTP status codes that mean "your credentials are wrong", not "the network
#: is having a bad day". 401 is an invalid or revoked key; 403 is a key that
#: authenticated but may not do this.
AUTH_STATUSES = (401, 403)


def failure_reason(exc: Exception) -> str:
    """Which KIND of unavailable this is, in one word the interface can say.

    EVERY SDK FAILURE USED TO BE `api_error`, and for three days that meant the
    Schedule page said "the second forecaster could not be reached" while the
    log said `AuthenticationError: 401 - API key is invalid`. It had been
    reached; it had refused. Those are not the same problem and they do not
    have the same fix -- one is worth retrying and the other is a key somebody
    has to set -- so the interface should not describe them with one sentence.
    (`DEGRADED_WORDS` already made this argument in its own comment: "a missing
    key is a setup step ... an API error is the only one that might be worth
    retrying". An invalid key was a setup step wearing the retry label.)
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status in AUTH_STATUSES:
        return "bad_api_key"
    if type(exc).__name__ == "AuthenticationError":
        return "bad_api_key"
    return "api_error"


def _client():
    if not config.ANTHROPIC_API_KEY:
        raise LLMUnavailable("no_api_key", "ANTHROPIC_API_KEY is not set")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - the dep is in requirements
        raise LLMUnavailable("sdk_missing", str(exc)) from exc
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def build_prompt(question: str, factor_rows: list[dict], notes: list[str]) -> str:
    lines = [f"CLAIM: {question}", "", "MEASURED FACTORS:"]
    unmeasured = []
    for row in factor_rows:
        if not row.get("present", True):
            unmeasured.append(row["factor"])
            continue
        source = f" [source: {row['source']}]" if row.get("source") else ""
        lines.append(f"- {row['factor']} = {row['value']:g}{source}")
        lines.append(f"    what it measures: {row['rationale']}")
    if unmeasured:
        lines.append("")
        lines.append(
            "NOT MEASURABLE for this game. No value exists. Do not assume one, "
            "and do not treat these as zero:"
        )
        lines.extend(f"- {name}" for name in unmeasured)
    if notes:
        lines.append("")
        lines.append("CAVEATS ON THIS DATA:")
        lines.extend(f"- {n}" for n in notes)
    lines.append("")
    lines.append("Give your probability that the CLAIM is true.")
    return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def reason(
    conn: sqlite3.Connection,
    *,
    question: str,
    factor_rows: list[dict],
    notes: list[str],
    game_id: str | None = None,
    client=None,
) -> LLMResult:
    """Run the reasoning pass. Raises `LLMUnavailable` rather than degrading
    silently; the caller decides what to record."""
    client = client or _client()

    # Refuse before spending, not after. A rough ceiling on this call is the
    # reasoning model's output cap plus a generous prompt allowance.
    projected = price(config.LLM_REASONING_MODEL, 2000, config.LLM_MAX_OUTPUT_TOKENS)
    if budget_remaining(conn) < projected:
        raise LLMUnavailable(
            "daily_budget",
            f"${spent_today(conn):.4f} of ${config.LLM_DAILY_USD_CAP:.2f} spent today; "
            f"this call needs about ${projected:.4f}",
        )

    prompt = build_prompt(question, factor_rows, notes)
    model = config.LLM_REASONING_MODEL
    try:
        response = client.messages.create(
            model=model,
            max_tokens=config.LLM_MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 - any SDK failure degrades
        record_call(
            conn,
            purpose="reasoning",
            model=model,
            input_tokens=0,
            output_tokens=0,
            usd=0.0,
            game_id=game_id,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise LLMUnavailable(failure_reason(exc), f"{type(exc).__name__}: {exc}") from exc

    text = "".join(getattr(block, "text", "") for block in response.content)
    tin = int(getattr(response.usage, "input_tokens", 0))
    tout = int(getattr(response.usage, "output_tokens", 0))
    usd = price(model, tin, tout)
    record_call(
        conn,
        purpose="reasoning",
        model=model,
        input_tokens=tin,
        output_tokens=tout,
        usd=usd,
        game_id=game_id,
    )

    parsed = _extract_json(text)
    repaired = False
    if parsed is None:
        # Routing: reshaping text into JSON is a formatting job, so it goes to
        # the cheap model rather than paying reasoning rates twice.
        parsed, repair_usd = _repair(conn, text, game_id, client)
        usd += repair_usd
        repaired = True
    if parsed is None:
        raise LLMUnavailable("unparseable", f"model returned no usable JSON: {text[:200]!r}")

    try:
        probability = float(parsed["probability"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMUnavailable("unparseable", f"no probability in {parsed!r}") from exc
    if not 0.0 < probability < 1.0:
        raise LLMUnavailable("out_of_range", f"probability {probability!r} is not a probability")

    reasoning = str(parsed.get("reasoning") or "").strip()
    if not reasoning:
        raise LLMUnavailable("no_reasoning", "the model gave a probability with no reasoning")

    return LLMResult(
        probability=min(max(probability, 0.02), 0.98),
        reasoning=reasoning,
        model=model,
        usd=usd,
        input_tokens=tin,
        output_tokens=tout,
        repaired=repaired,
    )


def _repair(
    conn: sqlite3.Connection, text: str, game_id: str | None, client
) -> tuple[dict | None, float]:
    model = config.LLM_CHEAP_MODEL
    try:
        response = client.messages.create(
            model=model,
            max_tokens=400,
            system=(
                'Return only a JSON object of the form {"probability": <float>, '
                '"reasoning": "<text>"} carrying the content of the message. '
                "Invent nothing; if there is no probability in it, return "
                '{"probability": null, "reasoning": ""}.'
            ),
            messages=[{"role": "user", "content": text}],
        )
    except Exception as exc:  # noqa: BLE001
        record_call(
            conn,
            purpose="format",
            model=model,
            input_tokens=0,
            output_tokens=0,
            usd=0.0,
            game_id=game_id,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        return None, 0.0

    tin = int(getattr(response.usage, "input_tokens", 0))
    tout = int(getattr(response.usage, "output_tokens", 0))
    usd = price(model, tin, tout)
    record_call(
        conn,
        purpose="format",
        model=model,
        input_tokens=tin,
        output_tokens=tout,
        usd=usd,
        game_id=game_id,
    )
    return _extract_json("".join(getattr(b, "text", "") for b in response.content)), usd
