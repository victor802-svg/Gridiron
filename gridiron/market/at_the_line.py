"""The frozen distribution, read at the venue's number (AT_THE_LINE E4).

**Arithmetic on a blind artifact, not a second prediction.** Every game
prediction carries a margin or total distribution written inside the blind
window and frozen with its row (E3). This module reads that distribution at a
number the venue published afterwards, and records the pair -- what the model
says about a proposition, and what the venue's price says about the same
proposition -- as a claim of its own kind.

Three properties hold it in place, and each one is in the schema rather than in
this docstring:

  * The claim is stamped after the prediction and after the quote. A row that
    could be read as blind is refused by a trigger.
  * The claim needs the frozen distribution; a prediction without one gets no
    claim, and the hole is counted by name rather than filled with a guess.
  * ONE FIXED PROPOSITION, NEVER A CHOSEN SIDE. A spread claim is always about
    the home side covering the venue's number, a total claim always about the
    over. The record holds two probabilities for the same question and stops
    there. It does not hold a side to take, which is what LAW 5 forbids.

WHICH RUNG OF THE LADDER. A venue quotes a ladder -- twenty-five strikes on one
game -- and one of them is what a reader means by "the line": the strike priced
nearest a coin flip. That is the rung this reads, declared here and dated,
because picking the strike where the model looks best would be choosing the
comparison after seeing the answer, which is the same error as fitting a factor
to the data it will be scored on.
"""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from ..db import utcnow

#: The venue whose ladder is read. One venue today; the column carries the name
#: on every row so a second one never merges into the first.
VENUE = "kalshi"

RUNG_CHOICE_DECLARED = "2026-09-06T00:00:00Z"
RUNG_CHOICE_RATIONALE = (
    "The strike priced nearest an even chance is the venue's own line -- the "
    "number a reader means by 'the line'. Declared before any claim was "
    "written, because choosing the rung where the model looks best would be "
    "choosing the comparison after seeing the answer."
)

PRICE_BASIS_MID = "the midpoint of the venue's yes bid and ask"
PRICE_BASIS_LAST = "the venue's last traded price, with no two-sided quote up"

#: A probability is stored strictly inside (0, 1): the schema says so, and a
#: normal tail rounds to zero long before the event becomes impossible.
_FLOOR = 0.0001
_CEIL = 0.9999

#: The three game markets a claim can be made in, and the proposition each one
#: is always about.
CLAIM_SIDE = {"spread": "home", "moneyline": "home", "total": "over",
              # A PROP IS AN OVER, always. The venue's contract is "more than
              # this many", and the claim is about that proposition whichever
              # side the model took.
              "prop": "over"}


def normal_cdf(z: float) -> float:
    """The standard normal's cumulative probability, from the error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def model_probability(quantity: str, mean: float, sd: float,
                      line: float | None) -> float | None:
    """The frozen distribution's answer to the venue's question.

    `home_margin` at a line of -6.5: the chance the home margin clears 6.5.
    `total` at 47.5: the chance the combined score goes over it. `home_win`:
    the chance the margin is positive at all. A line the shape does not need,
    or a spread with no line, answers None rather than something.
    """
    if sd is None or sd <= 0 or mean is None:
        return None
    if quantity == "home_win":
        z = mean / sd
    elif quantity == "home_margin":
        if line is None:
            return None
        # home covers L  <=>  margin + L > 0  <=>  margin > -L
        z = (mean + line) / sd
    elif quantity == "total":
        if line is None:
            return None
        z = (mean - line) / sd
    else:
        return None
    return min(_CEIL, max(_FLOOR, normal_cdf(z)))


def _price(quote: sqlite3.Row) -> tuple[float, str] | None:
    """The venue's price for its own yes side, and what that price is."""
    bid, ask = quote["yes_bid"], quote["yes_ask"]
    if bid is not None and ask is not None and 0 < (bid + ask) / 2 < 1:
        return (bid + ask) / 2, PRICE_BASIS_MID
    last = quote["last_price"]
    if last is not None and 0 < last < 1:
        return last, PRICE_BASIS_LAST
    return None


