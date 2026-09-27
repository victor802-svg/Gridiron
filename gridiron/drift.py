"""Does the market move toward the model, or away from it?

THE QUESTION D1 COULD NOT TEST. When the model disagrees with the published
line, two stories fit the same data and they have opposite meanings:

  * the model sees something early and the market later agrees — the line
    drifts TOWARD the model's number, and the model's disagreements are
    information arriving before the market prices it;
  * the market's information is simply better — the line drifts AWAY, and the
    disagreement was the model being wrong in a way the market was not.

A single snapshot taken when the prediction is written cannot tell them apart,
because it has nothing to compare against. Two snapshots can: the line when the
forecast was made, and the line near kickoff.

WHAT THIS MODULE MUST NOT DO
============================
It must not conclude. The gate is fifty drift pairs in a category, and below it
this reports the count and nothing else — no direction, no fraction, no
adjective. That is not modesty, it is the same rule as everywhere else in the
record: a number without a sample behind it is a claim, and the interesting
direction is the one a reader will remember whether or not it was earned.

There are deliberately no conclusions written into these comments either. The
number decides, later, with an N beside it.

BOTH LOOKS HAPPEN AFTER THE PREDICTION EXISTS
=============================================
LAW 1 is untouched and its structure is unchanged: `market_snapshots` rows
still require a prediction that predates them, enforced by trigger, and the
second look obeys that exactly as the first does. The blind window is about
what the model may see BEFORE it commits; this is about what the market did
afterwards, which the model never sees at all.
"""

from __future__ import annotations

import sqlite3

from . import config, language

#: Drift pairs needed in a category before any direction is reported.
MIN_PAIRS = 50

#: How far apart the model and the market must be for a game to count as a
#: DISAGREEMENT. Below this the two are saying the same thing and the movement
#: between them is noise about nothing.
MIN_DISAGREEMENT = 0.05


# ---------------------------------------------------------------------------
# ONE PAIR PER BET, PER FORECASTER, THROUGH THE STANDING RULE (operator
# question 14, ruled 2026-09-27, 2 of 3: "Every count on the Record page that
# states a gate distance is rebuilt per forecaster (per tier for UFC) and per
# distinct bet, through its record's standing rule.")
# ---------------------------------------------------------------------------

#: THE FORECASTERS WHOSE DISAGREEMENTS CAN BE COUNTED: the two the Record page
#: reports, each apart. Read from `config`, not written out again here.
FORECASTERS = tuple(config.FORECASTER_LABELS)

#: WHOSE DRIFT THE RECORD PAGE PAINTS (2026-09-27). The learning panel and the
#: gate list have only ever shown the statistical model's media-line drift, as
#: the correction beside it is the statistical model's. The reasoning pass's
#: pairs are counted by the same door when it is named -- under the fifty in
#: every market on 27 September (FOLLOWUPS) -- and are not painted: the ruling
#: rebuilds the counts the page states and adds none. Adding "llm" here would
#: paint them, each row naming its forecaster.
PAGE_FORECASTERS = ("statistical",)


class PooledCount(ValueError):
    """A count of drift pairs asked for without saying whose, in no one
    declared market, or across tiers."""


def refuse_a_pooled_count(sport: str, market, predictor, event_tier) -> None:
    """The questions every count of drift pairs must answer first.

    ONE FORECASTER, ONE MARKET AS THE RECORD NAMES IT, AND FOR A SPORT THAT
    SPLITS BELOW THE MARKET ONE TIER (LAW 4, LAW 6; operator question 14,
    2026-09-27). Asked in the door, so a pooled count cannot be made by
    leaving an argument out: until this date the forecaster had a default, a
    prop was counted by its `market_type` -- 'prop' for every prop type at
    once -- and UFC's three cards were one count.
    """
    config.require_sport(sport, "drift.standing_pairs")
    if predictor not in FORECASTERS:
        raise PooledCount(
            f"LAW 4 / LAW 6: a count of {sport} drift pairs was asked for "
            f"forecaster {predictor!r}. The statistical model's disagreements "
            f"and the reasoning pass's are counted apart and never pooled: "
            f"name one of {list(FORECASTERS)}.")
    declared = config.SPORT_MARKETS.get(sport, ())
    if market not in declared:
        raise PooledCount(
            f"LAW 4: a count of {sport} drift pairs was asked for market "
            f"{market!r}, which is not one of {sport}'s declared markets "
            f"{list(declared)}. A prop is counted by its own type: 'prop' is "
            f"every prop type in one count, which describes none of them.")
    tiers = config.event_tiers(sport)
    if tiers and event_tier not in tiers:
        raise PooledCount(
            f"LAW 6: a count of {sport} drift pairs names event tier "
            f"{event_tier!r}, not one of {sport}'s declared tiers "
            f"{list(tiers)}; tiers are reported side by side, never summed.")
    if not tiers and event_tier is not None:
        raise PooledCount(
            f"LAW 6: {sport} declares no event tiers, so a count naming tier "
            f"{event_tier!r} counts nothing that exists.")


