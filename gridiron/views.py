"""View models for the interface. Assembly only — no computation of new claims.

Everything here reads the record and shapes it for display. It never writes and
never derives a probability, so the numbers a person sees on the page are the
numbers that were written when the prediction was made.
"""

from __future__ import annotations

import json
import sqlite3

from . import calibration, config, db, language, sports
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
        """The slate's forecasts. VOIDED ROWS ARE NOT FORECASTS.

        A void is terminal: the question was never answered, the row is out of
        every curve, and it must not appear on the picks list as though the
        model were standing behind it. Forty-seven voided NBA rows -- written
        52 days before tip, then voided for exactly that reason -- were
        rendering as live forecasts on This week, twenty of them additionally
        showing the opposite side (K1). They belong in History with a VOID chip
        and their reason, which is where they now are and the only place.
        """
        if w is None:
            return []
        return conn.execute(
            "SELECT p.*, g.home, g.away, g.kickoff_utc, g.status, g.home_score,"
            " g.away_score FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND g.season = ? AND g.week = ?"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)"
            " ORDER BY p.id",
            (sport, s, w),
        ).fetchall()

    rows = fetch(season, wk)
    if not rows and not explicit:
        # The upcoming week may not be forecast yet (or this may be a backtest
        # database with no upcoming week at all). Fall back to the most recent
        # week that actually has forecasts rather than showing an empty page.
        latest = conn.execute(
            "SELECT g.season, g.week FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ?"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)"
            " ORDER BY g.season DESC, g.week DESC LIMIT 1",
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
                # Who the pick is FOR when the model takes the NO side.
                "opponent": r["away"] if r["subject"] == r["home"] else r["home"],
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
                # The side, in words, from the ONE humaniser. The renderer used
                # to build this and got spreads backwards on 34 cards.
                "chance_clause": language.chance_clause({
                    "subject": r["subject"], "market_type": r["market_type"],
                    "prop_type": r["prop_type"], "model_side": r["model_side"],
                    "line_asked": r["line_asked"],
                    "opponent": (r["away"] if r["subject"] == r["home"]
                                 else r["home"]),
                }),
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
                # --- the compact row (K2) -------------------------------------
                # Built here, not in the renderer. The row shows five things and
                # every one of them is a phrase the server wrote.
                "row_title": _row_title(r),
                "start_local": _start_local(r["kickoff_utc"]),
                "bucket_line": _bucket_line(bucket_cache[key]),
                "resolved_story": _resolved_story(r, gap),
            }
        )
        # PLAIN WORDS, built on the SERVER, exactly as the history table does.
        # The card used to build its own sentence in JavaScript from the raw
        # `subject` and a hardcoded verb, and it was wrong in two ways at once:
        # it printed the stored identifier ("FERNANDO TATIS JR. BATTER_HITS")
        # and it said "over" for every prop regardless of which side the model
        # had actually taken. A card reading "72% chance he goes over" beside a
        # prediction of UNDER is not a cosmetic fault; it is the interface
        # stating the opposite of the record.
        #
        # This is precisely the drift `language.py` exists to prevent, and the
        # reason it says the humanising rules live in ONE place: the history
        # table was fixed in C1 and the card was left building its own.
        cards[-1]["phrase"] = language.phrase(cards[-1])
        cards[-1]["player"] = language.strip_market_suffix(
            cards[-1]["subject"], cards[-1]["market"]
        )
        cards[-1]["market_label"] = language.market_label(cards[-1])
        cards[-1]["side_word"] = language.SIDE_WORDS.get(
            r["model_side"], r["model_side"] or ""
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
        # A THIN SLATE HAS TO EXPLAIN ITSELF. Eight picks on a fourteen-game
        # card reads as a failure until the floor is named, and the floor
        # holding is the system working (ruling R4).
        "below_floor": _below_floor(conn, sport, wk),
        "floor": config.PROPS_MIN_CLAIM,
        "quiet_markets": _quiet_markets(conn, sport, season, wk) if wk else [],
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
        item = {
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
                # The side, in words, from the ONE humaniser. The renderer used
                # to build this and got spreads backwards on 34 cards.
                "chance_clause": language.chance_clause({
                    "subject": r["subject"], "market_type": r["market_type"],
                    "prop_type": r["prop_type"], "model_side": r["model_side"],
                    "line_asked": r["line_asked"],
                    "opponent": (r["away"] if r["subject"] == r["home"]
                                 else r["home"]),
                }),
                "market_line_at_the_time": snap.get("line"),
                "market_implied_prob": snap.get("implied_prob"),
                "outcome": r["outcome"],
                "resolved_utc": r["resolved_utc"],
                "voided": r["id"] in voided,
                "void_reason": voided.get(r["id"]),
                "degraded": r["degraded"],
                "factor_set_version": r["factor_set_version"],
        }
        # PLAIN WORDS, built once on the server. The same sentence appears on a
        # card, in this table and in the digest; three copies of the humanising
        # rules would drift into three vocabularies, which is how this table
        # came to have two columns both called "Market".
        item["phrase"] = language.phrase(item)
        item["result"] = language.result_word(item)
        item["market_label"] = language.market_label(item)
        item["player"] = language.strip_market_suffix(item["subject"], item["market"])
        items.append(item)
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
                # The side, in words, from the ONE humaniser. The renderer used
                # to build this and got spreads backwards on 34 cards.
                "chance_clause": language.chance_clause({
                    "subject": r["subject"], "market_type": r["market_type"],
                    "prop_type": r["prop_type"], "model_side": r["model_side"],
                    "line_asked": r["line_asked"],
                    "opponent": (r["away"] if r["subject"] == r["home"]
                                 else r["home"]),
                }),
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


# ---------------------------------------------------------------------------
# since you last looked
# ---------------------------------------------------------------------------

def digest(
    conn: sqlite3.Connection,
    *,
    sport: str,
    since: str | None = None,
    day: str | None = None,
) -> dict:
    """What happened while you were away, for one sport.

    Two modes, and the difference matters:

      * `since` — everything resolved after this device last looked. The panel
        that leads the front page.
      * `day` — everything resolved on one calendar day, whether or not you
        were watching. This is what makes the digest LINKABLE: "what happened
        while I was away" should not evaporate the moment it is read once.

    Read-only by construction. The web layer hands this a `query_only`
    connection, and a test asserts the digest path cannot write even when
    handed a writable one — a page that summarises the record must not be able
    to touch it (LAW 3).
    """
    calibration.require_sport(sport, "views.digest")

    if day:
        window = (f"{day}T00:00:00Z", f"{day}T23:59:59Z")
        scope = f"on {day}"
    else:
        window = (since or "0000-01-01T00:00:00Z", db.utcnow())
        scope = "since you last looked" if since else "so far"

    rows = conn.execute(
        "SELECT p.id, p.subject, p.model_prob, p.model_side, p.outcome,"
        " p.resolved_utc, p.market_type, p.prop_type, p.predictor,"
        " g.home, g.away, g.home_score, g.away_score,"
        " s.implied_prob"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " LEFT JOIN market_snapshots s ON s.prediction_id = p.id"
        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL"
        "   AND p.resolved_utc > ? AND p.resolved_utc <= ?"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)"
        " ORDER BY p.resolved_utc DESC, p.id DESC",
        (sport, window[0], window[1]),
    ).fetchall()

    settled = []
    for r in rows:
        settled.append({
            "prediction_id": r["id"],
            "matchup": f"{r['away']} @ {r['home']}",
            "subject": r["subject"],
            "model_prob": r["model_prob"],
            "market_prob": r["implied_prob"],
            "outcome": r["outcome"],
            "correct": bool(r["outcome"]),
            "final_score": (
                f"{r['away']} {r['away_score']} - {r['home_score']} {r['home']}"
                if r["home_score"] is not None else None
            ),
            "market": r["prop_type"] or r["market_type"],
            "predictor": r["predictor"],
            "resolved_utc": r["resolved_utc"],
        })

    n = len(settled)
    correct = sum(1 for s in settled if s["correct"])
    brier = (
        round(sum((s["model_prob"] - s["outcome"]) ** 2 for s in settled) / n, 4)
        if n else None
    )

    # --- the headline, in the mockup's words -------------------------------
    if n:
        headline = (
            f"Since you last looked: {n} resolved - {correct} correct, "
            f"{n - correct} wrong"
        )
        if brier is not None:
            headline += f" · Brier {brier}"
    else:
        headline = _nothing_resolved_message(conn, sport)

    return {
        "sport": sport,
        "sport_label": config.SPORT_LABELS.get(sport, sport.upper()),
        "scope": scope,
        "since": window[0] if not day else None,
        "day": day,
        "n": n,
        "correct": correct,
        "wrong": n - correct,
        "brier": brier,
        "headline": headline,
        "settled": settled,
        "movement": _record_movement(conn, sport, n),
        "today": _todays_slate_line(conn, sport),
        # Warnings travel to the FRONT page. A panel nobody visits is a panel
        # that cannot warn anybody.
        "warnings": _front_page_warnings(conn),
    }