def rung_for(quotes: list[sqlite3.Row]) -> dict | None:
    """The venue's own line out of one look at one ladder.

    Returns the quote, the price the venue showed, and that price read as a
    probability for OUR fixed proposition -- the home side, or the over. A
    strike quoted from the away side answers the complementary question, so
    its price is complemented too; the stored line is already written from the
    home side's view, which is what makes that a subtraction and not a guess.
    """
    best = None
    for quote in quotes:
        priced = _price(quote)
        if priced is None:
            continue
        price, basis = priced
        implied = price if quote["yes_side"] in ("home", "over") else 1.0 - price
        if not 0 < implied < 1:
            continue
        distance = abs(implied - 0.5)
        if best is None or distance < best["distance"]:
            best = {"quote": quote, "price": round(price, 6),
                    "implied": round(implied, 6), "basis": basis,
                    "distance": distance}
    return best


def home_view_line(quote) -> float | None:
    """The venue's number as the CLAIM's fixed proposition sees it.

    A LATENT SIGN ERROR, FOUND BEFORE THE FIRST CLAIM WAS EVER WRITTEN.
    `rung_for` says "the stored line is already written from the home side's
    view", and it is not: `kalshi.parse_markets` stores the home strike for a
    home row and the AWAY strike for an away row, which are opposite numbers.
    The price was already being complemented for an away row; the line was
    not, so a claim built from one would have integrated the distribution at
    +3.5 while pricing -3.5.

    Nothing had ever been written through this path, so nothing in the record
    is wrong. It would have been wrong on the first row.
    """
    if quote["line"] is None:
        return None
    return (float(quote["line"]) if quote["yes_side"] in ("home", "over")
            else -float(quote["line"]))


#: The claim table as it stands after AT_THE_PRICE. A database built before
#: 2026-09-07 has the narrow one: no `shape`, NOT NULL distribution columns,
#: and CHECKs that admit neither a prop nor a count.
CLAIM_COLUMNS_NOW = ("id", "prediction_id", "quote_id", "venue", "sport",
                     "game_id", "market", "quantity", "line", "side", "shape",
                     "dist_mean", "dist_sd", "model_prob", "venue_price",
                     "venue_implied", "price_basis", "created_utc",
                     "resolved_utc", "outcome")


