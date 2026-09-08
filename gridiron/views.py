"""View models for the interface. Assembly only — no computation of new claims.

Everything here reads the record and shapes it for display. It never writes and
never derives a probability, so the numbers a person sees on the page are the
numbers that were written when the prediction was made.
"""

from __future__ import annotations

import json
import sqlite3
import statistics

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
        "unreachable_line": language.unreachable_line(),
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

        # AND THE FORMS THE MODEL ACTUALLY WROTE (2026-09-05). Asked about
        # `ufc_scheduled_rounds` it wrote "(scheduled_rounds = 0)", so the map
        # carries the prefix-stripped alias too -- derived, and only where it
        # is unambiguous. See `language.with_prefix_aliases`.
        _WHY_CACHE = language.with_prefix_aliases(
            {f.name: f.why for f in registry.all_factors() if f.why},
            config.SPORTS)
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


def _market_tabs(sport: str, cards: list) -> list[dict]:
    """One tab per DECLARED market, with the count on this slate (R4).

    NEVER A HARDCODED ROW. The tabs are `config.SPORT_MARKETS[sport]` in its
    declared order, so a fifth market appears the day it is declared and no
    file under `web/` changes. The renderer places what this returns and
    chooses nothing.

    ZERO-COUNT TABS STAY. "No strikeout questions on this card" is a fact
    about the slate, and a tab that disappears when the count reaches zero
    hides exactly the fact a reader would want. The count is beside the label
    for the same reason every other number in this project is: unlabelled, it
    would be a badge.

    THE LABELS ARE PLAIN WORDS. `prop:pitcher_strikeouts` is a storage key;
    "Strikeouts" is what a person says. `language.market_word` already knows
    that a handicap is a point spread in football and a run line in baseball.
    """
    counts: dict[str, int] = {}
    for card in cards:
        key = card.get("prop_type") or card.get("market_type") or ""
        counts[key] = counts.get(key, 0) + 1

    tabs = [{"market": "", "label": "All", "n": len(cards)}]
    # THE ACTIVE ROSTER (R1, 2026-09-05): a retired market is not a tab on
    # Picks. It keeps its category on Record, greyed, with its settled count.
    for market in config.active_markets(sport):
        tabs.append({
            "market": market,
            # SENTENCE CASE, not the storage form's lowercase. "Run line"
            # is what a person writes on a tab; `market_label` returns the
            # phrase and this capitalises only its first letter, so "total
            # bases" does not become the shouty "Total Bases".
            "label": language.sentence_case(
                language.market_label({"sport": sport, "market": market})),
            "n": counts.get(market, 0),
        })
    return tabs


def _yesterday(conn: sqlite3.Connection, sport: str) -> dict | None:
    """What settled yesterday, this sport's season record, and the next verdict.

    ONE SPORT, NEVER A TOTAL (LAW 6). Every figure here is filtered on `sport`
    and the strip is rendered per sport, so there is no number on it that
    describes two.

    RETURNS None WHEN NOTHING HAS SETTLED, rather than a row of zeroes. "0
    right, 0 wrong" reads as a bad day; the truth is that there was no day.
    """
    # THE LEAGUE DAY OF THE GAMES, NOT THE UTC DATE OF THE RESOLVER'S RUN
    # (UI audit finding 7, 2026-09-05). Grouping on `substr(resolved_utc, 1,
    # 10)` put every game that finished after 5 pm Pacific on tomorrow's
    # date, split one evening's results across two labels, and showed only
    # the later fragment: "6 September: 10 right, 9 wrong" at 10 pm on the
    # 5th. `games.league_date` is the day the league itself calls the game's
    # (the convention ruled on 2026-09-05), and it is the day a reader means.
    # A game with no league day recorded falls back to the resolver's UTC
    # date, so the strip never goes blank on an older row.
    day = conn.execute(
        "SELECT MAX(COALESCE(g.league_date, substr(p.resolved_utc, 1, 10))) AS d"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL", (sport,)).fetchone()
    if day is None or not day["d"]:
        return None
    latest = day["d"]

    row = conn.execute(
        "SELECT COUNT(*) AS n,"
        "       SUM(CASE WHEN p.outcome = 1 THEN 1 ELSE 0 END) AS right_n"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL"
        "   AND COALESCE(g.league_date, substr(p.resolved_utc, 1, 10)) = ?"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)",
        (sport, latest)).fetchone()
    settled = row["n"] or 0
    if not settled:
        return None
    right = row["right_n"] or 0

    season = conn.execute(
        "SELECT COUNT(*) AS n,"
        "       SUM(CASE WHEN p.outcome = 1 THEN 1 ELSE 0 END) AS right_n"
        "  FROM predictions p"
        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)",
        (sport,)).fetchone()

    return {
        # THE DAY IN WORDS, composed here like every other visible string. The
        # renderer would otherwise have to decide whether the latest settled
        # day counts as "yesterday", which is a claim about a calendar and not
        # a thing a renderer knows.
        "label": language.settled_day_label(latest),
        "right": right,
        "wrong": settled - right,
        "season": language.sport_record_line(
            config.SPORT_LABELS.get(sport, sport),
            season["right_n"] or 0,
            (season["n"] or 0) - (season["right_n"] or 0),
            season["n"] or 0),
        "next_verdict": None,
    }


