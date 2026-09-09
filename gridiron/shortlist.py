"""The rank, and the shortlist it produces (THE_SHORTLIST S1-S2, 2026-09-07).

**Nothing here changes what is predicted.** Every question the model asks it
still asks, still resolves and still scores; this decides only what the Picks
page puts in front of a person first, and the rest sits one tap behind a
control with its own count on its face. A page that quietly dropped fifty
questions would be lying about the record, and the count is what makes that
impossible to do by accident.

**A rank is an ordering, not a claim.** It states no probability, no edge and
no advice. It is written to `prediction_ranks` -- append-only, timestamped,
carrying the factor set and the ranker version -- for one reason above all
others: so the ranker itself can be scored later, by comparing what it put on
the shortlist against what it left off. A ranking nobody can check is a matter
of taste, and this project does not ship those.

THREE INPUTS, DECLARED IN CONFIG AND NOT TUNED (LAW 2):

  * **Confidence**, how far the model's own probability sits from a coin flip.
  * **Completeness**, the share of the declared factors that were actually
    present. A question asked with an unannounced starting pitcher is a worse
    question than the same one asked with the lineup in, and until now that
    absence was invisible on the page rather than costly.
  * **Edge against the market's line, GATED.** It carries zero weight until
    the market it belongs to has passed its own hundred-resolution gate. The
    reasoning is in `config.RANK_EDGE_GATE` and it is the most consequential
    decision in this module: before a model has earned a verdict, the
    questions where it most disagrees with a liquid market are mostly the
    questions where it is most wrong.

THIS MODULE IS OUTSIDE THE PREDICTION CLOSURE and stays there. It reads the
frozen prediction row and the market snapshot attached to it, both of which
exist only after the blind window has closed.
"""
from __future__ import annotations

import json
import sqlite3

from . import config
from .db import just_after, utcnow


class RankIsNotAClaim(RuntimeError):
    """A rank was read as, or written as, something other than an ordering."""


def confidence_score(model_prob: float | None) -> float:
    """How far from a coin flip, on nothing to certain.

    A stored probability below a half is a confident claim about the other
    side -- the record already treats it that way everywhere else -- so the
    distance is symmetric around 50.
    """
    if model_prob is None:
        return 0.0
    return round(min(1.0, max(0.0, abs(float(model_prob) - 0.5) * 2.0)), 6)


def completeness_score(factors_json: str | None) -> float:
    """The share of the question's declared factors that were present.

    Read off the frozen payload's own coverage figure, which the feature
    vector computed at the time; recomputing it here would be a second
    implementation of the same number and the two would eventually disagree.
    """
    try:
        payload = json.loads(factors_json or "{}") or {}
    except ValueError:
        return 0.0
    coverage = payload.get("coverage")
    if not isinstance(coverage, (int, float)):
        return 0.0
    return round(min(1.0, max(0.0, float(coverage))), 6)


def edge_score(model_prob: float | None, implied_prob: float | None) -> float | None:
    """How far the model sits from the market's own implied probability.

    None where the market never quoted this question. ABSENT STAYS ABSENT: an
    unquoted market is not a market the model agrees with, and writing zero
    here would say exactly that.
    """
    if model_prob is None or implied_prob is None:
        return None
    gap = abs(float(model_prob) - float(implied_prob))
    return round(min(1.0, gap / config.RANK_EDGE_SCALE), 6)


def combine(confidence: float, completeness: float, edge: float | None,
            *, edge_counted: bool) -> float:
    """The declared weights, over the inputs actually in play.

    RENORMALISED, DELIBERATELY. An input that is not in play -- an edge below
    its market's gate, or a market that quoted nothing -- is not scored as a
    zero, because a zero is a measurement and this is an absence. The weights
    that remain are rescaled to sum to one, so a question whose market has
    opened its gate is not ranked on a longer scale than one whose market has
    not, and the shortlist does not silently reorder itself the day a gate
    opens.
    """
    weights = config.RANK_WEIGHTS
    parts = [(weights["confidence"], confidence), (weights["completeness"], completeness)]
    if edge_counted:
        if edge is None:
            raise RankIsNotAClaim(
                "the edge was counted with nothing to count: a rank may not "
                "treat an unquoted market as a zero disagreement")
        parts.append((weights["edge"], edge))
    total = sum(w for w, _ in parts)
    if not total:
        return 0.0
    return round(sum(w * x for w, x in parts) / total, 6)


