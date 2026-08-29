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

import math
import sqlite3

from .. import config
from ..db import utcnow
from . import sources

#: Standard deviation of an NFL final margin around the closing spread, in
#: points. The value is stable across seasons at roughly 13; it is used only to
#: turn a spread into a comparable probability so the model and the market can be
#: read on the same axis. It is a stated modelling assumption, not a measurement,
#: and it is written down here rather than buried in an expression.
MARGIN_SD = 13.2

SOURCE = "nflverse/schedules"
NO_PROP_MARKET = "unavailable:no-free-prop-line-source"
NO_SOURCE = "unavailable:no-free-line-source"

#: Standard deviation of a final margin around the closing spread, per sport.
#: NFL's is the long-standing ~13; NBA's is ~11.5 across recent seasons. Both
#: are stated modelling assumptions used only to put the model and the market on
#: one probability axis, and both are written down rather than buried.
MARGIN_SD_BY_SPORT = {"nfl": 13.2, "nba": 11.5}


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
    sd = MARGIN_SD_BY_SPORT.get(sport, MARGIN_SD)
    return norm_cdf((market_spread + line_asked) / sd)


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


def snapshot_prediction(conn: sqlite3.Connection, prediction_id: int) -> dict | None:
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
    pred = conn.execute(
        "SELECT id, sport, game_id, market_type, prop_type, line_asked, model_side"
        " FROM predictions WHERE id = ?",
        (prediction_id,),
    ).fetchone()
    if pred is None:
        raise KeyError(f"no prediction {prediction_id}")

    existing = conn.execute(
        "SELECT * FROM market_snapshots WHERE prediction_id = ? ORDER BY id LIMIT 1",
        (prediction_id,),
    ).fetchone()
    if existing is not None:
        return dict(existing)

    sport = pred["sport"]
    market = pred["prop_type"] or pred["market_type"]
    availability = sources.for_market(sport, market)

    def write(source: str, line, implied) -> dict:
        cur = conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source, line,"
            " implied_prob, public_pct) VALUES (?,?,?,?,?,?)",
            (prediction_id, utcnow(), source, line, implied,
             public_percentage(conn, pred["game_id"])),
        )
        conn.commit()
        return {"id": cur.lastrowid, "source": source, "line": line,
                "implied_prob": implied, "public_pct": None}

    if not availability["available"]:
        return write(
            NO_PROP_MARKET if market in sources.NO_LINE_MARKETS else NO_SOURCE,
            None, None,
        )

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

    if row["spread_line"] is None:
        return None
    implied_yes = implied_cover_probability(row["spread_line"], pred["line_asked"], sport)
    implied = implied_yes if pred["model_side"] == "cover" else 1.0 - implied_yes
    return write(row["source"], row["spread_line"], round(implied, 6))


def ensure_lines(conn: sqlite3.Connection, prediction_ids: list[int]) -> dict:
    """Fetch whatever published lines exist for these predictions' games.

    NFL lines arrive with the nflverse schedule at load time. MLB and NBA are
    fetched here, from ESPN, AFTER the predictions exist -- which is the whole
    ordering LAW 1 is about, and why this function lives in the quarantine.
    """
    from . import espn

    if not prediction_ids:
        return {}
    placeholders = ",".join("?" for _ in prediction_ids)
    by_sport: dict[str, list[str]] = {}
    for r in conn.execute(
        f"SELECT DISTINCT sport, game_id FROM predictions WHERE id IN ({placeholders})",
        prediction_ids,
    ):
        by_sport.setdefault(r["sport"], []).append(r["game_id"])

    out = {}
    for sport, game_ids in by_sport.items():
        if sport in espn.LEAGUE_PATH:
            out[sport] = espn.fetch_for_games(conn, sport, game_ids)
    return out


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
