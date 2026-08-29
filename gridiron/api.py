"""The HTTP layer. Read-only, 127.0.0.1 only, no build step.

Every route is a GET. There is deliberately no verb that writes: predictions are
made by `python -m gridiron.cli predict` and settled by `... resolve`, and the
interface is a window onto the record rather than a way to alter it. That is
LAW 3 expressed as an API surface — "searchable, never editable" is not a
front-end convention here, there is simply nothing to call.

Serving is bound to 127.0.0.1. Not configurable to a public interface.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import calibration, config, db, views

WEB_DIR = config.PACKAGE_ROOT / "web"

app = FastAPI(
    title="Gridiron",
    description="An NFL forecaster that grades itself. Not a betting tool.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# A SQLite connection belongs to the thread that made it, and the ASGI server
# runs sync endpoints on a worker pool, so connections are thread-local. Each is
# opened read-only: the interface cannot write to the record even by accident
# (LAW 3), and `query_only` makes that a property of the handle rather than a
# promise about the code.
_local = threading.local()
_database: Path | None = None


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = db.open_db(_database)
        conn.execute("PRAGMA query_only = ON")
        _local.conn = conn
    return conn


def set_database(path: Path | str | None) -> None:
    """Point the app at a database. Used by the launcher and by tests."""
    global _database
    _database = Path(path) if path is not None else None
    _local.conn = None


@app.get("/api/health")
def health() -> dict:
    try:
        conn = get_conn()
        conn.execute("SELECT 1").fetchone()
    except Exception as exc:  # noqa: BLE001 - health must answer, not raise
        return JSONResponse(
            status_code=503, content={"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        )
    return {
        "ok": True,
        "version": app.version,
        "database": str(_database or config.DB_PATH),
        "kind": db.get_meta(conn, "kind", "live"),
        # How old what we know is, per sport. A loader served entirely from
        # cache reports success and fetches nothing, so "the load ran" is not
        # evidence that the data is current — only the fetch record is.
        "schedule_staleness": views.schedule_staleness(conn),
    }


DEFAULT_SPORT = config.SPORTS[0]


def _sport(value: str | None) -> str:
    """Resolve the sport for a request. Defaulting the QUERY PARAM is fine — a
    browser has to land somewhere — but the value is validated here and passed
    down explicitly, so nothing below ever sees a None (LAW 6)."""
    sport = value or DEFAULT_SPORT
    try:
        return calibration.require_sport(sport, "the request")
    except calibration.CrossSportAggregation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sports")
def sports() -> dict:
    """Every sport with its own counts, for the tab labels. Never a total."""
    payload = views.sports_summary(get_conn())
    calibration.assert_every_figure_has_n(payload)
    return payload


@app.get("/api/meta")
def meta(sport: str | None = None) -> dict:
    return views.meta(get_conn(), _sport(sport))


@app.get("/api/scorecard")
def scorecard(sport: str | None = None) -> dict:
    try:
        return views.scorecard(get_conn(), _sport(sport))
    except calibration.MissingSampleSize as exc:
        # LAW 4. Better a loud 500 than a page of numbers with no sample sizes.
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (calibration.MergedCurve, calibration.CrossSportAggregation) as exc:
        # LAW 6 / no-merged-curves, at the boundary.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/versions")
def versions(sport: str | None = None) -> dict:
    """Factor-set records side by side, within one sport. Never summed."""
    try:
        payload = calibration.version_comparison(get_conn(), sport=_sport(sport))
        calibration.assert_every_figure_has_n(payload)
        return payload
    except calibration.MissingSampleSize as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/week")
def week(sport: str | None = None, season: int | None = None,
         week: int | None = None) -> dict:
    return views.week(get_conn(), _sport(sport), season, week)


@app.get("/api/weeks")
def weeks(sport: str | None = None) -> dict:
    chosen = _sport(sport)
    available = views.available_weeks(get_conn(), chosen)
    return {"n": len(available), "sport": chosen, "weeks": available}


@app.get("/api/over-time")
def over_time(
    sport: str | None = None,
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str = "statistical",
    factor_set_version: str | None = None,
) -> dict:
    """Weekly calibration points, each carrying its own N."""
    try:
        payload = calibration.over_time(
            get_conn(), sport=_sport(sport), market_type=market_type, prop_type=prop_type,
            predictor=predictor, factor_set_version=factor_set_version,
        )
        calibration.assert_every_figure_has_n(payload)
        return payload
    except calibration.MissingSampleSize as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/markets")
def markets(sport: str | None = None) -> dict:
    """Every market of one sport that has its own curve and its own gate."""
    from .market import sources as line_sources

    chosen = _sport(sport)
    all_markets = list(config.SPORT_MARKETS.get(chosen, ()))
    props = list(config.SPORT_PROP_MARKETS.get(chosen, ()))
    return {
        "n": len(all_markets),
        "sport": chosen,
        "markets": all_markets,
        "game_markets": [m for m in all_markets if m not in props],
        "props": props,
        "line_availability": {
            m: line_sources.for_market(chosen, m) for m in all_markets
        },
        "props_per_week": config.PROPS_PER_WEEK,
        "props_per_game": config.PROPS_PER_GAME,
        "note": (
            "Prop markets are listed in descending order of real-world "
            "liquidity, which is the order the slate cap fills them in."
        ),
    }


@app.get("/api/factors")
def factors(sport: str | None = None) -> dict:
    try:
        return views.factors(get_conn(), _sport(sport))
    except calibration.MissingSampleSize as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/history")
def history(
    sport: str | None = None,
    q: str = "",
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    outcome: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    return views.history(
        get_conn(),
        sport=_sport(sport),
        query=q,
        market_type=market_type,
        prop_type=prop_type,
        predictor=predictor,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )


@app.get("/api/prediction/{prediction_id}")
def prediction(prediction_id: int) -> dict:
    detail = views.prediction_detail(get_conn(), prediction_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"no prediction {prediction_id}")
    return detail


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def serve(host: str = config.HOST, port: int = config.PORT, *, log_level: str = "info") -> None:
    import uvicorn

    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(
            f"refusing to bind {host!r}: Gridiron serves 127.0.0.1 only"
        )
    uvicorn.run(app, host=host, port=port, log_level=log_level)
