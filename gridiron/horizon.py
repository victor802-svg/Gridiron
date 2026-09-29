"""What a market's gate can still reach before its season ends.

RULING R3, made concrete. `GAME_TYPES` stays `("R",)`, so the MLB record ends on
the last day of the regular season and October is a different question. That has
a consequence the interface has to say out loud rather than imply: **some gates
cannot clear.**

A gate that will not be reached is not the same as a gate that has not been
reached yet, and showing them the same way is the quiet kind of dishonesty this
project exists to avoid. "6 of 100" reads as progress. "6 of 100 · ~60 expected
· season ends 09-27" reads as what it is.

The arithmetic is deliberately crude and deliberately stated: slates remaining,
times the rate this market has actually been writing at, plus what already
exists. It is an extrapolation from a small sample and it says so. The point is
not to predict the final number precisely; it is to make the difference between
"slow" and "impossible" visible without the reader doing arithmetic in their
head.
"""

from __future__ import annotations

import sqlite3

from . import config


def slates_remaining(conn: sqlite3.Connection, sport: str, season: int,
                     event_tier: str | None = None) -> int:
    """Distinct future slates still on the calendar for this sport's season.

    A SLATE IS WHAT THE SPORT WRITES BY: `games.week`, which is a week for
    football and basketball, a day for baseball and college football, a card
    for the fights. It is the same column `_written_so_far` divides by, and
    it has to be, because the outlook multiplies one by the other.

    Until 2026-09-05 this counted calendar days -- and UTC days at that, so a
    Sunday night football game was its own slate. The NFL record showed 73
    slates remaining against a rate measured per week, and the Record page
    projected ~3,504 resolutions from 48 written in week one. Eighteen weeks
    of 48 is 864.

    ONE CARD'S SLATES FOR ONE CARD'S RATE (operator question 14, 2026-09-27).
    A UFC outlook is one card's from this date, paced by that card's
    forecasts per card it wrote on, so it is multiplied by that card's cards
    still to come: a Contender Series rate times every card left on the
    calendar -- 3 of the 14 on 27 September -- would be the unit mismatch
    this function's history is about, one level down. `event_tier` is None
    for a sport that does not split below the market, and for the
    at-the-line outlook, which does not pass one (FOLLOWUPS).
    """
    sql = ("SELECT COUNT(DISTINCT week)"
           " FROM games WHERE sport = ? AND season = ? AND status = 'scheduled'")
    params: list = [sport, season]
    if event_tier is not None:
        # THE CARD, reached through the bout as every UFC count reaches it.
        sql += (" AND EXISTS (SELECT 1 FROM ufc_bouts b JOIN ufc_events e"
                "               ON e.id = b.event_id"
                "              WHERE b.id = games.id AND e.event_tier = ?)")
        params.append(event_tier)
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0)


def season_ends(conn: sqlite3.Connection, sport: str, season: int) -> str | None:
    row = conn.execute(
        "SELECT MAX(COALESCE(league_date, substr(kickoff_utc, 1, 10)))"
        " FROM games WHERE sport = ? AND season = ?",
        (sport, season),
    ).fetchone()
    return row[0] if row and row[0] else None


# ---------------------------------------------------------------------------
# ONE FORECASTER'S STANDING QUESTIONS, THE CURVE'S OWN (operator question 14,
# ruled 2026-09-27, 3 of 3: "Every count on the Record page that states a
# gate distance is rebuilt per forecaster (per tier for UFC) and per distinct
# bet, through its record's standing rule.")
# ---------------------------------------------------------------------------

#: THE TWO BLIND FORECASTERS -- `predictions.predictor`'s own CHECK, and the
#: two blind curves the Record page draws for every market.
FORECASTERS = tuple(config.FORECASTER_LABELS)


class PooledCount(ValueError):
    """An outlook's count asked for without saying whose, in no one declared
    market, or across tiers."""


