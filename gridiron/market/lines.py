"""Step 5: the market, and only after the prediction row exists.

This module is the quarantine. It is the only code permitted to read
`market_lines_raw`, and nothing on the prediction path may import it — the guard
test walks the import closure, and `gridiron.blind` refuses to let this package
load at all while a prediction is being formed.

What arrives here is a prediction id. What is written is a `market_snapshots`
row hanging off it. The database refuses the insert if the prediction does not
exist or if the snapshot claims to predate it.
"""

from __future__ import annotations

from dataclasses import dataclass

import math
import json
import sqlite3

from .. import config
from ..db import utcnow
from . import sources

#: The bare `MARGIN_SD = 13.2` that stood here was REMOVED on 2026-08-29. It
#: was the module-wide default behind `MARGIN_SD_BY_SPORT.get(sport,
#: MARGIN_SD)`, so any sport without its own entry silently received
#: football's number - and MLB had no entry. Its replacement is `margin_sd()`,
#: which has no fallback and fails by name. What was assumed and what was
#: measured now sit side by side on each MarginSD as `assumed_before`.

SOURCE = "nflverse/schedules"
NO_PROP_MARKET = "unavailable:no-free-prop-line-source"
NO_SOURCE = "unavailable:no-free-line-source"

class UnmeasuredMarginSD(RuntimeError):
    """A scoring path reached for a margin SD that carries no measurement."""


@dataclass(frozen=True)
class MarginSD:
    """A measured standard deviation, with the evidence attached.

    Every field is required. A bare float is what this replaces, and a bare
    float is how NBA's market comparison came to be wrong for an entire day:
    11.5 was written down as "~11.5 across recent seasons", nobody could check
    it because there was nothing to check it against, and the true figure is
    13.95. Understating it by 21% made the market's implied probabilities far
    too confident on big spreads, inflated its Brier score, and produced a
    backtest in which the model appeared to BEAT the market by 14%.
    """

    sd: float
    n: int
    measured_utc: str
    source: str
    assumed_before: float | None = None


#: SD(actual home margin - market spread), measured per sport by
#: `tools/measure_margin_sd.py`, deduplicated by game id across every database
#: that holds lines for that sport. NEVER assumed again: the guard below refuses
#: any entry without a measurement date, so a plausible-looking number cannot be
#: typed in and used.
#:
#: MLB is measured from ESPN's run line. Gridiron asks no run-line question, so
#: nothing uses it today — it is recorded because the previous table had NO mlb
#: key at all, which meant an MLB caller would have silently received football's
#: number through a dict default.
MARGIN_SD_BY_SPORT: dict[str, MarginSD] = {
    "nfl": MarginSD(
        sd=12.70, n=2761, measured_utc="2026-08-29T20:51:30Z",
        source="nflverse closing lines, 1999-2025 completed games",
        assumed_before=13.2,
    ),
    "mlb": MarginSD(
        sd=4.71, n=2110, measured_utc="2026-08-29T20:51:30Z",
        source="ESPN run line, 2025 season plus live fetches",
        assumed_before=None,   # there was no entry; the default would have applied
    ),
    "nba": MarginSD(
        sd=13.95, n=1191, measured_utc="2026-08-29T20:51:30Z",
        source="ESPN spread, 2025-26 season",
        assumed_before=11.5,
    ),
    # COLLEGE FOOTBALL IS 77% WIDER THAN THE NFL, which is the single most
    # consequential number the probe produced: a market comparison drawn with
    # football's 12.70 would make every college line look far more confident
    # than it is, and would inflate the market's Brier score the way NBA's
    # understated SD once did. Measured before anything used it.
    "cfb": MarginSD(
        sd=22.46, n=260, measured_utc="2026-08-31T00:00:00Z",
        source=("ESPN final scores, random sample of 260 of the 888 completed "
                "2025 FBS regular-season games"),
        assumed_before=None,   # nothing was assumed; the probe came first
    ),
}


