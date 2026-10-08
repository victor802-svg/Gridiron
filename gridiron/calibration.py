"""The scorecard. This is the product; the predictions are just its inputs.

LAW 4 is mechanical here, not editorial. Every figure this module produces is a
dict carrying its own `n`, and `assert_every_figure_has_n()` walks the finished
payload and raises if any number that could be read as a claim is standing
without its sample size. The API calls that validator before serialising, so a
figure cannot reach the browser naked.

Two other things this module refuses to do:

* It never merges categories. Spreads and props are different questions with
  different difficulty, and the statistical and LLM predictors are different
  forecasters. Averaging them produces a curve describing nobody.
* It reports the LARGEST gap, not the best-looking bucket. The sentence at the
  top of the track record is always the worst thing the record says.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field

from . import bet, config, horizon, language
from .factors import compute as factor_compute, registry
from .model import logistic

#: Stated-confidence buckets. Confidence is always >= 0.5 by construction: the
#: model states a side and its confidence in that side.
BUCKETS: tuple[tuple[float, float, str], ...] = (
    (0.50, 0.60, "50-60%"),
    (0.60, 0.70, "60-70%"),
    (0.70, 0.80, "70-80%"),
    (0.80, 1.01, "80%+"),
)

#: Confidence tiers, mapped from the claimed-probability bucket. This is a
#: LABEL over the existing buckets, not a second grouping: a tier's earned
#: figure comes from `bucket_record` — the same function the record page uses —
#: so the number on a pick card and the number on the chart cannot drift apart.
#:
#: STRONG covers two buckets, and each keeps its OWN number. Pooling 70-80% with
#: 80%+ to make one "STRONG hit rate" would be exactly the merge LAW 4 forbids,
#: and it would flatter: the easier bucket would lift the harder one.
TIERS: dict[str, str] = {
    "50-60%": "LEAN",
    "60-70%": "SOLID",
    "70-80%": "STRONG",
    "80%+": "STRONG",
}

#: A tier states its earned accuracy only once its own bucket holds this many
#: settled picks. Deliberately the same constant the calibration chart uses to
#: decide whether a point is provisional — one threshold, one meaning.
TIER_MIN_SETTLED = config.MIN_SAMPLE_FOR_BUCKET_POINT

ALWAYS_HALF_BRIER = 0.25
ALWAYS_HALF_LOG_LOSS = math.log(2.0)

#: Keys that assert a result. Any dict holding one of these must hold `n` too.
CLAIM_KEYS = frozenset(
    {
        "brier",
        "log_loss",
        "actual",
        "hit_rate",
        "resolved_in_model_favour",
        "delta_brier",
        "claimed",
    }
)


class MissingSampleSize(RuntimeError):
    """LAW 4: a figure was about to render without its N."""


#: RE-EXPORTED, not redefined. Both moved to `config`, beside `SPORTS`,
#: because this module names market columns and so cannot be imported by
#: anything on the prediction path -- which left LAW 6's own tripwire out of
#: reach of the modules most likely to need it. See `config.require_sport`.
CrossSportAggregation = config.CrossSportAggregation
require_sport = config.require_sport


#: HOW MANY EARLY/FINAL PAIRS BEFORE THE COMPARISON SAYS ANYTHING (A2).
#:
#: Fifty, and it is deliberately not the 100 of MIN_SAMPLE_FOR_EDGE_CLAIM,
#: because this is not an edge claim. It compares two forecasts of the SAME
#: game against the same outcome, so the pairing removes most of the variance
#: an edge estimate has to fight through -- the games are identical and only
#: the information differs. Below fifty the panel shows the COUNT and no
#: verdict, which is LAW 4's shape applied to a smaller question.
MIN_PAIRS_FOR_TIMING_VERDICT = 50


def early_vs_final(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Did forecasting later actually help? The number, not an opinion.

    THIS IS THE POINT OF THE WHOLE MECHANISM. Moving the graded forecast close
    to start is a bet that the market's edge on our confident disagreements
    (55.6% on n=207, docs/DIAGNOSIS.md) is partly an information gap we are
    inflicting on ourselves by asking early. That bet might be wrong. A later
    forecast could be a worse one -- more news is not automatically more
    signal, and a lineup can push a model around for no gain.

    So nothing here assumes it. On every resolved question that has BOTH a
    row from the early pass and one from the final pass, this reports how
    often the side changed, how far the claim moved, and which pass scored
    better by Brier. The number decides, on its date.

    LAW 6: one sport, required.
    """
    require_sport(sport, "early_vs_final")
    rows = conn.execute(
        "SELECT e.game_id, e.market_type, e.subject, e.predictor,"
        "       e.model_prob AS early_prob, e.model_side AS early_side,"
        "       f.model_prob AS final_prob, f.model_side AS final_side,"
        "       e.outcome"
        "  FROM predictions e"
        "  JOIN predictions f"
        "    ON f.game_id = e.game_id AND f.market_type = e.market_type"
        "   AND f.subject = e.subject AND f.predictor = e.predictor"
        "   AND f.factor_set_version = e.factor_set_version"
        "   AND IFNULL(f.line_asked, -1e9) = IFNULL(e.line_asked, -1e9)"
        "   AND f.pass_kind = 'final'"
        " WHERE e.sport = ? AND e.pass_kind = 'early'"
        # BOTH ROWS RESOLVED, and to the same outcome. They are two forecasts
        # of one question, so a disagreement about what happened would be a
        # resolution bug rather than a timing finding.
        "   AND e.resolved_utc IS NOT NULL AND f.resolved_utc IS NOT NULL"
        "   AND e.outcome = f.outcome"
        # NEITHER ROW VOIDED (ruling 1, 2026-09-24), even after it settled.
        "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
        "                   WHERE v.prediction_id IN (e.id, f.id))",
        (sport,)).fetchall()

    pairs = len(rows)
    changed = sum(1 for r in rows if r["early_side"] != r["final_side"])
    moved = [abs(r["final_prob"] - r["early_prob"]) for r in rows]
    early_better = final_better = 0
    early_brier = final_brier = 0.0
    for r in rows:
        # Brier against the row's OWN stated side: each pass is scored on the
        # claim it actually made, which is the only fair comparison when the
        # two passes may have named opposite sides.
        e = (r["early_prob"] - float(r["outcome"])) ** 2
        f = (r["final_prob"] - float(r["outcome"])) ** 2
        early_brier += e
        final_brier += f
        if f < e:
            final_better += 1
        elif e < f:
            early_better += 1

    out = {
        "n": pairs,
        "sport": sport,
        "gate": MIN_PAIRS_FOR_TIMING_VERDICT,
        "proven": pairs >= MIN_PAIRS_FOR_TIMING_VERDICT,
        "changed_side": changed,
        "final_better": final_better,
        "early_better": early_better,
        "mean_move": round(sum(moved) / pairs, 4) if pairs else None,
        "early_brier": round(early_brier / pairs, 4) if pairs else None,
        "final_brier": round(final_brier / pairs, 4) if pairs else None,
    }
    out["says"] = language.early_vs_final_line(out)
    return out


