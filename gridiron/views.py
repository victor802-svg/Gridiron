"""View models for the interface. Assembly only — no computation of new claims.

Everything here reads the record and shapes it for display. It never writes and
never derives a probability, so the numbers a person sees on the page are the
numbers that were written when the prediction was made.
"""

from __future__ import annotations

import json
import sqlite3

from . import calibration, config, db, sports
from .data import repo
from .factors import compute as factor_compute, registry
from .market import lines


def sports_summary(conn: sqlite3.Connection) -> dict:
    """Per-sport counts for the tab labels.

    Every sport is listed even with nothing in it, and each carries its own
    resolved count, so an empty record is visible BEFORE clicking the tab. A
    tab that looks the same whether it holds a season or nothing is a tab that
    hides an empty record (LAW 4 and LAW 6 together).
    """
    rows = {
        r["sport"]: r
        for r in conn.execute(
            "SELECT sport, COUNT(*) AS written,"
            " SUM(CASE WHEN resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved"
            " FROM predictions GROUP BY sport"
        )
    }
    voided = {
        r["sport"]: r["n"]
        for r in conn.execute(
            "SELECT p.sport, COUNT(*) AS n FROM prediction_voids v"
            " JOIN predictions p ON p.id = v.prediction_id GROUP BY p.sport"
        )
    }
    out = []
    for sport in config.SPORTS:
        row = rows.get(sport)
        games = conn.execute(
            "SELECT COUNT(*) AS n,"
            " SUM(CASE WHEN status = 'final' THEN 1 ELSE 0 END) AS final"
            " FROM games WHERE sport = ?",
            (sport,),
        ).fetchone()
        out.append({
            "sport": sport,
            "label": config.SPORT_LABELS.get(sport, sport.upper()),
            "n": (row["resolved"] if row else 0) or 0,
            "written": (row["written"] if row else 0) or 0,
            "voided": voided.get(sport, 0),
            "games_loaded": games["n"] or 0,
            "games_final": games["final"] or 0,
            "markets": list(config.SPORT_MARKETS.get(sport, ())),
            "line_source": lines.line_source_for(sport),
        })
    # No total. Summing resolved counts across sports would be the exact
    # aggregation LAW 6 forbids, and it would be the first number a reader saw.
    return {
        "side_by_side_sports": True,
        "sports": out,
        "never_summed": (
            "LAW 6: these counts are listed side by side and are never added "
            "together. There is deliberately no combined total."
        ),
    }


def meta(conn: sqlite3.Connection, sport: str) -> dict:
    from .model import llm

    calibration.require_sport(sport, "views.meta")
    kind = db.database_kind(conn)
    counts = repo.counts(conn)
    row = conn.execute(
        "SELECT MIN(created_utc) AS first, MAX(created_utc) AS last"
        " FROM predictions WHERE sport = ?",
        (sport,),
    ).fetchone()
    return {
        "sport": sport,
        "sport_label": config.SPORT_LABELS.get(sport, sport.upper()),
        "sports": sports_summary(conn),
        "markets": list(config.SPORT_MARKETS.get(sport, ())),
        "prop_markets": list(config.SPORT_PROP_MARKETS.get(sport, ())),
        "line_source": lines.line_source_for(sport),
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
        "market_coverage": lines.coverage(conn, sport=sport),
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


def week(conn: sqlite3.Connection, sport: str, season: int | None = None,
         wk: int | None = None) -> dict:
    """THE SLATE: one card per forecast, sorted by disagreement with the market.

    "Week" is the slate key. NFL and NBA number weeks; MLB numbers days, since
    a baseball slate is a day's card. Either way it is an integer that orders
    the record, and the interface prints the sport's own word for it.
    """
    calibration.require_sport(sport, "views.week")
    explicit = wk is not None
    season = season or config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    if wk is None:
        wk = repo.next_unplayed_week(conn, season, sport=sport)

    def fetch(s: int, w: int | None):
        if w is None:
            return []
        return conn.execute(
            "SELECT p.*, g.home, g.away, g.kickoff_utc, g.status, g.home_score,"
            " g.away_score FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND g.season = ? AND g.week = ? ORDER BY p.id",
            (sport, s, w),
        ).fetchall()

    rows = fetch(season, wk)
    if not rows and not explicit:
        # The upcoming week may not be forecast yet (or this may be a backtest
        # database with no upcoming week at all). Fall back to the most recent
        # week that actually has forecasts rather than showing an empty page.
        latest = conn.execute(
            "SELECT g.season, g.week FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? ORDER BY g.season DESC, g.week DESC LIMIT 1",
            (sport,),
        ).fetchone()
        if latest is None:
            return {"sport": sport, "season": season, "week": None, "n": 0,
                    "cards": [], "message": _empty_slate_message(conn, sport),
                    "slate_word": config.SPORT_SLATE_WORD.get(sport, "week"),
                    "line_source": lines.line_source_for(sport),
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
                conn, r["model_prob"], sport=sport, market_type=r["market_type"],
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
                "line_availability": lines.market_availability(
                    sport, r["prop_type"] or r["market_type"]),
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
                # Derived from the bucket above, never re-counted. One
                # implementation means the chip on this card and the point on
                # the calibration chart cannot disagree.
                "tier": calibration.tier_from_bucket(bucket_cache[key]),
                "market_fetched_utc": snap.get("fetched_utc"),
                "factor_set_version": r["factor_set_version"],
            }
        )

    # Sorted by disagreement size, because that is where anything interesting
    # lives. Cards with no market comparison sort last rather than first.
    cards.sort(key=lambda c: c["abs_gap"], reverse=True)
    return {
        "sport": sport,
        "season": season,
        "week": wk,
        "slate_word": config.SPORT_SLATE_WORD.get(sport, "week"),
        "n": len(cards),
        "cards": cards,
        "line_source": lines.line_source_for(sport),
        "sorted_by": (
            "size of disagreement with the market; no comparison sorts last"
            if lines.line_source_for(sport)["available"]
            else "prediction id; this sport has no line source, so there is no "
                 "disagreement to sort by"
        ),
    }