def _nothing_resolved_message(conn: sqlite3.Connection, sport: str) -> str:
    """The empty state, in plain words and with the next thing named."""
    label = config.SPORT_LABELS.get(sport, sport.upper())
    row = conn.execute(
        "SELECT MIN(kickoff_utc) AS next FROM games WHERE sport = ?"
        " AND status = 'scheduled' AND kickoff_utc > ?",
        (sport, db.utcnow()),
    ).fetchone()
    if row and row["next"]:
        return (
            f"Nothing resolved since you last looked. Next {label} games "
            f"{_friendly_time(row['next'])}."
        )
    return f"Nothing resolved since you last looked, and no {label} games are scheduled."


def _friendly_time(iso: str) -> str:
    """"tonight at 6:40" rather than an ISO timestamp, because this line is
    read by a person deciding whether to come back later."""
    from datetime import datetime, timezone

    try:
        when = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return iso
    now = datetime.now(timezone.utc)
    delta = (when.date() - now.date()).days
    clock = when.strftime("%H:%M UTC")
    if delta <= 0:
        return f"today at {clock}"
    if delta == 1:
        return f"tomorrow at {clock}"
    return f"on {when.date().isoformat()} at {clock}"


def _record_movement(conn: sqlite3.Connection, sport: str, just_settled: int) -> dict:
    """Resolved counts before and after, and how far the gate still is.

    One sport. LAW 6 means there is no combined movement figure and there never
    will be one here.
    """
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM predictions WHERE sport = ?"
        " AND resolved_utc IS NOT NULL"
        " AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                 WHERE v.prediction_id = predictions.id)",
        (sport,),
    ).fetchone()["n"]

    buckets = []
    for lo, hi, label in calibration.BUCKETS:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM predictions WHERE sport = ?"
            " AND resolved_utc IS NOT NULL AND model_prob >= ? AND model_prob < ?"
            " AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                 WHERE v.prediction_id = predictions.id)",
            (sport, lo, hi),
        ).fetchone()["n"]
        if not n:
            continue
        buckets.append({
            "label": label,
            "n": n,
            "needed": max(0, config.MIN_SAMPLE_FOR_EDGE_CLAIM - n),
            "provisional": n < config.MIN_SAMPLE_FOR_BUCKET_POINT,
            # The countdown line, right-aligned in the design and deliberately
            # unglamorous: it is the honest distance to being able to say
            # anything at all.
            "countdown": (
                f"{label} bucket: {n} of {config.MIN_SAMPLE_FOR_EDGE_CLAIM}"
                f" · {max(0, config.MIN_SAMPLE_FOR_EDGE_CLAIM - n)} more"
                " before calibration speaks"
            ),
        })

    return {
        "sport": sport,
        "resolved_before": total - just_settled,
        "resolved_now": total,
        "gained": just_settled,
        "buckets": buckets,
        "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
    }