def bet_of(pair) -> tuple:
    """Which bet a pair is on: its game and market -- and the player, for a
    prop -- without the forecaster, the pass or the rung.

    THE AT-THE-LINE RECORD'S KEY (GRIDIRON_REPAIR item 6, 2026-09-26), for the
    same reason: two standing questions of one game at two rungs read ONE
    published line moving once. The key the door keeps one pair per, and the
    key a payload's `distinct_bets` counts, so there is one key.
    """
    return (pair["game_id"], pair["market"],
            pair["subject"] if pair["prop_type"] else None)


def count_of_bets(pairs) -> int:
    """How many distinct bets a list of pairs is on."""
    return len({bet_of(p) for p in pairs})


def _last_before_the_start(row) -> tuple:
    """The order in which a bet's standing forecasts stand: one written before
    the start beats one written after it (a backtest's), then the later, the
    id breaking a tie -- item 6's rule for the claim a bet keeps."""
    before = row["kickoff_utc"] is None or row["created_utc"] <= row["kickoff_utc"]
    return (before, row["created_utc"], row["id"])


def standing_pairs(conn: sqlite3.Connection, *, sport: str, market: str,
                   predictor: str,
                   event_tier: str | None = None) -> list[dict]:
    """THE ONE DOOR every count of the media line's drift goes through: ONE
    PAIR PER BET, PER FORECASTER, through the blind record's standing rule.

    A pair is a forecast with both looks at the published line -- the one
    taken when it was written (`open_at_predict`) and the one near the start
    (`near_start`) -- that disagreed with the first look by
    `MIN_DISAGREEMENT` or more. `toward` is the signed movement of the
    market's implied probability in the direction the forecaster was
    pointing: positive means the line moved toward its number, negative away
    from it. The sign is derived from the two stored numbers rather than
    assumed from which side it took.

    THROUGH THE STANDING RULE (operator question 14, ruled 2026-09-27, 2 of
    3). Every forecast writes its own first look and is given its own second,
    so a question's morning and final pass were two pairs, and until this
    date every one was counted: on 26 September MLB moneyline said "over 75
    games", past the fifty, for 58 questions, 48 of them standing rows. The
    candidates are now the forecaster's STANDING forecasts
    (`calibration.standing_row_clause`: the latest written before the start,
    a withdrawn one never), so a superseded pass's pair is never counted --
    and a question whose standing forecast has no second look is not counted
    either, even if a superseded pass of it had one.

    ONE PER BET (`bet_of`). Two standing questions of one game at two rungs --
    the live NCAAF point spread record holds twelve such games, the morning
    pass's rung and a later pass's -- read one line moving once, and counting
    both counted that movement twice ("over 79 games" were 78 questions on 66
    games on 27 September). The bet's forecast is its LAST standing one
    written before the start, the id breaking a tie, and the bet is counted
    if that forecast has both looks and disagreed: the forecaster's last word
    on the game is the one the market is measured against, and an earlier
    rung is not its fallback.

    Each pair carries its forecaster, its market as the record names it (the
    prop type, or the market), its bet's keys and its card read off its own
    bout, so a payload counts beside the door how many bets it holds and
    whose.
    """
    from .calibration import market_type_of, prop_type_of, standing_row_clause

    refuse_a_pooled_count(sport, market, predictor, event_tier)
    prop = prop_type_of(sport, market)
    tiers = config.event_tiers(sport)
    # THE CARD, READ OFF THE ROW'S OWN BOUT, so a door that stopped filtering
    # by tier is seen in the payload rather than trusted (as the priced door
    # reads it, 2026-09-27).
    tier_column = (
        "(SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
        "   ON e.id = b.event_id WHERE b.id = p.game_id)"
        if tiers else "NULL")
    tier_clause = ""
    params: list = [sport, market_type_of(sport, market), prop or "", predictor]
    if event_tier is not None:
        # LAW 6 ONE LEVEL DOWN (R2, 2026-09-03), reached through the bout to
        # the card, exactly as `calibration.resolved` reaches it.
        tier_clause = (
            " AND EXISTS (SELECT 1 FROM ufc_bouts b JOIN ufc_events e"
            "               ON e.id = b.event_id"
            "              WHERE b.id = p.game_id AND e.event_tier = ?)")
        params.append(event_tier)
    rows = conn.execute(
        "SELECT p.id, p.predictor, p.game_id, p.subject, p.line_asked,"
        "       p.created_utc, p.model_prob, p.calibrated_prob, g.kickoff_utc,"
        "       o.implied_prob AS opened, o.fetched_utc AS opened_utc,"
        "       n.implied_prob AS near, n.fetched_utc AS near_utc,"
        f"      {tier_column} AS event_tier"
        "  FROM predictions p"
        "  JOIN games g ON g.id = p.game_id"
        "  LEFT JOIN market_snapshots o"
        "    ON o.prediction_id = p.id AND o.kind = 'open_at_predict'"
        "  LEFT JOIN market_snapshots n"
        "    ON n.prediction_id = p.id AND n.kind = 'near_start'"
        " WHERE p.sport = ? AND p.market_type = ?"
        "   AND IFNULL(p.prop_type, '') = ? AND p.predictor = ?"
        f"{tier_clause}{standing_row_clause(False)}",
        params).fetchall()

    kept: dict[tuple, dict] = {}
    for row in rows:
        pair = dict(row)
        pair.update(sport=sport, market=market, prop_type=prop)
        bet = bet_of(pair)
        if bet not in kept or (_last_before_the_start(row)
                               > _last_before_the_start(kept[bet])):
            kept[bet] = pair

    out = []
    for row in sorted(kept.values(), key=lambda r: r["id"]):
        if row["opened"] is None or row["near"] is None:
            continue
        claim = (row["calibrated_prob"] if row["calibrated_prob"] is not None
                 else row["model_prob"])
        disagreement = claim - row["opened"]
        if abs(disagreement) < MIN_DISAGREEMENT:
            continue
        movement = row["near"] - row["opened"]
        # Toward the model is movement sharing the sign of the disagreement.
        toward = movement if disagreement > 0 else -movement
        out.append({
            "prediction_id": row["id"],
            "predictor": row["predictor"],
            "sport": sport,
            "market": market,
            "prop_type": prop,
            "game_id": row["game_id"],
            "subject": row["subject"],
            "line_asked": row["line_asked"],
            "event_tier": row["event_tier"],
            "claim": claim,
            "opened": row["opened"],
            "opened_utc": row["opened_utc"],
            "near": row["near"],
            "near_utc": row["near_utc"],
            "disagreement": round(disagreement, 6),
            "movement": round(movement, 6),
            "toward": round(toward, 6),
        })
    return out