def assert_every_figure_has_n(payload, path: str = "$") -> None:
    """Walk a payload and refuse any claim standing without its sample size."""
    if isinstance(payload, dict):
        asserted = CLAIM_KEYS & payload.keys()
        if asserted and "n" not in payload:
            raise MissingSampleSize(
                f"LAW 4: {path} reports {sorted(asserted)} without an 'n'. "
                "No calibration curve, edge estimate or factor verdict renders "
                "without its sample size beside it."
            )
        for key, value in payload.items():
            assert_every_figure_has_n(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            assert_every_figure_has_n(value, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# reading resolved history
# ---------------------------------------------------------------------------

@dataclass
class Resolved:
    id: int
    created_utc: str
    game_id: str
    season: int
    week: int
    market_type: str
    prop_type: str | None
    predictor: str
    factor_set_version: str
    subject: str
    line_asked: float
    model_prob: float
    model_side: str
    outcome: int
    implied_prob: float | None
    factors_json: str = "{}"
    #: THE CARD THE ROW'S OWN BOUT WAS ON, for a sport that splits below the
    #: market (UFC), read off the bout and never off the category asked for;
    #: None for every other sport (operator question 34, 2026-10-08). How a
    #: count's guard sees a door that stopped asking for the card.
    event_tier: str | None = None


def standing_pass_order(forecast: str, game: str, row: str | None = None) -> str:
    """WHICH OF A QUESTION'S ROWS STANDS, as SQL `ORDER BY` terms, the first
    one standing (operator question 27, ruled 2026-09-28, the brief's reading
    confirmed 2026-09-29): "the standing pass is chosen by pass, not by write
    time: the final pass stands whenever one exists before the start;
    otherwise the latest early pass. A read rule -- no row changes."

    THE ONE DOOR FOR THE ORDER (2026-09-29). `standing_row_clause` orders a
    question's forecasts by it (`forecast` and `game` are its aliases), and
    the at-the-line record orders a question's claims by it
    (`at_the_line.standing_claims`: the rows ordered are claims, `row`, each
    on its forecast), so the two records cannot choose a pass two ways.
    `gridiron.recount` spells it again in Python, as it spells the clause,
    and `audit.standing_pass_faults` asks every door that chooses a
    question's row which one stands, on a world made to tell pass from write
    time (gate step 2).

    First a final pass written before its game's start -- a game with no
    start recorded keeps every row a candidate, as the clause always has, so
    its final pass stands; then the latest written; then the number, which
    breaks a tie in the second, as it always has. Two final passes (two
    factor sets) leave the later; early passes alone leave the latest: the
    ruling's "otherwise", and the rule as it was.

    WHY IT CHANGED. Until this date the order was the write time alone, so a
    question whose final pass was written first and its early pass after
    stood on the early one: sixteen NFL week-3 reasoning-pass totals, the
    final passes written by `final:nfl` (run 2052) on 23 September at 19:30Z
    and the early passes by the catch-up's `predict:nfl` (run 2336) at
    05:32-05:36Z the next morning, all before their starts
    (docs/REPAIR_STATE.md, question 27). The final pass is the forecast made
    on what is known close to the start; that is what it is for, whichever
    row was written last.

    A PASS WRITTEN AFTER THE START never comes first: the first term is false
    for it. The clause keeps it out whenever its question has a row written
    before the start; when none was (a backtest), every row is after the
    start, the first term is false for all of them, and the latest written
    stands -- the fallback kept as it was, as the brief's reading says.

    BEFORE THE START, AS INSTANTS, AND STRICTLY (operator question 35, ruled
    2026-09-30: "a pass written at or after the start is not blind. Store
    and compare starts as instants, never as text"; built 2026-10-01). Until
    this date the term compared the stored text and admitted a pass written
    AT the start (`<=`): UFC starts are stored to the minute ("...T19:00Z"),
    every pass to the second, and ':' sorts below 'Z', so eighteen UFC final
    passes written at 19:00:02-03Z on a card listed at 19:00Z (forecasts
    1014-1031, 5 September) came first, and the UFC ranker split read 49 and
    0 in each of three markets where it was 43 and 6 (the re-read of 29
    September; 53 and 0 against 47 and 6 on 1 October). Now `julianday()` on
    both sides -- the one expression every query compares a start by -- and
    `<`: a pass written at the start's second is not before it.

    A START NOBODY CAN READ IS BEFORE NOTHING, AND THE TERM SAYS SO (Q35's
    prover, 2026-10-01). `julianday()` of a start it cannot read -- an empty
    one, a feed's "TBD" kept as sent (`db.stored_start`) -- is NULL, so as
    first built the term was NULL for a final pass on such a game and 0 for
    an early pass, and ORDER BY ... DESC puts NULL last: the question stood
    on its latest EARLY pass, where the recount (`recount._before_the_start`,
    False) and the rule's own fallback -- nothing shown to come before the
    start, so the latest written stands -- keep the latest row: on a world
    with an early pass and a later final pass on an unreadable start, the
    clause stood the early one and the recount the final.
    `IFNULL(..., 0)`: not before the start, as the recount reads it. None on
    the record that day (24,310 starts, every one read).
    """
    row = row or forecast
    return (f"({forecast}.pass_kind = 'final'"
            f" AND ({game}.kickoff_utc IS NULL"
            f" OR IFNULL(julianday({forecast}.created_utc)"
            f" < julianday({game}.kickoff_utc), 0))) DESC,"
            f" {row}.created_utc DESC, {row}.id DESC")


def standing_row_clause(same_set: bool) -> str:
    """The SQL that keeps ONE standing row per question: a final pass written
    before the start if there is one, otherwise the latest written before the
    start (operator question 27, ruled 2026-09-28; until 2026-09-29 the
    latest written before the start, whatever its pass). Appended to a query
    over `predictions p JOIN games g`.

    ONE DOOR (audit 2026-09-05). `resolved()` had this rule inline and every
    scorecard went through it, but the version table's N and the pace line
    counted rows straight off the table -- so the MLB record showed 233
    settled under fs2 while its categories summed to 197, the other 36 being
    early rows a final pass had superseded. Two counts of one record cannot
    disagree if they share the clause.

    ONE STANDING ROW PER DISTINCT BET (operator question 17, 2026-09-28).
    "The question" is `bet.same` -- the one function's SQL form: the
    forecaster, the game, the market, the subject and the rung asked, NULL
    one value. It was written out here twice until this date, without the
    prop type, which the subject carries. `gridiron.recount` works this rule
    out again in Python, and each builder that counts through it refuses a
    count the two disagree on.

    STILL WITHOUT THE PROP TYPE (2026-09-29). From 2026-09-28 `bet.same`
    named it too, and measured on a copy of the record that day it moved 14
    NFL figures: a week-one prop asked at 05:55Z with no prop type and again
    at 07:34Z with one kept both rows here, one question counted twice in
    every reader of a sport's markets together (the factor table, the pick
    card's worst band, the tier table's pace). The question is named by its
    subject (`gridiron.bet`), as `resolved` below has said since 2026-09-02.

    CHOSEN BY PASS, NOT BY WRITE TIME (operator question 27, ruled
    2026-09-28; built 2026-09-29). Which rows may stand is what it was --
    written before the start, withdrawn never, a backtest's every row --
    and among them the order is `standing_pass_order`: a final pass before
    the start first, then the latest written. Every record that reads this
    clause moves with it and no row changes: the blind curves and the
    version table, the priced record, where the line went, the outlook, the
    coverage line at the venue's line, the ranker's standing rows and, from
    this date, the slate's cards (`views.week`, which had a write-time rule
    of its own). Measured on the record the day it was built: sixteen NFL
    week-3 reasoning-pass totals stood on an early pass written after their
    final pass, and stand on the final pass from this date (FOLLOWUPS, "The
    standing pass is chosen by pass").
    """
    same = (" AND p2.factor_set_version = p.factor_set_version"
            if same_set else "")
    # A VOIDED ROW IS NEVER THE STANDING ONE (operator ruling 1, 2026-09-24).
    #
    # Until this date a void stayed out of the arithmetic only because a
    # trigger refuses to resolve a voided row, so it never reached a count
    # that asks for an outcome. That holds for a void written BEFORE the game
    # settles, and it is the only case the resolver produces. The ruling's
    # voids are written by hand, and a game can settle first -- after which
    # the row carries an outcome and nothing here would have left it out.
    #
    # TWO PLACES, for two reasons. The row itself is excluded, so a voided
    # forecast is never graded. And it is skipped when choosing the standing
    # row, so a voided later row does not displace an earlier forecast of the
    # same question that still stands -- a withdrawal takes one row back, not
    # the question. The fallback below (every row written after the start)
    # still sees voided rows: a question whose pre-start forecasts were all
    # withdrawn had a forecast before the start, and a row written afterwards
    # must not become its standing one.
    voided = (" AND NOT EXISTS (SELECT 1 FROM prediction_voids vs"
              "                 WHERE vs.prediction_id = p.id)")
    skip_voided = ("                AND NOT EXISTS (SELECT 1 FROM prediction_voids v2"
                   "                                WHERE v2.prediction_id = p2.id)")
    # THE LATEST ROW **BEFORE START**, not simply the latest (2026-09-03).
    #
    # The final pass (config.FINAL_PASS) writes a second forecast close to
    # kickoff, so "which row is the standing one" stopped being a duplicate
    # question and became the ordinary case. A row written AFTER the game
    # began is not a forecast -- the MISSED rule already refuses to write one,
    # and this is the second lock: even if one existed, it could not become
    # the row the record is graded on. A backtest is the case that proves it
    # matters, because every backtest row is written after its game.
    #
    # `g2.kickoff_utc IS NULL` keeps a game with no scheduled time eligible
    # rather than silently dropping every question about it.
    #
    # AND AMONG THOSE, THE FINAL PASS (operator question 27, 2026-09-29): the
    # candidates are ordered by `standing_pass_order`, no longer by the write
    # time alone. The WHERE below is unchanged. A question whose final pass
    # was withdrawn is left its latest early pass, because a withdrawn row is
    # never a candidate (`skip_voided`).
    #
    # WRITTEN BEFORE THE START IS STRICTLY BEFORE IT, READ AS INSTANTS
    # (operator question 35, ruled 2026-09-30: "a pass written at or after the
    # start is not blind. Store and compare starts as instants, never as
    # text"; built 2026-10-01). Both tests below compared the stored text and
    # admitted a row written AT the start (`<=`); a start stored to the minute
    # ("...T19:00Z") then took a pass written at "...T19:00:02Z" for one
    # written before it (':' sorts below 'Z'). `julianday()` on both sides,
    # and `<`, in which rows may stand and in the backtest's fallback alike.
    return (
        f"{voided}"
        " AND p.id = (SELECT p2.id FROM predictions p2"
        "              JOIN games g2 ON g2.id = p2.game_id"
        f"              WHERE {bet.same('p2', 'p')}"
        f"{same}"
        f"{skip_voided}"
        "                AND (g2.kickoff_utc IS NULL"
        "                     OR julianday(p2.created_utc)"
        "                        < julianday(g2.kickoff_utc)"
        # A SLATE OF ROWS ALL WRITTEN AFTER START is a backtest, and a
        # backtest still has to produce a curve. When nothing was written
        # before kickoff the latest row stands, because refusing them all
        # would report an empty record rather than a retrospective one.
        "                     OR NOT EXISTS (SELECT 1 FROM predictions p3"
        "                                    JOIN games g3 ON g3.id = p3.game_id"
        f"                                    WHERE {bet.same('p3', 'p2')}"
        "                                      AND julianday(p3.created_utc)"
        "                                          < julianday(g3.kickoff_utc)))"
        f"              ORDER BY {standing_pass_order('p2', 'g2')} LIMIT 1)"
    )


def category_filter(
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
    event_tier: str | None = None,
) -> tuple[list[str], list]:
    """THE ONE DOOR FOR WHICH FORECASTS A CATEGORY HOLDS: its sport, its
    card, its market, its prop type, its forecaster and its factor set, as
    SQL terms on `predictions p` and their parameters.

    A CURVE AND THE VOID COUNT BESIDE IT ASK HERE BOTH (2026-10-01; the
    first of operator question 34's counts -- "every UFC count is per card
    tier" -- built ahead of it because question 35's voids made this one
    false). `resolved`, the curve's rows, and `withdrawn_forecasts`, its
    void count, built these terms apart until this date, and only
    `resolved` was handed the card: `curve` asked `void_count` for the
    market across every card, so once question 35's eighteen were voided
    (all Fight Night) each UFC market's Contender Series curve would have
    read "6 withdrawn, void rate 0.3" and its Numbered card curve "6
    withdrawn, void rate 1.0" on nothing settled, where only Fight Night's
    6 is true. One door, so a curve's count and its void count cannot name
    two populations; `assert_each_void_count_is_its_cards` holds the result
    to a recount made without it."""
    require_sport(sport, "calibration.category_filter")
    where = ["p.sport = ?"]
    params: list = [sport]
    if event_tier:
        # LAW 6 ONE LEVEL DOWN (R2, 2026-09-03). A Contender Series bout goes
        # the distance 43.6% of the time and a numbered-card bout 58.0%; one
        # UFC curve would average those and describe neither, which is exactly
        # the failure the law forbids across sports. The tier lives on the
        # EVENT, so this reaches through the bout to the card it was on.
        where.append(
            "EXISTS (SELECT 1 FROM ufc_bouts b JOIN ufc_events e"
            "          ON e.id = b.event_id"
            "         WHERE b.id = p.game_id AND e.event_tier = ?)")
        params.append(event_tier)
    if market_type:
        where.append("p.market_type = ?")
        params.append(market_type)
    if prop_type:
        where.append("p.prop_type = ?")
        params.append(prop_type)
    if predictor:
        where.append("p.predictor = ?")
        params.append(predictor)
    if factor_set_version:
        where.append("p.factor_set_version = ?")
        params.append(factor_set_version)
    return where, params


# ---------------------------------------------------------------------------
# EVERY UFC COUNT IS PER CARD TIER (operator question 34, ruled 2026-09-30:
# "every UFC count is per card tier: tier table, ranker, taken record, edge
# figure, board badge. Planting each."; built 2026-10-08)
# ---------------------------------------------------------------------------
#
# R2 of 2026-09-03 splits the UFC record by card because one curve over the
# three "would average those and describe neither" -- a Contender Series bout
# goes the distance 43.6% of the time and a numbered-card bout 58.0% -- and
# question 14 (2026-09-27) rebuilt three of the Record page's counts per card
# ("per tier for UFC"). The re-read of 29 September (finding G2) found five
# more counting the three cards as one: the tier table's bands (28/15/4/2,
# where Fight Night held 22/14/2/1 and the Contender Series 6/1/2/1), the
# ranker's "49 settled on the shortlist and 0 off it" (39/0, 10/0, 0/0), the
# taken record's "every forecast 49", the edge figure's "0 of the 100
# disagreements" and the board's badge, `shortlist.settled_for_gate`, 49.
# Each door now takes the card and refuses a UFC count asked without one
# (`refuse_a_count_across_cards`, the `PooledCount` precedent of the doors
# question 14 built), and each builder carries the cards its rows were on
# (read off each row's own bout) and the count `gridiron.recount` makes
# without the door, and refuses by name, inside itself, a count of another
# card than the one it names (`PooledCardCount`), so the API answers 500.
# (The two errors are declared beside `MergedCurve`, which they are.)


def refuse_a_count_across_cards(sport: str, event_tier: str | None,
                                what: str) -> None:
    """THE CARD RULE EVERY UFC COUNT'S DOOR ASKS FIRST (operator question
    34, 2026-10-08): for a sport that splits below the market, one of its
    declared cards; for one that does not, none."""
    tiers = config.event_tiers(sport)
    law = ("LAW 6 ONE LEVEL DOWN (operator question 34, ruled 2026-09-30: "
           "\"every UFC count is per card tier\")")
    if tiers and event_tier not in tiers:
        raise PooledCount(
            f"{law}: {what} in {sport} was asked for card {event_tier!r}, "
            f"not one of {sport}'s declared cards {list(tiers)}. Each card's "
            f"count is its own and they are reported side by side, never "
            f"summed: name one.")
    if not tiers and event_tier is not None:
        raise PooledCount(
            f"{law}: {what} in {sport} names card {event_tier!r}, but {sport} "
            f"declares no cards, so it would count nothing that exists.")


def refuse_another_cards_count(sport: str, event_tier: str | None,
                               cards, what: str) -> None:
    """THE GUARD'S CARD TEST, shared by the five counts: a count naming one
    of a carded sport's cards counts rows on that card and no other (`cards`,
    read off each row's own bout -- a bout whose card the source left
    unnamed is on none); a count in a sport that declares none names none."""
    tiers = config.event_tiers(sport)
    law = "QUESTION 34: EVERY UFC COUNT IS PER CARD TIER"
    if tiers:
        if event_tier not in tiers:
            raise PooledCardCount(
                f"{law}: {what} names card {event_tier!r}, not one of "
                f"{sport}'s cards {list(tiers)}: a count over the cards "
                f"together describes none of them.")
        if cards is None or any(c != event_tier for c in cards):
            raise PooledCardCount(
                f"{law}: {what} is the {event_tier!r} card's and counts rows "
                f"on {cards!r}: {sport}'s cards {list(tiers)} are reported "
                f"side by side, never summed.")
    elif event_tier is not None or cards:
        raise PooledCardCount(
            f"{law}: {what} names card {event_tier!r} and counts rows on "
            f"{cards!r} in {sport}, which declares no cards.")


def _cards_of(items) -> list:
    """The cards a count's rows were on, read off each row's own bout:
    sorted, with an unnamed card (None) kept, so it is seen."""
    return sorted({getattr(r, "event_tier", None) if not isinstance(r, dict)
                   else r.get("event_tier") for r in items}, key=str)


def resolved(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
    event_tier: str | None = None,
    with_factors: bool = False,
) -> list[Resolved]:
    require_sport(sport, "calibration.resolved")
    # THE CATEGORY'S ROWS THROUGH ITS ONE DOOR (2026-10-01), the void count's
    # too; settled ones only, here.
    where, params = category_filter(
        sport=sport, market_type=market_type, prop_type=prop_type,
        predictor=predictor, factor_set_version=factor_set_version,
        event_tier=event_tier)
    where = ["p.resolved_utc IS NOT NULL"] + where

    # SUPERSEDED FORECASTS ARE NOT IN THE RECORD'S ARITHMETIC (ruling R4,
    # 2026-09-02), and they are never deleted.
    #
    # `predict:nfl` ran twice on 2026-08-29 -- 05:55Z and again at 07:34Z --
    # and wrote a full second set of week 1 forecasts. Both rows are the
    # record: LAW 3 is append-only and a prediction is never removed. But a
    # curve that counts 26 questions twice is describing a slate that was
    # never asked, and it counts them with correlated errors, which is worse
    # than counting them once.
    #
    # THE STANDING FORECAST IS THE LATEST ONE WRITTEN, per question per
    # forecaster -- the same rule `views.week` already applies to Picks and
    # the same rule a revised call once followed. The earlier rows stay
    # readable in Results and in `prediction_detail`; they are simply not
    # arithmetic. FROM 2026-09-29 (operator question 27) THE PASS DECIDES
    # FIRST: a final pass written before the start stands over an early pass
    # written after it, and the latest written decides among the rest
    # (`standing_row_clause`, `standing_pass_order`).
    #
    # WHAT MAKES TWO ROWS THE SAME QUESTION: the game, the market, the
    # subject, the rung and the forecaster. `line_asked` is part of it -- the
    # same subject asked at two different rungs is two questions, not a
    # revision of one.
    #
    # `prop_type` IS DELIBERATELY NOT PART OF IT, and the reason is a data
    # artefact worth naming. The subject already carries the stat ("Trey
    # McBride receiving_yards"), and ten NFL rows from the earlier of the two
    # 2026-08-29 runs left `prop_type` NULL where the later run set it. Keying
    # on it split ten questions that are plainly the same one and counted each
    # twice -- 88 standing instead of 78, disagreeing with the Picks page
    # about the very same slate. One definition of "the same question", and
    # this is it.
    #
    # THE SUBQUERY MIRRORS THE FILTER, and it has to. `factor_set_version` is
    # a legitimate reason for two forecasts on one question -- a different
    # model asking it is a different forecast, and the record keeps both with
    # their versions attached. That is exactly what happened on 2026-08-29:
    # fs1 at 05:55 and fs2 at 07:34.
    #
    # So an UNFILTERED curve takes the latest across sets, because a curve
    # spanning two factor sets describes two models. A curve asked for ONE set
    # takes the latest within it -- without this, asking for fs1 would match
    # the fs2 row's id, fail the outer filter, and return nothing at all.
    standing = standing_row_clause(bool(factor_set_version))
    # THE CARD EACH ROW'S OWN BOUT WAS ON (operator question 34, 2026-10-08),
    # for a sport that splits by card: read off the row, so a count of
    # another card's rows is seen on the payload rather than trusted.
    card = ("(SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
            "   ON e.id = b.event_id WHERE b.id = p.game_id)"
            if config.event_tiers(sport) else "NULL")
    rows = conn.execute(
        "SELECT p.id, p.created_utc, p.game_id, g.season, g.week, p.market_type,"
        " p.prop_type, p.predictor, p.factor_set_version, p.subject, p.line_asked,"
        " p.model_prob, p.model_side, p.outcome, p.factors_json,"
        " (SELECT s.implied_prob FROM market_snapshots s WHERE s.prediction_id = p.id"
        "  ORDER BY s.id LIMIT 1) AS implied_prob,"
        f" {card} AS event_tier"
        f" FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE {' AND '.join(where)}{standing} ORDER BY p.id",
        params,
    ).fetchall()

    return [
        Resolved(
            id=r["id"],
            created_utc=r["created_utc"],
            game_id=r["game_id"],
            season=r["season"],
            week=r["week"],
            market_type=r["market_type"],
            prop_type=r["prop_type"],
            predictor=r["predictor"],
            factor_set_version=r["factor_set_version"],
            subject=r["subject"],
            line_asked=r["line_asked"],
            model_prob=r["model_prob"],
            model_side=r["model_side"],
            outcome=r["outcome"],
            implied_prob=r["implied_prob"],
            factors_json=r["factors_json"] if with_factors else "{}",
            event_tier=r["event_tier"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# the curve
# ---------------------------------------------------------------------------

def calibration_buckets(items: list[Resolved]) -> list[dict]:
    out = []
    for lo, hi, label in BUCKETS:
        chosen = [r for r in items if lo <= r.model_prob < hi]
        n = len(chosen)
        entry: dict = {
            "label": label,
            "lo": lo,
            "hi": min(hi, 1.0),
            "n": n,                       # LAW 4: present even when zero
            "provisional": n < config.MIN_SAMPLE_FOR_BUCKET_POINT,
        }
        if n:
            claimed = sum(r.model_prob for r in chosen) / n
            actual = sum(r.outcome for r in chosen) / n
            entry.update(
                claimed=round(claimed, 4),
                actual=round(actual, 4),
                gap=round(actual - claimed, 4),
            )
        else:
            entry.update(claimed=None, actual=None, gap=None)
        out.append(entry)
    return out


def largest_gap_sentence(buckets: list[dict], minimum_n: int | None = None) -> str:
    """The worst thing the record says, in one sentence. Never the best."""
    minimum_n = config.MIN_SAMPLE_FOR_BUCKET_POINT if minimum_n is None else minimum_n
    usable = [b for b in buckets if b["n"] >= minimum_n and b["gap"] is not None]
    if not usable:
        total = sum(b["n"] for b in buckets)
        if total == 0:
            return "Nothing has resolved yet, so there is no calibration to report."
        return (
            f"{total} predictions have resolved, but no confidence bucket yet holds "
            f"the {minimum_n} needed to say anything about calibration."
        )
    worst = max(usable, key=lambda b: abs(b["gap"]))
    direction = "overconfident" if worst["gap"] < 0 else "underconfident"
    return (
        f"Largest gap: in the {worst['label']} bucket the model claimed "
        f"{worst['claimed'] * 100:.1f}% and was right {worst['actual'] * 100:.1f}% "
        f"of the time across {worst['n']} resolved predictions — "
        f"{direction} by {abs(worst['gap']) * 100:.1f} points."
    )


def score(items: list[Resolved]) -> dict:
    n = len(items)
    if not n:
        return {"n": 0, "brier": None, "log_loss": None, "hit_rate": None}
    probs = [r.model_prob for r in items]
    outcomes = [r.outcome for r in items]
    return {
        "n": n,
        "brier": round(logistic.brier(probs, outcomes), 4),
        "log_loss": round(logistic.log_loss(probs, outcomes), 4),
        "hit_rate": round(sum(outcomes) / n, 4),
    }


def baselines(items: list[Resolved]) -> dict:
    """What the model has to beat: a coin, and the market."""
    out = {
        "always_50": {
            "n": len(items),
            "brier": round(ALWAYS_HALF_BRIER, 4),
            "log_loss": round(ALWAYS_HALF_LOG_LOSS, 4),
            "note": "a forecaster who says 50% to everything",
        }
    }
    with_market = [r for r in items if r.implied_prob is not None]
    if with_market:
        probs = [r.implied_prob for r in with_market]
        outcomes = [r.outcome for r in with_market]
        out["market"] = {
            "n": len(with_market),
            "brier": round(logistic.brier(probs, outcomes), 4),
            "log_loss": round(logistic.log_loss(probs, outcomes), 4),
            "note": (
                "the closing line converted to a probability, scored on the same "
                "questions. This is the number that is hard to beat."
            ),
        }
        # The model's own score restricted to the same subset, so the comparison
        # is like for like rather than across different question sets.
        out["model_on_market_subset"] = score(with_market)
    else:
        out["market"] = {
            "n": 0,
            "brier": None,
            "log_loss": None,
            "note": "no market comparison available for these questions",
        }
    return out


def withdrawn_forecasts(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
    event_tier: str | None = None,
) -> list[dict]:
    """Every withdrawn forecast ONE category holds -- the void count beside
    its curve -- each with the card its own bout was on (UFC; None
    elsewhere).

    `void_count` until 2026-10-01, which took no card: the count beside a
    UFC curve was its market's across every card. THROUGH THE CATEGORY'S
    DOOR now (`category_filter`), the curve's own: the card a curve counts
    is the card its void count counts. Every withdrawn row of the category,
    whichever pass it was, as before -- the card is the one change. The
    card read off each row (`event_tier`) is how the guard sees a door
    that stopped asking for it (`assert_each_void_count_is_its_cards`).
    """
    require_sport(sport, "calibration.withdrawn_forecasts")
    where, params = category_filter(
        sport=sport, market_type=market_type, prop_type=prop_type,
        predictor=predictor, factor_set_version=factor_set_version,
        event_tier=event_tier)
    card = ("(SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
            "   ON e.id = b.event_id WHERE b.id = p.game_id)"
            if config.event_tiers(sport) else "NULL")
    return [dict(r) for r in conn.execute(
        f"SELECT p.id, {card} AS event_tier"
        "  FROM prediction_voids v JOIN predictions p ON p.id = v.prediction_id"
        f" WHERE {' AND '.join(where)} ORDER BY p.id",
        params,
    ).fetchall()]


def void_rate(n: int, voided: int) -> float | None:
    """The share of a category's forecasts withdrawn: its void count over
    its settled count and its void count together. ONE ARITHMETIC, which
    the curve states and the guard works again (2026-10-01)."""
    return round(voided / (n + voided), 4) if (n + voided) else None


def curve(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    factor_set_version: str | None = None,
    event_tier: str | None = None,
) -> dict:
    from . import db

    require_sport(sport, "calibration.curve")
    cell = dict(sport=sport, market_type=market_type, prop_type=prop_type,
                predictor=predictor, factor_set_version=factor_set_version,
                event_tier=event_tier)
    # ONE CELL, ONE INSTANT (2026-10-01): the curve's rows and its void
    # count are asked of the same category -- its card included, which the
    # void count was not handed until this date -- in one read, so a void
    # written between the two cannot be counted on one side only.
    with db.one_instant(conn):
        items = resolved(conn, **cell)
        withdrawn = withdrawn_forecasts(conn, **cell)
    buckets = calibration_buckets(items)
    voids = len(withdrawn)
    return {
        "sport": sport,
        "filters": {
            "sport": sport,
            "market_type": market_type or "all",
            "prop_type": prop_type or "all",
            "predictor": predictor or "all",
            "factor_set_version": factor_set_version or "all",
            "event_tier": event_tier or "all",
        },
        "event_tier": event_tier,
        "tier_label": language.tier_label(event_tier),
        "n": len(items),
        "buckets": buckets,
        "largest_gap": largest_gap_sentence(buckets),
        "score": score(items),
        "baselines": baselines(items),
        # Reported beside the curve, never folded into it. A rising void rate is
        # a finding about which questions we are choosing, not a rounding error.
        "voided": voids,
        "void_rate": void_rate(len(items), voids),
        # THE CARDS THE VOID COUNT COUNTED, read off each withdrawn row's own
        # bout (2026-10-01): one card's for a UFC category, none named for a
        # sport that does not split by card. A card left unnamed by the
        # source is None, which is no category's.
        "void_tiers_counted": (sorted({r["event_tier"] for r in withdrawn},
                                      key=str)
                               if config.event_tiers(sport) else []),
    }


# ---------------------------------------------------------------------------
# the edge question — computed, and heavily caveated
# ---------------------------------------------------------------------------

EDGE_STANDING_NOTE = (
    "Beating the market on a small sample is the expected behaviour of luck, not "
    "evidence of an edge. A run of correct disagreements is what chance looks "
    "like at this scale. Nothing here should be read as a claim until the sample "
    f"is well past {config.MIN_SAMPLE_FOR_EDGE_CLAIM} and has survived a season "
    "it was not fitted on."
)


def edge(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str = "spread",
    prop_type: str | None = None,
    predictor: str | None = None,
    threshold: float | None = None,
    event_tier: str | None = None,
) -> dict:
    """Where the model disagreed with the market, who was right?

    "Disagreement" means the model was more confident in the side it stated than
    the market's implied probability for that same side, by more than the
    threshold. The reverse subset — where the market was more confident than the
    model — is reported alongside it, because showing only the flattering half
    of a comparison is how a record lies while being technically accurate.

    ONE CARD'S FOR UFC (operator question 34, ruled 2026-09-30; built
    2026-10-08): the card is required for a sport that splits by card
    (`refuse_a_count_across_cards`), the payload carries the cards its rows
    were on and the count `gridiron.recount` makes without the door, and
    `assert_no_pooled_edge` refuses another card's count inside this
    builder. Until this date UFC's "0 of the 100 disagreements required"
    was one count over the three cards (0 on each, so the number held).
    """
    from . import db, recount

    threshold = config.EDGE_DISAGREEMENT_THRESHOLD if threshold is None else threshold
    require_sport(sport, "calibration.edge")
    refuse_a_count_across_cards(sport, event_tier, "the edge figure's count")
    with db.one_instant(conn):
        everything = resolved(
            conn, sport=sport, market_type=market_type, prop_type=prop_type,
            predictor=predictor, event_tier=event_tier)
        again = (recount.disagreements(recount.settled_standing(
            conn, sport=sport, predictor=predictor, market_type=market_type,
            prop_type=prop_type, event_tier=event_tier), threshold)
            if predictor and market_type else None)
    items = [r for r in everything if r.implied_prob is not None]

    model_bolder = [r for r in items if r.model_prob - r.implied_prob > threshold]
    market_bolder = [r for r in items if r.implied_prob - r.model_prob > threshold]

    def side(subset: list[Resolved], label: str) -> dict:
        n = len(subset)
        entry: dict = {"label": label, "n": n}
        if n:
            entry["resolved_in_model_favour"] = round(
                sum(r.outcome for r in subset) / n, 4
            )
            entry["mean_model_prob"] = round(sum(r.model_prob for r in subset) / n, 4)
            entry["mean_market_prob"] = round(sum(r.implied_prob for r in subset) / n, 4)
        else:
            entry["resolved_in_model_favour"] = None
            entry["mean_model_prob"] = None
            entry["mean_market_prob"] = None
        return entry

    minimum = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    n_eligible = len(model_bolder)
    payload = {
        "sport": sport,
        "market_type": market_type,
        "prop_type": prop_type or "all",
        "predictor": predictor or "all",
        "threshold": threshold,
        "n": len(items),
        "n_disagreements": n_eligible,
        "minimum_for_a_claim": minimum,
        "standing_note": EDGE_STANDING_NOTE,
        # COUNTED AGAIN WITHOUT THE DOOR (operator question 34, 2026-10-08).
        "recounted": (None if again is None
                      else {"n": again[0], "n_disagreements": again[1]}),
    }
    if config.event_tiers(sport):
        # ONE CARD'S, NAMED -- keys only a carded sport's figure carries, so
        # no other sport's changes shape.
        payload["event_tier"] = event_tier
        # ITS MARKET AND ITS CARD, "moneyline, Fight Night": the render found
        # the card alone over each answer, the market said nowhere.
        payload["card_label"] = language.card_market_label(
            sport, prop_type or market_type, event_tier)
        payload["tiers_counted"] = _cards_of(everything)

    if n_eligible < minimum:
        payload["renderable"] = False
        payload["shortfall"] = minimum - n_eligible
        payload["message"] = (
            f"{n_eligible} resolved disagreements of the {minimum} required. "
            f"{minimum - n_eligible} more before this figure will be shown at all."
        )
        assert_no_pooled_edge(payload)
        return payload

    payload["renderable"] = True
    payload["model_more_confident"] = side(model_bolder, "model more confident")
    payload["market_more_confident"] = side(market_bolder, "market more confident")
    assert_no_pooled_edge(payload)
    return payload


def assert_no_pooled_edge(payload: dict) -> None:
    """THE EDGE FIGURE'S COUNT IS ONE CARD'S FOR UFC (operator question 34,
    ruled 2026-09-30; built 2026-10-08). Refused by name, inside `edge`, so
    `/api/scorecard` answers 500: a count naming no card, or one of none, in
    a sport that splits by card; one counting rows on another card than it
    names, or on every card (`tiers_counted`, read off each row's own bout);
    and a count of settled questions with a price, or of disagreements, that
    `gridiron.recount` does not make without the door (`recounted`; asked
    of one forecaster in one market, as the page asks it)."""
    what = (f"the edge figure for {payload.get('sport')} "
            f"{payload.get('market_type')}, {payload.get('predictor')}")
    refuse_another_cards_count(payload.get("sport"), payload.get("event_tier"),
                               payload.get("tiers_counted", []), what)
    again = payload.get("recounted")
    if again is None:
        if config.event_tiers(payload.get("sport")):
            raise PooledCardCount(
                f"QUESTION 34: EVERY UFC COUNT IS PER CARD TIER: {what} "
                f"carries no recount, so nothing shows it is one card's.")
        return
    if (again.get("n"), again.get("n_disagreements")) != (
            payload.get("n"), payload.get("n_disagreements")):
        raise PooledCardCount(
            f"QUESTION 34: EVERY UFC COUNT IS PER CARD TIER: {what} counts "
            f"{payload.get('n_disagreements')!r} disagreements of "
            f"{payload.get('n')!r} settled with a price where the recount "
            f"made without its door finds {again.get('n_disagreements')!r} "
            f"of {again.get('n')!r}.")


# ---------------------------------------------------------------------------
# per-factor scoring (LAW 2: is this factor actually doing anything?)
# ---------------------------------------------------------------------------

FACTOR_METHOD_NOTE = (
    "Each factor is scored by removing its contribution from the log-odds of the "
    "predictions it actually took part in, and comparing the Brier score with and "
    "without it. A positive delta means the record was better with the factor in. "
    "This is an attribution within the fitted model, not an independent test of "
    "the idea, and it only counts predictions made from the factor's activation "
    "date forward — never backfitted onto older ones."
)


def factor_report(
    conn: sqlite3.Connection, *, sport: str, factor_set_version: str | None = None
) -> dict:
    require_sport(sport, "calibration.factor_report")
    items = resolved(
        conn,
        sport=sport,
        predictor="statistical",
        factor_set_version=factor_set_version,
        with_factors=True,
    )

    stats: dict[str, dict] = {}
    for r in items:
        payload = json.loads(r.factors_json or "{}")
        contributions = payload.get("contributions") or []
        log_odds = payload.get("log_odds")
        question = payload.get("question") or {}
        yes_label = question.get("yes_label")
        absent = set(factor_compute.absent_factors(payload))
        if log_odds is None or not contributions or not yes_label:
            continue
        outcome_yes = r.outcome if r.model_side == yes_label else 1 - r.outcome

        for c in contributions:
            name = c["factor"]
            declared = registry.REGISTRY.get(name)
            if declared and r.created_utc < declared.added_utc:
                continue  # never scored before it existed
            bucket = stats.setdefault(
                name,
                {
                    "n": 0,
                    "with": 0.0,
                    "without": 0.0,
                    "abs_contribution": 0.0,
                    "nonzero": 0,
                    "defaulted": 0,
                },
            )
            p_with = logistic.sigmoid(log_odds)
            p_without = logistic.sigmoid(log_odds - c["contribution"])
            bucket["n"] += 1
            bucket["with"] += (p_with - outcome_yes) ** 2
            bucket["without"] += (p_without - outcome_yes) ** 2
            bucket["abs_contribution"] += abs(c["contribution"])
            # Whether the INPUT varied at all, kept apart from whether the
            # factor mattered. A factor the schedule never lets move is an
            # untested hypothesis, not a disproved one.
            if abs(c.get("value") or 0.0) > 1e-9:
                bucket["nonzero"] += 1
            if name in absent:
                bucket["defaulted"] += 1

    factors = []
    for f in registry.all_factors(sport=sport):
        entry: dict = {
            "factor": f.name,
            "added_utc": f.added_utc,
            "active": f.active,
            "applies_to": list(f.applies_to),
            "rationale": f.rationale,
            "note": f.note,
            "n": 0,
            "brier": None,
            "delta_brier": None,
            "mean_abs_contribution": None,
            "verdict": "no resolved predictions yet",
        }
        s = stats.get(f.name)
        if s and s["n"]:
            n = s["n"]
            with_brier = s["with"] / n
            without_brier = s["without"] / n
            mean_abs = s["abs_contribution"] / n
            nonzero_share = s["nonzero"] / n
            defaulted_share = s["defaulted"] / n
            entry.update(
                n=n,
                brier=round(with_brier, 4),
                brier_without=round(without_brier, 4),
                delta_brier=round(without_brier - with_brier, 5),
                mean_abs_contribution=round(mean_abs, 4),
                nonzero_share=round(nonzero_share, 4),
                defaulted_share=round(defaulted_share, 4),
                verdict=_factor_verdict(
                    without_brier - with_brier, mean_abs, n, nonzero_share, defaulted_share
                ),
            )
        elif not f.active:
            entry["verdict"] = "inactive; never used in a prediction"
        factors.append(entry)

    # What the current fit could actually do with each factor. A factor absent
    # from every training row, or present but never varying, has no coefficient
    # to score and would otherwise show as "no resolved predictions yet", which
    # reads like patience when it is really a measurement problem.
    #
    # EACH MARKET'S ACTIVE FIT, one entry per market that fit carries the
    # factor in (operator ruling 4, 2026-09-24: "the fit reports each factor's
    # rows used"). Until that day this read the NEWEST fit of the default
    # factor set under a market key that was wrong for every total, so the
    # page could describe a fit no market was forecasting from. The version
    # filter above scopes the RESOLVED predictions; the fits are the ones in
    # force, whatever it is.
    fit_status = _fit_status(conn, sport)
    for entry in factors:
        status = fit_status.get(entry["factor"])
        if not status:
            continue
        entry["fit_rows"] = status
        entry["fit_rows_words"] = language.fit_rows_words(sport, status)
        entry["excluded_from_fit"] = all(s["excluded"] for s in status)
        if entry["excluded_from_fit"] and not entry["n"]:
            entry["verdict"] = status[0]["reason"]

    factors.sort(key=lambda e: (-(e["delta_brier"] or -9), e["factor"]))
    return {
        "n": len(items),
        "sport": sport,
        "method": FACTOR_METHOD_NOTE,
        "factor_set_version": factor_set_version or config.FACTOR_SET_VERSION,
        "factors": factors,
    }


def _fit_status(conn: sqlite3.Connection, sport: str) -> dict[str, list[dict]]:
    """Per factor, the rows that carried it in each market's ACTIVE fit.

    ONE ENTRY PER MARKET, from the fit that market forecasts from
    (`activation.active_fit`), keyed by the market's own key
    (`baseline.market_key`) -- REPAIRED 2026-09-24 (operator ruling 4). It
    read the newest fit of one factor set for every market, looked a total
    up as 'prop:total', and kept the first market's count for a factor
    several markets share, so the wind on the page was one market's wind.

    `rows` is what the fit stored: the training rows that carried a value.
    `indoor_filled` marks a weather count taken before an indoor game carried
    no value (`registry.FILLED_INDOORS_UNTIL_2026_09_24`): those rows include
    domes given 0.0, which added nothing to the fit and are not readings.
    """
    from .model import activation, baseline

    out: dict[str, list[dict]] = {}
    for market in config.active_markets(sport):
        _, market_type = baseline.split_key(baseline.market_key(sport, market))
        active = activation.active_fit(conn, sport, market_type)
        if active is None:
            continue
        blob = json.loads(active["coefficients_json"])
        total = blob.get("n") or 0
        base = {"market": market, "fit_id": active["fit_id"],
                "factor_set_version": active["factor_set_version"], "n": total}
        presence = blob.get("presence") or {}
        filled = blob.get("indoor_weather") != factor_compute.INDOOR_WEATHER

        def add(name: str, rows, excluded: bool, reason: str | None = None):
            # Only a count that HAS rows can have domes among them: "0 of 64,
            # indoor games among them" rendered once and said nothing true.
            out.setdefault(name, []).append({
                **base, "rows": rows, "excluded": excluded, "reason": reason,
                "indoor_filled": bool(
                    filled and rows
                    and name in registry.FILLED_INDOORS_UNTIL_2026_09_24),
            })

        for name in (blob.get("coefficients") or {}):
            add(name, presence.get(name), False)
        for name, count in (blob.get("constant") or {}).items():
            add(name, count, True, (
                f"never varied where it could be measured - one value across all "
                f"{count:,} of {total:,} training rows that carried it, so there "
                "is nothing to fit and nothing to score"))
        for name, count in (blob.get("dropped") or {}).items():
            add(name, count, True, (
                f"measurable in only {count:,} of {total:,} training rows, below "
                "the floor for estimating a coefficient at all"))
    return out


def _factor_verdict(
    delta: float, mean_abs: float, n: int, nonzero_share: float, defaulted_share: float
) -> str:
    """Three different kinds of "nothing", told apart.

    A factor can look inert because its data was never available, because the
    world almost never let it vary, or because it genuinely does not matter.
    Only the third is a verdict on the hypothesis; reporting all three as
    "inert" would quietly retire good ideas for bad reasons.
    """
    if defaulted_share > 0.9:
        return (
            f"no data — defaulted in {defaulted_share * 100:.0f}% of predictions, "
            "so this has never actually been tested"
        )
    if nonzero_share < 0.05:
        return (
            f"input almost never varies ({nonzero_share * 100:.1f}% non-zero); "
            "untested rather than disproved"
        )
    if mean_abs < 0.005:
        return "inert — it barely moves any forecast"
    if n < config.MIN_SAMPLE_FOR_BUCKET_POINT:
        return f"too few resolved predictions ({n}) to say"
    if delta > 0.002:
        return "carrying weight"
    if delta < -0.002:
        return "costing accuracy"
    return "no measurable effect either way"


# ---------------------------------------------------------------------------
# the whole thing
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TWO PRE-LAW-6 FUNCTIONS WERE DELETED HERE, and they were not dead weight.
# ---------------------------------------------------------------------------
#
# `scorecard(conn)` and `version_comparison(conn)` -- no `sport` argument --
# were the versions from before LAW 6. Each queried `predictions` with no
# sport filter, which is the merged-across-sports read LAW 6 exists to make
# impossible. They were REPLACED further down the file by the `*, sport:`
# versions, and the old bodies were left in place.
#
# Python discards a shadowed definition, so neither ran. That is exactly why
# nothing caught them: `require_sport` never fired because the code never
# executed, the orphan scan saw the NAME reached (by the live definition's
# callers) and passed, and every test called the live one. Four hundred lines
# of a forbidden query, invisible to every guard in the project.
#
# Found by editing one of them and watching the output not change.
# `audit.check_no_shadowed_definitions` now fails on a redefined name.


def version_words(version: str) -> str:
    """A factor set named the way a person would name it: by when it started.

    "fs2" is an internal identifier -- it says neither what changed nor when,
    and the plain-words scan is right to reject it. The activation date is the
    thing that distinguishes one set from another to a reader, and it is
    already recorded. The code stays in the payload for matching against a
    stored row; it just does not reach the prose.
    """
    started = config.FACTOR_SET_ACTIVATED.get(version)
    return f"the set of {started[:10]}" if started else "an undated set"


def bucket_label(probability: float) -> str:
    """Which confidence bucket a stated probability falls in."""
    for lo, hi, label in BUCKETS:
        if lo <= probability < hi:
            return label
    return BUCKETS[-1][2]


def bucket_record(
    conn: sqlite3.Connection,
    probability: float,
    *,
    sport: str,
    market_type: str,
    prop_type: str | None = None,
    predictor: str = "statistical",
    factor_set_version: str | None = None,
    event_tier: str | None = None,
) -> dict:
    """How this bucket has actually done, for the chip on a pick card.

    Always carries `n`, including when `n` is zero. A chip that showed an
    accuracy without its sample size would be the most persuasive lie on the
    page: it sits right next to a specific forecast and reads as a track record
    for THAT pick.

    THE ONE DOOR A BAND IS COUNTED THROUGH -- the tier table's rows and the
    tier chip on every card -- AND ONE CARD'S FOR UFC (operator question 34,
    ruled 2026-09-30: "every UFC count is per card tier: tier table, ...";
    built 2026-10-08). The card is required for a sport that splits by card
    (`refuse_a_count_across_cards`); each entry carries it and the cards its
    rows were on (`tiers_counted`). Until this date a UFC band counted every
    card: "28 of 100" in moneyline's 50-60% band where Fight Night held 22
    and the Contender Series 6 (the re-read, 29 September).
    """
    label = bucket_label(probability)
    lo, hi = next((lo, hi) for lo, hi, name in BUCKETS if name == label)
    require_sport(sport, "calibration.bucket_record")
    refuse_a_count_across_cards(sport, event_tier, "a confidence band's count")
    items = [
        r
        for r in resolved(
            conn, sport=sport, market_type=market_type, prop_type=prop_type,
            predictor=predictor, factor_set_version=factor_set_version,
            event_tier=event_tier,
        )
        if lo <= r.model_prob < hi
    ]
    n = len(items)
    entry = {
        "label": label,
        "n": n,
        "provisional": n < config.MIN_SAMPLE_FOR_BUCKET_POINT,
        "minimum": config.MIN_SAMPLE_FOR_BUCKET_POINT,
    }
    if config.event_tiers(sport):
        # WHICH CARD, AND THE CARDS ITS ROWS WERE ON: only where the sport
        # splits by card, so no other sport's chip changes shape.
        entry["event_tier"] = event_tier
        entry["tiers_counted"] = _cards_of(items)
    if n:
        entry["actual"] = round(sum(r.outcome for r in items) / n, 4)
        entry["claimed"] = round(sum(r.model_prob for r in items) / n, 4)
    else:
        entry["actual"] = None
        entry["claimed"] = None
        entry["message"] = f"no resolved predictions in the {label} bucket yet"
    return entry


def bucket_on_no_card(probability: float, *, sport: str) -> dict:
    """THE BAND OF A QUESTION WHOSE OWN BOUT IS ON A CARD OF NO DECLARED KIND
    (the prover of operator question 34, 2026-10-08): in no card's count, so
    nothing settled stands behind it -- 0, named on no card.

    WHY NOT THE DOOR: `bucket_record` refuses a carded sport's band asked for
    no card, as it must (a band over every card is the pool question 34
    forbids), and the tier chip on every card and Results row asked it with
    the card read off the row's own bout. The source names some cards with no
    tier ("UFC Freedom 250", 14 June, is on the record) and the predict path
    writes a bout's questions whatever its card (`sports.ufc.slate_questions`
    reads no tier), so ONE such forecast made the door refuse inside
    `views.week` and `views.history` -- UFC's slate and the whole of UFC's
    Results answering 500 -- where until this release the chip counted every
    card. The board's badge (`board.build`) and the ranker's edge gate
    (`shortlist.rank_rows`) already count such a bout in no card's count, 0;
    this is the chip's same answer, and `assert_each_band_is_its_cards` holds
    every chip to it."""
    tiers = config.event_tiers(sport)
    if not tiers:
        raise PooledCount(
            f"a band on no declared card was asked in {sport}, which declares "
            f"no cards; its band is the door's (`bucket_record`).")
    label = bucket_label(probability)
    return {
        "label": label,
        "n": 0,
        "provisional": True,
        "minimum": config.MIN_SAMPLE_FOR_BUCKET_POINT,
        "event_tier": None,
        "tiers_counted": [],
        "on_no_card": True,
        "actual": None,
        "claimed": None,
        "message": language.band_on_no_card_words(label),
    }


def tier_from_bucket(bucket: dict) -> dict:
    """The tier chip for a pick, derived from the bucket record it already has.

    Takes the dict `bucket_record` returned rather than re-querying, so there is
    exactly one place that counts a bucket and exactly one number it can
    produce. `earned` is None below the threshold and the caller renders the
    shortfall instead — a tier that showed a hit rate on nine settled picks
    would be the most persuasive lie on the page, sitting beside a specific
    forecast and reading as a track record for it.
    """
    label = bucket.get("label")
    tier = TIERS.get(label)
    if tier is None:
        return {"tier": None, "earned": None, "n": 0, "proven": False,
                "message": "no tier for this probability"}

    n = bucket.get("n") or 0
    proven = n >= TIER_MIN_SETTLED
    entry = {
        "tier": tier,
        "bucket": label,
        "n": n,
        "needed": TIER_MIN_SETTLED,
        "proven": proven,
        "earned": bucket.get("actual") if proven else None,
    }
    # THE LABEL TELLS ITS OWN RECORD (S3, 2026-09-03), and says the tier's
    # NAME while doing it. "tier unproven - 19 settled of 20 needed" made a
    # reader carry the band in their head from the chip beside it; "STRONG --
    # 19 settled, not yet proven" is the same fact and needs nothing carried.
    entry["message"] = language.tier_record_line(
        tier, n, TIER_MIN_SETTLED, entry["earned"])
    if bucket.get("on_no_card"):
        # A BOUT ON A CARD OF NO DECLARED KIND SAYS SO (the prover of
        # operator question 34, 2026-10-08): its band is in no card's record,
        # which "0 settled" alone would not say (`bucket_on_no_card`).
        entry["message"] = language.tier_on_no_card_line(tier)
    # WHAT THE CHIP ITSELF READS (2026-09-04). Composed here rather than in the
    # browser, so a renderer cannot invent it -- and composed at all because
    # `message` above reached a grid card only as a hover tooltip, which is no
    # caveat on a phone. Measured across four live slates: 17 of 379 chips had
    # a settled record behind them.
    entry["chip_label"] = language.tier_chip_label(tier, proven)
    return entry


def over_time(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str = "statistical",
    factor_set_version: str | None = None,
) -> dict:
    """Weekly calibration points: how far claimed sat from actual, week by week.

    Each point carries its own n. Weeks are never smoothed into each other,
    because a rolling average across a thin week and a fat one is a line drawn
    through a sample size that never existed.
    """
    require_sport(sport, "calibration.over_time")
    items = resolved(
        conn, sport=sport, market_type=market_type, prop_type=prop_type,
        predictor=predictor, factor_set_version=factor_set_version,
    )
    weeks: dict[tuple[int, int], list[Resolved]] = {}
    for r in items:
        weeks.setdefault((r.season, r.week), []).append(r)

    points = []
    running = 0
    for (season, week) in sorted(weeks):
        chosen = weeks[(season, week)]
        n = len(chosen)
        running += n
        claimed = sum(r.model_prob for r in chosen) / n
        actual = sum(r.outcome for r in chosen) / n
        points.append({
            "season": season,
            "week": week,
            "label": f"{season} wk{week}",
            "n": n,
            "cumulative_n": running,
            "claimed": round(claimed, 4),
            "actual": round(actual, 4),
            "gap": round(actual - claimed, 4),
            "brier": round(logistic.brier(
                [r.model_prob for r in chosen], [r.outcome for r in chosen]), 4),
            "provisional": n < config.MIN_SAMPLE_FOR_BUCKET_POINT,
        })

    return {
        "n": len(items),
        "sport": sport,
        "filters": {
            "sport": sport,
            "market_type": market_type or "all",
            "prop_type": prop_type or "all",
            "predictor": predictor,
            "factor_set_version": factor_set_version or "all",
        },
        "points": points,
        "note": (
            "One point per week, each with its own N. Nothing is smoothed: a "
            "rolling average across a thin week and a fat one draws a line "
            "through a sample size that never existed."
        ),
    }


class MergedCurve(RuntimeError):
    """Two categories were averaged into one, which describes neither."""


class PooledCount(MergedCurve):
    """A count of a sport that splits below the market was asked for across
    its cards, or of a card that is not one of its declared tiers -- or a
    card was named in a sport that declares none (operator question 34,
    2026-10-08). Raised by the door, before anything is counted. A
    `MergedCurve`, so every door that answers 500 for a merged curve
    answers 500 for it."""


class PooledCardCount(MergedCurve):
    """A count beside a UFC card's name counted another card's rows, or
    every card's, or one the recount made without the door does not make
    (operator question 34, 2026-10-08). Raised by the builder's guard."""


def assert_no_merged_categories(payload: dict) -> None:
    """Every scoring category names exactly one concrete market of one sport.

    A "props" curve averaging rebounds with threes, a curve with
    `market_type: all`, or anything spanning two sports flatters reliably: the
    easy category dilutes the hard one and the result describes nobody. Checked
    on the payload rather than trusted to the code that built it.
    """
    sport = payload.get("sport")
    declared = set(config.SPORT_MARKETS.get(sport, ()))
    for category in payload.get("categories") or []:
        if category.get("sport") != sport:
            raise CrossSportAggregation(
                f"LAW 6: category {category.get('category')!r} reports sport "
                f"{category.get('sport')!r} inside a {sport!r} scorecard."
            )
        market = category.get("market")
        if market not in declared:
            raise MergedCurve(
                f"LAW: category {category.get('category')!r} reports market "
                f"{market!r}, which is not one of {sport}'s declared markets "
                f"{sorted(declared)}. Curves are never merged."
            )
        filters = category.get("filters") or {}
        if filters.get("predictor") in (None, "all"):
            raise MergedCurve(
                f"LAW: category {category.get('category')!r} merges the "
                "statistical and LLM forecasters into one curve."
            )
        is_prop = market in config.SPORT_PROP_MARKETS.get(sport, ())
        if is_prop and filters.get("prop_type") in (None, "all"):
            raise MergedCurve(
                f"LAW: category {category.get('category')!r} is a prop category "
                "with no prop_type filter, so it averages every prop market "
                "into a single number."
            )
        # LAW 6 ONE LEVEL DOWN (R2, 2026-09-03). A sport that splits below the
        # market may not report a category that spans its tiers: a UFC distance
        # curve mixing 43.6% Contender Series bouts with 58.0% numbered-card
        # ones describes neither, and flatters, for the same reason the law
        # forbids mixing sports.
        declared_tiers = config.event_tiers(sport)
        if declared_tiers:
            tier = category.get("event_tier")
            if tier in (None, "all"):
                raise MergedCurve(
                    f"LAW 6: category {category.get('category')!r} names no "
                    f"event tier, so it averages {sport}'s "
                    f"{len(declared_tiers)} tiers into one curve. Tiers are "
                    f"reported side by side, never summed."
                )
            if tier not in declared_tiers:
                raise MergedCurve(
                    f"LAW 6: category {category.get('category')!r} reports "
                    f"event tier {tier!r}, which is not one of {sport}'s "
                    f"declared tiers {list(declared_tiers)}."
                )


def assert_single_sport(payload, sport: str, path: str = "$") -> None:
    """LAW 6, on the finished payload: no nested figure names another sport.

    `require_sport` stops a cross-sport QUERY. This stops a cross-sport
    PAYLOAD — two individually correct queries stitched into one object that a
    reader would take for a single record.
    """
    if isinstance(payload, dict):
        if payload.get("side_by_side_sports"):
            # The one permitted multi-sport structure: the tab summary, which
            # lists every sport with its OWN counts and computes no total. LAW 6
            # forbids aggregating across sports, not displaying them beside each
            # other; this flag marks the difference explicitly rather than
            # leaving the validator to guess.
            return
        found = payload.get("sport")
        if found is not None and found != sport:
            raise CrossSportAggregation(
                f"LAW 6: {path} carries sport={found!r} inside a {sport!r} "
                "payload. Sports are reported side by side, never stitched "
                "into one record."
            )
        for key, value in payload.items():
            assert_single_sport(value, sport, f"{path}.{key}")
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            assert_single_sport(value, sport, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# factor-set versions: closed records and accumulating ones, never summed
# ---------------------------------------------------------------------------

VERSION_NOTE = (
    "A factor set is a different forecaster. Its record begins at N=0 on the day "
    "it was activated and nothing earlier is backfitted onto it (LAW 2). The "
    "versions below are reported side by side and are NEVER added together: a "
    "closed record and an accumulating one describe different models, and their "
    "sum describes neither."
)


def market_type_of(sport: str, market: str) -> str:
    """The `market_type` column value a named market is stored under."""
    if market in config.SPORT_PROP_MARKETS.get(sport, ()):
        return "prop"
    return market      # 'spread' or 'moneyline'


def prop_type_of(sport: str, market: str) -> str | None:
    return market if market in config.SPORT_PROP_MARKETS.get(sport, ()) else None


#: A factor's effect may order a sentence only when it rests on at least this
#: many settled predictions -- the same gate the tier table uses for a bucket.
#: Reused rather than invented: a second small-sample threshold with a
#: different number would be two answers to one question.
RANK_MIN_SETTLED = TIER_MIN_SETTLED


def _rank_changes(changes: dict, effects: dict) -> tuple[dict, str]:
    """Order a set's joined factors by measured effect, IF the record allows.

    "The two most consequential changes" needs consequence to be measured, and
    the only measurement here is a factor's effect on the record. Today every
    sport is at 2 to 25 settled predictions per factor; ordering by an effect
    computed on two is not a ranking, it is noise with a sort applied, and the
    sentence that came out of it would claim the two named mattered most.

    So the gate is explicit and the caller is TOLD which happened: with enough
    behind every candidate the list is sorted by |effect| and the line may say
    "the two that moved the answer most"; without it the declaration order
    stands and the line claims nothing about size.
    """
    joined = changes.get("joined") or []
    if not joined:
        return changes, "declaration"

    scored = []
    for item in joined:
        row = effects.get(item.get("name")) or {}
        n = row.get("n") or 0
        size = row.get("mean_abs_contribution")
        if n < RANK_MIN_SETTLED or size is None:
            return changes, "declaration"
        scored.append((abs(float(size)), item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    ranked = dict(changes)
    ranked["joined"] = [item for _size, item in scored]
    return ranked, "effect"


def version_comparison(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Every factor set that has produced predictions FOR THIS SPORT."""
    require_sport(sport, "calibration.version_comparison")
    seen = [
        r["v"]
        for r in conn.execute(
            "SELECT DISTINCT factor_set_version AS v FROM predictions"
            " WHERE sport = ? ORDER BY v",
            (sport,),
        )
    ]
    known = list(config.FACTOR_SET_HISTORY)
    versions = known + [v for v in seen if v not in known]

    # Each set's window runs from its own activation to the NEXT one's, so
    # "what changed" is read straight out of the registry rather than kept as a
    # hand-written changelog beside the version constant.
    # What each factor has actually been worth, for ordering the change lines.
    # Read once for the sport rather than per version: it is the same report.
    effects = {
        f["factor"]: f
        for f in (factor_report(conn, sport=sport).get("factors") or [])
    }
    starts = {v: (config.FACTOR_SET_ACTIVATED.get(v) or "")[:10] for v in versions}
    ordered = sorted([v for v in versions if starts.get(v)], key=lambda v: starts[v])

    entries = []
    for version in versions:
        # STANDING ROWS ONLY, the same clause every category beneath uses.
        # Counted off the raw table this said 280 written / 233 settled for
        # MLB's fs2 while the categories summed to 197 (audit 2026-09-05).
        counts = conn.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN p.resolved_utc IS NOT NULL THEN 1 ELSE 0 END) AS resolved"
            " FROM predictions p JOIN games g ON g.id = p.game_id"
            " WHERE p.sport = ? AND p.factor_set_version = ?"
            + standing_row_clause(True),
            (sport, version),
        ).fetchone()
        total = counts["total"] or 0
        n_resolved = counts["resolved"] or 0
        is_current = version == config.FACTOR_SET_VERSION

        categories = []
        # A SPORT THAT SPLITS BELOW THE MARKET GETS ONE CATEGORY PER TIER
        # (R2, 2026-09-03). `(None,)` for every other sport, so the loop below
        # is unchanged for four of the five and no category gains an empty
        # tier key it would have to be filtered out by later.
        tiers = config.event_tiers(sport) or (None,)
        for market in config.SPORT_MARKETS.get(sport, ()):
            for tier in tiers:
                for predictor in ("statistical", "llm"):
                    items = resolved(
                        conn,
                        sport=sport,
                        market_type=market_type_of(sport, market),
                        prop_type=prop_type_of(sport, market),
                        predictor=predictor,
                        factor_set_version=version,
                        event_tier=tier,
                    )
                    if not items and not is_current:
                        continue
                    entry_c = {
                        "category": (f"{market} / {tier} / {predictor}"
                                     if tier else f"{market} / {predictor}"),
                        "category_label": language.category_label(
                            market, tier, predictor,
                            config.retired_market(sport, market)),
                        "retired": config.retired_market(sport, market),
                        "market": market,
                        "predictor": predictor,
                        **score(items),
                    }
                    if tier:
                        entry_c["event_tier"] = tier
                        entry_c["tier_label"] = language.tier_label(tier)
                    categories.append(entry_c)

        start = starts.get(version) or None
        pos = ordered.index(version) if version in ordered else None
        nxt = ordered[pos + 1] if pos is not None and pos + 1 < len(ordered) else None
        changes = registry.set_changes(sport, start, starts.get(nxt)) if start else {}
        changes, ranked_by = _rank_changes(changes, effects)

        entry = {
            "version": version,
            "activated_utc": config.FACTOR_SET_ACTIVATED.get(version),
            # WHAT changed, not only when: derived from the registry's own
            # dates, so the line cannot drift from the factors it describes.
            "changed": (language.set_change_line(
                changes, first=(pos == 0), ranked_by=ranked_by,
                sport_label=config.SPORT_LABELS.get(sport, sport))
                if start else None),
            # THE FULL LIST, under the summary line. The line names two; the
            # ruling says the rest stays on the page rather than being lost to
            # a count, so it is carried here rather than left to the reader to
            # go and find on another page.
            "changed_detail": {
                "ranked_by": ranked_by,
                "joined": changes.get("joined") or [],
                "left": changes.get("left") or [],
                "tried_and_dropped": changes.get("tried_and_dropped") or [],
            } if start else None,
            "status": "current" if is_current else "closed",
            "n": n_resolved,
            "predictions_written": total,
            "open": total - n_resolved,
            "categories": categories,
        }
        if n_resolved == 0:
            label = config.SPORT_LABELS.get(sport, sport)
            entry["message"] = (
                f"{version_words(version).capitalize()} has {total} "
                f"prediction(s) written for {label} and 0 "
                "resolved. Its record begins at N=0 on activation"
                + ". Nothing is carried over from an earlier version, so there "
                "is nothing to show yet and nothing wrong."
            )
        entries.append(entry)

    return {
        "n": sum(e["n"] for e in entries),
        "sport": sport,
        "current": config.FACTOR_SET_VERSION,
        "note": VERSION_NOTE,
        "never_summed": True,
        "versions": entries,
    }


def blind_categories(conn: sqlite3.Connection, *, sport: str) -> list[dict]:
    """Every blind curve for ONE sport -- one per market, card and forecaster
    -- each with the outlook beside it, checked before anything is served.

    THE PAYLOAD BUILDER OF THE RECORD PAGE'S "RECORD BY CATEGORY" TABLE, taken
    out of `scorecard` on 2026-09-27 (operator question 14, 3 of 3) so the
    gate can build every sport's without the rest of the page, and the guard
    runs here, inside it: the API answers 500 rather than serve an outlook
    counting another record than the curve it sits under.

    AND THE VOID COUNT BESIDE EACH CURVE IS ITS OWN CARD'S (2026-10-01; the
    first of operator question 34's counts, built ahead of it because
    question 35's voids made this one false): each category carries the
    count `gridiron.recount` makes of its withdrawn forecasts without the
    category's door (`voids_recounted`), in the same read as the curves,
    and `assert_each_void_count_is_its_cards` runs here after the outlook's
    guard -- so the API answers 500 rather than serve a UFC card's void
    count of another card's withdrawals.
    """
    from . import db, recount

    require_sport(sport, "calibration.blind_categories")
    markets = config.SPORT_MARKETS.get(sport, ())
    categories = []
    # ONE CATEGORY PER TIER for a sport that splits below the market (R2),
    # and `(None,)` for the four that do not, so nothing changes for them.
    tiers = config.event_tiers(sport) or (None,)
    # ONE INSTANT FOR EVERY CURVE AND THE RECOUNT OF ITS VOIDS (2026-10-01),
    # as question 17's recounts are read: a forecast voided between the two
    # reads would make an honest count look pooled and the page answer 500.
    with db.one_instant(conn):
        withdrawn = recount.voids(conn, sport=sport)
        for market in markets:
            for tier in tiers:
                for predictor in ("statistical", "llm"):
                    c = curve(conn, sport=sport,
                              market_type=market_type_of(sport, market),
                              prop_type=prop_type_of(sport, market),
                              predictor=predictor, event_tier=tier)
                    c["category"] = (f"{market} / {tier} / {predictor}"
                                     if tier else f"{market} / {predictor}")
                    c["category_label"] = language.category_label(
                        market, tier, predictor, config.retired_market(sport, market))
                    c["retired"] = config.retired_market(sport, market)
                    c["market"] = market
                    # WHICH RECORD THIS ROW BELONGS TO (E4). Checked, not
                    # assumed: an at-the-line curve filed here would be
                    # averaging a forecast against a price with a forecast
                    # against its own rung.
                    c["record"] = "rung"
                    # ITS VOIDS, COUNTED WITHOUT ITS DOOR (2026-10-01): the
                    # recount the guard holds the void count to.
                    c["voids_recounted"] = recount.voids_in(
                        withdrawn, market_type=market_type_of(sport, market),
                        prop_type=prop_type_of(sport, market),
                        predictor=predictor, event_tier=tier)
                    # RULING R3: a gate that will not be reached is not a gate
                    # that has not been reached YET, and rendering them alike
                    # reads as progress.
                    #
                    # THE CURVE'S OWN FORECASTER AND CARD (operator question
                    # 14, 2026-09-27). The outlook is the statistical model's,
                    # beside its own curve on each card, counted through the
                    # door the curve's rows come from
                    # (`horizon.standing_questions`). Until this date one
                    # outlook per market, of every row on every card, sat
                    # beside each card's curve -- on the reasoning that the
                    # two forecasters answer the same questions, which the
                    # counts do not bear out (MLB moneyline 246 and 134
                    # standing on 27 September). The reasoning pass's curve in
                    # a market it is still asked carries its N and no
                    # projection, as it always has: the ruling rebuilds the
                    # counts the page states and adds none (FOLLOWUPS).
                    if predictor == "statistical":
                        c["outlook"] = horizon.market_outlook(
                            conn, sport, market, predictor=predictor,
                            event_tier=tier)
                    elif not config.llm_routed(sport, market):
                        # THE CURVE STOPS GROWING WITHOUT IMPLYING AN ERROR
                        # (ruling E1, 2026-09-06): the reasoning pass no
                        # longer asks this market, and the line says the
                        # count is final.
                        c["outlook"] = horizon.llm_routed_off_outlook(
                            conn, sport, market, event_tier=tier)
                    categories.append(c)
    payload = {"sport": sport, "record": "rung", "categories": categories}
    assert_no_pooled_outlooks(payload)
    assert_each_void_count_is_its_cards(payload)
    return categories


def assert_no_pooled_outlooks(payload: dict) -> None:
    """Every outlook beside a blind curve counts THAT CURVE'S standing
    questions: one forecaster's, one card's for UFC, each question once.

    The operator's ruling on question 14 (2026-09-27, 3 of 3): "Every count
    on the Record page that states a gate distance is rebuilt per forecaster
    (per tier for UFC) and per distinct bet, through its record's standing
    rule." Checked on the payload, as `assert_no_pooled_claims` checks the
    at-the-line record's -- and it runs `assert_no_merged_categories` first,
    so the sport, the market, the forecaster and the tier are one rule for
    every record.

    Then, for each category's outlook, by name: one filed from another
    record; one naming another forecaster than the curve's, or none, or
    counting another's rows (`forecasters_counted`); one naming another card
    than the curve's, or counting another card's bouts (`tiers_counted`, read
    off each row's own bout); a settled count or a pace counting more rows
    than distinct questions (a question's morning and final pass); a
    settled count or a pace other than the one `gridiron.recount` makes
    without the door, one per distinct bet by the one key (operator
    question 17, 2026-09-28: a door or a standing rule keyed without the
    rung, or across forecasters); a settled
    count that is not the curve's n -- two counts of one record (MLB
    moneyline said "330 of 100" beside a curve of 233 on 26 September); an
    expectation that is not its own counts' arithmetic; and a line stating
    another count than its own. Raised inside `blind_categories`, so the API
    answers 500 rather than serving the pool.
    """
    law = "LAW 4 / LAW 6 IN THE BLIND RECORD'S OUTLOOK"
    assert_no_merged_categories(payload)
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    for category in payload.get("categories") or []:
        outlook = category.get("outlook")
        if outlook is None:
            continue
        what = f"the outlook beside {category.get('category')!r}"
        if outlook.get("record") != "rung":
            raise MergedCurve(
                f"{law}: {what} belongs to the {outlook.get('record')!r} "
                f"record and is filed beside a blind curve.")
        named = (category.get("filters") or {}).get("predictor")
        if (outlook.get("predictor") != named
                or named not in horizon.FORECASTERS):
            raise MergedCurve(
                f"{law}: {what} names forecaster {outlook.get('predictor')!r} "
                f"beside the {named!r} forecaster's curve. The statistical "
                f"model's questions and the reasoning pass's are counted apart "
                f"and never pooled.")
        counted = outlook.get("forecasters_counted")
        if counted not in ([], [named]):
            raise MergedCurve(
                f"{law}: {what} is the {named!r} forecaster's and counts the "
                f"forecasts of {counted!r}: two forecasters pooled into one "
                f"count.")
        tier, cards = category.get("event_tier"), outlook.get("tiers_counted")
        if outlook.get("event_tier") != tier:
            raise MergedCurve(
                f"{law}: {what} names event tier {outlook.get('event_tier')!r} "
                f"beside the {tier!r} curve; {sport}'s cards are reported side "
                f"by side, never summed.")
        if tiers:
            if tier not in tiers or cards not in ([], [tier]):
                raise MergedCurve(
                    f"{law}: {what} names event tier {tier!r} and counts bouts "
                    f"on {cards!r}; {sport}'s tiers {list(tiers)} are reported "
                    f"side by side, never summed.")
        elif tier is not None or cards not in ([], None):
            raise MergedCurve(
                f"{law}: {what} names event tier {tier!r} in {sport}, which "
                f"declares none.")
        n, bets = outlook.get("resolved"), outlook.get("distinct_bets")
        if bets is None or n != bets or outlook.get("n") != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled forecasts for {bets} "
                f"distinct question{'' if bets == 1 else 's'}. A question is "
                f"counted once, on its standing forecast, however many passes "
                f"answered it.")
        written, asked = outlook.get("written"), outlook.get("distinct_bets_written")
        if asked is None or written != asked:
            raise MergedCurve(
                f"{law}: {what} paces {written} forecasts written this season "
                f"for {asked} distinct question{'' if asked == 1 else 's'}: a "
                f"rate from every pass projects questions nobody asked.")
        if n != category.get("n"):
            raise MergedCurve(
                f"{law}: {what} counts {n} settled beside a curve of "
                f"{category.get('n')!r}: two counts of one record.")
        if outlook.get("expected") != horizon.expected_from(outlook):
            raise MergedCurve(
                f"{law}: {what} expects {outlook.get('expected')!r} where its "
                f"own counts project {horizon.expected_from(outlook)!r}.")
        said = horizon.outlook_words(outlook)
        if outlook.get("message") != said:
            raise MergedCurve(
                f"{law}: {what} says {outlook.get('message')!r}, which is not "
                f"its own count of {n}: {said!r}.")
        # AND THE RECOUNT MADE WITHOUT THE DOOR (operator question 17,
        # 2026-09-28). The curve and the outlook both read the standing
        # clause, so a clause keyed without the rung, or across forecasters,
        # moves both alike and they still agree; only a count made without
        # it sees that they count other bets than the record holds.
        again, again_written = (outlook.get("recounted"),
                                outlook.get("recounted_written"))
        if again != n or again_written != written:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled and {written} written this "
                f"season where the recount made without its door finds "
                f"{again!r} and {again_written!r}, one per distinct bet by "
                f"the one key (`bet.of`: the forecaster, the game, the market, "
                f"the subject and the rung asked). A door or a standing rule "
                f"keyed any other way -- without the rung, or across "
                f"forecasters -- counts other bets than the record holds "
                f"(operator question 17, 2026-09-28).")
        # ONLY SLATES STILL TO COME, AND THE MOST IT CAN REACH (operator
        # question 33, ruled 2026-09-30; built 2026-10-08).
        refuse_slates_not_still_to_come(outlook, what)
        refuse_a_maximum_not_its_own(outlook, what)


class SlateNotStillToCome(MergedCurve):
    """An outlook multiplied its pace by a slate that is not still to come,
    or stated a most-reachable figure that is not its own counts'
    (operator question 33, 2026-10-08). A `MergedCurve`, so every door that
    answers 500 for a merged curve answers 500 for it."""


def refuse_slates_not_still_to_come(outlook: dict, what: str) -> None:
    """Every outlook that multiplies a pace by slates to come -- the blind
    record's and the at-the-line record's -- counts THE SLATES STILL TO
    COME AT THE CLOCK IT WAS ASKED AT, by the one rule, and no other
    (operator question 33, ruled 2026-09-30: "the outlook counts only cards
    still to come"; built 2026-10-08).

    Refused by name: an outlook carrying no slates or no recount of them (a
    payload carrying none, the precedent of question 17's `recounted`); one
    whose slates are not the ones `gridiron.recount.slates_to_come` finds
    without the rule -- a slate whose every game has started, or is past
    its listed start, counted because a game on it is still marked
    'scheduled' (the re-read's two fought Fight Night cards) -- naming each
    slate; and a count of slates that is not the list's. A retired market
    and a market the reasoning pass no longer asks project nothing and
    count none."""
    law = "QUESTION 33: AN OUTLOOK COUNTS ONLY SLATES STILL TO COME"
    if outlook.get("retired") or outlook.get("routed_off"):
        if outlook.get("slates_remaining") != 0 or outlook.get("to_come"):
            raise SlateNotStillToCome(
                f"{law}: {what} projects nothing and counts "
                f"{outlook.get('slates_remaining')!r} slates to come.")
        return
    ahead = outlook.get("slates_to_come")
    again = outlook.get("slates_to_come_recounted")
    if not isinstance(ahead, list) or not isinstance(again, list):
        raise SlateNotStillToCome(
            f"{law}: {what} carries no slates still to come, or no recount "
            f"of them, so nothing can show they are still to come.")
    if sorted(ahead) != sorted(again):
        extra = sorted(set(ahead) - set(again))
        lost = sorted(set(again) - set(ahead))
        raise SlateNotStillToCome(
            f"{law}: {what} counts as still to come the slates {sorted(ahead)} "
            f"where the recount made without its rule finds {sorted(again)}"
            + (f": every game on {extra} has started or is past its start, "
               f"though one may still be marked 'scheduled'" if extra else "")
            + (f"; and it leaves out {lost}, which hold a game still to come"
               if lost else "") + ".")
    if outlook.get("slates_remaining") != len(ahead):
        raise SlateNotStillToCome(
            f"{law}: {what} multiplies by {outlook.get('slates_remaining')!r} "
            f"slates to come beside a list of {len(ahead)}.")


def refuse_a_maximum_not_its_own(outlook: dict, what: str) -> None:
    """The most a blind outlook says its count can reach is its own counts'
    arithmetic, from the questions the recount finds on each slate
    (operator question 33, ruled 2026-09-30: "say the real maximum
    reachable this season"; built 2026-10-08).

    Refused by name: slates still to come other than the outlook's own
    list; questions on one of them -- settled or waiting -- or waiting on
    no slate still to come, other than `gridiron.recount.outlook` finds
    without the door; a part on the slates to come that is not its own
    arithmetic (`horizon.on_slates_to_come_from`); and a gate called
    reachable or not other than that figure against it. (The figure itself
    and the line are held above: `horizon.expected_from`,
    `horizon.outlook_words`.)"""
    law = "QUESTION 33: THE MOST AN OUTLOOK CAN REACH IS ITS OWN COUNTS'"
    if outlook.get("retired") or outlook.get("routed_off"):
        return
    to_come = outlook.get("to_come")
    if not isinstance(to_come, list):
        raise SlateNotStillToCome(
            f"{law}: {what} carries no questions on its slates to come.")
    if [e.get("slate") for e in to_come] != list(outlook.get("slates_to_come") or []):
        raise SlateNotStillToCome(
            f"{law}: {what} counts questions on the slates "
            f"{[e.get('slate') for e in to_come]} beside its slates still to "
            f"come {outlook.get('slates_to_come')!r}.")
    by_slate = outlook.get("recounted_by_slate") or {}
    for e in to_come:
        want = list(by_slate.get(e["slate"], by_slate.get(str(e["slate"]),
                                                          [0, 0])))
        if [e.get("settled"), e.get("waiting")] != want:
            raise SlateNotStillToCome(
                f"{law}: {what} counts {e.get('settled')!r} settled and "
                f"{e.get('waiting')!r} waiting on slate {e['slate']} where the "
                f"recount made without its door finds {want[0]} and "
                f"{want[1]}.")
    waiting = outlook.get("recounted_waiting")
    elsewhere = (None if waiting is None
                 else waiting - sum(e["waiting"] for e in to_come))
    if outlook.get("waiting_elsewhere") != elsewhere:
        raise SlateNotStillToCome(
            f"{law}: {what} counts {outlook.get('waiting_elsewhere')!r} "
            f"questions waiting to settle on slates no longer to come where "
            f"the recount finds {elsewhere!r}.")
    on = horizon.on_slates_to_come_from(outlook)
    if outlook.get("on_slates_to_come") != on:
        raise SlateNotStillToCome(
            f"{law}: {what} puts {outlook.get('on_slates_to_come')!r} on its "
            f"slates still to come where its own counts make {on!r}.")
    expected = outlook.get("expected")
    gate = outlook.get("gate", config.MIN_SAMPLE_FOR_EDGE_CLAIM)
    if expected is not None and outlook.get("reachable") != (expected >= gate):
        raise SlateNotStillToCome(
            f"{law}: {what} calls its gate reachable={outlook.get('reachable')!r} "
            f"where the most it can reach is {expected} of {gate!r}.")
    # THE WORDS SAY IT AS THE MOST, AND SAY IT CANNOT CLEAR EXACTLY WHERE IT
    # CANNOT (read here apart from the one composition, so words put back to
    # "~N expected" are seen even where the composer itself was put back).
    said = outlook.get("message") or ""
    if expected is not None:
        if not re.search(rf"\bat most ~?{expected}\b", said):
            raise SlateNotStillToCome(
                f"{law}: {what} says {said!r}, which does not say the most it "
                f"can reach, {expected}, as the most ('at most').")
        if ("CANNOT CLEAR" in said) != (expected < gate):
            raise SlateNotStillToCome(
                f"{law}: {what} says {said!r} of a most of {expected} against "
                f"a gate of {gate}: the gate cannot clear exactly where the "
                f"most it can reach is under it.")


class PooledVoidCount(MergedCurve):
    """A category's void count counted withdrawn forecasts of another card
    than the curve it sits beside (2026-10-01). A `MergedCurve`, so every
    door that answers 500 for a merged curve answers 500 for it."""


def assert_each_void_count_is_its_cards(payload: dict) -> None:
    """Every void count, and the void rate made from it, beside a blind
    curve counts THAT CURVE'S withdrawn forecasts: one card's for UFC, the
    card its curve counts (2026-10-01).

    THE FIRST OF OPERATOR QUESTION 34'S COUNTS, BUILT AHEAD OF IT. Question
    34 (ruled 2026-09-30: "every UFC count is per card tier: tier table,
    ranker, taken record, edge figure, board badge. Planting each.") is
    later in the order; this one count is built now because question 35's
    own voids would make it false. `curve` handed the card to `resolved`
    and not to `void_count`, so the count beside each UFC curve was its
    market's across every card: once the eighteen final passes 1014-1031
    (all Fight Night) are voided, each UFC market's Contender Series
    category reads "voided 6, void rate 0.3", its Numbered card category
    "voided 6, void rate 1.0" on 0 settled, and the Record page's line
    under the chart ("0 resolved, 6 withdrawn", the Numbered card's) with
    them -- only Fight Night's 6 is true.

    Refused by name, for each category of the payload: a void count that
    is not a whole number; withdrawn forecasts counted on another card than
    the category's, or on a card the source left unnamed, or on any card
    in a sport that does not split by card (`void_tiers_counted`, read off
    each withdrawn row's own bout); a void count other than the one
    `gridiron.recount` makes without the category's door
    (`voids_recounted`: a door that stopped asking for the card agrees
    with its own rows); and a void rate that is not its own counts'
    arithmetic (`void_rate`). Raised inside `blind_categories`, after the
    outlook's guard, so `/api/scorecard` answers 500 rather than serve it,
    and in gate step 2 for every sport that splits by card
    (`audit.check_a_ufc_void_count_is_its_cards`).
    """
    law = "LAW 4 / LAW 6 IN A CATEGORY'S VOID COUNT (EVERY UFC COUNT IS PER CARD)"
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    for category in payload.get("categories") or []:
        what = f"the void count beside {category.get('category')!r}"
        tier = category.get("event_tier")
        voided = category.get("voided")
        if not isinstance(voided, int) or isinstance(voided, bool) or voided < 0:
            raise PooledVoidCount(
                f"{law}: {what} is {voided!r}, not a count of withdrawn "
                f"forecasts.")
        cards = category.get("void_tiers_counted")
        if tiers:
            if cards != ([tier] if voided else []):
                raise PooledVoidCount(
                    f"{law}: {what} counts {voided} withdrawn forecast"
                    f"{'' if voided == 1 else 's'} on {cards!r} beside the "
                    f"{tier!r} curve: a UFC category counts its own card's "
                    f"voids, the card its curve counts -- {sport}'s cards "
                    f"{list(tiers)} are reported side by side, never summed.")
        elif cards != []:
            raise PooledVoidCount(
                f"{law}: {what} names the cards {cards!r} in {sport}, which "
                f"declares none.")
        again = category.get("voids_recounted")
        if again != voided:
            raise PooledVoidCount(
                f"{law}: {what} counts {voided} withdrawn where the recount "
                f"made without its door finds {again!r} on the category's "
                f"own market, forecaster and card: a void count asked of "
                f"another population than the curve's.")
        rate = void_rate(category.get("n") or 0, voided)
        if category.get("void_rate") != rate:
            raise PooledVoidCount(
                f"{law}: {what} states a void rate of "
                f"{category.get('void_rate')!r} where its own counts -- "
                f"{voided} withdrawn beside {category.get('n')!r} settled -- "
                f"make {rate!r}.")


#: WHAT A CORRECTION GATE'S PAYLOAD MAY CARRY AT ITS TOP LEVEL (operator
#: question 16, 2026-09-29): `n` is how many categories or rows, never a
#: settled count; any other figure there is a total over forecasters, markets
#: or prop types, which describes nobody's record.
CORRECTION_PAYLOAD_KEYS = {
    "correction": {"sport", "record", "n", "min_train", "categories",
                   "any_active", "note"},
    "learning": {"sport", "record", "n", "last_refit", "categories",
                 "never_rewrites", "note"},
}


def assert_no_pooled_correction_counts(payload: dict) -> None:
    """Every correction count the Record page states is the count the fit's
    own gate reads: ONE forecaster's category -- every prop type together,
    every card together -- EACH QUESTION ONCE (operator question 16, ruled
    (B) 2026-09-27: "on its key. Each correction gate's count per forecaster
    and distinct bet"; question 23, ruled (A) 2026-09-28; built 2026-09-29).

    Two payloads, one rule: the gate list's categories (`record`
    'correction', `views.corrections_report`) and the learning panel's rows
    (`record` 'learning', `views.learning`, each row's `correction`). Refused
    by name: a count naming no forecaster or one of neither, or counting
    another's forecasts (`forecasters_counted`); one prop type's count, or
    one filed under another market than its row's; a count of more
    forecasts than distinct questions (a question's morning and final pass,
    the page's count until this date); a count the recount made without the
    door does not make (`recounted`: a door keyed without the rung, or
    across forecasters, agrees with its own rows); one category stated twice
    in the gate list, or stated two ways across the learning panel's rows; a
    gate line or a row's `n` stating another count than its own; a label or
    a row's words that do not say the category is every prop type (every
    card) together; a version's forward count other than its questions or
    its recount; and a total at the top level. Raised inside both builders,
    so `/api/scorecard` and `/api/learning` answer 500 rather than serve it,
    and in the gate for every sport on the record's copy
    (`audit.check_the_correction_counts_are_never_pooled`).
    """
    law = "LAW 4 / LAW 6 IN THE CORRECTION GATES"
    from . import correction

    sport = payload.get("sport")
    kind = payload.get("record")
    if kind not in CORRECTION_PAYLOAD_KEYS:
        raise MergedCurve(f"{law}: a correction payload filed as {kind!r}.")
    extra = sorted(set(payload) - CORRECTION_PAYLOAD_KEYS[kind])
    if extra:
        raise MergedCurve(
            f"{law}: the {kind} payload carries {extra} beside its categories: "
            f"a figure over every category describes nobody's record.")
    rows = payload.get("categories") or []
    if payload.get("n") != len(rows):
        raise MergedCurve(
            f"{law}: the {kind} payload's n is {payload.get('n')!r} for "
            f"{len(rows)} categories: a sum of their counts is a total.")
    stated: dict[tuple, int] = {}
    for row in rows:
        count = row if kind == "correction" else (row.get("correction") or {})
        market_type, forecaster = count.get("market_type"), count.get("forecaster")
        what = (f"the correction for {row.get('label')!r}" if kind == "correction"
                else f"the learning panel's {row.get('market')!r} row")
        if count.get("sport") != sport:
            raise CrossSportAggregation(
                f"LAW 6: {what} counts sport {count.get('sport')!r} inside a "
                f"{sport!r} payload.")
        if forecaster not in correction.FORECASTERS:
            raise MergedCurve(
                f"{law}: {what} names forecaster {forecaster!r}. A correction "
                f"is one forecaster's, and so is its count.")
        counted = count.get("forecasters_counted")
        if counted not in ([], [forecaster]):
            raise MergedCurve(
                f"{law}: {what} is the {forecaster!r} forecaster's and counts "
                f"the forecasts of {counted!r}: two forecasters pooled into one "
                f"count.")
        if market_type in config.SPORT_PROP_MARKETS.get(sport, ()):
            raise MergedCurve(
                f"{law}: {what} counts one prop type ({market_type!r}); a "
                f"correction is fitted, and gated, for every prop type "
                f"together.")
        n, bets = count.get("settled"), count.get("distinct_bets")
        if bets is None or n != bets:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled for {bets} distinct "
                f"question{'' if bets == 1 else 's'}. A question is counted "
                f"once however many passes answered it -- the count the fit's "
                f"own gate reads from question 16's release.")
        if count.get("recounted") != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled questions where the recount "
                f"made without its door finds {count.get('recounted')!r}, one "
                f"per distinct bet by the one key (`bet.of`: the forecaster, "
                f"the game, the market, the subject and the rung asked). A "
                f"door keyed any other way -- without the rung, or across "
                f"forecasters -- counts other bets than the record holds.")
        scope = language.correction_scope_words(sport, market_type)
        if (count.get("every_prop_type") != (market_type == "prop")
                or count.get("every_card") != bool(config.event_tiers(sport))):
            raise MergedCurve(
                f"{law}: {what} does not say what its category holds: "
                f"{scope or 'one market'!r}.")
        key = (market_type, forecaster)
        if kind == "correction":
            if key in stated:
                raise MergedCurve(
                    f"{law}: {what} is stated twice in the gate list, so one "
                    f"category is counted on two rows.")
            if row.get("label") != language.correction_category_label(
                    sport, market_type, forecaster):
                raise MergedCurve(
                    f"{law}: {what} is not named for its category -- "
                    f"{language.correction_category_label(sport, market_type, forecaster)!r} "
                    f"-- so its count reads as another's.")
            if row.get("progress") != language.correction_gate_progress(
                    n, correction.MIN_TRAIN):
                raise MergedCurve(
                    f"{law}: {what} says {(row.get('progress') or {}).get('line')!r}, "
                    f"which is not its own count of {n} settled questions.")
            for version in row.get("versions") or []:
                forward = version.get("forward") or {}
                if (forward.get("n") != forward.get("distinct_bets")
                        or forward.get("recounted") != forward.get("n")
                        or forward.get("forecasters_counted") not in (
                            [], [forecaster])):
                    raise MergedCurve(
                        f"{law}: {what}, version {version.get('version')}, "
                        f"counts {forward.get('n')!r} forward for "
                        f"{forward.get('distinct_bets')!r} distinct questions "
                        f"of {forward.get('forecasters_counted')!r}, and the "
                        f"recount finds {forward.get('recounted')!r}: the "
                        f"forward count is each question once, one "
                        f"forecaster's.")
        else:
            if market_type != market_type_of(sport, row.get("market")):
                raise MergedCurve(
                    f"{law}: {what} states the count of {market_type!r}, not "
                    f"its own market's category.")
            if key in stated and stated[key] != n:
                raise MergedCurve(
                    f"{law}: {what} states {n} for a category another row "
                    f"states as {stated[key]}: one category, two counts.")
            if row.get("n") != n:
                raise MergedCurve(
                    f"{law}: {what} has n {row.get('n')!r} beside its "
                    f"category's count of {n}.")
            words = row.get("status_words") or ""
            said = (f"{n} {language.CORRECTION_GATE_NOUN}",
                    f"{n} of {correction.MIN_TRAIN} "
                    f"{language.CORRECTION_GATE_NOUN}")
            if not any(s in words for s in said) or (
                    scope and scope not in words):
                raise MergedCurve(
                    f"{law}: {what} says {words!r}, which does not state its "
                    f"category's count of {n} settled questions"
                    + (f" or say it is {scope}" if scope else "") + ".")
        stated[key] = n


def scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Every curve for ONE sport, kept separate. Never a merged headline."""
    require_sport(sport, "calibration.scorecard")
    markets = config.SPORT_MARKETS.get(sport, ())
    categories = blind_categories(conn, sport=sport)
    tiers = config.event_tiers(sport)

    headline_market = markets[0] if markets else "spread"
    # THE HEADLINE CURVE IS NEVER DRAWN FOR A SPORT THAT SPLITS BY CARD, AND
    # IS NOT MADE FOR ONE (operator question 34, ruled 2026-09-30; built
    # 2026-10-08). It is the chart's fallback, drawn only where no category
    # matches the market and forecaster chosen (app.js `findCurve`); every
    # UFC market, card and forecaster is a category of its own, so it was
    # never drawn for UFC -- and what the API served under its name was every
    # card's moneyline curve as one population, the pool LAW 6 forbids one
    # level down (the void-count row of CLAUDE.md named it "question 34's
    # ground"). Split, it would only repeat the categories; so it is None,
    # and the chart falls back to a category of the forecaster chosen.
    headline = None
    if not tiers:
        headline = curve(conn, sport=sport,
                         market_type=market_type_of(sport, headline_market),
                         prop_type=prop_type_of(sport, headline_market),
                         predictor="statistical")
        headline["market"] = headline_market
    # THE TIER TABLE AND THE EDGE FIGURE, ONE CARD'S EACH (operator question
    # 34, 2026-10-08): for UFC the tier table is the first declared card's
    # (the page's card choice asks for any other through `/api/tier-table`)
    # and the edge question is answered once per card, each named.
    first_card = tiers[0] if tiers else None

    def edge_of(tier):
        return edge(conn, sport=sport,
                    market_type=market_type_of(sport, headline_market),
                    prop_type=prop_type_of(sport, headline_market),
                    predictor="statistical", event_tier=tier)

    payload = {
        "sport": sport,
        "record": "rung",
        "sport_label": config.SPORT_LABELS.get(sport, sport.upper()),
        "generated_for_factor_set": config.FACTOR_SET_VERSION,
        "headline": headline,
        "headline_market": headline_market,
        # THE TIER TABLE leads the Record tab. Same bucket math as the chips on
        # every pick card -- one implementation, so the two cannot drift.
        "tier_table": tier_table(
            conn, sport=sport,
            market_type=market_type_of(sport, headline_market),
            prop_type=prop_type_of(sport, headline_market),
            predictor="statistical", event_tier=first_card,
        ),
        "categories": categories,
        "markets": list(markets),
        "edge": None if tiers else edge_of(None),
        "versions": version_comparison(conn, sport=sport),
        "separation_note": (
            "Curves are never merged, and never across sports (LAW 6). Each "
            "market is its own category with its own gate, and the statistical "
            "and LLM predictors are different forecasters. An average across "
            "any of these describes nobody."
        ),
    }
    if tiers:
        # THE CARDS, IN WORDS, FOR THE PAGE'S CARD CHOICE, AND ONE EDGE
        # QUESTION PER CARD (operator question 34, 2026-10-08).
        payload["cards"] = [{"tier": t, "label": language.tier_label(t)}
                            for t in tiers]
        payload["edges"] = [edge_of(t) for t in tiers]
    # THE OTHER RECORD, BESIDE THIS ONE AND NEVER INSIDE IT (E4, 2026-09-06).
    # Its own curves, its own gate, its own guard; the Record page draws it as
    # a separate section for the same reason.
    payload["at_the_line"] = at_the_line_scorecard(conn, sport=sport)
    # AND THE ORDERING'S OWN RECORD (S3, 2026-09-07): did the questions that
    # led each slate score better than the ones they outranked? Beside the
    # curves, never inside them -- this is a fact about the ranker, not about
    # the model.
    payload["ranker"] = ranker_scorecard(conn, sport=sport)
    # THE CLOSING LINE (R3, 2026-09-07): the first verdict available on whether
    # the app is buying cheap. Its own section, its own minimum, and capable of
    # returning bad news in words written before it was needed.
    #
    # ONE INSTANT FOR BOTH READS OF IT (2026-09-27): the closing line and the
    # kill criterion below ask the same window, and two readings of the clock
    # either side of midnight UTC on 15 October could have given the page a
    # verdict in one panel and none in the other.
    from . import audit, db
    from .db import utcnow
    from .priced import coverage as _coverage

    read_at = utcnow()
    # AND ONE INSTANT OF THE DATABASE FOR THE CLOSING LINE, THE KILL READ OF
    # IT AND BOTH RECOUNTS OF IT (the prover of operator question 22,
    # 2026-09-28; question 17's `db.one_instant`). Read one after another on
    # the live record, a close the closer wrote between the line and its
    # recount made an honest page refuse itself ("reports 1 ... holds 2", a
    # 500); the recounts ran in `views.scorecard` until this date, after
    # everything else on the page had been read.
    with db.one_instant(conn):
        payload["closing_line"] = clv_report(conn, sport=sport, now=read_at)
        stopped = list(_coverage.stopped(conn, sport, now=read_at).values())
        # NO WITHDRAWN RECOMMENDATION IS COUNTED (ruling 1, 2026-09-24), and
        # EACH FORECASTER'S DISTINCT BET ONCE (questions 12 and 22): both
        # recounted without the doors the report used, so neither reaches
        # the API.
        audit.check_no_withdrawn_recommendation_counted(
            conn, payload["closing_line"])
        audit.check_each_pair_counted_once(conn, payload["closing_line"])
    # AND WHETHER PACKAGES ARE WORTH TAKING AT ALL (GRIDIRON_COMBOS C4,
    # 2026-09-08). The kill criterion was declared before the first package
    # existed and is printed from the first day, so its wording cannot be
    # chosen later to suit the numbers.
    # The packages he marked, on their own line and never inside a leg's.
    payload["taken_packages"] = taken_packages(conn, sport=sport)
    # WHAT THE ENGINE IS ALLOWED TO PRICE AT ALL (P2, 2026-09-07), with the
    # measurement behind every entry and the reason for every exclusion; the
    # kill criterion's stops read above, in the closing line's instant.
    covered = _coverage.coverage(conn, sport)
    covered["words"] = language.priced_coverage_line(
        config.SPORT_LABELS.get(sport, sport.upper()), covered["covered"],
        len(covered["entries"]))
    covered["stopped"] = stopped
    payload["coverage"] = covered
    payload["priced"] = priced_scorecard(conn, sport=sport)

    assert_every_figure_has_n(payload)
    assert_no_merged_categories(payload)
    assert_the_records_stay_apart(payload)
    assert_single_sport(payload, sport)
    assert_no_pooled_headline(payload)
    return payload


def assert_no_pooled_headline(payload: dict) -> None:
    """NO HEADLINE CURVE AND NO EDGE QUESTION OVER EVERY CARD (operator
    question 34, ruled 2026-09-30; built 2026-10-08). For a sport that
    splits by card the Record page's payload carries no headline curve (it
    would be every card's moneyline as one population), no edge question
    but one per card, each naming its own (`edges`), and a tier table naming
    a card. Refused by name inside `scorecard`, so `/api/scorecard` answers
    500 rather than serve the pool."""
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    law = "QUESTION 34: EVERY UFC COUNT IS PER CARD TIER"
    if not tiers:
        return
    if payload.get("headline") is not None:
        raise PooledCardCount(
            f"{law}: the {sport} Record page carries a headline curve, every "
            f"card's {payload.get('headline_market')} as one population; "
            f"{sport}'s cards {list(tiers)} are reported side by side.")
    if payload.get("edge") is not None:
        raise PooledCardCount(
            f"{law}: the {sport} Record page carries one edge question over "
            f"every card; it is asked once per card.")
    asked = [e.get("event_tier") for e in payload.get("edges") or []]
    if asked != list(tiers):
        raise PooledCardCount(
            f"{law}: the {sport} Record page answers the edge question for "
            f"the cards {asked!r}, not once for each of {list(tiers)}.")
    if (payload.get("tier_table") or {}).get("event_tier") not in tiers:
        raise PooledCardCount(
            f"{law}: the {sport} Record page's tier table names no card.")

# ---------------------------------------------------------------------------
# THE TIER TABLE — the record as the operator already reads it
# ---------------------------------------------------------------------------
#
# The Record tab led with a calibration chart. A chart is the right shape for
# somebody auditing the model and the wrong shape for the question a reader
# actually has, which is "when it says STRONG, is it?". This is that question as
# a table, in the same vocabulary the tier chips on every pick already use.
#
# ONE ROW PER BUCKET, NOT PER TIER, AND THAT IS NOT A DETAIL. The brief that
# asked for this said the buckets and the tiers are "the same partition (LEAN
# 50-60, SOLID 60-70, STRONG 70%+)". They are not: there are four buckets and
# three tiers, because STRONG spans 70-80% AND 80%+. Collapsing them into one
# STRONG row is precisely the merge LAW 4 forbids, and it flatters in a
# predictable direction -- the easier bucket lifts the harder one, so a model
# that is well calibrated at 80%+ and badly calibrated at 70-80% would show a
# single reassuring number.
#
# So STRONG appears twice, labelled with its band. The table answers the same
# question and cannot tell that particular lie.

#: How far actual may sit from claimed before the verdict stops saying so, in
#: PERCENTAGE POINTS. Dated because it is a judgement about what "about right"
#: means, not a measurement.
VERDICT_BANDS_DECLARED = "2026-08-31T00:00:00Z"
VERDICT_CLOSE_ENOUGH = 3.0      # within this, the claim is honest
VERDICT_BADLY_OFF = 8.0         # beyond this, the claim is not close


def tier_verdict(claimed: float | None, actual: float | None, n: int) -> str:
    """The verdict words for one row, from a fixed rule on (actual - claimed).

    Below the gate there is no verdict, only the shortfall: a row with nine
    settled picks has nothing to say about calibration and must not imply it
    does (LAW 4). No italics, no hedge, no number.
    """
    if n < TIER_MIN_SETTLED:
        return f"unproven — {n} of {TIER_MIN_SETTLED}"
    if claimed is None or actual is None:
        return f"unproven — {n} of {TIER_MIN_SETTLED}"

    # Rounded to one decimal BEFORE the comparison. 0.53 - 0.50 is
    # 3.0000000000000027 in binary floating point, so a gap the rule calls
    # "close enough" fell out of its own band and read "overconfident by 3.0
    # points" -- a boundary decided by representation error rather than by the
    # declared threshold.
    gap = round((actual - claimed) * 100.0, 1)
    if abs(gap) <= VERDICT_CLOSE_ENOUGH:
        return "about as good as it claims"
    if gap > VERDICT_CLOSE_ENOUGH:
        return "better than it claims"
    if gap >= -VERDICT_BADLY_OFF:
        # ONE DECIMAL, not zero. A gap of 3.4 rounded to "3 points" sits
        # directly beside a rule that calls anything within 3 points honest,
        # and a reader is entitled to conclude one of them is wrong. The
        # decimal costs a character and removes the contradiction.
        return f"overconfident by {abs(gap):.1f} points"
    return "much more confident than it should be"


def tier_table(
    conn: sqlite3.Connection,
    *,
    sport: str,
    market_type: str,
    prop_type: str | None = None,
    predictor: str = "statistical",
    event_tier: str | None = None,
) -> dict:
    """One row per confidence band, with its verdict.

    EVERY NUMBER COMES FROM `bucket_record`, the same function the tier chip on
    a pick card calls. Not a reimplementation that happens to agree today: the
    chip and this table cannot drift, because there is one place that counts a
    bucket and one number it can produce.

    ONE CARD'S FOR UFC (operator question 34, ruled 2026-09-30; built
    2026-10-08): the card is required for a sport that splits by card, the
    table names it, and carries the cards its bands' rows were on and each
    band's count as `gridiron.recount` makes it without the door;
    `assert_no_pooled_tier_table` refuses another card's count inside this
    builder, so `/api/scorecard` and `/api/tier-table` answer 500. Until
    this date UFC's bands read 28/15/4/2 over the three cards together.
    """
    from . import db, recount

    require_sport(sport, "calibration.tier_table")
    refuse_a_count_across_cards(sport, event_tier, "the tier table")

    rows = []
    cards: set = set()
    with db.one_instant(conn):
        buckets = []
        for lo, hi, label in BUCKETS:
            midpoint = (lo + min(hi, 1.0)) / 2.0
            buckets.append((label, bucket_record(
                conn, midpoint, sport=sport, market_type=market_type,
                prop_type=prop_type, predictor=predictor,
                event_tier=event_tier)))
        again = recount.in_bands(recount.settled_standing(
            conn, sport=sport, predictor=predictor, market_type=market_type,
            prop_type=prop_type, event_tier=event_tier), BUCKETS)
    for label, bucket in buckets:
        cards.update(bucket.get("tiers_counted") or [])
        n = bucket.get("n") or 0
        proven = n >= TIER_MIN_SETTLED
        claimed = bucket.get("claimed") if proven else None
        actual = bucket.get("actual") if proven else None
        rows.append({
            "tier": TIERS.get(label),
            "band": label,
            "n": n,
            "settled": n,
            "right": round((actual or 0) * n) if proven else None,
            "claimed": claimed,
            "actual": actual,
            "proven": proven,
            "needed": TIER_MIN_SETTLED,
            "verdict": tier_verdict(claimed, actual, n),
            # HOW CLOSE THIS ROW IS (GRIDIRON_13 P1). The verdict gate at 20,
            # and once that is behind it the edge gate at 100. Counts only --
            # `audit.progress_faults` refuses a share of the way to a verdict,
            # because a percentage on this page reads as a probability.
            "progress": language.gate_progress(
                n, TIER_MIN_SETTLED, config.MIN_SAMPLE_FOR_EDGE_CLAIM),
        })

    table = {
        "sport": sport,
        "market_type": market_type,
        "prop_type": prop_type,
        "predictor": predictor,
        "rows": rows,
        "n": sum(r["n"] for r in rows),
        "minimum": TIER_MIN_SETTLED,
        "headline": _tier_headline(rows),
        "bands_note": (
            "One row per confidence band. STRONG spans two bands and they are "
            "shown separately: pooling them would let the easier one lift the "
            "harder one, which is the merge LAW 4 forbids."
        ),
        # WHICH NUMBERS THIS TABLE IS GRADING. A tier table over corrected
        # claims and one over raw claims are different tables, and a reader
        # comparing today's against last month's has to be told which they are
        # looking at.
        "corrections_note": _corrections_note(
            conn, sport=sport, market_type=market_type, predictor=predictor),
        # THE CORRECTION'S VERSION, IN THE NOTE'S TOOLTIP (operator question
        # 19; the board merge, 2026-09-29): the note names it by its day.
        "corrections_tip": _corrections_tip(
            conn, sport=sport, market_type=market_type, predictor=predictor),
        # WHICH GATE IS NEAREST, named once at the top rather than left for a
        # reader to work out by comparing four rows.
        "closest": _closest_verdict(conn, rows, sport=sport),
    }
    if config.event_tiers(sport):
        # ONE CARD'S, NAMED, AND COUNTED AGAIN WITHOUT THE DOOR (operator
        # question 34, 2026-10-08) -- keys only a carded sport's table
        # carries, so no other sport's table changes shape.
        table["event_tier"] = event_tier
        table["card_label"] = language.tier_label(event_tier) or None
        table["tiers_counted"] = sorted(cards, key=str)
    table["recounted"] = again
    assert_no_pooled_tier_table(table)
    return table


def assert_no_pooled_tier_table(table: dict) -> None:
    """THE TIER TABLE'S BANDS ARE ONE CARD'S FOR UFC (operator question 34,
    ruled 2026-09-30; built 2026-10-08). Refused by name, inside
    `tier_table`: a table naming no card, or one of none, in a sport that
    splits by card; bands counting rows on another card than it names, or
    on every card (`tiers_counted`, read off each row's own bout); a band
    whose count is not the one `gridiron.recount` makes without the door
    (`recounted`); and a table's n that is not its bands' sum."""
    sport = table.get("sport")
    what = (f"the tier table for {sport} "
            f"{table.get('prop_type') or table.get('market_type')}, "
            f"{table.get('predictor')}")
    refuse_another_cards_count(sport, table.get("event_tier"),
                               table.get("tiers_counted", []), what)
    counts = [r.get("n") for r in table.get("rows") or []]
    if table.get("recounted") != counts:
        raise PooledCardCount(
            f"QUESTION 34: EVERY UFC COUNT IS PER CARD TIER: {what} counts "
            f"{counts} settled in its bands where the recount made without "
            f"its door finds {table.get('recounted')!r}.")
    if table.get("n") != sum(c or 0 for c in counts):
        raise PooledCardCount(
            f"QUESTION 34: EVERY UFC COUNT IS PER CARD TIER: {what} says "
            f"{table.get('n')!r} settled beside bands of {counts}.")


def assert_each_band_is_its_cards(conn: sqlite3.Connection, sport: str,
                                  bands: list) -> None:
    """THE TIER CHIP'S BAND ON EVERY CARD AND RESULTS ROW IS ITS OWN CARD'S
    (the prover of operator question 34, 2026-10-08: the chip reads the tier
    table's door, and nothing held it). `bands` is (prediction id, band) for
    each chip a page draws -- the band as `bucket_record` or
    `bucket_on_no_card` gave it. Refused by name, inside `views.week` and
    `views.history`, so `/api/week` and `/api/history` answer 500, for a sport
    that splits by card: a band naming another card than its question's own
    bout is on (read here off the forecast, never off the band), counting
    rows on any other card (`tiers_counted`), or counting other than the
    recount made without the door finds in that card's band
    (`recount.settled_standing`) -- and a question on a card of no declared
    kind counting anything at all (in no card's count, the badge's rule); and
    in a sport that declares no cards, a band naming one."""
    from . import recount

    tiers = config.event_tiers(sport)
    law = "QUESTION 34: EVERY UFC COUNT IS PER CARD TIER (THE TIER CHIP)"
    if not tiers:
        for pid, band in bands:
            if band.get("event_tier") is not None or band.get("tiers_counted"):
                raise PooledCardCount(
                    f"{law}: the band on question {pid} names card "
                    f"{band.get('event_tier')!r} in {sport}, which declares "
                    f"no cards.")
        return
    ids = sorted({pid for pid, _ in bands})
    rows: dict = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        for r in conn.execute(
                "SELECT p.id, p.market_type, p.prop_type, p.predictor,"
                " (SELECT e.event_tier FROM ufc_bouts b JOIN ufc_events e"
                "    ON e.id = b.event_id WHERE b.id = p.game_id) AS event_tier"
                f"  FROM predictions p WHERE p.id IN ({','.join('?' for _ in chunk)})",
                chunk):
            rows[r["id"]] = r
    again: dict[tuple, list] = {}
    for pid, band in bands:
        row = rows.get(pid)
        card = row["event_tier"] if row is not None else None
        what = f"the band on question {pid} ({band.get('label')})"
        if band.get("event_tier", "absent") != card:
            raise PooledCardCount(
                f"{law}: {what} names card {band.get('event_tier', 'none')!r} "
                f"where its question's bout is on {card!r}: a UFC band is its "
                f"own card's.")
        if any(c != card for c in (band.get("tiers_counted") or [])):
            owner = (f"the {card!r} card's" if card is not None
                     else "on a card of no declared kind")
            raise PooledCardCount(
                f"{law}: {what} is {owner} and counts rows on "
                f"{band.get('tiers_counted')!r}: {sport}'s cards are counted "
                f"side by side, never summed.")
        if card is None or row is None:
            want = 0
        else:
            key = (row["market_type"], row["prop_type"], row["predictor"], card)
            if key not in again:
                again[key] = recount.settled_standing(
                    conn, sport=sport, predictor=row["predictor"],
                    market_type=row["market_type"], prop_type=row["prop_type"],
                    event_tier=card)
            lo, hi = next(((lo, hi) for lo, hi, name in BUCKETS
                           if name == band.get("label")), (None, None))
            want = (None if lo is None else
                    sum(1 for r in again[key] if lo <= r["model_prob"] < hi))
        if band.get("n") != want:
            raise PooledCardCount(
                f"{law}: {what} says {band.get('n')!r} settled where the "
                f"recount made without its door finds {want!r} on its own card "
                f"({card!r})"
                + ("; a question on a card of no declared kind is in no "
                   "card's count" if card is None else "") + ".")


# ---------------------------------------------------------------------------
# THE GREETING'S BAND LINE IS ONE CATEGORY'S (operator question 46, found
# 2026-10-08 by the prover of questions 33 and 34; built the same day)
# ---------------------------------------------------------------------------
#
# The line above every sport's slate said, for UFC, "50-60% bucket: 370
# settled · past the 100 needed, so calibration speaks here". It counted
# every settled forecast of the sport whose number fell in the band -- every
# pass, both forecasters, every market and every card -- where no UFC
# category's own 50-60% band held more than 36 and no NFL one more than 44;
# MLB's said 937 and NCAAF's 398. It has said so since 7ac5a73 (2026-08-29).
# SETTLED BY THE LAW AND A RULING, NOT A NEW ONE: LAW 4 ("nothing claims an
# edge below 100 resolved predictions in THAT CATEGORY"), NO MERGED CURVES
# (a curve is one market, one forecaster, one card for UFC), and question
# 14, ruled 2026-09-27 ("Every count on the Record page that states a gate
# distance is rebuilt per forecaster (per tier for UFC) and per distinct
# bet, through its record's standing rule"), applied to this line, which
# states a gate distance on another page.
#
# So each band count is ONE CATEGORY'S -- one market, the page's
# forecaster, one card for UFC -- its standing questions through the blind
# curve's own door (`resolved`, the standing clause, one per distinct bet):
# the number the Record page's curve draws for that band. Each carries the
# count `gridiron.recount` makes without the door, read in the same instant,
# and `assert_no_pooled_band_line` refuses, inside the builder
# (`views._record_movement`), a band whose count is not its category's or
# whose words do not name it, and the pooled shape itself, so
# `/api/digest` answers 500 by name. The page draws one band, the fullest
# (`fullest_band`), named; the payload carries every category's.


class PooledBandLine(MergedCurve):
    """A band count above a slate that is not its category's, or words that
    do not say whose (operator question 46, 2026-10-08)."""


BAND_LINE_LAW = (
    "QUESTION 46: THE GREETING'S BAND LINE IS ONE CATEGORY'S (LAW 4: "
    "\"nothing claims an edge below 100 resolved predictions in that "
    "category\"; question 14, ruled 2026-09-27, applied to the line: every "
    "count that states a gate distance is one forecaster's, one card's for "
    "UFC, one per distinct bet, through its record's standing rule)")


def band_lines(conn: sqlite3.Connection, *, sport: str,
               predictor: str) -> list[dict]:
    """Every confidence band of every curve of ONE sport and ONE forecaster
    -- one market, one card for a sport that splits by card -- each count
    the curve's own: its standing questions through `resolved` (the curve's
    door), as `curve` and `calibration_buckets` count them on the Record
    page. A band holding nothing is left out, unless the recount made
    without the door finds something in it (so the guard sees it).

    EACH ENTRY CARRIES what the guard reads: its market, card and
    forecaster; the cards and forecasters its rows were on (read off each
    row); the count `recount.settled_standing` makes without the door, in the
    same instant (`db.one_instant`); its distance to the hundred; and its
    words, naming the category (`language.bucket_countdown_line`)."""
    from . import db, recount

    require_sport(sport, "calibration.band_lines")
    if predictor not in ("statistical", "llm"):
        raise PooledCount(
            f"{BAND_LINE_LAW}: the band line in {sport} was asked for "
            f"forecaster {predictor!r}, not one of the two; a count for nobody "
            f"in particular is both together.")
    carded = bool(config.event_tiers(sport))
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    out: list[dict] = []
    with db.one_instant(conn):
        for market in config.SPORT_MARKETS.get(sport, ()):
            market_type = market_type_of(sport, market)
            prop_type = prop_type_of(sport, market)
            retired = config.retired_market(sport, market)
            for tier in (config.event_tiers(sport) or (None,)):
                rows = resolved(conn, sport=sport, market_type=market_type,
                                prop_type=prop_type, predictor=predictor,
                                event_tier=tier)
                again = recount.in_bands(recount.settled_standing(
                    conn, sport=sport, predictor=predictor,
                    market_type=market_type, prop_type=prop_type,
                    event_tier=tier), BUCKETS)
                label = language.category_label(market, tier, predictor, retired)
                for (lo, hi, band), recounted in zip(BUCKETS, again):
                    chosen = [r for r in rows if lo <= r.model_prob < hi]
                    n = len(chosen)
                    if not n and not recounted:
                        continue
                    out.append({
                        "market": market,
                        "market_type": market_type,
                        "prop_type": prop_type,
                        "event_tier": tier,
                        "predictor": predictor,
                        "category_label": label,
                        "band": band,
                        "n": n,
                        "gate": gate,
                        "needed": max(0, gate - n),
                        "past_the_gate": n >= gate,
                        "forecasters_counted": sorted({r.predictor for r in chosen}),
                        "tiers_counted": (_cards_of(chosen) if carded else []),
                        "recounted": recounted,
                        "words": language.bucket_countdown_line(label, band, n, gate),
                    })
    return out


def fullest_band(bands: list[dict]) -> dict | None:
    """THE BAND THE GREETING DRAWS: the fullest of any one curve -- the
    nearest any category of the page's forecaster is to the hundred, which
    is the question the line has always answered ("the honest distance to
    being able to say anything at all") asked of one category. A tie goes
    to the first in the declared order (market, card, band). None where no
    band holds anything."""
    shown = None
    for band in bands:
        if band.get("n") and (shown is None or band["n"] > shown["n"]):
            shown = band
    return shown


def assert_no_pooled_band_line(movement: dict) -> None:
    """THE GREETING'S BAND LINE IS ONE CATEGORY'S (operator question 46,
    2026-10-08). Refused by name, inside `views._record_movement`, so
    `/api/digest` answers 500: the pooled shape (a `buckets` list or a gate
    beside the sport's pooled counts, as it stood); a forecaster not one of
    the two; a band naming another market, card or forecaster than the
    sport declares and the page asked, or counting rows of another
    forecaster or card (read off each row); a band whose count is not the
    one `gridiron.recount` makes without the door -- a count wider than its
    category, every market, forecaster, pass or card together, is the pool
    LAW 4 forbids; a distance that is not its own arithmetic; words that do
    not name the category and band, state another count, or say
    "calibration speaks" of a band short of the hundred; one band twice; and
    a drawn line that is not the fullest band's words."""
    sport = movement.get("sport")
    require_sport(sport, "calibration.assert_no_pooled_band_line")
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    for key in ("buckets", "gate", "needed"):
        if key in movement:
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: the greeting for {sport} carries {key!r} "
                f"beside the sport's settled forecasts, every market, "
                f"forecaster, pass and card together -- a distance to the "
                f"{gate} stated of a pool. A band count is one category's.")
    if not movement.get("counted_words"):
        raise PooledBandLine(
            f"{BAND_LINE_LAW}: the greeting for {sport} states its pooled "
            f"settled count without saying what it pools.")
    forecaster = movement.get("forecaster")
    if forecaster not in ("statistical", "llm"):
        raise PooledBandLine(
            f"{BAND_LINE_LAW}: the greeting for {sport} names forecaster "
            f"{forecaster!r}, not one of the two.")
    markets = config.SPORT_MARKETS.get(sport, ())
    tiers = config.event_tiers(sport)
    labels = [name for _, _, name in BUCKETS]
    seen: set = set()
    bands = movement.get("bands")
    if not isinstance(bands, list):
        raise PooledBandLine(
            f"{BAND_LINE_LAW}: the greeting for {sport} carries no list of "
            f"its categories' bands.")
    for band in bands:
        market, tier = band.get("market"), band.get("event_tier")
        label = band.get("band")
        what = (f"the band line {label!r} of {band.get('category_label')!r} "
                f"in {sport}")
        if market not in markets:
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} names market {market!r}, not one "
                f"of {sport}'s declared markets {list(markets)}: a band over "
                f"every market describes none of them.")
        if tiers and tier not in tiers:
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} names card {tier!r}, not one of "
                f"{sport}'s cards {list(tiers)}: a band over every card "
                f"describes none of them.")
        if not tiers and tier is not None:
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} names card {tier!r} in {sport}, "
                f"which declares no cards.")
        if band.get("predictor") != forecaster:
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} is {band.get('predictor')!r}'s on a "
                f"page showing {forecaster!r}'s.")
        if any(f != forecaster for f in band.get("forecasters_counted") or []):
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} counts forecasts of "
                f"{band.get('forecasters_counted')!r}: both forecasters "
                f"together are a pool.")
        counted_cards = band.get("tiers_counted") or []
        if tiers and any(c != tier for c in counted_cards):
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} is the {tier!r} card's and counts "
                f"rows on {counted_cards!r}: {sport}'s cards are counted side "
                f"by side, never summed.")
        if not tiers and counted_cards:
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} counts rows on cards "
                f"{counted_cards!r} in {sport}, which declares no cards.")
        if label not in labels:
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} is not one of the bands {labels}.")
        if (market, tier, label) in seen:
            raise PooledBandLine(f"{BAND_LINE_LAW}: {what} is stated twice.")
        seen.add((market, tier, label))
        n = band.get("n")
        if not isinstance(n, int) or isinstance(n, bool) or n != band.get("recounted"):
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} counts {n!r} settled where its "
                f"category's own band, recounted without the door, holds "
                f"{band.get('recounted')!r}: a count wider than its category "
                f"-- every market, forecaster, pass or card together -- is the "
                f"pool LAW 4 forbids.")
        if band.get("gate") != gate or band.get("needed") != max(0, gate - n) \
                or band.get("past_the_gate") is not (n >= gate):
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} says {band.get('needed')!r} more to "
                f"the {band.get('gate')!r} on a count of {n}: the distance is "
                f"its own count's, to the {gate}.")
        category = band.get("category_label") or ""
        wanted = [language.MARKET_WORDS.get(market) or language.humanise(market),
                  language.FORECASTER_FILTER_WORDS.get(forecaster, forecaster)]
        if tier:
            wanted.append(language.tier_label(tier))
        if not category or any(w and w not in category for w in wanted):
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} is labelled {category!r}, which does "
                f"not name its market, forecaster{' and card' if tier else ''} "
                f"({wanted}).")
        words = band.get("words") or ""
        if not words.startswith(f"{category}, {label}: {n:,} "):
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} says {words!r}, which does not open "
                f"on its category, its band and its own count ({n:,}).")
        speaks = "calibration speaks here" in words
        if speaks is not (n >= gate) or (
                n < gate and f"{n:,} of {gate:,} · {gate - n:,} more " not in words):
            raise PooledBandLine(
                f"{BAND_LINE_LAW}: {what} says {words!r} on a count of {n}: "
                f"calibration speaks of a band past the {gate} and of no "
                f"other.")
    # THE LINE DRAWN IS THE FULLEST BAND'S, worked out here in the guard's
    # own spelling -- never by asking `fullest_band`, which a builder choosing
    # another band would have been changed to agree with: the most any one
    # band holds, and of the bands holding it the first in the declared
    # order (market, card, band).
    most = max((b["n"] for b in bands), default=0)
    shown = next((b for b in bands if most and b["n"] == most), None)
    line = movement.get("line")
    if (shown is None) is not (line is None) or (
            shown is not None and line != shown["words"]):
        raise PooledBandLine(
            f"{BAND_LINE_LAW}: the greeting for {sport} draws {line!r} where "
            f"the fullest band of any one category says "
            f"{(shown or {}).get('words')!r}.")


