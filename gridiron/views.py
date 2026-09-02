"""View models for the interface. Assembly only — no computation of new claims.

Everything here reads the record and shapes it for display. It never writes and
never derives a probability, so the numbers a person sees on the page are the
numbers that were written when the prediction was made.
"""

from __future__ import annotations

import json
import sqlite3

from . import (audit, buildinfo, calibration, config, db, language,
               sports, subjects)
from .data import reference, repo, teams
from .factors import compute as factor_compute, registry
from .market import lines


def sports_summary(conn: sqlite3.Connection) -> dict:
    """Per-sport counts for the tab labels.

    Every sport is listed even with nothing in it, and each carries its own
    resolved count, so an empty record is visible BEFORE clicking the tab. A
    tab that looks the same whether it holds a season or nothing is a tab that
    hides an empty record (LAW 4 and LAW 6 together).
    """
    # ALL TIME, RESOLVED, NON-VOID, and one row per sport -- never a total.
    # The wins are summed inside the sport's own row precisely so that no
    # query in this function can produce a figure spanning two of them.
    rows = {
        r["sport"]: r
        for r in conn.execute(
            "SELECT p.sport, COUNT(*) AS written,"
            " SUM(CASE WHEN p.resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved,"
            " SUM(CASE WHEN p.resolved_utc IS NOT NULL"
            "          AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                          WHERE v.prediction_id = p.id)"
            "     THEN 1 ELSE 0 END) AS settled,"
            " SUM(CASE WHEN p.resolved_utc IS NOT NULL"
            "          AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                          WHERE v.prediction_id = p.id)"
            "     THEN COALESCE(p.outcome, 0) ELSE 0 END) AS wins"
            " FROM predictions p GROUP BY p.sport"
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
        label = config.SPORT_LABELS.get(sport, sport.upper())
        settled = (row["settled"] if row else 0) or 0
        wins = (row["wins"] if row else 0) or 0
        written = (row["written"] if row else 0) or 0
        out.append({
            "sport": sport,
            "label": label,
            "n": (row["resolved"] if row else 0) or 0,
            "written": written,
            "voided": voided.get(sport, 0),
            "settled": settled,
            "wins": wins,
            "losses": settled - wins,
            # THE TAB'S OWN RECORD, in words, written here. The renderer used
            # to glue `sp.label + ': ' + sp.n + ' settled'` together itself.
            "record_line": language.sport_record_line(
                label, wins, settled - wins, settled),
            "record_parts": language.sport_record_parts(
                wins, settled - wins, settled),
            "record_detail": language.sport_record_detail(
                label, wins, settled - wins, settled, written,
                voided.get(sport, 0)),
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
    payload = {
        "sport": sport,
        "sport_label": config.SPORT_LABELS.get(sport, sport.upper()),
        "sports": sports_summary(conn),
        "markets": list(config.SPORT_MARKETS.get(sport, ())),
        "prop_markets": list(config.SPORT_PROP_MARKETS.get(sport, ())),
        "line_source": lines.line_source_for(sport),
        "database_kind": kind["kind"],
        # Said here. The browser built this label by uppercasing the stored
        # kind and appending " DATABASE -- ", which is prose composed in the
        # renderer out of a data field.
        "database_label": language.database_label(kind["kind"]),
        "database_note": kind["note"],
        "factor_set_version": config.FACTOR_SET_VERSION,
        # The date the current set began. What a reader can actually use: a
        # version code says neither what changed nor when.
        "factor_set_started": config.FACTOR_SET_ACTIVATED.get(
            config.FACTOR_SET_VERSION
        ),
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
        # WHICH BUILD THIS IS. Present in the payload rather than composed in
        # the browser, and computed by the same function the launcher calls so
        # the window and the launcher cannot disagree about how old it is.
        "build": buildinfo.freshness(),
        "not_a_betting_tool": (
            "Gridiron states probabilities and keeps score of them. It does not "
            "size stakes, manage a bankroll, or recommend a bet, and it connects "
            "to no sportsbook or exchange."
        ),
    }
    # The footer sentence, composed by the humaniser rather than glued together
    # in the browser. It is prose about data -- a spend, a span of seasons, a
    # coverage count -- and every one of those was formatted in `app.js`.
    payload["colophon"] = language.colophon(payload)
    return payload

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


def _why_phrases() -> dict:
    """Factor name -> its declared WHY phrase.

    Read from the registry so the prose on a card comes from the same
    declaration as the factor itself. Cached because a slate rebuilds this once
    per card otherwise, and the registry does not change while the process runs.
    """
    global _WHY_CACHE
    if _WHY_CACHE is None:
        from .factors import registry

        _WHY_CACHE = {f.name: f.why for f in registry.all_factors() if f.why}
    return _WHY_CACHE


_WHY_CACHE: dict | None = None


def _top_factors(payload: dict, limit: int = 5) -> list[dict]:
    sources = payload.get("sources") or {}
    contributions = payload.get("contributions") or []
    if contributions:
        return [
            {
                "factor": c["factor"],
                # The same phrase the pick cards and the Factors table use.
                # Without it the worked example's bars were labelled
                # `asked_line`, `srs_diff`, `home_field` -- the decomposition
                # is the one thing on that page whose whole job is explaining,
                # and it was the only part still speaking in column names.
                "plain_name": _why_phrases().get(c["factor"]),
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
         wk: int | None = None, forecaster: str | None = None) -> dict:
    """THE SLATE: one card per forecast, sorted by disagreement with the market.

    "Week" is the slate key. NFL and NBA number weeks; MLB numbers days, since
    a baseball slate is a day's card. Either way it is an integer that orders
    the record, and the interface prints the sport's own word for it.
    """
    calibration.require_sport(sport, "views.week")
    venues = _venues(conn, sport)
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
            "SELECT p.*, g.home, g.away, g.kickoff_utc, g.status,"
            " g.live_period, g.live_clock, g.home_score, g.league_date,"
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
            # THE GLANCE IS PRESENT ON AN EMPTY SLATE TOO. A summary panel
            # that disappears when there is nothing on the card only works on
            # the days a reader least needs it, and one payload shape with a
            # sometimes-missing key is how a renderer learns to guess.
            return {"sport": sport, "season": season, "week": None, "n": 0,
                    "cards": [], "message": _empty_slate_message(conn, sport),
                    # ONE PAYLOAD SHAPE. A key that is present on a full slate
                    # and missing on an empty one is how a renderer learns to
                    # guess, which is the rule the glance already follows.
                    "forecaster": forecaster or config.PICKS_DEFAULT_FORECASTER,
                    "forecasters": [],
                    "forecaster_message": None,
                    "slate_word": config.SPORT_SLATE_WORD.get(sport, "week"),
                    "line_source": lines.line_source_for(sport),
                    "glance": _glance(conn, sport, []),
                    "slate_title": language.slate_title(
                        season, None, config.SPORT_SLATE_WORD.get(sport, "week")),
                    "sorted_by": "size of disagreement with the market"}
        season, wk = latest["season"], latest["week"]
        rows = fetch(season, wk)

    # ONE FORECASTER IN ONE RANKING (GRIDIRON_14).
    #
    # THE SLATE IS CHOSEN FROM EVERY PREDICTION ON IT AND FILTERED AFTER, not
    # filtered first. Filtering first would let a forecaster that skipped
    # today pull the page back to whatever day it last ran, so changing the
    # selector would silently change the DATE as well as the forecaster.
    #
    # Before this, both forecasters were listed together, unlabelled and each
    # sorted on its own disagreement with the market, so one game could appear
    # twice naming opposite sides -- "Cleveland to win 53%" four rows above
    # "Toronto to win 53%", with nothing on either saying who said it.
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["predictor"]] = counts.get(r["predictor"], 0) + 1
    chosen = forecaster or config.PICKS_DEFAULT_FORECASTER
    available = [
        {"forecaster": name,
         "label": config.FORECASTER_LABELS.get(name, name),
         "n": counts[name]}
        for name in sorted(
            counts, key=lambda n: (n != config.PICKS_DEFAULT_FORECASTER, n))
    ]
    # AN ABSENT FORECASTER IS NOT QUIETLY SWAPPED for one that has rows: the
    # page would then show a ranking under a name that did not produce it,
    # which is the same lie as mixing them, told more quietly.
    rows = [r for r in rows if r["predictor"] == chosen]

    # ONE CARD PER QUESTION, and the second reason a game appeared twice.
    #
    # `predict:nfl` ran twice on 2026-08-29 -- 05:55Z and again at 07:34Z --
    # and wrote a full second set of forecasts for week 1. Both rows are the
    # record and both stay: LAW 3 is append-only and a prediction is never
    # deleted, so 26 of the 52 NFL questions legitimately hold two forecasts.
    # THE SLATE IS NOT THE RECORD, though. A picks list showing both says the
    # model has two opinions about one question and offers no way to tell
    # which is standing.
    #
    # The latest one written is the standing one: a later forecast supersedes
    # an earlier one and the earlier stays in the results. (The withdrawn
    # operator-calls feature applied the same rule to a revised call, which is
    # where the precedent came from.) Nothing here changes what is scored --
    # both rows remain in every curve, which is why the double run is a
    # RECORD problem reported in the close-out and not something a display
    # filter may quietly paper over.
    standing: dict = {}
    for r in rows:
        key = (r["game_id"], r["market_type"], r["subject"], r["line_asked"])
        seen = standing.get(key)
        if seen is None or (r["created_utc"], r["id"]) > (seen["created_utc"], seen["id"]):
            standing[key] = r
    superseded = len(rows) - len(standing)
    rows = sorted(standing.values(), key=lambda r: r["id"])

    forecaster_message = None
    if not rows and available:
        forecaster_message = language.no_picks_from(
            config.FORECASTER_LABELS.get(chosen, chosen),
            [(f["label"], f["n"]) for f in available
             if f["forecaster"] != chosen])

    ids = [r["id"] for r in rows]
    snapshots = lines.snapshots_for(conn, ids)
    voided = _voids_for(conn, ids)
    # One lookup for the slate, not one per card. Empty when the team table has
    # not been loaded, and every name then falls back to its tricode.
    team_names = teams.names(conn, sport)
    # One bucket record per (market, predictor, bucket) rather than one per
    # card: the same lookup would otherwise run once for every pick on the slate.
    bucket_cache: dict[tuple, dict] = {}
    cards = []
    for r in rows:
        payload = json.loads(r["factors_json"] or "{}")
        snap = snapshots.get(r["id"]) or {}
        implied = snap.get("implied_prob")
        # THE SHOWN NUMBER drives the chip, the gap and the sort. See
        # `shown_prob`: a card whose tier and percentage disagree is worse than
        # either being wrong, because both are real numbers and neither looks
        # like the mistake.
        shown = shown_prob(r)
        gap = None if implied is None else round(shown - implied, 4)

        key = (
            r["market_type"], r["prop_type"], r["predictor"],
            calibration.bucket_label(shown),
        )
        if key not in bucket_cache:
            bucket_cache[key] = calibration.bucket_record(
                conn, shown, sport=sport, market_type=r["market_type"],
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
                "team_names": team_names,
                "kickoff_utc": r["kickoff_utc"],
                "game_status": r["status"],
                "final_score": (
                    f"{r['away']} {r['away_score']} - {r['home_score']} {r['home']}"
                    if r["status"] == "final" else None
                ),
                "market_type": r["market_type"],
                # Recovered for reading where the column is empty; the
                # browser never queries with these. See _prose_prop_type.
                "prop_type": _prose_prop_type(r, sport),
                "market": _prose_prop_type(r, sport) or r["market_type"],
                "predictor": r["predictor"],
                "subject": r["subject"],
                "claim": (payload.get("question") or {}).get("claim"),
                "line_asked": r["line_asked"],
                # BOTH NUMBERS TRAVEL. `model_prob` is what the model
                # claimed; `shown_prob` is what the reader was shown, which
                # differ only once a correction is active. A payload carrying
                # one of them could not answer "was the correction right",
                # and the version says which correction to ask about.
                "model_prob": r["model_prob"],
                "shown_prob": shown,
                "correction_version": (r["correction_version"]
                                       if "correction_version" in r.keys()
                                       else None),
                # None on every card today, and that is the point: a raw
                # category must look exactly as it did before corrections
                # existed, or the reader is told something changed when
                # nothing did.
                "earned_line": language.earned_number_line(
                    r["model_prob"], shown, _correction_sample(conn, r),
                    (r["correction_version"]
                     if "correction_version" in r.keys() else None)),
                "model_side": r["model_side"],
        # The side, in words, from the ONE humaniser.
        "chance_clause": language.chance_clause({
            "subject": r["subject"], "market_type": r["market_type"],
            "prop_type": _prose_prop_type(r, sport), "model_side": r["model_side"],
            "line_asked": r["line_asked"],
            "opponent": r["away"] if r["subject"] == r["home"] else r["home"],
            "team_names": teams.names(conn, r["sport"]),
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
                # THE PLAIN WHY (K3). Built from the SAME contributions the
                # decomposition uses, so the words and the arithmetic cannot
                # disagree -- ordering and direction are read off them rather
                # than asserted anywhere.
                "why": language.why_block(
                    {
                        "subject": r["subject"],
                        "market_type": r["market_type"],
                        "prop_type": _prose_prop_type(r, sport),
                        # Without these two the why cannot tell which side was
                        # taken, and every reason renders against the question's
                        # yes side instead of the pick.
                        "model_side": r["model_side"],
                        "line_asked": r["line_asked"],
                        "opponent": (r["away"] if r["subject"] == r["home"]
                                     else r["home"]),
                        "model_prob": r["model_prob"],
                        "market_implied_prob": implied,
                        "team_names": team_names,
                        "contributions": payload.get("contributions") or [],
                        "absent_factors": _absent_factors(payload),
                    },
                    _why_phrases(),
                ),
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
                "resolved_story": _resolved_story(r, gap, team_names),
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
        # THE TILE'S TEXT, composed here like every other sentence (ruling,
        # 2026-08-31). A tile is 124px and three across, so it gets the
        # shortest honest form of the pick plus a label saying what its
        # percentage is a percentage OF -- both from the same `is_no_side`, so
        # the number and the word underneath cannot disagree.
        cards[-1]["tile_line"] = language.tile_line(cards[-1])
        cards[-1]["tile_label"] = language.tile_label(cards[-1])
        cards[-1]["player"] = language.strip_market_suffix(
            cards[-1]["subject"], cards[-1]["market"]
        )
        cards[-1]["sport"] = sport
        # THE SPORT NAMES ITS OWN MARKETS. Without this the label falls
        # back to the generic humaniser, which called a baseball run
        # line a "point spread" -- a sentence about the wrong sport.
        cards[-1]["market_label"] = language.market_label(cards[-1])
        # --- the game in flight (L2) ------------------------------------
        # Composed here like every other visible string. The renderer swaps
        # which of them it shows; it writes none of them.
        state = language.tile_state(
            r["status"], resolved=r["resolved_utc"] is not None,
            voided=r["id"] in voided)
        cards[-1]["tile_state"] = state
        # The slate's calendar date, so a sport whose slate key is an ordinal
        # can still be named by its date rather than by "Day 158".
        cards[-1]["league_date"] = r["league_date"]
        # THE TRICODE, which is what the column already holds. A score line
        # is read at a glance beside a 124px tile; "Alabama 21 · East Carolina
        # 7" is a sentence, and "ALA 21 · ECU 7" is a score.
        cards[-1]["score_line"] = language.score_line(
            r["home"], r["home_score"], r["away"], r["away_score"])
        cards[-1]["clock_line"] = language.clock_line(
            r["live_period"], r["live_clock"], state)
        cards[-1]["running_total"] = (
            language.running_total_line(
                r["home_score"], r["away_score"], r["line_asked"],
                language.tile_label(cards[-1]))
            if r["market_type"] == "total" else None)
        cards[-1]["verdict"] = language.verdict_word(
            r["outcome"], voided=r["id"] in voided)

        # MODEL, MARKET AND GAP AS A SENTENCE (R3), composed here like every
        # other visible string. The rail drew these three numbers as a
        # dot-and-span graphic until 2026-09-02 and made the reader estimate
        # two of them off a 100-pixel track.
        cards[-1]["rail_line"] = language.rail_numbers_line(
            cards[-1].get("shown_prob") if cards[-1].get("shown_prob") is not None
            else r["model_prob"],
            implied,
            cards[-1].get("gap"))
        # WHERE IT IS PLAYED, for the selected-pick subline. None when the
        # venue was never recorded, and the subline simply has one fewer part.
        cards[-1]["venue"] = venues.get(r["home"])
        cards[-1]["side_word"] = language.side_word_or_side(r["model_side"])

    # Sorted by disagreement size, because that is where anything interesting
    # lives. Cards with no market comparison sort last rather than first.
    cards.sort(key=lambda c: c["abs_gap"], reverse=True)
    payload = {
        "sport": sport,
        # THE SLATE AT A GLANCE (D3), computed from the cards above rather than
        # by asking the database the same questions a second time.
        "glance": _glance(conn, sport, cards),
        "season": season,
        "week": wk,
        "slate_word": config.SPORT_SLATE_WORD.get(sport, "week"),
        # WHAT TO CALL THIS SLATE, in words, composed here like every other
        # visible phrase. The renderer used to glue "Season " + season +
        # ", week " + week, which put the raw eight-digit key on the page.
        "slate_title": language.slate_title(
            season, wk, config.SPORT_SLATE_WORD.get(sport, "week"),
            # The slate's own calendar date, for the sports whose key is an
            # ordinal rather than a date. Taken from the cards so it costs no
            # query, and absent on an empty slate, which is honest.
            next((c.get("league_date") for c in cards if c.get("league_date")),
                 None)),
        "n": len(cards),
        "cards": cards,
        # WHOSE PICKS THESE ARE, and who else has some. Named on the payload
        # rather than inferred by the renderer from the cards: a list that
        # cannot say who made it is a list nobody can check.
        "forecaster": chosen,
        "forecasters": available,
        "forecaster_message": forecaster_message,
        # HOW MANY EARLIER FORECASTS THIS SLATE IS HIDING. Stated rather than
        # silent: a reader comparing the slate count against the record count
        # is owed the difference, and it is how the operator finds out a
        # prediction task ran twice.
        "superseded": superseded,
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
    # THE MERGE CANNOT REACH THE API, which is the same place the curve check
    # runs for the same reason: a guard that only runs in a test protects the
    # test. This one fired on the real slate the day it was written.
    audit.check_one_forecaster_per_list(payload)
    return payload


def _venues(conn: sqlite3.Connection, sport: str) -> dict:
    """Home city per team, for the selected pick's subline.

    ABSENT STAYS ABSENT. A team with no recorded venue contributes no city,
    and the subline renders without one rather than printing the tricode or a
    dash -- the same rule the factors follow, applied to a label.
    """
    return {
        r["tricode"]: r["venue_city"]
        for r in conn.execute(
            "SELECT tricode, venue_city FROM teams"
            " WHERE sport = ? AND venue_city IS NOT NULL", (sport,))
    }


def _count_lines(cards: list[dict]) -> dict:
    """"<market>|<tier>" -> "STRONG - 4 of 61 picks", for every combination.

    The denominator is always the slate as the OTHER filter left it, because a
    count with no whole beside it is the quietly misleading kind: four picks
    reads as a thin slate rather than a narrow filter, and nothing on the page
    tells the reader which they are looking at.
    """
    markets = {""} | {c.get("market") or "" for c in cards}
    tiers = {""} | {(c.get("tier") or {}).get("tier") or "" for c in cards}
    tiers.discard("")
    tiers.add("")
    out = {}
    for market in markets:
        in_market = [c for c in cards
                     if not market or (c.get("market") or "") == market]
        for tier in tiers:
            shown = [c for c in in_market
                     if not tier
                     or ((c.get("tier") or {}).get("tier") or "") == tier]
            out[f"{market}|{tier}"] = language.tier_filter_line(
                tier or None, len(shown), len(in_market))
    return out


def _glance(conn: sqlite3.Connection, sport: str, cards: list[dict]) -> dict:
    """WHAT THE WHOLE SLATE LOOKS LIKE, from the slate already in hand.

    Built from `cards`, not from a second query of the same rows: two counts of
    one slate is two chances to disagree, and the one that disagrees quietly is
    the one on the summary panel nobody checks.

    Every figure carries its N, and none of them is a rate. The one rate-shaped
    thing here -- how much of the record is gradeable -- is stated as a count of
    settled predictions per tier, because pooling hit rates across markets is
    the merge LAW 4 forbids.
    """
    games = {}
    for c in cards:
        games.setdefault(c["game_id"], c["kickoff_utc"])

    # --- kickoff windows, on the league's clock, GAMES not picks ------------
    counted = {name: 0 for _, _, name in language.KICKOFF_WINDOWS}
    unknown = 0
    for kickoff in games.values():
        window = language.kickoff_window(reference.eastern_hour(kickoff))
        if window is None:
            unknown += 1
        else:
            counted[window] += 1
    most = max(counted.values()) if counted else 0
    windows = [
        {
            "name": name,
            "n": counted[name],
            # A share OF THE BIGGEST WINDOW, not of the slate: the bars are
            # there to show the shape of a Saturday, and scaling to the total
            # makes three near-equal windows look like three short stubs.
            "share": (counted[name] / most) if most else 0.0,
            "line": language.window_line(name, counted[name]),
        }
        for _, _, name in language.KICKOFF_WINDOWS if counted[name]
    ]

    # --- how much of it the market priced (reported, never used to choose) --
    asked, priced = {}, {}
    for c in cards:
        # `market_label` is the ONE function that decides what a market is
        # called, so the coverage rows and the filter chips cannot end up
        # calling the same market two different things.
        key = c["market_label"]
        asked[key] = asked.get(key, 0) + 1
        if c.get("market_implied_prob") is not None:
            priced[key] = priced.get(key, 0) + 1
    coverage = [
        {
            "market": key,
            "priced": priced.get(key, 0),
            "asked": asked[key],
            "line": language.coverage_line(key, priced.get(key, 0), asked[key]),
        }
        for key in sorted(asked)
    ]

    # --- the widest disagreement on the slate -------------------------------
    lined = [c for c in cards if c.get("market_implied_prob") is not None]
    sharpest = max(lined, key=lambda c: c["abs_gap"]) if lined else None
    sharp = {
        "line": language.sharpest_line(
            sharpest["gap"] if sharpest else None,
            sharpest["phrase"] if sharpest else None),
        "prediction_id": sharpest["prediction_id"] if sharpest else None,
    }

    # --- LAW 4: how much of this sport is gradeable at all yet --------------
    proven = tiers = fullest = 0
    for market in config.SPORT_MARKETS.get(sport, ()):
        # A PROP IS STORED AS market_type='prop' WITH THE STAT IN prop_type.
        # Passing the bare stat as a market type asks for a category that has
        # no rows, and four empty buckets come back looking like four honest
        # unproven tiers -- so a sport with a proven spread would still report
        # "no tier proven yet", drowned by its own phantoms.
        is_prop = market in config.SPORT_PROP_MARKETS.get(sport, ())
        table = calibration.tier_table(
            conn, sport=sport,
            market_type="prop" if is_prop else market,
            prop_type=market if is_prop else None)
        for row in table["rows"]:
            tiers += 1
            proven += 1 if row["proven"] else 0
            fullest = max(fullest, row["n"])

    # WHAT STATE THE SLATE IS IN (R3). Counted from the games this slate's
    # cards belong to, so it cannot disagree with the tiles about how many
    # have finished.
    game_states = {}
    for c in cards:
        # `game_status`, which is what the card calls it. Reading `status` here
        # returned None for every card, so a finished slate would have counted
        # as upcoming and the countdown would have counted down to a kickoff
        # that had already happened.
        game_states.setdefault(c["game_id"], c.get("game_status"))
    done = sum(1 for st in game_states.values() if st == "final")
    running = sum(1 for st in game_states.values()
                  if st not in (None, "scheduled", "final"))
    if done and done == len(game_states):
        state = "complete"
    elif done or running:
        state = "live"
    else:
        state = "upcoming"
    kickoffs = [c["kickoff_utc"] for c in cards if c.get("kickoff_utc")]

    return {
        "games": len(games),
        "picks": len(cards),
        "state": state,
        "first_kickoff_utc": min(kickoffs) if kickoffs else None,
        "final": done,
        "in_progress": running,
        # The countdown's digits tick, so the browser renders them from the
        # instant above; every word around them is written here.
        "state_word": language.SLATE_STATES.get(state, state),
        "state_line": language.slate_state_line(state, done, len(game_states)),
        # EVERY COUNT LINE THE CONTROLS CAN PRODUCE, written here rather than
        # assembled in the browser. The pair of filters is small enough to
        # enumerate -- a handful of markets times a handful of tiers -- so the
        # renderer looks one up instead of gluing a sentence together, which
        # is what the 2026-08-31 ruling asks and what the JS tripwire checks.
        "count_lines": _count_lines(cards),
        "windows": windows,
        "windows_unknown": unknown,
        "games_line": f"{len(games)} {'game' if len(games) == 1 else 'games'}",
        # BOTH CAVEATS, JOINED, for the heading's tooltip. Still said, because
        # a caveat that vanishes is a caveat dropped -- LAW 1's reason for
        # reporting coverage rather than acting on it does not stop mattering
        # because the panel got tidier.
        "notes": (
            "Kickoff windows are grouped on the league's clock, not yours: a "
            "broadcast window is a fact about the schedule. Questions are "
            "formed for every game before any line is fetched (LAW 1), so the "
            "coverage figures say how many the market happened to price."),
        "windows_note": (
            "grouped on the league's clock, not yours: a broadcast window is a "
            "fact about the schedule"),
        "coverage": coverage,
        "coverage_note": (
            "questions are formed for every game before any line is fetched "
            "(LAW 1); this says how many the market happened to price"),
        "sharpest": sharp,
        # The row labels, written here like every other visible phrase.
        "labels": {key: language.glance_label(key)
                   for key in ("sharpest", "tiers")},
        "tiers": {
            "proven": proven,
            "of": tiers,
            "fullest": fullest,
            "needed": calibration.TIER_MIN_SETTLED,
            "line": language.tier_status_line(
                config.SPORT_LABELS.get(sport, sport), proven, tiers,
                fullest, calibration.TIER_MIN_SETTLED),
        },
    }


def live_slate(conn: sqlite3.Connection, sport: str, season: int | None = None,
               wk: int | None = None) -> dict:
    """THE COMPACT ONE. What changed about the games, and nothing else.

    The slate payload is large -- every card carries its decomposition, its
    why, its bucket -- and none of that moves while a game is being played.
    Re-fetching it every sixty seconds to learn that a score went from 7 to 10
    would be sending a book to deliver a number.

    So this is the number: per prediction, the state its game is in and the
    strings that describe it, all written by the same humaniser the full
    payload uses. `any_live` is the field the browser actually acts on -- it
    stops polling when nothing is on, rather than polling forever at a slate
    that finished hours ago.
    """
    calibration.require_sport(sport, "views.live_slate")
    season = season or config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON)
    if wk is None:
        wk = repo.next_unplayed_week(conn, season, sport=sport)
    # THE SAME SLATE THE PAGE IS SHOWING. `week()` falls back to the most
    # recent slate that has predictions when the next unplayed one has none,
    # and without the same fallback here the browser would poll one slate
    # while displaying another -- scores that never arrive, for games nobody
    # is looking at. The caller normally passes the week it is rendering;
    # this is for when it does not.
    if wk is not None and not conn.execute(
            "SELECT 1 FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND g.season = ? AND g.week = ? LIMIT 1",
            (sport, season, wk)).fetchone():
        latest = conn.execute(
            "SELECT g.season, g.week FROM predictions p"
            " JOIN games g ON g.id = p.game_id WHERE p.sport = ?"
            " ORDER BY g.season DESC, g.week DESC LIMIT 1", (sport,)).fetchone()
        if latest:
            season, wk = latest["season"], latest["week"]
    if wk is None:
        return {"sport": sport, "season": season, "week": wk, "any_live": False,
                "live": 0, "picks": []}

    voided = {r["prediction_id"] for r in conn.execute(
        "SELECT v.prediction_id FROM prediction_voids v JOIN predictions p"
        " ON p.id = v.prediction_id WHERE p.sport = ?", (sport,))}
    rows = conn.execute(
        "SELECT p.id, p.market_type, p.line_asked, p.model_side, p.outcome,"
        " p.resolved_utc, g.id AS game_id, g.home, g.away, g.status,"
        " g.home_score, g.away_score, g.live_period, g.live_clock,"
        " g.live_updated_utc"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ?",
        (sport, season, wk)).fetchall()

    picks, live_now = [], 0
    for r in rows:
        state = language.tile_state(
            r["status"], resolved=r["resolved_utc"] is not None,
            voided=r["id"] in voided)
        if state == "live":
            live_now += 1
        picks.append({
            "prediction_id": r["id"],
            "tile_state": state,
            "score_line": language.score_line(
                r["home"], r["home_score"], r["away"], r["away_score"]),
            "clock_line": language.clock_line(
                r["live_period"], r["live_clock"], state),
            "running_total": (
                language.running_total_line(
                    r["home_score"], r["away_score"], r["line_asked"],
                    language.tile_label({"market_type": r["market_type"],
                                         "model_side": r["model_side"]}))
                if r["market_type"] == "total" else None),
            "verdict": language.verdict_word(
                r["outcome"], voided=r["id"] in voided),
        })
    return {
        "sport": sport,
        "season": season,
        "week": wk,
        # WHAT THE BROWSER ACTS ON. Polling stops when this is false, which is
        # the client-side half of the same rule the poller follows: nothing on,
        # no requests.
        "any_live": live_now > 0,
        "live": live_now,
        "picks": picks,
    }


def available_weeks(conn: sqlite3.Connection, sport: str) -> list[dict]:
    calibration.require_sport(sport, "views.available_weeks")
    return [
        {"season": r["season"], "week": r["week"], "n": r["n"],
         # THE CHOOSER'S OWN WORDS. It was built in the browser as
         # `w.season + ' week ' + w.week`, which is both prose composed in the
         # renderer and the eight-digit key on the page.
         "label": language.slate_option(
             r["season"], r["week"], r["n"],
             config.SPORT_SLATE_WORD.get(sport, "week"))}
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
        " WHERE sport = ? AND status = 'scheduled' AND kickoff_utc IS NOT NULL"
        # FORWARD ONLY. Without this bound the "next scheduled game" was a
        # game from 2024 -- one college fixture that never got a final score
        # and so still reads as scheduled two years later. A record with any
        # history at all will have a few of those, and pointing a reader at
        # one as the NEXT game is worse than saying nothing.
        "   AND kickoff_utc > ?",
        (sport, db.utcnow()),
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


def login_glance(conn: sqlite3.Connection) -> dict:
    """What the login page may show: COUNTS AND RECORDS, and nothing else.

    THIS IS THE ONE PLACE THE RECORD FACES AN UNAUTHENTICATED READER, and the
    operator ruled it deliberately (GRIDIRON_13 P6): a sign-in screen that
    says "MLB 45-25 - 46 picks tonight" tells you the appliance is alive and
    working before you have typed anything, which is most of what you open it
    to find out.

    WHAT IT MAY NOT CARRY is everything that would make it worth reading to
    somebody who should not be reading it: no prediction, no side, no team
    with a line beside it, no probability. A count is not a tip.
    `audit.login_glance_faults` refuses all four, and a planting proves it.

    NEVER SUMMED (LAW 6). One clause per sport, no total anywhere.
    """
    out = []
    for sport in config.SPORTS:
        row = conn.execute(
            "SELECT COUNT(*) AS settled,"
            "       COALESCE(SUM(outcome), 0) AS won"
            "  FROM predictions WHERE sport = ? AND resolved_utc IS NOT NULL",
            (sport,)).fetchone()
        settled = row["settled"] or 0
        won = row["won"] or 0
        tonight = conn.execute(
            "SELECT COUNT(*) FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND p.resolved_utc IS NULL"
            "   AND g.status <> 'final'"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)",
            (sport,)).fetchone()[0]
        if not (settled or tonight):
            continue
        out.append({
            "sport": sport,
            "label": config.SPORT_LABELS.get(sport, sport.upper()),
            "settled": settled,
            "won": won,
            "lost": settled - won,
            "open": tonight,
            "n": settled,
            "line": language.login_glance_line(
                config.SPORT_LABELS.get(sport, sport.upper()),
                won, settled - won, tonight,
                config.SPORT_SLATE_WORD.get(sport, "week")),
        })
    payload = {"sports": out, "n": sum(s["settled"] for s in out),
               "never_summed": ("Each sport is its own record. They are never "
                                "added together.")}
    audit.check_the_login_page_shows_no_pick(payload)
    return payload


def settings_page(conn: sqlite3.Connection) -> dict:
    """Everything the Settings page shows, in the sections it shows it in.

    THE FENCE IS VISIBLE, not merely enforced. The model and law constants are
    listed beside the editable knobs, read-only, each with the date it was
    declared and the sentence saying that changing it is a ruling. Hiding them
    would make the page look complete while leaving a reader wondering where
    the props floor is; showing them without the fence would invite an edit
    the app must refuse.
    """
    from . import scheduler, settings as settings_mod, tasks

    values = settings_mod.current(conn)
    sections: dict[str, list] = {}
    for name, spec in settings_mod.EDITABLE.items():
        entry = {
            "name": name,
            "label": spec["label"],
            "why": spec["why"],
            "kind": spec["kind"],
            "value": values[name],
            "default": spec["default"],
        }
        if spec.get("task"):
            # WHAT THE OS ACTUALLY HOLDS, beside what the app has recorded.
            # These can disagree -- a change that did not take, a machine
            # where the tasks were never installed -- and the page says so
            # rather than showing the stored value twice.
            entry["task"] = spec["task"]
            entry["scheduler"] = scheduler.read_os(spec["task"])
            # WHEN THE TWO DISAGREE, SAY SO IN WORDS. This is not an edge
            # case: on the machine this was built on, the app had recorded
            # 09:00 for football while the scheduler held 11:00, and no
            # college football task was installed at all. A page that shows
            # only the stored value would have said 09:00 and been wrong,
            # confidently, forever.
            entry["disagreement"] = language.schedule_disagreement(
                spec["label"], entry["value"], entry["scheduler"])
        sections.setdefault(spec["section"], []).append(entry)

    return {
        "sections": [{"name": key, "settings": rows}
                     for key, rows in sections.items()],
        "fenced": settings_mod.fenced(),
        "fenced_note": settings_mod.FENCED_NOTE,
        "recent": settings_mod.history(conn),
        "n": len(settings_mod.EDITABLE),
        # HEALTH IS THE SCHEDULE PANEL, not a second implementation of it
        # (P3). Every cell comes from `task_runs`; no string on this page is
        # copied out of the mockup.
        "health": tasks.status(conn),
        "access": _access_panel(),
        "rulings": _rulings_in_force(),
    }


def change_setting(conn: sqlite3.Connection, *, name: str, raw: str) -> dict:
    """Record a change, and where it drives the OS, CONFIRM it there.

    A setting that moves a scheduled task is not done when the row is written.
    The row is what the app believes; the scheduler is what will actually
    happen, and only one of those wakes up at 11:05.
    """
    from . import scheduler, settings as settings_mod

    result = settings_mod.set_value(conn, name, raw)
    spec = settings_mod.EDITABLE[name]
    if spec.get("task") and result["changed"]:
        applied = scheduler.apply_time(spec["task"], result["value"])
        # THE CLAIM CANNOT LEAVE WITHOUT ITS EVIDENCE.
        audit.check_a_schedule_change_was_read_back(applied)
        result["scheduler"] = applied
        result["line"] = result["line"] + " " + applied["line"]
    result["recent"] = settings_mod.history(conn)
    return result


def _access_panel() -> dict:
    """The secrets, MASKED, and what may be done to them.

    NEITHER VALUE IS RETURNED. The token is the whole of the app's security
    and the ntfy topic is readable by anyone holding it; a page that shows
    either is a page that puts them in a screenshot.
    """
    from . import auth, config as cfg

    token = auth.read_token()
    topic = cfg.setting("GRIDIRON_NTFY_TOPIC")
    return {
        "token": {
            "label": "Access token",
            "state": ("set" if token else "not configured"),
            "masked": _mask(token),
            "how": "python tools/make_token.py",
            "why": ("Rotating it signs out every device. The token is never "
                    "shown, here or anywhere: it is compared server-side and "
                    "exchanged for a session."),
        },
        "topic": {
            "label": "Push topic",
            "state": ("set" if topic else "not configured"),
            "masked": _mask(topic),
            "how": "python tools/make_token.py --ntfy",
            "why": ("Anyone holding the topic can read the messages, which is "
                    "why they carry counts and team names and nothing else."),
        },
        "build": buildinfo.freshness(),
    }


def _mask(secret: str | None) -> str:
    """"KYOn...HZKE", or that there is nothing to mask.

    ENOUGH TO TELL TWO APART, not enough to use. Four characters at each end
    of a 43-character random string identifies which token is installed
    without meaningfully narrowing a guess at it.
    """
    if not secret:
        return "not set"
    if len(secret) <= 12:
        return "set"
    return f"{secret[:4]}...{secret[-4:]} ({len(secret)} characters)"


def _rulings_in_force() -> list[dict]:
    """The laws, shown where somebody might look for a switch.

    READ-ONLY AND SAID SO. This is the part of the settings page that exists
    to answer "can I turn this off" with "no, and here is why", rather than
    leaving a reader to search the codebase for a flag that does not exist.
    """
    return [
        {"name": "Blind first",
         "what": ("The probability is written before any market line is "
                  "fetched. Structural: the prediction row exists before the "
                  "line request is made.")},
        {"name": "Declared factors only",
         "what": ("Every factor is declared in advance with its rationale and "
                  "scored from the date it was added, never backfitted.")},
        {"name": "Append-only",
         "what": ("A prediction cannot be edited, deleted or re-scored. "
                  "Resolution writes an outcome and never rewrites a "
                  "probability.")},
        {"name": "No sample, no claim",
         "what": ("Nothing claims an edge below 100 resolved predictions in "
                  "that category, and every figure is shown with its N.")},
        {"name": "Not a betting tool",
         "what": ("No stake sizing, no bankroll, no bet recommendations. The "
                  "output is a probability, its reasoning and a track "
                  "record.")},
        {"name": "Never aggregate across sports",
         "what": ("Every curve, score, edge figure and sample size belongs to "
                  "exactly one sport. The functions that read the record take "
                  "the sport as a required argument.")},
    ]


def results_calendar(conn: sqlite3.Connection, *, sport: str,
                     days: int = 120) -> dict:
    """THE SEASON AS A SHAPE: one square per day, its balance inside.

    ONE SPORT, ALWAYS (LAW 6). A calendar mixing baseball and football would
    show a "day" that is two different slates from two different records, and
    the tint would average them. `require_sport` is the same tripwire every
    other reader of the record passes through.

    VOIDS ARE COUNTED AND ARE NEITHER. A void is a question that was never
    answered -- it is not a loss, and a day that voided four games and won
    three is not a 3-4 day. They are carried separately so the square can say
    so, and the balance that tints it never sees them.

    THE TINT IS THE DAY'S BALANCE AND NOTHING ELSE. Not the model's
    confidence that day, not how big the disagreements were, not a streak: a
    square that is green for any other reason is a square that says a day went
    well when it did not.
    """
    calibration.require_sport(sport, "views.results_calendar")
    rows = conn.execute(
        "SELECT g.league_date AS day,"
        "       SUM(CASE WHEN v.prediction_id IS NULL AND p.outcome = 1"
        "                THEN 1 ELSE 0 END) AS won,"
        "       SUM(CASE WHEN v.prediction_id IS NULL AND p.outcome = 0"
        "                THEN 1 ELSE 0 END) AS lost,"
        "       SUM(CASE WHEN v.prediction_id IS NOT NULL THEN 1 ELSE 0 END) AS void"
        "  FROM predictions p"
        "  JOIN games g ON g.id = p.game_id"
        "  LEFT JOIN prediction_voids v ON v.prediction_id = p.id"
        " WHERE p.sport = ?"
        "   AND (p.resolved_utc IS NOT NULL OR v.prediction_id IS NOT NULL)"
        "   AND g.league_date IS NOT NULL"
        " GROUP BY g.league_date"
        " ORDER BY g.league_date DESC"
        " LIMIT ?",
        (sport, days)).fetchall()

    out = []
    for r in rows:
        won, lost, void = r["won"] or 0, r["lost"] or 0, r["void"] or 0
        settled = won + lost
        out.append({
            "day": r["day"],
            "won": won,
            "lost": lost,
            "void": void,
            "settled": settled,
            "n": settled,
            "sport": sport,
            # THE BALANCE, and the only thing that may tint the square.
            "balance": ("up" if won > lost else
                        "down" if lost > won else "even"),
            "label": f"{won}-{lost}" if settled else "",
            "words": language.calendar_day_line(r["day"], won, lost, void),
        })
    out.reverse()
    payload = {
        "sport": sport,
        "days": out,
        "n": sum(d["settled"] for d in out),
        "void": sum(d["void"] for d in out),
        "note": language.calendar_note(),
    }
    # THE MERGE CANNOT REACH THE API, the same place every other guard runs.
    audit.check_the_calendar_says_what_it_shows(payload)
    return payload


def history(
    conn: sqlite3.Connection,
    *,
    sport: str,
    query: str = "",
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    outcome: str | None = None,
    day: str | None = None,
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
    if day:
        # THE CALENDAR'S OWN FILTER (GRIDIRON_13 P2). The LEAGUE date, not the
        # UTC one: a game starting at 02:00 UTC is the previous evening where
        # it is played, and a square that filtered on UTC would show a
        # different set of games than the one it counted.
        where.append("g.league_date = ?")
        params.append(day)
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
    # THE COUNT JOINS `games` TOO. It did not, and the day filter added in P2
    # names `g.league_date` -- so the rows query worked and the count threw
    # "no such column". The join is on a foreign key and is 1:1, so it cannot
    # change what is counted; the two queries now filter on the same columns,
    # which is the only way the total can be trusted to describe the rows.
    total = conn.execute(
        f"SELECT COUNT(*) FROM predictions p"
        f" JOIN games g ON g.id = p.game_id WHERE {clause}", params
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
    team_names = teams.names(conn, sport)

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
                # Recovered for reading where the column is empty; the
                # browser never queries with these. See _prose_prop_type.
                "prop_type": _prose_prop_type(r, sport),
                "market": _prose_prop_type(r, sport) or r["market_type"],
                "predictor": r["predictor"],
                "subject": r["subject"],
                "line_asked": r["line_asked"],
                "model_prob": r["model_prob"],
                "shown_prob": shown_prob(r),
                "correction_version": (r["correction_version"]
                                       if "correction_version" in r.keys()
                                       else None),
                "model_side": r["model_side"],
                # The side, in words, from the ONE humaniser. The renderer used
                # to build this and got spreads backwards on 34 cards.
                "chance_clause": language.chance_clause({
                    "subject": r["subject"], "market_type": r["market_type"],
                    "prop_type": _prose_prop_type(r, sport), "model_side": r["model_side"],
                    "line_asked": r["line_asked"],
                    "opponent": (r["away"] if r["subject"] == r["home"]
                                 else r["home"]),
                    "team_names": team_names,
                }),
                "market_line_at_the_time": snap.get("line"),
                "market_implied_prob": snap.get("implied_prob"),
                "outcome": r["outcome"],
                "resolved_utc": r["resolved_utc"],
                "voided": r["id"] in voided,
                "void_reason": voided.get(r["id"]),
                "degraded": r["degraded"],
                "factor_set_version": r["factor_set_version"],
                # THE TIER CHIP, on every history row (R3). The Record tab now
                # grades the tiers, so a reader looking at a settled pick should
                # be able to see which tier it was claimed at without opening it.
                # Derived from the same bucket the chip and the table use.
                "tier": calibration.tier_from_bucket(
                    calibration.bucket_record(
                        conn, r["model_prob"], sport=sport,
                        market_type=r["market_type"], prop_type=r["prop_type"],
                        predictor=r["predictor"],
                    )
                ),
        }
        # PLAIN WORDS, built once on the server. The same sentence appears on a
        # card, in this table and in the digest; three copies of the humanising
        # rules would drift into three vocabularies, which is how this table
        # came to have two columns both called "Market".
        item["phrase"] = language.phrase(item)
        item["result"] = language.result_word(item)
        item["sport"] = sport
        item["market_label"] = language.market_label(item)
        item["player"] = language.strip_market_suffix(item["subject"], item["market"])
        items.append(item)
    return {"n": total, "returned": len(items), "offset": offset, "items": items,
            # WHAT THIS LIST IS, in words, composed here like every other
            # visible string. The renderer used to glue " on " onto a date.
            "caption": language.results_caption(total, day)}


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
        "shown_prob": shown_prob(r),
        "correction_version": (r["correction_version"]
                               if "correction_version" in r.keys()
                               else None),
        "model_side": r["model_side"],
                # The side, in words, from the ONE humaniser. The renderer used
                # to build this and got spreads backwards on 34 cards.
        "chance_clause": language.chance_clause({
            "subject": r["subject"], "market_type": r["market_type"],
            "prop_type": _prose_prop_type(r, r["sport"]), "model_side": r["model_side"],
            "line_asked": r["line_asked"],
            "opponent": r["away"] if r["subject"] == r["home"] else r["home"],
            "team_names": teams.names(conn, r["sport"]),
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
    # THREE FORECASTERS, SIDE BY SIDE, NEVER ADDED (ruling R2). The selector
    # offers each its own table with its own gate; there is deliberately no
    # "all" option, because the only thing an "all" table could show is the
    # merge LAW 4 and LAW 6 both forbid -- and it would flatter, since the
    # operator only answers the questions they chose to answer.
    payload["forecasters"] = [
        {"forecaster": "statistical", "label": "statistical",
         "informed": False},
        {"forecaster": "llm", "label": "LLM", "informed": False},
    ]
    payload["meta"] = meta(conn, sport)
    payload["corrections"] = corrections_report(conn, sport)
    payload["drift"] = drift_report(conn, sport)
    # DATED READING WINDOWS (GRIDIRON_13 P1). A measurement that must not be
    # read early is a gate like any other, and until now the only place the
    # date existed was a sentence in a design document.
    payload["read_windows"] = [
        dict(window, key=key,
             progress=language.date_gate(window["declared"], window["opens"]))
        for key, window in config.READ_WINDOWS.items()
        if window.get("sport") == sport
    ]
    # ONE LIST OF GATES, NAMED HERE. The renderer used to build these names
    # by gluing a label onto a market field, which `check_js_composes_no_prose`
    # refuses: a sentence assembled in the browser is outside the plain-words
    # scan, outside the side resolver and outside the tests.
    payload["gates"] = (
        [{"name": language.gate_name("correction", c["label"]),
          "progress": c["progress"], "n": c["progress"]["n"]}
         for c in payload["corrections"]["categories"] if c.get("progress")]
        + [{"name": language.gate_name("drift", language.humanise(m["market_type"])),
            "progress": m["progress"], "n": m["progress"]["n"]}
           for m in payload["drift"]["markets"] if m.get("progress")]
        + [{"name": language.gate_name("read_window", w["label"]),
            "progress": w["progress"], "why": w["why"], "n": w["progress"]["n"]}
           for w in payload["read_windows"] if w.get("progress")]
    )
    calibration.assert_every_figure_has_n(payload)
    # EVERY GATE ON THIS PAGE COUNTS, and none of them renders a share (P1).
    audit.check_progress_is_counted(payload)
    calibration.assert_single_sport(payload, sport)
    return payload


def drift_report(conn: sqlite3.Connection, sport: str) -> dict:
    """Where the line went after we disagreed with it, per market.

    Reports the count for every market and a DIRECTION for none of them until
    a market has fifty pairs. The gate is in `drift`, not here; this only
    arranges what it returns.
    """
    from . import drift

    calibration.require_sport(sport, "views.drift_report")
    markets = sorted({
        r["market_type"]
        for r in conn.execute(
            "SELECT DISTINCT market_type FROM predictions WHERE sport = ?",
            (sport,))
    })
    per_market = [
        drift.report(conn, sport=sport, market_type=m) for m in markets
    ]
    return {
        "sport": sport,
        "n": sum(m["n"] for m in per_market),
        "min_pairs": drift.MIN_PAIRS,
        "markets": per_market,
        "question": (
            "When the model disagrees with the published line, does the line "
            "later move toward it or away? Two looks at the same line answer "
            "that; one cannot."
        ),
    }


def corrections_report(conn: sqlite3.Connection, sport: str) -> dict:
    """Every correction category for one sport, and how each version has done.

    THREE FIGURES PER VERSION, KEPT APART because they answer different
    questions and only one of them is evidence:

      * in-sample -- measured on the rows the fit was made from. It says the
        fit converged. A fit always improves the rows it was fitted on.
      * holdout -- the latest fifth, which the fit did not see. Thin, and
        labelled thin.
      * forward -- predictions actually WRITTEN under that version. The only
        one that answers "did it help", and empty until a version has been
        active long enough to have a record.

    A category with no correction at all still appears, with the shortfall in
    words, because "no correction" and "not enough record yet" are different
    states and the panel must not show them alike.
    """
    from . import correction

    calibration.require_sport(sport, "views.corrections_report")
    out = []
    for market_type, forecaster in sorted({
        (r["market_type"], r["predictor"])
        for r in conn.execute(
            "SELECT DISTINCT market_type, predictor FROM predictions"
            " WHERE sport = ?", (sport,))
    }):
        versions = correction.version_report(
            conn, sport=sport, market_type=market_type, forecaster=forecaster)
        latest = versions[-1] if versions else None
        # HOW CLOSE THIS CATEGORY IS to its first correction (P1). The same
        # component the tier rows use: counts, an N, and no percentage.
        settled = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE sport = ?"
            "   AND market_type = ? AND predictor = ?"
            "   AND resolved_utc IS NOT NULL",
            (sport, market_type, forecaster)).fetchone()[0]
        out.append({
            "market_type": market_type,
            "forecaster": forecaster,
            # THE FORECASTER'S OWN LABEL, not the stored key. This read
            # "moneyline, llm" on the page -- a lowercase identifier where a
            # name belongs, and the Record tab two panels above it says "LLM".
            "label": (f"{language.humanise(market_type)}, "
                      f"{config.FORECASTER_LABELS.get(forecaster, forecaster)}"),
            "active": bool(latest and latest["active_from"]),
            "status": (latest["status"] if latest else
                       f"corrections begin at {correction.MIN_TRAIN} settled "
                       "- nothing settled yet"),
            "versions": versions,
            "n": len(versions),
            "settled": settled,
            "progress": language.progress(
                settled, correction.MIN_TRAIN,
                cleared_note="fitted - applied only where it beat the rows it "
                             "was not fitted on"),
        })
    return {
        "sport": sport,
        "n": len(out),
        "min_train": correction.MIN_TRAIN,
        "categories": out,
        "any_active": any(c["active"] for c in out),
        # Said by the humaniser, in the same voice as every other gate line.
        "note": language.corrections_note(
            any(c["active"] for c in out), correction.MIN_TRAIN),
    }


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
        # THE PLAIN-WORDS NAME leads the row; the code goes underneath, small.
        # This is the one page allowed to be dense, and it is still read by a
        # person: the same phrase the pick cards use is what a factor is called.
        entry["plain_name"] = _why_phrases().get(entry["factor"])
        # "helps a little · 412 picks" -- the earned figure in words, with its
        # sample beside it. A verdict with no N is a claim (LAW 4).
        entry["earned_words"] = _factor_earned_words(entry)
        # ONE LINE FOR THE CARD (GRIDIRON_13 P5). The full declaration is a
        # LAW 2 dated record and stays in the table below; a card answers
        # "what is this" at a glance.
        entry["what"] = language.factor_what(
            entry.get("rationale"), _why_phrases())
    calibration.assert_every_figure_has_n(report)
    return report


#: How a factor's measured effect reads in words. Bands rather than a number,
#: because "mean |effect| 0.0412" is not a thing anybody can act on.
FACTOR_EFFECT_BANDS = (
    (0.30, "moves the answer a lot"),
    (0.10, "moves the answer a fair amount"),
    (0.02, "moves the answer a little"),
    (0.00, "barely moves the answer"),
)


def _factor_earned_words(entry: dict) -> str:
    """The factor's effect and its sample, in words.

    Below the gate it says so instead of grading, for the same reason a tier
    row does: an effect measured on nine resolutions is not a measurement.
    """
    n = entry.get("n") or 0
    effect = entry.get("mean_abs_contribution")
    if effect is None:
        return f"nothing resolved yet · {n} picks" if not n else f"not measured · {n} picks"
    words = FACTOR_EFFECT_BANDS[-1][1]
    for floor, said in FACTOR_EFFECT_BANDS:
        if effect >= floor:
            words = said
            break
    return f"{words} · {n} picks"


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
    # CFB's schedule is fetched per TEAM -- the union of 136 schedules is the
    # slate -- so the freshest of those requests is what "the schedule was last
    # read" means for this sport.
    "cfb": "%college-football%teams%events%",
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
        pattern = SCHEDULE_URL_PATTERNS.get(sport)
        if pattern is None:
            # A sport with no declared schedule URL is REPORTED, not skipped
            # and not crashed on: the panel's job is to say what it does not
            # know, and a KeyError here took down every page that shows it.
            out.append({
                "sport": sport,
                "label": config.SPORT_LABELS.get(sport, sport.upper()),
                "fetched_utc": None,
                "age_hours": None,
                "stale": None,
                "line": "no schedule source is declared for this sport",
            })
            continue
        newest = sources.newest_fetch(conn, pattern)
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
        # SHORT ENOUGH FOR THE SLOT IT HAS. The strip needed 264px in a 213px
        # slot at EVERY width, so it was clipped on a 1280px laptop too, and
        # the `flex: none` hiding that clipping pushed the whole PAGE 35-56px
        # wide instead.
        #
        # "this season" was the part to cut, not the sport. Dropping the label
        # first was wrong and a test caught it: with no label, two sports that
        # have both settled nothing render the same strip, so switching sports
        # showed no change at all. The season is said in full in the tooltip.
        "line": (
            f"{config.SPORT_LABELS.get(sport, sport.upper())} {wins}-{n - wins}"
            if n else
            # "0 settled", which is the brief's own wording for a sport with
            # no record yet, and it has to be this short: a fourth sport tab
            # took the header's spare width, and "NCAAF nothing settled yet"
            # needs 166px in a 139px slot. Measured, not guessed.
            f"{config.SPORT_LABELS.get(sport, sport.upper())} 0 settled"
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
        " p.line_asked, p.factors_json,"
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

    # The digest's rows were the last place the renderer still built a sentence
    # out of a raw field: `'picked ' + String(s.subject).toUpperCase()`. That is
    # the wrong-side defect a FIFTH time -- and in JavaScript, where the Python
    # scan that catches the other four cannot see it. Every phrase below is
    # composed here, by the same functions the pick cards use.
    team_names = teams.names(conn, sport)
    phrases = _why_phrases()

    settled = []
    for r in rows:
        payload = json.loads(r["factors_json"] or "{}")
        item = {
            "subject": r["subject"],
            "market_type": r["market_type"],
            "prop_type": _prose_prop_type(r, sport),
            "model_side": r["model_side"],
            "line_asked": r["line_asked"],
            "opponent": (r["away"] if r["subject"] == r["home"] else r["home"]),
            "model_prob": r["model_prob"],
            "market_implied_prob": r["implied_prob"],
            "team_names": team_names,
            "contributions": payload.get("contributions") or [],
            "absent_factors": _absent_factors(payload),
        }
        settled.append({
            "prediction_id": r["id"],
            "matchup": f"{r['away']} @ {r['home']}",
            "subject": r["subject"],
            # What the pick WAS, in words, with the flip applied.
            "phrase": language.phrase(item),
            # The same three-sentence reason the expanded pick rows carry, so a
            # resolved row in the digest explains itself without being opened.
            "why": language.why_block(item, phrases),
            "model_prob": r["model_prob"],
            "market_prob": r["implied_prob"],
            "outcome": r["outcome"],
            "correct": bool(r["outcome"]),
            "final_score": (
                f"{r['away']} {r['away_score']} - {r['home_score']} {r['home']}"
                if r["home_score"] is not None else None
            ),
            "market": _prose_prop_type(r, sport) or r["market_type"],
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
        # THE OPERATOR'S OWN, on their own line and never folded into the
        # counts above: "7 resolved, 4 correct" is about the model.
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


def _prose_prop_type(r, sport: str) -> str | None:
    """The stat a prop asked about, for READING. Never for querying.

    Thirty-two NFL prop rows predate the column and carry NULL (see
    `subjects.stat_suffix`), so every label built from `prop_type` fell back to
    the raw subject and the Picks page read "Sam Darnold passing_yards over
    165.5".

    FOR READING ONLY, and the distinction is not pedantic. The same rows are
    passed to `calibration` as query arguments, where `prop_type` selects which
    record a bucket and a tier are counted from. Filling it in there would ask
    for a category these rows are not stored under, and the lookup would come
    back empty -- a wrong chip instead of a raw one. So the recovered value
    goes into the prose item and nowhere near a query.
    """
    if r["market_type"] != "prop":
        return r["prop_type"]
    return r["prop_type"] or subjects.stat_suffix(
        r["subject"], config.SPORT_MARKETS.get(sport, ()))


def _correction_sample(conn: sqlite3.Connection, r) -> int | None:
    """How many settled rows the correction on this row was fitted from.

    Read from the stored version rather than recomputed, so the sentence a card
    shows cannot drift from the fit that actually produced its number.
    """
    version = r["correction_version"] if "correction_version" in r.keys() else None
    if version is None:
        return None
    row = conn.execute(
        "SELECT n_train FROM calibration_corrections"
        " WHERE sport = ? AND market_type = ? AND forecaster = ? AND version = ?",
        (r["sport"], r["market_type"], r["predictor"], version),
    ).fetchone()
    return int(row["n_train"]) if row else None


def shown_prob(r) -> float:
    """The number the reader saw, from a prediction row.

    `calibrated_prob` is written at prediction time when the category had an
    active correction, and is NULL otherwise. Everything a reader compares --
    the tier chip, the percentage on the card, the sort order, the gap against
    the market -- must agree about which number it is using, or a STRONG chip
    ends up on a card whose percentage says LEAN and neither figure is wrong.

    The RAW claim stays available beside it; this is not a replacement, it is
    the answer to "what was shown".
    """
    calibrated = r["calibrated_prob"] if "calibrated_prob" in r.keys() else None
    return calibrated if calibrated is not None else r["model_prob"]


def _row_title(r) -> str:
    """The row's heading: a matchup, or a subject and what is being asked.

    "SD @ TB" for a game market; "TATIS JR. - HITS" for a prop, because on a
    prop the subject IS the headline and the fixture is a detail that belongs
    on the pick line underneath.
    """
    if r["market_type"] != "prop":
        return f"{r['away']} @ {r['home']}"
    stat = _prose_prop_type(r, r["sport"])
    name = language.strip_market_suffix(r["subject"], stat)
    surname = name.split()[-1] if name else name
    # "Fernando Tatis Jr." -> "Tatis Jr."; a row is not the place for a full
    # name, and the expanded view carries it.
    parts = (name or "").split()
    if len(parts) > 2 and parts[-1].rstrip(".").lower() in ("jr", "sr", "ii", "iii"):
        surname = " ".join(parts[-2:])
    return f"{surname} · {language.humanise(stat)}"


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


def _resolved_story(r, gap, team_names: dict | None = None) -> str | None:
    """One line telling what happened, for the resolved section.

    THE FOURTH INSTANCE of the wrong-side defect, and the one that showed the
    class fix had been scoped too narrowly. `side_named` was introduced as the
    one door after the same inversion shipped three times, and its guard scans
    `language.py` -- on the premise that all prose lives in the humaniser. This
    line is prose and lives here, so the guard never looked at it, and it read
    "picked ATL" over nine resolved rows whose pick was on Colorado.

    A guard that checks the place the rule was written, rather than every place
    the rule applies, measures the author's memory.
    """
    if r["resolved_utc"] is None or r["status"] != "final":
        return None
    picked, _prob = language.side_named({
        "subject": r["subject"],
        "market_type": r["market_type"],
        "prop_type": r["prop_type"],
        "model_side": r["model_side"],
        "opponent": (r["away"] if r["subject"] == r["home"] else r["home"]),
        "team_names": team_names or {},
    })
    story = f"picked {picked}"
    if r["home_score"] is not None and r["away_score"] is not None:
        winner = r["home"] if r["home_score"] > r["away_score"] else r["away"]
        story += (f" · {winner} won {max(r['home_score'], r['away_score'])}"
                  f"-{min(r['home_score'], r['away_score'])}")
    if gap is not None:
        # ROUND BEFORE SIGNING. `{-0.004:+.0f}` is "-0", and a signed zero on a
        # resolved row reads as a rendering fault rather than as a gap too
        # small to show. Four rows said "gap was -0" and one said "gap was +0".
        points = round(gap * 100)
        story += f" · gap was {points:+.0f}" if points else " · gap was nil"
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
