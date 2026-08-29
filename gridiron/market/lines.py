"""Step 5: the market, and only after the prediction row exists.

This module is the quarantine. It is the only code permitted to read
`market_lines_raw`, and nothing on the prediction path may import it — the guard
test walks the import closure, and `gridiron.blind` refuses to let this package
load at all while a prediction is being formed.

What arrives here is a prediction id. What is written is a `market_snapshots`
row hanging off it. The database refuses the insert if the prediction does not
exist or if the snapshot claims to predate it.
"""

from __future__ import annotations

import math
import sqlite3

from ..db import utcnow

#: Standard deviation of an NFL final margin around the closing spread, in
#: points. The value is stable across seasons at roughly 13; it is used only to
#: turn a spread into a comparable probability so the model and the market can be
#: read on the same axis. It is a stated modelling assumption, not a measurement,
#: and it is written down here rather than buried in an expression.
MARGIN_SD = 13.2

SOURCE = "nflverse/schedules"
NO_PROP_MARKET = "unavailable:no-free-prop-line-source"


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def implied_cover_probability(market_spread: float, line_asked: float) -> float:
    """P(home covers `line_asked`), as implied by the market's spread.

    nflverse states `spread_line` as the expected home margin, so a home side
    favoured by three is +3. Our question asks whether the home margin plus
    `line_asked` exceeds zero, which under a normal margin is
    Phi((expected_margin + line_asked) / sd).
    """
    return norm_cdf((market_spread + line_asked) / MARGIN_SD)


def raw_line(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM market_lines_raw WHERE game_id = ?", (game_id,)
    ).fetchone()


def public_percentage(conn: sqlite3.Connection, game_id: str) -> float | None:
    """Always None, deliberately.

    No free source publishes ticket-count betting percentages with an API and a
    licence we can rely on (checked 2026-08-28). The column stays, the factor
    stays declared and inactive, and this returns nothing rather than a proxy
    that would be labelled "public" while measuring something else.
    """
    return None


def snapshot_prediction(conn: sqlite3.Connection, prediction_id: int) -> dict | None:
    """Attach the market to one already-written prediction.

    Idempotent: a prediction keeps its first snapshot. Re-running the week does
    not append a second look at a line that has since moved, because the record
    is of what the market said when the prediction was made.
    """
    pred = conn.execute(
        "SELECT id, game_id, market_type, line_asked, model_side FROM predictions"
        " WHERE id = ?",
        (prediction_id,),
    ).fetchone()
    if pred is None:
        raise KeyError(f"no prediction {prediction_id}")

    existing = conn.execute(
        "SELECT * FROM market_snapshots WHERE prediction_id = ? ORDER BY id LIMIT 1",
        (prediction_id,),
    ).fetchone()
    if existing is not None:
        return dict(existing)

    if pred["market_type"] != "spread":
        cur = conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line,"
            " implied_prob, public_pct) VALUES (?,?,?,NULL,NULL,NULL)",
            (prediction_id, utcnow(), NO_PROP_MARKET),
        )
        conn.commit()
        return {"id": cur.lastrowid, "source": NO_PROP_MARKET, "line": None,
                "implied_prob": None, "public_pct": None}

    row = raw_line(conn, pred["game_id"])
    if row is None or row["spread_line"] is None:
        return None

    implied_yes = implied_cover_probability(row["spread_line"], pred["line_asked"])
    # State the market's probability for the same side the model claimed, so the
    # two numbers on the card are answers to the same question.
    implied = implied_yes if pred["model_side"] == "cover" else 1.0 - implied_yes

    cur = conn.execute(
        "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line,"
        " implied_prob, public_pct) VALUES (?,?,?,?,?,?)",
        (
            prediction_id,
            utcnow(),
            SOURCE,
            row["spread_line"],
            round(implied, 6),
            public_percentage(conn, pred["game_id"]),
        ),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "source": SOURCE,
        "line": row["spread_line"],
        "implied_prob": round(implied, 6),
        "public_pct": None,
    }


def snapshot_many(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict[str, int]:
    counts = {"snapshotted": 0, "already": 0, "no_line": 0}
    for pid in prediction_ids:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM market_snapshots WHERE prediction_id = ?", (pid,)
        ).fetchone()["n"]
        result = snapshot_prediction(conn, pid)
        if result is None:
            counts["no_line"] += 1
        elif before:
            counts["already"] += 1
        else:
            counts["snapshotted"] += 1
    return counts


def snapshot_for_game(conn: sqlite3.Connection, game_id: str) -> dict[str, int]:
    ids = [
        r["id"]
        for r in conn.execute("SELECT id FROM predictions WHERE game_id = ?", (game_id,))
    ]
    return snapshot_many(conn, ids)


# ---------------------------------------------------------------------------
# read side, for the interface
# ---------------------------------------------------------------------------
# The rule in CLAUDE.md is that only this module reads the market tables. The
# interface needs those numbers, so the accessor lives here rather than the
# read being done inline somewhere on the other side of the wall.

def snapshots_for(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict[int, dict]:
    """First snapshot per prediction, keyed by prediction id."""
    if not prediction_ids:
        return {}
    placeholders = ",".join("?" for _ in prediction_ids)
    rows = conn.execute(
        f"SELECT prediction_id, MIN(id) AS id, fetched_utc, source, line, implied_prob,"
        f" public_pct FROM market_snapshots WHERE prediction_id IN ({placeholders})"
        f" GROUP BY prediction_id",
        prediction_ids,
    ).fetchall()
    return {r["prediction_id"]: dict(r) for r in rows}


def coverage(conn: sqlite3.Connection) -> dict:
    """How much of the record has a market comparison at all."""
    row = conn.execute(
        "SELECT COUNT(*) AS predictions,"
        " SUM(CASE WHEN s.implied_prob IS NOT NULL THEN 1 ELSE 0 END) AS with_line"
        " FROM predictions p LEFT JOIN market_snapshots s ON s.prediction_id = p.id"
    ).fetchone()
    return {
        "n": row["predictions"] or 0,
        "with_market_line": row["with_line"] or 0,
        "public_pct_available": 0,
        "note": (
            "Props have no free market line source, so they carry a snapshot "
            "recording that absence rather than a number. Public betting "
            "percentage is unavailable from any free source and is never proxied."
        ),
    }