def recent_settled(conn: sqlite3.Connection, *, sport: str, since: str) -> tuple[int, int]:
    """(standing rows settled since `since`, distinct days that settled any).

    Standing rows, through the one clause: a superseded early row settles on
    the same day as its final and would count the question twice.
    """
    require_sport(sport, "calibration.recent_settled")
    row = conn.execute(
        "SELECT COUNT(*) AS n, COUNT(DISTINCT substr(p.resolved_utc, 1, 10)) AS days"
        " FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND p.resolved_utc IS NOT NULL"
        "   AND p.resolved_utc >= ?" + standing_row_clause(False),
        (sport, since)).fetchone()
    return int(row["n"] or 0), int(row["days"] or 0)


def _closest_verdict(conn: sqlite3.Connection, rows: list, *, sport: str) -> dict:
    """The tier nearest a verdict, and roughly how many slates that is.

    PACE IS AN ESTIMATE AND SAYS SO. It divides what settled in the last
    fourteen days by the number of days that actually carried a settlement,
    which is the closest thing to "a slate" this record holds. Below a week of
    history it refuses to estimate at all rather than dividing by two days and
    calling the answer a forecast.
    """
    from . import language

    waiting = [r for r in rows if not r["proven"]]
    if not waiting:
        return {"n": sum(r["n"] for r in rows), "tier": None,
                "line": language.closest_verdict_line(None, 0, ""),
                "pace_known": False}
    nearest = min(waiting, key=lambda r: r["needed"] - r["n"])
    remaining = nearest["needed"] - nearest["n"]

    cutoff = _days_ago_iso(language.PACE_WINDOW_DAYS)
    n_recent, days = recent_settled(conn, sport=sport, since=cutoff)
    per_slate = (n_recent / days) if days else None
    return {
        "n": nearest["n"],
        "tier": nearest["tier"],
        "remaining": remaining,
        "settled_recently": n_recent,
        "days_of_history": days,
        "pace_known": days >= language.PACE_MIN_DAYS and bool(per_slate),
        "line": language.closest_verdict_line(
            nearest["tier"], remaining,
            language.pace_clause(remaining, per_slate, days)),
        "note": (
            f"pace from the last {language.PACE_WINDOW_DAYS} days - an "
            f"estimate, not a promise - {sport.upper()} only, because sports "
            f"are never added together"),
    }