@dataclass(frozen=True)
class TotalSD:
    """The spread of actual combined scores about a published total.

    ITS OWN CONSTANT, not a reuse of the margin SD, because it measures a
    different quantity: how far a game's TOTAL POINTS land from the number the
    market set. Borrowing the margin figure would be the same mistake as
    borrowing football's SD for basketball -- a plausible number, used with
    confidence, describing something else.
    """

    sd: float
    n: int
    measured_utc: str
    source: str


TOTAL_SD_BY_SPORT: dict[str, TotalSD] = {
    "cfb": TotalSD(
        sd=16.19, n=260, measured_utc="2026-08-31T00:00:00Z",
        source=("ESPN final scores, random sample of 260 of the 888 completed "
                "2025 FBS regular-season games; mean total 53.82"),
    ),
}


def total_sd(sport: str) -> float:
    """The measured total-points SD, or a NAMED failure. No fallback, ever."""
    entry = TOTAL_SD_BY_SPORT.get(sport)
    if entry is None:
        raise UnmeasuredMarginSD(
            f"no total-points SD has been measured for {sport!r}. A totals "
            "market cannot be compared with the market without one, and the "
            "margin SD is not a substitute: it measures a different quantity."
        )
    return entry.sd


def margin_sd(sport: str) -> float:
    """The measured SD for a sport, or a NAMED failure.

    There is deliberately no fallback. The old code did `.get(sport, MARGIN_SD)`,
    so a sport with no entry quietly received football's number and every
    probability derived from it was wrong in a way nothing would ever print.
    """
    entry = MARGIN_SD_BY_SPORT.get(sport)
    if entry is None:
        raise UnmeasuredMarginSD(
            f"no margin SD has been measured for {sport!r}. Run "
            "tools/measure_margin_sd.py and add a dated entry; do not guess one. "
            "A margin SD sets how confident the market is made to look, so an "
            "invented value silently rewrites the comparison this project exists "
            "to make."
        )
    if not entry.measured_utc or not entry.n:
        raise UnmeasuredMarginSD(
            f"the margin SD for {sport!r} carries no measurement date or sample "
            "size, so it is an assumption wearing a measurement's clothes."
        )
    return entry.sd


def market_availability(sport: str, market: str) -> dict:
    """Whether THIS market has a line, and the stated reason when it does not."""
    return sources.for_market(sport, market)


def line_source_for(sport: str) -> dict:
    """What this sport's market comparison is drawn from, or why there is none."""
    return sources.for_sport(sport)


def american_to_probability(price: int) -> float:
    """A moneyline price as an implied probability, vig included.

    The vig is NOT removed. Removing it requires assuming how the book split its
    margin between the two sides, and that assumption would be ours rather than
    the market's. Both sides are converted the same way and the pair sums to
    slightly more than one, which is the honest shape of a posted price.
    """
    if price < 0:
        return (-price) / ((-price) + 100.0)
    return 100.0 / (price + 100.0)


def devig_pair(home_price: int, away_price: int) -> tuple[float, float]:
    """The two implied probabilities, normalised to sum to one.

    Stated plainly because it IS an assumption: this is proportional de-vigging,
    which assumes the book loaded its margin evenly across both sides. It is the
    standard choice and it is not the only defensible one. The raw pair is kept
    alongside so a reader can see how much was removed.
    """
    home = american_to_probability(home_price)
    away = american_to_probability(away_price)
    total = home + away
    if total <= 0:
        return 0.5, 0.5
    return home / total, away / total


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def implied_cover_probability(
    market_spread: float, line_asked: float, sport: str = "nfl"
) -> float:
    """P(home covers `line_asked`), as implied by the market's spread.

    `spread_line` is stated as the expected home margin, so a home side favoured
    by three is +3. Our question asks whether the home margin plus `line_asked`
    exceeds zero, which under a normal margin is
    Phi((expected_margin + line_asked) / sd).
    """
    return norm_cdf((market_spread + line_asked) / margin_sd(sport))