def settled_for_gate(conn: sqlite3.Connection, sport: str, market_type: str,
                     prop_type: str | None, predictor: str) -> int:
    """How many of this market's questions have actually resolved.

    THE SAME DOOR THE RECORD USES. `calibration.resolved` applies the standing
    clause -- one row per question, the latest written before the start -- so
    the count that opens the edge gate is the same count the Record page shows
    beside every other figure. A second implementation here would be a second
    definition of "settled", and this project has been bitten by exactly that.
    """
    from . import calibration

    return len(calibration.resolved(
        conn, sport=sport, market_type=market_type, prop_type=prop_type,
        predictor=predictor))


def _gate_lookup(conn: sqlite3.Connection):
    """Settled counts, once per category per run rather than once per row."""
    cache: dict[tuple, int] = {}

    def counted(sport, market_type, prop_type, predictor):
        key = (sport, market_type, prop_type, predictor)
        if key not in cache:
            cache[key] = settled_for_gate(conn, sport, market_type, prop_type,
                                          predictor)
        return cache[key]

    return counted


def rank_rows(conn: sqlite3.Connection, prediction_ids: list[int] | None = None,
              *, backfilled: bool = False) -> dict:
    """Write a rank for every prediction that does not have one yet.

    Called after the market step, where the snapshot the edge is measured
    against already exists. Rerunning is safe: a prediction already ranked
    under this ranker version is left alone, because a rank is append-only and
    a second opinion about the same row under the same formula is not a thing
    this table can hold.
    """
    counts = {"ranked": 0, "already": 0, "edge_counted": 0, "no_line": 0,
              "considered": 0, "shortlisted": 0}
    where = ["1 = 1"]
    params: list = []
    if prediction_ids is not None:
        if not prediction_ids:
            return counts
        where.append("p.id IN (%s)" % ",".join("?" for _ in prediction_ids))
        params.extend(prediction_ids)
    rows = conn.execute(
        "SELECT p.id, p.sport, p.game_id, p.market_type, p.prop_type, p.predictor,"
        " p.model_prob, p.factors_json, p.factor_set_version, p.created_utc,"
        " g.season, g.week,"
        " (SELECT s.implied_prob FROM market_snapshots s"
        "   WHERE s.prediction_id = p.id ORDER BY s.id LIMIT 1) AS implied_prob,"
        # WHETHER THIS IS THE ROW THE RECORD GRADES. Through the same clause
        # every count on the Record page uses, because a selection that
        # disagreed with the record about which forecast stands would put rows
        # on a shortlist the page cannot show.
        f"      (SELECT 1{_standing_clause()}) AS is_standing,"
        # DOES THE VENUE LIST THIS QUESTION (operator ruling, 2026-09-09).
        # A question the venue does not price cannot become a recommendation,
        # so it ranks behind every question that can. Read off the quote rows
        # rather than asked of the venue: this runs inside the ranker, and a
        # ranker that made network calls would put a fetch in front of a
        # slate.
        #
        # ANY QUOTE COUNTS -- RATIFIED 2026-09-09 (evening). The ruling said
        # "an open read at the venue" and that admitted two readings: strictly
        # `read_kind = 'open'`, or any venue quote for the game and market.
        # The strict one would rank a game INSIDE the near-start window as
        # unpriceable, because such a game has had its near-start read and may
        # have no opening one -- the questions closest to kickoff, the ones a
        # reader is most likely to act on, would sink. The operator ruled the
        # second reading. No `read_kind` filter here is therefore deliberate,
        # and removing that absence would reverse a ruling.
        f"      (SELECT 1 FROM venue_quotes v"
        f"        WHERE v.game_id = p.game_id AND v.market = p.market_type"
        f"        LIMIT 1) AS venue_lists_it"
        f" FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE {' AND '.join(where)}"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_ranks r"
        "                   WHERE r.prediction_id = p.id"
        "                     AND r.ranker_version = ?)"
        " ORDER BY p.id", params + [config.RANKER_VERSION]).fetchall()

    gate_count = _gate_lookup(conn)
    stamp = utcnow()
    scored: list[dict] = []
    for row in rows:
        counts["considered"] += 1
        confidence = confidence_score(row["model_prob"])
        completeness = completeness_score(row["factors_json"])
        edge = edge_score(row["model_prob"], row["implied_prob"])
        if edge is None:
            counts["no_line"] += 1
        settled = gate_count(row["sport"], row["market_type"], row["prop_type"],
                             row["predictor"])
        # THE GATE, AND IT IS THE WHOLE POINT. The edge is stored and shown
        # either way; it moves the ordering only once its own market has a
        # record to stand on.
        edge_counted = edge is not None and settled >= config.RANK_EDGE_GATE
        scored.append({
            "prediction_id": row["id"],
            "sport": row["sport"],
            "game_id": row["game_id"],
            "slate": (row["season"], row["week"]),
            "market_type": row["market_type"],
            "prop_type": row["prop_type"],
            "market_key": row["prop_type"] or row["market_type"],
            "rank_score": combine(confidence, completeness, edge,
                                  edge_counted=edge_counted),
            "confidence": confidence,
            "completeness": completeness,
            "edge": edge,
            "edge_counted": edge_counted,
            "edge_gate_n": settled,
            "factor_set_version": row["factor_set_version"],
            "created_utc": row["created_utc"],
            "standing": bool(row["is_standing"]),
            # PRICEABLE FIRST (2026-09-09). In memory only: what it decides is
            # already recorded, in `shortlist_place` under ranker version r3.
            "priceable": bool(row["venue_lists_it"]),
        })

    # THE SELECTION IS DECIDED HERE, ONCE, AND STORED ON THE ROW. A shortlist
    # recomputed later under a changed cap is not the list anybody was shown,
    # and the comparison that scores the ranker has to read the one that was.
    # Slates are selected apart: two days of baseball never compete for one cap.
    places: dict[int, int] = {}
    for (sport, _slate), group in _by_slate(scored).items():
        standing = [e for e in group if e["standing"]]
        for place, pid in enumerate(select(sport, standing)):
            places[pid] = place

    for entry in scored:
        place = places.get(entry["prediction_id"])
        conn.execute(
            "INSERT INTO prediction_ranks (prediction_id, ranker_version, sport,"
            " market_type, prop_type, rank_score, confidence, completeness, edge,"
            " edge_counted, edge_gate_n, factor_set_version, on_shortlist,"
            " shortlist_place, backfilled, created_utc)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (entry["prediction_id"], config.RANKER_VERSION, entry["sport"],
             entry["market_type"], entry["prop_type"], entry["rank_score"],
             entry["confidence"], entry["completeness"], entry["edge"],
             1 if entry["edge_counted"] else 0, entry["edge_gate_n"],
             entry["factor_set_version"], 1 if place is not None else 0, place,
             1 if backfilled else 0,
             max(stamp, just_after(entry["created_utc"]))))
        counts["ranked"] += 1
        counts["edge_counted"] += 1 if entry["edge_counted"] else 0
        counts["shortlisted"] += 1 if place is not None else 0
    conn.commit()
    return counts