def ensure_claim_shape(conn: sqlite3.Connection) -> bool:
    """Widen `at_the_line_claims` on a database built before shapes existed.

    A VERIFIED COPY, like `db.widen_notification_states`, and for the same
    reason: SQLite applies a CHECK at CREATE and never revisits it, so a
    database made under the narrow definition refuses every prop claim and
    every claim with no distribution -- which is three of the four shapes.

    The row count is checked before the original is dropped. The last rebuild
    this project did left 311,655 rows in a table nobody wanted when a foreign
    key tripped after the copy.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='at_the_line_claims'").fetchone()
    if row is None or "shape" in (row[0] or ""):
        return False

    before = conn.execute("SELECT COUNT(*) FROM at_the_line_claims").fetchone()[0]
    schema = (Path(__file__).resolve().parent.parent / "schema.sql").read_text(
        encoding="utf-8")
    start = schema.index("CREATE TABLE IF NOT EXISTS at_the_line_claims")
    create = schema[start:schema.index(");", start) + 2].replace(
        "at_the_line_claims", "at_the_line_claims_wide", 1)

    conn.executescript("PRAGMA foreign_keys=OFF;")
    conn.executescript(create)
    # EVERY EXISTING ROW IS A MARGIN CLAIM. Nothing else could be written: the
    # old trigger refused a claim whose prediction had no margin distribution,
    # so a row that exists is a row that had one.
    conn.execute(
        "INSERT INTO at_the_line_claims_wide (id, prediction_id, quote_id,"
        " venue, sport, game_id, market, quantity, line, side, shape,"
        " dist_mean, dist_sd, model_prob, venue_price, venue_implied,"
        " price_basis, created_utc, resolved_utc, outcome)"
        " SELECT id, prediction_id, quote_id, venue, sport, game_id, market,"
        " quantity, line, side, 'rung_differs_margin', dist_mean, dist_sd,"
        " model_prob, venue_price, venue_implied, price_basis, created_utc,"
        " resolved_utc, outcome FROM at_the_line_claims")
    after = conn.execute(
        "SELECT COUNT(*) FROM at_the_line_claims_wide").fetchone()[0]
    if after != before:
        conn.execute("DROP TABLE at_the_line_claims_wide")
        conn.commit()
        raise RuntimeError(
            f"the claim table's widening copied {after} of {before} rows, so "
            f"nothing was dropped and nothing changed")
    _drop_dependent_triggers(conn, "at_the_line_claims")
    conn.executescript(
        "DROP TABLE at_the_line_claims;"
        " ALTER TABLE at_the_line_claims_wide RENAME TO at_the_line_claims;")
    conn.commit()
    conn.executescript("PRAGMA foreign_keys=ON;")
    ensure_claim_guards(conn)
    return True


def _drop_dependent_triggers(conn: sqlite3.Connection, table: str) -> list[str]:
    """Every trigger whose body names `table`, dropped so a rename can happen.

    SQLITE CHECKS TRIGGER BODIES ON RENAME. A claim trigger names
    `venue_quotes`, so renaming the widened copy into place fails while it
    stands -- and fails after the original has been dropped. They are restored
    from `schema.sql` immediately afterwards, by name, so nothing depends on
    what this returns.
    """
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        "   AND (sql LIKE ? OR tbl_name = ?)",
        (f"%{table}%", table)).fetchall()
    for row in rows:
        conn.execute(f"DROP TRIGGER IF EXISTS {row['name']}")
    conn.commit()
    return [row["name"] for row in rows]


def ensure_read_kind(conn: sqlite3.Connection) -> bool:
    """Let `venue_quotes` say which look it was, on an older database.

    A PLAIN ADD COLUMN, not a rebuild. The change is additive and the default
    is `'near_start'`, which is what every existing row actually is: until
    2026-09-09 the near-start pass was the only thing that ever read the
    venue. Backfilling them as opening reads would have made the claim guard
    fail on true history.
    """
    columns = {r[1] for r in conn.execute("PRAGMA table_info(venue_quotes)")}
    if not columns or "read_kind" in columns:
        return False
    conn.execute(
        "ALTER TABLE venue_quotes ADD COLUMN read_kind TEXT NOT NULL"
        " DEFAULT 'near_start'"
        " CHECK (read_kind IN ('open', 'near_start'))")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS venue_quotes_kind"
        " ON venue_quotes (game_id, market, read_kind, fetched_utc)")
    conn.commit()
    return True


def ensure_quote_shapes(conn: sqlite3.Connection) -> bool:
    """Let `venue_quotes` hold a prop, on a database built before shapes.

    Same verified rebuild as `ensure_claim_shape`, and needed for the same
    reason: SQLite applies a CHECK at CREATE and never revisits it, so a
    database made under the narrow definition cannot store the quote the
    count shape reads.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='venue_quotes'").fetchone()
    if row is None or "'prop'" in (row[0] or ""):
        return False

    before = conn.execute("SELECT COUNT(*) FROM venue_quotes").fetchone()[0]
    schema = (Path(__file__).resolve().parent.parent / "schema.sql").read_text(
        encoding="utf-8")
    start = schema.index("CREATE TABLE IF NOT EXISTS venue_quotes")
    create = schema[start:schema.index(");", start) + 2].replace(
        "venue_quotes", "venue_quotes_wide", 1)
    columns = [r[1] for r in conn.execute("PRAGMA table_info(venue_quotes)")]
    names = ", ".join(columns)

    conn.executescript("PRAGMA foreign_keys=OFF;")
    conn.executescript(create)
    conn.execute(f"INSERT INTO venue_quotes_wide ({names})"
                 f" SELECT {names} FROM venue_quotes")
    after = conn.execute("SELECT COUNT(*) FROM venue_quotes_wide").fetchone()[0]
    if after != before:
        conn.execute("DROP TABLE venue_quotes_wide")
        conn.commit()
        raise RuntimeError(
            f"the quote table's widening copied {after} of {before} rows, so "
            f"nothing was dropped and nothing changed")
    _drop_dependent_triggers(conn, "venue_quotes")
    conn.executescript(
        "DROP TABLE venue_quotes;"
        " ALTER TABLE venue_quotes_wide RENAME TO venue_quotes;")
    conn.commit()
    conn.executescript("PRAGMA foreign_keys=ON;")
    for statement in _schema_statements(schema, "venue_quotes"):
        conn.execute(statement)
    conn.commit()
    # THE CLAIM TABLE'S GUARDS NAME THIS TABLE, so they went with the rename.
    ensure_claim_guards(conn)
    return True