def _days_ago_iso(days: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _corrections_tip(conn: sqlite3.Connection, *, sport: str,
                     market_type: str, predictor: str) -> str | None:
    """The version of the correction the note speaks of, for its tooltip, or
    None when none is in force (operator question 19; the board merge,
    2026-09-29)."""
    from . import correction, language

    active = correction.active_correction(
        conn, sport=sport, market_type=market_type, forecaster=predictor)
    return language.correction_versions_tip([active["version"]] if active else [])


def _corrections_note(conn: sqlite3.Connection, *, sport: str,
                      market_type: str, predictor: str) -> str:
    from . import correction, language

    active = correction.active_correction(
        conn, sport=sport, market_type=market_type, forecaster=predictor)
    # SINCE WHEN, AND ON WHAT, from its own activation row (question 32,
    # 2026-09-29): the door returns the row beside the correction.
    return language.corrections_note(
        active is not None, correction.MIN_TRAIN,
        version=active["version"] if active else None,
        fitted=active["fitted_utc"] if active else None,
        settled=active["n_train"] if active else None,
        since=active["activated_utc"] if active else None,
        held_out=active["measured_holdout_n"] if active else None,
        questions=active["measured_bets"] if active else None,
    )


def _tier_headline(rows: list[dict]) -> str:
    """One sentence above the table: the LARGEST GAP, never the flattering row.

    A headline that picked the best-looking band would be the model marking its
    own homework. Where nothing is proven, it says that instead.
    """
    proven = [r for r in rows if r["proven"]]
    if not proven:
        best = max(rows, key=lambda r: r["n"]) if rows else None
        if best is None or not best["n"]:
            return "Nothing has resolved yet, so there is nothing to grade."
        return (
            f"No band has the {TIER_MIN_SETTLED} settled picks needed to grade "
            f"calibration — the fullest has {best['n']}."
        )

    worst = max(proven, key=lambda r: abs((r["actual"] or 0) - (r["claimed"] or 0)))
    actual = (worst["actual"] or 0) * 100
    return (
        f"{worst['tier']} picks in the {worst['band']} band have been right "
        f"{actual:.0f}% of the time over {worst['n']} — {worst['verdict']}."
    )


# ---------------------------------------------------------------------------
# THE AT-THE-LINE RECORD (E4, 2026-09-06)
# ---------------------------------------------------------------------------
#
# A SECOND RECORD, NOT A SECOND OPINION. Every row here is the frozen
# distribution read at a number the venue published after the prediction was
# written. It resolves like a prediction and calibrates like one, and it is
# kept apart from the blind rung record at every level:
#
#   * its own curves, one per market, never mixed with a rung curve;
#   * its own gate, the same 100 as every other edge figure, counted from its
#     own settled comparisons -- which are always fewer, because a claim needs
#     a ladder and a price as well as a forecast;
#   * its own guard. `assert_the_records_stay_apart` refuses a payload whose
#     categories do not all belong to the record they are filed under, and
#     `plant.py` puts an at-the-line curve in the blind record to prove it
#     fires. Merging the two would describe neither: one is what the model
#     said about its own question, the other what it says about the venue's.


class MergedRecord(RuntimeError):
    """The blind record and the at-the-line record were filed as one."""


class ComparedAcrossTwoContracts(MergedCurve):
    """A price comparison holds a claim priced across two contracts, or a
    recommendation priced from one (operator ruling A.2, 2026-10-05).

    A `MergedCurve`, so every route that answers a pooled count with a 500
    and its reason answers this one the same way: a figure setting a model
    number about one contract beside a price about another describes no
    contract, as a pooled curve describes no forecaster."""


#: WHY, in the refusal's words. "Before the fix of 30 September" (the prover,
#: 2026-10-05: "before 30 September" was false of the six claims written at
#: 18:00-18:05Z that day; `audit.two_contract_words_faults` holds it).
ACROSS_TWO_CONTRACTS_LAW = (
    "OPERATOR RULING A.2 (2026-10-05): a claim priced across two contracts "
    "-- an away contract read at -s before the fix of 30 September, its "
    "model number about one contract and its price about another -- stays in "
    "the blind record and is excluded by a dated rule from every price "
    "comparison: the at-the-line record, the closing line, edge figures and "
    "combos")


def refuse_a_comparison_across_two_contracts(conn: sqlite3.Connection,
                                             claim_ids, *, what: str) -> None:
    """THE GUARD INSIDE EACH BUILDER THAT SETS THE MODEL AGAINST A PRICE
    (operator ruling A.2, 2026-10-05): refuse, by name, a comparison whose
    claims include one priced across two contracts.

    It reads the stored claims the builder's rows name -- their own lines
    and contracts, through the one place (`at_the_line.
    across_two_contracts_among`) -- never the rows' own say-so, so a door
    that forgot the rule (`at_the_line.on_one_contract`) is seen here
    whatever it hands on. The at-the-line curve, its edge figure, the
    hypothetical ledger, the coverage line, the venue's drift pair and the
    card's count ask it; the closing line asks
    `refuse_recommendations_across_two_contracts`, and a proposed combo
    asks it of its legs' claims."""
    from .market import at_the_line

    found = at_the_line.across_two_contracts_among(conn, claim_ids)
    if found:
        shown = ", ".join(str(i) for i in found[:12])
        more = f" and {len(found) - 12} more" if len(found) > 12 else ""
        raise ComparedAcrossTwoContracts(
            f"{ACROSS_TWO_CONTRACTS_LAW}. {what} holds {len(found)} such "
            f"claim(s): {shown}{more}.")


def refuse_recommendations_across_two_contracts(conn: sqlite3.Connection,
                                                recommendation_ids, *,
                                                what: str) -> None:
    """The same guard for a comparison of recommendations -- the closing
    line and all it feeds: refuse, by name, one that counts a
    recommendation priced from a claim across two contracts, its pricing
    claim found by the close's own rule (`recommend.pricing_claim_ids`)."""
    from .market import at_the_line, recommend

    priced_from = recommend.pricing_claim_ids(conn, recommendation_ids)
    across = set(at_the_line.across_two_contracts_among(
        conn, priced_from.values()))
    found = sorted(rec for rec, claim in priced_from.items() if claim in across)
    if found:
        shown = ", ".join(str(i) for i in found[:12])
        more = f" and {len(found) - 12} more" if len(found) > 12 else ""
        raise ComparedAcrossTwoContracts(
            f"{ACROSS_TWO_CONTRACTS_LAW}. {what} counts {len(found)} "
            f"recommendation(s) priced from such a claim: {shown}{more}.")


AT_THE_LINE_NOTE = (
    "The model's own distribution, read at the venue's published line after the "
    "forecast was written and frozen. Two probabilities for the same question, "
    "and nothing else: this is a forecast beside a price, not a recommendation."
)


@dataclass(frozen=True)
class AtTheLineResolved:
    """One settled claim, in the shape the bucket and score functions read.

    It carries its BET -- its forecast's key, `bet.KEY`: the forecaster, the
    game, the market, the subject and the rung asked (operator question 17,
    2026-09-28; item 6 carried the game, market and side) -- so a payload
    can say how many distinct bets its count is (`bet.count`), and a guard
    can refuse one that counts a bet twice or two forecasters as one. The
    venue's own number is `line`; the rung the forecaster was asked is
    `line_asked`. (It carried the prop type too until 2026-09-29, when the
    key left it out: a prop's question is named by its subject, and nothing
    here read the type for anything else.)
    """
    model_prob: float
    implied_prob: float
    outcome: int
    market: str
    line: float | None
    game_id: str
    side: str
    predictor: str
    market_type: str
    subject: str
    line_asked: float | None


def _at_the_line_items_of(claims) -> list[AtTheLineResolved]:
    """The settled claims among the door's rows, as items."""
    from .market import at_the_line

    return [
        AtTheLineResolved(model_prob=c["model_prob"], implied_prob=c["venue_implied"],
                          outcome=c["outcome"], market=c["market"], line=c["line"],
                          game_id=c["game_id"], side=c["side"],
                          predictor=c["predictor"], market_type=c["market_type"],
                          subject=c["subject"], line_asked=c["line_asked"])
        for c in at_the_line.settled(claims)
    ]


def forecasters_counted(items) -> list[str]:
    """Whose claims a set of items holds, read off the items themselves."""
    return sorted({i.predictor for i in items})


def at_the_line_items(conn: sqlite3.Connection, *, sport: str, market: str,
                      predictor: str,
                      event_tier: str | None = None) -> list[AtTheLineResolved]:
    """The settled standing claims for one sport, market and forecaster --
    and, for a sport that splits below the market, one tier.

    ONE PER DISTINCT BET (the market module's door,
    `at_the_line.standing_claims`, keyed by `bet`): a question's morning and
    final pass and its every look are one claim, two rungs of one game are
    two, and the two forecasters are never counted together (item 6;
    operator question 17, 2026-09-28).

    AND NONE PRICED ACROSS TWO CONTRACTS (operator ruling A.2, 2026-10-05):
    the door leaves them out, and the guard asks the stored claims its rows
    name before any item is made of them -- the edge figure reads these.
    """
    from .market import at_the_line

    require_sport(sport, "calibration.at_the_line_items")
    claims = at_the_line.standing_claims(
        conn, sport=sport, market=market, predictor=predictor,
        event_tier=event_tier)
    refuse_a_comparison_across_two_contracts(
        conn, [c["id"] for c in claims],
        what=f"the at-the-line figures for {sport} {market}, {predictor}")
    return _at_the_line_items_of(claims)


def at_the_line_curve(conn: sqlite3.Connection, *, sport: str, market: str,
                      predictor: str, event_tier: str | None = None) -> dict:
    """One forecaster's at-the-line curve in one market, with the venue's own
    prices as the baseline it has to beat.

    ONE LIST, THREE COUNTS (GRIDIRON_REPAIR item 6, 2026-09-26). The door is
    asked once; the curve's n, the gate line and the outlook beside it are all
    read off that list. Until this date the outlook asked a query of its own,
    and MLB spread said "80 of 100" beside "128 of 100" -- two counts of one
    record, the ONE CLAUSE failure again (FOLLOWUPS, 2026-09-23).

    AND RECOUNTED WITHOUT THE DOOR (operator question 17, 2026-09-28): the
    same read asks `gridiron.recount` for the cell's settled bets by the one
    key, and the payload carries it as `recounted` for
    `assert_no_pooled_claims` to hold the curve's n to.
    """
    from . import db, recount
    from .market import at_the_line

    require_sport(sport, "calibration.at_the_line_curve")
    with db.one_instant(conn):
        bets = at_the_line.standing_claims(conn, sport=sport, market=market,
                                           predictor=predictor,
                                           event_tier=event_tier)
        # NO CLAIM PRICED ACROSS TWO CONTRACTS IN THE CURVE, ITS GATE LINE
        # OR ITS OUTLOOK (operator ruling A.2, 2026-10-05), asked of the
        # stored claims the door's rows name.
        refuse_a_comparison_across_two_contracts(
            conn, [c["id"] for c in bets],
            what=f"the at-the-line curve for {sport} {market}, {predictor}")
        again = recount.at_the_line(conn, sport=sport, market=market,
                                    predictor=predictor, event_tier=event_tier)
        outlook = horizon.at_the_line_outlook(
            conn, sport, market, predictor=predictor, bets=bets,
            event_tier=event_tier)
    items = _at_the_line_items_of(bets)
    buckets = calibration_buckets(items)
    filters = {"sport": sport, "market": market, "predictor": predictor,
               "record": "at_the_line"}
    if event_tier is not None:
        filters["event_tier"] = event_tier
    return {
        "sport": sport,
        "record": "at_the_line",
        "venue": at_the_line_venue(),
        "market": market,
        "predictor": predictor,
        "event_tier": event_tier,
        "category": " / ".join(
            [market] + ([event_tier] if event_tier else [])
            + [predictor, "at the venue's line"]),
        "category_label": language.at_the_line_category_label(
            market, predictor, event_tier),
        "filters": filters,
        "n": len(items),
        "distinct_bets": bet.count(items),
        "recounted": again["settled"],
        "forecasters_counted": forecasters_counted(items),
        "buckets": buckets,
        "largest_gap": largest_gap_sentence(buckets),
        "score": score(items),
        "baselines": baselines(items),
        "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
        "gate_line": language.at_the_line_gate_line(
            len(items), config.MIN_SAMPLE_FOR_EDGE_CLAIM),
        "outlook": outlook,
        "note": AT_THE_LINE_NOTE,
    }


def at_the_line_venue() -> str:
    """The venue these claims are read against, named on every figure."""
    from .market import at_the_line

    return at_the_line.VENUE


def at_the_line_edge(conn: sqlite3.Connection, *, sport: str, market: str,
                     predictor: str, event_tier: str | None = None,
                     threshold: float | None = None) -> dict:
    """Where the model and the venue's price disagree, who was right?

    Both directions, always. Showing only the half where the model led is how
    a record lies while staying technically accurate, and this figure is the
    most decision-relevant one the project can produce, so it carries the same
    gate and the same standing caveat as the blind edge figure.

    ONE FORECASTER'S (item 6, 2026-09-26), as the blind edge figure has
    always been: the scorecard asks for the statistical model's, and the
    payload says whose it is. Its settled claims are recounted without the
    door in the same read (`recounted`, operator question 17, 2026-09-28).
    """
    from . import db, recount

    threshold = config.EDGE_DISAGREEMENT_THRESHOLD if threshold is None else threshold
    with db.one_instant(conn):
        # NO CLAIM PRICED ACROSS TWO CONTRACTS IN AN EDGE FIGURE (operator
        # ruling A.2, 2026-10-05: "edge figures"): `at_the_line_items` asks
        # the guard of the claims it reads.
        items = at_the_line_items(conn, sport=sport, market=market,
                                  predictor=predictor, event_tier=event_tier)
        again = recount.at_the_line(conn, sport=sport, market=market,
                                    predictor=predictor, event_tier=event_tier)
    model_bolder = [r for r in items if r.model_prob - r.implied_prob > threshold]
    venue_bolder = [r for r in items if r.implied_prob - r.model_prob > threshold]

    def side(subset, label):
        n = len(subset)
        entry = {"label": label, "n": n}
        if n:
            entry["resolved_in_model_favour"] = round(
                sum(r.outcome for r in subset) / n, 4)
            entry["mean_model_prob"] = round(sum(r.model_prob for r in subset) / n, 4)
            entry["mean_venue_prob"] = round(sum(r.implied_prob for r in subset) / n, 4)
        else:
            entry["resolved_in_model_favour"] = None
            entry["mean_model_prob"] = None
            entry["mean_venue_prob"] = None
        return entry

    minimum = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    payload = {
        "sport": sport,
        "record": "at_the_line",
        "venue": at_the_line_venue(),
        "market": market,
        "predictor": predictor,
        "event_tier": event_tier,
        "threshold": threshold,
        "n": len(items),
        "distinct_bets": bet.count(items),
        "recounted": again["settled"],
        "forecasters_counted": forecasters_counted(items),
        "n_disagreements": len(model_bolder),
        "minimum_for_a_claim": minimum,
        "standing_note": EDGE_STANDING_NOTE,
        "note": AT_THE_LINE_NOTE,
    }
    if len(model_bolder) < minimum:
        payload["renderable"] = False
        payload["shortfall"] = minimum - len(model_bolder)
        payload["message"] = language.at_the_line_gate_line(len(model_bolder), minimum)
        return payload
    payload["renderable"] = True
    payload["model_more_confident"] = side(model_bolder, "model more confident")
    payload["venue_more_confident"] = side(venue_bolder, "the venue's price more confident")
    return payload


def at_the_line_scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """Every at-the-line curve for ONE sport, and the coverage behind them."""
    from .market import at_the_line

    require_sport(sport, "calibration.at_the_line_scorecard")
    markets = [m for m in at_the_line.BET_MARKETS
               if m in config.SPORT_MARKETS.get(sport, ())]
    # ONE CATEGORY PER MARKET, TIER AND FORECASTER (GRIDIRON_REPAIR item 6,
    # 2026-09-26): "The at-the-line scorecard never pools forecasters or
    # duplicates; per-forecaster, per-distinct-bet counts only, LAW 4 and
    # LAW 6." The tiers are `(None,)` for the four sports that do not split,
    # as in `scorecard`; the statistical model comes first in each market.
    tiers = config.event_tiers(sport) or (None,)
    cells = [(m, t, p) for m in markets for t in tiers
             for p in at_the_line.FORECASTERS]
    categories = [at_the_line_curve(conn, sport=sport, market=m, predictor=p,
                                    event_tier=t) for m, t, p in cells]
    # THE HYPOTHETICAL LEDGER, one per category (ruling D1, 2026-09-06; one
    # per forecaster from item 6). Beside the curves and never inside them: a
    # curve says whether 58% means 58%, and this says what the same rows
    # would have come to at the venue's prices, which is a fact about those
    # prices as much as about the forecast.
    from .market import paper

    ledgers = []
    for m, t, p in cells:
        entry = paper.ledger(conn, sport=sport, market=m, predictor=p,
                             event_tier=t)
        entry["words"] = language.paper_ledger_line(entry)
        entry["fee_words"] = language.paper_fee_line(entry)
        ledgers.append(entry)

    coverage = [row for t in tiers for p in at_the_line.FORECASTERS
                for row in at_the_line.coverage(conn, sport=sport, predictor=p,
                                                event_tier=t)]
    order = {m: i for i, m in enumerate(markets)}
    coverage.sort(key=lambda row: (order.get(row["market"], 99),
                                   tiers.index(row["event_tier"]),
                                   at_the_line.FORECASTERS.index(row["predictor"])))
    for row in coverage:
        # AND HOW MANY MORE WERE READ ONLY ACROSS TWO CONTRACTS, left out of
        # every comparison with a price (operator ruling A.2, 2026-10-05).
        row["words"] = language.at_the_line_coverage_line(
            row["market"], row["with_a_claim"], row["n"],
            predictor=row["predictor"], event_tier=row["event_tier"],
            across=row.get("across_two_contracts") or 0)
    headline_market = markets[0] if markets else None
    payload = {
        "sport": sport,
        "record": "at_the_line",
        "venue": at_the_line_venue(),
        "categories": categories,
        "markets": markets,
        "coverage": coverage,
        "paper": ledgers,
        # NO TOTAL. The `n` that stood here summed every category -- both
        # forecasters -- and described nobody's record (item 6, 2026-09-26).
        "note": AT_THE_LINE_NOTE,
        # THE STATISTICAL MODEL'S EDGE in the headline market, as the blind
        # record's edge figure is (`scorecard`); for a sport that splits, the
        # first declared tier's, which is the numbered card.
        "edge": (at_the_line_edge(conn, sport=sport, market=headline_market,
                                  predictor="statistical", event_tier=tiers[0])
                 if headline_market else None),
    }
    assert_the_records_stay_apart(payload)
    assert_no_pooled_claims(payload)
    assert_every_figure_has_n(payload)
    assert_single_sport(payload, sport)
    return payload


def assert_no_pooled_claims(payload: dict) -> None:
    """Every count at the venue's line is ONE forecaster's DISTINCT BETS.

    The operator's ruling of 2026-09-23 (GRIDIRON_REPAIR item 6): "The
    at-the-line scorecard never pools forecasters or duplicates;
    per-forecaster, per-distinct-bet counts only, LAW 4 and LAW 6." Checked on
    the payload, as `assert_no_merged_categories` checks the blind record's
    -- and it runs that check first, so the forecaster, the sport, the market
    and the tier are one rule for both records.

    Then, by name: a curve, a ledger or the edge that counts more claims than
    it has distinct bets (a question's morning and final pass, two looks, or
    two forecasters' claims on one question); one whose claims are another
    forecaster's than the one it names; a gate line or an outlook that
    states another count than the curve's own (the live record said "80 of
    100" beside "128 of 100" for one MLB category, 2026-09-23); a coverage
    line that names no forecaster, or counts one bet more than once (the
    prover, 2026-09-26); and a total across categories.

    AND A COUNT THE RECOUNT DOES NOT MAKE (operator question 17, ruled
    2026-09-27, built 2026-09-28). A distinct bet is `bet.of`, and a door
    keyed any other way -- without the rung, so two rungs of one game are
    one claim, or across forecasters, so one's later claim stands in for the
    other's question -- counts other bets than the record holds while its
    own `distinct_bets` agrees with it. Each curve, ledger, edge and coverage
    line carries `gridiron.recount`'s count, made without the door in the
    same read, and one that differs is refused by name.
    Raised inside `at_the_line_scorecard`, so the API answers 500 rather
    than serving a pool, the same as LAW 4 everywhere else.
    """
    from .market import at_the_line

    assert_no_merged_categories(payload)
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    law = "LAW 4 / LAW 6 AT THE VENUE'S LINE"

    def whose(entry: dict, what: str) -> None:
        named = entry.get("predictor")
        filtered = (entry.get("filters") or {}).get("predictor", named)
        if named not in at_the_line.FORECASTERS or filtered != named:
            raise MergedCurve(
                f"{law}: {what} names forecaster {named!r} (filtered by "
                f"{filtered!r}). The statistical model and the reasoning pass "
                f"are counted apart and never pooled.")
        counted = entry.get("forecasters_counted")
        if counted is not None and counted not in ([], [named]):
            raise MergedCurve(
                f"{law}: {what} is the {named!r} forecaster's and counts the "
                f"claims of {counted}: two forecasters pooled into one count.")
        if tiers and entry.get("event_tier") not in tiers:
            raise MergedCurve(
                f"{law}: {what} names event tier {entry.get('event_tier')!r}, "
                f"not one of {sport}'s {list(tiers)}; tiers are reported side "
                f"by side, never summed.")

    def once(entry: dict, what: str) -> None:
        n, bets = entry.get("n"), entry.get("distinct_bets")
        if bets is None or n != bets:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled claims for {bets} distinct "
                f"bet{'' if bets == 1 else 's'}. A distinct bet is counted once, "
                f"however many passes or looks repeated it.")

    def recounted(entry: dict, what: str) -> None:
        n, again = entry.get("n"), entry.get("recounted")
        if again != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} where the recount made without its "
                f"door finds {again!r}, one per distinct bet by the one "
                f"key (`bet.of`: the forecaster, the game, the market, the "
                f"subject and the rung asked). A door keyed any other way -- "
                f"without the rung, or across forecasters -- counts other bets "
                f"than the record holds (operator question 17, 2026-09-28).")

    if "n" in payload:
        raise MergedCurve(
            f"{law}: the at-the-line payload carries a total n of "
            f"{payload['n']}, a sum across its categories and so across both "
            f"forecasters, which is nobody's record.")
    for category in payload.get("categories") or []:
        what = f"category {category.get('category')!r}"
        whose(category, what)
        once(category, what)
        n = category.get("n")
        outlook = category.get("outlook") or {}
        if outlook.get("resolved") != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled beside an outlook of "
                f"{outlook.get('resolved')!r}: two counts of one record.")
        # ITS SLATES ARE THE ONE RULE'S, ONE CARD'S FOR UFC (operator
        # questions 33 and 34, 2026-10-08): the slates it multiplies its
        # pace by are those still to come, as the recount made without the
        # rule finds them.
        refuse_slates_not_still_to_come(outlook, f"the outlook beside {what}")
        said = language.at_the_line_gate_line(n, category.get("gate"))
        if category.get("gate_line") != said:
            raise MergedCurve(
                f"{law}: {what}'s gate line says {category.get('gate_line')!r}, "
                f"which is not its own count of {n}.")
        recounted(category, what)
    for entry in payload.get("paper") or []:
        what = (f"the hypothetical ledger for {entry.get('market')!r}, "
                f"{entry.get('predictor')!r}")
        whose(entry, what)
        once(entry, what)
        recounted(entry, what)
    edge = payload.get("edge")
    if edge:
        whose(edge, "the at-the-line edge figure")
        once(edge, "the at-the-line edge figure")
        recounted(edge, "the at-the-line edge figure")
    for row in payload.get("coverage") or []:
        what = (f"the coverage line for {row.get('market')!r}, "
                f"{row.get('predictor')!r}")
        whose(row, what)
        # AND ONCE PER BET (the prover of item 6, 2026-09-26): the coverage
        # line counted a question's passes as more forecasts than it had
        # bets, and read one bet twice. From operator question 17
        # (2026-09-28) a bet is `bet.of`, so two rungs of one game are two
        # questions here as on the curve beside it.
        n, bets, read = row.get("n"), row.get("distinct_bets"), row.get("with_a_claim")
        if (bets is None or n != bets or not isinstance(read, int)
                or not 0 <= read <= n):
            raise MergedCurve(
                f"{law}: {what} counts {n} questions, "
                f"{read!r} of them read, for {bets} distinct "
                f"bet{'' if bets == 1 else 's'}. A question is one bet however "
                f"many passes answered it.")
        if row.get("recounted") != n or row.get("read_recounted") != read:
            raise MergedCurve(
                f"{law}: {what} counts {n} questions, {read} of them read, "
                f"where the recount made without either door finds "
                f"{row.get('recounted')!r} and {row.get('read_recounted')!r}, "
                f"one per distinct bet by the one key (`bet.of`). A rule keyed "
                f"any other way counts other bets than the record holds "
                f"(operator question 17, 2026-09-28).")
        # AND THE QUESTIONS IT LEFT UNREAD BECAUSE THEIR ONLY CLAIMS WERE
        # PRICED ACROSS TWO CONTRACTS (operator ruling A.2, 2026-10-05): a
        # count the page says in words, held to the recount's.
        across = row.get("across_two_contracts")
        if (not isinstance(across, int) or not 0 <= across <= n - read
                or across != row.get("across_recounted")):
            raise ComparedAcrossTwoContracts(
                f"{ACROSS_TWO_CONTRACTS_LAW}. {what} says {across!r} of its "
                f"questions were read only across two contracts, where the "
                f"recount made without the door finds "
                f"{row.get('across_recounted')!r} of the {n - read} it did "
                f"not read.")