def refuse_a_pooled_count(sport: str, market, predictor, event_tier) -> None:
    """The questions every count of a blind outlook must answer first.

    ONE FORECASTER, ONE MARKET AS THE RECORD NAMES IT, AND FOR A SPORT THAT
    SPLITS BELOW THE MARKET ONE TIER (LAW 4, LAW 6; operator question 14,
    2026-09-27). Asked in the door, so a pooled count cannot be made by
    leaving an argument out: until this date the forecaster was a default
    argument and UFC's three cards were one count.
    """
    config.require_sport(sport, "horizon.standing_questions")
    if predictor not in FORECASTERS:
        raise PooledCount(
            f"LAW 4 / LAW 6: a count of {sport} blind forecasts for an outlook "
            f"was asked for forecaster {predictor!r}. The statistical model's "
            f"questions and the reasoning pass's are counted apart and never "
            f"pooled: name one of {list(FORECASTERS)}.")
    declared = config.SPORT_MARKETS.get(sport, ())
    if market not in declared:
        raise PooledCount(
            f"LAW 4: a count of {sport} blind forecasts for an outlook was "
            f"asked for market {market!r}, which is not one of {sport}'s "
            f"declared markets {list(declared)}. A prop is counted by its own "
            f"type: 'prop' is every prop type in one count.")
    tiers = config.event_tiers(sport)
    if tiers and event_tier not in tiers:
        raise PooledCount(
            f"LAW 6: a count of {sport} blind forecasts for an outlook names "
            f"event tier {event_tier!r}, not one of {sport}'s declared tiers "
            f"{list(tiers)}; tiers are reported side by side, never summed.")
    if not tiers and event_tier is not None:
        raise PooledCount(
            f"LAW 6: {sport} declares no event tiers, so a count naming tier "
            f"{event_tier!r} counts nothing that exists.")


def standing_questions(conn: sqlite3.Connection, *, sport: str, market: str,
                       predictor: str,
                       event_tier: str | None = None) -> list[dict]:
    """THE ONE DOOR every count of a blind outlook goes through: ONE
    forecaster's STANDING forecasts in one market (and, for UFC, on one card),
    settled or not, with the season and slate each was written in.

    THE CURVE'S OWN ROWS. The curve beside the outlook counts
    `calibration.resolved`: one standing row per question
    (`calibration.standing_row_clause`, the latest written before the start,
    a withdrawn one never -- and from 2026-09-29 a final pass written before
    the start first, operator question 27), for one forecaster, market and
    card. This door
    asks the same filters and the same clause without the settled condition,
    so its settled rows are that curve's rows and the outlook's count is the
    curve's n -- which `calibration.assert_no_pooled_outlooks` checks rather
    than trusts.

    THE OPERATOR'S RULING of 2026-09-27 (question 14, 3 of 3). Until this
    date the outlook counted every row of the market this season -- a
    question's morning and final pass each, and for UFC every card -- by a
    query of its own, and its forecaster was a default argument: on 26
    September MLB moneyline said "330 of 100" beside a curve of 233, spread
    and total "272 of 100" beside 175 and 182, and UFC "62 of 100" beside a
    Numbered-card curve of 0.

    Each row carries its market as the record names it, its forecast's key
    (`bet.columns`: the one function's, operator question 17, 2026-09-28) and
    its card read off its own bout, so a payload counts beside the door how
    many distinct bets it holds (`bet.count`) and whose.
    """
    from . import bet
    from .calibration import market_type_of, prop_type_of, standing_row_clause

    refuse_a_pooled_count(sport, market, predictor, event_tier)
    prop = prop_type_of(sport, market)
    tiers = config.event_tiers(sport)
    # THE CARD, READ OFF THE ROW'S OWN BOUT, so a door that stopped filtering
    # by card is seen in the payload rather than trusted.
    tier_column = (
        "(SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
        "   ON e.id = b.event_id WHERE b.id = p.game_id)"
        if tiers else "NULL")
    where = ["p.sport = ?", "p.market_type = ?", "p.predictor = ?"]
    params: list = [sport, market_type_of(sport, market), predictor]
    if prop:
        where.append("p.prop_type = ?")
        params.append(prop)
    if event_tier is not None:
        # LAW 6 ONE LEVEL DOWN (R2, 2026-09-03), reached through the bout to
        # the card, exactly as `calibration.resolved` reaches it.
        where.append(
            "EXISTS (SELECT 1 FROM ufc_bouts b JOIN ufc_events e"
            "          ON e.id = b.event_id"
            "         WHERE b.id = p.game_id AND e.event_tier = ?)")
        params.append(event_tier)
    rows = conn.execute(
        f"SELECT p.id, {bet.columns('p')},"
        "       p.resolved_utc, g.season, g.week,"
        f"      {tier_column} AS event_tier"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE {' AND '.join(where)}{standing_row_clause(False)}"
        " ORDER BY p.id", params).fetchall()
    return [dict(r, market=market, settled=r["resolved_utc"] is not None)
            for r in rows]