def ensure_claim_guards(conn: sqlite3.Connection) -> list[str]:
    """Re-declare the claim table's indexes and triggers. Idempotent.

    UNCONDITIONAL, AND THAT IS THE POINT. The first run of the widening
    dropped the old table, renamed the new one, and then died restoring the
    triggers -- leaving a claim table with no append-only guard on it, which
    is the worst place a migration can stop. Every path now ends here, and
    every statement is IF NOT EXISTS, so an interrupted rebuild heals on the
    next call rather than looking finished.
    """
    schema = (Path(__file__).resolve().parent.parent / "schema.sql").read_text(
        encoding="utf-8")
    applied = []
    for statement in _schema_statements(schema, "at_the_line_claims"):
        conn.execute(statement)
        applied.append(statement.split(chr(10))[0][:60])
    conn.commit()
    return applied


def _schema_statements(schema: str, table: str) -> list[str]:
    """Every index and trigger the schema declares for one table.

    A TRIGGER BODY HOLDS STATEMENTS OF ITS OWN, so splitting the file on ";"
    cuts one into three fragments and none of them parses. This reads a
    trigger through to its own `END;`.
    """
    out = []
    text = schema
    at = 0
    while True:
        start = min((i for i in (text.find("CREATE INDEX", at),
                                 text.find("CREATE TRIGGER", at)) if i >= 0),
                    default=-1)
        if start < 0:
            break
        if text.startswith("CREATE TRIGGER", start):
            end = text.find("END;", start)
            end = len(text) if end < 0 else end + len("END;")
        else:
            end = text.find(";", start)
            end = len(text) if end < 0 else end + 1
        statement = text[start:end].strip()
        at = end
        if table in statement:
            out.append(statement)
    return out


def _looks(conn: sqlite3.Connection, game_id: str, market: str) -> list[list[sqlite3.Row]]:
    """One ladder per look, oldest first."""
    # NEAR-START ONLY (GRIDIRON_OPENING_READ, 2026-09-09). The opening read
    # is a daily look at a market that may be a week from closing; a claim
    # priced off it would be a claim about a price nobody could still take by
    # kickoff, scored against an outcome. The guard says so by name.
    columns = {r[1] for r in conn.execute("PRAGMA table_info(venue_quotes)")}
    if "read_kind" in columns:
        rows = conn.execute(
            "SELECT * FROM venue_quotes"
            " WHERE game_id = ? AND market = ? AND venue = ?"
            "   AND read_kind = 'near_start'"
            " ORDER BY fetched_utc, line",
            (game_id, market, VENUE)).fetchall()
    else:
        # A DATABASE FROM BEFORE THE OPENING READ. Every row in it came from
        # the near-start pass, because that was the only thing that ever read
        # the venue -- so there is nothing to exclude, and no filter to apply.
        rows = conn.execute(
            "SELECT * FROM venue_quotes"
            " WHERE game_id = ? AND market = ? AND venue = ?"
            " ORDER BY fetched_utc, line",
            (game_id, market, VENUE)).fetchall()
    looks: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        looks.setdefault(row["fetched_utc"], []).append(row)
    return [looks[stamp] for stamp in sorted(looks)]


