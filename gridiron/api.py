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

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import (audit, auth, buildinfo, calibration, config, db, language,
               settings, views)

WEB_DIR = config.PACKAGE_ROOT / "web"

app = FastAPI(
    title="Gridiron",
    description="An NFL forecaster that grades itself. Not a betting tool.",
    version="0.1.0",
    # These describe the entire surface, so they sit BEHIND the gate like
    # everything else. `auth.path_is_open` does not list them, and the
    # middleware closes anything not on that list.
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


def get_auth_conn() -> sqlite3.Connection:
    """A WRITABLE handle, used only by the sign-in paths.

    The record's handle stays `query_only`, so the interface still cannot write
    a prediction even by accident (LAW 3). Sessions, failed attempts and handoff
    nonces are not the record, and they have to be written somewhere that
    survives a restart — a backoff held in memory is a backoff you get past by
    restarting the process.

    Nothing outside `gridiron.auth` is given this connection, and the LAW 3
    triggers on `predictions` remain the backstop if anything ever tries.
    """
    conn = getattr(_local, "auth_conn", None)
    if conn is None:
        conn = db.open_db(_database)
        _local.auth_conn = conn
    return conn


def get_settings_conn() -> sqlite3.Connection:
    """A WRITABLE handle, used only to append an operational setting.

    Same argument as `get_auth_conn`, and the same boundary. The record's
    handle stays `query_only`, so the interface cannot write a prediction even
    by accident (LAW 3). A settings row is not the record: it is when the
    baseball task runs and whether failure notifications are on.

    THE FENCE IS IN `settings.EDITABLE`, not here. This connection could write
    anything the schema allows; what stops it is that the only code given it
    refuses every name outside a closed list, and the `settings` table's own
    triggers refuse an UPDATE or a DELETE on what it has already written.
    """
    conn = getattr(_local, "settings_conn", None)
    if conn is None:
        conn = db.open_db(_database)
        _local.settings_conn = conn
    return conn


def set_database(path: Path | str | None) -> None:
    """Point the app at a database. Used by the launcher and by tests."""
    global _database
    _database = Path(path) if path is not None else None
    _local.conn = None
    _local.auth_conn = None
    _local.settings_conn = None


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

@app.middleware("http")
async def require_session(request: Request, call_next):
    """Everything is closed unless it is on the small open list.

    ENUMERATED FROM THE APP, not hardcoded: `auth.path_is_open` decides, and a
    route added tomorrow is closed by default because it is simply not on the
    list. The opposite arrangement — a list of protected paths — fails open, and
    the failure is invisible until someone reads the whole route table.

    /api/docs, /redoc and /openapi.json are NOT open. They describe the entire
    surface, which is exactly what an unauthenticated caller should not have.
    """
    path = request.url.path
    if auth.path_is_open(path):
        return await call_next(request)

    if auth.read_token() is None:
        # Refuse rather than fall open. An appliance with no token configured is
        # not "unprotected by choice", it is unconfigured, and serving the
        # record to anyone who asks would be the worst possible default.
        return JSONResponse(
            status_code=503,
            content={
                "error": "no access token is configured",
                "fix": "run: python tools/make_token.py",
            },
        )

    if auth.session_is_valid(get_auth_conn(), request.cookies.get(auth.COOKIE_NAME)):
        return await call_next(request)

    # A browser asking for a page gets the login page; anything else gets 401.
    accepts_html = "text/html" in (request.headers.get("accept") or "")
    if accepts_html and request.method == "GET":
        return RedirectResponse("/login", status_code=303)
    return JSONResponse(status_code=401, content={"error": "authentication required"})


@app.get("/sw.js")
def service_worker() -> FileResponse:
    """Served from the ROOT, not /static/, because a worker's scope is limited
    to the directory it is served from. At /static/sw.js it could only control
    /static/, which is the one part of the app that does not need it."""
    return FileResponse(
        WEB_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/login-glance")
def login_glance() -> dict:
    """COUNTS AND RECORDS for the sign-in screen, and nothing else.

    OPEN BY DESIGN and named in `auth.OPEN_PATHS`, which is a decision rather
    than an oversight: it tells the operator the appliance is alive and
    working before they type anything. `audit.check_the_login_page_shows_no_pick`
    runs inside `views.login_glance`, so a side, a probability, a team with a
    line or a rate cannot reach this route.
    """
    return views.login_glance(get_conn())


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(WEB_DIR / "login.html")


@app.post("/auth/login")
async def login(request: Request) -> JSONResponse:
    """Exchange the token for a session cookie.

    The cookie is set BY THE SERVER, with HttpOnly. JavaScript cannot set an
    HttpOnly cookie — `document.cookie` accepts the string and silently drops
    the flag, leaving a readable cookie that looks correct in every test that
    only checks the name. The handoff is a real POST for that reason.
    """
    conn = get_auth_conn()
    ip = request.client.host if request.client else "unknown"

    wait = auth.backoff_seconds(conn, ip)
    if wait > 0:
        return JSONResponse(
            status_code=429,
            content={"error": "too many attempts", "retry_after_seconds": wait},
            headers={"Retry-After": str(wait)},
        )

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - a malformed body is just a failed attempt
        body = {}
    candidate = (body.get("token") or "").strip()

    if not auth.token_matches(candidate):
        auth.record_failure(conn, ip, "bad token")
        return JSONResponse(status_code=401, content={"error": "that token is not valid"})

    session_id = auth.create_session(conn, user_agent=request.headers.get("user-agent"))
    response = JSONResponse(content={"ok": True})
    _set_session_cookie(response, session_id, request)
    return response


@app.get("/auth/handoff")
async def handoff(request: Request, n: str = Query(default="")):
    """The desktop launcher's single-use exchange.

    `n` is a NONCE, not the token: random, valid once, expiring in sixty
    seconds, and useless the moment it is redeemed. This is how `cli serve` can
    open an already-signed-in browser without the secret ever appearing in an
    address bar or a browser history.
    """
    conn = get_auth_conn()
    if not auth.redeem_handoff(conn, n):
        ip = request.client.host if request.client else "unknown"
        auth.record_failure(conn, ip, "bad or spent handoff nonce")
        return RedirectResponse("/login", status_code=303)
    session_id = auth.create_session(conn, user_agent=request.headers.get("user-agent"))
    response = RedirectResponse("/", status_code=303)
    _set_session_cookie(response, session_id, request)
    return response


@app.post("/auth/logout")
async def logout(request: Request) -> JSONResponse:
    """Sign out. `everywhere=true` drops every session, not just this one.

    Still ONE write route (`/auth/logout`), so the count in
    `test_no_route_can_write_to_the_record` does not move: signing out
    everywhere is the same act on a wider scope, not a new power.
    """
    conn = get_auth_conn()
    everywhere = request.query_params.get("everywhere") == "true"
    dropped = (auth.drop_all_sessions(conn) if everywhere else None)
    if not everywhere:
        auth.drop_session(conn, request.cookies.get(auth.COOKIE_NAME))
    response = JSONResponse(content={
        "ok": True,
        "line": (language.signed_out_line(dropped) if everywhere
                 else "Signed out on this device."),
    })
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return response


def _set_session_cookie(response, session_id: str, request: Request) -> None:
    """HttpOnly, SameSite=Strict, Secure over TLS.

    `secure` is conditional because the desktop case is plain http on
    127.0.0.1, where a Secure cookie would simply never be stored. Over the
    tailnet (P4) the scheme is https and the flag is set.
    """
    response.set_cookie(
        auth.COOKIE_NAME,
        session_id,
        max_age=auth.SESSION_HOURS * 3600,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/",
    )


@app.get("/api/health")
def health() -> dict:
    try:
        conn = get_conn()
        conn.execute("SELECT 1").fetchone()
    except Exception:  # noqa: BLE001 - health must answer, not raise
        # The EXCEPTION TEXT IS NOT RETURNED. A sqlite error carries the full
        # database path, so returning it from the one unauthenticated route
        # would leak the filesystem layout to anyone who could make the query
        # fail. The operator reads the real error in the server log.
        return JSONResponse(status_code=503, content={"ok": False})
    # LIVENESS ONLY. This is the one route that answers before authentication,
    # so it must carry NO data: not the database path, not the record's kind,
    # not counts, not staleness. Everything it used to return moved behind the
    # gate into /api/schedule, which is where a person looks anyway. An open
    # endpoint that reports what is in the database is a data leak with a
    # reassuring name.
    # THE BUILD, so the launcher can notice it is about to attach to an older
    # one (GRIDIRON_13 P6). Same class of thing as the version already here:
    # it says which code is answering, and that is precisely what a caller
    # must know in order to refuse to trust it.
    return {"ok": True, "version": app.version,
            "build": buildinfo.build_id()}


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


@app.get("/api/schedule")
def schedule() -> dict:
    """What the scheduler has and has not done.

    Not sport-scoped, and deliberately so: this reports on the APPLIANCE, not on
    the record. LAW 6 forbids mixing sports' predictions into one figure; it says
    nothing about whether a cron job fired, and pretending otherwise would mean
    four separate panels that each answer half the question "did it run".
    """
    from . import tasks

    return tasks.status(get_conn())


@app.get("/api/digest")
def digest(request: Request, sport: str | None = None,
           day: str | None = None, peek: bool = False) -> dict:
    """Since you last looked, for one sport.

    THE READ USES THE `query_only` CONNECTION. The digest summarises the record
    and must not be able to touch it: `get_conn()` is opened
    `PRAGMA query_only = ON`, so this path holds no write capability at all
    even if a future edit asked it to (LAW 3). Advancing the device's marker is
    a separate statement on the separate writable handle, and it happens after
    the digest has been computed against the OLD value.

    `day` returns one calendar day and never moves the marker, which is what
    makes a digest linkable. `peek` reads without advancing, for tests and for
    anyone who wants to look twice.
    """
    chosen = _sport(sport)
    if day:
        return views.digest(get_conn(), sport=chosen, day=day)

    session_id = request.cookies.get(auth.COOKIE_NAME)
    if peek:
        since = views.seen_marker(get_conn(), session_id, chosen)
    else:
        since = views.mark_seen(get_auth_conn(), session_id, chosen)
    return views.digest(get_conn(), sport=chosen, since=since)


@app.get("/digest")
def digest_page() -> FileResponse:
    """A permanent, linkable page. The front-page panel is ephemeral by design
    - it advances the marker - so the same content has a URL that does not."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/record-line")
def record_line(sport: str | None = None) -> dict:
    """The active sport's settled record for the header. One sport, never a sum."""
    return views.season_record(get_conn(), _sport(sport))


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
         week: int | None = None, forecaster: str | None = None,
         early_view: bool = False) -> dict:
    """The slate, from ONE forecaster's point of view (GRIDIRON_14).

    An unknown name is not corrected to the default: `views.week` returns that
    forecaster's empty list and says whose picks are missing, which is the
    honest answer to a question about a forecaster that made none.
    """
    payload = views.week(get_conn(), _sport(sport), season, week, forecaster,
                         early_view=early_view)
    # PICKS OPENS FILTERED (R2), so the count line is the only thing telling a
    # reader the slate is bigger than what they see. A loud 500 beats a page
    # that makes a narrow band look like a quiet night -- the same trade LAW
    # 4's sample-size check already makes on the routes above.
    faults = audit.tier_count_faults(payload)
    # THE COVERAGE LINE IS A CLAIM ABOUT THE ROW (S2). A card that says it
    # rested on everything while its own vector records an absence is
    # provenance a reader would act on, and it would be false.
    faults += audit.coverage_line_faults(payload.get("cards") or [])
    if faults:
        raise HTTPException(status_code=500, detail="; ".join(faults))
    return payload


@app.get("/api/live")
def live_slate(sport: str | None = None, season: int | None = None,
               week: int | None = None) -> dict:
    """The scores only. Small enough to ask for every sixty seconds."""
    return views.live_slate(get_conn(), _sport(sport), season, week)


@app.get("/api/settings")
def read_settings(request: Request) -> dict:
    """The settings page: what may be changed, what may only be read.

    AUTHENTICATED BECAUSE IT WAS ADDED. `require_session` closes every path
    not on `auth.path_is_open`, so this is protected by default rather than by
    somebody remembering.
    """
    payload = views.settings_page(get_conn())
    # THE FORM TOKEN TRAVELS WITH THE FORM. Derived from the session under the
    # access token, so it is unforgeable without the token and dies with the
    # session -- no table to expire and clean up.
    payload["csrf"] = auth.csrf_token(request.cookies.get(auth.COOKIE_NAME))
    return payload


@app.post("/api/settings")
async def write_setting(request: Request) -> dict:
    """Change one operational setting, and say what actually happened.

    THREE LOCKS, and each is here for its own reason. The SESSION closes the
    route (the middleware, by default). The CSRF token closes a cross-site
    POST that a browser might otherwise send with the cookie attached --
    SameSite=Strict already refuses that, and this is the lock that does not
    depend on somebody else's software honouring a promise. The FENCE in
    `settings.EDITABLE` closes everything that is not an operational knob.
    """
    session_id = request.cookies.get(auth.COOKIE_NAME)
    body = await request.json()
    if not auth.csrf_is_valid(session_id, request.headers.get(auth.CSRF_HEADER)):
        raise HTTPException(
            status_code=403,
            detail=("This form is out of date. Reload the page and try again "
                    "-- the app refuses a settings change that did not come "
                    "from a form it issued."))
    name = str(body.get("name") or "")
    raw = str(body.get("value") if body.get("value") is not None else "")
    try:
        return views.change_setting(get_settings_conn(), name=name, raw=raw)
    except settings.SettingRefused as exc:
        # 409: well formed, and the app will not take it. The operator reads
        # the reason in the words it was written in.
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
        # PLAIN WORDS: the browser renders these, never the raw names. Served
        # from the server so there is one vocabulary rather than one per page -
        # the market dropdowns were the last place `rushing_yards` was visible.
        "labels": {m: language.humanise(m) for m in all_markets},
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


@app.get("/api/calendar")
def calendar(sport: str | None = None) -> dict:
    """The season as a shape: one square per day, for ONE sport (LAW 6)."""
    return views.results_calendar(get_conn(), sport=_sport(sport))


@app.get("/api/history")
def history(
    sport: str | None = None,
    q: str = "",
    market_type: str | None = None,
    prop_type: str | None = None,
    predictor: str | None = None,
    outcome: str | None = None,
    day: str | None = None,
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
        day=day,
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


def desktop_handoff_url(host: str = config.HOST, port: int = config.PORT) -> str | None:
    """A one-time URL that opens an already-signed-in browser.

    THE TOKEN IS NOT IN IT. The nonce is random, single-use, and expires in
    sixty seconds; redeeming it is what mints the session. This is the whole
    reason the nonce exists — otherwise the only way to open a signed-in browser
    from a launcher is to put the secret in the address bar, where it lands in
    the browser's history and in any screen recording.

    Returns None when no token is configured, because there is then nothing to
    hand off and the caller should say so rather than opening a broken page.
    """
    if auth.read_token() is None:
        return None
    nonce = auth.mint_handoff(db.open_db(_database))
    return f"http://{host}:{port}/auth/handoff?n={nonce}"


def serve(host: str = config.HOST, port: int = config.PORT, *, log_level: str = "info",
          open_browser: bool = False) -> None:
    import uvicorn

    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(
            f"refusing to bind {host!r}: Gridiron serves 127.0.0.1 only. "
            "To reach it from another device use `tailscale serve`, which "
            "publishes it to your tailnet over TLS without opening a port to "
            "the internet."
        )
    if open_browser:
        import threading as _threading
        import webbrowser

        url = desktop_handoff_url(host, port)
        if url is None:
            print("No access token configured. Run: python tools/make_token.py")
        else:
            # Opened after a short delay so the server is listening. The URL is
            # never printed: a one-time nonce is not a secret worth guarding
            # forever, but there is no reason to put it in a terminal log.
            _threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level=log_level)
