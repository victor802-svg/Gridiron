"""View models for the interface. Assembly only — no computation of new claims.

Everything here reads the record and shapes it for display. It never writes and
never derives a probability, so the numbers a person sees on the page are the
numbers that were written when the prediction was made.
"""

from __future__ import annotations

import json
import sqlite3

from . import calibration, config, db
from .data import repo
from .factors import compute as factor_compute, registry
from .market import lines


def meta(conn: sqlite3.Connection) -> dict:
    from .model import llm

    kind = db.database_kind(conn)
    counts = repo.counts(conn)
    row = conn.execute(
        "SELECT MIN(created_utc) AS first, MAX(created_utc) AS last FROM predictions"
    ).fetchone()
    return {
        "database_kind": kind["kind"],
        "database_note": kind["note"],
        "factor_set_version": config.FACTOR_SET_VERSION,
        "minimum_for_edge_claim": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
        "minimum_for_bucket_point": config.MIN_SAMPLE_FOR_BUCKET_POINT,
        "seasons_loaded": counts["seasons"],
        "games": counts["games"],
        "games_final": counts["games_final"],
        "predictions": counts["predictions"],
        "first_prediction_utc": row["first"],
        "last_prediction_utc": row["last"],
        "market_coverage": lines.coverage(conn),
        "llm_ledger": llm.ledger_summary(conn),
        "not_a_betting_tool": (
            "Gridiron states probabilities and keeps score of them. It does not "
            "size stakes, manage a bankroll, or recommend a bet, and it connects "
            "to no sportsbook or exchange."
        ),
    }