def claim_probability(prediction, game, quote, shape: str,
                      home_line: float | None, dist: dict | None) -> dict:
    """The model's number for the VENUE's proposition, by shape.

    Each shape gets its own arithmetic and its own refusal. Nothing here falls
    back to another shape's method when its own inputs are missing: a claim
    assembled from whatever was to hand would sit in the table looking exactly
    like the others.
    """
    from ..model import counts
    from ..priced import shape as shapes

    quantity = quote["quantity"]
    if shape in (shapes.LINE_LESS, shapes.RUNG_MATCHED):
        got = shapes.blind_probability(prediction, game, quantity=quantity)
        if got["prob"] is None:
            return {"prob": None, "why": got["why"], "hole": "unmappable_side"}
        return {"prob": got["prob"], "why": got["why"], "dist": None}

    if shapes.needs_count_rate(shape):
        try:
            payload = json.loads(prediction["factors_json"]) or {}
        except ValueError:
            payload = {}
        rate = payload.get("expected_count")
        if rate is None:
            return {"prob": None, "hole": "no_blind_rate", "why": (
                "the count model's rate was not written with this prediction, "
                "and fitting one now would read a rate against a strike that "
                "was visible when it was fitted")}
        form, dispersion = counts.form_for(prediction["prop_type"])
        if not form:
            return {"prob": None, "hole": "no_declared_form", "why": (
                f"{prediction['prop_type']!r} has no declared count form, so "
                f"there is no distribution to read at the venue's strike")}
        return {"prob": counts.p_over(float(rate), float(home_line),
                                      form=form, dispersion=dispersion),
                "dist": None,
                "why": (f"the blind rate {float(rate):g} read at the venue's "
                        f"strike of {float(home_line):g}, as a {form}")}

    if shapes.needs_margin_distribution(shape):
        if not dist:
            return {"prob": None, "hole": "no_distribution", "why": (
                "the frozen margin distribution is not on this prediction")}
        prob = model_probability(quantity, dist.get("mean"), dist.get("sd"),
                                 home_line)
        if prob is None:
            return {"prob": None, "hole": "unusable_distribution", "why": (
                "the frozen distribution cannot be read at this number")}
        return {"prob": prob, "dist": dist, "why": (
            f"the frozen distribution read at {float(home_line):g}")}

    return {"prob": None, "hole": "unclassifiable", "why": "no shape"}