def _progress(n: int) -> dict:
    """How far one category's count is from the fifty, in the page's words."""
    return language.progress(n, MIN_PAIRS, noun="pairs",
                             cleared_note="enough pairs to report a direction")


def report(conn: sqlite3.Connection, *, sport: str, market: str,
           predictor: str, event_tier: str | None = None) -> dict:
    """The drift figure for one category -- one market as the record names
    it, one forecaster, and for UFC one card -- or the count and nothing else.

    Below `MIN_PAIRS` this returns no direction and no fraction. A reader who
    is told "the market moved toward the model 61% of the time" over nine games
    will remember the 61% and not the nine.

    ONE DOOR, AND ITS COUNTS BESIDE IT (operator question 14, 2026-09-27).
    The pairs come from `standing_pairs`, one per bet; `distinct_bets`,
    `forecasters_counted` and `tiers_counted` are read off the pairs' own
    keys rather than trusted to the door, so a door that let a bet in twice,
    or another forecaster's pairs, or another card's, is seen by
    `assert_no_pooled_drift_counts` in the builders that serve this.
    """
    from .calibration import market_type_of, prop_type_of

    found = standing_pairs(conn, sport=sport, market=market,
                           predictor=predictor, event_tier=event_tier)
    n = len(found)
    moved_toward = sum(1 for p in found if p["toward"] > 0)
    filters = {"sport": sport, "market": market, "predictor": predictor,
               "record": "drift"}
    if prop_type_of(sport, market):
        filters["prop_type"] = market
    if event_tier is not None:
        filters["event_tier"] = event_tier
    base = {
        "sport": sport,
        "record": "drift",
        "market": market,
        "market_type": market_type_of(sport, market),
        "predictor": predictor,
        "event_tier": event_tier,
        "category": " / ".join([market] + ([event_tier] if event_tier else [])
                               + [predictor, "drift"]),
        "category_label": language.drift_category_label(
            sport, market, predictor, event_tier),
        "filters": filters,
        "n": n,
        # COUNTED BESIDE THE DOOR, NOT BY IT (2026-09-27).
        "distinct_bets": count_of_bets(found),
        "forecasters_counted": sorted({p["predictor"] for p in found}),
        "tiers_counted": sorted({p["event_tier"] for p in found
                                 if p["event_tier"] is not None}),
        "min_pairs": MIN_PAIRS,
        "min_disagreement": MIN_DISAGREEMENT,
        # HOW CLOSE THIS MARKET IS to having a direction worth reporting
        # (GRIDIRON_13 P1). The same component the tier rows and the
        # correction gates use, so "close" means one thing on this page.
        "progress": _progress(n),
        "line": language.drift_line(
            sport, market, n, moved_toward if n >= MIN_PAIRS else None,
            MIN_PAIRS, MIN_DISAGREEMENT, event_tier),
    }
    if n < MIN_PAIRS:
        return base
    base.update({
        "toward_fraction": round(moved_toward / n, 4),
        "moved_toward": moved_toward,
        "mean_movement": round(sum(p["toward"] for p in found) / n, 6),
    })
    return base