def week(conn: sqlite3.Connection, sport: str, season: int | None = None,
         wk: int | None = None, forecaster: str | None = None,
         early_view: bool = False) -> dict:
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
            " g.away_score,"
            # WHICH KIND OF CARD A FIGHT IS ON (E3, 2026-09-03). Read here
            # rather than looked up per row, and NULL for every sport that
            # does not split -- the join is a left one for that reason.
            " (SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
            "    ON e.id = b.event_id WHERE b.id = p.game_id) AS event_tier"
            " FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND g.season = ? AND g.week = ?"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)"
            # ONE ROW PER QUESTION ON THE PICKS LIST (2026-09-03).
            #
            # The final pass writes a second forecast of every question, so
            # without this every game would appear TWICE -- which is precisely
            # the duplicate-slate defect of 2026-08-29 that took three days to
            # notice, arriving by a different road. The early row is not
            # hidden: `early_view=True` asks for it instead, and it is
            # labelled when shown.
            #
            # The rule matches calibration's: the standing forecast is the
            # latest row before start. Picks and the record must never
            # disagree about which forecast is the live one.
            + ("   AND p.pass_kind = 'early'" if early_view else
               "   AND NOT EXISTS (SELECT 1 FROM predictions later"
               "                   WHERE later.game_id = p.game_id"
               "                     AND later.market_type = p.market_type"
               "                     AND later.subject = p.subject"
               "                     AND later.predictor = p.predictor"
               "                     AND later.factor_set_version"
               "                         = p.factor_set_version"
               "                     AND IFNULL(later.line_asked, -1e9)"
               "                         = IFNULL(p.line_asked, -1e9)"
               "                     AND later.created_utc > p.created_utc"
               "                     AND later.created_utc <= g.kickoff_utc)")
            + " ORDER BY p.id",
            (sport, s, w),
        ).fetchall()

    rows = fetch(season, wk)
    # NOT `superseded` -- that name is already a COUNT further down this
    # function (line ~371), and shadowing it would have made a set of ids
    # and an integer take turns under one name.
    replaced_ids = _superseded_ids(conn, sport)
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
                    "early_view": early_view,
                    "has_early_view": False,
                    "hero_min_claim": config.HERO_MIN_CLAIM,
                    "no_lead": language.no_lead_line(config.HERO_MIN_CLAIM),
                    "default_tier": config.PICKS_DEFAULT_TIER,
                    "tier_caveat": _least_tested_line(conn, sport),
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
    # THE DEFAULT IS THE OPERATOR'S, FROM SETTINGS (ruling 2026-09-08). Picks
    # carries no control for this: a switch on the card face lets a reader
    # pick whichever forecaster flatters each pick, and `picks_taken` would
    # then record that choosing rather than one forecaster's work.
    from . import settings as _settings

    chosen = forecaster or _settings.value(conn, "default_forecaster") \
        or config.PICKS_DEFAULT_FORECASTER
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
    # WHAT THE SLATE IS HIDING, COUNTED AGAINST THE RECORD (2026-09-04).
    #
    # `len(rows) - len(standing)` was the difference between two DIFFERENT
    # definitions of "the same question" and reported only the second of them.
    # The fetch above already drops a row that a later row of the SAME FACTOR
    # SET replaced -- that is the door `_superseded_ids` and calibration both
    # use -- and the dedup here drops what is left over a BROADER key, which
    # is what catches the 2026-08-29 double run across factor set versions.
    # Both kinds of hiding are real; only the second was ever counted.
    #
    # IT UNDER-REPORTED BY 16 ON THE LIVE NFL SLATE: 45 rows hidden, 29
    # reported. This is the figure the close-out calls "how the operator finds
    # out a prediction task ran twice", so a count that is quietly short is
    # the one thing it must not be.
    #
    # COUNTED, NOT SUBTRACTED. One query over the slate, minus what the page
    # actually shows. A second definition cannot drift from it because there
    # is no second definition left.
    on_slate = conn.execute(
        "SELECT COUNT(*) FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ? AND p.predictor = ?"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id = p.id)",
        (sport, season, wk, chosen),
    ).fetchone()[0]
    superseded = max(0, on_slate - len(standing))
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
    # THE VENUE'S LINE FOR THIS SLATE (E4, 2026-09-06), one lookup as well.
    at_line = _at_the_line(conn, sport, ids, team_names)
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
                # FULL NAMES AND "at" (cards UI, 2026-09-04). This is the tail
                # of a prop card's pick line -- "Josh Allen over 245.5 passing
                # yards · Packers at Bills" -- so it is prose, and "GB @ BUF"
                # in the middle of a sentence is two tricodes and a symbol
                # nobody says aloud.
                "matchup": (
                    f"{language.team_name(r['away'], team_names, 'club')} at "
                    f"{language.team_name(r['home'], team_names, 'club')}"),
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
                # WHICH PASS WROTE THIS ROW (2026-09-03). The card carries
                # the fact and the sentence; the browser never composes
                # either. `pass_kind` is an internal word and never
                # reaches the page -- `pass_note` is what a reader sees.
                # WHAT IT KNEW (S2, 2026-09-03). Every row already
                # records which factors it could measure; none of it
                # reached a reader, so a forecast made without the
                # starter looked identical to one made with him.
                # THE NUMBERS THE SENTENCE ABOVE CLAIMS, carried beside it so
                # a scan can check the two agree rather than trusting the
                # composer. `audit.coverage_line_faults` reads exactly this.
                "factor_counts": {
                    "present": len(payload.get("present") or []),
                    "total": (len(payload.get("present") or [])
                              + len(payload.get("absent") or [])),
                },
                # THE RATE, FOR A COUNT MARKET (C3). "The model expects
                # about 0.9 home runs; clearing 0.5 is about 60%." A
                # logistic has no rate and gets an empty string.
                "rate_line": language.rate_line(
                    payload.get("expected_count"), r["line_asked"],
                    r["model_prob"], _prose_prop_type(r, sport)),
                "what_it_knew": language.what_it_knew(
                    len(payload.get("present") or []),
                    [_why_phrases().get(name) or language.humanise(name)
                     for name in (payload.get("absent") or [])],
                    _hours_before(r["created_utc"], r["kickoff_utc"])),
                "is_early_view": ((r["pass_kind"] or "early") == "early"
                                  and r["id"] in replaced_ids),
                "pass_note": (
                    language.early_view_note(
                        r["created_utc"], r["kickoff_utc"],
                        superseded=r["id"] in replaced_ids)
                    if (r["pass_kind"] or "early") == "early" else None
                ),
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
                # WHAT THIS MARKET'S METHOD IS KNOWN TO BE (operator ruling
                # 2, 2026-09-04). Absent on every card whose method carries no
                # finding, which is all of them but the totals.
                #
                # ONE FIELD, NOT TWO. The browser's rule is "a card with a
                # method note is never the hero" -- read off the words
                # themselves rather than off a second boolean that could come
                # to disagree with them. Two switches for one state is how a
                # card comes to be flagged according to one and eligible
                # according to the other, which this file has already fixed
                # once for the open/shut state.
                "method_note": language.method_note(
                    config.flagged_method(sport, r["market_type"])),
                "market_line": snap.get("line"),
                # THE VENUE'S OWN LINE, AND THE MODEL READ AT IT (E4). Absent
                # on a pick with no claim -- no frozen distribution, no ladder
                # or no price -- and absent means absent: the card shows
                # nothing rather than an empty comparison.
                "at_the_line": at_line.get(r["id"]),
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
                    # A JOINTLY-FITTED PAIR READS AS ONE REASON (D1). Two
                    # factors the model uses as a difference are not two
                    # reasons that disagree.
                    config.jointly_read(sport, r["market_type"]),
                ),
                "absent_factors": _absent_factors(payload),
                "factor_coverage": payload.get("coverage"),
                "notes": payload.get("notes") or [],
                # THROUGH THE ONE DOOR (2026-09-05). Stored reasoning is
                # never edited -- LAW 3 -- so a row written while the prompt
                # still used code names keeps `mlb_bullpen_recent_load` for
                # ever, and the READER is shown the plain phrase instead.
                "reasoning": language.humanise_reasoning(
                    r["reasoning"], _why_phrases()),
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
                # THE MODEL'S WORST BAND, BESIDE THIS PICK'S BAND (S3). The
                # record page has always led with the largest gap -- "the
                # sentence at the top of the track record is always the worst
                # thing the record says" -- and a reader looking at one pick
                # never saw it. One sport, never pooled (LAW 6).
                "worst_band": _worst_band(conn, sport),
                "market_fetched_utc": snap.get("fetched_utc"),
                "factor_set_version": r["factor_set_version"],
                # --- the compact row (K2) -------------------------------------
                # Built here, not in the renderer. The row shows five things and
                # every one of them is a phrase the server wrote.
                "row_title": _row_title(r, team_names),
                # THE TIER, IN WORDS, BESIDE THE TIME (E3). "Contender Series"
                # rather than 'contender': a reader is told which kind of card
                # this is, because a Contender Series bout goes the distance
                # 43.6% of the time against 58.0% on a numbered card and the
                # record is kept separately for exactly that reason. Empty for
                # every sport that does not split, and for a card whose tier
                # the source did not carry.
                "tier_label": language.tier_label(
                    r["event_tier"] if "event_tier" in r.keys() else None),
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
        # WHICH PICK THE WORKED EXAMPLE IS WORKING (2026-09-07). Composed here
        # because it is composed FROM the phrase, and composed at all because
        # the renderer was gluing it together out of a dash, a subject and a
        # percentage -- the shape the prose ruling exists to prevent.
        cards[-1]["example_caption"] = language.worked_example_caption(
            cards[-1]["phrase"], cards[-1].get("shown_prob"))
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
            cards[-1].get("gap"),
            venue_line=bool(cards[-1].get("at_the_line")))
        # WHERE IT IS PLAYED, for the selected-pick subline. None when the
        # venue was never recorded, and the subline simply has one fewer part.
        cards[-1]["venue"] = venues.get(r["home"])
        cards[-1]["side_word"] = language.side_word_or_side(r["model_side"])

    # Sorted by disagreement size, because that is where anything interesting
    # lives. Cards with no market comparison sort last rather than first.
    cards.sort(key=_card_order, reverse=True)

    # WHICH QUESTIONS LEAD THIS SLATE (THE_SHORTLIST S2, 2026-09-07).
    #
    # NOTHING IS REMOVED. Every card stays in `cards`, each marked with whether
    # it is on the shortlist and with the sentence that says what put it there;
    # the page shows the shortlist first and the count of the rest sits on the
    # face of the control that reveals them. A slate whose rows were written
    # before the ranker existed has no ranks, says so, and shows everything --
    # which is what this page did before any of this.
    # THE SECOND FORECASTER'S NUMBER, beside the first and never instead of it
    # (THE_PRICED P1, 2026-09-07).
    _attach_priced(conn, cards)

    shortlist_block = _shortlist_block(conn, sport, cards)
    # WHAT IS WORTH TAKING (R4, 2026-09-07), computed from the shortlist that
    # was just marked. Empty on most days by design.
    recommendations_block = _recommendations_block(conn, cards)
    # TODAY (T1, 2026-09-07): the two groups the operator reads first. Built
    # from the same priced entries the block above counts, so the page cannot
    # disagree with itself about what cleared the fee.
    from .market import recommend as _recommend

    today_block = _today_block(
        conn, cards,
        _recommend.for_predictions(
            conn, [c["prediction_id"] for c in cards if c.get("on_shortlist")]),
        # THE COUNT IS OF ONE FORECASTER'S QUESTIONS, and the strip says which.
        forecaster=chosen)

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
        "shortlist": shortlist_block,
        "recommendations": recommendations_block,
        "today": today_block,
        # WHOSE PICKS THESE ARE, and who else has some. Named on the payload
        # rather than inferred by the renderer from the cards: a list that
        # cannot say who made it is a list nobody can check.
        # PICKS OPENS ON STRONG (ruling R2, 2026-09-02), which puts the most
        # confident claims first -- and the tier with the fewest settled rows
        # behind them. The caveat says so, and disappears once the band earns
        # its verdict.
        # THE EARLY VIEW IS A SEPARATE LIST, NEVER A MIXED ONE (A3). Two
        # forecasts of one game ranked against each other would put the
        # same matchup twice in one ordering, naming a side twice -- the
        # shape the one-forecaster-per-list rule already forbids for the
        # LLM.
        "early_view": early_view,
        # AN EMPTY SLATE SAYS WHY EVEN WHEN THE WEEK WAS PINNED (finding 13):
        # the picker pins a week, and the season-start sentence used to come
        # only on the default request.
        "message": None if rows else _empty_slate_message(conn, sport),
        "has_early_view": bool(replaced_ids),
        "default_tier": config.PICKS_DEFAULT_TIER,
        "tier_caveat": _least_tested_line(conn, sport),
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
        # A QUIET MARKET IS A FACT ABOUT A SLATE THAT ASKED QUESTIONS. On a
        # slate that asked none, "0 asked -- model never reached 70%" is a
        # reason that is not true (finding 13).
        "quiet_markets": _quiet_markets(conn, sport, season, wk) if (wk and rows) else [],
        # THE MARKET TABS (R4), from the sport's DECLARED list and never a
        # hardcoded row: a fifth market appears the day it is declared.
        "market_tabs": _market_tabs(sport, cards),
        # THE HEADING AND ITS SUB-LINE, in words (cards UI). "Tonight" only
        # when it is tonight; the slate's day otherwise. A key like
        # "Day 159, 2026" in a heading is the database talking to itself, and
        # this project has fixed that twice already.
        "headline": None,     # filled in below, once slate_title is composed
        # WHAT SETTLED LAST, this sport only. LAW 6 all the way down: there is
        # no figure on this strip that describes two sports.
        "yesterday": _yesterday(conn, sport),
        "sorted_by": (
            "size of disagreement with the market; no comparison sorts last"
            if lines.line_source_for(sport)["available"]
            else "prediction id; this sport has no line source, so there is no "
                 "disagreement to sort by"
        ),
    }
    # THE HEADING AND ITS SUB-LINE (cards UI, 2026-09-04). Composed after the
    # payload so both can read what it already worked out -- the slate's title
    # in words, its glance, and how many picks the tier filter is holding back.
    #
    # "TONIGHT" ONLY WHEN IT IS TONIGHT. A slate five days out is not tonight,
    # and a heading that says so is wrong in the largest type on the page.
    _glance_now = payload.get("glance") or {}
    payload["headline"] = language.slate_headline(
        payload.get("slate_title"), _glance_now.get("state"),
        _glance_now.get("first_kickoff_utc"))
    # THE HERO'S TAG AGREES WITH THE HEADING about what today is, rather than
    # deciding again and disagreeing. Both sorts' wording is composed here; the
    # browser picks one, as it does with the count lines.
    payload["hero_tags"] = language.hero_tags(payload["headline"])
    payload["hero_min_claim"] = config.HERO_MIN_CLAIM
    payload["no_lead"] = language.no_lead_line(config.HERO_MIN_CLAIM)
    # NO SECOND SUB-LINE. The brief asks for "13 strong picks · first pitch in
    # 2h 14m · 15 more didn't clear the bar", and every one of those three
    # facts is ALREADY composed and already on the page: `glance.count_lines`
    # carries the tier-aware count ("STRONG - 24 of 78 picks"), the ticking
    # clock carries the countdown, and `below_floor` carries the shortfall.
    #
    # A `slate_subline` was written here and then deleted rather than shipped.
    # It would have been a second sentence saying what the first already says,
    # and worse: the server cannot know which tier the reader is filtered to,
    # so its count would have been the WRONG one whenever the filter was on.
    # Two claims about one thing, one of them wrong, is not more information.

    # THE MERGE CANNOT REACH THE API, which is the same place the curve check
    # runs for the same reason: a guard that only runs in a test protects the
    # test. This one fired on the real slate the day it was written.
    audit.check_one_forecaster_per_list(payload)
    # AND THE FLAG CANNOT DRIFT FROM THE CODE THAT EARNS IT (operator ruling
    # 2). Cheap -- a walk over five sports' declared markets -- and it runs
    # here for the same reason the merge check does: a market that started
    # choosing its own rung and was never flagged would otherwise be found by
    # nobody until a reader took a coin flip at face value.
    audit.check_flagged_methods()
    return payload