def available_weeks(conn: sqlite3.Connection, sport: str) -> list[dict]:
    calibration.require_sport(sport, "views.available_weeks")
    return [
        {"season": r["season"], "week": r["week"], "n": r["n"]}
        for r in conn.execute(
            "SELECT g.season, g.week, COUNT(*) AS n FROM predictions p"
            " JOIN games g ON g.id = p.game_id WHERE p.sport = ?"
            " GROUP BY g.season, g.week ORDER BY g.season DESC, g.week DESC",
            (sport,),
        )
    ]


def _empty_slate_message(conn: sqlite3.Connection, sport: str) -> str:
    """Why this tab is empty, in words. An empty tab that says nothing looks
    broken; an empty tab that says when the first slate arrives is just early."""
    label = config.SPORT_LABELS.get(sport, sport.upper())

    # A sport may know something more specific about why it is empty. Basketball
    # does: it can say the season starts on a named date, how far off that is,
    # and how many games are already loaded and waiting. An empty tab that says
    # "the season starts in 52 days" is early; one that says nothing is broken.
    adapter = sports.get(sport)
    note = getattr(adapter, "first_slate_note", None)
    if note is not None:
        detail = note(conn, config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON))
        if detail and detail.get("message"):
            return detail["message"]

    upcoming = conn.execute(
        "SELECT MIN(kickoff_utc) AS first FROM games"
        " WHERE sport = ? AND status = 'scheduled' AND kickoff_utc IS NOT NULL",
        (sport,),
    ).fetchone()
    loaded = conn.execute(
        "SELECT COUNT(*) AS n FROM games WHERE sport = ?", (sport,)
    ).fetchone()["n"]
    if not loaded:
        return (
            f"No {label} games are loaded yet. Run the loader for this sport; "
            "until then there is nothing to forecast and nothing is wrong."
        )
    if upcoming and upcoming["first"]:
        return (
            f"No {label} forecasts written yet. The next scheduled game is "
            f"{upcoming['first'].replace('T', ' ')}, and the first slate will be "
            "written blind before it."
        )
    return (
        f"No {label} forecasts written yet, and no scheduled games are loaded. "
        "The schedule for the coming season has not been published to the "
        "source yet."
    )


