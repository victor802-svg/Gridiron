"""The operator's own calls: a third forecaster, kept apart from the other two.

WHAT A CALL IS. A side and a confidence tier on a question the model has
already answered. Optional per question -- silence is not a call, and the
absence of one is never scored as anything.

WHY IT IS A SEPARATE CATEGORY AND NOT A ROW IN `predictions`. The operator
sees the model's probability and the market's line before calling. That makes
these INFORMED forecasts, and pooling them with the blind record would destroy
the one property that makes the blind record worth keeping: that nothing in it
saw a line first (LAW 1). It is the same argument LAW 6 makes about mixing
sports and the same separation `statistical` and `llm` already get -- side by
side, never added together.

WHAT A CALL IS NOT. A stake. There is no unit, no amount, no bankroll, and
LAW 5 is not a preference here: `audit.check_not_a_betting_tool` scans this
package's identifiers, and a planting adds an `amount` field to a call to
prove the scan fires by name.
"""

from __future__ import annotations

import sqlite3

from . import config, subjects
from .db import utcnow

#: TIER -> WHAT IT CLAIMS, declared 2026-09-02.
#:
#: The midpoint of each tier's bucket, so a call is graded on exactly the
#: buckets the model is. LEAN spans 50-60 and claims 55; SOLID spans 60-70 and
#: claims 65; STRONG spans 70-80 and claims 75. STRONG also covers 80+ for the
#: model, and a call cannot express that -- an operator who is more sure than
#: STRONG has no way to say so, which is a deliberate limit rather than an
#: oversight: three tiers a person can hold in their head beats five they have
#: to think about.
#:
#: The value is STORED ON THE ROW at call time. Changing this map later must
#: not rewrite what the operator was recorded as claiming, for the same reason
#: a prediction stores its factor set version.
TIER_CLAIM = {
    "LEAN": 0.55,
    "SOLID": 0.65,
    "STRONG": 0.75,
}

TIERS = tuple(TIER_CLAIM)


class CallRefused(RuntimeError):
    """A call that may not be recorded, and why, in words."""


def claim_for(tier: str) -> float:
    """What a tier claims. Raises rather than guessing at an unknown one."""
    try:
        return TIER_CLAIM[tier]
    except KeyError:
        raise CallRefused(
            f"{tier!r} is not a tier. The tiers are {', '.join(TIERS)} -- a "
            f"call has to say how sure it is in the same words the record "
            f"grades."
        ) from None