def evaluate(conn: sqlite3.Connection,
             prediction_ids: list[int] | None = None) -> dict:
    """Write a claim for every question whose shape the record can answer.

    FOUR SHAPES, EACH WITH ITS OWN INPUTS (AT_THE_PRICE, 2026-09-07). Until
    today this read a frozen margin distribution or counted a hole, so a
    winner contract -- where the blind probability IS the answer to the
    venue's question -- was refused for lacking something it does not use.
    The record held no claim at all as a result.

    Every hole is counted by its own name. A market that never gets a claim is
    a coverage fact, and a coverage fact that is silently zero is the failure
    this counting exists to prevent.
    """
    from ..priced import shape as shapes

    ensure_claim_shape(conn)
    ensure_quote_shapes(conn)
    ensure_read_kind(conn)
    counts_out = {"claims": 0, "already": 0, "no_distribution": 0,
                  "no_quotes": 0, "no_priced_rung": 0,
                  "unusable_distribution": 0, "predictions": 0,
                  "no_blind_rate": 0, "no_declared_form": 0,
                  "quote_after_first_pitch": 0, "game_under_way": 0,
                  "unmappable_side": 0, "unclassifiable": 0,
                  "line_presence_differs": 0,
                  "no_distribution_for_this_market": 0}
    for name in shapes.SHAPES:
        counts_out[name] = 0

    where = "p.market_type IN ('spread', 'total', 'moneyline', 'prop')"
    params: list = []
    if prediction_ids is not None:
        if not prediction_ids:
            return counts_out
        where += " AND p.id IN (%s)" % ",".join("?" for _ in prediction_ids)
        params = list(prediction_ids)
    rows = conn.execute(
        "SELECT p.id, p.sport, p.game_id, p.market_type, p.prop_type,"
        "       p.subject, p.line_asked, p.model_prob, p.model_side,"
        "       p.created_utc, p.factors_json, g.home, g.away, g.kickoff_utc,"
        "       g.status"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        f" WHERE {where} ORDER BY p.id", params).fetchall()

    for pred in rows:
        counts_out["predictions"] += 1
        # A GAME BEING PLAYED IS NOT A GAME TO CLAIM ABOUT. The status check
        # and the timestamp check are both here on purpose: a status is only
        # as fresh as the last refresh, and a kickoff time is a fact.
        if pred["status"] not in ("scheduled", "pre", None):
            counts_out["game_under_way"] += 1
            continue
        try:
            dist = (json.loads(pred["factors_json"]) or {}).get("margin_distribution")
        except ValueError:
            dist = None
        market = pred["market_type"]
        # A PROP IS QUOTED IN ITS OWN MARKET, and the venue's declared series
        # carry none today. The lookup is by the market name the quote table
        # uses, so a prop finds nothing and is counted as unquoted rather than
        # as a failure of this writer.
        looks = _looks(conn, pred["game_id"], market)
        if not looks:
            counts_out["no_quotes"] += 1
            continue
        priced = False
        for ladder in looks:
            best = rung_for(ladder)
            if best is None:
                continue
            priced = True
            quote = best["quote"]
            # NOT AGAINST A LIVE PRICE. A quote taken after first pitch is
            # priced off the game being played, and comparing it with a
            # pre-game probability is not a disagreement -- on the first live
            # run it produced a home side the model made 59.6% against a venue
            # price of 3.5%, which was the fourth inning. LAW 5 refuses to
            # size in-game one step later; this refuses to claim in-game.
            if pred["kickoff_utc"] and quote["fetched_utc"] >= pred["kickoff_utc"]:
                counts_out["quote_after_first_pitch"] += 1
                continue
            home_line = home_view_line(quote)
            classified = shapes.claim_shape(pred, home_line,
                                            quantity=quote["quantity"])
            if classified["shape"] is None:
                counts_out[classified["refused"]] = counts_out.get(
                    classified["refused"], 0) + 1
                continue
            got = claim_probability(pred, pred, quote, classified["shape"],
                                    home_line, dist)
            if got["prob"] is None:
                counts_out[got["hole"]] = counts_out.get(got["hole"], 0) + 1
                continue
            prob = min(max(got["prob"], _FLOOR), _CEIL)
            used = got.get("dist")
            stamp = max(utcnow(), quote["fetched_utc"])
            try:
                conn.execute(
                    "INSERT INTO at_the_line_claims (prediction_id, quote_id, venue,"
                    " sport, game_id, market, quantity, line, side, shape,"
                    " dist_mean, dist_sd, model_prob, venue_price, venue_implied,"
                    " price_basis, created_utc)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pred["id"], quote["id"], VENUE, pred["sport"], pred["game_id"],
                     market, quote["quantity"], home_line,
                     CLAIM_SIDE[market], classified["shape"],
                     round(float(used["mean"]), 4) if used else None,
                     round(float(used["sd"]), 4) if used else None,
                     round(prob, 6), best["price"], best["implied"], best["basis"],
                     stamp))
            except sqlite3.IntegrityError as exc:
                if "UNIQUE" not in str(exc):
                    raise
                counts_out["already"] += 1
                continue
            counts_out["claims"] += 1
            counts_out[classified["shape"]] += 1
        if not priced:
            counts_out["no_priced_rung"] += 1
        conn.commit()
    return counts_out