def _least_tested_line(conn: sqlite3.Connection, sport: str) -> str | None:
    """How much has actually settled in the tier Picks opens on.

    Counted from the record rather than from the slate: a reader wants to know
    what stands behind the band, not how many picks are in it tonight.
    """
    tier = config.PICKS_DEFAULT_TIER
    settled = conn.execute(
        "SELECT COUNT(*) FROM predictions"
        " WHERE sport = ? AND resolved_utc IS NOT NULL"
        "   AND calibrated_prob IS NOT NULL"
        "   AND calibrated_prob >= ?",
        (sport, config.PROPS_MIN_CLAIM)).fetchone()[0]
    if not settled:
        settled = conn.execute(
            "SELECT COUNT(*) FROM predictions"
            " WHERE sport = ? AND resolved_utc IS NOT NULL AND model_prob >= ?",
            (sport, config.PROPS_MIN_CLAIM)).fetchone()[0]
    return language.least_tested_tier_line(
        tier, settled, calibration.TIER_MIN_SETTLED)


_WORST_BAND_CACHE: dict = {}


def _worst_band(conn: sqlite3.Connection, sport: str) -> str:
    """The largest gap in this sport's own record, in one sentence.

    Cached per slate render: the sentence is the same for every card on a
    page, and recomputing a whole curve per card would count one record
    eighty times.

    ONE SPORT, NEVER POOLED. LAW 6 is why this takes `sport` at all -- a worst
    band drawn across sports would describe none of them and would flatter,
    because the easy sport dilutes the hard one.
    """
    if sport in _WORST_BAND_CACHE:
        return _WORST_BAND_CACHE[sport]
    try:
        curve = calibration.curve(conn, sport=sport)
        said = calibration.largest_gap_sentence(curve.get("buckets") or [])
    except Exception:  # noqa: BLE001 - a missing curve is not a broken card
        said = ""
    _WORST_BAND_CACHE[sport] = said
    return said


def _hours_before(created_utc, kickoff_utc):
    """How far ahead of the start the forecast was made, in hours.

    None when either end is missing -- an age nobody can compute is not
    reported as zero, which would read as "made at the bell".
    """
    from datetime import datetime as _dt

    if not created_utc or not kickoff_utc:
        return None
    try:
        made = _dt.fromisoformat(str(created_utc).replace("Z", "+00:00"))
        start = _dt.fromisoformat(str(kickoff_utc).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (start - made).total_seconds() / 3600.0


def _superseded_ids(conn: sqlite3.Connection, sport: str) -> set:
    """Early rows that a final pass actually replaced.

    An early row is only an "early view" if a later forecast exists to stand
    in its place. Where the final pass never ran, or ran after the game began
    and correctly wrote nothing, the early row IS the standing forecast and
    must not be labelled as superseded.
    """
    return {
        r["id"] for r in conn.execute(
            "SELECT e.id FROM predictions e"
            " WHERE e.sport = ? AND e.pass_kind = 'early'"
            "   AND EXISTS (SELECT 1 FROM predictions f"
            "               WHERE f.game_id = e.game_id"
            "                 AND f.market_type = e.market_type"
            "                 AND f.subject = e.subject"
            "                 AND f.predictor = e.predictor"
            "                 AND f.factor_set_version = e.factor_set_version"
            "                 AND IFNULL(f.line_asked, -1e9)"
            "                     = IFNULL(e.line_asked, -1e9)"
            "                 AND f.pass_kind = 'final')",
            (sport,))
    }


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


def _at_the_line(conn: sqlite3.Connection, sport: str, ids: list[int],
                 team_names: dict) -> dict[int, dict]:
    """The venue's line beside each pick on this slate, as words.

    ONE LOOKUP FOR THE SLATE. The standing claim per prediction -- the last
    one written -- with the settled count for its market beside it, because
    LAW 4 wants the sample next to the figure and this figure is a comparison
    with a price.

    A forecast, and nothing more. The sentence says what the model gives the
    proposition and what the venue's price implies for the same one; it does
    not say which of them to act on, and `audit.at_the_line_advice_faults`
    scans these words on every gate run.
    """
    from .market import at_the_line as venue

    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT c.* FROM at_the_line_claims c WHERE c.prediction_id IN ({placeholders})"
        "   AND c.created_utc = (SELECT MAX(c2.created_utc) FROM at_the_line_claims c2"
        "                        WHERE c2.prediction_id = c.prediction_id)",
        ids).fetchall()
    if not rows:
        return {}
    settled = {
        r["market"]: r["n"] for r in conn.execute(
            "SELECT market, COUNT(*) AS n FROM at_the_line_claims"
            " WHERE sport = ? AND resolved_utc IS NOT NULL GROUP BY market",
            (sport,))
    }
    homes = {
        r["id"]: r["home"] for r in conn.execute(
            f"SELECT p.id, g.home FROM predictions p JOIN games g ON g.id = p.game_id"
            f" WHERE p.id IN ({placeholders})", ids)
    }
    out: dict[int, dict] = {}
    for row in rows:
        n = settled.get(row["market"], 0)
        home = language.team_name(homes.get(row["prediction_id"]), team_names, "club")
        out[row["prediction_id"]] = {
            "words": language.at_the_line_line(
                row["market"], row["line"], row["model_prob"], row["venue_implied"],
                n, home=home),
            "venue": venue.VENUE,
            "line": row["line"],
            "model_prob": row["model_prob"],
            "venue_implied": row["venue_implied"],
            "price_basis": row["price_basis"],
            "n": n,
            "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
            "gate_line": language.at_the_line_gate_line(
                n, config.MIN_SAMPLE_FOR_EDGE_CLAIM),
        }
    return out