def _question(conn: sqlite3.Connection, prediction_id: int):
    row = conn.execute(
        "SELECT p.id, p.sport, p.game_id, p.market_type, p.model_side,"
        " p.subject, p.line_asked, p.resolved_utc, g.kickoff_utc, g.status"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.id = ?", (prediction_id,)).fetchone()
    if row is None:
        raise CallRefused(f"there is no prediction {prediction_id}")
    return row


def has_started(row, now: str | None = None) -> bool:
    """Has this game begun? The same bound the MISSED rule uses.

    A game with no kickoff time recorded counts as NOT started: refusing a
    call because a time is missing would punish the operator for a gap in the
    schedule feed.
    """
    now = now or utcnow()
    if row["status"] in ("in", "final"):
        return True
    kickoff = row["kickoff_utc"]
    return bool(kickoff) and kickoff <= now


def record(conn: sqlite3.Connection, prediction_id: int, side: str, tier: str,
           now: str | None = None) -> dict:
    """Write a call. Refuses after kickoff; a revision is a new row.

    BEFORE START ONLY, and structurally rather than by asking nicely: a call
    made after the first pitch is not a forecast, it is a report. The bound is
    the same kickoff the MISSED-slate rule uses, so the two cannot drift apart
    and disagree about when a game began.
    """
    now = now or utcnow()
    row = _question(conn, prediction_id)
    if has_started(row, now):
        raise CallRefused(
            f"{row['game_id']} has already started, so this is no longer a "
            f"forecast. Calls close at kickoff."
        )
    if side not in sides_for(row["market_type"], row["model_side"]):
        # A side the question cannot take is almost certainly a client bug,
        # and storing it would put a claim about nothing into a curve.
        raise CallRefused(
            f"{side!r} is not a side of this question ({row['market_type']}). "
            f"The sides are "
            f"{' and '.join(sides_for(row['market_type'], row['model_side']))}."
        )

    claim = claim_for(tier)
    conn.execute(
        "INSERT INTO operator_calls (created_utc, prediction_id, side, tier,"
        " claimed_prob) VALUES (?,?,?,?,?)",
        (now, prediction_id, side, tier, claim),
    )
    conn.commit()
    return latest(conn, prediction_id)


#: The NO side of each market, in the spelling a new call is stored under.
#:
#: The record holds two spellings for a failed spread -- `not_cover` from the
#: NFL and NBA, `fail to cover` from college football -- because a prediction
#: is append-only and the older rows keep the words they were written with.
#: Both are ACCEPTED here and one is WRITTEN, so the divergence stops growing
#: without rewriting anything. `language.SIDE_WORDS` already knows both.
NO_SIDE = {
    "spread": "not_cover",
    "moneyline": "lose",
    "prop": "under",
    "total": "under",
}


def sides_for(market_type: str, model_side: str) -> tuple[str, ...]:
    """Every side this question can be called on, as the record spells them.

    Includes the model's own side verbatim: whatever spelling that prediction
    was written with is by definition a side of its question, and refusing it
    would make a call impossible on exactly the older rows.
    """
    yes = subjects.YES_SIDE.get(market_type)
    no = NO_SIDE.get(market_type)
    return tuple(dict.fromkeys(s for s in (yes, no, model_side) if s))


def latest(conn: sqlite3.Connection, prediction_id: int) -> dict | None:
    """THE CALL THAT COUNTS: the most recent one made before kickoff.

    A revision supersedes rather than replaces -- the earlier row stays and the
    chain is shown in History. What is GRADED is the last thing the operator
    said while it was still a forecast.
    """
    row = conn.execute(
        "SELECT * FROM operator_calls WHERE prediction_id = ?"
        " ORDER BY created_utc DESC, id DESC LIMIT 1", (prediction_id,)
    ).fetchone()
    return dict(row) if row else None


def chain(conn: sqlite3.Connection, prediction_id: int) -> list[dict]:
    """Every call on this question, oldest first: the revision history."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM operator_calls WHERE prediction_id = ?"
        " ORDER BY created_utc, id", (prediction_id,))]


def resolve_for(conn: sqlite3.Connection, prediction_id: int,
                model_outcome: int, model_side: str,
                now: str | None = None) -> int:
    """Settle the open calls on one prediction. Returns how many.

    Called from the resolver's own pass, so a call settles at the same instant
    its prediction does and by the same code path. Only the LATEST call before
    kickoff is graded; earlier ones in the chain are superseded and stay
    unresolved -- they are history, not claims.

    THE CALL'S OUTCOME IS NOT THE MODEL'S. `predictions.outcome` says whether
    the MODEL's side was right. An operator who called the other side is right
    exactly when the model was wrong, so the outcome has to be derived from
    which side the call took -- inheriting the model's would score the
    operator on the model's opinion, and would do it silently, and would look
    perfectly reasonable in every row where they happened to agree.
    """
    now = now or utcnow()
    current = latest(conn, prediction_id)
    if not current or current["resolved_utc"] is not None:
        return 0
    agreed = current["side"] == model_side
    outcome = int(model_outcome) if agreed else 1 - int(model_outcome)
    conn.execute(
        "UPDATE operator_calls SET resolved_utc = ?, outcome = ?"
        " WHERE id = ? AND resolved_utc IS NULL",
        (now, int(outcome), current["id"]),
    )
    return 1


def void_for(conn: sqlite3.Connection, prediction_id: int) -> int:
    """A voided prediction voids its calls, for the same reason.

    The question was never answered, so nothing the operator said about it can
    be right or wrong. Left unresolved rather than marked lost -- the same
    treatment the prediction gets.
    """
    return conn.execute(
        "SELECT COUNT(*) FROM operator_calls WHERE prediction_id = ?"
        " AND resolved_utc IS NULL", (prediction_id,)).fetchone()[0]


def record_summary(conn: sqlite3.Connection, sport: str) -> dict:
    """The operator's settled record in one sport. NEVER across sports.

    `require_sport` is the same tripwire every other reader of the record
    passes through: a figure spanning two sports describes neither.
    """
    # `config.require_sport`, NOT `calibration`'s. The tripwire lives in both
    # names for history, but `calibration` names market columns in its own
    # code, so importing it from here would drag those into any prediction
    # closure that can reach a call -- and the resolver can. The scan caught
    # this on the first run; `require_sport` was moved to `config` during the
    # college football work for exactly this reason.
    config.require_sport(sport, "calls.record_summary")
    row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(c.outcome), 0) AS right_"
        " FROM operator_calls c JOIN predictions p ON p.id = c.prediction_id"
        " WHERE p.sport = ? AND c.resolved_utc IS NOT NULL",
        (sport,)).fetchone()
    settled = row["n"] or 0
    return {
        "sport": sport,
        "settled": settled,
        "right": row["right_"] or 0,
        "wrong": settled - (row["right_"] or 0),
        # LABELLED INFORMED WHEREVER IT APPEARS (ruling R2). The operator saw
        # the model and the market before calling, and a number that does not
        # say so invites comparison with a blind one.
        "forecaster": FORECASTER,
        "label": FORECASTER_LABEL,
    }


#: What the operator's forecaster is called, in the record and in the
#: interface. "informed" is not decoration: it is the whole difference between
#: this category and the other two.
FORECASTER = "operator"
FORECASTER_LABEL = "you (informed)"

# THE REPORTING TABLES LIVE IN `views`, NOT HERE, and the scan is why.
#
# `calls` is imported by the resolver, which puts it inside a prediction
# closure. A tier table needs `calibration` (for the gate and the verdict
# wording) and a model-versus-operator comparison needs `market_snapshots` --
# and either import drags market column names into that closure, which LAW 1
# refuses. The scan caught both within seconds, as it has now caught three
# other attempts to reach out of this module for one convenient thing.
#
# So this module writes, reads and resolves calls; `views.operator_tier_table`
# and `views.call_comparison` report on them.