def standing_claims(conn: sqlite3.Connection, *, sport: str,
                    market: str) -> list[sqlite3.Row]:
    """ONE CLAIM PER PREDICTION: the last one written before the game started.

    The same rule the rung record uses for a superseded answer, for the same
    reason. A ladder read twice would otherwise put two correlated rows in one
    curve and call the sample twice the size it is.
    """
    return conn.execute(
        "SELECT c.* FROM at_the_line_claims c"
        " JOIN games g ON g.id = c.game_id"
        " WHERE c.sport = ? AND c.market = ?"
        "   AND c.created_utc = (SELECT MAX(c2.created_utc) FROM at_the_line_claims c2"
        "                        WHERE c2.prediction_id = c.prediction_id"
        "                          AND c2.created_utc < g.kickoff_utc)"
        " ORDER BY c.id", (sport, market)).fetchall()


def resolve_claims(conn: sqlite3.Connection) -> dict:
    """Settle every open claim whose game has finished.

    A level game leaves a winner-market claim open and says so: "did the home
    side win" has no answer on a draw, and the rung record voids those rather
    than inventing one. The count is reported so an open row is never mistaken
    for a missing one.
    """
    from ..model import questions

    counts = {"settled": 0, "unanswerable_level_game": 0, "still_open": 0}
    rows = conn.execute(
        "SELECT c.*, g.home_score, g.away_score FROM at_the_line_claims c"
        " JOIN games g ON g.id = c.game_id"
        " WHERE c.resolved_utc IS NULL AND g.status = 'final'"
        " ORDER BY c.id").fetchall()
    for claim in rows:
        home, away = claim["home_score"], claim["away_score"]
        if home is None or away is None:
            continue
        if claim["quantity"] == "home_margin":
            outcome = questions.spread_outcome(home, away, claim["line"])
        elif claim["quantity"] == "total":
            outcome = questions.total_outcome(home, away, claim["line"])
        else:
            if home == away:
                counts["unanswerable_level_game"] += 1
                continue
            outcome = 1 if home > away else 0
        cur = conn.execute(
            "UPDATE at_the_line_claims SET resolved_utc = ?, outcome = ?"
            " WHERE id = ? AND resolved_utc IS NULL",
            (utcnow(), outcome, claim["id"]))
        conn.commit()
        counts["settled"] += cur.rowcount
    counts["still_open"] = conn.execute(
        "SELECT COUNT(*) FROM at_the_line_claims WHERE resolved_utc IS NULL"
    ).fetchone()[0]
    return counts


def coverage(conn: sqlite3.Connection, *, sport: str) -> list[dict]:
    """Per market: how many predictions could be read at the venue's line, and
    the named reason for every one that could not.

    A share with no reasons beside it is a number that hides its own holes.
    """
    out = []
    for market in ("spread", "total", "moneyline"):
        rows = conn.execute(
            "SELECT p.id, p.factors_json,"
            "  (SELECT COUNT(*) FROM at_the_line_claims c WHERE c.prediction_id = p.id) AS claims,"
            "  (SELECT COUNT(*) FROM venue_quotes q WHERE q.game_id = p.game_id"
            "     AND q.market = p.market_type) AS quotes"
            " FROM predictions p WHERE p.sport = ? AND p.market_type = ?",
            (sport, market)).fetchall()
        if not rows:
            continue
        with_claim = sum(1 for r in rows if r["claims"])
        no_dist = sum(1 for r in rows if not r["claims"]
                      and '"margin_distribution"' not in (r["factors_json"] or ""))
        no_quotes = sum(1 for r in rows if not r["claims"] and not r["quotes"]
                        and '"margin_distribution"' in (r["factors_json"] or ""))
        rest = len(rows) - with_claim - no_dist - no_quotes
        out.append({
            "market": market,
            "n": len(rows),
            "with_a_claim": with_claim,
            "share": round(with_claim / len(rows), 4) if rows else None,
            "holes": [
                {"reason": "the prediction carries no frozen distribution",
                 "n": no_dist},
                {"reason": "the venue quoted nothing for the game", "n": no_quotes},
                {"reason": "the venue's ladder carried no usable price", "n": rest},
            ],
        })
    return out
