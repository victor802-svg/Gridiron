"""The ordering, in one place.

This is the only module that touches both halves of the system, and it exists
so the ordering LAW 1 describes is visible as a shape on one page:

    with blind_window():          # gridiron.market cannot even be imported
        run = predict_week(...)   # probabilities computed AND WRITTEN
                                  # window closes
    from .market import lines     # ... only now does the market exist
    lines.snapshot_many(...)      # attached to rows that already exist

The market import is inside the function on purpose. If it were at module
scope, `gridiron.market` would be in `sys.modules` before the window opened and
`blind_window()` would refuse to run at all — which is exactly the failure it is
there to produce.
"""

from __future__ import annotations

import sqlite3

from . import config
from .blind import blind_window, forget_market_module
from .model import predict


#: A blank line between paragraphs of a refusal. Written as a name because an
#: escape inside an f-string has collapsed into a real line break twice in this
#: codebase, and a syntax error here stops every prediction.
_GAP = chr(10) + chr(10)


class SlateAlreadyAnswered(RuntimeError):
    """A slate this factor set has already forecast, and why that is refused."""


def already_answered(conn, sport: str, season: int, week: int,
                     *, include_props: bool = True) -> dict:
    """Has this factor set already answered this slate?

    THE FACTOR SET IS THE ESCAPE HATCH, deliberately. A different model asking
    the same question is a different forecast and the record keeps both, with
    the version on every row saying which produced which. The same model
    asking twice is a duplicate, and only the later one counts.
    """
    rows = conn.execute(
        "SELECT p.market_type, COUNT(*) AS n, MIN(p.created_utc) AS first_written"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.sport = ? AND g.season = ? AND g.week = ?"
        "   AND p.factor_set_version = ?"
        " GROUP BY p.market_type",
        (sport, season, week, config.FACTOR_SET_VERSION)).fetchall()
    answered = {r["market_type"]: r["n"] for r in rows}
    written = sum(answered.values())

    # PER MARKET, NOT PER SLATE, and the difference is a market that does not
    # exist yet. The run line and the total were added on 2026-09-02 to slates
    # whose moneyline had already been answered that morning; refusing the
    # whole slate would have meant a new market could never be asked about a
    # day the old ones had covered, which is not what "answered once" means.
    #
    # `predict` already skips a question that has a row, so a run that adds
    # only a new market writes only the new market.
    from . import sports

    # WHAT THIS RUN WOULD ASK, not what the sport declares. A run with
    # `include_props=False` asks no props, so an unanswered prop market is not
    # a gap it could fill -- counting it as one would mean such a run could
    # never be refused, however many times it repeated itself.
    expected = set()
    for market in sports.get(sport).markets():
        is_prop = market in config.SPORT_PROP_MARKETS.get(sport, ())
        if is_prop and not include_props:
            continue
        expected.add("prop" if is_prop else market)
    missing = sorted(expected - set(answered))
    return {
        "written": written,
        "by_market": answered,
        "missing": missing,
        "first_written": min((r["first_written"] for r in rows), default=""),
        "factor_set_version": config.FACTOR_SET_VERSION,
        "refuse": written > 0 and not missing,
    }


def run_slate(
    conn: sqlite3.Connection,
    sport: str,
    season: int,
    week: int,
    *,
    include_props: bool = True,
    use_llm: bool = True,
    llm_client=None,
    snapshot: bool = True,
    progress=None,
) -> dict:
    """Predict one slate blind, then attach the market to what was written."""
    already = already_answered(conn, sport, season, week,
                               include_props=include_props)
    if already["refuse"]:
        # A SLATE IS ANSWERED ONCE (ruling R4, 2026-09-02).
        #
        # `predict:nfl` ran twice on 2026-08-29 and wrote a full second set of
        # week 1 forecasts. Nothing stopped it, nothing said so, and the
        # duplicate surfaced days later as every game appearing twice on the
        # Picks page. The rows are the record and stay; what changes is that
        # it cannot happen again.
        #
        # A CHANGED FACTOR SET IS THE EXCEPTION, and it is a real one: a
        # different model asking the same question is a different forecast,
        # and the record keeps both with their versions attached.
        raise SlateAlreadyAnswered(
            f"{sport} {season} slate {week} already has {already['written']} "
            f"forecasts in every market it asks "
            f"({', '.join(sorted(already['by_market']))}), written "
            f"{already['first_written'][:16]} under factor set "
            f"{already['factor_set_version']!r}. A slate is answered once. "
            f"Nothing was written." + _GAP
            + "Re-answering it would put two forecasts on every question, and "
            "only the later one would count -- which is what happened on "
            "2026-08-29 and took three days to notice." + _GAP
            + f"The exception is a changed factor set: this run is on "
            f"{config.FACTOR_SET_VERSION!r}, the same one. If you mean to "
            f"re-answer under a new factor set, declare it first."
        )
    forget_market_module()

    with blind_window():
        run = predict.predict_slate(
            conn,
            sport,
            season,
            week,
            include_props=include_props,
            use_llm=use_llm,
            llm_client=llm_client,
            progress=progress,
        )

    result = {
        "sport": sport,
        "season": season,
        "week": week,
        "written": len(run.written),
        "by_predictor": {},
        "skipped": run.skipped,
        "degradations": run.degradations,
        # Carried out of the blind run so a slate that came in under its cap can
        # say why on the panel rather than looking like a quiet failure.
        "below_floor": run.below_floor,
        # A MEASUREMENT COUNT, never a prediction count. Reported separately
        # and named so it cannot be added to the one above by mistake.
        "rungs_logged": run.rungs_logged,
        "snapshots": None,
    }
    for w in run.written:
        result["by_predictor"][w.predictor] = result["by_predictor"].get(w.predictor, 0) + 1

    if snapshot:
        # Step 5. The window is closed; the rows exist; only now is there a line.
        from .market import lines

        if progress:
            progress("blind window closed - fetching market lines")
        result["snapshots"] = lines.snapshot_many(conn, run.prediction_ids)

    return result


def run_week(conn: sqlite3.Connection, season: int, week: int, **kwargs) -> dict:
    """NFL-shaped call, kept for existing callers and tests."""
    return run_slate(conn, "nfl", season, week, **kwargs)