def history(
    conn: sqlite3.Connection,
    *,
    sport: str,
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
    calibration.require_sport(sport, "views.history")
    where = ["p.sport = ?"]
    params: list = [sport]
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
    """One prediction, by id. Not sport-scoped because an id names exactly one
    row of exactly one sport; the sport is returned on the payload."""
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
        "sport": r["sport"],
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


def scorecard(conn: sqlite3.Connection, sport: str) -> dict:
    calibration.require_sport(sport, "views.scorecard")
    payload = calibration.scorecard(conn, sport=sport)
    payload["meta"] = meta(conn, sport)
    calibration.assert_every_figure_has_n(payload)
    calibration.assert_single_sport(payload, sport)
    return payload


def factors(conn: sqlite3.Connection, sport: str) -> dict:
    from .factors import store

    calibration.require_sport(sport, "views.factors")
    report = calibration.factor_report(conn, sport=sport)
    stored = {f["name"]: f for f in store.stored_factors(conn, sport=sport)}
    for entry in report["factors"]:
        row = stored.get(entry["factor"])
        if row:
            entry["recorded_added_utc"] = row["added_utc"]
            entry["deactivated_utc"] = row["deactivated_utc"]
    calibration.assert_every_figure_has_n(report)
    return report


# ---------------------------------------------------------------------------
# how stale is what we know
# ---------------------------------------------------------------------------

#: Where each sport's schedule comes from, as a LIKE pattern over the fetch
#: cache. Staleness is measured from the actual fetch record rather than from a
#: loader's own report of success, because a loader served entirely from cache
#: reports success and fetches nothing — which is exactly how a six-hour TTL hid
#: three finished baseball games while `load` said it had touched 2,458 rows.
SCHEDULE_URL_PATTERNS = {
    "nfl": "%nflverse-data%schedules%",
    "mlb": "%statsapi.mlb.com%schedule%",
    "nba": "%stats.nba.com%scheduleleaguev2%",
}

#: Beyond this, a sport's schedule is reported stale rather than merely old.
STALE_AFTER_HOURS = 12


def schedule_staleness(conn: sqlite3.Connection) -> dict:
    """Age of the newest schedule fetch, per sport.

    Reported so a silent loader is VISIBLE rather than assumed healthy. There is
    no combined figure: staleness belongs to one sport at a time like every
    other number here.
    """
    from datetime import datetime, timezone

    from .data import sources

    now = datetime.now(timezone.utc)
    out = []
    for sport in config.SPORTS:
        newest = sources.newest_fetch(conn, SCHEDULE_URL_PATTERNS[sport])
        if newest is None:
            out.append({
                "sport": sport,
                "label": config.SPORT_LABELS.get(sport, sport.upper()),
                "fetched_utc": None,
                "age_hours": None,
                "stale": True,
                "note": "no schedule has ever been fetched for this sport",
            })
            continue
        age = (now - datetime.strptime(newest, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )).total_seconds() / 3600.0
        out.append({
            "sport": sport,
            "label": config.SPORT_LABELS.get(sport, sport.upper()),
            "fetched_utc": newest,
            "age_hours": round(age, 2),
            "stale": age > STALE_AFTER_HOURS,
            "note": (
                f"schedule last fetched {age:.1f}h ago"
                if age <= STALE_AFTER_HOURS
                else f"schedule last fetched {age:.1f}h ago, which is stale; "
                     "results may have finished upstream without being recorded"
            ),
        })
    return {
        "side_by_side_sports": True,
        "stale_after_hours": STALE_AFTER_HOURS,
        "sports": out,
    }


def season_record(conn: sqlite3.Connection, sport: str) -> dict:
    """The active sport's settled record, for the header.

    Wins and losses of RESOLVED predictions in the current season, one sport
    only. LAW 6: there is no combined figure and the header shows whichever
    sport is being looked at, never a total.
    """
    calibration.require_sport(sport, "views.season_record")
    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    row = conn.execute(
        "SELECT COUNT(*) AS n, SUM(p.outcome) AS wins FROM predictions p"
        " JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND p.resolved_utc IS NOT NULL"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)",
        (sport, season),
    ).fetchone()
    n = row["n"] or 0
    wins = row["wins"] or 0
    updated = conn.execute(
        "SELECT MAX(resolved_utc) AS last FROM predictions WHERE sport = ?", (sport,)
    ).fetchone()["last"]
    return {
        "sport": sport,
        "label": config.SPORT_LABELS.get(sport, sport.upper()),
        "season": season,
        "n": n,
        "wins": wins,
        "losses": n - wins,
        "updated_utc": updated,
        # Said in words rather than assembled in the browser, so the one place
        # that decides how a record reads is here.
        "line": (
            f"{config.SPORT_LABELS.get(sport, sport.upper())} this season "
            f"{wins}-{n - wins}"
            if n else
            f"{config.SPORT_LABELS.get(sport, sport.upper())} this season - nothing settled yet"
        ),
    }
