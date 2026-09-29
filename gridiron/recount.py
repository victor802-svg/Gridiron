"""THE GUARD'S RECOUNT: every gate count the Record page states for the four
records keyed by a distinct bet -- at the venue's line, the priced record,
where the line went and the line beside each blind curve -- worked out again
from rows read straight off their tables, one per distinct bet (`bet.of`),
by each record's standing rule restated here in Python (operator question
17, ruled 2026-09-27; built 2026-09-28). And from 2026-09-29 the correction
gates' (`correction`: operator question 16), whose rule is settled before an
instant and withdrawn by no void at it.

WHY A SECOND SPELLING OF A STANDING RULE, where the house rule is one door.
The door is the rule; this is how the guard knows the door kept it. A door
keyed any other way than `bet` -- without the rung, so two rungs of one game
count as one bet, or without the forecaster, so one forecaster's later row
stands in for the other's question -- returns a count that its own
`distinct_bets` agrees with, because both are counted off the door's own
rows. Only a count made without the door can see it. So each builder asks
this module beside its door, inside one read of the database
(`db.one_instant`), puts the answer on the payload as `recounted`, and each
record's guard refuses a count that differs from it, by name. Question 12's
pair recount (`audit._closing_line_rows`) is the precedent: a recount that
went through the door would agree with a broken one.

WHAT IS NOT RESTATED: the key. Every recount groups by `bet.of` -- the one
function -- so the door and the recount can differ only where the door keys
or keeps otherwise.

WHICH PASS STANDS IS RESTATED (operator question 27, ruled 2026-09-28): a
final pass written before the start stands, otherwise the latest written
(`_final_before_the_start`, `calibration.standing_pass_order` in Python),
for the blind record's forecasts and the at-the-line record's claims alike.

NOT ON THE PREDICTION PATH: it reads the venue's claims and the line's
snapshots, so nothing in the blind import closure may import it; the key it
counts by (`gridiron.bet`) is closure-clean, for question 16's correction.
"""
from __future__ import annotations

import sqlite3

from . import bet


def _on_the_card(game: str, event_tier: str | None) -> tuple[str, list]:
    """The card filter every UFC count asks, reached through the bout, as the
    doors reach it: a cell filter, never part of the key."""
    if event_tier is None:
        return "", []
    return (" AND EXISTS (SELECT 1 FROM ufc_bouts b JOIN ufc_events e"
            "               ON e.id = b.event_id"
            f"              WHERE b.id = {game} AND e.event_tier = ?)",
            [event_tier])