def implied_over_probability(
    market_total: float, line_asked: float, sport: str
) -> float:
    """P(the combined score goes OVER `line_asked`), implied by the market total.

    The same normal argument as the spread, about a different quantity and with
    its own measured SD. `total_sd` has no fallback for exactly the reason
    `margin_sd` has none: reusing the margin figure here would be a plausible
    number describing something else, which is how NBA's market comparison was
    wrong for a day.

    The market's total is the expected combined score, so the question "does it
    exceed the number WE asked at" is Phi((their number - ours) / sd).
    """
    return norm_cdf((market_total - line_asked) / total_sd(sport))


def raw_line(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM market_lines_raw WHERE game_id = ?", (game_id,)
    ).fetchone()


def public_percentage(conn: sqlite3.Connection, game_id: str) -> float | None:
    """Always None, deliberately.

    No free source publishes ticket-count betting percentages with an API and a
    licence we can rely on (checked 2026-08-28). The column stays, the factor
    stays declared and inactive, and this returns nothing rather than a proxy
    that would be labelled "public" while measuring something else.
    """
    return None


def snapshot_prediction(conn: sqlite3.Connection, prediction_id: int, *,
                        kind: str = "open_at_predict") -> dict | None:
    """Attach the market to one already-written prediction.

    Idempotent: a prediction keeps its first snapshot. Re-running a slate does
    not append a second look at a line that has since moved, because the record
    is of what the market said when the prediction was made.

    Where no source exists for the sport or the market, a snapshot is still
    written — carrying NULLs and a source string naming the absence. That is
    deliberate: "we looked and there was nothing" is a different fact from "we
    never looked", and the interface shows the first as a missing comparison
    rather than as a missing prediction.
    """
    ensure_snapshot_columns(conn)
    pred = conn.execute(
        # `factors_json` carries the question, and the question carries the
        # subject's id -- which is what a prop quote has to be looked up by.
        # `subject` is the human string and cannot be matched on.
        "SELECT id, sport, game_id, market_type, prop_type, line_asked,"
        " model_side, factors_json FROM predictions WHERE id = ?",
        (prediction_id,),
    ).fetchone()
    if pred is None:
        raise KeyError(f"no prediction {prediction_id}")

    existing = conn.execute(
        "SELECT * FROM market_snapshots WHERE prediction_id = ? AND kind = ?"
        " ORDER BY id LIMIT 1",
        (prediction_id, kind),
    ).fetchone()
    if existing is not None:
        return dict(existing)

    sport = pred["sport"]
    market = pred["prop_type"] or pred["market_type"]
    availability = sources.for_market(sport, market)

    def write(source: str, line, implied) -> dict:
        cur = conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line,"
            " implied_prob, public_pct, kind) VALUES (?,?,?,?,?,?,?)",
            (prediction_id, utcnow(), source, line, implied,
             public_percentage(conn, pred["game_id"]), kind),
        )
        conn.commit()
        return {"id": cur.lastrowid, "source": source, "line": line,
                "implied_prob": implied, "public_pct": None}

    if not availability["available"]:
        return write(
            NO_PROP_MARKET if market in sources.NO_LINE_MARKETS else NO_SOURCE,
            None, None,
        )

    if pred["market_type"] == "prop":
        return _snapshot_prop(conn, pred, write)

    row = raw_line(conn, pred["game_id"])
    if row is None:
        return None

    if pred["market_type"] == "moneyline":
        if row["home_moneyline"] is None or row["away_moneyline"] is None:
            return None
        home_p, away_p = devig_pair(row["home_moneyline"], row["away_moneyline"])
        # `subject` names the side; model_side is 'win' or 'lose' for that side.
        implied_home = home_p
        implied = implied_home if pred["model_side"] == "win" else 1.0 - implied_home
        return write(row["source"], float(row["home_moneyline"]), round(implied, 6))

    if pred["market_type"] == "total":
        # A TOTALS COMPARISON USES THE TOTALS SD, never the margin one. They
        # measure different quantities and the wrong one would make the market
        # look far more or less certain than it is.
        if row["total_line"] is None:
            return None
        implied_yes = implied_over_probability(
            row["total_line"], pred["line_asked"], sport)
        implied = implied_yes if pred["model_side"] == "over" else 1.0 - implied_yes
        return write(row["source"], row["total_line"], round(implied, 6))

    if row["spread_line"] is None:
        return None
    implied_yes = implied_cover_probability(row["spread_line"], pred["line_asked"], sport)
    implied = implied_yes if pred["model_side"] == "cover" else 1.0 - implied_yes
    return write(row["source"], row["spread_line"], round(implied, 6))