def settled(rows) -> list:
    """The standing forecasts that carry an outcome: ONE predicate for every
    settled count of an outlook."""
    return [r for r in rows if r["settled"]]


def _written_so_far(rows: list, season: int) -> tuple[int, int, int]:
    """(written this season, slates that wrote any, settled) for one
    forecaster's standing questions in one market -- and one card.

    READ OFF THE DOOR'S ROWS, never a query of its own (2026-09-27): the
    settled count is every settled standing question, whatever its season,
    because that is what the curve and the gate count; the pace is this
    season's, the questions written in it over the slates they were written
    on -- `week`, the unit `slates_remaining` counts.
    """
    this_season = [r for r in rows if r["season"] == season]
    slates = {r["week"] for r in this_season}
    return len(this_season), len(slates), len(settled(rows))


def _asked(conn: sqlite3.Connection, sport: str, market: str, predictor: str,
           event_tier, season: int) -> tuple[list, dict]:
    """One forecaster's standing questions through the door, and the same
    cell recounted without it by the one key (`gridiron.recount`, operator
    question 17, 2026-09-28) -- in one read, so the two see the same rows."""
    from . import db, recount
    from .calibration import market_type_of, prop_type_of

    with db.one_instant(conn):
        rows = standing_questions(conn, sport=sport, market=market,
                                  predictor=predictor, event_tier=event_tier)
        again = recount.outlook(conn, sport=sport,
                                market_type=market_type_of(sport, market),
                                prop_type=prop_type_of(sport, market),
                                predictor=predictor, event_tier=event_tier,
                                season=season)
        ends = season_ends(conn, sport, season)
    return rows, dict(again, season_ends=ends)


def _counted(sport: str, market: str, predictor: str, event_tier,
             rows: list, season: int, again: dict) -> dict:
    """The part of an outlook every kind shares: its counts, whose they are,
    and how many distinct bets they hold -- counted beside the door
    (`bet.count`) and again without it (`recounted`, `recounted_written`)."""
    from . import bet

    ends = again["season_ends"]
    written, slates_used, resolved = _written_so_far(rows, season)
    return {
        "sport": sport,
        "record": "rung",
        "market": market,
        "predictor": predictor,
        "event_tier": event_tier,
        "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
        "resolved": resolved,
        "n": resolved,
        "written": written,
        "slates_used": slates_used,
        "season_ends": ends,
        # NOTHING THIS SEASON IS NOT NOTHING EVER (item 6's prover,
        # 2026-09-26): `resolved` counts every season's questions, so a line
        # with no rate this season must not deny the ones it has counted.
        "written_before": any(r["season"] != season for r in rows),
        "distinct_bets": bet.count(settled(rows)),
        "distinct_bets_written": bet.count(
            [r for r in rows if r["season"] == season]),
        "recounted": again["settled"],
        "recounted_written": again["written"],
        "forecasters_counted": sorted({r["predictor"] for r in rows}),
        "tiers_counted": sorted({r["event_tier"] for r in rows
                                 if r["event_tier"] is not None}),
    }