def _attach_priced(conn: sqlite3.Connection, cards: list[dict]) -> None:
    """Put the priced forecast on each card that has one.

    NEVER IN PLACE OF THE BLIND NUMBER. The card's percentage stays the blind
    forecaster's, because that is the one this project's record is about; the
    priced number is a second sentence that names itself.
    """
    from .priced import forecast as priced

    ids = [c["prediction_id"] for c in cards]
    rows = priced.forecasts_for(conn, ids)
    for card in cards:
        row = rows.get(card["prediction_id"])
        card["priced_line"] = None if row is None else language.priced_line(
            row["blind_prob"], row["priced_prob"], row["price_at_write"],
            row["price_move_cents"])


def _payout_for(price):
    """What a contract at this price returns, once the price has been turned
    round to the side the card names."""
    from .market import recommend as _recommend

    return _recommend.payout_multiple(price)


def _edge_side_words(edge_side, takes_the_proposition):
    """Is the edge on the side the question names, or the other one?

    `edge_side` is 'yes' or 'no' against the CLAIM's fixed proposition;
    `takes_the_proposition` says whether the question names that same side.
    The two together answer the only question a reader has.
    """
    if edge_side is None or takes_the_proposition is None:
        return None
    on_the_proposition = edge_side == "yes"
    return "yes" if on_the_proposition == bool(takes_the_proposition) else "no"


# ---------------------------------------------------------------------------
# THREE STATES (GRIDIRON_THREE_STATES, 2026-09-08)
# ---------------------------------------------------------------------------

#: The three states a card can be in, read off `games.status`, which the live
#: poller writes. NEVER off a request: a state a person can set is a state
#: that can disagree with the game.
CARD_STATES = ("upcoming", "live", "final")


def card_state(status: str | None) -> str:
    """Which of the three a game is in. Anything unknown is upcoming, because
    a card whose game the record cannot place has not started as far as this
    project knows, and showing it as live would be a claim about a game."""
    if status == "in":
        return "live"
    if status == "final":
        return "final"
    return "upcoming"


def team_colours(sport: str, tricode: str | None) -> dict:
    """One club's colours, or the neutral pair when the club is not known.

    MEASURED, NOT TYPED. `gridiron/data/team_colours.py` is generated from the
    same ESPN payload the team names come from, and it records for every club
    the shade a white name can actually be read on -- the primary where white
    clears WCAG AA on it, the club's alternate where that clears it instead,
    and the primary darkened where neither does.
    """
    from .data.team_colours import TEAM_COLOURS

    entry = (TEAM_COLOURS.get(sport) or {}).get(tricode or "")
    if not entry:
        return {"primary": "3a4250", "on_white": "3a4250", "how": "unknown",
                "known": False}
    primary, on_white, how = entry
    return {"primary": primary, "on_white": on_white, "how": how, "known": True}


def _recent_form(conn: sqlite3.Connection, sport: str, team: str | None,
                 before_utc: str | None, limit: int = 5) -> list[str]:
    """The club's last five results, most recent first, from this record.

    NOT `recent_form_diff`. That factor is a margin difference over four games
    and is a different quantity; this is what a reader means by form. Both
    come from the same finished games, and the card says which it is showing.
    """
    if not team:
        return []
    rows = conn.execute(
        "SELECT home, away, home_score, away_score FROM games"
        " WHERE sport = ? AND status = 'final' AND (home = ? OR away = ?)"
        "   AND (? IS NULL OR kickoff_utc < ?)"
        " ORDER BY kickoff_utc DESC LIMIT ?",
        (sport, team, team, before_utc, before_utc, limit)).fetchall()
    out = []
    for row in rows:
        if row["home_score"] is None or row["away_score"] is None:
            continue
        ours = row["home_score"] if row["home"] == team else row["away_score"]
        theirs = row["away_score"] if row["home"] == team else row["home_score"]
        out.append("W" if ours > theirs else ("L" if ours < theirs else "D"))
    return out


def _starter(conn: sqlite3.Connection, game_id: str, side: str) -> str | None:
    """The probable pitcher this game's factors already read."""
    row = conn.execute(
        "SELECT pitcher_name FROM mlb_probables WHERE game_id = ? AND side = ?"
        " ORDER BY recorded_utc DESC LIMIT 1", (game_id, side)).fetchone()
    return row["pitcher_name"] if row else None


def _weather(conn: sqlite3.Connection, game_id: str) -> str | None:
    """The forecast the weather factor already fetched, in a reader's units."""
    row = conn.execute(
        "SELECT temp_f, wind_mph, precip_pct FROM weather_forecasts"
        " WHERE game_id = ? ORDER BY fetched_utc DESC LIMIT 1",
        (game_id,)).fetchone()
    if row is None:
        return None
    return language.weather_words(row["temp_f"], row["wind_mph"],
                                  row["precip_pct"])


def _first_sentence(card: dict) -> str | None:
    """The first sentence of the reasoning, visible without a click.

    THE REST STAYS BEHIND `Why`. A card that shows everything is a card nobody
    scans; a card that shows nothing is a card the operator has to open twenty
    times to read his own slate.
    """
    sentences = ((card.get("why") or {}).get("sentences") or [])
    if sentences:
        return sentences[0]
    reasoning = card.get("reasoning")
    if not reasoning:
        return None
    head = str(reasoning).split(". ")[0].strip()
    return head + ("." if head and not head.endswith(".") else "")


def _club_name(names: dict, code: str | None) -> str:
    """"Phillies", from whatever shape the record holds a name in.

    `team_names` carries a structure -- full, city, club -- and a card wants
    the club alone: "Astros" beside "Phillies" reads as a matchup, and the
    full names are two lines of chrome.
    """
    entry = names.get(code or "")
    if isinstance(entry, dict):
        return entry.get("club") or entry.get("full") or (code or "")
    return entry or (code or "")