def _standing_clause() -> str:
    """The record's own one-row-per-question rule, as a subquery condition.

    ONE DOOR. `calibration.standing_row_clause` is the rule the whole record
    counts by; importing it here rather than writing a second version is what
    keeps the shortlist and the record from disagreeing about which forecast
    of a question is the one that stands.
    """
    from . import calibration

    return calibration.standing_row_clause(same_set=False)


def _by_slate(scored: list[dict]) -> dict:
    """The batch split into the slates it belongs to.

    A cap is per slate. Ranking several days in one call -- which the backfill
    does -- must not let one day crowd another off its own list.
    """
    groups: dict[tuple, list[dict]] = {}
    for entry in scored:
        groups.setdefault((entry["sport"], entry["slate"]), []).append(entry)
    return groups


def _fill(group: list[dict], chosen: list[int], per_game: dict[str, int],
          cap: int) -> None:
    """Take from one group until the cap is reached, by the declared rules.

    THE ROUND ROBIN AND THE PER-GAME CEILING, exactly as they were. `chosen`
    and `per_game` are threaded through so a game's ceiling spans the groups:
    a fixture cannot take a fourth place by being priceable for three of them.
    """
    queues: dict[str, list[dict]] = {}
    for entry in group:
        queues.setdefault(entry["market_key"], []).append(entry)
    kinds = list(queues)
    while len(chosen) < cap and any(queues[k] for k in kinds):
        for kind in kinds:
            if len(chosen) >= cap:
                break
            queue = queues[kind]
            while queue:
                entry = queue.pop(0)
                game = entry.get("game_id")
                if per_game.get(game, 0) >= config.SHORTLIST_PER_GAME:
                    continue
                chosen.append(entry["prediction_id"])
                per_game[game] = per_game.get(game, 0) + 1
                break