def outlook_words(out: dict) -> str:
    """The sentence an outlook states, from its own numbers and nothing else:
    the one composition the builder writes and the guard reads again."""
    from . import language

    if out.get("retired"):
        return language.retired_outlook_line(
            out["resolved"], out["gate"], out["retired"]["retired"])
    if out.get("routed_off"):
        return language.llm_routed_off_line(
            out["resolved"], out["gate"], out["routed_off"]["since"])
    return language.market_outlook_line(
        out["resolved"], out["gate"], out.get("expected"), out.get("season_ends"),
        written_before=bool(out.get("written_before")))


def market_outlook(conn: sqlite3.Connection, sport: str, market: str, *,
                   predictor: str, event_tier: str | None = None,
                   season: int | None = None) -> dict:
    """Whether ONE forecaster's 100-resolution gate in this market -- on one
    card, for UFC -- can clear before the season ends.

    Every figure carries the sample it came from (LAW 4). `expected` is an
    extrapolation and is labelled one; `reachable` is the judgement the
    interface renders, and it is only ever False when the arithmetic says so
    with the rate measured over at least one slate.

    THE CURVE'S OWN COUNT (operator question 14, ruled 2026-09-27, 3 of 3).
    The forecaster is required and the rows are the door's
    (`standing_questions`): `resolved` is the curve's n, the pace is this
    season's standing questions over the slates they were written on, and
    the multiplier is the card's own slates still to come.
    """
    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON) \
        if season is None else season
    rows, again = _asked(conn, sport, market, predictor, event_tier, season)
    out = _counted(sport, market, predictor, event_tier, rows, season, again)
    resolved, gate = out["resolved"], out["gate"]

    # A RETIRED MARKET PROJECTS NOTHING (R1, 2026-09-05): its settled count is
    # the final count, and a line reading "~446 expected" would be false.
    retired = config.retired_market(sport, market)
    if retired:
        out.update({
            "slates_remaining": 0, "per_slate": None, "expected": resolved,
            "expected_is_an_extrapolation": False, "retired": retired,
            "reachable": resolved >= gate,
        })
        out["message"] = outlook_words(out)
        return out

    remaining = slates_remaining(conn, sport, season, event_tier)
    per_slate = (out["written"] / out["slates_used"]) if out["slates_used"] else None
    expected = None
    if per_slate is not None:
        expected = int(round(resolved + per_slate * remaining))
    out.update({
        "slates_remaining": remaining,
        "per_slate": round(per_slate, 2) if per_slate is not None else None,
        "expected": expected,
        "expected_is_an_extrapolation": True,
        # NO RATE IS NOT "CANNOT CLEAR" (R3, 2026-09-05): absent, degraded
        # and declined are three states, and nothing written this season is
        # the first.
        "reachable": None if per_slate is None else expected >= gate,
    })
    out["message"] = outlook_words(out)
    return out


def expected_from(out: dict) -> int | None:
    """What an outlook's own counts project, worked out again from them --
    the arithmetic `market_outlook` states, for the guard to compare."""
    if out.get("retired") or out.get("routed_off"):
        return out.get("resolved")
    written, slates = out.get("written"), out.get("slates_used")
    if not slates:
        return None
    return int(round(out["resolved"]
                     + written / slates * (out.get("slates_remaining") or 0)))


def zero_write_line(market: str, asked: int, floor: float) -> str:
    """What a slate says about a market it wrote nothing in (ruling 1).

    A market where the model never reached the floor at the line the market
    actually quotes is the floor telling the truth, not a defect, and the card
    says so in words rather than leaving a silent gap that reads as a failure to
    find questions.
    """
    from . import language

    if asked:
        return ""
    return (
        f"{language.humanise(market)}: 0 asked — model never reached "
        f"{round(floor * 100)}% at the market's line"
    )


