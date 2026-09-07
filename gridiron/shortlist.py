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
from datetime import datetime, timedelta, timezone

from . import config
from .db import utcnow


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
              "considered": 0}
    where = ["1 = 1"]
    params: list = []
    if prediction_ids is not None:
        if not prediction_ids:
            return counts
        where.append("p.id IN (%s)" % ",".join("?" for _ in prediction_ids))
        params.extend(prediction_ids)
    rows = conn.execute(
        "SELECT p.id, p.sport, p.market_type, p.prop_type, p.predictor,"
        " p.model_prob, p.factors_json, p.factor_set_version, p.created_utc,"
        " (SELECT s.implied_prob FROM market_snapshots s"
        "   WHERE s.prediction_id = p.id ORDER BY s.id LIMIT 1) AS implied_prob"
        f" FROM predictions p WHERE {' AND '.join(where)}"
        "   AND NOT EXISTS (SELECT 1 FROM prediction_ranks r"
        "                   WHERE r.prediction_id = p.id"
        "                     AND r.ranker_version = ?)"
        " ORDER BY p.id", params + [config.RANKER_VERSION]).fetchall()

    gate_count = _gate_lookup(conn)
    stamp = utcnow()
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
        score = combine(confidence, completeness, edge, edge_counted=edge_counted)
        conn.execute(
            "INSERT INTO prediction_ranks (prediction_id, ranker_version, sport,"
            " market_type, prop_type, rank_score, confidence, completeness, edge,"
            " edge_counted, edge_gate_n, factor_set_version, backfilled, created_utc)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (row["id"], config.RANKER_VERSION, row["sport"], row["market_type"],
             row["prop_type"], score, confidence, completeness, edge,
             1 if edge_counted else 0, settled, row["factor_set_version"],
             1 if backfilled else 0, max(stamp, _after(row["created_utc"]))))
        counts["ranked"] += 1
        counts["edge_counted"] += 1 if edge_counted else 0
    conn.commit()
    return counts


def _after(created_utc: str | None) -> str:
    """One second past a prediction's own stamp.

    The trigger refuses equality as well as precedence, and a rank written in
    the same second as the row it scores would be refused for looking like a
    blind rank, which it is not. This is only ever the larger of the two in a
    test that writes a prediction stamped in the future; in earnest the clock
    is well past it.
    """
    if not created_utc:
        return utcnow()
    try:
        when = datetime.strptime(created_utc, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return utcnow()
    return (when.replace(tzinfo=timezone.utc)
            + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _market_key(row) -> str:
    """What a reader would call the kind of question this is."""
    return row["prop_type"] or row["market_type"]


def choose(conn: sqlite3.Connection, sport: str,
           prediction_ids: list[int]) -> dict:
    """Which of a slate's questions lead it, and in what order.

    THREE RULES, ALL DECLARED, NONE OF THEM ABOUT THE ANSWER:

      * the cap for the sport (`config.SHORTLIST_CAPS`), or the whole slate
        where the sport declares none -- a fight card is already a shortlist;
      * a ceiling per game, so one marquee fixture cannot fill the list;
      * a round robin across kinds of question, so the list is never twenty of
        the same market with the rest of the slate invisible behind them.

    NOTHING IS DISCARDED. The rest comes back in rank order too, because the
    page shows it behind a control that carries its count, and a slate that
    quietly lost fifty questions would misrepresent the record.
    """
    ranks = ranks_for(conn, prediction_ids)
    if not ranks:
        return {"shortlist": list(prediction_ids), "rest": [], "cap": None,
                "ranked": False}
    games = {
        r["id"]: r["game_id"] for r in conn.execute(
            "SELECT id, game_id FROM predictions WHERE id IN (%s)"
            % ",".join("?" for _ in prediction_ids), list(prediction_ids))
    }
    ordered = sorted(
        (ranks[pid] for pid in prediction_ids if pid in ranks),
        key=lambda r: (-r["rank_score"], r["prediction_id"]))
    cap = config.shortlist_cap(sport)
    if cap is None or len(ordered) <= cap:
        chosen = [r["prediction_id"] for r in ordered]
        unranked = [pid for pid in prediction_ids if pid not in ranks]
        return {"shortlist": chosen + unranked, "rest": [], "cap": cap,
                "ranked": True}

    queues: dict[str, list] = {}
    for row in ordered:
        queues.setdefault(_market_key(row), []).append(row)

    chosen: list[int] = []
    per_game: dict[str, int] = {}
    passed_over: list[int] = []
    kinds = list(queues)
    while len(chosen) < cap and any(queues[k] for k in kinds):
        for kind in kinds:
            if len(chosen) >= cap:
                break
            queue = queues[kind]
            while queue:
                row = queue.pop(0)
                game = games.get(row["prediction_id"])
                if per_game.get(game, 0) >= config.SHORTLIST_PER_GAME:
                    passed_over.append(row["prediction_id"])
                    continue
                chosen.append(row["prediction_id"])
                per_game[game] = per_game.get(game, 0) + 1
                break

    taken = set(chosen)
    rest = [r["prediction_id"] for r in ordered if r["prediction_id"] not in taken]
    rest += [pid for pid in prediction_ids if pid not in ranks and pid not in taken]
    return {"shortlist": chosen, "rest": rest, "cap": cap, "ranked": True}