def assert_the_records_stay_apart(payload: dict) -> None:
    """Every category belongs to the record it is filed under.

    The blind record answers the question the model chose; the at-the-line
    record answers the venue's. A payload holding both would average a
    forecast against its own rung with a forecast against a price, and the
    result would describe neither -- the same failure LAW 6 names one level up.
    """
    record = payload.get("record")
    if record not in ("rung", "at_the_line"):
        raise MergedRecord(
            f"a scorecard must say which record it is: {record!r} is neither "
            f"'rung' nor 'at_the_line'.")
    for category in payload.get("categories") or []:
        theirs = category.get("record")
        if theirs != record:
            raise MergedRecord(
                f"category {category.get('category')!r} belongs to the "
                f"{theirs!r} record and is filed under the {record!r} one. The "
                f"blind record and the at-the-line record are never merged: "
                f"one is what the model said about its own question, the other "
                f"what it says about the venue's.")


# ---------------------------------------------------------------------------
# SCORING THE RANKER ITSELF (THE_SHORTLIST S3, 2026-09-07)
# ---------------------------------------------------------------------------
#
# The reason the rank is written to the database rather than computed when the
# page loads. A shortlist is a claim of a kind -- that these twenty questions
# are the better ones -- and this project does not ship claims it cannot check.
#
# TWO CURVES, NEVER ONE. The questions that led their slate, and the questions
# they outranked, scored separately with their own N and the same hundred-
# resolution gate as every other figure here. Below the gate there is no
# verdict at all, only the count and what is missing.
#
# BACKFILLED RANKS ARE EXCLUDED, and the exclusion matters more than it looks.
# A rank computed after the games were played, by a formula written today, is
# not the same object as one computed before kickoff: it cannot have been
# influenced by the outcome, but it was written by somebody who already knew
# it. Mixing the two would flatter the ranker with rows it never really
# ordered.