def _voids_for(conn: sqlite3.Connection, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    return {
        r["prediction_id"]: r["reason"]
        for r in conn.execute(
            f"SELECT prediction_id, reason FROM prediction_voids"
            f" WHERE prediction_id IN ({placeholders})",
            ids,
        )
    }


def _rationale(name: str) -> str:
    factor = registry.REGISTRY.get(name)
    return factor.rationale if factor else ""


def _top_factors(payload: dict, limit: int = 5) -> list[dict]:
    sources = payload.get("sources") or {}
    contributions = payload.get("contributions") or []
    if contributions:
        return [
            {
                "factor": c["factor"],
                "value": c["value"],
                "contribution": c["contribution"],
                "present": c.get("present", True),
                "source": sources.get(c["factor"]),
                "rationale": _rationale(c["factor"]),
            }
            for c in contributions[:limit]
        ]
    # An LLM prediction has no decomposition; show the values it was given.
    values = payload.get("values") or {}
    return [
        {
            "factor": name,
            "value": value,
            "contribution": None,
            "present": True,
            "source": sources.get(name),
            "rationale": _rationale(name),
        }
        for name, value in list(values.items())[:limit]
    ]


def _absent_factors(payload: dict) -> list[dict]:
    """What the model could not see, named on the card rather than omitted."""
    detail = payload.get("absent_detail") or {}
    return [
        {
            "factor": name,
            "why": detail.get(name, "not measurable for this game"),
            "rationale": _rationale(name),
        }
        for name in factor_compute.absent_factors(payload)
    ]


def week(conn: sqlite3.Connection, season: int | None = None, wk: int | None = None) -> dict:
    """THIS WEEK: one card per forecast, sorted by disagreement with the market."""
    explicit = wk is not None
    season = season or config.CURRENT_SEASON
    if wk is None:
        wk = repo.next_unplayed_week(conn, season)

    def fetch(s: int, w: int | None):
        if w is None:
            return []
        return conn.execute(
            "SELECT p.*, g.home, g.away, g.kickoff_utc, g.status, g.home_score,"
            " g.away_score FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE g.season = ? AND g.week = ? ORDER BY p.id",
            (s, w),
        ).fetchall()

    rows = fetch(season, wk)
    if not rows and not explicit:
        # The upcoming week may not be forecast yet (or this may be a backtest
        # database with no upcoming week at all). Fall back to the most recent
        # week that actually has forecasts rather than showing an empty page.
        latest = conn.execute(
            "SELECT g.season, g.week FROM predictions p JOIN games g ON g.id = p.game_id"
            " ORDER BY g.season DESC, g.week DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            return {"season": season, "week": None, "n": 0, "cards": [],
                    "message": "No predictions have been made yet.",
                    "sorted_by": "size of disagreement with the market"}
        season, wk = latest["season"], latest["week"]
        rows = fetch(season, wk)
    ids = [r["id"] for r in rows]
    snapshots = lines.snapshots_for(conn, ids)
    voided = _voids_for(conn, ids)
    # One bucket record per (market, predictor, bucket) rather than one per
    # card: the same lookup would otherwise run once for every pick on the slate.
    bucket_cache: dict[tuple, dict] = {}

    cards = []
    for r in rows:
        payload = json.loads(r["factors_json"] or "{}")
        snap = snapshots.get(r["id"]) or {}
        implied = snap.get("implied_prob")
        gap = None if implied is None else round(r["model_prob"] - implied, 4)

        key = (
            r["market_type"], r["prop_type"], r["predictor"],
            calibration.bucket_label(r["model_prob"]),
        )
        if key not in bucket_cache:
            bucket_cache[key] = calibration.bucket_record(
                conn, r["model_prob"], market_type=r["market_type"],
                prop_type=r["prop_type"], predictor=r["predictor"],
            )
        cards.append(
            {
                "prediction_id": r["id"],
                "created_utc": r["created_utc"],
                "game_id": r["game_id"],
                "matchup": f"{r['away']} @ {r['home']}",
                "kickoff_utc": r["kickoff_utc"],
                "game_status": r["status"],
                "final_score": (
                    f"{r['away']} {r['away_score']} - {r['home_score']} {r['home']}"
                    if r["status"] == "final" else None
                ),
                "market_type": r["market_type"],
                "prop_type": r["prop_type"],
                "market": r["prop_type"] or r["market_type"],
                "predictor": r["predictor"],
                "subject": r["subject"],
                "claim": (payload.get("question") or {}).get("claim"),
                "line_asked": r["line_asked"],
                "model_prob": r["model_prob"],
                "model_side": r["model_side"],
                "market_line": snap.get("line"),
                "market_implied_prob": implied,
                "market_source": snap.get("source"),
                "public_pct": snap.get("public_pct"),
                "gap": gap,
                "abs_gap": abs(gap) if gap is not None else -1.0,
                "top_factors": _top_factors(payload),
                "absent_factors": _absent_factors(payload),
                "factor_coverage": payload.get("coverage"),
                "notes": payload.get("notes") or [],
                "reasoning": r["reasoning"],
                "degraded": r["degraded"],
                "outcome": r["outcome"],
                "resolved_utc": r["resolved_utc"],
                "voided": r["id"] in voided,
                "void_reason": voided.get(r["id"]),
                "bucket": bucket_cache[key],
                "market_fetched_utc": snap.get("fetched_utc"),
                "factor_set_version": r["factor_set_version"],
            }
        )

    # Sorted by disagreement size, because that is where anything interesting
    # lives. Cards with no market comparison sort last rather than first.
    cards.sort(key=lambda c: c["abs_gap"], reverse=True)
    return {
        "season": season,
        "week": wk,
        "n": len(cards),
        "cards": cards,
        "sorted_by": "size of disagreement with the market; no comparison sorts last",
    }


def available_weeks(conn: sqlite3.Connection) -> list[dict]:
    return [
        {"season": r["season"], "week": r["week"], "n": r["n"]}
        for r in conn.execute(
            "SELECT g.season, g.week, COUNT(*) AS n FROM predictions p"
            " JOIN games g ON g.id = p.game_id GROUP BY g.season, g.week"
            " ORDER BY g.season DESC, g.week DESC"
        )
    ]


def history(
    conn: sqlite3.Connection,
    *,
    query: str = "",
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Every past prediction, searchable. There is no write path to this table
    from the interface at all — the API exposes no verb but GET."""
    where = ["1=1"]
    params: list = []
    if query:
        where.append("(p.subject LIKE ? OR p.game_id LIKE ? OR p.reasoning LIKE ?)")
        like = f"%{query}%"
        params += [like, like, like]
    if market_type:
        where.append("p.market_type = ?")
        params.append(market_type)
    if prop_type:
        where.append("p.prop_type = ?")
        params.append(prop_type)
    if predictor:
        where.append("p.predictor = ?")
        params.append(predictor)
    if outcome == "resolved":
        where.append("p.resolved_utc IS NOT NULL")
    elif outcome == "open":
        where.append("p.resolved_utc IS NULL")
    elif outcome == "correct":
        where.append("p.outcome = 1")
    elif outcome == "wrong":
        where.append("p.outcome = 0")
    elif outcome == "void":
        where.append(
            "EXISTS (SELECT 1 FROM prediction_voids v WHERE v.prediction_id = p.id)"
        )

    clause = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM predictions p WHERE {clause}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT p.*, g.season, g.week, g.home, g.away, g.status"
        f" FROM predictions p JOIN games g ON g.id = p.game_id WHERE {clause}"
        f" ORDER BY p.id DESC LIMIT ? OFFSET ?",
        params + [min(limit, 500), offset],
    ).fetchall()
    ids = [r["id"] for r in rows]
    snapshots = lines.snapshots_for(conn, ids)
    voided = _voids_for(conn, ids)

    items = []
    for r in rows:
        snap = snapshots.get(r["id"]) or {}
        items.append(
            {
                "prediction_id": r["id"],
                "created_utc": r["created_utc"],
                "season": r["season"],
                "week": r["week"],
                "game_id": r["game_id"],
                "matchup": f"{r['away']} @ {r['home']}",
                "market_type": r["market_type"],
                "prop_type": r["prop_type"],
                "market": r["prop_type"] or r["market_type"],
                "predictor": r["predictor"],
                "subject": r["subject"],
                "line_asked": r["line_asked"],
                "model_prob": r["model_prob"],
                "model_side": r["model_side"],
                "market_line_at_the_time": snap.get("line"),
                "market_implied_prob": snap.get("implied_prob"),
                "outcome": r["outcome"],
                "resolved_utc": r["resolved_utc"],
                "voided": r["id"] in voided,
                "void_reason": voided.get(r["id"]),
                "degraded": r["degraded"],
                "factor_set_version": r["factor_set_version"],
            }
        )
    return {"n": total, "returned": len(items), "offset": offset, "items": items}


def prediction_detail(conn: sqlite3.Connection, prediction_id: int) -> dict | None:
    r = conn.execute(
        "SELECT p.*, g.season, g.week, g.home, g.away, g.status, g.home_score,"
        " g.away_score, g.kickoff_utc FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.id = ?",
        (prediction_id,),
    ).fetchone()
    if r is None:
        return None
    snap = lines.snapshots_for(conn, [prediction_id]).get(prediction_id) or {}
    payload = json.loads(r["factors_json"] or "{}")
    return {
        "prediction_id": r["id"],
        "created_utc": r["created_utc"],
        "game_id": r["game_id"],
        "matchup": f"{r['away']} @ {r['home']}",
        "season": r["season"],
        "week": r["week"],
        "market_type": r["market_type"],
        "predictor": r["predictor"],
        "subject": r["subject"],
        "claim": (payload.get("question") or {}).get("claim"),
        "line_asked": r["line_asked"],
        "model_prob": r["model_prob"],
        "model_side": r["model_side"],
        "reasoning": r["reasoning"],
        "degraded": r["degraded"],
        "outcome": r["outcome"],
        "resolved_utc": r["resolved_utc"],
        "factor_set_version": r["factor_set_version"],
        "factors": payload,
        "market": snap,
    }


def scorecard(conn: sqlite3.Connection) -> dict:
    payload = calibration.scorecard(conn)
    payload["meta"] = meta(conn)
    calibration.assert_every_figure_has_n(payload)
    return payload


def factors(conn: sqlite3.Connection) -> dict:
    from .factors import store

    report = calibration.factor_report(conn)
    stored = {f["name"]: f for f in store.stored_factors(conn)}
    for entry in report["factors"]:
        row = stored.get(entry["factor"])
        if row:
            entry["recorded_added_utc"] = row["added_utc"]
            entry["deactivated_utc"] = row["deactivated_utc"]
    calibration.assert_every_figure_has_n(report)
    return report