def _below_floor(conn: sqlite3.Connection, sport: str, wk: int | None) -> int:
    """How many prop questions this slate formed and did not ask.

    Read from the task's own recorded payload rather than recomputed: the
    number the reader sees is the number the run actually reported, so the
    card and the schedule panel cannot drift apart.
    """
    if wk is None:
        return 0
    row = conn.execute(
        "SELECT payload_json FROM task_runs WHERE task = ?"
        " AND payload_json LIKE ? ORDER BY id DESC LIMIT 1",
        (f"predict:{sport}", f'%"week": {wk},%'),
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(json.loads(row["payload_json"]).get("below_floor") or 0)
    except (ValueError, TypeError):
        return 0


def _row_title(r) -> str:
    """The row's heading: a matchup, or a subject and what is being asked.

    "SD @ TB" for a game market; "TATIS JR. - HITS" for a prop, because on a
    prop the subject IS the headline and the fixture is a detail that belongs
    on the pick line underneath.
    """
    if r["market_type"] != "prop":
        return f"{r['away']} @ {r['home']}"
    name = language.strip_market_suffix(r["subject"], r["prop_type"])
    surname = name.split()[-1] if name else name
    # "Fernando Tatis Jr." -> "Tatis Jr."; a row is not the place for a full
    # name, and the expanded view carries it.
    parts = (name or "").split()
    if len(parts) > 2 and parts[-1].rstrip(".").lower() in ("jr", "sr", "ii", "iii"):
        surname = " ".join(parts[-2:])
    return f"{surname} · {language.humanise(r['prop_type'])}"


def _start_local(kickoff_utc: str | None) -> str | None:
    """The start time as a reader's clock shows it, or None.

    A card that says 6:40 PM means the reader's evening. Formatted server-side
    so one implementation decides it; the browser's own timezone is applied by
    the browser, which is the one thing it is better placed to know -- so this
    returns the UTC instant and the row renders it.
    """
    return kickoff_utc


def _bucket_line(bucket: dict) -> str:
    """"50-60% bucket · 6 resolved · too few to grade", in words.

    LAW 4 on one line: the bucket, its N, and -- when the N is short -- what
    that means, rather than a number a reader has to interpret.
    """
    label = bucket.get("label") or "?"
    n = bucket.get("n") or 0
    minimum = bucket.get("minimum") or config.MIN_SAMPLE_FOR_BUCKET_POINT
    if n == 0:
        return f"{label} bucket · nothing resolved here yet"
    if n < minimum:
        return f"{label} bucket · {n} resolved · too few to grade"
    return f"{label} bucket · {n} resolved"


def _resolved_story(r, gap) -> str | None:
    """One line telling what happened, for the resolved section."""
    if r["resolved_utc"] is None or r["status"] != "final":
        return None
    subject = language.strip_market_suffix(r["subject"], r["prop_type"])
    story = f"picked {subject}"
    if r["home_score"] is not None and r["away_score"] is not None:
        winner = r["home"] if r["home_score"] > r["away_score"] else r["away"]
        story += (f" · {winner} won {max(r['home_score'], r['away_score'])}"
                  f"-{min(r['home_score'], r['away_score'])}")
    if gap is not None:
        story += f" · gap was {gap * 100:+.0f}"
    return story


def _todays_slate_line(conn: sqlite3.Connection, sport: str) -> dict:
    """Today's slate in one line, with the sharpest disagreement as the teaser."""
    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    week = repo.next_unplayed_week(conn, season, sport=sport)
    if week is None:
        return {"n": 0, "line": None, "week": None}

    rows = conn.execute(
        "SELECT p.model_prob, p.subject, g.away, g.home, s.implied_prob"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " LEFT JOIN market_snapshots s ON s.prediction_id = p.id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ?"
        "   AND p.resolved_utc IS NULL"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)",
        (sport, season, week),
    ).fetchall()
    if not rows:
        # Still say which markets went quiet. A slate with nothing standing is
        # exactly when a reader wants to know whether the model declined to
        # answer or was never asked.
        return {
            "n": 0, "line": None, "week": week,
            "quiet_markets": _quiet_markets(conn, sport, season, week),
        }

    label = config.SPORT_LABELS.get(sport, sport.upper())
    sharpest, gap = None, 0.0
    for r in rows:
        if r["implied_prob"] is None:
            continue
        delta = r["model_prob"] - r["implied_prob"]
        if abs(delta) > abs(gap):
            sharpest, gap = r, delta
    line = f"{len(rows)} {label} predictions in"
    if sharpest is not None:
        line += (
            f" · sharpest disagreement {gap * 100:+.1f} on "
            f"{sharpest['away']} @ {sharpest['home']}"
        )
    return {
        "n": len(rows), "week": week, "line": line,
        "sharpest_gap": round(gap, 4) if sharpest is not None else None,
        "quiet_markets": _quiet_markets(conn, sport, season, week),
    }