def ranker_comparison(conn: sqlite3.Connection, *, sport: str,
                      market_type: str, prop_type: str | None = None,
                      predictor: str = "statistical",
                      event_tier: str | None = None) -> dict:
    """Did the shortlist calibrate better than what it outranked?

    ONE CARD'S FOR UFC (operator question 34, ruled 2026-09-30; built
    2026-10-08): the card is required for a sport that splits by card, the
    comparison names it ("moneyline, Fight Night") and carries the cards its
    rows were on and both sides as `gridiron.recount` counts them without
    the door; `assert_no_pooled_ranker` refuses another card's count inside
    this builder. Until this date UFC's "49 settled on the shortlist and 0
    off it" counted the three cards as one (39/0, 10/0, 0/0 on 29 September).
    """
    from . import db, recount
    from . import shortlist as ranker

    require_sport(sport, "calibration.ranker_comparison")
    refuse_a_count_across_cards(sport, event_tier, "the ranker's record")
    with db.one_instant(conn):
        items = resolved(conn, sport=sport, market_type=market_type,
                         prop_type=prop_type, predictor=predictor,
                         event_tier=event_tier)
        ranks = ranker.ranks_for(conn, [r.id for r in items])
        again = recount.ranked(conn, recount.settled_standing(
            conn, sport=sport, predictor=predictor, market_type=market_type,
            prop_type=prop_type, event_tier=event_tier), config.RANKER_VERSION)
    led, rest = [], []
    for row in items:
        rank = ranks.get(row.id)
        if rank is None or rank["backfilled"]:
            continue
        (led if rank["on_shortlist"] else rest).append(row)

    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    led_score, rest_score = score(led), score(rest)
    payload = {
        "sport": sport,
        "record": "ranker",
        "market": prop_type or market_type,
        "ranker_version": config.RANKER_VERSION,
        "n": len(led) + len(rest),
        "gate": gate,
        "shortlisted": {
            "label": "led the slate", "n": len(led), "score": led_score,
            "buckets": calibration_buckets(led),
        },
        "not_shortlisted": {
            "label": "outranked", "n": len(rest), "score": rest_score,
            "buckets": calibration_buckets(rest),
        },
        "gate_line": language.ranker_gate_line(len(led), len(rest), gate),
        "excludes_backfilled": True,
    }
    payload["renderable"] = len(led) >= gate and len(rest) >= gate
    if payload["renderable"]:
        payload["verdict"] = language.ranker_verdict_line(
            led_score["brier"], rest_score["brier"], len(led), len(rest))
    else:
        payload["verdict"] = None
        payload["shortfall"] = max(gate - len(led), 0) + max(gate - len(rest), 0)
    payload["recounted"] = {"shortlisted": again[0], "not_shortlisted": again[1]}
    if config.event_tiers(sport):
        # ONE CARD'S, NAMED (operator question 34, 2026-10-08) -- keys only a
        # carded sport's comparison carries, so no other sport's changes.
        payload["event_tier"] = event_tier
        payload["category_label"] = language.card_market_label(
            sport, prop_type or market_type, event_tier)
        payload["tiers_counted"] = _cards_of(led + rest)
    assert_no_pooled_ranker(payload)
    return payload