def llm_routed_off_outlook(conn: sqlite3.Connection, sport: str, market: str,
                           *, event_tier: str | None = None,
                           season: int | None = None) -> dict:
    """The outlook for an LLM category whose market the reasoning pass no
    longer asks (ruling E1, 2026-09-06): the same shape as a retired market's,
    so the Record draws it with the same component.

    THE REASONING PASS'S OWN CURVE'S COUNT, one card's for UFC (operator
    question 14, 2026-09-27): read through the same door as every blind
    outlook, so "N settled is the final count" is the n of the curve it sits
    under. Until this date it counted every row of the market on every card,
    and UFC's Contender Series and Numbered-card rows said "14 of 100 ...
    the final count" beside curves of 0.
    """
    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON) \
        if season is None else season
    rows, again = _asked(conn, sport, market, "llm", event_tier, season)
    out = _counted(sport, market, "llm", event_tier, rows, season, again)
    out.update({
        "slates_remaining": 0, "per_slate": None, "expected": out["resolved"],
        "expected_is_an_extrapolation": False,
        "routed_off": {"since": config.LLM_ROUTING_DECLARED},
        "reachable": out["resolved"] >= out["gate"],
    })
    out["message"] = outlook_words(out)
    return out


def at_the_line_outlook(conn: sqlite3.Connection, sport: str, market: str, *,
                        predictor: str, bets: list,
                        event_tier: str | None = None,
                        season: int | None = None) -> dict:
    """When the at-the-line gate opens, at the rate claims are actually being
    written (E4, 2026-09-06).

    THE SAME SHAPE AS A MARKET'S OUTLOOK, and deliberately a separate count. A
    claim needs three things a prediction does not -- a frozen distribution, a
    ladder from the venue, and a price on it -- so its gate is always further
    away than the rung gate for the same market, and projecting one from the
    other would flatter by exactly the size of the coverage hole.

    THE CURVE'S OWN BETS, NOT A QUERY OF ITS OWN (GRIDIRON_REPAIR item 6,
    2026-09-26). `bets` is the list `at_the_line.standing_claims` gave the
    curve beside this line -- one forecaster's, one claim per bet -- so
    `resolved` is the curve's n by construction: every settled bet, whatever
    its season, because that is what the gate counts. The pace is this
    season's: the bets written in it, over the slates (`games.week`) they
    were written on -- the unit `slates_remaining` counts. Until this date
    the outlook counted every forecaster's claims itself and said "128 of
    100 · ~228 expected" beside a curve of 80 (2026-09-23).
    """
    from . import language
    from .market import at_the_line

    season = config.SPORT_CURRENT_SEASON.get(sport, config.CURRENT_SEASON) \
        if season is None else season
    this_season = [b for b in bets if b["season"] == season]
    written = len(this_season)
    slates_used = len({b["week"] for b in this_season})
    resolved = len(at_the_line.settled(bets))
    remaining = slates_remaining(conn, sport, season)
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    per_slate = (written / slates_used) if slates_used else None
    expected = int(round(resolved + per_slate * remaining)) if per_slate else None
    out = {
        "sport": sport, "market": market, "predictor": predictor,
        "event_tier": event_tier, "gate": gate, "resolved": resolved,
        "written": written, "n": resolved, "slates_used": slates_used,
        "slates_remaining": remaining, "season_ends": season_ends(conn, sport, season),
        "per_slate": round(per_slate, 2) if per_slate is not None else None,
        "expected": expected, "expected_is_an_extrapolation": True,
        "record": "at_the_line",
    }
    if per_slate is None:
        out["reachable"] = None
        # NOTHING THIS SEASON IS NOT NOTHING EVER (the prover, 2026-09-26):
        # `resolved` counts every season's bets, so the words must not deny
        # the claims it has just counted.
        out["message"] = language.at_the_line_pace_line(
            resolved, gate, None, None, written_before=bool(bets))
        return out
    out["reachable"] = expected >= gate
    out["message"] = language.at_the_line_pace_line(
        resolved, gate, expected, out["season_ends"])
    return out