def select(sport: str, scored: list[dict]) -> list[int]:
    """Which questions lead one slate, in order.

    FOUR RULES NOW, ALL DECLARED, NONE ABOUT THE ANSWER: the sport's cap, or
    the whole slate where it declares none -- a fight card is already a
    shortlist; a ceiling per game, so one marquee fixture cannot fill the
    list; a round robin across kinds of question, so the list is never twenty
    of the same market with the rest of the slate invisible behind them; and,
    from 2026-09-09 by operator ruling, PRICEABLE FIRST.

    PRICEABLE FIRST is not a change to the formula. r2's score, r2's weights
    and r2's tie-breaks decide the order inside each group; what the ruling
    adds is that the group the venue lists is emptied before the group it does
    not. `config.PRICEABLE_FIRST_FROM` carries the date, and the ranker
    version moved to r3 with it, because the LIST changes and a list that
    changed under an unchanged version is a measurement rewritten after the
    fact.

    THE REASON, from the ruling: the app's job is recommendations, and a
    question the venue does not list cannot become one. A slate of thirty that
    excluded the three priceable questions on the night's only game while
    carrying twenty unpriceable props was ranked against its own purpose.

    AND THERE IS NO IMMINENCE TERM -- RULED 2026-09-09 (evening), asked and
    answered so it is not asked again. The slate is the WEEK's, and a question
    on a game six days out competes with one on a game tonight on score alone.
    On the night this shipped that put "New England covers +3.5" 23rd of 48
    NFL spreads and off a list that takes fifteen, while the same game's
    moneyline made place 17. THAT IS THE CAP WORKING. Adding kickoff proximity
    to the ordering is a fifth rule; it was put to the operator and refused.
    """
    ordered = sorted(scored, key=lambda e: (-e["rank_score"], e["prediction_id"]))
    cap = config.shortlist_cap(sport)
    if cap is None or len(ordered) <= cap:
        return [e["prediction_id"] for e in ordered]

    chosen: list[int] = []
    per_game: dict[str, int] = {}
    # THE ONLY LINE THE RULING ADDS: two passes instead of one.
    _fill([e for e in ordered if e.get("priceable")], chosen, per_game, cap)
    _fill([e for e in ordered if not e.get("priceable")], chosen, per_game, cap)
    return chosen


def ranks_for(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict[int, sqlite3.Row]:
    """The current ranker's row per prediction, for a slate's worth of ids."""
    if not prediction_ids:
        return {}
    placeholders = ",".join("?" for _ in prediction_ids)
    return {
        r["prediction_id"]: r
        for r in conn.execute(
            f"SELECT * FROM prediction_ranks WHERE ranker_version = ?"
            f" AND prediction_id IN ({placeholders})",
            [config.RANKER_VERSION] + list(prediction_ids))
    }


def choose(conn: sqlite3.Connection, sport: str,
           prediction_ids: list[int]) -> dict:
    """What led this slate, as recorded when the ranks were written.

    A READ, NOT A DECISION. The cap, the ceiling and the round robin were
    applied once, at write time, and stored on the rows. Recomputing them here
    would mean a later change to a cap silently rewrote what a reader was shown
    last week, and the comparison that scores the ranker would then be scoring
    a shortlist nobody ever saw. Rows with no rank -- everything written before
    the ranker existed -- come back whole and say so.
    """
    ranks = ranks_for(conn, prediction_ids)
    if not ranks:
        return {"shortlist": list(prediction_ids), "rest": [], "cap": None,
                "ranked": False}
    on = [r for r in ranks.values() if r["on_shortlist"]]
    off = [r for r in ranks.values() if not r["on_shortlist"]]
    on.sort(key=lambda r: (r["shortlist_place"]
                           if r["shortlist_place"] is not None else 1_000_000,
                           -r["rank_score"]))
    off.sort(key=lambda r: (-r["rank_score"], r["prediction_id"]))
    unranked = [pid for pid in prediction_ids if pid not in ranks]
    return {
        "shortlist": [r["prediction_id"] for r in on] + unranked,
        "rest": [r["prediction_id"] for r in off],
        "cap": config.shortlist_cap(sport),
        "ranked": True,
    }