def assert_no_pooled_ranker(payload: dict) -> None:
    """THE RANKER'S RECORD IS ONE CARD'S FOR UFC (operator question 34,
    ruled 2026-09-30; built 2026-10-08). Refused by name, inside
    `ranker_comparison`, so `/api/scorecard` answers 500: a comparison
    naming no card, or one of none, in a sport that splits by card; one
    counting rows on another card than it names, or on every card
    (`tiers_counted`, read off each row's own bout); either side's count
    other than the one `gridiron.recount` makes without the door
    (`recounted`); and a total that is not the two sides'."""
    sport = payload.get("sport")
    what = f"the ranker's record for {sport} {payload.get('market')}"
    refuse_another_cards_count(sport, payload.get("event_tier"),
                               payload.get("tiers_counted", []), what)
    led = (payload.get("shortlisted") or {}).get("n")
    rest = (payload.get("not_shortlisted") or {}).get("n")
    again = payload.get("recounted") or {}
    if (again.get("shortlisted"), again.get("not_shortlisted")) != (led, rest):
        raise PooledCardCount(
            f"QUESTION 34: EVERY UFC COUNT IS PER CARD TIER: {what} counts "
            f"{led!r} that led the slate and {rest!r} outranked where the "
            f"recount made without its door finds "
            f"{again.get('shortlisted')!r} and {again.get('not_shortlisted')!r}.")
    if payload.get("n") != (led or 0) + (rest or 0):
        raise PooledCardCount(
            f"QUESTION 34: EVERY UFC COUNT IS PER CARD TIER: {what} says "
            f"{payload.get('n')!r} beside {led!r} and {rest!r}.")


def ranker_scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """One comparison per market of one sport, kept apart like every curve
    -- and per card for a sport that splits by card (operator question 34,
    2026-10-08): "moneyline, Numbered card", "moneyline, Fight Night", ..."""
    require_sport(sport, "calibration.ranker_scorecard")
    markets = config.SPORT_MARKETS.get(sport, ())
    comparisons = [
        ranker_comparison(conn, sport=sport,
                          market_type=market_type_of(sport, market),
                          prop_type=prop_type_of(sport, market),
                          event_tier=tier)
        for market in markets
        for tier in (config.event_tiers(sport) or (None,))
    ]
    return {
        "sport": sport,
        "record": "ranker",
        "ranker_version": config.RANKER_VERSION,
        # THE NAME'S ONE PLACE ON THE PAGE (operator question 19; the board
        # merge, 2026-09-29): the heading's tooltip, with what it names.
        "version_tip": language.version_tip("ranker", config.RANKER_VERSION),
        # HOW MANY COMPARISONS, NEVER A SUM OF THEIR COUNTS (operator
        # question 34, 2026-10-08): the sum over markets -- and with UFC's
        # cards apart, over cards -- was nobody's record and nothing read
        # it (the learning panel's `n`, question 16, is the precedent).
        "n": len(comparisons),
        "comparisons": comparisons,
        # "AND CARD" WHERE THE SPORT SPLITS BY CARD (operator question 34,
        # 2026-10-08): the render read "separately per market" above nine
        # rows, three cards to each market.
        "note": (
            "The shortlist is an ordering, and an ordering can be wrong. These "
            "compare what led each slate against what it outranked, separately "
            f"per market{' and card' if config.event_tiers(sport) else ''}, "
            "with the same gate as every other figure. Ranks "
            "computed after the fact are left out: a formula written today "
            "cannot be scored on games it already knows the answer to."
        ),
    }


# ---------------------------------------------------------------------------
# CLOSING-LINE VALUE (THE_RECOMMENDATION R3, 2026-09-07)
# ---------------------------------------------------------------------------
#
# THE VERDICT THAT ARRIVES FIRST. Every other figure on this page waits for
# games to finish and for a hundred of them to accumulate. This one compares
# the price the app recommended against the market's own final estimate of the
# same question, which is a far less noisy comparison than one outcome -- it
# says something at around fifty observations rather than several hundred.
#
# IT IS STILL A CLAIM, so it renders with its N and claims nothing below the
# declared minimum. And it is capable of returning bad news: a negative mean
# means the app is buying prices the market is about to move away from, and the
# sentence for that case is written in `language.clv_finding_line` rather than
# improvised on the day.

#: HOW MANY RECOMMENDATIONS BEFORE THE CLOSING LINE SAYS ANYTHING. Fifty,
#: declared 2026-09-07 and deliberately not the hundred of MIN_SAMPLE_FOR_EDGE_CLAIM:
#: this compares two prices for the same question rather than a forecast
#: against an outcome, so most of the variance an edge estimate fights through
#: is not in it. The number is a judgement and is dated as one.
MIN_RECOMMENDATIONS_FOR_CLV = 50
#: WHERE THE FIRST WINDOW STARTED, kept in the payload beside the second
#: (2026-09-27). The count started again on `config.CLOSING_LINE_WINDOW_START`
#: by the operator's ruling 8 of 2026-09-23, because nothing counted from this
#: date had been measured: every close before the repair was the price paid.
CLV_DECLARED = "2026-09-07T00:00:00Z"

#: AND A HUNDRED FOR A PACKAGE (GRIDIRON_COMBOS C4, 2026-09-08). A package's
#: close is the product of two or three moving quotes, so the same confidence
#: costs more observations than a single's does -- twice as many, which is the
#: coarsest defensible answer and is declared as a judgement, not fitted.
#: `MIN_PACKAGES_FOR_CLV = 100` stood here from 2026-09-08 until C4 was
#: WITHDRAWN on 2026-09-09. A package needed twice a single's observations
#: before its closing-line number meant anything -- a sound threshold for a
#: product with a closing line. A combo has none: the app never sees the price
#: the operator was quoted, so there is nothing to close against.
COMBO_CLV_WITHDRAWN = "2026-09-09"


def clv_minimum(market: str) -> int:
    """How many closes this market needs before its number means anything.

    ONE ANSWER NOW. The combo branch went with C4: no combo settles, so no
    combo market ever reaches this function.
    """
    return MIN_RECOMMENDATIONS_FOR_CLV


def closing_line_window(now: str | None = None) -> dict:
    """When the closing line counts from, and whether it may be read yet.

    THE ONE DOOR FOR THE OPERATOR'S RULING 8 OF 2026-09-23 (GRIDIRON_REPAIR
    item 8, built 2026-09-27): "the observation window restarts on the date
    item 1 ships; the first clean CLV read is 21 days after that, not before."
    The dates are `config.CLOSING_LINE_WINDOW_START` and
    `config.CLOSING_LINE_FIRST_CLEAN_READ`; whether today is on or after the
    second is asked here and nowhere else, counted in days by the same
    `language.date_gate` every dated window on the Record page uses.

    `now` is an instant (the record's format); only its UTC date is read. It
    defaults to the clock, and a test or a planting passes it so that what it
    proves does not change on 15 October.
    """
    from .db import utcnow

    today = (now or utcnow())[:10]
    days = language.date_gate(config.CLOSING_LINE_WINDOW_START,
                              config.CLOSING_LINE_FIRST_CLEAN_READ, today=today)
    return {
        "from": config.CLOSING_LINE_WINDOW_START,
        "from_utc": config.CLOSING_LINE_WINDOW_START + "T00:00:00Z",
        "first_clean_read": config.CLOSING_LINE_FIRST_CLEAN_READ,
        "open": bool(days["cleared"]),
        "days": days,
    }


def clv_report(conn: sqlite3.Connection, *, sport: str,
               now: str | None = None) -> dict:
    """What the closing line says about this sport's recommendations, one
    line per market and forecaster.

    COUNTED FROM `recommendation_closes`, NOT FROM THE COLUMNS (2026-09-23).
    Until then every close was the recommendation's own price and this read
    49 rows at 0.00c as a measurement. Now:

      * MEASURED -- a close by the one rule, at the time: counted, in N.
      * UNMEASURED -- closed with no later read of its own contract, or closed
        by the old closer and not yet restated: counted BESIDE, never at zero.
      * RESTATED -- an old close recomputed after the fact from quotes the
        record held before the start: counted beside too. It was computed by
        somebody who knew how the games went, so it is shown and never counted.
      * UNACCOUNTED -- an old close not yet restated. Its recorded value is
        its own price; counted beside, with its own words, until it is.
      * WITHDRAWN (ruling 1, 2026-09-24) -- a recommendation voided, or made
        on a voided forecast. Not in N, not in any bucket above, not awaiting
        a close: named once beside the closing line, in that word, and never
        counted anywhere. Every read below goes through
        `recommend.not_withdrawn`, the one door (from 2026-09-27 inside
        `recommend.counted_once`, which is that door and question 12's rule).
      * WOULD NOT HAVE CLEARED (GRIDIRON_REPAIR item 4, 2026-09-26) -- a
        recommendation the bar let through by dividing a no-side edge by the
        yes price, re-graded after the fact. A LABEL, NOT A WITHDRAWAL: it
        stays in whichever count above it was in -- the ruling says re-grade,
        where it says void when it means out of the counts -- and it is
        named once beside the closing line, with its N and its return on
        what its side cost.
      * BEFORE THE WINDOW (the operator's ruling 8 of 2026-09-23, built
        2026-09-27) -- a measured close on a recommendation written before
        `config.CLOSING_LINE_WINDOW_START`, the day the closing line was
        repaired. Counted beside, never in N: the count started again that
        day. (None exists on the record: every close before the repair was
        the old closer's, and is restated or unaccounted above.)
      * A PAIR, COUNTED ONCE (operator question 12, ruled 2026-09-27; on
        question 17's key by question 22, 2026-09-28) -- every read above
        goes through `recommend.counted_once`: of one forecaster's standing
        rows on one distinct bet and side only the first is in any figure
        above, and each later one is a REPEAT, named beside its market
        ("counted once, as the earlier one"). The rows stay as written; the
        tallies of what was set aside (`set_aside`) are in the payload so
        the withdrawn recount can still add up every standing row.
      * PRICED ACROSS TWO CONTRACTS (operator ruling A.2, 2026-10-05: the
        claims "are excluded by a dated rule from every price comparison:
        at-the-line record, closing line, edge figures, combos") -- a
        recommendation priced from a claim whose model number is about one
        contract and whose price is about another. Through
        `recommend.counted_once` it is in no figure above and never one of a
        pair; it is named once beside the closing line in its own line
        (`across_line`), tallied (`across_two_contracts`) as the repeats
        are. The 54 the ruling voids are then withdrawn, and named as
        withdrawn; nothing counted moves when they are.

    ONE LINE PER MARKET AND FORECASTER, AND NO TOTAL (operator question 22,
    ruled 2026-09-28: "(A). Recommendation counts split per forecaster, like
    every other count. This reverses Q12 for 45/46: each counts once in its
    own forecaster's line, and the 'Both sides, no position' row goes").
    Until this date each market's line held both forecasters'
    recommendations, the window line, the withdrawn and re-grade lines and
    every count beside them were one sum, and recs 45 and 46 -- the
    statistical model's over and the reasoning pass's under of one total --
    were in no figure, under a row of their own. Now `forecasters` holds one
    block per forecaster -- its window line, its N and every count beside
    it, its awaiting count, its withdrawn and re-grade lines, its set-aside
    tallies -- and `markets` one entry per market and forecaster, each
    named in words (`language.closing_line_label`: "total, reasoning
    pass"); 45 and 46 each count once in their own forecaster's total. The
    payload carries no pooled figure: `audit.pair_counted_faults` refuses
    one by name. A recommendation is its forecast's forecaster's, read
    through the forecast it was made from; every count is one forecaster's
    through the door itself (`counted_once` takes the forecaster).

    AND NO FIGURE BEFORE THE FIRST CLEAN READ (the same ruling 8: "the first
    clean CLV read is 21 days after that, not before"). Until
    `config.CLOSING_LINE_FIRST_CLEAN_READ`, asked through
    `closing_line_window`, no entry is renderable, its mean and the share
    that beat the close are None rather than figures nobody may read, no
    finding is written, and the words say the date. The count, with its N, is
    shown throughout: how many there are is not a verdict on them.
    """
    from .market import recommend

    require_sport(sport, "calibration.clv_report")
    window = closing_line_window(now)
    blocks, entries = [], []
    for predictor in recommend.FORECASTERS:
        block, markets = _closing_line_of(conn, sport=sport,
                                          predictor=predictor, window=window)
        blocks.append(block)
        entries.extend(markets)
    # MARKET BY MARKET, each forecaster's line under it, in the order the
    # page names the forecasters everywhere else.
    order = {who: i for i, who in enumerate(recommend.FORECASTERS)}
    entries.sort(key=lambda e: (e["market"], order[e["predictor"]]))
    return {
        "sport": sport,
        "record": "closing_line",
        "declared": CLV_DECLARED,
        # THE SECOND WINDOW (ruling 8, 2026-09-27): from when the count runs,
        # the first clean read, whether it has come, and the days between.
        "window": {"from": window["from"],
                   "first_clean_read": window["first_clean_read"],
                   "open": window["open"], "days": window["days"]},
        "forecasters": blocks,
        "markets": entries,
        "note": (
            "The price the app recommended against the market's own final "
            "estimate of the same question. It needs about fifty observations "
            "to say anything, where a win rate needs several hundred, which is "
            "why it is the first verdict this project can reach. A positive "
            "number means it is buying cheaper than the close."
        ),
    }


def _closing_line_of(conn: sqlite3.Connection, *, sport: str, predictor: str,
                     window: dict) -> tuple[dict, list[dict]]:
    """ONE FORECASTER'S closing line in one sport: its block (the window
    line, the counts beside the market lines, the withdrawn and re-grade
    lines) and its market entries. Every read names the forecaster in the
    door (`recommend.counted_once`, `not_counted_once`, `withdrawn`,
    `regraded`), so nothing here can count the other forecaster's rows."""
    from .market import recommend

    whose = language.FORECASTER_FILTER_WORDS.get(predictor, predictor)
    # COUNTED ONCE (operator questions 12 and 22): a same-side pair of one
    # distinct bet is its earlier row here, and only this forecaster's rows
    # are read at all.
    # AND NONE PRICED FROM A CLAIM ACROSS TWO CONTRACTS (operator ruling
    # A.2, 2026-10-05: the claims are excluded from "the closing line"), the
    # door's own rule (`recommend.priced_on_one_contract`), with the guard
    # asked of the rows it hands back below.
    rows = conn.execute(
        "SELECT r.id, r.market, r.side, r.price, c.clv_cents, c.restated,"
        "       r.closed_utc,"
        "       c.recommendation_id IS NOT NULL AS accounted,"
        "       r.created_utc >= ? AS in_window"
        "  FROM recommendations r"
        "  LEFT JOIN recommendation_closes c ON c.recommendation_id = r.id"
        " WHERE r.sport = ? AND r.closed_utc IS NOT NULL"
        + recommend.counted_once(conn, predictor=predictor),
        (window["from_utc"], sport)).fetchall()
    by_market: dict[str, list] = {}
    for row in rows:
        by_market.setdefault(row["market"], []).append(row)
    # WHAT THE DOOR LEFT OUT, NAMED RATHER THAN VANISHED: the repeats beside
    # their market's count.
    aside = recommend.not_counted_once(conn, sport=sport, predictor=predictor)
    repeats: dict[str, int] = {}
    for row in aside:
        repeats[row["market"]] = repeats.get(row["market"], 0) + 1

    entries = []
    for market in sorted(set(by_market) | set(repeats)):
        closed = by_market.get(market, [])
        measured = [r for r in closed if r["accounted"] and not r["restated"]
                    and r["clv_cents"] is not None]
        # THE COUNT STARTED AGAIN ON THE DAY OF THE REPAIR (ruling 8): a
        # measured close on a recommendation written before it is named
        # beside, never counted.
        got = [r for r in measured if r["in_window"]]
        before_window = len(measured) - len(got)
        restated = sum(1 for r in closed if r["accounted"] and r["restated"]
                       and r["clv_cents"] is not None)
        # CLOSED BY THE OLD CLOSER AND NOT YET RESTATED: its recorded close is
        # its own price, and nothing is known either way until it is.
        unaccounted = sum(1 for r in closed if not r["accounted"])
        unmeasured = len(closed) - len(measured) - restated - unaccounted
        n = len(got)
        # NO FIGURE BEFORE THE FIRST CLEAN READ (ruling 8). Not computed,
        # rather than computed and held back, so nothing downstream -- the
        # kill criterion, a payload read by hand -- can read one early.
        figures = bool(n) and window["open"]
        mean = round(sum(r["clv_cents"] for r in got) / n, 2) if figures else None
        beat = (round(sum(1 for r in got if r["clv_cents"] > 0) / n, 4)
                if figures else None)
        # ITS OWN N AND ITS OWN GATE. `combo_2` and `combo_3` are markets
        # here exactly like `moneyline` is, which is what keeps a package out
        # of a leg's count: this loop groups by the market a row was written
        # under, and a package is never written under a leg's.
        floor = clv_minimum(market)
        entry = {
            "sport": sport,
            "market": market,
            # WHOSE LINE, in the Record page's own words for the forecaster
            # (operator question 22): "point spread, statistical".
            "predictor": predictor,
            "category_label": language.closing_line_label(
                language.market_words(sport, market), predictor),
            "n": n,
            "unmeasured": unmeasured,
            "restated": restated,
            "unaccounted": unaccounted,
            "before_window": before_window,
            # QUESTION 12: the later rows of this forecaster's same-side
            # pairs in this market, in no figure here, named beside it.
            "repeats": repeats.get(market, 0),
            "minimum_for_a_claim": floor,
            # THE DATE AND THE SAMPLE, both: a verdict needs fifty closes
            # counted from the repair AND the first clean read to have come.
            "renderable": window["open"] and n >= floor,
            "mean_cents": mean,
            "beat_the_close": beat,
            "words": language.clv_line(
                n, mean, beat, floor, unmeasured=unmeasured,
                restated=restated, unaccounted=unaccounted,
                before_window=before_window, repeats=repeats.get(market, 0),
                since=window["from"],
                first_read=(None if window["open"]
                            else window["first_clean_read"])),
        }
        if entry["renderable"] and mean is not None and mean < 0:
            entry["finding"] = language.clv_finding_line(mean, n)
        # THE SERIES, ON REPAIR'S COUNT (the board merge, 2026-09-29). The
        # board drew the closing line over time from every measured close of a
        # market, both forecasters pooled and from before the repair; its
        # points are now this forecaster's counted rows since the window
        # opened -- `got`, read through `recommend.counted_once` -- and there
        # are none at all until the chart may be drawn: `renderable` needs the
        # first clean read to have come AND the floor (ruling 8: no figure
        # before 15 October; a point is a figure). Below either, the chart
        # area says how far off it is, the date included while it is to come.
        entry["series"] = [
            {"when": r["closed_utc"], "cents": round(r["clv_cents"], 2)}
            for r in sorted(got, key=lambda r: r["closed_utc"] or "")
        ] if entry["renderable"] else []
        entry["gate_words"] = language.chart_gate_words(
            n, floor, first_read=(None if window["open"]
                                  else window["first_clean_read"]))
        # THE CHART'S TITLE, the server's words: whose line, and its N.
        entry["chart_title"] = language.closing_chart_title(
            entry["category_label"], n)
        entries.append(entry)

    open_ids = [r[0] for r in conn.execute(
        "SELECT r.id FROM recommendations r"
        " WHERE r.sport = ? AND r.closed_utc IS NULL"
        + recommend.counted_once(conn, predictor=predictor),
        (sport,))]
    open_rows = len(open_ids)
    # THE GUARD (operator ruling A.2, 2026-10-05): no recommendation this
    # line counts -- closed or awaiting its close -- was priced from a claim
    # across two contracts, asked of each one's pricing claim in Python
    # (`recommend.pricing_claim_ids`), never of the door's SQL.
    refuse_recommendations_across_two_contracts(
        conn, [r["id"] for r in rows] + open_ids,
        what=f"the {sport} closing line, {whose}")
    # NAMED, NEVER COUNTED: the recommendations the rule leaves out, with the
    # tallies the withdrawn recount adds back, as it adds the repeats back.
    across = recommend.priced_across_two_contracts(conn, sport=sport,
                                                   predictor=predictor)
    # WHAT WAS SET ASIDE, TALLIED AS THE COUNTS ABOVE ARE (question 12), so
    # `audit.withdrawn_counted_faults` can still add every standing row up:
    # a measured close is one with its account written at the time.
    aside_ids = [row["id"] for row in aside]
    aside_measured = (conn.execute(
        "SELECT COUNT(*) FROM recommendation_closes c"
        f" WHERE c.recommendation_id IN ({','.join('?' * len(aside_ids))})"
        "   AND c.restated = 0 AND c.clv_cents IS NOT NULL",
        aside_ids).fetchone()[0] if aside_ids else 0)
    # SHOWN, NEVER COUNTED. A withdrawn recommendation that simply vanished
    # from this report would be a deletion by omission; it is named here, with
    # its reason, and in no figure above.
    withdrawn = recommend.withdrawn(conn, sport=sport, predictor=predictor)
    # NAMED, AND COUNTED WHERE THEY WERE (GRIDIRON_REPAIR item 4, 2026-09-26):
    # the recommendations the corrected bar would have refused, beside the
    # closing line and never taken out of it.
    regraded = recommend.regraded(conn, sport=sport, predictor=predictor)
    counted = sum(e["n"] for e in entries)
    block = {
        "predictor": predictor,
        "label": whose,
        # FROM WHEN IT COUNTS, AND THIS FORECASTER'S N SINCE (ruling 8;
        # question 22): the dates are the same for both, the count is not.
        "window_line": {
            "label": language.closing_line_label("Since the repair", predictor),
            "n": counted,
            "words": language.closing_line_window_line(
                window["from"], window["first_clean_read"], counted,
                verdict_open=window["open"], predictor=predictor),
        },
        "n": counted,
        "unmeasured": sum(e["unmeasured"] for e in entries),
        "restated": sum(e["restated"] for e in entries),
        "unaccounted": sum(e["unaccounted"] for e in entries),
        "before_window": sum(e["before_window"] for e in entries),
        "awaiting_close": open_rows,
        "withdrawn": len(withdrawn),
        "withdrawn_line": ({
            "label": language.closing_line_label("Withdrawn", predictor),
            "n": len(withdrawn),
            "words": language.withdrawn_recommendations_line(
                len(withdrawn), [w["reason"] for w in withdrawn]),
        } if withdrawn else None),
        "regraded": len(regraded),
        "regraded_line": ({
            "label": language.closing_line_label("Would not have cleared",
                                                 predictor),
            "n": len(regraded),
            "words": language.regraded_recommendations_line(
                [(g["return_on_cost"], g["minimum_return"]) for g in regraded]),
        } if regraded else None),
        # QUESTION 12: this forecaster's later rows of same-side pairs, each
        # counted once as its earlier row (named per market above).
        "repeats": sum(repeats.values()),
        "set_aside": {
            "n": len(aside),
            "measured": aside_measured,
            "closed": sum(1 for row in aside if row["closed"]),
            "awaiting_close": sum(1 for row in aside if not row["closed"]),
        },
        # PRICED FROM A CLAIM ACROSS TWO CONTRACTS (operator ruling A.2,
        # 2026-10-05): this forecaster's standing recommendations the rule
        # leaves out, named beside the line and in no figure above, tallied
        # as the repeats are so the withdrawn recount can add every standing
        # row up. Once the void tool has written the 54 they are withdrawn
        # and named there; until the operator rules on recs 114 and 115,
        # they are named here.
        "across_two_contracts": {
            "n": len(across),
            "measured": sum(1 for row in across
                            if row["closed"] and row["measured"]),
            "closed": sum(1 for row in across if row["closed"]),
            "awaiting_close": sum(1 for row in across if not row["closed"]),
        },
        "across_line": ({
            "label": language.closing_line_label(
                language.ACROSS_TWO_CONTRACTS_LABEL, predictor),
            "n": len(across),
            "words": language.across_two_contracts_recommendations_line(
                len(across)),
        } if across else None),
    }
    return block, entries