def _card_context(conn: sqlite3.Connection, card: dict) -> dict:
    """Everything the richer card shows that the record already holds.

    NOTHING NEW IS FETCHED. Every line here is a read of a table some factor
    already filled: the probable pitcher, the finished games, the forecast the
    weather factor pulled. A card may only show what a factor already read.
    """
    sport = card.get("sport")
    game_id = card.get("game_id")
    game = conn.execute(
        "SELECT home, away, status, home_score, away_score, kickoff_utc,"
        "       live_period, live_clock, live_updated_utc FROM games"
        " WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        return {"state": "upcoming"}

    state = card_state(game["status"])
    home_colours = team_colours(sport, game["home"])
    away_colours = team_colours(sport, game["away"])
    names = card.get("team_names") or {}
    context = {
        "state": state,
        "home": game["home"],
        "away": game["away"],
        "home_name": _club_name(names, game["home"]),
        "away_name": _club_name(names, game["away"]),
        "home_colour": home_colours,
        "away_colour": away_colours,
        # THE SPORT'S KEY, not its colour. The stylesheet holds the five
        # colours as tokens so the contrast tool can measure them; a hex here
        # as well would be a second copy to disagree with.
        "sport_key": sport,
        "home_form": language.form_words(
            _recent_form(conn, sport, game["home"], game["kickoff_utc"])),
        "away_form": language.form_words(
            _recent_form(conn, sport, game["away"], game["kickoff_utc"])),
        "first_sentence": _first_sentence(card),
    }
    if sport == "mlb":
        context["home_starter"] = language.starter_words(
            _starter(conn, game_id, "home"))
        context["away_starter"] = language.starter_words(
            _starter(conn, game_id, "away"))
    weather = _weather(conn, game_id)
    if weather:
        context["weather_words"] = weather
    if state in ("live", "final"):
        context["score_words"] = language.score_line_words(
            game["away"], game["away_score"], game["home"], game["home_score"])
    if state == "live":
        context["period_words"] = language.period_words(
            sport, game["live_period"], game["live_clock"])
        context["polled_words"] = language.polled_words(
            game["live_updated_utc"], db.utcnow())
    return context


def _today_card(entry: dict, card: dict, *, taken: bool,
                group_tier: str | None, unit_dollars: float | None,
                conn: sqlite3.Connection | None = None) -> dict:
    """One pick, in the grammar a sportsbook reader already has.

    THE EDGE IS THE LARGEST THING ON IT. Everything else on this card is
    context for that number: the event says which game, the question says what
    was asked, the model and venue chips say where the two prices are, and the
    edge says what the difference is worth after the fee. The probability --
    the number that used to be 40 pixels tall on every card -- is not on the
    face at all; it is in the fair value, as a price, which is the form the
    reader can compare with the venue's.
    """
    question = card.get("phrase") or card.get("row_title") or "this question"
    # THE PRICE ROW IS ABOUT THE SIDE THE QUESTION NAMES (2026-09-07). The
    # claim is stored from a fixed proposition -- the home side, or the over
    # -- and the question is stated from the side the model took. On the first
    # card that ever cleared the bar those were opposites, so it read
    # "Toronto covers +1.5" over three numbers about the Athletics.
    takes = entry.get("question_takes_the_proposition")
    flip = takes is False
    price = entry.get("price")
    if flip and price is not None:
        price = 1.0 - price
    tier = (card.get("tier") or {})
    chip = tier.get("chip_label")
    context = _card_context(conn, card) if conn is not None else {"state": "upcoming"}
    state = context.get("state", "upcoming")
    # WHICH CLUB THE QUESTION FAVOURS, for the accent and the payout chip.
    # The side the question names, which is the side its numbers are about.
    favoured = context.get("home") if _favours_home(entry, card, context) \
        else context.get("away")
    favoured_colour = (context.get("home_colour") if favoured == context.get("home")
                       else context.get("away_colour")) or {}
    out = {
        "prediction_id": entry["prediction_id"],
        # LAW 4 travels with every row on this page, as it does everywhere.
        "n": entry["gate_n"],
        # THE STATE IS DERIVED FROM THE GAME, never from a tab somebody chose.
        "state": state,
        # the event line: placed, never composed. The renderer turns the
        # instant into the reader's own clock and touches nothing else.
        "matchup": card.get("matchup") or card.get("row_title"),
        "kickoff_utc": card.get("kickoff_utc"),
        "kickoff_label": language.kickoff_label_words(),
        "sport_label": language.SPORT_LABELS.get(entry.get("sport"),
                                                 (entry.get("sport") or "").upper()),
        "question": question,
        # WHICH MARKET, so the chips above can filter the groups. The chips
        # are declared a filter row on Upcoming and were filtering only the
        # slate beneath it: switching to a market with no picks left the
        # previous market's cards standing in the groups.
        "market": entry.get("market") or card.get("market"),
        # the three chips
        "model_words": language.price_chip_words(
            None if entry.get("fair_value") is None
            else (1.0 - entry["fair_value"] if flip else entry["fair_value"]) * 100),
        "venue_words": language.venue_chip_words(
            price, _payout_for(price) if flip else entry.get("payout")),
        "edge_words": language.edge_chip_words(entry.get("edge_cents")),
        # THE EDGE KEEPS ITS SIGN -- it is what the better side is worth
        # either way -- and its label says "on the other side" only when the
        # better side is not the one the question names.
        "edge_label": language.edge_label_words(
            language.price_row_labels()["edge"],
            _edge_side_words(entry.get("edge_side"), takes)),
        "edge_state": language.edge_state(entry.get("edge_cents")),
        "edge_cents": entry.get("edge_cents"),
        "payout": entry.get("payout"),
        "gate_words": language.gate_status_words(entry["gate_n"], entry["gate"]),
        # THE TIER CHIP ONLY WHEN IT SAYS SOMETHING. Twelve chips reading
        # "STRONG · unproven" down one page is a group heading wearing a
        # badge twelve times; when every card in a group would carry the same
        # one, the heading carries it and the cards carry none.
        "tier_chip": None if (chip is None or chip == group_tier) else chip,
        "taken": taken,
        # collapsed by default; the operator reads each pick, so the prose
        # the reasoning pass already wrote is one click away rather than one
        # page away.
        "reasoning": card.get("reasoning"),
        "why": card.get("why"),
        "top_factors": card.get("top_factors") or [],
        # THE PAYOUT IS THE BIG CHIP from 2026-09-08, with the price beneath
        # it and the edge on its own quiet line under the row.
        "payout_words": language.payout_chip_words(entry.get("payout")),
        "price_words": language.price_under_payout_words(price),
        "favoured": favoured,
        "favoured_colour": favoured_colour.get("primary"),
        "favoured_on_white": favoured_colour.get("on_white"),
    }
    out.update({k: v for k, v in context.items() if k != "state"})
    out["edge_line_words"] = language.edge_line_words(
        entry.get("edge_cents"),
        other_side=_edge_side_words(entry.get("edge_side"), takes) == "no")
    # A LIVE CARD CARRIES NO PRICE, NO EDGE, NO SIZE AND NO TAP. The in-game
    # rule is already law (THE_PRICED P2): a score up to ninety seconds stale
    # against a live market is adversely selected by construction, so a card
    # whose game is being played states the score and nothing that could be
    # acted on. `audit.live_card_faults` fails the gate on any of them.
    if state == "live":
        for field in ("payout_words", "price_words", "edge_words",
                      "edge_line_words", "edge_label", "size_words",
                      "model_words", "venue_words"):
            out.pop(field, None)
        out["edge_state"] = "none"
        out["taken_badge"] = language.taken_badge_words() if taken else None
    if state == "final":
        out["settled_words"] = language.settled_outcome_words(
            card.get("shown_prob"), card.get("outcome"),
            out.get("question", ""))
    return out


def _favours_home(entry: dict, card: dict, context: dict) -> bool:
    """Which club the card's WORDS are about, for the accent colour.

    THE SAME ANSWER THE PRICES USE. `question_takes_the_proposition` says
    whether the question names the side the claim is stored from -- the home
    side on a winner or a spread -- and the accent follows the words rather
    than the subject: a prediction of "the home side does not cover" is a card
    about the away side, and painting it in the home club's colour is the
    wrong-side defect again, in paint.

    A GUESS HERE IS ONLY A COLOUR, and it is still not guessed: the subject
    names a club on a winner or a spread question, and a total is about
    neither, which the caller reads as the home side by convention rather
    than by inference.
    """
    takes = entry.get("question_takes_the_proposition")
    if takes is not None:
        return bool(takes)
    subject = (card.get("subject") or "").strip()
    return not (subject and subject == context.get("away"))


def _today_block(conn: sqlite3.Connection, cards: list[dict],
                 priced: list[dict], forecaster: str | None = None) -> dict:
    """The two groups the operator reads every morning, never blended.

    CLEARS THE BAR is what survives both conditions: an edge after the venue's
    fee, and enough of a return on the money to be worth the click (F2b).
    WATCHING is everything else on the shortlist, each carrying its own edge
    including when that number is negative, which is the point of showing it.

    THE FLOOR IS A DISPLAY PREFERENCE AND IS APPLIED HERE, on the way to the
    screen, never on the way to the record: `recommend.record_for` writes
    every pick that clears the bar whatever the floor says, so the closing
    line on the 21st is measured over all of them. A taste that could hide
    rows from the measurement would be the operator rewriting his own
    evidence.
    """
    from . import settings as _settings

    by_id = {c["prediction_id"]: c for c in cards}
    already = taken_ids(conn, [c["prediction_id"] for c in cards])
    try:
        floor = float(_settings.value(conn, "min_payout"))
    except (ValueError, TypeError):
        floor = 1.0
    raw_unit = _settings.value(conn, "unit_dollars")
    unit_dollars = float(raw_unit) if raw_unit else None

    # WHICH CHIP THE WHOLE GROUP WOULD WEAR. Computed before the cards are
    # built, because "is this chip worth showing" is a question about the
    # group and cannot be answered one card at a time.
    def _one_chip(entries):
        chips = {((by_id.get(e["prediction_id"]) or {}).get("tier") or {})
                 .get("chip_label") for e in entries}
        chips.discard(None)
        return next(iter(chips)) if len(chips) == 1 else None

    clears_entries, watch_entries, prices = [], [], []
    for entry in priced:
        if entry["prediction_id"] not in by_id:
            continue
        if entry.get("price") is not None:
            prices.append(entry["price"])
        (clears_entries if entry["side"] is not None else watch_entries).append(entry)

    clears_chip = _one_chip(clears_entries)
    watch_chip = _one_chip(watch_entries)

    clears, below_floor, watching, live, settled_cards = [], [], [], [], []
    for entry in clears_entries:
        card = _today_card(entry, by_id[entry["prediction_id"]],
                           taken=entry["prediction_id"] in already,
                           group_tier=clears_chip, unit_dollars=unit_dollars,
                           conn=conn)
        # A GAME BEING PLAYED IS NOT AN UPCOMING PICK. It moves whole, with
        # everything that could be acted on stripped off it by `_today_card`.
        if card["state"] == "live":
            live.append(card)
            continue
        size = entry["size"]
        card["size_words"] = language.size_words(
            units=size["units"], flat=size["kind"] == "flat",
            why=size.get("why"), unit_dollars=unit_dollars)
        payout = entry.get("payout")
        (below_floor if (payout is not None and payout < floor) else clears
         ).append(card)
    for entry in watch_entries:
        # NO SIZE ON A WATCHED CARD. A size on a pick that does not clear the
        # bar is a recommendation the app is not making.
        card = _today_card(
            entry, by_id[entry["prediction_id"]],
            taken=entry["prediction_id"] in already,
            group_tier=watch_chip, unit_dollars=unit_dollars, conn=conn)
        (live if card["state"] == "live" else watching).append(card)

    # HOW MANY OF THE DAY'S QUESTIONS HAVE FINISHED. Counted from the cards
    # themselves rather than queried again, so the strip cannot disagree with
    # the page about what day it is.
    settled_n = sum(1 for c in cards
                    if card_state((c.get("game_status") or "")) == "final")

    median_price = statistics.median(prices) if prices else None
    fee_cents = None
    if median_price is not None:
        from .market import recommend as _recommend

        fee_cents = round(_recommend.fee(median_price) * 100, 1)

    # THE LIVE GROUP IS BUILT FROM THE CARDS, not from the priced entries.
    # `recommend.for_predictions` calls `refuse_in_game` and drops a question
    # whose game has started -- correctly, because nothing may be sized
    # in-game -- so a card assembled from its output vanished the moment the
    # first pitch was thrown instead of moving to Live.
    # THE SETTLED CARDS, for Results. Same card, third state: the loop
    # closed on the one that opened it.
    for card_row in cards:
        if not (card_row.get("on_shortlist")
                or card_row["prediction_id"] in already):
            continue
        if card_state(card_row.get("game_status") or "") != "final":
            continue
        settled_cards.append(_today_card(
            {"prediction_id": card_row["prediction_id"],
             "gate_n": card_row.get("gate_n") or 0,
             "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
             "sport": card_row.get("sport")},
            card_row,
            taken=card_row["prediction_id"] in already,
            group_tier=None, unit_dollars=unit_dollars, conn=conn))

    priced_ids = {e["prediction_id"] for e in priced}
    for card_row in cards:
        # SHORTLISTED, OR ONE HE MARKED. A taken pick is the game he has money
        # on, and it belongs on Live whether or not the ranker put it in the
        # day's top twenty -- that ranking is about which questions were worth
        # asking before the game, and this tab is about the game.
        if not (card_row.get("on_shortlist")
                or card_row["prediction_id"] in already):
            continue
        if card_row["prediction_id"] in priced_ids:
            continue          # already handled above, in whichever group
        if card_state(card_row.get("game_status") or "") != "live":
            continue
        live.append(_today_card(
            {"prediction_id": card_row["prediction_id"],
             "gate_n": card_row.get("gate_n") or 0,
             "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
             "sport": card_row.get("sport")},
            card_row,
            taken=card_row["prediction_id"] in already,
            group_tier=None, unit_dollars=unit_dollars, conn=conn))

    # TAKEN FIRST ON LIVE, and nothing else about them. The game he has money
    # on is the one he is looking for; which way it is going is the game's to
    # say, not the app's.
    live.sort(key=lambda c: (not c["taken"], c.get("question") or ""))

    day = next((c.get("league_date") for c in cards if c.get("league_date")), None)
    sport = next((c.get("sport") for c in cards if c.get("sport")), None)
    strip = language.day_strip_words(
        day_words=language.date_words_from_iso(day),
        slate_words=language.SPORT_LABELS.get(sport, sport),
        clears=len(clears), watching=len(watching),
        below_floor=len(below_floor), floor=floor,
        forecaster=forecaster, live=len(live), settled=settled_n)

    from . import tasks as _tasks

    return {
        "n": len(clears),
        "watching_n": len(watching),
        "live_n": len(live),
        "settled_n": settled_n,
        "live": live,
        "live_heading": language.state_heading_words("live", len(live)),
        "settled": settled_cards,
        "settled_heading": language.state_heading_words(
            "final", len(settled_cards)),
        "live_empty_words": (None if live else language.live_empty_words(
            next((c.get("kickoff_utc") for c in cards
                  if card_state(c.get("game_status") or "") == "upcoming"
                  and c.get("kickoff_utc")), None))),
        "live_first_kickoff_utc": next(
            (c.get("kickoff_utc") for c in cards
             if card_state(c.get("game_status") or "") == "upcoming"
             and c.get("kickoff_utc")), None),
        "below_floor_n": len(below_floor),
        "floor": floor,
        "clears": clears,
        "below_floor": below_floor,
        "watching": watching,
        "clears_chip": clears_chip,
        "watching_chip": watch_chip,
        "where_words": strip["where"],
        "count_words": strip["counts"],
        # SAID ONCE FOR THE WHOLE SLATE, not appended to thirty rows. The
        # sentence was on every row until this brief, which is how a page
        # teaches a reader that its rows are not worth reading.
        "no_price_words": (None if median_price is not None
                           else language.first_price_words(_tasks.NEAR_START_HOURS)),
        "clears_heading": language.clears_the_bar_heading(len(clears),
                                                           len(below_floor)),
        "watching_heading": language.watching_heading(len(watching)),
        "below_floor_words": (language.below_floor_words(len(below_floor), floor)
                              if below_floor else None),
        # THE CHIP LABELS, from here rather than from the renderer, for the
        # same reason every other visible string is.
        "labels": language.price_row_labels(),
        "fee_line": language.fee_arithmetic_line(median_price, fee_cents),
        "taken_line": language.taken_line(len(
            [c for c in clears + below_floor + watching if c["taken"]])),
        "taken_today": taken_today(conn, cards),
    }


def taken_today(conn: sqlite3.Connection, cards: list[dict]) -> dict:
    """The running list, in the position a book puts one.

    IT IS A SELECTION RECORD AND NOT A SLIP. No stake, no payout, no total,
    and the word "slip" is not in it: what it holds is which questions the
    operator marked and when, which is the comparison `calibration
    .taken_comparison` exists to make.
    """
    by_id = {c["prediction_id"]: c for c in cards}
    rows = conn.execute(
        "SELECT prediction_id, taken_utc FROM picks_taken"
        " ORDER BY taken_utc DESC, id DESC LIMIT 40").fetchall()
    entries = []
    for row in rows:
        card = by_id.get(row["prediction_id"])
        if card is None:
            continue
        # THE EDGE AS IT STOOD WHEN THE PICK WAS MARKED. `picks_taken` holds a
        # prediction and a moment and nothing else -- three columns, by the
        # law that keeps it from becoming a ledger -- so the number comes from
        # the recommendation that was already on the record at that moment.
        # Later recommendations for the same question are ignored on purpose:
        # a number that moved afterwards would make this a scoreboard, and it
        # is a record of what was chosen.
        edge = conn.execute(
            "SELECT edge_cents FROM recommendations"
            " WHERE prediction_id = ? AND created_utc <= ?"
            " ORDER BY created_utc DESC, id DESC LIMIT 1",
            (row["prediction_id"], row["taken_utc"])).fetchone()
        entries.append({
            "prediction_id": row["prediction_id"],
            "taken_utc": row["taken_utc"],
            "words": language.taken_entry_words(
                card.get("phrase") or card.get("row_title") or "this question",
                edge["edge_cents"] if edge else None),
        })
    return {
        "n": len(entries),
        "entries": entries,
        "heading": language.taken_today_heading(len(entries)),
    }


def _recommendations_block(conn: sqlite3.Connection, cards: list[dict]) -> dict:
    """What is worth taking on this slate, and at what size.

    MOST DAYS THIS IS EMPTY, and an empty list is a correct output rather than
    a failure to find something. The page says so in a sentence instead of
    reaching: a surface that produces an opinion every morning is a surface
    that has stopped measuring anything.

    Nothing here is a wager. It is a price the model disagrees with, the size
    the declared rule allows, and the settled count behind it -- and below a
    market's gate that size is one flat unit whatever the model says.
    """
    from .market import recommend

    ids = [c["prediction_id"] for c in cards if c.get("on_shortlist")]
    priced = recommend.for_predictions(conn, ids)
    lines = []
    uncovered = 0
    no_edge = 0
    for entry in priced:
        if entry["side"] is None:
            if not (entry.get("coverage") or {}).get("priceable", True):
                uncovered += 1
            else:
                no_edge += 1
            continue
        size = entry["size"]
        lines.append({
            "prediction_id": entry["prediction_id"],
            "n": entry["gate_n"],
            "side": entry["side"],
            "edge_cents": entry["edge_cents"],
            "units": size["units"],
            "flat": size["kind"] == "flat",
            "words": language.recommendation_line(
                question=_question_words(cards, entry),
                fair_value=entry["fair_value"], price=entry["price"],
                edge_cents=entry["edge_cents"], side=entry["side"],
                units=size["units"], flat=size["kind"] == "flat",
                size_why=size.get("why")),
        })
    considered = len(priced)
    return {
        "n": len(lines),
        "considered": considered,
        "lines": lines,
        "empty_words": language.nothing_priced_line(considered, uncovered, no_edge),
        "uncovered": uncovered,
        "no_edge": no_edge,
    }


def _question_words(cards: list[dict], entry: dict) -> str:
    """The question this recommendation is about, in the words already on its
    card. Composed once, on the card, and reused rather than rebuilt."""
    for card in cards:
        if card["prediction_id"] == entry["prediction_id"]:
            return card.get("phrase") or card.get("row_title") or "this question"
    return "this question"


def _shortlist_block(conn: sqlite3.Connection, sport: str,
                     cards: list[dict]) -> dict:
    """Mark each card with its place in the ordering, and describe the split.

    The ordering itself is `shortlist.choose`; this is the page's half of it.
    Two properties matter more than the arithmetic:

      * THE COUNT OF WHAT IS NOT SHOWN IS ON THE CONTROL. Not in a tooltip,
        not implied by a scrollbar.
      * A SLATE WITH NO RANKS SHOWS EVERYTHING. The ranker landed on
        2026-09-07; every row written before it has no rank until the backfill
        runs, and a page that hid those would be hiding the record's own past.
    """
    from . import shortlist as ranker

    ids = [c["prediction_id"] for c in cards]
    picked = ranker.choose(conn, sport, ids)
    ranks = ranker.ranks_for(conn, ids)
    on = set(picked["shortlist"])
    order = {pid: i for i, pid in enumerate(picked["shortlist"])}
    for card in cards:
        pid = card["prediction_id"]
        row = ranks.get(pid)
        card["on_shortlist"] = pid in on
        card["shortlist_place"] = order.get(pid)
        card["rank_line"] = language.shortlist_rank_line(
            dict(row, gate=config.RANK_EDGE_GATE) if row else None)
    slate_word = config.SPORT_SLATE_WORD.get(sport, "week")
    return {
        "ranked": bool(picked["ranked"]),
        "n": len(picked["shortlist"]),
        "rest": len(picked["rest"]),
        "cap": picked["cap"],
        "ranker_version": config.RANKER_VERSION,
        "words": language.shortlist_line(len(picked["shortlist"]), len(cards),
                                         slate_word, ranked=bool(picked["ranked"])),
        # THE SECOND SENTENCE, for when the control has been opened and the
        # whole slate is on screen. Both are written here so the renderer picks
        # between two sentences rather than composing one -- and so the line
        # over the grid cannot go on claiming twenty while showing sixty, which
        # is what the first render of this did.
        "all_words": language.shortlist_line(len(cards), len(cards), slate_word,
                                             ranked=bool(picked["ranked"])),
        "rest_words": language.shortlist_rest_line(len(picked["rest"])),
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


def _settled_lines(cards: list[dict]) -> dict:
    """"<market>|<tier>" -> "13 settled", for every combination that has any:
    the picks a finished slate no longer shows (UI audit finding 9). Same keys
    as `_count_lines`, so the renderer looks one up beside the other."""
    markets = {""} | {c.get("market") or "" for c in cards}
    tiers = {""} | {(c.get("tier") or {}).get("tier") or "" for c in cards}
    settled = [c for c in cards if c.get("resolved_utc") is not None or c.get("voided")]
    out = {}
    for market in markets:
        for tier in tiers:
            n = len([c for c in settled
                     if (not market or (c.get("market") or "") == market)
                     and (not tier or ((c.get("tier") or {}).get("tier") or "") == tier)])
            if n:
                out[f"{market}|{tier}"] = language.settled_count_line(n)
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
        "settled_lines": _settled_lines(cards),
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


def _card_order(card: dict) -> tuple:
    """Disagreement first; among cards with no line, confidence.

    A card with no line has no disagreement to rank by (`abs_gap` is -1), and
    before 2026-09-05 every such card tied, so the one that led a lineless
    slate was whichever the query happened to return first -- under a tag
    that called it the sharpest disagreement.
    """
    return (card["abs_gap"], card.get("model_prob") or 0.0)


def tier_table_for(conn: sqlite3.Connection, sport: str, *,
                   market: str | None, forecaster: str | None) -> dict:
    """The tier table for ONE market and ONE forecaster of one sport.

    THE SELECT ABOVE THE TABLE DID NOTHING (UI audit finding 6, 2026-09-05):
    it was filled with the sport's markets and never wired, and the forecaster
    picker beside it set a variable nothing read. The scorecard carries one
    table -- the headline market, the statistical forecaster -- and this is
    the door for every other combination, through the same `tier_table` the
    chips on the cards use, so the two cannot drift.
    """
    calibration.require_sport(sport, "views.tier_table_for")
    markets = list(config.SPORT_MARKETS.get(sport, ()))
    if market not in markets:
        raise KeyError(market)
    predictor = forecaster if forecaster in ("statistical", "llm") else "statistical"
    table = calibration.tier_table(
        conn, sport=sport,
        market_type=calibration.market_type_of(sport, market),
        prop_type=calibration.prop_type_of(sport, market),
        predictor=predictor)
    table["market"] = market
    return table


def available_weeks(conn: sqlite3.Connection, sport: str) -> list[dict]:
    calibration.require_sport(sport, "views.available_weeks")
    return [
        {"season": r["season"], "week": r["week"], "n": r["n"],
         # THE CHOOSER'S OWN WORDS. It was built in the browser as
         # `w.season + ' week ' + w.week`, which is both prose composed in the
         # renderer and the eight-digit key on the page.
         # WITH THE SLATE'S OWN DATE (audit 2026-09-05): a baseball slate is
         # keyed by an ordinal, and without its calendar day the chooser read
         # "Day 155, 2026" -- the key with a word beside it, which is still
         # the key.
         "label": language.slate_option(
             r["season"], r["week"], r["n"],
             config.SPORT_SLATE_WORD.get(sport, "week"), r["league_date"])}
        for r in conn.execute(
            # FORECASTS, NOT ROWS (UI audit finding 13, 2026-09-05): the NBA
            # picker read "Week 1, 2026 (47)" beside "0 picks" because it
            # counted 47 voided rows. A voided row is not a forecast anywhere
            # else on the page, and a slate with none is not offered.
            "SELECT g.season, g.week, COUNT(*) AS n,"
            " MIN(g.league_date) AS league_date FROM predictions p"
            " JOIN games g ON g.id = p.game_id WHERE p.sport = ?"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)"
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
        # STANDING QUESTIONS, NOT ROWS (UI audit finding 12, 2026-09-05). The
        # login page said "NFL 152 picks this week" against Picks' "All 107":
        # this counted every unresolved row, early and final passes both.
        # One clause counts the record everywhere (`standing_row_clause`).
        tonight = conn.execute(
            "SELECT COUNT(*) FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND p.resolved_utc IS NULL"
            "   AND g.status <> 'final'"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)"
            + calibration.standing_row_clause(same_set=False),
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
        f"SELECT p.*, g.season, g.week, g.home, g.away, g.status, g.league_date"
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
                # THE SLATE IN WORDS (audit 2026-09-05). Results printed
                # `'wk ' + week` in the browser, which on a college row is
                # "wk 20260905": the key, composed in the renderer.
                "slate_label": language.slate_title(
                    r["season"], r["week"],
                    config.SPORT_SLATE_WORD.get(sport, "week"),
                    r["league_date"]),
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
        # Same door as the slate. A second surface rendering raw is exactly
        # what `check_no_code_names_in_llm_prose` exists to refuse.
        "reasoning": language.humanise_reasoning(
            r["reasoning"], _why_phrases()),
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
        " p.resolved_utc, p.market_type, p.prop_type, p.predictor, p.pass_kind,"
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
            # WHICH FORECAST THIS RESULT GRADED (A3, 2026-09-03). "final" when
            # a later pass wrote it, "early only" when the early row was the
            # only one this game got -- which is the MISSED case, and a reader
            # of the record is entitled to know which they are looking at.
            "pass_mark": language.pass_mark(r["pass_kind"]),
            # What the pick WAS, in words, with the flip applied.
            "phrase": language.phrase(item),
            # The same three-sentence reason the expanded pick rows carry, so a
            # resolved row in the digest explains itself without being opened.
            # A JOINTLY-FITTED PAIR READS AS ONE REASON (D1).
            "why": language.why_block(
                item, phrases,
                config.jointly_read(sport, r["market_type"])),
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
            "countdown": language.bucket_countdown_line(
                label, n, config.MIN_SAMPLE_FOR_EDGE_CLAIM),
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


def _row_title(r, team_names=None) -> str:
    """The row's heading: a matchup, or a subject and what is being asked.

    "SD @ TB" for a game market; "TATIS JR. - HITS" for a prop, because on a
    prop the subject IS the headline and the fixture is a detail that belongs
    on the pick line underneath.
    """
    # A FIGHT HAS NO HOME SIDE. "Salahdine Parnasse @ Dan Hooker" reads as a
    # visitor at a host, and there is neither: the two corners are stored in
    # the home/away columns because that is the shape `games` has, and the
    # interface may never repeat it back.
    # FULL NAMES, AND "at" RATHER THAN "@" (cards UI, 2026-09-04). The brief
    # asks for "Padres at Reds", and a heading in 22px type reading "MIA @ LV"
    # is a database talking to itself in the largest words on the page. The
    # tricode was right for a compact row 14px tall; the card is not that.
    #
    # THE CLUB'S OWN NAME, NOT ITS CITY. "Padres at Reds" is what the brief
    # writes and what a person says; `team_name(..., "club")` gives it where
    # the crosswalk has one and falls back to the tricode where it does not,
    # which is the same rule every other name on the page follows.
    if r["sport"] == "ufc":
        # A FIGHT HAS NO HOME SIDE, and surnames are how a card is billed:
        # "Hooker vs Parnasse", not two full names in a heading.
        return (f"{language.surname(r['home'])} vs "
                f"{language.surname(r['away'])}")
    if r["market_type"] != "prop":
        names = team_names
        return (f"{language.team_name(r['away'], names, 'club')} at "
                f"{language.team_name(r['home'], names, 'club')}")
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


#: How long a forecaster may write nothing before the front page says so.
#:
#: TWENTY-FOUR HOURS, because every sport that runs daily forecasts at least
#: once inside it and the weekly ones still have their slate written. A
#: forecaster that has produced no row in a day, on a machine that has been
#: forecasting, has stopped.
FORECASTER_SILENT_AFTER_HOURS = 24.0


def _silent_forecasters(conn: sqlite3.Connection) -> list[dict]:
    """A forecaster that used to write rows and has stopped.

    THIS EXISTS BECAUSE IT HAPPENED AND NOTHING SAID SO. The LLM forecaster
    wrote 23 rows on 2026-09-02 between 06:02 and 06:04 and never again; every
    predict run since recorded `llm_unavailable:bad_api_key` in its
    degradations, and the front page -- which warns about silent tasks, missed
    slates and stale schedules -- said nothing at all. The statistical model
    kept writing, so every screen looked healthy while half the forecasters
    were gone.

    A DEGRADATION RECORDED ONCE PER RUN IS A FOOTNOTE. A forecaster absent for
    a day is a defect, and this is the difference.

    Not sport-scoped, and that is not a LAW 6 problem: this is a fact about
    the appliance, not about any sport's record.
    """
    from . import config

    now = _parse_utc(db.utcnow())
    out: list[dict] = []
    for predictor in ("statistical", "llm"):
        row = conn.execute(
            "SELECT COUNT(*) AS n, MAX(created_utc) AS last"
            "  FROM predictions WHERE predictor = ?", (predictor,)).fetchone()
        if not row or not row["n"]:
            # NEVER HAVING WRITTEN IS NOT THE SAME AS HAVING STOPPED. A
            # forecaster with no rows at all may simply not be switched on,
            # and warning about it every day would train a reader to ignore
            # the panel.
            continue
        last = _parse_utc(row["last"])
        if last is None:
            continue
        hours = (now - last).total_seconds() / 3600.0
        if hours < FORECASTER_SILENT_AFTER_HOURS:
            continue

        reason = _latest_degradation(conn, predictor)
        out.append({
            "kind": "forecaster-silent",
            "predictor": predictor,
            "hours": round(hours, 1),
            "text": language.forecaster_silent_line(
                predictor, hours, row["n"], reason),
        })
    return out


def _latest_degradation(conn: sqlite3.Connection, predictor: str) -> str | None:
    """The reason the most recent run recorded, if it recorded one.

    THE APP ALREADY KNEW WHY. Every predict run stores its degradations, and
    `llm_unavailable:bad_api_key` sat in that column for thirty hours without
    reaching a single screen. Reading it here is the whole repair.
    """
    if predictor != "llm":
        return None
    for row in conn.execute(
            "SELECT payload_json FROM task_runs"
            "  WHERE task LIKE 'predict:%' OR task LIKE 'final:%'"
            "  ORDER BY started_utc DESC LIMIT 12"):
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except ValueError:
            continue
        for key in (payload.get("degradations") or {}):
            if str(key).startswith("llm_unavailable:"):
                return str(key).split(":", 1)[1]
    return None


def _parse_utc(text):
    from datetime import datetime as _dt

    if not text:
        return None
    try:
        return _dt.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None


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
    # A FORECASTER THAT HAS STOPPED WRITING (S4, 2026-09-03). The LLM was
    # absent for thirty hours with the reason sitting unread in task_runs.
    out.extend(_silent_forecasters(conn))
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


def take_pick(conn: sqlite3.Connection, prediction_id: int) -> dict:
    """Record that the operator took this pick. Which, and when. Nothing else.

    IDEMPOTENT BY THE TABLE'S OWN CONSTRAINT: a second tap on the same pick is
    not a second wager, and the record would have no way to tell the two
    apart, so it stores one row and says it was already there.
    """
    from .db import utcnow

    row = conn.execute("SELECT id, created_utc FROM predictions WHERE id = ?",
                       (prediction_id,)).fetchone()
    if row is None:
        return {"taken": False, "already": False,
                "why": "there is no such forecast to take"}
    try:
        conn.execute(
            "INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
            (prediction_id, utcnow()))
        conn.commit()
        return {"taken": True, "already": False, "prediction_id": prediction_id}
    except sqlite3.IntegrityError as exc:
        if "UNIQUE" not in str(exc):
            raise
        return {"taken": True, "already": True, "prediction_id": prediction_id}


def taken_ids(conn: sqlite3.Connection, prediction_ids: list[int]) -> set:
    """Which of these picks are already marked as taken."""
    if not prediction_ids:
        return set()
    placeholders = ",".join("?" for _ in prediction_ids)
    return {
        r["prediction_id"] for r in conn.execute(
            f"SELECT prediction_id FROM picks_taken"
            f" WHERE prediction_id IN ({placeholders})", list(prediction_ids))
    }


def learning(conn: sqlite3.Connection, sport: str) -> dict:
    """What the record has taught the model, per category.

    THE MACHINERY IS UNCHANGED. `correction.py` fits Platt scaling on the
    record's own claims and outcomes at fifty settled rows and applies it at
    write time; `drift.py` measures where the line went afterwards, gated at
    fifty pairs. Both have been running and neither has ever been on a page,
    which is why the operator concluded the app does not learn.
    """
    from . import correction, drift

    # WHEN THE REFIT LAST RAN AT ALL, so a category that is eligible and
    # unfitted says why rather than reading as a contradiction.
    last_refit = conn.execute(
        "SELECT MAX(fitted_utc) FROM calibration_corrections").fetchone()[0]

    rows = []
    for market in config.SPORT_MARKETS.get(sport, ()):
        market_type = calibration.market_type_of(sport, market)
        latest = conn.execute(
            "SELECT * FROM calibration_corrections"
            " WHERE sport = ? AND market_type = ? AND forecaster = 'statistical'"
            " ORDER BY version DESC LIMIT 1", (sport, market_type)).fetchone()
        settled = len(calibration.resolved(
            conn, sport=sport, market_type=market_type,
            prop_type=calibration.prop_type_of(sport, market),
            predictor="statistical"))
        active = correction.active_correction(
            conn, sport=sport, market_type=market_type, forecaster="statistical")
        shown, version = correction.shown_claim(
            conn, sport=sport, market_type=market_type,
            forecaster="statistical", claim=0.70)
        moved = drift.report(conn, sport=sport, market_type=market_type)
        rows.append({
            "market": market,
            "market_label": language.humanise(market),
            "n": settled,
            "minimum": correction.MIN_TRAIN,
            "fitted_utc": latest["fitted_utc"] if latest else None,
            "slope": latest["slope"] if latest else None,
            "intercept": latest["intercept"] if latest else None,
            "active": bool(active),
            "version": version,
            "n_train": latest["n_train"] if latest else 0,
            "status_words": language.correction_status_line(
                latest is not None, settled, correction.MIN_TRAIN,
                latest["fitted_utc"] if latest else None, bool(active),
                last_refit=last_refit,
                n_train=(latest["n_train"] if latest else 0) or 0),
            "meaning_words": language.correction_meaning_line(0.70, shown),
            "drift_words": moved.get("line"),
            "drift_n": moved.get("n", 0),
        })
    return {
        "sport": sport,
        "n": sum(r["n"] for r in rows),
        "last_refit": last_refit,
        "categories": rows,
        "never_rewrites": language.correction_never_rewrites_line(),
        "note": (
            "The correction is fitted from this record's own claims and "
            "outcomes once a category has fifty settled rows, and applied to "
            "what gets written next. The drift figure is where the market's "
            "line went after a disagreement, gated at fifty pairs. Both have "
            "been running since they were built; this panel is the first time "
            "either has been visible."
        ),
    }