#: What a category reports only once it has its fifty: the direction.
DIRECTION_KEYS = ("toward_fraction", "moved_toward", "mean_movement")


def assert_no_pooled_drift_counts(payload: dict) -> None:
    """Every drift count on the Record page is ONE forecaster's BETS, once
    each, through the blind record's standing rule -- and for UFC one card's.

    The operator's ruling on question 14 (2026-09-27, 2 of 3): "Every count
    on the Record page that states a gate distance is rebuilt per forecaster
    (per tier for UFC) and per distinct bet, through its record's standing
    rule." Checked on the payload (`{"sport", "categories"}`), as
    `calibration.assert_no_pooled_priced_counts` checks the priced record's,
    and `calibration.assert_no_merged_categories` runs first, so the sport,
    the market (a prop by its own type), the forecaster and the tier are one
    rule for every record.

    Then, by name: a category of another record; one naming no forecaster,
    or counting another's pairs; one counting another card's pairs, or
    naming a card in a sport that has none; one category twice; more pairs
    than distinct bets (a question's two passes, two rungs of one game); a
    direction below the gate; a progress line or a sentence stating another
    count than its own (the page said "over 75 games" for 48 standing rows
    on 26 September); and a total across categories. Raised inside
    `views.drift_report` and `views.learning`, so the API answers 500 rather
    than serve a pooled count.
    """
    from . import calibration

    law = "LAW 4 / LAW 6 IN THE LINE'S DRIFT"
    calibration.assert_no_merged_categories(payload)
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    if "n" in payload:
        raise calibration.MergedCurve(
            f"{law}: the drift payload carries a total 'n' of "
            f"{payload['n']!r}, a sum across its categories, which is "
            f"nobody's record.")
    seen: set = set()
    for category in payload.get("categories") or []:
        what = f"drift category {category.get('category')!r}"
        if category.get("record") != "drift":
            raise calibration.MergedRecord(
                f"{what} belongs to the {category.get('record')!r} record and "
                f"is filed under the line's drift.")
        named = category.get("predictor")
        filtered = (category.get("filters") or {}).get("predictor")
        if named not in FORECASTERS or filtered != named:
            raise calibration.MergedCurve(
                f"{law}: {what} names forecaster {named!r} (filtered by "
                f"{filtered!r}). The statistical model's disagreements and "
                f"the reasoning pass's are counted apart and never pooled.")
        counted = category.get("forecasters_counted")
        if counted not in ([], [named]):
            raise calibration.MergedCurve(
                f"{law}: {what} is the {named!r} forecaster's and counts pairs "
                f"on the forecasts of {counted!r}: two forecasters pooled into "
                f"one count.")
        tier, cards = category.get("event_tier"), category.get("tiers_counted")
        if tiers:
            if tier not in tiers or cards not in ([], [tier]):
                raise calibration.MergedCurve(
                    f"{law}: {what} names event tier {tier!r} and counts bouts "
                    f"on {cards!r}; {sport}'s tiers {list(tiers)} are reported "
                    f"side by side, never summed.")
        elif tier is not None or cards not in ([], None):
            raise calibration.MergedCurve(
                f"{law}: {what} names event tier {tier!r} in {sport}, which "
                f"declares none.")
        key = (category.get("market"), tier, named)
        if key in seen:
            raise calibration.MergedCurve(
                f"{law}: {what} is counted twice in one payload.")
        seen.add(key)
        n, bets = category.get("n"), category.get("distinct_bets")
        if bets is None or n != bets:
            raise calibration.MergedCurve(
                f"{law}: {what} counts {n} pairs for {bets} distinct "
                f"bet{'' if bets == 1 else 's'}. A game is counted once per "
                f"forecaster, on its last standing forecast, however many "
                f"passes or rungs asked it.")
        if n < MIN_PAIRS and any(k in category for k in DIRECTION_KEYS):
            raise calibration.MergedCurve(
                f"{law}: {what} reports a direction on {n} of the "
                f"{MIN_PAIRS} pairs it needs first.")
        if category.get("progress") != _progress(n):
            raise calibration.MergedCurve(
                f"{law}: {what}'s progress line says "
                f"{(category.get('progress') or {}).get('line')!r}, which is "
                f"not its own count of {n}.")
        said = language.drift_line(
            sport, category.get("market"), n, category.get("moved_toward"),
            MIN_PAIRS, MIN_DISAGREEMENT, tier)
        if category.get("line") != said:
            raise calibration.MergedCurve(
                f"{law}: {what}'s sentence says {category.get('line')!r}, "
                f"which is not its own count of {n}.")