#: Why a prop got no comparison. Each is a DIFFERENT fact and they are recorded
#: differently on purpose: "nobody published a price", "a price exists but we
#: cannot tell whose it is", "a price exists for this player but at a different
#: rung", and "a price exists at this rung but its side could not be derived".
#: Collapsing them into one "no line" would hide which part of the chain broke.
NO_PROP_CROSSWALK = "unavailable:player-matched-to-nobody-in-the-odds-feed"
#: He was never in the crosswalk to begin with, because the odds feed published
#: no prop about him at all on this slate. DIFFERENT from a refusal: nothing was
#: ambiguous and nothing failed -- there was simply nothing to match against, so
#: recording it as a matching failure would blame the bridge for the absence of
#: the thing on the far side of it.
NO_PROP_SUBJECT_QUOTED = "unavailable:no-prop-published-for-this-player"
NO_PROP_AT_RUNG = "unavailable:no-quote-at-the-rung-asked"
#: The market is published one-sided -- a milestone with no other half -- and we
#: stated the side it does not carry. The complement is NOT computed: a vigged
#: price does not have an honest complement, so 1 - P(over) would understate the
#: under by the book's whole margin and the comparison would be against a number
#: nobody quoted.
NO_PROP_THIS_SIDE = "unavailable:market-is-one-sided-and-we-took-the-other"


def _snapshot_prop(conn: sqlite3.Connection, pred: sqlite3.Row, write) -> dict:
    """Attach a published prop quote to one prediction, or record why not.

    The quote must be for exactly the question asked: same game, same market,
    same rung, same side. A price at a neighbouring rung is a different question
    and is not a substitute -- that substitution is how a comparison ends up
    looking rigorous and measuring something else.
    """
    from . import props

    payload = json.loads(pred["factors_json"])
    question = payload.get("question") or {}
    subject_id = question.get("player_id")
    if not subject_id:
        return write(NO_SOURCE, None, None)

    espn_id = props.espn_id_for(conn, pred["sport"], int(subject_id))
    if espn_id is None:
        looked_at = conn.execute(
            "SELECT method FROM player_crosswalk WHERE sport = ? AND source_id = ?",
            (pred["sport"], int(subject_id)),
        ).fetchone()
        return write(
            NO_PROP_CROSSWALK if looked_at else NO_PROP_SUBJECT_QUOTED,
            None, None,
        )

    row = props.line_for(
        conn, pred["game_id"], pred["prop_type"], espn_id,
        pred["line_asked"], pred["model_side"],
    )
    if row is None:
        other = props.line_for(
            conn, pred["game_id"], pred["prop_type"], espn_id,
            pred["line_asked"],
            "under" if pred["model_side"] == "over" else "over",
        )
        return write(
            NO_PROP_THIS_SIDE if other is not None else NO_PROP_AT_RUNG,
            None, None,
        )
    return write(row["source"], row["line"], row["implied_prob"])


