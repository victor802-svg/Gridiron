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

from .blind import blind_window, forget_market_module
from .model import predict


def run_week(
    conn: sqlite3.Connection,
    season: int,
    week: int,
    *,
    include_props: bool = True,
    use_llm: bool = True,
    llm_client=None,
    snapshot: bool = True,
    progress=None,
) -> dict:
    """Predict a week blind, then attach the market to what was written."""
    forget_market_module()

    with blind_window():
        run = predict.predict_week(
            conn,
            season,
            week,
            include_props=include_props,
            use_llm=use_llm,
            llm_client=llm_client,
            progress=progress,
        )

    result = {
        "season": season,
        "week": week,
        "written": len(run.written),
        "by_predictor": {},
        "skipped": run.skipped,
        "degradations": run.degradations,
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