def _quiet_markets(conn: sqlite3.Connection, sport: str, season: int,
                   week: int) -> list[str]:
    """Prop markets this slate asked NOTHING in, said in words (ruling 1).

    A market where the model never reached the confidence floor at the line the
    market actually quotes is the floor working, not a defect and not a gap. The
    slate says so, because a silent absence reads as a failure to find questions
    and invites exactly the wrong repair -- adding rungs until the model is
    confident somewhere, which is choosing the questions to flatter the answer.
    """
    from . import horizon

    props = config.SPORT_PROP_MARKETS.get(sport, ())
    if not props:
        return []
    asked = {
        r["prop_type"]: r["n"]
        for r in conn.execute(
            "SELECT p.prop_type, COUNT(*) AS n FROM predictions p"
            " JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND g.season = ? AND g.week = ?"
            "   AND p.market_type = 'prop' AND p.predictor = 'statistical'"
            " GROUP BY p.prop_type",
            (sport, season, week),
        )
    }
    return [
        horizon.zero_write_line(market, asked.get(market, 0), config.PROPS_MIN_CLAIM)
        for market in props
        if not asked.get(market)
    ]


def _front_page_warnings(conn: sqlite3.Connection) -> list[dict]:
    """MISSED slates, silent tasks and stale schedules, on the front page.

    Not sport-scoped, and that is not a LAW 6 problem: these are facts about
    the APPLIANCE, not about any sport's record. A cron job that did not fire
    belongs to the machine.
    """
    from . import tasks

    out: list[dict] = []
    status = tasks.status(conn)
    for task in status["tasks"]:
        if task["silent"]:
            out.append({"kind": "silent", "text": f"{task['task']}: {task['warning']}"})
        for missed in task["missed"]:
            out.append({
                "kind": "missed",
                "text": f"{task['task']} MISSED {missed['started_utc']}: "
                        f"{missed['detail'][:160]}",
            })
    for entry in status["schedule_staleness"]["sports"]:
        if entry["stale"]:
            out.append({
                "kind": "stale",
                "text": f"{entry['label']} schedule: {entry['note']}",
            })
    return out