def ensure_lines(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict:
    """Fetch whatever published lines exist for these predictions' games.

    NFL lines arrive with the nflverse schedule at load time. MLB and NBA are
    fetched here, from ESPN, AFTER the predictions exist -- which is the whole
    ordering LAW 1 is about, and why this function lives in the quarantine.

    MLB player props are fetched here too, by the same rule and in the same
    place: the prediction rows exist before the request is made.
    """
    from . import espn, props

    if not prediction_ids:
        return {}
    placeholders = ",".join("?" for _ in prediction_ids)
    by_sport: dict[str, list[str]] = {}
    for r in conn.execute(
        f"SELECT DISTINCT sport, game_id FROM predictions WHERE id IN ({placeholders})",
        prediction_ids,
    ):
        by_sport.setdefault(r["sport"], []).append(r["game_id"])

    has_props = {
        r["sport"]
        for r in conn.execute(
            f"SELECT DISTINCT sport FROM predictions WHERE id IN ({placeholders})"
            " AND market_type = 'prop'",
            prediction_ids,
        )
    }

    out = {}
    for sport, game_ids in by_sport.items():
        if sport in espn.LEAGUE_PATH:
            out[sport] = espn.fetch_for_games(conn, sport, game_ids)
        if sport in has_props and sport in props.LEAGUE_PATH:
            out[f"{sport}:props"] = _fetch_prop_days(conn, sport, game_ids)
    return out


#: Columns added to `market_snapshots` after the first databases were built.
#: Applied here rather than in `db.MIGRATIONS` because this package is inside
#: the LAW 1 quarantine and `db` is not: a module on the prediction path may
#: not name a market table in code, and the scan enforces it.
SNAPSHOT_MIGRATIONS = (
    # C3, 2026-08-31: which look this was. Every row that existed before is the
    # first look, which is exactly what the default says, so no stored row
    # changes meaning.
    ("kind", "TEXT NOT NULL DEFAULT 'open_at_predict'"),
)


def ensure_snapshot_columns(conn: sqlite3.Connection) -> list[str]:
    """Add any missing snapshot column. Idempotent, and cheap enough to call often."""
    have = {r["name"] for r in conn.execute("PRAGMA table_info(market_snapshots)")}
    if not have:
        return []                      # fresh database; the schema defines them
    added = []
    for column, decl in SNAPSHOT_MIGRATIONS:
        if column not in have:
            conn.execute(
                f"ALTER TABLE market_snapshots ADD COLUMN {column} {decl}")
            added.append(column)
    if added:
        conn.commit()
    return added


def refresh_quotes(conn: sqlite3.Connection, prediction_ids: list[int],
                   *, ttl=None) -> int:
    """Re-read the published lines behind these predictions, past the cache.

    Used by the drift pass and nowhere else. `ttl` is what makes it a genuinely
    second look: without it the six-hour live window serves the bytes the first
    look already stored, and the two snapshots agree by construction.

    Returns how many quote rows were written, which is a fetch count and not a
    claim about anything.
    """
    # Local, like every market import in this package: at module scope it
    # would put `gridiron.market.espn` into sys.modules before the blind
    # window opened, and the window would refuse to run.
    from . import espn

    if not prediction_ids:
        return 0
    placeholders = ",".join("?" for _ in prediction_ids)
    by_sport: dict[str, list[str]] = {}
    for r in conn.execute(
        f"SELECT DISTINCT sport, game_id FROM predictions WHERE id IN ({placeholders})",
        prediction_ids,
    ):
        by_sport.setdefault(r["sport"], []).append(r["game_id"])

    written = 0
    for sport, game_ids in by_sport.items():
        if sport in espn.LEAGUE_PATH:
            written += espn.fetch_for_games(conn, sport, game_ids,
                                            ttl=ttl)["written"]
    return written


def _fetch_prop_days(conn: sqlite3.Connection, sport: str,
                     game_ids: list[str]) -> dict:
    """Prop quotes for the dates these games fall on, one fetch per date.

    The import is local for the same reason every market import in this project
    is local: at module scope it would put `gridiron.market.props` into
    sys.modules before the blind window opened, and the window would refuse to
    run. It was missing here and the caller's local import did not reach this
    function, so the whole market step raised NameError AFTER the predictions
    were already safely written -- which is the ordering working, but it left
    eight rows with no line until this was fixed.
    """
    from . import props

    placeholders = ",".join("?" for _ in game_ids)
    days = [
        r["d"]
        for r in conn.execute(
            f"SELECT DISTINCT substr(kickoff_utc, 1, 10) AS d FROM games"
            f" WHERE id IN ({placeholders}) AND kickoff_utc IS NOT NULL",
            game_ids,
        )
    ]
    totals = {"days": 0, "written": 0, "unknown_side": 0,
              "unmatched_athlete": 0, "unmatched_game": 0}
    for day in sorted(set(days)):
        settled = conn.execute(
            "SELECT COUNT(*) AS n FROM games WHERE sport = ?"
            " AND substr(kickoff_utc, 1, 10) = ? AND status = 'scheduled'",
            (sport, day),
        ).fetchone()["n"] == 0
        counts = props.fetch_day(
            conn, sport, day.replace("-", ""), settled=settled
        )
        totals["days"] += 1
        for key in ("written", "unknown_side", "unmatched_athlete",
                    "unmatched_game"):
            totals[key] += counts.get(key, 0)
    return totals


def snapshot_many(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict[str, int]:
    counts = {"snapshotted": 0, "already": 0, "no_line": 0}
    counts["fetched"] = ensure_lines(conn, prediction_ids)
    for pid in prediction_ids:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM market_snapshots WHERE prediction_id = ?", (pid,)
        ).fetchone()["n"]
        result = snapshot_prediction(conn, pid)
        if result is None:
            counts["no_line"] += 1
        elif before:
            counts["already"] += 1
        else:
            counts["snapshotted"] += 1
    return counts


def snapshot_for_game(conn: sqlite3.Connection, game_id: str) -> dict[str, int]:
    ids = [
        r["id"]
        for r in conn.execute("SELECT id FROM predictions WHERE game_id = ?", (game_id,))
    ]
    return snapshot_many(conn, ids)


# ---------------------------------------------------------------------------
# read side, for the interface
# ---------------------------------------------------------------------------
# The rule in CLAUDE.md is that only this module reads the market tables. The
# interface needs those numbers, so the accessor lives here rather than the
# read being done inline somewhere on the other side of the wall.

def snapshots_for(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict[int, dict]:
    """First snapshot per prediction, keyed by prediction id."""
    if not prediction_ids:
        return {}
    placeholders = ",".join("?" for _ in prediction_ids)
    rows = conn.execute(
        f"SELECT prediction_id, MIN(id) AS id, fetched_utc, source, line, implied_prob,"
        f" public_pct FROM market_snapshots WHERE prediction_id IN ({placeholders})"
        f" GROUP BY prediction_id",
        prediction_ids,
    ).fetchall()
    return {r["prediction_id"]: dict(r) for r in rows}


def coverage(conn: sqlite3.Connection, *, sport: str) -> dict:
    """How much of ONE sport's record has a market comparison at all (LAW 6)."""
    row = conn.execute(
        "SELECT COUNT(*) AS predictions,"
        " SUM(CASE WHEN s.implied_prob IS NOT NULL THEN 1 ELSE 0 END) AS with_line"
        " FROM predictions p LEFT JOIN market_snapshots s ON s.prediction_id = p.id"
        " WHERE p.sport = ?",
        (sport,),
    ).fetchone()
    descriptor = sources.for_sport(sport)
    return {
        "n": row["predictions"] or 0,
        "sport": sport,
        "with_market_line": row["with_line"] or 0,
        "public_pct_available": 0,
        "source": descriptor.get("name"),
        "licence": descriptor.get("licence"),
        "markets_priced": descriptor.get("markets", []),
        "note": (
            "Player props have no free market line source in any sport, so they "
            "carry a snapshot recording that absence rather than a number. "
            "Public betting percentage is unavailable from any free source and "
            "is never proxied."
        ),
    }