def forecasts(conn: sqlite3.Connection, *, sport: str, predictor: str,
              market_type: str | None, prop_type: str | None,
              event_tier: str | None) -> list[dict]:
    """Every forecast of one forecaster in one sport -- in one market when
    `market_type` is named -- read straight off the table: no standing
    clause, no key, every pass, every withdrawal marked rather than left out.

    THE CELL AS ITS DOOR ASKS IT (the prover, 2026-09-28): `prop_type` None
    asks no prop type (the outlook's and the coverage line's doors, as the
    curve asks); '' asks a row with none, NULL or '' (the drift door's
    `IFNULL(p.prop_type, '') = ''` for a market that is not a prop); a name
    asks that type. A recount asking a wider cell than its door would refuse
    an honest count over a row the door was never asked about."""
    card, params = _on_the_card("p.game_id", event_tier)
    where = ["p.sport = ?", "p.predictor = ?"]
    first: list = [sport, predictor]
    if market_type is not None:
        where.append("p.market_type = ?")
        first.append(market_type)
    if prop_type == "":
        where.append("IFNULL(p.prop_type, '') = ''")
    elif prop_type is not None:
        where.append("p.prop_type = ?")
        first.append(prop_type)
    # THE PROP TYPE BESIDE THE KEY, NOT IN IT (2026-09-29): `priced` names a
    # row's market by it, and `bet.columns` carried it until the key left it
    # out (a prop's question is named by its subject; `gridiron.bet`).
    # THE PASS BESIDE THE KEY (operator question 27, 2026-09-28): the
    # standing rule chooses a question's row by it (`standing_of`).
    return [dict(r) for r in conn.execute(
        f"SELECT p.id, {bet.columns('p')}, p.prop_type, p.created_utc,"
        "       p.pass_kind, p.resolved_utc,"
        "       p.outcome, p.model_prob, p.calibrated_prob, g.kickoff_utc,"
        "       g.season, g.week,"
        "       EXISTS (SELECT 1 FROM prediction_voids v"
        "                WHERE v.prediction_id = p.id) AS voided"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE {' AND '.join(where)}{card}", first + params)]


def _final_before_the_start(pass_kind: str, written: str,
                            kickoff: str | None) -> bool:
    """`calibration.standing_pass_order`'s first term, in Python: a final
    pass written before its game's start, or on a game with no start time
    recorded (operator question 27, 2026-09-28). `written` is the
    forecast's own write time, for a claim as for a forecast."""
    return pass_kind == "final" and (kickoff is None or written <= kickoff)


def standing_of(rows: list[dict]) -> dict[tuple, dict]:
    """THE BLIND RECORD'S STANDING RULE, worked out again: one forecast per
    distinct bet -- a final pass written before the start if there is one,
    otherwise the latest written before the start (the id breaking a tie), a
    withdrawn one never.

    `calibration.standing_row_clause` in Python, clause by clause: a
    withdrawn row never stands and never displaces an earlier one; a game
    with no start time keeps every row eligible; a question with any row
    written before its start -- withdrawn or not -- stands on one of those;
    a question with none (a backtest's) stands on its latest row.

    CHOSEN BY PASS (operator question 27, ruled 2026-09-28): among the rows
    that may stand, the order is `calibration.standing_pass_order`'s -- a
    final pass before the start first, then the latest written, then the
    number. Until this date the order here was the write time alone, as the
    clause's was; the two moved together, so a door that kept a later early
    pass over a final one agreed with this count. From this date a door
    choosing by write time counts what this does not wherever the choice
    moves a count (a question whose final pass was priced and its later
    early pass was not, or the other way round), and
    `audit.distinct_bet_key_faults` reads the clause's own order for the rest.
    """
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault(bet.of(row), []).append(row)
    out = {}
    for key, group in groups.items():
        kickoff = group[0]["kickoff_utc"]
        live = [r for r in group if not r["voided"]]
        if kickoff is not None and any(r["created_utc"] <= kickoff for r in group):
            live = [r for r in live if r["created_utc"] <= kickoff]
        if live:
            out[key] = max(live, key=lambda r: (
                _final_before_the_start(r["pass_kind"], r["created_utc"], kickoff),
                r["created_utc"], r["id"]))
    return out


def claims(conn: sqlite3.Connection, *, sport: str, market: str,
           predictor: str, event_tier: str | None) -> list[dict]:
    """Every claim of one forecaster in one market at the venue's line, read
    straight off the table, each with its forecast's key: every pass, every
    look, withdrawals marked rather than left out."""
    card, params = _on_the_card("c.game_id", event_tier)
    # EACH CLAIM'S FORECAST'S PASS AND WRITE TIME (operator question 27,
    # 2026-09-28): the claim that stands is chosen by its forecast's pass.
    return [dict(r) for r in conn.execute(
        f"SELECT c.id, c.prediction_id, c.market, c.line, c.model_prob,"
        f"       c.venue_implied, c.created_utc, c.resolved_utc, c.outcome,"
        f"       p.pass_kind, p.created_utc AS forecast_utc,"
        f"       {bet.columns('p')}, g.kickoff_utc, g.season, g.week,"
        "       EXISTS (SELECT 1 FROM prediction_voids v"
        "                WHERE v.prediction_id = c.prediction_id) AS voided"
        "  FROM at_the_line_claims c"
        "  JOIN predictions p ON p.id = c.prediction_id"
        "  JOIN games g ON g.id = c.game_id"
        f" WHERE c.sport = ? AND c.market = ? AND p.predictor = ?{card}",
        [sport, market, predictor] + params)]


def standing_claims_of(rows: list[dict]) -> dict[tuple, dict]:
    """THE AT-THE-LINE RECORD'S STANDING RULE, worked out again: one claim
    per distinct bet -- a final pass's claim if one was written before the
    start, otherwise the last written before the start, the id breaking a
    tie -- never one on a withdrawn forecast and never one written at or
    after the start (`at_the_line.standing_claims`, in Python).

    CHOSEN BY PASS (operator question 27, ruled 2026-09-28): the claim's
    forecast's pass first, as `calibration.standing_pass_order` orders the
    door's window; the last written before the start until then."""
    def order(row: dict) -> tuple:
        return (_final_before_the_start(row["pass_kind"], row["forecast_utc"],
                                        row["kickoff_utc"]),
                row["created_utc"], row["id"])

    out: dict[tuple, dict] = {}
    for row in rows:
        if row["voided"]:
            continue
        if row["kickoff_utc"] is not None and not row["created_utc"] < row["kickoff_utc"]:
            continue
        key = bet.of(row)
        held = out.get(key)
        if held is None or order(row) > order(held):
            out[key] = row
    return out


def _settled_claim(row: dict) -> bool:
    return row["resolved_utc"] is not None and row["outcome"] is not None


def at_the_line(conn: sqlite3.Connection, *, sport: str, market: str,
                predictor: str, event_tier: str | None,
                threshold: float | None = None) -> dict:
    """One forecaster's cell at the venue's line, recounted: its standing
    claims (`claims`, and `settled` -- the curve's n, the edge's), the
    hypothetical ledger's qualifying settled claims at `threshold` (the
    ledger's own, `paper.qualifying`), and the coverage line's standing
    questions (`questions`) and how many of them hold a standing claim
    (`read`)."""
    from .market import paper

    chosen = standing_claims_of(claims(conn, sport=sport, market=market,
                                       predictor=predictor,
                                       event_tier=event_tier))
    settled = [c for c in chosen.values() if _settled_claim(c)]
    questions = standing_of(forecasts(conn, sport=sport, predictor=predictor,
                                      market_type=market, prop_type=None,
                                      event_tier=event_tier))
    return {
        "claims": len(chosen),
        "settled": len(settled),
        "qualifying": sum(1 for c in settled if paper.qualifying(
            c["model_prob"], c["venue_implied"], threshold) is not None),
        "questions": len(questions),
        "read": len(questions.keys() & chosen.keys()),
    }


def priced(conn: sqlite3.Connection, *, sport: str, predictor: str,
           event_tier: str | None, blend_version: int) -> dict[str, int]:
    """One blind forecaster's settled priced rows, recounted per market as
    the record names it: the rows of `blend_version` on each distinct bet's
    STANDING forecast (the blind rule above), a question whose standing
    forecast carried no price not counted."""
    standing = standing_of(forecasts(conn, sport=sport, predictor=predictor,
                                     market_type=None, prop_type=None,
                                     event_tier=event_tier))
    settled = {r["prediction_id"] for r in conn.execute(
        "SELECT prediction_id FROM priced_forecasts"
        " WHERE sport = ? AND blend_version = ? AND outcome IS NOT NULL",
        (sport, blend_version))}
    out: dict[str, int] = {}
    for row in standing.values():
        if row["id"] in settled:
            market = row["prop_type"] or row["market_type"]
            out[market] = out.get(market, 0) + 1
    return out


def drift(conn: sqlite3.Connection, *, sport: str, market_type: str,
          prop_type: str | None, predictor: str,
          event_tier: str | None) -> int:
    """One forecaster's media-line drift pairs in one market, recounted: the
    distinct bets whose STANDING forecast has both looks at the line and
    disagreed with the first by `drift.MIN_DISAGREEMENT` or more."""
    from . import drift as media

    standing = standing_of(forecasts(conn, sport=sport, predictor=predictor,
                                     market_type=market_type,
                                     prop_type=prop_type,
                                     event_tier=event_tier))
    if not standing:
        return 0
    ids = [r["id"] for r in standing.values()]
    looks: dict[tuple, float] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        for r in conn.execute(
                "SELECT prediction_id, kind, implied_prob FROM market_snapshots"
                f" WHERE prediction_id IN ({','.join('?' for _ in chunk)})"
                "   AND kind IN ('open_at_predict', 'near_start')", chunk):
            if r["implied_prob"] is not None:
                looks[(r["prediction_id"], r["kind"])] = r["implied_prob"]
    pairs = 0
    for row in standing.values():
        opened = looks.get((row["id"], "open_at_predict"))
        near = looks.get((row["id"], "near_start"))
        if opened is None or near is None:
            continue
        claim = (row["calibrated_prob"] if row["calibrated_prob"] is not None
                 else row["model_prob"])
        if abs(claim - opened) >= media.MIN_DISAGREEMENT:
            pairs += 1
    return pairs


def correction(conn: sqlite3.Connection, *, sport: str, market_type: str,
               predictor: str, before_utc: str,
               version: int | None = None, as_it_stood: bool = False) -> int:
    """One correction category's gate count, recounted (operator question 16,
    ruled 2026-09-27; built 2026-09-29): every forecast of the category read
    straight off the table -- every pass, every rung, both forecasters' rows
    left to the filter below, no door -- and counted by `bet.of` where it had
    an outcome before `before_utc` and no void -- none at all, or, read as it
    stood at the instant, none stamped at or before it (the prover,
    2026-09-29: a void stamped after now is a withdrawal on the record now) --
    only those written under `version` when one is named.
    `correction.settled_rows` in Python, clause by clause; the key is not
    restated."""
    rows = [dict(r) for r in conn.execute(
        f"SELECT p.id, {bet.columns('p')}, p.resolved_utc, p.outcome,"
        "       p.correction_version,"
        "       (SELECT MIN(v.voided_utc) FROM prediction_voids v"
        "         WHERE v.prediction_id = p.id) AS voided_utc"
        "  FROM predictions p"
        " WHERE p.sport = ? AND p.market_type = ?",
        (sport, market_type))]
    return bet.count(
        r for r in rows
        if r["predictor"] == predictor
        and r["resolved_utc"] is not None and r["outcome"] is not None
        and r["resolved_utc"] < before_utc
        and (r["voided_utc"] is None
             or (as_it_stood and r["voided_utc"] > before_utc))
        and (version is None or r["correction_version"] == version))


def outlook(conn: sqlite3.Connection, *, sport: str, market_type: str,
            prop_type: str | None, predictor: str, event_tier: str | None,
            season: int) -> dict:
    """The line beside one blind curve, recounted: the distinct bets whose
    standing forecast has settled (`settled`, the curve's n) and those
    written in `season` (`written`, the pace's)."""
    standing = standing_of(forecasts(conn, sport=sport, predictor=predictor,
                                     market_type=market_type,
                                     prop_type=prop_type,
                                     event_tier=event_tier))
    return {
        "settled": sum(1 for r in standing.values() if r["resolved_utc"] is not None),
        "written": sum(1 for r in standing.values() if r["season"] == season),
    }