# ---------------------------------------------------------------------------
# THE PRICED FORECASTER'S OWN RECORD (THE_PRICED P1/P4, 2026-09-07)
# ---------------------------------------------------------------------------
#
# NEVER MERGED WITH THE BLIND ONE, and the reason is the whole point of having
# two. A forecaster that reads the price will beat a blind one at predicting
# outcomes while teaching nobody anything about the model's own skill, because
# most of what it knows it read off the market. Reported side by side, they
# answer two different questions: "are we any good?" and "are we making money?"
#
# ITS OBJECTIVE IS NOT A BRIER SCORE. A priced forecaster with a worse Brier
# score and a better closing line is succeeding, and this payload is built so
# the page can say that without a reader thinking something has gone wrong.


def priced_scorecard(conn: sqlite3.Connection, *, sport: str) -> dict:
    """What the priced forecaster's rows say, beside the blind ones.

    Both scores are reported for the same questions -- the priced rows carry
    the id of the blind row they came from -- so the comparison is like for
    like rather than across two different question sets.

    ONE CATEGORY PER MARKET, TIER AND BLIND FORECASTER, ONE ROW PER STANDING
    QUESTION (operator question 14, ruled 2026-09-27, 1 of 3: "Every count on
    the Record page that states a gate distance is rebuilt per forecaster
    (per tier for UFC) and per distinct bet, through its record's standing
    rule."). A priced row blends one blind forecast, so it is counted as that
    forecast's forecaster's, through the one door
    (`priced.forecast.standing_forecasts`, the blind record's standing rule).
    Until this date every settled priced row of a market was one count --
    both forecasters, a question's morning and final pass -- and MLB
    moneyline's gate line said "261 settled comparisons, past the 100 this
    record needs" for 96 and 84 standing questions.

    ONE PER DISTINCT BET, RECOUNTED (operator question 17, 2026-09-28): the
    door keys by `bet` through the standing clause, and the same read asks
    `gridiron.recount` for each forecaster's settled priced bets per market
    without it. A market the recount holds is a category even where the
    door found none, so a door that lost a market is seen, not skipped; each
    category carries `recounted` for `assert_no_pooled_priced_counts`.
    """
    from . import db, recount
    from .priced import forecast as priced

    require_sport(sport, "calibration.priced_scorecard")
    tiers = config.event_tiers(sport) or (None,)
    cells: dict[tuple, list] = {}
    recounted: dict[tuple, int] = {}
    with db.one_instant(conn):
        for tier in tiers:
            for predictor in priced.BLIND_FORECASTERS:
                rows = priced.standing_forecasts(conn, sport=sport,
                                                 predictor=predictor,
                                                 event_tier=tier)
                for row in priced.settled(rows):
                    cells.setdefault((row["market"], tier, predictor),
                                     []).append(row)
                again = recount.priced(conn, sport=sport, predictor=predictor,
                                       event_tier=tier,
                                       blend_version=config.PRICED_VERSION)
                for market, n in again.items():
                    recounted[(market, tier, predictor)] = n
                    cells.setdefault((market, tier, predictor), [])

    categories = []
    # A CATEGORY WHERE SOMETHING HAS SETTLED, as before this date (a market
    # with none showed no row); the markets in name order, then the tiers in
    # their declared order, then the statistical model before the reasoning
    # pass, as every other list on the Record page.
    for market, tier, predictor in sorted(
            cells, key=lambda k: (k[0], tiers.index(k[1]),
                                  priced.BLIND_FORECASTERS.index(k[2]))):
        got = cells[(market, tier, predictor)]
        priced_items = [_PricedResolved(r["priced_prob"], r["outcome"]) for r in got]
        blind_items = [_PricedResolved(r["blind_prob"], r["outcome"]) for r in got]
        market_items = [_PricedResolved(r["price_at_write"], r["outcome"]) for r in got]
        filters = {"sport": sport, "market": market, "predictor": predictor,
                   "record": "priced"}
        if prop_type_of(sport, market):
            filters["prop_type"] = market
        if tier is not None:
            filters["event_tier"] = tier
        categories.append({
            "sport": sport,
            "record": "priced",
            "forecaster": "priced",
            # WHOSE FORECASTS WERE PRICED, and on which card (2026-09-27).
            "predictor": predictor,
            "event_tier": tier,
            "market": market,
            "category": " / ".join([market] + ([tier] if tier else [])
                                   + [predictor, "priced"]),
            "category_label": language.priced_category_label(
                sport, market, predictor, tier),
            "filters": filters,
            "blend_version": config.PRICED_VERSION,
            "n": len(got),
            # COUNTED BESIDE THE DOOR, NOT BY IT: read off the rows' own
            # questions, forecasters and cards, so a door that let a bet in
            # twice, or two forecasters or two cards in, is seen.
            "distinct_bets": bet.count(got),
            "recounted": recounted.get((market, tier, predictor), 0),
            "forecasters_counted": sorted({r["predictor"] for r in got}),
            "tiers_counted": sorted({r["event_tier"] for r in got
                                     if r["event_tier"] is not None}),
            "priced": score(priced_items),
            "blind_on_the_same_questions": score(blind_items),
            "market_on_the_same_questions": score(market_items),
            "buckets": calibration_buckets(priced_items),
            "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
            "gate_line": language.at_the_line_gate_line(
                len(got), config.MIN_SAMPLE_FOR_EDGE_CLAIM),
        })

    payload = {
        "sport": sport,
        "record": "priced",
        "blend_version": config.PRICED_VERSION,
        # THE NAME'S ONE PLACE ON THE PAGE (operator question 19; the board
        # merge, 2026-09-29): the heading's tooltip, with what it names.
        "version_tip": language.version_tip("blend", config.PRICED_VERSION),
        "model_weight": config.PRICED_MODEL_WEIGHT,
        "declared": config.PRICED_WEIGHT_DECLARED,
        # NO TOTAL, AND NO POOLED "AWAITING" COUNT (2026-09-27). The `n` that
        # stood here summed every category -- both forecasters -- and
        # `awaiting_outcome` counted every unsettled priced row of the sport,
        # both passes of a question included. Neither was painted; both
        # described nobody's record, as item 6's at-the-line total did.
        "categories": categories,
        "note": (
            "A second forecaster that reads the price the blind one is forbidden "
            "to see. Its scores are shown beside the blind forecaster's on the "
            "same questions and are never added to them. A better Brier score "
            "here would mostly be the market's skill, not this project's, which "
            "is why the number that matters for this record is the closing line "
            "rather than the curve."
        ),
    }
    # INSIDE THE BUILDER (question 14, 2026-09-27), so the API answers 500
    # rather than serve a pooled count, and the gate's build of every sport
    # on the record's copy runs it (`audit.check_the_priced_record_is_never_pooled`).
    assert_no_pooled_priced_counts(payload)
    assert_every_figure_has_n(payload)
    assert_single_sport(payload, sport)
    return payload


#: The three scores a priced category reports on ONE set of questions.
PRICED_SCORES = ("priced", "blind_on_the_same_questions",
                 "market_on_the_same_questions")


def assert_no_pooled_priced_counts(payload: dict) -> None:
    """Every count in the priced record is ONE blind forecaster's STANDING
    QUESTIONS, once each -- and for UFC one card's.

    The operator's ruling on question 14 (2026-09-27): "Every count on the
    Record page that states a gate distance is rebuilt per forecaster (per
    tier for UFC) and per distinct bet, through its record's standing rule."
    Checked on the payload, as `assert_no_pooled_claims` checks the
    at-the-line record's -- and it runs `assert_no_merged_categories` first,
    so the sport, the market, the forecaster and the tier are one rule for
    every record.

    Then, by name: a category that counts more rows than it has distinct
    bets (a question's morning and final pass); one whose rows are another
    forecaster's, or another card's, than the one it names; one naming no
    blind forecaster; a count other than the one `gridiron.recount` makes
    without the door, one per distinct bet by the one key (operator question
    17, 2026-09-28: a door keyed without the rung, or across forecasters);
    a score on other questions than the count; a gate line stating another
    count than its own (the page said "261 settled comparisons, past the
    100" for 96 and 84 standing questions on 26 September); and a total or a
    pooled "awaiting" count across categories. Raised inside
    `priced_scorecard`, so the API answers 500 rather than serving a pool.
    """
    from .priced import forecast as priced

    law = "LAW 4 / LAW 6 IN THE PRICED RECORD"
    assert_no_merged_categories(payload)
    sport = payload.get("sport")
    tiers = config.event_tiers(sport)
    for key in ("n", "awaiting_outcome"):
        if key in payload:
            raise MergedCurve(
                f"{law}: the priced payload carries a total {key!r} of "
                f"{payload[key]!r}, a sum across its categories and so across "
                f"both forecasters and every pass of a question, which is "
                f"nobody's record.")
    for category in payload.get("categories") or []:
        what = f"priced category {category.get('category')!r}"
        if category.get("record") != "priced":
            raise MergedRecord(
                f"{what} belongs to the {category.get('record')!r} record and "
                f"is filed under the priced one.")
        named = category.get("predictor")
        filtered = (category.get("filters") or {}).get("predictor")
        if named not in priced.BLIND_FORECASTERS or filtered != named:
            raise MergedCurve(
                f"{law}: {what} names forecaster {named!r} (filtered by "
                f"{filtered!r}). A priced row blends one blind forecast, and "
                f"the statistical model's and the reasoning pass's are counted "
                f"apart and never pooled.")
        counted = category.get("forecasters_counted")
        if counted not in ([], [named]):
            raise MergedCurve(
                f"{law}: {what} is the {named!r} forecaster's and counts rows "
                f"on the forecasts of {counted!r}: two forecasters pooled into "
                f"one count.")
        tier, cards = category.get("event_tier"), category.get("tiers_counted")
        if tiers:
            if tier not in tiers or cards not in ([], [tier]):
                raise MergedCurve(
                    f"{law}: {what} names event tier {tier!r} and counts bouts "
                    f"on {cards!r}; {sport}'s tiers {list(tiers)} are reported "
                    f"side by side, never summed.")
        elif tier is not None or cards not in ([], None):
            raise MergedCurve(
                f"{law}: {what} names event tier {tier!r} in {sport}, which "
                f"declares none.")
        n, bets = category.get("n"), category.get("distinct_bets")
        if bets is None or n != bets:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled priced rows for {bets} "
                f"distinct bet{'' if bets == 1 else 's'}. A question is counted "
                f"once, on its standing forecast, however many passes priced it.")
        for key in PRICED_SCORES:
            scored = (category.get(key) or {}).get("n")
            if scored != n:
                raise MergedCurve(
                    f"{law}: {what} counts {n} and scores {key!r} on {scored!r}: "
                    f"two counts of one record.")
        said = language.at_the_line_gate_line(n, category.get("gate"))
        if category.get("gate_line") != said:
            raise MergedCurve(
                f"{law}: {what}'s gate line says {category.get('gate_line')!r}, "
                f"which is not its own count of {n}.")
        # AND THE RECOUNT MADE WITHOUT THE DOOR (operator question 17,
        # 2026-09-28): a door keyed without the rung, or across forecasters,
        # counts other questions than the record holds while its own
        # distinct bets, scores and gate line all agree with it.
        if category.get("recounted") != n:
            raise MergedCurve(
                f"{law}: {what} counts {n} settled priced rows where the "
                f"recount made without its door finds "
                f"{category.get('recounted')!r}, one per distinct bet by the "
                f"one key (`bet.of`: the forecaster, the game, the market, the "
                f"subject and the rung asked). A door keyed any other way -- "
                f"without the rung, or across forecasters -- counts other bets "
                f"than the record holds (operator question 17, 2026-09-28).")


@dataclass(frozen=True)
class _PricedResolved:
    """The two fields the bucket and score functions actually read."""
    model_prob: float
    outcome: int


def taken_comparison(conn: sqlite3.Connection, *, sport: str,
                     market_type: str, prop_type: str | None = None,
                     predictor: str = "statistical",
                     event_tier: str | None = None) -> dict:
    """Do the picks the operator took score better than the ones he passed over?

    THREE CURVES, NEVER MERGED: taken, not taken, and all of them. The third is
    not the sum of the first two in any useful sense -- it is the population
    both were drawn from, and it is reported so that a reader can see whether
    either group differs from the model's ordinary behaviour at all.

    NOTHING HERE FEEDS THE MODEL. This is a report about a human being's
    choices, read after the fact; `audit.check_taken_not_in_training` refuses
    the table's name in anything that trains or corrects, and a planting proves
    it fires.

    ONE CARD'S FOR UFC (operator question 34, ruled 2026-09-30; built
    2026-10-08): the card is required for a sport that splits by card, the
    payload names it and carries the cards its rows were on and the three
    counts as `gridiron.recount` makes them without the door, and
    `assert_no_pooled_taken_record` refuses another card's count inside this
    builder. Until this date UFC's "passed over 49 of 100 ... every forecast
    49" counted the three cards as one (39, 10 and 0 on 29 September).
    """
    from . import db, recount

    require_sport(sport, "calibration.taken_comparison")
    refuse_a_count_across_cards(sport, event_tier, "the taken record")
    with db.one_instant(conn):
        items = resolved(conn, sport=sport, market_type=market_type,
                         prop_type=prop_type, predictor=predictor,
                         event_tier=event_tier)
        standing = recount.settled_standing(
            conn, sport=sport, predictor=predictor, market_type=market_type,
            prop_type=prop_type, event_tier=event_tier)
        again_taken = recount.taken(conn, standing)
    # SINGLE TAPS ONLY IN THIS COMPARISON. A package tap is a row in the same
    # table carrying a package id instead of a prediction id, and it belongs to
    # `combo_2`/`combo_3` rather than to this market -- counting it here would
    # put a package in a leg's curve, which is LAW 6 one level down.
    # TAKEN IS A DISTINCT BET TAKEN (the board merge, 2026-09-29; operator
    # question 17's key). `items` holds one standing row per distinct bet --
    # the final pass before the start where one exists (question 27) -- and a
    # tap names whichever row was on the page when it was made. Matched by
    # row number, a question tapped on its morning pass and standing on its
    # final one was counted "passed over"; matched by `bet.of`, a tap on any
    # pass of a question takes that question, once. The board brought this
    # comparison onto the Record page (2026-09-25), where a gate distance is
    # a count on the key.
    # A TAP ON A WITHDRAWN FORECAST TAKES NOTHING (operator ruling 1,
    # 2026-09-24: a voided forecast is never counted): the tap stays, as
    # every tap does, and the question it named is not moved into the taken
    # curve by another pass of it the operator was never shown.
    taken_keys = {
        bet.of(r) for r in conn.execute(
            f"SELECT {bet.columns('p')} FROM picks_taken t"
            "  JOIN predictions p ON p.id = t.prediction_id"
            " WHERE t.prediction_id IS NOT NULL"
            "   AND t.id NOT IN (SELECT taken_id FROM picks_retracted)"
            "   AND NOT EXISTS (SELECT 1 FROM prediction_voids v"
            "                   WHERE v.prediction_id = p.id)")
    }
    took = [r for r in items if bet.of(r) in taken_keys]
    passed = [r for r in items if bet.of(r) not in taken_keys]
    gate = config.MIN_SAMPLE_FOR_EDGE_CLAIM
    payload = {
        "sport": sport,
        "record": "taken",
        # WHOSE (the board merge, 2026-09-29): one forecaster's questions.
        "predictor": predictor,
        "market": prop_type or market_type,
        "n": len(items),
        "gate": gate,
        "taken": {"label": "taken", "n": len(took), "score": score(took),
                  "buckets": calibration_buckets(took)},
        "not_taken": {"label": "passed over", "n": len(passed),
                      "score": score(passed), "buckets": calibration_buckets(passed)},
        "all": {"label": "every forecast", "n": len(items), "score": score(items),
                "buckets": calibration_buckets(items)},
        "renderable": len(took) >= gate and len(passed) >= gate,
        "note": (
            "What the operator chose against what he passed over, on the same "
            "questions and the same scale. It reads his selections, never the "
            "model's inputs: nothing that trains or corrects the model may see "
            "this table."
        ),
    }
    payload["words"] = language.taken_comparison_line(
        len(took), len(passed), gate,
        payload["taken"]["score"]["brier"] if payload["renderable"] else None,
        payload["not_taken"]["score"]["brier"] if payload["renderable"] else None)
    payload["recounted"] = {"taken": again_taken,
                            "not_taken": len(standing) - again_taken,
                            "all": len(standing)}
    if config.event_tiers(sport):
        # ONE CARD'S, NAMED (operator question 34, 2026-10-08) -- keys only a
        # carded sport's record carries, so no other sport's changes.
        payload["event_tier"] = event_tier
        payload["tiers_counted"] = _cards_of(items)
    assert_no_pooled_taken_record(payload)
    return payload


def assert_no_pooled_taken_record(payload: dict) -> None:
    """THE TAKEN RECORD IS ONE CARD'S FOR UFC (operator question 34, ruled
    2026-09-30; built 2026-10-08). Refused by name, inside
    `taken_comparison`, so `/api/scorecard` answers 500: a record naming no
    card, or one of none, in a sport that splits by card; one counting rows
    on another card than it names, or on every card (`tiers_counted`, read
    off each row's own bout); and a count of taken, passed over or every
    forecast other than the one `gridiron.recount` makes without the door
    (`recounted`)."""
    sport = payload.get("sport")
    what = (f"the taken record for {sport} {payload.get('market')}, "
            f"{payload.get('predictor')}")
    refuse_another_cards_count(sport, payload.get("event_tier"),
                               payload.get("tiers_counted", []), what)
    said = tuple((payload.get(k) or {}).get("n")
                 for k in ("taken", "not_taken", "all"))
    again = payload.get("recounted") or {}
    want = tuple(again.get(k) for k in ("taken", "not_taken", "all"))
    if said != want or payload.get("n") != said[2]:
        raise PooledCardCount(
            f"QUESTION 34: EVERY UFC COUNT IS PER CARD TIER: {what} counts "
            f"taken, passed over and every forecast {said} (n "
            f"{payload.get('n')!r}) where the recount made without its door "
            f"finds {want}.")


# `combo_kill_verdict` STOOD HERE from 2026-09-08 until C4 was WITHDRAWN on
# 2026-09-09. It asked whether a sport's packages were losing to the close
# while its singles beat it, and retired the combo markets when they were.
#
# IT COULD NEVER HAVE FIRED. It counted SETTLED packages, and a combo cannot
# settle: the app never sees the price the operator was quoted, so there is no
# closing line to compare against and no verdict to reach. A criterion that
# cannot fire is worse than no criterion -- it reads as a safety net while
# being a sign saying one is there.
#
# What replaced it is a sentence on the card and a line in READINESS saying
# the product is unmeasurable by construction, which is the true thing.


def taken_packages(conn: sqlite3.Connection, *, sport: str) -> dict:
    """The combo line on the taken record: what he took, of what was offered.

    ITS OWN LINE AND NEVER MERGED into the single-leg comparison. A package and
    a leg are different products at different prices with different fees, and
    one curve holding both would report a rate for a thing nobody buys.

    IT IS A COUNT, NOT A CURVE, until there are packages to score. Below the
    gate that is all it can honestly be, and the sentence says so.
    """
    require_sport(sport, "calibration.taken_packages")
    # PLACED IN GAMES THIS RECORD HOLDS, or it was never priceable here. A
    # package naming games the project has never seen has no legs to multiply,
    # so it is not one of the packages this app was "able to price at all" and
    # does not belong in the denominator. Added 2026-09-08 after a verification
    # run against the live database wrote exactly such a row.
    offered = conn.execute(
        "SELECT COUNT(*) FROM venue_packages v WHERE v.sport = ? AND v.priceable = 1"
        "   AND EXISTS (SELECT 1 FROM games g WHERE instr(v.game_ids, g.id) > 0)",
        (sport,)).fetchone()[0]
    took = conn.execute(
        "SELECT COUNT(*) FROM picks_taken t"
        "  JOIN venue_packages p ON p.id = t.package_id"
        " WHERE p.sport = ?"
        "   AND t.id NOT IN (SELECT taken_id FROM picks_retracted)"
        "   AND EXISTS (SELECT 1 FROM games g WHERE instr(p.game_ids, g.id) > 0)",
        (sport,)).fetchone()[0]
    return {
        "sport": sport,
        "record": "taken_packages",
        "market": "packages",
        "offered": offered,
        "n": took,
        "gate": config.MIN_SAMPLE_FOR_EDGE_CLAIM,
        "renderable": False if took < config.MIN_SAMPLE_FOR_EDGE_CLAIM else True,
        "words": language.taken_packages_line(
            took, offered, config.MIN_SAMPLE_FOR_EDGE_CLAIM),
        "note": (
            "Packages the operator marked, against the packages this app was "
            "able to price at all. It is its own line: a package and a single "
            "leg are different products, and one curve holding both would "
            "describe neither."
        ),
    }