def seen_marker(conn: sqlite3.Connection, session_id: str | None, sport: str) -> str | None:
    """When this device last read THIS SPORT's digest, without moving it."""
    if not session_id:
        return None
    row = conn.execute(
        "SELECT last_seen_utc FROM session_seen WHERE session_id = ? AND sport = ?",
        (session_id, sport),
    ).fetchone()
    return row["last_seen_utc"] if row else None


def mark_seen(
    conn: sqlite3.Connection, session_id: str | None, sport: str
) -> str | None:
    """Advance this device's marker FOR ONE SPORT and return what it was.

    Per sport, and that is not fussiness. With one marker per device, opening
    the app on football advanced it, and switching to baseball then reported
    "nothing resolved since you last looked" across six results that had landed
    minutes earlier. The panel was confidently wrong about the only thing it
    exists to say.

    Returns the PREVIOUS value so the caller computes the digest against it
    before the marker moves.
    """
    if not session_id:
        return None
    previous = seen_marker(conn, session_id, sport)
    conn.execute(
        "INSERT INTO session_seen (session_id, sport, last_seen_utc)"
        " VALUES (?,?,?) ON CONFLICT(session_id, sport)"
        " DO UPDATE SET last_seen_utc = excluded.last_seen_utc",
        (session_id, sport, db.utcnow()),
    )
    conn.commit()
    return previous