# ---------------------------------------------------------------------------
# THE VENUE'S OWN PAIR: OPEN TO CLOSE (GRIDIRON_OPENING_READ, 2026-09-09)
# ---------------------------------------------------------------------------
#
# The near-start half of this pair is the at-the-line claim, which already
# carries the venue's price read as a probability for a FIXED proposition --
# the home side, or the over -- with the model's probability for that same
# proposition beside it. Reusing it is not a shortcut: those mappings were
# measured, and re-deriving them here would be a second implementation of the
# thing most likely to be wrong.
#
# The open half is the EARLIEST opening read of the same game and market. Not
# the latest: "the open" means the first time this project looked, and a
# re-read twelve hours later is a later look at the same market, not a new
# opening.


def venue_pairs(conn: sqlite3.Connection, *, sport: str, market_type: str,
                predictor: str, event_tier: str | None = None) -> list[dict]:
    """Every at-the-line claim that also has an opening read to compare with.

    `toward` carries the same meaning as in `pairs()`: positive is movement in
    the direction the model was pointing. The sign comes from the two stored
    probabilities, both written for the same fixed proposition.

    ONE FORECASTER'S BETS (GRIDIRON_REPAIR item 6, 2026-09-26): the claims
    are the at-the-line record's own, through its door, one per game and
    market -- a game is one pair however many passes forecast it.
    """
    from .market import at_the_line

    config.require_sport(sport, "drift.venue_pairs")
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "at_the_line_claims" not in tables:
        return []
    columns = {r[1] for r in conn.execute("PRAGMA table_info(venue_quotes)")}
    if "read_kind" not in columns:
        # A RECORD OLDER THAN THE OPENING READ has no opening reads in it, so
        # there is no pair to report. Migrating here would make a reporting
        # function write to the database it is reading -- which is what the
        # gate's query-only handle refused, correctly, the first time this ran.
        return []

    # ONE PAIR PER BET, not per claim row (2026-09-23) nor per forecast
    # (2026-09-26): the venue is read on every firing, each look writes a
    # claim, and the morning and final pass each hold one. The door keeps the
    # last claim before the start on each game, for one forecaster.
    claims = at_the_line.standing_claims(
        conn, sport=sport, market=market_type, predictor=predictor,
        event_tier=event_tier)

    out = []
    for claim in claims:
        first = conn.execute(
            "SELECT MIN(fetched_utc) FROM venue_quotes"
            " WHERE game_id = ? AND market = ? AND read_kind = 'open'",
            (claim["game_id"], claim["market"])).fetchone()[0]
        if first is None:
            continue
        ladder = conn.execute(
            "SELECT * FROM venue_quotes"
            " WHERE game_id = ? AND market = ? AND read_kind = 'open'"
            "   AND fetched_utc = ?",
            (claim["game_id"], claim["market"], first)).fetchall()
        opened = at_the_line.rung_for(list(ladder))
        if opened is None:
            continue
        disagreement = claim["model_prob"] - opened["implied"]
        if abs(disagreement) < MIN_DISAGREEMENT:
            continue
        movement = claim["venue_implied"] - opened["implied"]
        toward = movement if disagreement > 0 else -movement
        out.append({
            "claim_id": claim["id"],
            "prediction_id": claim["prediction_id"],
            "claim": claim["model_prob"],
            "opened": opened["implied"],
            "opened_utc": first,
            "near": claim["venue_implied"],
            "disagreement": round(disagreement, 6),
            "movement": round(movement, 6),
            "toward": round(toward, 6),
        })
    return out


def venue_report(conn: sqlite3.Connection, *, sport: str, market_type: str,
                 predictor: str, event_tier: str | None = None) -> dict:
    """The venue's open-to-close drift for one category, or the count alone.

    Same gate as `report`, and it is the same rule rather than a copy of it:
    below fifty pairs a direction is a number a reader will remember and the
    sample is not. One forecaster's category (item 6, 2026-09-26).
    """
    found = venue_pairs(conn, sport=sport, market_type=market_type,
                        predictor=predictor, event_tier=event_tier)
    n = len(found)
    base = {
        "sport": sport,
        "market_type": market_type,
        "predictor": predictor,
        "event_tier": event_tier,
        "source": "venue",
        "n": n,
        "min_pairs": MIN_PAIRS,
        "min_disagreement": MIN_DISAGREEMENT,
        "progress": language.progress(
            n, MIN_PAIRS, noun="pairs",
            cleared_note="enough pairs to report a direction"),
    }
    if n < MIN_PAIRS:
        base["line"] = (
            f"{n} of {MIN_PAIRS} disagreements have both the venue's opening "
            f"read and its price at the line. Nothing is reported about "
            f"direction until there are enough.")
        return base
    moved_toward = sum(1 for p in found if p["toward"] > 0)
    base.update({
        "toward_fraction": round(moved_toward / n, 4),
        "moved_toward": moved_toward,
        "mean_movement": round(sum(p["toward"] for p in found) / n, 6),
        "line": (
            f"Between the venue's opening read and its price at the line, and "
            f"where the model disagreed by {MIN_DISAGREEMENT:.0%} or more, the "
            f"price moved toward the model {moved_toward / n:.0%} of the time "
            f"over {n} games."),
    })
    return base
